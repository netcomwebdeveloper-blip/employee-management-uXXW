from django.contrib import admin
from .models import SalaryStructure, PayrollRecord

@admin.register(SalaryStructure)
class SalaryStructureAdmin(admin.ModelAdmin):
    list_display = ('employee', 'basic_salary', 'hra', 'allowances', 'pf_deduction', 'tax_deduction', 'net_salary')

@admin.register(PayrollRecord)
class PayrollRecordAdmin(admin.ModelAdmin):
    list_display = ('employee', 'month', 'year', 'net_salary', 'status', 'payment_date')
    list_filter = ('year', 'month', 'status')
    search_fields = ('employee__employee_code', 'employee__user__username')
