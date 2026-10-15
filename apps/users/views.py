from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages

def root_redirect_view(request):
    """Direct root URL access."""
    if request.user.is_authenticated:
        return redirect('dashboard:index')
    return redirect('login')

def custom_login_view(request):
    """Preserves exact /login/ URL with clean modern styling and robust auth."""
    if request.user.is_authenticated:
        return redirect('dashboard:index')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
                next_url = request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect('dashboard:index')
            else:
                messages.error(request, "Your account has been deactivated. Please contact HR or Administrator.")
        else:
            messages.error(request, "Invalid username or password. Please verify your credentials.")

    return render(request, 'users/login.html')

def custom_logout_view(request):
    """Secure logout view redirecting back to login."""
    if request.user.is_authenticated:
        logout(request)
        messages.info(request, "You have been logged out successfully.")
    return redirect('login')

@login_required
def user_profile_view(request):
    """Current logged-in user profile and password change."""
    profile = getattr(request.user, 'employee', None)
    password_form = PasswordChangeForm(user=request.user)

    if request.method == 'POST':
        if 'change_password' in request.POST:
            password_form = PasswordChangeForm(user=request.user, data=request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Your password was successfully updated!')
                return redirect('users:profile')
            else:
                for err_list in password_form.errors.values():
                    for err in err_list:
                        messages.error(request, err)

    return render(request, 'users/profile.html', {
        'profile': profile,
        'password_form': password_form,
    })
