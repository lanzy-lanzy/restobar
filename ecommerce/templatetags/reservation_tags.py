from django import template

register = template.Library()

@register.simple_tag
def has_pending_payment(reservation):
    """Check if a reservation has any pending payments"""
    return reservation.payments.filter(status='PENDING').exists()
