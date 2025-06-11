import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext, filedialog
import threading
import time
import os
import sys
import subprocess
import queue # For thread communication
from datetime import datetime
from pathlib import Path
import binascii
import shutil
import traceback # For detailed error logging
import re # For parsing DIDs from text
import json
import xml.etree.ElementTree as ET

# --- Dependency Checks (with automatic installation) ---
try:
    import pyautogui
except ImportError:
    if messagebox.askyesno("Dependency Missing", "The 'pyautogui' library is missing. Would you like to attempt to install it now?"):
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyautogui"])
            import pyautogui
        except Exception as e:
            messagebox.showerror("Installation Failed", f"Failed to install pyautogui. Please run 'pip install pyautogui' manually.\n\nError: {e}")
            sys.exit(1)
    else:
        messagebox.showerror("Prerequisite Missing", "pyautogui is required for this script to function. Exiting.")
        sys.exit(1)
try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None
    if messagebox.askyesno("Dependency Missing", "The 'pyserial' library is missing. Power supply features will be disabled unless it is installed.\n\nWould you like to attempt to install it now?"):
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyserial"])
            import serial
            import serial.tools.list_ports
        except Exception as e:
            messagebox.showwarning("Installation Failed", f"Failed to install pyserial. Power supply features will remain disabled.\nPlease run 'pip install pyserial' manually.\n\nError: {e}")
try:
    import pyperclip
except ImportError:
    pyperclip = None
    if messagebox.askyesno("Dependency Missing", "The 'pyperclip' library is missing. Copy/paste features will be disabled unless it is installed.\n\nWould you like to attempt to install it now?"):
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyperclip"])
            import pyperclip
        except Exception as e:
            messagebox.showwarning("Installation Failed", f"Failed to install pyperclip. Copy/paste features will remain disabled.\nPlease run 'pip install pyperclip' manually.\n\nError: {e}")
try:
    import can
except ImportError:
    can = None
    if messagebox.askyesno("Dependency Missing", "The 'python-can' library is missing. Direct CAN features will be disabled unless it is installed.\n\nWould you like to attempt to install it now?"):
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "python-can"])
            import can
        except Exception as e:
            messagebox.showwarning("Installation Failed", f"Failed to install python-can. Direct CAN features will remain disabled.\nPlease run 'pip install python-can' manually.\n\nError: {e}")
try:
    import cantools
except ImportError:
    cantools = None
    if messagebox.askyesno("Dependency Missing", "The 'cantools' library is missing. DBC/CDD features will be disabled unless it is installed.\n\nWould you like to attempt to install it now?"):
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "cantools"])
            import cantools
        except Exception as e:
            messagebox.showwarning("Installation Failed", f"Failed to install cantools. DBC/CDD features will remain disabled.\nPlease run 'pip install cantools' manually.\n\nError: {e}")
try:
    import cv2
    from PIL import Image, ImageTk
except ImportError:
    cv2, Image, ImageTk = None, None, None
    if messagebox.askyesno("Dependency Missing", "The 'opencv-python' and 'Pillow' libraries are missing. Camera features will be disabled unless they are installed.\n\nWould you like to attempt to install them now?"):
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "opencv-python", "Pillow"])
            import cv2
            from PIL import Image, ImageTk
        except Exception as e:
            messagebox.showwarning("Installation Failed", f"Failed to install camera libraries. Camera features will remain disabled.\nPlease run 'pip install opencv-python Pillow' manually.\n\nError: {e}")

# --- Global Variables for Camera feature ---
camera_capture_object = None
camera_thread = None
stop_camera_thread_event = threading.Event()
latest_camera_frame = None

# --- Configuration ---
POWER_SUPPLY_DESCRIPTION = "Silicon Labs CP210x USB to UART Bridge"
SAVED_DIDS_FILE = "sent_dids_history.json" # For DID History
CUSTOM_MESSAGES_FILE = "custom_can_messages.json" # For Custom CAN Sender

# --- Core Automation Logic ---
output_queue = queue.Queue() 
power_supply_serial = None # Global handle for the serial port
dbc_db = None # For DBC database

# --- DBC and CDD Loading Functions ---
def load_dbc_files(self):
    """Loads and merges DBC files, attempting to identify problematic files."""
    global dbc_db
    if cantools is None:
        self.log_to_status("ERROR: cantools library is not available.")
        return

    filepaths = filedialog.askopenfilenames(
        title="Select DBC Files",
        filetypes=(("DBC Files", "*.dbc *.txt"), ("All files", "*.*"))
    )
    if not filepaths:
        return

    # Reset the database before loading new files
    dbc_db = None
    loaded_successfully = True

    # Try loading files one by one to find the faulty one
    for path in filepaths:
        self.log_to_status(f"Attempting to load file: {Path(path).name}...")
        try:
            # Use load_file (singular) for individual checking
            new_db_part = cantools.db.load_file(path, strict=False)
            if dbc_db is None:
                # The first successfully loaded file becomes the base
                dbc_db = new_db_part
                self.update_dbc_message_dropdown() # This will populate the new message sender

            else:
                # Add subsequent files to the main database
                dbc_db.add_dbc(new_db_part)
            self.log_to_status(f"-> Successfully loaded and merged {Path(path).name}")
        except Exception as e:
            # If any file fails, log the specific error and which file caused it
            self.log_to_status(f"!!! FAILED to load file: {Path(path).name} !!!")
            self.log_to_status(f"Error details: {e}")
            self.log_to_status("Please check this file for syntax errors. DBC loading has been aborted.")
            loaded_successfully = False
            # Stop on the first error to avoid further issues
            break

    if loaded_successfully and dbc_db is not None:
        self.log_to_status(f"Finished loading DBC files.")
    else:
        # If loading failed for any file, we consider the whole process a failure
        # and reset the database to prevent using a partial one.
        self.log_to_status("DBC loading was not successful. The database is empty.")
        dbc_db = None

def load_dids_from_cdd(self):
    """Loads DIDs from a CDD file using the cantools library."""
    global dbc_db
    if cantools is None:
        self.log_to_status("ERROR: cantools library is not installed. Please run 'pip install cantools'")
        return

    filepath = filedialog.askopenfilename(
        title="Select CDD File",
        filetypes=(("CDD Files", "*.cdd *.xml *.txt"), ("All files", "*.*"))
    )
    if not filepath:
        return

    try:
        # Use cantools to load the CDD file directly
        cdd_db = cantools.db.load_file(filepath, strict=False)
        dids = []

        if not hasattr(cdd_db, 'dids') or not cdd_db.dids:
             self.log_to_status("No DIDs were found by the cantools parser in the selected file.")
             return

        for did in cdd_db.dids:
            did_hex = f"{did.identifier:02X}"
            dids.append(f"{did_hex} - {did.name}")

        if dids:
            unique_dids = sorted(list(set(dids)))
            self.did_dropdown['values'] = unique_dids
            self.did_dropdown.current(0)
            self.log_to_status(f"Loaded {len(unique_dids)} unique DIDs from {Path(filepath).name}")

            if dbc_db is not None:
                dbc_db.add_dbc(cdd_db)
                self.log_to_status("Merged CDD DID information into the main DBC database.")
            else:
                dbc_db = cdd_db

        else:
            self.log_to_status("The file was parsed, but it contains no DID definitions.")

    except Exception as e:
        self.log_to_status(f"Error parsing CDD file with cantools: {e}\n{traceback.format_exc()}")

def update_status(message): 
    """Puts a message into the queue for the GUI to display."""
    output_queue.put(message) 

# --- Power Supply Control Functions ---
def ps_connectSerial(description=POWER_SUPPLY_DESCRIPTION): 
    """Attempts to connect to the power supply."""
    global power_supply_serial 
    if serial is None: 
        update_status("ERROR: pyserial module not loaded.") 
        return None

    if power_supply_serial and power_supply_serial.is_open: 
        update_status(f"Power supply already connected at {power_supply_serial.port}") 
        return power_supply_serial 

    ports = serial.tools.list_ports.comports() 
    found_ser_object = None 
    for port_info in ports: 
        temp_ser = None 
        try:
            if description in port_info.description: 
                update_status(f"Found potential PS at {port_info.device}. Attempting to connect...") 
                temp_ser = serial.Serial(port_info.device, 9600, timeout=1) 
                update_status(f"Successfully opened port {port_info.device}.") 
                found_ser_object = temp_ser 
                break 
        except Exception as e: 
            update_status(f"ERROR connecting to {port_info.device}: {e}") 
            if temp_ser and temp_ser.is_open: 
                temp_ser.close() 
            found_ser_object = None 

    if found_ser_object: 
        power_supply_serial = found_ser_object 
        update_status(f"Power supply connected at {power_supply_serial.port}.") 
        return power_supply_serial 
    else:
        update_status(f"ERROR: Target power supply ('{description}') not found or failed to connect.") 
        power_supply_serial = None 
        return None

# Using the corrected ps_readVoltage and ps_readCurrent from previous interactions
def ps_readVoltage(ser_handle): 
    """Reads voltage. Assumes GETD returns 'XXVVVVCCCCS...' on one line."""
    if ser_handle is None or not ser_handle.is_open: 
        update_status("ERROR: Power supply not connected for readVoltage.") 
        return None
    try:
        command = "GETD\r" 
        ser_handle.reset_input_buffer() 
        ser_handle.write(command.encode()) 
        time.sleep(0.2) # Increased slightly for response
        response_bytes = ser_handle.readline().strip() 
        response_str = response_bytes.decode(errors='ignore') 
        update_status(f"PS GETD raw response: '{response_str}'") 

        if len(response_str) >= 6: 
            voltage_str_part = response_str[0:4] # Characters at index 2, 3, 4, 5 
            val = int(voltage_str_part) / 100.0 
            update_status(f"PS Parsed Voltage: {val:.2f} V (from '{voltage_str_part}')") 
            return val 
        else:
            update_status(f"ERROR: Short or unexpected response for GETD (voltage): '{response_str}'") 
            return None
    except ValueError as ve: # Specifically for int conversion 
        update_status(f"ERROR during ps_readVoltage (ValueError): {ve}. Response part for voltage: '{voltage_str_part if 'voltage_str_part' in locals() else 'N/A'}'") 
        return None
    except Exception as e: 
        update_status(f"ERROR during ps_readVoltage: {type(e).__name__} - {e}") 
        return None

def ps_readCurrent(ser_handle): 
    """Reads current. Assumes GETD returns 'XXVVVVCCCCS...' on one line."""
    if ser_handle is None or not ser_handle.is_open: 
        update_status("ERROR: Power supply not connected for readCurrent.") 
        return None
    try:
        command = "GETD\r" 
        ser_handle.reset_input_buffer() 
        ser_handle.write(command.encode()) 
        time.sleep(0.2) # Increased slightly for response 
        response_bytes = ser_handle.readline().strip() 
        response_str = response_bytes.decode(errors='ignore') 
        update_status(f"PS GETD raw response (for current): '{response_str}'") 

        if len(response_str) >= 10: # Need at least up to the end of the current part 
            current_str_part = response_str[5:8] # Characters at index 6, 7, 8, 9 
            val = int(current_str_part) / 100.0 
            update_status(f"PS Parsed Current: {val:.2f} A (from '{current_str_part}')") 
            return val 
        else:
            update_status(f"ERROR: Short or unexpected response for GETD (current): '{response_str}'") 
            return None
    except ValueError as ve: # Specifically for int conversion 
        update_status(f"ERROR during ps_readCurrent (ValueError): {ve}. Response part for current: '{current_str_part if 'current_str_part' in locals() else 'N/A'}'") 
        return None
    except Exception as e: 
        update_status(f"ERROR during ps_readCurrent: {type(e).__name__} - {e}") 
        return None

def ps_on(ser_handle): 
    """Turns the power supply output ON."""
    if ser_handle is None or not ser_handle.is_open: 
        update_status("ERROR: Power supply not connected for ON command.") 
        return
    try:
        update_status("Turning power supply ON...") 
        command = "SOUT0\r" # Assuming SOUT0 is ON based on SOUT1 being OFF 
        ser_handle.write(command.encode()) 
        time.sleep(0.1) 
        response = ser_handle.readline().decode().strip() 
        update_status(f"PS ON command ('SOUT0') response: '{response}'") 
        if response.upper() != "OK": #
             update_status(f"Warning: PS ON command did not return 'OK'. Got: '{response}'") 
        time.sleep(1) 
    except Exception as e: 
        update_status(f"ERROR during ps_on: {e}") 

def ps_off(ser_handle): #
    """Turns the power supply output OFF."""
    if ser_handle is None or not ser_handle.is_open: 
        update_status("ERROR: Power supply not connected for OFF command.") 
        return
    try:
        update_status("Turning power supply OFF...") 
        command = "SOUT1\r" 
        ser_handle.write(command.encode()) 
        time.sleep(0.1) 
        response = ser_handle.readline().decode().strip() 
        update_status(f"PS OFF command ('SOUT1') response: '{response}'") 
        if response.upper() != "OK": 
             update_status(f"Warning: PS OFF command did not return 'OK'. Got: '{response}'") 
        time.sleep(1) 
    except Exception as e: 
        update_status(f"ERROR during ps_off: {e}") 

def ps_setVolt(ser_handle, volt_float_input): 
    """
    Sets the power supply voltage. Accepts float (e.g., 13.5V),
    formats command to VOLTXXX (e.g., VOLT135 for 13.5V).
    """
    if ser_handle is None or not ser_handle.is_open: 
        update_status("ERROR: Power supply not connected for setVolt.") 
        return False
    try:
        desired_voltage_float = float(volt_float_input) 
        value_to_send = int(round(desired_voltage_float * 10)) # For VOLTddd (0.1V units) 

        if not (0 <= value_to_send <= 999): # Assuming 3 digits for VOLT command 
            update_status(f"ERROR: Voltage {desired_voltage_float:.1f}V (command val {value_to_send}) out of settable range for VOLTddd (0.0-99.9V).") 
            return False

        command_param_str = f"{value_to_send:03d}" # e.g., 135 for 13.5V 
        send_string_command = f"VOLT{command_param_str}\r" 

        update_status(f"Setting PS voltage to {desired_voltage_float:.1f}V (Command: VOLT{command_param_str})...") 
        ser_handle.write(send_string_command.encode()) 
        time.sleep(0.1) #
        response = ser_handle.readline().decode().strip() 
        update_status(f"PS setVolt command response: '{response}'") 

        command_successful = response.upper() == "OK" 
        if not command_successful: 
            update_status(f"ERROR: PS setVolt command 'VOLT{command_param_str}' failed or unexpected response: '{response}'") 

        time.sleep(0.5) 

        read_back_voltage = ps_readVoltage(ser_handle) # Pass the handle 
        if read_back_voltage is not None: 
            if abs(read_back_voltage - desired_voltage_float) < 0.2: # Verification threshold 
                update_status(f"Voltage verified near {desired_voltage_float:.1f}V (Read: {read_back_voltage:.2f}V).") 
            else:
                update_status(f"Warning: Voltage verification discrepancy. Desired: {desired_voltage_float:.1f}V, Read: {read_back_voltage:.2f}V.") 
        else:
            update_status(f"Warning: Could not read back voltage for verification after setVolt.") 

        return command_successful 
    except Exception as e: 
        update_status(f"ERROR during ps_setVolt: {e}") 
        return False
# --- End Power Supply ---

def log_can_message_to_file(log_entry):
    """
    Appends a formatted CAN log entry to a text file in the script's root directory.
    This function is called automatically for all TX and RX messages.
    """
    try:
        with open("can_log.txt", "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")
    except Exception as e:
        # This will print to the console, not the GUI, to avoid feedback loops
        print(f"CRITICAL: Failed to write to can_log.txt: {e}")

def camera_worker_thread(app_instance, camera_index):
    """
    A worker thread that continuously captures frames from the specified camera.
    """
    global camera_capture_object, latest_camera_frame, stop_camera_thread_event
    
    try:
        camera_capture_object = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if not camera_capture_object.isOpened():
            raise ConnectionError(f"Could not open camera at index {camera_index}.")
        
        update_status(f"Camera connected successfully at index {camera_index}.")
        
        # Continuously read frames from the camera
        while not stop_camera_thread_event.is_set():
            ret, frame = camera_capture_object.read()
            if not ret:
                update_status("Warning: Camera frame could not be read. Stream may have ended.")
                time.sleep(0.5)
                continue
            
            # Store the latest frame for screenshots and GUI updates
            latest_camera_frame = frame
            
            # Add a small delay to prevent hogging the CPU
            time.sleep(0.01)

    except Exception as e:
        update_status(f"ERROR in camera thread: {e}")
    finally:
        if camera_capture_object and camera_capture_object.isOpened():
            camera_capture_object.release()
        camera_capture_object = None
        latest_camera_frame = None
        update_status("Camera disconnected.")

def update_camera_feed_label(app_instance):
    """

    Periodically updates the Tkinter label with the latest frame from the camera.
    """
    global latest_camera_frame, stop_camera_thread_event
    
    # If the thread is supposed to be stopped, clear the image
    if stop_camera_thread_event.is_set():
        if hasattr(app_instance, 'camera_feed_label'):
             app_instance.camera_feed_label.config(image='')
        return # Do not reschedule

    if latest_camera_frame is not None:
        try:
            # Resize frame for display in the GUI to prevent overly large windows
            height, width, _ = latest_camera_frame.shape
            scale_percent = 300 / height # Aim for a display height of 300px
            new_width = int(width * scale_percent)
            new_height = int(height * scale_percent)
            display_frame = cv2.resize(latest_camera_frame, (new_width, new_height), interpolation=cv2.INTER_AREA)

            # Convert frame for Tkinter
            cv2image = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(cv2image)
            imgtk = ImageTk.PhotoImage(image=img)
            
            # Update the label
            if hasattr(app_instance, 'camera_feed_label') and app_instance.camera_feed_label.winfo_exists():
                app_instance.camera_feed_label.imgtk = imgtk
                app_instance.camera_feed_label.config(image=imgtk)

        except Exception as e:
            # This can happen if the frame is corrupted or during shutdown
            print(f"Error updating camera feed label: {e}")
            
    # Reschedule this function to be called after a short delay
    if hasattr(app_instance, 'root') and app_instance.root.winfo_exists():
        app_instance.root.after(30, lambda: update_camera_feed_label(app_instance))

