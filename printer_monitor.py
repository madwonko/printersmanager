"""
Printer Usage Monitoring System - Windows & Linux Compatible
Monitors network printers via SNMP and tracks usage metrics
"""

import sqlite3
from datetime import datetime
import time
import sys
import asyncio

# Try to import pysnmp
try:
    import pysnmp.hlapi.asyncio as hlapi
except ImportError:
    print("Error: pysnmp library not installed")
    print("Install with: python -m pip install pysnmp")
    sys.exit(1)

# ============================================================================
# CONFIGURATION
# ============================================================================

SNMP_COMMUNITY = "public"
DATABASE_FILE = "printer_monitoring.db"

# ============================================================================
# DATABASE SETUP
# ============================================================================

def init_database():
    """Initialize SQLite database with required tables"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # Create printers table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS printers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            location TEXT,
            model TEXT,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create metrics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            printer_id INTEGER NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_pages INTEGER,
            toner_level_pct INTEGER,
            toner_status TEXT,
            drum_level_pct INTEGER,
            device_status INTEGER,
            FOREIGN KEY (printer_id) REFERENCES printers (id)
        )
    ''')
    
    # Create index for faster queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_metrics_timestamp 
        ON metrics(timestamp)
    ''')
    
    conn.commit()
    conn.close()
    print(f"Database initialized: {DATABASE_FILE}")

# ============================================================================
# SNMP FUNCTIONS
# ============================================================================

async def snmp_get(ip, oid, timeout=2):
    """
    Query a single SNMP OID from a device using async API
    
    Args:
        ip: IP address of the printer
        oid: SNMP OID to query
        timeout: Timeout in seconds
    
    Returns:
        Value if successful, None otherwise
    """
    try:
        snmpEngine = hlapi.SnmpEngine()
        errorIndication, errorStatus, errorIndex, varBinds = await hlapi.getCmd(
            snmpEngine,
            hlapi.CommunityData(SNMP_COMMUNITY, mpModel=0),
            hlapi.UdpTransportTarget((ip, 161), timeout=timeout),
            hlapi.ContextData(),
            hlapi.ObjectType(hlapi.ObjectIdentity(oid))
        )
        
        if errorIndication:
            return None
        elif errorStatus:
            return None
        else:
            value = str(varBinds[0][1])
            if "No Such" not in value and value.strip():
                return value
            return None
    except Exception:
        return None

async def get_supply_info(ip, index):
    """Get supply information for a specific index"""
    base_oids = {
        'description': f'1.3.6.1.2.1.43.11.1.1.6.1.{index}',
        'type': f'1.3.6.1.2.1.43.11.1.1.5.1.{index}',
        'unit': f'1.3.6.1.2.1.43.11.1.1.7.1.{index}',
        'max_capacity': f'1.3.6.1.2.1.43.11.1.1.8.1.{index}',
        'current_level': f'1.3.6.1.2.1.43.11.1.1.9.1.{index}',
    }
    
    supply = {}
    for key, oid in base_oids.items():
        value = await snmp_get(ip, oid)
        if value:
            supply[key] = value
    
    return supply if supply else None

async def calculate_toner_percentage(current, max_capacity):
    """Calculate toner percentage from current and max values"""
    try:
        current_val = int(current)
        max_val = int(max_capacity)
        
        # Handle special values
        if current_val == -3:
            return None, "OK"  # Toner OK but level not reported
        elif current_val == -2:
            return None, "Unknown"
        elif current_val < 0:
            return None, f"Status: {current_val}"
        
        # Calculate percentage if we have valid values
        if max_val > 0 and max_val != -2:
            percentage = int((current_val / max_val) * 100)
            return percentage, None
        
        return None, "Cannot calculate"
        
    except (ValueError, ZeroDivisionError):
        return None, "Error"

async def get_printer_metrics_async(ip):
    """
    Get all metrics for a printer asynchronously
    
    Args:
        ip: IP address of the printer
    
    Returns:
        Dictionary with metrics or None if failed
    """
    print(f"\nQuerying printer at {ip}...")
    
    metrics = {
        'total_pages': None,
        'model': None,
        'device_status': None,
        'toner_level_pct': None,
        'toner_status': None,
        'drum_level_pct': None,
    }
    
    # Get basic info
    total_pages = await snmp_get(ip, '1.3.6.1.2.1.43.10.2.1.4.1.1')
    if total_pages:
        try:
            metrics['total_pages'] = int(total_pages)
            print(f"  Total Pages: {total_pages}")
        except ValueError:
            pass
    
    model = await snmp_get(ip, '1.3.6.1.2.1.25.3.2.1.3.1')
    if model:
        metrics['model'] = model
        print(f"  Model: {model}")
    
    device_status = await snmp_get(ip, '1.3.6.1.2.1.25.3.2.1.5.1')
    if device_status:
        try:
            metrics['device_status'] = int(device_status)
        except ValueError:
            pass
    
    # Get supply information
    # Check first few indices for toner and drum
    for index in range(1, 10):
        supply = await get_supply_info(ip, index)
        if not supply:
            continue
        
        desc = supply.get('description', '').lower()
        current = supply.get('current_level')
        max_cap = supply.get('max_capacity')
        
        if not current or not max_cap:
            continue
        
        # Check if this is toner
        if 'toner' in desc and 'black' in desc:
            pct, status = await calculate_toner_percentage(current, max_cap)
            if pct is not None:
                metrics['toner_level_pct'] = pct
                print(f"  Black Toner: {pct}%")
            elif status:
                metrics['toner_status'] = status
                print(f"  Black Toner: {status}")
        
        # Check if this is drum
        elif 'drum' in desc:
            pct, status = await calculate_toner_percentage(current, max_cap)
            if pct is not None:
                metrics['drum_level_pct'] = pct
                print(f"  Drum Unit: {pct}%")
    
    return metrics if any(v is not None for v in metrics.values()) else None

def get_printer_metrics(ip):
    """Synchronous wrapper for async get_printer_metrics"""
    try:
        return asyncio.run(get_printer_metrics_async(ip))
    except Exception as e:
        print(f"  Error getting metrics: {e}")
        return None

# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

def get_printers_from_db():
    """Get list of printers from database"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT ip, name, location FROM printers ORDER BY name')
    db_printers = cursor.fetchall()
    
    conn.close()
    
    # Convert to the format expected by monitor_printers
    printers = []
    for ip, name, location in db_printers:
        printers.append({
            'ip': ip,
            'name': name,
            'location': location
        })
    
    return printers

