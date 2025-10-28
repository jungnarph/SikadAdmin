"""
Django Admin for Geofencing
"""

from django.contrib import admin
from .models import Zone, ZoneViolation


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = [
        'firebase_id',
        'name',
        'is_active',
        'point_count',
        'synced_at'
    ]
    list_filter = ['is_active', 'synced_at']
    search_fields = ['firebase_id', 'name']
    readonly_fields = ['firebase_id', 'point_count', 'synced_at', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Firebase Information', {
            'fields': ('firebase_id',)
        }),
        ('Zone Details', {
            'fields': ('name', 'color_code', 'is_active')
        }),
        ('Location', {
            'fields': ('center_latitude', 'center_longitude', 'polygon_points', 'point_count')
        }),
        ('Administration', {
            'fields': ('created_by',)
        }),
        ('Metadata', {
            'fields': ('synced_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ZoneViolation)
class ZoneViolationAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'zone',
        'bike_id',
        'customer_id',
        'violation_type',
        'violation_time',
        'resolved'
    ]
    list_filter = ['violation_type', 'resolved', 'violation_time']
    search_fields = ['bike_id', 'customer_id', 'zone__name']
    readonly_fields = ['zone', 'bike_id', 'customer_id', 'rental_id', 'violation_time', 'created_at']
    
    fieldsets = (
        ('Violation Details', {
            'fields': (
                'zone',
                'bike_id',
                'customer_id',
                'rental_id',
                'violation_type',
                'violation_time'
            )
        }),
        ('Location', {
            'fields': ('latitude', 'longitude')
        }),
        ('Resolution', {
            'fields': ('resolved', 'resolved_at', 'notes')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_resolved']
    
    def mark_resolved(self, request, queryset):
        from django.utils import timezone
        queryset.update(resolved=True, resolved_at=timezone.now())
        self.message_user(request, f"{queryset.count()} violations marked as resolved.")
    mark_resolved.short_description = "Mark selected violations as resolved"