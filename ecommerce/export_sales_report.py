import datetime
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Count, F, Avg, Q
from django.contrib.auth.models import User
from django.db.models.functions import TruncDate, TruncMonth, TruncYear, ExtractHour
from django.http import HttpResponse

from .models import Order, OrderItem, Category, StaffProfile, Payment
from .utils.pdf_utils import generate_sales_report_pdf

@login_required
def export_sales_report(request):
    """
    Advanced sales report with export options and filtering by cashier, date, and time period
    """
    # Get date range
    today = timezone.now().date()
    date_from = request.GET.get('date_from', (today - datetime.timedelta(days=30)).isoformat())
    date_to = request.GET.get('date_to', today.isoformat())

    # Get filters
    category_id = request.GET.get('category', '')
    cashier_id = request.GET.get('cashier', '')
    payment_method = request.GET.get('payment_method', '')
    report_type = request.GET.get('report_type', 'daily')  # daily, monthly, yearly

    # Convert date strings to date objects
    try:
        date_from = datetime.datetime.strptime(date_from, '%Y-%m-%d').date()
        date_to = datetime.datetime.strptime(date_to, '%Y-%m-%d').date()
    except ValueError:
        # Handle invalid date format
        date_from = today - datetime.timedelta(days=30)
        date_to = today

    # Base query for completed orders
    orders_query = Order.objects.filter(
        status='COMPLETED',
        created_at__date__gte=date_from,
        created_at__date__lte=date_to
    )

    # Apply cashier filter if provided
    if cashier_id:
        orders_query = orders_query.filter(created_by_id=cashier_id)

    # Apply payment method filter if provided
    if payment_method:
        orders_query = orders_query.filter(payment_method=payment_method)

    # Get order items
    order_items_query = OrderItem.objects.filter(order__in=orders_query)

    # Apply category filter if provided
    if category_id:
        order_items_query = order_items_query.filter(menu_item__category_id=category_id)

    # Group by menu item
    item_sales = order_items_query.values(
        'menu_item__id',
        'menu_item__name',
        'menu_item__category__name'
    ).annotate(
        quantity=Sum('quantity'),
        orders=Count('order', distinct=True),
        avg_price=Avg('price')
    ).order_by('-quantity')

    # Calculate revenue for each item
    for item in item_sales:
        item_order_items = order_items_query.filter(menu_item__id=item['menu_item__id'])
        item['revenue'] = sum(oi.quantity * oi.price for oi in item_order_items)

    # Calculate totals
    total_quantity = sum(item['quantity'] for item in item_sales)
    total_revenue = sum(item['revenue'] for item in item_sales)

    # Get order count and average order value
    order_count = orders_query.count()
    avg_order_value = total_revenue / order_count if order_count > 0 else 0

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

    # Get time series data based on report type
    time_labels = []
    time_values = []
    time_counts = []

    if report_type == 'daily':
        # Daily report - group by date
        time_series = orders_query.annotate(
            period=TruncDate('created_at')
        ).values('period').annotate(
            total=Sum('total_amount'),
            count=Count('id')
        ).order_by('period')

        for entry in time_series:
            time_labels.append(entry['period'].strftime('%Y-%m-%d'))
            time_values.append(float(entry['total']))
            time_counts.append(entry['count'])

    elif report_type == 'monthly':
        # Monthly report - group by month
        time_series = orders_query.annotate(
            period=TruncMonth('created_at')
        ).values('period').annotate(
            total=Sum('total_amount'),
            count=Count('id')
        ).order_by('period')

        for entry in time_series:
            time_labels.append(entry['period'].strftime('%b %Y'))
            time_values.append(float(entry['total']))
            time_counts.append(entry['count'])

    elif report_type == 'yearly':
        # Yearly report - group by year
        time_series = orders_query.annotate(
            period=TruncYear('created_at')
        ).values('period').annotate(
            total=Sum('total_amount'),
            count=Count('id')
        ).order_by('period')

        for entry in time_series:
            time_labels.append(entry['period'].strftime('%Y'))
            time_values.append(float(entry['total']))
            time_counts.append(entry['count'])

    # Get only users with CASHIER role for filter
    cashiers = User.objects.filter(
        staff_profile__isnull=False,
        staff_profile__role='CASHIER',
        staff_profile__is_active_staff=True
    ).distinct().select_related('staff_profile')

    # If no cashiers found, include users who have created orders
    if not cashiers.exists():
        cashiers = User.objects.filter(
            Q(staff_profile__isnull=False) &
            Q(created_orders__isnull=False)
        ).distinct().select_related('staff_profile')

    # Get all categories for filter
    categories = Category.objects.all().order_by('name')

    # Get all payment methods for filter
    payment_methods = Order.PAYMENT_METHOD_CHOICES

    # Check if export to PDF is requested
    if request.GET.get('export_pdf'):
        # Get cashier name if filter is applied
        cashier_name = "All Cashiers"
        if cashier_id:
            try:
                cashier = User.objects.get(id=cashier_id)
                cashier_name = f"{cashier.first_name} {cashier.last_name}".strip() or cashier.username
            except User.DoesNotExist:
                pass

        # Get payment method sales
        payment_method_sales = Order.objects.filter(
            status='COMPLETED',
            created_at__date__gte=date_from,
            created_at__date__lte=date_to
        )

        if cashier_id:
            payment_method_sales = payment_method_sales.filter(created_by_id=cashier_id)

        payment_method_sales = payment_method_sales.values(
            'payment_method'
        ).annotate(
            count=Count('id'),
            total=Sum('total_amount')
        ).order_by('-total')

        # Get order type sales
        order_type_sales = Order.objects.filter(
            status='COMPLETED',
            created_at__date__gte=date_from,
            created_at__date__lte=date_to
        )

        if cashier_id:
            order_type_sales = order_type_sales.filter(created_by_id=cashier_id)

        order_type_sales = order_type_sales.values(
            'order_type'
        ).annotate(
            count=Count('id'),
            total=Sum('total_amount')
        ).order_by('-total')

        # Generate PDF
        return generate_sales_report_pdf(
            date_from,
            date_to,
            item_sales,
            total_revenue,
            total_quantity,
            payment_method_sales,
            order_type_sales,
            [], # category_sales - not used in this report
            order_count,
            cashier_name
        )

    # Prepare context for template
    context = {
        'date_from': date_from.isoformat(),
        'date_to': date_to.isoformat(),
        'category_id': category_id,
        'cashier_id': cashier_id,
        'payment_method': payment_method,
        'report_type': report_type,
        'categories': categories,
        'cashiers': cashiers,
        'payment_methods': payment_methods,
        'item_sales': item_sales,
        'total_quantity': total_quantity,
        'total_revenue': total_revenue,
        'order_count': order_count,
        'avg_order_value': avg_order_value,
        'cashier_sales': cashier_sales,
        'time_labels': time_labels,
        'time_values': time_values,
        'time_counts': time_counts,
        'active_section': 'export_sales_report'
    }

    return render(request, 'manager/export_sales_report.html', context)


