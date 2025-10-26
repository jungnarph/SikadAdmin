# Updated content for jungnarph/sikadadmin/SikadAdmin-536c6c488986007128f3aeddc27af5ff3c51f130/apps/customers/admin.py
"""
Django Admin for Customers
"""

from django.contrib import admin
from .models import (
    Customer,
    CustomerStatistics
)
# REMOVED: CustomerActivityLog import

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