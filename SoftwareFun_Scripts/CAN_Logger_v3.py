import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, simpledialog
import can
import threading
import time
import json # For saving/loading DIDs
from queue import Queue # For thread-safe GUI updates

# --- Constants ---
LOG_FILE_NAME = "can_traffic_log.txt"
SAVED_DIDS_FILE = "saved_dids.json" # File to store saved DID commands
GUI_UPDATE_INTERVAL = 100 # Milliseconds to check for new CAN messages for GUI update

# --- Global Variables ---
can_bus = None
is_bus_active = False # True if CAN bus is connected and active
listener_thread = None # Thread for listening to CAN messages
stop_listener_event = threading.Event() # Event to signal the listener thread to stop
gui_queue = Queue() # Queue for messages from CAN thread to GUI thread

# --- CAN Core Functions ---

def log_to_file(log_entry_text):
    """Appends a log entry to the persistent text file."""
    try:
        with open(LOG_FILE_NAME, "a", encoding="utf-8") as f:
            f.write(log_entry_text + "\n")
    except Exception as e:
        # This print will go to console, not GUI.
        # Consider putting error messages into gui_queue for GUI display.
        print(f"Error writing to log file {LOG_FILE_NAME}: {e}")

def can_message_receiver_thread_func():
    """
    Listens for incoming CAN messages and puts them into the gui_queue.
    This function is designed to run in a separate thread.
    Filters can be applied here if needed, e.g., by ECU Response ID.
    """
    global can_bus, stop_listener_event, gui_queue
    if not can_bus:
        print("CAN bus not available for listener thread.")
        return

    print("CAN listener thread started.")
    try:
        # The `can_bus` object itself is iterable and will yield messages as they are received.
        for msg in can_bus:
            if stop_listener_event.is_set():
                break # Exit if stop event is set
            if msg: # If a message is received
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                # Check if it's an extended ID for formatting
                id_hex = f"{msg.arbitration_id:08X}" if msg.is_extended_id else f"{msg.arbitration_id:03X}"
                log_entry = f"{timestamp} | RX | ID: {id_hex} | DLC: {msg.dlc} | Data: {' '.join(f'{b:02X}' for b in msg.data)}"
                gui_queue.put(log_entry) # Add to queue for GUI update
                log_to_file(log_entry) # Also log RX to file immediately
        # If using a Notifier, it would be stopped here.
        # For an iterable bus, exiting the loop (due to stop_event or bus shutdown) is sufficient.
    except can.CanError as e:
        error_msg = f"CAN Read Error in listener: {e}"
        print(error_msg)
        gui_queue.put(error_msg)
    except Exception as e:
        error_msg = f"Listener thread encountered an unexpected exception: {e}"
        print(error_msg)
        gui_queue.put(error_msg)
    finally:
        print("CAN listener thread stopped.")

