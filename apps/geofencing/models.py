"""
Geofencing Models - PostgreSQL Analytics Models
Primary data stored in Firebase, synced to PostgreSQL for analytics

This file contains 3 models:
1. Zone - Main geofence zone model
2. ZoneViolation - Violation tracking
3. ZonePerformance - Daily performance metrics
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
    name = models.CharField(max_length=100, help_text="Zone name")
    color_code = models.CharField(
        max_length=7, 
        default='#3388ff',
        help_text="Hex color code for map display"
    )
    is_active = models.BooleanField(default=True)
    
    # Zone center (calculated from polygon points)
    center_latitude = models.DecimalField(
        max_digits=10, 
        decimal_places=7, 
        null=True, 
        blank=True,
        help_text="Center latitude of the zone"
    )
    center_longitude = models.DecimalField(
        max_digits=10, 
        decimal_places=7, 
        null=True, 
        blank=True,
        help_text="Center longitude of the zone"
    )
    
    # Polygon data stored as JSON for PostgreSQL
    # Format: [{"latitude": 14.417587, "longitude": 120.884827}, ...]
    polygon_points = models.JSONField(
        default=list,
        help_text="List of lat/lng points defining the polygon boundary"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        'accounts.AdminUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_zones',
        help_text="Admin user who created this zone"
    )
    synced_at = models.DateTimeField(auto_now=True, help_text="Last sync from Firebase")
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
        return f"{self.name}"
    
    @property
    def point_count(self):
        """Get number of polygon points"""
        return len(self.polygon_points) if self.polygon_points else 0
    
    @property
    def is_polygon(self):
        """Check if zone has at least 3 points to form a polygon"""
        return self.point_count >= 3


class ZoneViolation(models.Model):
    """
    Zone violation logs
    Created when bikes leave assigned zones or violate zone rules
    Synced from Firebase or created by system monitoring
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
        db_column='zone_firebase_id',
        help_text="Reference to zone by Firebase ID"
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
        db_index=True,
        help_text="Firebase rental document ID (if applicable)"
    )
    
    violation_type = models.CharField(max_length=30, choices=VIOLATION_TYPE_CHOICES)
    
    # Violation location
    latitude = models.DecimalField(
        max_digits=10, 
        decimal_places=7,
        help_text="Latitude where violation occurred"
    )
    longitude = models.DecimalField(
        max_digits=10, 
        decimal_places=7,
        help_text="Longitude where violation occurred"
    )
    
    # Violation details
    violation_time = models.DateTimeField(help_text="When the violation occurred")
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, help_text="Additional notes or resolution details")
    
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
    
    def resolve(self, notes=""):
        """Mark violation as resolved"""
        from django.utils import timezone
        self.resolved = True
        self.resolved_at = timezone.now()
        if notes:
            self.notes = notes
        self.save()


class ZonePerformance(models.Model):
    """
    Daily zone performance metrics (aggregated from rental data)
    Generated by Celery tasks for analytics dashboard
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    zone = models.ForeignKey(
        Zone,
        on_delete=models.CASCADE,
        related_name='performance_records',
        to_field='firebase_id',
        db_column='zone_firebase_id',
        help_text="Reference to zone by Firebase ID"
    )
    performance_date = models.DateField(help_text="Date for this performance record")
    total_rentals = models.IntegerField(default=0, help_text="Number of rentals started in this zone")
    total_violations = models.IntegerField(default=0, help_text="Number of violations in this zone")
    revenue_generated = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Total revenue from rentals in this zone"
    )
    unique_bikes = models.IntegerField(default=0, help_text="Number of unique bikes used")
    unique_customers = models.IntegerField(default=0, help_text="Number of unique customers")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'zone_performance'
        verbose_name = 'Zone Performance'
        verbose_name_plural = 'Zone Performance'
        unique_together = ['zone', 'performance_date']
        indexes = [
            models.Index(fields=['zone', 'performance_date']),
            models.Index(fields=['performance_date']),
        ]
        ordering = ['-performance_date']
    
    def __str__(self):
        return f"{self.zone.name} - {self.performance_date} ({self.total_rentals} rentals)"