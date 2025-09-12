import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext
from tkinter import messagebox
import can
import threading
import queue
import time
import binascii
import sys
import logging # Import the logging module
import os # To get current directory easily

# --- Global Variables/Constants ---
LOG_FILENAME = "can_log.txt"

class SimpleCanToolGUI:
    def __init__(self, master):
        self.master = master
        master.title("Simple CAN Tool GUI (with Logging)")
        master.geometry("750x650") # Increased height slightly for log info

        # --- Setup Logging ---
        self.setup_logging() # Call logging setup early

        # --- Instance Variables ---
        self.bus = None
        self.rx_thread = None
        self.rx_queue = queue.Queue()
        self.stop_rx_flag = threading.Event()
        self.is_connected = False

        # --- Style ---
        self.style = ttk.Style()
        try:
            self.style.theme_use('vista')
        except tk.TclError:
            logging.warning("Vista theme not available, using default.")

        # --- Frames ---
        connection_frame = ttk.LabelFrame(master, text="Connection Settings", padding=(10, 5))
        connection_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        tx_frame = ttk.LabelFrame(master, text="Transmit Message", padding=(10, 5))
        tx_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        rx_frame = ttk.LabelFrame(master, text="Received/Sent Messages (Live View)", padding=(10, 5))
        rx_frame.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")

        status_frame = ttk.Frame(master, padding=(10, 5))
        status_frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

        # Configure grid expansion
        master.columnconfigure(0, weight=1)
        master.rowconfigure(2, weight=1) # Allow RX frame to expand vertically

        # --- Connection Settings Widgets ---
        # (Identical to previous version - no changes needed here)
        ttk.Label(connection_frame, text="Interface:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.interface_var = tk.StringVar(value="virtual")
        self.interface_entry = ttk.Entry(connection_frame, textvariable=self.interface_var, width=15)
        self.interface_entry.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        ttk.Label(connection_frame, text="(e.g., pcan, vector, virtual)").grid(row=0, column=2, columnspan=3, padx=5, pady=2, sticky="w")

        ttk.Label(connection_frame, text="Channel:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.channel_var = tk.StringVar(value="vcan0")
        self.channel_entry = ttk.Entry(connection_frame, textvariable=self.channel_var, width=15)
        self.channel_entry.grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        ttk.Label(connection_frame, text="(e.g. 0, vcan0, COM3)").grid(row=1, column=2, columnspan=3, padx=5, pady=2, sticky="w")

        ttk.Label(connection_frame, text="Baudrate:").grid(row=2, column=0, padx=5, pady=2, sticky="w")
        self.baudrate_var = tk.StringVar(value="500000")
        self.baudrate_entry = ttk.Entry(connection_frame, textvariable=self.baudrate_var, width=10)
        self.baudrate_entry.grid(row=2, column=1, padx=5, pady=2, sticky="ew")

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

        connection_frame.columnconfigure(1, weight=1)
        connection_frame.columnconfigure(3, weight=1)

        self.connect_button = ttk.Button(connection_frame, text="Connect", command=self.connect_can)
        self.connect_button.grid(row=0, column=4, rowspan=2, padx=10, pady=5, sticky="ns")
        self.disconnect_button = ttk.Button(connection_frame, text="Disconnect", command=self.disconnect_can, state=tk.DISABLED)
        self.disconnect_button.grid(row=2, column=4, rowspan=2, padx=10, pady=5, sticky="ns")

        # --- TX Widgets ---
        # (Identical to previous version - no changes needed here)
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

        tx_frame.columnconfigure(1, weight=1)

        # --- RX Widgets ---
        # (Identical to previous version - no changes needed here)
        self.rx_text = scrolledtext.ScrolledText(rx_frame, wrap=tk.WORD, height=15, width=80, state=tk.DISABLED)
        self.rx_text.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

        # --- Status Bar ---
        # (Adding Log File Location Info)
        self.status_var = tk.StringVar(value="Status: Disconnected")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Add a label to show where the log file is
        log_file_path = os.path.abspath(LOG_FILENAME)
        self.log_file_label = ttk.Label(status_frame, text=f"Log: {log_file_path}", anchor=tk.E)
        self.log_file_label.pack(side=tk.RIGHT)


        # --- Start Queue Processor ---
        self.master.after(100, self.process_rx_queue)

        # --- Handle Window Closing ---
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Log application start
        logging.info("="*20 + " Application Started " + "="*20)


    def setup_logging(self):
        """Configures file logging."""
        log_formatter = logging.Formatter('%(asctime)s [%(levelname)-5.5s] %(message)s')
        root_logger = logging.getLogger()

        # Set overall logging level (can be changed to DEBUG, WARNING, etc.)
        root_logger.setLevel(logging.INFO)

        # File Handler
        file_handler = logging.FileHandler(LOG_FILENAME, mode='a') # Append mode
        file_handler.setFormatter(log_formatter)
        root_logger.addHandler(file_handler)

        # Optional: Console Handler (for debugging the script itself)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(log_formatter)
        root_logger.addHandler(console_handler)

        logging.info("Logging initialized.")

    def toggle_fd_options(self):
        """Enable/disable CAN FD specific options based on checkbox."""
        # (Identical to previous version)
        if self.fd_var.get():
            self.brs_check.config(state=tk.NORMAL)
            self.data_baudrate_label.config(state=tk.NORMAL)
            self.data_baudrate_entry.config(state=tk.NORMAL)
        else:
            self.brs_check.config(state=tk.DISABLED)
            self.data_baudrate_label.config(state=tk.DISABLED)
            self.data_baudrate_entry.config(state=tk.DISABLED)
            self.brs_var.set(False)

    def set_status(self, message, is_error=False):
        """Update the status bar."""
        # (Identical to previous version)
        self.status_var.set(f"Status: {message}")
        if is_error:
            self.status_label.config(foreground="red")
        else:
            self.status_label.config(foreground='')

    def log_message(self, message, level=logging.INFO):
        """Append a message to the RX text area AND log it to file."""
        # Log to file first
        if level == logging.ERROR:
            logging.error(message)
        elif level == logging.WARNING:
            logging.warning(message)
        else: # Default to INFO
            logging.info(message)

        # Update GUI
        try:
             # Check if master window still exists before updating GUI
            if self.master.winfo_exists():
                self.rx_text.config(state=tk.NORMAL)
                self.rx_text.insert(tk.END, message + "\n")
                self.rx_text.see(tk.END) # Auto-scroll
                self.rx_text.config(state=tk.DISABLED)
        except tk.TclError:
            # Handle cases where the window might be closing during logging
            pass
        except Exception as e:
             # Catch other potential GUI update errors during shutdown
            print(f"Error updating GUI log: {e}") # Print to console if GUI fails


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
            err_msg = "Invalid baudrate value. Must be an integer."
            self.set_status(err_msg, is_error=True)
            logging.error(err_msg)
            messagebox.showerror("Error", err_msg)
            return

        config = {
            'interface': interface,
            'channel': channel,
            'bitrate': baudrate,
            'fd': self.fd_var.get(),
        }
        log_config_str = f"Interface={interface}, Channel={channel}, Baudrate={baudrate}, FD={config['fd']}"

        if config['fd']:
            try:
                data_baudrate = int(self.data_baudrate_var.get())
                config['data_bitrate'] = data_baudrate
                config['br_switch'] = self.brs_var.get()
                log_config_str += f", DataRate={data_baudrate}, BRS={config['br_switch']}"
            except ValueError:
                err_msg = "Invalid data baudrate value. Must be an integer for FD."
                self.set_status(err_msg, is_error=True)
                logging.error(err_msg)
                messagebox.showerror("Error", err_msg)
                return

        try:
            self.set_status(f"Connecting ({interface}:{channel})...")
            self.master.update_idletasks()
            logging.info(f"Attempting CAN connection: {log_config_str}")

            # ***** Connect *****
            self.bus = can.Bus(**config)
            # *******************

            self.is_connected = True
            status_msg = f"Connected to {self.bus.channel_info}"
            self.set_status(status_msg)
            self.log_message(f"INFO: {status_msg}") # Log successful connection

            # Update GUI state (Enable/Disable buttons/fields)
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
            logging.error(f"CAN Connection Failed: {err_msg} (Config: {log_config_str})")
            messagebox.showerror("Connection Failed", f"{err_msg}\n\nPlease check hardware, drivers, interface, channel, and settings.")
        except ImportError as e:
             self.is_connected = False
             self.bus = None
             err_msg = f"Import Error: {e}. Library for '{interface}' not found?"
             self.set_status(err_msg, is_error=True)
             logging.error(f"Import Error during connection: {e} (Interface: {interface})")
             messagebox.showerror("Import Error", f"{err_msg}\n\nTry: pip install python-can[{interface}]")
        except Exception as e:
            self.is_connected = False
            self.bus = None
            err_msg = f"An unexpected error occurred during connection: {e}"
            self.set_status(err_msg, is_error=True)
            logging.exception("Unexpected connection error:") # Logs traceback
            messagebox.showerror("Error", err_msg)

    def disconnect_can(self):
        """Disconnect from the CAN bus."""
        if not self.is_connected:
            return # Already disconnected

        self.set_status("Disconnecting...")
        logging.info("Disconnect requested.")
        self.stop_rx_flag.set()

        # Shutdown bus BEFORE joining thread
        if self.bus:
            try:
                self.bus.shutdown()
                self.log_message("INFO: CAN bus shut down.")
            except Exception as e:
                # Log the error but continue disconnect process
                err_msg = f"Exception during bus shutdown: {e}"
                self.log_message(f"ERROR: {err_msg}", level=logging.ERROR)
                self.set_status(f"Error during shutdown: {e}", is_error=True)

        # Join thread AFTER shutdown attempt
        if self.rx_thread and self.rx_thread.is_alive():
            logging.debug("Waiting for RX thread to join...")
            self.rx_thread.join(timeout=1.0)
            if self.rx_thread.is_alive():
                 self.log_message("WARNING: RX thread did not terminate cleanly after shutdown.", level=logging.WARNING)
            else:
                 logging.debug("RX thread joined.")

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
        self.toggle_fd_options() # Re-enable based on checkbox state

        self.set_status("Disconnected")
        self.log_message("INFO: Disconnected.", level=logging.INFO) # Use log_message for consistency


    def rx_worker(self):
        """Worker thread for receiving CAN messages."""
        self.log_message("INFO: RX Thread Started.", level=logging.INFO)
        msg_count = 0
        try:
            while not self.stop_rx_flag.is_set():
                if self.bus:
                    # Receive with timeout to allow checking stop flag periodically
                    msg = self.bus.recv(timeout=0.2)
                    if msg:
                        msg_count += 1
                        self.rx_queue.put(msg) # Put message onto the queue for GUI thread
                        # Optional: Log directly here if high performance needed
                        # logging.debug(f"RX Raw: {msg}")
                else:
                    logging.warning("RX worker loop: Bus object is None.")
                    break # Exit loop if bus is gone
        except can.CanError as e:
            # Put error onto queue to display in GUI and log
            err_msg = f"ERROR (RX Thread CAN): {e}"
            self.rx_queue.put(err_msg) # Signal GUI
            logging.error(err_msg) # Log the error
        except Exception as e:
            err_msg = f"ERROR (RX Thread Unexpected): {e}"
            self.rx_queue.put(err_msg)
            logging.exception("Unexpected RX thread error:") # Log traceback
        finally:
            final_msg = f"INFO: RX Thread Stopped. Received {msg_count} messages."
            # Put final message onto queue for GUI
            self.rx_queue.put(final_msg)
            # Log directly as well
            logging.info(final_msg)


    def process_rx_queue(self):
        """Check the queue for messages/strings from RX thread and update GUI/log."""
        try:
            while True: # Process all items currently in the queue
                item = self.rx_queue.get_nowait()

                if isinstance(item, can.Message):
                    # Format CAN message string (same as before)
                    timestamp = f"{item.timestamp:.3f}"
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
                    # Use the unified log_message function
                    self.log_message(log_entry, level=logging.INFO)

                elif isinstance(item, str):
                    # Handle informational or error strings from the RX thread
                    if "ERROR" in item:
                        self.log_message(item, level=logging.ERROR)
                        self.set_status("Error occurred in RX thread", is_error=True)
                    elif "WARNING" in item:
                         self.log_message(item, level=logging.WARNING)
                    else: # Assume INFO
                         self.log_message(item, level=logging.INFO)

        except queue.Empty:
            pass # No messages in the queue right now
        except Exception as e:
             # Catch errors during queue processing itself
             logging.exception("Error processing RX queue:")
             self.log_message(f"ERROR: Could not process item from RX queue: {e}", level=logging.ERROR)


        # Reschedule self to run again ONLY if the window still exists
        if self.master.winfo_exists():
             self.master.after(100, self.process_rx_queue)

    def send_can_message(self):
        """Send a CAN message based on TX fields."""
        if not self.is_connected or not self.bus:
            messagebox.showerror("Error", "Not connected to CAN bus.")
            return

        tx_id_str = self.tx_id_var.get()
        tx_data_str = self.tx_data_var.get()
        is_extended = self.tx_extended_var.get()
        is_fd = self.fd_var.get()
        brs = self.brs_var.get() if is_fd else False
        payload = bytes() # Initialize payload

        try:
            # Validate and parse ID
            try:
                arbitration_id = int(tx_id_str, 16)
            except ValueError:
                raise ValueError(f"Invalid hex format for ID: '{tx_id_str}'")

            # Validate ID range
            if is_extended and arbitration_id > 0x1FFFFFFF:
                 raise ValueError("Extended ID exceeds 29 bits")
            if not is_extended and arbitration_id > 0x7FF:
                 raise ValueError("Standard ID exceeds 11 bits")

            # Validate and parse Data
            if tx_data_str:
                try:
                     payload = binascii.unhexlify(tx_data_str)
                except (binascii.Error, ValueError):
                     raise ValueError(f"Invalid hex format or odd length for Data: '{tx_data_str}'")

            # Validate DLC based on CAN standard / FD
            if not is_fd and len(payload) > 8:
                 raise ValueError(f"Data length ({len(payload)}) exceeds 8 bytes for standard CAN")
            if is_fd and len(payload) > 64:
                 raise ValueError(f"Data length ({len(payload)}) exceeds 64 bytes for CAN FD")

            # Create Message
            message = can.Message(
                arbitration_id=arbitration_id,
                data=payload,
                is_extended_id=is_extended,
                is_fd=is_fd,
                bitrate_switch=brs
                # timestamp=time.time() # Optional: add timestamp if needed by interface
            )

            # ***** Send Message *****
            self.bus.send(message)
            # ************************

            # Format log entry for TX (similar to RX)
            timestamp = f"{message.timestamp if message.timestamp else time.time():.3f}" # Use actual if available
            id_str = f"ID: {tx_id_str.upper().rjust(8 if is_extended else 3)}"
            flags = []
            if is_extended: flags.append("EXT")
            if is_fd: flags.append("FD")
            if brs: flags.append("BRS")
            flags_str = f" Flags:[{' '.join(flags)}]" if flags else ""
            dlc_str = f" DLC:{len(payload)}"
            data_str = f" Data: {tx_data_str.upper()}" if payload else ""
            log_entry = f"TX: {timestamp} {id_str}{dlc_str}{flags_str}{data_str}"

            # Log using the unified function
            self.log_message(log_entry, level=logging.INFO)
            self.set_status("Message sent successfully")

        except ValueError as e: # Catches specific validation errors
            err_msg = f"TX Error: Invalid input - {e}"
            self.set_status(err_msg, is_error=True)
            logging.error(err_msg) # Log the validation error
            messagebox.showerror("TX Error", err_msg)
        except can.CanError as e:
            err_msg = f"TX Error: Failed to send - {e}"
            self.set_status(err_msg, is_error=True)
            logging.error(f"{err_msg} (Message: ID={tx_id_str}, Data={tx_data_str})")
            messagebox.showerror("TX Error", err_msg)
        except Exception as e:
             err_msg = f"TX Error: An unexpected error occurred - {e}"
             self.set_status(err_msg, is_error=True)
             logging.exception("Unexpected TX error:") # Log traceback
             messagebox.showerror("TX Error", err_msg)


    def on_closing(self):
        """Handle window close event."""
        logging.info("Close requested.")
        if self.is_connected:
            if messagebox.askokcancel("Quit", "CAN bus is connected. Disconnect and quit?"):
                self.disconnect_can() # Disconnect first
                logging.info("Application closing after disconnect.")
                logging.shutdown() # Ensure log handlers are flushed/closed
                self.master.destroy()
            else:
                logging.info("Quit cancelled.")
                return # Don't close yet
        else:
            logging.info("Application closing.")
            logging.shutdown() # Ensure log handlers are flushed/closed
            self.master.destroy()


# --- Main Execution ---
if __name__ == "__main__":
    root = tk.Tk()
    app = SimpleCanToolGUI(root)
    root.mainloop()