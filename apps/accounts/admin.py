"""
Accounts Admin Configuration
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import AdminUser, SessionTracking


@admin.register(AdminUser)
class AdminUserAdmin(UserAdmin):
    """Custom admin for AdminUser"""
    list_display = ['username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'date_joined']
    list_filter = ['role', 'is_active', 'is_staff', 'is_superuser', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'phone_number')}),
        ('Permissions', {
            'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'role'),
        }),
    )

@admin.register(SessionTracking)
class SessionTrackingAdmin(admin.ModelAdmin):
    """Admin for SessionTracking"""
    list_display = ['admin_user', 'ip_address', 'login_time', 'last_activity', 'is_active']
    list_filter = ['is_active', 'login_time']
    search_fields = ['admin_user__username', 'ip_address']
    readonly_fields = ['admin_user', 'session_key', 'ip_address', 'user_agent', 'login_time', 'last_activity', 'logout_time']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False