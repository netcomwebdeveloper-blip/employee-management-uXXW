import calendar
from datetime import date, timedelta, datetime
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count, Sum, Q
from apps.employees.models import Employee
from apps.departments.models import Department, Designation
from apps.users.decorators import admin_required, hr_or_admin_required
from apps.attendance.models import Attendance, DailyWork, AttendanceAuditLog, BiometricDevice, DailyWorkPlan
from apps.attendance.forms import ManualAttendanceForm, DailyWorkForm, BiometricDeviceForm, DailyWorkPlanForm
from apps.attendance.services import check_and_restore_casual_leave_on_attendance, reset_daily_missed_punch_in_status, mark_employee_official_duty
from apps.leave_management.models import LeaveRequest, HRNotification, OfficePaidLeave
from apps.leave_management.forms import LeaveRequestForm
from apps.leave_management.views import auto_credit_monthly_leave, refresh_all_active_employees_monthly_leave
from apps.payroll.models import PayrollRecord
from .models import DashboardBanner, DashboardPopup


def get_or_create_employee_profile(user):
    """Ensures every authenticated user always has a linked Employee profile safely."""
    profile = getattr(user, 'employee', None)
    if profile:
        return profile
    try:
        return Employee.objects.get(user=user)
    except Employee.DoesNotExist:
        role = 'ADMIN' if (user.is_superuser or user.is_staff) else 'EMPLOYEE'
        code = f"{'ADM' if role == 'ADMIN' else 'EMP'}{user.id:04d}"
        idx = 1
        while Employee.objects.filter(employee_code=code).exists():
            code = f"{'ADM' if role == 'ADMIN' else 'EMP'}{user.id:04d}_{idx}"
            idx += 1

        dept = Department.objects.first()
        return Employee.objects.create(
            user=user,
            employee_code=code,
            role=role,
            department=dept,
            casual_leave_balance=1,
            is_active_employee=True,
        )

def build_employee_calendar(profile, year=None, month=None):
    today = timezone.localdate()
    try:
        year = int(year) if year else today.year
        month = int(month) if month else today.month
        if month < 1 or month > 12:
            year, month = today.year, today.month
    except (ValueError, TypeError):
        year, month = today.year, today.month

    month_days = calendar.monthcalendar(year, month)
    full_day_dates = set()
    half_day_dates = set()
    permission_dates = set()
    leave_dates = set()
    official_duty_dates = set()
    missed_punch_dates = {}

    if profile:
        month_start = date(year, month, 1)
        month_end = date(year, month, calendar.monthrange(year, month)[1])

        # Approved leaves
        leaves = LeaveRequest.objects.filter(
            employee=profile,
            status='Approved',
            from_date__lte=month_end,
            to_date__gte=month_start
        )
        for l in leaves:
            curr = max(l.from_date, month_start)
            end = min(l.to_date, month_end)
            while curr <= end:
                leave_dates.add(curr.day)
                curr += timedelta(days=1)

        # Rejected leaves (displayed in red on the employee's calendar with rejection reason)
        rejected_leaves = LeaveRequest.objects.filter(
            employee=profile,
            status='Rejected',
            from_date__lte=month_end,
            to_date__gte=month_start
        )
        rejected_leave_dates = {}
        for rl in rejected_leaves:
            curr = max(rl.from_date, month_start)
            end = min(rl.to_date, month_end)
            while curr <= end:
                rejected_leave_dates[curr.day] = {
                    'reason': rl.rejection_reason or 'Rejected by HR/Management',
                    'reviewer': rl.reviewed_by.username if rl.reviewed_by else 'HR'
                }
                curr += timedelta(days=1)

        # Attendances
        attendances = Attendance.objects.filter(
            employee=profile,
            date__year=year,
            date__month=month
        )
        for a in attendances:
            d = a.date.day
            if getattr(a, 'is_official_duty', False) or a.update_source == 'Official Office Duty' or a.leave_type == 'Official Duty':
                official_duty_dates.add(d)
            elif a.status == 'Permission - 2 Hours' or a.is_permission:
                permission_dates.add(d)
            elif a.status == 'On Leave':
                leave_dates.add(d)
            elif getattr(a, 'is_missing_punch_out', False) or a.status == 'Missing Punch-Out':
                missed_punch_dates[d] = 'Missing Punch-Out'
            elif getattr(a, 'is_missed_punch_in', False) or a.status in ('Missed Punch-In', 'Absent'):
                missed_punch_dates[d] = a.status
            elif a.is_full_day or a.total_work_minutes >= 540:
                full_day_dates.add(d)
            elif a.is_half_day or (270 <= a.total_work_minutes < 540):
                half_day_dates.add(d)

    office_paid_leaves = OfficePaidLeave.objects.filter(
        date__year=year,
        date__month=month
    )
    office_paid_leave_dates = {opl.date.day: opl for opl in office_paid_leaves}

    rows = []
    for week in month_days:
        row = []
        for day in week:
            if day == 0:
                row.append({'day': '', 'class_name': 'empty-day', 'label': ''})
            elif day in office_paid_leave_dates:
                opl = office_paid_leave_dates[day]
                row.append({
                    'day': day,
                    'class_name': 'office-paid-leave-day',
                    'label': f"Office Paid Leave: {opl.title}",
                    'tooltip': f"Paid Leave for the Office: {opl.title} ({opl.description or 'Full Pay Holiday'})"
                })
            elif day in official_duty_dates:
                # Official Office Duty marked as Present in green
                row.append({
                    'day': day,
                    'class_name': 'working-day',
                    'label': 'Official Duty (Present)',
                    'tooltip': 'Official Office Duty / Work Assignment (Present)'
                })
            elif day in permission_dates:
                # Approved 2-hour permission in green with label “Permission – 2 Hours”
                row.append({'day': day, 'class_name': 'permission-day', 'label': 'Permission – 2 Hours'})
            elif day in half_day_dates:
                # Half-day attendance in yellow
                row.append({'day': day, 'class_name': 'half-day', 'label': 'Half Day'})
            elif day in full_day_dates:
                # Full-day attendance in green
                row.append({'day': day, 'class_name': 'working-day', 'label': 'Full Day (9h)'})
            elif day in leave_dates:
                # Approved leave days
                row.append({'day': day, 'class_name': 'leave-day', 'label': 'Approved Leave'})
            elif day in missed_punch_dates:
                # Display missed punch or missing punch-out prominently in red
                status_lbl = missed_punch_dates[day]
                row.append({
                    'day': day,
                    'class_name': 'rejected-leave-day',
                    'label': status_lbl,
                    'tooltip': f"Attendance Issue: {status_lbl} (Action Required)"
                })
            elif day in rejected_leave_dates:
                # Rejected leave in red with clear rejection status and reason
                rej = rejected_leave_dates[day]
                row.append({
                    'day': day,
                    'class_name': 'rejected-leave-day',
                    'label': f"Rejected: {rej['reason'][:25]}",
                    'tooltip': f"Rejected Leave Reason: {rej['reason']}"
                })
            else:
                row.append({'day': day, 'class_name': 'regular-day', 'label': ''})
        rows.append(row)

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

    return {
        'calendar_rows': rows,
        'calendar_employee': profile,
        'month_name': calendar.month_name[month],
        'current_year': year,
        'current_month': month,
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
        'office_paid_leaves': list(office_paid_leaves),
        'all_office_paid_leaves': OfficePaidLeave.objects.all().order_by('-date')[:15],
    }

