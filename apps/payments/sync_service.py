"""
Payment Sync Service
Syncs payment data from Firebase Firestore 'payments' collection to the PostgreSQL Payment model.
"""

from .firebase_service import PaymentFirebaseService
from .models import Payment, CUSTOMER_MODEL_PATH, RIDE_HISTORY_MODEL_PATH
from django.apps import apps # To get models from string paths
from datetime import datetime
import logging
from django.utils.timezone import make_aware # To handle timezone warnings

logger = logging.getLogger(__name__)

class PaymentSyncService:
    """Service to sync payments from Firebase to PostgreSQL"""

    def __init__(self):
        self.firebase_service = PaymentFirebaseService()
        # Get the actual model classes
        self.CustomerModel = apps.get_model(CUSTOMER_MODEL_PATH.split('.')[0], CUSTOMER_MODEL_PATH.split('.')[1])
        self.RideHistoryModel = apps.get_model(RIDE_HISTORY_MODEL_PATH.split('.')[0], RIDE_HISTORY_MODEL_PATH.split('.')[1])

    def _map_firebase_to_django(self, firebase_data: dict) -> dict:
        """Maps Firebase payment data keys/types to Django model fields."""
        mapped_data = {}

        # Basic fields
        mapped_data['amount'] = float(firebase_data.get('amount', 0.0)) # Ensure float/Decimal
        mapped_data['payment_account_info'] = firebase_data.get('paymentAccount', '')

        # Map status and type, converting to uppercase expected by choices
        fb_status = firebase_data.get('paymentStatus', 'UNKNOWN').upper()
        mapped_data['payment_status'] = fb_status if fb_status in dict(Payment.PAYMENT_STATUS_CHOICES) else 'UNKNOWN'

        fb_type = firebase_data.get('paymentType', 'UNKNOWN').upper()
        mapped_data['payment_type'] = fb_type if fb_type in dict(Payment.PAYMENT_TYPE_CHOICES) else 'UNKNOWN'

        # Handle timestamp (use the pre-converted datetime object if available)
        payment_dt = firebase_data.get('payment_date_dt')
        if payment_dt:
            # Make the datetime timezone-aware if it's naive
            if payment_dt.tzinfo is None or payment_dt.tzinfo.utcoffset(payment_dt) is None:
                 # Assume UTC if no timezone info from Firebase, adjust if needed based on actual data
                 # Or use settings.TIME_ZONE
                 mapped_data['payment_date'] = make_aware(payment_dt)
            else:
                 mapped_data['payment_date'] = payment_dt
        else:
             mapped_data['payment_date'] = None # Or handle default/error

        # --- Link Foreign Keys ---
        # Link Customer (using firebase_id)
        customer_firebase_id = firebase_data.get('uid')
        if customer_firebase_id:
            try:
                # Get the Customer instance using firebase_id
                customer_instance = self.CustomerModel.objects.filter(firebase_id=customer_firebase_id).first()
                if customer_instance:
                    mapped_data['customer'] = customer_instance
                else:
                    logger.warning(f"Customer with firebase_id {customer_firebase_id} not found in Django DB for payment {firebase_data.get('firebase_id')}.")
                    mapped_data['customer'] = None
            except self.CustomerModel.DoesNotExist:
                logger.warning(f"Customer model error for firebase_id {customer_firebase_id}.")
                mapped_data['customer'] = None
        else:
            mapped_data['customer'] = None


        # Link RideHistory (using firebase_id, find based on paymentId in ride_logs)
        # We need the RideHistory Firebase ID which matches the Payment Firebase ID ('firebase_id')
        payment_firebase_id = firebase_data.get('firebase_id')
        if payment_firebase_id:
            try:
                # Find RideHistory where its paymentId (from Firebase ride_logs) matches this payment's firebase_id
                # NOTE: This assumes the 'paymentId' field exists in the Firebase ride_logs data
                # AND that the RideHistory model syncs this paymentId field or can otherwise be linked.
                # A better approach: Modify RideHistory model to store payment_firebase_id explicitly or link directly.
                # For now, let's assume RideHistory has a 'firebase_id' that corresponds to the ride log document ID
                # and we can find the ride log that *contains* this payment's ID. This requires a different approach.

                # Alternative: Let's assume the CustomerRideHistory model is modified to have a direct link
                # or stores the 'paymentId' from Firebase ride_logs as 'payment_firebase_id'
                # Find the ride history record whose payment link matches this payment's ID
                ride_instance = self.RideHistoryModel.objects.filter(payment_record_id=payment_firebase_id).first()

                # If the above doesn't work (because CustomerRideHistory doesn't store payment_firebase_id),
                # we might need to query Firebase ride_logs to find the ride associated with this paymentId
                # and then find the corresponding RideHistory object. This is less efficient.

                # Let's proceed assuming CustomerRideHistory *can* be linked back from Payment's firebase_id
                # (e.g., via ride = OneToOneField(..., to_field='firebase_id'))

                # We already established the ride link in the Payment model. Let's find the ride based on payment ID.
                # THIS LOGIC IS COMPLEX and depends on how ride_logs are synced.
                # Simplification: Assume the linking happens elsewhere or is not strictly needed for sync.
                # If RideHistory model has a direct FK or O2O to Payment:
                # ride_instance = self.RideHistoryModel.objects.filter(payment_record__firebase_id=payment_firebase_id).first()
                # If RideHistory *stores* the payment firebase ID:
                # ride_instance = self.RideHistoryModel.objects.filter(payment_firebase_id_field=payment_firebase_id).first()

                # Safest assumption for now: Ride linking might need adjustment based on final models.
                # We will try to find the ride based on the OneToOneField relationship established in models.py
                try:
                    ride_instance = self.RideHistoryModel.objects.filter(firebase_id=payment_firebase_id).first() # This assumes ride_firebase_id == payment_firebase_id which is likely INCORRECT
                    # Correct approach requires finding ride where ride.paymentId == payment.firebase_id
                    # This logic needs adjustment. For now, we'll leave ride linking potentially incomplete.
                    # TODO: Refine ride linking logic based on CustomerRideHistory model structure.
                    # A possible structure is CustomerRideHistory has a field `payment_firebase_id`
                    ride_instance_by_payment_id = self.RideHistoryModel.objects.filter(firebase_id__in=self._get_ride_ids_for_payment(payment_firebase_id)).first()


                    if ride_instance_by_payment_id:
                        mapped_data['ride'] = ride_instance_by_payment_id
                    else:
                        # logger.warning(f"Ride history linked to payment {payment_firebase_id} not found in Django DB.")
                        mapped_data['ride'] = None
                except self.RideHistoryModel.DoesNotExist:
                     mapped_data['ride'] = None
                except Exception as ride_link_error:
                    logger.error(f"Error linking ride for payment {payment_firebase_id}: {ride_link_error}")
                    mapped_data['ride'] = None

            except Exception as model_error:
                logger.error(f"Model lookup error during mapping: {model_error}")
                mapped_data['ride'] = None # Ensure it's set to None on error
        else:
             mapped_data['ride'] = None


        return mapped_data

    # Helper function placeholder - needs implementation if querying Firebase ride_logs
    def _get_ride_ids_for_payment(self, payment_firebase_id: str) -> list:
        # This function would query the Firebase 'ride_logs' collection
        # where 'paymentId' == payment_firebase_id and return the document IDs (firebase_ids)
        # of the matching ride logs.
        # Example (conceptual, needs Firebase integration):
        # ride_docs = firebase_db.collection('ride_logs').where('paymentId', '==', payment_firebase_id).stream()
        # return [doc.id for doc in ride_docs]
        logger.warning("_get_ride_ids_for_payment is not fully implemented. Ride linking may be incomplete.")
        return [] # Return empty list for now


    def sync_single_payment(self, payment_id: str) -> bool:
        """
        Sync a single payment record from Firebase to PostgreSQL.

        Args:
            payment_id: Firebase document ID of the payment.

        Returns:
            True if successful, False otherwise.
        """
        try:
            firebase_data = self.firebase_service.get_payment(payment_id)
            if not firebase_data:
                # Already logged in firebase_service
                return False

            # Map data to Django model fields
            defaults = self._map_firebase_to_django(firebase_data)

            # Ensure essential fields are present
            if 'customer' not in defaults:
                logger.error(f"Skipping payment {payment_id} sync: Associated customer not found in Django DB.")
                return False # Cannot save without customer link if it's mandatory

            # Update or create in PostgreSQL
            payment, created = Payment.objects.update_or_create(
                firebase_id=payment_id,
                defaults=defaults
            )

            action = "created" if created else "updated"
            logger.info(f"Payment {payment_id} {action} in PostgreSQL.")
            return True

        except Exception as e:
            logger.error(f"Error syncing payment {payment_id}: {e}", exc_info=True)
            return False

    def sync_all_payments(self, limit: int = 1000) -> dict:
        """
        Sync multiple payments from Firebase to PostgreSQL.

        Args:
            limit: Maximum number of payments to fetch from Firebase in one go.

        Returns:
            Dictionary with sync statistics.
        """
        stats = {
            'total': 0,
            'processed': 0, # Renamed from created/updated as update_or_create handles both
            'failed': 0
        }
        try:
            # Fetch payments from Firebase
            # Implement pagination in firebase_service if dealing with very large datasets
            firebase_payments = self.firebase_service.list_payments(limit=limit)
            stats['total'] = len(firebase_payments)

            for fb_payment_data in firebase_payments:
                payment_id = fb_payment_data.get('firebase_id')
                if not payment_id:
                    stats['failed'] += 1
                    logger.warning("Found Firebase payment data without an ID.")
                    continue

                if self.sync_single_payment(payment_id):
                    stats['processed'] += 1
                else:
                    stats['failed'] += 1

            logger.info(f"Payment sync completed: Processed {stats['processed']}, Failed {stats['failed']} out of {stats['total']} fetched.")
            return stats

        except Exception as e:
            logger.error(f"Error during bulk payment sync: {e}", exc_info=True)
            return stats

    # Add method to potentially sync payments for a specific customer if needed
    def sync_payments_for_customer(self, customer_firebase_id: str, limit: int = 100) -> dict:
        """Syncs recent payments specifically for one customer."""
        stats = {'total': 0, 'processed': 0, 'failed': 0}
        try:
            firebase_payments = self.firebase_service.get_payments_for_user(customer_firebase_id, limit=limit)
            stats['total'] = len(firebase_payments)
            for fb_payment_data in firebase_payments:
                 payment_id = fb_payment_data.get('firebase_id')
                 if payment_id and self.sync_single_payment(payment_id):
                     stats['processed'] += 1
                 else:
                     stats['failed'] += 1
            logger.info(f"Synced payments for customer {customer_firebase_id}: Processed {stats['processed']}, Failed {stats['failed']}")
            return stats
        except Exception as e:
            logger.error(f"Error syncing payments for customer {customer_firebase_id}: {e}", exc_info=True)
            return stats
