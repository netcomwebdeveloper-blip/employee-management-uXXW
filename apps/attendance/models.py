from datetime import datetime, timedelta
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from apps.employees.models import Employee

class Attendance(models.Model):
    STATUS_CHOICES = (
        ('Present', 'Present (Full Day)'),
        ('Half Day', 'Half Day'),
        ('Permission - 2 Hours', 'Permission – 2 Hours'),
        ('On Leave', 'Approved Leave'),
        ('Official Duty', 'Official Duty (Present)'),
        ('Absent', 'Absent'),
        ('Missed Punch-In', 'Missed Punch-In'),
        ('Missing Punch-Out', 'Missing Punch-Out'),
        ('Pending Punch-In', 'Pending Punch-In'),
    )

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField(default=timezone.localdate, db_index=True)
    in_time = models.TimeField(null=True, blank=True)
    out_time = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='Pending Punch-In')
    is_permission = models.BooleanField(default=False)
    permission_hours = models.DecimalField(max_digits=4, decimal_places=2, default=0.00)
    is_approved_leave = models.BooleanField(default=False)
    leave_type = models.CharField(max_length=50, blank=True, default='')
    leave_reason = models.TextField(blank=True, default='')
    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    update_source = models.CharField(max_length=50, default='Employee Punch')
    in_photo = models.ImageField(upload_to='attendance_photos/in/%Y/%m/', null=True, blank=True)
    out_photo = models.ImageField(upload_to='attendance_photos/out/%Y/%m/', null=True, blank=True)
    in_latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    in_longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    out_latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    out_longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    in_location = models.CharField(max_length=255, blank=True, default='')
    out_location = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('employee', 'date')
        ordering = ['-date', '-id']
        verbose_name = 'Attendance'
        verbose_name_plural = 'Attendance Records'

    def __str__(self):
        return f"{self.employee.employee_code} - {self.date} ({self.status})"

    @property
    def is_official_duty(self):
        """Returns True if marked for Official Office Duty / Official Work Assignment."""
        return self.update_source == 'Official Office Duty' or self.leave_type == 'Official Duty' or self.status == 'Official Duty'

    @property
    def is_missing_punch_out(self):
        """Returns True if employee punched in but punch-out is missing and not on official duty or leave."""
        if self.is_official_duty or self.is_approved_leave:
            return False
        return bool(self.in_time and not self.out_time)

    @property
    def is_missed_punch_in(self):
        """Returns True if employee failed to punch in for the required attendance."""
        if self.is_official_duty or self.is_approved_leave:
            return False
        return bool(not self.in_time and self.status in ('Missed Punch-In', 'Absent'))

    @property
    def total_work_minutes(self):
        # Do not calculate working hours for incomplete attendance
        if self.is_official_duty:
            return 540  # Full 9 hours for official office duty
        if not self.in_time or not self.out_time or self.is_missing_punch_out:
            return 0
        start = datetime.combine(self.date, self.in_time)
        end = datetime.combine(self.date, self.out_time)
        if end < start:
            end += timedelta(days=1)
        return int((end - start).total_seconds() // 60)

    @property
    def total_work_time(self):
        if self.is_official_duty:
            return "9h 0m (Official Duty)"
        if self.is_missing_punch_out:
            return "Incomplete (Missing Punch-Out)"
        if not self.in_time or not self.out_time:
            return "-"
        mins = self.total_work_minutes
        hours = mins // 60
        rem = mins % 60
        return f"{hours}h {rem}m"

    @property
    def is_full_day(self):
        """9 working hours (>= 540 mins) count as a full working day."""
        if self.is_official_duty:
            return True
        if self.is_missing_punch_out or not self.out_time:
            return False
        return self.total_work_minutes >= 540 or self.status == 'Present'

    @property
    def is_half_day(self):
        """4 hours and 30 minutes (>= 270 mins and < 540 mins) count as a half working day."""
        if self.is_official_duty or self.is_missing_punch_out or not self.out_time:
            return False
        if self.status == 'Half Day':
            return True
        return 270 <= self.total_work_minutes < 540

    @property
    def is_permission_approved(self):
        """Up to 2 hours of approved permission."""
        return self.is_permission or self.status == 'Permission - 2 Hours'

    def save(self, *args, **kwargs):
        # Official duty automatically Present
        if self.is_official_duty:
            self.status = 'Present'
            self.is_approved_leave = False
        # Auto-compute status when punch in & out are present and not manually overridden
        elif self.in_time and self.out_time:
            if not self.is_permission and self.status not in ('Permission - 2 Hours', 'On Leave'):
                mins = self.total_work_minutes
                if mins >= 540:
                    self.status = 'Present'
                elif mins >= 270:
                    self.status = 'Half Day'
        elif self.in_time and not self.out_time:
            if self.status not in ('Permission - 2 Hours', 'On Leave'):
                self.status = 'Missing Punch-Out'
        if self.status == 'Permission - 2 Hours':
            self.is_permission = True
            if not self.permission_hours or self.permission_hours == 0:
                self.permission_hours = Decimal('2.00')
        if self.status == 'On Leave':
            self.is_approved_leave = True
        super().save(*args, **kwargs)


class DailyWork(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
    )

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='daily_works')
    date = models.DateField(default=timezone.localdate, db_index=True)
    project_name = models.CharField(max_length=150)
    work_details = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    work_image = models.ImageField(upload_to='daily_work_images/', null=True, blank=True, verbose_name='Activity / Site Image')
    is_offsite = models.BooleanField(default=False, verbose_name='Off-Site Work Activity')
    location_notes = models.CharField(max_length=255, blank=True, verbose_name='Off-Site Location / Site Details')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']
        verbose_name = 'Daily Work'
        verbose_name_plural = 'Daily Work Submissions'

    def __str__(self):
        return f"{self.employee.employee_code} - {self.project_name} ({self.date})"


