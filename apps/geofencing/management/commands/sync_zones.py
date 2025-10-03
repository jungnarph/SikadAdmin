"""
Django management command to sync geofence zones from Firebase to PostgreSQL
Usage: python manage.py sync_zones
"""

from django.core.management.base import BaseCommand
from apps.geofencing.sync_service import GeofenceSyncService


class Command(BaseCommand):
    help = 'Sync geofence zones from Firebase to PostgreSQL'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--zone-id',
            type=str,
            help='Sync a specific zone by Firebase ID'
        )
    
    def handle(self, *args, **options):
        sync_service = GeofenceSyncService()
        
        zone_id = options.get('zone_id')
        
        if zone_id:
            # Sync single zone
            self.stdout.write(f"Syncing zone: {zone_id}")
            success = sync_service.sync_single_zone(zone_id)
            
            if success:
                self.stdout.write(self.style.SUCCESS(f'✓ Zone {zone_id} synced successfully'))
            else:
                self.stdout.write(self.style.ERROR(f'✗ Failed to sync zone {zone_id}'))
        else:
            # Sync all zones
            self.stdout.write("Syncing all zones from Firebase...")
            stats = sync_service.sync_all_zones()
            
            self.stdout.write(self.style.SUCCESS(f'\n✓ Sync completed:'))
            self.stdout.write(f'  Total: {stats["total"]}')
            self.stdout.write(f'  Created: {stats["created"]}')
            self.stdout.write(f'  Updated: {stats["updated"]}')
            self.stdout.write(f'  Failed: {stats["failed"]}')