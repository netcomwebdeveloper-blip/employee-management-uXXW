from django.db import models
from apps.employees.models import Employee

class SalaryStructure(models.Model):
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='salary_structure')
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    hra = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    pf_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    tax_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total_earnings(self):
        return self.basic_salary + self.hra + self.allowances

    @property
    def total_deductions(self):
        return self.pf_deduction + self.tax_deduction

    @property
    def net_salary(self):
        return max(0, self.total_earnings - self.total_deductions)

    def __str__(self):
        return f"{self.employee.employee_code} - Net: ₹{self.net_salary:.2f}"


class PayrollRecord(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Processing', 'Processing'),
        ('Paid', 'Paid'),
    )

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payroll_records')
    year = models.IntegerField()
    month = models.IntegerField()
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2)
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    net_salary = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    payment_date = models.DateField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('employee', 'year', 'month')
        ordering = ['-year', '-month', 'employee__employee_code']
        verbose_name = 'Payroll Record'
        verbose_name_plural = 'Payroll Records'

    def __str__(self):
        return f"{self.employee.employee_code} - {self.month}/{self.year} (₹{self.net_salary:.2f})"
