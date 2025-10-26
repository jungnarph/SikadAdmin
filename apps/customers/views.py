"""
Customers Views - Complete Customer Management
Refactored to use apps.rides.models.Ride instead of CustomerRideHistory
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count, Avg
from django.db.models.functions import TruncMonth
from datetime import datetime, timedelta
# Import the main Customer model from the current app
from .models import Customer 
# Import the Ride model from the rides app
from apps.rides.models import Ride # CHANGED: Import Ride model
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
        # Assuming 'PENDING' is still a valid verification status
        'pending_verification': Customer.objects.filter(verification_status='PENDING').count(), 
    }

    return render(request, 'customers/customer_list.html', context)


@login_required
def customer_detail(request, customer_id):
    """View customer details from PostgreSQL"""
    # Get customer from PostgreSQL
    try:
        customer = Customer.objects.get(firebase_id=customer_id)
    except Customer.DoesNotExist:
        messages.error(request, f'Customer {customer_id} not found')
        return redirect('customers:customer_list')

    # Get ride history using the Ride model
    ride_history = Ride.objects.filter(
        customer=customer
    ).select_related('bike').order_by('-start_time')[:10]

    # Calculate statistics from PostgreSQL
    rides_queryset = Ride.objects.filter(customer=customer)

    total_rides = rides_queryset.count()
    total_spent = rides_queryset.aggregate(Sum('amount_charged'))['amount_charged__sum'] or 0
    total_distance = rides_queryset.aggregate(Sum('distance_km'))['distance_km__sum'] or 0
    total_duration = rides_queryset.aggregate(Sum('duration_minutes'))['duration_minutes__sum'] or 0

    completed_rides = rides_queryset.filter(rental_status='COMPLETED').count()
    active_rides = rides_queryset.filter(rental_status='ACTIVE').count()

    statistics = {
        'total_rides': total_rides,
        'total_spent': float(total_spent),
        'total_distance': float(total_distance),
        'total_duration': total_duration,
        'completed_rides': completed_rides,
        'active_rides': active_rides,
        'average_ride_duration': total_duration / total_rides if total_rides > 0 else 0,
        'average_distance': float(total_distance) / total_rides if total_rides > 0 else 0,
    }

    context = {
        'customer': customer,
        'ride_history': ride_history,
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
                # Ensure keys match Firebase expectations if different from form
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
                messages.error(request, 'Failed to update customer in Firebase')
        else:
            messages.error(request, 'Please correct the errors below')
    else:
        # Pre-fill form with existing data
        initial_data = {
            'name': customer_data.get('name', ''), # Use 'name' from model
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
            # Consider adding reason_category to the suspend call if needed by Firebase service
            # reason_category = form.cleaned_data['reason_category'] 

            firebase_service = CustomerFirebaseService()
            success = firebase_service.suspend_customer(
                customer_id,
                reason,
                str(request.user.id) # Assuming admin_id is the Django user ID
            )

            if success:
                # Sync to PostgreSQL
                sync_service = CustomerSyncService()
                sync_service.sync_single_customer(customer_id)

                messages.success(request, f'Customer {customer_id} has been suspended')
                return redirect('customers:customer_detail', customer_id=customer_id)
            else:
                messages.error(request, 'Failed to suspend customer in Firebase')
        else:
            messages.error(request, 'Please correct the errors below')
    else:
        form = CustomerSuspendForm()

    # Get customer data for context
    firebase_service = CustomerFirebaseService()
    customer_data = firebase_service.get_customer(customer_id)

    if not customer_data:
        messages.error(request, f'Customer {customer_id} not found')
        return redirect('customers:customer_list')
        
    # Pass customer name for display
    customer_name = customer_data.get('name', customer_id) 

    return render(request, 'customers/customer_suspend.html', {
        'form': form,
        'customer_id': customer_id,
        'customer_name': customer_name, # Pass name for template
        'customer': customer_data, # Keep full data if template uses more fields
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

            messages.success(request, f'Customer {customer_id} has been reactivated')
        else:
            messages.error(request, 'Failed to reactivate customer in Firebase')

        return redirect('customers:customer_detail', customer_id=customer_id)

    # GET request - show confirmation page
    firebase_service = CustomerFirebaseService()
    customer_data = firebase_service.get_customer(customer_id)

    if not customer_data:
        messages.error(request, f'Customer {customer_id} not found')
        return redirect('customers:customer_list')

    # Pass customer name for display
    customer_name = customer_data.get('name', customer_id)

    return render(request, 'customers/customer_reactivate.html', {
        'customer_id': customer_id,
        'customer_name': customer_name, # Pass name for template
        'customer': customer_data, # Keep full data if template uses more fields
    })


@login_required
def customer_rides(request, customer_id):
    """View all rides for a customer using the Ride model"""
    try:
        # Fetch customer from PostgreSQL using firebase_id
        customer = Customer.objects.get(firebase_id=customer_id)
    except Customer.DoesNotExist:
        messages.error(request, f'Customer {customer_id} not found in the local database.')
        # Optionally, try syncing the customer first before redirecting
        # sync_service = CustomerSyncService()
        # if sync_service.sync_single_customer(customer_id):
        #    customer = Customer.objects.get(firebase_id=customer_id)
        # else:
        #    return redirect('customers:customer_list')
        return redirect('customers:customer_list')

    # CHANGED: Get ride history using the Ride model and the customer instance
    rides_queryset = Ride.objects.filter(customer=customer).select_related('bike').order_by('-start_time')

    # Apply filters (adjust field names if needed based on Ride model)
    status = request.GET.get('status')
    if status:
        rides_queryset = rides_queryset.filter(rental_status=status) # Assuming field name is the same

    # Pagination
    paginator = Paginator(rides_queryset, 20) # Rides per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Statistics (Calculated from the Ride model queryset)
    total_rides = rides_queryset.count()
    completed_rides = rides_queryset.filter(rental_status='COMPLETED').count() # Assuming status value
    total_distance = rides_queryset.aggregate(Sum('distance_km'))['distance_km__sum'] or 0
    total_spent = rides_queryset.aggregate(Sum('amount_charged'))['amount_charged__sum'] or 0
    avg_duration = rides_queryset.aggregate(Avg('duration_minutes'))['duration_minutes__avg'] or 0

    context = {
        'customer': customer, # Use the PostgreSQL customer object
        'rides': page_obj,    # Pass the paginated rides
        'total_rides': total_rides,
        'completed_rides': completed_rides,
        'total_distance': total_distance,
        'total_spent': total_spent,
        'avg_duration': avg_duration,
    }

    return render(request, 'customers/customer_rides.html', context)


@login_required
def customer_verify(request, customer_id):
    """Mark customer as verified (updates Firebase and syncs)"""
    if request.method == 'POST':
        firebase_service = CustomerFirebaseService()
        # Assuming verify_customer updates 'verification_status' in Firebase
        success = firebase_service.verify_customer(customer_id) 

        if success:
            # Sync to PostgreSQL to update the local record
            sync_service = CustomerSyncService()
            sync_service.sync_single_customer(customer_id)

            messages.success(request, f'Customer {customer_id} has been marked as verified.')
        else:
            messages.error(request, 'Failed to verify customer in Firebase.')

        return redirect('customers:customer_detail', customer_id=customer_id)

    # Redirect if GET request
    return redirect('customers:customer_detail', customer_id=customer_id)


@login_required
def sync_customer(request, customer_id):
    """Sync a single customer from Firebase to PostgreSQL"""
    sync_service = CustomerSyncService()
    success = sync_service.sync_single_customer(customer_id)

    if success:
        messages.success(request, f'Customer {customer_id} synced successfully from Firebase.')
    else:
        messages.error(request, f'Failed to sync customer {customer_id}. Check logs for details.')

    # Redirect back to the detail page which will now show updated data (if sync worked)
    return redirect('customers:customer_detail', customer_id=customer_id)


@login_required
def sync_all_customers(request):
    """Sync all customers from Firebase to PostgreSQL"""
    sync_service = CustomerSyncService()
    # Assuming sync_all_customers handles fetching and syncing logic
    stats = sync_service.sync_all_customers() 

    messages.success(
        request,
        f'Sync initiated. Attempted sync for {stats.get("total", 0)} customers: '
        f'{stats.get("created", 0)} created, {stats.get("updated", 0)} updated, '
        f'{stats.get("failed", 0)} failed. Rides synced: {stats.get("rides_synced", 0)}. Check logs for details.'
    )

    return redirect('customers:customer_list')


@login_required
def customer_statistics(request):
    """View overall customer statistics and analytics"""
    # Overall stats from PostgreSQL
    total_customers = Customer.objects.count()
    active_customers = Customer.objects.filter(status='ACTIVE').count()
    suspended_customers = Customer.objects.filter(status='SUSPENDED').count()
    verified_customers = Customer.objects.filter(verification_status='VERIFIED').count()

    # Recent registrations from PostgreSQL
    recent_customers = Customer.objects.order_by('-registration_date')[:10]

    # Top customers by rides (using calculated field in Customer model)
    top_by_rides = Customer.objects.filter(total_rides__gt=0).order_by('-total_rides')[:10]

    # Top customers by spending (using calculated field in Customer model)
    top_by_spending = Customer.objects.filter(total_spent__gt=0).order_by('-total_spent')[:10]

    # Monthly registration trend (last 6 months) from PostgreSQL
    six_months_ago = datetime.now() - timedelta(days=180)
    monthly_registrations = Customer.objects.filter(
        registration_date__gte=six_months_ago
    ).annotate(
        month=TruncMonth('registration_date')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')

    # Convert month objects to strings for Chart.js labels
    monthly_data = [{'month': item['month'].strftime('%b %Y'), 'count': item['count']} for item in monthly_registrations]


    context = {
        'total_customers': total_customers,
        'active_customers': active_customers,
        'suspended_customers': suspended_customers,
        'verified_customers': verified_customers,
        'recent_customers': recent_customers,
        'top_by_rides': top_by_rides,
        'top_by_spending': top_by_spending,
        'monthly_registrations_json': json.dumps(monthly_data), # Pass as JSON for JS
    }

    return render(request, 'customers/customer_statistics.html', context)


@login_required
def customer_export(request):
    """Export customer data to CSV"""
    response = HttpResponse(content_type='text/csv')
    # Format filename with current date
    filename = f"customers_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    # Write header row
    writer.writerow([
        'Firebase ID', 'Name', 'Email', 'Phone Number', 'Status',
        'Verification Status', 'Phone Verified', 'Total Rides', 'Total Spent', 
        'Account Balance', 'Registration Date', 'Last Login', 
        'Suspended At', 'Suspension Reason' 
    ])

    # Fetch all customers (consider batching for very large datasets)
    customers = Customer.objects.all().order_by('registration_date') 
    for customer in customers:
        writer.writerow([
            customer.firebase_id,
            customer.name,
            customer.email,
            customer.phone_number,
            customer.status,
            customer.verification_status,
            customer.phone_verified,
            customer.total_rides,
            customer.total_spent,
            customer.account_balance, # Added balance
            customer.registration_date.strftime('%Y-%m-%d %H:%M:%S') if customer.registration_date else '',
            customer.last_login.strftime('%Y-%m-%d %H:%M:%S') if customer.last_login else '',
            customer.suspended_at.strftime('%Y-%m-%d %H:%M:%S') if customer.suspended_at else '', # Added suspension date
            customer.suspension_reason, # Added reason
        ])

    return response

# Note: The add_admin_note view was removed as CustomerActivityLog was removed. 
# If admin notes are needed, they should be stored elsewhere (e.g., directly in Firebase or a new simple model).