# --- NEW CAMERA AND LOGGING FUNCTIONS END ---

# --- CDA Specific Functions (pyautogui) ---
def save_DID_Response(DID_str, operation_mode): 
    if operation_mode != "CDA": 
        return 
    if 'pyautogui' not in sys.modules or pyperclip is None: 
        update_status("ERROR: pyautogui/pyperclip missing for save_DID_Response.") 
        return
    try:
        # User to verify/adjust these coordinates for their CDA tool setup
        response_win_coord = (886, 476)
        select_all_coord = (947, 584)
        copy_coord = (947, 522) 
        update_status(f"Saving CDA response for: {DID_str}") 
        pyautogui.click(response_win_coord, clicks=2, interval=0.1)
        time.sleep(0.5) 
        pyautogui.click(button='right')
        time.sleep(0.5)
        pyautogui.click(select_all_coord)
        time.sleep(0.5) 
        pyautogui.click(button='right')
        time.sleep(0.5)
        pyautogui.click(copy_coord)
        time.sleep(0.5)
        s = pyperclip.paste()
        time.sleep(0.1) 
        if not s: 
            update_status("WARNING: Clipboard empty for DID response.") 
            return
        cleaned_s = ''.join(s.split()) 
        if not cleaned_s or not all(c in '0123456789abcdefABCDEF' for c in cleaned_s): 
            update_status(f"WARNING: Clipboard not hex for DID ('{s[:50].strip()}...').") 
            return
        hex_part = cleaned_s 
        actual_payload_hex = hex_part[6:] if len(hex_part) > 6 else "" 
        ascii_string = "" 
        if actual_payload_hex: 
            try:
                ascii_string = bytes.fromhex(actual_payload_hex).decode('ascii', 'ignore') 
            except ValueError: 
                ascii_string = "(Cannot decode payload to ASCII)" 
        else:
            ascii_string = "(No payload for ASCII conversion)" 

        log_file = Path("./DID_Response.txt") 
        with open(log_file, "a") as f: 
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
            f.write(f"[{ts}] Req: {DID_str}\nASCII Resp: {ascii_string}\nRaw Resp: {s.strip()}\n---\n") 
        update_status(f"Saved response for {DID_str} to {log_file.name}") 
    except Exception as e: 
        update_status(f"ERROR saving DID response: {e}\n{traceback.format_exc()}") 

def clear_PID_Editor(operation_mode): 
    if operation_mode != "CDA": 
        return 
    if 'pyautogui' not in sys.modules: 
        update_status("ERROR: pyautogui missing for clear_PID_Editor.") 
        return
    try:
        request_field_coord = (664, 479) 
        pyautogui.click(request_field_coord, clicks=2, interval=0.1); time.sleep(0.3) 
        pyautogui.press("delete"); time.sleep(0.2) 
    except Exception as e: 
        update_status(f"ERROR clearing PID editor: {e}") 

def openCDA(operation_mode): 
    if operation_mode != "CDA": 
        return True 
    if 'pyautogui' not in sys.modules:
        update_status("ERROR: pyautogui missing for openCDA.")
        return False 
    cda_path_str = r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\CDA 6\CDA 6.lnk" 
    cda_path_obj = Path(cda_path_str) 
    if not cda_path_obj.exists(): 
        update_status(f"ERROR: CDA shortcut not found: {cda_path_str}")
        return False 
    try:
        update_status("Opening CDA 6...") 
        subprocess.Popen(['cmd', '/c', 'start', '', f'"{cda_path_str}"'], shell=True) 
        update_status("Waiting 30s for CDA to launch (adjust if needed)...")
        time.sleep(30) 
        return True 
    except Exception as e: 
        update_status(f"ERROR opening CDA: {e}")
        return False 

def loginCDA(operation_mode, username, password): 
    if operation_mode != "CDA": 
        return True 
    if 'pyautogui' not in sys.modules: update_status("ERROR: pyautogui missing for loginCDA.")
    return False 
    if not username or not password: 
        update_status("ERROR: Credentials for CDA empty.") 
        return False 
    try:
        update_status("Attempting CDA login (Ensure CDA window is active and focused!)...")
        time.sleep(5) 
    except Exception as e: 
        update_status(f"ERROR preparing for CDA login: {e}")
        return False 
    try:
        time.sleep(1)
        pyautogui.press('tab', presses=3, interval=0.3)
        time.sleep(0.5) 
        pyautogui.press('backspace', presses=30, interval=0.05)
        pyautogui.write(username)
        time.sleep(0.5) 
        pyautogui.press("tab")
        time.sleep(0.5)
        pyautogui.write(password)
        time.sleep(0.5) 
        pyautogui.press("enter")
        update_status("Login submitted. Waiting 15s for CDA...")
        time.sleep(15) 
        return True 
    except Exception as e: 
        update_status(f"ERROR during CDA login automation: {e}")
        return False 

def deviceConnection(operation_mode): 
    if operation_mode != "CDA":
        return True 
    if 'pyautogui' not in sys.modules:
        update_status("ERROR: pyautogui missing for deviceConnection.")
        return False 
    try: 
        update_status("Attempting CDA device connection...")
        time.sleep(5) 
    except Exception as e:
        update_status(f"ERROR preparing for CDA device connection: {e}")
        return False 
    try:
        benchtop_coord=(1378, 538)
        continue_coord=(1411, 871)
        ecu_entry_coord=(532, 366)
        ok_button_coord=(957, 638) 
        ecu_name = "cvadas" 
        pyautogui.click(benchtop_coord)
        time.sleep(2) 
        pyautogui.click(continue_coord)
        time.sleep(2) 
        pyautogui.click(ecu_entry_coord)
        time.sleep(1)
        pyautogui.write(ecu_name)
        time.sleep(1)
        pyautogui.press("enter")
        time.sleep(8) 
        pyautogui.click(ok_button_coord, clicks=2, interval=0.1)
        time.sleep(2) 
        update_status("CDA Device connection sequence attempted.")
        return True 
    except Exception as e: 
        update_status(f"ERROR during CDA device connection automation: {e}")
        return False 

def unlockECU(app_instance): 
    operation_mode = app_instance.operation_mode_var.get() 
    if operation_mode == "Direct CAN": 
        update_status("Info: Sending Security Seed/Key DID 27 11 and 27 12.. Please wait..") 
        send_DID(app_instance,"27 11 00 00 00 00 00 00 00")
        send_DID(app_instance,"27 12 00 00 00 00 00 00 00")
        return True # Placeholder for Direct CAN unlock 
    elif operation_mode == "CDA": 
        if 'pyautogui' not in sys.modules: 
            update_status("ERROR: pyautogui missing for unlockECU via CDA.")
            return False 
        try: 
            update_status("Attempting ECU Unlock via CDA GUI...")
            time.sleep(3) 
        except Exception as e: 
            update_status(f"ERROR preparing for CDA ECU unlock: {e}")
            return False 
        try:
            unlock_main_btn_coord=(1197, 374)
            unlock_dialog_btn_coord=(661, 635) 
            pyautogui.click(unlock_main_btn_coord, clicks=2, interval=0.1)
            time.sleep(5) 
            pyautogui.click(unlock_dialog_btn_coord)
            time.sleep(1) 
            update_status("Waiting 20s for CDA unlock process...")
            time.sleep(20) 
            update_status("CDA Unlock command sent (assumed success).") 
            return True 
        except Exception as e: 
            update_status(f"ERROR during CDA ECU unlock automation: {e}")
            return False 
    else: 
        update_status(f"ERROR: Unknown operation mode '{operation_mode}' for unlockECU")
        return False 
# --- End CDA Specific ---

# --- Core DID Sending Function ---
def send_DID(app_instance, DID_hex_string): 
    operation_mode = app_instance.operation_mode_var.get() 
    success = False 
    if not DID_hex_string: 
        update_status("ERROR: DID_hex_string is empty in send_DID call.") 
        return False
        
    if DID_hex_string not in app_instance.sent_dids_history:
        app_instance.sent_dids_history.append(DID_hex_string)
        update_status(f"DID '{DID_hex_string}' added to history.")

    if operation_mode == "CDA": 
        if 'pyautogui' not in sys.modules: 
            update_status("ERROR: pyautogui missing.")
            return False 
        try:
            clear_PID_Editor(operation_mode) 
            pyautogui.write(DID_hex_string)
            time.sleep(0.3) 
            pyautogui.press("enter")
            time.sleep(1.5) # Allow CDA to process 
            save_DID_Response(DID_hex_string, operation_mode) 
            success = True 
        except Exception as e: 
            update_status(f"ERROR sending '{DID_hex_string}' in CDA mode: {e}")
            success = False 
    elif operation_mode == "Direct CAN": 
        if can is None: 
            update_status("ERROR: python-can missing.")
            return False 
        if not app_instance.can_bus:
            update_status(f"ERROR: CAN disconnected. Cannot send '{DID_hex_string}'.")
            return False 
        
        req_id_str = "" 
        payload_bytes = b'' 
        ecu_request_id = 0 
        
        try:
            req_id_str = app_instance.can_req_id_var.get().strip() 
            if not req_id_str: 
                raise ValueError("ECU Req ID in GUI is empty.") 
            ecu_request_id = int(req_id_str.replace(" ",""), 16) 
            if not (0 <= ecu_request_id <= 0x1FFFFFFF): 
                raise ValueError("ECU Req ID out of valid 29-bit range.") 
            
            payload_str_cleaned = DID_hex_string.replace(" ", "").replace("0x", "", 1).replace("0X", "", 1) 
            payload_bytes = bytes.fromhex(payload_str_cleaned) if payload_str_cleaned else b'' 

        except Exception as e:  
            msg = f"Invalid input for Direct CAN send: ECU Req ID='{req_id_str}', DID='{DID_hex_string}'. Error: {e}" 
            update_status(f"ERROR: {msg}"); messagebox.showerror("Invalid Input", msg)
            return False 

        is_extended_id_flag = ecu_request_id > 0x7FF 
        message_to_send = can.Message(arbitration_id=ecu_request_id, data=payload_bytes, is_extended_id=is_extended_id_flag) 
        
        timestamp_tx = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] 
        log_entry_tx = "" 
        try:
            arb_id_tx = message_to_send.arbitration_id 
            is_ext_tx = message_to_send.is_extended_id 
            dlc_tx = message_to_send.dlc 
            data_bytes_tx = message_to_send.data 

            id_hex_str_tx = f"{arb_id_tx:08X}" if is_ext_tx else f"{arb_id_tx:03X}" 
            
            data_hex_parts_tx = [] 
            if data_bytes_tx is not None: 
                for byte_val_tx in data_bytes_tx: 
                    data_hex_parts_tx.append(f"{byte_val_tx:02X}") 
            data_hex_str_tx = ' '.join(data_hex_parts_tx) 

            log_entry_tx = f"{timestamp_tx} | [CAN Tx] | ID: {id_hex_str_tx} | DL: {dlc_tx} | Data: {data_hex_str_tx}" 

        except ValueError as ve_tx: 
            if "format string" in str(ve_tx).lower(): 
                err_detail_tx = (f"TX FORMAT ValueError (Invalid format string) Details:\n" 
                                 f"  Timestamp: {timestamp_tx}\n"
                                 f"  Arb ID: {repr(message_to_send.arbitration_id)}\n"
                                 f"  Is Extended: {repr(message_to_send.is_extended_id)}\n"
                                 f"  DLC: {repr(message_to_send.dlc)}\n"
                                 f"  Data: {repr(message_to_send.data)}\n"
                                 f"  Exception: {ve_tx}")
                update_status(err_detail_tx) 
                log_entry_tx = f"{timestamp_tx} | TX_FALLBACK | ID: {str(message_to_send.arbitration_id)} | DLC: {str(message_to_send.dlc)} | Data: {str(list(message_to_send.data if message_to_send.data is not None else []))}" 
            else:
                update_status(f"TX Other ValueError: {ve_tx}. Msg: {repr(message_to_send)}") 
                log_entry_tx = f"{timestamp_tx} | TX_ERROR_VAL | {ve_tx}" # Fallback 
        except TypeError as te_tx: 
            err_detail_tx = (f"TX FORMAT TypeError Details:\n" 
                             f"  Timestamp: {timestamp_tx}\n"
                             f"  Arb ID: {repr(message_to_send.arbitration_id)}\n"
                             f"  Is Extended: {repr(message_to_send.is_extended_id)}\n"
                             f"  DLC: {repr(message_to_send.dlc)}\n"
                             f"  Data: {repr(message_to_send.data)}\n"
                             f"  Exception: {te_tx}")
            update_status(err_detail_tx) 
            log_entry_tx = f"{timestamp_tx} | TX_FALLBACK_TE | ID: {str(message_to_send.arbitration_id)} | DLC: {str(message_to_send.dlc)} | Data: {str(list(message_to_send.data if message_to_send.data is not None else []))}" 
        except Exception as e_fmt_tx: 
            error_msg_tx = f"TX log formatting error for msg {repr(message_to_send)}: {type(e_fmt_tx).__name__}: {e_fmt_tx}" 
            update_status(error_msg_tx) 
            log_entry_tx = f"{timestamp_tx} | TX_ERROR_FMT | {error_msg_tx}" 
        
        update_status(log_entry_tx) # Log the formatted TX message (or error/fallback) 
        log_can_message_to_file(log_entry_tx) # <<< ADD THIS LINE

        try:
            app_instance.can_bus.send(message_to_send, timeout=0.8) 
            success = True 

            response_timeout_s = 0.8  # Listen for 0.8 seconds for an immediate response
            rx_message_observed = False
            start_rx_listen_time = time.monotonic()
            
            parsed_expected_resp_id_val = None
            ecu_resp_id_str_gui = app_instance.can_resp_id_var.get().strip()
            if ecu_resp_id_str_gui:
                try:
                    parsed_expected_resp_id_val = int(ecu_resp_id_str_gui.replace(" ", ""), 16)
                except ValueError:
                    update_status(f"Warning: Invalid ECU Resp ID '{ecu_resp_id_str_gui}' in GUI for immediate RX check. Will log any RX.")
            
            while (time.monotonic() - start_rx_listen_time) < response_timeout_s:
                rx_can_message = app_instance.can_bus.recv(timeout=0.8) # Short recv timeout
                if rx_can_message is not None:
                    rx_message_observed = True
                    timestamp_rx = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                    log_entry_rx = ""
                    log_prefix_str = "[CAN Direct DID-RX]" # For immediate response after send_DID

                    try:
                        arb_id_rx = rx_can_message.arbitration_id
                        is_ext_rx = rx_can_message.is_extended_id
                        dlc_rx = rx_can_message.dlc
                        data_bytes_rx = rx_can_message.data
                        id_hex_str_rx = f"{arb_id_rx:08X}" if is_ext_rx else f"{arb_id_rx:03X}"
                        data_hex_parts_rx = [f"{b:02X}" for b in data_bytes_rx] if data_bytes_rx is not None else []
                        data_hex_str_rx = ' '.join(data_hex_parts_rx)

                        if parsed_expected_resp_id_val is not None and rx_can_message.arbitration_id == parsed_expected_resp_id_val:
                            log_prefix_str = "[CAN Direct DID-RX MATCH]"
                        
                        log_entry_rx = f"{timestamp_rx} | {log_prefix_str} | ID: {id_hex_str_rx} | DL: {dlc_rx} | Data: {data_hex_str_rx}"

                    except ValueError as ve_rx:
                        if "format string" in str(ve_rx).lower():
                            err_detail_rx = (f"Immediate RX FORMAT ValueError (Invalid format string) Details:\n"
                                             f"  Timestamp: {timestamp_rx}, Arb ID: {repr(rx_can_message.arbitration_id)}, Type: {type(rx_can_message.arbitration_id)}\n"
                                             f"  Is Extended: {repr(rx_can_message.is_extended_id)}, Type: {type(rx_can_message.is_extended_id)}\n"
                                             f"  DLC: {repr(rx_can_message.dlc)}, Type: {type(rx_can_message.dlc)}\n"
                                             f"  Data: {repr(rx_can_message.data)}, Type: {type(rx_can_message.data)}\n"
                                             f"  Exception: {ve_rx}")
                            update_status(err_detail_rx)
                            log_entry_rx = f"{timestamp_rx} | RX_FALLBACK | ID: {str(rx_can_message.arbitration_id)} | DLC: {str(rx_can_message.dlc)} | Data: {str(list(rx_can_message.data if rx_can_message.data is not None else []))}"
                        else:
                            update_status(f"Immediate RX Other ValueError: {ve_rx}. Msg: {repr(rx_can_message)}")
                            log_entry_rx = f"{timestamp_rx} | RX_ERROR_VAL | {ve_rx}"
                    except TypeError as te_rx:
                        err_detail_rx = (f"Immediate RX FORMAT TypeError Details:\n"
                                         f"  Timestamp: {timestamp_rx}, Arb ID: {repr(rx_can_message.arbitration_id)}, Type: {type(rx_can_message.arbitration_id)}\n"
                                         f"  Is Extended: {repr(rx_can_message.is_extended_id)}, Type: {type(rx_can_message.is_extended_id)}\n"
                                         f"  DLC: {repr(rx_can_message.dlc)}, Type: {type(rx_can_message.dlc)}\n"
                                         f"  Data: {repr(rx_can_message.data)}, Type: {type(rx_can_message.data)}\n"
                                         f"  Exception: {te_rx}")
                        update_status(err_detail_rx)
                        log_entry_rx = f"{timestamp_rx} | RX_FALLBACK_TE | ID: {str(rx_can_message.arbitration_id)} | DLC: {str(rx_can_message.dlc)} | Data: {str(list(rx_can_message.data if rx_can_message.data is not None else []))}"
                    except Exception as e_fmt_rx:
                        update_status(f"Immediate RX log formatting error for msg {repr(rx_can_message)}: {type(e_fmt_rx).__name__}: {e_fmt_rx}")
                        log_entry_rx = f"{timestamp_rx} | RX_ERROR_FMT | {repr(rx_can_message)}"
                    
                    update_status(log_entry_rx)
                    break # Processed first response, exit listen loop
                
                if not app_instance.can_bus: # Bus might have been disconnected by another thread/error
                    update_status("WARNING: CAN bus became unavailable during immediate RX listen.")
                    break
                    
            if not rx_message_observed:
                update_status(f"WARNING: No immediate RX response observed for TX ID {ecu_request_id:#X}, DID: {DID_hex_string} within {response_timeout_s}s.")
                log_can_message_to_file(warning_msg) 
        except can.CanError as e: 
            err_msg = f"CAN Send Error: {e}"
            print(f"CAN Send Error Details: {traceback.format_exc()}")
            update_status(f"ERROR: {err_msg}") 
            app_instance.shutdown_can()
            messagebox.showerror("CAN Send Error", f"{err_msg}\n\nCAN connection has been reset.")
            success = False 
        except Exception as e: 
            err_msg = f"Unexpected error during CAN send or immediate RX: {e}"
            print(f"Unexpected CAN Send/RX Error Details: {traceback.format_exc()}")
            update_status(f"ERROR: {err_msg}")
            success = False 
    else: 
        update_status(f"ERROR: Unknown operation mode '{operation_mode}' for send_DID")
        success = False 

    time.sleep(0.1) # Small delay after sending/listening, adjust as needed 
    return success

