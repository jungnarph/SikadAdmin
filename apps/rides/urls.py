"""
Rides URL Configuration
"""

from django.urls import path
from . import views

app_name = 'rides'

urlpatterns = [
    # List view for all rides
    path('', views.ride_list, name='ride_list'),

    # Detail view
    path('<str:ride_firebase_id>/', views.ride_detail, name='ride_detail'),
]
