from django.contrib import admin
from .models import Department, Designation

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'employee_count', 'created_at')
    search_fields = ('name', 'code')

@admin.register(Designation)
class DesignationAdmin(admin.ModelAdmin):
    list_display = ('title', 'department')
    search_fields = ('title', 'department__name')
    list_filter = ('department',)
