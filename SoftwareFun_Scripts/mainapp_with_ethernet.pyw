import time
import re
import subprocess
import win32com.client
import pandas as pd
import openpyxl
import sys
import xml.etree.ElementTree as ET
import pythoncom
import logging
import psutil
import glob
import os
import csv
import shutil
from PyQt5.QtWidgets import (
    QApplication, QDialog, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit,
    QComboBox, QHBoxLayout, QMenuBar, QAction, QStatusBar, QFrame, QMessageBox, QFormLayout, QLineEdit, QFileDialog, QScrollArea, QGridLayout
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSettings, QTimer, QObject
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import QSpinBox

# Global base directory
BASE_DIR = r"C:\Users\saymtamb\OneDrive - Magna\Desktop\Standalone_Demo_Final"

# ---------------------------
# Logging Handler
# ---------------------------
class QTextEditLogger(logging.Handler, QObject):
    """Custom logger to emit logs to a QTextEdit via signal."""
    log_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__()
        QObject.__init__(self, parent)
        self.setLevel(logging.INFO)

    def emit(self, record):
        """Format and emit log message."""
        try:
            msg = self.format(record)
            self.log_signal.emit(msg)
        except Exception as e:
            print(f"Logging error: {e}")

def log_and_print(message):
    """Log and print info message."""
    logging.info(message)

def error_and_exit(message, code=1):
    """Log error and exit application."""
    log_and_print(message)
    sys.exit(code)

def DoEvents():
    """Process pending COM messages."""
    pythoncom.PumpWaitingMessages()
    time.sleep(0.1)

def DoEventsUntil(cond):
    """Wait until condition is met by processing events."""
    while not cond():
        DoEvents()

# ---------------------------
# XML Parsing & Exporting Functions
# ---------------------------
def parse_xml_report(xml_file):
    """Parse CANoe XML report and extract test data."""
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        test_data = []
        for testunit in root.findall('testunit'):
            test_name_elem = testunit.find('title')
            test_name = test_name_elem.text if test_name_elem is not None else "Unknown Test Name"
            for testcase in testunit.findall('testcase'):
                start_time = testcase.get('starttime', '')
                verdict_elem = testcase.find('verdict')
                end_time = verdict_elem.get('endtime', '') if verdict_elem is not None else ""
                result = verdict_elem.get('result', '') if verdict_elem is not None else ""
                for step in testcase.findall('teststep'):
                    timestamp = step.get('timestamp', '')
                    description = step.text or ""
                    step_result = step.get('result', '')
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
        log_and_print(f"Failed to parse XML report: {e}")
        return None

def export_to_excel(report_data, output_excel_path):
    """Export parsed report data to Excel or CSV."""
    try:
        df = pd.DataFrame(report_data)
        if output_excel_path.endswith('.csv'):
            df.to_csv(output_excel_path, index=False)
        else:
            df.to_excel(output_excel_path, index=False)
        log_and_print(f"Report exported to {output_excel_path}")
    except Exception as e:
        log_and_print(f"Failed to export report: {e}")

# ---------------------------
# Custom Toggle Button
# ---------------------------
class ToggleButton(QPushButton):
    """Button that toggles between selected/unselected states."""
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.selected = False
        self.default_style = "background-color: lightgray; color: black; font-weight: bold; padding: 12px;"
        self.selected_style = "background-color: green; color: white; font-weight: bold; padding: 12px;"
        self.setStyleSheet(self.default_style)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(self.toggleState)

    def toggleState(self):
        """Toggle selection state and update style."""
        self.selected = not self.selected
        self.setStyleSheet(self.selected_style if self.selected else self.default_style)

    def setSelected(self, select: bool):
        """Set selection state."""
        self.selected = select
        self.setStyleSheet(self.selected_style if select else self.default_style)

# ---------------------------
# Dialog Classes
# ---------------------------
class ProjectSelectionDialog(QDialog):
    """Dialog to allow the user to select a project."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_project = None
        self.initUI()
    
    def initUI(self):
        self.setWindowTitle("Select Project")
        self.setGeometry(300, 300, 300, 150)
        layout = QVBoxLayout()
        label = QLabel("Select a Project:")
        layout.addWidget(label)
        self.project_dropdown = QComboBox()
        self.project_dropdown.addItems(["DT-MY26", "HD-MY25", "BEV-MY25", "DT-MY24"])
        layout.addWidget(self.project_dropdown)
        select_button = ToggleButton("Select")
        select_button.clicked.connect(self.select_project)
        layout.addWidget(select_button)
        self.setLayout(layout)
    
    def select_project(self):
        self.selected_project = self.project_dropdown.currentText()
        self.accept()

class AboutDialog(QDialog):
    """application info."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Application")
        self.setGeometry(400, 300, 400, 200)
        layout = QVBoxLayout()
        about_label = QLabel(
            "<h2 style='color:#1976D2;'>Magna Test Execution Application</h2>"
            "<b>Version 1.0.0</b><br><br>"
            "This application is designed to execute and validate test cases for automotive systems."
        )
        about_label.setWordWrap(True)
        layout.addWidget(about_label)
        self.setLayout(layout)

