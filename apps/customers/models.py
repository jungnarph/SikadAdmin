# Updated content for jungnarph/sikadadmin/SikadAdmin-536c6c488986007128f3aeddc27af5ff3c51f130/apps/customers/models.py
"""
Customer Models - PostgreSQL Analytics Models
Primary data stored in Firebase, synced to PostgreSQL for analytics
"""

from django.db import models
import uuid


class Customer(models.Model):
    """
    Customer analytics model synced from Firebase
    Firebase Structure:
    customers/{customer_id}/
        - email: string
        - phone_number: string
        - name: string # CHANGED: Replaces full_name/username
        - profile_image_url: string
        - status: string
        - created_at: timestamp
    """

    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('SUSPENDED', 'Suspended'),
        ('BANNED', 'Banned'),
        ('PENDING', 'Pending Verification'),
    ]

    VERIFICATION_STATUS_CHOICES = [
        ('UNVERIFIED', 'Unverified'),
        ('VERIFIED', 'Verified'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    firebase_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Document ID from Firebase (UID)"
    )

    # Personal Information
    email = models.EmailField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    name = models.CharField(max_length=255, blank=True)
    profile_image_url = models.URLField(max_length=500, blank=True, null=True)

    # Account Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ACTIVE'
    )
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS_CHOICES,
        default='UNVERIFIED'
    )

    # Account Dates
    # REMOVED: email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    registration_date = models.DateTimeField(null=True, blank=True)
    last_login = models.DateTimeField(null=True, blank=True)

    # Statistics (calculated fields)
    total_rides = models.IntegerField(default=0)
    total_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    account_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Administrative
    suspension_reason = models.TextField(blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspended_by = models.ForeignKey(
        'accounts.AdminUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='suspended_customers'
    )

    # REMOVED: username = models.CharField(max_length=150, blank=True, help_text="Customer's chosen username")

    # Sync metadata
    synced_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'customers'
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'
        indexes = [
            models.Index(fields=['firebase_id']),
            models.Index(fields=['email']),
            models.Index(fields=['phone_number']),
            models.Index(fields=['status']),
            models.Index(fields=['registration_date']),
        ]
        ordering = ['-registration_date']

    def __str__(self):
        # CHANGED: Use 'name' field
        return f"{self.name or self.email or self.firebase_id}"

    @property
    def is_suspended(self):
        return self.status == 'SUSPENDED'

    @property
    def is_active(self):
        return self.status == 'ACTIVE'


class CustomerRideHistory(models.Model):
    """
    Customer ride history synced from Firebase
    """

    RENTAL_STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    firebase_id = models.CharField(max_length=255, unique=True, db_index=True)

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='ride_history',
        to_field='firebase_id',
        db_column='customer_firebase_id'
    )

    bike_id = models.CharField(max_length=255, db_index=True)

    # Rental Details
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.IntegerField(default=0)

    # Location
    start_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    start_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    end_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    end_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    start_zone_id = models.CharField(max_length=255, blank=True)
    end_zone_id = models.CharField(max_length=255, blank=True)

    # Metrics
    distance_km = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Payment
    amount_charged = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=20, default='PENDING')

    # Status
    rental_status = models.CharField(
        max_length=20,
        choices=RENTAL_STATUS_CHOICES,
        default='ACTIVE'
    )

    # Notes
    cancellation_reason = models.TextField(blank=True)

    synced_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'customer_ride_history'
        verbose_name = 'Ride History'
        verbose_name_plural = 'Ride History'
        indexes = [
            models.Index(fields=['customer', 'start_time']),
            models.Index(fields=['bike_id']),
            models.Index(fields=['start_time']),
            models.Index(fields=['rental_status']),
        ]
        ordering = ['-start_time']

    def __str__(self):
        # CHANGED: Use 'name' from related customer
        return f"{self.customer.name} - {self.bike_id} - {self.start_time}"


# REMOVED CustomerActivityLog model


class CustomerStatistics(models.Model):
    """Daily customer statistics for analytics"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='statistics',
        to_field='firebase_id',
        db_column='customer_firebase_id'
    )

    stats_date = models.DateField()

    rides_count = models.IntegerField(default=0)
    total_distance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_duration = models.IntegerField(default=0, help_text="Total minutes")
    total_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'customer_statistics'
        verbose_name = 'Customer Statistics'
        verbose_name_plural = 'Customer Statistics'
        unique_together = ['customer', 'stats_date']
        indexes = [
            models.Index(fields=['customer', 'stats_date']),
            models.Index(fields=['stats_date']),
        ]
        ordering = ['-stats_date']

    def __str__(self):
        # CHANGED: Use 'name' from related customer
        return f"{self.customer.name} - {self.stats_date}"