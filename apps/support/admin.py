"""
Django Admin for Support app
"""

from django.contrib import admin
from .models import SupportRequest
from django.utils.html import format_html


@admin.register(SupportRequest)
class SupportRequestAdmin(admin.ModelAdmin):
    list_display = [
        'firebase_id_short',
        'customer_name',
        'issue_preview',
        'status',
        'priority',
        'assigned_to',
        'submission_datetime',
        'app_version',
    ]
    list_filter = ['status', 'priority', 'app_version', 'submission_datetime']
    search_fields = [
        'firebase_id',
        'test_id',
        'customer__name',
        'customer__email',
        'customer__firebase_id',
        'issue',
        'response',
        'assigned_to',
    ]
    readonly_fields = [
        'id',
        'firebase_id',
        'customer',
        'submission_time',
        'timestamp',
        'submission_datetime',
        'synced_at',
        'created_at',
        'updated_at',
    ]
    list_select_related = ('customer',)

    fieldsets = (
        ('Identifiers', {
            'fields': ('firebase_id', 'id', 'test_id')
        }),
        ('Customer', {
            'fields': ('customer',)
        }),
        ('Request Details', {
            'fields': ('issue', 'response', 'app_version')
        }),
        ('Status & Priority', {
            'fields': ('status', 'priority', 'assigned_to')
        }),
        ('Timeline', {
            'fields': ('submission_time', 'timestamp', 'submission_datetime')
        }),
        ('Metadata', {
            'fields': ('synced_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def firebase_id_short(self, obj):
        """Display shortened firebase_id for better readability"""
        return obj.firebase_id[:12] + '...' if len(obj.firebase_id) > 12 else obj.firebase_id
    firebase_id_short.short_description = 'Firebase ID'
    firebase_id_short.admin_order_field = 'firebase_id'

    def customer_name(self, obj):
        """Display customer name or 'Unknown'"""
        if obj.customer:
            return obj.customer.name
        return "Unknown"
    customer_name.short_description = 'Customer'
    customer_name.admin_order_field = 'customer'

    def issue_preview(self, obj):
        """Display first 50 characters of the issue"""
        if len(obj.issue) > 50:
            return obj.issue[:50] + '...'
        return obj.issue
    issue_preview.short_description = 'Issue'

    # Status badges with colors
    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',      # Yellow
            'in_progress': '#17a2b8',  # Blue
            'resolved': '#28a745',     # Green
            'closed': '#6c757d',       # Gray
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    # Priority badges with colors
    def priority_badge(self, obj):
        colors = {
            'low': '#28a745',       # Green
            'medium': '#ffc107',    # Yellow
            'high': '#fd7e14',      # Orange
            'critical': '#dc3545',  # Red
        }
        color = colors.get(obj.priority, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_priority_display()
        )
    priority_badge.short_description = 'Priority'

    # Allow editing support requests (unlike rides which are read-only)
    def has_add_permission(self, request):
        # Support requests should come from Firebase, but allow manual creation if needed
        return True

    def has_change_permission(self, request, obj=None):
        # Allow admins to update status, priority, response, and assignment
        return True