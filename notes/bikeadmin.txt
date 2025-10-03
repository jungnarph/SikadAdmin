"""
Django Admin for Bikes
"""

from django.contrib import admin
from .models import Bike, BikeLocationHistory, BikePerformance


@admin.register(Bike)
class BikeAdmin(admin.ModelAdmin):
    list_display = [
        'firebase_id', 
        'bike_model', 
        'bike_type', 
        'status', 
        'current_zone_id',
        'synced_at'
    ]
    list_filter = ['status', 'bike_type', 'synced_at']
    search_fields = ['firebase_id', 'bike_model', 'current_zone_id']
    readonly_fields = ['firebase_id', 'synced_at', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Firebase Information', {
            'fields': ('firebase_id',)
        }),
        ('Bike Details', {
            'fields': ('bike_model', 'bike_type', 'status')
        }),
        ('Location', {
            'fields': ('current_latitude', 'current_longitude', 'current_zone_id')
        }),
        ('Metadata', {
            'fields': ('synced_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(BikeLocationHistory)
class BikeLocationHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'bike',
        'latitude',
        'longitude',
        'speed',
        'recorded_at',
        'synced_at'
    ]
    list_filter = ['recorded_at', 'synced_at']
    search_fields = ['bike__firebase_id']
    readonly_fields = ['bike', 'latitude', 'longitude', 'speed', 'recorded_at', 'synced_at']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(BikePerformance)
class BikePerformanceAdmin(admin.ModelAdmin):
    list_display = [
        'bike',
        'performance_date',
        'ride_count',
        'total_distance',
        'revenue_generated',
        'utilization_rate'
    ]
    list_filter = ['performance_date']
    search_fields = ['bike__firebase_id']
    readonly_fields = ['bike', 'performance_date', 'created_at']
    
    fieldsets = (
        ('Performance Summary', {
            'fields': (
                'bike',
                'performance_date',
                'ride_count',
                'total_distance',
                'total_duration',
                'revenue_generated',
                'utilization_rate'
            )
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )