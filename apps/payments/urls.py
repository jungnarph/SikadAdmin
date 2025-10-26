"""
Payments URL Configuration
"""

from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # List view for all payments
    path('', views.payment_list, name='payment_list'),

    # Sync endpoint
    path('sync/all/', views.sync_all_payments, name='sync_all_payments'),

    # Optional: Detail view if needed later
    # path('<str:payment_firebase_id>/', views.payment_detail, name='payment_detail'),
]
