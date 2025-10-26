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


class CustomerPaymentMethod(models.Model):
    """Customer payment methods"""

    PAYMENT_TYPE_CHOICES = [
        ('GCASH', 'GCash'),
        ('PAYMAYA', 'PayMaya'),
        ('CARD', 'Credit/Debit Card'),
        ('BANK', 'Bank Transfer'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='payment_methods',
        to_field='firebase_id',
        db_column='customer_firebase_id'
    )

    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES)
    provider_reference = models.CharField(max_length=255, blank=True)

    # Masked details for display
    masked_number = models.CharField(max_length=50, blank=True)
    holder_name = models.CharField(max_length=255, blank=True)

    is_default = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'customer_payment_methods'
        verbose_name = 'Payment Method'
        verbose_name_plural = 'Payment Methods'
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        # CHANGED: Use 'name' from related customer
        return f"{self.customer.name} - {self.get_payment_type_display()} - {self.masked_number}"


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


class CustomerActivityLog(models.Model):
    """Log of customer activities"""

    ACTIVITY_TYPE_CHOICES = [
        ('REGISTRATION', 'Registration'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('RENTAL_START', 'Rental Started'),
        ('RENTAL_END', 'Rental Ended'),
        ('PAYMENT', 'Payment Made'),
        ('PROFILE_UPDATE', 'Profile Updated'),
        ('VERIFICATION_SUBMITTED', 'Verification Submitted'),
        ('SUSPENSION', 'Account Suspended'),
        ('REACTIVATION', 'Account Reactivated'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='activity_logs',
        to_field='firebase_id',
        db_column='customer_firebase_id'
    )

    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPE_CHOICES)
    description = models.TextField(blank=True)

    # Location data
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_info = models.CharField(max_length=255, blank=True)

    # Related references
    related_id = models.CharField(max_length=255, blank=True, help_text="Related rental, payment, etc.")

    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'customer_activity_logs'
        verbose_name = 'Activity Log'
        verbose_name_plural = 'Activity Logs'
        indexes = [
            models.Index(fields=['customer', 'timestamp']),
            models.Index(fields=['activity_type']),
            models.Index(fields=['timestamp']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
         # CHANGED: Use 'name' from related customer
        return f"{self.customer.name} - {self.get_activity_type_display()} - {self.timestamp}"


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