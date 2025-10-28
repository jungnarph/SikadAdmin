"""
Geofencing Models - PostgreSQL Analytics Models
Primary data stored in Firebase, synced to PostgreSQL for analytics
"""

from django.db import models
import uuid


class Zone(models.Model):
    """
    Geofence zone analytics model synced from Firebase
    Firebase Structure:
    geofence/{zone_id}/
        - name: string
        - is_active: boolean
        - color_code: string
        - points/{index}/location: GeoPoint
        - created_at: timestamp
        - updated_at: timestamp
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    firebase_id = models.CharField(
        max_length=255, 
        unique=True, 
        db_index=True,
        help_text="Document ID from Firebase"
    )
    name = models.CharField(max_length=100)
    color_code = models.CharField(max_length=7, default='#3388ff')
    is_active = models.BooleanField(default=True)
    
    # Zone center (calculated from points)
    center_latitude = models.DecimalField(
        max_digits=10, 
        decimal_places=7, 
        null=True, 
        blank=True
    )
    center_longitude = models.DecimalField(
        max_digits=10, 
        decimal_places=7, 
        null=True, 
        blank=True
    )
    
    # Polygon data stored as JSON for PostgreSQL
    # Format: [{"lat": 14.417587, "lng": 120.884827}, ...]
    polygon_points = models.JSONField(
        default=list,
        help_text="List of lat/lng points defining the polygon"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        'accounts.AdminUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_zones'
    )
    synced_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'zones'
        verbose_name = 'Zone'
        verbose_name_plural = 'Zones'
        indexes = [
            models.Index(fields=['firebase_id']),
            models.Index(fields=['is_active']),
        ]
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @property
    def point_count(self):
        """Get number of polygon points"""
        return len(self.polygon_points) if self.polygon_points else 0


class ZoneViolation(models.Model):
    """
    Zone violation logs
    Created when bikes leave assigned zones or violate zone rules
    """
    
    VIOLATION_TYPE_CHOICES = [
        ('EXIT_ZONE', 'Exit Zone'),
        ('UNAUTHORIZED_PARKING', 'Unauthorized Parking'),
        ('SPEED_LIMIT', 'Speed Limit Violation'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    zone = models.ForeignKey(
        Zone,
        on_delete=models.CASCADE,
        related_name='violations',
        to_field='firebase_id',
        db_column='zone_firebase_id'
    )
    bike_id = models.CharField(
        max_length=255, 
        db_index=True,
        help_text="Firebase bike document ID"
    )
    customer_id = models.CharField(
        max_length=255, 
        db_index=True,
        help_text="Firebase customer document ID"
    )
    rental_id = models.CharField(
        max_length=255, 
        null=True, 
        blank=True,
        help_text="Firebase rental document ID"
    )
    
    violation_type = models.CharField(max_length=30, choices=VIOLATION_TYPE_CHOICES)
    
    # Violation location
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    
    # Violation details
    violation_time = models.DateTimeField()
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'zone_violations'
        verbose_name = 'Zone Violation'
        verbose_name_plural = 'Zone Violations'
        indexes = [
            models.Index(fields=['zone', 'violation_time']),
            models.Index(fields=['bike_id']),
            models.Index(fields=['customer_id']),
            models.Index(fields=['violation_time']),
            models.Index(fields=['resolved']),
        ]
        ordering = ['-violation_time']
    
    def __str__(self):
        return f"{self.get_violation_type_display()} - {self.bike_id} at {self.violation_time}"