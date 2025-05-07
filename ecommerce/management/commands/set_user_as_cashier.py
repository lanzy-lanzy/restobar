from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from ecommerce.models import StaffProfile

class Command(BaseCommand):
    help = 'Set a user as a cashier by username'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username of the user to set as cashier')

    def handle(self, *args, **options):
        username = options['username']
        
        try:
            user = User.objects.get(username=username)
            
            # Update staff profile
            if hasattr(user, 'staff_profile'):
                user.staff_profile.role = 'CASHIER'
                user.staff_profile.is_active_staff = True
                user.staff_profile.save()
                self.stdout.write(self.style.SUCCESS(f'Successfully set {username} as a cashier'))
            else:
                self.stdout.write(self.style.ERROR(f'User {username} does not have a staff profile'))
                
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User {username} does not exist'))
