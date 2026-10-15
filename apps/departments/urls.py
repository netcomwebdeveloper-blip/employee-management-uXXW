from django.urls import path
from . import views

app_name = 'departments'

urlpatterns = [
    path('', views.department_list, name='list'),
    path('<int:pk>/edit/', views.department_update, name='edit'),
    path('<int:pk>/delete/', views.department_delete, name='delete'),
    path('designation/<int:pk>/delete/', views.designation_delete, name='designation_delete'),
]
