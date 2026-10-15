from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum
from apps.users.decorators import hr_or_admin_required
from apps.attendance.models import Attendance, AttendanceAuditLog
from .models import LeaveRequest, MonthlyLeaveCredit, HRNotification
from .forms import LeaveRequestForm

def refresh_monthly_leave_for_employee(employee, today=None):
    """
    Refreshes an employee's casual leave balance to exactly 1 casual leave per month
    at the beginning of every month.
    Casual leave does NOT carry forward from one month to the next.
    Any unused casual leave from the previous month is not carried forward.
    Current month approved casual leaves are deducted from the 1-day allowance.
    """
    if not employee or not employee.is_active_employee:
        return False
    if today is None:
        today = timezone.localdate()

    credit, created = MonthlyLeaveCredit.objects.get_or_create(
        employee=employee,
        year=today.year,
        month=today.month,
        defaults={'casual_added': 1}
    )

    if created:
        # New month reset: refresh to strictly 1 casual leave per month, zero carry-forward
        employee.casual_leave_balance = 1
        employee.save(update_fields=['casual_leave_balance'])
        return True
    elif employee.casual_leave_balance > 1:
        # Eliminate legacy carried-forward balances exceeding monthly allowance
        employee.casual_leave_balance = 1
        employee.save(update_fields=['casual_leave_balance'])
        return True
    return False

def refresh_all_active_employees_monthly_leave():
    """
    Refreshes monthly casual leave balance for all active employees (1/month, no carry-forward).
    """
    today = timezone.localdate()
    from apps.employees.models import Employee
    for emp in Employee.objects.filter(is_active_employee=True):
        refresh_monthly_leave_for_employee(emp, today)

# Backward compatibility alias
auto_credit_monthly_leave = refresh_monthly_leave_for_employee

@login_required
def leave_list(request):
    profile = getattr(request.user, 'employee', None)
    if profile:
        refresh_monthly_leave_for_employee(profile)

    is_management = profile and (profile.role in ('ADMIN', 'HR') or request.user.is_superuser)

    if is_management:
        status_filter = request.GET.get('status', '')
        requests_qs = LeaveRequest.objects.select_related('employee', 'employee__user', 'employee__department').all()
        if status_filter:
            requests_qs = requests_qs.filter(status=status_filter)
    else:
        requests_qs = LeaveRequest.objects.filter(employee=profile)

    apply_form = LeaveRequestForm()
    if request.method == 'POST':
        apply_form = LeaveRequestForm(request.POST)
        if apply_form.is_valid():
            leave = apply_form.save(commit=False)
            leave.employee = profile
            leave.total_days = max(1, (leave.to_date - leave.from_date).days + 1)

            leave.save()

            # Automatically notify the HR department
            HRNotification.objects.create(
                recipient_role='HR',
                title=f"New Leave Request from {profile.display_name()}",
                message=(
                    f"{profile.display_name()} ({profile.employee_code}) has submitted a {leave.leave_type} request "
                    f"for {leave.total_days} day(s) from {leave.from_date} to {leave.to_date}. Reason: {leave.reason}"
                ),
                leave_request=leave
            )

            messages.success(request, f"{leave.leave_type} application for {leave.total_days} day(s) submitted for approval. The HR department has been notified.")
            return redirect('leave_management:list')
        else:
            for err_list in apply_form.errors.values():
                for err in err_list:
                    messages.error(request, err)

    pending_count = LeaveRequest.objects.filter(status='Pending').count() if is_management else 0
    hr_notifications = HRNotification.objects.filter(is_read=False)[:10] if is_management else []

    context = {
        'leaves': requests_qs[:100],
        'apply_form': apply_form,
        'profile': profile,
        'is_management': is_management,
        'pending_count': pending_count,
        'hr_notifications': hr_notifications,
    }
    return render(request, 'leave_management/leave_list.html', context)