def get_or_create_printer(ip, name, location, model=None):
    """
    Get printer ID from database or create new entry
    
    Args:
        ip: Printer IP address
        name: Printer name
        location: Printer location
        model: Printer model (optional)
    
    Returns:
        Printer ID
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # Try to find existing printer
    cursor.execute('SELECT id FROM printers WHERE ip = ?', (ip,))
    result = cursor.fetchone()
    
    if result:
        printer_id = result[0]
        # Update model if we got it and it's not set
        if model:
            cursor.execute('UPDATE printers SET model = ? WHERE id = ? AND model IS NULL',
                         (model, printer_id))
            conn.commit()
    else:
        # Create new printer entry
        cursor.execute('''
            INSERT INTO printers (ip, name, location, model)
            VALUES (?, ?, ?, ?)
        ''', (ip, name, location, model))
        conn.commit()
        printer_id = cursor.lastrowid
        print(f"Added new printer to database: {name} ({ip})")
    
    conn.close()
    return printer_id

def save_metrics(printer_id, metrics):
    """
    Save metrics to database
    
    Args:
        printer_id: Printer ID in database
        metrics: Dictionary of metrics
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO metrics 
        (printer_id, total_pages, toner_level_pct, toner_status, 
         drum_level_pct, device_status)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        printer_id,
        metrics.get('total_pages'),
        metrics.get('toner_level_pct'),
        metrics.get('toner_status'),
        metrics.get('drum_level_pct'),
        metrics.get('device_status')
    ))
    
    conn.commit()
    conn.close()

# ============================================================================
# REPORTING FUNCTIONS
# ============================================================================

