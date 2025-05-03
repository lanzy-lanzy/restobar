from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, F, Q
from django.http import JsonResponse, HttpResponseRedirect
from decimal import Decimal, InvalidOperation
from django.contrib.auth.models import User
from django.urls import reverse
from datetime import datetime
import json

from .models import Order, OrderItem, MenuItem, StaffActivity, Payment, Refund, Reservation, Category, ReservationPayment

@login_required
def cashier_dashboard(request):
    # Check if user has cashier role
    if hasattr(request.user, 'staff_profile') and request.user.staff_profile.role == 'CASHIER':
        # Grant the permission if the user has the cashier role
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from .models import StaffProfile

        # Try to get the permission
        try:
            content_type = ContentType.objects.get_for_model(StaffProfile)
            perm = Permission.objects.get(codename='process_orders', content_type=content_type)
            # Add the permission to the user
            request.user.user_permissions.add(perm)
            request.user.save()
            print(f"Added process_orders permission to user {request.user.username}")
        except Exception as e:
            print(f"Error adding permission: {str(e)}")
    """Main dashboard for cashiers"""
    # Get today's date
    today = timezone.now().date()

    # Get today's orders
    today_orders = Order.objects.filter(
        created_at__date=today
    ).order_by('-created_at')

    # Get pending orders (not completed or cancelled)
    pending_orders = today_orders.filter(
        status__in=['PENDING', 'PREPARING', 'READY']
    )

    # Get completed orders
    completed_orders = today_orders.filter(status='COMPLETED')

    # Get cancelled orders
    cancelled_orders = today_orders.filter(status='CANCELLED')

    # Get unprocessed reservations
    unprocessed_reservations = Reservation.objects.filter(
        status='CONFIRMED',
        date=today,
        is_processed=False
    ).order_by('time')

    # Get completed reservations
    completed_reservations = Reservation.objects.filter(
        status='COMPLETED',
        date=today
    ).order_by('-processed_at')

    # Calculate today's sales - include all completed orders and verified payments
    # First get sales from completed orders
    completed_orders_sales = completed_orders.aggregate(
        total=Sum('total_amount')
    )['total'] or 0

    # Then get sales from verified payments for orders that aren't completed yet
    verified_payments_sales = Payment.objects.filter(
        status='COMPLETED',
        verification_date__date=today,
        order__status__in=['PENDING', 'PREPARING', 'READY']
    ).aggregate(
        total=Sum('amount')
    )['total'] or 0

    # Add reservation payments that have been verified today
    reservation_payments_sales = ReservationPayment.objects.filter(
        status='COMPLETED',
        verification_date__date=today
    ).aggregate(
        total=Sum('amount')
    )['total'] or 0

    # Total sales is the sum of all three
    today_sales = completed_orders_sales + verified_payments_sales + reservation_payments_sales

    # Calculate today's order count - include all orders with verified payments
    # Count completed orders
    completed_orders_count = completed_orders.count()

    # Count orders with verified payments that aren't completed yet
    # Use the reverse relationship from Order to Payment
    verified_payment_orders_count = Order.objects.filter(
        created_at__date=today,
        status__in=['PENDING', 'PREPARING', 'READY'],
        payments__status='COMPLETED',
        payments__verification_date__date=today
    ).distinct().count()

    # Total order count is the sum of both
    today_order_count = completed_orders_count + verified_payment_orders_count

    # Calculate average order value
    avg_order_value = today_sales / today_order_count if today_order_count > 0 else 0

    # Get most ordered items today - include items from all orders with verified payments
    # Get orders with verified payments (both completed and in-progress)
    orders_with_payments = Order.objects.filter(
        Q(status='COMPLETED', created_at__date=today) |
        Q(payments__status='COMPLETED', payments__verification_date__date=today)
    ).distinct()

    # Get top items from these orders
    top_items = OrderItem.objects.filter(
        order__in=orders_with_payments
    ).values(
        'menu_item__name'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_sales=Sum(F('quantity') * F('price'))
    ).order_by('-total_quantity')[:5]

    # Get pending payments
    pending_payments = Payment.objects.filter(
        status='PENDING'
    ).order_by('-payment_date')[:5]

    # Log activity
    StaffActivity.objects.create(
        staff=request.user,
        action='LOGIN',
        details=f"Accessed cashier dashboard",
        ip_address=get_client_ip(request)
    )

    context = {
        'today_date': today,
        'pending_orders': pending_orders,
        'completed_orders': completed_orders,
        'cancelled_orders': cancelled_orders,
        'unprocessed_reservations': unprocessed_reservations,
        'completed_reservations': completed_reservations,
        'today_sales': today_sales,
        'today_order_count': today_order_count,
        'avg_order_value': avg_order_value,
        'top_items': top_items,
        'pending_payments': pending_payments,
        'unprocessed_reservations_count': unprocessed_reservations.count(),
        'active_section': 'cashier_dashboard',
        # Detailed sales breakdown
        'completed_orders_sales': completed_orders_sales,
        'verified_payments_sales': verified_payments_sales,
        'reservation_payments_sales': reservation_payments_sales,
        'completed_orders_count': completed_orders_count,
        'verified_payment_orders_count': verified_payment_orders_count
    }

    return render(request, 'cashier/dashboard.html', context)

