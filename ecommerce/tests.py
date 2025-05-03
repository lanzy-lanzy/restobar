from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from .models import MenuItem, Order, OrderItem, InventoryTransaction, Reservation, ReservationPayment, StaffProfile
from decimal import Decimal
from datetime import date, time

# Create your tests here.

class SalesInventoryTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.admin = User.objects.create_superuser(username='admin', password='adminpass', email='admin@example.com')
        # Remove any auto-created StaffProfiles to avoid unique constraint issues
        StaffProfile.objects.filter(user=self.user).delete()
        StaffProfile.objects.filter(user=self.admin).delete()
        StaffProfile.objects.create(user=self.user, role='CASHIER', is_active_staff=True, employee_id='EMP002')
        StaffProfile.objects.create(user=self.admin, role='MANAGER', is_active_staff=True, employee_id='EMP001')
        self.menu_item = MenuItem.objects.create(
            name='Test Dish', price=Decimal('100.00'), cost_price=Decimal('60.00'), current_stock=50
        )

    def test_walkin_order_updates_inventory(self):
        order = Order.objects.create(
            user=self.user,
            status='COMPLETED',
            order_type='DINE_IN',
            payment_method='CASH',
            payment_status='PAID',
            total_amount=Decimal('200.00'),
            tax_amount=Decimal('0.00'),
            delivery_fee=Decimal('0.00'),
            discount_amount=Decimal('0.00')
        )
        item = OrderItem.objects.create(order=order, menu_item=self.menu_item, quantity=2, price=Decimal('100.00'))
        item.refresh_from_db()
        self.menu_item.refresh_from_db()
        self.assertEqual(self.menu_item.current_stock, 48)
        self.assertTrue(InventoryTransaction.objects.filter(menu_item=self.menu_item, transaction_type='SALE').exists())

    def test_reservation_order_updates_inventory(self):
        reservation = Reservation.objects.create(
            user=self.user,
            name='Test User',
            email='test@example.com',
            phone='1234567890',
            date=date(2025, 4, 19),
            time=time(18, 0),
            party_size=2,
            status='CONFIRMED'
        )
        ReservationPayment.objects.create(reservation=reservation, amount=Decimal('200.00'), payment_type='FULL', status='COMPLETED')
        # Simulate process_reservation logic
        reservation.status = 'COMPLETED'
        reservation.is_processed = True
        reservation.save()
        order = Order.objects.create(
            user=self.user,
            status='COMPLETED',
            order_type='DINE_IN',
            payment_method='GCASH',
            payment_status='PAID',
            total_amount=Decimal('200.00'),
            tax_amount=Decimal('0.00'),
            delivery_fee=Decimal('0.00'),
            discount_amount=Decimal('0.00')
        )
        item = OrderItem.objects.create(order=order, menu_item=self.menu_item, quantity=2, price=Decimal('100.00'))
        item.refresh_from_db()
        self.menu_item.refresh_from_db()
        self.assertEqual(self.menu_item.current_stock, 48)  
        self.assertTrue(InventoryTransaction.objects.filter(menu_item=self.menu_item, transaction_type='SALE').exists())

    def test_dashboard_sales_metrics(self):
        # Create completed orders
        Order.objects.create(
            user=self.admin,
            status='COMPLETED',
            order_type='DINE_IN',
            payment_method='CASH',
            payment_status='PAID',
            total_amount=Decimal('100.00'),
            tax_amount=Decimal('0.00'),
            delivery_fee=Decimal('0.00'),
            discount_amount=Decimal('0.00')
        )
        Order.objects.create(
            user=self.admin,
            status='COMPLETED',
            order_type='DELIVERY',
            payment_method='GCASH',
            payment_status='PAID',
            total_amount=Decimal('150.00'),
            tax_amount=Decimal('0.00'),
            delivery_fee=Decimal('0.00'),
            discount_amount=Decimal('0.00')
        )
        self.client.login(username='admin', password='adminpass')
        response = self.client.get(reverse('manager_dashboard'))
        self.assertContains(response, '100.00')
        self.assertContains(response, '150.00')
