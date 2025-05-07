from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
from .models import MenuItem, Category, Reservation, Order, OrderItem, Payment

@require_GET
def menu_items_api(request):
    """API endpoint to get menu items in JSON format"""
    # Get all available menu items
    menu_items = MenuItem.objects.filter(is_available=True)

    # Filter by category if provided
    category_id = request.GET.get('category')
    if category_id:
        menu_items = menu_items.filter(category_id=category_id)

    # Convert to list of dictionaries
    items_data = []
    for item in menu_items:
        items_data.append({
            'id': item.id,
            'name': item.name,
            'description': item.description,
            'price': float(item.price),
            'image': item.image.url if item.image else None,
            'category': item.category.name if item.category else 'Uncategorized',
            'is_vegetarian': item.is_vegetarian,
            'spice_level': item.spice_level
        })

    return JsonResponse(items_data, safe=False)

@require_GET
def reservation_detail_api(request, reservation_id):
    """API endpoint to get reservation details in JSON format"""
    try:
        # Get the reservation
        if request.user.is_staff:
            reservation = Reservation.objects.get(id=reservation_id)
        else:
            # Regular users can only view their own reservations
            reservation = Reservation.objects.get(id=reservation_id, user=request.user)

        # Get menu items if any
        menu_items = []
        if reservation.has_menu_items:
            reservation_items = reservation.reservation_items.all()
            for item in reservation_items:
                menu_items.append({
                    'id': item.menu_item.id,
                    'name': item.menu_item.name,
                    'quantity': item.quantity,
                    'price': float(item.price),
                    'subtotal': float(item.subtotal),
                    'special_instructions': item.special_instructions
                })

        # Convert to dictionary
        reservation_data = {
            'id': reservation.id,
            'name': reservation.name,
            'email': reservation.email,
            'phone': reservation.phone,
            'date': reservation.date.strftime('%b %d, %Y'),
            'time': reservation.time.strftime('%H:%M'),
            'party_size': reservation.party_size,
            'table_number': reservation.table_number,
            'special_requests': reservation.special_requests,
            'status': reservation.get_status_display(),
            'status_code': reservation.status,
            'has_menu_items': reservation.has_menu_items,
            'menu_items': menu_items,
            'created_at': reservation.created_at.strftime('%b %d, %Y %H:%M'),
            'updated_at': reservation.updated_at.strftime('%b %d, %Y %H:%M') if reservation.updated_at else None
        }

        return JsonResponse(reservation_data)
    except Reservation.DoesNotExist:
        return JsonResponse({'error': 'Reservation not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_GET
def order_details_api(request, order_id):
    """API endpoint to get order details for modal view"""
    try:
        # Check if user has permission to view all orders
        if not request.user.is_staff and not request.user.is_superuser:
            return JsonResponse({'error': 'Permission denied'}, status=403)

        # Get the order
        order = Order.objects.get(id=order_id)
        order_items = order.order_items.all()

        # Get payment information if available
        payment = Payment.objects.filter(order=order).first()

        # Render the order details template
        html_content = render_to_string('admin/order_details_modal.html', {
            'order': order,
            'order_items': order_items,
            'payment': payment,
        })

        return JsonResponse({
            'html': html_content,
            'order_id': order.id
        })
    except Order.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
