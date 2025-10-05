"""
Customers URL Configuration
"""

from django.urls import path
from . import views

app_name = 'customers'

urlpatterns = [
    # List and statistics
    path('', views.customer_list, name='customer_list'),
    path('statistics/', views.customer_statistics, name='customer_statistics'),
    path('export/', views.customer_export, name='customer_export'),
    
    # Customer detail and management
    path('<str:customer_id>/', views.customer_detail, name='customer_detail'),
    path('<str:customer_id>/edit/', views.customer_edit, name='customer_edit'),
    path('<str:customer_id>/rides/', views.customer_rides, name='customer_rides'),
    
    # Account actions
    path('<str:customer_id>/suspend/', views.customer_suspend, name='customer_suspend'),
    path('<str:customer_id>/reactivate/', views.customer_reactivate, name='customer_reactivate'),
    path('<str:customer_id>/verify/', views.customer_verify, name='customer_verify'),
    
    # Sync operations
    path('<str:customer_id>/sync/', views.sync_customer, name='sync_customer'),
    path('sync/all/', views.sync_all_customers, name='sync_all_customers'),
]