# --- Test Case Data Structure ---
def test_spare_ground_checks(app_instance): # Doc 2.5.3 
    update_status("--- Starting Section 2.5.3: Spare Ground Checks ---") 
    update_status("Action: Manually measure spare ground voltage on PIN 15A. Expected: -0.25V to +0.25V (or 3.38V +/- 0.25V for CCI FFT Tester).")  
    update_status("Action: Manually measure spare ground voltage on PIN 17A. Expected: -0.25V to +0.25V (or 3.38V +/- 0.25V for CCI FFT Tester).")  
    update_status("Spare Ground Checks section requires manual measurement.") 
    return True # Script can't automate this measurement 

def test_dut_serialization(app_instance): # Doc 2.5.4 
    update_status("--- Starting Section 2.5.4: DUT Serialization ---") 
    success = True 
    update_status("Reading DID $FD1D – PCB Serial Number...") 
    if not send_DID(app_instance, "22 FD1D"): 
        success = False 
    update_status("Reading DID $F18C – ECU Serial Number...") 
    if not send_DID(app_instance, "22 F18C"): 
        success = False 
    update_status(f"DUT Serialization DIDs sent. Success: {success}. Check logs for ECU responses.") 
    return success 

def test_ecu_identification_dids(app_instance): # Doc 2.5.5 
    update_status("--- Starting Section 2.5.5: Standardized Data Identifiers – ECU Identification ---") 
    success = True 
    dids_to_read = {  
        "F122": "Software EBOM Part Number",  
        "F132": "EBOM ECU part number",  
        "F133": "EBOM Assembly Part Number",  
        "F154": "Hardware Supplier Identification",  
        "F155": "Software Supplier Identification",  
        "F180": "Bootloader Software version",  
        "F181": "Application Software identification",  
        "F192": "Supplier Manufacturer ECU Hardware Part Number",  
        "F193": "Supplier Manufacturer ECU Hardware Version Number",  
        "F194": "Supplier Manufacturer ECU Software Part Number",  
        "F195": "Supplier Manufacturer ECU Software Version Number"  
    }
    for did, desc in dids_to_read.items(): 
        update_status(f"Reading DID ${did} – {desc}...") 
        if not send_DID(app_instance, f"22 {did}"): success = False
        break  
        time.sleep(0.1)  
    update_status(f"ECU Identification DIDs sent. Success: {success}. Check logs for ECU responses.") 
    return success 

def test_internal_dids(app_instance): # Doc 2.5.6 
    update_status("--- Starting Section 2.5.6: Standardized Data Identifiers – Internal DIDs ---") 
    success = True 
    dids_to_read = {  
        "FD15": "Magna Production Hardware Number",  
        "FD16": "Magna Production ICT Data",  
        "FD17": "Magna Production Hardware Version Information",  
        "FD38": "Programmed Assembly (Magna's ECU Part Number)",  
        "FD14": "Production Date"  
    }
    for did, desc in dids_to_read.items(): 
        update_status(f"Reading DID ${did} – {desc}...") 
        if not send_DID(app_instance, f"22 {did}"): 
            success = False
            break 
        time.sleep(0.1) 
    update_status(f"Internal DIDs sent. Success: {success}. Check logs for ECU responses.") 
    return success 

def test_temperature_checks(app_instance): # Doc 2.5.7 
    update_status("--- Starting Section 2.5.7: Temperature Checks ---") 
    success = True 
    update_status("Reading DID $FD47 – SoC Temperature...") 
    if not send_DID(app_instance, "22 FD47"):
        success = False 
    update_status("Reading DID $FD48 – PCBA Temperature...") 
    if not send_DID(app_instance, "22 FD48"): 
        success = False 
    update_status(f"Temperature Check DIDs sent. Success: {success}. Check logs for ECU responses.") 
    return success 

def test_interfaces_power_supply(app_instance): # Doc 2.5.8 
    update_status("--- Starting Section 2.5.8: Interfaces Power Supply (Cameras and USS) ---") 
    success = True 
    update_status("Reading DID $FD4A – USS Power supply and Current Level...") 
    if not send_DID(app_instance, "22 FD4A"): 
        success = False 
    update_status("Reading DID $FD46 – Cameras Power supply and Current Level...") 
    if not send_DID(app_instance, "22 FD46"): 
        success = False 
    update_status(f"Interfaces Power Supply DIDs sent. Success: {success}. Check logs for ECU responses.") 
    return success 

def test_security_access_unlock(app_instance): # Doc 2.5.9 
    update_status("--- Starting Section 2.5.9: Security Access Unlock ---") 
    update_status("Attempting ECU Unlock (standard procedure for selected mode)...") 
    if not unlockECU(app_instance):  
        update_status("ERROR: Standard ECU Unlock failed.") 
        return False
    update_status("Note: Full Security Access Unlock as per section 2.5.9 (API calls, multi-step crypto) is complex and assumed to be handled externally or via a more specialized tool if required beyond basic unlock.") 
    return True 

def perform_camera_test_patterns_main_sequence(app_instance, cycles=1): # Doc 2.5.10 
    update_status(f"--- Starting Section 2.5.10: Camera Video Test ({cycles} cycle(s)) ---") 
    success = True 
    update_status("Ensuring ECU is unlocked for Camera Video Test...") 
    if not unlockECU(app_instance): 
        update_status("ERROR: ECU Unlock failed before Camera Video Test.")
        return False 
    for i in range(cycles): 
        if not app_instance.worker_thread or not app_instance.worker_thread.is_alive():  
            update_status("Camera Test execution prematurely stopped (worker thread ended).")
            success=False
            break 
        update_status(f"Camera Video Test: Cycle {i+1}/{cycles}") 
        # Front Camera
        if not send_DID(app_instance, "31 01 FE 0E 01 01"): 
            success=False
            break  
        update_status("FrontCam PATTERN ON. Wait 7s. MANUALLY EVALUATE IMAGE.")
        time.sleep(7)  
        if not send_DID(app_instance, "31 02 FE 0E"):
            success=False
            break  
        update_status("FrontCam PATTERN OFF. Wait 2s.")
        time.sleep(2)  
        # Rear Camera
        if not send_DID(app_instance, "31 01 FE 0E 03 01"): 
            success=False
            break  
        update_status("RearCam PATTERN ON. Wait 7s. MANUALLY EVALUATE IMAGE.")
        time.sleep(7)  
        if not send_DID(app_instance, "31 02 FE 0E"): 
            success=False
            break  
        update_status("RearCam PATTERN OFF. Wait 2s.")
        time.sleep(2)  
        # Left Camera
        if not send_DID(app_instance, "31 01 FE 0E 02 01"): 
            success=False
            break  
        update_status("LeftCam PATTERN ON. Wait 7s. MANUALLY EVALUATE IMAGE.")
        time.sleep(7)  
        if not send_DID(app_instance, "31 02 FE 0E"):
            success=False
            break  
        update_status("LeftCam PATTERN OFF. Wait 2s.")
        time.sleep(2)  
        # Right Camera
        if not send_DID(app_instance, "31 01 FE 0E 04 01"): 
            success=False
            break  
        update_status("RightCam PATTERN ON. Wait 7s. MANUALLY EVALUATE IMAGE.")
        time.sleep(7)  
        if not send_DID(app_instance, "31 02 FE 0E"): 
            success=False
            break  
            update_status("RightCam PATTERN OFF. Wait 2s.")
            time.sleep(2)  
        # Cargo Camera 
        if not send_DID(app_instance, "31 01 FE 0E 06 01"): 
            success=False
            break  
        update_status("CargoCam PATTERN ON. Wait 7s. MANUALLY EVALUATE IMAGE.")
        time.sleep(7)  
        if not send_DID(app_instance, "31 02 FE 0E"): 
            success=False
            break  
        update_status("CargoCam PATTERN OFF. Wait 2s.")
        time.sleep(2)  
        if not success: 
            break 
    update_status(f"MANUAL CHECK: Image Evaluation (2.5.10.6) for color bars & Distortion (2.5.10.7).")  
    update_status(f"Camera Video Test finished. Scripted part success: {success}")
    return success 

def test_exit_in_plant_mode(app_instance): # Doc 2.5.11 
    update_status("--- Starting Section 2.5.11: Exit In-Plant Mode (Retest DUTs only) ---")  
    update_status("Note: This section is typically for retest DUTs.")  
    success = True 
    if not send_DID(app_instance, "10 03"): 
        success = False  
    if success and not send_DID(app_instance, "31 01 5200 01"):
        success = False  
    time.sleep(0.5) #
    if success and not send_DID(app_instance, "31 03 5200"):
        success = False  
    update_status(f"Exit In-Plant Mode attempted. Success: {success}. Expected Resp for last: ~71 03 5200 01")
    return success 

def test_dtc_checks(app_instance): # Doc 2.5.12 
    update_status("--- Starting Section 2.5.12: Diagnostic Trouble Codes (DTC) ---")  
    success = True 
    update_status("Clearing DTCs (Initial)...") 
    if not send_DID(app_instance, "14 FFFFFF"): 
        success = False  
    update_status("Info: Simulating VehicleSpeed=8kph (manual/external setup needed if not CDA).")  
    update_status(f"Waiting 17s for conditions before reading DTCs...")
    time.sleep(17)  
    update_status("Reading Active/Stored DTCs ($19 02 09)...") 
    if success and not send_DID(app_instance, "19 02 09"): 
        success = False  
    update_status("DTCs read. MANUAL EVALUATION of response required based on spec Appendix A, Table 6 & 7.")  
    update_status("Info: Simulating VehicleSpeed=0kph.")  
    update_status(f"Waiting 2s...")
    time.sleep(2)  
    update_status("Clearing DTCs (Final)...") 
    if success and not send_DID(app_instance, "14 FFFFFF"):
        success = False  
    update_status(f"DTC Check sequence attempted. Success: {success}.")
    return success #

def test_enter_in_plant_mode(app_instance): # Doc 2.5.13 
    update_status("--- Starting Section 2.5.13: Enter In-Plant Mode ---")  
    success = True 
    update_status("Starting In-Plant Mode routine...") 
    if not send_DID(app_instance, "31 01 5200 00"):
        success = False  
    time.sleep(0.5) 
    update_status("Requesting In-Plant Mode routine results...") 
    if success and not send_DID(app_instance, "31 03 52 00"): 
        success = False  
    update_status("MANUAL CHECK: DTC $621200 should be active.")  
    update_status(f"Enter In-Plant Mode attempted. Success: {success}. Expected Resp for last: ~71 03 5200 02")
    return success 

def test_sleep_and_power_off(app_instance): # Doc 2.5.14 
    global power_supply_serial # Access the global handle 
    update_status("--- Starting Section 2.5.14: Sleep and Power Off ---")  
    success = True 
    update_status("Simulating Ignition OFF & stopping Tester Present (conceptual steps).")  
    update_status("Note: Full CAN sim for ignition off (BCM_FD_10) not implemented. Proceeding with PS Off logic.") 
    update_status("Waiting 12s for ECU to attempt sleep (as per spec calculation)...")  
    time.sleep(12) 
    update_status("MANUAL ACTION: Measure CVADAS current draw. Expected: 0.000 A to 0.001 A.")  
    # Use the global power_supply_serial for this step, as automation_worker's handle might be gone
    if power_supply_serial and power_supply_serial.is_open: 
        ps_off(power_supply_serial)  
        update_status("Power supply output turned OFF via global handle.") 
    elif hasattr(app_instance, 'power_supply_serial_handle') and app_instance.power_supply_serial_handle and app_instance.power_supply_serial_handle.is_open: 
        # Fallback to instance handle if set by a running worker (less likely here as this is end of sequence)
        ps_off(app_instance.power_supply_serial_handle) 
        update_status("Power supply output turned OFF via instance handle.") 
    else:
        update_status("Warning: PS not connected or handle unavailable, cannot turn off automatically.")
        success = False 
    update_status(f"Sleep and Power Off sequence steps issued. Result: {success}. Manual checks required.")
    return success 
# --- End Functional Test Sequence Functions ---

# --- Main Test Sequence Orchestration ---
def run_complete_eol_test_sequence(app_instance): 
    """Orchestrates the full EOL test sequence from 2.5.3 to 2.5.14."""
    update_status("====== Starting Complete EOL Test Sequence ======") 
    overall_success = True 
    update_status("Note: Full CAN bus simulation for '2.5.2.2 CAN Initialization' is not performed by this script.") 
    
    eol_steps = [ #
        ("2.5.3 Spare Ground Checks", test_spare_ground_checks),
        ("2.5.4 DUT Serialization", test_dut_serialization),
        ("2.5.5 ECU Identification DIDs", test_ecu_identification_dids),
        ("2.5.6 Internal DIDs", test_internal_dids),
        ("2.5.7 Temperature Checks", test_temperature_checks),
        ("2.5.8 Interfaces Power Supply", test_interfaces_power_supply),
        ("2.5.9 Security Access Unlock", test_security_access_unlock),
        ("2.5.10 Camera Video Test", lambda app: perform_camera_test_patterns_main_sequence(app, 1)), # Use lambda for cycles
        ("2.5.11 Exit In-Plant Mode", test_exit_in_plant_mode), 
        ("2.5.12 DTC Checks", test_dtc_checks),
        ("2.5.13 Enter In-Plant Mode", test_enter_in_plant_mode),
        ("2.5.14 Sleep and Power Off", test_sleep_and_power_off)
    ]

    for name, func in eol_steps: 
        if not (app_instance.worker_thread and app_instance.worker_thread.is_alive()): 
             update_status(f"EOL sequence '{name}' aborted (worker thread stopped).") 
             overall_success = False; break 
        if not overall_success: 
            update_status(f"Skipping step '{name}' due to previous failure.") 
            continue 
        update_status(f"--- Running EOL Step: {name} ---") 
        if not func(app_instance): 
            overall_success = False 
            update_status(f"!!! EOL Step FAILED: {name} !!!") 
        else:
            update_status(f"--- EOL Step Finished: {name} ---") 
        time.sleep(0.5)  

    update_status(f"====== Complete EOL Test Sequence Finished. Overall Result: {'SUCCESS' if overall_success else 'FAIL/ERRORS'} ======") 
    return overall_success 

def perform_all_part_number_reads_sequence(app_instance): 
    """Runs all Part Number DID read sequences."""
    update_status("====== Starting All Part Number Reads Sequence ======") 
    overall_success = True 
    if not test_dut_serialization(app_instance): overall_success = False 
    if overall_success and not test_ecu_identification_dids(app_instance): 
        overall_success = False 
    if overall_success and not test_internal_dids(app_instance): 
        overall_success = False 
    update_status(f"====== All Part Number Reads Sequence Finished. Overall Result: {'SUCCESS' if overall_success else 'FAIL/ERRORS'} ======") 
    return overall_success 

def CheckPartNumbers_Quick(app_instance):  
    if app_instance.operation_mode_var.get() != "CDA": 
        update_status("Skipping Quick Check PNs (CDA Mode Only).")
        return True 
    if 'pyautogui' not in sys.modules: 
        update_status("ERROR: pyautogui missing for CheckPartNumbers_Quick.")
        return False 
    
    update_status("Starting Quick Part Number Check (CDA GUI)...") 
    read_write_data_softkey_coord = (661, 366)  
    first_item_in_list_coord = (823, 546)     

    ss_folder_quick_check = Path("./QuickCheck_PartNumber_Screenshots") 
    ss_folder_quick_check.mkdir(exist_ok=True) 
    
    try:
        update_status("Ensure CDA 'Read/Write Data By Identifier' screen is active and list is populated.") 
        pyautogui.click(read_write_data_softkey_coord)
        time.sleep(5)  
        pyautogui.click(first_item_in_list_coord)
        time.sleep(5)     

        for i in range(89):  
            if not (app_instance.worker_thread and app_instance.worker_thread.is_alive()): 
                update_status(f"Quick PN Check aborted at step {i+1} (worker thread stopped).") 
                raise InterruptedError("Worker thread stopped during Quick PN Check") 
            update_status(f"Quick Check PNs Step {i+1}/89") 
            pyautogui.press("pagedown"); time.sleep(1)     
            try:
                pyautogui.screenshot(str(ss_folder_quick_check / f"QuickCheck_PN_{i+1}_A_{datetime.now().strftime('%H%M%S')}.png")) 
            except Exception as e_ss: 
                update_status(f"Warning: Screenshot A for PN step {i+1} failed: {e_ss}") 
            
            pyautogui.press("down")
            time.sleep(0.2)  
            pyautogui.press("enter")
            time.sleep(1)  
            try:
                pyautogui.screenshot(str(ss_folder_quick_check / f"QuickCheck_PN_{i+1}_B_{datetime.now().strftime('%H%M%S')}.png")) 
            except Exception as e_ss: 
                update_status(f"Warning: Screenshot B for PN step {i+1} failed: {e_ss}") 
            time.sleep(0.2) 
        update_status("Quick Part Number Check Finished.")
        return True 
    except InterruptedError: # Catch specific interruption 
        return False 
    except Exception as e: 
        update_status(f"ERROR during Quick Part Number Check: {e}") 
        update_status(traceback.format_exc()) 
        return False 
