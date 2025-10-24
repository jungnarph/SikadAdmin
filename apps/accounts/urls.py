"""
Accounts URL Configuration
"""

from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication
    path('login/', views.admin_login, name='login'),
    path('logout/', views.admin_logout, name='logout'),
    
    # Profile Management
    path('profile/', views.profile, name='profile'),
    path('change-password/', views.change_password, name='change_password'),
    
    # Password Reset Flow
    path('password-reset/', views.password_reset_request, name='password_reset'),
    path('password-reset/sent/', views.password_reset_sent, name='password_reset_sent'),
    path('password-reset/<uidb64>/<token>/', views.password_reset_confirm, name='password_reset_confirm'),
    path('password-reset/complete/', views.password_reset_complete, name='password_reset_complete'),
]
