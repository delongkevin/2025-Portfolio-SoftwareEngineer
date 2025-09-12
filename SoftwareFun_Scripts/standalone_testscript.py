import time
import os
import logging
import subprocess
import sys
import win32com.client
import pandas as pd
import openpyxl
import xml.etree.ElementTree as ET
import pythoncom 

# Setup logging
log_file_path = 'canoe_execution_log.txt'
logging.basicConfig(filename=log_file_path, level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def log_and_print(message):
    print(message)
    logging.info(message)

def error_and_exit(message, exit_code):
    log_and_print(f"ERROR: {message}")
    logging.error(message)
    sys.exit(exit_code)

def DoEvents():
    pythoncom.PumpWaitingMessages()
    time.sleep(0.1)

def DoEventsUntil(cond):
    while not cond():
        DoEvents()

class CanoeSync(object):
    """Wrapper class for CANoe Application object"""
    Started = False
    Stopped = False
    ConfigPath = ""
    
    def __init__(self):
        try:
            app = win32com.client.DispatchEx('CANoe.Application')
            app.Configuration.Modified = False
            ver = app.Version
            log_and_print(f'Loaded CANoe version {ver.major}.{ver.minor}.{ver.Build}')
            self.App = app
            self.Measurement = app.Measurement
            self.Running = lambda : self.Measurement.Running
            self.WaitForStart = lambda: DoEventsUntil(lambda: CanoeSync.Started)
            self.WaitForStop = lambda: DoEventsUntil(lambda: CanoeSync.Stopped)
            win32com.client.WithEvents(self.App.Measurement, CanoeMeasurementEvents)
        except Exception as e:
            error_and_exit(f"Failed to load CANoe: {e}", 1)

    def Load(self, cfgPath):
        if not os.path.isfile(cfgPath):
            log_and_print(f"Config file not found at {cfgPath}. Using default path.")
            cfgPath = r"C:\Users\GM_Tester1\Desktop\Sayma\BEV_CVADAS_RBS\ME_L2H7010_BEV_CVADAS.cfg"
        try:
            cfg = os.path.abspath(cfgPath)
            log_and_print(f'Opening config: {cfg}')
            self.ConfigPath = os.path.dirname(cfg)
            self.Configuration = self.App.Configuration
            self.App.Open(cfg)
            log_and_print("Configuration loaded successfully.")
        except Exception as e:
            error_and_exit(f"Failed to load CANoe configuration: {e}", 2)

    def LoadTestConfiguration(self, testcfgname, testunit):
        """ Adds a test configuration and initialize it with a test unit """
        if not os.path.isfile(testunit):
            log_and_print(f"VTU file not found at {testunit}. Using default VTU path.")
            testunit = r"C:\Users\GM_Tester1\Desktop\Sayma\BEV_CVADAS_RBS\TTFI.vtuexe"
        try:
            tc = self.App.Configuration.TestConfigurations.Add()
            tc.Name = testcfgname
            tus = win32com.client.CastTo(tc.TestUnits, "ITestUnits2")
            tus.Add(testunit)
            log_and_print(f"VTU file {testunit} loaded successfully.")
            self.TestConfigs = [CanoeTestConfiguration(tc)]
            log_and_print(f"Test configuration {testcfgname} added successfully.")
        except Exception as e:
            error_and_exit(f"Failed to load test configuration: {e}", 3)

    def Start(self):
        if not self.Running():
            try:
                self.Measurement.Start()
                self.WaitForStart()
                log_and_print("Measurement started successfully.")
            except Exception as e:
                error_and_exit(f"Failed to start measurement: {e}", 4)

    def Stop(self):
        if self.Running():
            try:
                self.Measurement.Stop()
                self.WaitForStop()
                log_and_print("Measurement stopped successfully.")
            except Exception as e:
                error_and_exit(f"Failed to stop measurement: {e}", 5)

    def RunTestConfigs(self):
        """ Starts all test configurations """
        try:
            for tc in self.TestConfigs:
                tc.Start()
            while not all([not tc.Enabled or tc.IsDone() for tc in self.TestConfigs]):
                DoEvents()
            log_and_print("Test configurations run completed.")
        except Exception as e:
            error_and_exit(f"Failed to run test configurations: {e}", 6)

    def KillCANoe(self):
        """ Kill CANoe process """
        try:
            log_and_print("Closing CANoe application...")
            self.App.Quit()
            log_and_print("CANoe application closed.")
        except Exception as e:
            error_and_exit(f"Failed to close CANoe application: {e}", 7)

class CanoeMeasurementEvents(object):
    """Handler for CANoe measurement events"""
    def OnStart(self): 
        CanoeSync.Started = True
        CanoeSync.Stopped = False
        log_and_print("< measurement started >")

    def OnStop(self): 
        CanoeSync.Started = False
        CanoeSync.Stopped = True
        log_and_print("< measurement stopped >")

class CanoeTestConfiguration:
    """Wrapper class for a CANoe Test Configuration object"""
    def __init__(self, tc):        
        self.tc = tc
        self.Name = tc.Name
        self.Events = win32com.client.DispatchWithEvents(tc, CanoeTestEvents)
        self.IsDone = lambda: self.Events.stopped
        self.Enabled = tc.Enabled
    def Start(self):
        if self.tc.Enabled:
            self.tc.Start()
            self.Events.WaitForStart()

class CanoeTestEvents:
    """Handle the test events"""
    def __init__(self):
        self.started = False
        self.stopped = False
        self.WaitForStart = lambda: DoEventsUntil(lambda: self.started)
        self.WaitForStop = lambda: DoEventsUntil(lambda: self.stopped)
    def OnStart(self):
        self.started = True
        self.stopped = False        
        log_and_print(f"< {self.Name} started >")
    def OnStop(self, reason):
        self.started = False
        self.stopped = True 
        log_and_print(f"< {self.Name} stopped >")

def get_user_input(prompt, default):
    user_input = input(f"{prompt} (default: {default}): ")
    return user_input.strip() if user_input else default

def parse_xml_report(xml_file):
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        test_data = []

        # Extract general test information and test steps
        for testunit in root.findall('testunit'):
            for testcase in testunit.findall('testcase'):
                test_name = testunit.find('title').text
                start_time = testcase.get('starttime')
                end_time = testcase.find('verdict').get('endtime')
                result = testcase.find('verdict').get('result')

                # Capture all the steps of the test
                for step in testcase.findall('teststep'):
                    timestamp = step.get('timestamp')
                    description = step.text
                    step_result = step.get('result')

                    test_data.append({
                        'Test Name': test_name,
                        'Start Time': start_time,
                        'End Time': end_time,
                        'Step Description': description,
                        'Step Timestamp': timestamp,
                        'Result': result,
                        'Step Result': step_result
                    })

        return test_data
    except Exception as e:
        print(f"Failed to parse XML report: {e}")
        sys.exit(2)

def export_to_excel(report_data, output_excel_path):
    """Exports the parsed test results to an Excel or CSV file"""
    try:
        df = pd.DataFrame(report_data)

        # save as CSV, otherwise save as Excel
        if output_excel_path.endswith('.csv'):
            df.to_csv(output_excel_path, index=False)
        else:
            df.to_excel(output_excel_path, index=False)

        print(f"Report exported to {output_excel_path}")
    except Exception as e:
        print(f"Failed to export report: {e}")
        sys.exit(3)

# Main
def main():
    try:
        app = CanoeSync()

        # Get user input for CANoe config path and VTU path
        cfg_path = get_user_input("Enter CANoe config file path", r"C:\Users\GM_Tester1\Desktop\Sayma\BEV_CVADAS_RBS\ME_L2H7010_BEV_CVADAS.cfg")
        vtu_path = get_user_input("Enter VTU file path", r"C:\Users\GM_Tester1\Desktop\Sayma\BEV_CVADAS_RBS\TTFI.vtuexe")

        # Load the configuration
        app.Load(cfg_path)

        # Add a test configuration and load VTU
        app.LoadTestConfiguration('Sanity_Demo', vtu_path)

        # Start the measurement
        app.Start()    

        # Run the test configurations
        app.RunTestConfigs()

         # Stop CANoe measurement
        app.Stop()

        # XML report path
        xml_report_path = r"C:\Users\GM_Tester1\Desktop\Sayma\BEV_CVADAS_RBS\Report_Sanity_Demo.xml"

        # Parse the XML report
        print("Parsing XML report...")
        report_data = parse_xml_report(xml_report_path)

        # Export parsed data to Excel or CSV
        output_excel_path = 'SWQT_Daily_Tracking.xlsx'  # or .csv
        export_to_excel(report_data, output_excel_path)
        log_and_print("Test results saved to Excel!")

        # Log and print completion
        log_and_print("Test execution and reporting completed.")

        # Kill CANoe
        app.KillCANoe()

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
