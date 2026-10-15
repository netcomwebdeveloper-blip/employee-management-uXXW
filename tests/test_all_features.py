import base64
from datetime import date, time, timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.departments.models import Department, Designation
from apps.employees.models import Employee
from apps.attendance.models import Attendance, DailyWork, AttendanceAuditLog, BiometricDevice, DailyWorkPlan
from apps.attendance.biometric_service import test_device_connection, sync_biometric_device
from apps.attendance.services import check_and_restore_casual_leave_on_attendance
from apps.leave_management.models import LeaveRequest, HRNotification
from apps.payroll.models import SalaryStructure, PayrollRecord
from apps.payroll.views import calculate_payroll_for_employee
from apps.dashboard.models import DashboardBanner, DashboardPopup



class ComprehensiveSystemTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Create Department and Designation
        self.dept = Department.objects.create(name='Technology', code='TECH')
        self.desig = Designation.objects.create(department=self.dept, title='Software Engineer')

        # Admin user (NETCOM)
        self.admin_user = User.objects.create_superuser('NETCOM', 'admin@netcom.com', 'Netcom@2026@Netcom')
        self.admin_profile = Employee.objects.create(
            user=self.admin_user,
            employee_code='NETCOM001',
            role='ADMIN',
            department=self.dept,
            designation=self.desig,
            casual_leave_balance=1
        )

        # HR user
        self.hr_user = User.objects.create_user('hr_user', 'hr@example.com', 'hr12345')
        self.hr_profile = Employee.objects.create(
            user=self.hr_user,
            employee_code='HR001',
            role='HR',
            department=self.dept,
            designation=self.desig,
            casual_leave_balance=1
        )

        # Employee user
        self.emp_user = User.objects.create_user('emp_user', 'emp@example.com', 'emp12345')
        self.emp_profile = Employee.objects.create(
            user=self.emp_user,
            employee_code='EMP001',
            role='EMPLOYEE',
            department=self.dept,
            designation=self.desig,
            basic_salary=30000.00,
            casual_leave_balance=1
        )

    def test_login_url_preservation_and_auth(self):
        # 1. Exact /login/ route check
        r_get = self.client.get('/login/')
        self.assertEqual(r_get.status_code, 200)

        # 2. Login with specified NETCOM credentials
        r_post = self.client.post('/login/', {
            'username': 'NETCOM',
            'password': 'Netcom@2026@Netcom'
        })
        self.assertEqual(r_post.status_code, 302)
        self.client.logout()

    def test_dashboard_titles_across_the_system(self):
        # Admin dashboard
        self.client.login(username='NETCOM', password='Netcom@2026@Netcom')
        r = self.client.get('/dashboard/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Netcom Admin Dashboard')
        self.assertNotContains(r, 'Biometric Machine CSV Import')
        self.client.logout()

        # HR dashboard
        self.client.login(username='hr_user', password='hr12345')
        r = self.client.get('/dashboard/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Netcom HR Dashboard')
        self.assertNotContains(r, 'Biometric Machine CSV Import')
        self.client.logout()

        # Employee dashboard
        self.client.login(username='emp_user', password='emp12345')
        r = self.client.get('/dashboard/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Netcom Employee Dashboard')
        self.client.logout()

    def test_banner_upload_and_popup_display(self):
        # Admin uploads new banner
        self.client.login(username='NETCOM', password='Netcom@2026@Netcom')
        fake_img = SimpleUploadedFile("banner.jpg", b"fake_banner_image_bytes", content_type="image/jpeg")

        r = self.client.post('/dashboard/', {
            'action': 'upload_banner',
            'banner_title': 'Annual Technology Summit 2026',
            'banner_image': fake_img
        })
        self.assertEqual(r.status_code, 302)

        banner = DashboardBanner.get_active_banner()
        self.assertIsNotNone(banner)
        self.assertEqual(banner.title, 'Annual Technology Summit 2026')
        self.assertTrue(banner.is_active)
        self.client.logout()

        # Employee logs in and enters dashboard -> popup modal exists in template
        self.client.login(username='emp_user', password='emp12345')
        r_emp = self.client.get('/dashboard/')
        self.assertEqual(r_emp.status_code, 200)
        self.assertContains(r_emp, 'employeeAnnouncementModal')
        self.assertContains(r_emp, 'Close Announcement')
        self.assertContains(r_emp, 'Annual Technology Summit 2026')
        self.client.logout()

    def test_salary_and_attendance_calculation_rules(self):
        """
        Verify rules:
        - 9 working hours count as full working day -> Full-day salary.
        - 4 hours 30 mins count as half working day -> Half-day salary.
        - Up to 2 hours of approved permission must not affect salary.
        - Approved leave days must not result in salary deductions.
        """
        # Create salary structure for EMP001 (Basic 30000, 30-day month -> 1000/day)
        SalaryStructure.objects.create(
            employee=self.emp_profile,
            basic_salary=Decimal('30000.00'),
            hra=Decimal('0.00'),
            allowances=Decimal('0.00'),
            pf_deduction=Decimal('0.00'),
            tax_deduction=Decimal('0.00')
        )

        test_year = 2026
        test_month = 11  # November (30 days, daily rate = 1000.00)

        # Day 1: Full working day (9 hours: 09:00 to 18:00) -> 0 deduction
        Attendance.objects.create(
            employee=self.emp_profile,
            date=date(test_year, test_month, 1),
            in_time=time(9, 0),
            out_time=time(18, 0),
            status='Present'
        )

        # Day 2: Half working day (4 hours 30 mins: 09:00 to 13:30) -> 0.5 day deduction (-500)
        Attendance.objects.create(
            employee=self.emp_profile,
            date=date(test_year, test_month, 2),
            in_time=time(9, 0),
            out_time=time(13, 30),
            status='Half Day'
        )

        # Day 3: Approved 2 hours permission -> Must NOT affect salary (0 deduction)
        Attendance.objects.create(
            employee=self.emp_profile,
            date=date(test_year, test_month, 3),
            in_time=time(9, 0),
            out_time=time(16, 0),
            status='Permission - 2 Hours',
            is_permission=True,
            permission_hours=Decimal('2.00')
        )

        # Day 4: Approved leave day -> Must NOT result in salary deductions (0 deduction)
        LeaveRequest.objects.create(
            employee=self.emp_profile,
            leave_type='Casual Leave',
            from_date=date(test_year, test_month, 4),
            to_date=date(test_year, test_month, 4),
            reason='Family event',
            status='Approved'
        )

        calc = calculate_payroll_for_employee(self.emp_profile, test_year, test_month)

        # Verify daily rate is 30000 / 30 = 1000.00
        # Only Day 2 (Half Day) has a deduction: 0.5 * 1000 = 500.00
        # Days 1 (Full Day), 3 (2h Permission), and 4 (Approved Leave) have ZERO deductions
        self.assertEqual(calc['half_days'], 1)
        self.assertEqual(calc['permission_days'], 1)
        self.assertEqual(calc['approved_leaves'], 1)
        self.assertEqual(calc['absent_days'], 0)
        self.assertEqual(calc['deductions'], Decimal('500.00'))
        self.assertEqual(calc['net_salary'], Decimal('29500.00'))

    def test_admin_and_hr_leave_and_permission_assignment(self):
        self.client.login(username='NETCOM', password='Netcom@2026@Netcom')
        test_date = date(2026, 11, 15)

        # Admin grants 2-hour permission
        r = self.client.post('/dashboard/', {
            'action': 'update_employee_leave',
            'employee_id': self.emp_profile.id,
            'leave_type': 'Permission – 2 Hours',
            'from_date': test_date.strftime('%Y-%m-%d'),
            'to_date': test_date.strftime('%Y-%m-%d'),
            'reason': 'Doctor appointment',
            'status': 'Approved'
        })
        self.assertEqual(r.status_code, 302)

        # Check Attendance record was created and labeled with Permission – 2 Hours
        att = Attendance.objects.filter(employee=self.emp_profile, date=test_date).first()
        self.assertIsNotNone(att)
        self.assertEqual(att.status, 'Permission - 2 Hours')
        self.assertTrue(att.is_permission)
        self.assertEqual(att.permission_hours, Decimal('2.00'))

        # Check calendar context reflects Permission – 2 Hours
        r_cal = self.client.get(f'/dashboard/?calendar_emp={self.emp_profile.id}&year=2026&month=11')
        self.assertEqual(r_cal.status_code, 200)
        self.assertContains(r_cal, 'permission-day')

    def test_punch_with_photo_and_gps_and_audit_log(self):
        self.client.login(username='emp_user', password='emp12345')
        today = date.today()

        fake_photo = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="

        # Punch In with photo and GPS
        r_in = self.client.post('/attendance/punch/', {
            'action': 'punch_in',
            'photo_data': fake_photo,
            'latitude': '12.971598',
            'longitude': '77.594566',
            'location': 'Bangalore HQ Office'
        })
        self.assertEqual(r_in.status_code, 302)

        att = Attendance.objects.filter(employee=self.emp_profile, date=today).first()
        self.assertIsNotNone(att)
        self.assertIsNotNone(att.in_time)
        self.assertAlmostEqual(float(att.in_latitude), 12.971598, places=4)
        self.assertAlmostEqual(float(att.in_longitude), 77.594566, places=4)
        self.assertEqual(att.in_location, 'Bangalore HQ Office')
        self.assertTrue(bool(att.in_photo))

        # Check audit log for Punch In
        in_log = AttendanceAuditLog.objects.filter(attendance=att, action='PUNCH_IN').first()
        self.assertIsNotNone(in_log)
        self.assertEqual(in_log.changed_by, self.emp_user)

        # Punch Out with photo and GPS
        r_out = self.client.post('/attendance/punch/', {
            'action': 'punch_out',
            'photo_data': fake_photo,
            'latitude': '12.971600',
            'longitude': '77.594570',
            'location': 'Bangalore HQ Office Exit'
        })
        self.assertEqual(r_out.status_code, 302)

        att.refresh_from_db()
        self.assertIsNotNone(att.out_time)
        self.assertAlmostEqual(float(att.out_latitude), 12.971600, places=4)
        self.assertTrue(bool(att.out_photo))

    def test_user_details_and_leave_balance_quick_update(self):
        self.client.login(username='NETCOM', password='Netcom@2026@Netcom')

        r = self.client.post('/dashboard/', {
            'action': 'update_employee_details',
            'employee_id': self.emp_profile.id,
            'first_name': 'UpdatedFirst',
            'last_name': 'UpdatedLast',
            'email': 'updated@example.com',
            'phone': '+91 9999988888',
            'role': 'EMPLOYEE',
            'department': self.dept.id,
            'casual_leave_balance': 8,
            'is_active_employee': 'on'
        })
        self.assertEqual(r.status_code, 302)

        self.emp_profile.refresh_from_db()
        self.emp_user.refresh_from_db()

        self.assertEqual(self.emp_user.first_name, 'UpdatedFirst')
        self.assertEqual(self.emp_user.last_name, 'UpdatedLast')
        self.assertEqual(self.emp_user.email, 'updated@example.com')
        self.assertEqual(self.emp_profile.phone, '+91 9999988888')
        self.assertEqual(self.emp_profile.casual_leave_balance, 8)
        self.assertTrue(self.emp_profile.is_active_employee)

    def test_biometric_device_integration_and_sync(self):
        device = BiometricDevice.objects.create(
            name='Main Gate ZKTeco',
            device_model='ZKTeco K40',
            ip_address='127.0.0.1',
            port=4370,
            protocol='TCP'
        )
        self.assertEqual(device.name, 'Main Gate ZKTeco')

        online, msg = test_device_connection(device)
        self.assertIn('device', msg.lower())
        self.assertTrue(bool(device.last_status))

        simulated_punches = [
            {'employee_code': 'EMP001', 'timestamp': '2026-10-12 09:00:00', 'punch_type': 'in'},
            {'employee_code': 'EMP001', 'timestamp': '2026-10-12 18:00:00', 'punch_type': 'out'},
        ]
        synced_count, sync_msg = sync_biometric_device(device, user=self.admin_user, simulated_logs=simulated_punches)
        self.assertEqual(synced_count, 2)

        # Test duplicate prevention
        synced_again, _ = sync_biometric_device(device, user=self.admin_user, simulated_logs=simulated_punches)
        self.assertEqual(synced_again, 0)
        self.assertEqual(Attendance.objects.filter(employee=self.emp_profile, date=date(2026, 10, 12)).count(), 1)

    def test_leave_application_and_approval_workflow(self):
        self.client.login(username='emp_user', password='emp12345')
        today = date.today()

        # Submit leave (1 day casual leave matching monthly allocation)
        r = self.client.post('/leave/', {
            'leave_type': 'Casual Leave',
            'from_date': today.strftime('%Y-%m-%d'),
            'to_date': today.strftime('%Y-%m-%d'),
            'reason': 'Family emergency'
        })
        self.assertEqual(r.status_code, 302)
        leave = LeaveRequest.objects.filter(employee=self.emp_profile, reason='Family emergency').first()
        self.assertIsNotNone(leave)
        self.assertEqual(leave.total_days, 1)
        self.assertEqual(leave.status, 'Pending')
        self.client.logout()

        # HR Approves
        self.emp_profile.refresh_from_db()
        balance_before = self.emp_profile.casual_leave_balance
        self.client.login(username='hr_user', password='hr12345')
        r = self.client.get(f'/leave/{leave.id}/Approved/')
        self.assertEqual(r.status_code, 302)
        leave.refresh_from_db()
        self.emp_profile.refresh_from_db()
        self.assertEqual(leave.status, 'Approved')
        self.assertEqual(self.emp_profile.casual_leave_balance, balance_before - 1)

    def test_payroll_payslip_generation(self):
        self.client.login(username='NETCOM', password='Netcom@2026@Netcom')

        r = self.client.post('/payroll/generate/', {'year': 2026, 'month': 11})
        self.assertEqual(r.status_code, 302)

        record = PayrollRecord.objects.filter(employee=self.emp_profile, year=2026, month=11).first()
        self.assertIsNotNone(record)
        self.assertGreater(record.net_salary, Decimal('0.00'))

        r_slip = self.client.get(f'/payroll/{record.id}/payslip/')
        self.assertEqual(r_slip.status_code, 200)
        self.assertContains(r_slip, 'PAYSLIP')

    def test_leave_request_notification_and_review_classification(self):
        # 1. Employee applies for leave -> HRNotification created
        self.client.login(username='emp_user', password='emp12345')
        today = date(2026, 11, 10)
        r = self.client.post('/leave/', {
            'leave_type': 'Casual Leave',
            'from_date': today.strftime('%Y-%m-%d'),
            'to_date': today.strftime('%Y-%m-%d'),
            'reason': 'Personal errand'
        })
        self.assertEqual(r.status_code, 302)
        leave = LeaveRequest.objects.filter(employee=self.emp_profile, from_date=today).first()
        self.assertIsNotNone(leave)
        self.assertEqual(leave.status, 'Pending')

        # Verify automatic HR notification was generated
        notif = HRNotification.objects.filter(leave_request=leave).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.recipient_role, 'HR')
        self.assertFalse(notif.is_read)
        self.client.logout()

        # 2. HR reviews and approves as Paid Casual Leave
        self.emp_profile.refresh_from_db()
        bal_before = self.emp_profile.casual_leave_balance
        self.client.login(username='hr_user', password='hr12345')
        r_rev = self.client.post(f'/leave/{leave.id}/review/', {
            'status': 'Approved',
            'classification': 'Paid Casual Leave'
        })
        self.assertEqual(r_rev.status_code, 302)

        leave.refresh_from_db()
        self.emp_profile.refresh_from_db()
        self.assertEqual(leave.status, 'Approved')
        self.assertTrue(leave.is_paid)
        self.assertEqual(leave.approval_type, 'Paid Casual Leave')
        self.assertEqual(self.emp_profile.casual_leave_balance, bal_before - 1)

        # 3. Verify Leave categories are strictly Casual Leave and Sick Leave only
        leave_types = [t[0] for t in LeaveRequest.LEAVE_TYPES]
        self.assertEqual(leave_types, ['Casual Leave', 'Sick Leave'])
        self.assertNotIn('Annual Leave', leave_types)
        self.assertNotIn('Unpaid Leave', leave_types)

        # Employee applies for Sick Leave
        self.client.logout()
        self.client.login(username='emp_user', password='emp12345')
        sick_date = date(2026, 11, 12)
        self.client.post('/leave/', {
            'leave_type': 'Sick Leave',
            'from_date': sick_date.strftime('%Y-%m-%d'),
            'to_date': sick_date.strftime('%Y-%m-%d'),
            'reason': 'Medical recovery'
        })
        sick_leave = LeaveRequest.objects.filter(employee=self.emp_profile, from_date=sick_date).first()
        self.assertIsNotNone(sick_leave)
        self.assertEqual(sick_leave.leave_type, 'Sick Leave')
        self.client.logout()

        # HR approves as Paid Sick Leave -> casual balance NOT deducted
        self.client.login(username='hr_user', password='hr12345')
        bal_before_sick = self.emp_profile.casual_leave_balance
        self.client.post(f'/leave/{sick_leave.id}/review/', {
            'status': 'Approved',
            'classification': 'Paid Sick Leave'
        })
        sick_leave.refresh_from_db()
        self.emp_profile.refresh_from_db()
        self.assertEqual(sick_leave.status, 'Approved')
        self.assertTrue(sick_leave.is_paid)
        self.assertEqual(sick_leave.approval_type, 'Paid Sick Leave')
        self.assertEqual(self.emp_profile.casual_leave_balance, bal_before_sick)

        # 4. Verify salary calculation: Paid Casual Leave & Paid Sick Leave have ZERO salary deduction!
        SalaryStructure.objects.get_or_create(
            employee=self.emp_profile,
            defaults={
                'basic_salary': Decimal('30000.00'),
                'hra': Decimal('0.00'),
                'allowances': Decimal('0.00'),
                'pf_deduction': Decimal('0.00'),
                'tax_deduction': Decimal('0.00')
            }
        )
        calc = calculate_payroll_for_employee(self.emp_profile, 2026, 11)
        # 1 paid casual leave + 1 paid sick leave = 2 approved leaves with 0 salary deduction
        self.assertEqual(calc['approved_leaves'], 2)
        self.assertEqual(calc['unpaid_leaves'], 0)
        self.assertEqual(calc['deductions'], Decimal('0.00'))
        self.assertEqual(calc['net_salary'], Decimal('30000.00'))

    def test_rejected_leave_calendar_display_and_reason(self):
        self.client.login(username='emp_user', password='emp12345')
        rej_date = date(2026, 11, 20)
        self.client.post('/leave/', {
            'leave_type': 'Casual Leave',
            'from_date': rej_date.strftime('%Y-%m-%d'),
            'to_date': rej_date.strftime('%Y-%m-%d'),
            'reason': 'Day off requested'
        })
        leave = LeaveRequest.objects.filter(employee=self.emp_profile, from_date=rej_date).first()
        self.client.logout()

        # HR Rejects with specific reason
        self.client.login(username='hr_user', password='hr12345')
        r_rej = self.client.post(f'/leave/{leave.id}/review/', {
            'status': 'Rejected',
            'rejection_reason': 'Critical project sprint deadline'
        })
        self.assertEqual(r_rej.status_code, 302)
        leave.refresh_from_db()
        self.assertEqual(leave.status, 'Rejected')
        self.assertEqual(leave.rejection_reason, 'Critical project sprint deadline')
        self.client.logout()

        # Employee checks calendar: rejected leave date is red with rejection reason
        self.client.login(username='emp_user', password='emp12345')
        r_cal = self.client.get('/dashboard/?year=2026&month=11')
        self.assertEqual(r_cal.status_code, 200)
        self.assertContains(r_cal, 'rejected-leave-day')
        self.assertContains(r_cal, 'Critical project sprint')

    def test_casual_leave_restoration_when_employee_attends_office(self):
        # 1. Employee has approved casual leave for today
        target_date = date(2026, 11, 25)
        leave = LeaveRequest.objects.create(
            employee=self.emp_profile,
            leave_type='Casual Leave',
            approval_type='Paid Casual Leave',
            from_date=target_date,
            to_date=target_date,
            reason='Personal day',
            status='Approved',
            is_paid=True
        )
        self.emp_profile.casual_leave_balance = 0
        self.emp_profile.save(update_fields=['casual_leave_balance'])

        # Attendance initialized as On Leave
        att = Attendance.objects.create(
            employee=self.emp_profile,
            date=target_date,
            status='On Leave',
            is_approved_leave=True,
            leave_type='Casual Leave'
        )

        # 2. Employee actually attends office and completes 9 working hours (09:00 to 18:00)
        att.in_time = time(9, 0)
        att.out_time = time(18, 0)
        att.save()

        # 3. Call restoration check
        restored, msg = check_and_restore_casual_leave_on_attendance(self.emp_profile, target_date, att, changed_by=self.emp_user)
        self.assertTrue(restored)

        # 4. Verify: leave cancelled, casual leave balance restored by 1 day, attendance set to Present
        leave.refresh_from_db()
        self.emp_profile.refresh_from_db()
        att.refresh_from_db()

        self.assertEqual(leave.status, 'Cancelled')
        self.assertIn('Cancelled: Employee attended office', leave.rejection_reason)
        self.assertEqual(self.emp_profile.casual_leave_balance, 1)  # Restored from 0 to 1!
        self.assertEqual(att.status, 'Present')
        self.assertFalse(att.is_approved_leave)

        # 5. Check audit log was recorded
        audit = AttendanceAuditLog.objects.filter(attendance=att, action='CASUAL_LEAVE_RESTORED').first()
        self.assertIsNotNone(audit)
        self.assertIn('Restored +1 casual leave', audit.new_values)

        # 6. Verify idempotency: calling again should not restore a second time
        second_run, _ = check_and_restore_casual_leave_on_attendance(self.emp_profile, target_date, att)
        self.assertFalse(second_run)
        self.emp_profile.refresh_from_db()
        self.assertEqual(self.emp_profile.casual_leave_balance, 1)

    def test_role_based_access_controls(self):
        # 1. HR user cannot access Admin dashboard
        self.client.login(username='hr_user', password='hr12345')
        r_hr_admin = self.client.get('/dashboard/admin/')
        # Redirected back to dashboard index by @admin_required decorator
        self.assertNotEqual(r_hr_admin.status_code, 200)
        self.client.logout()

        # 2. Admin user CAN access HR dashboard
        self.client.login(username='NETCOM', password='Netcom@2026@Netcom')
        r_admin_hr = self.client.get('/dashboard/hr/')
        self.assertEqual(r_admin_hr.status_code, 200)
        self.assertContains(r_admin_hr, 'Netcom HR Dashboard')
        self.client.logout()

    def test_daily_work_image_attachment_and_offsite(self):
        self.client.login(username='emp_user', password='emp12345')
        tiny_gif = (
            b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00'
            b'!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01'
            b'\x00\x00\x02\x02D\x01\x00;'
        )
        fake_work_img = SimpleUploadedFile("site_photo.gif", tiny_gif, content_type="image/gif")

        r = self.client.post('/attendance/daily-work/', {
            'project_name': 'Cloud Infrastructure Migration',
            'work_details': 'Configured remote gateway and hardware sensors at Client Data Center.',
            'status': 'In Progress',
            'is_offsite': 'on',
            'location_notes': 'Client Data Center Sector 5',
            'work_image': fake_work_img
        })
        self.assertEqual(r.status_code, 302)

        work = DailyWork.objects.filter(employee=self.emp_profile, project_name='Cloud Infrastructure Migration').first()
        self.assertIsNotNone(work)
        self.assertTrue(work.is_offsite)
        self.assertEqual(work.location_notes, 'Client Data Center Sector 5')
        self.assertTrue(bool(work.work_image))
        self.client.logout()

        # Admin can view the work log and attachment
        self.client.login(username='NETCOM', password='Netcom@2026@Netcom')
        r_admin = self.client.get('/attendance/daily-work/')
        self.assertEqual(r_admin.status_code, 200)
        self.assertContains(r_admin, 'Cloud Infrastructure Migration')
        self.assertContains(r_admin, 'Off-Site Activity')
        self.assertContains(r_admin, 'Client Data Center Sector 5')
        self.client.logout()

    def test_leave_request_allowed_with_zero_casual_balance_using_reason(self):
        # Employee with 0 casual leave balance can still apply for leave with only reason
        self.emp_profile.casual_leave_balance = 0
        self.emp_profile.save(update_fields=['casual_leave_balance'])

        self.client.login(username='emp_user', password='emp12345')
        req_date = date(2026, 12, 1)
        r = self.client.post('/leave/', {
            'leave_type': 'Casual Leave',
            'from_date': req_date.strftime('%Y-%m-%d'),
            'to_date': req_date.strftime('%Y-%m-%d'),
            'reason': 'Urgent doctor consultation and rest'
        })
        self.assertEqual(r.status_code, 302)

        leave = LeaveRequest.objects.filter(employee=self.emp_profile, from_date=req_date).first()
        self.assertIsNotNone(leave)
        self.assertEqual(leave.status, 'Pending')
        self.assertEqual(leave.reason, 'Urgent doctor consultation and rest')

        # Verify HR is notified
        notif = HRNotification.objects.filter(leave_request=leave).first()
        self.assertIsNotNone(notif)
        self.client.logout()

        # HR can approve without error even with 0 casual balance
        self.client.login(username='hr_user', password='hr12345')
        r_approve = self.client.post(f'/leave/{leave.id}/review/', {
            'status': 'Approved',
            'classification': 'Paid Casual Leave'  # System smoothly adapts to Unpaid Leave or approves
        })
        self.assertEqual(r_approve.status_code, 302)
        leave.refresh_from_db()
        self.assertEqual(leave.status, 'Approved')

    def test_edit_employee_button_in_employee_details_section(self):
        self.client.login(username='NETCOM', password='Netcom@2026@Netcom')
        r = self.client.get('/dashboard/admin/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'User Details and Leave Balance')
        self.assertContains(r, '✏️ Edit Employee')

    def test_complete_hr_report_export_excel_and_pdf(self):
        self.client.login(username='hr_user', password='hr12345')

        # 1. Download Excel
        r_excel = self.client.get('/reports/complete-export/?from_date=2026-10-01&to_date=2026-10-31&format=excel')
        self.assertEqual(r_excel.status_code, 200)
        self.assertIn('spreadsheetml', r_excel['Content-Type'])
        self.assertIn('attachment;', r_excel['Content-Disposition'])

        # 2. Download PDF
        r_pdf = self.client.get('/reports/complete-export/?from_date=2026-10-01&to_date=2026-10-31&format=pdf')
        self.assertEqual(r_pdf.status_code, 200)
        self.assertEqual(r_pdf['Content-Type'], 'application/pdf')
        self.assertIn('attachment;', r_pdf['Content-Disposition'])

    def test_employee_daily_work_planning_and_targeted_notification(self):
        # HR creates daily work plan for employee
        self.client.login(username='hr_user', password='hr12345')
        target_date = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        r_create = self.client.post('/dashboard/', {
            'action': 'create_work_plan',
            'employee_id': self.emp_profile.id,
            'work_date': target_date,
            'title': 'API Microservices Optimization',
            'tasks': 'Refactor user authentication pipeline and verify database query indexes.',
            'status': 'Assigned'
        })
        self.assertEqual(r_create.status_code, 302)

        plan = DailyWorkPlan.objects.filter(employee=self.emp_profile, work_date=target_date).first()
        self.assertIsNotNone(plan)
        self.assertEqual(plan.title, 'API Microservices Optimization')
        self.assertEqual(plan.status, 'Assigned')
        self.assertEqual(plan.assigned_by, self.hr_user)
        self.client.logout()

        # Employee logs in -> views dashboard -> sees targeted notification banner
        self.client.login(username='emp_user', password='emp12345')
        r_emp = self.client.get('/dashboard/')
        self.assertEqual(r_emp.status_code, 200)
        self.assertContains(r_emp, 'Daily Work Plan Assigned by HR')
        self.assertContains(r_emp, 'API Microservices Optimization')
        self.assertContains(r_emp, 'Refactor user authentication pipeline')
        self.assertContains(r_emp, 'My Assigned Daily Work Plans')
        self.client.logout()

        # HR updates the work plan
        self.client.login(username='hr_user', password='hr12345')
        r_update = self.client.post('/dashboard/', {
            'action': 'update_work_plan',
            'plan_id': plan.id,
            'work_date': target_date,
            'title': 'API Microservices Optimization (Priority)',
            'tasks': 'Complete backend auth tests and deploy staging build.',
            'status': 'In Progress'
        })
        self.assertEqual(r_update.status_code, 302)
        plan.refresh_from_db()
        self.assertEqual(plan.status, 'In Progress')
        self.assertEqual(plan.title, 'API Microservices Optimization (Priority)')

    def test_employee_dashboard_sidebar_restricted(self):
        # Employee dashboard displays only Dashboard link in sidebar
        self.client.login(username='emp_user', password='emp12345')
        r = self.client.get('/dashboard/')
        self.assertEqual(r.status_code, 200)
        # Dashboard is in sidebar
        self.assertContains(r, '<span>Dashboard</span>')
        # Off-Site Work Activity removed from employee work report form
        self.assertNotContains(r, 'Off-Site Work Activity (Client / Field Site)')
        # Top punch horizontal bar present
        self.assertContains(r, 'punch-horizontal-bar')
        self.assertContains(r, 'Punch-In Time')
        self.assertContains(r, 'Punch-Out Time')
        self.assertContains(r, 'Total Working Time')
        self.assertContains(r, 'Casual Leave Balance')
        self.client.logout()

    def test_dashboards_have_punch_horizontal_bar_and_image_management(self):
        # HR dashboard has punch bar and image management modal
        self.client.login(username='hr_user', password='hr12345')
        r_hr = self.client.get('/dashboard/hr/')
        self.assertEqual(r_hr.status_code, 200)
        self.assertContains(r_hr, 'punch-horizontal-bar')
        self.assertContains(r_hr, 'Comprehensive HR Report Download')
        self.assertContains(r_hr, 'Employee Daily Work Planning')
        self.assertNotContains(r_hr, 'Biometric Machine Synchronization')
        self.client.logout()

        # Admin dashboard has punch bar
        self.client.login(username='NETCOM', password='Netcom@2026@Netcom')
        r_admin = self.client.get('/dashboard/admin/')
        self.assertEqual(r_admin.status_code, 200)
        self.assertContains(r_admin, 'punch-horizontal-bar')
        self.client.logout()

    def test_admin_duty_punch_terminal_and_execution(self):
        # Admin can view Duty Punch Terminal on Admin dashboard and punch in/out
        self.client.login(username='NETCOM', password='Netcom@2026@Netcom')
        r_admin = self.client.get('/dashboard/admin/')
        self.assertEqual(r_admin.status_code, 200)
        self.assertContains(r_admin, 'Administrator Duty Punch Terminal')
        self.assertContains(r_admin, 'adminPunchForm')
        self.assertContains(r_admin, 'Admin Punch In')
        self.assertContains(r_admin, 'Admin Punch Out')

        # Admin Punches In
        fake_photo = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
        r_in = self.client.post('/attendance/punch/', {
            'action': 'punch_in',
            'photo_data': fake_photo,
            'latitude': '13.082680',
            'longitude': '80.270718',
            'location': 'Netcom Admin HQ'
        })
        self.assertEqual(r_in.status_code, 302)

        att = Attendance.objects.filter(employee=self.admin_profile, date=date.today()).first()
        self.assertIsNotNone(att)
        self.assertIsNotNone(att.in_time)
        self.assertEqual(att.status, 'Present')
        self.assertIn('ADMIN Punch', att.update_source)
        self.assertIsNotNone(att.in_photo)

        # Admin Punches Out
        r_out = self.client.post('/attendance/punch/', {
            'action': 'punch_out',
            'photo_data': fake_photo,
            'latitude': '13.082680',
            'longitude': '80.270718',
            'location': 'Netcom Admin HQ'
        })
        self.assertEqual(r_out.status_code, 302)
        att.refresh_from_db()
        self.assertIsNotNone(att.out_time)
        self.client.logout()

    def test_casual_leave_policy_monthly_reset_no_carry_forward(self):
        from apps.leave_management.views import refresh_monthly_leave_for_employee
        from apps.leave_management.models import MonthlyLeaveCredit

        # Month 1: Employee starts with 1 casual leave
        month1 = date(2026, 1, 1)
        refresh_monthly_leave_for_employee(self.emp_profile, today=month1)
        self.emp_profile.refresh_from_db()
        self.assertEqual(self.emp_profile.casual_leave_balance, 1)

        # Employee does NOT use their leave in Month 1 (balance is still 1)
        # Advance to Month 2 (Feb 2026):
        month2 = date(2026, 2, 1)
        refresh_monthly_leave_for_employee(self.emp_profile, today=month2)
        self.emp_profile.refresh_from_db()
        # Strictly 1 casual leave: NO carry-forward (balance is 1, NOT 2!)
        self.assertEqual(self.emp_profile.casual_leave_balance, 1)

        # Verify MonthlyLeaveCredit created for month 1 and month 2
        self.assertTrue(MonthlyLeaveCredit.objects.filter(employee=self.emp_profile, year=2026, month=1).exists())
        self.assertTrue(MonthlyLeaveCredit.objects.filter(employee=self.emp_profile, year=2026, month=2).exists())

    def test_unwanted_text_phrases_removed_from_all_pages(self):
        # Admin dashboard
        self.client.login(username='NETCOM', password='Netcom@2026@Netcom')
        r_admin = self.client.get('/dashboard/admin/')
        self.assertNotContains(r_admin, 'Welcome to Netcom Executive Administration')
        self.assertNotContains(r_admin, 'Enterprise HRM')
        self.assertNotContains(r_admin, 'Full Day (9h - Green)')
        self.assertNotContains(r_admin, 'Half Day (4.5h - Yellow)')
        self.assertNotContains(r_admin, 'Rejected Leave (Red)')
        self.assertNotContains(r_admin, 'Displays 4 records initially')
        self.assertNotContains(r_admin, 'Displaying 5 records initially')
        self.assertNotContains(r_admin, 'Displaying 10 records initially')
        self.client.logout()

        # Employee dashboard
        self.client.login(username='emp_user', password='emp12345')
        r_emp = self.client.get('/dashboard/')
        self.assertNotContains(r_emp, 'Attendance Rules: 9 working hours')
        self.assertNotContains(r_emp, 'Full Day (9h - Green)')
        self.assertNotContains(r_emp, 'Half Day (4.5h - Yellow)')
        self.assertNotContains(r_emp, 'Rejected Leave (Red)')
        self.assertNotContains(r_emp, 'Displays 4 records initially')
        self.client.logout()

        # HR dashboard
        self.client.login(username='hr_user', password='hr12345')
        r_hr = self.client.get('/dashboard/hr/')
        self.assertNotContains(r_hr, 'Full Day (9h - Green)')
        self.assertNotContains(r_hr, 'Half Day (4.5h - Yellow)')
        self.assertNotContains(r_hr, 'Displaying 5 records initially')
        self.client.logout()

    def test_strict_once_per_day_punch_rules_and_error_messages(self):
        self.client.login(username='emp_user', password='emp12345')
        # 1. First punch in -> Success
        r1 = self.client.post('/attendance/punch/', {'action': 'punch_in'}, follow=True)
        messages1 = [str(m) for m in r1.context['messages']]
        self.assertTrue(any("Punch In recorded" in m for m in messages1))

        # 2. Second punch in -> Exact error message
        r2 = self.client.post('/attendance/punch/', {'action': 'punch_in'}, follow=True)
        messages2 = [str(m) for m in r2.context['messages']]
        self.assertIn("You have already punched in for today.", messages2)

        # 3. First punch out -> Success
        r3 = self.client.post('/attendance/punch/', {'action': 'punch_out'}, follow=True)
        messages3 = [str(m) for m in r3.context['messages']]
        self.assertTrue(any("Punch Out recorded" in m for m in messages3))

        # 4. Second punch out -> Exact error message
        r4 = self.client.post('/attendance/punch/', {'action': 'punch_out'}, follow=True)
        messages4 = [str(m) for m in r4.context['messages']]
        self.assertIn("You have already punched out for today.", messages4)
        self.client.logout()

    def test_office_paid_leave_functionality_and_payroll(self):
        from apps.leave_management.models import OfficePaidLeave
        today = timezone.localdate()

        self.client.login(username='hr_user', password='hr12345')
        # Mark Office Paid Leave
        r = self.client.post('/dashboard/', {
            'action': 'mark_office_paid_leave',
            'date': today.strftime('%Y-%m-%d'),
            'title': 'Netcom Annual Company Day',
            'description': 'Celebration holiday with full pay'
        }, follow=True)
        self.assertEqual(r.status_code, 200)

        # Verify OfficePaidLeave created
        opl = OfficePaidLeave.objects.filter(date=today).first()
        self.assertIsNotNone(opl)
        self.assertEqual(opl.title, 'Netcom Annual Company Day')

        # Verify Attendance record synced for employee
        att = Attendance.objects.get(employee=self.emp_profile, date=today)
        self.assertEqual(att.status, 'On Leave')
        self.assertTrue(att.is_approved_leave)
        self.assertEqual(att.leave_type, 'Paid Leave for the Office')

        # Casual leave balance not reduced (still 1)
        self.emp_profile.refresh_from_db()
        self.assertEqual(self.emp_profile.casual_leave_balance, 1)

        # Verify Payroll calculation: Full basic salary (zero deduction)
        payroll = calculate_payroll_for_employee(self.emp_profile, today.year, today.month)
        self.assertEqual(payroll['deductions'], Decimal('0.00'))
        self.assertEqual(payroll['basic_salary'], self.emp_profile.basic_salary)
        self.client.logout()

    def test_employee_password_visibility_and_management(self):
        from apps.employees.forms import EmployeeCreateForm

        # 1. Create employee via EmployeeCreateForm and verify raw_password stored
        form_data = {
            'username': 'test_worker',
            'password': 'SecureWorker@2026',
            'first_name': 'Worker',
            'last_name': 'One',
            'email': 'worker@netcom.com',
            'employee_code': 'WRK001',
            'role': 'EMPLOYEE',
            'basic_salary': 25000.00,
            'casual_leave_balance': 1,
        }
        form = EmployeeCreateForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        worker_emp = form.save()
        self.assertEqual(worker_emp.raw_password, 'SecureWorker@2026')

        # 2. Admin updates password via dashboard quick edit
        self.client.login(username='NETCOM', password='Netcom@2026@Netcom')
        r = self.client.post('/dashboard/', {
            'action': 'update_employee_details',
            'employee_id': worker_emp.id,
            'first_name': 'Worker',
            'last_name': 'Updated',
            'email': 'worker@netcom.com',
            'phone': '9876543210',
            'role': 'EMPLOYEE',
            'casual_leave_balance': 1,
            'password': 'NewPassword@2026',
            'is_active_employee': 'on',
        }, follow=True)
        self.assertEqual(r.status_code, 200)

        worker_emp.refresh_from_db()
        self.assertEqual(worker_emp.raw_password, 'NewPassword@2026')
        self.assertTrue(worker_emp.user.check_password('NewPassword@2026'))
        self.client.logout()

    def test_calendar_view_isolation_and_permissions(self):
        # 1. Regular employee sees own calendar only
        self.client.login(username='emp_user', password='emp12345')
        r_emp = self.client.get('/dashboard/employee/')
        self.assertContains(r_emp, self.emp_profile.employee_code)
        self.assertNotContains(r_emp, 'name="calendar_emp"')
        self.client.logout()

        # 2. HR can view other user calendar
        self.client.login(username='hr_user', password='hr12345')
        r_hr = self.client.get(f'/dashboard/hr/?calendar_emp={self.emp_profile.id}')
        self.assertContains(r_hr, 'name="calendar_emp"')
        self.assertEqual(r_hr.context['calendar_employee'].id, self.emp_profile.id)
        self.client.logout()

    def test_employee_deletion_permissions_and_netcom_protection(self):
        # 1. HR cannot delete NETCOM
        self.client.login(username='hr_user', password='hr12345')
        r_del_netcom = self.client.get(f'/employees/{self.admin_profile.id}/delete/', follow=True)
        messages_netcom = [str(m) for m in r_del_netcom.context['messages']]
        self.assertTrue(any("cannot be deleted" in m for m in messages_netcom))
        self.assertTrue(Employee.objects.filter(id=self.admin_profile.id).exists())

        # 2. Admin cannot delete NETCOM either
        self.client.logout()
        self.client.login(username='NETCOM', password='Netcom@2026@Netcom')
        r_admin_del_netcom = self.client.get(f'/employees/{self.admin_profile.id}/delete/', follow=True)
        messages_admin_netcom = [str(m) for m in r_admin_del_netcom.context['messages']]
        self.assertTrue(any("cannot be deleted" in m for m in messages_admin_netcom))
        self.assertTrue(Employee.objects.filter(id=self.admin_profile.id).exists())

        # 3. HR can delete regular employee
        self.client.logout()
        self.client.login(username='hr_user', password='hr12345')
        del_target = User.objects.create_user('temp_emp', 'temp@test.com', 'emp12345')
        del_profile = Employee.objects.create(
            user=del_target, employee_code='TEMP001', role='EMPLOYEE',
            department=self.dept, designation=self.desig
        )
        r_del_emp = self.client.get(f'/employees/{del_profile.id}/delete/', follow=True)
        self.assertFalse(Employee.objects.filter(id=del_profile.id).exists())
        self.client.logout()

    def test_hr_not_allowed_to_access_admin_page(self):
        self.client.login(username='hr_user', password='hr12345')
        r = self.client.get('/dashboard/admin/', follow=True)
        messages = [str(m) for m in r.context['messages']]
        self.assertTrue(any("Administrator privileges required" in m for m in messages))
        # Redirected away to dashboard (which routes HR to hr_dashboard)
        self.assertContains(r, 'Netcom HR Dashboard')
        self.client.logout()

    def test_login_page_and_title(self):
        r = self.client.get('/login/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Employee Management Portal')
        self.assertNotContains(r, 'Employee Management Pro Portal')
        self.assertNotContains(r, 'Authorized Access Credentials:')
        self.assertNotContains(r, 'Netcom@2026@Netcom')

    def test_removed_workspace_text_and_leave_categories(self):
        self.client.login(username='emp_user', password='emp12345')
        r = self.client.get('/dashboard/')
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'Self-service workspace. Record attendance with live webcam')
        # Check leave categories in form
        self.assertContains(r, 'Casual Leave')
        self.assertContains(r, 'Sick Leave')
        self.assertNotContains(r, 'Annual Leave')
        self.assertNotContains(r, 'Unpaid Leave')
        self.client.logout()



