from django.contrib import admin
from .models import DashboardBanner

@admin.register(DashboardBanner)
class DashboardBannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'uploaded_by', 'created_at')
    list_filter = ('is_active',)