# --- End Main Test Sequence Orchestration ---

# --- Worker Thread Functions ---
def automation_worker(app_instance, username, password, test_type, cycles):  
    global power_supply_serial # Ensure we interact with the global handle 
    app_instance.power_supply_serial_handle = None # Thread-local copy for its lifecycle management 
    success = False 
    operation_mode = app_instance.operation_mode_var.get() 
    update_status(f"Automation worker started: Mode={operation_mode}, Test={test_type}") 
    try:
        update_status("--- Setting up Power Supply ---") 
        # Use ps_connectSerial which sets the global power_supply_serial
        # and assign it to the instance handle for this worker's context
        app_instance.power_supply_serial_handle = ps_connectSerial()  
        if not app_instance.power_supply_serial_handle : 
            raise RuntimeError("PS Connect failed.") 
        # Pass the handle (which is the global one now) to ps_setVolt and ps_on
        if not ps_setVolt(app_instance.power_supply_serial_handle, 13.5): 
            raise RuntimeError("PS Set Volt failed.") 
        ps_on(app_instance.power_supply_serial_handle)
        time.sleep(2) 
        
        if operation_mode == "CDA": 
            update_status("--- CDA Setup ---") 
            if not openCDA(operation_mode): raise RuntimeError("Open CDA failed.") 
            if not loginCDA(operation_mode, username, password): 
                raise RuntimeError("CDA Login failed.") 
            if not deviceConnection(operation_mode): 
                raise RuntimeError("CDA Device Connect failed.") 
        elif operation_mode == "Direct CAN": 
            if not app_instance.can_bus: 
                raise RuntimeError("Direct CAN: Bus not connected prior to starting sequence.") 
        else: 
            raise RuntimeError(f"Unknown operation mode: {operation_mode}") 
        
        update_status(f"--- Starting Test: {test_type} ---") 
        test_func = app_instance.main_test_map.get(test_type) 
        if test_func: 
            if test_type == "Camera Test Patterns":  
                success = test_func(app_instance, cycles)  
            else:
                success = test_func(app_instance) 
        else: 
            update_status(f"ERROR: Test '{test_type}' not implemented or mapped.")
            success = False 
    except Exception as e: 
        update_status(f"ERROR in automation_worker: {type(e).__name__}: {e}"); update_status(traceback.format_exc())
        success = False 
    finally:
        # Use the instance handle for cleanup within this worker's scope
        if hasattr(app_instance, 'power_supply_serial_handle') and app_instance.power_supply_serial_handle and app_instance.power_supply_serial_handle.is_open: 
            update_status("--- Cleaning up PS (automation_worker) ---") 
            ps_off(app_instance.power_supply_serial_handle)
            time.sleep(0.5) 
            update_status("PS Off called by automation worker.") 
        
        app_instance.last_run_success = success 
        update_status("--- Automation FINISHED" + (" successfully" if success else " (with errors/failed)") + " ---") 

def run_queue_worker(app_instance, test_queue_items): 
    global power_supply_serial # Ensure we interact with the global handle 
    app_instance.power_supply_serial_handle = None  
    success = True 
    operation_mode = app_instance.operation_mode_var.get() 
    update_status(f"Queue worker started: Mode={operation_mode}, Items={len(test_queue_items)}") 
    try:
        update_status("--- Setting up Power Supply for Queue ---") 
        app_instance.power_supply_serial_handle = ps_connectSerial() 
        if not app_instance.power_supply_serial_handle: 
            raise RuntimeError("PS Connect failed for queue.") 
        if not ps_setVolt(app_instance.power_supply_serial_handle, 13.5): 
            raise RuntimeError("PS Set Volt failed for queue.") 
            ps_on(app_instance.power_supply_serial_handle)
            time.sleep(2) 
        
        if operation_mode == "CDA": update_status("Info: Assuming CDA ready & unlocked for queue.") 
        elif operation_mode == "Direct CAN": 
            if not app_instance.can_bus: 
                raise RuntimeError("Direct CAN: Bus not connected for queue.") 
            update_status("Info: Assuming ECU unlocked for Direct CAN queue.") 
            
        update_status(f"--- Starting Test Queue ({len(test_queue_items)} items) ---") 
        for i, item_data in enumerate(test_queue_items): 
            item_id, item_name, item_did_val = item_data.get('id','N/A'), item_data.get('name','N/A'), item_data.get('did') 
            update_status(f"Run Item {i+1}/{len(test_queue_items)}: [{item_id}] {item_name}") 
            item_success_flag = False 
            if item_did_val: 
                if callable(item_did_val):  
                    func_name = item_did_val.__name__ if hasattr(item_did_val, '__name__') else 'lambda_action' 
                    # Special handling for camera test to pass cycles, default to 1 for queue
                    if func_name == "perform_camera_test_patterns_main_sequence": 
                         item_success_flag = item_did_val(app_instance, 1) # Default to 1 cycle for queue items 
                    else:
                         item_success_flag = item_did_val(app_instance) 
                else: 
                    item_success_flag = send_DID(app_instance, str(item_did_val)) 
                if not item_success_flag: 
                    update_status(f"ERROR: Step '{item_id} - {item_name}' failed. Stopping queue.")
                    success = False
                    break 
            else: 
                update_status(f"Skipping: Test '{item_name}' ({item_id}) has no DID/action.")
                item_success_flag = True 
            
            if hasattr(app_instance, 'worker_thread_stop_event') and app_instance.worker_thread_stop_event.is_set(): 
                 update_status("Queue execution prematurely stopped by user/system.")
                 success=False
                 break 
            time.sleep(0.1)  
    except Exception as e: 
        update_status(f"ERROR during Queue worker: {type(e).__name__}: {e}")
        update_status(traceback.format_exc())
        success = False 
    finally:
        if hasattr(app_instance, 'power_supply_serial_handle') and app_instance.power_supply_serial_handle and app_instance.power_supply_serial_handle.is_open:
            update_status("--- Cleaning up PS (run_queue_worker) ---")
            ps_off(app_instance.power_supply_serial_handle)
            time.sleep(0.5) 
            update_status("PS Off called by queue worker.") 
        
        app_instance.last_run_success = success 
        update_status("--- Test Queue FINISHED" + (" successfully" if success else " (with errors/stopped)") + " ---") 

def send_and_monitor_worker(app_instance, did_to_send_hex, ecu_req_id_hex, ecu_resp_id_hex, monitor_duration_seconds): 
    if not app_instance.can_bus: 
        update_status("ERROR: Direct CAN: Bus not connected."); update_status("--- Direct Send & Monitor FINISHED ---")
        return 

    try: 
        ecu_request_id_val = int(ecu_req_id_hex.replace(" ",""), 16) 
        if not (0 <= ecu_request_id_val <= 0x1FFFFFFF): 
            raise ValueError("ECU Req ID out of 29-bit range.") 
    except Exception as e: 
        update_status(f"ERROR: Invalid ECU Req ID '{ecu_req_id_hex}': {e}"); update_status("--- Direct Send & Monitor FINISHED ---")
        eturn 

    parsed_ecu_resp_id_val = None 
    if ecu_resp_id_hex:  
        try:
            parsed_ecu_resp_id_val = int(ecu_resp_id_hex.replace(" ",""), 16) 
            if not (0 <= parsed_ecu_resp_id_val <= 0x1FFFFFFF): 
                update_status(f"Warning: ECU Resp ID '{ecu_resp_id_hex}' out of range. Will monitor all IDs."); parsed_ecu_resp_id_val = None 
        except ValueError: 
            update_status(f"Warning: Invalid ECU Resp ID '{ecu_resp_id_hex}'. Will monitor all IDs."); parsed_ecu_resp_id_val = None 
    
    try: 
        payload_str_cleaned = did_to_send_hex.replace(" ", "").replace("0x", "", 1).replace("0X", "", 1) 
        payload_bytes_data = bytes.fromhex(payload_str_cleaned) if payload_str_cleaned else b'' 
    except ValueError: 
        update_status(f"ERROR: Invalid DID payload hex: '{did_to_send_hex}'"); update_status("--- Direct Send & Monitor FINISHED ---")
        return 

    is_extended_flag = ecu_request_id_val > 0x7FF 
    tx_message = can.Message(arbitration_id=ecu_request_id_val, data=payload_bytes_data, is_extended_id=is_extended_flag) 

    # Send TX message with integrated logging (already present and verified from previous session)
    timestamp_tx = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] 
    log_entry_tx = "" 
    try:
        arb_id_tx = tx_message.arbitration_id; is_ext_tx = tx_message.is_extended_id 
        dlc_tx = tx_message.dlc; data_bytes_tx = tx_message.data 
        id_hex_str_tx = f"{arb_id_tx:08X}" if is_ext_tx else f"{arb_id_tx:03X}" 
        data_hex_parts_tx = [f"{b:02X}" for b in data_bytes_tx] if data_bytes_tx is not None else [] 
        data_hex_str_tx = ' '.join(data_hex_parts_tx) 
        log_entry_tx = f"{timestamp_tx} | [CAN Direct Send TX] | ID: {id_hex_str_tx} | DL: {dlc_tx} | Data: {data_hex_str_tx}" 
        log_can_message_to_file(log_entry_rx) #  FOR RX LOGGING
    except Exception as e_fmt_tx: # Catch any formatting error for TX 
        update_status(f"TX log formatting error for {repr(tx_message)}: {e_fmt_tx}") 
        log_entry_tx = f"{timestamp_tx} | TX_ERROR_FMT | {repr(tx_message)}" 
    update_status(log_entry_tx) 

    try: 
        app_instance.can_bus.send(tx_message, timeout=0.5) 
    except can.CanError as e: 
        update_status(f"ERROR: CAN Send Error: {e}")
        update_status("--- Direct Send & Monitor FINISHED ---")
        return 
    except Exception as e: 
        update_status(f"ERROR: Unexpected CAN send error: {e}")
        update_status("--- Direct Send & Monitor FINISHED ---")
        return 

    log_msg_monitor = f"Monitoring RX for {monitor_duration_seconds:.1f} seconds..." 
    if parsed_ecu_resp_id_val is not None: log_msg_monitor += f" Highlighting ID {parsed_ecu_resp_id_val:#X}." 
    else: log_msg_monitor += " (All IDs)." 
    update_status(log_msg_monitor) 
    
    start_time_monitor = time.monotonic(); received_msg_count = 0; highlighted_msg_count = 0 
    try:
        while (time.monotonic() - start_time_monitor) < monitor_duration_seconds: 
            if hasattr(app_instance, 'worker_thread') and \
               app_instance.worker_thread is not None and \
               app_instance.worker_thread.is_alive() and \
               threading.current_thread().name != app_instance.worker_thread.name : # Ensure it's not self-stopping 
                 update_status("Warning: New primary task started, stopping current Direct Send & Monitor RX.") 
                 break 

            rx_can_message = app_instance.can_bus.recv(timeout=0.8) # Short timeout to remain responsive 
            if rx_can_message is not None: 
                received_msg_count += 1 
                timestamp_rx = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] 
                log_entry_rx = "" 
                log_prefix_str = "[CAN Direct RX]" 
                
                # <<< INTEGRATED CAN RX LOGGING (from previous session, verified) START >>>
                try:
                    arb_id_rx = rx_can_message.arbitration_id 
                    is_ext_rx = rx_can_message.is_extended_id 
                    dlc_rx = rx_can_message.dlc 
                    data_bytes_rx = rx_can_message.data 

                    id_hex_str_rx = f"{arb_id_rx:08X}" if is_ext_rx else f"{arb_id_rx:03X}" 
                    
                    data_hex_parts_rx = [] 
                    if data_bytes_rx is not None: 
                        for byte_val_rx in data_bytes_rx: 
                            data_hex_parts_rx.append(f"{byte_val_rx:02X}") 
                    data_hex_str_rx = ' '.join(data_hex_parts_rx) 

                    if parsed_ecu_resp_id_val is not None and rx_can_message.arbitration_id == parsed_ecu_resp_id_val: 
                        log_prefix_str = "[CAN Direct RX MATCH]" 
                        highlighted_msg_count +=1 
                    
                    log_entry_rx = f"{timestamp_rx} | {log_prefix_str} | ID: {id_hex_str_rx} | DL: {dlc_rx} | Data: {data_hex_str_rx}" 

                except ValueError as ve_rx: 
                    if "format string" in str(ve_rx).lower(): 
                        err_detail_rx = (f"RX FORMAT ValueError (Invalid format string) Details:\n" 
                                         f"  Timestamp: {timestamp_rx}\n"
                                         f"  Arb ID: {repr(rx_can_message.arbitration_id)}\n"
                                         f"  Is Extended: {repr(rx_can_message.is_extended_id)}\n"
                                         f"  DLC: {repr(rx_can_message.dlc)}\n"
                                         f"  Data: {repr(rx_can_message.data)}\n"
                                         f"  Exception: {ve_rx}")
                        update_status(err_detail_rx) 
                        log_entry_rx = f"{timestamp_rx} | RX_FALLBACK | ID: {str(rx_can_message.arbitration_id)} | DLC: {str(rx_can_message.dlc)} | Data: {str(list(rx_can_message.data if rx_can_message.data is not None else []))}" 
                    else:
                        update_status(f"RX Other ValueError: {ve_rx}. Msg: {repr(rx_can_message)}") 
                        log_entry_rx = f"{timestamp_rx} | RX_ERROR_VAL | {ve_rx}" 
                except TypeError as te_rx: 
                    err_detail_rx = (f"RX FORMAT TypeError Details:\n" 
                                     f"  Timestamp: {timestamp_rx}\n"
                                     f"  Arb ID: {repr(rx_can_message.arbitration_id)}\n"
                                     f"  Is Extended: {repr(rx_can_message.is_extended_id)}\n"
                                     f"  DLC: {repr(rx_can_message.dlc)}\n"
                                     f"  Data: {repr(rx_can_message.data)}\n"
                                     f"  Exception: {te_rx}")
                    update_status(err_detail_rx) 
                    log_entry_rx = f"{timestamp_rx} | RX_FALLBACK_TE | ID: {str(rx_can_message.arbitration_id)} | DLC: {str(rx_can_message.dlc)} | Data: {str(list(rx_can_message.data if rx_can_message.data is not None else []))}" 
                except Exception as e_fmt_rx: 
                    error_msg_rx = f"RX log formatting error for msg {repr(rx_can_message)}: {type(e_fmt_rx).__name__}: {e_fmt_rx}" 
                    update_status(error_msg_rx) 
                    log_entry_rx = f"{timestamp_rx} | RX_ERROR_FMT | {error_msg_rx}" 
                # <<< INTEGRATED CAN RX LOGGING (from previous session, verified) END >>>
                update_status(log_entry_rx) 
    except Exception as e: update_status(f"ERROR during CAN receive loop: {e}"); update_status(traceback.format_exc()) 

    if received_msg_count == 0: 
        update_status(f"No messages received during {monitor_duration_seconds:.1f}s monitoring.") 
    else: update_status(f"Finished monitoring. Received {received_msg_count} message(s).") 
    if parsed_ecu_resp_id_val and highlighted_msg_count > 0: 
        update_status(f"Found {highlighted_msg_count} message(s) matching expected Resp ID {parsed_ecu_resp_id_val:#X}.") 
    update_status("--- Direct Send & Monitor FINISHED ---") # This signals enable_buttons 
# --- End Worker Functions ---

