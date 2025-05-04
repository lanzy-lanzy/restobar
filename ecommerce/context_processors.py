from .views import get_cart_count
from django.utils import timezone
from .models import Reservation, ReservationPayment, Order

def cart_processor(request):
    """Add cart count to all templates"""
    return {
        'cart_count': get_cart_count(request)
    }

def reservation_processor(request):
    """Add reservation notifications to all templates"""
    # Only process for authenticated users with staff roles
    if not request.user.is_authenticated or not hasattr(request.user, 'staff_profile'):
        return {}

    # Get today's confirmed reservations for cashiers
    today = timezone.now().date()
    confirmed_reservations = Reservation.objects.filter(
        status='CONFIRMED',
        date=today
    ).order_by('time')

    # Count of unprocessed confirmed reservations for cashiers
    unprocessed_count = confirmed_reservations.filter(is_processed=False).count()

    # Get reservations with pre-ordered menu items
    reservations_with_preorders = confirmed_reservations.filter(
        is_processed=False,
        has_menu_items=True
    )

    # Get reservations without pre-ordered menu items
    reservations_without_preorders = confirmed_reservations.filter(
        is_processed=False,
        has_menu_items=False
    )

    # Count of pending reservation payments for cashiers
    pending_payments_count = ReservationPayment.objects.filter(status='PENDING').count()

    # Count of pending reservations for managers
    pending_reservations_count = Reservation.objects.filter(status='PENDING').count()

    # Get recent pending reservations for managers (last 24 hours)
    yesterday = timezone.now() - timezone.timedelta(days=1)
    recent_pending_reservations = Reservation.objects.filter(
        status='PENDING',
        created_at__gte=yesterday
    ).order_by('-created_at')[:5]

    return {
        'confirmed_reservations': confirmed_reservations,
        'unprocessed_reservations_count': unprocessed_count,
        'reservations_with_preorders': reservations_with_preorders,
        'reservations_without_preorders': reservations_without_preorders,
        'reservations_with_preorders_count': reservations_with_preorders.count(),
        'reservations_without_preorders_count': reservations_without_preorders.count(),
        'pending_reservation_payments_count': pending_payments_count,
        'pending_reservations_count': pending_reservations_count,
        'recent_pending_reservations': recent_pending_reservations
    }

