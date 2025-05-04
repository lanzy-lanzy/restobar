import datetime
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.db.models import Sum, Count, F, Q, Avg
from django.db.models.functions import TruncDate, TruncHour, TruncMonth, TruncWeek
from django.utils import timezone
from django.contrib import messages

from .models import Order, OrderItem, Category, MenuItem, Payment
from .utils.reportlab_utils import generate_sales_report_pdf, generate_simple_sales_report_pdf, generate_sales_report_data


@login_required
def cashier_view_sales_report(request):
    """Comprehensive sales report for cashiers with filtering and export options"""
    # Check if user has cashier role
    if not hasattr(request.user, 'staff_profile') or request.user.staff_profile.role != 'CASHIER':
        messages.error(request, "You don't have permission to access this page.")
        return redirect('login')

    # Get date range
    today = timezone.now().date()
    date_from_str = request.GET.get('date_from', (today - datetime.timedelta(days=7)).isoformat())
    date_to_str = request.GET.get('date_to', today.isoformat())

    try:
        date_from = datetime.datetime.fromisoformat(date_from_str).date()
        date_to = datetime.datetime.fromisoformat(date_to_str).date()
    except ValueError:
        # Handle invalid date format
        date_from = today - datetime.timedelta(days=7)
        date_to = today
        messages.error(request, "Invalid date format. Using default date range.")

    category_id = request.GET.get('category', '')
    payment_method = request.GET.get('payment_method', '')
    report_type = request.GET.get('report_type', 'daily')  # daily, weekly, monthly

    # Check if export to PDF is requested
    export_pdf = request.GET.get('export_pdf', False)

    # Base query for completed orders
    orders = Order.objects.filter(
        status='COMPLETED',
        created_at__date__gte=date_from,
        created_at__date__lte=date_to
    )

    # Apply payment method filter if provided
    if payment_method:
        orders = orders.filter(payment_method=payment_method)

    # Get sales data
    sales_data = OrderItem.objects.filter(
        order__in=orders
    )

    # Apply category filter if provided
    if category_id:
        sales_data = sales_data.filter(menu_item__category_id=category_id)

    # Group by menu item
    item_sales = sales_data.values(
        'menu_item__id',
        'menu_item__name',
        'menu_item__category__name'
    ).annotate(
        quantity=Sum('quantity'),
        orders=Count('order', distinct=True),
        avg_price=Avg('price')
    )

    # Calculate revenue for each item
    for item in item_sales:
        # Get all order items for this menu item
        item_order_items = sales_data.filter(menu_item__id=item['menu_item__id'])
        # Calculate revenue
        item['revenue'] = sum(oi.quantity * oi.price for oi in item_order_items.iterator())

    # Calculate totals
    total_quantity = sum(item['quantity'] for item in item_sales)
    total_revenue = sum(item['revenue'] for item in item_sales)

    # Get order count and average order value
    order_count = orders.count()
    avg_order_value = total_revenue / order_count if order_count > 0 else 0

    # Get sales by payment method
    payment_method_sales = orders.values('payment_method').annotate(
        count=Count('id'),
        total=Sum('total_amount')
    ).order_by('-total')

    # Get sales by order type
    order_type_sales = orders.values('order_type').annotate(
        count=Count('id'),
        total=Sum('total_amount')
    ).order_by('-total')

    # Get sales by category
    category_sales = []
    category_data = sales_data.values('menu_item__category__name').annotate(
        quantity=Sum('quantity')
    )

    # Calculate total manually for each category
    for category in category_data:
        category_items = sales_data.filter(menu_item__category__name=category['menu_item__category__name'])
        total = sum(item.quantity * item.price for item in category_items)
        category_sales.append({
            'menu_item__category__name': category['menu_item__category__name'],
            'quantity': category['quantity'],
            'total': total
        })

    # Sort by total
    category_sales = sorted(category_sales, key=lambda x: x['total'], reverse=True)

    # Get time series data based on report type
    time_labels = []
    time_values = []
    time_counts = []

    if orders.exists():
        if report_type == 'daily':
            time_series = orders.annotate(
                date=TruncDate('created_at')
            ).values('date').annotate(
                total=Sum('total_amount'),
                count=Count('id')
            ).order_by('date')

            # Format for chart
            time_labels = [entry['date'].strftime('%b %d') for entry in time_series]
            time_values = [float(entry['total']) for entry in time_series]
            time_counts = [entry['count'] for entry in time_series]

        elif report_type == 'weekly':
            time_series = orders.annotate(
                week=TruncWeek('created_at')
            ).values('week').annotate(
                total=Sum('total_amount'),
                count=Count('id')
            ).order_by('week')

            # Format for chart
            time_labels = [f"Week {entry['week'].strftime('%U')}" for entry in time_series]
            time_values = [float(entry['total']) for entry in time_series]
            time_counts = [entry['count'] for entry in time_series]

        else:  # monthly
            time_series = orders.annotate(
                month=TruncMonth('created_at')
            ).values('month').annotate(
                total=Sum('total_amount'),
                count=Count('id')
            ).order_by('month')

            # Format for chart
            time_labels = [entry['month'].strftime('%b %Y') for entry in time_series]
            time_values = [float(entry['total']) for entry in time_series]
            time_counts = [entry['count'] for entry in time_series]

    # Sales by hour of day
    if orders.exists():
        sales_by_hour = orders.annotate(
            hour=TruncHour('created_at')
        ).values(
            hour_num=F('hour__hour')
        ).annotate(
            total=Sum('total_amount'),
            count=Count('id')
        ).order_by('hour_num')

        # Format for chart
        hour_data = [0] * 24  # Initialize with zeros for all 24 hours
        for entry in sales_by_hour:
            hour_num = entry['hour_num']
            if 0 <= hour_num < 24:  # Ensure valid hour
                hour_data[hour_num] = float(entry['total'])
    else:
        hour_data = [0] * 24

    # Get all categories for filter
    categories = Category.objects.all().order_by('name')

    # Get all payment methods for filter
    payment_methods = Order.PAYMENT_METHOD_CHOICES

    # If export to PDF is requested
    if export_pdf:
        # Prepare data for PDF
        data = {
            'date_from': date_from,
            'date_to': date_to,
            'item_sales': list(item_sales),
            'total_revenue': total_revenue,
            'total_quantity': total_quantity,
            'payment_method_sales': list(payment_method_sales),
            'order_type_sales': list(order_type_sales),
            'category_sales': list(category_sales),
            'sales_by_day': list(time_series) if 'time_series' in locals() else [],
            'orders_count': order_count,
            'cashier_name': request.user.get_full_name() or request.user.username,
            'payment_methods': payment_methods,
            'order_types': Order.ORDER_TYPE_CHOICES,
            'categories': categories,
        }

        # Generate PDF
        pdf_buffer = generate_simple_sales_report_pdf(data)

        # Create response
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="sales_report_{date_from}_to_{date_to}.pdf"'

        return response

    context = {
        'date_from': date_from,
        'date_to': date_to,
        'category_id': category_id,
        'payment_method': payment_method,
        'report_type': report_type,
        'categories': categories,
        'payment_methods': payment_methods,
        'item_sales': item_sales,
        'total_quantity': total_quantity,
        'total_revenue': total_revenue,
        'order_count': order_count,
        'avg_order_value': avg_order_value,
        'time_labels': time_labels,
        'time_values': time_values,
        'time_counts': time_counts,
        'hour_data': hour_data,
        'category_sales': category_sales,
        'payment_method_sales': payment_method_sales,
        'order_type_sales': order_type_sales,
        'active_section': 'cashier_sales_report'
    }

    return render(request, 'cashier/reports/sales_report.html', context)


