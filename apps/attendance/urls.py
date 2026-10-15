from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    path('', views.attendance_list, name='list'),
    path('punch/', views.punch_view, name='punch'),
    path('manual-update/', views.manual_update, name='manual_update'),
    path('mark-official-duty/', views.mark_official_duty, name='mark_official_duty'),
    path('device-manage/', views.device_manage, name='device_manage'),
    path('daily-work/', views.daily_work_list, name='daily_work'),
]
