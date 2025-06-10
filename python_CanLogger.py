import sys
import subprocess

def check_dependencies():
    """Install required dependencies if they are missing."""
    required_packages = ["can", "signal", "threading"]
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            print(f"{package} not found. Installing...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Run the dependency check before starting the main script
check_dependencies()

import can
import threading
import signal
from datetime import datetime

def check_dependencies():
    """Install required dependencies if they are missing."""
    required_packages = ["python-can", "can", "signal"]
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            print(f"{package} not found. Installing...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Run the dependency check before starting the main script
check_dependencies()

# Set up the timestamp for log files
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# Define log file names with the timestamp
log_file_1 = f"CAN-FD2_log_{timestamp}.txt"
log_file_2 = f"CAN-FD14_log_{timestamp}.txt"

# Define CAN buses
bus_1 = can.interface.Bus(
    interface='vector',
    app_name='CANoe',
    channel=0,
    bitrate=500000,
    data_bitrate=2000000,
    fd=True,
    receive_own_messages=False
)

bus_2 = can.interface.Bus(
    interface='vector',
    app_name='CANoe',
    channel=1,
    bitrate=500000,
    data_bitrate=2000000,
    fd=True,
    receive_own_messages=False
)

# Event to stop threads
stop_event = threading.Event()

def listen_on_channel(bus, channel_name, log_file):
    """Function to passively log CAN messages to a file."""
    print(f"Listening on {channel_name} in logging-only mode... Press Ctrl+C to exit.")
    with open(log_file, 'a') as f:
        while not stop_event.is_set():
            message = bus.recv(timeout=1.0)
            if message:
                data_str = ' '.join(f"{byte:02X}" for byte in message.data)
                log_entry = f"ID: {hex(message.arbitration_id)}, DLC: {message.dlc}, Data: {data_str}\n"
                f.write(log_entry)
        print(f"\nStopping listener on {channel_name}. Log saved to {log_file}.")
    bus.shutdown()

# Signal handler for graceful shutdown on Ctrl+C
def signal_handler(sig, frame):
    print("\nStopping all listeners...")
    stop_event.set()

# Bind the signal handler for Ctrl+C
signal.signal(signal.SIGINT, signal_handler)

# Create and start threads for each channel, passing log files
thread_1 = threading.Thread(target=listen_on_channel, args=(bus_1, "CAN-FD2", log_file_1))
thread_2 = threading.Thread(target=listen_on_channel, args=(bus_2, "CAN-FD14", log_file_2))

thread_1.start()
thread_2.start()

# Wait for threads to complete
thread_1.join()
thread_2.join()

print("All listeners stopped. Logs saved.")
