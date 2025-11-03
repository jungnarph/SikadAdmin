import os
from django.db import migrations
from django.contrib.auth.hashers import make_password

def create_admin_user(apps, schema_editor):
    """
    Creates a superuser from environment variables,
    only if one doesn't already exist.
    """
    AdminUser = apps.get_model('accounts', 'AdminUser')
    
    # Get credentials from environment variables
    USERNAME = os.environ.get('ADMIN_USER')
    EMAIL = os.environ.get('ADMIN_EMAIL')
    PASSWORD = os.environ.get('ADMIN_PASS')

    # Don't do anything if variables aren't set
    if not all([USERNAME, EMAIL, PASSWORD]):
        print("ADMIN_USER, ADMIN_EMAIL, or ADMIN_PASS environment variables not set. Skipping superuser creation.")
        return

    # Only create if the user does not exist
    if not AdminUser.objects.filter(username=USERNAME).exists():
        AdminUser.objects.create_superuser(
            username=USERNAME,
            email=EMAIL,
            password=PASSWORD
        )
        print(f"Superuser '{USERNAME}' created successfully.")
    else:
        print(f"Superuser '{USERNAME}' already exists. Skipping creation.")


class Migration(migrations.Migration):

    dependencies = [
        # Change this to your LAST accounts migration
        ('accounts', '0004_delete_role'), 
    ]

    operations = [
        migrations.RunPython(create_admin_user),
    ]