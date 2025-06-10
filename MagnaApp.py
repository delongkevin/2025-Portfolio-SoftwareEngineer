# Magna CANoe/Serial/Camera/TestRunner Test Application
import time
import re
import subprocess
import win32com.client
import pandas as pd
import sys
import xml.etree.ElementTree as ET
import pythoncom
import logging
import psutil
import glob
import os
import csv
import shutil
import json
import numpy as np
from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, QObject, QMutex, QMutexLocker, QTextCodec, QProcess
from PyQt5.QtWidgets import (
    QApplication, QDialog, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit,
    QComboBox, QHBoxLayout, QMenuBar, QAction, QStatusBar, QFrame, QMessageBox, QFormLayout,
    QLineEdit, QFileDialog, QScrollArea, QGridLayout, QTabWidget, QSpinBox, QSlider
)
from PyQt5.QtGui import QFont, QIcon, QTextCursor, QColor, QImage, QPixmap
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView 

try:
    import can
    PYTHON_CAN_AVAILABLE = True
    # Example: Supported interfaces by python-can often include 'socketcan', 'pcan', 'vector', 'kvaser', 'serial', 'usb2can', etc.
    # The exact backend setup (drivers, etc.) depends on the user's CAN hardware.
except ImportError:
    PYTHON_CAN_AVAILABLE = False
    print("Warning: python-can library not found. python-can logging feature disabled.")
    print("Install it using: pip install python-can")

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    print("Warning: PySerial library not found. Serial Monitor feature disabled.")

# --- OpenCV Import for Camera ---
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    print("Warning: OpenCV library not found. Camera View feature disabled.")

# --- PyQt5 Imports ---
from PyQt5.QtWidgets import (
    QApplication, QDialog, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit,
    QComboBox, QHBoxLayout, QMenuBar, QAction, QStatusBar, QFrame, QMessageBox, QFormLayout,
    QLineEdit, QFileDialog, QScrollArea, QGridLayout, QTabWidget
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QObject, QMutex, QMutexLocker, QTextCodec
from PyQt5.QtGui import QFont, QIcon, QTextCursor, QColor
from PyQt5.QtWidgets import QSpinBox

# --- Configuration File ---
CONFIG_FILE = Path("app_config.json")

# --- Style Constants ---
STYLE_SHEET = """
    QMainWindow, QDialog {
        background-color: #f0f0f0;
    }
    QWidget#mainTabWidget {
        background-color: #ffffff;
    }
    QLabel {
        font-size: 10pt;
    }
    QLabel[heading="true"] {
        font-size: 11pt;
        font-weight: bold;
        color: #003366;
        margin-bottom: 5px;
    }
    QPushButton {
        font-size: 10pt;
        padding: 8px 15px;
        border-radius: 4px;
        border: 1px solid #cccccc;
        background-color: #e7e7e7;
        color: #333333;
        min-width: 80px;
    }
    QPushButton:hover {
        background-color: #d4d4d4;
        border-color: #aaaaaa;
    }
    QPushButton:pressed {
        background-color: #c8c8c8;
    }
    QPushButton:disabled {
        background-color: #f0f0f0;
        color: #a0a0a0;
        border-color: #dcdcdc;
    }
    QPushButton#StartButton, QPushButton#RunScriptButton {
        background-color: #28a745;
        color: white;
        font-weight: bold;
        border-color: #218838;
    }
    QPushButton#StartButton:hover, QPushButton#RunScriptButton:hover { background-color: #218838; }
    QPushButton#StartButton:pressed, QPushButton#RunScriptButton:pressed { background-color: #1e7e34; }
    QPushButton#StartButton:disabled, QPushButton#RunScriptButton:disabled { background-color: #6fc281; border-color: #6fc281; color: #e0e0e0; }

    QPushButton#StopButton, QPushButton#StopScriptButton {
        background-color: #dc3545;
        color: white;
        font-weight: bold;
        border-color: #c82333;
    }
    QPushButton#StopButton:hover, QPushButton#StopScriptButton:hover { background-color: #c82333; }
    QPushButton#StopButton:pressed, QPushButton#StopScriptButton:pressed { background-color: #bd2130; }
    QPushButton#StopButton:disabled, QPushButton#StopScriptButton:disabled { background-color: #e97b85; border-color: #e97b85; color: #f5f5f5; }

    QPushButton#ReportButton {
        background-color: #007bff;
        color: white;
        font-weight: bold;
        border-color: #0069d9;
    }
    QPushButton#ReportButton:hover { background-color: #0069d9; }
    QPushButton#ReportButton:pressed { background-color: #005cbf; }

    QPushButton#ConfigFolderButton {
        background-color: #ffc107;
        color: #333333;
        font-weight: bold;
        border-color: #e0a800;
    }
    QPushButton#ConfigFolderButton:hover { background-color: #e0a800; }
    QPushButton#ConfigFolderButton:pressed { background-color: #d39e00; }

    QPushButton#SerialConnectButton {
        background-color: #17a2b8;
        color: white;
        border-color: #138496;
    }
    QPushButton#SerialConnectButton:hover { background-color: #138496; }
    QPushButton#SerialConnectButton:pressed { background-color: #117a8b; }
    QPushButton#SerialConnectButton:checked {
        background-color: #ffc107;
        color: #333333;
        border-color: #e0a800;
    }
     QPushButton#SerialConnectButton:checked:hover { background-color: #e0a800; }
     QPushButton#SerialConnectButton:checked:pressed { background-color: #d39e00; }

    QPushButton#SerialLogButton {
        background-color: #007bff;
        color: white;
        border-color: #0069d9;
    }
    QPushButton#SerialLogButton:hover { background-color: #0069d9; }
    QPushButton#SerialLogButton:pressed { background-color: #005cbf; }
    QPushButton#SerialLogButton:checked {
        background-color: #dc3545;
        color: white;
        border-color: #c82333;
    }
    QPushButton#SerialLogButton:checked:hover { background-color: #c82333; }
    QPushButton#SerialLogButton:checked:pressed { background-color: #bd2130; }
    
    QPushButton#SendCommandButton { /* Style for the new Send Command button */
        background-color: #6f42c1; /* Purple */
        color: white;
        border-color: #5a2a96;
    }
    QPushButton#SendCommandButton:hover { background-color: #5a2a96; }
    QPushButton#SendCommandButton:pressed { background-color: #4d247e; }
    QPushButton#SendCommandButton:disabled { background-color: #b39ddb; border-color: #b39ddb; }


    QPushButton#StopFeedButton {
        background-color: #dc3545;
        color: white;
        font-weight: bold;
        border-color: #c82333;
    }
    QPushButton#StopFeedButton:hover { background-color: #c82333; }
    QPushButton#StopFeedButton:pressed { background-color: #bd2130; }

    QTextEdit {
        border: 1px solid #cccccc;
        border-radius: 3px;
        background-color: #ffffff;
    }
    QTextEdit#AppLog, QTextEdit#TestRunnerLog {
        background-color:#f8f9fa;
        font-family: Consolas, Monaco, monospace;
        font-size: 10pt;
        color: #333333;
    }
     QTextEdit#SerialLog {
        background-color:#e8f4f8;
        font-family: Consolas, Monaco, monospace;
        font-size: 10pt;
        color: #333333;
    }

    QScrollArea {
        border: 1px solid #cccccc;
        border-radius: 3px;
        background-color: #ffffff;
    }
    QComboBox {
        padding: 5px;
        border: 1px solid #cccccc;
        border-radius: 3px;
        min-width: 100px;
    }
    QSpinBox {
         padding: 5px;
         border: 1px solid #cccccc;
         border-radius: 3px;
    }
    QSlider::groove:horizontal {
        border: 1px solid #bbb;
        background: white;
        height: 10px;
        border-radius: 4px;
    }
    QSlider::sub-page:horizontal {
        background: qlineargradient(x1: 0, y1: 0,    x2: 0, y2: 1,
            stop: 0 #66e, stop: 1 #bbf);
        background: qlineargradient(x1: 0, y1: 0.2, x2: 1, y2: 1,
            stop: 0 #bbf, stop: 1 #55f);
        border: 1px solid #777;
        height: 10px;
        border-radius: 4px;
    }
    QSlider::add-page:horizontal {
        background: #fff;
        border: 1px solid #777;
        height: 10px;
        border-radius: 4px;
    }
    QSlider::handle:horizontal {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #eee, stop:1 #ccc);
        border: 1px solid #777;
        width: 13px;
        margin-top: -2px;
        margin-bottom: -2px;
        border-radius: 4px;
    }
    QSlider::handle:horizontal:hover {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #fff, stop:1 #ddd);
        border: 1px solid #444;
        border-radius: 4px;
    }

    QMenuBar {
        background-color: #e0e0e0;
    }
    QMenuBar::item:selected {
        background-color: #007bff;
        color: white;
    }
    QMenu {
        background-color: white;
        border: 1px solid #cccccc;
    }
    QMenu::item:selected {
        background-color: #007bff;
        color: white;
    }
    QStatusBar {
        font-size: 9pt;
    }
    QTabWidget::pane {
        border-top: 2px solid #c2c7cb;
        margin-top: -2px;
    }
    QTabBar::tab {
        background: #e0e0e0;
        border: 1px solid #cccccc;
        border-bottom-color: #c2c7cb;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        min-width: 2ex;
        margin-right: 2px;
        color: #333333;
        padding: 8px 20px;
    }
    QTabBar::tab:selected, QTabBar::tab:hover {
        background: #f8f9fa;
        color: #003366;
        padding: 8px 20px;
    }
    QTabBar::tab:selected {
        border-color: #c2c7cb;
        border-bottom-color: #f8f9fa;
        font-weight: bold;
        padding: 8px 20px;
    }
    QTabBar::tab:!selected {
        margin-top: 14px;
        padding: 8px 25px;
    }

    QLabel#CanoeStatusLabel[status="Ready"] { color: #28a745; font-weight: bold; }
    QLabel#CanoeStatusLabel[status="Not Running"] { color: #dc3545; font-weight: bold; }
    QLabel#CanoeStatusLabel[status="Unknown"] { color: #fd7e14; font-weight: bold; }
    QLabel#CanoeStatusLabel[status="Error"] { color: #dc3545; font-weight: bold; }
    QLabel#CanoeStatusLabel[status="No Config"] { color: #777777; font-style: italic; }


    QLabel#SerialStatusLabel[status="Connected"] { color: #28a745; font-weight: bold; }
    QLabel#SerialStatusLabel[status="Disconnected"] { color: #dc3545; font-weight: bold; }
    QLabel#SerialStatusLabel[status="Error"] { color: #dc3545; font-weight: bold; }
"""

COM_DISCONNECTED_ERRORS = {
    -2147023174,
    -2147418107,
    -2147467263,
    -2147467259,
    -2147024891,
}

# --- Configuration Functions ---
def load_config():
    if CONFIG_FILE.is_file():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                if 'last_cfg_file' in config and config['last_cfg_file']:
                    cfg_path = Path(config['last_cfg_file'])
                    if not cfg_path.is_file() or cfg_path.suffix.lower() != '.cfg':
                        logging.warning(f"Config file '{config['last_cfg_file']}' invalid/not found.")
                        config['last_cfg_file'] = None
                return config
        except json.JSONDecodeError: logging.error(f"Error decoding {CONFIG_FILE}."); return {}
        except Exception as e: logging.error(f"Error loading {CONFIG_FILE}: {e}"); return {}
    return {}

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f: json.dump(config, f, indent=4)
        logging.info(f"Config saved to {CONFIG_FILE}")
    except Exception as e: logging.error(f"Error saving {CONFIG_FILE}: {e}")

# --- Logging Handler ---
class QTextEditLogger(logging.Handler, QObject):
    log_signal = pyqtSignal(str)
    def __init__(self, parent=None): super().__init__(); QObject.__init__(self, parent); self.setLevel(logging.INFO); self.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    def emit(self, record):
        try: msg = self.format(record); self.log_signal.emit(msg)
        except RecursionError: raise
        except Exception as e: print(f"Log emit error: {e}")

def log_and_print(message): logging.info(message)
def error_and_exit(message, code=1):
    logging.error(message)
    QMessageBox.critical(None, "Critical Error", message)
    sys.exit(code)

# --- COM Handling ---
def DoEvents():
    try: pythoncom.PumpWaitingMessages(); time.sleep(0.05)
    except Exception as e: log_and_print(f"DoEvents error: {e}")

def DoEventsUntil(cond, timeout=30):
    start_time = time.time()
    while not cond():
        if time.time() - start_time > timeout:
            log_and_print(f"Timeout in DoEventsUntil after {timeout}s.")
            return False
        DoEvents()
    return True

# --- XML Parsing & Exporting ---
def parse_xml_report(xml_file):
    try: tree = ET.parse(xml_file); root = tree.getroot(); test_data = [];
    except Exception as e: log_and_print(f"Failed parse XML: {xml_file} - {e}"); return None
    for test_exec in root.findall('.//TestExecution'):
        for test_case in test_exec.findall('.//TestCase'):
            test_name = test_case.get('title', "N/A"); start_time = test_case.get('starttime', '')
            verdict_elem = test_case.find('.//Verdict'); end_time = verdict_elem.get('endtime', '') if verdict_elem else ""; result = verdict_elem.get('result', '') if verdict_elem else ""
            for step in test_case.findall('.//TestStep'):
                timestamp = step.get('timestamp', ''); desc_elem = step.find('.//Description'); desc = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else ""
                step_result = step.get('result', '')
                test_data.append({'Test Name': test_name, 'Start Time': start_time, 'End Time': end_time, 'Step Description': desc, 'Step Timestamp': timestamp, 'Result': result, 'Step Result': step_result})
    if not test_data: log_and_print(f"Warning: No test data parsed from {xml_file}.")
    return test_data

def export_to_excel(report_data, output_excel_path):
    if not report_data: log_and_print(f"No data to export to {output_excel_path}"); return
    try: df = pd.DataFrame(report_data); output_path = Path(output_excel_path); output_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as mk_e: log_and_print(f"Error creating export dir: {mk_e}"); return
    try:
        if output_path.suffix.lower() == '.csv': df.to_csv(output_path, index=False, encoding='utf-8-sig')
        else:
            if output_path.suffix.lower() != '.xlsx': output_path = output_path.with_suffix('.xlsx')
            try: df.to_excel(output_path, index=False, engine='openpyxl')
            except ImportError: df.to_excel(output_path, index=False)
        log_and_print(f"Report exported to {output_path}")
    except Exception as e: log_and_print(f"Failed export report {output_excel_path}: {e}")

# --- Custom Toggle Button ---
class ToggleButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent); self.selected = False
        self.default_style = "QPushButton { background-color: #f8f9fa; color: #495057; border: 1px solid #ced4da; padding: 8px 12px; font-size: 10pt; border-radius: 4px; min-width: 80px; } QPushButton:hover { background-color: #e2e6ea; border-color: #adb5bd; } QPushButton:pressed { background-color: #dae0e5; } QPushButton:disabled { background-color: #e9ecef; color: #adb5bd; }"
        self.selected_style = "QPushButton { background-color: #007bff; color: white; border: 1px solid #0069d9; padding: 8px 12px; font-size: 10pt; font-weight: bold; border-radius: 4px; min-width: 80px; } QPushButton:hover { background-color: #0069d9; } QPushButton:pressed { background-color: #005cbf; } QPushButton:disabled { background-color: #6c757d; border-color: #6c757d; color: #e9ecef; }"
        self.setStyleSheet(self.default_style); self.setCursor(Qt.PointingHandCursor); self.setCheckable(True); self.clicked.connect(self.toggleState)
    def toggleState(self, checked): self.selected = checked; self.setStyleSheet(self.selected_style if self.selected else self.default_style)
    def setSelected(self, select: bool): self.setChecked(select)

# --- Dialog Classes ---
class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About")
        self.setGeometry(400, 300, 400, 200)
        layout = QVBoxLayout()
        about_label = QLabel("<h2 style='color:#003366;'>Magna Test Exec App</h2><b>V1.5.0</b><br><br>Runs CANoe tests, logs serial data, provides camera view, and includes a Python Test Runner.<br>Requires CANoe, PySerial, and OpenCV.") 
        about_label.setWordWrap(True)
        layout.addWidget(about_label)
        self.setLayout(layout)
class AboutCreatorsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Creators")
        self.setGeometry(400, 300, 450, 250)
        layout = QVBoxLayout(); creators_info = ("<h3 style='color:#003366;'>Developed by:</h3><p><b>SW Test Team, Auburn Hills, MI</b></p><h3>Team:</h3><ul><li>K. Delong</li><li>A. Haque</li><li>S. Tamboli</li></ul>")
        label = QLabel(creators_info)
        label.setWordWrap(True)
        label.setTextFormat(Qt.RichText)
        label.setOpenExternalLinks(True)
        layout.addWidget(label)
        self.setLayout(layout)
