"""
Diagnose printer toner OIDs - Find the correct toner level readings
"""
import asyncio
import pysnmp.hlapi.asyncio as hlapi

PRINTERS = [
    {"ip": "10.164.1.30", "name": "Brother MFC-L5915DW"},
    {"ip": "192.168.1.100", "name": "Samsung SL4070"},
]

SNMP_COMMUNITY = "public"

async def snmp_walk(ip, base_oid):
    """Walk an SNMP OID tree to get all sub-values"""
    results = []
    try:
        snmpEngine = hlapi.SnmpEngine()
        
        # Get multiple values by incrementing the OID
        for i in range(1, 20):  # Try indices 1-20
            oid = f"{base_oid}.{i}"
            try:
                errorIndication, errorStatus, errorIndex, varBinds = await hlapi.getCmd(
                    snmpEngine,
                    hlapi.CommunityData(SNMP_COMMUNITY, mpModel=0),
                    hlapi.UdpTransportTarget((ip, 161), timeout=2),
                    hlapi.ContextData(),
                    hlapi.ObjectType(hlapi.ObjectIdentity(oid))
                )
                
                if errorIndication or errorStatus:
                    break
                
                value = str(varBinds[0][1])
                if "No Such" not in value and value.strip() and value != "":
                    results.append((oid, value))
                else:
                    # If we hit a missing index, we might be done
                    if i > 5 and len(results) > 0:
                        break
            except:
                break
        
        snmpEngine.close()
        
    except Exception as e:
        print(f"    Error: {e}")
    
    return results

async def snmp_get(ip, oid):
    """Get a single SNMP value"""
    try:
        snmpEngine = hlapi.SnmpEngine()
        errorIndication, errorStatus, errorIndex, varBinds = await hlapi.getCmd(
            snmpEngine,
            hlapi.CommunityData(SNMP_COMMUNITY, mpModel=0),
            hlapi.UdpTransportTarget((ip, 161), timeout=3),
            hlapi.ContextData(),
            hlapi.ObjectType(hlapi.ObjectIdentity(oid))
        )
        
        snmpEngine.close()
        
        if errorIndication or errorStatus:
            return None
        
        value = str(varBinds[0][1])
        if "No Such" not in value and value.strip():
            return value
        return None
        
    except Exception as e:
        return None

