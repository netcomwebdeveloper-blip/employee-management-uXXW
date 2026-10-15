from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('profile/', views.user_profile_view, name='profile'),
]