class FeedbackDialog(QDialog):
    def __init__(self, config_dir, parent=None):
        super().__init__(parent); self.config_dir = Path(config_dir)
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
        self.rating_layout = QHBoxLayout()
        self.stars = []
        self.selected_rating = 0
        [self._add_star(i) for i in range(5)]
        form_layout.addRow("Rating:", self.rating_layout)
        submit_btn = QPushButton("Submit")
        submit_btn.setStyleSheet("background-color: #007bff; color: white; padding: 10px; border-radius: 4px;")
        submit_btn.clicked.connect(self.submit_feedback); layout.addLayout(form_layout); layout.addWidget(submit_btn)
    def _add_star(self, idx):
        star = QPushButton("☆")
        star.setFont(QFont("Arial", 20))
        star.setFlat(True)
        star.setStyleSheet("color: gray; border: none;")
        star.setCursor(Qt.PointingHandCursor)
        star.clicked.connect(lambda checked, i=idx: self.update_stars(i))
        self.rating_layout.addWidget(star)
        self.stars.append(star)
    def update_stars(self, index):
        self.selected_rating = index + 1
        [star.setText("★" if i <= index else "☆") or star.setStyleSheet(f"color: {'#ffc107' if i <= index else 'gray'}; border: none;") for i, star in enumerate(self.stars)]
    def submit_feedback(self):
        name = self.name_input.text() or "Anon"
        feedback = self.feedback_input.toPlainText()
        rating = self.selected_rating
        feedback_file = self.config_dir / "feedback.csv"
        if not feedback:
            QMessageBox.warning(self, "Feedback Empty", "Please enter feedback.")
            return
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            file_exists = feedback_file.exists()
        except Exception as mk_e:
            QMessageBox.critical(self, "Save Error", f"Could not create dir:\n{mk_e}")
            return
        try:
            with open(feedback_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                (not file_exists and writer.writerow(["Timestamp", "Name", "Feedback", "Rating"]))
                writer.writerow([time.strftime("%Y%m%d_%H%M%S"), name, feedback, rating])
            QMessageBox.information(self, "Thank You", f"Feedback saved:\n{feedback_file}")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save feedback:\n{e}")
            log_and_print(f"Feedback save error: {e}")

# --- CANoe Event Handler Classes ---
class CanoeMeasurementEvents:
    def OnStart(self):
        CanoeSync.Started = True
        CanoeSync.Stopped = False
        log_and_print("CANoe Measurement Event: Started")

    def OnStop(self):
        CanoeSync.Started = False
        CanoeSync.Stopped = True
        log_and_print("CANoe Measurement Event: Stopped")

class CanoeTestEvents:
    def __init__(self):
        self.started = False
        self.stopped = False
        self.Name = "Unnamed TC"
        self.WaitForStart = lambda: DoEventsUntil(lambda: self.started)
        self.WaitForStop = lambda: DoEventsUntil(lambda: self.stopped)

    def OnStart(self):
        self.started = True
        self.stopped = False
        log_and_print(f"Test Configuration Event: '{self.Name}' started.")

    def OnStop(self, reason):
        self.started = False
        self.stopped = True
        log_and_print(f"Test Configuration Event: '{self.Name}' stopped (Reason code: {reason}).")

# --- CanoeTestConfiguration Wrapper ---
class CanoeTestConfiguration:
    def __init__(self, tc_com_object):
        self.tc = tc_com_object
        try:
            self.Name = self.tc.Name
            self.Enabled = self.tc.Enabled
        except AttributeError as e:
            log_and_print(f"Error accessing properties of Test Configuration COM object: {e}")
            self.Name = "Unknown TC"
            self.Enabled = False
        except pythoncom.com_error as e:
             log_and_print(f"COM Error accessing properties of Test Configuration '{getattr(self.tc, 'Name', 'N/A')}': {e}")
             self.Name = "Error TC"
             self.Enabled = False

        try:
            self.Events = win32com.client.DispatchWithEvents(self.tc, CanoeTestEvents)
            self.Events.Name = self.Name
        except Exception as e:
             log_and_print(f"Error dispatching events for Test Configuration '{self.Name}': {e}")
             self.Events = None

        self.IsDone = lambda: self.Events is not None and self.Events.stopped

    def Start(self):
        if not self.Enabled:
            log_and_print(f"Test Configuration '{self.Name}' is disabled, skipping start.")
            return

        if self.Events is None:
             log_and_print(f"Cannot start Test Configuration '{self.Name}': Event handler not initialized.")
             return

        log_and_print(f"Attempting to start Test Configuration: {self.Name}")
        try:
            self.Events.started = False
            self.Events.stopped = False
            self.tc.Start()
        except pythoncom.com_error as e:
            hr, msg, exc, arg = e.args
            log_and_print(f"COM Error starting Test Configuration '{self.Name}': {msg} (HRESULT: {hr})")
            if self.Events: self.Events.stopped = True
        except Exception as e:
            log_and_print(f"Unexpected error starting Test Configuration '{self.Name}': {e}")
            if self.Events: self.Events.stopped = True

# --- CanoeSync Class ---
class CanoeSync:
    Started = False
    Stopped = False

    def __init__(self, existing_app=None):
        self.App = existing_app
        self.Measurement = None
        self.Configuration = None
        self.TestSetup = None
        self.TestEnvironments = None
        self.TestConfigs = []
        self.ConfigPath = None
        self.com_initialized_by_sync = False

    def __enter__(self):
        try:
            pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
            self.com_initialized_by_sync = True
            log_and_print("CanoeSync: COM Initialized (CoInitializeEx).")

            if self.App is None:
                try:
                    log_and_print("CanoeSync: Trying GetActiveObject...")
                    self.App = win32com.client.GetActiveObject('CANoe.Application')
                    log_and_print("CanoeSync: Connected to existing CANoe instance.")
                except pythoncom.com_error:
                    log_and_print("CanoeSync: GetActiveObject failed. Dispatching new CANoe.Application...")
                    self.App = win32com.client.DispatchEx('CANoe.Application')
                    log_and_print("CanoeSync: New CANoe Application object dispatched.")
                    if self.App: self.App.Visible = False

            if not self.App:
                raise RuntimeError("CanoeSync: Failed to get or dispatch CANoe.Application object.")

            log_and_print("CanoeSync: Acquiring core CANoe objects...")
            self.Configuration = self.App.Configuration
            if not self.Configuration: raise RuntimeError("CanoeSync: App.Configuration is None.")
            log_and_print("CanoeSync: Got Configuration object.")

            try:
                self.Configuration.Modified = False
                log_and_print("CanoeSync: Set App.Configuration.Modified = False")
            except Exception as mod_err:
                log_and_print(f"CanoeSync: Warning - Could not set Configuration.Modified: {mod_err}")

            self.Measurement = self.App.Measurement
            if not self.Measurement: raise RuntimeError("CanoeSync: App.Measurement is None.")
            log_and_print("CanoeSync: Got Measurement object.")

            self.TestSetup = self.Configuration.TestSetup
            if not self.TestSetup: raise RuntimeError("CanoeSync: Configuration.TestSetup is None.")
            log_and_print("CanoeSync: Got TestSetup object.")

            if hasattr(self.TestSetup, 'TestEnvironments'):
                self.TestEnvironments = self.TestSetup.TestEnvironments
                log_and_print(f"CanoeSync: Got TestEnvironments collection (Count: {self.TestEnvironments.Count if self.TestEnvironments else 'N/A'}).")
            else:
                 log_and_print("CanoeSync: Warning - TestSetup has no 'TestEnvironments' collection.")
                 self.TestEnvironments = None

            win32com.client.WithEvents(self.Measurement, CanoeMeasurementEvents)
            log_and_print("CanoeSync: Measurement event handler attached.")

            self.Running = lambda: self.Measurement.Running if self.Measurement else False

            log_and_print("CanoeSync: Context entered successfully.")
            return self

        except pythoncom.com_error as ce:
            if self.com_initialized_by_sync: pythoncom.CoUninitialize()
            self.com_initialized_by_sync = False
            raise RuntimeError(f"CanoeSync COM Init Failed: {ce.strerror} (HRESULT: {ce.hresult})") from ce
        except Exception as e:
            if self.com_initialized_by_sync: pythoncom.CoUninitialize()
            self.com_initialized_by_sync = False
            log_and_print(f"Error during CanoeSync __enter__: {e}")
            logging.exception("CanoeSync __enter__ details:")
            raise RuntimeError(f"CanoeSync General Init Failed: {e}") from e

    def __exit__(self, exc_type, exc_val, exc_tb):
        log_and_print("CanoeSync: Exiting context...")
        log_and_print(f"CanoeSync: Clearing {len(self.TestConfigs)} TestConfiguration wrappers...")
        for tc_wrapper in self.TestConfigs:
            if hasattr(tc_wrapper, 'tc'): del tc_wrapper.tc
        self.TestConfigs.clear()
        log_and_print("CanoeSync: TestConfiguration wrappers cleared.")

        if hasattr(self, 'TestEnvironments') and self.TestEnvironments is not None:
             del self.TestEnvironments; self.TestEnvironments = None
        if hasattr(self, 'TestSetup') and self.TestSetup is not None:
             del self.TestSetup; self.TestSetup = None
        if hasattr(self, 'Configuration') and self.Configuration is not None:
             del self.Configuration; self.Configuration = None
        if hasattr(self, 'Measurement') and self.Measurement is not None:
             del self.Measurement; self.Measurement = None
        if hasattr(self, 'App') and self.App is not None:
             del self.App; self.App = None

        if self.com_initialized_by_sync:
             pythoncom.CoUninitialize()
             log_and_print("CanoeSync: COM Uninitialized (CoUninitialize).")
             self.com_initialized_by_sync = False
        log_and_print("CanoeSync: Context exited.")

    def WaitForStart(self, timeout=300):
        log_and_print(f"Waiting up to {timeout}s for measurement start event...")
        if not DoEventsUntil(lambda: CanoeSync.Started, timeout):
            if self.Measurement and self.Measurement.Running:
                log_and_print("Timeout waiting for OnStart event, but measurement IS running.")
                CanoeSync.Started = True
            else:
                raise TimeoutError(f"Timeout waiting for CANoe measurement to start ({timeout}s).")
        log_and_print("Measurement start event confirmed or measurement is running.")

    def WaitForStop(self, timeout=600):
        log_and_print(f"Waiting up to {timeout}s for measurement stop event...")
        if not DoEventsUntil(lambda: CanoeSync.Stopped, timeout):
            if self.Measurement and not self.Measurement.Running:
                log_and_print("Timeout waiting for OnStop event, but measurement IS stopped.")
                CanoeSync.Stopped = True
            else:
                 raise TimeoutError(f"Timeout waiting for CANoe measurement to stop ({timeout}s).")
        log_and_print("Measurement stop event confirmed or measurement is stopped.")

    def Load(self, cfg_file_path_str):
        cfg_file_path = Path(cfg_file_path_str)
        log_and_print(f"Attempting to load CANoe configuration: {cfg_file_path}")
        if not self.App: raise RuntimeError("CANoe Application object is not initialized.")
        if not cfg_file_path.is_file(): raise FileNotFoundError(f"CANoe configuration file not found: {cfg_file_path}")
        if cfg_file_path.suffix.lower() != '.cfg': raise ValueError(f"Invalid file extension. Expected .cfg.")

        try:
            cfg_abs_path = str(cfg_file_path.resolve())
            log_and_print(f"Calling CANoe App.Open() with path: {cfg_abs_path}")
            self.App.Open(cfg_abs_path)
            time.sleep(2)
            DoEvents()
            log_and_print("App.Open() call completed.")

            log_and_print("Re-acquiring CANoe object references after load...")
            self.Configuration = self.App.Configuration
            if not self.Configuration: raise RuntimeError("Failed to re-acquire Configuration object.")
            self.TestSetup = self.Configuration.TestSetup
            if not self.TestSetup: raise RuntimeError("Failed to re-acquire TestSetup object.")
            self.TestEnvironments = self.TestSetup.TestEnvironments if hasattr(self.TestSetup, 'TestEnvironments') else None
            self.Measurement = self.App.Measurement
            if not self.Measurement: raise RuntimeError("Failed to re-acquire Measurement object.")

            if not all([self.Configuration, self.TestSetup, self.Measurement]):
                 missing = [name for name, obj in [("Configuration", self.Configuration), ("TestSetup", self.TestSetup), ("Measurement", self.Measurement)] if obj is None]
                 raise RuntimeError(f"Failed to re-acquire essential CANoe objects: {', '.join(missing)}")
            log_and_print("Object references re-acquired.")

            win32com.client.WithEvents(self.Measurement, CanoeMeasurementEvents)
            log_and_print("Re-attached measurement event handler.")

            self.Configuration.Modified = False
            self.ConfigPath = cfg_file_path
            CanoeSync.Started = False
            CanoeSync.Stopped = True
            log_and_print(f"CANoe configuration '{cfg_file_path.name}' loaded successfully.")

        except pythoncom.com_error as e:
            hr, msg, exc, arg = e.args
            log_and_print(f"COM Error loading config '{cfg_file_path.name}': {msg} (HRESULT: {hr})")
            raise RuntimeError(f"Failed to load config '{cfg_file_path.name}': {msg}") from e
        except Exception as e:
            log_and_print(f"Unexpected error loading config '{cfg_file_path.name}': {e}")
            logging.exception("Traceback for unexpected config load error:")
            raise RuntimeError(f"Unexpected error loading config '{cfg_file_path.name}': {e}") from e

    def Start(self):
        if not self.Measurement: raise RuntimeError("Measurement object not available.")
        if not self.Running():
            log_and_print("Measurement not running. Sending Start command...")
            try:
                CanoeSync.Started = False
                CanoeSync.Stopped = False
                self.Measurement.Start()
                self.WaitForStart()
            except pythoncom.com_error as e:
                hr, msg, exc, arg = e.args; log_and_print(f"COM Error starting measurement: {msg} (HRESULT: {hr})")
                if self.Running(): CanoeSync.Started = True
                raise RuntimeError(f"Failed to start measurement: {msg}") from e
            except TimeoutError as e:
                 log_and_print(f"TimeoutError waiting for measurement start event: {e}")
                 if self.Running(): CanoeSync.Started = True; log_and_print("Measurement started despite OnStart timeout.")
                 raise
            except Exception as e:
                log_and_print(f"Unexpected error starting measurement: {e}")
                if self.Running(): CanoeSync.Started = True
                raise RuntimeError(f"Unexpected error starting measurement: {e}") from e
        else:
            log_and_print("Measurement is already running.")
            CanoeSync.Started = True; CanoeSync.Stopped = False

    def Stop(self):
        if not self.Measurement:
             log_and_print("Warning: Measurement object not available for Stop.")
             CanoeSync.Started = False; CanoeSync.Stopped = True; return
        if self.Running():
            log_and_print("Measurement running. Sending Stop command...")
            try:
                CanoeSync.Started = False; CanoeSync.Stopped = False
                self.Measurement.Stop()
                self.WaitForStop()
            except pythoncom.com_error as e:
                hr, msg, exc, arg = e.args; log_and_print(f"COM Error stopping measurement: {msg} (HRESULT: {hr})")
                if not self.Running(): CanoeSync.Stopped = True
            except TimeoutError as e:
                 log_and_print(f"TimeoutError waiting for measurement stop event: {e}")
                 if not self.Running(): CanoeSync.Stopped = True; log_and_print("Measurement stopped despite OnStop timeout.")
            except Exception as e:
                log_and_print(f"Unexpected error stopping measurement: {e}")
                if not self.Running(): CanoeSync.Stopped = True
        else:
            log_and_print("Measurement is not running.")
            CanoeSync.Started = False; CanoeSync.Stopped = True

    def LoadTestConfiguration(self, testcfgname, testunit_path_str, timeout_seconds=60):
        testunit_path = Path(testunit_path_str)
        if not testunit_path.is_file():
            raise FileNotFoundError(f"Test Unit file not found: {testunit_path_str}")

        log_and_print(f"Attempting to load Test Config '{testcfgname}' with TU '{testunit_path.name}'...")
        start_time = time.time()
        tc_collection = None

        while time.time() - start_time < timeout_seconds:
            try:
                if not self.App: raise RuntimeError("CANoe App object is not available.")
                if not self.Configuration: self.Configuration = self.App.Configuration
                if not self.Configuration: raise RuntimeError("CANoe Configuration object is not available.")
                if not self.TestSetup: self.TestSetup = self.Configuration.TestSetup
                if not self.TestSetup: raise RuntimeError("CANoe TestSetup object is not available.")

                if not hasattr(self.TestSetup, 'TestConfigurations'):
                    raise AttributeError("TestSetup object has no 'TestConfigurations' attribute.")
                
                tc_collection = self.TestSetup.TestConfigurations
                if tc_collection is not None:
                    log_and_print("Required CANoe objects for Test Config loading are accessible.")
                    break
                else:
                    log_and_print("Waiting for TestSetup.TestConfigurations collection...")
            
            except pythoncom.com_error as ce:
                 hr, msg, _, _ = ce.args
                 log_and_print(f"COM Warning while waiting for objects: {msg} (HRESULT: {hr}). Retrying...")
            except AttributeError as ae:
                 log_and_print(f"AttributeError while waiting for objects: {ae}. Retrying...")
            except Exception as e:
                 log_and_print(f"Unexpected error while waiting for CANoe objects: {e}. Retrying...")
            
            DoEvents()
            time.sleep(0.5)
        else:
            raise TimeoutError(f"Timeout ({timeout_seconds}s) waiting for essential CANoe objects.")

        tc = None
        try:
            log_and_print(f"Accessing TestConfigurations (Count: {tc_collection.Count}). Searching for '{testcfgname}'...")
            found_tc = None
            for i in range(1, tc_collection.Count + 1):
                try:
                    item = tc_collection.Item(i)
                    if hasattr(item, 'Name') and item.Name == testcfgname:
                        found_tc = item
                        log_and_print(f"Found existing Test Configuration: {testcfgname}")
                        break
                except pythoncom.com_error as item_err:
                    log_and_print(f"Warning: COM error accessing Test Config Item {i}: {item_err.strerror}")
                except AttributeError:
                    log_and_print(f"Warning: Test Config Item {i} might be invalid or lack 'Name' attribute.")
            
            tc = found_tc
            if tc is None:
                log_and_print(f"Test Configuration '{testcfgname}' not found. Creating new one...")
                tc = tc_collection.Add()
                tc.Name = testcfgname
                DoEvents()
                log_and_print(f"Created and named new Test Configuration: {testcfgname}")

            if not hasattr(tc, 'TestUnits'):
                raise RuntimeError(f"Test Configuration '{testcfgname}' has no 'TestUnits' collection.")
            test_units = tc.TestUnits
            if test_units is None:
                 raise RuntimeError(f"Could not access TestUnits for TC '{testcfgname}'.")

            log_and_print(f"Clearing existing Test Units for TC '{testcfgname}'...")
            for i in range(test_units.Count, 0, -1):
                 try:
                     test_units.Remove(i)
                 except pythoncom.com_error as rem_err:
                     log_and_print(f"Warning: Failed to remove Test Unit at index {i} for TC '{testcfgname}': {rem_err.strerror}")
            DoEvents()

            log_and_print(f"Adding Test Unit '{testunit_path.name}' to TC '{testcfgname}'...")
            abs_testunit_path = str(testunit_path.resolve())
            test_units.Add(abs_testunit_path)
            DoEvents()
            log_and_print(f"Added TU '{testunit_path.name}'. Verification Count: {test_units.Count}")

            for old_tc_wrapper in self.TestConfigs:
                if hasattr(old_tc_wrapper, 'tc'): del old_tc_wrapper.tc
            self.TestConfigs.clear()
            self.TestConfigs.append(CanoeTestConfiguration(tc))
            log_and_print(f"TC '{testcfgname}' wrapper created and stored.")

        except pythoncom.com_error as ce:
            error_msg = f"COM Error during Test Config setup for '{testcfgname}': {ce.strerror} (HRESULT: {ce.hresult})"
            log_and_print(error_msg); logging.exception("COM Error Details:")
            raise RuntimeError(error_msg) from ce
        except AttributeError as ae:
            error_msg = f"Attribute Error during Test Config setup for '{testcfgname}': {ae}."
            log_and_print(error_msg); logging.exception("Attribute Error Details:")
            raise RuntimeError(error_msg) from ae
        except Exception as e:
            error_msg = f"Unexpected error during Test Config setup for '{testcfgname}': {e}"
            log_and_print(error_msg); logging.exception("Unexpected Error Details:")
            raise RuntimeError(error_msg) from e

        log_and_print(f"Successfully prepared Test Configuration '{testcfgname}'.")

# --- CanoeWorker Class ---
class CanoeWorker(QThread):
    status_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, action, canoe_config_path, test_script_paths, iteration_data, config_dir, parent=None):
        super().__init__(parent)
        self.action = action
        self.canoe_config_path = Path(canoe_config_path)
        self.test_script_paths = [Path(p) for p in test_script_paths]
        self.iteration_data = iteration_data
        self.config_dir = Path(config_dir)
        self.stop_requested = False

    def request_stop(self):
        self.status_signal.emit("STATUS: Stop requested by user.")
        log_and_print("CanoeWorker stop requested.")
        self.stop_requested = True

    def run(self):
        thread_com_initialized = False
        try:
            log_and_print("Worker COM Initializing (CoInitializeEx)...")
            pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
            thread_com_initialized = True
            self.status_signal.emit("STATUS: Initializing CANoe connection...")

            with CanoeSync() as canoe_sync:
                if not canoe_sync.App:
                     raise RuntimeError("Failed to establish valid CANoe Application object.")
                self.status_signal.emit("STATUS: CANoe connection established.")

                self.status_signal.emit(f"STATUS: Loading base config: {self.canoe_config_path.name}")
                try:
                    current_config_path_str = ""
                    if canoe_sync.App.Configuration and canoe_sync.App.Configuration.FullName:
                        current_config_path_str = canoe_sync.App.Configuration.FullName
                    
                    if current_config_path_str.lower() != str(self.canoe_config_path.resolve()).lower():
                        log_and_print("Config not loaded or different. Attempting load...")
                        canoe_sync.Load(str(self.canoe_config_path))
                        self.status_signal.emit("STATUS: Base config loaded successfully.")
                    else:
                        log_and_print(f"Config '{self.canoe_config_path.name}' already loaded. Re-linking objects.")
                        canoe_sync.Configuration = canoe_sync.App.Configuration
                        canoe_sync.Measurement = canoe_sync.App.Measurement
                        if canoe_sync.Configuration: canoe_sync.TestSetup = canoe_sync.Configuration.TestSetup
                        if canoe_sync.TestSetup and hasattr(canoe_sync.TestSetup, 'TestEnvironments'):
                            canoe_sync.TestEnvironments = canoe_sync.TestSetup.TestEnvironments
                        if canoe_sync.Measurement:
                             win32com.client.WithEvents(canoe_sync.Measurement, CanoeMeasurementEvents)
                        canoe_sync.ConfigPath = self.canoe_config_path
                        self.status_signal.emit("STATUS: Using already loaded config.")

                except pythoncom.com_error as load_err:
                     error_msg = f"Failed to load config '{self.canoe_config_path.name}'. Error: {load_err.strerror}"
                     if load_err.hresult == -2147352567:
                         error_msg += "\nThis might happen if CANoe has a modal dialog open or the file is locked."
                     self.status_signal.emit(f"FATAL: {error_msg}")
                     raise RuntimeError(error_msg) from load_err
                except Exception as load_err:
                    self.status_signal.emit(f"FATAL: Failed to load config '{self.canoe_config_path.name}': {load_err}")
                    raise RuntimeError(f"Failed to load config '{self.canoe_config_path.name}': {load_err}") from load_err

                config_load_settle_time = 5
                log_and_print(f"Waiting {config_load_settle_time}s for CANoe to settle...")
                settle_start = time.time()
                while time.time() - settle_start < config_load_settle_time:
                    DoEvents(); QThread.msleep(100)
                    if self.stop_requested: raise InterruptedError("Stop requested during config settle.")
                log_and_print("Settling time complete.")

                active_vtu_paths = [p for p in self.test_script_paths if self.iteration_data['run_counts'].get(str(p), 0) < self.iteration_data['iterations'].get(str(p), 1)]
                total_executions_in_batch = len(active_vtu_paths)
                executed_in_batch = 0
                log_and_print(f"Total VTU executions queued: {total_executions_in_batch}")

                if not active_vtu_paths:
                     self.status_signal.emit("STATUS: No pending VTU executions.")
                     return

                measurement_running = False
                try:
                    if canoe_sync.Measurement: measurement_running = canoe_sync.Measurement.Running
                except Exception as meas_check_err: 
                    log_and_print(f"Warning: Could not check measurement status: {meas_check_err}")

                if not measurement_running:
                    self.status_signal.emit("STATUS: Starting CANoe measurement...")
                    log_and_print("Attempting to start measurement...")
                    canoe_sync.Start()
                    self.status_signal.emit("STATUS: CANoe measurement started.")
                else:
                    self.status_signal.emit("STATUS: CANoe measurement already running.")

                for vtu_path in active_vtu_paths:
                    if self.stop_requested:
                        self.status_signal.emit("STATUS: Stop requested, aborting cycles.")
                        break
                    
                    executed_in_batch += 1
                    vtuname = vtu_path.stem
                    current_run_count = self.iteration_data['run_counts'].get(str(vtu_path), 0)
                    total_runs_for_vtu = self.iteration_data['iterations'].get(str(vtu_path), 1)
                    
                    total_runs_done_overall = sum(self.iteration_data['run_counts'].get(str(p), 0) for p in self.test_script_paths)
                    total_runs_needed_overall = sum(self.iteration_data['iterations'].get(str(p), 1) for p in self.test_script_paths)
                    self.status_signal.emit(f"QUEUE: {total_runs_done_overall + 1}/{total_runs_needed_overall}")

                    self.status_signal.emit(f"EXEC: Preparing {vtuname} (Cycle {current_run_count + 1}/{total_runs_for_vtu})...")
                    log_and_print(f"--- Starting cycle {current_run_count + 1}/{total_runs_for_vtu} for: {vtuname} ---")
                    cycle_start_time = time.time()

                    try:
                        self.status_signal.emit(f"EXEC: Loading Test Unit {vtuname}...")
                        canoe_sync.LoadTestConfiguration(vtuname, str(vtu_path))
                        self.status_signal.emit(f"EXEC: Test Unit {vtuname} loaded.")

                        if not canoe_sync.TestConfigs:
                            raise RuntimeError(f"No Test Configuration found after LoadTestConfiguration for {vtuname}")
                        tc_wrapper = canoe_sync.TestConfigs[0]

                        if tc_wrapper and tc_wrapper.Enabled:
                             self.status_signal.emit(f"EXEC: Starting Test Config {tc_wrapper.Name}...")
                             tc_start_time_inner = time.time()
                             log_and_print(f"Calling Start() on Test Config: {tc_wrapper.Name}")
                             tc_wrapper.Start()

                             log_and_print(f"Waiting for Test Config {tc_wrapper.Name} to complete...")
                             while not tc_wrapper.IsDone():
                                 if self.stop_requested: break
                                 DoEvents()
                                 QThread.msleep(100)
                             
                             if self.stop_requested:
                                 self.status_signal.emit(f"EXEC: {tc_wrapper.Name} interrupted.")
                                 log_and_print(f"Test Config {tc_wrapper.Name} interrupted.")
                                 try:
                                     if hasattr(tc_wrapper.tc, "Stop"): tc_wrapper.tc.Stop()
                                 except Exception as tc_stop_err:
                                     log_and_print(f"Warning: Error trying to stop TC {tc_wrapper.Name}: {tc_stop_err}")
                                 break

                             tc_end_time_inner = time.time()
                             runtime = tc_end_time_inner - tc_start_time_inner
                             self.status_signal.emit(f"EXEC: {tc_wrapper.Name} finished. Runtime: {runtime:.2f}s")
                             log_and_print(f"Finished Test Config {tc_wrapper.Name}")
                             
                             vtu_path_str = str(vtu_path)
                             self.iteration_data['run_counts'][vtu_path_str] = self.iteration_data['run_counts'].get(vtu_path_str, 0) + 1
                             
                             if self.parent() and hasattr(self.parent(), '_schedule_ui_update') and self.iteration_data.get('update_func'):
                                 self.parent()._schedule_ui_update(self.iteration_data['update_func'])

                             self.save_report(vtu_path, canoe_sync)

                        elif tc_wrapper:
                            log_and_print(f"Test Config '{tc_wrapper.Name}' is disabled. Skipping.")
                            self.status_signal.emit(f"EXEC: Skipped (disabled) {tc_wrapper.Name}")
                        else:
                            log_and_print(f"Error: No valid Test Configuration wrapper for {vtuname}.")
                            self.status_signal.emit(f"ERROR: No TC object for {vtuname}")
                    
                    except RuntimeError as cycle_runtime_err:
                         error_msg = f"ERROR: Failed cycle for VTU '{vtuname}': {cycle_runtime_err}"
                         self.status_signal.emit(f"EXEC: {error_msg}")
                         log_and_print(error_msg)
                    except pythoncom.com_error as cycle_com_err:
                         is_disconnect = cycle_com_err.hresult in COM_DISCONNECTED_ERRORS
                         error_msg = f"ERROR: COM Error during cycle for VTU '{vtuname}': {cycle_com_err.strerror} ({cycle_com_err.hresult})"
                         self.status_signal.emit(f"EXEC: {error_msg}")
                         log_and_print(error_msg)
                         if is_disconnect:
                             self.status_signal.emit(f"FATAL: Disconnected from CANoe during VTU '{vtuname}'. Aborting.")
                             self.stop_requested = True
                    except Exception as cycle_err:
                         error_msg = f"ERROR: Unexpected error during cycle for VTU '{vtuname}': {cycle_err}"
                         self.status_signal.emit(f"EXEC: {error_msg}")
                         logging.exception(f"VTU Cycle Error Details for {vtuname}:")

                    cycle_end_time = time.time()
                    total_cycle_runtime = cycle_end_time - cycle_start_time
                    log_and_print(f"Total cycle time for {vtuname}: {total_cycle_runtime:.2f}s")
                    self.status_signal.emit(f"EXEC: Cycle time for {vtuname}: {total_cycle_runtime:.2f}s")

                    if not self.stop_requested and executed_in_batch < total_executions_in_batch:
                        wait_time = 3
                        self.status_signal.emit(f"QUEUE: Cooling down for {wait_time}s...")
                        log_and_print(f"Waiting {wait_time}s before next cycle.")
                        cooldown_start = time.time()
                        while time.time() - cooldown_start < wait_time:
                            if self.stop_requested: break
                            DoEvents(); QThread.msleep(100)

                measurement_running_after = False
                try:
                    if canoe_sync.Measurement: measurement_running_after = canoe_sync.Measurement.Running
                except Exception: pass

                if measurement_running_after:
                    if not self.stop_requested:
                        self.status_signal.emit("STATUS: All queued executions completed.")
                    log_and_print("Attempting to stop measurement...")
                    canoe_sync.Stop()
                    self.status_signal.emit("STATUS: CANoe measurement stopped.")
                else:
                     log_and_print("Measurement was not running at end of test batch.")
                     self.status_signal.emit("STATUS: Measurement already stopped.")

        except FileNotFoundError as e:
              error_msg = f"FATAL: File not found: {e}"
              self.status_signal.emit(error_msg); log_and_print(error_msg)
        except pythoncom.com_error as e:
              error_msg = f"FATAL: Worker COM Error: {e.strerror} ({e.hresult})"
              self.status_signal.emit(error_msg); log_and_print(error_msg)
        except InterruptedError as e:
            log_and_print(f"Worker Interrupted: {e}")
            self.status_signal.emit(f"STATUS: Worker process interrupted: {e}")
        except RuntimeError as e:
              error_msg = f"FATAL: CanoeWorker Runtime Error: {e}"
              self.status_signal.emit(error_msg); log_and_print(error_msg)
        except Exception as e:
              error_msg = f"FATAL: Unexpected Worker Error: {e}"
              self.status_signal.emit(error_msg); logging.exception("Worker thread unexpected error")
        finally:
            log_and_print("CanoeWorker run method entering finally block.")
            if thread_com_initialized:
                try:
                    pythoncom.CoUninitialize()
                    log_and_print("Worker COM Uninitialized.")
                except Exception as cu_err:
                    log_and_print(f"Warning during CoUninitialize in worker: {cu_err}")

            self.finished_signal.emit()
            log_and_print("Worker finished signal emitted.")
            log_and_print("--- CanoeWorker thread finished ---")

    def save_report(self, vtu_path, canoe_sync):
        vtuname = vtu_path.stem
        log_and_print(f"Attempting to save/process reports for VTU: {vtuname}")

        if not canoe_sync or not canoe_sync.ConfigPath or not canoe_sync.ConfigPath.parent.is_dir():
            error_msg = f"Error: Cannot determine report source folder for {vtuname}."
            log_and_print(error_msg)
            self.status_signal.emit(f"EXEC: ERROR - Could not find report folder for {vtuname}")
            return
        
        report_source_folder = canoe_sync.ConfigPath.parent
        log_and_print(f"Searching for reports for '{vtuname}' in: {report_source_folder}")

        pattern_html = f"Report_{vtuname}*.html"; pattern_xml = f"Report_{vtuname}*.xml"
        
        try:
            report_files = list(report_source_folder.glob(pattern_html)) + list(report_source_folder.glob(pattern_xml))
        except Exception as glob_err:
             error_msg = f"Error searching for report files in {report_source_folder}: {glob_err}"
             log_and_print(error_msg)
             self.status_signal.emit(f"EXEC: ERROR - Failed searching reports for {vtuname}")
             return

        if not report_files:
            log_and_print(f"Warning: No report files found for '{vtuname}' in {report_source_folder}.")
            self.status_signal.emit(f"EXEC: No reports found for {vtuname}"); return

        log_and_print(f"Found {len(report_files)} report file(s) for {vtuname}.")
        dest_folder_html_xml = self.config_dir / "Reports" / "HTML_XML_Reports" / f"{vtuname}_reports"
        dest_folder_excel = self.config_dir / "Reports" / "Excel_Sheet"
        
        try:
             dest_folder_html_xml.mkdir(parents=True, exist_ok=True)
             dest_folder_excel.mkdir(parents=True, exist_ok=True)
             log_and_print(f"Ensured report destination folders exist.")
        except OSError as e:
             error_msg = f"Error creating report directories: {e}"
             self.status_signal.emit(f"EXEC: {error_msg}"); log_and_print(error_msg); return

        moved_files_count = 0; parsed_xml_data = None; processed_xml_path = None
        for source_path in report_files:
            dest_file = dest_folder_html_xml / source_path.name
            try:
                log_and_print(f"Moving '{source_path.name}' to '{dest_folder_html_xml}'...")
                shutil.move(str(source_path), str(dest_file)); moved_files_count += 1
                log_and_print(f"Successfully moved report to: {dest_file}")

                if source_path.suffix.lower() == '.xml' and parsed_xml_data is None:
                    self.status_signal.emit(f"EXEC: Parsing report {source_path.name}...")
                    log_and_print(f"Parsing XML report: {dest_file}")
                    parsed_data = parse_xml_report(dest_file)
                    if parsed_data:
                        parsed_xml_data = parsed_data; processed_xml_path = dest_file
                        log_and_print(f"Successfully parsed {len(parsed_data)} entries from {dest_file.name}")
                        self.status_signal.emit(f"EXEC: Parsed {len(parsed_data)} steps from {source_path.name}")
                    else:
                         log_and_print(f"Warning: Parsing returned no data for {dest_file.name}.")
                         self.status_signal.emit(f"EXEC: Warning - Could not parse data from {source_path.name}")
            
            except Exception as e:
                error_msg = f"Error processing report '{source_path.name}': {e}"
                self.status_signal.emit(f"EXEC: {error_msg}"); log_and_print(error_msg)

        if moved_files_count > 0:
            try:
                rel_dest_html = dest_folder_html_xml.relative_to(self.config_dir / "Reports")
                status_msg = f"EXEC: {moved_files_count} report file(s) for {vtuname} saved to Reports/{rel_dest_html}"
            except ValueError:
                status_msg = f"EXEC: {moved_files_count} report file(s) for {vtuname} saved to {dest_folder_html_xml}"
            self.status_signal.emit(status_msg); log_and_print(f"Finished moving {moved_files_count} report file(s) for {vtuname}.")

        if parsed_xml_data and processed_xml_path:
            excel_file_name = f"{processed_xml_path.stem}_parsed_report.xlsx"
            excel_file_path = dest_folder_excel / excel_file_name
            
            log_and_print(f"Attempting to export parsed data to: {excel_file_path}")
            self.status_signal.emit(f"EXEC: Exporting parsed data for {vtuname}...")
            export_to_excel(parsed_xml_data, excel_file_path)

    def force_kill_canoe(self):
        log_and_print("Attempting to force kill CANoe processes...")
        killed_pids = []
        process_name = "canoe64.exe"
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] and proc.info['name'].lower() == process_name:
                        pid_to_kill = proc.pid
                        log_and_print(f"Found CANoe process PID {pid_to_kill}. Terminating...")
                        process_obj = psutil.Process(pid_to_kill)
                        process_obj.terminate()
                        log_and_print(f"Sent terminate signal to PID {pid_to_kill}.")
                        try:
                            process_obj.wait(timeout=1.0)
                            log_and_print(f"CANoe PID {pid_to_kill} terminated gracefully.")
                            killed_pids.append(pid_to_kill); continue
                        except psutil.TimeoutExpired:
                            log_and_print(f"CANoe PID {pid_to_kill} did not terminate gracefully. Killing...")
                            process_obj.kill(); process_obj.wait(timeout=0.5)
                            log_and_print(f"CANoe PID {pid_to_kill} killed forcefully.")
                            killed_pids.append(pid_to_kill)
                except psutil.NoSuchProcess:
                    log_and_print(f"Process PID {pid_to_kill} no longer exists.")
                    pass
                except psutil.AccessDenied:
                    log_and_print(f"Access denied trying to terminate CANoe PID {pid_to_kill}.")
                except Exception as term_err:
                    log_and_print(f"Error terminating CANoe PID {pid_to_kill}: {term_err}")
        except Exception as iter_err: log_and_print(f"Error iterating system processes: {iter_err}")

        if killed_pids:
            status_msg = f"STATUS: CANoe process termination finished. Killed PIDs: {killed_pids}"
            self.status_signal.emit(status_msg); log_and_print(f"Finished killing CANoe processes. PIDs: {killed_pids}")
        else:
            log_and_print("No running CANoe process found to kill.")

