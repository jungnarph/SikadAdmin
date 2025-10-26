"""
Ride Models - PostgreSQL Analytics Models
Primary data synced from Firebase ride_logs collection
"""

from django.db import models
import uuid

# Using string references for related models to avoid circular imports
CUSTOMER_MODEL_PATH = 'customers.Customer'
PAYMENT_MODEL_PATH = 'payments.Payment'
BIKE_MODEL_PATH = 'bikes.Bike' # Assuming bike model is needed

class Ride(models.Model):
    """
    Ride analytics model synced from Firebase ride_logs collection
    Firebase Structure (ride_logs/{ride_id}):
        - bikeId: string
        - endTime: timestamp or null
        - paymentId: string (links to payments collection)
        - points: map (containing lat/lng/timestamp objects) - Store as JSON
        - startTime: timestamp
        - userId: string (Customer Firebase ID)
    """

    RENTAL_STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('UNKNOWN', 'Unknown'), # Added for robustness
    ]

    PAYMENT_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('FAILED', 'Failed'),
        ('REFUNDED', 'Refunded'),
        ('UNKNOWN', 'Unknown'), # Added for robustness
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    firebase_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Document ID from Firebase ride_logs collection"
    )

    # --- Relationships ---
    customer = models.ForeignKey(
        CUSTOMER_MODEL_PATH,
        on_delete=models.SET_NULL, # Keep ride record even if customer is deleted
        null=True,
        blank=True,
        related_name='rides',
        to_field='firebase_id', # Link via customer's firebase_id
        db_column='customer_firebase_id',
        help_text="Customer who took the ride (Firebase: userId)"
    )

    bike = models.ForeignKey(
        BIKE_MODEL_PATH,
        on_delete=models.SET_NULL, # Keep ride record even if bike is deleted
        null=True,
        blank=True,
        related_name='rides',
        to_field='firebase_id', # Link via bike's firebase_id
        db_column='bike_firebase_id',
        help_text="Bike used for the ride (Firebase: bikeId)"
    )

    # Use OneToOneField from Payment to Ride instead, keep this nullable for now
    # If a ride MUST have a payment, change null/blank later
    # payment = models.ForeignKey(
    #     PAYMENT_MODEL_PATH,
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name='rides',
    #     to_field='firebase_id', # Link via payment's firebase_id
    #     db_column='payment_firebase_id',
    #     help_text="Payment associated with this ride (Firebase: paymentId)"
    # )

    # --- Ride Details ---
    start_time = models.DateTimeField(null=True, blank=True, help_text="Timestamp when the ride started")
    end_time = models.DateTimeField(null=True, blank=True, help_text="Timestamp when the ride ended")
    duration_minutes = models.IntegerField(default=0, help_text="Calculated duration of the ride in minutes")

    # --- Location ---
    # Store aggregated start/end, actual path points stored in JSON
    start_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    start_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    end_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    end_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    # Store the points array/map from Firebase as JSON
    # Format: [{"latitude": float, "longitude": float, "timestamp": iso_string}, ...]
    ride_path_points = models.JSONField(
        default=list,
        help_text="List of coordinate points recorded during the ride"
    )

    start_zone_id = models.CharField(max_length=255, blank=True, help_text="Firebase zone ID where ride started")
    end_zone_id = models.CharField(max_length=255, blank=True, help_text="Firebase zone ID where ride ended")

    # --- Metrics ---
    distance_km = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Calculated distance of the ride in kilometers"
    )

    # --- Payment ---
    amount_charged = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Amount charged for the ride"
    )
    # Status primarily tracked on the Payment model, but can be denormalized here for quick lookup
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='PENDING',
        help_text="Status of the payment associated with this ride"
    )

    # --- Status ---
    rental_status = models.CharField(
        max_length=20,
        choices=RENTAL_STATUS_CHOICES,
        default='ACTIVE',
        help_text="Current status of the ride/rental"
    )

    # --- Notes ---
    cancellation_reason = models.TextField(blank=True)

    # --- Sync Metadata ---
    synced_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True) # When record created in Django DB
    updated_at = models.DateTimeField(auto_now=True)   # When record updated in Django DB

    class Meta:
        db_table = 'rides' # New table name
        verbose_name = 'Ride'
        verbose_name_plural = 'Rides'
        indexes = [
            models.Index(fields=['firebase_id']),
            models.Index(fields=['customer']),
            models.Index(fields=['bike']),
            models.Index(fields=['start_time']),
            models.Index(fields=['rental_status']),
            models.Index(fields=['payment_status']),
        ]
        ordering = ['-start_time'] # Show most recent first

    def __str__(self):
        customer_ref = self.customer.name if self.customer else self.customer_id[:8] if self.customer_id else "Unknown"
        bike_ref = self.bike.firebase_id if self.bike else self.bike_id[:8] if self.bike_id else "Unknown"
        return f"Ride {self.firebase_id[:8]} - Cust: {customer_ref}, Bike: {bike_ref} ({self.rental_status})"

    def save(self, *args, **kwargs):
        # Potential place to add logic to calculate duration or distance if needed
        # Or parse start/end points from ride_path_points
        super().save(*args, **kwargs)