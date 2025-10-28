"""
Dashboard Views
"""

import json
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
from django.db.models.functions import TruncDay # Add this

from apps.bikes.models import Bike
from apps.geofencing.models import Zone
from apps.rides.models import Ride # Add Ride model import

@login_required
def dashboard(request):
    """Main dashboard view"""

    # --- Existing Bike/Zone Stats ---
    total_bikes = Bike.objects.count()
    available_bikes = Bike.objects.filter(status='AVAILABLE').count()
    in_use_bikes = Bike.objects.filter(status='IN_USE').count()
    offline_bikes = Bike.objects.filter(status='OFFLINE').count()

    if total_bikes > 0:
        available_percentage = round((available_bikes / total_bikes) * 100, 1)
        in_use_percentage = round((in_use_bikes / total_bikes) * 100, 1)
        offline_percentage = round((offline_bikes / total_bikes) * 100, 1)
    else:
        available_percentage = 0
        in_use_percentage = 0
        offline_percentage = 0

    total_zones = Zone.objects.count()
    active_zones = Zone.objects.filter(is_active=True)[:5]
    recent_bikes = Bike.objects.all().order_by('-created_at')[:5]
    last_bike = Bike.objects.order_by('-synced_at').first()
    last_sync = last_bike.synced_at if last_bike else timezone.now()
    active_rentals = in_use_bikes # Placeholder

    # --- NEW: Usage Statistics ---
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # Correctly get the start of the week (assuming Monday is the first day)
    week_start = today_start - timedelta(days=today_start.weekday())
    # Correctly get the start of the month
    month_start = today_start.replace(day=1)
    # For daily trend (last 7 days)
    seven_days_ago = today_start - timedelta(days=6)

    rides_today = Ride.objects.filter(start_time__gte=today_start).count()
    rides_this_week = Ride.objects.filter(start_time__gte=week_start).count()
    rides_this_month = Ride.objects.filter(start_time__gte=month_start).count()

    # Data for daily trend chart (last 7 days)
    daily_rides_trend = Ride.objects.filter(
        start_time__gte=seven_days_ago
    ).annotate(
        day=TruncDay('start_time')
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')

    # Prepare data for Chart.js
    daily_trend_data = []
    # Create a dictionary of counts for quick lookup
    counts_by_day = {item['day'].strftime('%Y-%m-%d'): item['count'] for item in daily_rides_trend}
    # Iterate through the last 7 days to ensure all days are present
    for i in range(7):
        day = (seven_days_ago + timedelta(days=i)).date()
        day_str = day.strftime('%Y-%m-%d')
        daily_trend_data.append({
            'day': day.strftime('%a, %b %d'), # Format for label
            'count': counts_by_day.get(day_str, 0) # Get count or 0 if no rides
        })

    # --- Context Dictionary ---
    context = {
        # Existing context
        'total_bikes': total_bikes,
        'available_bikes': available_bikes,
        'in_use_bikes': in_use_bikes,
        'offline_bikes': offline_bikes,
        'available_percentage': available_percentage,
        'in_use_percentage': in_use_percentage,
        'offline_percentage': offline_percentage,
        'total_zones': total_zones,
        'active_zones': active_zones,
        'recent_bikes': recent_bikes,
        'active_rentals': active_rentals,
        'last_sync': last_sync,

        # New Usage Stats context
        'rides_today': rides_today,
        'rides_this_week': rides_this_week,
        'rides_this_month': rides_this_month,
        'daily_trend_data_json': json.dumps(daily_trend_data), # Pass as JSON
    }

    return render(request, 'dashboard/dashboard.html', context)