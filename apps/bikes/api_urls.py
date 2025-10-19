"""
Bikes API URL Configuration
"""

from django.urls import path
from . import api_views

app_name = 'bikes_api'

urlpatterns = [
    # List endpoints
    path('bikes/', api_views.api_bikes_list, name='bikes_list'),
    path('bikes/stats/', api_views.api_bikes_by_status, name='bikes_stats'),
    
    # Single bike endpoints
    path('bikes/<str:bike_id>/', api_views.api_bike_detail, name='bike_detail'),
    path('bikes/<str:bike_id>/location/', api_views.api_bike_update_location, name='bike_update_location'),
    path('bikes/<str:bike_id>/history/', api_views.api_bike_location_history, name='bike_location_history'),
]