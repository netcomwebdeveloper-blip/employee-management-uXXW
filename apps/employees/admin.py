from django.contrib import admin
from .models import Employee

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('employee_code', 'display_name', 'role', 'department', 'designation', 'phone', 'is_active_employee')
    list_filter = ('role', 'department', 'is_active_employee')
    search_fields = ('employee_code', 'user__username', 'user__first_name', 'user__last_name', 'phone')
