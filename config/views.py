"""
Dashboard Views
"""
import json # Make sure json is imported
from decimal import Decimal # Add Decimal import

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Sum # Add Sum import
from django.db.models.functions import TruncDay
from django.db.models import Q

from django.conf import settings

from apps.bikes.models import Bike
from apps.geofencing.models import Zone
from apps.rides.models import Ride

@login_required
def dashboard(request):
    """Main dashboard view"""

    # --- Timeframes ---
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    seven_days_ago = today_start - timedelta(days=6)
    thirty_days_ago = today_start - timedelta(days=30)

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
        available_percentage, in_use_percentage, offline_percentage = 0, 0, 0

    total_zones = Zone.objects.count()
    active_zones = Zone.objects.filter(is_active=True)[:5]
    recent_bikes = Bike.objects.all().order_by('-created_at')[:5]
    last_bike = Bike.objects.order_by('-synced_at').first()
    last_sync = last_bike.synced_at if last_bike else timezone.now()
    active_rentals = in_use_bikes

    # --- Usage Statistics ---
    rides_today = Ride.objects.filter(start_time__gte=today_start).count()
    rides_this_week = Ride.objects.filter(start_time__gte=week_start).count()
    rides_this_month = Ride.objects.filter(start_time__gte=month_start).count()

    daily_rides_trend = Ride.objects.filter(
        start_time__gte=seven_days_ago
    ).annotate(
        day=TruncDay('start_time')
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')

    daily_rides_trend_data = []
    counts_by_day_rides = {item['day'].strftime('%Y-%m-%d'): item['count'] for item in daily_rides_trend}
    for i in range(7):
        day = (seven_days_ago + timedelta(days=i)).date()
        day_str = day.strftime('%Y-%m-%d')
        daily_rides_trend_data.append({
            'day': day.strftime('%a, %b %d'),
            'count': counts_by_day_rides.get(day_str, 0)
        })

    # --- NEW: Revenue Statistics ---
    # We sum 'amount_charged' from the Ride model
    # Filter for completed or potentially active rides that might have charges
    revenue_rides_base_query = Ride.objects.filter(
        Q(rental_status='COMPLETED') | Q(rental_status='ACTIVE') # Consider charges on active rides too
    )

    revenue_today = revenue_rides_base_query.filter(
        start_time__gte=today_start
    ).aggregate(Sum('amount_charged'))['amount_charged__sum'] or Decimal(0)

    revenue_this_week = revenue_rides_base_query.filter(
        start_time__gte=week_start
    ).aggregate(Sum('amount_charged'))['amount_charged__sum'] or Decimal(0)

    revenue_this_month = revenue_rides_base_query.filter(
        start_time__gte=month_start
    ).aggregate(Sum('amount_charged'))['amount_charged__sum'] or Decimal(0)

    # Data for daily revenue trend chart (last 7 days)
    daily_revenue_trend = revenue_rides_base_query.filter(
        start_time__gte=seven_days_ago
    ).annotate(
        day=TruncDay('start_time')
    ).values('day').annotate(
        total_revenue=Sum('amount_charged')
    ).order_by('day')

    # Prepare data for Chart.js, ensuring Decimal is converted for JSON
    daily_revenue_trend_data = []
    revenue_by_day = {item['day'].strftime('%Y-%m-%d'): float(item['total_revenue'] or 0) for item in daily_revenue_trend}
    for i in range(7):
        day = (seven_days_ago + timedelta(days=i)).date()
        day_str = day.strftime('%Y-%m-%d')
        daily_revenue_trend_data.append({
            'day': day.strftime('%a, %b %d'), # Format for label
            'revenue': revenue_by_day.get(day_str, 0.0) # Get revenue or 0.0
        })

    # --- NEW: System Performance (Most/Least Used Bikes - Last 30 Days) ---
    # Annotate Bike objects with their ride count in the last 30 days
    # We filter rides first, then group by bike, count, and order.
    # Exclude archived bikes from consideration.
    bike_usage_stats = Ride.objects.filter(
        start_time__gte=thirty_days_ago,
        bike__isnull=False, # Ensure the ride is linked to a bike
        # bike__status__ne='ARCHIVED' # <--- This was the error
    ).exclude( # <--- Use exclude here
        bike__status='ARCHIVED' # Exclude rides from archived bikes
    ).values(
        'bike__firebase_id', 'bike__bike_model' # Group by bike ID and model
    ).annotate(
        ride_count=Count('id') # Count rides for each bike
    ).order_by('-ride_count') # Order by ride count descending

    most_used_bikes = list(bike_usage_stats[:5]) # Top 5
    least_used_bikes_queryset = bike_usage_stats.order_by('ride_count') # Order ascending for least used
    least_used_bikes = list(least_used_bikes_queryset[:5]) # Bottom 5

    firebase_config = {
        'databaseURL': getattr(settings, 'FIREBASE_DATABASE_URL', 'https://cit306-finalproject-default-rtdb.firebaseio.com/'),
        'apiKey': getattr(settings, 'FIREBASE_API_KEY', ''),
        'authDomain': getattr(settings, 'FIREBASE_AUTH_DOMAIN', ''),
        'projectId': getattr(settings, 'FIREBASE_PROJECT_ID', ''),
    }

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
        'rides_today': rides_today,
        'rides_this_week': rides_this_week,
        'rides_this_month': rides_this_month,
        'daily_rides_trend_data_json': json.dumps(daily_rides_trend_data),

        # New Revenue Stats context
        'revenue_today': revenue_today,
        'revenue_this_week': revenue_this_week,
        'revenue_this_month': revenue_this_month,
        'daily_revenue_trend_data_json': json.dumps(daily_revenue_trend_data),
        
        'most_used_bikes': most_used_bikes,
        'least_used_bikes': least_used_bikes,
        'bike_usage_period_days': 30,
        'firebase_config': json.dumps(firebase_config),
    }

    return render(request, 'dashboard/dashboard.html', context)