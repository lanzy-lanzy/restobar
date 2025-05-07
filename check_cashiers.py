"""
Script to check if there are any users with the CASHIER role.
"""
import os
import sys
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'restobar.settings')
django.setup()

# Import models
from django.contrib.auth.models import User
from ecommerce.models import StaffProfile

# Get all users with CASHIER role
cashiers = User.objects.filter(
    staff_profile__isnull=False,
    staff_profile__role='CASHIER',
    staff_profile__is_active_staff=True
).distinct().select_related('staff_profile')

print(f"Found {cashiers.count()} users with CASHIER role:")
for cashier in cashiers:
    print(f"- {cashier.username} ({cashier.get_full_name()}), ID: {cashier.id}, Employee ID: {cashier.staff_profile.employee_id}")

# Get all staff users
staff_users = User.objects.filter(
    staff_profile__isnull=False,
    staff_profile__is_active_staff=True
).distinct().select_related('staff_profile')

print(f"\nFound {staff_users.count()} active staff users:")
for user in staff_users:
    print(f"- {user.username} ({user.get_full_name()}), Role: {user.staff_profile.role}, ID: {user.id}, Employee ID: {user.staff_profile.employee_id}")
