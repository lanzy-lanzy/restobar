"""
Utility functions for generating PDF reports using ReportLab.
"""
import io
import os
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, KeepTogether, HRFlowable, Flowable
)
from reportlab.graphics.shapes import Drawing, Line
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.legends import Legend
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Register DejaVuSans font for proper peso sign rendering
font_path = os.path.join(settings.STATIC_ROOT, 'fonts', 'ttf', 'DejaVuSans.ttf')
if not os.path.exists(font_path):
    # If STATIC_ROOT is not set up correctly, try with BASE_DIR
    font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'ttf', 'DejaVuSans.ttf')

# Register the font if it exists
if os.path.exists(font_path):
    pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
else:
    print(f"Warning: DejaVuSans font not found at {font_path}")


class ChartDrawing(Drawing):
    """
    Custom flowable for charts
    """
    def __init__(self, width, height, chart):
        Drawing.__init__(self, width, height)
        self.add(chart)


def generate_sales_report_pdf(data):
    """
    Generate a comprehensive sales report PDF using ReportLab.

    Args:
        data (dict): Dictionary containing all the data needed for the report

    Returns:
        BytesIO: PDF file as a BytesIO object
    """
    # Create a file-like buffer to receive PDF data
    buffer = io.BytesIO()

    # Create the PDF object, using the buffer as its "file"
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=inch/2,
        leftMargin=inch/2,
        topMargin=inch/2,
        bottomMargin=inch/2,
        title=f"Sales Report {data['date_from']} to {data['date_to']}"
    )

    # Get styles
    styles = getSampleStyleSheet()

    # Create custom styles with unique names
    title_style = ParagraphStyle(
        name='CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=12,
        textColor=colors.HexColor('#F9A826'),
        fontName='DejaVuSans' if 'DejaVuSans' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
    )

    subtitle_style = ParagraphStyle(
        name='CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=12,
        textColor=colors.HexColor('#F9A826'),
        fontName='DejaVuSans' if 'DejaVuSans' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
    )

    section_title_style = ParagraphStyle(
        name='CustomSectionTitle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=6,
        textColor=colors.HexColor('#F9A826'),
        fontName='DejaVuSans' if 'DejaVuSans' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
    )

    normal_center_style = ParagraphStyle(
        name='CustomNormalCenter',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontName='DejaVuSans' if 'DejaVuSans' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
    )

    normal_right_style = ParagraphStyle(
        name='CustomNormalRight',
        parent=styles['Normal'],
        alignment=TA_RIGHT,
        fontName='DejaVuSans' if 'DejaVuSans' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
    )

    # Add styles to the stylesheet
    for style in [title_style, subtitle_style, section_title_style, normal_center_style, normal_right_style]:
        try:
            styles.add(style)
        except KeyError:
            # Style already exists, just use it
            pass

    # Container for the 'Flowable' objects
    elements = []

    # Add restaurant logo if available
    logo_path = os.path.join(settings.STATIC_ROOT, 'logo', '5th_avenue_logo.jpg')
    if not os.path.exists(logo_path):
        # If STATIC_ROOT is not set up correctly, try with BASE_DIR
        logo_path = os.path.join(settings.BASE_DIR, 'static', 'logo', '5th_avenue_logo.jpg')

    if os.path.exists(logo_path):
        logo = Image(logo_path, width=1.5*inch, height=1.5*inch)
        logo.hAlign = 'CENTER'
        elements.append(logo)
        elements.append(Spacer(1, 0.25*inch))

    # Add title
    elements.append(Paragraph("5th Avenue Grill and Restobar", styles['CustomTitle']))
    elements.append(Paragraph("Sales Report", styles['CustomSubtitle']))

    # Add date range and generation info
    date_from_str = data['date_from'].strftime('%B %d, %Y')
    date_to_str = data['date_to'].strftime('%B %d, %Y')
    elements.append(Paragraph(f"Period: {date_from_str} to {date_to_str}", styles['CustomNormalCenter']))
    elements.append(Paragraph(f"Generated on: {timezone.now().strftime('%B %d, %Y %H:%M')}", styles['CustomNormalCenter']))

    elements.append(Spacer(1, 0.5*inch))

    # Add summary section
    elements.append(Paragraph("Sales Summary", styles['CustomSectionTitle']))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#F9A826'), spaceAfter=0.1*inch))

    # Create summary table
    summary_data = [
        ["Total Revenue", "Total Items Sold", "Total Orders", "Average Order Value"],
        [
            f"₱{data['total_revenue']:.2f}",
            f"{data['total_quantity']}",
            f"{data['orders_count']}",
            f"₱{(data['total_revenue'] / data['orders_count'] if data['orders_count'] > 0 else 0):.2f}"
        ]
    ]

    summary_table = Table(summary_data, colWidths=[doc.width/4.0]*4)
    # Determine font to use
    font_name = 'DejaVuSans' if 'DejaVuSans' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
    bold_font = 'DejaVuSans-Bold' if 'DejaVuSans-Bold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'

    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#333333')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), bold_font),
        ('FONTNAME', (0, 1), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f2f2f2')),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 11),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]))

    elements.append(summary_table)
    elements.append(Spacer(1, 0.3*inch))

    # Add sales by payment method section
    elements.append(Paragraph("Sales by Payment Method", styles['CustomSectionTitle']))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#F9A826'), spaceAfter=0.1*inch))

    # Create payment method table
    payment_header = ["Payment Method", "Orders", "Revenue", "% of Total"]
    payment_data = [payment_header]

    # Add payment method data
    for payment in data['payment_method_sales']:
        payment_name = next((name for code, name in data['payment_methods'] if code == payment['payment_method']), payment['payment_method'])
        percentage = (payment['total'] / data['total_revenue'] * 100) if data['total_revenue'] > 0 else 0
        payment_data.append([
            payment_name,
            str(payment['count']),
            f"₱{payment['total']:.2f}",
            f"{percentage:.1f}%"
        ])

    payment_table = Table(payment_data, colWidths=[doc.width*0.4, doc.width*0.2, doc.width*0.2, doc.width*0.2])
    payment_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#333333')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))

    elements.append(payment_table)

    # Add payment method pie chart
    if data['payment_method_sales']:
        elements.append(Spacer(1, 0.2*inch))
        elements.append(Paragraph("Payment Method Distribution", styles['CustomNormalCenter']))

        drawing = Drawing(500, 200)
        pie = Pie()
        pie.x = 150
        pie.y = 15
        pie.width = 200
        pie.height = 200
        # Convert Decimal to float
        pie.data = [float(payment['total']) for payment in data['payment_method_sales']]
        pie.labels = [next((name for code, name in data['payment_methods'] if code == payment['payment_method']), payment['payment_method'])
                     for payment in data['payment_method_sales']]
        pie.slices.strokeWidth = 0.5

        # Add a legend
        legend = Legend()
        legend.alignment = 'right'
        legend.x = 380
        legend.y = 85
        legend.colorNamePairs = [(colors.HexColor(f"#{hash(label) % 0xffffff:06x}"), label)
                                for label in pie.labels]
        drawing.add(pie)
        drawing.add(legend)

        elements.append(drawing)

    elements.append(Spacer(1, 0.3*inch))

    # Add sales by category section
    elements.append(Paragraph("Sales by Category", styles['CustomSectionTitle']))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#F9A826'), spaceAfter=0.1*inch))

    # Create category table
    category_header = ["Category", "Items Sold", "Revenue", "% of Total"]
    category_data = [category_header]

    # Add category data
    for category in data['category_sales']:
        category_name = category['menu_item__category__name'] or "No Category"
        percentage = (category['total'] / data['total_revenue'] * 100) if data['total_revenue'] > 0 else 0
        category_data.append([
            category_name,
            str(category['quantity']),
            f"₱{category['total']:.2f}",
            f"{percentage:.1f}%"
        ])

    category_table = Table(category_data, colWidths=[doc.width*0.4, doc.width*0.2, doc.width*0.2, doc.width*0.2])
    category_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#333333')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))

    elements.append(category_table)

    # Add category bar chart
    if data['category_sales']:
        elements.append(Spacer(1, 0.2*inch))
        elements.append(Paragraph("Revenue by Category", styles['CustomNormalCenter']))

        drawing = Drawing(500, 200)
        bc = VerticalBarChart()
        bc.x = 50
        bc.y = 50
        bc.height = 125
        bc.width = 400
        # Convert Decimal to float
        bc.data = [[float(category['total']) for category in data['category_sales']]]
        bc.strokeColor = colors.black
        bc.valueAxis.valueMin = 0
        # Convert Decimal to float before multiplication
        max_value = max([float(category['total']) for category in data['category_sales']])
        bc.valueAxis.valueMax = max_value * 1.1
        bc.valueAxis.valueStep = bc.valueAxis.valueMax / 5
        bc.categoryAxis.labels.boxAnchor = 'ne'
        bc.categoryAxis.labels.dx = 8
        bc.categoryAxis.labels.dy = -2
        bc.categoryAxis.labels.angle = 30
        bc.categoryAxis.categoryNames = [category['menu_item__category__name'] or "No Category" for category in data['category_sales']]
        bc.bars[0].fillColor = colors.HexColor('#F9A826')

        drawing.add(bc)
        elements.append(drawing)

    elements.append(PageBreak())

    # Add top selling items section
    elements.append(Paragraph("Top Selling Items", styles['CustomSectionTitle']))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#F9A826'), spaceAfter=0.1*inch))

    # Create items table
    items_header = ["Item", "Category", "Quantity", "Revenue", "% of Total"]
    items_data = [items_header]

    # Add item data (limit to top 15 items)
    for item in data['item_sales'][:15]:
        item_name = item['menu_item__name']
        category_name = item['menu_item__category__name'] or "No Category"
        percentage = (item['revenue'] / data['total_revenue'] * 100) if data['total_revenue'] > 0 else 0
        items_data.append([
            item_name,
            category_name,
            str(item['quantity']),
            f"₱{item['revenue']:.2f}",
            f"{percentage:.1f}%"
        ])

    items_table = Table(items_data, colWidths=[doc.width*0.3, doc.width*0.2, doc.width*0.15, doc.width*0.15, doc.width*0.2])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#333333')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))

    elements.append(items_table)

    # Add top items bar chart
    if data['item_sales']:
        elements.append(Spacer(1, 0.2*inch))
        elements.append(Paragraph("Top 5 Items by Quantity", styles['CustomNormalCenter']))

        # Limit to top 5 items for the chart
        top_items = sorted(data['item_sales'][:5], key=lambda x: x['quantity'], reverse=True)

        drawing = Drawing(500, 200)
        bc = VerticalBarChart()
        bc.x = 50
        bc.y = 50
        bc.height = 125
        bc.width = 400
        # Convert Decimal to float
        bc.data = [[float(item['quantity']) for item in top_items]]
        bc.strokeColor = colors.black
        bc.valueAxis.valueMin = 0
        # Convert to float before multiplication
        max_value = max([float(item['quantity']) for item in top_items])
        bc.valueAxis.valueMax = max_value * 1.1
        bc.valueAxis.valueStep = bc.valueAxis.valueMax / 5
        bc.categoryAxis.labels.boxAnchor = 'ne'
        bc.categoryAxis.labels.dx = 8
        bc.categoryAxis.labels.dy = -2
        bc.categoryAxis.labels.angle = 30
        bc.categoryAxis.categoryNames = [item['menu_item__name'] for item in top_items]
        bc.bars[0].fillColor = colors.HexColor('#F9A826')

        drawing.add(bc)
        elements.append(drawing)

    # Add daily sales chart if available
    if 'sales_by_day' in data and data['sales_by_day']:
        elements.append(Spacer(1, 0.3*inch))
        elements.append(Paragraph("Daily Sales Trend", styles['CustomSectionTitle']))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#F9A826'), spaceAfter=0.1*inch))

        drawing = Drawing(500, 200)
        lc = HorizontalLineChart()
        lc.x = 50
        lc.y = 50
        lc.height = 125
        lc.width = 400

        # Extract dates and sales values
        dates = [day['date'].strftime('%m/%d') for day in data['sales_by_day']]
        # Convert Decimal to float
        sales = [float(day['total']) for day in data['sales_by_day']]

        lc.data = [sales]
        lc.categoryAxis.categoryNames = dates
        lc.categoryAxis.labels.boxAnchor = 'n'
        lc.categoryAxis.labels.angle = 30
        lc.categoryAxis.labels.dx = 0
        lc.categoryAxis.labels.dy = -2

        lc.valueAxis.valueMin = 0
        # Convert to float before multiplication
        max_value = max([float(val) for val in sales]) * 1.1 if sales else 1000
        lc.valueAxis.valueMax = max_value
        lc.valueAxis.valueStep = lc.valueAxis.valueMax / 5

        lc.lines[0].strokeWidth = 3
        lc.lines[0].strokeColor = colors.HexColor('#F9A826')

        drawing.add(lc)
        elements.append(drawing)

    # Build the PDF
    doc.build(elements)

    # Get the value of the BytesIO buffer and return it
    buffer.seek(0)
    return buffer


def generate_simple_sales_report_pdf(data):
    """
    Generate a simple sales report PDF using ReportLab, focusing only on tables without charts.

    Args:
        data (dict): Dictionary containing all the data needed for the report

    Returns:
        BytesIO: PDF file as a BytesIO object
    """
    # Create a file-like buffer to receive PDF data
    buffer = io.BytesIO()

    # Create the PDF object, using the buffer as its "file"
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=inch/2,
        leftMargin=inch/2,
        topMargin=inch/2,
        bottomMargin=inch/2,
        title=f"Sales Report {data['date_from']} to {data['date_to']}"
    )

    # Get styles
    styles = getSampleStyleSheet()

    # Create custom styles with unique names
    title_style = ParagraphStyle(
        name='SimpleTitle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=12,
        textColor=colors.HexColor('#333333'),
        fontName='DejaVuSans' if 'DejaVuSans' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
    )

    subtitle_style = ParagraphStyle(
        name='SimpleSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=12,
        textColor=colors.HexColor('#333333'),
        fontName='DejaVuSans' if 'DejaVuSans' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
    )

    section_title_style = ParagraphStyle(
        name='SimpleSectionTitle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=6,
        textColor=colors.HexColor('#333333'),
        fontName='DejaVuSans' if 'DejaVuSans' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
    )

    normal_center_style = ParagraphStyle(
        name='SimpleNormalCenter',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontName='DejaVuSans' if 'DejaVuSans' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
    )

    normal_right_style = ParagraphStyle(
        name='SimpleNormalRight',
        parent=styles['Normal'],
        alignment=TA_RIGHT,
        fontName='DejaVuSans' if 'DejaVuSans' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
    )

    # Add styles to the stylesheet
    for style in [title_style, subtitle_style, section_title_style, normal_center_style, normal_right_style]:
        try:
            styles.add(style)
        except KeyError:
            # Style already exists, just use it
            pass

    # Container for the 'Flowable' objects
    elements = []

    # Add restaurant logo if available
    logo_path = os.path.join(settings.STATIC_ROOT, 'logo', '5th_avenue_logo.jpg')
    if not os.path.exists(logo_path):
        # If STATIC_ROOT is not set up correctly, try with BASE_DIR
        logo_path = os.path.join(settings.BASE_DIR, 'static', 'logo', '5th_avenue_logo.jpg')

    if os.path.exists(logo_path):
        logo = Image(logo_path, width=1.5*inch, height=1.5*inch)
        logo.hAlign = 'CENTER'
        elements.append(logo)
        elements.append(Spacer(1, 0.25*inch))

    # Add title
    elements.append(Paragraph("5th Avenue Grill and Restobar", styles['SimpleTitle']))
    elements.append(Paragraph("Sales Report", styles['SimpleSubtitle']))

    # Add date range and generation info
    date_from_str = data['date_from'].strftime('%B %d, %Y')
    date_to_str = data['date_to'].strftime('%B %d, %Y')
    elements.append(Paragraph(f"Period: {date_from_str} to {date_to_str}", styles['SimpleNormalCenter']))
    elements.append(Paragraph(f"Generated on: {timezone.now().strftime('%B %d, %Y %H:%M')}", styles['SimpleNormalCenter']))

    elements.append(Spacer(1, 0.5*inch))

    # Add summary section
    elements.append(Paragraph("Sales Summary", styles['SimpleSectionTitle']))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceAfter=0.1*inch))

    # Create summary table
    summary_data = [
        ["Total Revenue", "Total Items Sold", "Total Orders", "Average Order Value"],
        [
            f"₱{data['total_revenue']:.2f}",
            f"{data['total_quantity']}",
            f"{data['orders_count']}",
            f"₱{(data['total_revenue'] / data['orders_count'] if data['orders_count'] > 0 else 0):.2f}"
        ]
    ]

    summary_table = Table(summary_data, colWidths=[doc.width/4.0]*4)
    # Determine font to use
    font_name = 'DejaVuSans' if 'DejaVuSans' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
    bold_font = 'DejaVuSans-Bold' if 'DejaVuSans-Bold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'

    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#333333')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), bold_font),
        ('FONTNAME', (0, 1), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f2f2f2')),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 11),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]))

    elements.append(summary_table)
    elements.append(Spacer(1, 0.3*inch))

    # Add sales by payment method section
    elements.append(Paragraph("Sales by Payment Method", styles['SimpleSectionTitle']))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceAfter=0.1*inch))

    # Create payment method table
    payment_header = ["Payment Method", "Orders", "Revenue", "% of Total"]
    payment_data = [payment_header]

    # Add payment method data
    for payment in data['payment_method_sales']:
        payment_name = next((name for code, name in data['payment_methods'] if code == payment['payment_method']), payment['payment_method'])
        percentage = (payment['total'] / data['total_revenue'] * 100) if data['total_revenue'] > 0 else 0
        payment_data.append([
            payment_name,
            str(payment['count']),
            f"₱{payment['total']:.2f}",
            f"{percentage:.1f}%"
        ])

    payment_table = Table(payment_data, colWidths=[doc.width*0.4, doc.width*0.2, doc.width*0.2, doc.width*0.2])
    payment_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#333333')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), bold_font),
        ('FONTNAME', (0, 1), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))

    elements.append(payment_table)
    elements.append(Spacer(1, 0.3*inch))

    # Add sales by category section
    elements.append(Paragraph("Sales by Category", styles['SimpleSectionTitle']))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceAfter=0.1*inch))

    # Create category table
    category_header = ["Category", "Items Sold", "Revenue", "% of Total"]
    category_data = [category_header]

    # Add category data
    for category in data['category_sales']:
        category_name = category['menu_item__category__name'] or "No Category"
        percentage = (category['total'] / data['total_revenue'] * 100) if data['total_revenue'] > 0 else 0
        category_data.append([
            category_name,
            str(category['quantity']),
            f"₱{category['total']:.2f}",
            f"{percentage:.1f}%"
        ])

    category_table = Table(category_data, colWidths=[doc.width*0.4, doc.width*0.2, doc.width*0.2, doc.width*0.2])
    category_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#333333')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), bold_font),
        ('FONTNAME', (0, 1), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))

    elements.append(category_table)
    elements.append(PageBreak())

    # Add top selling items section
    elements.append(Paragraph("Top Selling Items", styles['SimpleSectionTitle']))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceAfter=0.1*inch))

    # Create items table
    items_header = ["Item", "Category", "Quantity", "Revenue", "% of Total"]
    items_data = [items_header]

    # Add item data (limit to top 15 items)
    for item in data['item_sales'][:15]:
        item_name = item['menu_item__name']
        category_name = item['menu_item__category__name'] or "No Category"
        percentage = (item['revenue'] / data['total_revenue'] * 100) if data['total_revenue'] > 0 else 0
        items_data.append([
            item_name,
            category_name,
            str(item['quantity']),
            f"₱{item['revenue']:.2f}",
            f"{percentage:.1f}%"
        ])

    items_table = Table(items_data, colWidths=[doc.width*0.3, doc.width*0.2, doc.width*0.15, doc.width*0.15, doc.width*0.2])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#333333')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), bold_font),
        ('FONTNAME', (0, 1), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))

    elements.append(items_table)
    elements.append(Spacer(1, 0.3*inch))

    # Add order type sales section
    elements.append(Paragraph("Sales by Order Type", styles['SimpleSectionTitle']))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceAfter=0.1*inch))

    # Create order type table
    order_type_header = ["Order Type", "Orders", "Revenue", "% of Total"]
    order_type_data = [order_type_header]

    # Add order type data
    for order_type in data['order_type_sales']:
        order_type_name = next((name for code, name in data['order_types'] if code == order_type['order_type']), order_type['order_type'])
        percentage = (order_type['total'] / data['total_revenue'] * 100) if data['total_revenue'] > 0 else 0
        order_type_data.append([
            order_type_name,
            str(order_type['count']),
            f"₱{order_type['total']:.2f}",
            f"{percentage:.1f}%"
        ])

    order_type_table = Table(order_type_data, colWidths=[doc.width*0.4, doc.width*0.2, doc.width*0.2, doc.width*0.2])
    order_type_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#333333')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), bold_font),
        ('FONTNAME', (0, 1), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))

    elements.append(order_type_table)
    elements.append(Spacer(1, 0.3*inch))

    # Add footer
    elements.append(Paragraph(f"© {timezone.now().year} 5th Avenue Grill and Restobar. All rights reserved.", styles['SimpleNormalCenter']))

    # Build the PDF
    doc.build(elements)

    # Get the value of the BytesIO buffer and return it
    buffer.seek(0)
    return buffer