@login_required
def index(request):
    reset_daily_missed_punch_in_status()
    profile = get_or_create_employee_profile(request.user)
    if profile.role in ('ADMIN', 'HR') or request.user.is_superuser:
        refresh_all_active_employees_monthly_leave()
    else:
        auto_credit_monthly_leave(profile)

    if profile.role == 'ADMIN' or request.user.is_superuser:
        return admin_dashboard(request, profile)
    elif profile.role == 'HR':
        return hr_dashboard(request, profile)
    else:
        return employee_dashboard(request, profile)

@login_required
@admin_required
def admin_dashboard_view(request):
    """Enforces backend role permission: HR users cannot access Admin dashboard."""
    reset_daily_missed_punch_in_status()
    profile = get_or_create_employee_profile(request.user)
    refresh_all_active_employees_monthly_leave()
    return admin_dashboard(request, profile)

@login_required
@hr_or_admin_required
def hr_dashboard_view(request):
    """Enforces backend role permission: Admin users CAN access HR dashboard when required."""
    reset_daily_missed_punch_in_status()
    profile = get_or_create_employee_profile(request.user)
    refresh_all_active_employees_monthly_leave()
    return hr_dashboard(request, profile)

@login_required
def employee_dashboard_view(request):
    reset_daily_missed_punch_in_status()
    profile = get_or_create_employee_profile(request.user)
    auto_credit_monthly_leave(profile)
    return employee_dashboard(request, profile)

