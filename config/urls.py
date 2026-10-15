from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.users import views as user_views

urlpatterns = [
    # Django Administration Backend
    path('django-admin/', admin.site.urls),

    # Authentication Routes (Exact preservation of /login/ and /logout/ URLs)
    path('', user_views.root_redirect_view, name='home'),
    path('login/', user_views.custom_login_view, name='login'),
    path('logout/', user_views.custom_logout_view, name='logout'),

    # Modular App Endpoints
    path('dashboard/', include('apps.dashboard.urls', namespace='dashboard')),
    path('employees/', include('apps.employees.urls', namespace='employees')),
    path('departments/', include('apps.departments.urls', namespace='departments')),
    path('attendance/', include('apps.attendance.urls', namespace='attendance')),
    path('leave/', include('apps.leave_management.urls', namespace='leave_management')),
    path('payroll/', include('apps.payroll.urls', namespace='payroll')),
    path('reports/', include('apps.reports.urls', namespace='reports')),
    path('users/', include('apps.users.urls', namespace='users')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
