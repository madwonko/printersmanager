"""
Windows Service for Printer Dashboard
Ensures the dashboard runs automatically and stays running
"""
import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import sys
import os
import logging
import traceback

# IMPORTANT: Set working directory
os.chdir(r'C:\printermanager')

# Setup logging BEFORE importing app
log_dir = r'C:\printermanager\logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    filename=r'C:\printermanager\logs\service.log',
    level=logging.DEBUG,  # Changed to DEBUG for more info
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Add printermanager to path
sys.path.insert(0, r'C:\printermanager')

class PrinterDashboardService(win32serviceutil.ServiceFramework):
    _svc_name_ = "PrinterDashboard"
    _svc_display_name_ = "Printer Monitoring Dashboard"
    _svc_description_ = "Web dashboard for monitoring network printers via SNMP"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.is_alive = True
        logging.info("Service __init__ called")

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        logging.info("Service stop requested")
        win32event.SetEvent(self.stop_event)
        self.is_alive = False

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        logging.info("="*80)
        logging.info("Service SvcDoRun called")
        logging.info(f"Current directory: {os.getcwd()}")
        logging.info(f"Python path: {sys.path}")
        logging.info("="*80)
        self.main()

    def main(self):
        try:
            logging.info("Attempting to import modules...")
            from waitress import serve
            logging.info("Waitress imported successfully")
            
            from printer_web_dashboard import app
            logging.info("Flask app imported successfully")
            
            logging.info("Starting Waitress server on 0.0.0.0:5000")
            
            serve(
                app,
                host='0.0.0.0',
                port=5000,
                threads=4,
                _quiet=False  # Show errors
            )
        except Exception as e:
            error_msg = f"Service error: {str(e)}\n{traceback.format_exc()}"
            logging.error(error_msg)
            servicemanager.LogErrorMsg(error_msg)
            raise

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(PrinterDashboardService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(PrinterDashboardService)