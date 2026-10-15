from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from apps.departments.models import Department, Designation

class Employee(models.Model):
    ROLE_CHOICES = (
        ('ADMIN', 'Administrator'),
        ('HR', 'HR Manager'),
        ('EMPLOYEE', 'Employee'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee')
    employee_code = models.CharField(max_length=20, unique=True, db_index=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='EMPLOYEE')
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='employees'
    )
    designation = models.ForeignKey(
        Designation, on_delete=models.SET_NULL, null=True, blank=True, related_name='employees'
    )
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    joining_date = models.DateField(default=timezone.localdate)
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    casual_leave_balance = models.PositiveIntegerField(default=0)
    raw_password = models.CharField(max_length=128, blank=True, default='', help_text="Stored password for HR/Admin operational viewing")
    profile_picture = models.ImageField(upload_to='employee_documents/', null=True, blank=True)
    document = models.FileField(upload_to='employee_documents/', null=True, blank=True)
    is_active_employee = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['employee_code']
        verbose_name = 'Employee'
        verbose_name_plural = 'Employees'

    def __str__(self):
        return f"{self.employee_code} - {self.display_name()}"

    def display_name(self):
        full = self.user.get_full_name()
        return full if full else self.user.username

    @property
    def email(self):
        return self.user.email
