"""
Django management command to sync rides from Firebase Firestore to PostgreSQL.
Usage: python manage.py sync_rides [--ride-id <firebase_doc_id>] [--limit <num>]
"""

from django.core.management.base import BaseCommand, CommandError
from apps.rides.sync_service import RideSyncService
from apps.rides.firebase_service import RideFirebaseService # Import Firebase service to fetch data
from apps.rides.models import Ride
from django.db.models import Max
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Sync rides from Firebase Firestore (ride_logs collection) to PostgreSQL database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ride-id',
            type=str,
            help='Sync only a specific ride by its Firebase document ID.'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=1000, # Default limit for bulk sync
            help='Maximum number of rides to fetch during bulk sync (default: 1000).'
        )
        # Add other arguments if needed, e.g., --start-date, --end-date

    def handle(self, *args, **options):
        # This is the "Full Sync" command.
        # It runs in a loop until all rides are synced.
        
        sync_service = RideSyncService()
        ride_id_arg = options.get('ride_id')
        
        BATCH_SIZE = 1000 # Use the large limit from the --limit arg
        
        start_message = "Starting FULL incremental ride sync..."
        self.stdout.write(self.style.NOTICE(start_message))
        logger.info(start_message)

        try:
            if ride_id_arg:
                # Sync a single ride
                self.stdout.write(f"Attempting to sync specific ride: {ride_id_arg}")
                success, created = sync_service.sync_single_ride(ride_id_arg) # Assumes sync_single_ride exists
                if success:
                    self.stdout.write(self.style.SUCCESS(f'✓ Successfully synced ride {ride_id_arg}'))
                else:
                    self.stdout.write(self.style.ERROR(f'✗ Failed to sync ride {ride_id_arg}. Check logs.'))
                
                return # Stop after syncing the single ride

            # --- This is the new looping logic for a full sync ---
            total_created = 0
            total_updated = 0
            total_failed = 0

            while True:
                # 1. Find the last sync point from our database
                latest_ride = Ride.objects.order_by('-start_time').first()
                start_after = latest_ride.start_time if latest_ride else None
                
                if start_after:
                    self.stdout.write(f"Querying for {BATCH_SIZE} rides after {start_after}...")
                else:
                    self.stdout.write(f"Querying for first {BATCH_SIZE} rides from beginning...")

                # 2. Fetch the next batch
                stats = sync_service.sync_all_rides(
                    limit=BATCH_SIZE,
                    start_after_timestamp=start_after,
                    order_by='startTime',
                    direction='ASCENDING' # Sync oldest-to-newest
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
                # If the number of rides we got back is less than our limit,
                # it means we've processed the last page.
                if stats.get('total', 0) < BATCH_SIZE:
                    self.stdout.write(self.style.SUCCESS("✓ All rides are now synced."))
                    break
            
            final_message = f"Full sync complete. Total: {total_created} created, {total_updated} updated, {total_failed} failed."
            self.stdout.write(self.style.SUCCESS(final_message))
            logger.info(final_message)


        except Exception as e:
            logger.error(f"An unexpected error occurred during ride sync: {e}", exc_info=True)
            raise CommandError(f"Ride sync failed: {e}")