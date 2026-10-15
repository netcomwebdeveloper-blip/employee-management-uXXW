from django.contrib import admin
from .models import LeaveRequest, MonthlyLeaveCredit

@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('employee', 'leave_type', 'from_date', 'to_date', 'total_days', 'status', 'applied_on')
    list_filter = ('status', 'leave_type', 'from_date')
    search_fields = ('employee__employee_code', 'employee__user__username', 'reason')

@admin.register(MonthlyLeaveCredit)
class MonthlyLeaveCreditAdmin(admin.ModelAdmin):
    list_display = ('employee', 'year', 'month', 'casual_added', 'credited_on')
    list_filter = ('year', 'month')

from .models import HRNotification, OfficePaidLeave
@admin.register(HRNotification)
class HRNotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient_role', 'is_read', 'created_at')
    list_filter = ('recipient_role', 'is_read')

@admin.register(OfficePaidLeave)
class OfficePaidLeaveAdmin(admin.ModelAdmin):
    list_display = ('date', 'title', 'marked_by', 'created_at')
    list_filter = ('date',)

