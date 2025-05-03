"""
Email utility functions for the ecommerce app.
"""
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags

def send_reservation_confirmation_email(reservation):
    """
    Send a confirmation email to the customer after making a reservation.
    
    Args:
        reservation: The Reservation object
    """
    subject = f'Reservation Confirmation - 5th Avenue Grill and Restobar #{reservation.id}'
    
    # Prepare context for email template
    context = {
        'reservation': reservation,
        'restaurant_name': '5th Avenue Grill and Restobar',
        'restaurant_address': '123 Main Street, Anytown, Philippines',
        'restaurant_phone': '+63 123 456 7890',
        'restaurant_email': 'info@5thavenuegrill.com',
    }
    
    # Render HTML content from template
    html_message = render_to_string('emails/reservation_confirmation.html', context)
    plain_message = strip_tags(html_message)
    
    # Send email
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[reservation.email],
        html_message=html_message,
        fail_silently=False,
    )
    
    return True

def send_reservation_update_email(reservation, status_change=None):
    """
    Send an email to the customer when their reservation status is updated.
    
    Args:
        reservation: The Reservation object
        status_change: Optional string describing the status change
    """
    subject = f'Reservation Update - 5th Avenue Grill and Restobar #{reservation.id}'
    
    # Prepare context for email template
    context = {
        'reservation': reservation,
        'status_change': status_change or f'Your reservation has been updated to {reservation.get_status_display()}',
        'restaurant_name': '5th Avenue Grill and Restobar',
        'restaurant_address': '123 Main Street, Anytown, Philippines',
        'restaurant_phone': '+63 123 456 7890',
        'restaurant_email': 'info@5thavenuegrill.com',
    }
    
    # Render HTML content from template
    html_message = render_to_string('emails/reservation_update.html', context)
    plain_message = strip_tags(html_message)
    
    # Send email
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[reservation.email],
        html_message=html_message,
        fail_silently=False,
    )
    
    return True

def send_payment_confirmation_email(payment):
    """
    Send a confirmation email to the customer after their payment is verified.
    
    Args:
        payment: The Payment object (either Payment or ReservationPayment)
    """
    # Determine if this is a reservation payment or order payment
    is_reservation = hasattr(payment, 'reservation')
    
    if is_reservation:
        reservation = payment.reservation
        subject = f'Payment Confirmation - Reservation #{reservation.id}'
        
        context = {
            'payment': payment,
            'reservation': reservation,
            'is_reservation': True,
            'restaurant_name': '5th Avenue Grill and Restobar',
            'restaurant_address': '123 Main Street, Anytown, Philippines',
            'restaurant_phone': '+63 123 456 7890',
            'restaurant_email': 'info@5thavenuegrill.com',
        }
        
        recipient = reservation.email
    else:
        order = payment.order
        subject = f'Payment Confirmation - Order #{order.id}'
        
        context = {
            'payment': payment,
            'order': order,
            'is_reservation': False,
            'restaurant_name': '5th Avenue Grill and Restobar',
            'restaurant_address': '123 Main Street, Anytown, Philippines',
            'restaurant_phone': '+63 123 456 7890',
            'restaurant_email': 'info@5thavenuegrill.com',
        }
        
        recipient = order.email or order.user.email
    
    # Render HTML content from template
    html_message = render_to_string('emails/payment_confirmation.html', context)
    plain_message = strip_tags(html_message)
    
    # Send email
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient],
        html_message=html_message,
        fail_silently=False,
    )
    
    return True
