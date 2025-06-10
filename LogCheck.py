import os
import subprocess
import time
from pathlib import Path
import serial.tools.list_ports

# Function to automatically detect available COM ports
def detect_serial_ports():
    """Detect and return a list of available serial COM ports."""
    ports = list(serial.tools.list_ports.comports())
    serial_ports = [port.device for port in ports]
    return serial_ports

# Configuration for log files
log_directory = "./logs"
log_files = []

# Ensure the log directory exists
os.makedirs(log_directory, exist_ok=True)

# Function to start logging using Tera Term
def start_logging(serial_port, log_file):
    """Start logging on the specified serial port using Tera Term."""
    tera_term_path = "C:\\Program Files\\Tera Term\\ttermpro.exe"  # Adjust this path to where Tera Term is installed
    log_command = f"{tera_term_path} /C={serial_port} /BAUD=115200 /M=TTY /L={log_file} /FD /T=1"
    # The /FD flag enables timestamps in the log
    subprocess.Popen(log_command, shell=True)
    print(f"Started logging on {serial_port}, saving to {log_file}")

# Function to start logging on all serial ports
def log_on_all_ports(serial_ports):
    """Start logging on all configured serial ports."""
    global log_files
    for port in serial_ports:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_directory, f"log_{port}_{timestamp}.log")
        log_files.append(log_file)
        start_logging(port, log_file)
    print("Logging started on all ports.")

# Function to compare log file sizes after closing the logs
def compare_log_file_sizes():
    """Compare the file sizes of all log files once logging is complete."""
    file_sizes = {}
    for log_file in log_files:
        try:
            size = os.path.getsize(log_file)
            file_sizes[log_file] = size
        except FileNotFoundError:
            print(f"Log file {log_file} not found.")
            file_sizes[log_file] = 0
    return file_sizes

# Example usage
if __name__ == "__main__":
    serial_ports = detect_serial_ports()

    if len(serial_ports) < 4:
        print("Error: Less than 4 serial ports detected.")
        print(f"Detected ports: {serial_ports}")
        exit(1)  # Exit the script if less than 4 ports are found
    else:
        serial_ports = serial_ports[:4]  # Take only the first 4 if more than 4 are detected
        print(f"Detected 4 serial ports: {serial_ports}")
    
    log_on_all_ports(serial_ports)

    # Wait for some time to collect logs (adjust as necessary)
    time.sleep(20)  # wait for script to finish ; adjust this for your use case

    # Close Tera Term instances and compare log file sizes
    print("Comparing log file sizes...")
    file_sizes = compare_log_file_sizes()

    # Display the file sizes
    for log_file, size in file_sizes.items():
        print(f"{log_file}: {size} bytes")
