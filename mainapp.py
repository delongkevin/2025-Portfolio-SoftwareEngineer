import sys
import serial
import serial.tools.list_ports
import cv2
import os
import time
import re
import subprocess
import win32com.client
import pandas as pd
import openpyxl
import xml.etree.ElementTree as ET
import pythoncom
import logging
import win32gui
import ctypes


from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit, QLineEdit, QHBoxLayout, QComboBox, QTabWidget, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QListWidget, QListWidgetItem, QFileDialog,  QSpinBox
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QPixmap, QIcon, QFont
from PyQt5.QtWidgets import QWidget, QVBoxLayout

# Setup logging
log_file_path = 'canoe_execution_log.txt'
logging.basicConfig(filename=log_file_path, level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')



def find_canoe_panel(panel_name):
    hwnd = win32gui.FindWindow(None, panel_name)
    if hwnd:
        print(f"Found panel: {panel_name} with HWND: {hwnd}")
        return hwnd
    else:
        print(f"Panel '{panel_name}' not found")
        return None


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

def start_measurement(canoe_app):
    if canoe_app:
        canoe_app.Measurement.Start()
        print("CANoe Measurement started")

def stop_measurement(canoe_app):
    if canoe_app:
        canoe_app.Measurement.Stop()
        print("CANoe Measurement stopped")

class CanoePanelEmbedder(QWidget):
    def __init__(self, hwnd, parent=None):
        super().__init__(parent)
        self.hwnd = hwnd
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        self.setLayout(layout)
        self.embed_canoe_panel(self.hwnd)

    def embed_canoe_panel(self, hwnd):
        if hwnd:
            ctypes.windll.user32.SetParent(hwnd, int(self.winId()))  # Embed CANoe's HWND into this widget's window
            ctypes.windll.user32.SetWindowLongW(hwnd, -16, 0x10000000 | 0x40000000)  # Adjust window styles
            ctypes.windll.user32.ShowWindow(hwnd, 1)  # Show the panel


class CanoeWorker(QThread):
    status_signal = pyqtSignal(str)

    def __init__(self, canoe_config_path, test_script_path, parent=None):
        super().__init__(parent)
        self.canoe_config_path = canoe_config_path
        self.test_script_path = test_script_path
        self.canoe_sync = None

    def run(self):
        try:
            self.status_signal.emit("Initializing CANoe...")
            self.canoe_sync = CanoeSync()  # Initialize CANoeSync object

            self.status_signal.emit("Loading CANoe configuration...")
            self.canoe_sync.Load(self.canoe_config_path)  # Load CANoe configuration

            self.status_signal.emit("Loading test configuration...")
            self.canoe_sync.LoadTestConfiguration("TestConfig", self.test_script_path)  # Load test script

            self.status_signal.emit("Starting CANoe simulation...")
            self.canoe_sync.Start()  # Start CANoe simulation

            self.status_signal.emit("Running test configurations...")
            self.canoe_sync.RunTestConfigs()  # Run the test configurations

            self.status_signal.emit("Stopping CANoe simulation...")
            self.canoe_sync.Stop()  # Stop CANoe simulation

            self.status_signal.emit("CANoe simulation completed.")
        except Exception as e:
            self.status_signal.emit(f"Error during CANoe execution: {str(e)}")



class SerialPortLogger(QThread):
    data_received = pyqtSignal(dict)  # Emit a dictionary with port and raw byte data

    def __init__(self, port, app, log_file, parent=None):
        super().__init__(parent)
        self.port = port
        self.app = app
        self.log_file = log_file
        self.serial_conn = None
        self.connected = False

    def run(self):
        """Continuously read from the serial port and emit the raw byte data."""
        try:
            self.serial_conn = serial.Serial(self.port, baudrate=115200, timeout=0)
            self.app.serial_conns[self.port] = self.serial_conn
            self.connected = True

            while self.connected:
                if self.serial_conn.is_open:
                    raw_data = self.serial_conn.read(1024)  # Read up to 1024 bytes of data
                    if raw_data:
                        # Emit the raw data to update the UI
                        self.data_received.emit({'port': self.port, 'data': raw_data})

                        # Try to decode the raw data as ASCII (or UTF-8) before writing to the log file
                        try:
                            decoded_data = raw_data.decode('ascii', errors='replace').strip()
                        except UnicodeDecodeError:
                            decoded_data = raw_data.decode('utf-8', errors='replace').strip()

                        if self.log_file:
                            try:
                                # Add a timestamp before writing the decoded data
                                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')  # Format the current time
                                self.log_file.write(f"{timestamp}-{decoded_data}\n")
                                self.log_file.flush()  # Ensure the data is written to disk immediately
                            except Exception as e:
                                print(f"Unable to parse byte to log file: {e}")
                                time.sleep(1)
                else:
                    self.connected = False
                    self.data_received.emit({'port': self.port, 'data': f"{self.port} connection lost.".encode('utf-8')})
                    break
        except serial.SerialException as e:
            # Handle serial exceptions
            self.data_received.emit({'port': self.port, 'data': f"Error opening {self.port}: {str(e)}".encode('utf-8')})
        finally:
            # Clean up the serial connection and log file
            if self.serial_conn:
                self.serial_conn.close()
            if self.log_file:
                self.log_file.close()
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


class CanoeSync:
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

class SerialCameraApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.serial_ports = []
        self.serial_threads = []
        self.serial_conns = {}
        self.log_files = {}
        self.canoe_config_path = ""
        self.test_script_path = ""
        self.canoe_running = False
        self.canoe_app = None
        self.captured_images = []  # List to store paths of captured images
        self.canoe_sync = None #canoesync object
        self.canoe_worker = None #placeholder for the thread object
        self.initUI()

    # Function to start CANoe in the background
    def start_canoe():
        """Start the CANoe application in the background"""
        try:
            canoe_app = win32com.client.DispatchEx('CANoe.Application')
            canoe_app.Visible = False  # Set this to False if you want CANoe to run without showing the main window
            print('CANoe started successfully')
            return canoe_app
        except Exception as e:
            print(f"Failed to start CANoe: {str(e)}")
            return None

    def stop_canoe(self):
        """Stop CANoe application"""
        if self.canoe_app:
            self.canoe_app.Quit()  # Close CANoe
            print('CANoe stopped successfully')

    def find_canoe_panel(self, panel_name):
        """Find CANoe panel HWND by its name"""
        hwnd = win32gui.FindWindow(None, panel_name)
        if hwnd:
            print(f"Found panel: {panel_name} with HWND: {hwnd}")
            return hwnd
        else:
            print(f"Panel '{panel_name}' not found")
            return None

    def initUI(self):
        self.setWindowTitle('Serial and Camera Manager')

        # Main widget and layout
        widget = QWidget()
        self.setCentralWidget(widget)
        layout = QVBoxLayout(widget)

        # Tab Widget to switch between functionalities
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Serial Port Manager Tab
        self.serial_tab = QWidget()
        self.init_serial_tab()
        self.tab_widget.addTab(self.serial_tab, "Serial Port Logger")

        # Camera Capture Tab
        self.camera_tab = QWidget()
        self.init_camera_tab()
        self.tab_widget.addTab(self.camera_tab, "Camera Capture")

        # Capture History Tab
        self.capture_history_tab = QWidget()
        self.init_capture_history_tab()
        self.tab_widget.addTab(self.capture_history_tab, "Capture History")

        # CANoe Simulation Tab
        self.canoe_tab = QWidget()
        self.init_canoe_tab()
        self.tab_widget.addTab(self.canoe_tab, "CANoe Simulation")
        
        # Power Supply Control Tab
        self.power_supply_tab = QWidget()
        self.init_power_supply_tab()
        self.tab_widget.addTab(self.power_supply_tab, "Power Supply Control")

        # Add buttons to control CANoe
        start_button = QPushButton('Start CANoe', self)
        start_button.clicked.connect(self.start_canoe)
        layout.addWidget(start_button)

        stop_button = QPushButton('Stop CANoe', self)
        stop_button.clicked.connect(self.stop_canoe)
        layout.addWidget(stop_button)

        # Embed the CANoe Measurement panel (for example)
        measurement_hwnd = find_canoe_panel("MainPanel")
        if measurement_hwnd:
            self.canoe_panel = CanoePanelEmbedder(measurement_hwnd, self)
            layout.addWidget(self.canoe_panel)

        self.setGeometry(100, 100, 800, 600)
        self.show()
        
    def init_power_supply_tab(self):
        layout = QVBoxLayout(self.power_supply_tab)

        # Power Supply Status Label
        self.power_supply_status_label = QLabel('Power Supply Status: Not connected')
        layout.addWidget(self.power_supply_status_label)

        # Voltage and Current Display (Larger text)
        self.voltage_label = QLabel("Voltage: N/A V")
        self.voltage_label.setFont(QFont('Arial', 24))  # Set larger font size
        layout.addWidget(self.voltage_label)

        self.current_label = QLabel("Current: N/A A")
        self.current_label.setFont(QFont('Arial', 24))  # Set larger font size
        layout.addWidget(self.current_label)

        # Buttons for connecting, reading, and controlling power supply
        self.connect_power_supply_button = QPushButton('Connect to Power Supply')
        layout.addWidget(self.connect_power_supply_button)
        self.connect_power_supply_button.clicked.connect(self.connect_power_supply)

        self.disconnect_power_supply_button = QPushButton('Disconnect from Power Supply')
        layout.addWidget(self.disconnect_power_supply_button)
        self.disconnect_power_supply_button.clicked.connect(self.disconnect_power_supply)
        self.disconnect_power_supply_button.setEnabled(False)  # Initially disable the button

        self.read_voltage_current_button = QPushButton('Read Voltage and Current')
        layout.addWidget(self.read_voltage_current_button)
        self.read_voltage_current_button.setEnabled(False)  # Initially disable the button
        self.read_voltage_current_button.clicked.connect(self.read_voltage_current)

        self.on_button = QPushButton('Turn On Power Supply')
        layout.addWidget(self.on_button)
        self.on_button.setEnabled(False)  # Initially disable the button
        self.on_button.clicked.connect(lambda: self.send_power_supply_command('SOUT0\r'))

        self.off_button = QPushButton('Turn Off Power Supply')
        layout.addWidget(self.off_button)
        self.off_button.setEnabled(False)  # Initially disable the button
        self.off_button.clicked.connect(lambda: self.send_power_supply_command('SOUT1\r'))

        self.voltage_spinbox = QSpinBox()
        self.voltage_spinbox.setRange(0, 300)  # Represents 0.0V to 30.0V
        self.voltage_spinbox.setSuffix(' V')
        layout.addWidget(self.voltage_spinbox)

        self.set_voltage_button = QPushButton('Set Voltage')
        layout.addWidget(self.set_voltage_button)
        self.set_voltage_button.setEnabled(False)  # Initially disable the button
        self.set_voltage_button.clicked.connect(self.set_voltage)

        
    def connect_power_supply(self):
        # Detect available serial ports with description "Silicon Labs CP210x USB to UART Bridge"
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if "Silicon Labs CP210x USB to UART Bridge" in port.description:
                try:
                    self.power_supply_conn = serial.Serial(port.device, baudrate=9600, timeout=1)
                    self.power_supply_status_label.setText(f'Connected to Power Supply: {port.device}')
                    self.connect_power_supply_button.setEnabled(False)  # Disable the connect button
                    self.disconnect_power_supply_button.setEnabled(True)  # Enable the disconnect button
                    self.read_voltage_current_button.setEnabled(True)  # Enable the read button
                    self.on_button.setEnabled(True)  # Enable the ON button
                    self.off_button.setEnabled(True)  # Enable the OFF button
                    self.set_voltage_button.setEnabled(True)  # Enable the set voltage button
                    return
                except serial.SerialException as e:
                    self.power_supply_status_label.setText(f'Error: {str(e)}')
                    return
        self.power_supply_status_label.setText('Error: Power Supply not found')


    def disconnect_power_supply(self):
        try:
            # Check if the power supply connection exists and is open
            if hasattr(self, 'power_supply_conn') and self.power_supply_conn.is_open:
                self.power_supply_conn.close()  # Close the connection
                self.power_supply_status_label.setText('Power Supply Status: Disconnected')
                self.connect_power_supply_button.setEnabled(True)  # Enable the connect button
                self.disconnect_power_supply_button.setEnabled(False)  # Disable the disconnect button
                self.read_voltage_current_button.setEnabled(False)  # Disable the read button
                self.on_button.setEnabled(False)  # Disable the ON button
                self.off_button.setEnabled(False)  # Disable the OFF button
                self.set_voltage_button.setEnabled(False)  # Disable the set voltage button
            else:
                self.power_supply_status_label.setText('Error: Power Supply not connected')
        except Exception as e:
            self.power_supply_status_label.setText(f'Error while disconnecting: {str(e)}')


    def read_voltage_current(self):
        log_and_print("Attempting to read voltage and current from power supply...")
        if hasattr(self, 'power_supply_conn') and self.power_supply_conn.is_open:
            try:
                # Send the command to read voltage and current
                self.power_supply_conn.write(b'GETD\r')
                log_and_print("Sent GETD command to power supply")
                response = self.power_supply_conn.readline().decode('utf-8').strip()
                log_and_print(f"Received response: {response}")
            
                # Parse response assuming first 4 digits are voltage and next 4 are current
                if len(response) >= 8:  # Check if the response has at least 8 digits
                    voltage_str = response[:3]
                    current_str = response[4:7]

                    # Convert the strings to float values
                    voltage = int(voltage_str) / 10.0  # Convert to volts (e.g., '0121' -> 12.1V)
                    current = int(current_str) / 10.0  # Convert to amps (e.g., '0000' -> 0.00A)

                    # Update the labels with the parsed values
                    self.voltage_label.setText(f"Voltage: {voltage} V")
                    self.current_label.setText(f"Current: {current} A")
                    self.power_supply_status_label.setText(f"Voltage: {voltage}V, Current: {current}A")
                    log_and_print(f"Voltage: {voltage} V, Current: {current} A")
                else:
                    log_and_print("Error: Could not parse voltage/current data.")
                    self.power_supply_status_label.setText("Error: Could not parse voltage/current data.")
            except Exception as e:
                log_and_print(f"Error while reading voltage/current: {str(e)}")
                self.power_supply_status_label.setText(f'Error while reading voltage/current: {str(e)}')
        else:
            log_and_print("Error: Power Supply not connected")
            self.power_supply_status_label.setText('Error: Power Supply not connected')

    def send_power_supply_command(self, command):
        if hasattr(self, 'power_supply_conn') and self.power_supply_conn.is_open:
            self.power_supply_conn.write(command.encode('utf-8'))
            self.power_supply_status_label.setText(f'Sent command: {command}')
        else:
            self.power_supply_status_label.setText('Error: Power Supply not connected')

    def set_voltage(self):
        voltage_value = self.voltage_spinbox.value()
        command = f'VOLT{voltage_value:03d}\r'  # Voltage command in format VOLTXXX\r
        self.send_power_supply_command(command)     

    def init_serial_tab(self):
        layout = QVBoxLayout(self.serial_tab)

        # Dropdown for selecting the COM port to send commands to
        self.com_port_selector = QComboBox()
        layout.addWidget(self.com_port_selector)

        # Serial Port Status
        self.serial_status_label = QLabel('USB Serial Port Status: Not connected')
        layout.addWidget(self.serial_status_label)

        # Connect Button
        self.connect_serial_button = QPushButton('Connect to Serial Ports')
        layout.addWidget(self.connect_serial_button)
        self.connect_serial_button.clicked.connect(self.connect_serial_ports)

        # Disconnect Button
        self.disconnect_serial_button = QPushButton('Disconnect from Serial Ports')
        self.disconnect_serial_button.setEnabled(False)
        layout.addWidget(self.disconnect_serial_button)
        self.disconnect_serial_button.clicked.connect(self.disconnect_serial_ports)

        # Log viewer for all COM ports
        self.log_viewer = QTextEdit(self)
        self.log_viewer.setReadOnly(True)
        layout.addWidget(self.log_viewer)

        # Input field and button to send commands
        command_layout = QHBoxLayout()
        self.command_input = QLineEdit(self)
        command_layout.addWidget(self.command_input)

        self.send_command_button = QPushButton('Send Command', self)
        command_layout.addWidget(self.send_command_button)
        layout.addLayout(command_layout)

        self.send_command_button.clicked.connect(self.send_command_to_port)

    def init_camera_tab(self):
        layout = QVBoxLayout(self.camera_tab)

        # Button to capture image
        self.capture_button = QPushButton('Capture Image')
        layout.addWidget(self.capture_button)
        self.capture_button.clicked.connect(self.capture_image)

        self.camera_status_label = QLabel('Camera Status: Not started')
        layout.addWidget(self.camera_status_label)

        # Graphics view to display captured images
        self.graphics_view = QGraphicsView()
        self.graphics_scene = QGraphicsScene()
        self.graphics_view.setScene(self.graphics_scene)
        layout.addWidget(self.graphics_view)

    def init_capture_history_tab(self):
        layout = QVBoxLayout(self.capture_history_tab)

        # List widget to show thumbnails of all captured images
        self.capture_history_list = QListWidget()
        self.capture_history_list.itemClicked.connect(self.open_image)
        layout.addWidget(self.capture_history_list)

    def init_canoe_tab(self):
        layout = QVBoxLayout(self.canoe_tab)

        # Button to open CANoe configuration
        self.open_canoe_button = QPushButton('Select CANoe Configuration')
        layout.addWidget(self.open_canoe_button)
        self.open_canoe_button.clicked.connect(self.open_canoe_config)

        # Button to select test script
        self.select_script_button = QPushButton('Select Test Script')
        layout.addWidget(self.select_script_button)
        self.select_script_button.clicked.connect(self.select_test_script)

        # Button to start CANoe simulation
        self.start_simulation_button = QPushButton('Start CANoe Application')
        layout.addWidget(self.start_simulation_button)
        self.start_simulation_button.clicked.connect(self.start_canoe_simulation)

        # Button to kill CANoe process
        self.kill_canoe_button = QPushButton('Kill CANoe Process')
        layout.addWidget(self.kill_canoe_button)
        self.kill_canoe_button.clicked.connect(self.kill_canoe_process)

        # Label to display simulation status
        self.simulation_status_label = QLabel('Simulation Status: Not started')
        layout.addWidget(self.simulation_status_label)

        # Label to display CANoe readiness status
        self.canoe_status_label = QLabel('CANoe Status: Not ready')
        self.canoe_status_label.setStyleSheet('QLabel { color : red; }')
        layout.addWidget(self.canoe_status_label)

        # Timer to check CANoe status
        self.canoe_status_timer = QTimer()
        self.canoe_status_timer.timeout.connect(self.check_canoe_status)
        #self.canoe_status_timer.start(1000)
        
    def connect_serial_ports(self):
        # Detect available serial ports
        ports = serial.tools.list_ports.comports()
        available_ports = [port.device for port in ports if "USB Serial" in port.description]

        if len(available_ports) >= 4:
            self.serial_ports = available_ports[:4]
            self.serial_status_label.setText(f'Connected to USB serial ports: {", ".join(self.serial_ports)}')

            # Populate the COM port dropdown
            self.com_port_selector.addItems(self.serial_ports)

            # Start threads to log data from each port
            for port in self.serial_ports:
                timestamp = time.strftime('%Y-%m-%d')  # Format the current time
                log_file_path = f"{port}_UART_{timestamp}.txt"
                log_file = open(log_file_path, 'a')  # Open the log file for writing
                self.log_files[port] = log_file  # Store the log file handle for each port

                # Start the serial logger thread
                serial_thread = SerialPortLogger(port, self, log_file)
                serial_thread.data_received.connect(self.update_log_viewer)
                serial_thread.start()
                self.serial_threads.append(serial_thread)

            # Disable the connect button and enable the disconnect button
            self.connect_serial_button.setEnabled(False)
            self.disconnect_serial_button.setEnabled(True)
        else:
            self.serial_status_label.setText('Error: Less than 4 USB serial ports available.')

    def disconnect_serial_ports(self):
        try:
            # Stop each thread and close each open serial connection
            for thread in self.serial_threads:
                thread.connected = False  # Stop the thread loop
                thread.wait()  # Ensure the thread finishes

            for port, conn in self.serial_conns.items():
                if conn.is_open:
                    conn.close()

            # Clear the list of serial connections and threads
            self.serial_conns.clear()
            self.serial_threads.clear()

            # Update the UI
            self.serial_status_label.setText('USB Serial Port Status: Disconnected')
            self.com_port_selector.clear()

            # Enable the connect button and disable the disconnect button
            self.connect_serial_button.setEnabled(True)
            self.disconnect_serial_button.setEnabled(False)
            
        except Exception as e:
            print(f"Unable to parse byte to log file: {e}")
            time.sleep(1)

    def send_command_to_port(self):
        selected_port = self.com_port_selector.currentText()
        command = self.command_input.text()

        # Ensure a command is provided before sending
        if not command.strip():
            self.log_viewer.append("Error: No command entered.")
            return

        # Check if the selected port is valid and open
        if selected_port in self.serial_conns and self.serial_conns[selected_port].is_open:
            try:
                # Add terminator if needed, like '\r' or '\n'
                full_command = command + '\r'  # Adjust as necessary
                self.serial_conns[selected_port].write(full_command.encode('utf-8'))
                self.log_viewer.append(f"Sent to {selected_port}: {command}")

                # Wait for a response after sending the command
                time.sleep(0.1)  # Short delay to allow response
                response = self.serial_conns[selected_port].readline().decode('utf-8', errors='replace').strip()
                if response:
                    self.log_viewer.append(f"Response from {selected_port}: {response}")
                else:
                    self.log_viewer.append(f"No response from {selected_port}")

            except Exception as e:
                self.log_viewer.append(f"Error sending command: {str(e)}")
        else:
            self.log_viewer.append(f"Error: {selected_port} is not connected or is closed.")

    def update_log_viewer(self, data):
        try:
            decoded_data = data['data'].decode('utf-8', errors='replace').strip()
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            self.log_viewer.append(f"[{data['port']}] {timestamp} - {decoded_data}\n")
        except Exception as e:
            hex_data = data['data'].hex()
            self.log_viewer.append(f"[{data['port']}] Raw Data (hex): {hex_data}\n")

    def capture_image(self):
        self.camera_status_label.setText('Capturing image...')
        if not os.path.exists('.//images'):
            os.makedirs('.//images')

        for i in range(1):
            camera = cv2.VideoCapture(i)
            if camera.isOpened():
                return_value, image = camera.read()
                new_image_name = f'CVADAS_{i}_TimeStamp_{time.time()}.png'
                image_path = os.path.join('.//images', new_image_name)
                cv2.imwrite(image_path, image)

                # Display the captured image as a thumbnail
                pixmap = QPixmap(image_path)
                self.graphics_scene.clear()
                self.graphics_scene.addPixmap(pixmap)
                self.camera_status_label.setText(f'Image captured: {new_image_name}')
                self.captured_images.append(image_path)
                self.update_capture_history()
                camera.release()
                return
        self.camera_status_label.setText('Error: No camera detected.')

    def update_capture_history(self):
        self.capture_history_list.clear()
        for image_path in self.captured_images:
            item = QListWidgetItem()
            icon = QIcon(QPixmap(image_path).scaled(100, 100, Qt.KeepAspectRatio))
            item.setIcon(icon)
            item.setText(image_path)
            self.capture_history_list.addItem(item)

    def open_image(self, item):
        image_path = item.text()
        os.startfile(image_path)

    def open_canoe_config(self):
        self.canoe_config_path, _ = QFileDialog.getOpenFileName(self, 'Open CANoe Configuration', '', 'CANoe Config Files (*.cfg)')
        if self.canoe_config_path:
            self.simulation_status_label.setText(f'CANoe Config Selected: {os.path.basename(self.canoe_config_path)}')

    def select_test_script(self):
        self.test_script_path, _ = QFileDialog.getOpenFileName(self, 'Select Test Script', '', 'VTUExe Files (*.vtuexe);;All Files (*)')
        if self.test_script_path:
            self.simulation_status_label.setText(f'Test Script Selected: {os.path.basename(self.test_script_path)}')

    def kill_canoe_process(self):
        try:
            if self.canoe_sync:
                self.canoe_sync.KillCANoe()
                self.simulation_status_label.setText('Simulation Status: Stopped')
        except Exception as e:
            print(e)
            
    def start_canoe_simulation(self):
        """Start the CANoe simulation process"""
        self.canoe_app = start_canoe()  # This will call the start_canoe() function
        if self.canoe_app:
            print("CANoe is running and ready for simulation.")
        else:
            print("Failed to start CANoe.")

    def update_canoe_status(self, message):
        """Update the GUI with the status message from the CANoe worker thread."""
        self.simulation_status_label.setText(message)
        

    def check_canoe_status(self):
        """Check if CANoe64.exe is running, but only if it's expected to be running."""
        if self.canoe_running:
            try:
                output = subprocess.check_output(['tasklist'], universal_newlines=True)
                if 'CANoe64.exe' in output:
                    self.canoe_status_label.setText('CANoe Status: Ready')
                    self.canoe_status_label.setStyleSheet('QLabel { color : green; }')
                else:
                    # If CANoe was running but now isn't, stop further checks
                    self.canoe_running = False
                    self.canoe_status_label.setText('CANoe Status: Not ready')
                    self.canoe_status_label.setStyleSheet('QLabel { color : red; }')
            except Exception as e:
                self.canoe_status_label.setText(f'Error: {str(e)}')


if __name__ == '__main__':
    try:
        app = QApplication(sys.argv)
        main_window = SerialCameraApp()
        main_window.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(e)