class AttendanceAuditLog(models.Model):
    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE, related_name='audit_logs')
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=50)  # PUNCH_IN, PUNCH_OUT, MANUAL_UPDATE, DEVICE_SYNC
    old_values = models.TextField(blank=True)
    new_values = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.CharField(max_length=50, blank=True, default='')

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Attendance Audit Log'
        verbose_name_plural = 'Attendance Audit Logs'

    def __str__(self):
        return f"{self.attendance.employee.employee_code} - {self.action} at {self.timestamp}"


class BiometricDevice(models.Model):
    PROTOCOL_CHOICES = (
        ('TCP', 'ZKTeco / Standalone TCP (Port 4370)'),
        ('UDP', 'Standalone UDP (Port 4370)'),
        ('REST_API', 'Network REST / Cloud Webhook API'),
    )

    name = models.CharField(max_length=100)
    device_model = models.CharField(max_length=100, default='ZKTeco K40 / iClock / Standalone')
    ip_address = models.CharField(max_length=50, default='192.168.1.201')
    port = models.IntegerField(default=4370)
    protocol = models.CharField(max_length=20, choices=PROTOCOL_CHOICES, default='TCP')
    communication_key = models.CharField(max_length=50, blank=True, default='0')
    is_active = models.BooleanField(default=True)
    last_sync = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(max_length=100, default='Ready to Connect')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Biometric Device'
        verbose_name_plural = 'Biometric Devices'

    def __str__(self):
        return f"{self.name} ({self.ip_address}:{self.port})"


class DailyWorkPlan(models.Model):
    STATUS_CHOICES = (
        ('Assigned', 'Assigned / Planned'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
        ('Deferred', 'Deferred'),
    )

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='work_plans')
    work_date = models.DateField(db_index=True, help_text='Date for which the tasks are planned')
    title = models.CharField(max_length=200, default='Daily Work Plan & Responsibilities')
    tasks = models.TextField(help_text='Specific tasks, deliverables, and responsibilities planned by HR')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='Assigned')
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_work_plans')
    is_notification_sent = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-work_date', '-created_at']
        verbose_name = 'Daily Work Plan'
        verbose_name_plural = 'Daily Work Plans'

    def __str__(self):
        return f"{self.employee.employee_code} - {self.work_date}: {self.title}"

