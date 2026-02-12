"""
Test SNMP on a specific printer - Direct Import Version
"""
PRINTER_IP = "192.168.1.100"

print(f"Testing SNMP on {PRINTER_IP}...\n")

try:
    # Try importing the specific functions we need
    from pysnmp.entity.engine import SnmpEngine
    from pysnmp.entity.rfc3413.oneliner.cmdgen import CommunityData, UdpTransportTarget, ContextData
    from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType
    from pysnmp.entity.rfc3413.oneliner import cmdgen
    
    print("Using legacy pysnmp API...")
    
    cmdGen = cmdgen.CommandGenerator()
    
    oids = {
        'System Description': '1.3.6.1.2.1.1.1.0',
        'System Name': '1.3.6.1.2.1.1.5.0',
        'Printer Model': '1.3.6.1.2.1.25.3.2.1.3.1',
        'Page Counter': '1.3.6.1.2.1.43.10.2.1.4.1.1',
    }
    
    for name, oid in oids.items():
        errorIndication, errorStatus, errorIndex, varBinds = cmdGen.getCmd(
            cmdgen.CommunityData('public'),
            cmdgen.UdpTransportTarget((PRINTER_IP, 161), timeout=3, retries=1),
            oid
        )
        
        if errorIndication:
            print(f"  {name}: {errorIndication}")
        elif errorStatus:
            print(f"  {name}: {errorStatus}")
        else:
            for varBind in varBinds:
                print(f"  ✓ {name}: {varBind[1]}")

except ImportError as e1:
    print(f"Legacy API not available: {e1}")
    print("\nTrying modern API...")
    
    try:
        # Modern API
        import pysnmp.hlapi.asyncio as hlapi
        import asyncio
        
        async def snmp_get(ip, oid):
            snmpEngine = hlapi.SnmpEngine()
            errorIndication, errorStatus, errorIndex, varBinds = await hlapi.getCmd(
                snmpEngine,
                hlapi.CommunityData('public', mpModel=0),
                hlapi.UdpTransportTarget((ip, 161)),
                hlapi.ContextData(),
                hlapi.ObjectType(hlapi.ObjectIdentity(oid))
            )
            
            if errorIndication:
                return None, str(errorIndication)
            elif errorStatus:
                return None, str(errorStatus)
            else:
                return str(varBinds[0][1]), None
        
        async def test_printer():
            oids = {
                'System Description': '1.3.6.1.2.1.1.1.0',
                'System Name': '1.3.6.1.2.1.1.5.0',
                'Printer Model': '1.3.6.1.2.1.25.3.2.1.3.1',
                'Page Counter': '1.3.6.1.2.1.43.10.2.1.4.1.1',
            }
            
            for name, oid in oids.items():
                value, error = await snmp_get(PRINTER_IP, oid)
                if value:
                    print(f"  ✓ {name}: {value}")
                else:
                    print(f"  {name}: {error}")
        
        asyncio.run(test_printer())
        
    except Exception as e2:
        print(f"Modern API also failed: {e2}")
        print("\n" + "="*80)
        print("ALTERNATIVE SOLUTION")
        print("="*80)
        print("\nSince the Python library is having issues, let's use Windows SNMP:")
        print("\n1. Install Windows SNMP feature:")
        print("   - Open 'Turn Windows features on or off'")
        print("   - Check 'Simple Network Management Protocol (SNMP)'")
        print("   - Click OK and restart if needed")
        print("\n2. Or use snmpwalk.exe from Net-SNMP:")
        print("   - Download from: http://www.net-snmp.org/download.html")
        print("   - Install and run:")
        print(f"     snmpwalk -v 2c -c public {PRINTER_IP}")