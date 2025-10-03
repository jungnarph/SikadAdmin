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