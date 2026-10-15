from django.contrib import admin
from .models import Attendance, DailyWork, DailyWorkPlan

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'in_time', 'out_time', 'total_work_time', 'status', 'update_source')
    list_filter = ('date', 'status', 'update_source')
    search_fields = ('employee__employee_code', 'employee__user__username')

@admin.register(DailyWork)
class DailyWorkAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'project_name', 'status')
    list_filter = ('date', 'status')
    search_fields = ('employee__employee_code', 'project_name')

@admin.register(DailyWorkPlan)
class DailyWorkPlanAdmin(admin.ModelAdmin):
    list_display = ('employee', 'work_date', 'title', 'status', 'assigned_by', 'created_at')
    list_filter = ('work_date', 'status')
    search_fields = ('employee__employee_code', 'employee__user__first_name', 'title', 'tasks')
