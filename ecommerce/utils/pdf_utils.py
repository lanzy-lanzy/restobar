from io import BytesIO
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import os
from django.conf import settings
from decimal import Decimal

def generate_sales_report_pdf(
    date_from,
    date_to,
    item_sales,
    total_revenue,
    total_quantity,
    payment_method_sales,
    order_type_sales,
    category_sales,
    orders_count,
    cashier_name
):
    """
    Generate a comprehensive sales report PDF using ReportLab.

    Args:
        date_from: Start date for the report
        date_to: End date for the report
        item_sales: List of items sold with quantities and revenue
        total_revenue: Total revenue for the period
        total_quantity: Total quantity of items sold
        payment_method_sales: Sales breakdown by payment method
        order_type_sales: Sales breakdown by order type
        category_sales: Sales breakdown by category
        orders_count: Total number of orders
        cashier_name: Name of the cashier generating the report

    Returns:
        HttpResponse with PDF content
    """
    # Create response object
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="sales_report_{date_from}_to_{date_to}.pdf"'

    # Create PDF document
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.5*inch,
        leftMargin=0.5*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )

    # Get styles
    styles = getSampleStyleSheet()

    # Create custom styles with unique names
    title_style = ParagraphStyle(
        name='PDFTitle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=12
    )

    subtitle_style = ParagraphStyle(
        name='PDFSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=12
    )

    section_title_style = ParagraphStyle(
        name='PDFSectionTitle',
        parent=styles['Heading3'],
        fontSize=12,
        spaceAfter=6
    )

    normal_center_style = ParagraphStyle(
        name='PDFNormalCenter',
        parent=styles['Normal'],
        alignment=TA_CENTER
    )

    normal_right_style = ParagraphStyle(
        name='PDFNormalRight',
        parent=styles['Normal'],
        alignment=TA_RIGHT
    )

    # Add styles to the stylesheet
    for style in [title_style, subtitle_style, section_title_style, normal_center_style, normal_right_style]:
        try:
            styles.add(style)
        except KeyError:
            # Style already exists, just use it
            pass

    # Create elements list
    elements = []

    # Add logo if available
    logo_path = os.path.join(settings.STATIC_ROOT, 'logo', '5th_avenue_logo.jpg')
    if os.path.exists(logo_path):
        img = Image(logo_path, width=1.5*inch, height=1.5*inch)
        img.hAlign = 'CENTER'
        elements.append(img)
        elements.append(Spacer(1, 0.2*inch))

    # Add title
    elements.append(Paragraph("5th Avenue Grill and Restobar", styles['PDFTitle']))

    # Check if this is a cashier-specific report
    if cashier_name != "All Cashiers":
        elements.append(Paragraph(f"Cashier Sales Report - {cashier_name}", styles['PDFSubtitle']))
    else:
        elements.append(Paragraph("Cashier Sales Report", styles['PDFSubtitle']))

    elements.append(Paragraph(f"From {date_from.strftime('%B %d, %Y')} to {date_to.strftime('%B %d, %Y')}", styles['PDFNormalCenter']))
    elements.append(Spacer(1, 0.3*inch))

    # Add summary section
    elements.append(Paragraph("Sales Summary", styles['PDFSectionTitle']))

    # Create summary table
    summary_data = [
        ["Total Revenue", "Total Items Sold", "Total Orders", "Average Order Value"],
        [
            f"₱{total_revenue:.2f}",
            f"{total_quantity}",
            f"{orders_count}",
            f"₱{(total_revenue / orders_count if orders_count > 0 else 0):.2f}"
        ]
    ]

    summary_table = Table(summary_data, colWidths=[doc.width/4.0]*4)
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
    ]))

    elements.append(summary_table)
    elements.append(Spacer(1, 0.2*inch))

    # Add payment method section
    elements.append(Paragraph("Sales by Payment Method", styles['PDFSectionTitle']))

    # Create payment method table
    payment_data = [["Payment Method", "Orders", "Revenue", "% of Total"]]

    for payment in payment_method_sales:
        payment_method = payment.get('payment_method', 'Unknown')
        # Convert payment method code to display name
        payment_method_display = payment_method
        for method_code, method_name in [
            ('CASH', 'Cash'),
            ('CASH_ON_HAND', 'Cash on Hand'),
            ('CARD', 'Credit/Debit Card'),
            ('GCASH', 'GCash'),
            ('ONLINE', 'Other Online Payment')
        ]:
            if payment_method == method_code:
                payment_method_display = method_name
                break

        count = payment.get('count', 0)
        total = payment.get('total', 0)
        percentage = (total / total_revenue * 100) if total_revenue > 0 else 0

        payment_data.append([
            payment_method_display,
            str(count),
            f"₱{total:.2f}",
            f"{percentage:.1f}%"
        ])

    payment_table = Table(payment_data, colWidths=[doc.width*0.4, doc.width*0.15, doc.width*0.25, doc.width*0.2])
    payment_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ALIGN', (1, 1), (3, -1), 'RIGHT'),
    ]))

    elements.append(payment_table)
    elements.append(Spacer(1, 0.2*inch))

    # Add category section
    elements.append(Paragraph("Sales by Category", styles['PDFSectionTitle']))

    # Create category table
    category_data = [["Category", "Items Sold", "Revenue", "% of Total"]]

    for category in category_sales:
        category_name = category.get('menu_item__category__name', 'No Category')
        quantity = category.get('quantity', 0)
        total = category.get('total', 0)
        percentage = (total / total_revenue * 100) if total_revenue > 0 else 0

        category_data.append([
            category_name,
            str(quantity),
            f"₱{total:.2f}",
            f"{percentage:.1f}%"
        ])

    category_table = Table(category_data, colWidths=[doc.width*0.4, doc.width*0.15, doc.width*0.25, doc.width*0.2])
    category_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ALIGN', (1, 1), (3, -1), 'RIGHT'),
    ]))

    elements.append(category_table)
    elements.append(Spacer(1, 0.2*inch))

    # Add top items section
    elements.append(Paragraph("Top Selling Items", styles['PDFSectionTitle']))

    # Create items table
    items_data = [["Item", "Category", "Quantity", "Revenue", "% of Total"]]

    # Sort items by revenue
    sorted_items = sorted(item_sales, key=lambda x: x.get('revenue', 0), reverse=True)

    # Take top 10 items
    for item in sorted_items[:10]:
        item_name = item.get('menu_item__name', 'Unknown')
        category_name = item.get('menu_item__category__name', 'No Category')
        quantity = item.get('quantity', 0)
        revenue = item.get('revenue', 0)
        percentage = (revenue / total_revenue * 100) if total_revenue > 0 else 0

        items_data.append([
            item_name,
            category_name,
            str(quantity),
            f"₱{revenue:.2f}",
            f"{percentage:.1f}%"
        ])

    items_table = Table(items_data, colWidths=[doc.width*0.25, doc.width*0.2, doc.width*0.15, doc.width*0.2, doc.width*0.2])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ALIGN', (2, 1), (4, -1), 'RIGHT'),
    ]))

    elements.append(items_table)
    elements.append(Spacer(1, 0.2*inch))

    # Add order type section
    elements.append(Paragraph("Sales by Order Type", styles['PDFSectionTitle']))

    # Create order type table
    order_type_data = [["Order Type", "Orders", "Revenue", "% of Total"]]

    for order_type in order_type_sales:
        order_type_code = order_type.get('order_type', 'Unknown')
        # Convert order type code to display name
        order_type_display = order_type_code
        for type_code, type_name in [
            ('DELIVERY', 'Delivery'),
            ('PICKUP', 'Pickup'),
            ('DINE_IN', 'Dine In')
        ]:
            if order_type_code == type_code:
                order_type_display = type_name
                break

        count = order_type.get('count', 0)
        total = order_type.get('total', 0)
        percentage = (total / total_revenue * 100) if total_revenue > 0 else 0

        order_type_data.append([
            order_type_display,
            str(count),
            f"₱{total:.2f}",
            f"{percentage:.1f}%"
        ])

    order_type_table = Table(order_type_data, colWidths=[doc.width*0.4, doc.width*0.15, doc.width*0.25, doc.width*0.2])
    order_type_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ALIGN', (1, 1), (3, -1), 'RIGHT'),
    ]))

    elements.append(order_type_table)
    elements.append(Spacer(1, 0.2*inch))

    # Add footer
    elements.append(Paragraph(f"© {date_from.strftime('%Y')} 5th Avenue Grill and Restobar. All rights reserved.", styles['PDFNormalCenter']))

    # Build PDF
    doc.build(elements)

    # Get PDF from buffer
    pdf = buffer.getvalue()
    buffer.close()

    # Write PDF to response
    response.write(pdf)

    return response