class AboutCreatorsDialog(QDialog):
    """creators info."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Creators")
        self.setGeometry(400, 300, 450, 250)
        layout = QVBoxLayout()
        creators_info = (
            "<h3 style='color:#1976D2;'>Developed and Designed by:</h3>"
            "<p style='font-size:14px;'><b>Software Test Team, Auburn Hills, MI, USA</b></p>"
            "<h3 style='color:#333;'>Team Members:</h3>"
            "<ul style='font-size:13px;'>"
            "<li><b>Kevin Delong</b> - kevin.delong@magna.com</li>"
            "<li><b>Azharul Haque</b> - azharul.haque@magna.com</li>"
            "<li><b>Sayma Tamboli</b> - sayma.tamboli@magna.com</li>"
            "</ul>"
        )
        label = QLabel(creators_info)
        label.setWordWrap(True)
        label.setTextFormat(Qt.RichText)
        label.setOpenExternalLinks(True)
        layout.addWidget(label)
        self.setLayout(layout)

class FeedbackDialog(QDialog):
    """Dialog for user feedback submission."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Feedback")
        self.setGeometry(400, 300, 400, 300)
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Your Name")
        form_layout.addRow("Name:", self.name_input)

        self.feedback_input = QTextEdit()
        self.feedback_input.setPlaceholderText("Your Feedback...")
        form_layout.addRow("Feedback:", self.feedback_input)

        # Star rating (1 to 5)
        self.rating_layout = QHBoxLayout()
        self.stars = []
        for i in range(5):
            star = ToggleButton("★")
            star.setFont(QFont("Arial", 20))
            star.setStyleSheet("background-color: lightgray; color: black;")
            star.clicked.connect(lambda checked, idx=i: self.update_stars(idx))
            self.rating_layout.addWidget(star)
            self.stars.append(star)
        form_layout.addRow("Rating:", self.rating_layout)

        submit_btn = ToggleButton("Submit")
        submit_btn.clicked.connect(self.submit_feedback)

        layout.addLayout(form_layout)
        layout.addWidget(submit_btn)
    
    def update_stars(self, index):
        """Highlight stars based on selected rating."""
        colors = ["lightblue", "lightgreen", "pink", "gold", "orange"]
        for i, star in enumerate(self.stars):
            star.setStyleSheet("background-color: lightgray; color: " + (colors[index] if i <= index else "black") + ";")
        self.selected_rating = index + 1

    def submit_feedback(self):
        """Write feedback to CSV."""
        name = self.name_input.text()
        feedback = self.feedback_input.toPlainText()
        rating = getattr(self, "selected_rating", 0)
        with open("feedback.csv", "a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([name, feedback, rating])
        QMessageBox.information(self, "Thank You", f"Thank you {name} for your feedback!")
        self.accept()


# ---------------------------
# Ethernet Logger
# ---------------------------
from scapy.all import sniff, wrpcap

class EthernetLogger(QThread):
    status_signal = pyqtSignal(str)

    def __init__(self, filter_str, output_file, packet_count=0):
        super().__init__()
        self.filter_str = filter_str
        self.output_file = output_file
        self.packet_count = packet_count
        self.stop_flag = False
        self.packets = []

    def run(self):
        self.status_signal.emit("Ethernet Logger Started...")
        try:
            sniff(filter=self.filter_str,
                  prn=lambda pkt: self.packets.append(pkt),
                  stop_filter=lambda pkt: self.stop_flag,
                  store=True)
            wrpcap(self.output_file, self.packets)
            self.status_signal.emit(f"Saved packets to {self.output_file}")
        except Exception as e:
            self.status_signal.emit(f"Error: {e}")

    def stop(self):
        self.stop_flag = True


# ---------------------------
# CANoe Test Classes
# ---------------------------
class CanoeMeasurementEvents(object):
    def OnStart(self):
        CanoeSync.Started = True
        CanoeSync.Stopped = False
        log_and_print("Info: Measurement started!!")
    
    def OnStop(self):
        CanoeSync.Started = False
        CanoeSync.Stopped = True
        log_and_print("Info: Measurement stopped!!")

class CanoeTestConfiguration:
    def __init__(self, tc):
        self.tc = tc
        self.Name = tc.Name
        self.Events = win32com.client.DispatchWithEvents(tc, CanoeTestEvents)
        self.Events.Name = self.Name
        self.IsDone = lambda: self.Events.stopped
        self.Enabled = tc.Enabled

    def Start(self):
        if self.tc.Enabled:
            log_and_print(f"< {self.Name} starting >")
            self.tc.Start()
            self.Events.WaitForStop()  # Wait until the test completes
            log_and_print(f"< {self.Name} completed >")
            return None  # runtime is tracked manually in the worker

class CanoeTestEvents:
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

# ---------------------------
# CanoeWorker (Thread) Class
# ---------------------------
class CanoeWorker(QThread):
    status_signal = pyqtSignal(str)
    stop_signal = pyqtSignal()

    def __init__(self, canoe_config_path, test_script_paths, selected_project, iteration_data, parent=None):
        super().__init__(parent)
        self.canoe_config_path = canoe_config_path
        self.test_script_paths = test_script_paths
        self.selected_project = selected_project
        self.iteration_data = iteration_data  # Includes VTU iterations, run counts, and callback
        self.canoe_sync = None
        self.stop_requested = False

    def request_stop(self):
        """Stop CANoe simulation."""
        self.stop_requested = True
        if self.canoe_sync:
            try:
                self.canoe_sync.Stop()
                self.status_signal.emit("SIMULATION_STATUS: Stop requested — CANoe stopped.")
            except Exception as e:
                self.status_signal.emit("SIMULATION_STATUS: Error stopping CANoe: " + str(e))

    def run(self):
        """Thread execution logic for running CANoe test scripts."""
        try:
            self.status_signal.emit("SIMULATION_STATUS: Initializing CANoe...")
            self.canoe_sync = CanoeSync()

            self.status_signal.emit("SIMULATION_STATUS: Loading CANoe configuration...")
            self.canoe_sync.Load(self.canoe_config_path)

            # Prepare list of scripts with remaining iterations
            filtered_scripts = []
            for vtu in self.test_script_paths:
                count = self.iteration_data['iterations'].get(vtu, 1)
                done = self.iteration_data['run_counts'].get(vtu, 0)
                remaining = count - done
                if remaining > 0:
                    filtered_scripts.extend([vtu] * remaining)

            total = len(filtered_scripts)

            for idx, vtu in enumerate(filtered_scripts, start=1):
                if self.stop_requested:
                    self.status_signal.emit("SIMULATION_STATUS: Stop requested. Aborting further executions.")
                    break

                vtuname = os.path.basename(vtu)
                self.status_signal.emit(f"QUEUE_ITERATION: {idx}/{total}")
                self.status_signal.emit(f"TEST_EXEC_STATUS: Running {vtuname}")

                vtu_start_time = time.time()  # Start runtime timer

                try:
                    # Load VTU and start CANoe
                    self.canoe_sync.LoadTestConfiguration(vtuname, vtu)
                    self.status_signal.emit("SIMULATION_STATUS: Starting CANoe simulation...")
                    self.canoe_sync.Start()

                    # Run all test configs
                    for tc in self.canoe_sync.TestConfigs:
                        runtime = tc.Start()
                        if runtime is not None:
                            self.status_signal.emit(f"TEST_EXEC_STATUS: {tc.Name} runtime: {runtime:.2f}s")

                        while not tc.IsDone():
                            if self.stop_requested:
                                self.status_signal.emit("SIMULATION_STATUS: Stop requested during test configuration execution.")
                                break
                            DoEvents()

                    # Stop simulation
                    self.status_signal.emit("SIMULATION_STATUS: Stopping CANoe simulation...")
                    self.canoe_sync.Stop()

                    # Report total runtime
                    vtu_end_time = time.time()
                    total_runtime = vtu_end_time - vtu_start_time
                    self.status_signal.emit(f"TEST_EXEC_STATUS: Total runtime for {vtuname}: {total_runtime:.2f} seconds")
                    self.status_signal.emit(f"TEST_EXEC_STATUS: {vtuname} Completed!!")

                    # Mark iteration completed
                    self.iteration_data['run_counts'][vtu] = self.iteration_data['run_counts'].get(vtu, 0) + 1
                    if self.iteration_data.get('update_func'):
                        self.iteration_data['update_func']()

                    # Save CANoe report
                    self.save_report(vtu)

                except Exception as vtu_error:
                    error_msg = f"ERROR: VTU '{vtuname}' failed — {str(vtu_error)}"
                    self.status_signal.emit(f"TEST_EXEC_STATUS: {error_msg}")
                    log_and_print(error_msg)
                    try:
                        self.canoe_sync.Stop()
                    except:
                        pass

                # Cool-down delay between scripts
                for i in range(5):
                    if self.stop_requested:
                        break
                    self.status_signal.emit(f"QUEUE_ITERATION: Waiting {i+1} sec...")
                    time.sleep(1)

            self.status_signal.emit("SIMULATION_STATUS: All VTU executions completed!!.")

        except Exception as e:
            self.status_signal.emit(f"Error during CANoe execution: {str(e)}")

    def save_report(self, vtu_file):
        """Move HTML/XML report files to destination folder."""
        vtuname = os.path.splitext(os.path.basename(vtu_file))[0]
        config_folder = os.path.dirname(self.canoe_config_path)

        # Match report file patterns
        pattern_html = os.path.join(config_folder, f"Report_{vtuname}*.html")
        pattern_xml = os.path.join(config_folder, f"Report_{vtuname}*.xml")
        report_files = glob.glob(pattern_html) + glob.glob(pattern_xml)

        if not report_files:
            self.status_signal.emit(f"SIMULATION_STATUS: No HTML/XML report found for {vtuname} in {config_folder}")
            return

        # Destination folder for reports
        dest_folder = os.path.join(BASE_DIR, self.selected_project, "Reports", "HTML_XML_Reports", vtuname + "_reports")
        if not os.path.exists(dest_folder):
            os.makedirs(dest_folder)

        for source_report in report_files:
            dest_file = os.path.join(dest_folder, os.path.basename(source_report))
            try:
                shutil.move(source_report, dest_file)
                self.status_signal.emit(f"TEST_EXEC_STATUS: Report {os.path.basename(source_report)} for {vtuname} saved to {dest_folder}")
            except Exception as e:
                self.status_signal.emit(f"TEST_EXEC_STATUS: Error saving report {os.path.basename(source_report)} for {vtuname}: {str(e)}")

class CanoeSync:
    # Global flags 
    Started = False
    Stopped = False
    ConfigPath = ""

    def __init__(self):
        """Initialize CANoe application and set up measurement handlers."""
        try:
            pythoncom.CoInitializeEx(0)
            app = win32com.client.DispatchEx('CANoe.Application')
            app.Configuration.Modified = False
            ver = app.Version
            log_and_print(f"Loaded CANoe version {ver.major}.{ver.minor}.{ver.Build}")

            self.App = app
            self.Measurement = app.Measurement
            self.Running = lambda: self.Measurement.Running
            self.WaitForStart = lambda: DoEventsUntil(lambda: CanoeSync.Started)
            self.WaitForStop = lambda: DoEventsUntil(lambda: CanoeSync.Stopped)

            # measurement event handlers
            win32com.client.WithEvents(self.App.Measurement, CanoeMeasurementEvents)
        except Exception as e:
            error_and_exit(f"Failed to load CANoe: {e}", 1)

    def Load(self, cfgPath):
        """Load a CANoe configuration file (.cfg)."""
        if os.path.isfile(cfgPath):
            try:
                cfg = os.path.abspath(cfgPath)
                log_and_print(f"Opening config: {cfg}")
                self.ConfigPath = os.path.dirname(cfg)
                self.Configuration = self.App.Configuration
                self.App.Open(cfg)
                log_and_print("Configuration loaded successfully.")
            except Exception as e:
                log_and_print(f"Failed to load CANoe configuration: {e}")
                error_and_exit(f"Failed to load CANoe configuration: {e}", 2)
        else:
            error_and_exit(f"Configuration file does not exist: {cfgPath}", 2)

    def Start(self):
        """Start the CANoe measurement if not already running."""
        if not self.Running():
            try:
                self.Measurement.Start()
                self.WaitForStart()
                log_and_print("Measurement started successfully.")
            except Exception as e:
                error_and_exit(f"Failed to start measurement: {e}", 4)

    def Stop(self):
        """Stop the CANoe measurement if running."""
        if self.Running():
            try:
                self.Measurement.Stop()
                self.WaitForStop()
                log_and_print("Measurement stopped successfully.")
            except Exception as e:
                error_and_exit(f"Failed to stop measurement: {e}", 5)

    def LoadTestConfiguration(self, testcfgname, testunit):
        """Load a VTU file as a new test configuration."""
        if os.path.isfile(testunit):
            try:
                # unique test configuration name
                existing_names = [tc.Name for tc in self.App.Configuration.TestConfigurations]
                if testcfgname in existing_names:
                    testcfgname += f"_{len(existing_names)}"

                tc = self.App.Configuration.TestConfigurations.Add()
                tc.Name = testcfgname

                # Add VTU to the test unit slot
                tus = win32com.client.CastTo(tc.TestUnits, "ITestUnits2")
                tus.Add(testunit)

                log_and_print(f"VTU file {testunit} loaded successfully.")
                self.TestConfigs = [CanoeTestConfiguration(tc)]
                log_and_print(f"Test configuration {testcfgname} added successfully.")
            except Exception as e:
                error_and_exit(f"Failed to load test configuration: {e}", 3)
        else:
            error_and_exit(f"File does not exist: {testunit}", 3)

    def RunTestConfigs(self):
        """Run all loaded test configurations."""
        try:
            for tc in self.TestConfigs:
                tc.Start()
            log_and_print("Test configurations run completed.")
        except Exception as e:
            error_and_exit(f"Failed to run test configurations: {e}", 6)

    def closeEvent(self, event):
        """Cleanup CANoe resources on application close."""
        if hasattr(self, 'canoe_sync') and self.canoe_sync:
            self.canoe_sync.Stop()
        log_and_print("Application closed. Resources cleaned up.")
        event.accept()

# ---------------------------
# TestExecutionApp (Main Window) Class
    def start_ethernet_logging(self):
        if not self.eth_enable_toggle.selected:
            self.append_log("Ethernet logging not enabled.")
            return

        fmt = self.eth_format_combo.currentText().lower()
        filter_str = self.eth_filter_input.text().strip()
        filename = QFileDialog.getSaveFileName(self, "Save Ethernet Log", "", f"{fmt.upper()} Files (*.{fmt})")[0]
        if not filename:
            return

        if not filename.endswith(f".{fmt}"):
            filename += f".{fmt}"

        self.eth_logger_thread = EthernetLogger(filter_str, filename)
        self.eth_logger_thread.status_signal.connect(self.append_log)
        self.eth_logger_thread.start()
        self.eth_start_button.setEnabled(False)
        self.eth_stop_button.setEnabled(True)

    def stop_ethernet_logging(self):
        if hasattr(self, 'eth_logger_thread'):
            self.eth_logger_thread.stop()
            self.eth_logger_thread.quit()
            self.eth_logger_thread.wait()
            self.append_log("Ethernet logging stopped.")
            self.eth_start_button.setEnabled(True)
            self.eth_stop_button.setEnabled(False)

# ---------------------------
class TestExecutionApp(QMainWindow):
    def __init__(self, selected_project):
        super().__init__()
        self.selected_project = selected_project
        self.test_thread = None
        self.settings = QSettings("Magna", "TestExecutionApp")
        self.project_history = self.settings.value("project_history", []) or []
        self.canoe_config_file = ""
        self.canoe_config_path = ""
        self.test_script_paths = []  # List of selected VTUexe files
        self.canoe_sync = None
        self.canoe_worker = None
        self.vtu_iterations = {}     # VTU path -> total iterations
        self.vtu_run_counts = {}     # VTU path -> completed iterations
        self.execution_started = False
        self.initUI()

    def initUI(self):
        """Initialize UI layout and elements."""
        self.setWindowTitle('Magna Test Execution Application - CVADAS Core')
        self.setGeometry(100, 100, 900, 600)

        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)

        # Top-level layout for the main window
        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(5)

        # Status labels
        self.simulation_status_label = QLabel("Simulation Status: Not started")
        self.main_layout.addWidget(self.simulation_status_label)

        self.canoe_status_label = QLabel("CANoe Status: Not running")
        self.canoe_status_label.setStyleSheet("color: red;")
        self.main_layout.addWidget(self.canoe_status_label)

        self.test_execution_status_label = QLabel("Test Execution Status: Not started")
        self.main_layout.addWidget(self.test_execution_status_label)

        self.queue_iterations_label = QLabel("Testing Queue Iterations: 0")
        self.main_layout.addWidget(self.queue_iterations_label)

        # Buttons: Start, Stop, View Report, Logs
        button_layout = QHBoxLayout()
        button_layout.setSpacing(5)

        self.start_button = QPushButton("START")
        self.start_button.setStyleSheet("background-color: green; color: white; font-weight: bold; padding: 12px;")
        self.start_button.clicked.connect(self.start_execution)
        button_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("STOP")
        self.stop_button.setStyleSheet("background-color: red; color: white; font-weight: bold; padding: 12px;")
        self.stop_button.clicked.connect(self.stop_execution)
        button_layout.addWidget(self.stop_button)

        self.view_report_button = ToggleButton("VIEW REPORT")
        self.view_report_button.setStyleSheet("background-color: lightgray; color: black; font-weight: bold; padding: 12px;")
        self.view_report_button.clicked.connect(self.show_report_options)
        button_layout.addWidget(self.view_report_button)

        self.view_can_log_button = ToggleButton("VIEW CAN LOG")
        self.view_can_log_button.setStyleSheet("background-color: lightgray; color: black; font-weight: bold; padding: 12px;")
        self.view_can_log_button.clicked.connect(lambda: self.open_folder(
            os.path.join(BASE_DIR, self.selected_project, "Reports", "Logs", "CAN_Log")))
        button_layout.addWidget(self.view_can_log_button)

        self.view_uart_log_button = ToggleButton("VIEW UART LOG")
        self.view_uart_log_button.setStyleSheet("background-color: lightgray; color: black; font-weight: bold; padding: 12px;")
        button_layout.addWidget(self.view_uart_log_button)

        self.main_layout.addLayout(button_layout)

        # Split layout into left (VTUs) and right (Log Output)
        self.main_columns_layout = QHBoxLayout()

        self.vtu_scroll_area = self.populate_vtu_exes()  # VTU buttons and spinboxes
        self.main_columns_layout.addWidget(self.vtu_scroll_area, 1)

        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setFrameShadow(QFrame.Sunken)
        self.main_columns_layout.addWidget(divider)

        self.output_column = QVBoxLayout()
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("background-color: #fff3e0; font-size: 14px;")
        self.output_column.addWidget(self.log_output)
        self.main_columns_layout.addLayout(self.output_column, 1)
        self.main_layout.addLayout(self.main_columns_layout)

        # logging
        self.log_handler = QTextEditLogger()
        self.log_handler.setFormatter(logging.Formatter("%(message)s"))
        self.log_handler.log_signal.connect(self.append_log)
        logging.getLogger().addHandler(self.log_handler)

        # check if CANoe is running
        self.canoe_status_timer = QTimer(self)
        self.canoe_status_timer.timeout.connect(self.check_canoe_status)
        self.canoe_status_timer.start(1000)

        # Status bar for COM port info
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.serial_status = QLabel("Serial COM Ports: ")
        self.serial_status.setStyleSheet("color: green; font-weight: bold;")
        self.status_bar.addWidget(self.serial_status)

        # Menu Bar and actions
        self.menu_bar = QMenuBar(self)
        self.menu_bar.setStyleSheet("QMenu::item:selected { background-color: #1976D2; color: black; }")
        self.setMenuBar(self.menu_bar)

        # File menu
        file_menu = self.menu_bar.addMenu("File")
        file_menu.addAction(QAction("Open Different Project", self, triggered=self.open_project_selection))
        file_menu.addAction(QAction("Upload VTU File", self, triggered=self.upload_vtu_file))
        file_menu.addAction(QAction("View History", self, triggered=self.view_history))
        file_menu.addAction(QAction("Exit", self, triggered=self.close_application))

        # About menu
        about_menu = self.menu_bar.addMenu("About")
        about_menu.addAction(QAction("About Application", self, triggered=self.show_about_info))
        about_menu.addAction(QAction("Authors", self, triggered=self.show_about_creators))
        about_menu.addAction(QAction("Feedback", self, triggered=self.show_feedback_form))

        # Tools menu
        tools_menu = self.menu_bar.addMenu("Tools")
        tools_menu.addAction(QAction("Miscellaneous Tools", self, triggered=self.open_tools))

    def append_log(self, msg):
        """Append log message to the log output."""
        self.log_output.append(msg)

    def generate_excel_reports(self):
        """Generate and export Excel reports from XML test results."""
        for vtu_file in self.test_script_paths:
            vtuname = os.path.splitext(os.path.basename(vtu_file))[0]
            report_folder = os.path.join(BASE_DIR, self.selected_project, "Reports", "HTML_XML_Reports", vtuname + "_reports")

            # Handle both single and multiple execution XML report formats
            pattern_single = os.path.join(report_folder, f"Report_{vtuname}.xml")
            pattern_multi = os.path.join(report_folder, f"Report_{vtuname}_*.xml")
            xml_files = glob.glob(pattern_single) + glob.glob(pattern_multi)

            if not xml_files:
                log_and_print(f"No XML reports found for {vtuname} in {report_folder}")
                continue

            all_data = []
            for xml_file in xml_files:
                report_data = parse_xml_report(xml_file)
                if report_data:
                    all_data.extend(report_data)
                else:
                    log_and_print(f"Parsing failed for {xml_file}")

            if all_data:
                excel_folder = os.path.join(BASE_DIR, self.selected_project, "Reports", "Excel_Sheet", vtuname + "_executed")
                os.makedirs(excel_folder, exist_ok=True)
                output_csv = os.path.join(excel_folder, f"{vtuname}_excel_report.csv")
                export_to_excel(all_data, output_csv)

    def process_status_message(self, msg):
        """Update the appropriate status label based on message prefix."""
        if msg.startswith("SIMULATION_STATUS:"):
            status = msg.split(":", 1)[1].strip()
            self.simulation_status_label.setText("Simulation Status: " + status)
        elif msg.startswith("CANOE_STATUS:"):
            status = msg.split(":", 1)[1].strip()
            self.canoe_status_label.setText("CANoe Status: " + status)
        elif msg.startswith("TEST_EXEC_STATUS:"):
            status = msg.split(":", 1)[1].strip()
            self.test_execution_status_label.setText("Test Execution Status: " + status)
        elif msg.startswith("QUEUE_ITERATION:"):
            count = msg.split(":", 1)[1].strip()
            self.queue_iterations_label.setText("Testing Queue Iterations: " + count)
        else:
            self.simulation_status_label.setText(msg)
        self.log_output.append(msg)

    def populate_vtu_exes(self):
        """Create scrollable list of VTU buttons with iteration spin boxes."""
        self.vtu_buttons = {}
        vtu_dir = os.path.join(BASE_DIR, self.selected_project, "VTUexes")

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        container = QWidget()
        container.setStyleSheet("background-color: #fff3e0;")

        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(10, 10, 10, 10)
        grid_layout.setVerticalSpacing(15)
        grid_layout.setHorizontalSpacing(15)

        if not os.path.exists(vtu_dir):
            log_and_print(f"VTUexes folder not found: {vtu_dir}")
            grid_layout.addWidget(QLabel("VTUexes folder not found."), 0, 0)
        else:
            vtu_files = glob.glob(os.path.join(vtu_dir, "*.vtuexe"))
            if not vtu_files:
                log_and_print(f"No VTUexe files found in {vtu_dir}")
                grid_layout.addWidget(QLabel("No VTUexe files found."), 0, 0)
            else:
                col_count = 3
                for idx, file in enumerate(vtu_files):
                    vtuname = os.path.splitext(os.path.basename(file))[0]

                    # ToggleButton
                    btn = ToggleButton(vtuname)
                    btn.setFixedSize(130, 60)
                    btn.clicked.connect(lambda checked, f=file: self.select_vtu_file(f))
                    self.vtu_buttons[vtuname] = btn

                    # SpinBox for iterations
                    spin = QSpinBox()
                    spin.setMinimum(1)
                    spin.setValue(1)
                    spin.setMaximum(100)
                    spin.setFixedWidth(50)
                    spin.valueChanged.connect(lambda val, f=file: self.update_vtu_iterations(f, val))

                    # Combine button and spin into grid
                    row = idx // col_count
                    col = idx % col_count
                    layout = QHBoxLayout()
                    layout.addWidget(btn)
                    layout.addWidget(spin)
                    wrapper = QWidget()
                    wrapper.setLayout(layout)
                    grid_layout.addWidget(wrapper, row, col, alignment=Qt.AlignLeft)

        outer_layout = QVBoxLayout(container)
        outer_layout.setContentsMargins(10, 10, 10, 10)
        outer_layout.addLayout(grid_layout)
        outer_layout.addStretch()
        scroll_area.setWidget(container)
        return scroll_area

    def update_vtu_iterations(self, vtu_file, count):
        """Update iteration count for a given VTU file."""
        self.vtu_iterations[vtu_file] = count
        self.vtu_run_counts.setdefault(vtu_file, 0)
        self.update_queue_label()

    def update_queue_label(self):
        """Update VTU execution status and disable completed buttons."""
        for vtu_file, btn in self.vtu_buttons.items():
            full_path = os.path.normpath(os.path.join(BASE_DIR, self.selected_project, "VTUexes", vtu_file + ".vtuexe"))
            total = self.vtu_iterations.get(full_path, 0)
            done = self.vtu_run_counts.get(full_path, 0)
            if self.execution_started and done >= total:
                btn.setEnabled(False)
                btn.setSelected(False)

        total = sum(self.vtu_iterations.get(f, 0) for f in self.test_script_paths)
        done = sum(self.vtu_run_counts.get(f, 0) for f in self.test_script_paths)
        self.queue_iterations_label.setText(f"Testing Queue Iterations: {done}/{total}")

    def select_vtu_file(self, file):
        """Select a VTU file for execution."""
        norm_file = os.path.normpath(file)
        vtuname = os.path.splitext(os.path.basename(norm_file))[0]
        if norm_file not in self.test_script_paths:
            total = self.vtu_iterations.get(norm_file, 1)
            done = self.vtu_run_counts.get(norm_file, 0)
            if done >= total:
                log_and_print(f"Skipping VTU {norm_file}: all iterations completed.")
                return
            self.test_script_paths.append(norm_file)
            self.vtu_iterations.setdefault(norm_file, 1)
            self.vtu_run_counts.setdefault(norm_file, 0)
            self.update_queue_label()
            log_and_print("Selected VTUexe: " + norm_file)
            btn = self.vtu_buttons.get(vtuname)
            if btn:
                btn.setSelected(True)
        else:
            log_and_print("VTUexe already selected: " + norm_file)

    def upload_vtu_file(self):
        """Allow user to upload a new VTU file to the project."""
        options = QFileDialog.Options()
        path, _ = QFileDialog.getOpenFileName(self, "Upload VTU File", "", "VTUexe Files (*.vtuexe);;All Files (*)", options=options)
        if path:
            dest = os.path.join(BASE_DIR, self.selected_project, "VTUexes")
            os.makedirs(dest, exist_ok=True)
            try:
                shutil.copy(path, os.path.join(dest, os.path.basename(path)))
                log_and_print("Uploaded VTU file to " + dest)
                self.vtu_scroll_area.setParent(None)
                self.vtu_scroll_area = self.populate_vtu_exes()
                self.main_columns_layout.insertWidget(0, self.vtu_scroll_area)
            except Exception as e:
                QMessageBox.warning(self, "Upload Error", str(e))

    def start_execution(self):
        """Start the CANoe simulation with selected VTUs."""
        try:
            log_and_print("SIMULATION_STATUS: Attempting to start CANoe measurement...")
            config_file = self.get_config_file_path()
            log_and_print(f"DEBUG: Using configuration file: {config_file}")
            self.canoe_config_path = config_file

            if not self.test_script_paths:
                raise Exception("No VTUexe file selected. Please select one or more VTUexe files before starting execution.")
            
            self.disable_buttons(keep_stop=True)

            # Prepare execution data
            iteration_data = {
                'iterations': self.vtu_iterations,
                'run_counts': self.vtu_run_counts,
                'update_func': self.update_queue_label
            }

            # Start the worker thread
            self.canoe_worker = CanoeWorker(
                self.canoe_config_path,
                self.test_script_paths,
                self.selected_project,
                iteration_data
            )
            self.canoe_worker.status_signal.connect(self.process_status_message)
            self.canoe_worker.finished.connect(self.enable_buttons)
            self.canoe_worker.start()

            self.simulation_status_label.setText("SIMULATION_STATUS: CANoe Measurement Started")
            self.canoe_status_label.setText("CANOE_STATUS: Running")
            self.canoe_status_label.setStyleSheet("color: green;")
        except Exception as e:
            log_and_print(f"Error starting CANoe measurement: {str(e)}")
            self.simulation_status_label.setText(f"Error: {str(e)}")

    def stop_execution(self):
        """Stop the running CANoe simulation."""
        try:
            log_and_print("SIMULATION_STATUS: Attempting to stop CANoe measurement...")
            if self.canoe_worker and self.canoe_worker.isRunning():
                self.canoe_worker.request_stop()
            else:
                log_and_print("SIMULATION_STATUS: No running CANoe process detected.")
            self.simulation_status_label.setText("SIMULATION_STATUS: Stop requested")
            self.canoe_status_label.setText("CANOE_STATUS: Not running")
            self.canoe_status_label.setStyleSheet("color: red;")
            self.enable_buttons()
        except Exception as e:
            log_and_print(f"Error while stopping CANoe measurement: {e}")
            self.simulation_status_label.setText(f"Error: {e}")

    def disable_buttons(self, keep_stop=False):
        """Disable all UI buttons during test execution, except STOP."""
        for button in self.vtu_buttons.values():
            if button.text() not in [os.path.basename(f) for f in self.test_script_paths]:
                button.setEnabled(False)
        self.view_report_button.setEnabled(False)
        self.view_can_log_button.setEnabled(False)
        self.view_uart_log_button.setEnabled(False)
        self.start_button.setEnabled(False)
        if not keep_stop:
            self.stop_button.setEnabled(False)

    def enable_buttons(self):
        """Re-enable all UI buttons after test execution."""
        for button in self.vtu_buttons.values():
            button.setEnabled(True)
            button.setSelected(False)
        self.view_report_button.setEnabled(True)
        self.view_can_log_button.setEnabled(True)
        self.view_uart_log_button.setEnabled(True)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(True)

    def get_config_file_path(self):
        """Find and return the latest .cfg file from the CANoe_RBS folder."""
        project_folder = os.path.join(BASE_DIR, self.selected_project)
        rb_folder = os.path.join(project_folder, "CANoe_RBS")
        if not os.path.exists(rb_folder):
            raise Exception("CANoe_RBS folder not found.")
        
        subs = [d for d in os.listdir(rb_folder) if os.path.isdir(os.path.join(rb_folder, d))]
        if not subs:
            raise Exception("No subfolder in CANoe_RBS.")
        
        chosen = max(subs, key=lambda d: os.path.getmtime(os.path.join(rb_folder, d)))
        cfg_folder = os.path.join(rb_folder, chosen)
        cfg_files = [f for f in os.listdir(cfg_folder) if f.lower().endswith('.cfg')]
        if not cfg_files:
            raise Exception("No .cfg file found.")
        
        config_path = os.path.join(cfg_folder, cfg_files[0])
        log_and_print(f"DEBUG: Selected CANoe Config File: {config_path}")
        return config_path

    def show_report_options(self):
        """Display dialog for choosing which report type to view."""
        dialog = QDialog(self)
        dialog.setWindowTitle("View Report Options")
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        layout.addWidget(QLabel("Select Report Type to View:"))

        # Excel Report Button
        btn_excel = ToggleButton("Excel Sheet")
        btn_excel.clicked.connect(lambda: [
            self.generate_excel_reports(),
            self.open_folder(os.path.join(BASE_DIR, self.selected_project, "Reports", "Excel_Sheet"))
        ])
        layout.addWidget(btn_excel)

        # HTML/XML Report Button
        btn_html = ToggleButton("HTML/XML Reports")
        btn_html.clicked.connect(lambda: self.open_folder(
            os.path.join(BASE_DIR, self.selected_project, "Reports", "HTML_XML_Reports")))
        layout.addWidget(btn_html)

        dialog.setLayout(layout)
        dialog.exec_()

    def open_folder(self, folder):
        """Open a folder."""
        if os.path.exists(folder):
            os.startfile(folder)
        else:
            QMessageBox.warning(self, "Folder Not Found", "Folder does not exist: " + folder)

    def open_project_selection(self):
        """Show dialog to switch to a different project."""
        dialog = ProjectSelectionDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            new_proj = dialog.selected_project
            self.reload_project(new_proj)

    def reload_project(self, new_project):
        """Close and reload application with a different project."""
        self.update_history()
        self.close()
        self.new_app = TestExecutionApp(new_project)
        self.new_app.project_history = self.project_history
        self.new_app.show()

    def view_history(self):
        """Display list of previously opened projects."""
        if self.project_history:
            history_message = "\n".join(self.project_history)
        else:
            history_message = "No previous projects."
        QMessageBox.information(self, "Project History", f"Previously Opened Projects:\n{history_message}")

    def update_history(self):
        """Add the current project to history if not already listed."""
        if self.selected_project and self.selected_project not in self.project_history:
            self.project_history.append(self.selected_project)

    def close_application(self):
        """close the application and terminate CANoe process if running."""
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            output = subprocess.check_output(['tasklist'], startupinfo=startupinfo, universal_newlines=True)
            if 'CANoe64.exe' in output:
                log_and_print("CANoe64.exe is running. Attempting to kill the process...")
                subprocess.call(["taskkill", "/F", "/IM", "CANoe64.exe"], startupinfo=startupinfo)
                log_and_print("CANoe64.exe process killed.")
        except Exception as e:
            log_and_print(f"Error while killing CANoe process: {e}")
        self.close()

    def show_about_info(self):
        """Open the About Application dialog."""
        about_dialog = AboutDialog(self)
        about_dialog.exec_()

    def show_about_creators(self):
        """Open the About Creators dialog."""
        about_creators_dialog = AboutCreatorsDialog(self)
        about_creators_dialog.exec_()

    def show_feedback_form(self):
        """Open the Feedback form dialog."""
        feedback_dialog = FeedbackDialog(self)
        feedback_dialog.exec_()

    def open_tools(self):
        """Stub for opening additional tools."""
        self.log_output.append("Opening Miscellaneous Tools...")

    def check_canoe_status(self):
        """Periodically check if CANoe is running and update UI."""
        try:
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            out = subprocess.check_output(['tasklist'], startupinfo=startup, universal_newlines=True)
            if "CANoe64.exe" in out:
                self.canoe_status_label.setText("CANoe Status: Ready")
                self.canoe_status_label.setStyleSheet("color: green;")
            else:
                self.canoe_status_label.setText("CANoe Status: Not ready")
                self.canoe_status_label.setStyleSheet("color: red;")
        except Exception as e:
            self.canoe_status_label.setText("Error: " + str(e))

# ----------------------------
# Application 
# ----------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    project_dialog = ProjectSelectionDialog()
    if project_dialog.exec_() == QDialog.Accepted:
        selected_project = project_dialog.selected_project

        # Setup logging path for selected project
        log_folder = os.path.join(BASE_DIR, selected_project, "Reports", "Logs", "CAN_Log")
        os.makedirs(log_folder, exist_ok=True)
        log_file = os.path.join(log_folder, "canoe_execution_log.txt")

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(log_file, mode="a", encoding="utf-8")
            ]
        )

        main_window = TestExecutionApp(selected_project)
        main_window.show()
        sys.exit(app.exec_())


