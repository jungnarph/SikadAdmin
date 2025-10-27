"""
Support URL Configuration
"""

from django.urls import path
from . import views

app_name = 'support'

urlpatterns = [
    # List view for all support requests
    path('', views.support_request_list, name='support_request_list'),

    # Detail view
    path('<str:request_firebase_id>/', views.support_request_detail, name='support_request_detail'),

    # Sync support requests from Firebase
    path('sync/all/', views.sync_support_requests, name='sync_support_requests'),
]