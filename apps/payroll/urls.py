from django.urls import path
from . import views

app_name = 'payroll'

urlpatterns = [
    path('', views.payroll_list, name='list'),
    path('generate/', views.generate_payroll, name='generate'),
    path('<int:pk>/payslip/', views.payslip_detail, name='payslip'),
    path('<int:pk>/mark-paid/', views.mark_paid, name='mark_paid'),
]
