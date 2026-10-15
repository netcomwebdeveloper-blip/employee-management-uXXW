from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        profile = getattr(request.user, 'employee', None)
        if profile and profile.role == 'ADMIN':
            return view_func(request, *args, **kwargs)
        messages.error(request, 'Access denied. Administrator privileges required.')
        return redirect('dashboard:index')
    return _wrapped_view

def hr_or_admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        profile = getattr(request.user, 'employee', None)
        if profile and profile.role in ('ADMIN', 'HR'):
            return view_func(request, *args, **kwargs)
        messages.error(request, 'Access denied. HR or Admin privileges required.')
        return redirect('dashboard:index')
    return _wrapped_view
