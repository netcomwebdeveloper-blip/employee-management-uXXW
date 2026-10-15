from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.reports_index, name='index'),
    path('attendance/', views.attendance_report, name='attendance'),
    path('leave/', views.leave_report, name='leave'),
    path('payroll/', views.payroll_report, name='payroll'),
    path('complete-export/', views.complete_hr_report_export, name='complete_export'),
]
