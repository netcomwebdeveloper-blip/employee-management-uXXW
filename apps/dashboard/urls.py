from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    path('admin/', views.admin_dashboard_view, name='admin_dashboard'),
    path('hr/', views.hr_dashboard_view, name='hr_dashboard'),
    path('employee/', views.employee_dashboard_view, name='employee_dashboard'),
]
