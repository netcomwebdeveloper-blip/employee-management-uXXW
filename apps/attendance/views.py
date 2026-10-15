import base64
from datetime import datetime, date
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.utils import timezone
from apps.users.decorators import hr_or_admin_required
from apps.employees.models import Employee
from .models import Attendance, DailyWork, AttendanceAuditLog, BiometricDevice
from .forms import ManualAttendanceForm, DailyWorkForm, BiometricDeviceForm
from .biometric_service import test_device_connection, sync_biometric_device
from .services import check_and_restore_casual_leave_on_attendance, reset_daily_missed_punch_in_status, mark_employee_official_duty


def parse_base64_image(data_uri, name_prefix):
    """Safely decodes HTML5 camera DataURI into a Django ContentFile."""
    if not data_uri or ';base64,' not in data_uri:
        return None
    try:
        header, encoded = data_uri.split(';base64,', 1)
        ext = header.split('/')[-1] if '/' in header else 'jpg'
        if ext == 'jpeg':
            ext = 'jpg'
        decoded = base64.b64decode(encoded)
        filename = f"{name_prefix}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
        return ContentFile(decoded, name=filename)
    except Exception:
        return None


@login_required
def punch_view(request):
    """
    Handles employee or HR instant punch-in and punch-out.
    Captures live camera photo and GPS location coordinates, storing them in the database.
    """
    profile = getattr(request.user, 'employee', None)
    if not profile:
        messages.error(request, "Employee profile required to punch.")
        return redirect('dashboard:index')

    reset_daily_missed_punch_in_status()
    today = timezone.localdate()
    now_time = timezone.localtime().time()
    attendance, _ = Attendance.objects.get_or_create(employee=profile, date=today)

    action = request.POST.get('action')
    photo_data = request.POST.get('photo_data', '')
    lat_val = request.POST.get('latitude', '').strip()
    lon_val = request.POST.get('longitude', '').strip()
    loc_desc = request.POST.get('location', '').strip()

    latitude = None
    longitude = None
    if lat_val and lon_val:
        try:
            latitude = Decimal(str(float(lat_val)))
            longitude = Decimal(str(float(lon_val)))
        except (ValueError, TypeError):
            latitude = None
            longitude = None

    client_ip = request.META.get('REMOTE_ADDR', '')

    if action == 'punch_in':
        if attendance.in_time:
            messages.error(request, "You have already punched in for today.")
        else:
            old_val = f"in: None, out: {attendance.out_time}"
            attendance.in_time = now_time
            # Punch in is recorded, punch out is marked as missing until completed
            attendance.status = 'Missing Punch-Out'
            attendance.update_source = f"{profile.role} Punch"

            if photo_data:
                photo_file = parse_base64_image(photo_data, f"in_{profile.employee_code}")
                if photo_file:
                    attendance.in_photo = photo_file

            if latitude and longitude:
                attendance.in_latitude = latitude
                attendance.in_longitude = longitude
                attendance.in_location = loc_desc or f"GPS: {latitude}, {longitude}"

            attendance.save()

            # Record audit log
            AttendanceAuditLog.objects.create(
                attendance=attendance,
                changed_by=request.user,
                action='PUNCH_IN',
                old_values=old_val,
                new_values=f"Time: {now_time}, GPS: ({latitude}, {longitude}), Location: {attendance.in_location}",
                ip_address=client_ip
            )
            messages.success(request, f"Punch In recorded at {now_time.strftime('%I:%M %p')} with photo & GPS verification.")

    elif action == 'punch_out':
        if not attendance.in_time:
            messages.error(request, "Please punch in before recording punch out.")
        elif attendance.out_time:
            messages.error(request, "You have already punched out for today.")
        else:
            old_val = f"in: {attendance.in_time}, out: None"
            attendance.out_time = now_time
            attendance.update_source = f"{profile.role} Punch"

            if photo_data:
                photo_file = parse_base64_image(photo_data, f"out_{profile.employee_code}")
                if photo_file:
                    attendance.out_photo = photo_file

            if latitude and longitude:
                attendance.out_latitude = latitude
                attendance.out_longitude = longitude
                attendance.out_location = loc_desc or f"GPS: {latitude}, {longitude}"

            attendance.save()

            # Record audit log
            AttendanceAuditLog.objects.create(
                attendance=attendance,
                changed_by=request.user,
                action='PUNCH_OUT',
                old_values=old_val,
                new_values=f"Time: {now_time}, GPS: ({latitude}, {longitude}), Duration: {attendance.total_work_time}",
                ip_address=client_ip
            )
            messages.success(request, f"Punch Out recorded at {now_time.strftime('%I:%M %p')}. Total: {attendance.total_work_time}")

            # Automatic Casual Leave restoration if employee applied for leave but attended office
            restored, msg = check_and_restore_casual_leave_on_attendance(profile, today, attendance, changed_by=request.user)
            if restored:
                messages.info(request, f"Notice: Casual leave for today was automatically cancelled because you attended office and completed {attendance.total_work_time}. 1 day has been restored to your Casual Leave balance! (New Balance: {profile.casual_leave_balance})")

    return redirect('dashboard:index')


