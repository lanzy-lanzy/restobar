from django import template
import json

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiply the value by the argument"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return value

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary using a key"""
    return dictionary.get(key)

@register.filter
def currency(value):
    """Format value as Philippine Peso with thousand separators and decimal places"""
    try:
        return f"₱{float(value):,.2f}"
    except (ValueError, TypeError):
        return value

@register.filter
def split(value, arg):
    """Split a string by a delimiter"""
    return value.split(arg)

@register.filter
def sum_attr(items, attr):
    """Sum a specific attribute across a list of dictionaries"""
    try:
        return sum(float(item[attr]) if item[attr] is not None else 0 for item in items)
    except (KeyError, TypeError, ValueError):
        return 0

@register.filter
def js(value):
    """Pass through filter for JavaScript code"""
    return value

@register.filter
def is_step_active(order, step):
    """Check if a step is active in the order progress"""
    if order.status == step:
        return True
    if step == 'PAID' and hasattr(order, 'payment') and order.payment and order.payment.status == 'COMPLETED':
        return True
    if step == 'COMPLETED' and order.status == 'COMPLETED':
        return True
    if step == 'CANCELLED' and order.status == 'CANCELLED':
        return True
    return False

@register.filter
def format_menu_items(menu_items_data):
    """Format menu items data from JSON to a readable format"""
    if not menu_items_data:
        return ""

    try:
        # Try to parse the JSON data
        if isinstance(menu_items_data, str):
            items = json.loads(menu_items_data)
        else:
            items = menu_items_data

        if not items:
            return ""

        # Format the items into a readable string
        formatted_items = []
        for item in items:
            if isinstance(item, dict):
                name = item.get('name', 'Unknown Item')
                quantity = item.get('quantity', 1)
                formatted_items.append(f"{quantity}x {name}")
            else:
                formatted_items.append(str(item))

        return ", ".join(formatted_items)
    except (json.JSONDecodeError, TypeError, ValueError):
        # If there's an error parsing the JSON, return a placeholder
        return "Menu items available"

@register.filter
def has_pending_payment(reservation):
    """Check if a reservation has any pending payments"""
    return reservation.payments.filter(status='PENDING').exists()

@register.filter
def filter_by_status(orders, status):
    """Filter a queryset of orders by status"""
    return [order for order in orders if order.status == status]

@register.filter
def percentage(value, total):
    """Calculate percentage of value relative to total"""
    try:
        if float(total) == 0:
            return 0
        return (float(value) / float(total)) * 100
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter
def divide(value, divisor):
    """Divide value by divisor"""
    try:
        if float(divisor) == 0:
            return 0
        return float(value) / float(divisor)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0
