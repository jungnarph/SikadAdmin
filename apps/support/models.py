"""
Support Request Models - PostgreSQL Analytics Models
Primary data synced from Firebase support_requests collection
"""

from django.db import models
import uuid

# Using string references for related models to avoid circular imports
CUSTOMER_MODEL_PATH = 'customers.Customer'


class SupportRequest(models.Model):
    """
    Support Request model synced from Firebase support_requests collection
    Firebase Structure (support_requests/{request_id}):
        - appVersion: string
        - assignedTo: string (admin user ID)
        - issue: string (description of the issue)
        - priority: string (low, medium, high, critical)
        - response: string (admin response)
        - status: string (pending, in_progress, resolved, closed)
        - submissionTime: string (formatted datetime)
        - testId: string (unique identifier)
        - timestamp: number (unix timestamp in milliseconds)
        - userId: string (Customer Firebase ID)
    """

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    firebase_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Document ID from Firebase support_requests collection"
    )

    # --- Relationships ---
    customer = models.ForeignKey(
        CUSTOMER_MODEL_PATH,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='support_requests',
        to_field='firebase_id',
        db_column='customer_firebase_id',
        help_text="Customer who submitted the support request (Firebase: userId)"
    )

    # --- Request Details ---
    issue = models.TextField(help_text="Description of the issue")
    response = models.TextField(blank=True, help_text="Admin response to the issue")

    app_version = models.CharField(
        max_length=50,
        blank=True,
        help_text="App version when the issue was reported"
    )

    test_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="Test identifier from Firebase"
    )

    # --- Status and Priority ---
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text="Current status of the support request"
    )

    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='medium',
        db_index=True,
        help_text="Priority level of the support request"
    )

    # --- Assignment ---
    assigned_to = models.CharField(
        max_length=255,
        blank=True,
        help_text="Admin user assigned to this request"
    )

    # --- Timestamps ---
    submission_time = models.CharField(
        max_length=255,
        blank=True,
        help_text="Formatted submission time from Firebase"
    )

    timestamp = models.BigIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Unix timestamp in milliseconds from Firebase"
    )

    submission_datetime = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Converted datetime from timestamp"
    )

    # --- Sync Metadata ---
    synced_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'support_requests'
        verbose_name = 'Support Request'
        verbose_name_plural = 'Support Requests'
        indexes = [
            models.Index(fields=['firebase_id']),
            models.Index(fields=['customer']),
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['submission_datetime']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        customer_ref = self.customer.name if self.customer else "Unknown"
        return f"Support #{self.firebase_id[:8]} - {customer_ref} ({self.status})"

    def save(self, *args, **kwargs):
        # Convert timestamp to datetime if available
        if self.timestamp and not self.submission_datetime:
            from datetime import datetime
            self.submission_datetime = datetime.fromtimestamp(self.timestamp / 1000)
        super().save(*args, **kwargs)