"""
Django Admin configuration for the Payments app
"""

import logging
from django.contrib import admin
from .models import Payment
from django.urls import reverse
from django.utils.html import format_html

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'firebase_id',
        'customer_link', # Use custom method to make it clickable
        'ride_link',     # Use custom method to make it clickable
        'amount',
        'payment_type',
        'payment_status',
        'payment_date',
        'synced_at'
    ]
    list_filter = ['payment_status', 'payment_type', 'payment_date', 'synced_at']
    search_fields = [
        'firebase_id',
        'customer__firebase_id', # Search by customer's Firebase ID
        'customer__name',        # Search by customer's name
        'customer__email',       # Search by customer's email
        'ride__firebase_id',     # Search by ride's Firebase ID
        'payment_account_info'
    ]
    readonly_fields = [
        'id',
        'firebase_id',
        'customer',
        'ride',
        'amount',
        'payment_type',
        'payment_status',
        'payment_account_info',
        'payment_date',
        'synced_at',
        'created_at',
        'updated_at',
    ]
    list_select_related = ('customer', 'ride', 'ride__bike') # Optimize queries

    fieldsets = (
        ('Identifiers', {
            'fields': ('firebase_id', 'id')
        }),
        ('Association', {
            'fields': ('customer', 'ride')
        }),
        ('Payment Details', {
            'fields': ('amount', 'payment_type', 'payment_status', 'payment_account_info', 'payment_date')
        }),
        ('Metadata', {
            'fields': ('synced_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    # Make customer and ride links clickable in the list display
    def customer_link(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        if obj.customer:
            # Assuming you have a customer detail view named 'customer_detail' in 'customers' app
            url = reverse('customers:customer_detail', args=[obj.customer.firebase_id])
            return format_html('<a href="{}">{}</a>', url, obj.customer)
        return "N/A"
    customer_link.short_description = 'Customer'
    customer_link.admin_order_field = 'customer' # Allows sorting by customer

    def ride_link(self, obj):
        if obj.ride:
            # Assuming you have a ride detail view named 'ride_detail' in the 'rides' app
            try:
                # Use the correct app name 'rides' and view name
                url = reverse('rides:ride_detail', args=[obj.ride.firebase_id]) 
                return format_html('<a href="{}">{}</a>', url, obj.ride.firebase_id[:8] + '...')
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(f"Error generating ride link in PaymentAdmin: {e}")
                # Fallback if URL reversing fails
                return obj.ride.firebase_id[:8] + '... (link error)'
        return "N/A"
    ride_link.short_description = 'Ride'
    ride_link.admin_order_field = 'ride'

    # Disable adding payments directly through admin (they should sync from Firebase)
    def has_add_permission(self, request):
        return False

    # Optional: Disable changing payments directly through admin
    # def has_change_permission(self, request, obj=None):
    #     return False

    # Optional: Disable deleting payments directly through admin
    # def has_delete_permission(self, request, obj=None):
    #     return False
