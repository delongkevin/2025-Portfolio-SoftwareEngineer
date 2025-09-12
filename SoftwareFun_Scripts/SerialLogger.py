import sys
import serial
import serial.tools.list_ports
import os
import time
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit, QLineEdit, QHBoxLayout, QComboBox, QTabWidget, QFileDialog
)
from PyQt5.QtCore import QThread, pyqtSignal

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
                            decoded_data = raw_data.decode('ascii', errors='replace')
                        except UnicodeDecodeError:
                            decoded_data = raw_data.decode('utf-8', errors='replace')

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
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Serial and Camera Manager')

        widget = QWidget()
        self.setCentralWidget(widget)
        layout = QVBoxLayout(widget)

        # Tab Widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Serial Port Tab
        self.serial_tab = QWidget()
        self.init_serial_tab()
        self.tab_widget.addTab(self.serial_tab, "Serial Port Logger")

        self.setGeometry(100, 100, 800, 600)

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
                log_file_path = f"{port}_log.txt"
                log_file = open(log_file_path, 'w')  # Open the log file for writing
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
            # Close each open serial connection
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
            decoded_data = data['data'].decode('utf-8', errors='replace')
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            self.log_viewer.append(f"[{data['port']}] {timestamp} - {decoded_data}")
        except Exception as e:
            hex_data = data['data'].hex()
            self.log_viewer.append(f"[{data['port']}] Raw Data (hex): {hex_data}")


if __name__ == '__main__':
    try:
        app = QApplication(sys.argv)
        main_window = SerialCameraApp()
        main_window.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(e)
