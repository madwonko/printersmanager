"""
Printer Monitoring Web Dashboard
A web interface to view and manage printer monitoring
"""

from flask import Flask, render_template, jsonify, request, redirect, url_for, send_file
import sqlite3
from datetime import datetime, timedelta
import json
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

app = Flask(__name__)
DATABASE_FILE = "printer_monitoring.db"

# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn

def get_all_printers(location_filter=None, model_filter=None):
    """Get all printers with their latest metrics, optionally filtered"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = '''
        SELECT 
            p.id,
            p.ip,
            p.name,
            p.location,
            p.model,
            p.first_seen,
            m.total_pages,
            m.toner_level_pct,
            m.toner_status,
            m.drum_level_pct,
            m.timestamp as last_updated
        FROM printers p
        LEFT JOIN metrics m ON p.id = m.printer_id
        WHERE (m.id IN (
            SELECT MAX(id) FROM metrics GROUP BY printer_id
        ) OR m.id IS NULL)
    '''
    
    params = []
    
    if location_filter:
        query += ' AND p.location = ?'
        params.append(location_filter)
    
    if model_filter:
        query += ' AND p.model = ?'
        params.append(model_filter)
    
    query += ' ORDER BY p.location, p.name'
    
    cursor.execute(query, params)
    printers = cursor.fetchall()
    conn.close()
    return printers

def get_all_locations():
    """Get list of all unique locations"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT DISTINCT location FROM printers ORDER BY location')
    locations = [row['location'] for row in cursor.fetchall()]
    
    conn.close()
    return locations

def get_all_models():
    """Get list of all unique printer models"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT DISTINCT model FROM printers WHERE model IS NOT NULL ORDER BY model')
    models = [row['model'] for row in cursor.fetchall()]
    
    conn.close()
    return models

def get_printer_details(printer_id):
    """Get detailed info for a specific printer"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get printer info
    cursor.execute('SELECT * FROM printers WHERE id = ?', (printer_id,))
    printer = cursor.fetchone()
    
    # Get latest metrics
    cursor.execute('''
        SELECT * FROM metrics 
        WHERE printer_id = ? 
        ORDER BY timestamp DESC 
        LIMIT 1
    ''', (printer_id,))
    latest_metrics = cursor.fetchone()
    
    conn.close()
    return printer, latest_metrics