def generate_current_status_report():
    """Generate a report of current printer status"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    print("\n" + "="*80)
    print("CURRENT PRINTER STATUS REPORT")
    print("="*80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Get latest metrics for each printer
    cursor.execute('''
        SELECT 
            p.name,
            p.location,
            p.ip,
            p.model,
            m.total_pages,
            m.toner_level_pct,
            m.toner_status,
            m.drum_level_pct,
            m.timestamp
        FROM printers p
        LEFT JOIN metrics m ON p.id = m.printer_id
        WHERE m.id IN (
            SELECT MAX(id) FROM metrics GROUP BY printer_id
        ) OR m.id IS NULL
        ORDER BY p.location, p.name
    ''')
    
    results = cursor.fetchall()
    
    if not results:
        print("\nNo data available yet. Run a monitoring cycle first.")
    
    current_location = None
    for row in results:
        name, location, ip, model, pages, toner_pct, toner_status, drum_pct, timestamp = row
        
        # Print location header if changed
        if location != current_location:
            print(f"\n[{location}]")
            print("-" * 80)
            current_location = location
        
        print(f"\nPrinter: {name}")
        print(f"  IP: {ip}")
        if model:
            print(f"  Model: {model}")
        print(f"  Total Pages: {pages if pages else 'N/A'}")
        
        if toner_pct is not None:
            print(f"  Toner Level: {toner_pct}%")
        elif toner_status:
            print(f"  Toner Status: {toner_status}")
        else:
            print(f"  Toner: Not available")
            
        if drum_pct is not None:
            print(f"  Drum Level: {drum_pct}%")
            
        if timestamp:
            print(f"  Last Updated: {timestamp}")
    
    conn.close()
    print("\n" + "="*80)

def generate_usage_report(days=7):
    """
    Generate usage report for specified number of days
    
    Args:
        days: Number of days to report on
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    print("\n" + "="*80)
    print(f"PRINTER USAGE REPORT - LAST {days} DAYS")
    print("="*80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Get usage for each printer
    cursor.execute('''
        SELECT 
            p.name,
            p.location,
            MIN(m.total_pages) as start_pages,
            MAX(m.total_pages) as end_pages,
            MAX(m.total_pages) - MIN(m.total_pages) as pages_printed,
            COUNT(m.id) as readings,
            MIN(m.timestamp) as first_reading,
            MAX(m.timestamp) as last_reading
        FROM printers p
        JOIN metrics m ON p.id = m.printer_id
        WHERE m.timestamp >= datetime('now', '-' || ? || ' days')
        AND m.total_pages IS NOT NULL
        GROUP BY p.id, p.name, p.location
        ORDER BY p.location, pages_printed DESC
    ''', (days,))
    
    results = cursor.fetchall()
    total_pages = 0
    
    if not results:
        print(f"\nNo usage data available for the last {days} days.")
    
    current_location = None
    for row in results:
        name, location, start, end, printed, readings, first, last = row
        
        # Print location header if changed
        if location != current_location:
            print(f"\n[{location}]")
            print("-" * 80)
            current_location = location
        
        print(f"\nPrinter: {name}")
        print(f"  Pages Printed: {printed if printed else 0}")
        print(f"  Period: {first} to {last}")
        print(f"  Number of Readings: {readings}")
        if printed:
            total_pages += printed
    
    if total_pages > 0:
        print(f"\n{'='*80}")
        print(f"TOTAL PAGES PRINTED (ALL PRINTERS): {total_pages:,}")
    
    print("="*80)
    
    conn.close()

def generate_usage_summary_report(periods=[30, 90, 120, 365]):
    """
    Generate usage summary for multiple periods
    
    Args:
        periods: List of day periods to report on
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    print("\n" + "="*80)
    print(f"PRINTER USAGE SUMMARY REPORT")
    print("="*80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Summary table
    print("\nUSAGE SUMMARY:")
    print("-"*80)
    print(f"{'Period':<20} {'Total Pages':<20} {'Active Printers':<20} {'Avg/Printer':<20}")
    print("-"*80)
    
    for days in periods:
        cursor.execute('''
            SELECT 
                COUNT(DISTINCT m.printer_id) as active_printers,
                SUM(pages_printed) as total_pages
            FROM (
                SELECT 
                    m.printer_id,
                    MAX(m.total_pages) - MIN(m.total_pages) as pages_printed
                FROM metrics m
                WHERE m.timestamp >= datetime('now', '-' || ? || ' days')
                AND m.total_pages IS NOT NULL
                GROUP BY m.printer_id
            )
        ''', (days,))
        
        result = cursor.fetchone()
        active_printers = result[0] or 0
        total_pages = result[1] or 0
        avg_pages = int(total_pages / active_printers) if active_printers > 0 else 0
        
        print(f"Last {days} Days{'':<10} {total_pages:,}{'':<8} {active_printers}{'':<15} {avg_pages:,}")
    
    print("-"*80)
    
    # Detailed breakdown
    for days in periods:
        print(f"\n\nDETAILED BREAKDOWN - LAST {days} DAYS:")
        print("-"*80)
        print(f"{'Printer':<35} {'Location':<25} {'Pages Printed':<20}")
        print("-"*80)
        
        cursor.execute('''
            SELECT 
                p.name,
                p.location,
                MAX(m.total_pages) - MIN(m.total_pages) as pages_printed
            FROM metrics m
            JOIN printers p ON m.printer_id = p.id
            WHERE m.timestamp >= datetime('now', '-' || ? || ' days')
            AND m.total_pages IS NOT NULL
            GROUP BY m.printer_id, p.name, p.location
            HAVING pages_printed > 0
            ORDER BY pages_printed DESC
        ''', (days,))
        
        printers = cursor.fetchall()
        
        if printers:
            for name, location, pages in printers:
                print(f"{name[:34]:<35} {location[:24]:<25} {pages:,}")
        else:
            print("No usage data for this period.")
        
        print("-"*80)
    
    print("\n" + "="*80)
    
    conn.close()

def export_to_csv(filename="printer_report.csv", days=30):
    """
    Export metrics to CSV file
    
    Args:
        filename: Output CSV filename
        days: Number of days of data to export
    """
    import csv
    
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            p.name,
            p.location,
            p.ip,
            m.timestamp,
            m.total_pages,
            m.toner_level_pct,
            m.toner_status,
            m.drum_level_pct
        FROM printers p
        JOIN metrics m ON p.id = m.printer_id
        WHERE m.timestamp >= datetime('now', '-' || ? || ' days')
        ORDER BY p.location, p.name, m.timestamp
    ''', (days,))
    
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Printer', 'Location', 'IP', 'Timestamp', 'Total Pages', 
                        'Toner Level %', 'Toner Status', 'Drum Level %'])
        writer.writerows(cursor.fetchall())
    
    conn.close()
    print(f"\nData exported to {filename}")

# ============================================================================
# MAIN MONITORING FUNCTION
# ============================================================================

def monitor_printers():
    """Main function to monitor all configured printers"""
    
    # Get printers from database
    printers = get_printers_from_db()
    
    if not printers:
        print("\nNo printers in database!")
        print("Run: python auto_configure_monitoring.py")
        return
    
    print("\n" + "="*80)
    print("PRINTER MONITORING - STARTING COLLECTION")
    print("="*80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Monitoring {len(printers)} printers from database")
    
    for printer in printers:
        try:
            # Get metrics from printer
            metrics = get_printer_metrics(printer['ip'])
            
            if metrics:
                # Get or create printer in database
                printer_id = get_or_create_printer(
                    printer['ip'],
                    printer['name'],
                    printer['location'],
                    metrics.get('model')
                )
                
                # Save metrics
                save_metrics(printer_id, metrics)
                print(f"  ✓ Metrics saved for {printer['name']}")
            else:
                print(f"  ✗ Failed to get metrics for {printer['name']}")
                
        except Exception as e:
            print(f"  ✗ Error processing {printer['name']}: {e}")
    
    print("\n" + "="*80)
    print("MONITORING CYCLE COMPLETE")
    print("="*80)

# ============================================================================
# MAIN PROGRAM
# ============================================================================

def main():
    """Main program entry point"""
    
    # Initialize database
    init_database()
    
    # Check command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "monitor":
            # Single monitoring run
            monitor_printers()
            generate_current_status_report()
            
        elif command == "report":
            # Generate reports only
            generate_current_status_report()
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
            generate_usage_report(days)
            
        elif command == "export":
            # Export to CSV
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            filename = sys.argv[3] if len(sys.argv) > 3 else "printer_report.csv"
            export_to_csv(filename, days)
            
        elif command == "loop":
            # Continuous monitoring
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 3600  # Default 1 hour
            print(f"Starting continuous monitoring (interval: {interval} seconds)")
            print("Press Ctrl+C to stop")
            try:
                while True:
                    monitor_printers()
                    print(f"\nSleeping for {interval} seconds...")
                    time.sleep(interval)
            except KeyboardInterrupt:
                print("\n\nMonitoring stopped by user")
        
        elif command == "summary":
            # Generate usage summary
            periods = [30, 90, 120, 365]
            if len(sys.argv) > 2:
                # Custom periods from command line
                periods = [int(d) for d in sys.argv[2:]]
            generate_usage_summary_report(periods)
        
        else:
            print("Unknown command")
            print_usage()
    else:
        # Default: single monitoring run
        monitor_printers()
        generate_current_status_report()

def print_usage():
    """Print usage instructions"""
    print("""
Printer Monitoring System - Usage:

python printer_monitor.py                    - Run single monitoring cycle
python printer_monitor.py monitor            - Run single monitoring cycle with report
python printer_monitor.py report [days]      - Generate usage report (default: 7 days)
python printer_monitor.py export [days] [file] - Export to CSV (default: 30 days)
python printer_monitor.py loop [seconds]     - Continuous monitoring (default: 3600s)

Examples:
    python printer_monitor.py monitor
    python printer_monitor.py report 30
    python printer_monitor.py export 90 monthly_report.csv
    python printer_monitor.py loop 1800

To schedule automatic monitoring on Windows:
    1. Open Task Scheduler
    2. Create Basic Task
    3. Set trigger (e.g., daily at 9 AM)
    4. Action: Start a program
    5. Program: python
    6. Arguments: C:\\path\\to\\printer_monitor.py monitor
    7. Start in: C:\\path\\to\\

To schedule on Linux (crontab):
    0 * * * * cd /path/to/scripts && python3 printer_monitor.py monitor
""")

if __name__ == "__main__":
    main()