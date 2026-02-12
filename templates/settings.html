{% extends "base.html" %}

{% block title %}Settings - Printer Monitoring{% endblock %}

{% block content %}
<h1 style="margin-bottom: 1.5rem;">Settings</h1>

<div style="background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 2rem;">
    <h2 style="margin-bottom: 1rem;">Manage Printers</h2>
    
    <table>
        <thead>
            <tr>
                <th>Name</th>
                <th>IP Address</th>
                <th>Location</th>
                <th>Model</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for printer in printers %}
            <tr>
                <td>{{ printer.name }}</td>
                <td>{{ printer.ip }}</td>
                <td>{{ printer.location }}</td>
                <td>{{ printer.model or 'Unknown' }}</td>
                <td>
                    <a href="/printer/{{ printer.id }}" class="btn" style="padding: 0.3rem 0.8rem; font-size: 0.9rem;">View</a>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<div style="background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
    <h2 style="margin-bottom: 1rem;">Actions</h2>
    
    <div style="margin-bottom: 1rem;">
        <h3 style="margin-bottom: 0.5rem;">Discover New Printers</h3>
        <p style="color: #7f8c8d; margin-bottom: 1rem;">Run the discovery script to find and add printers to the database.</p>
        <code style="display: block; padding: 1rem; background: #ecf0f1; border-radius: 4px;">
            python auto_configure_monitoring.py
        </code>
    </div>
    
    <div style="margin-bottom: 1rem;">
        <h3 style="margin-bottom: 0.5rem;">Run Monitoring</h3>
        <p style="color: #7f8c8d; margin-bottom: 1rem;">Collect current metrics from all printers.</p>
        <code style="display: block; padding: 1rem; background: #ecf0f1; border-radius: 4px;">
            python printer_monitor.py monitor
        </code>
    </div>
    
    <div>
        <h3 style="margin-bottom: 0.5rem;">Export Data</h3>
        <p style="color: #7f8c8d; margin-bottom: 1rem;">Export printer metrics to CSV.</p>
        <code style="display: block; padding: 1rem; background: #ecf0f1; border-radius: 4px;">
            python printer_monitor.py export 90 report.csv
        </code>
    </div>
</div>

<div style="margin-top: 2rem; background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
    <h2 style="margin-bottom: 1rem;">Usage Reports</h2>
    
    <div style="margin-bottom: 1rem;">
        <h3 style="margin-bottom: 0.5rem;">Download Usage Summary Report</h3>
        <p style="color: #7f8c8d; margin-bottom: 1rem;">Generate a comprehensive report showing total pages printed across multiple time periods.</p>
        
        <div style="margin-bottom: 1rem;">
            <label style="display: block; margin-bottom: 0.5rem; font-weight: 600;">Select Time Periods:</label>
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.5rem;">
                <label style="display: flex; align-items: center; gap: 0.5rem;">
                    <input type="checkbox" checked id="period-30"> 30 Days
                </label>
                <label style="display: flex; align-items: center; gap: 0.5rem;">
                    <input type="checkbox" checked id="period-90"> 90 Days
                </label>
                <label style="display: flex; align-items: center; gap: 0.5rem;">
                    <input type="checkbox" checked id="period-120"> 120 Days
                </label>
                <label style="display: flex; align-items: center; gap: 0.5rem;">
                    <input type="checkbox" checked id="period-365"> 365 Days
                </label>
            </div>
        </div>
        
        <button class="btn" onclick="downloadCustomUsageReport()" style="background: #2980b9;">
            Download Usage Summary Report
        </button>
    </div>
</div>

<script>
function downloadCustomUsageReport() {
    const periods = [];
    if (document.getElementById('period-30').checked) periods.push('30');
    if (document.getElementById('period-90').checked) periods.push('90');
    if (document.getElementById('period-120').checked) periods.push('120');
    if (document.getElementById('period-365').checked) periods.push('365');
    
    if (periods.length === 0) {
        alert('Please select at least one time period');
        return;
    }
    
    const url = `/download-usage-summary?periods=${periods.join(',')}`;
    window.location.href = url;
}
</script>
{% endblock %}