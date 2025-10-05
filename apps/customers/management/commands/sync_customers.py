"""
Django management command to sync customers from Firebase to PostgreSQL
Usage: python manage.py sync_customers
"""

from django.core.management.base import BaseCommand
from apps.customers.sync_service import CustomerSyncService


class Command(BaseCommand):
    help = 'Sync customers from Firebase to PostgreSQL'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--customer-id',
            type=str,
            help='Sync a specific customer by Firebase ID'
        )
        parser.add_argument(
            '--with-rides',
            action='store_true',
            help='Also sync ride history'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=1000,
            help='Maximum number of customers to sync (default: 1000)'
        )
    
    def handle(self, *args, **options):
        sync_service = CustomerSyncService()
        
        customer_id = options.get('customer_id')
        with_rides = options.get('with_rides', False)
        limit = options.get('limit', 1000)
        
        if customer_id:
            # Sync single customer
            self.stdout.write(f"Syncing customer: {customer_id}")
            success = sync_service.sync_single_customer(customer_id)
            
            if success:
                self.stdout.write(self.style.SUCCESS(f'✓ Customer {customer_id} synced successfully'))
                
                if with_rides:
                    self.stdout.write(f"Syncing ride history for {customer_id}")
                    count = sync_service.sync_customer_rides(customer_id)
                    self.stdout.write(self.style.SUCCESS(f'✓ Synced {count} ride records'))
            else:
                self.stdout.write(self.style.ERROR(f'✗ Failed to sync customer {customer_id}'))
        else:
            # Sync all customers
            self.stdout.write(f"Syncing up to {limit} customers from Firebase...")
            stats = sync_service.sync_all_customers(limit=limit)
            
            self.stdout.write(self.style.SUCCESS(f'\n✓ Sync completed:'))
            self.stdout.write(f'  Total: {stats["total"]}')
            self.stdout.write(f'  Created: {stats["created"]}')
            self.stdout.write(f'  Updated: {stats["updated"]}')
            self.stdout.write(f'  Failed: {stats["failed"]}')