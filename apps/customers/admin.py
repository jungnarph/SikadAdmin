"""
Django Admin for Customers
"""

from django.contrib import admin
from .models import (
    Customer, CustomerPaymentMethod, CustomerRideHistory, 
    CustomerActivityLog, CustomerStatistics
)

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = [
        'firebase_id',
        'name',
        'email',
        'phone_number',
        'status',
        'verification_status',
        'total_rides',
        'total_spent',
        'registration_date'
    ]
    list_filter = ['status', 'verification_status', 'phone_verified', 'registration_date']
    search_fields = ['firebase_id', 'email', 'phone_number', 'name']
    readonly_fields = [
        'firebase_id', 'registration_date', 'last_login', 
        'synced_at', 'created_at', 'updated_at',
        'total_rides', 'total_spent'
    ]
    
    fieldsets = (
        ('Firebase Information', {
            'fields': ('firebase_id',)
        }),
        ('Personal Information', {
            'fields': ('name', 'email', 'phone_number', 'profile_image_url')
        }),
        ('Account Status', {
            'fields': ('status', 'verification_status', 'phone_verified')
        }),
        ('Statistics', {
            'fields': ('total_rides', 'total_spent', 'account_balance'),
            'classes': ('collapse',)
        }),
        ('Suspension Info', {
            'fields': ('suspension_reason', 'suspended_at', 'suspended_by'),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': ('registration_date', 'last_login', 'synced_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CustomerPaymentMethod)
class CustomerPaymentMethodAdmin(admin.ModelAdmin):
    list_display = [
        'customer',
        'payment_type',
        'masked_number',
        'is_default',
        'is_verified',
        'created_at'
    ]
    list_filter = ['payment_type', 'is_default', 'is_verified']
    search_fields = ['customer__name', 'customer__email', 'masked_number']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(CustomerRideHistory)
class CustomerRideHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'firebase_id',
        'customer',
        'bike_id',
        'start_time',
        'duration_minutes',
        'distance_km',
        'amount_charged',
        'rental_status'
    ]
    list_filter = ['rental_status', 'payment_status', 'start_time']
    search_fields = ['firebase_id', 'customer__name', 'bike_id']
    readonly_fields = ['firebase_id', 'synced_at', 'created_at']
    
    fieldsets = (
        ('Rental Information', {
            'fields': ('firebase_id', 'customer', 'bike_id', 'rental_status')
        }),
        ('Time & Location', {
            'fields': (
                'start_time', 'end_time', 'duration_minutes',
                'start_latitude', 'start_longitude',
                'end_latitude', 'end_longitude',
                'start_zone_id', 'end_zone_id'
            )
        }),
        ('Metrics', {
            'fields': ('distance_km',)
        }),
        ('Payment', {
            'fields': ('amount_charged', 'payment_status')
        }),
        ('Notes', {
            'fields': ('cancellation_reason',),
            'classes': ('collapse',)
        }),
        ('Sync', {
            'fields': ('synced_at', 'created_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CustomerActivityLog)
class CustomerActivityLogAdmin(admin.ModelAdmin):
    list_display = [
        'customer',
        'activity_type',
        'description',
        'ip_address',
        'timestamp'
    ]
    list_filter = ['activity_type', 'timestamp']
    search_fields = ['customer__name', 'customer__email', 'description']
    readonly_fields = ['customer', 'activity_type', 'description', 'ip_address', 'device_info', 'related_id', 'timestamp']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(CustomerStatistics)
class CustomerStatisticsAdmin(admin.ModelAdmin):
    list_display = [
        'customer',
        'stats_date',
        'rides_count',
        'total_distance',
        'total_duration',
        'total_spent'
    ]
    list_filter = ['stats_date']
    search_fields = ['customer__name', 'customer__email']
    readonly_fields = ['customer', 'stats_date', 'created_at']
    
    fieldsets = (
        ('Statistics Summary', {
            'fields': (
                'customer',
                'stats_date',
                'rides_count',
                'total_distance',
                'total_duration',
                'total_spent'
            )
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )