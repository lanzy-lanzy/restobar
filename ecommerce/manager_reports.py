import datetime
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Count, F, Avg, Q
from django.contrib.auth.models import User
from django.db.models.functions import TruncDate, TruncHour, ExtractHour

from .models import Order, OrderItem, Category, StaffProfile, Payment

@login_required
def comprehensive_sales_report(request):
    """Comprehensive sales report with multiple views and filtering options"""
    # Get date range
    today = timezone.now().date()
    date_from = request.GET.get('date_from', (today - datetime.timedelta(days=30)).isoformat())
    date_to = request.GET.get('date_to', today.isoformat())
    category_filter = request.GET.get('category', '')
    cashier_filter = request.GET.get('cashier', '')
    payment_method_filter = request.GET.get('payment_method', '')

    # Reset filters if requested
    if request.GET.get('reset'):
        date_from = (today - datetime.timedelta(days=30)).isoformat()
        date_to = today.isoformat()
        category_filter = ''
        cashier_filter = ''
        payment_method_filter = ''

    # Base query for completed orders
    orders_query = Order.objects.filter(
        status='COMPLETED',
        created_at__date__gte=date_from,
        created_at__date__lte=date_to
    )

    # Apply filters
    if cashier_filter:
        orders_query = orders_query.filter(created_by_id=cashier_filter)

    if payment_method_filter:
        # Filter by the order's own payment_method field
        orders_query = orders_query.filter(payment_method=payment_method_filter)

    # Get order items
    items_query = OrderItem.objects.filter(order__in=orders_query)

    if category_filter:
        items_query = items_query.filter(menu_item__category_id=category_filter)

    # Calculate summary metrics
    total_orders = orders_query.count()
    total_revenue = orders_query.aggregate(total=Sum('total_amount'))['total'] or 0

    # Convert items_query to a list to avoid multiple evaluations
    items_list = list(items_query)

    # Calculate total quantity manually
    total_quantity = sum(item.quantity for item in items_list)

    avg_order_value = total_revenue / total_orders if total_orders > 0 else 0

    # Get sales by item
    item_sales = []

    # Group items by menu item
    item_groups = {}
    for item in items_list:
        item_name = item.menu_item.name
        category_name = item.menu_item.category.name if item.menu_item.category else 'Uncategorized'

        if item_name not in item_groups:
            item_groups[item_name] = {
                'menu_item__name': item_name,
                'menu_item__category__name': category_name,
                'quantity': 0,
                'revenue': 0,
                'price_sum': 0,
                'price_count': 0,
                'orders': set()
            }

        item_groups[item_name]['quantity'] += item.quantity
        item_groups[item_name]['revenue'] += item.quantity * item.price
        item_groups[item_name]['price_sum'] += item.price
        item_groups[item_name]['price_count'] += 1
        item_groups[item_name]['orders'].add(item.order_id)

    # Convert to list format
    for item_data in item_groups.values():
        avg_price = item_data['price_sum'] / item_data['price_count'] if item_data['price_count'] > 0 else 0
        item_sales.append({
            'menu_item__name': item_data['menu_item__name'],
            'menu_item__category__name': item_data['menu_item__category__name'],
            'quantity': item_data['quantity'],
            'revenue': item_data['revenue'],
            'avg_price': avg_price,
            'orders': len(item_data['orders'])
        })

    # Sort by quantity
    item_sales = sorted(item_sales, key=lambda x: x['quantity'], reverse=True)

    # Calculate percentage of total for each item
    for item in item_sales:
        item['percentage'] = (item['revenue'] / total_revenue * 100) if total_revenue > 0 else 0

    # Get sales by category
    category_sales = []

    # Group items by category
    category_groups = {}
    for item in items_list:
        category_name = item.menu_item.category.name if item.menu_item.category else 'Uncategorized'
        if category_name not in category_groups:
            category_groups[category_name] = {
                'quantity': 0,
                'revenue': 0,
                'orders': set()
            }
        category_groups[category_name]['quantity'] += item.quantity
        category_groups[category_name]['revenue'] += item.quantity * item.price
        category_groups[category_name]['orders'].add(item.order_id)

    # Convert to list format
    for category_name, data in category_groups.items():
        category_sales.append({
            'menu_item__category__name': category_name,
            'quantity': data['quantity'],
            'revenue': data['revenue'],
            'orders': len(data['orders'])
        })

    # Sort by revenue
    category_sales = sorted(category_sales, key=lambda x: x['revenue'], reverse=True)

    # Calculate percentage of total for each category
    for category in category_sales:
        category['percentage'] = (category['revenue'] / total_revenue * 100) if total_revenue > 0 else 0
        category['avg_price'] = category['revenue'] / category['quantity'] if category['quantity'] > 0 else 0

    # Get sales by cashier
    cashier_sales = orders_query.values(
        'created_by__username',
        'created_by__first_name',
        'created_by__last_name',
        'created_by__staff_profile__employee_id'
    ).annotate(
        order_count=Count('id'),
        total_sales=Sum('total_amount'),
        avg_order_value=Avg('total_amount')
    ).order_by('-total_sales')

    # Calculate percentage of total for each cashier
    for cashier in cashier_sales:
        cashier['percentage'] = (cashier['total_sales'] / total_revenue * 100) if total_revenue > 0 else 0
        cashier['full_name'] = f"{cashier['created_by__first_name']} {cashier['created_by__last_name']}".strip() or cashier['created_by__username']

    # Get sales by payment method
    payment_method_sales = orders_query.values(
        'payment_method'
    ).annotate(
        order_count=Count('id'),
        total_sales=Sum('total_amount')
    ).order_by('-total_sales')

    # Get sales over time (daily)
    daily_sales = orders_query.annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        total=Sum('total_amount'),
        count=Count('id')
    ).order_by('date')

    # Get sales by hour
    hourly_sales = orders_query.annotate(
        hour=ExtractHour('created_at')
    ).values('hour').annotate(
        total=Sum('total_amount'),
        count=Count('id')
    ).order_by('hour')

    # Prepare data for charts
    time_labels = [sale['date'].strftime('%Y-%m-%d') for sale in daily_sales]
    time_values = [float(sale['total']) for sale in daily_sales]

    daily_labels = time_labels
    daily_values = time_values

    hourly_labels = [f"{hour['hour']}:00" for hour in hourly_sales]
    hourly_values = [float(hour['total']) for hour in hourly_sales]

    top_items = sorted(item_sales, key=lambda x: x['revenue'], reverse=True)[:10]
    top_items_names = [item['menu_item__name'] for item in top_items]
    top_items_revenue = [float(item['revenue']) for item in top_items]

    category_names = [cat['menu_item__category__name'] or 'Uncategorized' for cat in category_sales]
    category_values = [float(cat['revenue']) for cat in category_sales]

    cashier_names = [cashier['full_name'] for cashier in cashier_sales]
    cashier_values = [float(cashier['total_sales']) for cashier in cashier_sales]

    payment_method_names = [payment['payment_method'] for payment in payment_method_sales]
    payment_method_values = [float(payment['total_sales']) for payment in payment_method_sales]

    # Get filter options
    categories = Category.objects.all()
    cashiers = User.objects.filter(
        staff_profile__isnull=False,
        staff_profile__is_active_staff=True
    ).select_related('staff_profile')

    payment_methods = [
        ('CASH', 'Cash'),
        ('CREDIT_CARD', 'Credit Card'),
        ('DEBIT_CARD', 'Debit Card'),
        ('GCASH', 'GCash'),
        ('PAYMAYA', 'PayMaya'),
        ('BANK_TRANSFER', 'Bank Transfer')
    ]

    # Define table headers
    item_headers = [
        {'name': 'Item', 'key': 'menu_item__name'},
        {'name': 'Category', 'key': 'menu_item__category__name'},
        {'name': 'Quantity', 'key': 'quantity'},
        {'name': 'Revenue', 'key': 'revenue', 'type': 'currency'},
        {'name': 'Avg. Price', 'key': 'avg_price', 'type': 'currency'},
        {'name': 'Orders', 'key': 'orders'},
        {'name': '% of Total', 'key': 'percentage', 'type': 'progress'}
    ]

    category_headers = [
        {'name': 'Category', 'key': 'menu_item__category__name'},
        {'name': 'Quantity', 'key': 'quantity'},
        {'name': 'Revenue', 'key': 'revenue', 'type': 'currency'},
        {'name': 'Avg. Price', 'key': 'avg_price', 'type': 'currency'},
        {'name': 'Orders', 'key': 'orders'},
        {'name': '% of Total', 'key': 'percentage', 'type': 'progress'}
    ]

    cashier_headers = [
        {'name': 'Cashier', 'key': 'full_name'},
        {'name': 'Employee ID', 'key': 'created_by__staff_profile__employee_id'},
        {'name': 'Orders', 'key': 'order_count'},
        {'name': 'Revenue', 'key': 'total_sales', 'type': 'currency'},
        {'name': 'Avg. Order Value', 'key': 'avg_order_value', 'type': 'currency'},
        {'name': '% of Total', 'key': 'percentage', 'type': 'progress'}
    ]

    context = {
        'date_from': date_from,
        'date_to': date_to,
        'category_filter': category_filter,
        'cashier_filter': cashier_filter,
        'payment_method_filter': payment_method_filter,
        'categories': categories,
        'cashiers': cashiers,
        'payment_methods': payment_methods,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'total_quantity': total_quantity,
        'avg_order_value': avg_order_value,
        'item_sales': list(item_sales),
        'category_sales': list(category_sales),
        'cashier_sales': list(cashier_sales),
        'time_labels': time_labels,
        'time_values': time_values,
        'daily_labels': daily_labels,
        'daily_values': daily_values,
        'hourly_labels': hourly_labels,
        'hourly_values': hourly_values,
        'top_items_names': top_items_names,
        'top_items_revenue': top_items_revenue,
        'category_names': category_names,
        'category_values': category_values,
        'cashier_names': cashier_names,
        'cashier_values': cashier_values,
        'payment_method_names': payment_method_names,
        'payment_method_values': payment_method_values,
        'item_headers': item_headers,
        'category_headers': category_headers,
        'cashier_headers': cashier_headers,
        'active_section': 'comprehensive_sales_report'
    }

    return render(request, 'manager/comprehensive_sales_report.html', context)

