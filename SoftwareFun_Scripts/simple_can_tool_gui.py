import tkinter as tk
from tkinter import ttk  # Themed widgets
from tkinter import scrolledtext
from tkinter import messagebox
import can
import threading
import queue # For thread-safe communication
import time
import binascii
import sys

class SimpleCanToolGUI:
    def __init__(self, master):
        self.master = master
        master.title("Simple CAN Tool GUI")
        master.geometry("750x600") # Adjusted size

        self.bus = None
        self.rx_thread = None
        self.rx_queue = queue.Queue()
        self.stop_rx_flag = threading.Event()
        self.is_connected = False

        # --- Style ---
        self.style = ttk.Style()
        # Use 'clam', 'alt', 'default', or 'classic' depending on OS and preference
        # Some themes might look better on specific OSes
        try:
            self.style.theme_use('vista') # Good starting point for Windows
        except tk.TclError:
            print("Vista theme not available, using default.")
            # Fallback or choose another theme like 'clam' if needed


        # --- Frames ---
        connection_frame = ttk.LabelFrame(master, text="Connection Settings", padding=(10, 5))
        connection_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        tx_frame = ttk.LabelFrame(master, text="Transmit Message", padding=(10, 5))
        tx_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        rx_frame = ttk.LabelFrame(master, text="Received/Sent Messages", padding=(10, 5))
        rx_frame.grid(row=2, column=0, padx=10, pady=5, sticky="nsew") # Expand this frame

        status_frame = ttk.Frame(master, padding=(10, 5))
        status_frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

        # Configure grid expansion
        master.columnconfigure(0, weight=1)
        master.rowconfigure(2, weight=1) # Allow RX frame to expand vertically

        # --- Connection Settings Widgets ---
        ttk.Label(connection_frame, text="Interface:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.interface_var = tk.StringVar(value="virtual") # Default example
        self.interface_entry = ttk.Entry(connection_frame, textvariable=self.interface_var, width=15)
        self.interface_entry.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        ttk.Label(connection_frame, text="(e.g., pcan, vector, virtual)").grid(row=0, column=2, columnspan=3, padx=5, pady=2, sticky="w")

        ttk.Label(connection_frame, text="Channel:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.channel_var = tk.StringVar(value="vcan0") # Default example
        self.channel_entry = ttk.Entry(connection_frame, textvariable=self.channel_var, width=15)
        self.channel_entry.grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        ttk.Label(connection_frame, text="(e.g., PCAN_USBBUS1, 0, vcan0, COM3)").grid(row=1, column=2, columnspan=3, padx=5, pady=2, sticky="w")

        ttk.Label(connection_frame, text="Baudrate:").grid(row=2, column=0, padx=5, pady=2, sticky="w")
        self.baudrate_var = tk.StringVar(value="500000")
        self.baudrate_entry = ttk.Entry(connection_frame, textvariable=self.baudrate_var, width=10)
        self.baudrate_entry.grid(row=2, column=1, padx=5, pady=2, sticky="ew")

        # CAN FD Options
        self.fd_var = tk.BooleanVar(value=False)
        self.fd_check = ttk.Checkbutton(connection_frame, text="CAN FD", variable=self.fd_var, command=self.toggle_fd_options)
        self.fd_check.grid(row=3, column=0, padx=5, pady=2, sticky="w")

        self.brs_var = tk.BooleanVar(value=False)
        self.brs_check = ttk.Checkbutton(connection_frame, text="Bitrate Switch", variable=self.brs_var, state=tk.DISABLED)
        self.brs_check.grid(row=3, column=1, padx=5, pady=2, sticky="w")

        self.data_baudrate_label = ttk.Label(connection_frame, text="Data Baudrate:", state=tk.DISABLED)
        self.data_baudrate_label.grid(row=3, column=2, padx=5, pady=2, sticky="w")
        self.data_baudrate_var = tk.StringVar(value="2000000")
        self.data_baudrate_entry = ttk.Entry(connection_frame, textvariable=self.data_baudrate_var, width=10, state=tk.DISABLED)
        self.data_baudrate_entry.grid(row=3, column=3, padx=5, pady=2, sticky="ew")

        connection_frame.columnconfigure(1, weight=1) # Allow entry fields to expand a bit
        connection_frame.columnconfigure(3, weight=1)

        # Connect/Disconnect Button
        self.connect_button = ttk.Button(connection_frame, text="Connect", command=self.connect_can)
        self.connect_button.grid(row=0, column=4, rowspan=2, padx=10, pady=5, sticky="ns")
        self.disconnect_button = ttk.Button(connection_frame, text="Disconnect", command=self.disconnect_can, state=tk.DISABLED)
        self.disconnect_button.grid(row=2, column=4, rowspan=2, padx=10, pady=5, sticky="ns")


        # --- TX Widgets ---
        ttk.Label(tx_frame, text="ID (Hex):").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.tx_id_var = tk.StringVar(value="100")
        self.tx_id_entry = ttk.Entry(tx_frame, textvariable=self.tx_id_var, width=10)
        self.tx_id_entry.grid(row=0, column=1, padx=5, pady=2, sticky="ew")

        self.tx_extended_var = tk.BooleanVar(value=False)
        self.tx_extended_check = ttk.Checkbutton(tx_frame, text="Extended ID", variable=self.tx_extended_var)
        self.tx_extended_check.grid(row=0, column=2, padx=5, pady=2, sticky="w")

        ttk.Label(tx_frame, text="Data (Hex):").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.tx_data_var = tk.StringVar(value="01020304")
        self.tx_data_entry = ttk.Entry(tx_frame, textvariable=self.tx_data_var, width=30)
        self.tx_data_entry.grid(row=1, column=1, columnspan=3, padx=5, pady=2, sticky="ew")

        self.send_button = ttk.Button(tx_frame, text="Send", command=self.send_can_message, state=tk.DISABLED)
        self.send_button.grid(row=0, column=4, rowspan=2, padx=10, pady=5, sticky="ns")

        tx_frame.columnconfigure(1, weight=1) # Allow data entry to expand


        # --- RX Widgets ---
        self.rx_text = scrolledtext.ScrolledText(rx_frame, wrap=tk.WORD, height=15, width=80, state=tk.DISABLED)
        self.rx_text.pack(padx=5, pady=5, fill=tk.BOTH, expand=True) # Use pack within its frame


        # --- Status Bar ---
        self.status_var = tk.StringVar(value="Status: Disconnected")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, anchor=tk.W)
        self.status_label.pack(fill=tk.X, expand=True)

        # --- Start Queue Processor ---
        self.master.after(100, self.process_rx_queue) # Check queue every 100ms

        # --- Handle Window Closing ---
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)


    def toggle_fd_options(self):
        """Enable/disable CAN FD specific options based on checkbox."""
        if self.fd_var.get():
            self.brs_check.config(state=tk.NORMAL)
            self.data_baudrate_label.config(state=tk.NORMAL)
            self.data_baudrate_entry.config(state=tk.NORMAL)
        else:
            self.brs_check.config(state=tk.DISABLED)
            self.data_baudrate_label.config(state=tk.DISABLED)
            self.data_baudrate_entry.config(state=tk.DISABLED)
            # Ensure BRS is off if FD is off
            self.brs_var.set(False)


    def set_status(self, message, is_error=False):
        """Update the status bar."""
        self.status_var.set(f"Status: {message}")
        if is_error:
            self.status_label.config(foreground="red")
        else:
             # Reset to default color (might need adjustment based on theme)
             # Using foreground='' often resets to the theme's default.
            self.status_label.config(foreground='')

    def log_message(self, message):
        """Append a message to the RX text area."""
        self.rx_text.config(state=tk.NORMAL)
        self.rx_text.insert(tk.END, message + "\n")
        self.rx_text.see(tk.END) # Auto-scroll
        self.rx_text.config(state=tk.DISABLED)

    def connect_can(self):
        """Attempt to connect to the CAN bus."""
        if self.is_connected:
            messagebox.showwarning("Connect", "Already connected.")
            return

        interface = self.interface_var.get()
        channel = self.channel_var.get()
        try:
            baudrate = int(self.baudrate_var.get())
        except ValueError:
            self.set_status("Invalid baudrate value.", is_error=True)
            messagebox.showerror("Error", "Baudrate must be an integer.")
            return

        config = {
            'interface': interface,
            'channel': channel,
            'bitrate': baudrate,
            'fd': self.fd_var.get(),
        }
        if config['fd']:
            try:
                config['data_bitrate'] = int(self.data_baudrate_var.get())
            except ValueError:
                self.set_status("Invalid data baudrate value.", is_error=True)
                messagebox.showerror("Error", "Data Baudrate must be an integer for FD.")
                return
            config['br_switch'] = self.brs_var.get()

        try:
            self.set_status(f"Connecting to {interface}:{channel}...")
            self.master.update_idletasks() # Update GUI to show status

            self.bus = can.Bus(**config)
            self.is_connected = True
            self.set_status(f"Connected to {self.bus.channel_info}")
            self.log_message(f"INFO: Connected to {self.bus.channel_info}")

            # Update GUI state
            self.connect_button.config(state=tk.DISABLED)
            self.disconnect_button.config(state=tk.NORMAL)
            self.send_button.config(state=tk.NORMAL)
            self.interface_entry.config(state=tk.DISABLED)
            self.channel_entry.config(state=tk.DISABLED)
            self.baudrate_entry.config(state=tk.DISABLED)
            self.fd_check.config(state=tk.DISABLED)
            self.brs_check.config(state=tk.DISABLED)
            self.data_baudrate_entry.config(state=tk.DISABLED)
            self.data_baudrate_label.config(state=tk.DISABLED)


            # Start RX thread
            self.stop_rx_flag.clear()
            self.rx_thread = threading.Thread(target=self.rx_worker, daemon=True)
            self.rx_thread.start()

        except can.CanError as e:
            self.is_connected = False
            self.bus = None
            err_msg = f"Error connecting: {e}"
            self.set_status(err_msg, is_error=True)
            messagebox.showerror("Connection Failed", f"{err_msg}\n\nPlease check hardware, drivers, interface, channel, and settings.")
        except ImportError as e:
             self.is_connected = False
             self.bus = None
             err_msg = f"Import Error: {e}. Library for '{interface}' not found?"
             self.set_status(err_msg, is_error=True)
             messagebox.showerror("Import Error", f"{err_msg}\n\nTry: pip install python-can[{interface}]")
        except Exception as e:
            self.is_connected = False
            self.bus = None
            err_msg = f"An unexpected error occurred: {e}"
            self.set_status(err_msg, is_error=True)
            messagebox.showerror("Error", err_msg)


    def disconnect_can(self):
        """Disconnect from the CAN bus."""
        if not self.is_connected or not self.bus:
            # messagebox.showwarning("Disconnect", "Not connected.")
            return # Already disconnected or never connected

        self.set_status("Disconnecting...")
        self.stop_rx_flag.set() # Signal thread to stop

        # Wait briefly for the thread to notice the flag
        # Don't join here directly, as bus.shutdown might be needed first
        # and join can block the GUI if the thread is stuck on recv()

        try:
            # Attempt to shutdown the bus first
            self.bus.shutdown()
            self.log_message("INFO: CAN bus shut down.")
        except Exception as e:
            self.log_message(f"ERROR: Exception during bus shutdown: {e}")
            self.set_status(f"Error during shutdown: {e}", is_error=True)
            # Continue cleanup even if shutdown fails

        # Now try joining the thread
        if self.rx_thread and self.rx_thread.is_alive():
            self.rx_thread.join(timeout=1.0) # Wait max 1 sec
            if self.rx_thread.is_alive():
                 self.log_message("WARNING: RX thread did not terminate cleanly.")


        self.bus = None
        self.is_connected = False
        self.rx_thread = None


        # Update GUI state
        self.connect_button.config(state=tk.NORMAL)
        self.disconnect_button.config(state=tk.DISABLED)
        self.send_button.config(state=tk.DISABLED)
        self.interface_entry.config(state=tk.NORMAL)
        self.channel_entry.config(state=tk.NORMAL)
        self.baudrate_entry.config(state=tk.NORMAL)
        self.fd_check.config(state=tk.NORMAL)
        # Re-enable FD options based on checkbox state
        self.toggle_fd_options()

        self.set_status("Disconnected")
        self.log_message("INFO: Disconnected.")

    def rx_worker(self):
        """Worker thread for receiving CAN messages."""
        self.log_message("INFO: RX Thread Started.")
        try:
            while not self.stop_rx_flag.is_set():
                if self.bus:
                    msg = self.bus.recv(timeout=0.2) # Timeout allows checking stop flag
                    if msg:
                        self.rx_queue.put(msg) # Put received message onto the queue
                else:
                    # Bus object might have been destroyed during disconnect
                    break
                # Small sleep if needed to reduce CPU if recv timeout is very low
                # time.sleep(0.001)
        except can.CanError as e:
             # Put error onto queue to display in GUI
            self.rx_queue.put(f"ERROR (RX Thread): {e}")
        except Exception as e:
            self.rx_queue.put(f"ERROR (RX Thread Unexpected): {e}")
        finally:
             # Signal final message or potentially handle reconnect logic if desired
             self.rx_queue.put("INFO: RX Thread Stopped.")


    def process_rx_queue(self):
        """Check the queue for messages from the RX thread and update GUI."""
        try:
            while True: # Process all messages currently in the queue
                item = self.rx_queue.get_nowait()
                if isinstance(item, can.Message):
                    # Format CAN message
                    timestamp = f"{item.timestamp:.3f}" # Reduced precision for GUI
                    id_hex = f"{item.arbitration_id:X}"
                    id_str = f"ID: {id_hex.rjust(8 if item.is_extended_id else 3)}"
                    flags = []
                    if item.is_extended_id: flags.append("EXT")
                    if item.is_remote_frame: flags.append("RTR")
                    if item.is_error_frame: flags.append("ERR")
                    if item.is_fd: flags.append("FD")
                    if item.bitrate_switch: flags.append("BRS")
                    if item.error_state_indicator: flags.append("ESI")
                    flags_str = f" Flags:[{' '.join(flags)}]" if flags else ""
                    dlc_str = f" DLC:{item.dlc}"
                    data_str = f" Data: {item.data.hex().upper()}" if not item.is_remote_frame and item.dlc > 0 else ""

                    log_entry = f"RX: {timestamp} {id_str}{dlc_str}{flags_str}{data_str}"
                    self.log_message(log_entry)
                elif isinstance(item, str):
                    # Log informational or error strings from the thread
                     self.log_message(item)
                     if "ERROR" in item:
                         self.set_status("Error occurred in RX thread", is_error=True)

        except queue.Empty:
            pass # No messages in the queue right now

        # Reschedule self to run again
        self.master.after(100, self.process_rx_queue)

    def send_can_message(self):
        """Send a CAN message based on TX fields."""
        if not self.is_connected or not self.bus:
            messagebox.showerror("Error", "Not connected to CAN bus.")
            return

        try:
            tx_id_str = self.tx_id_var.get()
            tx_data_str = self.tx_data_var.get()
            arbitration_id = int(tx_id_str, 16)
            is_extended = self.tx_extended_var.get()

            # Validate ID range
            if is_extended and arbitration_id > 0x1FFFFFFF:
                 raise ValueError("Extended ID exceeds 29 bits")
            if not is_extended and arbitration_id > 0x7FF:
                 raise ValueError("Standard ID exceeds 11 bits")

            # Allow empty data field for DLC=0
            if tx_data_str:
                 payload = binascii.unhexlify(tx_data_str)
            else:
                 payload = bytes()

            is_fd = self.fd_var.get()
            brs = self.brs_var.get() if is_fd else False

            # Validate DLC based on CAN standard / FD
            if not is_fd and len(payload) > 8:
                 raise ValueError("Data length exceeds 8 bytes for standard CAN")
            if is_fd and len(payload) > 64:
                 raise ValueError("Data length exceeds 64 bytes for CAN FD")


            message = can.Message(
                arbitration_id=arbitration_id,
                data=payload,
                is_extended_id=is_extended,
                is_fd=is_fd,
                bitrate_switch=brs
            )

            self.bus.send(message)
            # Log the sent message
            timestamp = f"{time.time():.3f}" # Approximate timestamp
            id_str = f"ID: {tx_id_str.upper().rjust(8 if is_extended else 3)}"
            flags = []
            if is_extended: flags.append("EXT")
            if is_fd: flags.append("FD")
            if brs: flags.append("BRS")
            flags_str = f" Flags:[{' '.join(flags)}]" if flags else ""
            dlc_str = f" DLC:{len(payload)}"
            data_str = f" Data: {tx_data_str.upper()}" if payload else ""
            log_entry = f"TX: {timestamp} {id_str}{dlc_str}{flags_str}{data_str}"
            self.log_message(log_entry)
            self.set_status("Message sent successfully")

        except ValueError as e:
            self.set_status(f"TX Error: Invalid input - {e}", is_error=True)
            messagebox.showerror("TX Error", f"Invalid input: {e}")
        except binascii.Error:
             err_msg = "TX Error: Invalid hex characters or odd length in Data field."
             self.set_status(err_msg, is_error=True)
             messagebox.showerror("TX Error", err_msg)
        except can.CanError as e:
            err_msg = f"TX Error: Failed to send - {e}"
            self.set_status(err_msg, is_error=True)
            messagebox.showerror("TX Error", err_msg)
        except Exception as e:
             err_msg = f"TX Error: An unexpected error occurred - {e}"
             self.set_status(err_msg, is_error=True)
             messagebox.showerror("TX Error", err_msg)


    def on_closing(self):
        """Handle window close event."""
        if self.is_connected:
            if messagebox.askokcancel("Quit", "CAN bus is connected. Disconnect and quit?"):
                self.disconnect_can()
                self.master.destroy()
            else:
                return # Don't close yet
        else:
            self.master.destroy()


# --- Main Execution ---
if __name__ == "__main__":
    root = tk.Tk()
    app = SimpleCanToolGUI(root)
    root.mainloop()