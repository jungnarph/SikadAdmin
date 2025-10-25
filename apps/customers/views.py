"""
Customers Views - Complete Customer Management
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count, Avg
from django.db.models.functions import TruncMonth
from datetime import datetime, timedelta
from .models import Customer, CustomerRideHistory, CustomerActivityLog, CustomerPaymentMethod
from .firebase_service import CustomerFirebaseService
from .sync_service import CustomerSyncService
from .forms import CustomerEditForm, CustomerSuspendForm, CustomerNoteForm
import json
import csv


@login_required
def customer_list(request):
    """List all customers from PostgreSQL"""
    customers = Customer.objects.all().order_by('-registration_date')
    
    # Apply filters
    status = request.GET.get('status')
    verification = request.GET.get('verification')
    search = request.GET.get('search')
    
    if status:
        customers = customers.filter(status=status)
    if verification:
        customers = customers.filter(verification_status=verification)
    if search:
        customers = customers.filter(
            Q(email__icontains=search) |
            Q(phone_number__icontains=search) |
            Q(name__icontains=search) |
            Q(firebase_id__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(customers, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    context = {
        'customers': page_obj,
        'total_count': Customer.objects.count(),
        'active_count': Customer.objects.filter(status='ACTIVE').count(),
        'suspended_count': Customer.objects.filter(status='SUSPENDED').count(),
        'pending_verification': Customer.objects.filter(verification_status='PENDING').count(),
    }
    
    return render(request, 'customers/customer_list.html', context)


@login_required
def customer_detail(request, customer_id):
    """View customer details from Firebase and PostgreSQL"""
    firebase_service = CustomerFirebaseService()
    customer_data = firebase_service.get_customer(customer_id)
    
    if not customer_data:
        messages.error(request, f'Customer {customer_id} not found in Firebase')
        return redirect('customers:customer_list')
    
    # Get PostgreSQL data if exists
    try:
        pg_customer = Customer.objects.get(firebase_id=customer_id)
    except Customer.DoesNotExist:
        pg_customer = None
    
    # Get ride history
    ride_history = CustomerRideHistory.objects.filter(
        customer__firebase_id=customer_id
    ).order_by('-start_time')[:10]
    
    # Get activity logs
    activity_logs = CustomerActivityLog.objects.filter(
        customer__firebase_id=customer_id
    ).order_by('-timestamp')[:20]
    
    # Get payment methods
    payment_methods = CustomerPaymentMethod.objects.filter(
        customer__firebase_id=customer_id
    ).order_by('-is_default', '-created_at')
    
    # Get statistics from Firebase
    statistics = firebase_service.get_customer_statistics(customer_id)
    
    context = {
        'customer': customer_data,
        'pg_customer': pg_customer,
        'ride_history': ride_history,
        'activity_logs': activity_logs,
        'payment_methods': payment_methods,
        'statistics': statistics,
    }
    
    return render(request, 'customers/customer_detail.html', context)


@login_required
def customer_edit(request, customer_id):
    """Edit customer information"""
    firebase_service = CustomerFirebaseService()
    customer_data = firebase_service.get_customer(customer_id)
    
    if not customer_data:
        messages.error(request, f'Customer {customer_id} not found')
        return redirect('customers:customer_list')
    
    if request.method == 'POST':
        form = CustomerEditForm(request.POST)
        if form.is_valid():
            # Prepare update data
            updates = {
                'name': form.cleaned_data['name'],
                'email': form.cleaned_data['email'],
                'phone_number': form.cleaned_data['phone_number'],
            }
            
            # Update in Firebase
            success = firebase_service.update_customer(customer_id, updates)
            
            if success:
                # Sync to PostgreSQL
                sync_service = CustomerSyncService()
                sync_service.sync_single_customer(customer_id)
                
                messages.success(request, f'Customer {customer_id} updated successfully!')
                return redirect('customers:customer_detail', customer_id=customer_id)
            else:
                messages.error(request, 'Failed to update customer')
        else:
            messages.error(request, 'Please correct the errors below')
    else:
        # Pre-fill form with existing data
        initial_data = {
            'name': customer_data.get('name', ''),
            'email': customer_data.get('email', ''),
            'phone_number': customer_data.get('phone_number', ''),
        }
        form = CustomerEditForm(initial=initial_data)
    
    return render(request, 'customers/customer_edit.html', {
        'form': form,
        'customer_id': customer_id,
        'customer': customer_data,
    })


@login_required
def customer_suspend(request, customer_id):
    """Suspend a customer account"""
    if request.method == 'POST':
        form = CustomerSuspendForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data['reason']
            
            firebase_service = CustomerFirebaseService()
            success = firebase_service.suspend_customer(
                customer_id, 
                reason, 
                str(request.user.id)
            )
            
            if success:
                # Sync to PostgreSQL
                sync_service = CustomerSyncService()
                sync_service.sync_single_customer(customer_id)
                
                # Log the activity
                try:
                    customer = Customer.objects.get(firebase_id=customer_id)
                    CustomerActivityLog.objects.create(
                        customer=customer,
                        activity_type='SUSPENSION',
                        description=f'Account suspended by {request.user.username}. Reason: {reason}'
                    )
                except Customer.DoesNotExist:
                    pass
                
                messages.success(request, f'Customer {customer_id} has been suspended')
                return redirect('customers:customer_detail', customer_id=customer_id)
            else:
                messages.error(request, 'Failed to suspend customer')
        else:
            messages.error(request, 'Please correct the errors below')
    else:
        form = CustomerSuspendForm()
    
    # Get customer data
    firebase_service = CustomerFirebaseService()
    customer_data = firebase_service.get_customer(customer_id)
    
    if not customer_data:
        messages.error(request, f'Customer {customer_id} not found')
        return redirect('customers:customer_list')
    
    return render(request, 'customers/customer_suspend.html', {
        'form': form,
        'customer_id': customer_id,
        'customer': customer_data,
    })


@login_required
def customer_reactivate(request, customer_id):
    """Reactivate a suspended customer account"""
    if request.method == 'POST':
        firebase_service = CustomerFirebaseService()
        success = firebase_service.reactivate_customer(customer_id)
        
        if success:
            # Sync to PostgreSQL
            sync_service = CustomerSyncService()
            sync_service.sync_single_customer(customer_id)
            
            # Log the activity
            try:
                customer = Customer.objects.get(firebase_id=customer_id)
                CustomerActivityLog.objects.create(
                    customer=customer,
                    activity_type='REACTIVATION',
                    description=f'Account reactivated by {request.user.username}'
                )
            except Customer.DoesNotExist:
                pass
            
            messages.success(request, f'Customer {customer_id} has been reactivated')
        else:
            messages.error(request, 'Failed to reactivate customer')
        
        return redirect('customers:customer_detail', customer_id=customer_id)
    
    # GET request - show confirmation page
    firebase_service = CustomerFirebaseService()
    customer_data = firebase_service.get_customer(customer_id)
    
    if not customer_data:
        messages.error(request, f'Customer {customer_id} not found')
        return redirect('customers:customer_list')
    
    return render(request, 'customers/customer_reactivate.html', {
        'customer_id': customer_id,
        'customer': customer_data,
    })


@login_required
def customer_rides(request, customer_id):
    """View all rides for a customer"""
    try:
        customer = Customer.objects.get(firebase_id=customer_id)
    except Customer.DoesNotExist:
        messages.error(request, f'Customer {customer_id} not found')
        return redirect('customers:customer_list')
    
    # Get ride history with filters
    rides = CustomerRideHistory.objects.filter(customer=customer).order_by('-start_time')
    
    # Apply filters
    status = request.GET.get('status')
    if status:
        rides = rides.filter(rental_status=status)
    
    # Pagination
    paginator = Paginator(rides, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    total_rides = rides.count()
    completed_rides = rides.filter(rental_status='COMPLETED').count()
    total_distance = rides.aggregate(Sum('distance_km'))['distance_km__sum'] or 0
    total_spent = rides.aggregate(Sum('amount_charged'))['amount_charged__sum'] or 0
    avg_duration = rides.aggregate(Avg('duration_minutes'))['duration_minutes__avg'] or 0
    
    context = {
        'customer': customer,
        'rides': page_obj,
        'total_rides': total_rides,
        'completed_rides': completed_rides,
        'total_distance': total_distance,
        'total_spent': total_spent,
        'avg_duration': avg_duration,
    }
    
    return render(request, 'customers/customer_rides.html', context)


@login_required
def customer_verify(request, customer_id):
    """Mark customer as verified"""
    if request.method == 'POST':
        firebase_service = CustomerFirebaseService()
        success = firebase_service.verify_customer(customer_id)
        
        if success:
            # Sync to PostgreSQL
            sync_service = CustomerSyncService()
            sync_service.sync_single_customer(customer_id)
            
            messages.success(request, f'Customer {customer_id} has been verified')
        else:
            messages.error(request, 'Failed to verify customer')
        
        return redirect('customers:customer_detail', customer_id=customer_id)
    
    return redirect('customers:customer_detail', customer_id=customer_id)


@login_required
def sync_customer(request, customer_id):
    """Sync a single customer from Firebase to PostgreSQL"""
    sync_service = CustomerSyncService()
    success = sync_service.sync_single_customer(customer_id)
    
    if success:
        messages.success(request, f'Customer {customer_id} synced successfully')
    else:
        messages.error(request, f'Failed to sync customer {customer_id}')
    
    return redirect('customers:customer_detail', customer_id=customer_id)


@login_required
def sync_all_customers(request):
    """Sync all customers from Firebase to PostgreSQL"""
    sync_service = CustomerSyncService()
    stats = sync_service.sync_all_customers()
    
    messages.success(
        request,
        f'Synced {stats["total"]} customers: {stats["created"]} created, {stats["updated"]} updated'
    )
    
    return redirect('customers:customer_list')


@login_required
def customer_statistics(request):
    """View overall customer statistics and analytics"""
    # Overall stats
    total_customers = Customer.objects.count()
    active_customers = Customer.objects.filter(status='ACTIVE').count()
    suspended_customers = Customer.objects.filter(status='SUSPENDED').count()
    verified_customers = Customer.objects.filter(verification_status='VERIFIED').count()
    
    # Recent registrations
    recent_customers = Customer.objects.order_by('-registration_date')[:10]
    
    # Top customers by rides
    top_by_rides = Customer.objects.filter(total_rides__gt=0).order_by('-total_rides')[:10]
    
    # Top customers by spending
    top_by_spending = Customer.objects.filter(total_spent__gt=0).order_by('-total_spent')[:10]
    
    # Monthly registration trend (last 6 months)
    six_months_ago = datetime.now() - timedelta(days=180)
    monthly_registrations = Customer.objects.filter(
        registration_date__gte=six_months_ago
    ).annotate(
        month=TruncMonth('registration_date')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')
    
    context = {
        'total_customers': total_customers,
        'active_customers': active_customers,
        'suspended_customers': suspended_customers,
        'verified_customers': verified_customers,
        'recent_customers': recent_customers,
        'top_by_rides': top_by_rides,
        'top_by_spending': top_by_spending,
        'monthly_registrations': monthly_registrations,
    }
    
    return render(request, 'customers/customer_statistics.html', context)


@login_required
def customer_export(request):
    """Export customer data to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="customers_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Customer ID', 'Name', 'Email', 'Phone', 'Status', 
        'Verification', 'Total Rides', 'Total Spent', 'Registration Date'
    ])
    
    customers = Customer.objects.all()
    for customer in customers:
        writer.writerow([
            customer.firebase_id,
            customer.name,
            customer.email,
            customer.phone_number,
            customer.status,
            customer.verification_status,
            customer.total_rides,
            customer.total_spent,
            customer.registration_date.strftime('%Y-%m-%d') if customer.registration_date else ''
        ])
    
    return response