def get_printer_history(printer_id, days=30):
    """Get historical metrics for a printer"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM metrics 
        WHERE printer_id = ? 
        AND timestamp >= datetime('now', '-' || ? || ' days')
        ORDER BY timestamp ASC
    ''', (printer_id, days))
    
    history = cursor.fetchall()
    conn.close()
    return history

def get_printer_usage(printer_id, days=30):
    """Get usage stats for a printer"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            MIN(total_pages) as start_pages,
            MAX(total_pages) as end_pages,
            MAX(total_pages) - MIN(total_pages) as pages_printed,
            COUNT(*) as readings,
            MIN(timestamp) as first_reading,
            MAX(timestamp) as last_reading
        FROM metrics 
        WHERE printer_id = ? 
        AND timestamp >= datetime('now', '-' || ? || ' days')
        AND total_pages IS NOT NULL
    ''', (printer_id, days))
    
    result = cursor.fetchone()
    conn.close()
    return result

def get_total_stats(location_filter=None, model_filter=None):
    """Get overall statistics, optionally filtered"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Build WHERE clause for filters
    where_clause = ""
    params = []
    
    if location_filter or model_filter:
        where_conditions = []
        if location_filter:
            where_conditions.append("p.location = ?")
            params.append(location_filter)
        if model_filter:
            where_conditions.append("p.model = ?")
            params.append(model_filter)
        where_clause = " WHERE " + " AND ".join(where_conditions)
    
    # Total printers
    query = 'SELECT COUNT(*) as total FROM printers p' + where_clause
    cursor.execute(query, params)
    total_printers = cursor.fetchone()['total']
    
    # Total pages printed (last 30 days) - FIXED CALCULATION
    where_parts = []
    subquery_params = []
    
    if location_filter:
        where_parts.append("p.location = ?")
        subquery_params.append(location_filter)
    if model_filter:
        where_parts.append("p.model = ?")
        subquery_params.append(model_filter)
    
    where_filter = " AND " + " AND ".join(where_parts) if where_parts else ""
    
    query = f'''
        SELECT COALESCE(SUM(pages_printed), 0) as total_pages
        FROM (
            SELECT 
                p.id,
                MAX(m.total_pages) - MIN(m.total_pages) as pages_printed
            FROM printers p
            JOIN metrics m ON p.id = m.printer_id
            WHERE m.timestamp >= datetime('now', '-30 days')
            AND m.total_pages IS NOT NULL
            {where_filter}
            GROUP BY p.id
        )
    '''
    
    cursor.execute(query, subquery_params)
    total_pages = cursor.fetchone()['total_pages'] or 0
    
    # Printers with low toner (<20%)
    query = '''
        SELECT COUNT(DISTINCT m.printer_id) as low_toner FROM metrics m
        JOIN printers p ON m.printer_id = p.id
        WHERE m.id IN (SELECT MAX(id) FROM metrics GROUP BY printer_id)
        AND m.toner_level_pct < 20
        AND m.toner_level_pct IS NOT NULL
    '''
    
    if where_clause:
        query += ' AND ' + where_clause.replace(' WHERE ', '')
    
    cursor.execute(query, params)
    low_toner = cursor.fetchone()['low_toner']
    
    conn.close()
    
    return {
        'total_printers': total_printers,
        'total_pages_30_days': total_pages,
        'low_toner_count': low_toner
    }

def update_printer_location(printer_id, location):
    """Update printer location"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('UPDATE printers SET location = ? WHERE id = ?', (location, printer_id))
    conn.commit()
    conn.close()

def delete_printer(printer_id):
    """Delete a printer and all its metrics"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM metrics WHERE printer_id = ?', (printer_id,))
    cursor.execute('DELETE FROM printers WHERE id = ?', (printer_id,))
    conn.commit()
    conn.close()

# ============================================================================
# PDF GENERATION FUNCTIONS
# ============================================================================

def generate_pdf_report(location_filter=None, model_filter=None, days=30):
    """Generate PDF report of all printers"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    # Container for PDF elements
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=12,
        spaceBefore=12
    )
    
    # Title
    title_text = "Printer Monitoring Report"
    if location_filter or model_filter:
        filters = []
        if location_filter:
            filters.append(f"Location: {location_filter}")
        if model_filter:
            filters.append(f"Model: {model_filter}")
        title_text += f"<br/><font size=12>({', '.join(filters)})</font>"
    
    elements.append(Paragraph(title_text, title_style))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Summary Statistics
    stats = get_total_stats(location_filter, model_filter)
    elements.append(Paragraph("Summary Statistics", heading_style))
    
    stats_data = [
        ['Metric', 'Value'],
        ['Total Printers', str(stats['total_printers'])],
        [f'Pages Printed ({days} days)', f"{stats['total_pages_30_days']:,}"],
        ['Low Toner Alerts', str(stats['low_toner_count'])]
    ]
    
    stats_table = Table(stats_data, colWidths=[3*inch, 2*inch])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]))
    
    elements.append(stats_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Printer Details
    elements.append(Paragraph("Printer Details", heading_style))
    
    printers = get_all_printers(location_filter, model_filter)
    
    if printers:
        printer_data = [['Name', 'Location', 'IP', 'Model', 'Pages', 'Toner', 'Drum']]
        
        for printer in printers:
            toner_display = f"{printer['toner_level_pct']}%" if printer['toner_level_pct'] is not None else (printer['toner_status'] if printer['toner_status'] else 'N/A')
            drum_display = f"{printer['drum_level_pct']}%" if printer['drum_level_pct'] is not None else 'N/A'
            
            printer_data.append([
                printer['name'][:20],  # Truncate if too long
                printer['location'][:15],
                printer['ip'],
                (printer['model'][:20] if printer['model'] else 'Unknown'),
                f"{printer['total_pages']:,}" if printer['total_pages'] else 'N/A',
                toner_display,
                drum_display
            ])
        
        printer_table = Table(printer_data, colWidths=[1.3*inch, 1*inch, 0.9*inch, 1.3*inch, 0.8*inch, 0.6*inch, 0.6*inch])
        printer_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        
        elements.append(printer_table)
    else:
        elements.append(Paragraph("No printers found.", styles['Normal']))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_usage_summary_pdf(days_periods=[30, 90, 120, 365], location_filter=None, model_filter=None):
    """
    Generate PDF report showing usage summary for multiple time periods
    
    Args:
        days_periods: List of day periods to report on (default: [30, 90, 120, 365])
        location_filter: Optional location filter
        model_filter: Optional model filter
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=12,
        spaceBefore=12
    )
    
    # Title
    title_text = "Printer Usage Summary Report"
    if location_filter or model_filter:
        filters = []
        if location_filter:
            filters.append(f"Location: {location_filter}")
        if model_filter:
            filters.append(f"Model: {model_filter}")
        title_text += f"<br/><font size=12>({', '.join(filters)})</font>"
    
    elements.append(Paragraph(title_text, title_style))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Get data for each period
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Summary table data
    summary_data = [['Period', 'Total Pages Printed', 'Active Printers', 'Avg Pages/Printer']]
    
    for days in days_periods:
        # Build WHERE clause for filters
        where_parts = []
        params = []
        
        if location_filter:
            where_parts.append("p.location = ?")
            params.append(location_filter)
        if model_filter:
            where_parts.append("p.model = ?")
            params.append(model_filter)
        
        where_clause = " AND " + " AND ".join(where_parts) if where_parts else ""
        
        # Get total pages for period
        query = f'''
            SELECT 
                COUNT(DISTINCT printer_id) as active_printers,
                COALESCE(SUM(pages_printed), 0) as total_pages
            FROM (
                SELECT 
                    p.id as printer_id,
                    MAX(m.total_pages) - MIN(m.total_pages) as pages_printed
                FROM printers p
                JOIN metrics m ON p.id = m.printer_id
                WHERE m.timestamp >= datetime('now', '-' || ? || ' days')
                AND m.total_pages IS NOT NULL
                {where_clause}
                GROUP BY p.id
            ) AS subquery
        '''
        
        cursor.execute(query, [days] + params)
        result = cursor.fetchone()
        
        active_printers = result['active_printers'] or 0
        total_pages = result['total_pages'] or 0
        avg_pages = int(total_pages / active_printers) if active_printers > 0 else 0
        
        summary_data.append([
            f"Last {days} Days",
            f"{total_pages:,}",
            str(active_printers),
            f"{avg_pages:,}"
        ])
    
    # Create summary table
    elements.append(Paragraph("Usage Summary", heading_style))
    
    summary_table = Table(summary_data, colWidths=[1.5*inch, 2*inch, 1.5*inch, 2*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Detailed breakdown by printer for each period
    elements.append(Paragraph("Detailed Breakdown by Printer", heading_style))
    
    for days in days_periods:
        elements.append(Paragraph(f"Last {days} Days", styles['Heading3']))
        
        # Build WHERE clause for filters
        where_parts = []
        params = [days]
        
        if location_filter:
            where_parts.append("p.location = ?")
            params.append(location_filter)
        if model_filter:
            where_parts.append("p.model = ?")
            params.append(model_filter)
        
        where_clause = " AND " + " AND ".join(where_parts) if where_parts else ""
        
        # Get printer breakdown - NOW WITH IP ADDRESS
        query = f'''
            SELECT 
                p.name,
                p.ip,
                p.location,
                MAX(m.total_pages) - MIN(m.total_pages) as pages_printed
            FROM printers p
            JOIN metrics m ON p.id = m.printer_id
            WHERE m.timestamp >= datetime('now', '-' || ? || ' days')
            AND m.total_pages IS NOT NULL
            {where_clause}
            GROUP BY p.id, p.name, p.ip, p.location
            HAVING pages_printed > 0
            ORDER BY pages_printed DESC
        '''
        
        cursor.execute(query, params)
        printers = cursor.fetchall()
        
        if printers:
            # Updated header to include IP Address
            printer_data = [['Printer', 'IP Address', 'Location', 'Pages Printed']]
            
            for printer in printers:
                printer_data.append([
                    printer['name'][:22],
                    printer['ip'],
                    printer['location'][:18],
                    f"{printer['pages_printed']:,}"
                ])
            
            # Updated column widths to accommodate IP address
            printer_table = Table(printer_data, colWidths=[2.0*inch, 1.2*inch, 1.5*inch, 1.3*inch])
            printer_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (3, 0), (3, -1), 'RIGHT'),  # Right-align pages printed
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('TOPPADDING', (0, 1), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ]))
            
            elements.append(printer_table)
        else:
            elements.append(Paragraph("No usage data for this period.", styles['Normal']))
        
        elements.append(Spacer(1, 0.2*inch))
    
    conn.close()
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

# ============================================================================
# ROUTES
# ============================================================================

@app.route('/')
def index():
    """Main dashboard"""
    # Get filter parameters
    location_filter = request.args.get('location')
    model_filter = request.args.get('model')
    
    # Get data with filters
    printers = get_all_printers(location_filter, model_filter)
    stats = get_total_stats(location_filter, model_filter)
    
    # Get filter options
    locations = get_all_locations()
    models = get_all_models()
    
    return render_template('dashboard.html', 
                         printers=printers, 
                         stats=stats,
                         locations=locations,
                         models=models,
                         current_location=location_filter,
                         current_model=model_filter)

@app.route('/printer/<int:printer_id>')
def printer_detail(printer_id):
    """Printer detail page"""
    # Get period from query parameter, default to 30 days
    period = request.args.get('period', '30')
    try:
        days = int(period)
    except ValueError:
        days = 30
    
    printer, latest_metrics = get_printer_details(printer_id)
    history = get_printer_history(printer_id, days)
    usage_30 = get_printer_usage(printer_id, 30)
    usage_7 = get_printer_usage(printer_id, 7)
    
    return render_template('printer_detail.html', 
                         printer=printer, 
                         latest_metrics=latest_metrics,
                         history=history,
                         usage_30=usage_30,
                         usage_7=usage_7,
                         current_period=days)

@app.route('/api/printer/<int:printer_id>/chart-data')
def printer_chart_data(printer_id):
    """Get chart data for a printer"""
    # Get period from query parameter
    period = request.args.get('period', '30')
    try:
        days = int(period)
    except ValueError:
        days = 30
    
    history = get_printer_history(printer_id, days)
    
    # Prepare data for charts
    labels = []
    pages = []
    toner = []
    drum = []
    
    for record in history:
        labels.append(record['timestamp'])
        pages.append(record['total_pages'] if record['total_pages'] else 0)
        toner.append(record['toner_level_pct'] if record['toner_level_pct'] else None)
        drum.append(record['drum_level_pct'] if record['drum_level_pct'] else None)
    
    return jsonify({
        'labels': labels,
        'pages': pages,
        'toner': toner,
        'drum': drum
    })

@app.route('/api/printer/<int:printer_id>/update-location', methods=['POST'])
def update_location(printer_id):
    """Update printer location via API"""
    data = request.get_json()
    location = data.get('location', '')
    
    update_printer_location(printer_id, location)
    
    return jsonify({'success': True, 'location': location})

@app.route('/api/printer/<int:printer_id>/delete', methods=['POST'])
def api_delete_printer(printer_id):
    """Delete printer via API"""
    delete_printer(printer_id)
    return jsonify({'success': True})

@app.route('/download-report')
def download_report():
    """Download PDF report"""
    location_filter = request.args.get('location')
    model_filter = request.args.get('model')
    days = request.args.get('days', '30')
    
    try:
        days_int = int(days)
    except ValueError:
        days_int = 30
    
    pdf_buffer = generate_pdf_report(location_filter, model_filter, days_int)
    
    # Generate filename
    filename = f"printer_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

@app.route('/download-usage-summary')
def download_usage_summary():
    """Download usage summary PDF report for multiple time periods"""
    location_filter = request.args.get('location')
    model_filter = request.args.get('model')
    
    # Get custom periods if provided, otherwise use defaults
    periods_param = request.args.get('periods', '30,90,120,365')
    try:
        periods = [int(p.strip()) for p in periods_param.split(',')]
    except ValueError:
        periods = [30, 90, 120, 365]
    
    pdf_buffer = generate_usage_summary_pdf(periods, location_filter, model_filter)
    
    # Generate filename
    filename = f"printer_usage_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

@app.route('/settings')
def settings():
    """Settings page"""
    printers = get_all_printers()
    return render_template('settings.html', printers=printers)

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("="*80)
    print("PRINTER MONITORING WEB DASHBOARD")
    print("="*80)
    print("\nStarting web server...")
    print("Open your browser to: http://localhost:5000")
    print("\nPress Ctrl+C to stop the server")
    print("="*80)
    
    app.run(debug=True, host='0.0.0.0', port=5000)