# --- GUI Class ---
class App: 
    
    def update_dbc_message_dropdown(self):
        """Refreshes the DBC message sender dropdown with messages from the loaded db."""
        if not hasattr(self, 'dbc_message_combo') or dbc_db is None:
            return
        
        try:
            # Get a sorted list of message names from the database
            message_names = sorted([msg.name for msg in dbc_db.messages])
            self.dbc_message_combo['values'] = message_names
            if message_names:
                self.dbc_message_combo.current(0)
            self.log_to_status(f"Updated DBC message sender with {len(message_names)} messages.")
        except Exception as e:
            self.log_to_status(f"Error updating DBC message dropdown: {e}")

    def open_dbc_send_dialog(self):
        """Opens a new window to edit and send a selected DBC message."""
        if dbc_db is None:
            messagebox.showerror("DBC Error", "No DBC database is loaded.", parent=self.root)
            return
            
        selected_message_name = self.dbc_message_var.get()
        if not selected_message_name:
            messagebox.showerror("Selection Error", "Please select a message from the dropdown.", parent=self.root)
            return

        try:
            message_obj = dbc_db.get_message_by_name(selected_message_name)
        except KeyError:
            messagebox.showerror("Error", f"Could not find message '{selected_message_name}' in the database.", parent=self.root)
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Send {message_obj.name}")
        dialog.transient(self.root)
        dialog.grab_set()

        signal_entries = {}
        for i, signal in enumerate(message_obj.signals):
            ttk.Label(dialog, text=f"{signal.name}:").grid(row=i, column=0, padx=5, pady=5, sticky="e")
            entry = ttk.Entry(dialog, width=25)
            entry.insert(0, "0")
            entry.grid(row=i, column=1, padx=5, pady=5)
            signal_entries[signal.name] = entry

        def on_dialog_send():
            if not self.can_bus:
                messagebox.showerror("CAN Error", "Direct CAN: Bus not connected.", parent=dialog)
                return

            signal_data_dict = {}
            try:
                for sig_name, entry_widget in signal_entries.items():
                    signal_data_dict[sig_name] = float(entry_widget.get())
            except ValueError as e:
                messagebox.showerror("Input Error", f"Invalid number entered for a signal.\n\nError: {e}", parent=dialog)
                return

            try:
                data_bytes = message_obj.encode(signal_data_dict)
                
                # --- FIX: Check if the message is CAN FD ---
                is_fd_frame = (hasattr(message_obj, 'protocol') and message_obj.protocol == 'can-fd')

                # Create the can.Message object, setting the is_fd flag correctly
                msg_to_send = can.Message(
                    arbitration_id=message_obj.frame_id,
                    data=data_bytes,
                    is_extended_id=message_obj.is_extended_frame,
                    is_fd=is_fd_frame # This tells python-can to use a CAN FD frame if needed
                )
                
                self.can_bus.send(msg_to_send)
                
                id_hex_display = f"{msg_to_send.arbitration_id:08X}" if msg_to_send.is_extended_id else f"{msg_to_send.arbitration_id:03X}"
                log_entry = f"[DBC TX] | ID: {id_hex_display} | DL: {msg_to_send.dlc} | Data: {' '.join(f'{b:02X}' for b in msg_to_send.data)}"
                self.log_to_status(log_entry)
                self.log_to_status(f"  └ Sent Signals: {signal_data_dict}")

                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Send Error", f"Failed to encode or send message:\n\n{e}", parent=dialog)
                self.log_to_status(f"DBC Send Error: {traceback.format_exc()}")

        send_button = ttk.Button(dialog, text="Send Message", command=on_dialog_send)
        send_button.grid(row=len(message_obj.signals), column=0, columnspan=2, padx=10, pady=10)
    
    def validate_hex_with_space(self, P_value): 
        return all(c in '0123456789abcdefABCDEF ' for c in P_value) or P_value == "" 
        
    def on_connect_can_click(self): 
        if self.can_bus: 
            self.log_to_status("CAN already connected.")
            return 
        self.set_can_config_fields_state(tk.DISABLED) 
        self.connect_can_button.config(state=tk.DISABLED) 
        if hasattr(self, 'disconnect_can_button'): 
            self.disconnect_can_button.config(state=tk.DISABLED) 
        if hasattr(self, 'send_monitor_button'): 
            self.send_monitor_button.config(state=tk.DISABLED) 
        self.root.update_idletasks() 

        if self.initialize_can(): # This updates can_bus and status label 
            self.set_can_config_fields_state(tk.DISABLED) # Keep config disabled after successful connect 
            self.connect_can_button.config(state=tk.DISABLED) 
            if hasattr(self, 'disconnect_can_button'): 
                self.disconnect_can_button.config(state=tk.NORMAL) 
            if hasattr(self, 'send_monitor_button'):
                self.send_monitor_button.config(state=tk.NORMAL) 
        else: # Connection failed 
            self.set_can_config_fields_state(tk.NORMAL) # Re-enable config fields 
            self.connect_can_button.config(state=tk.NORMAL) 

    def on_disconnect_can_click(self): 
        self.shutdown_can() # This updates can_bus and status label 
        self.set_can_config_fields_state(tk.NORMAL) 
        self.connect_can_button.config(state=tk.NORMAL) 
        if hasattr(self, 'disconnect_can_button'): 
            self.disconnect_can_button.config(state=tk.DISABLED) 
        if hasattr(self, 'send_monitor_button'): 
            self.send_monitor_button.config(state=tk.DISABLED) 
   
    def load_sent_dids(self):
        """Loads the list of sent DIDs from the JSON file."""
        try:
            with open(SAVED_DIDS_FILE, 'r') as f:
                import json
                # Ensure we load a list, not a dictionary or other type
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (FileNotFoundError, json.JSONDecodeError):
            return [] # Return an empty list if file doesn't exist or is invalid

    def persist_sent_dids(self):
        """Saves the current DID history list to the JSON file."""
        try:
            with open(SAVED_DIDS_FILE, 'w') as f:
                import json
                json.dump(self.sent_dids_history, f, indent=4)
        except Exception as e:
            # Don't show a popup, just log to status to avoid being intrusive
            update_status(f"ERROR: Could not save DID history: {e}")

    def update_did_history_dropdown(self):
        """Refreshes the Combobox with the current list of saved DIDs."""
        if hasattr(self, 'did_history_combo'):
            # Sort for consistency, but you could keep original order if preferred
            self.did_history_combo['values'] = sorted(self.sent_dids_history)

    def on_save_current_did_click(self):
        """Manually saves the DID currently in the 'DID to Send' entry box."""
        did_to_save = self.direct_can_did_to_send_var.get().strip()
        if not did_to_save:
            messagebox.showwarning("Input Empty", "The 'DID to Send' box is empty.", parent=self.root)
            return
            
        if did_to_save not in self.sent_dids_history:
            self.sent_dids_history.append(did_to_save)
            self.persist_sent_dids()
            self.update_did_history_dropdown()
            update_status(f"Manually saved DID to history: {did_to_save}")
        else:
            update_status(f"Info: DID '{did_to_save}' is already in the history.")

    def on_load_saved_did_click(self):
        """Loads the selected DID from the history dropdown into the entry box."""
        selected_did = self.saved_did_var.get()
        if selected_did:
            self.direct_can_did_to_send_var.set(selected_did)
            update_status(f"Loaded DID from history: {selected_did}")
        else:
            messagebox.showwarning("Selection Empty", "Please select a DID from the history dropdown.", parent=self.root)

    def on_delete_saved_did_click(self):
        """Deletes the selected DID from the history."""
        selected_did = self.saved_did_var.get()
        if not selected_did:
            messagebox.showwarning("Selection Empty", "Please select a DID from the history dropdown to delete.", parent=self.root)
            return

        if selected_did in self.sent_dids_history:
            if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{selected_did}' from the history?", parent=self.root):
                self.sent_dids_history.remove(selected_did)
                self.persist_sent_dids()
                self.saved_did_var.set("") # Clear the selection
                self.update_did_history_dropdown()
                update_status(f"Deleted DID from history: {selected_did}")
    
    def on_send_custom_can_click(self):
        """Assembles and sends a custom CAN message from the GUI inputs."""
        if not self.can_bus:
            messagebox.showerror("CAN Error", "Direct CAN: Bus not connected.")
            return

        try:
            # Read and validate the CAN ID
            can_id_str = self.custom_can_id_var.get().strip()
            if not can_id_str: raise ValueError("CAN ID cannot be empty.")
            can_id = int(can_id_str, 16)

            # Read and validate each byte entry
            payload = []
            for i, byte_var in enumerate(self.custom_byte_vars):
                byte_str = byte_var.get().strip()
                if not byte_str: # If a byte is empty, treat as 00
                    payload.append(0)
                    continue
                if len(byte_str) > 2 or not all(c in '0123456789abcdefABCDEF' for c in byte_str):
                    raise ValueError(f"Invalid hex value for Byte {i}: '{byte_str}'")
                payload.append(int(byte_str, 16))
            
            # Remove trailing zeros for correct DLC, but only if user left them empty
            # Find the last non-zero byte to determine the actual payload length
            dlc = 8
            for i in range(7, -1, -1):
                if self.custom_byte_vars[i].get().strip() != "":
                    dlc = i + 1
                    break
            else: # If all fields are empty
                dlc = 0
            
            final_payload = payload[:dlc]

        except ValueError as e:
            messagebox.showerror("Input Error", f"Invalid input for Custom CAN message. {e}")
            return

        # Construct and send the message
        is_extended = can_id > 0x7FF
        msg_to_send = can.Message(arbitration_id=can_id, data=final_payload, is_extended_id=is_extended)
        
        try:
            self.can_bus.send(msg_to_send)
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            id_hex_display = f"{msg_to_send.arbitration_id:08X}" if msg_to_send.is_extended_id else f"{msg_to_send.arbitration_id:03X}"
            log_entry = f"{timestamp} | [Custom TX] | ID: {id_hex_display} | DL: {msg_to_send.dlc} | Data: {' '.join(f'{b:02X}' for b in msg_to_send.data)}"
            
            update_status(log_entry)
            log_can_message_to_file(log_entry)
        except can.CanError as e:
            messagebox.showerror("CAN Send Error", f"Error sending CAN message: {e}")
            update_status(f"TX Error: {e}")

    def save_custom_message(self):
        """Saves the current custom CAN message configuration to a JSON file."""
        message_name = simpledialog.askstring("Save Custom Message", "Enter a name for this message:", parent=self.root)
        if not message_name:
            return

        current_id = self.custom_can_id_var.get().strip()
        current_data = [var.get().strip() for var in self.custom_byte_vars]

        if not current_id:
            messagebox.showwarning("Incomplete", "CAN ID must be filled to save a message.")
            return

        all_messages = self.load_all_custom_messages()
        if message_name in all_messages and not messagebox.askyesno("Overwrite?", f"A message named '{message_name}' already exists. Overwrite it?"):
            return
            
        all_messages[message_name] = {
            "id": current_id,
            "data": current_data
        }
        
        try:
            with open(CUSTOM_MESSAGES_FILE, 'w') as f:
                import json
                json.dump(all_messages, f, indent=4)
            update_status(f"Saved custom message: '{message_name}'")
            self.update_custom_messages_dropdown()
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save custom messages: {e}")

    def load_custom_message(self):
        """Loads a saved custom message into the entry fields."""
        selected_name = self.custom_message_var.get()
        if not selected_name:
            messagebox.showwarning("Selection Error", "No custom message selected from the dropdown.")
            return

        all_messages = self.load_all_custom_messages()
        message_data = all_messages.get(selected_name)

        if message_data:
            self.custom_can_id_var.set(message_data.get("id", ""))
            data_bytes = message_data.get("data", [])
            for i, byte_var in enumerate(self.custom_byte_vars):
                if i < len(data_bytes):
                    byte_var.set(data_bytes[i])
                else:
                    byte_var.set("") # Clear any extra fields
            update_status(f"Loaded custom message: '{selected_name}'")
        else:
            messagebox.showerror("Load Error", f"Could not find data for '{selected_name}'.")

    def delete_custom_message(self):
        """Deletes the selected custom message."""
        selected_name = self.custom_message_var.get()
        if not selected_name:
            messagebox.showwarning("Selection Error", "No custom message selected to delete.")
            return
            
        all_messages = self.load_all_custom_messages()
        if selected_name in all_messages and messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{selected_name}'?"):
            del all_messages[selected_name]
            try:
                with open(CUSTOM_MESSAGES_FILE, 'w') as f:
                    import json
                    json.dump(all_messages, f, indent=4)
                update_status(f"Deleted custom message: '{selected_name}'")
                self.custom_message_var.set("") # Clear selection
                self.update_custom_messages_dropdown()
            except Exception as e:
                messagebox.showerror("Delete Error", f"Could not update saved messages: {e}")

    def load_all_custom_messages(self):
        """Helper to load all saved messages from the JSON file."""
        try:
            with open(CUSTOM_MESSAGES_FILE, 'r') as f:
                import json
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {} # Return empty dict if file doesn't exist or is invalid

    def update_custom_messages_dropdown(self):
        """Refreshes the dropdown with the latest list of saved messages."""
        all_messages = self.load_all_custom_messages()
        self.custom_message_combo['values'] = sorted(list(all_messages.keys()))
 
    def __init__(self, root_tk): 
        self.root = root_tk 
        self.root.title("Field Functional Tester (FFT) - Stellantis") 
        self.root.geometry("1700x900") # Increased height slightly for PS controls 

        self.can_bus = None 
        self.worker_thread = None 
        self.last_run_success = None 
        self.sent_dids_history = self.load_sent_dids()
        self.available_tests = [] 
        self.test_queue = [] 
        self.main_test_map = { 
            "Full EOL Sequence": run_complete_eol_test_sequence,
            "Part Numbers (All)": perform_all_part_number_reads_sequence,
            "Camera Test Patterns": perform_camera_test_patterns_main_sequence,
            "DTC Checks": test_dtc_checks,
            "Quick Check PNs (CDA)": CheckPartNumbers_Quick 
        }

        style = ttk.Style()  
        style.theme_use('vista')  
        DEFAULT_BG, ACTIVE_BG, DISABLED_BG, SUCCESS_BG, FAIL_BG = '#E1E1E1', '#B0C4DE', '#D3D3D3', '#90EE90', '#FFA07A'  
        BTN_FONT = ('Segoe UI', 10)
        ACCENT_STYLE='Accent.TButton'
        SUCCESS_STYLE='Success.TButton'
        FAIL_STYLE='Fail.TButton'  
        style.configure('.', font=('Segoe UI', 9))  
        style.configure('TButton', font=BTN_FONT, padding=5)  
        style.configure('Accent.TButton', font=(BTN_FONT[0], BTN_FONT[1], 'bold'), background=DEFAULT_BG)
        style.map('Accent.TButton', background=[('active', ACTIVE_BG), ('disabled', DISABLED_BG)])  
        style.configure('Success.TButton', font=(BTN_FONT[0], BTN_FONT[1], 'bold'), background=SUCCESS_BG)
        style.map('Success.TButton', background=[('active', '#79D879'), ('disabled', DISABLED_BG)])  
        style.configure('Fail.TButton', font=(BTN_FONT[0], BTN_FONT[1], 'bold'), background=FAIL_BG)
        style.map('Fail.TButton', background=[('active', '#EFA07A'), ('disabled', DISABLED_BG)])  
        style.configure('Toolbutton', font=('Segoe UI', 9))  

        self.notebook = ttk.Notebook(self.root)  
        self.notebook.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)  

        self.tab1 = ttk.Frame(self.notebook, padding=10)  
        self.notebook.add(self.tab1, text=' Main Control ')  
        self.create_main_control_tab(self.tab1)  

        self.tab2 = ttk.Frame(self.notebook, padding=10)  
        self.notebook.add(self.tab2, text=' Test Sequencer ')  
        self.create_test_sequencer_tab(self.tab2)  
        
        self.tab3 = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab3, text=' TX CAN Msg Sender ')
        self.create_custom_can_sender_tab(self.tab3)

        status_frame = ttk.LabelFrame(self.root, text="Status / Output", padding=(10, 5))  
        status_frame.pack(padx=10, pady=(0, 10), fill=tk.BOTH, expand=True)  
        self.status_text = scrolledtext.ScrolledText(status_frame, height=16, wrap=tk.WORD, state=tk.DISABLED, font=('Consolas', 9), relief=tk.SUNKEN, borderwidth=1)  
        self.status_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)  

        self.update_status_display()  
        self.load_and_parse_tests()  
        self.on_mode_change()  
        self.update_can_status_label()  
        self.update_ps_button_states() # Initialize PS button states 
        self.update_camera_button_states() # 
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)  
    
    def create_custom_can_sender_tab(self, parent_tab):
        """Creates the GUI elements for the custom CAN message sender."""
        
        # --- Main Frame for the Tab ---
        main_frame = ttk.Frame(parent_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # --- DBC Message Sender Frame ---
        dbc_sender_frame = ttk.LabelFrame(main_frame, text="DBC Message Sender", padding=10)
        dbc_sender_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(dbc_sender_frame, text="Select Message:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.dbc_message_var = tk.StringVar()
        self.dbc_message_combo = ttk.Combobox(dbc_sender_frame, textvariable=self.dbc_message_var, width=50, state='readonly')
        self.dbc_message_combo.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        edit_send_button = ttk.Button(dbc_sender_frame, text="Edit & Send...", command=self.open_dbc_send_dialog, style='Accent.TButton')
        edit_send_button.grid(row=0, column=2, padx=10, pady=5)
        
        dbc_sender_frame.columnconfigure(1, weight=1)

        # --- Manual Message Configuration Frame ---
        config_frame = ttk.LabelFrame(main_frame, text="Manual Message Sender", padding=10)
        config_frame.pack(fill=tk.X, pady=(0, 10))

        # --- Message Configuration Frame ---
        config_frame = ttk.LabelFrame(main_frame, text="Message Configuration", padding=10)
        config_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(config_frame, text="CAN ID (Hex):").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.custom_can_id_var = tk.StringVar(value="123")
        id_entry = ttk.Entry(config_frame, textvariable=self.custom_can_id_var, width=12)
        id_entry.grid(row=0, column=1, padx=5, pady=5)

        # Frame for the byte entries
        bytes_frame = ttk.Frame(config_frame)
        bytes_frame.grid(row=1, column=0, columnspan=10, pady=10)
        
        ttk.Label(bytes_frame, text="Data (Hex):").pack(side=tk.LEFT, padx=(0, 10))
        
        self.custom_byte_vars = []
        for i in range(8):
            ttk.Label(bytes_frame, text=f"B{i}").pack(side=tk.LEFT, padx=(5,1))
            var = tk.StringVar()
            self.custom_byte_vars.append(var)
            entry = ttk.Entry(bytes_frame, textvariable=var, width=4)
            entry.pack(side=tk.LEFT)

        # Send Button
        self.custom_send_button = ttk.Button(config_frame, text="Send Custom Message", command=self.on_send_custom_can_click, style='Accent.TButton')
        self.custom_send_button.grid(row=2, column=0, columnspan=10, pady=10, sticky=tk.EW)

        # --- Saved Messages Frame ---
        saved_frame = ttk.LabelFrame(main_frame, text="Saved Messages", padding=10)
        saved_frame.pack(fill=tk.X, pady=10)

        ttk.Label(saved_frame, text="Recall Message:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.E)
        self.custom_message_var = tk.StringVar()
        self.custom_message_combo = ttk.Combobox(saved_frame, textvariable=self.custom_message_var, width=40, postcommand=self.update_custom_messages_dropdown, state='readonly')
        self.custom_message_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)

        load_button = ttk.Button(saved_frame, text="Load", command=self.load_custom_message, style='Toolbutton.TButton')
        load_button.grid(row=0, column=2, padx=5, pady=5)

        delete_button = ttk.Button(saved_frame, text="Delete", command=self.delete_custom_message, style='Toolbutton.TButton')
        delete_button.grid(row=0, column=3, padx=5, pady=5)

        save_button = ttk.Button(saved_frame, text="Save Current Message", command=self.save_custom_message)
        save_button.grid(row=1, column=1, columnspan=2, pady=10, sticky=tk.EW)
        
        saved_frame.columnconfigure(1, weight=1)

    def on_camera_connect_click(self):
        global camera_thread, stop_camera_thread_event
        if camera_thread and camera_thread.is_alive():
            update_status("Camera is already connected.")
            return

        if cv2 is None:
            messagebox.showerror("Dependency Error", "OpenCV (cv2) or Pillow (PIL) is not installed.")
            return
            
        try:
            cam_index = self.camera_index_var.get()
        except tk.TclError:
            update_status("ERROR: Invalid camera index.")
            return

        stop_camera_thread_event.clear()
        camera_thread = threading.Thread(target=camera_worker_thread, args=(self, cam_index), daemon=True)
        camera_thread.start()
        
        update_camera_feed_label(self)
        self.update_camera_button_states()

    def on_camera_disconnect_click(self):
        global camera_thread, stop_camera_thread_event
        if camera_thread and camera_thread.is_alive():
            update_status("Disconnecting camera...")
            stop_camera_thread_event.set()
            camera_thread.join(timeout=2)
        else:
            update_status("Camera is not currently connected.")
        
        self.update_camera_button_states()
        self.camera_feed_label.config(image='')

    def on_camera_screenshot_click(self):
        global latest_camera_frame
        if latest_camera_frame is None:
            messagebox.showwarning("No Image", "Camera not connected or no frame available to capture.")
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            save_path = Path("./") / filename
            
            cv2.imwrite(str(save_path), latest_camera_frame)
            update_status(f"Screenshot saved to: {save_path.resolve()}")
        except Exception as e:
            update_status(f"ERROR saving screenshot: {e}")

    def update_camera_button_states(self):
        # ... (code for this method as provided previously)
        global camera_thread, cv2
        is_lib_missing = cv2 is None
        is_running = camera_thread and camera_thread.is_alive()

        connect_state = tk.DISABLED if is_running or is_lib_missing else tk.NORMAL
        disconnect_state = tk.NORMAL if is_running else tk.DISABLED
        screenshot_state = tk.NORMAL if is_running else tk.DISABLED
        index_state = tk.DISABLED if is_running or is_lib_missing else 'readonly'

    def on_send_did_click_from_dropdown(self):
        """Sends the DID selected from the dropdown menu, using the selected service prefix."""
        service_prefix = self.did_service_prefix_var.get()
        if not service_prefix:
            messagebox.showwarning("Input Error", "Please select a service prefix (10, 22, etc.).", parent=self.root)
            return

        did_string_full = self.did_dropdown.get()
        if not did_string_full:
            messagebox.showwarning("Input Error", "Please select a DID from the dropdown.", parent=self.root)
            return

        did_value = did_string_full.split(' - ')[0].strip()

        if did_value:
            # Check if the DID value has an even number of hex characters to be spaced.
            if len(did_value) % 2 == 0 and all(c in '0123456789abcdefABCDEF' for c in did_value.upper()):
                # Format any multi-byte DID with spaces (e.g., "F18C" -> "F1 8C", "FD1234" -> "FD 12 34")
                spaced_did = " ".join(did_value[i:i+2] for i in range(0, len(did_value), 2))
                full_did_command = f"{service_prefix} {spaced_did}"
            else:
                # For single-byte or oddly-formatted DIDs, use the original format
                full_did_command = f"{service_prefix} {did_value}"

            self.log_to_status(f"Sending from Dropdown: {full_did_command}")
            send_DID(self, full_did_command)
        else:
             messagebox.showwarning("Input Error", "Could not parse a valid DID from the selection.", parent=self.root)
    
    def process_can_message(self, msg):
        """Processes and logs an incoming CAN message, decoding it if DBC is loaded."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        id_hex_str = f"{msg.arbitration_id:08X}" if msg.is_extended_id else f"{msg.arbitration_id:03X}"
        data_hex_str = binascii.hexlify(msg.data).decode('utf-8').upper()

        log_entry = f"[{timestamp}] RX - ID: {id_hex_str} | DLC: {msg.dlc} | Data: {data_hex_str}"

        if dbc_db:
            try:
                # Use the integer arbitration_id and bytes data for decoding
                decoded_message = dbc_db.decode_message(msg.arbitration_id, msg.data)
                # Format the decoded signals nicely
                decoded_signals = ', '.join([f"{k}: {v}" for k, v in decoded_message.items()])
                log_entry += f"\n  └ Decoded: {decoded_signals}"
            except KeyError:
                # This is normal, means the ID is not in the DBC
                pass
            except Exception as e:
                # Log other potential decoding errors
                log_entry += f"\n  └ DBC Decode Error: {e}"

        self.log_to_status(log_entry)

    def create_main_control_tab(self, parent_tab): 
        top_config_row = ttk.Frame(parent_tab)
        top_config_row.pack(fill=tk.X, pady=(0,10)) 

        left_col_frame = ttk.Frame(top_config_row)
        left_col_frame.pack(side=tk.LEFT, padx=(0,5), fill=tk.Y, anchor=tk.NW) 
        
        cred_frame = ttk.LabelFrame(left_col_frame, text="Credentials (CDA)", padding=(10,5))
        cred_frame.pack(fill=tk.X, pady=(0,5)) 
        ttk.Label(cred_frame, text="Username:").grid(row=0, column=0, padx=5, pady=3, sticky=tk.W) 
        self.username_var = tk.StringVar(value=os.environ.get("CDA_USER", "YourUsername")) 
        self.username_entry = ttk.Entry(cred_frame, textvariable=self.username_var, width=20)
        self.username_entry.grid(row=0, column=1, padx=5, pady=3, sticky=tk.EW) 
        ttk.Label(cred_frame, text="Password:").grid(row=1, column=0, padx=5, pady=3, sticky=tk.W) 
        self.password_var = tk.StringVar(value=os.environ.get("CDA_PASS", "")) 
        self.password_entry = ttk.Entry(cred_frame, textvariable=self.password_var, show="*", width=20)
        self.password_entry.grid(row=1, column=1, padx=5, pady=3, sticky=tk.EW) 
        
        # --- DBC/CDD Frame --- 
        self.dbc_cdd_frame = ttk.LabelFrame(left_col_frame, text="File Support", padding=(10, 5))
        self.dbc_cdd_frame.pack(fill=tk.X, pady=(5,5), anchor='n')

        self.load_dbc_button = ttk.Button(self.dbc_cdd_frame, text="Load DBCs", command=lambda: load_dbc_files(self))
        self.load_dbc_button.pack(fill=tk.X, padx=5, pady=2)

        self.load_cdd_button = ttk.Button(self.dbc_cdd_frame, text="Load CDD", command=lambda: load_dids_from_cdd(self))
        self.load_cdd_button.pack(fill=tk.X, padx=5, pady=2)

        self.can_config_frame = ttk.LabelFrame(top_config_row, text="CAN Config (Direct CAN)", padding=(10,5))
        self.can_config_frame.pack(side=tk.LEFT, padx=(5,5), fill=tk.Y, anchor=tk.NW)

        
        mode_frame = ttk.LabelFrame(left_col_frame, text="Operation Mode", padding=(10,5)); mode_frame.pack(fill=tk.X, pady=(5,0))         
        self.operation_mode_var = tk.StringVar(value="Direct CAN")  
        self.cda_radio = ttk.Radiobutton(mode_frame, text="CDA (GUI)", variable=self.operation_mode_var, value="CDA", command=self.on_mode_change)
        self.cda_radio.pack(anchor=tk.W, padx=5, pady=2) 
        self.direct_can_radio = ttk.Radiobutton(mode_frame, text="Direct CAN", variable=self.operation_mode_var, value="Direct CAN", command=self.on_mode_change); self.direct_can_radio.pack(anchor=tk.W, padx=5, pady=2) 

        self.can_config_frame = ttk.LabelFrame(top_config_row, text="CAN Config (Direct CAN)", padding=(10,5))  
        self.can_config_frame.pack(side=tk.LEFT, padx=(5,5), fill=tk.Y, anchor=tk.NW) 
        
        # --- DID Sender Frame --- 
        self.did_sender_frame = ttk.LabelFrame(self.can_config_frame, text="CDD DID Sender", padding=(10, 5))
        self.did_sender_frame.grid(row=9, column=0, columnspan=3, padx=5, pady=(10,5), sticky="ew")

        # Add Service/Prefix Dropdown
        ttk.Label(self.did_sender_frame, text="Service:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.did_service_prefix_var = tk.StringVar()
        self.did_service_prefix_combo = ttk.Combobox(self.did_sender_frame, textvariable=self.did_service_prefix_var, width=8, state='readonly')
        self.did_service_prefix_combo['values'] = ['10', '11', '22', '2E']
        self.did_service_prefix_combo.set('22') # Default to Read DID
        self.did_service_prefix_combo.grid(row=0, column=1, padx=5, pady=2, sticky="w")

        # Existing DID Dropdown
        ttk.Label(self.did_sender_frame, text="Select DID:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.did_dropdown = ttk.Combobox(self.did_sender_frame, width=30, state='readonly')
        self.did_dropdown.grid(row=1, column=1, columnspan=2, padx=5, pady=2, sticky="ew")

        # Send Button
        self.send_did_button = ttk.Button(self.did_sender_frame, text="Send Selected DID", command=self.on_send_did_click_from_dropdown)
        self.send_did_button.grid(row=2, column=0, columnspan=3, padx=5, pady=(8,2), sticky="ew")

        # Column configuration to make the DID dropdown expand
        self.did_sender_frame.columnconfigure(1, weight=1)

        # --- DID History Frame ---
        did_history_frame = ttk.LabelFrame(top_config_row, text="DID History", padding=(10,5))
        did_history_frame.pack(side=tk.LEFT, padx=(5,5), fill=tk.Y, anchor=tk.NW)

        self.saved_did_var = tk.StringVar()
        self.did_history_combo = ttk.Combobox(did_history_frame, textvariable=self.saved_did_var, width=25, state='readonly', postcommand=self.update_did_history_dropdown)
        self.did_history_combo.pack(pady=5, padx=5)

        history_buttons_frame = ttk.Frame(did_history_frame)
        history_buttons_frame.pack(pady=5, padx=5, fill=tk.X)
        
        load_btn = ttk.Button(history_buttons_frame, text="Load", command=self.on_load_saved_did_click, style='Toolbutton.TButton', width=8)
        load_btn.pack(side=tk.LEFT, expand=True, padx=(0,2))
        
        save_btn = ttk.Button(history_buttons_frame, text="Save", command=self.on_save_current_did_click, style='Toolbutton.TButton', width=8)
        save_btn.pack(side=tk.LEFT, expand=True, padx=2)

        delete_btn = ttk.Button(history_buttons_frame, text="Delete", command=self.on_delete_saved_did_click, style='Toolbutton.TButton', width=8)
        delete_btn.pack(side=tk.LEFT, expand=True, padx=(2,0))
        ttk.Label(self.can_config_frame, text="Interface:").grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)
        self.can_interface_var = tk.StringVar(); interfaces = ['vector', 'pcan', 'kvaser', 'serial', 'socketcan', 'usb2can', 'ixxat', 'slcan', 'virtual']
        self.can_interface_combo = ttk.Combobox(self.can_config_frame, textvariable=self.can_interface_var, values=sorted(interfaces), width=16, state='readonly')
        self.can_interface_combo.grid(row=0, column=1, columnspan=2, padx=5, pady=2, sticky=tk.EW); self.can_interface_combo.set('vector')
       
        ttk.Label(self.can_config_frame, text="Channel:").grid(row=1, column=0, padx=5, pady=2, sticky=tk.W) 
        self.can_channel_var = tk.StringVar(value='0'); self.can_channel_entry = ttk.Entry(self.can_config_frame, textvariable=self.can_channel_var, width=18)
        self.can_channel_entry.grid(row=1, column=1, columnspan=2, padx=5, pady=2, sticky=tk.EW) 
        ttk.Label(self.can_config_frame, text="Bitrate:").grid(row=2, column=0, padx=5, pady=2, sticky=tk.W) 
        self.can_bitrate_var = tk.StringVar(value='500000'); common_bitrates = ["125000", "250000", "500000", "1000000"] 
        self.can_bitrate_combo = ttk.Combobox(self.can_config_frame, textvariable=self.can_bitrate_var, values=common_bitrates, width=16)
        self.can_bitrate_combo.grid(row=2, column=1, columnspan=2, padx=5, pady=2, sticky=tk.EW) 
        vcmd_hex_with_space = (self.root.register(self.validate_hex_with_space), '%P') 
        ttk.Label(self.can_config_frame, text="ECU Req ID (Hex):").grid(row=3, column=0, padx=5, pady=2, sticky=tk.W) 
        self.can_req_id_var = tk.StringVar(value='18DAF2A0') 
        self.can_req_id_entry = ttk.Entry(self.can_config_frame, textvariable=self.can_req_id_var, width=18, validate='key', validatecommand=vcmd_hex_with_space)
        self.can_req_id_entry.grid(row=3, column=1, columnspan=2, padx=5, pady=2, sticky=tk.EW) 
        ttk.Label(self.can_config_frame, text="ECU Resp ID (Hex):").grid(row=4, column=0, padx=5, pady=2, sticky=tk.W) 
        self.can_resp_id_var = tk.StringVar(value='18DAA0F2')  
        self.can_resp_id_entry = ttk.Entry(self.can_config_frame, textvariable=self.can_resp_id_var, width=18, validate='key', validatecommand=vcmd_hex_with_space)
        self.can_resp_id_entry.grid(row=4, column=1, columnspan=2, padx=5, pady=2, sticky=tk.EW) 
        ttk.Label(self.can_config_frame, text="DID to Send (Hex):").grid(row=5, column=0, padx=5, pady=2, sticky=tk.W) 
        self.direct_can_did_to_send_var = tk.StringVar(value='22 F180') 
        self.direct_can_did_entry = ttk.Entry(self.can_config_frame, textvariable=self.direct_can_did_to_send_var, width=18, validate='key', validatecommand=vcmd_hex_with_space)
        self.direct_can_did_entry.grid(row=5, column=1, columnspan=2, padx=5, pady=2, sticky=tk.EW) 
        can_buttons_frame = ttk.Frame(self.can_config_frame); can_buttons_frame.grid(row=6, column=0, columnspan=3, pady=(5,0), sticky=tk.EW) 
        self.connect_can_button = ttk.Button(can_buttons_frame, text="Connect CAN", command=self.on_connect_can_click, width=13, style='Toolbutton.TButton')
        self.connect_can_button.pack(side=tk.LEFT, padx=(0,2)) 
        self.disconnect_can_button = ttk.Button(can_buttons_frame, text="Disconnect", command=self.on_disconnect_can_click, state=tk.DISABLED, width=10, style='Toolbutton.TButton')
        self.disconnect_can_button.pack(side=tk.LEFT, padx=2) 
        self.send_monitor_button = ttk.Button(self.can_config_frame, text="Send DID & Monitor RX", command=self.on_send_and_monitor_direct_can_click, style='Accent.TButton')
        self.send_monitor_button.grid(row=7, column=0, columnspan=3, padx=0, pady=(5,2), sticky=tk.EW) 
        self.can_status_label = ttk.Label(self.can_config_frame, text="CAN Status: Init", anchor=tk.W, relief=tk.GROOVE, padding=3, font=('Segoe UI', 8))
        self.can_status_label.grid(row=8, column=0, columnspan=3, padx=0, pady=(2,0), sticky=tk.EW) 
        
        ps_control_frame = ttk.LabelFrame(top_config_row, text="Power Supply Control", padding=(10,5)) 
        ps_control_frame.pack(side=tk.LEFT, padx=(5,0), fill=tk.Y, anchor=tk.NW) 

        ps_buttons_top_row = ttk.Frame(ps_control_frame) 
        ps_buttons_top_row.pack(fill=tk.X, pady=2) 
        self.ps_connect_button = ttk.Button(ps_buttons_top_row, text="Connect PS", command=self.on_ps_connect_click, width=12, style='Toolbutton.TButton') 
        self.ps_connect_button.pack(side=tk.LEFT, padx=(0,3)) 
        self.ps_disconnect_button = ttk.Button(ps_buttons_top_row, text="Disconnect PS", command=self.on_ps_disconnect_click, width=12, style='Toolbutton.TButton') 
        self.ps_disconnect_button.pack(side=tk.LEFT, padx=3) 

        ps_buttons_mid_row = ttk.Frame(ps_control_frame) 
        ps_buttons_mid_row.pack(fill=tk.X, pady=2) 
        self.ps_on_button = ttk.Button(ps_buttons_mid_row, text="PS ON", command=self.on_ps_on_click, width=12, style='Toolbutton.TButton') 
        self.ps_on_button.pack(side=tk.LEFT, padx=(0,3)) 
        self.ps_off_button = ttk.Button(ps_buttons_mid_row, text="PS OFF", command=self.on_ps_off_click, width=12, style='Toolbutton.TButton') 
        self.ps_off_button.pack(side=tk.LEFT, padx=3) 
       
        ps_buttons_bot_row = ttk.Frame(ps_control_frame) 
        ps_buttons_bot_row.pack(fill=tk.X, pady=2) 
        self.ps_readv_button = ttk.Button(ps_buttons_bot_row, text="Read Voltage", command=self.on_ps_read_voltage_click, width=12, style='Toolbutton.TButton') 
        self.ps_readv_button.pack(side=tk.LEFT, padx=(0,3)) 
        self.ps_readc_button = ttk.Button(ps_buttons_bot_row, text="Read Current", command=self.on_ps_read_current_click, width=12, style='Toolbutton.TButton') 
        self.ps_readc_button.pack(side=tk.LEFT, padx=3) 
        
        self.ps_setv_button = ttk.Button(ps_control_frame, text="Set Voltage", command=self.on_ps_set_voltage_click, style='Accent.TButton') 
        self.ps_setv_button.pack(fill=tk.X, pady=(5,2)) 

        self.ps_status_label = ttk.Label(ps_control_frame, text="PS Status: Init", anchor=tk.W, relief=tk.GROOVE, padding=3, font=('Segoe UI', 8)) 
        self.ps_status_label.pack(fill=tk.X, pady=(2,0)) 
        
        sequence_run_frame = ttk.LabelFrame(parent_tab, text="Run Main Test Sequence", padding=(10,5)) 
        sequence_run_frame.pack(padx=5, pady=5, fill=tk.BOTH, expand=True) 

        self.test_type_var = tk.StringVar(value="Full EOL Sequence")  
        
        # --- Column 4: Camera Feed ---
        camera_frame = ttk.LabelFrame(top_config_row, text="Camera Feed", padding=(10,5))
        camera_frame.pack(side=tk.LEFT, padx=(5,0), fill=tk.BOTH, expand=True, anchor=tk.NW)

        self.camera_feed_label = tk.Label(camera_frame, background='black')
        self.camera_feed_label.pack(fill=tk.BOTH, expand=True, pady=5)

        camera_controls_frame = ttk.Frame(camera_frame)
        camera_controls_frame.pack(fill=tk.X, pady=(5,0))
        
        ttk.Label(camera_controls_frame, text="Index:").pack(side=tk.LEFT, padx=(0,2))
        self.camera_index_var = tk.IntVar(value=0)
        self.camera_index_spinbox = ttk.Spinbox(camera_controls_frame, from_=0, to=10, textvariable=self.camera_index_var, width=4)
        self.camera_index_spinbox.pack(side=tk.LEFT, padx=(0,5))

        self.cam_connect_button = ttk.Button(camera_controls_frame, text="Connect", command=self.on_camera_connect_click, width=10, style='Toolbutton.TButton')
        self.cam_connect_button.pack(side=tk.LEFT, padx=2)
        self.cam_disconnect_button = ttk.Button(camera_controls_frame, text="Disconnect", command=self.on_camera_disconnect_click, width=10, style='Toolbutton.TButton')
        self.cam_disconnect_button.pack(side=tk.LEFT, padx=2)
        self.cam_screenshot_button = ttk.Button(camera_controls_frame, text="Screenshot", command=self.on_camera_screenshot_click, width=12, style='Toolbutton.TButton')
        self.cam_screenshot_button.pack(side=tk.LEFT, padx=2)
        
        for test_name_key in self.main_test_map.keys(): 
            rb = ttk.Radiobutton(sequence_run_frame, text=test_name_key, variable=self.test_type_var, value=test_name_key, command=self.toggle_cycles_entry)
            rb.pack(anchor=tk.NW, padx=5, pady=2) 
        
        cycles_frame = ttk.Frame(sequence_run_frame); cycles_frame.pack(anchor=tk.NW, padx=5, pady=(5,0)) 
        self.cycles_label = ttk.Label(cycles_frame, text="Cycles (for Camera Test Patterns):")
        self.cycles_label.pack(side=tk.LEFT, padx=(0, 2)) 
        self.cycles_var = tk.IntVar(value=1)
        vcmd_digit = (self.root.register(self.validate_cycles), '%P') 
        self.cycles_entry = ttk.Entry(cycles_frame, textvariable=self.cycles_var, width=5, validate='key', validatecommand=vcmd_digit)
        self.cycles_entry.pack(side=tk.LEFT) 

        controls_frame = ttk.Frame(sequence_run_frame)
        controls_frame.pack(padx=5, pady=10, fill=tk.X, anchor=tk.SW) 
        self.run_button = ttk.Button(controls_frame, text="Start Main Sequence", command=self.start_automation_thread, style='Accent.TButton')
        self.run_button.pack(side=tk.LEFT, padx=(0,10), ipady=2) 
        self.coord_button = ttk.Button(controls_frame, text="Get Mouse Pos (CDA)", command=self.get_coordinates_helper, style='Toolbutton.TButton')
        self.coord_button.pack(side=tk.LEFT, padx=(0, 10)) 

    def create_test_sequencer_tab(self, parent_tab): 
        list_frame = ttk.Frame(parent_tab)
        list_frame.pack(padx=5, pady=5, fill=tk.BOTH, expand=True) 
        available_frame = ttk.LabelFrame(list_frame, text="Available Test Cases", padding=5)
        available_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5)) 
        avail_scrollbar_y = ttk.Scrollbar(available_frame, orient=tk.VERTICAL) 
        avail_scrollbar_x = ttk.Scrollbar(available_frame, orient=tk.HORIZONTAL) 
        self.available_listbox = tk.Listbox(available_frame, yscrollcommand=avail_scrollbar_y.set, xscrollcommand=avail_scrollbar_x.set, exportselection=False, selectmode=tk.EXTENDED, width=70, height=20, font=('Consolas', 9)) 
        avail_scrollbar_y.config(command=self.available_listbox.yview)
        avail_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y) 
        avail_scrollbar_x.config(command=self.available_listbox.xview)
        avail_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X) 
        self.available_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True) 

        button_frame = ttk.Frame(list_frame)
        button_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=20) 
        add_button = ttk.Button(button_frame, text="Add >>", command=self.add_selected_to_queue, width=10, style='Toolbutton.TButton')
        add_button.pack(pady=10) 
        remove_button = ttk.Button(button_frame, text="<< Remove", command=self.remove_selected_from_queue, width=10, style='Toolbutton.TButton')
        remove_button.pack(pady=10) 
        clear_button = ttk.Button(button_frame, text="Clear Queue", command=self.clear_queue, width=10, style='Toolbutton.TButton')
        clear_button.pack(pady=10) 

        queue_frame = ttk.LabelFrame(list_frame, text="Test Queue (Selected for Run)", padding=5)
        queue_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0)) 
        queue_scrollbar_y = ttk.Scrollbar(queue_frame, orient=tk.VERTICAL) 
        queue_scrollbar_x = ttk.Scrollbar(queue_frame, orient=tk.HORIZONTAL) 
        self.queue_listbox = tk.Listbox(queue_frame, yscrollcommand=queue_scrollbar_y.set, xscrollcommand=queue_scrollbar_x.set, exportselection=False, selectmode=tk.EXTENDED, width=70, height=20, font=('Consolas', 9)) 
        queue_scrollbar_y.config(command=self.queue_listbox.yview); queue_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y) 
        queue_scrollbar_x.config(command=self.queue_listbox.xview); queue_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X) 
        self.queue_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True) 

        run_queue_frame = ttk.Frame(parent_tab)
        run_queue_frame.pack(pady=(10, 5), fill=tk.X) 
        self.run_queue_button = ttk.Button(run_queue_frame, text="Run Selected Test Queue", command=self.start_queue_thread, style='Accent.TButton'); self.run_queue_button.pack(ipady=2) 

    def load_and_parse_tests(self): 
        _tests = [ 
            {'id': 'SEQ.1', 'name': 'Full EOL Test Sequence', 'did': run_complete_eol_test_sequence},
            {'id': 'SEQ.2', 'name': 'All Part Number Reads', 'did': perform_all_part_number_reads_sequence},
            {'id': 'SEQ.3', 'name': 'Camera Test Patterns Only', 'did': lambda app: perform_camera_test_patterns_main_sequence(app, 1)}, 
            {'id': 'SEQ.4', 'name': 'DTC Checks Only', 'did': test_dtc_checks},
            {'id': 'DID.1', 'name': '2.5.4.1. DID $FD1D – PCB Serial Number', 'did': '22 FD 1D'},
            {'id': 'DID.2', 'name': '2.5.4.2. DID $F18C – ECU Serial Number', 'did': '22 F1 8C'},
            {'id': 'DID.3', 'name': '2.5.5.1. DID $F122 – Software EBOM Part Number', 'did': '22 F1 22'},
            {'id': 'DID.4', 'name': '2.5.5.2. DID $F132 – EBOM ECU part number.', 'did': '22 F1 32'},
            {'id': 'DID.5', 'name': '2.5.5.3. DID $F133 – EBOM Assembly Part Number.', 'did': '22 F1 33'},
            {'id': 'DID.6', 'name': '2.5.5.4. DID $F154 – Hardware Supplier Identification.', 'did': '22 F1 54'},
            {'id': 'DID.7', 'name': '2.5.5.5. DID $F155 – Software Supplier Identification.', 'did': '22 F1 55'},
            {'id': 'DID.8', 'name': '2.5.5.6. DID $F180 – Bootloader Software version.', 'did': '22 F1 80'},
            {'id': 'DID.9', 'name': '2.5.5.7. DID $F181 – Application Software identification.', 'did': '22 F1 81'},
            {'id': 'DID.10', 'name': '2.5.5.8. DID $F192 – Supplier Manufacturer ECU Hardware Part Number. ', 'did': '22 F1 92'},
            {'id': 'DID.11', 'name': '2.5.5.9. DID $F193 – Supplier Manufacturer ECU Hardware Version Number. ', 'did': '22 F1 93'},
            {'id': 'DID.12', 'name': '2.5.5.10. DID $F194 – Supplier Manufacturer ECU Software Part Number.	', 'did': '22 F1 94'},
            {'id': 'DID.13', 'name': '2.5.5.11.	DID $F195 – Supplier Manufacturer ECU Software Version Number. ', 'did': '22 F1 95'},
            {'id': 'DID.14', 'name': '2.5.6.1.1. DID 0xFD13 - Magna Production Hardware Number.', 'did': '22 FD13'}, 
            {'id': 'DID.15', 'name': '2.5.6.1. DID 0xFD15 - Magna Production Hardware Number.', 'did': '22 FD 15'},
            {'id': 'DID.16', 'name': '2.5.6.2. DID 0xFD16 - Magna Production ICT Data', 'did': '22 FD16'},
            {'id': 'DID.17', 'name': '2.5.6.3. DID 0xFD17 - Magna Production Hardware Version Information', 'did': '22 FD 17'},
            {'id': 'DID.18', 'name': '2.5.6.4. DID 0xFD38 - Programmed Assembly Magna ECU Part Number', 'did': '22 FD 38'},
            {'id': 'DID.19', 'name': '2.5.6.5. DID 0xFD14 – Production Date', 'did': '22 FD 14'},
            {'id': 'DID.20', 'name': '2.5.7.1. DID 0xFD47 – SoC Temperature', 'did': '22 FD 47'},
            {'id': 'DID.21', 'name': '2.5.7.2. DID 0xFD48 – PCBA Temperature', 'did': '22 FD 48'},
            {'id': 'DID.22', 'name': '2.5.8.1. DID 0xFD4A – Ultrasonic Sensors Power supply and Current Level', 'did': '22 FD 4A'},
            {'id': 'DID.23', 'name': '2.5.8.2. DID 0xFD46 – Cameras Power supply and Current Level', 'did': '22 FD 46'}, 
        ]
        self.available_tests = _tests 
        update_status(f"Loaded {len(self.available_tests)} Functional Test Cases") 
        self.available_listbox.delete(0, tk.END) 
        for test in self.available_tests: 
            did_val = test.get('did') 
            action_name = "N/A" 
            if did_val is not None: 
                if callable(did_val): 
                    action_name = did_val.__name__ if hasattr(did_val, '__name__') else 'lambda_action' 
                    did_info = f" [Action: {action_name}]" 
                else:
                    did_info = f" [DID: {str(did_val)}]" 
            else:
                did_info = " [Sequence/Manual]" 
            self.available_listbox.insert(tk.END, f"{test['id']} - {test['name']}{did_info}") 

    def add_selected_to_queue(self): 
        selected_indices = self.available_listbox.curselection() 
        if not selected_indices: 
            return 
        for index in selected_indices: 
            self.test_queue.append(self.available_tests[index]) 
        self.update_queue_listbox() 

    def remove_selected_from_queue(self): 
        selected_indices = self.queue_listbox.curselection() 
        if not selected_indices: return 
        for index in sorted(selected_indices, reverse=True): del self.test_queue[index] 
        self.update_queue_listbox() 

    def clear_queue(self): self.test_queue = []; self.update_queue_listbox() 

    def update_queue_listbox(self): 
        self.queue_listbox.delete(0, tk.END) 
        for i, test in enumerate(self.test_queue): 
            did_val = test.get('did'); did_info = "" 
            if did_val is not None: 
                if callable(did_val): 
                    action_name = did_val.__name__ if hasattr(did_val, '__name__') else 'lambda_action' 
                    did_info = f" [Action: {action_name}]" 
                else:
                    did_info = f" [DID: {str(did_val)}]" 
            else:
                did_info = " [Sequence/Manual]" 
            self.queue_listbox.insert(tk.END, f"{i+1}. {test['id']} - {test['name']}{did_info}") 

    def start_queue_thread(self): 
        if not self.test_queue: 
            messagebox.showinfo("Empty Queue", "Add test cases to the queue first.")
            return 
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showwarning("Busy", "Another automation task is currently running.")
            return 
        op_mode = self.operation_mode_var.get() 
        if op_mode == "Direct CAN" and not self.can_bus:
            messagebox.showerror("CAN Error", "Direct CAN: Bus not connected. Please connect first.")
            return 
        if not messagebox.askyesno("Confirm Run Queue", f"Are you sure you want to run {len(self.test_queue)} test(s) from the queue?"): 
            return 
        self.status_text.config(state=tk.NORMAL)
        self.status_text.delete('1.0', tk.END)
        self.status_text.config(state=tk.DISABLED) 
        self.run_queue_button.config(style='Accent.TButton')
        self.disable_buttons()
        self.last_run_success = None 
        update_status(f"Starting Test Queue execution ({len(self.test_queue)} items)...") 
        self.worker_thread = threading.Thread(target=run_queue_worker, args=(self, list(self.test_queue)), daemon=True) 
        self.worker_thread.start() 

    def validate_cycles(self, P_value): 
        return P_value.isdigit() or P_value == "" 

    def toggle_cycles_entry(self): 
        test_type_selected = self.test_type_var.get() 
        cycles_relevant_test = "Camera Test Patterns"  

        if hasattr(self, 'cycles_label') and self.cycles_label.winfo_exists(): 
            self.cycles_label.config(text=f"Cycles (for {cycles_relevant_test}):") 
        
        enable_cycles = test_type_selected == cycles_relevant_test 
        state_to_set = tk.NORMAL if enable_cycles else tk.DISABLED 
        
        if hasattr(self, 'cycles_entry') and self.cycles_entry.winfo_exists(): 
             self.cycles_entry.config(state=state_to_set) 
        if hasattr(self, 'cycles_label') and self.cycles_label.winfo_exists(): 
            self.cycles_label.config(state=state_to_set) 

    def on_mode_change(self): 
        mode = self.operation_mode_var.get(); is_cda_mode = mode == "CDA" 
        
        cred_frame_state = tk.NORMAL if is_cda_mode else tk.DISABLED 
        if hasattr(self, 'username_entry'): 
            self.username_entry.config(state=cred_frame_state) 
        if hasattr(self, 'password_entry'): 
            self.password_entry.config(state=cred_frame_state) 
        if hasattr(self, 'coord_button'): 
            self.coord_button.config(state=tk.NORMAL if is_cda_mode else tk.DISABLED) 

        can_config_input_fields_state = tk.NORMAL if not is_cda_mode and not self.can_bus else tk.DISABLED 
        self.set_can_config_fields_state(can_config_input_fields_state) 
        
        direct_can_did_input_state = tk.NORMAL if not is_cda_mode else tk.DISABLED 
        if hasattr(self, 'direct_can_did_entry'): 
            self.direct_can_did_entry.config(state=direct_can_did_input_state) 

        can_connect_button_state = tk.NORMAL if not is_cda_mode and not self.can_bus else tk.DISABLED 
        can_disconnect_button_state = tk.NORMAL if not is_cda_mode and self.can_bus else tk.DISABLED 
        can_send_monitor_button_state = tk.NORMAL if not is_cda_mode and self.can_bus else tk.DISABLED 

        if hasattr(self, 'connect_can_button'): 
            self.connect_can_button.config(state=can_connect_button_state) 
        if hasattr(self, 'disconnect_can_button'): 
            self.disconnect_can_button.config(state=can_disconnect_button_state) 
        if hasattr(self, 'send_monitor_button'): 
            self.send_monitor_button.config(state=can_send_monitor_button_state) 
        
        self.update_can_status_label() #
        self.update_ps_button_states() # Update PS buttons based on mode/connection too 

    def set_can_config_fields_state(self, state_value): 
         if not hasattr(self, 'can_interface_combo'): 
             return 
         is_normal_state = state_value == tk.NORMAL 
         combo_box_state = 'readonly' if is_normal_state else tk.DISABLED 
         entry_field_state = tk.NORMAL if is_normal_state else tk.DISABLED 
         bitrate_combo_state = tk.NORMAL if is_normal_state else tk.DISABLED 
         fields_to_update = { 
             'can_interface_combo': combo_box_state, 'can_channel_entry': entry_field_state,
             'can_bitrate_combo': bitrate_combo_state, 'can_req_id_entry': entry_field_state,
             'can_resp_id_entry': entry_field_state 
         }
         for widget_name_str, new_state in fields_to_update.items(): 
             widget_obj = getattr(self, widget_name_str, None) 
             if widget_obj and widget_obj.winfo_exists(): 
                 try: widget_obj.config(state=new_state) 
                 except Exception: pass # Ignore if minor TclError during quick state changes 

    def disable_buttons(self): # Called when a worker starts 
         widgets_to_disable_names = [ 
             'run_button', 'coord_button', 'cda_radio', 'direct_can_radio',
             'connect_can_button', 'disconnect_can_button', 'run_queue_button',
             'cycles_entry', 'send_monitor_button', 'direct_can_did_entry', 
             'can_req_id_entry', 'can_resp_id_entry',
             'can_interface_combo', 'can_channel_entry', 'can_bitrate_combo',
             'ps_connect_button', 'ps_disconnect_button', 'ps_on_button', 
             'ps_off_button', 'ps_readv_button', 'ps_readc_button', 'ps_setv_button'
         ]
         for name in widgets_to_disable_names: 
             widget = getattr(self, name, None) 
             if widget and widget.winfo_exists(): 
                  try: widget.config(state=tk.DISABLED) 
                  except Exception: 
                      pass 
         
         if hasattr(self, 'sequence_run_frame') and self.sequence_run_frame.winfo_exists(): 
            for child in self.sequence_run_frame.winfo_children(): 
                if isinstance(child, (ttk.Radiobutton, ttk.Frame)): # Frame for cycles 
                    try: child.config(state=tk.DISABLED) # This might not work for frames, better to target entries inside 
                    except:
                        pass 
            if hasattr(self,'cycles_entry') and self.cycles_entry.winfo_exists(): 
                self.cycles_entry.config(state=tk.DISABLED) 


    def enable_buttons(self): # Called when a worker finishes 
        final_style_name = 'Accent.TButton' 
        if self.last_run_success is True: final_style_name = 'Success.TButton' 
        elif self.last_run_success is False: final_style_name = 'Fail.TButton' 
        
        if hasattr(self, 'run_button') and self.run_button.winfo_exists(): 
            self.run_button.config(style=final_style_name, state=tk.NORMAL) 
        if hasattr(self, 'run_queue_button') and self.run_queue_button.winfo_exists(): 
            self.run_queue_button.config(style=final_style_name, state=tk.NORMAL) 
        
        if hasattr(self, 'send_monitor_button') and self.send_monitor_button.winfo_exists(): 
            self.send_monitor_button.config(style='Accent.TButton')  
        
        if hasattr(self, 'cda_radio') and self.cda_radio.winfo_exists(): 
            self.cda_radio.config(state=tk.NORMAL) 
        if hasattr(self, 'direct_can_radio') and self.direct_can_radio.winfo_exists(): 
            self.direct_can_radio.config(state=tk.NORMAL) 
        
        if hasattr(self, 'sequence_run_frame') and self.sequence_run_frame.winfo_exists(): # For test type radio buttons 
            for child in self.sequence_run_frame.winfo_children(): 
                if isinstance(child, ttk.Radiobutton): 
                    try: 
                        child.config(state=tk.NORMAL) 
                    except: 
                        pass 
        
        self.on_mode_change()  
        self.toggle_cycles_entry() # This will correctly set state of cycles_entry 

    def initialize_can(self):
        global can
        if not can:
            self.log_to_status("ERROR: python-can library missing.")
            self.update_can_status_label()
            return False
        if self.can_bus:
            self.log_to_status("CAN is already connected.")
            return True
        
        interface = self.can_interface_var.get()
        channel = self.can_channel_var.get().strip()
        bitrate_str = self.can_bitrate_var.get().strip()

        if not interface:
            messagebox.showerror("CAN Error", "CAN Interface cannot be empty.")
            return False
        try:
            bitrate = int(bitrate_str)
            if bitrate <= 0: raise ValueError("Bitrate must be positive.")
        except ValueError:
            messagebox.showerror("CAN Error", f"Invalid Bitrate specified: '{bitrate_str}'.")
            return False
        
        self.log_to_status(f"Attempting to connect CAN: Interface='{interface}', Channel='{channel}', Bitrate={bitrate} bps...")
        self.can_status_label.config(text="CAN: Connecting..."); self.root.update_idletasks()
        
        # --- FIX: Added CAN FD flags for Vector Interface ---
        extra_can_args = {}
        if interface == 'vector':
            self.log_to_status("Vector interface detected, enabling CAN FD mode.")
            extra_can_args = {
                'app_name': 'CANoe',
                'fd': True,          # Enable CAN FD
                'fd_bitrate': 2000000  # Set the data phase bitrate (e.g., 2Mbit/s)
            }
        
        try:
            self.can_bus = can.interface.Bus(bustype=interface, channel=channel, bitrate=bitrate, **extra_can_args)
            self.log_to_status(f"CAN connected successfully: {getattr(self.can_bus, 'channel_info', 'N/A')}")
        except Exception as e:
            err_msg = f"Failed to initialize CAN bus: {type(e).__name__}: {e}"
            self.log_to_status(f"ERROR: {err_msg}\n{traceback.format_exc()}")
            messagebox.showerror("CAN Initialization Error", f"{err_msg}\n\nPlease check CAN hardware, drivers, and parameters.")
            self.can_bus = None
        finally:
            self.update_can_status_label()
        return self.can_bus is not None

    def shutdown_can(self): 
        if self.can_bus: 
            self.log_to_status("Disconnecting CAN bus..."); 
            try: self.can_bus.shutdown() 
            except Exception as e: self.log_to_status(f"Error during CAN bus shutdown: {e}") 
            finally: self.can_bus = None 
        else: self.log_to_status("CAN bus already disconnected or not initialized.") 
        self.update_can_status_label() 

    def update_can_status_label(self): 
         if not hasattr(self, 'can_status_label') or not self.can_status_label.winfo_exists(): 
             return 
         global can 
         if self.can_bus: 
             info = getattr(self.can_bus, 'channel_info', 'Active') 
             self.can_status_label.config(text=f"CAN: Connected ({info})", foreground="#006400") # Dark Green 
         else:
             status_txt, color_txt = ("CAN: Disconnected", "red") if can else ("CAN: Library Missing", "darkred") 
             self.can_status_label.config(text=status_txt, foreground=color_txt) 

    def update_ps_status_label(self): 
        global power_supply_serial 
        if not hasattr(self, 'ps_status_label') or not self.ps_status_label.winfo_exists(): 
            return 
        global serial # Check if pyserial module is loaded #
        if power_supply_serial and power_supply_serial.is_open: 
            self.ps_status_label.config(text=f"PS: Connected ({power_supply_serial.port})", foreground="#006400") 
        else:
            status_txt, color_txt = ("PS: Disconnected", "red") if serial else ("PS: Library Missing", "darkred") 
            self.ps_status_label.config(text=status_txt, foreground=color_txt) 

    def update_ps_button_states(self): 
        global power_supply_serial, serial 
        lib_missing_state = tk.DISABLED if serial is None else tk.NORMAL 

        if hasattr(self, 'ps_connect_button'): 
            self.ps_connect_button.config(state=lib_missing_state) 
        if hasattr(self, 'ps_disconnect_button'): 
            self.ps_disconnect_button.config(state=lib_missing_state) 
        
        is_connected = power_supply_serial and power_supply_serial.is_open 
        connected_state = tk.NORMAL if is_connected else tk.DISABLED 
        disconnected_state = tk.NORMAL if not is_connected and serial else tk.DISABLED 

        if hasattr(self, 'ps_connect_button'): self.ps_connect_button.config(state=disconnected_state) 
        if hasattr(self, 'ps_disconnect_button'): self.ps_disconnect_button.config(state=connected_state) 
        
        ps_action_buttons = ['ps_on_button', 'ps_off_button', 'ps_readv_button',  
                             'ps_readc_button', 'ps_setv_button']
        for btn_name in ps_action_buttons: 
            widget = getattr(self, btn_name, None) 
            if widget and widget.winfo_exists(): 
                widget.config(state=connected_state) 
        self.update_ps_status_label() 

    def on_ps_connect_click(self): 
        global power_supply_serial 
        if self.worker_thread and self.worker_thread.is_alive(): 
            messagebox.showwarning("Busy", "Automation task running. Cannot connect PS now.") 
            return
        ps_connectSerial() # This updates the global power_supply_serial and logs via update_status 
        self.update_ps_button_states() 

    def on_ps_disconnect_click(self): 
        global power_supply_serial 
        if self.worker_thread and self.worker_thread.is_alive(): 
            messagebox.showwarning("Busy", "Automation task running. Cannot disconnect PS now.") 
            return
        if power_supply_serial and power_supply_serial.is_open: 
            try:
                power_supply_serial.close() 
                update_status(f"Power supply at {power_supply_serial.port} disconnected by user.") 
            except Exception as e: 
                update_status(f"Error disconnecting power supply: {e}") 
            finally:
                power_supply_serial = None 
        else:
            update_status("Power supply already disconnected.") 
        self.update_ps_button_states() 

    def on_ps_on_click(self): 
        global power_supply_serial 
        if self.worker_thread and self.worker_thread.is_alive(): 
            return # Silently ignore if worker active 
        if not (power_supply_serial and power_supply_serial.is_open): 
            update_status("ERROR: PS not connected. Please connect first.")
            return 
        ps_on(power_supply_serial) 

    def on_ps_off_click(self): 
        global power_supply_serial 
        if self.worker_thread and self.worker_thread.is_alive(): 
            return 
        if not (power_supply_serial and power_supply_serial.is_open): 
            update_status("ERROR: PS not connected. Please connect first.")
            return 
        ps_off(power_supply_serial) 

    def on_ps_read_voltage_click(self): 
        global power_supply_serial 
        if self.worker_thread and self.worker_thread.is_alive(): 
            return 
        if not (power_supply_serial and power_supply_serial.is_open): 
            update_status("ERROR: PS not connected. Please connect first.")
            return 
        voltage = ps_readVoltage(power_supply_serial) 
        if voltage is not None: 
            update_status(f"PS Manual Read Voltage: {voltage:.2f} V") 

    def on_ps_read_current_click(self): 
        global power_supply_serial 
        if self.worker_thread and self.worker_thread.is_alive(): 
            return 
        if not (power_supply_serial and power_supply_serial.is_open): 
            update_status("ERROR: PS not connected. Please connect first.")
            return 
        current = ps_readCurrent(power_supply_serial) 
        if current is not None: 
            update_status(f"PS Manual Read Current: {current:.2f} A") 

    def on_ps_set_voltage_click(self): 
        global power_supply_serial 
        if self.worker_thread and self.worker_thread.is_alive(): 
            return 
        if not (power_supply_serial and power_supply_serial.is_open): #
            update_status("ERROR: PS not connected. Please connect first.")
            return 
        
        volt_val = simpledialog.askfloat("Set Power Supply Voltage",  
                                         "Enter desired voltage (e.g., 13.5):",
                                         parent=self.root, minvalue=0.0, maxvalue=60.0) # Adjust maxvalue as per PS capability
        if volt_val is not None: 
            update_status(f"Attempting to set PS voltage to {volt_val:.2f}V...") 
            ps_setVolt(power_supply_serial, volt_val) 
        else:
            update_status("PS Set Voltage cancelled by user.") 

    def log_to_status(self, message_text): 
        if not hasattr(self, 'status_text') or not self.status_text.winfo_exists(): 
            return 
        try:
            self.status_text.config(state=tk.NORMAL) 
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3] 
            self.status_text.insert(tk.END, f"[{timestamp}] {message_text}\n") 
            self.status_text.see(tk.END) 
            self.status_text.config(state=tk.DISABLED) 
        except tk.TclError:
            pass # Ignore if widget is destroyed during update 

    def update_status_display(self): 
        if not hasattr(self, 'root') or not self.root.winfo_exists(): return # Stop if root is gone 
        try:
            while True: # Process all messages in queue 
                message = output_queue.get_nowait() 
                self.log_to_status(message) 
                if message.startswith("--- Automation FINISHED") or \
                   message.startswith("--- Test Queue FINISHED") or \
                   message.startswith("--- Direct Send & Monitor FINISHED ---"): 
                     self.root.after(50, self.enable_buttons) # Delay slightly to ensure worker exits 
                     if not message.startswith("--- Direct Send & Monitor FINISHED ---"): 
                        success_flag = "successfully" in message or "(0 errors)" in message # Basic check 
                        popup_title = "Automation Status" 
                        popup_message = message.split('\n')[0] # Get first line for brevity 
                        show_popup_func = lambda m=popup_message, t=(messagebox.showinfo if success_flag else messagebox.showwarning): t(popup_title, m) 
                        self.root.after(100, show_popup_func) 

        except queue.Empty: 
            pass # No more messages 
        except Exception as e: 
            print(f"Error in update_status_display: {type(e).__name__}: {e}") 
        finally:
            if hasattr(self, 'root') and self.root.winfo_exists(): # Check again before scheduling 
                 self.root.after(100, self.update_status_display) # Schedule next check 

    def start_automation_thread(self): 
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showwarning("Busy", "Another task is currently running.")
            return 
        op_mode = self.operation_mode_var.get() 
        if op_mode == "Direct CAN" and not self.can_bus: 
            messagebox.showerror("CAN Error", "Direct CAN mode selected, but CAN bus is not connected.")
            return 
        username = self.username_var.get()
        password = self.password_var.get() 
        if op_mode == "CDA" and (not username or not password): 
            messagebox.showerror("Missing Input", "Username and Password are required for CDA mode.")
            return 
        test_type_selected = self.test_type_var.get()
        cycles_to_run = 1 
        if test_type_selected == "Camera Test Patterns": 
            try:
                cycles_to_run = self.cycles_var.get() 
                if cycles_to_run <= 0: raise ValueError("Cycles must be positive.") 
            except (tk.TclError, ValueError): 
                messagebox.showerror("Invalid Input", "Cycles for 'Camera Test Patterns' must be a positive integer.")
                return 
        confirm_message = f"Are you sure you want to start the '{test_type_selected}' sequence in {op_mode} mode?" 
        if test_type_selected == "Camera Test Patterns":
            confirm_message += f"\nCycles: {cycles_to_run}" 
        if op_mode == "CDA": 
            confirm_message += "\n\nIMPORTANT: Ensure CDA application is ready and do NOT use mouse/keyboard during CDA automation!" 
        if not messagebox.askyesno("Confirm Start Sequence", confirm_message): 
            return 
        self.status_text.config(state=tk.NORMAL)
        self.status_text.delete('1.0', tk.END)
        self.status_text.config(state=tk.DISABLED) 
        self.run_button.config(style='Accent.TButton')
        self.disable_buttons()
        self.last_run_success = None 
        log_start_msg = f"Starting Main Sequence: Mode={op_mode}, Test={test_type_selected}" 
        if test_type_selected == "Camera Test Patterns": 
            log_start_msg += f", Cycles={cycles_to_run}" 
        update_status(log_start_msg) 
        self.worker_thread = threading.Thread(target=automation_worker, args=(self, username, password, test_type_selected, cycles_to_run), name="AutomationWorkerThread", daemon=True) 
        self.worker_thread.start() 

    def on_send_and_monitor_direct_can_click(self): 
        if self.worker_thread and self.worker_thread.is_alive(): 
            messagebox.showwarning("Busy", "Another task (automation or monitoring) is currently running.") 
            return
        if self.operation_mode_var.get() != "Direct CAN":
            messagebox.showerror("Mode Error", "This function is only available in 'Direct CAN' mode.")
            return 
        if not self.can_bus: 
            messagebox.showerror("CAN Error", "Direct CAN: Bus not connected. Please connect first.")
            return 

        ecu_req_id_str = self.can_req_id_var.get().strip() 
        ecu_resp_id_str = self.can_resp_id_var.get().strip()  
        did_to_send_str = self.direct_can_did_to_send_var.get().strip() 

        if not ecu_req_id_str: 
            messagebox.showerror("Input Error", "ECU Req ID (Hex) cannot be empty.")
            return 
        try: # Validate hex inputs before proceeding 
            if ecu_req_id_str:
                int(ecu_req_id_str.replace(" ",""), 16) 
            if ecu_resp_id_str: 
                int(ecu_resp_id_str.replace(" ",""), 16) # Allow empty response ID 
            if did_to_send_str: 
                bytes.fromhex(did_to_send_str.replace(" ", "").replace("0x", "", 1).replace("0X", "", 1)) 
        except ValueError as e: 
            messagebox.showerror("Input Error", f"Invalid Hex input: {e}\nEnsure IDs and DID are valid hex.")
            return 
            
        duration_str = simpledialog.askstring("Monitor Duration", "Enter RX monitoring duration (s, e.g., 2):", initialvalue="2", parent=self.root) 
        if duration_str is None: 
            return  
        try:
            monitor_duration = float(duration_str) 
            if not (0.1 <= monitor_duration <= 300):
                raise ValueError("Duration: 0.1-300s.") 
        except ValueError as e: 
            messagebox.showerror("Input Error", f"Invalid duration: {e}")
            return 

        log_resp_id_display = ecu_resp_id_str if ecu_resp_id_str else "Any" 
        update_status(f"Starting Direct CAN Send: REQ_ID={ecu_req_id_str}, EXPECTED_RESP_ID={log_resp_id_display}, DID='{did_to_send_str}', Monitoring RX for {monitor_duration:.1f}s") 
        self.disable_buttons()  
        self.worker_thread = threading.Thread(target=send_and_monitor_worker, args=(self, did_to_send_str, ecu_req_id_str, ecu_resp_id_str, monitor_duration), name="SendAndMonitorThread", daemon=True) 
        self.worker_thread.start() 

    def get_coordinates_helper(self): 
        if 'pyautogui' not in sys.modules or pyperclip is None:
            messagebox.showerror("Error", "pyautogui and/or pyperclip library missing.")
            return 
        if self.operation_mode_var.get() != "CDA": 
            messagebox.showinfo("Info", "Coordinate helper is intended for CDA mode.")
            return 
        try:
            messagebox.showinfo("Info","Move mouse to exact touch coordinate.  Press OK and move within 3 seconds for script to copy x-y coordinates!")
            delay_seconds = 3 #Adjust as needed for user to move mouse to desired spot
            self.log_to_status(f"Please move mouse to desired location within {delay_seconds} seconds...")
            self.root.iconify()
            self.root.update_idletasks() # Ensure it minimizes 
            time.sleep(delay_seconds) 
            x_coord, y_coord = pyautogui.position() 
            self.root.deiconify() 
            coords_text = f"({x_coord}, {y_coord})" 
            self.log_to_status(f"Mouse Coordinates: {coords_text}") 
            pyperclip.copy(coords_text) 
            self.log_to_status("(Coordinates copied to clipboard)") 
            messagebox.showinfo("Coordinates Captured", f"Position: {coords_text}\n(Copied to clipboard)") 
        except Exception as e: 
            self.log_to_status(f"Coordinate Helper Error: {e}") 
            messagebox.showerror("Coordinate Helper Error", f"Failed to get coordinates: {e}") 
        finally:
             if hasattr(self.root, 'state') and self.root.state() == 'iconic': 
                 self.root.deiconify() 

    def on_close(self): 
        if self.worker_thread and self.worker_thread.is_alive(): 
             if not messagebox.askyesno("Confirm Exit", "A task is currently running. Are you sure you want to exit? This may leave hardware in an indeterminate state."): 
                 return 
        
        self.log_to_status("Shutdown sequence initiated..."); 
        self.shutdown_can() # Handles CAN bus 
        self.on_camera_disconnect_click() # 
        self.persist_sent_dids() # 
        global power_supply_serial # Use the global handle for final shutdown 
        if power_supply_serial and power_supply_serial.is_open: 
             update_status("Attempting to turn off and close power supply...") 
             try:
                 ps_off(power_supply_serial) # Turn off output 
                 power_supply_serial.close()  # Close serial port 
                 update_status("Power supply successfully turned off and port closed.") 
             except Exception as e: 
                 update_status(f"Error during power supply final shutdown: {e}") 
        
        self.root.destroy() 

# --- Main Execution ---
if __name__ == "__main__": 
    if serial is None: 
        messagebox.showwarning("Dependency Missing", "pyserial library not found.\nPower supply control features will be disabled.") 
    if can is None: 
         if not messagebox.askyesno("Dependency Missing", "python-can library not found.\nDirect CAN Mode will be unavailable.\n\nDo you want to continue with other features (e.g., CDA mode)?"): 
             sys.exit(1) 
    
    main_app_root = tk.Tk() 
    app_instance = App(main_app_root) 
    main_app_root.mainloop() 