# --- Serial Worker ---
if SERIAL_AVAILABLE:
    class SerialWorker(QThread):
        data_received_signal = pyqtSignal(str)
        error_signal = pyqtSignal(str)
        finished_signal = pyqtSignal()

        def __init__(self, serial_instance, parent=None):
            super().__init__(parent)
            self.serial = serial_instance
            self._running = False
            self.mutex = QMutex()

        def run(self):
            log_and_print("SerialWorker thread started.")
            self._set_running(True)
            decoder = QTextCodec.codecForName("UTF-8").makeDecoder(QTextCodec.IgnoreHeader | QTextCodec.ConvertInvalidToNull)

            while self._is_running():
                if self.serial and self.serial.is_open:
                    try:
                        if self.serial.in_waiting > 0:
                            line_bytes = self.serial.read(self.serial.in_waiting)
                            if line_bytes:
                                try:
                                    line_str = decoder.toUnicode(line_bytes)
                                except Exception as decode_err:
                                     log_and_print(f"Serial decoding error: {decode_err}. Data: {line_bytes!r}")
                                     line_str = ""
                                if line_str: self.data_received_signal.emit(line_str)
                        else: time.sleep(0.05)
                    except serial.SerialException as e:
                        error_msg = f"Serial communication error: {e}"
                        self.error_signal.emit(error_msg)
                        log_and_print(error_msg)
                        self._set_running(False); break
                    except OSError as e:
                         error_msg = f"Serial OS error: {e}"
                         self.error_signal.emit(error_msg)
                         log_and_print(error_msg)
                         self._set_running(False); break
                    except Exception as e:
                        error_msg = f"Unexpected error in SerialWorker: {e}"
                        self.error_signal.emit(error_msg)
                        logging.exception("Serial worker unexpected error:")
                        self._set_running(False); break
                else:
                    log_and_print("Serial port not open. Stopping SerialWorker.")
                    self._set_running(False); break
            
            log_and_print("SerialWorker thread finished run loop.")
            self.finished_signal.emit()

        def stop(self):
            log_and_print("SerialWorker stop requested.")
            self._set_running(False)

        def _is_running(self):
            with QMutexLocker(self.mutex): return self._running

        def _set_running(self, running):
            with QMutexLocker(self.mutex): self._running = running