@login_required
def cashier_performance_report(request):
    """Detailed report on cashier performance"""
    # Get date range
    today = timezone.now().date()
    date_from = request.GET.get('date_from', (today - datetime.timedelta(days=30)).isoformat())
    date_to = request.GET.get('date_to', today.isoformat())
    cashier_filter = request.GET.get('cashier', '')

    # Reset filters if requested
    if request.GET.get('reset'):
        date_from = (today - datetime.timedelta(days=30)).isoformat()
        date_to = today.isoformat()
        cashier_filter = ''

    # Get all cashiers
    cashiers = User.objects.filter(
        staff_profile__isnull=False,
        staff_profile__role='CASHIER',
        staff_profile__is_active_staff=True
    ).select_related('staff_profile')

    # Get completed orders within date range
    orders_query = Order.objects.filter(
        status='COMPLETED',
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
        created_by__isnull=False
    )

    # Calculate summary metrics
    total_orders = orders_query.count()
    total_revenue = orders_query.aggregate(total=Sum('total_amount'))['total'] or 0
    active_cashiers = orders_query.values('created_by').distinct().count()
    avg_order_value = total_revenue / total_orders if total_orders > 0 else 0

    # Get sales by cashier
    cashier_sales = orders_query.values(
        'created_by__username',
        'created_by__first_name',
        'created_by__last_name',
        'created_by__staff_profile__employee_id',
        'created_by_id'
    ).annotate(
        order_count=Count('id'),
        total_sales=Sum('total_amount'),
        avg_order_value=Avg('total_amount')
    ).order_by('-total_sales')

    # Calculate percentage of total for each cashier
    for cashier in cashier_sales:
        cashier['percentage'] = (cashier['total_sales'] / total_revenue * 100) if total_revenue > 0 else 0
        cashier['full_name'] = f"{cashier['created_by__first_name']} {cashier['created_by__last_name']}".strip() or cashier['created_by__username']

    # Get sales over time (daily)
    daily_sales = orders_query.annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        total=Sum('total_amount'),
        count=Count('id')
    ).order_by('date')

    # Prepare data for charts
    daily_labels = [sale['date'].strftime('%Y-%m-%d') for sale in daily_sales]
    daily_values = [float(sale['total']) for sale in daily_sales]

    cashier_names = [cashier['full_name'] for cashier in cashier_sales]
    cashier_revenues = [float(cashier['total_sales']) for cashier in cashier_sales]
    cashier_orders_count = [int(cashier['order_count']) for cashier in cashier_sales]

    # Individual cashier details if selected
    selected_cashier = None
    cashier_revenue = 0
    cashier_orders = 0
    cashier_avg_order = 0
    cashier_daily_labels = []
    cashier_daily_values = []
    cashier_recent_orders = []

    if cashier_filter:
        try:
            selected_cashier = User.objects.get(id=cashier_filter)

            # Get cashier's orders
            cashier_orders_query = orders_query.filter(created_by=selected_cashier)

            # Calculate cashier metrics
            cashier_revenue = cashier_orders_query.aggregate(total=Sum('total_amount'))['total'] or 0
            cashier_orders = cashier_orders_query.count()
            cashier_avg_order = cashier_revenue / cashier_orders if cashier_orders > 0 else 0

            # Get cashier's daily sales
            cashier_daily_sales = cashier_orders_query.annotate(
                date=TruncDate('created_at')
            ).values('date').annotate(
                total=Sum('total_amount'),
                count=Count('id')
            ).order_by('date')

            cashier_daily_labels = [sale['date'].strftime('%Y-%m-%d') for sale in cashier_daily_sales]
            cashier_daily_values = [float(sale['total']) for sale in cashier_daily_sales]

            # Get cashier's recent orders
            cashier_recent_orders = cashier_orders_query.order_by('-created_at')[:20].values(
                'id', 'created_at', 'total_amount', 'order_type', 'customer_name'
            )

            for order in cashier_recent_orders:
                order['created_at_formatted'] = order['created_at'].strftime('%Y-%m-%d %H:%M')
                order['order_type_display'] = order['order_type'].replace('_', ' ').title()

        except User.DoesNotExist:
            pass

    # Define table headers
    cashier_headers = [
        {'name': 'Cashier', 'key': 'full_name'},
        {'name': 'Employee ID', 'key': 'created_by__staff_profile__employee_id'},
        {'name': 'Orders', 'key': 'order_count'},
        {'name': 'Revenue', 'key': 'total_sales', 'type': 'currency'},
        {'name': 'Avg. Order Value', 'key': 'avg_order_value', 'type': 'currency'},
        {'name': '% of Total', 'key': 'percentage', 'type': 'progress'}
    ]

    order_headers = [
        {'name': 'Order #', 'key': 'id'},
        {'name': 'Date & Time', 'key': 'created_at_formatted'},
        {'name': 'Customer', 'key': 'customer_name'},
        {'name': 'Type', 'key': 'order_type_display'},
        {'name': 'Amount', 'key': 'total_amount', 'type': 'currency'}
    ]

    context = {
        'date_from': date_from,
        'date_to': date_to,
        'cashier_filter': cashier_filter,
        'cashiers': cashiers,
        'selected_cashier': selected_cashier,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'active_cashiers': active_cashiers,
        'avg_order_value': avg_order_value,
        'cashier_sales': list(cashier_sales),
        'daily_labels': daily_labels,
        'daily_values': daily_values,
        'cashier_names': cashier_names,
        'cashier_revenues': cashier_revenues,
        'cashier_orders_count': cashier_orders_count,
        'cashier_revenue': cashier_revenue,
        'cashier_orders': cashier_orders,
        'cashier_avg_order': cashier_avg_order,
        'cashier_daily_labels': cashier_daily_labels,
        'cashier_daily_values': cashier_daily_values,
        'cashier_recent_orders': list(cashier_recent_orders),
        'cashier_headers': cashier_headers,
        'order_headers': order_headers,
        'active_section': 'cashier_performance_report'
    }

    return render(request, 'manager/cashier_performance_report.html', context)
