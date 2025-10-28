"""
Customer Sync Service
Syncs customer data from Firebase to PostgreSQL
"""

from .firebase_service import CustomerFirebaseService
from .models import Customer
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def convert_firebase_timestamp(timestamp):
    """
    Convert Firebase timestamp (milliseconds) to Python datetime object

    Args:
        timestamp: Firebase timestamp in milliseconds (int) or datetime object

    Returns:
        datetime object or None if invalid
    """
    if timestamp is None:
        return None

    # If already a datetime object, return as-is
    if isinstance(timestamp, datetime):
        return timestamp

    try:
        # Firebase timestamps are in milliseconds, Python expects seconds
        if isinstance(timestamp, (int, float)):
            return datetime.fromtimestamp(timestamp / 1000.0)
        return None
    except (ValueError, OSError) as e:
        logger.warning(f"Invalid timestamp value: {timestamp} - {e}")
        return None


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
                    'name': firebase_data.get('name', ''),
                    'profile_image_url': firebase_data.get('profile_image_url'),
                    'status': firebase_data.get('status', 'ACTIVE'),
                    'phone_verified': firebase_data.get('phoneVerified', False),
                    'email_verified': firebase_data.get('emailVerified', False),
                    'registration_date': convert_firebase_timestamp(firebase_data.get('createdAt')),
                    'last_login': convert_firebase_timestamp(firebase_data.get('lastLoginTimestamp')),
                    'suspension_reason': firebase_data.get('suspension_reason', ''),
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
    
    def sync_all_customers(self, limit: int = 1000, ride_limit_per_customer: int = 100) -> dict:
        """
        Sync all customers from Firebase to PostgreSQL
        
        Args:
            limit: Maximum number of customers to sync
            ride_limit_per_customer: Maximum number of rides to sync for each customer
            
        Returns:
            Dictionary with sync statistics
        """
        stats = {
            'total': 0,
            'created': 0,
            'updated': 0,
            'failed': 0,
        }
        
        try:
            # Get all customers from Firebase
            firebase_customers = self.firebase_service.list_customers(limit=limit)
            stats['total'] = len(firebase_customers)
            
            for customer_data in firebase_customers:
                customer_id = None # Define outside try block for error logging
                try:
                    customer_id = customer_data['firebase_id']
                    
                    customer, created = Customer.objects.update_or_create(
                        firebase_id=customer_id,
                        defaults={
                            'email': customer_data.get('email', ''),
                            'phone_number': customer_data.get('phone', ''),
                            'name': customer_data.get('name', ''),
                            'profile_image_url': customer_data.get('profileImageUrl'),
                            'status': customer_data.get('status', 'ACTIVE'),
                            'phone_verified': customer_data.get('phoneVerified', False),
                            'registration_date': convert_firebase_timestamp(customer_data.get('createdAt')),
                            'last_login': convert_firebase_timestamp(customer_data.get('lastLoginTimestamp')),
                            'suspension_reason': customer_data.get('suspension_reason', ''),
                        }
                    )

                    # Also sync customer statistics (mirroring sync_single_customer logic)
                    fb_stats = self.firebase_service.get_customer_statistics(customer_id)
                    if fb_stats:
                        customer.total_rides = fb_stats.get('total_rides', 0)
                        customer.total_spent = fb_stats.get('total_spent', 0)
                        customer.save()
                    
                    if created:
                        stats['created'] += 1
                    else:
                        stats['updated'] += 1
                        
                except Exception as e:
                    logger.error(f"Error syncing customer {customer_id}: {e}")
                    stats['failed'] += 1
            
            logger.info(f"Customer sync completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error syncing all customers: {e}")
            return stats