# --- Camera Worker ---
if OPENCV_AVAILABLE:
    class CameraWorker(QThread):
        frame_update_signal = pyqtSignal(QImage)
        camera_error_signal = pyqtSignal(str)
        change_info_signal = pyqtSignal(int, float) # change_count, time_of_last_change
        finished_signal = pyqtSignal()

        def __init__(self, camera_index, frame_log_dir, initial_threshold, parent=None):
            super().__init__(parent)
            self.camera_index = camera_index
            self.frame_log_dir = Path(frame_log_dir)
            self.current_threshold = initial_threshold
            self._running = False
            self.mutex = QMutex()
            self.prev_frame_gray = None
            self.change_count = 0
            self.time_of_last_change = 0.0
            self.significant_change_pixel_percentage = 0.001 

        def run(self):
            log_and_print(f"CameraWorker started for camera index {self.camera_index} with threshold {self.current_threshold}.")
            self._set_running(True)
            cap = None
            try:
                cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW) 
                if not cap.isOpened():
                    raise IOError(f"Cannot open camera index {self.camera_index}")
                
                self.frame_log_dir.mkdir(parents=True, exist_ok=True)
                log_and_print(f"Camera frame logging to: {self.frame_log_dir}")

                while self._is_running():
                    ret, frame = cap.read()
                    if not ret:
                        log_and_print("Failed to grab frame from camera. Stopping worker.")
                        break 
                    
                    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    gray_frame = cv2.GaussianBlur(gray_frame, (21, 21), 0) 

                    frame_changed = False
                    if self.prev_frame_gray is None:
                        self.prev_frame_gray = gray_frame.copy()
                        self.save_frame(frame) 
                        frame_changed = True
                    else:
                        frame_delta = cv2.absdiff(self.prev_frame_gray, gray_frame)
                        thresh_val = self.current_threshold 
                        thresh = cv2.threshold(frame_delta, thresh_val, 255, cv2.THRESH_BINARY)[1]
                        
                        num_pixels_changed_threshold = thresh.shape[0] * thresh.shape[1] * self.significant_change_pixel_percentage
                        
                        if np.sum(thresh > 0) > num_pixels_changed_threshold: 
                            self.save_frame(frame)
                            frame_changed = True
                        self.prev_frame_gray = gray_frame.copy()
                    
                    if frame_changed:
                        self.change_count +=1
                        self.time_of_last_change = time.time()
                        self.change_info_signal.emit(self.change_count, self.time_of_last_change)

                    rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb_image.shape
                    bytes_per_line = ch * w
                    qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
                    self.frame_update_signal.emit(qt_image.copy()) 
                    
                    self.msleep(33) 
            
            except Exception as e:
                error_msg = f"Error in CameraWorker (idx {self.camera_index}): {e}"
                log_and_print(error_msg)
                logging.exception("CameraWorker Exception details:")
                self.camera_error_signal.emit(error_msg)
            finally:
                if cap and cap.isOpened(): cap.release()
                log_and_print(f"CameraWorker for index {self.camera_index} finished.")
                self.finished_signal.emit()

        def save_frame(self, frame):
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            ms = int(time.time() * 1000) % 1000
            filename = self.frame_log_dir / f"frame_cam{self.camera_index}_{timestamp}_{ms:03d}.jpg"
            try:
                cv2.imwrite(str(filename), frame)
                log_and_print(f"Frame saved: {filename.name}")
            except Exception as e:
                log_and_print(f"Error saving frame {filename.name}: {e}")
        
        def set_threshold(self, threshold):
            log_and_print(f"CameraWorker: Threshold updated to {threshold}")
            self.current_threshold = threshold

        def reset_change_stats(self):
            log_and_print("CameraWorker: Resetting change stats.")
            self.change_count = 0
            self.time_of_last_change = 0.0 
            self.change_info_signal.emit(self.change_count, self.time_of_last_change)


        def stop(self):
            log_and_print(f"CameraWorker (idx {self.camera_index}) stop requested.")
            self._set_running(False)

        def _is_running(self):
            with QMutexLocker(self.mutex): return self._running

        def _set_running(self, running):
            with QMutexLocker(self.mutex): self._running = running

# --- Python Script Worker for Test Runner ---
class PythonScriptWorker(QThread):
    output_received = pyqtSignal(str)
    process_finished = pyqtSignal(int, QProcess.ExitStatus)
    
    def __init__(self, script_path, parent=None):
        super().__init__(parent)
        self.script_path = str(script_path)
        self.process = None
        self._is_running = False

    def run(self):
        log_and_print(f"Starting Python script worker for: {self.script_path}")
        self._is_running = True
        try:
            self.process = QProcess()
            self.process.setProcessChannelMode(QProcess.MergedChannels)
            self.process.readyReadStandardOutput.connect(self.handle_stdout)
            
            # Start the python interpreter and pass the script path to it
            self.process.start(sys.executable, [self.script_path])
            
            if not self.process.waitForStarted():
                log_and_print(f"Failed to start process for script: {self.script_path}")
                self.process_finished.emit(-1, QProcess.CrashExit)
                return

            # Keep the thread alive until the process finishes
            self.process.waitForFinished(-1)
            
            exit_code = self.process.exitCode()
            exit_status = self.process.exitStatus()
            log_and_print(f"Script {self.script_path} finished with exit code {exit_code} and status {exit_status}.")
            self.process_finished.emit(exit_code, exit_status)

        except Exception as e:
            log_and_print(f"Error in PythonScriptWorker for {self.script_path}: {e}")
            self.output_received.emit(f"\n--- WORKER ERROR: {e} ---\n")
            self.process_finished.emit(-1, QProcess.CrashExit) # Emit crash signal
        finally:
            self._is_running = False
            self.process = None

    def handle_stdout(self):
        data = self.process.readAllStandardOutput().data().decode(errors='ignore')
        self.output_received.emit(data)

    def stop(self):
        if self._is_running and self.process:
            log_and_print(f"Forcefully stopping script process PID: {self.process.processId()}")
            self.output_received.emit("\n--- STOP REQUESTED BY USER ---\n")
            self.process.kill() # Force kill
            if not self.process.waitForFinished(2000): # Wait 2s for kill
                log_and_print(f"Process PID {self.process.processId()} did not terminate after kill signal.")
        self._is_running = False