def admin_dashboard(request, profile):
    today = timezone.localdate()

    # 1. Handle Banner Image Upload/Update
    if request.method == 'POST' and request.POST.get('action') == 'upload_banner':
        banner_file = request.FILES.get('banner_image')
        banner_title = request.POST.get('banner_title', '').strip() or 'Netcom Corporate Updates'
        if banner_file:
            DashboardBanner.objects.filter(is_active=True).update(is_active=False)
            banner = DashboardBanner.objects.create(
                title=banner_title,
                image=banner_file,
                uploaded_by=request.user,
                is_active=True
            )
            messages.success(request, "Dashboard banner image updated successfully! The latest banner is now live across all Employee, HR, and Admin dashboards.")
        else:
            messages.error(request, "Please select an image file to upload as the dashboard banner.")
        return redirect('dashboard:index')

    # 1b. Handle Popup Announcement Image Upload/Update
    if request.method == 'POST' and request.POST.get('action') == 'upload_popup':
        popup_file = request.FILES.get('popup_image')
        popup_title = request.POST.get('popup_title', '').strip() or 'Netcom Corporate Announcement'
        popup_desc = request.POST.get('popup_description', '').strip()
        if popup_file:
            DashboardPopup.objects.filter(is_active=True).update(is_active=False)
            DashboardPopup.objects.create(
                title=popup_title,
                image=popup_file,
                description=popup_desc,
                uploaded_by=request.user,
                is_active=True
            )
            messages.success(request, "Announcement popup image updated successfully! Now displayed across the login page and all dashboards.")
        else:
            messages.error(request, "Please select an image file to upload as the announcement popup.")
        return redirect('dashboard:index')

    # 2. Handle Admin/HR Leave Days & Reason/Type Update
    if request.method == 'POST' and request.POST.get('action') == 'update_employee_leave':
        emp_id = request.POST.get('employee_id')
        target_emp = get_object_or_404(Employee, id=emp_id)
        leave_type = request.POST.get('leave_type', 'Casual Leave')
        from_d_str = request.POST.get('from_date')
        to_d_str = request.POST.get('to_date')
        reason = request.POST.get('reason', '').strip() or 'Admin Approved Leave/Permission'
        leave_status = request.POST.get('status', 'Approved')

        try:
            from_d = datetime.strptime(from_d_str, '%Y-%m-%d').date()
            to_d = datetime.strptime(to_d_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, "Invalid dates provided for leave.")
            return redirect('dashboard:index')

        req = LeaveRequest.objects.create(
            employee=target_emp,
            leave_type=leave_type,
            from_date=from_d,
            to_date=to_d,
            reason=reason,
            status=leave_status,
            reviewed_by=request.user
        )

        if leave_status == 'Approved':
            curr = from_d
            while curr <= to_d:
                att, created = Attendance.objects.get_or_create(employee=target_emp, date=curr)
                if leave_type in ('Permission – 2 Hours', 'Permission - 2 Hours'):
                    att.status = 'Permission - 2 Hours'
                    att.is_permission = True
                    att.permission_hours = Decimal('2.00')
                else:
                    att.status = 'On Leave'
                    att.is_approved_leave = True
                    att.leave_type = leave_type
                    att.leave_reason = reason
                att.updated_by = request.user
                att.update_source = 'Admin Leave Assignment'
                att.save()

                AttendanceAuditLog.objects.create(
                    attendance=att,
                    changed_by=request.user,
                    action='LEAVE_ASSIGNMENT',
                    old_values='NEW_ASSIGNMENT' if created else 'UPDATED_LEAVE',
                    new_values=f"Type: {leave_type}, Reason: {reason}, Status: {leave_status}",
                    ip_address=request.META.get('REMOTE_ADDR', '')
                )
                curr += timedelta(days=1)

            if leave_type == 'Casual Leave':
                target_emp.casual_leave_balance = max(0, target_emp.casual_leave_balance - req.total_days)
                target_emp.save(update_fields=['casual_leave_balance'])

        messages.success(request, f"{leave_type} ({from_d} to {to_d}) recorded for {target_emp.display_name()}. Synchronized with employee records, calendar, and payroll.")
        return redirect('dashboard:index')

    # 3. Handle Quick Employee Details & Leave Balance Update
    if request.method == 'POST' and request.POST.get('action') == 'update_employee_details':
        emp_id = request.POST.get('employee_id')
        target_emp = get_object_or_404(Employee, id=emp_id)
        user_obj = target_emp.user
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        new_role = request.POST.get('role', target_emp.role)

        if first_name:
            user_obj.first_name = first_name
        user_obj.last_name = last_name
        user_obj.email = email
        if new_role in ('ADMIN', 'HR', 'EMPLOYEE'):
            target_emp.role = new_role
            if new_role == 'ADMIN':
                user_obj.is_staff = True
                user_obj.is_superuser = True
            else:
                user_obj.is_staff = False
                user_obj.is_superuser = False
        user_obj.save()

        dept_id = request.POST.get('department')
        if dept_id:
            target_emp.department = Department.objects.filter(id=dept_id).first()
        elif dept_id == '':
            target_emp.department = None

        target_emp.phone = request.POST.get('phone', '').strip()
        try:
            target_emp.casual_leave_balance = max(0, int(request.POST.get('casual_leave_balance', 0)))
        except (ValueError, TypeError):
            pass

        target_emp.is_active_employee = (request.POST.get('is_active_employee') == 'on')

        new_password = request.POST.get('password', '').strip()
        if new_password:
            user_obj.set_password(new_password)
            user_obj.save()
            target_emp.raw_password = new_password

        pic = request.FILES.get('profile_picture')
        if pic:
            target_emp.profile_picture = pic

        doc = request.FILES.get('document')
        if doc:
            target_emp.document = doc

        target_emp.save()

        messages.success(request, f"Employee {target_emp.display_name()} ({target_emp.employee_code}) details and leave balance updated successfully.")
        return redirect('dashboard:index')

    # 3b. Handle Mark Paid Leave for the Office
    if request.method == 'POST' and request.POST.get('action') == 'mark_office_paid_leave':
        leave_date_str = request.POST.get('date')
        title = request.POST.get('title', '').strip() or 'Paid Leave for the Office'
        description = request.POST.get('description', '').strip()
        try:
            target_date = datetime.strptime(leave_date_str, '%Y-%m-%d').date()
            opl, created = OfficePaidLeave.objects.get_or_create(
                date=target_date,
                defaults={'title': title, 'description': description, 'marked_by': request.user}
            )
            if not created:
                opl.title = title
                opl.description = description
                opl.marked_by = request.user
                opl.save()

            for emp in Employee.objects.filter(is_active_employee=True):
                att, _ = Attendance.objects.get_or_create(employee=emp, date=target_date)
                att.status = 'On Leave'
                att.is_approved_leave = True
                att.leave_type = 'Paid Leave for the Office'
                att.leave_reason = title
                att.updated_by = request.user
                att.update_source = 'Office Paid Leave'
                att.save()

            messages.success(request, f"Successfully marked {target_date} as '{title}' (Paid Leave for the Office). Synchronized with attendance, calendars, and payroll.")
        except Exception as e:
            messages.error(request, f"Failed to mark Office Paid Leave: {e}")
        return redirect('dashboard:index')

    if request.method == 'POST' and request.POST.get('action') == 'delete_office_paid_leave':
        opl_id = request.POST.get('office_paid_leave_id')
        try:
            opl = OfficePaidLeave.objects.get(id=opl_id)
            target_date = opl.date
            opl.delete()
            Attendance.objects.filter(date=target_date, leave_type='Paid Leave for the Office').delete()
            messages.success(request, f"Removed Office Paid Leave for {target_date}.")
        except Exception as e:
            messages.error(request, f"Could not remove Office Paid Leave: {e}")
        return redirect('dashboard:index')

    # 3c. Handle Mark Official Office Duty / Work Assignment (Admin)
    if request.method == 'POST' and request.POST.get('action') == 'mark_official_duty':
        emp_id = request.POST.get('employee_id')
        date_str = request.POST.get('date')
        duty_title = request.POST.get('duty_title', '').strip() or 'Official Office Duty / Work Assignment'
        notes = request.POST.get('notes', '').strip()
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            target_emp = get_object_or_404(Employee, id=emp_id)
            success, msg = mark_employee_official_duty(target_emp, target_date, duty_title, notes, marked_by=request.user)
            if success:
                messages.success(request, msg)
            else:
                messages.error(request, msg)
        except Exception as e:
            messages.error(request, f"Failed to mark Official Duty: {e}")
        return redirect('dashboard:index')

    # 3d. Handle Toggle Notification Read Status (Admin)
    if request.method == 'POST' and request.POST.get('action') == 'toggle_notification_read':
        notif_id = request.POST.get('notification_id')
        notif = HRNotification.objects.filter(id=notif_id).first()
        if notif:
            notif.is_read = not notif.is_read
            notif.save(update_fields=['is_read'])
            messages.success(request, "Notification status updated.")
        return redirect('dashboard:index')

    # 4. Handle Manual Attendance & Permission Update from Calendar
    if request.method == 'POST' and request.POST.get('action') == 'manual_attendance':
        manual_form = ManualAttendanceForm(request.POST)
        if manual_form.is_valid():
            emp = manual_form.cleaned_data['employee']
            att_date = manual_form.cleaned_data['date']
            att, created = Attendance.objects.get_or_create(employee=emp, date=att_date)
            old_val = f"in: {att.in_time}, out: {att.out_time}, status: {att.status}"
            att.in_time = manual_form.cleaned_data['in_time']
            att.out_time = manual_form.cleaned_data['out_time']
            att.status = manual_form.cleaned_data['status']
            att.leave_type = manual_form.cleaned_data.get('leave_type', '')
            att.leave_reason = manual_form.cleaned_data.get('leave_reason', '')
            att.updated_by = request.user
            att.update_source = 'Admin Manual Dashboard'

            if att.status == 'Permission - 2 Hours':
                att.is_permission = True
                att.permission_hours = Decimal('2.00')

            att.save()

            AttendanceAuditLog.objects.create(
                attendance=att,
                changed_by=request.user,
                action='MANUAL_UPDATE' if not created else 'MANUAL_CREATE',
                old_values=old_val if not created else 'NEW_RECORD',
                new_values=f"in: {att.in_time}, out: {att.out_time}, status: {att.status}",
                ip_address=request.META.get('REMOTE_ADDR', '')
            )
            # Automatic Casual Leave restoration if employee attended office
            restored, msg = check_and_restore_casual_leave_on_attendance(emp, att_date, att, changed_by=request.user)
            if restored:
                messages.info(request, f"Notice: Casual leave for {emp.display_name()} on {att_date} was cancelled and +1 day restored to balance due to attendance ({att.total_work_time}).")

            messages.success(request, f"Attendance record for {emp.display_name()} ({att_date}) updated with audit log.")
            return redirect('dashboard:index')
        else:
            for err_list in manual_form.errors.values():
                for err in err_list:
                    messages.error(request, err)

    total_employees = Employee.objects.filter(is_active_employee=True).count()
    present_today = Attendance.objects.filter(date=today, in_time__isnull=False).count()
    on_leave_today = LeaveRequest.objects.filter(
        status='Approved', from_date__lte=today, to_date__gte=today
    ).count()
    pending_leaves = LeaveRequest.objects.filter(status='Pending').count()
    total_departments = Department.objects.count()

    latest_payroll_sum = PayrollRecord.objects.filter(
        year=today.year, month=today.month, status='Paid'
    ).aggregate(total=Sum('net_salary'))['total'] or 0

    departments = Department.objects.annotate(emp_count=Count('employees'))
    all_active_employees = Employee.objects.filter(is_active_employee=True).select_related('user')

    # Calendar support for Admin
    calendar_emp_id = request.GET.get('calendar_emp')
    calendar_employee = None
    if calendar_emp_id:
        calendar_employee = Employee.objects.filter(id=calendar_emp_id).first()
    if not calendar_employee:
        calendar_employee = all_active_employees.first() or profile

    cal_year = request.GET.get('year')
    cal_month = request.GET.get('month')
    calendar_context = build_employee_calendar(calendar_employee, cal_year, cal_month)

    # Search & Employee Details and Leave Balance (display 10 initially with scroll)
    emp_search = request.GET.get('emp_search', '').strip()
    emp_records = Employee.objects.select_related('user', 'department', 'designation').all()
    if emp_search:
        emp_records = emp_records.filter(
            Q(employee_code__icontains=emp_search) |
            Q(user__username__icontains=emp_search) |
            Q(user__first_name__icontains=emp_search) |
            Q(user__last_name__icontains=emp_search)
        )

    # Lists for Admin Dashboard with scrolling containers (untruncated querysets)
    all_leave_requests = LeaveRequest.objects.select_related('employee', 'employee__user').all()
    all_work_updates = DailyWork.objects.select_related('employee', 'employee__user').all()
    employee_and_hr_attendances = Attendance.objects.select_related('employee', 'employee__user', 'employee__department').all()

    biometric_devices = BiometricDevice.objects.all()
    device_form = BiometricDeviceForm()
    manual_form = ManualAttendanceForm(initial={'date': today, 'employee': calendar_employee})
    active_banner = DashboardBanner.get_active_banner()

    attendance, _ = Attendance.objects.get_or_create(employee=profile, date=today)
    active_popup = DashboardPopup.get_active_popup()

    context = {
        'profile': profile,
        'today': today,
        'attendance': attendance,
        'active_banner': active_banner,
        'active_popup': active_popup,
        'total_employees': total_employees,
        'present_today': present_today,
        'absent_today': max(0, total_employees - present_today - on_leave_today),
        'on_leave_today': on_leave_today,
        'pending_leaves': pending_leaves,
        'total_departments': total_departments,
        'latest_payroll_sum': latest_payroll_sum,
        'departments': departments,
        'all_active_employees': all_active_employees,
        'all_calendar_users': Employee.objects.select_related('user', 'department').all(),
        'calendar_employee': calendar_employee,
        'emp_search': emp_search,
        # Display limit lists (CSS scroll container provides 10 records initially with scrolling)
        'employee_details_and_leave_balance': emp_records,
        'all_leave_requests': all_leave_requests,
        'all_work_updates': all_work_updates,
        'employee_and_hr_attendances': employee_and_hr_attendances,
        'biometric_devices': biometric_devices,
        'device_form': device_form,
        'manual_form': manual_form,
        'all_office_paid_leaves': OfficePaidLeave.objects.all().order_by('-date'),
        'hr_notifications': HRNotification.objects.filter(is_read=False)[:10],
        'employee_messages': HRNotification.objects.filter(recipient_role='HR').order_by('-created_at')[:30],
    }
    context.update(calendar_context)
    return render(request, 'dashboard/admin_dashboard.html', context)