@login_required
@hr_or_admin_required
def attendance_list(request):
    reset_daily_missed_punch_in_status()
    date_filter = request.GET.get('date', '')
    employee_code = request.GET.get('employee_code', '').strip()

    records = Attendance.objects.select_related('employee', 'employee__user', 'employee__department').all()

    if date_filter:
        records = records.filter(date=date_filter)
    if employee_code:
        records = records.filter(employee__employee_code__icontains=employee_code)

    manual_form = ManualAttendanceForm()
    device_form = BiometricDeviceForm()
    devices = BiometricDevice.objects.all()

    context = {
        'attendances': records,  # Passed for CSS scroll container
        'date_filter': date_filter,
        'employee_code': employee_code,
        'manual_form': manual_form,
        'device_form': device_form,
        'devices': devices,
        'total_count': records.count(),
    }
    return render(request, 'attendance/attendance_list.html', context)


@login_required
@hr_or_admin_required
def manual_update(request):
    """Allows authorized Admin and HR users to manually add or correct attendance with full audit logs."""
    if request.method == 'POST':
        form = ManualAttendanceForm(request.POST)
        if form.is_valid():
            emp = form.cleaned_data['employee']
            att_date = form.cleaned_data['date']
            att, created = Attendance.objects.get_or_create(employee=emp, date=att_date)

            old_val = f"in: {att.in_time}, out: {att.out_time}, status: {att.status}"
            att.in_time = form.cleaned_data['in_time']
            att.out_time = form.cleaned_data['out_time']
            att.status = form.cleaned_data['status']
            att.leave_type = form.cleaned_data.get('leave_type', '')
            att.leave_reason = form.cleaned_data.get('leave_reason', '')
            if att.status == 'Permission - 2 Hours':
                att.is_permission = True
                att.permission_hours = Decimal('2.00')
            elif att.status == 'On Leave':
                att.is_approved_leave = True

            att.updated_by = request.user
            att.update_source = 'HR/Admin Manual Update'
            att.save()

            # Record audit log
            AttendanceAuditLog.objects.create(
                attendance=att,
                changed_by=request.user,
                action='MANUAL_UPDATE' if not created else 'MANUAL_CREATE',
                old_values=old_val if not created else 'NEW_RECORD',
                new_values=f"in: {att.in_time}, out: {att.out_time}, status: {att.status}, type: {att.leave_type}",
                ip_address=request.META.get('REMOTE_ADDR', '')
            )

            # Automatic Casual Leave restoration if employee attended office
            restored, msg = check_and_restore_casual_leave_on_attendance(emp, att_date, att, changed_by=request.user)
            if restored:
                messages.info(request, f"Notice: Casual leave for {emp.display_name()} on {att_date} was cancelled and +1 day restored to balance due to recorded office attendance ({att.total_work_time}).")

            messages.success(request, f"Attendance record for {emp.display_name()} ({att_date}) updated with audit trail.")
            return redirect(request.META.get('HTTP_REFERER') or 'attendance:list')
        else:
            for err_list in form.errors.values():
                for err in err_list:
                    messages.error(request, err)
    return redirect('attendance:list')


