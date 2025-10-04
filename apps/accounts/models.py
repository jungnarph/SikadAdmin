"""
Admin User Models - Stored in PostgreSQL
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid


class AdminUser(AbstractUser):
    """
    Custom Admin User Model
    Stored in PostgreSQL for admin authentication
    """
    
    ROLE_CHOICES = [
        ('SUPER_ADMIN', 'Super Admin'),
        ('STAFF_ADMIN', 'Staff Admin'),
        ('SUPPORT', 'Support'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone_number = models.CharField(max_length=20, blank=True)
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='SUPPORT'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'admin_users'
        verbose_name = 'Admin User'
        verbose_name_plural = 'Admin Users'
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username


class Role(models.Model):
    """Role model for future granular permissions"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'roles'
    
    def __str__(self):
        return self.name


class SessionTracking(models.Model):
    """Track admin user sessions"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin_user = models.ForeignKey(AdminUser, on_delete=models.CASCADE, related_name='sessions')
    session_key = models.CharField(max_length=255, unique=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    device_info = models.CharField(max_length=255, blank=True)
    login_time = models.DateTimeField()
    last_activity = models.DateTimeField()
    logout_time = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'session_tracking'
        indexes = [
            models.Index(fields=['admin_user']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.admin_user.username} - {self.login_time}"