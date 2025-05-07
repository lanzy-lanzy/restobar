from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from ecommerce.models import StaffProfile

class Command(BaseCommand):
    help = 'Fix display of cashiers in staff list by ensuring is_active_staff is True for all cashiers'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting to fix cashier display...'))
        
        # Get all users with cashier role
        cashiers = StaffProfile.objects.filter(role='CASHIER')
        self.stdout.write(self.style.SUCCESS(f'Found {cashiers.count()} cashiers'))
        
        updated_count = 0
        
        for staff_profile in cashiers:
            try:
                # Ensure is_active_staff is True
                if not staff_profile.is_active_staff:
                    staff_profile.is_active_staff = True
                    staff_profile.save()
                    updated_count += 1
                    self.stdout.write(self.style.SUCCESS(f'Updated {staff_profile.user.username} to be active staff'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error updating {staff_profile.user.username}: {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS(f'Successfully updated {updated_count} cashiers'))