def generate_sales_report_data(request, orders, order_items_query, date_from, date_to):
    """
    Generate data for sales report.

    Args:
        request: The HTTP request
        orders: QuerySet of orders
        order_items_query: QuerySet of order items
        date_from: Start date
        date_to: End date

    Returns:
        dict: Data for the sales report
    """
    from ecommerce.models import Order, Category
    from django.db.models import Sum, Count, F

    # Get sales by item - calculate revenue directly
    item_sales = order_items_query.values(
        'menu_item__id',
        'menu_item__name',
        'menu_item__category__name'
    ).annotate(
        quantity=Sum('quantity'),
        orders_count=Count('order', distinct=True)
    ).order_by('-quantity')

    # Calculate revenue manually for each item
    for item in item_sales:
        # Get the total price for this item
        item_total = order_items_query.filter(
            menu_item__id=item['menu_item__id']
        ).aggregate(
            total=Sum('price')
        )['total'] or 0

        # Calculate revenue
        item['revenue'] = item_total

    # Calculate total revenue and quantity
    total_revenue = sum(item['revenue'] or 0 for item in item_sales)
    total_quantity = sum(item['quantity'] or 0 for item in item_sales)

    # Get sales by payment method
    payment_method_sales = orders.values(
        'payment_method'
    ).annotate(
        total=Sum('total_amount'),
        count=Count('id')
    ).order_by('-total')

    # Get sales by order type
    order_type_sales = orders.values(
        'order_type'
    ).annotate(
        total=Sum('total_amount'),
        count=Count('id')
    ).order_by('-total')

    # Get sales by category - calculate total directly
    category_sales = order_items_query.values(
        'menu_item__category__name'
    ).annotate(
        quantity=Sum('quantity')
    ).order_by('-quantity')

    # Calculate total manually for each category
    for category in category_sales:
        # Get the total price for this category
        category_total = order_items_query.filter(
            menu_item__category__name=category['menu_item__category__name']
        ).aggregate(
            total=Sum('price')
        )['total'] or 0

        # Calculate total
        category['total'] = category_total

    # Get sales by day for chart
    sales_by_day = orders.values(
        'created_at__date'
    ).annotate(
        date=F('created_at__date'),
        total=Sum('total_amount'),
        count=Count('id')
    ).order_by('date')

    # Get all categories for filter
    categories = Category.objects.all().order_by('name')

    # Prepare data for the report
    data = {
        'date_from': date_from,
        'date_to': date_to,
        'item_sales': list(item_sales),
        'total_revenue': total_revenue,
        'total_quantity': total_quantity,
        'payment_method_sales': list(payment_method_sales),
        'order_type_sales': list(order_type_sales),
        'category_sales': list(category_sales),
        'sales_by_day': list(sales_by_day),
        'orders_count': orders.count(),
        'cashier_name': request.user.get_full_name(),
        'payment_methods': Order.PAYMENT_METHOD_CHOICES,
        'order_types': Order.ORDER_TYPE_CHOICES,
        'categories': categories,
    }

    return data