@login_required
@hr_or_admin_required
def mark_official_duty(request):
    """
    Allows authorized HR and Admin users to mark an employee as on official office duty
    or official work assignment for a selected date.
    Automatically marks the employee as Present instead of Leave, restores casual leave balance
    if previously deducted, and synchronizes attendance and payroll calculations with audit logging.
    """
    if request.method == 'POST':
        emp_id = request.POST.get('employee_id')
        date_str = request.POST.get('date')
        duty_title = request.POST.get('duty_title', '').strip() or 'Official Office Duty / Work Assignment'
        notes = request.POST.get('notes', '').strip()

        if not emp_id or not date_str:
            messages.error(request, "Please select both an employee and a date.")
            return redirect(request.META.get('HTTP_REFERER') or 'attendance:list')

        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, "Invalid date format. Please use YYYY-MM-DD.")
            return redirect(request.META.get('HTTP_REFERER') or 'attendance:list')

        target_emp = get_object_or_404(Employee, id=emp_id)
        success, msg = mark_employee_official_duty(
            employee=target_emp,
            att_date=target_date,
            duty_title=duty_title,
            notes=notes,
            marked_by=request.user
        )
        if success:
            messages.success(request, msg)
        else:
            messages.error(request, msg)

    return redirect(request.META.get('HTTP_REFERER') or 'attendance:list')




@login_required
@hr_or_admin_required
def device_manage(request):
    """Allows Admin/HR to register biometric devices or trigger automated sync."""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_device':
            form = BiometricDeviceForm(request.POST)
            if form.is_valid():
                device = form.save()
                messages.success(request, f"Biometric device '{device.name}' added successfully.")
            else:
                for err_list in form.errors.values():
                    for err in err_list:
                        messages.error(request, err)
        elif action == 'test_device':
            device_id = request.POST.get('device_id')
            device = get_object_or_404(BiometricDevice, id=device_id)
            online, msg = test_device_connection(device)
            if online:
                messages.success(request, f"Biometric Device '{device.name}': {msg}")
            else:
                messages.warning(request, f"Biometric Device '{device.name}': {msg}")
        elif action == 'sync_device':
            device_id = request.POST.get('device_id')
            device = get_object_or_404(BiometricDevice, id=device_id)
            synced, msg = sync_biometric_device(device, user=request.user)
            if synced > 0:
                messages.success(request, msg)
            else:
                messages.info(request, msg)

    return redirect('attendance:list')


@login_required
def daily_work_list(request):
    profile = getattr(request.user, 'employee', None)
    is_management = profile and profile.role in ('ADMIN', 'HR')

    if is_management:
        works = DailyWork.objects.select_related('employee', 'employee__user').all()
    else:
        works = DailyWork.objects.filter(employee=profile)

    form = DailyWorkForm()
    if request.method == 'POST':
        form = DailyWorkForm(request.POST, request.FILES)
        if form.is_valid():
            work = form.save(commit=False)
            work.employee = profile
            work.date = timezone.localdate()
            work.save()
            messages.success(request, "Daily task report with attachment submitted successfully.")
            return redirect('attendance:daily_work')
        else:
            for err_list in form.errors.values():
                for err in err_list:
                    messages.error(request, err)

    context = {
        'works': works,
        'form': form,
        'is_management': is_management,
    }
    return render(request, 'attendance/daily_work_list.html', context)
