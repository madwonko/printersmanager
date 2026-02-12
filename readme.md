# Printer Monitoring System

A comprehensive SNMP-based printer monitoring solution with web dashboard, automated discovery, and reporting capabilities.

![Version](https://img.shields.io/badge/version-2.0.0-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
  - [Web Dashboard](#web-dashboard)
  - [Command Line Tools](#command-line-tools)
  - [Automated Monitoring](#automated-monitoring)
- [Reports](#reports)
- [Maintenance](#maintenance)
- [Troubleshooting](#troubleshooting)
- [File Structure](#file-structure)
- [Changelog](#changelog)

---

## 🎯 Overview

The Printer Monitoring System is a production-ready solution for monitoring network printers across multiple locations. It uses SNMP to collect metrics including page counts, toner levels, drum status, and device health. All data is stored in a local SQLite database and presented through a modern web interface.

**Key Capabilities:**
- Automatic network discovery of SNMP-enabled printers
- Real-time monitoring of toner, drum, and page counts
- Web-based dashboard with filtering and search
- PDF reports for current status and usage summaries
- Multi-period usage analysis (30, 90, 120, 365 days)
- Low toner alerts and notifications
- Historical tracking and trend analysis

---

## ✨ Features

### Network Discovery
- Automatic printer discovery across multiple subnets
- Subnet-to-location mapping
- Model identification and metadata extraction
- Safe duplicate handling (preserves existing data)

### Monitoring & Metrics
- **Page Counts:** Total pages printed, usage by time period
- **Toner Levels:** Percentage-based or status (OK/Low)
- **Drum Units:** Remaining capacity percentage
- **Device Status:** Online/offline detection
- **Multi-vendor Support:** Brother, Samsung, HP, Xerox, and more

### Web Dashboard
- Clean, responsive interface
- Filter by location and printer model
- Real-time status cards with color-coded alerts
- Interactive charts (7, 14, 30, 60, 90-day views)
- Individual printer detail pages
- Editable location assignments

### Reporting
- **Current Status Report:** Snapshot of all printers
- **Usage Summary Report:** Multi-period analysis (30/90/120/365 days)
- PDF exports with professional formatting
- CSV data exports for external analysis
- Filtering by location and model

### Production Deployment
- Windows Service integration
- Task Scheduler support
- Automatic restart and monitoring
- Detailed logging and diagnostics
- Internal-only network access controls

---

## 💻 System Requirements

### Software
- **Operating System:** Windows Server 2019+ or Windows 10/11
- **Python:** 3.11 or higher
- **Network:** Access to printer subnet(s)
- **Protocol:** SNMP v1/v2c enabled on printers

### Python Dependencies
```
Flask==3.0.0
pysnmp==6.2.6
reportlab==4.0.9
waitress==3.0.0
pywin32==306
```

### Hardware
- **Minimum:** 2 GB RAM, 2 CPU cores, 10 GB disk
- **Recommended:** 4 GB RAM, 4 CPU cores, 20 GB disk
- Network connectivity to all monitored printers

---

## 🚀 Installation

### 1. Install Python

```powershell
# Using winget (Windows 11/Server 2022)
winget install Python.Python.3.11

# Or download from python.org
# https://www.python.org/downloads/
```

**Important:** During installation, check "Add Python to PATH"

### 2. Clone or Extract Files

Extract all files to: `C:\printermanager`

### 3. Install Dependencies

```powershell
cd C:\printermanager
pip install -r requirements.txt
```

### 4. Create Logs Directory

```powershell
New-Item -Path "C:\printermanager\logs" -ItemType Directory -Force
```

### 5. Configure Firewall

```powershell
# Allow port 5000 for internal network only
New-NetFirewallRule -DisplayName "Printer Dashboard - Internal" `
    -Direction Inbound `
    -LocalPort 5000 `
    -Protocol TCP `
    -Action Allow `
    -RemoteAddress 10.0.0.0/8,172.16.0.0/12,192.168.0.0/16 `
    -Profile Domain,Private
```

---

## ⚙️ Configuration

### Network Configuration

Create or edit `C:\printermanager\subnets.txt`:

```
# Format: SUBNET/CIDR,Location Name
10.164.1.0/24,Main Office
10.164.2.0/24,North Main
10.164.3.0/24,South Branch
192.168.1.0/24,Home Office
```

### SNMP Requirements

Ensure printers have SNMP enabled:
- **Protocol:** SNMPv1 or SNMPv2c
- **Community String:** public (default) or custom
- **Port:** 161 (standard SNMP)

### Initial Discovery

```powershell
cd C:\printermanager
python auto_configure_monitoring.py
```

This will:
1. Scan all subnets in `subnets.txt`
2. Detect SNMP-enabled printers
3. Identify manufacturer and model
4. Populate the database with printer records

---

## 📖 Usage

### Web Dashboard

#### Start the Dashboard

**Option A: Windows Service (Recommended)**

```powershell
# Install service
python dashboard_service.py install

# Start service
python dashboard_service.py start

# Set to auto-start
sc config PrinterDashboard start=auto
```

**Option B: Task Scheduler**

```powershell
$action = New-ScheduledTaskAction -Execute "python.exe" -Argument "C:\printermanager\run_production.py" -WorkingDirectory "C:\printermanager"
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName "PrinterDashboard" -Action $action -Trigger $trigger -Principal $principal -Settings $settings
Start-ScheduledTask -TaskName "PrinterDashboard"
```

**Option C: Manual (Testing Only)**

```powershell
python run_production.py
```

#### Access the Dashboard

Open browser to: **http://10.1.3.12:5000** (or your server IP)

From the terminal server: **http://localhost:5000**

#### Dashboard Features

**Main Dashboard:**
- View all printers with current status
- Filter by location and model
- See aggregate statistics
- Download PDF reports
- Access individual printer details

**Printer Detail Page:**
- View complete printer information
- Historical charts (page count, toner, drum)
- Adjustable time periods (7-90 days)
- Usage statistics for 7 and 30-day periods
- Edit printer location
- Delete printer (removes all history)

**Settings Page:**
- Manage all printers
- Download usage summary reports
- Custom time period selection
- View command-line instructions

---

### Command Line Tools

#### Discovery Tool

```powershell
# Auto-discover using subnets.txt
python auto_configure_monitoring.py

# Create sample subnets.txt
python auto_configure_monitoring.py --create

# Scan a specific subnet
python auto_configure_monitoring.py 192.168.1.0/24

# Use custom subnet file
python auto_configure_monitoring.py --file custom_subnets.txt
```

#### Monitoring Tool

```powershell
# Quick monitoring (no reports)
python printer_monitor.py

# Full monitoring with report
python printer_monitor.py monitor

# Generate 30-day usage report
python printer_monitor.py report 30

# Export to CSV
python printer_monitor.py export 90 report.csv

# Continuous monitoring (runs every hour)
python printer_monitor.py loop 3600
```

---

### Automated Monitoring

#### Daily Metrics Collection

```powershell
# Schedule daily monitoring at 6 AM
$action = New-ScheduledTaskAction -Execute "python.exe" -Argument "C:\printermanager\printer_monitor.py monitor" -WorkingDirectory "C:\printermanager"
$trigger = New-ScheduledTaskTrigger -Daily -At 6am
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName "PrinterMonitoring-Daily" -Action $action -Trigger $trigger -Principal $principal
```

#### Dashboard Monitoring

```powershell
# Monitor dashboard health every 5 minutes
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File C:\printermanager\check_dashboard.ps1"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration ([TimeSpan]::MaxValue)
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName "Monitor-PrinterDashboard" -Action $action -Trigger $trigger -Principal $principal
```

---

## 📊 Reports

### Current Status Report

**What it includes:**
- Summary statistics (total printers, pages, alerts)
- Complete printer table with current metrics
- Toner and drum levels
- Filterable by location and model

**How to generate:**
- **Web:** Click "Download Current Status Report" button
- **URL:** `/download-report?location=X&model=Y&days=30`

### Usage Summary Report

**What it includes:**
- Multi-period summary table (30, 90, 120, 365 days)
- Total pages printed per period
- Active printer count
- Average pages per printer
- Detailed breakdown by printer for each period

**How to generate:**
- **Web:** Click "Download Usage Summary Report" button
- **Web (Custom):** Settings page → Select periods → Download
- **URL:** `/download-usage-summary?periods=30,90,120,365`

### CSV Export

```powershell
# Export 90 days of data
python printer_monitor.py export 90 printer_data.csv
```

**CSV includes:**
- Printer name, IP, location, model
- Page counts and usage statistics
- Toner and drum levels
- Last updated timestamp

---

## 🔧 Maintenance

### Service Management

```powershell
# Check status
Get-Service PrinterDashboard

# Start/Stop/Restart
Start-Service PrinterDashboard
Stop-Service PrinterDashboard
Restart-Service PrinterDashboard

# View logs
Get-Content C:\printermanager\logs\service.log -Tail 50
Get-Content C:\printermanager\logs\dashboard.log -Tail 50
```

### Task Scheduler Management

```powershell
# Check status
Get-ScheduledTask -TaskName "PrinterDashboard"

# Start/Stop
Start-ScheduledTask -TaskName "PrinterDashboard"
Stop-ScheduledTask -TaskName "PrinterDashboard"
```

### Database Maintenance

```powershell
# Backup database
Copy-Item C:\printermanager\printer_monitoring.db C:\printermanager\backups\printer_monitoring_$(Get-Date -Format 'yyyyMMdd').db

# Check database size
Get-Item C:\printermanager\printer_monitoring.db | Select-Object Name, @{Name="Size(MB)";Expression={[math]::Round($_.Length/1MB,2)}}

# Vacuum database (optimize)
python -c "import sqlite3; conn=sqlite3.connect('printer_monitoring.db'); conn.execute('VACUUM'); conn.close()"
```

### Cleaning Old Data

```powershell
# Delete metrics older than 90 days
python
```

```python
import sqlite3
conn = sqlite3.connect('printer_monitoring.db')
cursor = conn.cursor()
cursor.execute("DELETE FROM metrics WHERE timestamp < datetime('now', '-90 days')")
print(f"Deleted {cursor.rowcount} old metrics")
conn.commit()
conn.close()
exit()
```

### Log Rotation

```powershell
# Archive old logs
$date = Get-Date -Format "yyyyMMdd"
Compress-Archive -Path C:\printermanager\logs\*.log -DestinationPath C:\printermanager\logs\archive_$date.zip
Remove-Item C:\printermanager\logs\*.log
```

---

## 🔍 Troubleshooting

### Dashboard Won't Start

**Check if Python is installed:**
```powershell
python --version
```

**Check if packages are installed:**
```powershell
pip list | findstr "Flask pysnmp reportlab waitress"
```

**Check if port 5000 is in use:**
```powershell
netstat -ano | findstr :5000
```

**Kill conflicting process:**
```powershell
Get-Process python* | Stop-Process -Force
```

**View detailed errors:**
```powershell
python C:\printermanager\printer_web_dashboard.py
# Look for error messages
```

### Service Won't Start

**Remove and reinstall:**
```powershell
python C:\printermanager\dashboard_service.py stop
python C:\printermanager\dashboard_service.py remove
python C:\printermanager\dashboard_service.py install
python C:\printermanager\dashboard_service.py start
```

**Check service logs:**
```powershell
Get-Content C:\printermanager\logs\service.log -Tail 50
```

### Database Errors

**Check if database exists:**
```powershell
Test-Path C:\printermanager\printer_monitoring.db
```

**Rebuild database:**
```powershell
Remove-Item C:\printermanager\printer_monitoring.db
python printer_monitor.py monitor
```

### Printers Not Discovered

**Verify SNMP is enabled on printers**

**Test SNMP manually:**
```powershell
python
```

```python
from pysnmp.hlapi.v1arch import *

# Test SNMP connection
g = getCmd(SnmpDispatcher(),
           CommunityData('public'),
           UdpTransportTarget(('10.164.1.5', 161)),
           ('1.3.6.1.2.1.1.1.0',))  # System description

errorIndication, errorStatus, errorIndex, varBinds = next(g)

if errorIndication:
    print(f"Error: {errorIndication}")
else:
    print(f"Success: {varBinds[0][1]}")
```

**Check firewall:**
```powershell
Test-NetConnection -ComputerName 10.164.1.5 -Port 161
```

### Page Counts Incorrect

**Issue:** Page counts show incorrect numbers after initial setup

**Solution:** This is normal! The system needs at least 2 readings to calculate pages printed.

- Day 1: Shows 0 (only 1 reading)
- Day 2+: Shows accurate counts

**To reset metrics:**
```powershell
python
```

```python
import sqlite3
conn = sqlite3.connect('printer_monitoring.db')
conn.execute("DELETE FROM metrics")
conn.commit()
conn.close()
exit()
```

Then run: `python printer_monitor.py monitor`

---

## 📁 File Structure

```
C:\printermanager\
├── printer_web_dashboard.py       # Main Flask application
├── printer_monitor.py             # Monitoring and metrics collection
├── auto_configure_monitoring.py   # Network discovery tool
├── run_production.py              # Production server launcher
├── dashboard_service.py           # Windows service wrapper
├── check_dashboard.ps1            # Health monitoring script
├── requirements.txt               # Python dependencies
├── README.md                      # This file
├── printer_monitoring.db          # SQLite database
├── subnets.txt                    # Network configuration
├── templates\                     # HTML templates
│   ├── base.html
│   ├── dashboard.html
│   ├── printer_detail.html
│   └── settings.html
└── logs\                          # Application logs
    ├── dashboard.log
    ├── service.log
    └── monitor.log
```

---

## 📝 Changelog

### Version 2.0.0 (2025-02-12)
**Major Release - Production Deployment**

**Added:**
- Windows Service support for automatic startup
- Task Scheduler integration as alternative deployment
- Usage Summary Report with multi-period analysis (30/90/120/365 days)
- Automated health monitoring with `check_dashboard.ps1`
- Production server using Waitress WSGI
- Comprehensive logging system
- Database maintenance utilities
- README documentation

**Changed:**
- Improved page count calculations (now accurate from start date)
- Updated database queries for better performance
- Enhanced error handling and logging
- Streamlined installation process

**Fixed:**
- Page count accumulation issues
- Service restart reliability
- Database locking on Windows
- Chart data loading performance

---

### Version 1.5.0 (2025-02-10)
**Feature Release - Web Dashboard Enhancement**

**Added:**
- Location and model filtering on dashboard
- Active filter tags with individual removal
- PDF report generation with filters
- Adjustable chart periods (7, 14, 30, 60, 90 days)
- Settings page for printer management
- Desktop shortcuts for users

**Changed:**
- Improved mobile responsiveness
- Enhanced UI/UX with better visual hierarchy
- Optimized database queries for filtered views

**Fixed:**
- Template syntax errors in printer detail page
- Chart rendering on slow connections

---

### Version 1.0.0 (2025-02-06)
**Initial Release**

**Core Features:**
- SNMP-based printer monitoring
- Automatic network discovery
- SQLite database storage
- Flask web dashboard
- Real-time metrics collection
- Toner and drum level tracking
- Page count monitoring
- Location-based organization
- Individual printer detail pages
- Historical data charts
- CSV export functionality

**Supported Manufacturers:**
- Brother
- Samsung
- Xerox
- HP
- Canon
- Ricoh

**Platform:**
- Windows Server 2019+
- Windows 10/11
- Python 3.11+

---

## 📄 License

Copyright © 2025. All rights reserved.

This software is provided for internal use only. Redistribution and use in source and binary forms, with or without modification, are permitted for internal organizational purposes only.

---

## 🆘 Support

For issues, questions, or feature requests:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review log files in `C:\printermanager\logs\`
3. Contact your system administrator

---

## 🙏 Acknowledgments

**Technologies Used:**
- Flask - Web framework
- pysnmp - SNMP library
- ReportLab - PDF generation
- Waitress - Production WSGI server
- Chart.js - Data visualization
- SQLite - Database engine

**Developed for:**
- Internal printer fleet management
- Cost tracking and analysis
- Proactive maintenance alerting
- Multi-location monitoring

---

**Last Updated:** February 12, 2025  
**Version:** 2.0.0  
**Status:** Production Ready ✅