@login_required
@hr_or_admin_required
def leave_status_update(request, pk, status=None):
    leave = get_object_or_404(LeaveRequest, pk=pk)
    old_status = leave.status

    if request.method == 'POST':
        status = request.POST.get('status', status or 'Approved')
        classification = request.POST.get('classification', 'Paid Casual Leave')
        rejection_reason = request.POST.get('rejection_reason', '').strip()
    else:
        status = status or request.GET.get('status', 'Approved')
        classification = request.GET.get('classification', 'Paid Casual Leave')
        rejection_reason = request.GET.get('rejection_reason', '').strip()

    if status in ('Approved', 'Rejected'):
        if status == 'Approved':
            # Check classification: Paid Sick Leave vs Paid Casual Leave
            if classification == 'Paid Sick Leave' or leave.leave_type == 'Sick Leave':
                leave.is_paid = True
                leave.approval_type = 'Paid Sick Leave'
                leave.leave_type = 'Sick Leave'
                att_leave_type = 'Paid Sick Leave'
            elif classification == 'Unpaid Leave':
                # Legacy compatibility
                leave.is_paid = False
                leave.approval_type = 'Unpaid Leave'
                leave.leave_type = 'Unpaid Leave'
                att_leave_type = 'Unpaid Leave'
            else:
                # Paid Casual Leave
                if old_status != 'Approved':
                    leave.employee.casual_leave_balance = max(0, leave.employee.casual_leave_balance - leave.total_days)
                    leave.employee.save(update_fields=['casual_leave_balance'])
                leave.is_paid = True
                leave.approval_type = 'Paid Casual Leave'
                leave.leave_type = 'Casual Leave'
                att_leave_type = 'Paid Casual Leave'

            leave.status = 'Approved'
            leave.reviewed_by = request.user
            leave.save()

            # Synchronize Attendance records for dates in range
            curr = leave.from_date
            while curr <= leave.to_date:
                att, created = Attendance.objects.get_or_create(employee=leave.employee, date=curr)
                # Only mark On Leave if employee hasn't completed actual work on this day
                if att.total_work_minutes < 270:
                    att.status = 'On Leave'
                    att.is_approved_leave = True
                    att.leave_type = att_leave_type
                    att.leave_reason = leave.reason
                    att.updated_by = request.user
                    att.update_source = f'HR Review ({leave.approval_type})'
                    att.save()

                    AttendanceAuditLog.objects.create(
                        attendance=att,
                        changed_by=request.user,
                        action='LEAVE_APPROVED',
                        old_values=old_status,
                        new_values=f"Approved as {leave.approval_type}, Paid: {leave.is_paid}",
                        ip_address=request.META.get('REMOTE_ADDR', '')
                    )
                curr += timedelta(days=1)

            messages.success(
                request,
                f"Leave request for {leave.employee.display_name()} approved as {leave.approval_type}."
            )

        elif status == 'Rejected':
            # Revert balance if previously approved as Paid Casual Leave
            if old_status == 'Approved' and leave.is_paid and ('Casual' in leave.approval_type or 'Casual' in leave.leave_type):
                leave.employee.casual_leave_balance = min(1, leave.employee.casual_leave_balance + leave.total_days)
                leave.employee.save(update_fields=['casual_leave_balance'])

            leave.status = 'Rejected'
            leave.reviewed_by = request.user
            leave.rejection_reason = rejection_reason or 'Leave request rejected by HR reviewer.'
            leave.save()

            # Revert attendance records for these dates
            curr = leave.from_date
            while curr <= leave.to_date:
                att = Attendance.objects.filter(employee=leave.employee, date=curr).first()
                if att and att.status == 'On Leave':
                    att.is_approved_leave = False
                    att.leave_type = ''
                    att.leave_reason = f"Rejected: {leave.rejection_reason}"
                    att.status = 'Absent' if not att.in_time else att.status
                    att.updated_by = request.user
                    att.save()
                curr += timedelta(days=1)

            messages.warning(
                request,
                f"Leave request for {leave.employee.display_name()} has been rejected. Calendar marked in red."
            )

        # Mark all notifications for this request as read
        HRNotification.objects.filter(leave_request=leave).update(is_read=True)

    return redirect(request.META.get('HTTP_REFERER') or 'leave_management:list')
