"""
Firebase Service for Customers
Handles all Firebase Firestore operations for customers
"""

from firebase_admin import firestore, auth
from datetime import datetime
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class CustomerFirebaseService:
    """Service class for Firebase customer operations"""
    
    def __init__(self):
        self.db = firestore.client()
        self.collection = self.db.collection('customers')
    
    def get_customer(self, customer_id: str) -> Optional[Dict]:
        """
        Get a single customer from Firebase
        
        Args:
            customer_id: Firebase document ID (UID)
            
        Returns:
            Dictionary with customer data or None if not found
        """
        try:
            doc_ref = self.collection.document(customer_id)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                data['firebase_id'] = doc.id
                return data
            
            return None
        except Exception as e:
            logger.error(f"Error fetching customer {customer_id}: {e}")
            return None
    
    def list_customers(self, status: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """
        List customers from Firebase with optional filters
        
        Args:
            status: Filter by status (ACTIVE, SUSPENDED, etc.)
            limit: Maximum number of customers to retrieve
            
        Returns:
            List of customer dictionaries
        """
        try:
            query = self.collection.limit(limit)
            
            if status:
                query = query.where('status', '==', status)
            
            docs = query.stream()
            customers = []
            
            for doc in docs:
                data = doc.to_dict()
                data['firebase_id'] = doc.id
                customers.append(data)
            
            return customers
        except Exception as e:
            logger.error(f"Error listing customers: {e}")
            return []
    
    def update_customer(self, customer_id: str, updates: Dict) -> bool:
        """
        Update a customer in Firebase
        
        Args:
            customer_id: Firebase document ID
            updates: Dictionary of fields to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc_ref = self.collection.document(customer_id)
            updates['updated_at'] = firestore.SERVER_TIMESTAMP
            doc_ref.update(updates)
            logger.info(f"Updated customer {customer_id} in Firebase")
            return True
        except Exception as e:
            logger.error(f"Error updating customer {customer_id}: {e}")
            return False
    
    def suspend_customer(self, customer_id: str, reason: str, admin_id: str) -> bool:
        """
        Suspend a customer account
        
        Args:
            customer_id: Firebase document ID
            reason: Reason for suspension
            admin_id: ID of admin performing the suspension
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Update Firestore
            doc_ref = self.collection.document(customer_id)
            doc_ref.update({
                'status': 'SUSPENDED',
                'suspension_reason': reason,
                'suspended_at': firestore.SERVER_TIMESTAMP,
                'suspended_by': admin_id,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            # Disable Firebase Auth account
            try:
                auth.update_user(customer_id, disabled=True)
            except Exception as auth_error:
                logger.warning(f"Could not disable auth for {customer_id}: {auth_error}")
            
            logger.info(f"Suspended customer {customer_id}")
            return True
        except Exception as e:
            logger.error(f"Error suspending customer {customer_id}: {e}")
            return False
    
    def reactivate_customer(self, customer_id: str) -> bool:
        """
        Reactivate a suspended customer account
        
        Args:
            customer_id: Firebase document ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Update Firestore
            doc_ref = self.collection.document(customer_id)
            doc_ref.update({
                'status': 'ACTIVE',
                'suspension_reason': firestore.DELETE_FIELD,
                'suspended_at': firestore.DELETE_FIELD,
                'suspended_by': firestore.DELETE_FIELD,
                'reactivated_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            # Re-enable Firebase Auth account
            try:
                auth.update_user(customer_id, disabled=False)
            except Exception as auth_error:
                logger.warning(f"Could not enable auth for {customer_id}: {auth_error}")
            
            logger.info(f"Reactivated customer {customer_id}")
            return True
        except Exception as e:
            logger.error(f"Error reactivating customer {customer_id}: {e}")
            return False
    
    def get_customer_rides(self, customer_id: str, limit: int = 50) -> List[Dict]:
        """
        Get ride history for a customer
        
        Args:
            customer_id: Firebase document ID
            limit: Maximum number of rides to retrieve
            
        Returns:
            List of ride dictionaries
        """
        try:
            rides_ref = self.db.collection('rentals')
            query = rides_ref.where('customer_id', '==', customer_id)\
                             .order_by('start_time', direction=firestore.Query.DESCENDING)\
                             .limit(limit)
            
            docs = query.stream()
            rides = []
            
            for doc in docs:
                data = doc.to_dict()
                data['firebase_id'] = doc.id
                rides.append(data)
            
            return rides
        except Exception as e:
            logger.error(f"Error fetching rides for customer {customer_id}: {e}")
            return []
    
    def get_customer_statistics(self, customer_id: str) -> Dict:
        """
        Get aggregated statistics for a customer
        
        Args:
            customer_id: Firebase document ID
            
        Returns:
            Dictionary with statistics
        """
        try:
            rides = self.get_customer_rides(customer_id, limit=1000)
            
            total_rides = len(rides)
            total_spent = sum(ride.get('amount_charged', 0) for ride in rides)
            total_distance = sum(ride.get('distance_km', 0) for ride in rides)
            total_duration = sum(ride.get('duration_minutes', 0) for ride in rides)
            
            completed_rides = [r for r in rides if r.get('rental_status') == 'COMPLETED']
            active_rides = [r for r in rides if r.get('rental_status') == 'ACTIVE']
            
            return {
                'total_rides': total_rides,
                'total_spent': total_spent,
                'total_distance': total_distance,
                'total_duration': total_duration,
                'completed_rides': len(completed_rides),
                'active_rides': len(active_rides),
                'average_ride_duration': total_duration / total_rides if total_rides > 0 else 0,
                'average_distance': total_distance / total_rides if total_rides > 0 else 0,
            }
        except Exception as e:
            logger.error(f"Error getting statistics for customer {customer_id}: {e}")
            return {}
    
    def verify_customer(self, customer_id: str) -> bool:
        """
        Mark customer as verified (email and phone verified)
        
        Args:
            customer_id: Firebase document ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc_ref = self.collection.document(customer_id)
            
            doc_ref.update({
                'verification_status': 'VERIFIED',
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            logger.info(f"Verified customer {customer_id}")
            return True
        except Exception as e:
            logger.error(f"Error verifying customer {customer_id}: {e}")
            return False
    
    def search_customers(self, search_term: str, limit: int = 50) -> List[Dict]:
        """
        Search customers by email, phone, or name
        
        Args:
            search_term: Search string
            limit: Maximum results
            
        Returns:
            List of matching customers
        """
        try:
            customers = []
            
            # Search by email
            query = self.collection.where('email', '>=', search_term)\
                                  .where('email', '<=', search_term + '\uf8ff')\
                                  .limit(limit)
            
            for doc in query.stream():
                data = doc.to_dict()
                data['firebase_id'] = doc.id
                customers.append(data)
            
            # Search by phone (if not already found by email)
            if len(customers) < limit:
                query = self.collection.where('phone_number', '>=', search_term)\
                                      .where('phone_number', '<=', search_term + '\uf8ff')\
                                      .limit(limit - len(customers))
                
                for doc in query.stream():
                    data = doc.to_dict()
                    data['firebase_id'] = doc.id
                    if data not in customers:
                        customers.append(data)
            
            return customers
        except Exception as e:
            logger.error(f"Error searching customers: {e}")
            return []
    
    def add_admin_note(self, customer_id: str, note: str, admin_id: str) -> bool:
        """
        Add an admin note to customer record
        
        Args:
            customer_id: Firebase document ID
            note: Note text
            admin_id: Admin user ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc_ref = self.collection.document(customer_id)
            
            # Get current notes
            doc = doc_ref.get()
            current_notes = doc.to_dict().get('admin_notes', '') if doc.exists else ''
            
            # Append new note with timestamp
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            new_note = f"\n[{timestamp}] Admin {admin_id}: {note}"
            updated_notes = current_notes + new_note
            
            doc_ref.update({
                'admin_notes': updated_notes,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            logger.info(f"Added admin note to customer {customer_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding admin note to customer {customer_id}: {e}")
            return False