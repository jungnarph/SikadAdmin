"""
Bike Models - PostgreSQL Analytics Models
Primary data stored in Firebase, synced to PostgreSQL for analytics
"""

from django.db import models
import uuid


class Bike(models.Model):
    """
    Bike analytics model synced from Firebase
    Firebase Structure:
    bikes/{bike_id}/
        - bike_model: string
        - status: string
        - current_location: GeoPoint
        - current_zone_id: string
        - bike_type: string
        - created_at: timestamp
    """
    
    BIKE_TYPE_CHOICES = [
        ('REGULAR', 'Regular'),
        ('ELECTRIC', 'Electric'),
        ('MOUNTAIN', 'Mountain'),
    ]
    
    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('IN_USE', 'In Use'),
        ('OFFLINE', 'Offline'),
        ('ARCHIVED', 'Archived'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    firebase_id = models.CharField(
        max_length=255, 
        unique=True, 
        db_index=True,
        help_text="Document ID from Firebase"
    )
    bike_model = models.CharField(max_length=100)
    bike_type = models.CharField(max_length=20, choices=BIKE_TYPE_CHOICES, default='REGULAR')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE')
    
    # Current location (synced from Firebase)
    current_latitude = models.DecimalField(
        max_digits=10, 
        decimal_places=7, 
        null=True, 
        blank=True
    )
    current_longitude = models.DecimalField(
        max_digits=10, 
        decimal_places=7, 
        null=True, 
        blank=True
    )
    
    # Zone assignment
    current_zone_id = models.CharField(
        max_length=255, 
        null=True, 
        blank=True,
        help_text="Firebase zone document ID"
    )
    
    # Sync metadata
    synced_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'bikes'
        verbose_name = 'Bike'
        verbose_name_plural = 'Bikes'
        indexes = [
            models.Index(fields=['firebase_id']),
            models.Index(fields=['status']),
            models.Index(fields=['bike_type']),
            models.Index(fields=['current_zone_id']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.firebase_id} - {self.bike_model} ({self.get_status_display()})"


class BikeLocationHistory(models.Model):
    """
    Historical bike locations synced from Firebase subcollection
    Firebase Structure:
    bikes/{bike_id}/location_history/{timestamp}/
        - location: GeoPoint
        - speed: number
        - recorded_at: timestamp
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bike = models.ForeignKey(
        Bike, 
        on_delete=models.CASCADE, 
        related_name='location_history',
        to_field='firebase_id',
        db_column='bike_firebase_id'
    )
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    speed = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Speed in km/h"
    )
    recorded_at = models.DateTimeField()
    synced_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'bike_location_history'
        verbose_name = 'Bike Location History'
        verbose_name_plural = 'Bike Location History'
        indexes = [
            models.Index(fields=['bike', 'recorded_at']),
            models.Index(fields=['recorded_at']),
        ]
        ordering = ['-recorded_at']
    
    def __str__(self):
        return f"{self.bike.firebase_id} at {self.recorded_at}"