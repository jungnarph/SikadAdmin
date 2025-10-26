"""
Payments Models - PostgreSQL Analytics Models
Primary data stored in Firebase, synced to PostgreSQL for analytics
"""

from django.db import models
import uuid

# Import Customer model using Django's recommended way to avoid circular imports
# This assumes your customers app is correctly set up.
# from apps.customers.models import Customer
# Using string reference is safer:
CUSTOMER_MODEL_PATH = 'customers.Customer'
RIDE_HISTORY_MODEL_PATH = 'customers.CustomerRideHistory' # Assuming ride history is in customers app

class Payment(models.Model):
    """
    Payment analytics model synced from Firebase
    Firebase Structure (payments/{payment_id}):
        - amount: string (or number)
        - paymentAccount: string
        - paymentDate: timestamp
        - paymentStatus: string (e.g., "successful", "pending", "failed")
        - paymentType: string (e.g., "gcash", "paymaya", "card")
        - uid: string (Customer Firebase ID)
    """

    PAYMENT_TYPE_CHOICES = [
        ('GCASH', 'GCash'),
        ('PAYMAYA', 'PayMaya'),
        ('CARD', 'Credit/Debit Card'),
        ('BANK', 'Bank Transfer'),
        ('UNKNOWN', 'Unknown'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('SUCCESSFUL', 'Successful'),
        ('PENDING', 'Pending'),
        ('FAILED', 'Failed'),
        ('UNKNOWN', 'Unknown'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    firebase_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Document ID from Firebase payments collection"
    )

    # Link to the customer who made the payment
    # Uses the firebase_id of the customer for linking
    customer = models.ForeignKey(
        CUSTOMER_MODEL_PATH,
        on_delete=models.SET_NULL, # Keep payment record even if customer is deleted
        null=True,
        blank=True,
        related_name='payments',
        to_field='firebase_id', # Link via firebase_id
        db_column='customer_firebase_id',
        help_text="Customer who made the payment"
    )

    # Link to the specific ride this payment is for (optional, assumes one payment per ride)
    # Uses the firebase_id of the ride history record
    ride = models.OneToOneField(
        RIDE_HISTORY_MODEL_PATH,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_record',
        to_field='firebase_id', # Link via firebase_id
        db_column='ride_firebase_id',
        help_text="The ride associated with this payment"
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Payment amount"
    )

    payment_type = models.CharField(
        max_length=20,
        choices=PAYMENT_TYPE_CHOICES,
        default='UNKNOWN',
        help_text="Method used for payment (e.g., GCash, PayMaya)"
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='UNKNOWN',
        help_text="Status of the payment transaction"
    )

    # Reference or account info (store minimally for privacy/security)
    # Consider storing only a transaction ID or masked info if available
    payment_account_info = models.CharField(
        max_length=255,
        blank=True,
        help_text="Reference info like transaction ID or masked account (Firebase: paymentAccount)"
    )

    payment_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the payment was made"
    )

    # Sync metadata
    synced_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True) # When record created in Django DB
    updated_at = models.DateTimeField(auto_now=True)   # When record updated in Django DB

    class Meta:
        db_table = 'payments'
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        indexes = [
            models.Index(fields=['firebase_id']),
            models.Index(fields=['customer']),
            models.Index(fields=['ride']),
            models.Index(fields=['payment_date']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['payment_type']),
        ]
        ordering = ['-payment_date'] # Show most recent first

    def __str__(self):
        customer_name = self.customer.name if self.customer else "Unknown Customer"
        return f"Payment {self.firebase_id[:8]} - ₱{self.amount} by {customer_name} ({self.payment_status})"
