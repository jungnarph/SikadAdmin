"""
Django management command to sync payments from Firebase Firestore to PostgreSQL.
Usage: python manage.py sync_payments [--payment-id <id>] [--limit <num>]
"""

from django.core.management.base import BaseCommand, CommandError
from apps.payments.sync_service import PaymentSyncService
import logging
from apps.payments.models import Payment
from django.db.models import Max

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Sync payments from Firebase Firestore to PostgreSQL database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--payment-id',
            type=str,
            help='Sync only a specific payment by its Firebase document ID.'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=1000, # Default limit for bulk sync
            help='Maximum number of payments to fetch during bulk sync (default: 1000).'
        )
        parser.add_argument(
            '--customer-id',
            type=str,
            help='Sync payments only for a specific customer by their Firebase UID.'
        )

    def handle(self, *args, **options):
        # This is the "Full Sync" command.
        # It runs in a loop until all payments are synced.
        
        sync_service = PaymentSyncService()
        payment_id_arg = options.get('payment_id')
        customer_id_arg = options.get('customer_id')
        
        # Use the --limit arg from the command, default to 1000
        BATCH_SIZE = options.get('limit', 1000)
        
        start_message = "Starting FULL incremental payment sync..."
        self.stdout.write(self.style.NOTICE(start_message))
        logger.info(start_message)

        try:
            if payment_id_arg:
                # Sync a single payment
                self.stdout.write(f"Attempting to sync specific payment: {payment_id_arg}")
                success, created = sync_service.sync_single_payment(payment_id_arg) # Assumes sync_single_payment exists
                if success:
                    self.stdout.write(self.style.SUCCESS(f'✓ Successfully synced payment {payment_id_arg}'))
                else:
                    self.stdout.write(self.style.ERROR(f'✗ Failed to sync payment {payment_id_arg}. Check logs.'))
                return # Stop

            if customer_id_arg:
                 # Sync payments for a specific customer (this is not a looping sync)
                 self.stdout.write(f"Attempting to sync payments for customer: {customer_id_arg} (limit: {BATCH_SIZE})")
                 stats = sync_service.sync_payments_for_customer(customer_id_arg, limit=BATCH_SIZE)
                 self.stdout.write(
                     f"Customer Payment Sync Result: Fetched {stats['total']}, "
                     f"Processed {stats['processed']}, Failed {stats['failed']}."
                 )
                 return # Stop

            # --- This is the new looping logic for a full sync ---
            total_created = 0
            total_updated = 0
            total_failed = 0

            while True:
                # 1. Find the last sync point from our database
                latest_payment = Payment.objects.order_by('-payment_date').first()
                start_after = latest_payment.payment_date if latest_payment else None
                
                if start_after:
                    self.stdout.write(f"Querying for {BATCH_SIZE} payments after {start_after}...")
                else:
                    self.stdout.write(f"Querying for first {BATCH_SIZE} payments from beginning...")

                # 2. Fetch the next batch
                stats = sync_service.sync_all_payments(
                    limit=BATCH_SIZE,
                    start_after_timestamp=start_after,
                    order_by='paymentDate', # Match Firebase field
                    direction='ASCENDING'   # Sync oldest-to-newest
                )
                
                created = stats.get("created", 0)
                updated = stats.get("updated", 0)
                failed = stats.get("failed", 0)
                
                total_created += created
                total_updated += updated
                total_failed += failed

                if created > 0 or updated > 0 or failed > 0:
                    self.stdout.write(
                        f"✓ Batch complete: {created} created, {updated} updated, {failed} failed."
                    )
                
                # 3. Check if we are done
                # If the number of payments we got back is less than our batch size,
                # it means we've processed the last page.
                if stats.get('total', 0) < BATCH_SIZE:
                    self.stdout.write(self.style.SUCCESS("✓ All payments are now synced."))
                    break
            
            final_message = f"Full sync complete. Total: {total_created} created, {total_updated} updated, {total_failed} failed."
            self.stdout.write(self.style.SUCCESS(final_message))
            logger.info(final_message)


        except Exception as e:
            logger.error(f"An unexpected error occurred during payment sync: {e}", exc_info=True)
            raise CommandError(f"Payment sync failed: {e}")
