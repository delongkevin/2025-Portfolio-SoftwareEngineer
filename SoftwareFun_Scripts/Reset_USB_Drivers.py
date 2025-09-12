import subprocess
import json
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys

CONFIG_FILE = "usb_reset_config.json"
LOG_FILE = "usb_reset_log.txt"
ICON_FILE = "magna_icon.ico"

# Check dependencies and install if missing
def install_dependencies():
    for package in ["pyserial", "wmi"]:
        try:
            __import__(package)
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

install_dependencies()

import serial.tools.list_ports
import wmi

# Load saved configuration
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

# Save configuration
def save_config(data):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# Logging functionality
def log_result(message):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(LOG_FILE, 'a') as log:
        log.write(f"[{timestamp}] {message}\n")

# Reset Methods
def reset_with_devcon(hardware_id, devcon_path):
    try:
        subprocess.check_call([devcon_path, 'disable', hardware_id], shell=True)
        time.sleep(3)
        subprocess.check_call([devcon_path, 'enable', hardware_id], shell=True)
        log_result(f"DevCon reset successful for {hardware_id}")
        return True
    except Exception as e:
        log_result(f"DevCon reset failed: {e}")
        return False

def reset_with_pyserial(port_name):
    try:
        ser = serial.Serial(port_name)
        ser.close()
        time.sleep(2)
        ser.open()
        ser.close()
        log_result(f"PySerial reset successful for {port_name}")
        return True
    except Exception as e:
        log_result(f"PySerial reset failed: {e}")
        return False

def reset_with_wmi(device_id):
    try:
        subprocess.run(['pnputil', '/disable-device', device_id], shell=True)
        time.sleep(3)
        subprocess.run(['pnputil', '/enable-device', device_id], shell=True)
        log_result(f"WMI reset successful for {device_id}")
        return True
    except Exception as e:
        log_result(f"WMI reset failed: {e}")
        return False

# GUI App
class USBResetGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Advanced USB Port Reset Utility")
        self.geometry("750x500")
        self.configure(bg="#f0f4f8")

        if os.path.exists(ICON_FILE):
            self.iconbitmap(ICON_FILE)

        self.config_data = load_config()

        self.create_widgets()

    def create_widgets(self):
        frame = ttk.LabelFrame(self, text="Device Manager USB Devices", padding=(10, 10))
        frame.pack(padx=15, pady=15, fill='both', expand=True)

        self.tree = ttk.Treeview(frame)
        self.tree.pack(fill='both', expand=True, padx=10, pady=10)
        self.populate_tree()

        method_frame = ttk.LabelFrame(self, text="Reset Method", padding=(10, 10))
        method_frame.pack(padx=15, pady=10, fill='x', expand=True)

        self.method_var = tk.StringVar(value=self.config_data.get('method', 'DevCon'))
        ttk.Radiobutton(method_frame, text="DevCon (Recommended)", variable=self.method_var, value='DevCon').pack(anchor='w', padx=10, pady=2)
        ttk.Radiobutton(method_frame, text="WMI", variable=self.method_var, value='WMI').pack(anchor='w', padx=10, pady=2)
        ttk.Radiobutton(method_frame, text="PySerial (COM Ports Only)", variable=self.method_var, value='PySerial').pack(anchor='w', padx=10, pady=2)

        button_frame = ttk.Frame(self)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Refresh Devices", command=self.populate_tree).pack(side='left', padx=10)
        ttk.Button(button_frame, text="Start Reset", command=self.start_reset).pack(side='left', padx=10)

    def populate_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        c = wmi.WMI()
        categories = {}

        for device in c.Win32_PnPEntity():
            category = device.PNPClass or "Other Devices"
            if category not in categories:
                categories[category] = self.tree.insert('', 'end', text=category, open=True)
            self.tree.insert(categories[category], 'end', text=f"{device.Name}", values=(device.DeviceID,))

    def start_reset(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showerror("Error", "Please select a device to reset.")
            return

        device_id = self.tree.item(selected_item, 'values')[0]
        method = self.method_var.get()

        if method == "DevCon":
            devcon_path = filedialog.askopenfilename(title="Select DevCon.exe", filetypes=[("Executable", "*.exe")])
            result = reset_with_devcon(device_id, devcon_path)
        elif method == "WMI":
            result = reset_with_wmi(device_id)
        elif method == "PySerial":
            result = reset_with_pyserial(device_id)
        else:
            messagebox.showerror("Error", "Invalid method selected.")
            return

        save_config({"method": method, "device_id": device_id})

        if result:
            messagebox.showinfo("Success", "Device reset successfully.")
        else:
            messagebox.showerror("Failure", "Failed to reset device.")

# CLI Integration
def run_cli():
    config = load_config()
    device_id = config.get('device_id')
    method = config.get('method')

    if method == "DevCon":
        devcon_path = config.get('devcon_path')
        reset_with_devcon(device_id, devcon_path)
    elif method == "WMI":
        reset_with_wmi(device_id)
    elif method == "PySerial":
        reset_with_pyserial(device_id)

# Main
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "cli":
        run_cli()
    else:
        app = USBResetGUI()
        app.mainloop()