def cashier_notification_processor(request):
    """Add cashier notifications and categorized orders to all templates"""
    # Only process for authenticated users with cashier role
    if not request.user.is_authenticated or not hasattr(request.user, 'staff_profile') or request.user.staff_profile.role != 'CASHIER':
        return {}

    # Get today's date
    today = timezone.now().date()

    # Get all orders for today
    today_orders = Order.objects.filter(
        created_at__date=today
    ).order_by('-created_at')

    # Categorize orders
    # 1. Walk-in orders (DINE_IN orders created by staff without reservation)
    walkin_orders = today_orders.filter(
        order_type='DINE_IN',
        reservation__isnull=True,
        created_by__staff_profile__isnull=False
    )

    # 2. Regular orders (non-reservation, non-walkin)
    regular_orders = today_orders.filter(
        reservation__isnull=True
    ).exclude(
        id__in=walkin_orders.values_list('id', flat=True)
    )

    # 3. Orders from reservations with pre-ordered menu items
    reservation_with_preorder_orders = today_orders.filter(
        reservation__isnull=False,
        reservation__has_menu_items=True
    )

    # 4. Orders from reservations without pre-ordered menu items
    reservation_without_preorder_orders = today_orders.filter(
        reservation__isnull=False,
        reservation__has_menu_items=False
    )

    # Get pending orders (not completed or cancelled) for each category
    pending_walkin_orders = walkin_orders.filter(status__in=['PENDING', 'PREPARING', 'READY'])
    pending_regular_orders = regular_orders.filter(status__in=['PENDING', 'PREPARING', 'READY'])
    pending_reservation_with_preorder_orders = reservation_with_preorder_orders.filter(status__in=['PENDING', 'PREPARING', 'READY'])
    pending_reservation_without_preorder_orders = reservation_without_preorder_orders.filter(status__in=['PENDING', 'PREPARING', 'READY'])

    # Get unprocessed reservations that need attention
    unprocessed_reservations = Reservation.objects.filter(
        status='CONFIRMED',
        date=today,
        is_processed=False
    ).order_by('time')

    # Get pending reservation payments
    pending_reservation_payments = ReservationPayment.objects.filter(status='PENDING')

    # Get pending GCash payments
    pending_payments = Order.objects.filter(
        payment_method='GCASH',
        payment_status='PENDING'
    )

    # Create notifications list
    notifications = []

    # Add notifications for unprocessed reservations
    for reservation in unprocessed_reservations:
        notification_type = 'reservation_with_preorder' if reservation.has_menu_items else 'reservation_without_preorder'
        icon = 'fa-utensils' if reservation.has_menu_items else 'fa-calendar-check'
        color = 'red' if reservation.has_menu_items else 'blue'

        notifications.append({
            'type': notification_type,
            'message': f'Reservation #{reservation.id} for {reservation.name} at {reservation.time} needs processing',
            'link': f'/cashier/reservations/{reservation.id}/',
            'icon': icon,
            'color': color,
            'time': f'Table: {reservation.table_number or "Not assigned"} | {reservation.party_size} guests'
        })

    # Add notifications for pending reservation payments
    for payment in pending_reservation_payments:
        notifications.append({
            'type': 'reservation_payment',
            'message': f'Reservation payment of {payment.amount} needs verification',
            'link': f'/cashier/reservation-payments/{payment.id}/',
            'icon': 'fa-credit-card',
            'color': 'green',
            'time': f'Ref: {payment.reference_number}'
        })

    # Add notifications for pending orders
    recent_pending_orders = today_orders.filter(
        status__in=['PENDING', 'PREPARING', 'READY']
    ).order_by('-created_at')[:5]

    for order in recent_pending_orders:
        status_color = {
            'PENDING': 'yellow',
            'PREPARING': 'purple',
            'READY': 'green'
        }.get(order.status, 'gray')

        status_icon = {
            'PENDING': 'fa-clock',
            'PREPARING': 'fa-fire',
            'READY': 'fa-check-circle'
        }.get(order.status, 'fa-question-circle')

        order_type = "Walk-in" if order.order_type == 'DINE_IN' and order.reservation is None else order.get_order_type_display()

        notifications.append({
            'type': 'order',
            'message': f'Order #{order.id} ({order_type}) is {order.get_status_display()}',
            'link': f'/cashier/order/{order.id}/',
            'icon': status_icon,
            'color': status_color,
            'time': f'₱{order.total_amount} | {order.created_at.strftime("%H:%M")}'
        })

    # Add notifications for pending GCash payments
    for order in pending_payments:
        notifications.append({
            'type': 'payment',
            'message': f'GCash payment for Order #{order.id} needs verification',
            'link': f'/cashier/payments/?status=pending',
            'icon': 'fa-money-bill-wave',
            'color': 'blue',
            'time': f'₱{order.total_amount}'
        })

    return {
        'walkin_orders': walkin_orders,
        'regular_orders': regular_orders,
        'reservation_with_preorder_orders': reservation_with_preorder_orders,
        'reservation_without_preorder_orders': reservation_without_preorder_orders,
        'pending_walkin_orders': pending_walkin_orders,
        'pending_regular_orders': pending_regular_orders,
        'pending_reservation_with_preorder_orders': pending_reservation_with_preorder_orders,
        'pending_reservation_without_preorder_orders': pending_reservation_without_preorder_orders,
        'pending_walkin_orders_count': pending_walkin_orders.count(),
        'pending_regular_orders_count': pending_regular_orders.count(),
        'pending_reservation_with_preorder_orders_count': pending_reservation_with_preorder_orders.count(),
        'pending_reservation_without_preorder_orders_count': pending_reservation_without_preorder_orders.count(),
        'cashier_unprocessed_reservations': unprocessed_reservations,
        'cashier_notifications': notifications,
        'cashier_notification_count': len(notifications)
    }

def customer_notification_processor(request):
    """Add customer notifications to all templates"""
    notifications = []

    if request.user.is_authenticated and not hasattr(request.user, 'staff_profile'):
        try:
            # Check for pending reservations
            pending_reservations = Reservation.objects.filter(
                user=request.user,
                status='PENDING'
            )

            for reservation in pending_reservations:
                notifications.append({
                    'type': 'reservation_pending',
                    'message': f'Your reservation for {reservation.date} at {reservation.time} is pending confirmation.',
                    'link': f'/customer/reservations/',
                    'icon': 'fa-clock',
                    'color': 'yellow'
                })

            # Check for confirmed reservations in the next 24 hours
            now = timezone.now()
            tomorrow = now + timezone.timedelta(days=1)
            upcoming_reservations = Reservation.objects.filter(
                user=request.user,
                status='CONFIRMED',
                date__gte=now.date(),
                date__lte=tomorrow.date()
            )

            for reservation in upcoming_reservations:
                notifications.append({
                    'type': 'reservation_upcoming',
                    'message': f'Your reservation for {reservation.date} at {reservation.time} is coming up soon!',
                    'link': f'/customer/reservations/',
                    'icon': 'fa-calendar-check',
                    'color': 'green'
                })

            # Check for reservations with unpaid status
            unpaid_reservations = Reservation.objects.filter(
                user=request.user,
                payment_status='UNPAID'
            )

            for reservation in unpaid_reservations:
                notifications.append({
                    'type': 'reservation_unpaid',
                    'message': f'Your reservation for {reservation.date} requires payment.',
                    'link': f'/reservations/{reservation.id}/payment/',
                    'icon': 'fa-credit-card',
                    'color': 'red'
                })

        except Exception:
            # Handle any errors gracefully
            pass

    return {
        'customer_notifications': notifications,
        'customer_notification_count': len(notifications)
    }
