"""
Printer Discovery Script - Windows Working Version
"""

import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import sys
import asyncio

try:
    import pysnmp.hlapi.asyncio as hlapi
except ImportError:
    print("Error: pysnmp not installed")
    print("Install with: python -m pip install pysnmp")
    sys.exit(1)

# ============================================================================
# CONFIGURATION
# ============================================================================

SUBNET = "192.168.1.0/24"
SNMP_COMMUNITY = "public"
SNMP_TIMEOUT = 2
MAX_THREADS = 20

OIDS = {
    'sysDescr': '1.3.6.1.2.1.1.1.0',
    'sysName': '1.3.6.1.2.1.1.5.0',
    'model': '1.3.6.1.2.1.25.3.2.1.3.1',
    'total_pages': '1.3.6.1.2.1.43.10.2.1.4.1.1',
}

# ============================================================================
# SNMP FUNCTIONS
# ============================================================================

async def snmp_get(ip, oid, timeout=2):
    """Query a single SNMP OID using async API"""
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
        if "No Such" in value or not value.strip():
            return None
        return value
        
    except Exception:
        return None

async def check_if_printer(ip):
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
        # Get additional info
        name = await snmp_get(ip, OIDS['sysName'], SNMP_TIMEOUT)
        model = await snmp_get(ip, OIDS['model'], SNMP_TIMEOUT)
        total_pages = await snmp_get(ip, OIDS['total_pages'], SNMP_TIMEOUT)
        
        return {
            'ip': ip,
            'name': name if name else 'Unknown',
            'description': sys_descr,
            'model': model if model else 'Unknown',
            'total_pages': total_pages if total_pages else 'N/A'
        }
    
    return None

def scan_ip_sync(ip):
    """Synchronous wrapper for async scan"""
    ip_str = str(ip)
    try:
        result = asyncio.run(check_if_printer(ip_str))
        if result:
            print(f"✓ Found printer at {ip_str}")
            return result
    except Exception:
        pass
    return None

# ============================================================================
# SCANNING FUNCTIONS
# ============================================================================

def scan_subnet(subnet, max_threads=20):
    """Scan a subnet for printers"""
    print("="*80)
    print("PRINTER DISCOVERY SCAN")
    print("="*80)
    print(f"Subnet: {subnet}")
    print(f"SNMP Community: {SNMP_COMMUNITY}")
    print(f"Timeout: {SNMP_TIMEOUT}s")
    print(f"Threads: {max_threads}")
    print("="*80)
    
    network = ipaddress.ip_network(subnet, strict=False)
    ip_list = list(network.hosts())
    
    total_ips = len(ip_list)
    print(f"\nScanning {total_ips} IP addresses...")
    print("This may take a few minutes...\n")
    
    printers = []
    scanned = 0
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        future_to_ip = {executor.submit(scan_ip_sync, ip): ip for ip in ip_list}
        
        for future in as_completed(future_to_ip):
            scanned += 1
            
            if scanned % 10 == 0:
                elapsed = time.time() - start_time
                rate = scanned / elapsed if elapsed > 0 else 0
                remaining = (total_ips - scanned) / rate if rate > 0 else 0
                print(f"Progress: {scanned}/{total_ips} IPs scanned "
                      f"({scanned*100//total_ips}%) - "
                      f"~{remaining:.0f}s remaining")
            
            try:
                result = future.result()
                if result:
                    printers.append(result)
            except Exception:
                pass
    
    elapsed_time = time.time() - start_time
    
    print(f"\n" + "="*80)
    print(f"SCAN COMPLETE")
    print(f"Time elapsed: {elapsed_time:.1f} seconds")
    print(f"IPs scanned: {total_ips}")
    print(f"Printers found: {len(printers)}")
    print("="*80)
    
    return printers

def print_printer_report(printers):
    """Print report of discovered printers"""
    if not printers:
        print("\nNo printers found on the network.")
        return
    
    print("\n" + "="*80)
    print("DISCOVERED PRINTERS")
    print("="*80)
    
    for i, printer in enumerate(printers, 1):
        print(f"\nPrinter {i}:")
        print(f"  IP Address: {printer['ip']}")
        print(f"  Name: {printer['name']}")
        print(f"  Model: {printer['model']}")
        print(f"  Description: {printer['description']}")
        print(f"  Total Pages: {printer['total_pages']}")
    
    print("\n" + "="*80)

def generate_config_snippet(printers):
    """Generate configuration for printer_monitor.py"""
    if not printers:
        return
    
    print("\n" + "="*80)
    print("CONFIGURATION SNIPPET FOR PRINTER_MONITOR.PY")
    print("="*80)
    print("\nCopy this into your printer_monitor.py PRINTERS list:\n")
    
    print("PRINTERS = [")
    for printer in printers:
        name = printer['name'] if printer['name'] != 'Unknown' else printer['model']
        print(f"    {{\"ip\": \"{printer['ip']}\", "
              f"\"name\": \"{name}\", "
              f"\"location\": \"To be configured\"}},")
    
    print("]")
    print("\n" + "="*80)

def export_to_csv(printers, filename="discovered_printers.csv"):
    """Export to CSV"""
    if not printers:
        return
    
    import csv
    
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = ['ip', 'name', 'model', 'description', 'total_pages']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for printer in printers:
            writer.writerow(printer)
    
    print(f"\nPrinter list exported to: {filename}")

def ping_sweep_windows(subnet):
    """Quick ping sweep"""
    import subprocess
    
    print("Running quick ping sweep to find live hosts...")
    
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
    
    print(f"Found {len(live_hosts)} live hosts")
    return live_hosts

# ============================================================================
# MAIN
# ============================================================================

def main():
    subnet = SUBNET
    if len(sys.argv) > 1:
        subnet = sys.argv[1]
    
    # Ping sweep first
    live_hosts = ping_sweep_windows(subnet)
    
    if live_hosts:
        print(f"\nScanning {len(live_hosts)} live hosts for printers...\n")
        printers = []
        
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            future_to_ip = {executor.submit(scan_ip_sync, ip): ip for ip in live_hosts}
            
            for future in as_completed(future_to_ip):
                try:
                    result = future.result()
                    if result:
                        printers.append(result)
                except Exception:
                    pass
    else:
        printers = scan_subnet(subnet, MAX_THREADS)
    
    print_printer_report(printers)
    generate_config_snippet(printers)
    
    if printers:
        export_to_csv(printers)

if __name__ == "__main__":
    main()