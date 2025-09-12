import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import can
import cantools
import os
import threading
import time
from datetime import datetime
import serial
import serial.tools.list_ports
from queue import Queue
import json

class CANApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CAN Bus GUI Application")
        self.root.geometry("800x600")
        
        # CAN bus variables
        self.bus = None
        self.db = None
        self.log_file = None
        self.running = False
        self.rx_queue = Queue()
        
        # Serial variables
        self.serial_port = None
        
        # Saved commands
        self.saved_commands = {}
        self.commands_file = "saved_commands.json"
        self.load_saved_commands()
        
        # GUI Elements
        self.create_gui()
        
        # Start RX thread
        self.rx_thread = None
        self.update_log()
        
    def create_gui(self):
        # CAN Interface Selection
        tk.Label(self.root, text="CAN Interface:").grid(row=0, column=0, padx=5, pady=5)
        self.interface_var = tk.StringVar(value="socketcan")
        interfaces = ["socketcan", "pcan", "kvaser", "virtual"]
        tk.OptionMenu(self.root, self.interface_var, *interfaces).grid(row=0, column=1, padx=5, pady=5)
        
        tk.Label(self.root, text="Channel:").grid(row=0, column=2, padx=5, pady=5)
        self.channel_entry = tk.Entry(self.root)
        self.channel_entry.insert(0, "vcan0")
        self.channel_entry.grid(row=0, column=3, padx=5, pady=5)
        
        tk.Label(self.root, text="Bitrate:").grid(row=0, column=4, padx=5, pady=5)
        self.bitrate_entry = tk.Entry(self self.bitrate_entry.insert(0, "500000")
        self.bitrate_entry.grid(row=0, column=5, padx=5, pady=5)
        
        tk.Button(self.root, text="Connect CAN", command=self.connect_can).grid(row=0, column=6, padx=5, pady=5)
        tk.Button(self.root, text="Disconnect CAN", command=self.disconnect_can).grid(row=0, column=7, padx=5, pady=5)
        
        # Serial Interface
        tk.Label(self.root, text="Serial Port:").grid(row=1, column=0, padx=5, pady=5)
        self.serial_ports = [port.device for port in serial.tools.list_ports.comports()]
        self.serial_var = tk.StringVar(value=self.serial_ports[0] if self.serial_ports else "None")
        tk.OptionMenu(self.root, self.serial_var, *self.serial_ports).grid(row=1, column=1, padx=5, pady=5)
        
        tk.Button(self.root, text="Connect Serial", command=self.connect_serial).grid(row=1, column=2, padx=5, pady=5)
        tk.Button(self.root, text="Disconnect Serial", command=self.disconnect_serial).grid(row=1, column=3, padx=5, pady=5)
        
        # File Loader
        tk.Button(self.root, text="Load DBC/CDD", command=self.load_file).grid(row=2, column=0, columnspan=2, padx=5, pady=5)
        self.file_label = tk.Label(self.root, text="No file loaded")
        self.file_label.grid(row=2, column=2, columnspan=2, padx=5, pady=5)
        
        # Message Selection
        tk.Label(self.root, text="Select Message:").grid(row=3, column=0, padx=5, pady=5)
        self.message_var = tk.StringVar()
        self.message_menu = tk.OptionMenu(self.root, self.message_var, [])
        self.message_menu.grid(row=3, column=1, columnspan=2, padx=5, pady=5)
        self.message_var.trace("w", self.update_signal_inputs)
        
        # Signal Inputs
        self.signal_frame = tk.Frame(self.root)
        self.signal_frame.grid(row=4, column=0, columnspan=8, padx=5, pady=5)
        self.signal_entries = {}
        
        # Send Message
        tk.Button(self.root, text="Send Message", command=self.send_message).grid(row=5, column=0, columnspan=2, padx=5, pady=5)
        tk.Button(self.root, text="Save Command", command=self.save_command).grid(row=5, column=2, columnspan=2, padx=5, pady=5)
        
        # Saved Commands
        tk.Label(self.root, text="Saved Commands:").grid(row=6, column=0, padx=5, pady=5)
        self.command_var = tk.StringVar()
        self.command_menu = tk.OptionMenu(self.root, self.command_var, *self.saved_commands.keys())
        self.command_menu.grid(row=6, column=1, columnspan=2, padx=5, pady=5)
        tk.Button(self.root, text="Send Saved Command", command=self.send_saved_command).grid(row=6, column=3, columnspan=2, padx=5, pady=5)
        
        # Log Display
        self.log_text = tk.Text(self.root, height=15, width=80)
        self.log_text.grid(row=7, column=0, columnspan=8, padx=5, pady=5)
        
        # Start/Stop Logging
        tk.Button(self.root, text="Start Logging", command=self.start_logging).grid(row=8, column=0, columnspan=2, padx=5, pady=5)
        tk.Button(self.root, text="Stop Logging", command=self.stop_logging).grid(row=8, column=2, columnspan=2, padx=5, pady=5)
        
    def load_saved_commands(self):
        if os.path.exists(self.commands_file):
            with open(self.commands_file, 'r') as f:
                self.saved_commands = json.load(f)
                
    def save_commands_to_file(self):
        with open(self.commands_file, 'w') as f:
            json.dump(self.saved_commands, f, indent=4)
            
    def connect_can(self):
        try:
            interface = self.interface_var.get()
            channel = self.channel_entry.get()
            bitrate = int(self.bitrate_entry.get())
            self.bus = can.interface.Bus(channel=channel, bustype=interface, bitrate=bitrate)
            self.running = True
            self.rx_thread = threading.Thread(target=self.receive_messages, daemon=True)
            self.rx_thread.start()
            self.log_text.insert(tk.END, f"Connected to CAN bus: {interface} {channel}\n")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect to CAN bus: {str(e)}")
            
    def disconnect_can(self):
        self.running = False
        if self.bus:
            self.bus.shutdown()
            self.bus = None
            self.log_text.insert(tk.END, "Disconnected from CAN bus\n")
            
    def connect_serial(self):
        try:
            port = self.serial_var.get()
            self.serial_port = serial.Serial(port, baudrate=9600, timeout=1)
            self.log_text.insert(tk.END, f"Connected to serial port: {port}\n")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect to serial port: {str(e)}")
            
    def disconnect_serial(self):
        if self.serial_port:
            self.serial_port.close()
            self.serial_port = None
            self.log_text.insert(tk.END, "Disconnected from serial port\n")
            
    def load_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("DBC/CDD Files", "*.dbc *.cdd")])
        if file_path:
            try:
                self.db = cantools.database.load_file(file_path)
                self.file_label.config(text=os.path.basename(file_path))
                messages = [msg.name for msg in self.db.messages]
                self.message_menu['menu'].delete(0, 'end')
                for msg in messages:
                    self.message_menu['menu'].add_command(label=msg, command=lambda m=msg: self.message_var.set(m))
                self.log_text.insert(tk.END, f"Loaded file: {file_path}\n")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load file: {str(e)}")
                
    def update_signal_inputs(self, *args):
        for widget in self.signal_frame.winfo_children():
            widget.destroy()
        self.signal_entries = {}
        if self.db and self.message_var.get():
            message = self.db.get_message_by_name(self.message_var.get())
            row = 0
            for signal in message.signals:
                tk.Label(self.signal_frame, text=signal.name).grid(row=row, column=0, padx=5, pady=2)
                entry = tk.Entry(self.signal_frame)
                entry.grid(row=row, column=1, padx=5, pady=2)
                self.signal_entries[signal.name] = entry
                row += 1
                
    def send_message(self):
        if not self.bus or not self.db:
            messagebox.showwarning("Warning", "Connect to CAN bus and load a DBC/CDD file first")
            return
        try:
            message_name = self.message_var.get()
            message = self.db.get_message_by_name(message_name)
            data = {}
            for signal_name, entry in self.signal_entries.items():
                value = entry.get()
                try:
                    data[signal_name] = float(value) if '.' in value else int(value)
                except ValueError:
                    messagebox.showerror("Error", f"Invalid value for signal {signal_name}")
                    return
            can_msg = self.db.encode_message(message_name, data)
            msg = can.Message(arbitration_id=message.frame_id, data=can_msg, is_extended_id=message.is_extended_frame)
            self.bus.send(msg)
            self.log_text.insert(tk.END, f"TX: {message_name} ID: {hex(message.frame_id)} Data: {can_msg.hex()}\n")
            if self.log_file:
                self.log_file.write(f"{datetime.now()} TX: {message_name} ID: {hex(message.frame_id)} Data: {can_msg.hex()}\n")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send message: {str(e)}")
            
    def save_command(self):
        if not self.message_var.get():
            messagebox.showwarning("Warning", "Select a message to save")
            return
        command_name = tk.simpledialog.askstring("Command Name", "Enter command name:")
        if command_name:
            signals = {name: entry.get() for name, entry in self.signal_entries.items()}
            self.saved_commands[command_name] = {
                'message': self.message_var.get(),
                'signals': signals
            }
            self.save_commands_to_file()
            self.command_menu['menu'].delete(0, 'end')
            for cmd in self.saved_commands.keys():
                self.command_menu['menu'].add_command(label=cmd, command=lambda c=cmd: self.command_var.set(c))
            self.log_text.insert(tk.END, f"Saved command: {command_name}\n")
            
    def send_saved_command(self):
        if not self.bus or not self.db:
            messagebox.showwarning("Warning", "Connect to CAN bus and load a DBC/CDD file first")
            return
        command_name = self.command_var.get()
        if command_name in self.saved_commands:
            try:
                cmd = self.saved_commands[command_name]
                message = self.db.get_message_by_name(cmd['message'])
                data = {k: float(v) if '.' in v else int(v) for k, v in cmd['signals'].items()}
                can_msg = self.db.encode_message(cmd['message'], data)
                msg = can.Message(arbitration_id=message.frame_id, data=can_msg, is_extended_id=message.is_extended_frame)
                self.bus.send(msg)
                self.log_text.insert(tk.END, f"TX (Saved): {cmd['message']} ID: {hex(message.frame_id)} Data: {can_msg.hex()}\n")
                if self.log_file:
                    self.log_file.write(f"{datetime.now()} TX (Saved): {cmd['message']} ID: {hex(message.frame_id)} Data: {can_msg.hex()}\n")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to send saved command: {str(e)}")
                
    def receive_messages(self):
        while self.running and self.bus:
            try:
                msg = self.bus.recv(timeout=1.0)
                if msg:
                    self.rx_queue.put(msg)
            except Exception as e:
                self.log_text.insert(tk.END, f"RX Error: {str(e)}\n")
                
    def update_log(self):
        while not self.rx_queue.empty():
            msg = self.rx_queue.get()
            try:
                if self.db:
                    message = self.db.get_message_by_frame_id(msg.arbitration_id)
                    data = self.db.decode_message(message.name, msg.data)
                    log_entry = f"RX: {message.name} ID: {hex(msg.arbitration_id)} Data: {data}\n"
                else:
                    log_entry = f"RX: ID: {hex(msg.arbitration_id)} Data: {msg.data.hex()}\n"
                self.log_text.insert(tk.END, log_entry)
                if self.log_file:
                    self.log_file.write(f"{datetime.now()} {log_entry}")
                self.log_text.see(tk.END)
            except Exception as e:
                self.log_text.insert(tk.END, f"RX Decode Error: {str(e)}\n")
        self.root.after(100, self.update_log)
        
    def start_logging(self):
        if self.log_file:
            self.log_file.close()
        log_filename = f"can_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        self.log_file = open(log_filename, 'w')
        self.log_text.insert(tk.END, f"Started logging to {log_filename}\n")
        
    def stop_logging(self):
        if self.log_file:
            self.log_file.close()
            self.log_file = None
            self.log_text.insert(tk.END, "Stopped logging\n")

if __name__ == "__main__":
    root = tk.Tk()
    app = CANApp(root)
    root.mainloop()
