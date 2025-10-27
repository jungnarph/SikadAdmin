"""
Geofencing URL Configuration - Complete CRUD
"""

from django.urls import path
from . import views

app_name = 'geofencing'

urlpatterns = [
    # List views
    path('', views.zone_list, name='zone_list'),
    path('violations/', views.violation_list, name='violation_list'),

    # CRUD operations
    path('create/', views.zone_create, name='zone_create'),
    path('<str:zone_id>/', views.zone_detail, name='zone_detail'),
    path('<str:zone_id>/edit/', views.zone_update, name='zone_update'),
    path('<str:zone_id>/delete/', views.zone_delete, name='zone_delete'),

    # Sync operations
    path('<str:zone_id>/sync/', views.sync_zone, name='sync_zone'),
    path('sync/all/', views.sync_all_zones, name='sync_all_zones'),

    # Violation operations
    path('violations/process/', views.process_violations, name='process_violations'),
    path('violations/<uuid:violation_id>/resolve/', views.resolve_violation, name='resolve_violation'),

    # API endpoints
    path('api/zone/<str:zone_firebase_id>/data/', views.get_zone_data, name='get_zone_data'),
]