@login_required
def new_order(request):
    """Create a new order"""
    # Get all menu items
    menu_items = MenuItem.objects.filter(is_available=True).order_by('category__name', 'name')

    # Get servers for dine-in orders
    servers = User.objects.filter(staff_profile__role__in=['WAITER', 'CASHIER']).order_by('first_name')

    if request.method == 'POST':
        # Get customer information
        customer_name = request.POST.get('customer_name', '')
        customer_phone = request.POST.get('customer_phone', '')
        order_type = request.POST.get('order_type', 'DINE_IN')
        table_number = request.POST.get('table_number', '')
        special_instructions = request.POST.get('special_instructions', '')

        # Get dine-in specific information
        number_of_guests = request.POST.get('number_of_guests', 1)
        server_assigned_id = request.POST.get('server_assigned', None)
        estimated_dining_time = request.POST.get('estimated_dining_time', 60)
        cash_on_hand = request.POST.get('cash_on_hand', '0')

        # Get split bill information
        split_bill = request.POST.get('split_bill', 'false').lower() == 'true'
        split_type = request.POST.get('split_type', 'equal')
        split_ways = request.POST.get('split_ways', 2)

        # Get order items
        item_ids = request.POST.getlist('item_id[]')
        quantities = request.POST.getlist('quantity[]')
        special_instructions_list = request.POST.getlist('item_instructions[]')

        if not item_ids or not quantities or len(item_ids) != len(quantities):
            messages.error(request, 'Please add at least one item to the order')
            return redirect('new_order')

        try:
            # Calculate total amount first
            total_amount = Decimal('0.00')

            # Get menu items and calculate total
            for i in range(len(item_ids)):
                item_id = item_ids[i]
                quantity = int(quantities[i])

                if quantity <= 0:
                    continue

                menu_item = MenuItem.objects.get(id=item_id)
                price = menu_item.price
                total_amount += price * quantity

            # Validate cash on hand for dine-in orders
            if order_type == 'DINE_IN':
                try:
                    cash_amount = Decimal(cash_on_hand)
                except Exception:
                    messages.error(request, 'Invalid cash amount entered.')
                    return redirect('new_order')
                if cash_amount < total_amount:
                    messages.error(request, 'Cash on hand is less than the order total.')
                    return redirect('new_order')

            # Set default payment status and order status based on order type
            payment_status = 'PAID' if order_type == 'DINE_IN' else 'UNPAID'
            payment_method = 'CASH_ON_HAND' if order_type == 'DINE_IN' else 'PENDING'
            # For walk-in orders (DINE_IN), set status directly to COMPLETED to skip the preparation tracking
            order_status = 'COMPLETED' if order_type == 'DINE_IN' else 'PENDING'

            # Create order with basic information including total_amount
            order = Order.objects.create(
                user=request.user,
                customer_name=customer_name,
                customer_phone=customer_phone,
                order_type=order_type,
                table_number=table_number,
                special_instructions=special_instructions,
                status=order_status,  # Set status based on order type
                created_by=request.user,
                total_amount=total_amount,  # Set the total amount here
                payment_status=payment_status,  # Set payment status based on order type
                payment_method=payment_method,  # Set payment method for dine-in
                preparing_at=timezone.now() if order_type == 'DINE_IN' else None,  # Set preparing timestamp for dine-in
                completed_at=timezone.now() if order_type == 'DINE_IN' else None  # Set completed timestamp for dine-in
            )

            # Add dine-in specific information if applicable
            if order_type == 'DINE_IN':
                try:
                    order.number_of_guests = int(number_of_guests)
                except (ValueError, TypeError):
                    order.number_of_guests = 1

                try:
                    order.estimated_dining_time = int(estimated_dining_time)
                except (ValueError, TypeError):
                    order.estimated_dining_time = 60

                if server_assigned_id:
                    try:
                        server = User.objects.get(id=server_assigned_id)
                        order.server_assigned = server
                    except User.DoesNotExist:
                        pass

                # Save split bill information
                order.split_bill = split_bill
                order.split_type = split_type.upper()

                try:
                    order.split_ways = int(split_ways)
                    if order.split_ways < 2:
                        order.split_ways = 2
                except (ValueError, TypeError):
                    order.split_ways = 2

                order.save()

                # Create a payment record for dine-in orders
                try:
                    change_amount = Decimal(cash_on_hand) - total_amount if Decimal(cash_on_hand) > total_amount else Decimal('0.00')
                    Payment.objects.create(
                        order=order,
                        amount=total_amount,
                        payment_method='CASH_ON_HAND',
                        status='COMPLETED',
                        verified_by=request.user,
                        verification_date=timezone.now(),
                        reference_number=f'CASH-{order.id}',
                        notes=f'Cash payment: ₱{cash_on_hand}. Change: ₱{change_amount}'
                    )
                    messages.success(request, f"Order #{order.id} created successfully. Change: ₱{change_amount:.2f}")
                except Exception as e:
                    messages.error(request, f"Error recording payment: {str(e)}")
            # Add order items
            for i in range(len(item_ids)):
                item_id = item_ids[i]
                quantity = int(quantities[i])
                item_instructions = special_instructions_list[i] if i < len(special_instructions_list) else ''

                if quantity <= 0:
                    continue

                menu_item = MenuItem.objects.get(id=item_id)
                price = menu_item.price

                OrderItem.objects.create(
                    order=order,
                    menu_item=menu_item,
                    quantity=quantity,
                    price=price,
                    special_instructions=item_instructions
                )

            # Log activity
            StaffActivity.objects.create(
                staff=request.user,
                action='CREATE_ORDER',
                details=f"Created new order #{order.id} for {customer_name}",
                ip_address=get_client_ip(request)
            )

            return redirect('view_order', order_id=order.id)

        except Exception as e:
            messages.error(request, f'Error creating order: {str(e)}')

    # Get occupied tables
    from .views import get_occupied_tables
    occupied_tables = get_occupied_tables()

    context = {
        'menu_items': menu_items,
        'servers': servers,
        'occupied_tables': occupied_tables,
        'active_section': 'new_order'
    }

    return render(request, 'cashier/new_order.html', context)

@login_required
def view_order(request, order_id):
    """View order details"""
    order = get_object_or_404(Order, id=order_id)
    order_items = order.order_items.all()

    # Get payment information if available
    payment = Payment.objects.filter(order=order).first()

    context = {
        'order': order,
        'order_items': order_items,
        'payment': payment,
        'active_section': 'orders'
    }

    return render(request, 'cashier/view_order.html', context)

