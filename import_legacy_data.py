import os
import sys
import django
import sqlite3
from datetime import datetime, date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from apps.departments.models import Department, Designation
from apps.employees.models import Employee
from apps.attendance.models import Attendance, DailyWork
from apps.leave_management.models import LeaveRequest, MonthlyLeaveCredit
from apps.payroll.models import SalaryStructure, PayrollRecord

def migrate():
    legacy_db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'employee_db.sqlite3'))
    print(f"[*] Reading legacy database from: {legacy_db_path}")

    if not os.path.exists(legacy_db_path):
        print(f"[!] Legacy database not found at {legacy_db_path}")
        return

    conn = sqlite3.connect(legacy_db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. Migrate / Create Departments
    dept_map = {}
    default_departments = [
        ('Management', 'MGT', 'Executive and Administrative Leadership'),
        ('Human Resource', 'HR', 'People Operations & Talent'),
        ('IT', 'IT', 'Software Development & Systems'),
        ('Administration', 'ADM', 'General Administration & Facilities'),
    ]
    for name, code, desc in default_departments:
        dept, _ = Department.objects.get_or_create(name=name, defaults={'code': code, 'description': desc})
        dept_map[name.lower()] = dept

    # 2. Migrate Users & Employee Profiles
    cur.execute("SELECT * FROM auth_user")
    legacy_users = cur.fetchall()

    user_map = {}
    for u in legacy_users:
        orig_username = u['username']
        # If legacy admin, update to NETCOM per user requirement
        target_username = 'NETCOM' if orig_username.lower() in ('admin', 'administrator') else orig_username

        user, created = User.objects.get_or_create(username=target_username)
        if target_username == 'NETCOM':
            user.set_password('Netcom@2026@Netcom')
            user.is_superuser = True
            user.is_staff = True
            user.first_name = 'NETCOM'
            user.last_name = 'Administrator'
            user.email = 'admin@netcom.com'
        else:
            # Preserve existing password hash
            user.password = u['password']
            user.first_name = u['first_name']
            user.last_name = u['last_name']
            user.email = u['email']
            user.is_staff = bool(u['is_staff'])
            user.is_superuser = bool(u['is_superuser'])
        user.is_active = bool(u['is_active'])
        user.save()
        user_map[u['id']] = user
        print(f"  [+] Migrated User: {target_username} (ID: {user.id})")

    # Ensure demo users hr and emp have standard passwords if created fresh
    if User.objects.filter(username='hr').exists():
        u_hr = User.objects.get(username='hr')
        u_hr.set_password('hr12345')
        u_hr.save()
    if User.objects.filter(username='emp').exists():
        u_emp = User.objects.get(username='emp')
        u_emp.set_password('emp12345')
        u_emp.save()

    # Migrate Employee Profiles
    cur.execute("SELECT * FROM core_employeeprofile")
    legacy_profiles = cur.fetchall()

    emp_profile_map = {}
    for p in legacy_profiles:
        user = user_map.get(p['user_id'])
        if not user:
            continue

        role = p['role']
        if user.username == 'NETCOM':
            role = 'ADMIN'

        dept_name = p['department'] or 'Administration'
        dept = dept_map.get(dept_name.lower())
        if not dept:
            dept, _ = Department.objects.get_or_create(
                name=dept_name,
                defaults={'code': dept_name[:3].upper(), 'description': f'{dept_name} Department'}
            )
            dept_map[dept_name.lower()] = dept

        desig_title = p['designation'] or 'Executive'
        desig, _ = Designation.objects.get_or_create(
            department=dept,
            title=desig_title
        )

        emp, created = Employee.objects.get_or_create(
            user=user,
            defaults={
                'employee_code': p['employee_code'],
                'role': role,
                'department': dept,
                'designation': desig,
                'phone': p['phone'] or '',
                'address': p['address'] or '',
                'joining_date': p['joining_date'] or date.today(),
                'casual_leave_balance': p['casual_leave_balance'],
                'is_active_employee': bool(p['is_active_employee']),
                'basic_salary': 35000.00 if role == 'EMPLOYEE' else 60000.00,
            }
        )
        if not created:
            emp.employee_code = p['employee_code']
            emp.role = role
            emp.department = dept
            emp.designation = desig
            emp.casual_leave_balance = p['casual_leave_balance']
            emp.save()

        emp_profile_map[p['id']] = emp

        # Create SalaryStructure & Initial Payroll record
        SalaryStructure.objects.get_or_create(
            employee=emp,
            defaults={
                'basic_salary': emp.basic_salary,
                'hra': 8000.00,
                'allowances': 4000.00,
                'pf_deduction': 1800.00,
                'tax_deduction': 1200.00,
            }
        )
        print(f"  [+] Migrated Employee Profile: {emp.employee_code} ({emp.display_name()})")

    # 3. Migrate Attendance History
    cur.execute("SELECT * FROM core_attendance")
    legacy_attendance = cur.fetchall()
    att_count = 0
    for a in legacy_attendance:
        emp = emp_profile_map.get(a['employee_id'])
        if not emp:
            continue

        in_t = None
        if a['in_time']:
            try:
                in_t = datetime.strptime(a['in_time'], '%H:%M:%S.%f').time()
            except ValueError:
                in_t = datetime.strptime(a['in_time'], '%H:%M:%S').time()

        out_t = None
        if a['out_time']:
            try:
                out_t = datetime.strptime(a['out_time'], '%H:%M:%S.%f').time()
            except ValueError:
                out_t = datetime.strptime(a['out_time'], '%H:%M:%S').time()

        Attendance.objects.get_or_create(
            employee=emp,
            date=a['date'],
            defaults={
                'in_time': in_t,
                'out_time': out_t,
                'status': 'Present' if in_t else 'Absent',
                'update_source': a['update_source'] or 'Legacy Import',
            }
        )
        att_count += 1
    print(f"  [+] Migrated Attendance Records: {att_count}")

    # 4. Migrate Daily Work
    cur.execute("SELECT * FROM core_dailywork")
    legacy_works = cur.fetchall()
    work_count = 0
    for w in legacy_works:
        emp = emp_profile_map.get(w['employee_id'])
        if not emp:
            continue
        DailyWork.objects.get_or_create(
            employee=emp,
            date=w['date'],
            project_name=w['project_name'],
            defaults={
                'work_details': w['work_details'],
                'status': w['status'] or 'Completed',
            }
        )
        work_count += 1
    print(f"  [+] Migrated Daily Works: {work_count}")

    # 5. Migrate Leave Requests
    cur.execute("SELECT * FROM core_leaverequest")
    legacy_leaves = cur.fetchall()
    leave_count = 0
    for l in legacy_leaves:
        emp = emp_profile_map.get(l['employee_id'])
        if not emp:
            continue
        LeaveRequest.objects.get_or_create(
            employee=emp,
            from_date=l['from_date'],
            to_date=l['to_date'],
            reason=l['reason'],
            defaults={
                'leave_type': l['leave_type'],
                'total_days': l['total_days'],
                'status': l['status'],
            }
        )
        leave_count += 1
    print(f"  [+] Migrated Leave Requests: {leave_count}")

    # 6. Migrate Monthly Leave Credits
    cur.execute("SELECT * FROM core_monthlyleavecredit")
    legacy_credits = cur.fetchall()
    credit_count = 0
    for c in legacy_credits:
        emp = emp_profile_map.get(c['employee_id'])
        if not emp:
            continue
        MonthlyLeaveCredit.objects.get_or_create(
            employee=emp,
            year=c['year'],
            month=c['month'],
            defaults={
                'casual_added': c['casual_added'],
            }
        )
        credit_count += 1
    print(f"  [+] Migrated Monthly Leave Credits: {credit_count}")

    # Generate initial payroll records for active employees for current month
    today = date.today()
    for emp in Employee.objects.filter(is_active_employee=True):
        struct = emp.salary_structure
        PayrollRecord.objects.get_or_create(
            employee=emp,
            year=today.year,
            month=today.month,
            defaults={
                'basic_salary': struct.basic_salary,
                'allowances': struct.hra + struct.allowances,
                'deductions': struct.pf_deduction + struct.tax_deduction,
                'net_salary': struct.net_salary,
                'status': 'Paid' if emp.role == 'ADMIN' else 'Pending',
                'payment_date': today if emp.role == 'ADMIN' else None
            }
        )

    conn.close()
    print("[OK] Legacy data migration and admin update completed successfully!")

if __name__ == '__main__':
    migrate()
