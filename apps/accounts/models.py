"""
Admin User Models - Stored in PostgreSQL
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid
import random # Add import
import string # Add import
from django.utils import timezone # Add import
from datetime import timedelta # Add import


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

    is_mfa_enabled = models.BooleanField(default=False, help_text="Designates whether the user has MFA enabled.")
    mfa_email_code = models.CharField(max_length=6, blank=True, null=True, help_text="Temporary code sent via email.")
    mfa_code_expiry = models.DateTimeField(blank=True, null=True, help_text="Expiry time for the MFA code.")
    
    class Meta:
        db_table = 'admin_users'
        verbose_name = 'Admin User'
        verbose_name_plural = 'Admin Users'
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username
    
    def generate_mfa_code(self):
        """Generates a 6-digit code, saves it with expiry, and returns it."""
        code = "".join(random.choices(string.digits, k=6))
        self.mfa_email_code = code
        # Set expiry (e.g., 5 minutes from now)
        self.mfa_code_expiry = timezone.now() + timedelta(minutes=5)
        self.save(update_fields=['mfa_email_code', 'mfa_code_expiry'])
        return code

    def verify_mfa_code(self, submitted_code):
        """Verifies the submitted MFA code against the stored one and checks expiry."""
        if not self.mfa_email_code or not self.mfa_code_expiry:
            return False # No code generated or already used/expired in a previous check

        if timezone.now() > self.mfa_code_expiry:
            # Code expired, clear it
            self.mfa_email_code = None
            self.mfa_code_expiry = None
            self.save(update_fields=['mfa_email_code', 'mfa_code_expiry'])
            return False # Indicate code expired

        is_valid = (submitted_code == self.mfa_email_code)

        if is_valid:
            # Code is valid, clear it immediately to prevent reuse
            self.mfa_email_code = None
            self.mfa_code_expiry = None
            self.save(update_fields=['mfa_email_code', 'mfa_code_expiry'])

        return is_valid

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