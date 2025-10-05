"""
Customer Sync Service
Syncs customer data from Firebase to PostgreSQL
"""

from .firebase_service import CustomerFirebaseService
from .models import Customer, CustomerRideHistory
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class CustomerSyncService:
    """Service to sync customers from Firebase to PostgreSQL"""
    
    def __init__(self):
        self.firebase_service = CustomerFirebaseService()
    
    def sync_single_customer(self, customer_id: str) -> bool:
        """
        Sync a single customer from Firebase to PostgreSQL
        
        Args:
            customer_id: Firebase document ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get customer data from Firebase
            firebase_data = self.firebase_service.get_customer(customer_id)
            
            if not firebase_data:
                logger.warning(f"Customer {customer_id} not found in Firebase")
                return False
            
            # Update or create in PostgreSQL
            customer, created = Customer.objects.update_or_create(
                firebase_id=customer_id,
                defaults={
                    'email': firebase_data.get('email', ''),
                    'phone_number': firebase_data.get('phone_number', ''),
                    'full_name': firebase_data.get('full_name', ''),
                    'profile_image_url': firebase_data.get('profile_image_url'),
                    'status': firebase_data.get('status', 'ACTIVE'),
                    'verification_status': firebase_data.get('verification_status', 'UNVERIFIED'),
                    'id_document_url': firebase_data.get('id_document_url'),
                    'id_document_type': firebase_data.get('id_document_type', ''),
                    'email_verified': firebase_data.get('email_verified', False),
                    'phone_verified': firebase_data.get('phone_verified', False),
                    'registration_date': firebase_data.get('created_at'),
                    'last_login': firebase_data.get('last_login'),
                    'suspension_reason': firebase_data.get('suspension_reason', ''),
                    'admin_notes': firebase_data.get('admin_notes', ''),
                }
            )
            
            # Get and sync statistics
            stats = self.firebase_service.get_customer_statistics(customer_id)
            if stats:
                customer.total_rides = stats.get('total_rides', 0)
                customer.total_spent = stats.get('total_spent', 0)
                customer.save()
            
            action = "created" if created else "updated"
            logger.info(f"Customer {customer_id} {action} in PostgreSQL")
            return True
            
        except Exception as e:
            logger.error(f"Error syncing customer {customer_id}: {e}")
            return False
    
    def sync_all_customers(self, limit: int = 1000) -> dict:
        """
        Sync all customers from Firebase to PostgreSQL
        
        Args:
            limit: Maximum number of customers to sync
            
        Returns:
            Dictionary with sync statistics
        """
        stats = {
            'total': 0,
            'created': 0,
            'updated': 0,
            'failed': 0
        }
        
        try:
            # Get all customers from Firebase
            firebase_customers = self.firebase_service.list_customers(limit=limit)
            stats['total'] = len(firebase_customers)
            
            for customer_data in firebase_customers:
                try:
                    customer_id = customer_data['firebase_id']
                    
                    customer, created = Customer.objects.update_or_create(
                        firebase_id=customer_id,
                        defaults={
                            'email': customer_data.get('email', ''),
                            'phone_number': customer_data.get('phone_number', ''),
                            'full_name': customer_data.get('full_name', ''),
                            'profile_image_url': customer_data.get('profile_image_url'),
                            'status': customer_data.get('status', 'ACTIVE'),
                            'verification_status': customer_data.get('verification_status', 'UNVERIFIED'),
                            'id_document_url': customer_data.get('id_document_url'),
                            'id_document_type': customer_data.get('id_document_type', ''),
                            'email_verified': customer_data.get('email_verified', False),
                            'phone_verified': customer_data.get('phone_verified', False),
                            'registration_date': customer_data.get('created_at'),
                            'last_login': customer_data.get('last_login'),
                            'suspension_reason': customer_data.get('suspension_reason', ''),
                            'admin_notes': customer_data.get('admin_notes', ''),
                        }
                    )
                    
                    if created:
                        stats['created'] += 1
                    else:
                        stats['updated'] += 1
                        
                except Exception as e:
                    logger.error(f"Error syncing customer: {e}")
                    stats['failed'] += 1
            
            logger.info(f"Customer sync completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error syncing all customers: {e}")
            return stats
    
    def sync_customer_rides(self, customer_id: str, limit: int = 100) -> int:
        """
        Sync ride history for a customer from Firebase to PostgreSQL
        
        Args:
            customer_id: Firebase document ID
            limit: Maximum number of rides to sync
            
        Returns:
            Number of rides synced
        """
        try:
            # Ensure customer exists in PostgreSQL
            customer = Customer.objects.filter(firebase_id=customer_id).first()
            if not customer:
                logger.warning(f"Customer {customer_id} not found in PostgreSQL, syncing first")
                self.sync_single_customer(customer_id)
                customer = Customer.objects.get(firebase_id=customer_id)
            
            # Get ride history from Firebase
            rides = self.firebase_service.get_customer_rides(customer_id, limit=limit)
            
            synced_count = 0
            for ride in rides:
                try:
                    CustomerRideHistory.objects.update_or_create(
                        firebase_id=ride.get('firebase_id'),
                        defaults={
                            'customer': customer,
                            'bike_id': ride.get('bike_id', ''),
                            'start_time': ride.get('start_time'),
                            'end_time': ride.get('end_time'),
                            'duration_minutes': ride.get('duration_minutes', 0),
                            'start_latitude': ride.get('start_latitude'),
                            'start_longitude': ride.get('start_longitude'),
                            'end_latitude': ride.get('end_latitude'),
                            'end_longitude': ride.get('end_longitude'),
                            'start_zone_id': ride.get('start_zone_id', ''),
                            'end_zone_id': ride.get('end_zone_id', ''),
                            'distance_km': ride.get('distance_km', 0),
                            'amount_charged': ride.get('amount_charged', 0),
                            'payment_status': ride.get('payment_status', 'PENDING'),
                            'rental_status': ride.get('rental_status', 'ACTIVE'),
                            'cancellation_reason': ride.get('cancellation_reason', ''),
                        }
                    )
                    synced_count += 1
                except Exception as e:
                    logger.error(f"Error syncing ride record: {e}")
            
            logger.info(f"Synced {synced_count} rides for customer {customer_id}")
            return synced_count
            
        except Exception as e:
            logger.error(f"Error syncing rides for customer {customer_id}: {e}")
            return 0