@login_required
def update_prep_time(request, order_id):
    """Update the estimated preparation time for an order"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

    order = get_object_or_404(Order, id=order_id)

    # Only allow updating preparation time for orders in PREPARING status
    if order.status != 'PREPARING':
        return JsonResponse({'status': 'error', 'message': 'Can only update preparation time for orders in PREPARING status'})

    try:
        # Get the new preparation time
        prep_time = int(request.POST.get('prep_time', 30))

        # Validate the preparation time (between 5 and 120 minutes)
        if prep_time < 5 or prep_time > 120:
            return JsonResponse({'status': 'error', 'message': 'Preparation time must be between 5 and 120 minutes'})

        # Update the preparation time
        order.estimated_preparation_time = prep_time
        order.save()

        # Log activity
        StaffActivity.objects.create(
            staff=request.user,
            action='UPDATE_ORDER',
            details=f"Updated preparation time for order #{order.id} to {prep_time} minutes",
            ip_address=get_client_ip(request)
        )

        return JsonResponse({
            'status': 'success',
            'message': f'Preparation time updated to {prep_time} minutes'
        })
    except ValueError:
        return JsonResponse({'status': 'error', 'message': 'Invalid preparation time'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Error updating preparation time: {str(e)}'})

@login_required
def update_order_status(request, order_id):
    """Update order status with proper flow validation"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

    order = get_object_or_404(Order, id=order_id)
    new_status = request.POST.get('status')
    old_status = order.status

    # Validate the status exists
    if new_status not in dict(Order.STATUS_CHOICES):
        return JsonResponse({'status': 'error', 'message': 'Invalid status'})

    # Validate proper status flow
    valid_transitions = {
        'PENDING': ['PREPARING', 'CANCELLED'],
        'PREPARING': ['READY', 'CANCELLED'],
        'READY': ['COMPLETED', 'CANCELLED'],
        'COMPLETED': [],  # Terminal state
        'CANCELLED': []   # Terminal state
    }

    if new_status not in valid_transitions[old_status]:
        return JsonResponse({
            'status': 'error',
            'message': f'Cannot change order status from {dict(Order.STATUS_CHOICES)[old_status]} to {dict(Order.STATUS_CHOICES)[new_status]}'
        })

    try:
        # Update the status
        order.status = new_status

        # Set timestamps based on status
        if new_status == 'PREPARING':
            order.preparing_at = timezone.now()

            # Set estimated preparation time based on order complexity
            # Default is 30 minutes, but we can adjust based on number of items or item types
            item_count = order.order_items.count()
            if item_count <= 2:
                order.estimated_preparation_time = 15  # Quick orders
            elif item_count <= 5:
                order.estimated_preparation_time = 30  # Standard orders
            else:
                order.estimated_preparation_time = 45  # Complex orders

        elif new_status == 'READY':
            order.ready_at = timezone.now()
        elif new_status == 'COMPLETED':
            order.completed_at = timezone.now()
        elif new_status == 'CANCELLED':
            order.cancelled_at = timezone.now()

        order.save()

        # Log activity with detailed message
        status_messages = {
            'PREPARING': 'started preparing',
            'READY': 'marked as ready for pickup/service',
            'COMPLETED': 'completed',
            'CANCELLED': 'cancelled'
        }

        activity_message = f"Order #{order.id} {status_messages[new_status]}"

        StaffActivity.objects.create(
            staff=request.user,
            action='UPDATE_ORDER',
            details=activity_message,
            ip_address=get_client_ip(request)
        )

        return JsonResponse({
            'status': 'success',
            'message': f'Order status updated to {dict(Order.STATUS_CHOICES)[new_status]}'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Error updating order status: {str(e)}'})

@login_required
def orders_list(request):
    """View list of orders with filtering and batch actions"""
    # Handle POST requests for batch actions
    if request.method == 'POST':
        selected_orders = request.POST.getlist('selected_orders')
        action = request.POST.get('action', '')

        if selected_orders and action:
            if action.startswith('update_status_'):
                status = action.replace('update_status_', '')
                if status in dict(Order.STATUS_CHOICES):
                    # Update status for all selected orders
                    updated_count = 0
                    for order_id in selected_orders:
                        try:
                            order = Order.objects.get(id=order_id)
                            old_status = order.status

                            # Check if transition is valid
                            valid_transitions = {
                                'PENDING': ['PREPARING', 'CANCELLED'],
                                'PREPARING': ['READY', 'CANCELLED'],
                                'READY': ['COMPLETED', 'CANCELLED'],
                                'COMPLETED': [],  # Terminal state
                                'CANCELLED': []   # Terminal state
                            }

                            if status in valid_transitions[old_status]:
                                # Update the status
                                order.status = status

                                # Set timestamps based on status
                                if status == 'PREPARING':
                                    order.preparing_at = timezone.now()
                                elif status == 'READY':
                                    order.ready_at = timezone.now()
                                elif status == 'COMPLETED':
                                    order.completed_at = timezone.now()
                                elif status == 'CANCELLED':
                                    order.cancelled_at = timezone.now()

                                order.save()
                                updated_count += 1

                                # Log activity
                                StaffActivity.objects.create(
                                    staff=request.user,
                                    action='UPDATE_ORDER',
                                    details=f"Updated order #{order.id} status to {dict(Order.STATUS_CHOICES)[status]}",
                                    ip_address=get_client_ip(request)
                                )
                        except Order.DoesNotExist:
                            continue
                        except Exception as e:
                            messages.error(request, f"Error updating order #{order_id}: {str(e)}")

                    if updated_count > 0:
                        messages.success(request, f"Successfully updated {updated_count} order(s) to {dict(Order.STATUS_CHOICES)[status]}")

            elif action == 'print_receipts':
                # Redirect to a page that will print multiple receipts
                order_ids = ','.join(selected_orders)
                return redirect(f"/cashier/print-multiple-receipts/?order_ids={order_ids}")

    # Get filters
    status_filter = request.GET.get('status', '')
    date_from = request.GET.get('date_from', timezone.now().date().isoformat())
    date_to = request.GET.get('date_to', timezone.now().date().isoformat())
    search_query = request.GET.get('q', '')
    order_type_filter = request.GET.get('order_type', '')
    payment_status_filter = request.GET.get('payment_status', '')
    payment_method_filter = request.GET.get('payment_method', '')
    min_amount = request.GET.get('min_amount', '')
    max_amount = request.GET.get('max_amount', '')
    sort_by = request.GET.get('sort', 'newest')

    # Base queryset
    orders = Order.objects.all()

    # Apply filters
    if status_filter:
        orders = orders.filter(status=status_filter)

    if date_from:
        orders = orders.filter(created_at__date__gte=date_from)

    if date_to:
        orders = orders.filter(created_at__date__lte=date_to)

    if search_query:
        orders = orders.filter(
            Q(id__icontains=search_query) |
            Q(customer_name__icontains=search_query) |
            Q(customer_phone__icontains=search_query) |
            Q(table_number__icontains=search_query)
        )

    if order_type_filter:
        orders = orders.filter(order_type=order_type_filter)

    if payment_status_filter:
        orders = orders.filter(payment_status=payment_status_filter)

    if payment_method_filter:
        orders = orders.filter(payment_method=payment_method_filter)

    if min_amount:
        try:
            orders = orders.filter(total_amount__gte=Decimal(min_amount))
        except (ValueError, TypeError, InvalidOperation):
            pass

    if max_amount:
        try:
            orders = orders.filter(total_amount__lte=Decimal(max_amount))
        except (ValueError, TypeError, InvalidOperation):
            pass

    # Apply sorting
    if sort_by == 'oldest':
        orders = orders.order_by('created_at')
    elif sort_by == 'highest':
        orders = orders.order_by('-total_amount')
    elif sort_by == 'lowest':
        orders = orders.order_by('total_amount')
    else:  # newest
        orders = orders.order_by('-created_at')

    # Log activity
    StaffActivity.objects.create(
        staff=request.user,
        action='VIEW_ORDERS',
        details=f"Viewed orders list with {orders.count()} results",
        ip_address=get_client_ip(request)
    )

    # Calculate today's completed sales for the summary widget
    today = timezone.now().date()

    # Get completed orders for today
    completed_orders = Order.objects.filter(
        status='COMPLETED',
        created_at__date=today
    )

    # Calculate completed orders sales total
    completed_orders_sales = completed_orders.aggregate(
        total=Sum('total_amount')
    )['total'] or 0

    # Add verified payments for today (excluding completed orders to avoid double counting)
    verified_payments_sales = Payment.objects.filter(
        status='COMPLETED',
        verification_date__date=today,
        order__status__in=['PENDING', 'PREPARING', 'READY']
    ).aggregate(
        total=Sum('amount')
    )['total'] or 0

    # Add reservation payments for today
    reservation_payments_sales = ReservationPayment.objects.filter(
        status='COMPLETED',
        verification_date__date=today
    ).aggregate(
        total=Sum('amount')
    )['total'] or 0

    # Total sales is the sum of all three
    today_total_sales = completed_orders_sales + verified_payments_sales + reservation_payments_sales

    # Count of completed orders today
    completed_orders_count = completed_orders.count()

    context = {
        'orders': orders,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search_query,
        'order_type_filter': order_type_filter,
        'payment_status_filter': payment_status_filter,
        'payment_method_filter': payment_method_filter,
        'min_amount': min_amount,
        'max_amount': max_amount,
        'sort_by': sort_by,
        'status_choices': Order.STATUS_CHOICES,
        'active_section': 'orders',
        # Add sales summary data
        'completed_sales_total': today_total_sales,
        'completed_orders_count': completed_orders_count,
        'completed_orders_sales': completed_orders_sales,
        'verified_payments_sales': verified_payments_sales,
        'reservation_payments_sales': reservation_payments_sales,
        'order_types': Order.ORDER_TYPE_CHOICES,
        'payment_statuses': Order.PAYMENT_STATUS_CHOICES,
        'payment_methods': Order.PAYMENT_METHOD_CHOICES
    }

    return render(request, 'cashier/orders_list.html', context)

@login_required
def print_receipt(request, order_id):
    """Generate receipt for printing. Shows partial payment if applicable."""
    order = get_object_or_404(Order, id=order_id)
    order_items = order.order_items.all()

    # Fetch reservation and payment info if linked
    reservation = getattr(order, 'reservation', None)
    payment_info = None
    if reservation:
        payment_info = ReservationPayment.objects.filter(reservation=reservation, status='COMPLETED').order_by('-payment_date').first()

    StaffActivity.objects.create(
        staff=request.user,
        action='OTHER',
        details=f"Printed receipt for order #{order.id}",
        ip_address=get_client_ip(request)
    )

    context = {
        'order': order,
        'order_items': order_items,
        'print_date': timezone.now(),
        'cashier_name': request.user.get_full_name(),
        'reservation': reservation,
        'payment_info': payment_info,
        'print_view': True,  # Add this parameter to hide status in printed receipts
    }
    return render(request, 'cashier/receipt.html', context)


@login_required
def print_multiple_receipts(request):
    """Print multiple receipts at once"""
    order_ids = request.GET.get('order_ids', '')

    if not order_ids:
        messages.error(request, 'No orders selected for printing')
        return redirect('cashier_orders_list')

    try:
        # Split the comma-separated list of order IDs
        order_id_list = [int(id) for id in order_ids.split(',')]

        # Get all the orders
        orders = Order.objects.filter(id__in=order_id_list)

        if not orders.exists():
            messages.error(request, 'No valid orders found for printing')
            return redirect('cashier_orders_list')

        # Log activity
        StaffActivity.objects.create(
            staff=request.user,
            action='OTHER',
            details=f"Printed multiple receipts for orders: {order_ids}",
            ip_address=get_client_ip(request)
        )

        context = {
            'orders': orders,
            'print_date': timezone.now(),
            'cashier_name': request.user.get_full_name(),
            'print_view': True  # Add this parameter to hide status in printed receipts
        }

        return render(request, 'cashier/multiple_receipts.html', context)

    except Exception as e:
        messages.error(request, f'Error printing receipts: {str(e)}')
        return redirect('cashier_orders_list')

@login_required
def cashier_profile_edit(request):
    """Edit cashier profile"""
    staff_profile = request.user.staff_profile

    if request.method == 'POST':
        # Get form data
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone = request.POST.get('phone', '')
        address = request.POST.get('address', '')
        emergency_contact = request.POST.get('emergency_contact', '')
        emergency_phone = request.POST.get('emergency_phone', '')
        profile_picture = request.FILES.get('profile_picture')

        # Check if email already exists for other users
        if User.objects.filter(email=email).exclude(id=request.user.id).exists():
            messages.error(request, f'Email "{email}" is already registered to another user')
            return redirect('cashier_profile_edit')

        try:
            # Update user
            request.user.email = email
            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.save()

            # Update staff profile
            staff_profile.phone = phone
            staff_profile.address = address
            staff_profile.emergency_contact = emergency_contact
            staff_profile.emergency_phone = emergency_phone

            # Handle profile picture upload
            if profile_picture:
                staff_profile.profile_picture = profile_picture

            staff_profile.save()

            # Log activity
            StaffActivity.objects.create(
                staff=request.user,
                action='OTHER',
                details=f'Updated own profile information',
                ip_address=get_client_ip(request)
            )

            messages.success(request, 'Profile updated successfully')
            return redirect('cashier_dashboard')

        except Exception as e:
            messages.error(request, f'Error updating profile: {str(e)}')

    context = {
        'staff_profile': staff_profile,
        'active_section': 'profile'
    }

    return render(request, 'cashier/profile_edit.html', context)

def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@login_required
def pending_payments(request):
    """View and manage pending GCash payments"""
    # Get filters
    status_filter = request.GET.get('status', 'PENDING')
    date_from = request.GET.get('date_from', timezone.now().date().isoformat())
    date_to = request.GET.get('date_to', timezone.now().date().isoformat())

    # Base queryset
    payments = Payment.objects.all().order_by('-payment_date')

    # Apply filters
    if status_filter and status_filter != 'all':
        payments = payments.filter(status=status_filter)

    if date_from:
        payments = payments.filter(payment_date__date__gte=date_from)

    if date_to:
        payments = payments.filter(payment_date__date__lte=date_to)

    # Log activity
    StaffActivity.objects.create(
        staff=request.user,
        action='OTHER',
        details=f"Viewed pending payments",
        ip_address=get_client_ip(request)
    )

    context = {
        'payments': payments,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'active_section': 'payments'
    }

    return render(request, 'cashier/pending_payments.html', context)


@login_required
def view_payment(request, payment_id):
    """View payment details"""
    payment = get_object_or_404(Payment, id=payment_id)

    # Log activity
    StaffActivity.objects.create(
        staff=request.user,
        action='OTHER',
        details=f"Viewed payment #{payment.id} details",
        ip_address=get_client_ip(request)
    )

    context = {
        'payment': payment,
        'active_section': 'payments'
    }

    return render(request, 'cashier/view_payment.html', context)


@login_required
def verify_payment(request, payment_id):
    """Verify a payment as completed"""
    payment = get_object_or_404(Payment, id=payment_id)

    if payment.status != 'PENDING':
        messages.error(request, f'Payment #{payment.id} is already {payment.get_status_display().lower()}')
        return redirect('view_payment', payment_id=payment.id)

    if request.method == 'POST':
        notes = request.POST.get('notes', '')

        # Update payment status
        payment.status = 'COMPLETED'
        payment.verification_date = timezone.now()
        payment.verified_by = request.user
        payment.notes = notes
        payment.save()

        # Update order status
        order = payment.order
        order.payment_status = 'PAID'

        # Only update status if it's still pending
        if order.status == 'PENDING':
            order.status = 'PREPARING'  # Move to preparing status
            order.preparing_at = timezone.now()

        order.save()

        # Log activity
        StaffActivity.objects.create(
            staff=request.user,
            action='UPDATE_PAYMENT',
            details=f"Verified payment #{payment.id} for order #{order.id}",
            ip_address=get_client_ip(request)
        )

        messages.success(request, f'Payment #{payment.id} has been verified successfully')
        return redirect('pending_payments')

    context = {
        'payment': payment,
        'active_section': 'payments'
    }

    return render(request, 'cashier/verify_payment.html', context)


@login_required
def record_payment(request, order_id):
    """Record a new payment for an order"""
    order = get_object_or_404(Order, id=order_id)

    if order.payment_status == 'PAID':
        messages.warning(request, f'Order #{order.id} is already marked as paid')
        return redirect('view_order', order_id=order.id)

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        amount = request.POST.get('amount')
        reference_number = request.POST.get('reference_number', '')
        notes = request.POST.get('notes', '')

        try:
            # Validate payment method
            if payment_method not in dict(Order.PAYMENT_METHOD_CHOICES):
                raise ValueError('Invalid payment method')

            # Validate amount
            amount_decimal = Decimal(amount)
            if amount_decimal <= 0:
                raise ValueError('Payment amount must be greater than zero')

            # Create payment record
            payment = Payment.objects.create(
                order=order,
                amount=amount_decimal,
                payment_method=payment_method,
                reference_number=reference_number,
                notes=notes,
                status='COMPLETED',  # Mark as completed immediately since cashier is recording it
                verified_by=request.user,
                verification_date=timezone.now()
            )

            # Update order payment status
            order.payment_status = 'PAID'

            # Use CASH_ON_HAND for dine-in cash payments
            if order.order_type == 'DINE_IN' and payment_method == 'CASH':
                order.payment_method = 'CASH_ON_HAND'
            else:
                order.payment_method = payment_method

            # Mark order as COMPLETED to skip the preparation tracking
            if order.status != 'COMPLETED':
                order.status = 'COMPLETED'
                order.completed_at = timezone.now()

            order.save()

            # Calculate change if cash payment
            change_amount = Decimal('0.00')
            if payment_method == 'CASH' and amount_decimal > order.total_amount:
                change_amount = amount_decimal - order.total_amount

            # Log activity
            StaffActivity.objects.create(
                staff=request.user,
                action='CREATE_PAYMENT',
                details=f"Recorded {payment.get_payment_method_display()} payment of {amount_decimal} for order #{order.id}",
                ip_address=get_client_ip(request)
            )

            messages.success(request, f'Payment of {amount_decimal} recorded successfully for Order #{order.id}')

            if change_amount > 0:
                messages.info(request, f'Change amount: ₱{change_amount:.2f}')

            return redirect('view_order', order_id=order.id)

        except ValueError as e:
            messages.error(request, f'Error recording payment: {str(e)}')
        except InvalidOperation:
            messages.error(request, 'Invalid amount format')
        except Exception as e:
            messages.error(request, f'Error recording payment: {str(e)}')

    context = {
        'order': order,
        'payment_methods': Order.PAYMENT_METHOD_CHOICES,
        'active_section': 'orders'
    }

    return render(request, 'cashier/record_payment.html', context)


@login_required
def reject_payment(request, payment_id):
    """Reject a payment"""
    payment = get_object_or_404(Payment, id=payment_id)

    if payment.status != 'PENDING':
        messages.error(request, f'Payment #{payment.id} is already {payment.get_status_display().lower()}')
        return redirect('view_payment', payment_id=payment.id)

    if request.method == 'POST':
        reason = request.POST.get('reason', '')

        # Update payment status
        payment.status = 'REJECTED'
        payment.verification_date = timezone.now()
        payment.verified_by = request.user
        payment.notes = reason
        payment.save()

        # Log activity
        StaffActivity.objects.create(
            staff=request.user,
            action='UPDATE_PAYMENT',
            details=f"Rejected payment #{payment.id} for order #{payment.order.id}",
            ip_address=get_client_ip(request)
        )

        messages.success(request, f'Payment #{payment.id} has been rejected')
        return redirect('pending_payments')

    context = {
        'payment': payment,
        'active_section': 'payments'
    }

    return render(request, 'cashier/reject_payment.html', context)


@login_required
def cancel_order(request, order_id):
    """Cancel an order and handle all related processes"""
    order = get_object_or_404(Order, id=order_id)

    # Check if order can be cancelled (not already completed or cancelled)
    if order.status in ['COMPLETED', 'CANCELLED']:
        messages.error(request, f'Order #{order.id} cannot be cancelled because it is already {order.get_status_display().lower()}')
        return redirect('view_order', order_id=order.id)

    if request.method == 'POST':
        cancellation_reason = request.POST.get('cancellation_reason', 'OTHER')
        cancellation_notes = request.POST.get('cancellation_notes', '')

        # Begin transaction to ensure all changes are atomic
        with transaction.atomic():
            # 1. Update order status
            order.status = 'CANCELLED'
            order.cancelled_at = timezone.now()
            order.cancellation_reason = cancellation_reason
            order.cancellation_notes = cancellation_notes
            order.cancelled_by = request.user
            order.save()

            # 2. Handle payment if already paid
            if order.payment_status == 'PAID':
                # Create refund record
                refund = Refund.objects.create(
                    order=order,
                    amount=order.grand_total,
                    reason=f"Order cancelled: {dict(Order.CANCELLATION_REASON_CHOICES).get(cancellation_reason, 'Other reason')}",
                    status='PENDING',
                    initiated_by=request.user,
                    notes=cancellation_notes
                )

                # Update payment status
                order.payment_status = 'REFUNDED'
                order.save(update_fields=['payment_status'])

                # Update any existing payments
                for payment in Payment.objects.filter(order=order, status='COMPLETED'):
                    payment.status = 'REFUNDED'
                    payment.save()

                messages.info(request, f'A refund of ₱{order.grand_total} has been initiated for this order')

            # 3. Free up table reservation (for dine-in)
            if order.order_type == 'DINE_IN' and order.table_number:
                messages.info(request, f'Table {order.table_number} has been released')

            # 4. Log activity
            StaffActivity.objects.create(
                staff=request.user,
                action='CANCEL_ORDER',
                details=f"Cancelled order #{order.id}. Reason: {dict(Order.CANCELLATION_REASON_CHOICES).get(cancellation_reason, 'Other reason')}",
                ip_address=get_client_ip(request)
            )

        messages.success(request, f'Order #{order.id} has been cancelled successfully')
        return redirect('cashier_orders_list')

    context = {
        'order': order,
        'cancellation_reasons': Order.CANCELLATION_REASON_CHOICES,
        'active_section': 'orders'
    }

    return render(request, 'cashier/cancel_order.html', context)


@login_required
def reservations_list(request):
    """View for cashiers to see and process confirmed reservations"""
    # Get date from query parameters or use today's date
    date_str = request.GET.get('date')
    if date_str:
        try:
            # Parse the date from the query parameter
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            # If invalid date format, use today's date
            selected_date = timezone.now().date()
    else:
        # Default to today's date
        selected_date = timezone.now().date()

    # Get all reservations
    reservations = Reservation.objects.all().order_by('time')

    # Get the date filter mode
    date_filter_mode = request.GET.get('date_filter', 'today_and_future')

    # Apply date filter based on mode
    if date_filter_mode == 'specific_date':
        # Filter by the specific selected date
        reservations = reservations.filter(date=selected_date)
    elif date_filter_mode == 'today_and_future':
        # Show today and future reservations (default)
        reservations = reservations.filter(date__gte=timezone.now().date())
    elif date_filter_mode == 'all':
        # Show all reservations regardless of date
        pass
    else:
        # Default to today and future if invalid mode
        reservations = reservations.filter(date__gte=timezone.now().date())

    # Filter by status if requested
    status_filter = request.GET.get('status', 'all')
    if status_filter == 'unprocessed':
        # Show confirmed reservations that need preparation
        reservations = reservations.filter(status='CONFIRMED')
    elif status_filter == 'confirmed':
        # Show all confirmed reservations
        reservations = reservations.filter(status='CONFIRMED')
    elif status_filter == 'completed':
        # Show completed reservations
        reservations = reservations.filter(status='COMPLETED')
    elif status_filter == 'pending':
        # Show pending reservations
        reservations = reservations.filter(status='PENDING')
    # 'all' shows all reservations for the selected date

    context = {
        'reservations': reservations,
        'status_filter': status_filter,
        'today': selected_date,
        'active_section': 'reservations_list'
    }

    return render(request, 'cashier/reservations_list.html', context)

@login_required
def process_reservation(request, reservation_id):
    """Process a confirmed reservation and create an order. Handles partial payment and enables receipt printing."""
    reservation = get_object_or_404(Reservation, id=reservation_id, status='CONFIRMED')

    if reservation.is_processed:
        messages.warning(request, f'Reservation #{reservation_id} has already been processed.')
        # Redirect to order receipt if already processed
        order = Order.objects.filter(reservation=reservation).first()
        if order:
            return redirect('print_receipt', order_id=order.id)
        return redirect('cashier_reservations_list')

    if reservation.payment_status not in ['PAID', 'PARTIALLY_PAID']:
        messages.error(request, f'Reservation #{reservation_id} cannot be processed until payment is completed or at least partially paid.')
        return redirect('cashier_reservations_list')

    # Get pre-ordered menu items if any
    reservation_items = reservation.reservation_items.all()
    has_menu_items = reservation_items.exists()

    if request.method == 'POST':
        with transaction.atomic():
            # Get special requests without menu items data
            special_requests = reservation.special_requests or ''
            clean_special_requests = special_requests

            # If using old format with menu items in special requests, clean it up
            if '[MENU_ITEMS_DATA:' in special_requests:
                try:
                    start_index = special_requests.find('[MENU_ITEMS_DATA:')
                    if start_index >= 0:
                        end_index = special_requests.find(']', start_index)
                        if end_index >= 0:
                            # Clean the special requests by removing the menu items data
                            clean_special_requests = special_requests[:start_index].strip()
                except Exception as e:
                    # Log the error but continue processing
                    print(f"Error cleaning menu items data: {str(e)}")

            # Update reservation status
            reservation.is_processed = True
            reservation.processed_by = request.user
            reservation.processed_at = timezone.now()
            reservation.status = 'COMPLETED'
            reservation.save(update_fields=['is_processed', 'processed_by', 'processed_at', 'status'])

            # Determine payment method/status
            payment_method = 'CASH'
            payment_status = 'PENDING'
            order_status = 'PENDING'
            latest_payment = None
            completed_payments = ReservationPayment.objects.filter(
                reservation=reservation,
                status='COMPLETED'
            ).order_by('-payment_date')
            if completed_payments.exists():
                latest_payment = completed_payments.first()
                payment_method = 'GCASH'
                if latest_payment.payment_type == 'FULL':
                    payment_status = 'PAID'
                    order_status = 'COMPLETED'
                else:
                    payment_status = 'PARTIALLY_PAID'
                    order_status = 'COMPLETED'  # Allow completion for partial payment
            else:
                pending_payments = ReservationPayment.objects.filter(
                    reservation=reservation,
                    status='PENDING'
                ).order_by('-payment_date')
                if pending_payments.exists():
                    latest_payment = pending_payments.first()
                    payment_method = 'GCASH'

            # Create order and link to reservation
            order = Order.objects.create(
                user=reservation.user,
                status=order_status,
                order_type='DINE_IN',
                payment_method=payment_method,
                payment_status=payment_status,
                table_number=reservation.table_number,
                number_of_guests=reservation.party_size,
                special_instructions=clean_special_requests,
                created_by=request.user,
                total_amount=reservation.total_amount
            )

            # Add pre-ordered menu items to the order if any
            if has_menu_items:
                for item in reservation_items:
                    OrderItem.objects.create(
                        order=order,
                        menu_item=item.menu_item,
                        quantity=item.quantity,
                        price=item.price,
                        special_instructions=item.special_instructions
                    )

                    # Mark reservation item as prepared
                    item.is_prepared = True
                    item.save(update_fields=['is_prepared'])

            # Log activity
            StaffActivity.objects.create(
                staff=request.user,
                action='PROCESS_RESERVATION',
                details=f"Processed reservation #{reservation.id} (Order #{order.id})",
                ip_address=get_client_ip(request)
            )

            # Redirect to print receipt after processing
            return redirect('print_receipt', order_id=order.id)

    # GET: Show processing page
    return render(request, 'cashier/process_reservation.html', {'reservation': reservation})


@login_required
def pending_reservation_payments(request):
    """View for cashiers to see and verify pending reservation payments"""
    # Get pending reservation payments
    pending_payments = ReservationPayment.objects.filter(status='PENDING').order_by('-payment_date')

    context = {
        'pending_payments': pending_payments,
        'active_section': 'pending_reservation_payments'
    }

    return render(request, 'cashier/pending_reservation_payments.html', context)


@login_required
def view_reservation_payment(request, payment_id):
    """View and verify a reservation payment"""
    payment = get_object_or_404(ReservationPayment, id=payment_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        reservation = payment.reservation

        if action == 'verify':
            # Check if reservation is in a valid state for verification
            if reservation.status != 'CONFIRMED':
                messages.error(request, f'Reservation must be CONFIRMED before payment can be verified. Current status: {reservation.status}')
                return redirect('view_reservation_payment', payment_id=payment_id)

            # Mark payment as completed
            payment.status = 'COMPLETED'
            payment.verified_by = request.user
            payment.verification_date = timezone.now()
            payment.save()

            # Clean up any other pending payments for this reservation
            other_pending_payments = ReservationPayment.objects.filter(
                reservation=payment.reservation,
                status='PENDING'
            ).exclude(id=payment.id)

            if other_pending_payments.exists():
                for old_payment in other_pending_payments:
                    old_payment.delete()

            # Update the reservation status to CONFIRMED
            reservation.status = 'CONFIRMED'

            # Update payment status based on payment type
            if payment.payment_type == 'FULL':
                reservation.payment_status = 'PAID'
            else:
                # Calculate total paid amount
                total_paid = ReservationPayment.objects.filter(
                    reservation=reservation,
                    status='COMPLETED'
                ).aggregate(total=Sum('amount'))['total'] or 0

                # If total paid equals or exceeds the total amount, mark as PAID
                if total_paid >= reservation.total_amount:
                    reservation.payment_status = 'PAID'
                else:
                    reservation.payment_status = 'PARTIALLY_PAID'

            # Save the reservation with updated status
            reservation.save(update_fields=['status', 'payment_status'])

            # Check if there are any existing orders for this reservation
            orders = Order.objects.filter(
                table_number=reservation.table_number,
                number_of_guests=reservation.party_size,
                user=reservation.user
            )

            if orders.exists():
                order = orders.first()
                order.payment_method = 'GCASH'
                if payment.payment_type == 'FULL':
                    order.payment_status = 'PAID'
                    order.status = 'COMPLETED'
                    Payment.objects.create(
                        order=order,
                        amount=payment.amount,
                        payment_method='GCASH',
                        status='COMPLETED',
                        reference_number=payment.reference_number,
                        payment_proof=payment.payment_proof,
                        verified_by=request.user,
                        verification_date=timezone.now(),
                        notes=f'Payment from reservation #{reservation.id}'
                    )
                else:
                    order.payment_status = 'PARTIALLY_PAID'
                    Payment.objects.create(
                        order=order,
                        amount=payment.amount,
                        payment_method='GCASH',
                        status='COMPLETED',
                        reference_number=payment.reference_number,
                        payment_proof=payment.payment_proof,
                        verified_by=request.user,
                        verification_date=timezone.now(),
                        notes=f'Partial payment (deposit) from reservation #{reservation.id}'
                    )
                order.save(update_fields=['payment_method', 'payment_status', 'status'])
                messages.success(request, f'Payment verified and order #{order.id} has been updated.')

            StaffActivity.objects.create(
                staff=request.user,
                action='VERIFY_RESERVATION_PAYMENT',
                details=f"Verified payment of ₱{payment.amount} for Reservation #{reservation.id}"
            )

            # Create the URL with appropriate parameters
            reservations_url = reverse("cashier_reservations_list") + "?status=unprocessed&date_filter=today_and_future"

            # Use the messages.success with the safe filter in the template
            messages.success(request, f'Payment for Reservation #{reservation.id} has been verified successfully!')

            # Add a second message with the action button that will be rendered with the safe filter
            messages.info(request, f'<a href="{reservations_url}" class="btn-primary px-4 py-2 rounded-lg inline-flex items-center"><i class="fas fa-clipboard-list mr-2"></i> Go to Reservations</a>')
            return redirect('pending_reservation_payments')
        elif action == 'reject':
            return redirect('reject_reservation_payment', payment_id=payment_id)

    context = {
        'payment': payment,
        'active_section': 'pending_reservation_payments'
    }

    return render(request, 'cashier/view_reservation_payment.html', context)


@login_required
def reject_reservation_payment(request, payment_id):
    """Reject a reservation payment"""
    payment = get_object_or_404(ReservationPayment, id=payment_id)

    if request.method == 'POST':
        reason = request.POST.get('reason', 'Payment rejected')

        # Mark payment as failed
        payment.status = 'FAILED'
        payment.notes = reason
        payment.verified_by = request.user
        payment.verification_date = timezone.now()
        payment.save()

        # Update the reservation status if needed
        reservation = payment.reservation
        if reservation.status == 'PENDING':
            # Keep it as pending if it was pending before
            pass
        elif reservation.payment_status == 'UNPAID':
            # If no other payments exist, ensure reservation stays in pending state
            other_completed_payments = ReservationPayment.objects.filter(
                reservation=reservation,
                status='COMPLETED'
            ).exists()

            if not other_completed_payments:
                # No valid payments, so keep reservation as pending
                reservation.status = 'PENDING'
                reservation.payment_status = 'UNPAID'
                reservation.save(update_fields=['status', 'payment_status'])

        # Log the activity
        StaffActivity.objects.create(
            staff=request.user,
            action='REJECT_RESERVATION_PAYMENT',
            details=f"Rejected payment for Reservation #{payment.reservation.id}. Reason: {reason}"
        )

        messages.success(request, f'Payment for Reservation #{payment.reservation.id} has been rejected.')
        return redirect('pending_reservation_payments')

    # If not a POST request, show the rejection form
    context = {
        'payment': payment,
        'active_section': 'pending_reservation_payments'
    }
    return render(request, 'cashier/reject_reservation_payment.html', context)

@login_required
def settle_remaining_balance(request, order_id):
    """Settle the remaining balance for an order that was partially paid via reservation deposit."""
    order = get_object_or_404(Order, id=order_id)
    reservation = getattr(order, 'reservation', None)

    if not reservation or reservation.payment_status != 'PARTIALLY_PAID':
        messages.error(request, 'This order does not have a partially paid reservation.')
        return redirect('print_receipt', order_id=order.id)

    if request.method == 'POST':
        # Assume cashier enters the remaining payment amount
        remaining_due = order.total_amount
        payment_info = ReservationPayment.objects.filter(reservation=reservation, status='COMPLETED', payment_type='DEPOSIT').order_by('-payment_date').first()
        if payment_info:
            remaining_due -= payment_info.amount
        try:
            paid_amount = Decimal(request.POST.get('paid_amount', '0'))
        except Exception:
            paid_amount = Decimal('0.00')
        if paid_amount < remaining_due:
            messages.error(request, f'Amount entered (₱{paid_amount}) is less than the remaining balance (₱{remaining_due}).')
            return redirect('settle_remaining_balance', order_id=order.id)
        # Mark reservation and order as fully paid
        reservation.payment_status = 'PAID'
        reservation.save(update_fields=['payment_status'])
        order.payment_status = 'PAID'
        order.status = 'COMPLETED'
        order.save(update_fields=['payment_status', 'status'])
        # Log payment (could create a Payment object here as well)
        StaffActivity.objects.create(
            staff=request.user,
            action='SETTLE_BALANCE',
            details=f'Settled remaining balance for order #{order.id}',
            ip_address=get_client_ip(request)
        )
        messages.success(request, f'Order #{order.id} is now fully paid and completed.')
        return redirect('print_receipt', order_id=order.id)

    # GET: Show settle balance form
    payment_info = ReservationPayment.objects.filter(reservation=reservation, status='COMPLETED', payment_type='DEPOSIT').order_by('-payment_date').first()
    remaining_due = order.total_amount
    if payment_info:
        remaining_due -= payment_info.amount
    return render(request, 'cashier/settle_balance.html', {
        'order': order,
        'reservation': reservation,
        'remaining_due': remaining_due,
        'payment_info': payment_info,
    })

@login_required
def cashier_mark_prepared(request, reservation_id):
    """Mark a reservation as prepared (for kitchen/cashier workflow)"""
    from ecommerce.models import Reservation, StaffActivity
    reservation = get_object_or_404(Reservation, id=reservation_id)
    if reservation.status == 'CONFIRMED':
        reservation.status = 'COMPLETED'  # Or 'PREPARED' if you have such a status
        reservation.save(update_fields=['status'])

        # Log the activity
        StaffActivity.objects.create(
            staff=request.user,
            action='MARK_RESERVATION_PREPARED',
            details=f"Marked Reservation #{reservation.id} as prepared for {reservation.name}, party of {reservation.party_size}"
        )

        messages.success(request, f'Reservation #{reservation.id} for {reservation.name} has been marked as prepared and is ready to be served.')
    else:
        messages.warning(request, f'Reservation #{reservation.id} cannot be marked as prepared. It must be in CONFIRMED status.')
    return redirect('cashier_reservations_list')


@login_required
def unmark_table(request):
    """Unmark a table as occupied by completing or cancelling the associated order"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

    table_number = request.POST.get('table_number')
    action = request.POST.get('action', 'complete')  # Default action is to complete the order

    if not table_number:
        return JsonResponse({'status': 'error', 'message': 'Table number is required'})

    # Find the active order for this table
    try:
        order = Order.objects.get(
            table_number=table_number,
            order_type='DINE_IN',
            status__in=['PENDING', 'PREPARING', 'READY']
        )

        # Update the order status based on the action
        if action == 'complete':
            order.status = 'COMPLETED'
            order.completed_at = timezone.now()
            status_message = 'completed'
        else:  # cancel
            order.status = 'CANCELLED'
            order.cancelled_at = timezone.now()
            order.cancellation_reason = 'CUSTOMER_LEFT'
            order.cancellation_notes = 'Customer left the table, marked as available by cashier'
            order.cancelled_by = request.user
            status_message = 'cancelled'

        order.save()

        # Log activity
        StaffActivity.objects.create(
            staff=request.user,
            action='UPDATE_ORDER',
            details=f"Order #{order.id} {status_message} to free up table {table_number}",
            ip_address=get_client_ip(request)
        )

        return JsonResponse({
            'status': 'success',
            'message': f'Table {table_number} is now available. Order #{order.id} has been {status_message}.',
            'order_id': order.id
        })

    except Order.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': f'No active order found for table {table_number}'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error unmarking table: {str(e)}'
        })


@login_required
def preparation_tracker(request):
    """View for tracking preparation progress of reservations and orders"""
    from ecommerce.models import Reservation, Order
    from django.db.models import Count

    # Get today's date
    today = timezone.now().date()

    # Get all reservations for today and future dates
    reservations = Reservation.objects.filter(
        date__gte=today,
        status__in=['CONFIRMED', 'COMPLETED']
    ).order_by('date', 'time')

    # Get all orders that are in progress
    orders = Order.objects.filter(
        status__in=['PENDING', 'PROCESSING', 'READY', 'COMPLETED'],
        created_at__date=today
    ).order_by('-created_at')

    # Calculate statistics
    total_preparations = reservations.count() + orders.count()
    in_progress_count = reservations.filter(status='CONFIRMED').count() + orders.filter(status='PROCESSING').count()
    ready_count = orders.filter(status='READY').count()
    completed_today = reservations.filter(status='COMPLETED').count() + orders.filter(status='COMPLETED').count()

    context = {
        'reservations': reservations,
        'orders': orders,
        'total_preparations': total_preparations,
        'in_progress_count': in_progress_count,
        'ready_count': ready_count,
        'completed_today': completed_today,
        'active_section': 'preparation_tracker'
    }

    return render(request, 'cashier/preparation_tracker.html', context)