def hr_dashboard(request, profile):
    today = timezone.localdate()

    # 1. Handle Banner Image Upload/Update for HR
    if request.method == 'POST' and request.POST.get('action') == 'upload_banner':
        banner_file = request.FILES.get('banner_image')
        banner_title = request.POST.get('banner_title', '').strip() or 'Netcom HR Announcement'
        if banner_file:
            DashboardBanner.objects.filter(is_active=True).update(is_active=False)
            DashboardBanner.objects.create(
                title=banner_title,
                image=banner_file,
                uploaded_by=request.user,
                is_active=True
            )
            messages.success(request, "Dashboard banner image updated successfully! The latest banner is now live across all Employee, HR, and Admin dashboards.")
        else:
            messages.error(request, "Please select an image file to upload as the dashboard banner.")
        return redirect('dashboard:index')

    # 1b. Handle Popup Announcement Image Upload/Update for HR
    if request.method == 'POST' and request.POST.get('action') == 'upload_popup':
        popup_file = request.FILES.get('popup_image')
        popup_title = request.POST.get('popup_title', '').strip() or 'Netcom HR Announcement'
        popup_desc = request.POST.get('popup_description', '').strip()
        if popup_file:
            DashboardPopup.objects.filter(is_active=True).update(is_active=False)
            DashboardPopup.objects.create(
                title=popup_title,
                image=popup_file,
                description=popup_desc,
                uploaded_by=request.user,
                is_active=True
            )
            messages.success(request, "Announcement popup image updated successfully! Displayed across the login page and all dashboards.")
        else:
            messages.error(request, "Please select an image file to upload as the announcement popup.")
        return redirect('dashboard:index')

    # 2. Handle HR Leave Days & Permission Assignment
    if request.method == 'POST' and request.POST.get('action') == 'update_employee_leave':
        emp_id = request.POST.get('employee_id')
        target_emp = get_object_or_404(Employee, id=emp_id)
        leave_type = request.POST.get('leave_type', 'Casual Leave')
        from_d_str = request.POST.get('from_date')
        to_d_str = request.POST.get('to_date')
        reason = request.POST.get('reason', '').strip() or 'HR Approved Leave/Permission'
        leave_status = request.POST.get('status', 'Approved')

        try:
            from_d = datetime.strptime(from_d_str, '%Y-%m-%d').date()
            to_d = datetime.strptime(to_d_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, "Invalid dates provided for leave.")
            return redirect('dashboard:index')

        req = LeaveRequest.objects.create(
            employee=target_emp,
            leave_type=leave_type,
            from_date=from_d,
            to_date=to_d,
            reason=reason,
            status=leave_status,
            reviewed_by=request.user
        )

        if leave_status == 'Approved':
            curr = from_d
            while curr <= to_d:
                att, created = Attendance.objects.get_or_create(employee=target_emp, date=curr)
                if leave_type in ('Permission – 2 Hours', 'Permission - 2 Hours'):
                    att.status = 'Permission - 2 Hours'
                    att.is_permission = True
                    att.permission_hours = Decimal('2.00')
                else:
                    att.status = 'On Leave'
                    att.is_approved_leave = True
                    att.leave_type = leave_type
                    att.leave_reason = reason
                att.updated_by = request.user
                att.update_source = 'HR Leave Assignment'
                att.save()

                AttendanceAuditLog.objects.create(
                    attendance=att,
                    changed_by=request.user,
                    action='LEAVE_ASSIGNMENT',
                    old_values='NEW_ASSIGNMENT' if created else 'UPDATED_LEAVE',
                    new_values=f"Type: {leave_type}, Reason: {reason}, Status: {leave_status}",
                    ip_address=request.META.get('REMOTE_ADDR', '')
                )
                curr += timedelta(days=1)

            if leave_type == 'Casual Leave':
                target_emp.casual_leave_balance = max(0, target_emp.casual_leave_balance - req.total_days)
                target_emp.save(update_fields=['casual_leave_balance'])

        messages.success(request, f"{leave_type} ({from_d} to {to_d}) recorded for {target_emp.display_name()}. Synchronized with employee records, calendar, and payroll.")
        return redirect('dashboard:index')

    # 3. Handle HR Quick Employee Edit
    if request.method == 'POST' and request.POST.get('action') == 'update_employee_details':
        emp_id = request.POST.get('employee_id')
        target_emp = get_object_or_404(Employee, id=emp_id)
        user_obj = target_emp.user
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()

        if first_name:
            user_obj.first_name = first_name
        user_obj.last_name = last_name
        user_obj.email = email
        user_obj.save()

        dept_id = request.POST.get('department')
        if dept_id:
            target_emp.department = Department.objects.filter(id=dept_id).first()

        target_emp.phone = request.POST.get('phone', '').strip()
        try:
            target_emp.casual_leave_balance = max(0, int(request.POST.get('casual_leave_balance', 0)))
        except (ValueError, TypeError):
            pass

        new_password = request.POST.get('password', '').strip()
        if new_password:
            user_obj.set_password(new_password)
            user_obj.save()
            target_emp.raw_password = new_password

        pic = request.FILES.get('profile_picture')
        if pic:
            target_emp.profile_picture = pic

        doc = request.FILES.get('document')
        if doc:
            target_emp.document = doc

        target_emp.save()

        messages.success(request, f"Employee {target_emp.display_name()} ({target_emp.employee_code}) details updated.")
        return redirect('dashboard:index')

    # 3b. Handle Mark Paid Leave for the Office (HR)
    if request.method == 'POST' and request.POST.get('action') == 'mark_office_paid_leave':
        leave_date_str = request.POST.get('date')
        title = request.POST.get('title', '').strip() or 'Paid Leave for the Office'
        description = request.POST.get('description', '').strip()
        try:
            target_date = datetime.strptime(leave_date_str, '%Y-%m-%d').date()
            opl, created = OfficePaidLeave.objects.get_or_create(
                date=target_date,
                defaults={'title': title, 'description': description, 'marked_by': request.user}
            )
            if not created:
                opl.title = title
                opl.description = description
                opl.marked_by = request.user
                opl.save()

            for emp in Employee.objects.filter(is_active_employee=True):
                att, _ = Attendance.objects.get_or_create(employee=emp, date=target_date)
                att.status = 'On Leave'
                att.is_approved_leave = True
                att.leave_type = 'Paid Leave for the Office'
                att.leave_reason = title
                att.updated_by = request.user
                att.update_source = 'Office Paid Leave'
                att.save()

            messages.success(request, f"Successfully marked {target_date} as '{title}' (Paid Leave for the Office). Synchronized with employee calendars, attendance, and payroll.")
        except Exception as e:
            messages.error(request, f"Failed to mark Office Paid Leave: {e}")
        return redirect('dashboard:index')

    if request.method == 'POST' and request.POST.get('action') == 'delete_office_paid_leave':
        opl_id = request.POST.get('office_paid_leave_id')
        try:
            opl = OfficePaidLeave.objects.get(id=opl_id)
            target_date = opl.date
            opl.delete()
            Attendance.objects.filter(date=target_date, leave_type='Paid Leave for the Office').delete()
            messages.success(request, f"Removed Office Paid Leave for {target_date}.")
        except Exception as e:
            messages.error(request, f"Could not remove Office Paid Leave: {e}")
        return redirect('dashboard:index')

    # 3c. Handle Mark Official Office Duty / Work Assignment (HR)
    if request.method == 'POST' and request.POST.get('action') == 'mark_official_duty':
        emp_id = request.POST.get('employee_id')
        date_str = request.POST.get('date')
        duty_title = request.POST.get('duty_title', '').strip() or 'Official Office Duty / Work Assignment'
        notes = request.POST.get('notes', '').strip()
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            target_emp = get_object_or_404(Employee, id=emp_id)
            success, msg = mark_employee_official_duty(target_emp, target_date, duty_title, notes, marked_by=request.user)
            if success:
                messages.success(request, msg)
            else:
                messages.error(request, msg)
        except Exception as e:
            messages.error(request, f"Failed to mark Official Duty: {e}")
        return redirect('dashboard:index')

    # 3d. Handle Toggle Notification / Message Read Status (HR)
    if request.method == 'POST' and request.POST.get('action') == 'toggle_notification_read':
        notif_id = request.POST.get('notification_id')
        notif = HRNotification.objects.filter(id=notif_id).first()
        if notif:
            notif.is_read = not notif.is_read
            notif.save(update_fields=['is_read'])
            messages.success(request, "Message / Notification status updated.")
        return redirect('dashboard:index')

    # 4. Handle Employee Daily Work Planning Creation
    if request.method == 'POST' and request.POST.get('action') == 'create_work_plan':
        emp_id = request.POST.get('employee_id')
        target_emp = get_object_or_404(Employee, id=emp_id)
        work_date_str = request.POST.get('work_date')
        tasks = request.POST.get('tasks', '').strip()
        plan_title = request.POST.get('title', '').strip() or 'Daily Work Plan & Responsibilities'
        status_val = request.POST.get('status', 'Assigned')
        try:
            work_date = datetime.strptime(work_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            work_date = today + timedelta(days=1)

        DailyWorkPlan.objects.create(
            employee=target_emp,
            work_date=work_date,
            title=plan_title,
            tasks=tasks,
            status=status_val,
            assigned_by=request.user,
            is_notification_sent=True
        )
        messages.success(request, f"Daily work plan assigned to {target_emp.display_name()} for {work_date}. Notification sent directly to employee dashboard!")
        return redirect('dashboard:index')

    # 5. Handle Employee Daily Work Planning Update/Edit
    if request.method == 'POST' and request.POST.get('action') == 'update_work_plan':
        plan_id = request.POST.get('plan_id')
        plan = get_object_or_404(DailyWorkPlan, id=plan_id)
        work_date_str = request.POST.get('work_date')
        tasks = request.POST.get('tasks', '').strip()
        plan_title = request.POST.get('title', '').strip() or plan.title
        status_val = request.POST.get('status', plan.status)
        if work_date_str:
            try:
                plan.work_date = datetime.strptime(work_date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pass
        plan.title = plan_title
        plan.tasks = tasks
        plan.status = status_val
        plan.save()
        messages.success(request, f"Daily work plan for {plan.employee.display_name()} ({plan.work_date}) updated successfully.")
        return redirect('dashboard:index')

    total_employees = Employee.objects.filter(is_active_employee=True).count()
    present_today = Attendance.objects.filter(date=today, in_time__isnull=False).count()
    pending_leaves_count = LeaveRequest.objects.filter(status='Pending').count()

    hr_attendance, _ = Attendance.objects.get_or_create(employee=profile, date=today)
    all_active_employees = Employee.objects.filter(is_active_employee=True).select_related('user')

    # Calendar support for HR
    calendar_emp_id = request.GET.get('calendar_emp')
    calendar_employee = None
    if calendar_emp_id:
        calendar_employee = Employee.objects.filter(id=calendar_emp_id).first()
    if not calendar_employee:
        calendar_employee = profile

    cal_year = request.GET.get('year')
    cal_month = request.GET.get('month')
    calendar_context = build_employee_calendar(calendar_employee, cal_year, cal_month)

    # Lists for HR Dashboard (CSS scroll container provides 5 records initially with scrolling)
    hr_leave_requests = LeaveRequest.objects.select_related('employee', 'employee__user').all()
    hr_work_details = DailyWork.objects.select_related('employee', 'employee__user').all()
    daily_work_plans = DailyWorkPlan.objects.select_related('employee', 'employee__user', 'assigned_by').all()
    next_day_date = (today + timedelta(days=1)).strftime('%Y-%m-%d')

    manual_form = ManualAttendanceForm(initial={'date': today, 'employee': calendar_employee})
    biometric_devices = BiometricDevice.objects.all()
    device_form = BiometricDeviceForm()
    active_banner = DashboardBanner.get_active_banner()

    active_popup = DashboardPopup.get_active_popup()
    report_from_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
    report_to_date = today.strftime('%Y-%m-%d')

    employee_messages = HRNotification.objects.filter(recipient_role='HR').order_by('-created_at')[:30]

    context = {
        'profile': profile,
        'today': today,
        'attendance': hr_attendance,
        'hr_attendance': hr_attendance,
        'active_banner': active_banner,
        'active_popup': active_popup,
        'report_from_date': report_from_date,
        'report_to_date': report_to_date,
        'total_employees': total_employees,
        'present_today': present_today,
        'pending_leaves_count': pending_leaves_count,
        'all_active_employees': all_active_employees,
        'all_calendar_users': Employee.objects.select_related('user', 'department').all(),
        'calendar_employee': calendar_employee,
        # Display limit lists (5 records initially with scroll)
        'employee_details_and_leave_balance': Employee.objects.select_related('user', 'department', 'designation').all(),
        'departments': Department.objects.all(),
        'leave_requests': hr_leave_requests,
        'employee_work_details': hr_work_details,
        'daily_work_plans': daily_work_plans,
        'next_day_date': next_day_date,
        'manual_form': manual_form,
        'biometric_devices': biometric_devices,
        'device_form': device_form,
        'hr_notifications': HRNotification.objects.filter(is_read=False)[:10],
        'employee_messages': employee_messages,
    }
    context.update(calendar_context)
    return render(request, 'dashboard/hr_dashboard.html', context)


def employee_dashboard(request, profile):
    today = timezone.localdate()
    attendance, _ = Attendance.objects.get_or_create(employee=profile, date=today)

    # Handle Employee "Send Message" to HR
    if request.method == 'POST' and request.POST.get('action') == 'send_hr_message':
        category = request.POST.get('category', 'General Enquiry').strip()
        subject = request.POST.get('subject', '').strip()
        msg_body = request.POST.get('message', '').strip()

        if not subject or not msg_body:
            messages.error(request, "Please enter both a Subject and Message.")
        else:
            HRNotification.objects.create(
                recipient_role='HR',
                title=f"[{category}] {subject} - {profile.display_name()} ({profile.employee_code})",
                message=(
                    f"Category: {category}\n"
                    f"Subject: {subject}\n"
                    f"From Employee: {profile.display_name()} ({profile.employee_code})\n"
                    f"Department: {profile.department.name if profile.department else 'N/A'}\n"
                    f"Date: {timezone.localtime().strftime('%Y-%m-%d %I:%M %p')}\n\n"
                    f"Enquiry / Work-Related Concern:\n{msg_body}"
                ),
                is_read=False
            )
            messages.success(request, "Your message has been sent directly to the HR department. HR will review and address your enquiry.")
        return redirect('dashboard:index')

    year = request.GET.get('year')
    month = request.GET.get('month')

    work_form = DailyWorkForm()
    leave_form = LeaveRequestForm()

    # Lists for Employee Dashboard (CSS scroll container provides 4 records initially with scrolling)
    my_daily_work_details = DailyWork.objects.filter(employee=profile)
    my_leave_details = LeaveRequest.objects.filter(employee=profile)
    my_attendances = Attendance.objects.filter(employee=profile)
    my_work_plans = DailyWorkPlan.objects.filter(employee=profile).order_by('-work_date', '-created_at')
    active_work_plan_notification = DailyWorkPlan.objects.filter(
        employee=profile,
        work_date__gte=today
    ).order_by('work_date').first()

    my_sent_messages = HRNotification.objects.filter(message__contains=profile.employee_code).order_by('-created_at')[:15]

    active_banner = DashboardBanner.get_active_banner()
    active_popup = DashboardPopup.get_active_popup()

    context = {
        'profile': profile,
        'today': today,
        'active_banner': active_banner,
        'active_popup': active_popup,
        'attendance': attendance,
        'work_form': work_form,
        'leave_form': leave_form,
        # Display limit lists (4 records initially with scroll)
        'my_daily_work_details': my_daily_work_details,
        'my_leave_details': my_leave_details,
        'my_attendances': my_attendances,
        'my_work_plans': my_work_plans,
        'active_work_plan_notification': active_work_plan_notification,
        'my_sent_messages': my_sent_messages,
        'has_missing_punch_out': getattr(attendance, 'is_missing_punch_out', False),
        'has_missed_punch_in': (attendance.status == 'Missed Punch-In'),
    }
    context.update(build_employee_calendar(profile, year, month))
    return render(request, 'dashboard/employee_dashboard.html', context)