# --- TestExecutionApp Main GUI Class ---
class TestExecutionApp(QMainWindow):
    DEFAULT_CAMERA_THRESHOLD = 30

    def __init__(self, cfg_file_path_str, config): 
        super().__init__()
        self.config = config
        self.app_data_dir = Path(os.getenv('APPDATA', Path.home() / ".MagnaTestExec")) / "MagnaTestExecApp"
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        self.python_scripts_dir = self.app_data_dir / "PythonScripts"
        self.python_scripts_dir.mkdir(parents=True, exist_ok=True)

        if cfg_file_path_str:
            self.canoe_config_path = Path(cfg_file_path_str)
            if self.canoe_config_path.is_file() and self.canoe_config_path.suffix.lower() == '.cfg':
                self.config_dir = self.canoe_config_path.parent
                log_and_print(f"Application initialized with CANoe config: {self.canoe_config_path}")
            else: 
                log_and_print(f"Invalid CANoe config path provided: {cfg_file_path_str}. Initializing without CANoe config.")
                self.canoe_config_path = None
                self.config_dir = self.app_data_dir / "DefaultWorkspace" 
                self.config_dir.mkdir(parents=True, exist_ok=True)
        else: 
            log_and_print("Initializing without CANoe config.")
            self.canoe_config_path = None
            self.config_dir = self.app_data_dir / "DefaultWorkspace"
            self.config_dir.mkdir(parents=True, exist_ok=True)

        self.canoe_worker = None
        self.serial_worker = None
        self.serial_port = None
        self.is_serial_logging = False
        self.serial_log_file = None
        self.serial_command_history_list = [] 
        
        self.camera_worker = None
        self.current_camera_threshold = self.DEFAULT_CAMERA_THRESHOLD
        self.last_change_timestamp = 0.0
        self.camera_frame_save_path = ""
        self.last_change_display_timer = QTimer(self)
        self.last_change_display_timer.timeout.connect(self.update_last_change_display)

        # Test Runner attributes
        self.python_script_worker = None
        self.test_runner_success_count = 0
        self.test_runner_error_count = 0

        self.execution_started = False
        self.test_script_paths = []
        self.vtu_iterations = {}
        self.vtu_run_counts = {}
        self.vtu_buttons = {}
        self.vtu_spinboxes = {}
        self.select_cfg_action = None
        self.upload_action = None

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setObjectName("AppLog")
        self.log_handler = QTextEditLogger(self)
        self.log_handler.log_signal.connect(self.append_log)
        logging.getLogger().addHandler(self.log_handler)
        log_and_print("GUI Logger Initialized.")

        self.initUI() # Create all UI elements
        self.setStyleSheet(STYLE_SHEET)
        
        self.setup_logging() # Uses self.config_dir which is now set
        self.load_test_runner_history()
        
        if SERIAL_AVAILABLE:
            self.populate_com_ports()
        else:
            if hasattr(self, 'serial_tab'):
                serial_tab_index = self.tab_widget.indexOf(self.serial_tab)
                if serial_tab_index != -1:
                    self.tab_widget.setTabEnabled(serial_tab_index, False)
                    self.tab_widget.setTabText(serial_tab_index, "Serial Monitor (Disabled)")

        if OPENCV_AVAILABLE:
            self.populate_camera_sources()
        else:
            if hasattr(self, 'camera_tab'):
                camera_tab_index = self.tab_widget.indexOf(self.camera_tab)
                if camera_tab_index != -1:
                    self.tab_widget.setTabEnabled(camera_tab_index, False)
                    self.tab_widget.setTabText(camera_tab_index, "Camera View (Disabled)")

        self.update_ui_for_config_state() # Call after initUI and other setups
        self.check_canoe_status() # Initial check after UI is ready

        log_and_print(f"Application data directory: {self.app_data_dir}")
        log_and_print(f"Current project/config directory: {self.config_dir}")

    def _schedule_ui_update(self, func, *args):
        QTimer.singleShot(0, lambda: func(*args))

    def update_window_title(self):
        if self.canoe_config_path and self.canoe_config_path.is_file():
            title = f"Magna Test Exec - {self.config_dir.name} ({self.canoe_config_path.name})"
        else:
            title = "Magna Test Exec - No CANoe Config Loaded"
        self.setWindowTitle(title)

    def initUI(self):
        self.setGeometry(100, 100, 1200, 900) 
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10); self.main_layout.setSpacing(10)

        # Status Frame
        status_frame = QFrame(); status_frame.setFrameShape(QFrame.StyledPanel)
        status_layout = QGridLayout(status_frame)
        status_layout.setContentsMargins(5,5,5,5); status_layout.setHorizontalSpacing(15)
        status_layout.addWidget(QLabel("<b>CANoe Sim:</b>"), 0, 0)
        self.simulation_status_label = QLabel("Idle"); status_layout.addWidget(self.simulation_status_label, 0, 1)
        status_layout.addWidget(QLabel("<b>CANoe App:</b>"), 0, 2)
        self.canoe_status_label = QLabel("Checking..."); self.canoe_status_label.setObjectName("CanoeStatusLabel")
        status_layout.addWidget(self.canoe_status_label, 0, 3)
        status_layout.addWidget(QLabel("<b>Test Exec:</b>"), 1, 0)
        self.test_execution_status_label = QLabel("Idle"); status_layout.addWidget(self.test_execution_status_label, 1, 1)
        status_layout.addWidget(QLabel("<b>Queue:</b>"), 1, 2)
        self.queue_iterations_label = QLabel("0 / 0"); status_layout.addWidget(self.queue_iterations_label, 1, 3)
        status_layout.addWidget(QLabel("<b>Serial:</b>"), 0, 4)
        self.serial_status_label = QLabel("Disabled" if not SERIAL_AVAILABLE else "Disconnected")
        self.serial_status_label.setObjectName("SerialStatusLabel")
        self.set_status_label_style(self.serial_status_label, "Disconnected" if SERIAL_AVAILABLE else "Error")
        status_layout.addWidget(self.serial_status_label, 0, 5)
        status_layout.setColumnStretch(1,1); status_layout.setColumnStretch(3,1); status_layout.setColumnStretch(5,1); status_layout.setColumnStretch(6,2)
        self.main_layout.addWidget(status_frame)

        self.tab_widget = QTabWidget(); self.tab_widget.setObjectName("mainTabWidget")
        self.main_layout.addWidget(self.tab_widget, 1) # Add stretch factor

        # --- Tab 1: CANoe Execution ---
        self.canoe_tab = QWidget(); self.tab_widget.addTab(self.canoe_tab, " CANoe Execution ")
        self.initCanoeTab()

        # --- Tab 2: Serial Monitor ---
        self.serial_tab = QWidget(); self.tab_widget.addTab(self.serial_tab, "Serial Monitor")
        self.initSerialTab()

        # --- Tab 3: Camera View ---
        self.camera_tab = QWidget(); self.tab_widget.addTab(self.camera_tab, "Camera View")
        self.initCameraTab()
        
        # --- Tab 4: Test Runner ---
        self.test_runner_tab = QWidget(); self.tab_widget.addTab(self.test_runner_tab, "Test Runner")
        self.initTestRunnerTab()

        # --- Menu Bar ---
        self.menu_bar = QMenuBar(self); self.setMenuBar(self.menu_bar)
        file_menu = self.menu_bar.addMenu("&File")
        self.select_cfg_action = QAction(QIcon.fromTheme("document-open"), "Select &CANoe Config File (.cfg)...", self)
        self.select_cfg_action.triggered.connect(self.select_new_config_file); file_menu.addAction(self.select_cfg_action)
        file_menu.addSeparator()
        self.upload_action = QAction(QIcon.fromTheme("document-save-as"), "&Upload VTU File...", self)
        self.upload_action.triggered.connect(self.upload_vtu_file); file_menu.addAction(self.upload_action)
        file_menu.addSeparator()
        exit_action = QAction(QIcon.fromTheme("application-exit"), "E&xit", self); exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close); file_menu.addAction(exit_action)
        help_menu = self.menu_bar.addMenu("&Help")
        about_action = QAction("&About Application", self); about_action.triggered.connect(self.show_about_info); help_menu.addAction(about_action)
        creators_action = QAction("About &Creators", self); creators_action.triggered.connect(self.show_about_creators); help_menu.addAction(creators_action)
        help_menu.addSeparator()
        feedback_action = QAction("Submit &Feedback", self); feedback_action.triggered.connect(self.show_feedback_form); help_menu.addAction(feedback_action)

        self.status_bar = QStatusBar(); self.setStatusBar(self.status_bar)

        self.canoe_status_timer = QTimer(self)
        self.canoe_status_timer.timeout.connect(self.check_canoe_status)
        self.canoe_status_timer.start(5000)
    
    def initCanoeTab(self):
        canoe_tab_layout = QVBoxLayout(self.canoe_tab)
        canoe_tab_layout.setContentsMargins(10,15,10,10); canoe_tab_layout.setSpacing(10)
        canoe_button_layout = QHBoxLayout()
        self.start_button = QPushButton(QIcon.fromTheme("media-playback-start"), " START CANoe"); self.start_button.setObjectName("StartButton")
        self.start_button.clicked.connect(self.start_execution)
        canoe_button_layout.addWidget(self.start_button)
        self.stop_button = QPushButton(QIcon.fromTheme("media-playback-stop"), " STOP CANoe"); self.stop_button.setObjectName("StopButton")
        self.stop_button.clicked.connect(self.stop_execution); self.stop_button.setEnabled(False)
        canoe_button_layout.addWidget(self.stop_button)
        canoe_button_layout.addStretch(1)
        self.clear_app_log_button = QPushButton("Clear App Log"); self.clear_app_log_button.setObjectName("ClearAppLogButton")
        self.clear_app_log_button.clicked.connect(self.log_output.clear)
        canoe_button_layout.addWidget(self.clear_app_log_button)
        self.view_report_button = QPushButton(" VIEW REPORTS"); self.view_report_button.setObjectName("ReportButton")
        self.view_report_button.clicked.connect(self.show_report_options)
        canoe_button_layout.addWidget(self.view_report_button)
        self.open_config_folder_button = QPushButton(" WORKSPACE"); self.open_config_folder_button.setObjectName("ConfigFolderButton") 
        self.open_config_folder_button.clicked.connect(lambda: self.open_folder(self.config_dir)) 
        canoe_button_layout.addWidget(self.open_config_folder_button)
        canoe_tab_layout.addLayout(canoe_button_layout)
        canoe_content_layout = QHBoxLayout(); canoe_content_layout.setSpacing(10)
        vtu_selection_frame = QFrame(); vtu_selection_frame.setFrameShape(QFrame.StyledPanel)
        vtu_selection_layout = QVBoxLayout(vtu_selection_frame); vtu_selection_layout.setContentsMargins(5,5,5,5)
        vtu_label = QLabel("Available Test Units (.vtuexe):"); vtu_label.setProperty("heading", True)
        vtu_selection_layout.addWidget(vtu_label)
        self.vtu_scroll_area = QScrollArea(); self.vtu_scroll_area.setWidgetResizable(True); self.vtu_scroll_area.setMinimumHeight(200)
        vtu_selection_layout.addWidget(self.vtu_scroll_area)
        canoe_content_layout.addWidget(vtu_selection_frame, 1)
        log_output_frame = QFrame(); log_output_frame.setFrameShape(QFrame.StyledPanel)
        log_output_layout = QVBoxLayout(log_output_frame); log_output_layout.setContentsMargins(5,5,5,5)
        log_label = QLabel("Application & CANoe Log:"); log_label.setProperty("heading", True)
        log_output_layout.addWidget(log_label)
        log_output_layout.addWidget(self.log_output)
        canoe_content_layout.addWidget(log_output_frame, 2)
        canoe_tab_layout.addLayout(canoe_content_layout)

    def initSerialTab(self):
        serial_tab_layout = QVBoxLayout(self.serial_tab)
        serial_tab_layout.setContentsMargins(10,15,10,10); serial_tab_layout.setSpacing(10)
        
        serial_ctrl_layout = QHBoxLayout(); serial_ctrl_layout.setSpacing(10)
        serial_ctrl_layout.addWidget(QLabel("COM Port:"))
        self.com_port_combo = QComboBox(); self.com_port_combo.setMinimumWidth(200)
        serial_ctrl_layout.addWidget(self.com_port_combo)
        self.refresh_ports_button = QPushButton("Refresh")
        if SERIAL_AVAILABLE: self.refresh_ports_button.clicked.connect(self.populate_com_ports)
        else: self.refresh_ports_button.setEnabled(False)
        serial_ctrl_layout.addWidget(self.refresh_ports_button)
        serial_ctrl_layout.addWidget(QLabel("Baud Rate:"))
        self.baud_rate_combo = QComboBox(); self.baud_rate_combo.addItems(['9600', '19200', '38400', '57600', '115200', '230400', '460800', '921600']); self.baud_rate_combo.setCurrentText('115200')
        serial_ctrl_layout.addWidget(self.baud_rate_combo)
        serial_ctrl_layout.addStretch(1)
        self.connect_serial_button = QPushButton("Connect"); self.connect_serial_button.setObjectName("SerialConnectButton"); self.connect_serial_button.setCheckable(True)
        if SERIAL_AVAILABLE: self.connect_serial_button.clicked.connect(self.toggle_serial_connection)
        else: self.connect_serial_button.setEnabled(False)
        serial_ctrl_layout.addWidget(self.connect_serial_button)
        self.log_serial_button = QPushButton("Start Logging"); self.log_serial_button.setObjectName("SerialLogButton"); self.log_serial_button.setCheckable(True); self.log_serial_button.setEnabled(False)
        if SERIAL_AVAILABLE: self.log_serial_button.clicked.connect(self.toggle_serial_logging)
        serial_ctrl_layout.addWidget(self.log_serial_button)
        self.save_serial_log_button = QPushButton("Save Log"); self.save_serial_log_button.setEnabled(False)
        if SERIAL_AVAILABLE: self.save_serial_log_button.clicked.connect(self.save_serial_log)
        serial_ctrl_layout.addWidget(self.save_serial_log_button)
        self.clear_serial_log_button = QPushButton("Clear Display")
        if SERIAL_AVAILABLE: self.clear_serial_log_button.clicked.connect(lambda: self.serial_log_output.clear())
        else: self.clear_serial_log_button.setEnabled(False)
        serial_ctrl_layout.addWidget(self.clear_serial_log_button)
        serial_tab_layout.addLayout(serial_ctrl_layout)

        serial_command_layout = QHBoxLayout(); serial_command_layout.setSpacing(10)
        serial_command_layout.addWidget(QLabel("Command:"))
        self.serial_command_combo = QComboBox()
        self.serial_command_combo.setEditable(True)
        self.serial_command_combo.lineEdit().setPlaceholderText("Enter command or select history")
        self.serial_command_combo.setMinimumWidth(300)
        self.serial_command_combo.setEnabled(False) 
        serial_command_layout.addWidget(self.serial_command_combo, 1) 

        self.send_serial_command_button = QPushButton("Send")
        self.send_serial_command_button.setObjectName("SendCommandButton") 
        self.send_serial_command_button.setEnabled(False) 
        if SERIAL_AVAILABLE: self.send_serial_command_button.clicked.connect(self.handle_send_serial_command)
        serial_command_layout.addWidget(self.send_serial_command_button)
        
        self.serial_command_status_label = QLabel("Status: Idle")
        self.serial_command_status_label.setMinimumWidth(200) 
        serial_command_layout.addWidget(self.serial_command_status_label)
        serial_tab_layout.addLayout(serial_command_layout)
        
        self.serial_log_output = QTextEdit(); self.serial_log_output.setReadOnly(True); self.serial_log_output.setObjectName("SerialLog"); self.serial_log_output.setLineWrapMode(QTextEdit.WidgetWidth)
        serial_tab_layout.addWidget(self.serial_log_output)
    
    def initCameraTab(self):
        camera_tab_main_layout = QVBoxLayout(self.camera_tab) 
        camera_tab_main_layout.setContentsMargins(10,15,10,10); camera_tab_main_layout.setSpacing(10)

        camera_top_ctrl_layout = QHBoxLayout(); camera_top_ctrl_layout.setSpacing(10)
        camera_top_ctrl_layout.addWidget(QLabel("Video Source:"))
        self.camera_source_combo = QComboBox(); self.camera_source_combo.setMinimumWidth(250)
        camera_top_ctrl_layout.addWidget(self.camera_source_combo)
        self.refresh_cameras_button = QPushButton("Refresh Sources")
        camera_top_ctrl_layout.addWidget(self.refresh_cameras_button)
        camera_top_ctrl_layout.addStretch(1)
        self.stop_feed_button = QPushButton("Stop Feed"); self.stop_feed_button.setObjectName("StopFeedButton")
        self.stop_feed_button.setEnabled(False)
        camera_top_ctrl_layout.addWidget(self.stop_feed_button)
        camera_tab_main_layout.addLayout(camera_top_ctrl_layout)

        camera_info_grid_layout = QGridLayout() 
        camera_info_grid_layout.setSpacing(10)
        camera_info_grid_layout.addWidget(QLabel("Frame Logs:"), 0, 0, alignment=Qt.AlignTop)
        self.change_count_label = QLabel("Changes Detected: 0")
        camera_info_grid_layout.addWidget(self.change_count_label, 0, 1, alignment=Qt.AlignTop)
        self.reset_change_button = QPushButton("Reset Counter")
        self.reset_change_button.setEnabled(False) 
        camera_info_grid_layout.addWidget(self.reset_change_button, 0, 2, alignment=Qt.AlignTop)

        camera_info_grid_layout.addWidget(QLabel("Last Log Time:"), 1, 0)
        self.last_change_label = QLabel("Last Change: N/A")
        camera_info_grid_layout.addWidget(self.last_change_label, 1, 1, 1, 2) 
        
        camera_info_grid_layout.addWidget(QLabel("Save Path:"), 2, 0)
        self.image_save_path_label = QLabel("Saving to: Not Active")
        self.image_save_path_label.setWordWrap(True)
        camera_info_grid_layout.addWidget(self.image_save_path_label, 2, 1, 1, 2)

        threshold_label_text = QLabel("Detection Sensitivity:")
        camera_info_grid_layout.addWidget(threshold_label_text, 3, 0)
        
        self.threshold_slider = QSlider(Qt.Horizontal)
        self.threshold_slider.setMinimum(5)  
        self.threshold_slider.setMaximum(100) 
        self.threshold_slider.setValue(self.DEFAULT_CAMERA_THRESHOLD)
        self.threshold_slider.setTickInterval(10)
        self.threshold_slider.setTickPosition(QSlider.TicksBelow)
        self.threshold_slider.setEnabled(False)
        camera_info_grid_layout.addWidget(self.threshold_slider, 3, 1)
        
        self.threshold_value_label = QLabel(f"{self.DEFAULT_CAMERA_THRESHOLD}")
        self.threshold_value_label.setFixedWidth(35)
        self.threshold_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        camera_info_grid_layout.addWidget(self.threshold_value_label, 3, 2)
        
        camera_info_grid_layout.setColumnStretch(1, 1) 
        camera_tab_main_layout.addLayout(camera_info_grid_layout)

        self.camera_feed_label = QLabel("Select a video source to start the feed.")
        self.camera_feed_label.setAlignment(Qt.AlignCenter)
        self.camera_feed_label.setStyleSheet("background-color: black; color: white; font-size: 14pt; border: 1px solid #555555;")
        self.camera_feed_label.setFixedSize(640, 480)
        
        camera_feed_container = QWidget() 
        camera_feed_centered_layout = QHBoxLayout(camera_feed_container)
        camera_feed_centered_layout.addStretch()
        camera_feed_centered_layout.addWidget(self.camera_feed_label)
        camera_feed_centered_layout.addStretch()
        camera_feed_centered_layout.setContentsMargins(0,0,0,0)
        camera_tab_main_layout.addWidget(camera_feed_container, 1) 

        if OPENCV_AVAILABLE:
            self.camera_source_combo.currentIndexChanged.connect(self.start_camera_feed_from_combo)
            self.refresh_cameras_button.clicked.connect(self.populate_camera_sources)
            self.stop_feed_button.clicked.connect(self.stop_camera_feed)
            self.threshold_slider.valueChanged.connect(self.update_threshold_display_and_worker)
            self.reset_change_button.clicked.connect(self.reset_change_stats_ui)
    
    def initTestRunnerTab(self):
        runner_layout = QVBoxLayout(self.test_runner_tab)
        runner_layout.setContentsMargins(10, 15, 10, 10)
        runner_layout.setSpacing(10)

        # --- Controls Layout ---
        controls_layout = QHBoxLayout()
        self.upload_py_button = QPushButton("Upload Script")
        self.upload_py_button.clicked.connect(self.upload_python_script)
        controls_layout.addWidget(self.upload_py_button)

        self.py_script_combo = QComboBox()
        self.py_script_combo.setMinimumWidth(250)
        self.py_script_combo.setToolTip("Select a previously uploaded Python script to run.")
        controls_layout.addWidget(self.py_script_combo, 1)

        self.run_script_button = QPushButton("Run Script")
        self.run_script_button.setObjectName("RunScriptButton")
        self.run_script_button.clicked.connect(self.run_python_script)
        controls_layout.addWidget(self.run_script_button)
        
        self.stop_script_button = QPushButton("Stop Script")
        self.stop_script_button.setObjectName("StopScriptButton")
        self.stop_script_button.setEnabled(False)
        self.stop_script_button.clicked.connect(self.stop_python_script)
        controls_layout.addWidget(self.stop_script_button)
        
        controls_layout.addStretch()
        
        self.clear_runner_log_button = QPushButton("Clear Log")
        self.clear_runner_log_button.clicked.connect(lambda: self.test_runner_log.clear())
        controls_layout.addWidget(self.clear_runner_log_button)

        self.clear_history_button = QPushButton("Clear History")
        self.clear_history_button.clicked.connect(self.clear_script_history)
        controls_layout.addWidget(self.clear_history_button)
        runner_layout.addLayout(controls_layout)

        # --- Log Output ---
        self.test_runner_log = QTextEdit()
        self.test_runner_log.setReadOnly(True)
        self.test_runner_log.setObjectName("TestRunnerLog")
        runner_layout.addWidget(self.test_runner_log, 1)

        # --- Status Bar ---
        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.StyledPanel)
        runner_status_layout = QHBoxLayout(status_frame)
        runner_status_layout.setContentsMargins(8, 5, 8, 5)

        self.test_runner_status_label = QLabel("Status: Idle")
        runner_status_layout.addWidget(self.test_runner_status_label, 1)

        self.test_runner_success_label = QLabel("Successful Runs: 0")
        runner_status_layout.addWidget(self.test_runner_success_label)

        self.test_runner_error_label = QLabel("Errors: 0")
        runner_status_layout.addWidget(self.test_runner_error_label)

        runner_layout.addWidget(status_frame)

    def update_ui_for_config_state(self):
        config_loaded = self.canoe_config_path and self.canoe_config_path.is_file()
        self.update_window_title()
        
        try:
            if hasattr(self, 'start_button') and self.start_button:
                self.start_button.setEnabled(config_loaded)
        
            if hasattr(self, 'upload_action') and self.upload_action: # Check if menu action exists
                self.upload_action.setEnabled(config_loaded)
        
            if hasattr(self, 'open_config_folder_button') and self.open_config_folder_button:
                self.open_config_folder_button.setToolTip(f"Open: {self.config_dir.resolve()}")
                self.open_config_folder_button.setEnabled(True) 

            if hasattr(self, 'view_report_button') and self.view_report_button:
                self.view_report_button.setEnabled(True)
        except Exception as e:
            print(e)


        if config_loaded:
            if hasattr(self, 'vtu_scroll_area'):
                self.refresh_vtu_list()
            if hasattr(self, 'canoe_status_label') and self.canoe_status_label:
                self.set_status_label_style(self.canoe_status_label, "Checking...")
        else:
            if hasattr(self, 'vtu_scroll_area') and self.vtu_scroll_area:
                 placeholder_vtu_widget = QWidget()
                 placeholder_layout = QVBoxLayout(placeholder_vtu_widget)
                 placeholder_label = QLabel("No CANoe Configuration Loaded.\nSelect via File menu."); 
                 placeholder_label.setAlignment(Qt.AlignCenter)
                 placeholder_layout.addWidget(placeholder_label)
                 old_widget = self.vtu_scroll_area.takeWidget()
                 if old_widget: old_widget.deleteLater()
                 self.vtu_scroll_area.setWidget(placeholder_vtu_widget)
            
            if hasattr(self, 'canoe_status_label') and self.canoe_status_label:
                self.set_status_label_style(self.canoe_status_label, "No Config")
                self.canoe_status_label.setText("No Config Loaded")
            if hasattr(self, 'simulation_status_label') and self.simulation_status_label:
                self.simulation_status_label.setText("N/A")
            if hasattr(self, 'test_execution_status_label') and self.test_execution_status_label:
                self.test_execution_status_label.setText("N/A")
            if hasattr(self, 'queue_iterations_label') and self.queue_iterations_label:
                self.queue_iterations_label.setText("N/A")

        if hasattr(self, 'status_bar') and self.status_bar:
            self.status_bar.showMessage("Ready" if config_loaded else "Ready (No CANoe Config)", 3000)
        log_and_print(f"UI updated for config state. Config loaded: {config_loaded}")


    def set_status_label_style(self, label, status_text):
        if not isinstance(label, QLabel):
            log_and_print(f"Warning: Attempted to set status style on non-QLabel object: {label}")
            return
        label.setProperty("status", status_text)
        label.style().unpolish(label); label.style().polish(label)

    def append_log(self, msg):
        try:
            self.log_output.append(msg)
            scrollbar = self.log_output.verticalScrollBar()
            if scrollbar: scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            print(f"Error appending message to GUI log: {e}\nOriginal message: {msg}")

    def closeEvent(self, event):
        log_and_print("Close event triggered.")
        if self.execution_started and self.canoe_worker and self.canoe_worker.isRunning():
            reply = QMessageBox.question(self, "Confirm Exit", "CANoe execution running.\nStop and exit?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                log_and_print("User confirmed exit during CANoe execution.")
                self.stop_execution()
                if self.canoe_worker: self.canoe_worker.wait(15000)
            else:
                log_and_print("User cancelled exit."); event.ignore(); return
        
        if self.python_script_worker and self.python_script_worker.isRunning():
            reply = QMessageBox.question(self, "Confirm Exit", "A Python script is running.\nStop and exit?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                log_and_print("User confirmed exit during script execution.")
                self.stop_python_script()
                if self.python_script_worker: self.python_script_worker.wait(5000)
            else:
                log_and_print("User cancelled exit."); event.ignore(); return

        self.stop_camera_feed() 
        if self.camera_worker and self.camera_worker.isRunning():
             if not self.camera_worker.wait(2000): 
                 log_and_print("Camera worker did not stop gracefully on close.")
        self.camera_worker = None

        self.stop_serial_logging()
        if self.serial_worker and self.serial_worker.isRunning(): 
            if not self.serial_worker.wait(500):
                log_and_print("Serial worker did not stop gracefully on close.")
        self.serial_worker = None
        self.disconnect_serial()

        if self.serial_log_file:
            try: self.serial_log_file.close(); log_and_print("Closed open serial log file."); self.serial_log_file = None
            except Exception as e: log_and_print(f"Error closing serial log file: {e}")

        if hasattr(self, 'log_handler') and self.log_handler:
            logging.getLogger().removeHandler(self.log_handler)
            self.log_handler.close(); self.log_handler = None

        log_and_print("Cleanup finished. Accepting close event.")
        event.accept()

    def populate_vtu_exes(self):
        vtu_search_dir = self.config_dir
        log_and_print(f"Scanning for Test Units (.vtuexe) in: {vtu_search_dir}")
        container_widget = QWidget()
        grid_layout = QGridLayout(container_widget)
        grid_layout.setContentsMargins(10, 10, 10, 10)
        grid_layout.setVerticalSpacing(10); grid_layout.setHorizontalSpacing(15)
        if not vtu_search_dir.is_dir():
            error_label = QLabel(f"Error: Directory not found:\n{vtu_search_dir}"); error_label.setStyleSheet("color: red;")
            grid_layout.addWidget(error_label, 0, 0, 1, 2)
            log_and_print(f"Error populating VTUs: Directory not found - {vtu_search_dir}")
            return container_widget
        vtu_files = sorted(list(vtu_search_dir.glob("*.vtuexe")))
        if not vtu_files:
            info_label = QLabel(f"No Test Unit files (.vtuexe) found in:\n{vtu_search_dir}"); info_label.setAlignment(Qt.AlignCenter)
            grid_layout.addWidget(info_label, 0, 0, 1, 2)
            log_and_print("No .vtuexe files found.")
        else:
            log_and_print(f"Found {len(vtu_files)} .vtuexe Test Unit file(s).")
            col_count = 2; row, col = 0, 0
            for vtu_path in vtu_files:
                vtuname = vtu_path.stem; vtu_path_str = str(vtu_path)
                vtu_item_widget = QWidget(); item_layout = QHBoxLayout(vtu_item_widget)
                item_layout.setContentsMargins(0, 0, 0, 0); item_layout.setSpacing(5)
                btn = ToggleButton(vtuname); btn.setToolTip(f"{vtu_path.name}\n{vtu_path}")
                btn.clicked.connect(lambda checked, p=vtu_path: self.toggle_vtu_selection(p, checked))
                self.vtu_buttons[vtuname] = btn; item_layout.addWidget(btn, 1)
                spin = QSpinBox(); spin.setMinimum(1); spin.setMaximum(100); spin.setFixedWidth(60)
                spin.setToolTip("Set execution count")
                initial_iterations = self.vtu_iterations.get(vtu_path_str, 1)
                spin.setValue(initial_iterations)
                spin.valueChanged.connect(lambda val, p_str=vtu_path_str: self.update_vtu_iterations(p_str, val))
                self.vtu_spinboxes[vtu_path_str] = spin
                self.vtu_iterations.setdefault(vtu_path_str, initial_iterations)
                self.vtu_run_counts.setdefault(vtu_path_str, 0)
                item_layout.addWidget(spin)
                grid_layout.addWidget(vtu_item_widget, row, col)
                col += 1
                if col >= col_count: col = 0; row += 1
            grid_layout.setRowStretch(row + 1, 1)
        container_widget.adjustSize()
        return container_widget

    # --- Test Runner Methods ---
    def upload_python_script(self):
        source_path_str, _ = QFileDialog.getOpenFileName(self, "Select Python Script to Upload", str(Path.home()), "Python Files (*.py)")
        if not source_path_str:
            log_and_print("Python script upload cancelled by user.")
            return

        source_path = Path(source_path_str)
        dest_path = self.python_scripts_dir / source_path.name
        
        if dest_path.exists():
            reply = QMessageBox.question(self, "File Exists", f"'{source_path.name}' has been uploaded before.\nOverwrite it?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                QMessageBox.information(self, "Upload Cancelled", "Script not overwritten.")
                return

        try:
            shutil.copy2(source_path, dest_path)
            log_and_print(f"Copied script '{source_path.name}' to '{dest_path}'")
            self.add_script_to_history(source_path.name)
            QMessageBox.information(self, "Upload Successful", f"Script '{source_path.name}' has been uploaded and is ready to run.")
        except Exception as e:
            log_and_print(f"Error copying script file: {e}")
            QMessageBox.critical(self, "Upload Error", f"Error copying script file:\n{e}")

    def add_script_to_history(self, script_name):
        # Load current history from config
        script_history = self.config.get('python_script_history', [])
        if script_name not in script_history:
            script_history.insert(0, script_name)
            self.config['python_script_history'] = script_history
            save_config(self.config)
            log_and_print(f"Added '{script_name}' to script history.")
        
        self.load_test_runner_history() # Refresh the dropdown
        # Set the newly added script as the current one
        self.py_script_combo.setCurrentText(script_name)

    def load_test_runner_history(self):
        self.py_script_combo.blockSignals(True)
        self.py_script_combo.clear()
        
        script_history = self.config.get('python_script_history', [])
        if not script_history:
            self.py_script_combo.addItem("No scripts uploaded yet.")
            self.py_script_combo.setEnabled(False)
        else:
            self.py_script_combo.addItems(script_history)
            self.py_script_combo.setEnabled(True)
        
        self.py_script_combo.blockSignals(False)
        self.set_test_runner_ui_state(running=False) # Ensure UI state is correct
        log_and_print(f"Loaded {len(script_history)} scripts into Test Runner history.")
        
    def clear_script_history(self):
        reply = QMessageBox.question(self, "Confirm Clear", "Are you sure you want to clear all uploaded script history?\nThis will delete the scripts from the application data folder.", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            log_and_print("Clearing Python script history and deleting files.")
            self.config['python_script_history'] = []
            save_config(self.config)
            try:
                for item in self.python_scripts_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                QMessageBox.information(self, "History Cleared", "All uploaded scripts and history have been removed.")
            except Exception as e:
                 log_and_print(f"Error deleting script files: {e}")
                 QMessageBox.warning(self, "Deletion Error", f"Could not delete all script files:\n{e}")
            self.load_test_runner_history()

    def set_test_runner_ui_state(self, running: bool):
        is_history_empty = self.py_script_combo.count() == 0 or "No scripts" in self.py_script_combo.itemText(0)
        self.run_script_button.setEnabled(not running and not is_history_empty)
        self.stop_script_button.setEnabled(running)
        self.upload_py_button.setEnabled(not running)
        self.py_script_combo.setEnabled(not running)
        self.clear_history_button.setEnabled(not running and not is_history_empty)

    def run_python_script(self):
        if self.python_script_worker and self.python_script_worker.isRunning():
            QMessageBox.warning(self, "Already Running", "A Python script is already in progress.")
            return

        script_name = self.py_script_combo.currentText()
        if not script_name or "No scripts" in script_name:
            QMessageBox.warning(self, "No Script Selected", "Please upload or select a script to run.")
            return
            
        script_path = self.python_scripts_dir / script_name
        if not script_path.is_file():
            QMessageBox.critical(self, "Script Not Found", f"The script file '{script_name}' was not found in the application directory. It may have been deleted.")
            # Remove broken entry from history
            script_history = self.config.get('python_script_history', [])
            if script_name in script_history: script_history.remove(script_name)
            self.config['python_script_history'] = script_history
            save_config(self.config)
            self.load_test_runner_history()
            return
            
        self.test_runner_log.clear()
        self.test_runner_log.append(f"--- Starting script: {script_name} ---\n")
        self.test_runner_status_label.setText(f"Status: Running '{script_name}'...")
        self.set_test_runner_ui_state(running=True)

        self.python_script_worker = PythonScriptWorker(script_path, parent=self)
        self.python_script_worker.output_received.connect(self.append_test_runner_log)
        self.python_script_worker.process_finished.connect(self.on_python_script_finished)
        self.python_script_worker.start()

    def stop_python_script(self):
        if self.python_script_worker and self.python_script_worker.isRunning():
            self.python_script_worker.stop()
            self.stop_script_button.setText("Stopping...")
            self.stop_script_button.setEnabled(False)
    
    def append_test_runner_log(self, text):
        # Check for common error keywords to color the text red
        error_keywords = ['error', 'exception', 'traceback', 'fail', 'failed']
        cursor = self.test_runner_log.textCursor()
        
        color = QColor("red") if any(keyword in text.lower() for keyword in error_keywords) else self.test_runner_log.textColor()
        
        # Insert text with the determined color
        fmt = cursor.charFormat()
        fmt.setForeground(color)
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text, fmt)
        self.test_runner_log.verticalScrollBar().setValue(self.test_runner_log.verticalScrollBar().maximum())

    def on_python_script_finished(self, exit_code, exit_status):
        log_and_print(f"Python script worker finished. Exit Code: {exit_code}, Exit Status: {exit_status}")
        self.test_runner_log.append("\n")
        if exit_status == QProcess.NormalExit and exit_code == 0:
            self.test_runner_log.append("--- Script finished successfully ---")
            self.test_runner_status_label.setText("Status: Finished (Success)")
            self.test_runner_success_count += 1
        elif exit_status == QProcess.CrashExit or exit_code != 0:
            self.append_test_runner_log(f"--- Script finished with an error (Exit Code: {exit_code}) ---")
            self.test_runner_status_label.setText(f"Status: Finished (Error Code: {exit_code})")
            self.test_runner_error_count += 1
        
        self.test_runner_success_label.setText(f"Successful Runs: {self.test_runner_success_count}")
        self.test_runner_error_label.setText(f"Errors: {self.test_runner_error_count}")
        
        self.python_script_worker = None
        self.stop_script_button.setText("Stop Script")
        self.set_test_runner_ui_state(running=False)

    # --- Camera View Methods ---
    def populate_camera_sources(self):
        if not OPENCV_AVAILABLE: return
        log_and_print("Scanning for available camera sources...")
        self.camera_source_combo.blockSignals(True)
        self.camera_source_combo.clear()
        self.camera_source_combo.addItem("Select a video source...", -1) 
        
        available_cameras = []
        for i in range(5): 
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW) 
            if cap.isOpened():
                available_cameras.append(i)
                cap.release()
        
        if not available_cameras:
            log_and_print("No camera sources found.")
            self.camera_source_combo.addItem("No cameras found", -1) 
            self.camera_source_combo.setEnabled(False)
        else:
            log_and_print(f"Found cameras at indices: {available_cameras}")
            for idx in available_cameras:
                self.camera_source_combo.addItem(f"Camera {idx}", idx) 
            self.camera_source_combo.setEnabled(True)
        
        self.camera_source_combo.blockSignals(False)
        self.camera_source_combo.setCurrentIndex(0) 

    def start_camera_feed_from_combo(self, combo_box_index):
        if not OPENCV_AVAILABLE: return
        if combo_box_index <= 0 : 
            self.stop_camera_feed() 
            self.camera_feed_label.setText("Select a video source to start the feed.")
            self.camera_feed_label.setPixmap(QPixmap()) 
            self.image_save_path_label.setText("Saving to: Not Active")
            self.threshold_slider.setEnabled(False)
            self.reset_change_button.setEnabled(False)
            self.update_change_detection_info(0,0.0) 
            self.last_change_label.setText("Last Change: N/A")
            return

        if self.camera_worker and self.camera_worker.isRunning():
            log_and_print("Stopping existing camera feed before starting new one.")
            self.camera_worker.stop()
            if not self.camera_worker.wait(1000):
                 log_and_print("Warning: Previous camera worker did not stop in time.")
            self.camera_worker = None

        camera_id = self.camera_source_combo.itemData(combo_box_index)

        log_and_print(f"Starting camera feed for index {camera_id} with threshold {self.current_camera_threshold}...")
        self.camera_frame_save_path = self.config_dir / "Camera_Frames" 
        self.image_save_path_label.setText(f"Saving to: {self.camera_frame_save_path.resolve()}")
        
        self.camera_worker = CameraWorker(camera_id, self.camera_frame_save_path, self.current_camera_threshold, parent=self)
        self.camera_worker.frame_update_signal.connect(self.update_camera_frame)
        self.camera_worker.camera_error_signal.connect(self.on_camera_error)
        self.camera_worker.change_info_signal.connect(self.update_change_detection_info)
        self.camera_worker.finished_signal.connect(self.on_camera_worker_finished)
        self.camera_worker.start()
        
        self.camera_source_combo.setEnabled(False)
        self.refresh_cameras_button.setEnabled(False)
        self.stop_feed_button.setEnabled(True)
        self.threshold_slider.setEnabled(True)
        self.reset_change_button.setEnabled(True)
        self.camera_feed_label.setText("Connecting to camera...")
        self.last_change_display_timer.start(1000) 
        self.update_change_detection_info(0, 0.0)


    def stop_camera_feed(self):
        if not OPENCV_AVAILABLE: return
        self.last_change_display_timer.stop()
        if self.camera_worker and self.camera_worker.isRunning():
            log_and_print("Stopping camera feed...")
            self.camera_worker.stop()
        else: 
            self.on_camera_worker_finished() 
        self.stop_feed_button.setEnabled(False) 


    def update_camera_frame(self, qt_image):
        if not self.camera_feed_label: return
        pixmap = QPixmap.fromImage(qt_image)
        scaled_pixmap = pixmap.scaled(self.camera_feed_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.camera_feed_label.setPixmap(scaled_pixmap)

    def on_camera_error(self, error_message):
        log_and_print(f"Camera Error: {error_message}")
        QMessageBox.critical(self, "Camera Error", f"An error occurred with the camera:\n{error_message}")
        self.stop_camera_feed() 

    def on_camera_worker_finished(self):
        log_and_print("Camera worker finished signal received.")
        self.last_change_display_timer.stop()
        self.camera_worker = None 
        self.camera_feed_label.setText("Feed stopped. Select a source to begin.")
        self.camera_feed_label.setStyleSheet("background-color: black; color: white; font-size: 14pt; border: 1px solid #555555;")
        self.camera_feed_label.setPixmap(QPixmap()) 
        
        self.camera_source_combo.setEnabled(True)
        self.refresh_cameras_button.setEnabled(True)
        self.stop_feed_button.setEnabled(False)
        self.threshold_slider.setEnabled(False)
        self.reset_change_button.setEnabled(False)
        self.image_save_path_label.setText("Saving to: Not Active")
        self.update_change_detection_info(0, 0.0) 
        self.last_change_label.setText("Last Change: N/A")


    def update_change_detection_info(self, count, timestamp):
        self.change_count_label.setText(f"Changes Detected: {count}")
        self.last_change_timestamp = timestamp
        self.update_last_change_display() 
        if count > 0 and timestamp > 0 and not self.last_change_display_timer.isActive():
            self.last_change_display_timer.start(1000) 
        elif count == 0 or timestamp == 0.0 : 
            self.last_change_display_timer.stop()
            self.last_change_label.setText("Last Change: N/A")


    def update_last_change_display(self):
        if self.last_change_timestamp > 0:
            time_ago_seconds = time.time() - self.last_change_timestamp
            if time_ago_seconds < 0: time_ago_seconds = 0 

            if time_ago_seconds < 60:
                self.last_change_label.setText(f"{int(time_ago_seconds)}s ago")
            elif time_ago_seconds < 3600:
                minutes = int(time_ago_seconds / 60)
                seconds = int(time_ago_seconds % 60)
                self.last_change_label.setText(f"{minutes}m {seconds}s ago")
            else:
                hours = int(time_ago_seconds / 3600)
                minutes = int((time_ago_seconds % 3600) / 60)
                self.last_change_label.setText(f"{hours}h {minutes}m ago")
        else:
            self.last_change_label.setText("Last Change: N/A")

    def update_threshold_display_and_worker(self, value):
        self.current_camera_threshold = value
        self.threshold_value_label.setText(f"{value}")
        if self.camera_worker and self.camera_worker.isRunning():
            self.camera_worker.set_threshold(value)

    def reset_change_stats_ui(self):
        if self.camera_worker and self.camera_worker.isRunning():
            self.camera_worker.reset_change_stats() 
        else: 
            self.update_change_detection_info(0, 0.0)
            self.last_change_label.setText("Last Change: N/A")
        log_and_print("Change counter and stats reset by user.")

        
    def select_new_config_file(self):
        log_and_print("User requested to select a new CANoe config file...")
        current_dir = str(self.config_dir) if self.canoe_config_path and self.config_dir.is_dir() else str(Path.home())

        new_cfg_file_str, _ = QFileDialog.getOpenFileName(self, "Select New CANoe Configuration File (.cfg)", current_dir, "CANoe Config (*.cfg);;All Files (*)")
        if new_cfg_file_str:
            new_cfg_path = Path(new_cfg_file_str)
            if new_cfg_path != self.canoe_config_path: 
                log_and_print(f"New CANoe config selected: {new_cfg_path}")
                self.config['last_cfg_file'] = str(new_cfg_path)
                self.config['last_browse_dir'] = str(new_cfg_path.parent)
                save_config(self.config)
                QMessageBox.information(self, "Configuration Changed", f"CANoe Configuration changed to:\n{new_cfg_path.name}\n\nThe application will now restart to apply changes.")
                self.restart_application()
            elif self.canoe_config_path is None and new_cfg_path.is_file(): 
                log_and_print(f"Initial CANoe config selected: {new_cfg_path}")
                self.config['last_cfg_file'] = str(new_cfg_path)
                self.config['last_browse_dir'] = str(new_cfg_path.parent)
                save_config(self.config)
                QMessageBox.information(self, "Configuration Loaded", f"CANoe Configuration loaded:\n{new_cfg_path.name}\n\nThe application will now restart to apply changes.")
                self.restart_application()
            else:
                log_and_print("User re-selected the current config file, or no change made.")
                QMessageBox.information(self, "Configuration Unchanged", "The current CANoe configuration file was re-selected or no change was made.")
        else:
            log_and_print("CANoe config file selection cancelled.")


    def upload_vtu_file(self):
        if not (self.canoe_config_path and self.canoe_config_path.is_file()):
            QMessageBox.warning(self, "No CANoe Config", "Please load a CANoe configuration file first to define the target folder for VTU upload.")
            return

        dest_dir = self.config_dir 
        log_and_print(f"Attempting to upload VTU to current config folder: {dest_dir}")

        source_path_str, _ = QFileDialog.getOpenFileName(self, "Select VTU File to Upload", str(Path.home()), "CANoe Test Unit Files (*.vtuexe *.xml)")
        if source_path_str:
            source_path = Path(source_path_str)
            dest_path = dest_dir / source_path.name
            if dest_path.exists():
                reply = QMessageBox.question(self, "File Exists", f"'{source_path.name}' already exists in {dest_dir}.\nOverwrite?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No:
                    QMessageBox.information(self, "Upload Cancelled", "File not overwritten.")
                    return
            try:
                shutil.copy2(source_path, dest_path)
                QMessageBox.information(self, "Upload Successful", f"File '{source_path.name}' uploaded to\n{dest_dir}")
                self.refresh_vtu_list()
            except Exception as e:
                QMessageBox.critical(self, "Upload Error", f"Error copying file:\n{e}")

    def refresh_vtu_list(self):
        if not (self.canoe_config_path and self.canoe_config_path.is_file()):
            log_and_print("Skipping VTU list refresh: No CANoe config loaded.")
            return

        log_and_print("Refreshing VTU list UI...")
        self.vtu_buttons.clear(); self.vtu_spinboxes.clear()
        new_container = self.populate_vtu_exes()
        old_widget = self.vtu_scroll_area.takeWidget()
        if old_widget: old_widget.deleteLater()
        self.vtu_scroll_area.setWidget(new_container)
        self.reapply_vtu_selections_and_counts()
        log_and_print("VTU list UI refreshed.")


    def reapply_vtu_selections_and_counts(self):
        selected_paths_str = {str(p) for p in self.test_script_paths}
        for vtu_path_str, spinbox in self.vtu_spinboxes.items():
            vtuname = Path(vtu_path_str).stem
            button = self.vtu_buttons.get(vtuname)
            if button: button.setChecked(vtu_path_str in selected_paths_str)
            spinbox.setValue(self.vtu_iterations.get(vtu_path_str, 1))
            self.vtu_run_counts.setdefault(vtu_path_str, 0)
        self.update_queue_label()
        self.set_ui_state_running(self.execution_started)

    def toggle_vtu_selection(self, vtu_path_obj, is_selected):
        vtu_path_str = str(vtu_path_obj)
        if is_selected:
            if vtu_path_obj not in self.test_script_paths: self.test_script_paths.append(vtu_path_obj)
        else:
            if vtu_path_obj in self.test_script_paths: self.test_script_paths.remove(vtu_path_obj)
        spinbox = self.vtu_spinboxes.get(vtu_path_str)
        self.vtu_iterations.setdefault(vtu_path_str, spinbox.value() if spinbox else 1)
        self.vtu_run_counts.setdefault(vtu_path_str, 0)
        self.update_queue_label()

    def update_vtu_iterations(self, vtu_path_str, count):
        self.vtu_iterations[vtu_path_str] = count
        self.vtu_run_counts.setdefault(vtu_path_str, 0)
        self.update_queue_label()

    def update_queue_label(self):
        total_iterations_selected = sum(self.vtu_iterations.get(str(p), 1) for p in self.test_script_paths)
        total_iterations_completed = sum(self.vtu_run_counts.get(str(p), 0) for p in self.test_script_paths)
        
        if self.canoe_config_path and self.canoe_config_path.is_file():
             self.queue_iterations_label.setText(f"{total_iterations_completed} / {total_iterations_selected}")
        else:
             self.queue_iterations_label.setText("N/A")

        for vtu_path_s, spinbox_widget in self.vtu_spinboxes.items(): 
            vtu_p_obj = Path(vtu_path_s)
            button_widget = self.vtu_buttons.get(vtu_p_obj.stem)
            if button_widget:
                is_selected = vtu_p_obj in self.test_script_paths
                is_completed = self.vtu_run_counts.get(vtu_path_s, 0) >= self.vtu_iterations.get(vtu_path_s, 1)
                can_interact = not self.execution_started or (is_selected and not is_completed)
                button_widget.setEnabled(can_interact)
                spinbox_widget.setEnabled(can_interact)

    def start_execution(self):
        if not (self.canoe_config_path and self.canoe_config_path.is_file()):
            QMessageBox.warning(self, "No CANoe Config", "Please load a CANoe configuration file first using the File menu.")
            return
        if self.execution_started: QMessageBox.warning(self, "Already Running", "Execution already running."); return
        if not self.test_script_paths: QMessageBox.warning(self, "No Test Units Selected", "Please select test units."); return
        
        iteration_data_for_worker = {
            'iterations': {str(p): self.vtu_iterations.get(str(p), 1) for p in self.test_script_paths},
            'run_counts': {str(p): self.vtu_run_counts.get(str(p), 0) for p in self.test_script_paths},
            'update_func': self.update_queue_label
        }
        active_vtu_paths_obj = [Path(p_str) for p_str, total_iter in iteration_data_for_worker['iterations'].items() if iteration_data_for_worker['run_counts'].get(p_str, 0) < total_iter]
        if not active_vtu_paths_obj: QMessageBox.information(self, "Already Completed", "Selected tests already completed."); return

        self.set_ui_state_running(True)
        self.status_bar.showMessage("Starting CANoe execution...", 0)
        try:
            self.canoe_worker = CanoeWorker("run_vtu", str(self.canoe_config_path), active_vtu_paths_obj, iteration_data_for_worker, self.config_dir, parent=self)
            self.canoe_worker.status_signal.connect(self.process_status_message)
            self.canoe_worker.finished_signal.connect(self.on_execution_finished)
            self.canoe_worker.start()
            self.simulation_status_label.setText("Initializing...")
            self.test_execution_status_label.setText("Starting...")
        except Exception as e:
            QMessageBox.critical(self, "Thread Error", f"Failed to start CanoeWorker thread: {e}")
            self.set_ui_state_running(False); self.status_bar.showMessage("Error starting.", 5000)

    def stop_execution(self):
        if not self.execution_started or not self.canoe_worker or not self.canoe_worker.isRunning(): return
        self.status_bar.showMessage("Stop requested...", 0)
        self.stop_button.setEnabled(False); self.stop_button.setText("STOPPING...")
        self.canoe_worker.request_stop()

    def on_execution_finished(self):
        final_status = self.test_execution_status_label.text()
        if "ERROR" in final_status or "FATAL" in final_status: self.status_bar.showMessage("Execution finished with errors.", 5000)
        elif "stopped" in final_status.lower() or "aborted" in final_status.lower(): self.status_bar.showMessage("Execution stopped by user.", 5000)
        else: self.status_bar.showMessage("Execution finished.", 5000)
        self.set_ui_state_running(False)
        self.canoe_worker = None

    def set_ui_state_running(self, running):
        self.execution_started = running
        config_loaded_and_valid = self.canoe_config_path and self.canoe_config_path.is_file()
        
        if hasattr(self, 'start_button') and self.start_button:
            self.start_button.setEnabled(config_loaded_and_valid and not running)
        
        if hasattr(self, 'stop_button') and self.stop_button:
            self.stop_button.setEnabled(running) 
            if not running: self.stop_button.setText(" STOP CANoe")
        
        if self.select_cfg_action: self.select_cfg_action.setEnabled(not running)
        if self.upload_action: self.upload_action.setEnabled(not running and config_loaded_and_valid) 
        
        self.update_queue_label() 
        if not running: 
            if hasattr(self, 'simulation_status_label') and self.simulation_status_label and \
               "ERROR" not in self.simulation_status_label.text() and \
               "FATAL" not in self.simulation_status_label.text():
                self.simulation_status_label.setText("Idle" if config_loaded_and_valid else "N/A")


    def process_status_message(self, msg):
        prefix_map = {"STATUS:": self.simulation_status_label, "EXEC:": self.test_execution_status_label, "QUEUE:": self.queue_iterations_label}
        processed = False
        if msg.startswith("FATAL:") or msg.startswith("ERROR:"):
            self.simulation_status_label.setText("ERROR")
            self.test_execution_status_label.setText(msg)
            if msg.startswith("FATAL:"): QMessageBox.critical(self, "CANoe Critical Error", msg)
            elif msg.startswith("ERROR:"): QMessageBox.warning(self, "CANoe Execution Warning", msg)
            processed = True
        if not processed:
            for prefix, label in prefix_map.items():
                if msg.startswith(prefix):
                    label.setText(msg[len(prefix):].strip()); break
        self.append_log(msg)

    def show_report_options(self):
        dialog = QDialog(self); dialog.setWindowTitle("View Reports & Logs"); dialog.setMinimumWidth(350)
        layout = QVBoxLayout(dialog); layout.setContentsMargins(15,15,15,15); layout.setSpacing(10)
        layout.addWidget(QLabel("<b>Open Folder:</b>"))
        reports_base = self.config_dir / "Reports" 
        btn_excel = QPushButton("Parsed Excel/CSV Reports"); btn_excel.clicked.connect(lambda: self.open_folder(reports_base / "Excel_Sheet")); layout.addWidget(btn_excel)
        btn_html = QPushButton("Raw HTML/XML Reports"); btn_html.clicked.connect(lambda: self.open_folder(reports_base / "HTML_XML_Reports")); layout.addWidget(btn_html)
        btn_logs = QPushButton("Application Logs"); btn_logs.clicked.connect(lambda: self.open_folder(reports_base / "Logs")); layout.addWidget(btn_logs)
        btn_camera = QPushButton("Camera Frames"); btn_camera.clicked.connect(lambda: self.open_folder(self.config_dir / "Camera_Frames")); layout.addWidget(btn_camera)
        btn_serial_logs = QPushButton("Saved Serial Logs"); btn_serial_logs.clicked.connect(lambda: self.open_folder(self.config_dir / "SerialLogs")); layout.addWidget(btn_serial_logs)
        btn_python_scripts = QPushButton("Uploaded Python Scripts"); btn_python_scripts.clicked.connect(lambda: self.open_folder(self.python_scripts_dir)); layout.addWidget(btn_python_scripts)
        layout.addSpacing(10)
        btn_cfg_dir = QPushButton("Current Workspace Folder"); btn_cfg_dir.clicked.connect(lambda: self.open_folder(self.config_dir)); layout.addWidget(btn_cfg_dir)
        close_button_box = QHBoxLayout(); close_button_box.addStretch()
        close_btn = QPushButton("Close"); close_btn.clicked.connect(dialog.accept); close_button_box.addWidget(close_btn); layout.addLayout(close_button_box)
        dialog.exec_()

    def open_folder(self, folder_path_obj):
        folder_path = Path(folder_path_obj)
        if not folder_path.is_dir():
            reply = QMessageBox.question(self, "Folder Not Found", f"Folder does not exist:\n{folder_path}\n\nCreate it?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                try: folder_path.mkdir(parents=True, exist_ok=True)
                except Exception as e: QMessageBox.critical(self, "Error", f"Could not create folder:\n{e}"); return
            else: return
        try:
            if sys.platform == "win32": os.startfile(str(folder_path))
            elif sys.platform == "darwin": subprocess.run(["open", str(folder_path)], check=True)
            else: subprocess.run(["xdg-open", str(folder_path)], check=True)
        except Exception as e: QMessageBox.warning(self, "Error", f"Error opening folder:\n{e}")

    def restart_application(self):
        if self.canoe_worker and self.canoe_worker.isRunning(): self.canoe_worker.request_stop(); self.canoe_worker.wait(10000)
        if self.serial_worker and self.serial_worker.isRunning(): self.serial_worker.stop(); self.serial_worker.wait(10000)
        self.disconnect_serial()
        QTimer.singleShot(100, self._perform_restart)

    def _perform_restart(self):
        try:
            subprocess.Popen([sys.executable] + sys.argv)
            self.close()
        except Exception as e:
            QMessageBox.critical(self, "Restart Failed", f"Could not restart.\nPlease close manually.\n\nError: {e}")

    def show_about_info(self): dialog = AboutDialog(self); dialog.exec_()
    def show_about_creators(self): dialog = AboutCreatorsDialog(self); dialog.exec_()
    def show_feedback_form(self): dialog = FeedbackDialog(self.app_data_dir, self); dialog.exec_()

    def check_canoe_status(self):
        if self.execution_started: return 
        if not (self.canoe_config_path and self.canoe_config_path.is_file()):
            if hasattr(self, 'canoe_status_label') and self.canoe_status_label:
                self.set_status_label_style(self.canoe_status_label, "No Config")
                self.canoe_status_label.setText("No Config Loaded")
            return
        try:
            canoe_running = any(proc.info['name'] and proc.info['name'].lower() == "canoe64.exe" for proc in psutil.process_iter(['name']))
            self.set_status_label_style(self.canoe_status_label, "Ready" if canoe_running else "Not Running")
            self.canoe_status_label.setText("Ready" if canoe_running else "Not Running")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
             if hasattr(self, 'canoe_status_label') and self.canoe_status_label:
                self.set_status_label_style(self.canoe_status_label, "Unknown") 
                self.canoe_status_label.setText("Status Check Error")


    def setup_logging(self): 
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            if isinstance(handler, logging.FileHandler) and "app_execution_log.txt" in handler.baseFilename:
                handler.close(); root_logger.removeHandler(handler)
        
        log_folder = self.config_dir / "Reports" / "Logs" 
        log_file = log_folder / "app_execution_log.txt"
        try:
            log_folder.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
            file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)-8s - %(threadName)s - %(message)s"))
            file_handler.setLevel(logging.INFO)
            root_logger.addHandler(file_handler)
            log_and_print(f"File logging initialized: {log_file}")
        except Exception as e:
            print(f"Error setting up file logging to {log_file}: {e}")


    def populate_com_ports(self):
        if not SERIAL_AVAILABLE: return
        self.com_port_combo.clear()
        ports = serial.tools.list_ports.comports()
        if not ports:
            self.com_port_combo.addItem("No COM ports found"); self.com_port_combo.setEnabled(False); self.connect_serial_button.setEnabled(False)
        else:
            for port in sorted(ports, key=lambda p: p.device):
                self.com_port_combo.addItem(f"{port.device} - {port.description.split(' (')[0]}", userData=port.device)
            self.com_port_combo.setEnabled(True); self.connect_serial_button.setEnabled(True)
        self.refresh_ports_button.setEnabled(True)

    def toggle_serial_connection(self, checked):
        if checked: self.connect_serial()
        else: self.disconnect_serial()

    def connect_serial(self):
        if self.serial_port and self.serial_port.is_open: return True
        current_index = self.com_port_combo.currentIndex()
        if current_index < 0: QMessageBox.warning(self, "No Port Selected", "Select COM port."); self.connect_serial_button.setChecked(False); return False
        port_name = self.com_port_combo.itemData(current_index); baud_rate_str = self.baud_rate_combo.currentText()
        if not port_name or not baud_rate_str: QMessageBox.warning(self, "Connection Error", "Invalid port/baud."); self.connect_serial_button.setChecked(False); return False
        try:
            self.serial_port = serial.Serial(port=port_name, baudrate=int(baud_rate_str), timeout=0.1)
            if self.serial_port.is_open:
                self.set_status_label_style(self.serial_status_label, "Connected"); self.serial_status_label.setText(f"Connected ({port_name})")
                self.connect_serial_button.setText("Disconnect"); self.connect_serial_button.setChecked(True)
                self.log_serial_button.setEnabled(True); self.com_port_combo.setEnabled(False); self.baud_rate_combo.setEnabled(False); self.refresh_ports_button.setEnabled(False)
                if hasattr(self, 'serial_command_combo'): self.serial_command_combo.setEnabled(True) 
                if hasattr(self, 'send_serial_command_button'): self.send_serial_command_button.setEnabled(True) 
                self.start_serial_worker(); return True
            else: raise serial.SerialException(f"Failed to open {port_name}")
        except Exception as e:
            QMessageBox.critical(self, "Serial Error", f"Failed connect {port_name}: {e}"); self.serial_port = None; self.connect_serial_button.setChecked(False)
            self.set_status_label_style(self.serial_status_label, "Error"); self.serial_status_label.setText("Connection Error"); return False

    def disconnect_serial(self):
        self.stop_serial_worker()
        if self.serial_port and self.serial_port.is_open:
            try: self.serial_port.close()
            except Exception as e: log_and_print(f"Error closing port {self.serial_port.port}: {e}")
        self.serial_port = None
        self.set_status_label_style(self.serial_status_label, "Disconnected"); self.serial_status_label.setText("Disconnected")
        self.connect_serial_button.setText("Connect"); self.connect_serial_button.setChecked(False); self.connect_serial_button.setEnabled(True)
        self.log_serial_button.setEnabled(False); self.log_serial_button.setChecked(False); self.log_serial_button.setText("Start Logging")
        self.com_port_combo.setEnabled(True); self.baud_rate_combo.setEnabled(True); self.refresh_ports_button.setEnabled(True)
        self.save_serial_log_button.setEnabled(bool(self.serial_log_output.toPlainText()))
        if hasattr(self, 'serial_command_combo'): self.serial_command_combo.setEnabled(False) 
        if hasattr(self, 'send_serial_command_button'): self.send_serial_command_button.setEnabled(False) 
        if hasattr(self, 'serial_command_status_label'):
            self.serial_command_status_label.setText("Status: Idle")
            self.serial_command_status_label.setStyleSheet("")


    def start_serial_worker(self):
        if self.serial_worker and self.serial_worker.isRunning(): return
        try:
            self.serial_worker = SerialWorker(self.serial_port, parent=self)
            self.serial_worker.data_received_signal.connect(self.append_serial_log)
            self.serial_worker.error_signal.connect(self.handle_serial_error)
            self.serial_worker.finished_signal.connect(self.on_serial_worker_finished)
            self.serial_worker.start()
        except Exception as e:
             QMessageBox.critical(self, "Thread Error", f"Could not start serial thread:\n{e}"); self.disconnect_serial()

    def stop_serial_worker(self):
        if self.serial_worker and self.serial_worker.isRunning(): self.serial_worker.stop()

    def on_serial_worker_finished(self):
        self.serial_worker = None
        if not (self.serial_port and self.serial_port.is_open) and self.connect_serial_button.isChecked():
            QMessageBox.warning(self, "Serial Disconnected", "The serial connection was lost.")
            self.disconnect_serial()

    def handle_serial_error(self, error_message):
        self.append_serial_log(f"\n--- SERIAL ERROR: {error_message} ---\n")
        self.set_status_label_style(self.serial_status_label, "Error"); self.serial_status_label.setText("Comm Error")
        QMessageBox.critical(self, "Serial Error", f"Error occurred:\n{error_message}\n\nDisconnecting.")
        self.disconnect_serial()

    def append_serial_log(self, text):
        self.serial_log_output.moveCursor(QTextCursor.End); self.serial_log_output.insertPlainText(text)
        if not self.save_serial_log_button.isEnabled(): self.save_serial_log_button.setEnabled(True)
        if self.is_serial_logging and self.serial_log_file: self.serial_log_file.write(text)

    def toggle_serial_logging(self, checked):
        if checked:
            if not self.serial_port or not self.serial_port.is_open: QMessageBox.warning(self, "Not Connected", "Connect to port first."); self.log_serial_button.setChecked(False); return
            self.start_serial_logging()
        else: self.stop_serial_logging()

    def start_serial_logging(self):
        if self.is_serial_logging: return
        timestamp = time.strftime("%Y%m%d_%H%M%S"); port_name = self.serial_port.port if self.serial_port else "UNKNOWN"
        safe_port_name = port_name.replace('/', '_').replace('\\', '_')
        log_folder = self.config_dir / "SerialLogs" 
        log_folder.mkdir(parents=True, exist_ok=True)
        log_filename = f"serial_log_{safe_port_name}_{timestamp}.txt"
        log_filepath = log_folder / log_filename
        try:
            self.serial_log_file = open(log_filepath, "a", encoding="utf-8", buffering=1)
            header = f"--- Serial Log Started: {time.strftime('%Y-%m-%d %H:%M:%S')} ---\nPort: {port_name}, Baud: {self.serial_port.baudrate}\n\n"
            self.serial_log_file.write(header)
            self.is_serial_logging = True; self.log_serial_button.setText("Stop Logging"); self.log_serial_button.setChecked(True)
            self.status_bar.showMessage(f"Logging serial to {log_filename}", 0)
        except Exception as e:
            QMessageBox.critical(self, "Logging Error", f"Could not open log file:\n{log_filepath}\n\nError: {e}")
            self.serial_log_file = None; self.is_serial_logging = False; self.log_serial_button.setChecked(False)

    def stop_serial_logging(self, log_error=False):
        if not self.is_serial_logging: return
        if self.serial_log_file:
            try:
                footer = f"\n\n--- Serial Log Stopped: {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n"
                self.serial_log_file.write(footer); self.serial_log_file.close()
                if not log_error: self.status_bar.showMessage("Serial file logging stopped.", 3000)
            except Exception as e: log_and_print(f"Error closing serial log file: {e}")
        self.serial_log_file = None; self.is_serial_logging = False
        self.log_serial_button.setText("Start Logging"); self.log_serial_button.setChecked(False)

    def save_serial_log(self):
        log_text = self.serial_log_output.toPlainText()
        if not log_text: QMessageBox.information(self, "Log Empty", "No data to save."); return
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        port_name = self.serial_port.port if self.serial_port and self.serial_port.port else "UNKNOWN"
        safe_port_name = port_name.replace('/', '_').replace('\\', '_')
        log_folder = self.config_dir / "SerialLogs" 
        log_folder.mkdir(parents=True, exist_ok=True)
        default_filename = f"manual_serial_save_{safe_port_name}_{timestamp}.txt"; default_path = log_folder / default_filename
        filePath, _ = QFileDialog.getSaveFileName(self, "Save Serial Log As", str(default_path), "Text Files (*.txt);;All Files (*)")
        if filePath:
            try:
                with open(filePath, 'w', encoding='utf-8') as f: f.write(log_text)
                QMessageBox.information(self, "Log Saved", f"Log saved to:\n{filePath}")
            except Exception as e: QMessageBox.critical(self, "Save Error", f"Could not save log:\n{e}")

    def handle_send_serial_command(self):
        if not SERIAL_AVAILABLE: return
        
        command_text = self.serial_command_combo.currentText().strip()
        if not command_text:
            self.serial_command_status_label.setText("Status: No command entered.")
            self.serial_command_status_label.setStyleSheet("color: orange;")
            return

        if not self.serial_port or not self.serial_port.is_open:
            self.serial_command_status_label.setText("Status: Not connected.")
            self.serial_command_status_label.setStyleSheet("color: red;")
            QMessageBox.warning(self, "Not Connected", "Serial port is not connected. Please connect first.")
            return

        try:
            full_command = command_text + '\r\n' 
            self.serial_port.write(full_command.encode('utf-8')) 
            log_and_print(f"Serial command sent: {command_text!r}") 
            self.serial_command_status_label.setText(f"Status: Sent '{command_text[:20]}{'...' if len(command_text)>20 else ''}'")
            self.serial_command_status_label.setStyleSheet("color: green;")

            if command_text not in self.serial_command_history_list:
                self.serial_command_history_list.insert(0, command_text) 
                if len(self.serial_command_history_list) > 20: 
                    self.serial_command_history_list.pop()
                
                self.serial_command_combo.blockSignals(True)
                current_selection = self.serial_command_combo.currentText() 
                self.serial_command_combo.clear()
                self.serial_command_combo.addItems(self.serial_command_history_list)
                if current_selection in self.serial_command_history_list:
                     self.serial_command_combo.setCurrentText(current_selection)
                else: 
                    self.serial_command_combo.setCurrentIndex(0)
                self.serial_command_combo.lineEdit().setText("") 
                self.serial_command_combo.blockSignals(False)

            else: 
                self.serial_command_history_list.remove(command_text)
                self.serial_command_history_list.insert(0, command_text)
                self.serial_command_combo.blockSignals(True)
                self.serial_command_combo.clear()
                self.serial_command_combo.addItems(self.serial_command_history_list)
                self.serial_command_combo.setCurrentIndex(0)
                self.serial_command_combo.lineEdit().setText("") 
                self.serial_command_combo.blockSignals(False)


        except serial.SerialException as e:
            error_msg = f"Serial write error: {e}"
            log_and_print(error_msg)
            self.serial_command_status_label.setText(f"Status: Error - {error_msg}")
            self.serial_command_status_label.setStyleSheet("color: red;")
            QMessageBox.critical(self, "Serial Send Error", error_msg)
        except Exception as e:
            error_msg = f"Unexpected error sending command: {e}"
            log_and_print(error_msg)
            logging.exception("Unexpected serial send error:")
            self.serial_command_status_label.setText(f"Status: Error - {error_msg}")
            self.serial_command_status_label.setStyleSheet("color: red;")
            QMessageBox.critical(self, "Send Error", error_msg)


if __name__ == "__main__":
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)-8s - %(threadName)-10s - %(message)s", handlers=[logging.StreamHandler(sys.stdout)])
    log_and_print("Application starting...")

    config = load_config()
    cfg_file_str = config.get('last_cfg_file')
    initial_cfg_path = None 

    if cfg_file_str:
        temp_path = Path(cfg_file_str)
        if temp_path.is_file() and temp_path.suffix.lower() == '.cfg':
            initial_cfg_path = temp_path
            log_and_print(f"Found valid last used CANoe config: {initial_cfg_path}")
        else:
            log_and_print(f"Last used CANoe config is invalid or not found: {cfg_file_str}. Starting without a pre-loaded config.")
    else:
        log_and_print("No last used CANoe config found. Starting without a pre-loaded config.")

    try:
        main_window = TestExecutionApp(str(initial_cfg_path) if initial_cfg_path else None, config)
        main_window.show()
        exit_code = app.exec_()
        log_and_print(f"Application exiting with code {exit_code}.")
        # Explicitly delete main_window before sys.exit to help with Qt object cleanup
        del main_window 
        sys.exit(exit_code)
    except Exception as e:
         logging.exception("A critical error occurred during application startup or execution!")
         QMessageBox.critical(None, "Application Startup Error", f"A critical error occurred:\n{e}\n\nPlease check the logs for more details.")
         sys.exit(1)