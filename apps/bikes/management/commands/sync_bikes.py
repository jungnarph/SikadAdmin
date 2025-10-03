"""
Django management command to sync bikes from Firebase to PostgreSQL
Usage: python manage.py sync_bikes
"""

from django.core.management.base import BaseCommand
from apps.bikes.sync_service import BikeSyncService


class Command(BaseCommand):
    help = 'Sync bikes from Firebase to PostgreSQL'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--bike-id',
            type=str,
            help='Sync a specific bike by Firebase ID'
        )
        parser.add_argument(
            '--with-history',
            action='store_true',
            help='Also sync location history'
        )
    
    def handle(self, *args, **options):
        sync_service = BikeSyncService()
        
        bike_id = options.get('bike_id')
        with_history = options.get('with_history', False)
        
        if bike_id:
            # Sync single bike
            self.stdout.write(f"Syncing bike: {bike_id}")
            success = sync_service.sync_single_bike(bike_id)
            
            if success:
                self.stdout.write(self.style.SUCCESS(f'✓ Bike {bike_id} synced successfully'))
                
                if with_history:
                    self.stdout.write(f"Syncing location history for {bike_id}")
                    count = sync_service.sync_bike_location_history(bike_id)
                    self.stdout.write(self.style.SUCCESS(f'✓ Synced {count} location records'))
            else:
                self.stdout.write(self.style.ERROR(f'✗ Failed to sync bike {bike_id}'))
        else:
            # Sync all bikes
            self.stdout.write("Syncing all bikes from Firebase...")
            stats = sync_service.sync_all_bikes()
            
            self.stdout.write(self.style.SUCCESS(f'\n✓ Sync completed:'))
            self.stdout.write(f'  Total: {stats["total"]}')
            self.stdout.write(f'  Created: {stats["created"]}')
            self.stdout.write(f'  Updated: {stats["updated"]}')
            self.stdout.write(f'  Failed: {stats["failed"]}')