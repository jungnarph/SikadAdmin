"""
Bikes URL Configuration - Complete CRUD with Archive
"""

from django.urls import path
from . import views

app_name = 'bikes'

urlpatterns = [
    # List and Map views
    path('', views.bike_list, name='bike_list'),
    path('map/', views.bike_map, name='bike_map'),
    
    # CRUD operations
    path('create/', views.bike_create, name='bike_create'),
    path('<str:bike_id>/', views.bike_detail, name='bike_detail'),
    path('<str:bike_id>/edit/', views.bike_update, name='bike_update'),
    path('<str:bike_id>/delete/', views.bike_delete, name='bike_delete'),
    path('<str:bike_id>/restore/', views.bike_restore, name='bike_restore'),
    
    # Quick actions
    path('<str:bike_id>/update-status/', views.bike_update_status, name='bike_update_status'),
    path('<str:bike_id>/sync/', views.sync_bike, name='sync_bike'),
    
    # Bulk operations
    path('sync/all/', views.sync_all_bikes, name='sync_all_bikes'),
]