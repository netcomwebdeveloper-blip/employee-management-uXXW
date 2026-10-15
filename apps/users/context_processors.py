from datetime import date
from apps.dashboard.models import DashboardBanner, DashboardPopup

def company_context(request):
    """Provides global context to templates without hardcoded paths or values."""
    profile = None
    if request.user.is_authenticated:
        try:
            profile = getattr(request.user, 'employee', None)
        except Exception:
            profile = None

    active_banner = DashboardBanner.get_active_banner()
    active_popup = DashboardPopup.get_active_popup()

    return {
        'COMPANY_NAME': 'Netcom Computers Pvt Ltd',
        'SYSTEM_NAME': 'Employee Management System Pro',
        'CURRENT_YEAR': date.today().year,
        'CURRENT_DATE': date.today(),
        'current_profile': profile,
        'active_banner': active_banner,
        'active_popup': active_popup,
    }