@login_required
def cashier_export_sales_report_pdf(request):
    """Export sales report as PDF for cashiers"""
    # Check if user has cashier role
    if not hasattr(request.user, 'staff_profile') or request.user.staff_profile.role != 'CASHIER':
        messages.error(request, "You don't have permission to access this page.")
        return redirect('login')

    # Get date range
    today = timezone.now().date()
    date_from_str = request.GET.get('date_from', (today - datetime.timedelta(days=7)).isoformat())
    date_to_str = request.GET.get('date_to', today.isoformat())

    try:
        date_from = datetime.datetime.fromisoformat(date_from_str).date()
        date_to = datetime.datetime.fromisoformat(date_to_str).date()
    except ValueError:
        # Handle invalid date format
        date_from = today - datetime.timedelta(days=7)
        date_to = today
        messages.error(request, "Invalid date format. Using default date range.")

    category_id = request.GET.get('category', '')
    payment_method = request.GET.get('payment_method', '')

    # Base query for completed orders
    orders = Order.objects.filter(
        status='COMPLETED',
        created_at__date__gte=date_from,
        created_at__date__lte=date_to
    )

    # Apply payment method filter if provided
    if payment_method:
        orders = orders.filter(payment_method=payment_method)

    # Get sales data
    order_items_query = OrderItem.objects.filter(order__in=orders)

    # Apply category filter if provided
    if category_id:
        order_items_query = order_items_query.filter(menu_item__category_id=category_id)

    # Generate data for the report
    data = generate_sales_report_data(request, orders, order_items_query, date_from, date_to)

    # Generate PDF
    pdf_buffer = generate_simple_sales_report_pdf(data)

    # Create response
    response = HttpResponse(pdf_buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="sales_report_{date_from}_to_{date_to}.pdf"'

    return response
