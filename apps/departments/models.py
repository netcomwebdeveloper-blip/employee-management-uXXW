from django.db import models

class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def employee_count(self):
        return self.employees.count()


class Designation(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='designations')
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        unique_together = ('department', 'title')
        ordering = ['department', 'title']
        verbose_name = 'Designation'
        verbose_name_plural = 'Designations'

    def __str__(self):
        return f"{self.title} - {self.department.name}"
