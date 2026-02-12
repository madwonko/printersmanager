<#
.SYNOPSIS
    Monitors the Printer Dashboard service/process
.DESCRIPTION
    Checks if dashboard is running and restarts if needed
#>

$logFile = "C:\printermanager\logs\monitor.log"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

function Write-Log {
    param($Message)
    "$timestamp - $Message" | Out-File -FilePath $logFile -Append
    Write-Host "$timestamp - $Message"
}

# Check if running as service
$service = Get-Service -Name "PrinterDashboard" -ErrorAction SilentlyContinue

if ($service) {
    if ($service.Status -ne "Running") {
        Write-Log "Service not running, attempting to start..."
        Start-Service -Name "PrinterDashboard"
        Start-Sleep -Seconds 5
        
        $service = Get-Service -Name "PrinterDashboard"
        if ($service.Status -eq "Running") {
            Write-Log "Service started successfully"
        } else {
            Write-Log "ERROR: Failed to start service"
        }
    } else {
        Write-Log "Service running normally"
    }
} else {
    # Check if running as scheduled task
    $process = Get-Process python* -ErrorAction SilentlyContinue | Where-Object {$_.Path -like "*printermanager*"}
    
    if ($process) {
        $cpu = [math]::Round($process.CPU, 2)
        $memory = [math]::Round($process.WorkingSet64 / 1MB, 2)
        
        Write-Log "Dashboard running - CPU: $cpu sec, Memory: $memory MB"
        
        # Alert if high memory usage
        if ($memory -gt 500) {
            Write-Log "WARNING: High memory usage detected: $memory MB"
        }
    } else {
        Write-Log "ERROR: Dashboard not running, attempting restart..."
        Start-ScheduledTask -TaskName "PrinterDashboard" -ErrorAction SilentlyContinue
    }
}

# Test HTTP endpoint
try {
    $response = Invoke-WebRequest -Uri "http://localhost:5000" -TimeoutSec 5 -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Log "HTTP endpoint responding normally"
    }
} catch {
    Write-Log "ERROR: HTTP endpoint not responding"
}