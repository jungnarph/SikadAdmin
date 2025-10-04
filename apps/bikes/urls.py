"""
Bikes URL Configuration
"""

from django.urls import path
from . import views

app_name = 'bikes'

urlpatterns = [
    path('', views.bike_list, name='bike_list'),
    path('map/', views.bike_map, name='bike_map'),
    path('sync/all/', views.sync_all_bikes, name='sync_all_bikes'),
    path('<str:bike_id>/', views.bike_detail, name='bike_detail'),
    path('<str:bike_id>/sync/', views.sync_bike, name='sync_bike'),
]