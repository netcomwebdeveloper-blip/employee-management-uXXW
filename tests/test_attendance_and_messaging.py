from datetime import date, time, timedelta, datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.utils import timezone
from django.contrib.auth.models import User
from apps.departments.models import Department, Designation
from apps.employees.models import Employee
from apps.attendance.models import Attendance, AttendanceAuditLog
from apps.attendance.services import reset_daily_missed_punch_in_status, mark_employee_official_duty
from apps.leave_management.models import LeaveRequest, HRNotification
from apps.payroll.models import SalaryStructure, PayrollRecord
from apps.payroll.views import calculate_payroll_for_employee
from unittest.mock import patch


class AttendanceAndMessagingTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Department & Designation
        self.dept = Department.objects.create(name='Operations', code='OPS')
        self.desig = Designation.objects.create(department=self.dept, title='Specialist')

        # Admin user
        self.admin_user = User.objects.create_superuser('NETCOM', 'admin@netcom.com', 'Netcom@2026@Netcom')
        self.admin_profile = Employee.objects.create(
            user=self.admin_user,
            employee_code='NETCOM001',
            role='ADMIN',
            department=self.dept,
            designation=self.desig,
            casual_leave_balance=10
        )

        # HR user
        self.hr_user = User.objects.create_user('hr_user', 'hr@example.com', 'hr12345')
        self.hr_profile = Employee.objects.create(
            user=self.hr_user,
            employee_code='HR001',
            role='HR',
            department=self.dept,
            designation=self.desig,
            casual_leave_balance=10
        )

        # Employee user
        self.emp_user = User.objects.create_user('emp_john', 'john@example.com', 'john12345')
        self.emp_profile = Employee.objects.create(
            user=self.emp_user,
            employee_code='EMP101',
            role='EMPLOYEE',
            department=self.dept,
            designation=self.desig,
            basic_salary=Decimal('30000.00'),
            casual_leave_balance=1
        )

        today = timezone.localdate()
        from apps.leave_management.models import MonthlyLeaveCredit
        MonthlyLeaveCredit.objects.get_or_create(
            employee=self.emp_profile,
            year=today.year,
            month=today.month,
            defaults={'casual_added': 1}
        )

        # Salary Structure for payroll
        SalaryStructure.objects.create(
            employee=self.emp_profile,
            basic_salary=Decimal('30000.00'),
            hra=Decimal('5000.00'),
            allowances=Decimal('5000.00'),
            pf_deduction=Decimal('1800.00'),
            tax_deduction=Decimal('200.00')
        )

    def test_mandatory_punch_in_and_12pm_reset(self):
        today = timezone.localdate()
        past_date = today - timedelta(days=2)

        # Create historical attendance record (must NEVER be altered or deleted)
        past_att = Attendance.objects.create(
            employee=self.emp_profile,
            date=past_date,
            status='Present',
            in_time=time(9, 30),
            out_time=time(18, 30)
        )

        # Before 12:00 PM, reset does not flag today's attendance as Missed Punch-In
        with patch('apps.attendance.services.timezone.localtime') as mock_time:
            # Mock 10:00 AM local time
            mock_time.return_value = datetime(today.year, today.month, today.day, 10, 0, 0)
            reset_daily_missed_punch_in_status(target_date=today)

            today_att = Attendance.objects.filter(employee=self.emp_profile, date=today).first()
            if today_att:
                self.assertNotEqual(today_att.status, 'Missed Punch-In')

        # After 12:00 PM, unpunched employee is flagged as Missed Punch-In
        with patch('apps.attendance.services.timezone.localtime') as mock_time:
            # Mock 12:01 PM local time
            mock_time.return_value = datetime(today.year, today.month, today.day, 12, 1, 0)
            count = reset_daily_missed_punch_in_status(target_date=today)
            self.assertGreaterEqual(count, 1)

            today_att = Attendance.objects.get(employee=self.emp_profile, date=today)
            self.assertEqual(today_att.status, 'Missed Punch-In')
            self.assertTrue(today_att.is_missed_punch_in)

        # Verify historical records were NOT altered or deleted
        past_att_refreshed = Attendance.objects.get(id=past_att.id)
        self.assertEqual(past_att_refreshed.status, 'Present')
        self.assertEqual(past_att_refreshed.date, past_date)

    def test_missing_punch_out_handling_and_payroll_exclusion(self):
        today = timezone.localdate()

        # Employee punches in at 09:15 but misses punch-out
        att = Attendance.objects.create(
            employee=self.emp_profile,
            date=today,
            in_time=time(9, 15)
        )

        # Verify status and calculations
        self.assertEqual(att.status, 'Missing Punch-Out')
        self.assertTrue(att.is_missing_punch_out)
        self.assertEqual(att.total_work_minutes, 0)
        self.assertIn('Incomplete', att.total_work_time)
        self.assertFalse(att.is_full_day)
        self.assertFalse(att.is_half_day)

        # Verify payroll excludes missing punch-out day and does not finalize salary on incomplete data
        payroll_data = calculate_payroll_for_employee(self.emp_profile, today.year, today.month)
        self.assertEqual(payroll_data['full_days'], 0)
        self.assertEqual(payroll_data['half_days'], 0)
        self.assertIn('missing punch-out', payroll_data['remarks'])

        # Verify employee dashboard prominently instructs employee to contact HR
        self.client.login(username='emp_john', password='john12345')
        response = self.client.get('/dashboard/employee/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Punch-Out Missing')
        self.assertContains(response, 'Please contact HR to enter or correct your missing punch-out time')
        self.client.logout()

    def test_official_duty_marking_and_payroll(self):
        target_date = timezone.localdate() - timedelta(days=1)

        # First give employee a leave on that date that reduced balance
        initial_balance = self.emp_profile.casual_leave_balance  # 1
        LeaveRequest.objects.create(
            employee=self.emp_profile,
            leave_type='Casual Leave',
            from_date=target_date,
            to_date=target_date,
            status='Approved',
            total_days=1
        )
        self.emp_profile.casual_leave_balance = 0
        self.emp_profile.save()
        self.assertEqual(self.emp_profile.casual_leave_balance, 0)

        # HR marks employee as on Official Office Duty
        self.client.login(username='hr_user', password='hr12345')
        response = self.client.post('/dashboard/', {
            'action': 'mark_official_duty',
            'employee_id': self.emp_profile.id,
            'date': target_date.strftime('%Y-%m-%d'),
            'duty_title': 'Client Site Technical Audit',
            'notes': 'Official deployment at client premise'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.client.logout()

        # Check attendance record (marked as Present instead of Leave, with official duty properties)
        att = Attendance.objects.get(employee=self.emp_profile, date=target_date)
        self.assertEqual(att.status, 'Present')
        self.assertTrue(att.is_official_duty)
        self.assertTrue(att.is_full_day)
        self.assertEqual(att.total_work_minutes, 540)  # 9 hours credited

        # Check leave restoration
        self.emp_profile.refresh_from_db()
        self.assertEqual(self.emp_profile.casual_leave_balance, initial_balance)  # Restored to 1

        # Check payroll credits full day Present with zero deduction
        payroll_data = calculate_payroll_for_employee(self.emp_profile, target_date.year, target_date.month)
        self.assertEqual(payroll_data['full_days'], 1)
        self.assertEqual(payroll_data['absent_deduction'], Decimal('0.00'))

    def test_unauthorized_official_duty_rejected(self):
        target_date = timezone.localdate()
        # Non-HR/Admin employee attempts to mark official duty
        self.client.login(username='emp_john', password='john12345')
        response = self.client.post('/attendance/mark-official-duty/', {
            'employee_id': self.emp_profile.id,
            'date': target_date.strftime('%Y-%m-%d'),
            'duty_title': 'Self assigned'
        }, follow=True)
        # Should be forbidden or redirected
        att = Attendance.objects.filter(employee=self.emp_profile, date=target_date, status='Official Duty').first()
        self.assertIsNone(att)
        self.client.logout()

    def test_send_message_feature_between_employee_and_hr(self):
        # 1. Employee sends enquiry message to HR
        self.client.login(username='emp_john', password='john12345')
        response = self.client.post('/dashboard/employee/', {
            'action': 'send_hr_message',
            'category': 'Attendance Regularization / Missing Punch-Out',
            'subject': 'Missing Punch-Out Correction',
            'message': 'Dear HR, I missed my punch out yesterday due to emergency client visit. Kindly update my out time to 18:30.'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your message has been sent directly to the HR department.')
        self.client.logout()

        # Verify message created as HRNotification
        notif = HRNotification.objects.filter(recipient_role='HR', title__contains='Missing Punch-Out Correction').first()
        self.assertIsNotNone(notif)
        self.assertIn('Missing Punch-Out Correction', notif.title)
        self.assertIn('18:30', notif.message)
        self.assertFalse(notif.is_read)

        # 2. HR views message on HR Dashboard
        self.client.login(username='hr_user', password='hr12345')
        hr_response = self.client.get('/dashboard/hr/')
        self.assertEqual(hr_response.status_code, 200)
        self.assertContains(hr_response, 'Missing Punch-Out Correction')
        self.assertContains(hr_response, 'Dear HR, I missed my punch out yesterday')

        # 3. HR toggles message as read / reviewed
        toggle_response = self.client.post('/dashboard/', {
            'action': 'toggle_notification_read',
            'notification_id': notif.id
        }, follow=True)
        self.assertEqual(toggle_response.status_code, 200)

        notif.refresh_from_db()
        self.assertTrue(notif.is_read)
        self.client.logout()
