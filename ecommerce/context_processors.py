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
        'pending_reservation_payments_count': pending_payments_count,
        'pending_reservations_count': pending_reservations_count,
        'recent_pending_reservations': recent_pending_reservations
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
