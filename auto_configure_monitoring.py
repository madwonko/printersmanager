"""
Auto-configure printer monitoring from network discovery
Discovers printers and adds them to printer_monitor.py configuration
Can read subnets from a text file with locations
"""

import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import sys
import asyncio
import sqlite3
import os

try:
    import pysnmp.hlapi.asyncio as hlapi
except ImportError:
    print("Error: pysnmp not installed")
    print("Install with: python -m pip install pysnmp")
    sys.exit(1)

# ============================================================================
# CONFIGURATION
# ============================================================================

DEFAULT_SUBNET = "10.164.1.0/24"  # Used if no file specified
SUBNETS_FILE = "subnets.txt"  # Default subnets file
SNMP_COMMUNITY = "public"
SNMP_TIMEOUT = 2
MAX_THREADS = 20
DATABASE_FILE = "printer_monitoring.db"

OIDS = {
    'sysDescr': '1.3.6.1.2.1.1.1.0',
    'sysName': '1.3.6.1.2.1.1.5.0',
    'model': '1.3.6.1.2.1.25.3.2.1.3.1',
    'total_pages': '1.3.6.1.2.1.43.10.2.1.4.1.1',
}

# ============================================================================
# SUBNET FILE FUNCTIONS
# ============================================================================

def read_subnets_from_file(filename):
    """
    Read subnets from a text file with optional location
    
    File format (one subnet per line):
        10.164.1.0/24,Main Office
        192.168.1.0/24,Home Office
        # This is a comment
        172.16.0.0/16,Branch A
        10.0.0.0/24    (location will be "Auto-discovered")
    
    Args:
        filename: Path to subnets file
    
    Returns:
        List of tuples: [(subnet_string, location), ...]
    """
    subnets = []
    
    if not os.path.exists(filename):
        print(f"Subnets file not found: {filename}")
        return []
    
    try:
        with open(filename, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Parse subnet and optional location
                parts = [p.strip() for p in line.split(',', 1)]
                subnet = parts[0]
                location = parts[1] if len(parts) > 1 else "Auto-discovered"
                
                # Validate subnet format
                try:
                    ipaddress.ip_network(subnet, strict=False)
                    subnets.append((subnet, location))
                    print(f"  ✓ Added subnet: {subnet} → {location}")
                except ValueError as e:
                    print(f"  ✗ Invalid subnet on line {line_num}: {subnet} - {e}")
        
        return subnets
        
    except Exception as e:
        print(f"Error reading file {filename}: {e}")
        return []

def create_sample_subnets_file(filename):
    """Create a sample subnets.txt file"""
    sample_content = """# Subnets to scan for printers
# Format: subnet,location
# Location is optional - defaults to "Auto-discovered" if not specified
# Lines starting with # are comments

# Example subnets with locations:
10.164.1.0/24,Main Office
10.164.2.0/24,North Branch
192.168.1.0/24,Home Office

# Example without location (will use "Auto-discovered"):
# 172.16.0.0/24

# Add your subnets below:
"""
    
    try:
        with open(filename, 'w') as f:
            f.write(sample_content)
        print(f"Created sample subnets file: {filename}")
        print("Edit this file and add your subnets, then run the script again.")
        return True
    except Exception as e:
        print(f"Error creating file: {e}")
        return False

# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

def init_database():
    """Initialize database if it doesn't exist"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
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
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_metrics_timestamp 
        ON metrics(timestamp)
    ''')
    
    conn.commit()
    conn.close()

def add_printer_to_db(printer):
    """Add discovered printer to database"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO printers (ip, name, location, model)
            VALUES (?, ?, ?, ?)
        ''', (
            printer['ip'],
            printer['name'],
            printer.get('location', 'Auto-discovered'),
            printer.get('model', 'Unknown')
        ))
        conn.commit()
        print(f"  ✓ Added {printer['name']} ({printer['location']}) to database")
        return True
    except sqlite3.IntegrityError:
        # Printer already exists, update it (including location if provided)
        cursor.execute('''
            UPDATE printers 
            SET name = ?, model = ?, location = ?
            WHERE ip = ?
        ''', (printer['name'], printer.get('model'), printer.get('location'), printer['ip']))
        conn.commit()
        print(f"  ↻ Updated {printer['name']} ({printer['location']}) in database")
        return False
    finally:
        conn.close()

def get_existing_printers():
    """Get list of printers already in database"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT ip, name, location, model FROM printers')
    printers = cursor.fetchall()
    
    conn.close()
    return printers

# ============================================================================
# SNMP DISCOVERY FUNCTIONS
# ============================================================================

async def snmp_get(ip, oid, timeout=2):
    """Query a single SNMP OID"""
    try:
        snmpEngine = hlapi.SnmpEngine()
        errorIndication, errorStatus, errorIndex, varBinds = await hlapi.getCmd(
            snmpEngine,
            hlapi.CommunityData(SNMP_COMMUNITY, mpModel=0),
            hlapi.UdpTransportTarget((ip, 161), timeout=timeout),
            hlapi.ContextData(),
            hlapi.ObjectType(hlapi.ObjectIdentity(oid))
        )
        
        if errorIndication or errorStatus:
            return None
        
        value = str(varBinds[0][1])
        if "No Such" not in value and value.strip():
            return value
        return None
        
    except Exception:
        return None

async def check_if_printer(ip, location="Auto-discovered"):
    """Check if an IP is a printer"""
    sys_descr = await snmp_get(ip, OIDS['sysDescr'], SNMP_TIMEOUT)
    
    if not sys_descr:
        return None
    
    printer_keywords = [
        'printer', 'print', 'laser', 'inkjet', 'multifunction',
        'hp', 'canon', 'epson', 'brother', 'xerox', 'ricoh',
        'samsung', 'lexmark', 'kyocera', 'sharp', 'dell',
        'konica', 'oki', 'toshiba', 'copystation', 'mfp'
    ]
    
    is_printer = any(keyword in sys_descr.lower() for keyword in printer_keywords)
    
    if is_printer:
        name = await snmp_get(ip, OIDS['sysName'], SNMP_TIMEOUT)
        model = await snmp_get(ip, OIDS['model'], SNMP_TIMEOUT)
        total_pages = await snmp_get(ip, OIDS['total_pages'], SNMP_TIMEOUT)
        
        return {
            'ip': ip,
            'name': name if name else model if model else f'Printer-{ip}',
            'description': sys_descr,
            'model': model if model else 'Unknown',
            'total_pages': total_pages if total_pages else 'N/A',
            'location': location  # Include location from subnet file
        }
    
    return None

def scan_ip_sync(ip, location="Auto-discovered"):
    """Synchronous wrapper for async scan"""
    ip_str = str(ip)
    try:
        result = asyncio.run(check_if_printer(ip_str, location))
        if result:
            print(f"✓ Found printer at {ip_str} ({location})")
            return result
    except Exception:
        pass
    return None

def ping_sweep_windows(subnet):
    """Quick ping sweep"""
    import subprocess
    
    print(f"Ping sweep: {subnet}")
    
    network = ipaddress.ip_network(subnet, strict=False)
    live_hosts = []
    
    def ping_ip(ip):
        ip_str = str(ip)
        try:
            result = subprocess.run(
                ['ping', '-n', '1', '-w', '100', ip_str],
                capture_output=True,
                timeout=2
            )
            if result.returncode == 0:
                return ip_str
        except:
            pass
        return None
    
    with ThreadPoolExecutor(max_workers=100) as executor:
        futures = [executor.submit(ping_ip, ip) for ip in network.hosts()]
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                live_hosts.append(result)
    
    print(f"  Found {len(live_hosts)} live hosts in {subnet}")
    return live_hosts

def scan_subnet(subnet, location="Auto-discovered", max_threads=20):
    """Scan a single subnet for printers"""
    print("\n" + "-"*80)
    print(f"Scanning subnet: {subnet} ({location})")
    print("-"*80)
    
    # Ping sweep first
    live_hosts = ping_sweep_windows(subnet)
    
    if not live_hosts:
        print(f"  No live hosts found in {subnet}")
        return []
    
    print(f"  Checking {len(live_hosts)} hosts for SNMP printers...")
    
    printers = []
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        future_to_ip = {executor.submit(scan_ip_sync, ip, location): ip for ip in live_hosts}
        
        for future in as_completed(future_to_ip):
            try:
                result = future.result()
                if result:
                    printers.append(result)
            except Exception:
                pass
    
    print(f"  Found {len(printers)} printer(s) in {subnet}")
    
    return printers

def scan_multiple_subnets(subnet_list, max_threads=20):
    """
    Scan multiple subnets and combine results
    
    Args:
        subnet_list: List of tuples [(subnet, location), ...]
    """
    print("="*80)
    print("PRINTER DISCOVERY & DATABASE POPULATION")
    print("="*80)
    print(f"Scanning {len(subnet_list)} subnet(s)")
    print(f"Database: {DATABASE_FILE}")
    print("="*80)
    
    all_printers = []
    
    for subnet, location in subnet_list:
        printers = scan_subnet(subnet, location, max_threads)
        all_printers.extend(printers)
    
    print(f"\n{'='*80}")
    print(f"SCAN COMPLETE - Found {len(all_printers)} total printer(s)")
    print("="*80)
    
    return all_printers

# ============================================================================
# REPORTING
# ============================================================================

def print_discovered_printers(printers):
    """Print discovered printers"""
    if not printers:
        print("\nNo printers found.")
        return
    
    print("\n" + "="*80)
    print("DISCOVERED PRINTERS")
    print("="*80)
    
    for i, printer in enumerate(printers, 1):
        print(f"\nPrinter {i}:")
        print(f"  IP: {printer['ip']}")
        print(f"  Name: {printer['name']}")
        print(f"  Location: {printer['location']}")
        print(f"  Model: {printer['model']}")
        print(f"  Total Pages: {printer['total_pages']}")
    
    print("\n" + "="*80)

def print_database_summary():
    """Print summary of printers in database"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM printers')
    count = cursor.fetchone()[0]
    
    print("\n" + "="*80)
    print("DATABASE SUMMARY")
    print("="*80)
    print(f"Total printers in database: {count}")
    print("="*80)
    
    # Group by location
    cursor.execute('''
        SELECT location, COUNT(*) as count 
        FROM printers 
        GROUP BY location 
        ORDER BY location
    ''')
    locations = cursor.fetchall()
    
    print("\nPrinters by Location:")
    for location, count in locations:
        print(f"  {location}: {count} printer(s)")
    
    print("\nAll Printers:")
    cursor.execute('SELECT ip, name, location, model FROM printers ORDER BY location, name')
    printers = cursor.fetchall()
    
    current_location = None
    for ip, name, location, model in printers:
        if location != current_location:
            print(f"\n  [{location}]")
            current_location = location
        print(f"    {name} ({ip}) - {model}")
    
    print("\n" + "="*80)
    
    conn.close()

def generate_config_snippet():
    """Generate Python config snippet for manual use"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT ip, name, location FROM printers ORDER BY location, name')
    printers = cursor.fetchall()
    
    print("\n" + "="*80)
    print("PYTHON CONFIGURATION SNIPPET")
    print("="*80)
    print("\nIf you want to manually configure printer_monitor.py:")
    print("\nPRINTERS = [")
    
    current_location = None
    for ip, name, location in printers:
        if location != current_location:
            if current_location is not None:
                print()
            print(f"    # {location}")
            current_location = location
        print(f'    {{"ip": "{ip}", "name": "{name}", "location": "{location}"}},')
    
    print("]")
    print("\n" + "="*80)
    
    conn.close()

# ============================================================================
# MAIN
# ============================================================================

def print_usage():
    """Print usage information"""
    print("""
Printer Auto-Configuration - Usage:

python auto_configure_monitoring.py                    - Use subnets.txt file
python auto_configure_monitoring.py <subnet>           - Scan single subnet
python auto_configure_monitoring.py --file <filename>  - Use custom file
python auto_configure_monitoring.py --create           - Create sample subnets.txt

Examples:
    python auto_configure_monitoring.py
    python auto_configure_monitoring.py 192.168.1.0/24
    python auto_configure_monitoring.py --file my_networks.txt
    python auto_configure_monitoring.py --create

Subnets file format (one subnet per line):
    10.164.1.0/24,Main Office
    192.168.1.0/24,Branch A
    172.16.0.0/16,North Location
    # Comments start with #
    
Note: Location is optional. If not specified, "Auto-discovered" will be used.
""")

def main():
    """Main program"""
    # Initialize database
    print("Initializing database...")
    init_database()
    
    # Show existing printers
    existing = get_existing_printers()
    if existing:
        print(f"\nDatabase currently has {len(existing)} printer(s)")
        locations = {}
        for ip, name, location, model in existing:
            if location not in locations:
                locations[location] = []
            locations[location].append(f"{name} ({ip})")
        
        for location, printers in sorted(locations.items()):
            print(f"\n  [{location}]")
            for printer in printers:
                print(f"    - {printer}")
    
    # Determine what to scan
    subnet_list = []  # List of tuples: (subnet, location)
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--create':
            create_sample_subnets_file(SUBNETS_FILE)
            return
        elif sys.argv[1] == '--help' or sys.argv[1] == '-h':
            print_usage()
            return
        elif sys.argv[1] == '--file':
            if len(sys.argv) > 2:
                filename = sys.argv[2]
                print(f"\nReading subnets from: {filename}")
                subnet_list = read_subnets_from_file(filename)
            else:
                print("Error: --file requires a filename")
                print_usage()
                return
        else:
            # Single subnet on command line
            subnet = sys.argv[1]
            try:
                ipaddress.ip_network(subnet, strict=False)
                subnet_list = [(subnet, "Auto-discovered")]
                print(f"\nScanning subnet: {subnet}")
            except ValueError:
                print(f"Error: Invalid subnet format: {subnet}")
                print_usage()
                return
    else:
        # Try to read from default subnets file
        if os.path.exists(SUBNETS_FILE):
            print(f"\nReading subnets from: {SUBNETS_FILE}")
            subnet_list = read_subnets_from_file(SUBNETS_FILE)
        else:
            print(f"\nSubnets file not found: {SUBNETS_FILE}")
            response = input("Create sample subnets.txt file? [Y/n]: ").strip().lower()
            if response in ['', 'y', 'yes']:
                create_sample_subnets_file(SUBNETS_FILE)
            else:
                print(f"\nUsing default subnet: {DEFAULT_SUBNET}")
                subnet_list = [(DEFAULT_SUBNET, "Auto-discovered")]
    
    if not subnet_list:
        print("\nNo subnets to scan!")
        return
    
    # Scan for printers
    printers = scan_multiple_subnets(subnet_list, MAX_THREADS)
    
    # Display discovered printers
    print_discovered_printers(printers)
    
    if not printers:
        print("\nNo new printers found.")
        return
    
    # Ask to add to database
    print(f"\n{'='*80}")
    response = input(f"Add {len(printers)} printer(s) to database? [Y/n]: ").strip().lower()
    
    if response in ['', 'y', 'yes']:
        print("\nAdding printers to database...")
        new_count = 0
        for printer in printers:
            if add_printer_to_db(printer):
                new_count += 1
        
        print(f"\n✓ Added {new_count} new printer(s) to database")
        print(f"✓ Updated {len(printers) - new_count} existing printer(s)")
        
        # Show database summary
        print_database_summary()
        
        # Generate config snippet
        generate_config_snippet()
        
        print("\n" + "="*80)
        print("NEXT STEPS")
        print("="*80)
        print("\nYou can now run printer monitoring:")
        print("  python printer_monitor.py monitor")
        print("\nOr view the web dashboard:")
        print("  python printer_web_dashboard.py")
        print("  Then open: http://localhost:5000")
    else:
        print("\nSkipped adding printers to database.")

if __name__ == "__main__":
    main()