class CANInterfaceApp:
    def __init__(self, root_window):
        self.root = root_window
        self.root.title("Python CAN Utility")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing_application) # Handle window close button

        # Initialize StringVars for GUI elements
        self.can_interface_var = tk.StringVar(value="vector") # Default interface
        self.can_channel_var = tk.StringVar(value="0")       # Default channel
        self.can_bitrate_var = tk.StringVar(value="500000")  # Default bitrate
        self.ecu_req_id_var = tk.StringVar(value="18DAF2A0") # Default ECU Request ID
        self.ecu_resp_id_var = tk.StringVar(value="18DAA0F2")# Default ECU Response ID
        self.did_to_send_var = tk.StringVar(value="22 F180") # Default DID to send

        self.saved_commands = self.load_saved_commands() # Load previously saved commands
        self.selected_saved_command = tk.StringVar()

        self.setup_gui_layout() # Initialize the GUI layout
        self.periodic_gui_update() # Start the loop for updating GUI from queue

    def setup_gui_layout(self):
        # --- Configuration Frame ---
        config_frame = ttk.LabelFrame(self.root, text="CAN Configuration (Direct CAN)")
        config_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        ttk.Label(config_frame, text="Interface:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.interface_combo = ttk.Combobox(config_frame, textvariable=self.can_interface_var,
                                            values=["vector", "pcan", "kvaser", "socketcan", "serial", "virtual", "slcan"])
        self.interface_combo.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(config_frame, text="Channel:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.channel_entry = ttk.Entry(config_frame, textvariable=self.can_channel_var)
        self.channel_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(config_frame, text="Bitrate:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.bitrate_combo = ttk.Combobox(config_frame, textvariable=self.can_bitrate_var,
                                         values=["100000", "125000", "250000", "500000", "1000000"])
        self.bitrate_combo.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(config_frame, text="ECU Req ID (Hex):").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.req_id_entry = ttk.Entry(config_frame, textvariable=self.ecu_req_id_var)
        self.req_id_entry.grid(row=3, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(config_frame, text="ECU Resp ID (Hex):").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.resp_id_entry = ttk.Entry(config_frame, textvariable=self.ecu_resp_id_var)
        self.resp_id_entry.grid(row=4, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(config_frame, text="DID to Send (Hex):").grid(row=5, column=0, padx=5, pady=5, sticky="w")
        self.did_entry = ttk.Entry(config_frame, textvariable=self.did_to_send_var)
        self.did_entry.grid(row=5, column=1, padx=5, pady=5, sticky="ew")

        self.connect_button = ttk.Button(config_frame, text="Connect CAN", command=self.toggle_can_bus_connection)
        self.connect_button.grid(row=6, column=0, padx=5, pady=10, sticky="ew")

        self.send_did_button = ttk.Button(config_frame, text="Send DID & Monitor RX", command=self.send_did_over_can, state=tk.DISABLED)
        self.send_did_button.grid(row=6, column=1, padx=5, pady=10, sticky="ew")

        self.status_label = ttk.Label(config_frame, text="CAN: Disconnected", foreground="red", font=("Arial", 10, "bold"))
        self.status_label.grid(row=7, column=0, columnspan=2, padx=5, pady=5, sticky="w")

        config_frame.columnconfigure(1, weight=1) # Make entry fields expand

        # --- Saved Commands Frame ---
        saved_cmd_frame = ttk.LabelFrame(self.root, text="Saved Commands (DIDs/RIDs)")
        saved_cmd_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        self.saved_cmds_combobox = ttk.Combobox(saved_cmd_frame, textvariable=self.selected_saved_command,
                                                values=list(self.saved_commands.keys()), postcommand=self.refresh_saved_commands_dropdown,
                                                width=40)
        self.saved_cmds_combobox.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.saved_cmds_combobox.bind("<<ComboboxSelected>>", self.load_selected_command_details)

        self.save_current_cmd_button = ttk.Button(saved_cmd_frame, text="Save Current", command=self.save_current_command_config)
        self.save_current_cmd_button.grid(row=0, column=1, padx=5, pady=5)

        self.delete_saved_cmd_button = ttk.Button(saved_cmd_frame, text="Delete Selected", command=self.delete_selected_command)
        self.delete_saved_cmd_button.grid(row=0, column=2, padx=5, pady=5)
        saved_cmd_frame.columnconfigure(0, weight=1)


        # --- Output Monitoring Frame ---
        output_frame = ttk.LabelFrame(self.root, text="CAN Traffic Monitor")
        output_frame.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")

        self.output_text_area = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, height=20, width=100, state=tk.DISABLED)
        self.output_text_area.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

        self.copy_traffic_button = ttk.Button(output_frame, text="Copy All Traffic", command=self.copy_all_displayed_traffic)
        self.copy_traffic_button.pack(pady=5)

        # Configure grid resizing behavior
        self.root.columnconfigure(0, weight=1) # Allow main column to expand
        self.root.rowconfigure(2, weight=1)    # Allow output_frame (and thus text_area) to expand vertically


    def periodic_gui_update(self):
        """Processes messages from the gui_queue to update the ScrolledText widget safely."""
        try:
            while not gui_queue.empty():
                message = gui_queue.get_nowait()
                self.output_text_area.configure(state='normal') # Enable editing
                self.output_text_area.insert(tk.END, message + "\n")
                self.output_text_area.configure(state='disabled') # Disable editing
                self.output_text_area.see(tk.END) # Scroll to the latest message
        except Exception as e:
            print(f"Error updating GUI: {e}") # Should ideally not happen with queue
        finally:
            self.root.after(GUI_UPDATE_INTERVAL, self.periodic_gui_update) # Schedule next update

    def _set_config_fields_state(self, new_state):
        """Enable or disable CAN configuration fields."""
        self.interface_combo.config(state=new_state)
        self.channel_entry.config(state=new_state)
        self.bitrate_combo.config(state=new_state)
        # IDs and DID can remain editable, or be disabled too based on preference
        # self.req_id_entry.config(state=new_state)
        # self.resp_id_entry.config(state=new_state)
        # self.did_entry.config(state=new_state)

    def toggle_can_bus_connection(self):
        global is_bus_active, can_bus, listener_thread, stop_listener_event
        if not is_bus_active: # If currently disconnected, try to connect
            interface = self.can_interface_var.get()
            channel = self.can_channel_var.get()
            try:
                bitrate = int(self.can_bitrate_var.get())
            except ValueError:
                messagebox.showerror("Input Error", "Bitrate must be a valid integer.")
                return

            if not interface: # Channel can sometimes be optional depending on interface
                messagebox.showerror("Input Error", "CAN Interface cannot be empty.")
                return

            try:
                self.add_text_to_output_area(f"Attempting to connect to {interface} (Channel: {channel or 'default'}, Bitrate: {bitrate} bps)...")
                # Set receive_own_messages=False if you only want to see external messages
                # or if you explicitly log TX messages and don't want duplicates from the listener.
                can_bus = can.interface.Bus(bustype=interface, channel=channel, bitrate=bitrate, receive_own_messages=False)

                is_bus_active = True
                self.status_label.config(text="CAN: Connected", foreground="green")
                self.connect_button.config(text="Disconnect CAN")
                self.send_did_button.config(state=tk.NORMAL) # Enable Send button
                self._set_config_fields_state(tk.DISABLED) # Disable config fields

                stop_listener_event.clear() # Clear stop signal for new thread
                listener_thread = threading.Thread(target=can_message_receiver_thread_func, daemon=True)
                listener_thread.start()
                self.add_text_to_output_area("CAN connection successful. Listener started.")

            except Exception as e:
                is_bus_active = False # Ensure state is reset on failure
                can_bus = None # Clear bus object
                messagebox.showerror("CAN Connection Error", f"Failed to connect to CAN bus:\n{e}")
                self.status_label.config(text=f"CAN: Error - Connection Failed", foreground="red")
                self.add_text_to_output_area(f"CAN connection failed: {e}")
        else: # If currently connected, disconnect
            self.disconnect_active_can_bus()

    def disconnect_active_can_bus(self):
        global is_bus_active, can_bus, listener_thread, stop_listener_event
        self.add_text_to_output_area("Attempting to disconnect from CAN bus...")
        if listener_thread and listener_thread.is_alive():
            stop_listener_event.set() # Signal listener thread to stop
            listener_thread.join(timeout=2) # Wait for thread to finish
            if listener_thread.is_alive():
                self.add_text_to_output_area("Warning: CAN listener thread did not stop gracefully.")

        if can_bus:
            try:
                can_bus.shutdown()
                self.add_text_to_output_area("CAN bus hardware shut down.")
            except Exception as e:
                self.add_text_to_output_area(f"Error during CAN bus hardware shutdown: {e}")
        
        can_bus = None
        is_bus_active = False
        self.status_label.config(text="CAN: Disconnected", foreground="red")
        self.connect_button.config(text="Connect CAN")
        self.send_did_button.config(state=tk.DISABLED) # Disable Send button
        self._set_config_fields_state(tk.NORMAL) # Re-enable config fields
        self.add_text_to_output_area("CAN Disconnected.")


    def send_did_over_can(self):
        global can_bus
        if not is_bus_active or not can_bus:
            messagebox.showwarning("CAN Not Active", "Connect to CAN bus before sending a command.")
            return

        req_id_hex_str = self.ecu_req_id_var.get().strip()
        did_data_hex_str = self.did_to_send_var.get().strip()

        if not req_id_hex_str or not did_data_hex_str:
            messagebox.showerror("Input Error", "ECU Request ID and DID/Data to Send cannot be empty.")
            return

        try:
            # Validate and convert hex strings
            arbitration_id = int(req_id_hex_str, 16)
            data_bytes = bytes.fromhex(did_data_hex_str.replace(" ", "")) # Remove spaces before conversion
        except ValueError:
            messagebox.showerror("Hex Format Error", "Invalid Hexadecimal value for ID or DID/Data.")
            return

        # Determine if the ID is extended (common for UDS on CAN)
        # Standard CAN IDs are 11-bit (max 0x7FF or 2047).
        # Extended CAN IDs are 29-bit. IDs like "18DAF2A0" are clearly extended.
        is_extended_format = arbitration_id > 0x7FF

        msg_to_send = can.Message(
            arbitration_id=arbitration_id,
            data=data_bytes,
            is_extended_id=is_extended_format,
            dlc=len(data_bytes) # Data Length Code
        )

        try:
            can_bus.send(msg_to_send)
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            id_hex_display = f"{msg_to_send.arbitration_id:08X}" if msg_to_send.is_extended_id else f"{msg_to_send.arbitration_id:03X}"
            log_entry = f"{timestamp} | TX | ID: {id_hex_display} | DLC: {msg_to_send.dlc} | Data: {' '.join(f'{b:02X}' for b in msg_to_send.data)}"
            
            gui_queue.put(log_entry) # Add to queue for GUI display
            log_to_file(log_entry) # Log TX to file immediately
        except can.CanError as e:
            messagebox.showerror("CAN Send Error", f"Error sending CAN message: {e}")
            self.add_text_to_output_area(f"TX Error: {e}")
        except Exception as e:
            messagebox.showerror("Unexpected Send Error", f"An unexpected error occurred during send: {e}")
            self.add_text_to_output_area(f"TX Error (Unexpected): {e}")

    def add_text_to_output_area(self, text_to_add):
        """Appends text directly to the output ScrolledText widget (use for GUI-thread messages)."""
        self.output_text_area.configure(state='normal')
        self.output_text_area.insert(tk.END, text_to_add + "\n")
        self.output_text_area.configure(state='disabled')
        self.output_text_area.see(tk.END)

    def copy_all_displayed_traffic(self):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.output_text_area.get(1.0, tk.END))
            messagebox.showinfo("Clipboard", "All traffic from monitor copied to clipboard.")
        except Exception as e:
            messagebox.showerror("Clipboard Error", f"Could not copy to clipboard: {e}")

    def load_saved_commands(self):
        try:
            with open(SAVED_DIDS_FILE, 'r', encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {} # Return an empty dict if file doesn't exist
        except json.JSONDecodeError:
            messagebox.showerror("File Error", f"Error decoding {SAVED_DIDS_FILE}. Starting with an empty command list.")
            return {}

    def persist_saved_commands(self):
        try:
            with open(SAVED_DIDS_FILE, 'w', encoding="utf-8") as f:
                json.dump(self.saved_commands, f, indent=4)
        except Exception as e:
            messagebox.showerror("File Save Error", f"Could not save commands to {SAVED_DIDS_FILE}: {e}")

    def save_current_command_config(self):
        current_did_value = self.did_to_send_var.get().strip()
        current_req_id = self.ecu_req_id_var.get().strip()
        current_resp_id = self.ecu_resp_id_var.get().strip()

        if not current_did_value or not current_req_id:
            messagebox.showwarning("Input Incomplete", "ECU Request ID and DID to Send fields must be filled to save a command.")
            return

        # Prompt user for a name for this command
        command_name = simpledialog.askstring("Save Command", "Enter a name for this command:", parent=self.root,
                                              initialvalue=f"Req:{current_req_id} DID:{current_did_value[:10]}")
        if command_name: # If user provided a name (didn't cancel)
            if command_name in self.saved_commands:
                if not messagebox.askyesno("Overwrite Confirmation", f"Command '{command_name}' already exists. Overwrite?"):
                    return
            self.saved_commands[command_name] = {
                "req_id": current_req_id,
                "resp_id": current_resp_id,
                "did_data": current_did_value
            }
            self.persist_saved_commands()
            self.refresh_saved_commands_dropdown()
            self.selected_saved_command.set(command_name) # Select the newly saved command
            messagebox.showinfo("Command Saved", f"Command '{command_name}' has been saved.")


    def refresh_saved_commands_dropdown(self):
        """Updates the Combobox with the current list of saved command names."""
        sorted_command_names = sorted(list(self.saved_commands.keys()))
        self.saved_cmds_combobox['values'] = sorted_command_names


    def load_selected_command_details(self, event=None): # event is passed by ComboboxSelected binding
        selected_name = self.selected_saved_command.get()
        if selected_name in self.saved_commands:
            command_details = self.saved_commands[selected_name]
            self.ecu_req_id_var.set(command_details.get("req_id", ""))
            self.ecu_resp_id_var.set(command_details.get("resp_id", ""))
            self.did_to_send_var.set(command_details.get("did_data", ""))
            self.add_text_to_output_area(f"Loaded saved command: {selected_name}")


    def delete_selected_command(self):
        selected_name = self.selected_saved_command.get()
        if not selected_name:
            messagebox.showwarning("Selection Missing", "No saved command selected to delete.")
            return
        if selected_name in self.saved_commands:
            if messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete the command '{selected_name}'?"):
                del self.saved_commands[selected_name]
                self.persist_saved_commands()
                self.selected_saved_command.set("") # Clear selection
                self.ecu_req_id_var.set("") # Optionally clear fields
                self.ecu_resp_id_var.set("")
                self.did_to_send_var.set("")
                self.refresh_saved_commands_dropdown()
                self.add_text_to_output_area(f"Deleted saved command: {selected_name}")
        else:
            messagebox.showwarning("Command Not Found", f"Command '{selected_name}' not found in the saved list.")

    def on_closing_application(self):
        """Handles window close event (e.g., clicking the 'X' button)."""
        if is_bus_active: # If CAN bus is currently active
            if messagebox.askyesno("Exit Confirmation", "CAN bus is currently active. Disconnect before exiting?"):
                self.disconnect_active_can_bus()
            else:
                # If user chooses not to disconnect gracefully, still attempt a quick cleanup.
                global stop_listener_event, can_bus
                stop_listener_event.set() # Signal listener thread to stop
                if can_bus:
                    try:
                        can_bus.shutdown() # Attempt to shut down the bus interface
                    except Exception:
                        pass # Ignore errors during forced exit
        self.root.destroy() # Close the Tkinter window


if __name__ == "__main__":
    main_app_window = tk.Tk()
    app_instance = CANInterfaceApp(main_app_window)
    main_app_window.mainloop()