async def diagnose_printer(printer):
    """Diagnose toner OIDs for a printer"""
    ip = printer['ip']
    name = printer['name']
    
    print("\n" + "="*80)
    print(f"DIAGNOSING: {name} ({ip})")
    print("="*80)
    
    # Walk the supply table to find all toner/supply entries
    print("\n1. SUPPLY DESCRIPTIONS (what supplies exist):")
    print("-" * 80)
    
    descriptions = await snmp_walk(ip, '1.3.6.1.2.1.43.11.1.1.6.1')
    supply_map = {}
    
    for oid, value in descriptions:
        # Extract index from OID (last number)
        index = oid.split('.')[-1]
        supply_map[index] = {'description': value}
        print(f"  Index {index}: {value}")
    
    if not descriptions:
        print("  No supply descriptions found")
    
    # Get supply types
    print("\n2. SUPPLY TYPES:")
    print("-" * 80)
    types = await snmp_walk(ip, '1.3.6.1.2.1.43.11.1.1.5.1')
    for oid, value in types:
        index = oid.split('.')[-1]
        if index in supply_map:
            supply_map[index]['type'] = value
            print(f"  Index {index}: Type {value}")
    
    if not types:
        print("  No supply types found")
    
    # Get supply units
    print("\n3. SUPPLY UNITS (measurement unit):")
    print("-" * 80)
    units = await snmp_walk(ip, '1.3.6.1.2.1.43.11.1.1.7.1')
    unit_names = {
        '3': 'tenThousandthsOfInches',
        '4': 'micrometers',
        '7': 'impressions',
        '8': 'sheets',
        '11': 'hours',
        '12': 'thousandthsOfOunces',
        '13': 'tenthsOfGrams',
        '14': 'hundrethsOfFluidOunces',
        '15': 'tenthsOfMilliliters',
        '16': 'feet',
        '17': 'meters',
        '18': 'items',
        '19': 'percent'
    }
    
    for oid, value in units:
        index = oid.split('.')[-1]
        if index in supply_map:
            unit_name = unit_names.get(value, f'Unknown ({value})')
            supply_map[index]['unit'] = unit_name
            print(f"  Index {index}: {unit_name}")
    
    if not units:
        print("  No supply units found")
    
    # Get max capacity
    print("\n4. SUPPLY MAX CAPACITY:")
    print("-" * 80)
    max_caps = await snmp_walk(ip, '1.3.6.1.2.1.43.11.1.1.8.1')
    for oid, value in max_caps:
        index = oid.split('.')[-1]
        if index in supply_map:
            supply_map[index]['max_capacity'] = value
            print(f"  Index {index}: {value}")
    
    if not max_caps:
        print("  No max capacities found")
    
    # Get current level
    print("\n5. SUPPLY CURRENT LEVEL:")
    print("-" * 80)
    levels = await snmp_walk(ip, '1.3.6.1.2.1.43.11.1.1.9.1')
    for oid, value in levels:
        index = oid.split('.')[-1]
        if index in supply_map:
            supply_map[index]['current_level'] = value
            print(f"  Index {index}: {value}")
    
    if not levels:
        print("  No current levels found")
    
    # Calculate percentages
    print("\n6. CALCULATED TONER PERCENTAGES:")
    print("="*80)
    
    if not supply_map:
        print("  No supply information available")
    
    for index, supply in supply_map.items():
        desc = supply.get('description', 'Unknown')
        current = supply.get('current_level', '0')
        max_cap = supply.get('max_capacity', '0')
        unit = supply.get('unit', 'Unknown')
        
        # Only show toner/ink supplies
        if any(keyword in desc.lower() for keyword in ['toner', 'ink', 'black', 'cyan', 'magenta', 'yellow', 'cartridge']):
            try:
                current_val = int(current)
                max_val = int(max_cap)
                
                print(f"\n  {desc}:")
                print(f"    Index: {index}")
                print(f"    Current: {current_val}")
                print(f"    Max: {max_val}")
                print(f"    Unit: {unit}")
                
                if unit == 'percent':
                    # Already a percentage
                    percentage = current_val
                    print(f"    ✓ Percentage: {percentage}% (already in percent)")
                elif max_val > 0 and max_val != -2 and current_val != -2 and current_val != -3:
                    # Calculate percentage
                    percentage = (current_val / max_val) * 100
                    print(f"    ✓ Calculated Percentage: {percentage:.1f}%")
                elif current_val == -2:
                    print(f"    Status: Unknown")
                elif current_val == -3:
                    print(f"    Status: OK/Available")
                else:
                    print(f"    Status: Cannot calculate percentage")
                    
            except (ValueError, ZeroDivisionError) as e:
                print(f"\n  {desc}: Unable to calculate - {e}")
    
    # Also try some manufacturer-specific OIDs
    print("\n7. TRYING MANUFACTURER-SPECIFIC OIDS:")
    print("="*80)
    
    # Brother-specific OIDs
    print("\n  Brother-specific OIDs:")
    brother_oids = {
        'Brother Toner Level': '1.3.6.1.4.1.2435.2.3.9.4.2.1.5.5.1.0',
        'Brother Toner Status': '1.3.6.1.4.1.2435.2.3.9.4.2.1.5.5.8.1',
    }
    
    for name, oid in brother_oids.items():
        value = await snmp_get(ip, oid)
        if value:
            print(f"    {name}: {value}")
    
    # Samsung-specific
    print("\n  Samsung-specific OIDs:")
    samsung_oids = {
        'Samsung Toner Remaining': '1.3.6.1.4.1.236.11.5.11.55.1.1.4.1',
        'Samsung Toner Status': '1.3.6.1.4.1.236.11.5.11.55.1.1.3.1',
    }
    
    for name, oid in samsung_oids.items():
        value = await snmp_get(ip, oid)
        if value:
            print(f"    {name}: {value}")
    
    print("\n" + "="*80)

async def main():
    for printer in PRINTERS:
        await diagnose_printer(printer)
        await asyncio.sleep(1)  # Brief pause between printers

if __name__ == "__main__":
    asyncio.run(main())