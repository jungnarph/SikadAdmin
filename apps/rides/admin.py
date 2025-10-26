"""
Django Admin for Rides app
"""

from django.contrib import admin
from .models import Ride
from django.urls import reverse
from django.utils.html import format_html

@admin.register(Ride)
class RideAdmin(admin.ModelAdmin):
    list_display = [
        'firebase_id',
        'customer_link',
        'bike_link',
        'start_time',
        'duration_minutes',
        'distance_km',
        'amount_charged',
        'rental_status',
        'payment_status',
    ]
    list_filter = ['rental_status', 'payment_status', 'start_time', 'bike']
    search_fields = [
        'firebase_id',
        'customer__name',
        'customer__email',
        'customer__firebase_id',
        'bike__firebase_id',
    ]
    readonly_fields = [
        'id', 'firebase_id', 'customer', 'bike', 'start_time', 'end_time',
        'duration_minutes', 'distance_km', 'amount_charged',
        'start_latitude', 'start_longitude', 'end_latitude', 'end_longitude',
        'ride_path_points', # Display JSON nicely? Maybe custom widget later
        'start_zone_id', 'end_zone_id', 'cancellation_reason',
        'synced_at', 'created_at', 'updated_at',
    ]
    list_select_related = ('customer', 'bike') # Optimize queries

    fieldsets = (
        ('Identifiers', {
            'fields': ('firebase_id', 'id')
        }),
        ('Association', {
            'fields': ('customer', 'bike') # Removed payment link for now
        }),
        ('Timeline', {
            'fields': ('start_time', 'end_time', 'duration_minutes')
        }),
         ('Location', {
            'fields': ('start_latitude', 'start_longitude', 'end_latitude', 'end_longitude',
                       'start_zone_id', 'end_zone_id', 'ride_path_points'),
            'classes': ('collapse',) # Hide complex data initially
        }),
        ('Metrics & Payment', {
            'fields': ('distance_km', 'amount_charged', 'payment_status')
        }),
        ('Status & Notes', {
            'fields': ('rental_status', 'cancellation_reason')
        }),
        ('Metadata', {
            'fields': ('synced_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    # Make customer and bike links clickable
    def customer_link(self, obj):
        if obj.customer:
            url = reverse('customers:customer_detail', args=[obj.customer.firebase_id])
            return format_html('<a href="{}">{}</a>', url, obj.customer)
        return "N/A"
    customer_link.short_description = 'Customer'
    customer_link.admin_order_field = 'customer'

    def bike_link(self, obj):
        if obj.bike:
            url = reverse('bikes:bike_detail', args=[obj.bike.firebase_id])
            return format_html('<a href="{}">{}</a>', url, obj.bike.firebase_id)
        return "N/A"
    bike_link.short_description = 'Bike'
    bike_link.admin_order_field = 'bike'

    # Disable adding/changing rides directly through admin (they should sync)
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # Allow viewing but not changing? Or disable completely? For now, disable.
        return False