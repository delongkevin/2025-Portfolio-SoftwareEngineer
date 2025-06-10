# <<< Start of Consolidated Python Script >>>
import sys
import cv2
import numpy as np
import os
import csv
import imageio
import json
import subprocess
import traceback
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout,
    QComboBox, QSlider, QFileDialog, QTextEdit, QRadioButton, QButtonGroup,
    QInputDialog, QMessageBox, QFrame, QLineEdit, QCheckBox, QGroupBox, QSizePolicy,
    QListWidget, QProgressBar, QAbstractItemView
)
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap

# --- Try importing win32com ---
try:
    import win32com.client
    import pythoncom
    WIN32COM_AVAILABLE = True
    # --- ADD THIS LIST ---
    # Common COM error codes indicating disconnection/server unavailable
    COM_DISCONNECTED_ERRORS = [-2147220995, -2147417848, -2147418113]
    # --- END ADD ---
except ImportError:
    WIN32COM_AVAILABLE = False
    COM_DISCONNECTED_ERRORS = [] # Define as empty if pywin32 not available
    print("[WARN] win32com.client not available. CANoe automation limited.")
    print("[WARN] Please install pywin32: pip install pywin32")
# -----------------------------

CONFIG_FILE = "canoe_config.json"
COMMAND_CONFIG_FILE = "canoe_commands.json"
DIAG_CONFIG_FILE = "diag_requests.json"

def handle_exception(exc_type, exc_value, exc_traceback):
    """ Catches unhandled exceptions, logs them, and shows a message box """
    error_message = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    log_entry = f"[CRITICAL ERROR]\n{error_message}"
    print(log_entry)
    try:
        # Append to log file
        with open("app_crash.log", "a") as f:
            f.write(f"{datetime.now().isoformat()}\n{log_entry}\n---\n")
    except Exception:
        pass # Ignore logging errors

    # Show user message (ensure basic Qt elements are used)
    try:
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("Application Error")
        msg_box.setText("An unexpected error occurred.")
        msg_box.setInformativeText("Please check console or 'app_crash.log'. You may need to restart.")
        # msg_box.setDetailedText(error_message) # Optional: Show full traceback
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()
    except Exception as mb_err:
        print(f"ERROR: Could not display error message box: {mb_err}")

    # Optional: Uncomment to force exit after showing the message
    # sys.exit(1)

# --- Worker Threads ---

class CanoeWorker(QThread):
    """ Handles CANoe COM operations like launch, run, stop, exit """
    signal_message = pyqtSignal(str)
    signal_canoe_launched = pyqtSignal(object)
    signal_canoe_exited = pyqtSignal()
    signal_simulation_started = pyqtSignal()
    signal_simulation_stopped = pyqtSignal()
    signal_error = pyqtSignal(str, bool)

    def __init__(self, action, config=None, canoe_app=None, retries=3):
        super().__init__()
        self.action = action
        self.config = config if config is not None else {}
        self.canoe_app = canoe_app
        self.max_retries = retries

    def _call_com_with_retry(self, func, *args, **kwargs):
        last_error = None
        for attempt in range(self.max_retries):
            try:
                result = func(*args, **kwargs)
                return result
            except pythoncom.com_error as e:
                last_error = e
                disconnected_codes = [-2147220995, -2147417848, -2147418113]
                if e.hresult in disconnected_codes:
                    wait_ms = 1000 + attempt * 250
                    self.signal_message.emit(f"[WARN] COM disconnected/unavailable attempt {attempt+1}/{self.max_retries}. Retrying in {wait_ms}ms...")
                    QThread.msleep(wait_ms)
                else:
                    raise
            except Exception as e:
                 last_error = e
                 raise
            finally:
                pythoncom.CoUninitialize()
        self.signal_message.emit(f"[ERROR] COM call failed after {self.max_retries} retries.")
        raise last_error

    def run(self):
        thread_com_initialized = False
        if WIN32COM_AVAILABLE:
            try:
                pythoncom.CoInitialize()
                thread_com_initialized = True
            except pythoncom.com_error as e:
                self.signal_message.emit(f"[WARN] CoInitialize failed in CanoeWorker: {e}")
            finally:
                pythoncom.CoUninitialize()

        if not WIN32COM_AVAILABLE:
            self.signal_error.emit("win32com.client not installed.")
            if thread_com_initialized: pythoncom.CoUninitialize()
            return

        canoe_app_local = None
        try:
            if self.action == "launch":
                self.signal_message.emit("[INFO] Launching CANoe...")
                canoe_app_local = win32com.client.DispatchEx("CANoe.Application")
                is_hidden = self.config.get('canoe_hidden', True)
                try:
                    self._call_com_with_retry(setattr, canoe_app_local, 'Visible', not is_hidden)
                except Exception as vis_err:
                     self.signal_message.emit(f"[WARN] Could not set CANoe visibility: {vis_err}")
                visibility_state = "hidden" if is_hidden else "visible"
                self.signal_message.emit(f"[INFO] CANoe object created ({visibility_state}).")
                try:
                    self._call_com_with_retry(getattr, canoe_app_local, 'Name')
                    self.signal_message.emit("[INFO] CANoe COM object responsive.")
                except Exception as e:
                     self.signal_error.emit(f"[ERROR] Launched CANoe unresponsive: {repr(e)}")
                     if thread_com_initialized: pythoncom.CoUninitialize(); return

                cfg_path = self.config.get('cfg_path')
                if cfg_path and os.path.exists(cfg_path):
                     try:
                         measurement_obj = self._call_com_with_retry(getattr, canoe_app_local, 'Measurement')
                         if self._call_com_with_retry(getattr, measurement_obj, 'Running'):
                              self._call_com_with_retry(measurement_obj.Stop); QThread.msleep(500)
                         self._call_com_with_retry(canoe_app_local.Open, cfg_path)
                         self.signal_message.emit(f"[INFO] Opened config: {cfg_path}")
                     except Exception as e:
                         self.signal_error.emit(f"[ERROR] Failed open config '{cfg_path}': {repr(e)}")
                else:
                     self.signal_message.emit(f"[WARN] No valid CFG path. Launched {visibility_state} without config.")
                self.signal_canoe_launched.emit(canoe_app_local)

            elif self.action == "run" and self.canoe_app:
                self.signal_message.emit("[INFO] Starting simulation...")
                try:
                    measurement = self._call_com_with_retry(getattr, self.canoe_app, 'Measurement')
                    if not self._call_com_with_retry(getattr, measurement, 'Running'):
                        self._call_com_with_retry(measurement.Start); QThread.msleep(300)
                        if self._call_com_with_retry(getattr, measurement, 'Running'): self.signal_simulation_started.emit()
                        else: self.signal_error.emit("[ERROR] Start called but not running.")
                    else: self.signal_message.emit("[WARN] Already running.")
                except Exception as e: self.signal_error.emit(f"[ERROR] Failed start sim: {repr(e)}")

            elif self.action == "stop" and self.canoe_app:
                self.signal_message.emit("[INFO] Stopping simulation...")
                try:
                    measurement = self._call_com_with_retry(getattr, self.canoe_app, 'Measurement')
                    if self._call_com_with_retry(getattr, measurement, 'Running'):
                        self._call_com_with_retry(measurement.Stop); QThread.msleep(300)
                        if not self._call_com_with_retry(getattr, measurement, 'Running'): self.signal_simulation_stopped.emit()
                        else: self.signal_error.emit("[ERROR] Stop called but still running.")
                    else: self.signal_message.emit("[WARN] Not running.")
                except Exception as e: self.signal_error.emit(f"[ERROR] Failed stop sim: {repr(e)}")

            elif self.action == "exit" and self.canoe_app:
                self.signal_message.emit("[INFO] Exiting CANoe...")
                try:
                    is_running = False;
                    try: measurement = self._call_com_with_retry(getattr, self.canoe_app, 'Measurement'); is_running = self._call_com_with_retry(getattr, measurement, 'Running')
                    except: pass
                    if is_running:
                         self.signal_message.emit("[INFO] Stopping simulation before exit...")
                         try: self._call_com_with_retry(self.canoe_app.Measurement.Stop); QThread.msleep(1000)
                         except: pass
                    self.canoe_app.Quit()
                    self.signal_message.emit("[INFO] CANoe Quit sent.")
                    self.signal_canoe_exited.emit()
                except Exception as e:
                     self.signal_message.emit(f"[ERROR] Error during CANoe exit: {repr(e)}")
                     self.signal_canoe_exited.emit()
                finally:
                    pythoncom.CoUninitialize()

        except pythoncom.com_error as ce:
            err_msg = f"CANoe Worker COM Error ({self.action}): {ce.strerror} ({ce.hresult})"
            is_disconnect = ce.hresult in COM_DISCONNECTED_ERRORS # Check if it's a disconnect error
            self.signal_error.emit(err_msg, is_disconnect) # Emit the flag
        except Exception as e:
            # Assume other errors are not disconnect errors
            self.signal_error.emit(f"CANoe Worker Error ({self.action}): {repr(e)}", False)

class CanoeCommandWorker(QThread):
    """ Worker to execute a specific command (e.g., set sysvar) """
    signal_success = pyqtSignal(str, str, str) # origin_id, var_name, value
    signal_error = pyqtSignal(str,str, bool) # origin_id, error_message
    signal_message = pyqtSignal(str)

    def __init__(self, action, canoe_app, origin_id, details):
        super().__init__()
        self.action = action
        self.canoe_app = canoe_app
        self.origin_id = origin_id
        self.details = details

    def run(self):
        thread_com_initialized = False
        if WIN32COM_AVAILABLE:
             try: pythoncom.CoInitialize(); thread_com_initialized = True
             except pythoncom.com_error: pass

        if not WIN32COM_AVAILABLE: 
            self.signal_error.emit(self.origin_id, "pywin32 not installed.")
            pythoncom.CoUninitialize()

        elif not self.canoe_app:
             is_disconnected = False
             if hasattr(self.canoe_app, '_oleobj_'):
                  try: _ = self.canoe_app.Name
                  except pythoncom.com_error as ce: 
                      is_disconnected = ce.hresult in [-2147220995,-2147417848,-2147418113]
                  except: 
                      pass
             if is_disconnected: 
                 self.signal_error.emit(self.origin_id, "CANoe disconnected. Exit/Launch.")
             else: 
                 self.signal_error.emit(self.origin_id, "CANoe app object invalid.")
        else:
            try:
                if self.action == "set_sysvar":
                    var_name = self.details.get('var_name'); value_str = self.details.get('value')
                    if not var_name or value_str is None: raise ValueError("SysVar name/value missing.")
                    self.signal_message.emit(f"[CMD] Set SysVar '{var_name}' = '{value_str}'")
                    sys_vars = self.canoe_app.System.Variables; target_var = sys_vars(var_name)
                    try:
                        target_var.Value = int(value_str)
                        self.signal_message.emit(f"[CMD] Set '{var_name}' as Int.")
                    except:
                        try:
                            target_var.Value = float(value_str)
                            self.signal_message.emit(f"[CMD] Set '{var_name}' as Float.")
                        except:
                            try:
                                target_var.Value = str(value_str)
                                self.signal_message.emit(f"[CMD] Set '{var_name}' as String.")
                            except Exception as str_err: raise ValueError(f"Set as String failed: {str_err}")
                    self.signal_success.emit(self.origin_id, var_name, value_str)
            except pythoncom.com_error as pycome:
                is_disconnect = pycome.hresult in COM_DISCONNECTED_ERRORS # Check flag
                self.signal_error.emit(self.origin_id, f"COM Error: {pycome.strerror} ({pycome.hresult})", is_disconnect) # Emit flag
            except Exception as e:
                # Assume other errors are not disconnect errors
                self.signal_error.emit(self.origin_id, f"Error: {str(e)}", False)

class TestExecutionWorker(QThread):
    """ Worker thread for starting, stopping, and polling CANoe Test Execution state """
    signal_progress = pyqtSignal(int, str) # progress (0-100), state_text
    signal_finished = pyqtSignal(str) # final_verdict text
    signal_error = pyqtSignal(str, bool) # error_message
    signal_message = pyqtSignal(str) # General logging

    STATE_MAP = {0: "Stopped", 1: "Running", 2: "Finished"}
    VERDICT_MAP = {0: "None", 1: "Pass", 2: "Fail", 3: "Error", 4: "Inconclusive"}

    def __init__(self, canoe_app, action="start_poll"):
        super().__init__()
        self.canoe_app = canoe_app
        self.action = action

    def run(self):
        thread_com_initialized = False
        # Use the global list of known disconnect codes
        global COM_DISCONNECTED_ERRORS

        if WIN32COM_AVAILABLE:
             try:
                # Initialize COM for this thread
                pythoncom.CoInitialize()
                thread_com_initialized = True
             except pythoncom.com_error as e:
                 # Emit error if CoInitialize fails, treat as non-disconnect
                 self.signal_error.emit(f"Test Worker CoInitialize Error: {e}", False) # Pass False
                 # Cannot proceed without COM
                 return # Exit run method

        # Check dependencies and canoe_app validity after attempting CoInitialize
        if not WIN32COM_AVAILABLE:
            self.signal_error.emit("CANoe app not ready: pywin32 missing.", False) # Pass False
            if thread_com_initialized: pythoncom.CoUninitialize()
            return
        if not self.canoe_app:
             # Check if canoe_app reference itself is None or invalid
             self.signal_error.emit("CANoe app not ready: App object is None.", False) # Pass False
             if thread_com_initialized: pythoncom.CoUninitialize()
             return
             # You might add a COM check here too, like trying to access canoe_app.Name
             # within a try/except, and emitting with is_disconnect=True if it fails
             # with a known COM disconnect error.

        try:
            test_exec = None
            # Attempt to get the TestExecution object
            try:
                 # Check common locations for TestExecution object based on CANoe version/setup
                 if hasattr(self.canoe_app, 'TestEnvironment') and self.canoe_app.TestEnvironment:
                     test_exec = self.canoe_app.TestEnvironment.TestExecution
                 elif hasattr(self.canoe_app, 'TestExecution'):
                      test_exec = self.canoe_app.TestExecution
                 # Add other potential paths if needed, e.g., via Configuration.TestSetup
                 elif hasattr(self.canoe_app, 'Configuration') and self.canoe_app.Configuration and hasattr(self.canoe_app.Configuration, 'TestSetup') and self.canoe_app.Configuration.TestSetup:
                      test_exec = self.canoe_app.Configuration.TestSetup.TestExecution

                 # Validate the found object
                 if test_exec is None:
                     raise AttributeError("TestExecution object could not be located in CANoe Application structure.")
                 # Optional: Try accessing a property to ensure it's a valid COM object
                 _ = test_exec.State # Try accessing State property

            except AttributeError as ae:
                 # Emit error if TestExecution object not found, treat as non-disconnect
                 self.signal_error.emit(f"Error finding TestExecution object: {ae}", False) # Pass False
                 if thread_com_initialized: pythoncom.CoUninitialize(); return
            except pythoncom.com_error as ce:
                 # If accessing test_exec fails with COM error, check if it's a disconnect
                 is_disconnect = ce.hresult in COM_DISCONNECTED_ERRORS
                 self.signal_error.emit(f"COM Error accessing TestExecution object: {ce.strerror} ({ce.hresult})", is_disconnect) # Pass flag
                 if thread_com_initialized: pythoncom.CoUninitialize(); return
            except Exception as e:
                 # Other unexpected errors finding test_exec
                 self.signal_error.emit(f"Unexpected error finding TestExecution object: {repr(e)}", False) # Pass False
                 if thread_com_initialized: pythoncom.CoUninitialize(); return


            # --- Main Action Logic ---
            if self.action == "start_poll":
                current_state_val = int(test_exec.State)
                if current_state_val == 0: # If stopped, start it
                    self.signal_message.emit("[TEST] Sending TestExecution.Start()...")
                    test_exec.Start()
                    QThread.msleep(500) # Give it a moment to start
                else:
                    self.signal_message.emit(f"[TEST] Already in state {self.STATE_MAP.get(current_state_val, '?')}. Monitoring...")

                # Start polling loop
                while not self.isInterruptionRequested():
                    try:
                        # Get current state and progress inside loop
                        current_state_val = int(test_exec.State)
                        state_text = self.STATE_MAP.get(current_state_val, f"Unknown({current_state_val})")
                        progress = 0
                        try: # Progress might not always be available
                            if hasattr(test_exec, 'Progress'): progress = int(test_exec.Progress)
                        except: pass # Ignore errors getting progress

                        # Emit progress
                        self.signal_progress.emit(progress, state_text)

                        # Check if execution finished (State is not Running)
                        if current_state_val != 1:
                            final_verdict_val = -1; final_verdict_text = "Unknown"
                            try: # Getting verdict might fail
                                if hasattr(test_exec, 'Verdict'): final_verdict_val = int(test_exec.Verdict)
                                final_verdict_text = self.VERDICT_MAP.get(final_verdict_val, f"Unknown({final_verdict_val})")
                            except: pass
                            self.signal_finished.emit(final_verdict_text)
                            break # Exit polling loop

                        # Wait before next poll
                        QThread.msleep(1000)

                    except pythoncom.com_error as poll_err:
                         # Check if polling failed due to disconnect
                         is_disconnect = poll_err.hresult in COM_DISCONNECTED_ERRORS
                         if is_disconnect:
                             self.signal_error.emit("CANoe lost during test poll.", True) # Pass True
                             break # Exit polling loop on disconnect
                         else:
                             # Re-raise other COM errors to be caught by outer handler
                             raise poll_err
                    except Exception as poll_e:
                        # Catch other potential errors during polling (e.g., converting state/progress)
                         self.signal_error.emit(f"Error during test poll loop: {repr(poll_e)}", False) # Pass False
                         break # Exit loop on other errors too? Or log and continue? Let's exit.


                # Check if loop exited due to interruption request
                if self.isInterruptionRequested():
                    self.signal_message.emit("[TEST] Polling stopped by request.")

            elif self.action == "stop":
                # Attempt to stop test execution
                self.signal_message.emit("[TEST] Sending TestExecution.Stop()...")
                test_exec.Stop()
                # Note: We don't wait or check state here, just send stop signal

        # --- Outer Exception Handling ---
        except pythoncom.com_error as ce:
            # Catch COM errors from actions like Start(), Stop()
            is_disconnect = ce.hresult in COM_DISCONNECTED_ERRORS
            self.signal_error.emit(f"Test COM Error ({self.action}): {ce.strerror} ({ce.hresult})", is_disconnect) # Pass flag
        except Exception as e:
            # Catch any other unexpected errors during the run method
            # Assume these are not disconnect errors unless specifically checked
            self.signal_error.emit(f"Test Worker Error ({self.action}): {repr(e)}", False) # Pass False
        finally:
            # Ensure COM is uninitialized for this thread
            if thread_com_initialized:
                try:
                    pythoncom.CoUninitialize()
                except Exception as uninit_err:
                     # Log if uninitialize fails, but don't overwrite primary error signal
                     print(f"[WARN] Error during CoUninitialize in TestExecutionWorker: {uninit_err}")

# --- Main Application Window ---

class RearCameraTester(QWidget):
    def handle_disconnect_error(self, origin="Unknown"):
        """ Central handler for fatal disconnect errors """
        self.log_message(f"[CRITICAL] CANoe disconnected during {origin}. Resetting CANoe state.")
        QMessageBox.critical(self, "CANoe Disconnected",
                             f"Connection to CANoe was lost or it may have crashed ({origin}).\n"
                             f"Internal state reset. Please try Launch CANoe again.")
        self.canoe_app = None # Crucial: Clear the invalid COM object reference

        # Ensure workers using the invalid object are stopped/cleaned up
        if self.canoe_cmd_worker and self.canoe_cmd_worker.isRunning():
             self.canoe_cmd_worker.quit() # Ask thread to terminate
             self.canoe_cmd_worker = None # Clear reference
        if self.test_execution_worker and self.test_execution_worker.isRunning():
             self.test_execution_worker.requestInterruption() # Ask thread to stop polling
             self.test_execution_worker.quit() # Ask thread to terminate
             self.test_execution_worker = None # Clear reference
        if self.canoe_launch_worker and self.canoe_launch_worker.isRunning():
             # If launch worker failed with disconnect, quit it too
             if self.canoe_launch_worker.action == "launch":
                  self.canoe_launch_worker.quit()
                  self.canoe_launch_worker = None

        # Reset UI state
        self.update_canoe_button_states() # This should re-enable Launch button
        if hasattr(self, 'test_progress_bar'):
            self.test_progress_bar.setValue(0)
            self.test_progress_bar.setFormat("CANoe Disconnected")

    def update_test_exec_ui_state(self, is_running):
        """ Helper to enable/disable test queue controls based on running state """
        if hasattr(self, 'test_start_btn'): self.test_start_btn.setEnabled(not is_running)
        if hasattr(self, 'test_stop_btn'): self.test_stop_btn.setEnabled(is_running)
        if hasattr(self, 'test_group'): self.test_group.setEnabled(not is_running) # Disable editing queue while running

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rear Camera Tester + CANoe Control")
        self.setGeometry(50, 50, 1300, 950) # Adjusted height

        # --- Initialize instance variables ---
        self.output_dir = os.getcwd(); self.detected_frames = []; self.gif_duration = 200
        self.canoe_config = {}; self.canoe_app = None; self.canoe_launch_worker = None; self.canoe_cmd_worker = None
        self.button_commands = {}; self.saved_diag_requests = {} ; self.panel_widgets = {}
        self.cap = None; self.out = None; self.prev_frame = None; self.start_time = None; self.frame_index = 0
        self.csv_file = ""; self.video_file = ""; self.frame_folder = ""; self.threshold = 80
        self.test_execution_worker = None; self.current_test_queue = []

        # --- Create Core UI Elements (Console first, ensure existence) ---
        self.console = QTextEdit(); self.console.setReadOnly(True); self.console.setMaximumHeight(100)

        # --- Load Configs FIRST ---
        self.load_canoe_config(); self.load_commands(); self.load_diag_requests()

        # --- Create UI Widgets (Order Matters!) ---
        self.label = QLabel("Camera Feed"); self.label.setAlignment(Qt.AlignCenter); self.label.setMinimumSize(640, 480)
        self.start_btn = QPushButton("Start Recording"); self.stop_btn = QPushButton("Stop Recording"); self.stop_btn.setEnabled(False)
        self.export_btn = QPushButton("Export Detected Frames"); self.camera_selector = QComboBox(); self.camera_selector.addItems([str(i) for i in range(5)])
        # Create slider & label BEFORE they are used in layout or methods
        self.threshold_slider = QSlider(Qt.Horizontal); self.threshold_slider.setMinimum(10); self.threshold_slider.setMaximum(100); self.threshold_slider.setValue(self.threshold); self.threshold_slider.setTickInterval(10); self.threshold_slider.setTickPosition(QSlider.TicksBelow)
        self.threshold_label = QLabel(f"Change Threshold: {self.threshold}%") # Use variable
        self.radio_gif = QRadioButton("Export as GIF"); self.radio_video = QRadioButton("Export as Video"); self.radio_gif.setChecked(True)
        self.export_format_group = QButtonGroup(); self.export_format_group.addButton(self.radio_gif); self.export_format_group.addButton(self.radio_video)
        self.browse_btn = QPushButton("Browse Save Folder")
        self.launch_canoe_btn = QPushButton("Launch CANoe"); self.exit_canoe_btn = QPushButton("Exit CANoe")
        self.run_sim_btn = QPushButton("Run Simulation"); self.stop_sim_btn = QPushButton("Stop Simulation")
        self.config_canoe_btn = QPushButton("Configure Paths"); self.clear_commands_btn = QPushButton("Clear Panel Cmds")
        self.chk_canoe_hidden = QCheckBox("Run CANoe Hidden"); self.chk_canoe_hidden.setChecked(self.canoe_config.get('canoe_hidden', True))

        # Create Right Panel Widgets (Placeholders first)
        self.panel_container = QFrame(); self.panel_container.setFrameShape(QFrame.StyledPanel)
        self.panel_layout = QVBoxLayout(self.panel_container) # Assign attribute HERE
        self.diag_group = QGroupBox("Send Diagnostic Request"); self.diag_request_combo = QComboBox(); self.diag_clear_btn = QPushButton("Clear Saved")
        self.diag_request_input = QLineEdit(); self.diag_send_btn = QPushButton("Send"); self.diag_save_btn = QPushButton("Save Request")
        self.test_group = QGroupBox("Test Execution Queue"); self.test_module_input = QLineEdit(); self.test_add_btn = QPushButton("Add to Queue")
        self.test_queue_list = QListWidget(); self.test_move_up_btn = QPushButton("Move Up"); self.test_move_down_btn = QPushButton("Move Down"); self.test_remove_btn = QPushButton("Remove"); self.test_clear_queue_btn = QPushButton("Clear Queue")
        self.test_start_btn = QPushButton("Start Test Execution"); self.test_stop_btn = QPushButton("Stop Test Execution"); self.test_stop_btn.setEnabled(False)
        self.test_progress_bar = QProgressBar(); self.test_progress_bar.setRange(0, 100); self.test_progress_bar.setValue(0); self.test_progress_bar.setTextVisible(True); self.test_progress_bar.setFormat("Test Progress: %p%")

        # --- Setup Main Layout ---
        app_layout = QVBoxLayout(self) # Main Vertical Layout
        main_hbox_layout = QHBoxLayout() # Top Horizontal Split

        # == Left Side Layout ==
        left_widget = QWidget(); left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(self.label) # Camera Feed
        # Camera Controls Area
        controls_area = QWidget(); controls_grid = QGridLayout(controls_area)
        controls_grid.addWidget(QLabel("Camera:"), 0, 0); controls_grid.addWidget(self.camera_selector, 1, 0)
        controls_grid.addWidget(self.start_btn, 2, 0); controls_grid.addWidget(self.stop_btn, 3, 0)
        controls_grid.addWidget(self.browse_btn, 4, 0)
        controls_grid.addWidget(self.threshold_label, 0, 1); controls_grid.addWidget(self.threshold_slider, 1, 1)
        radio_layout = QHBoxLayout(); radio_layout.addWidget(self.radio_gif); radio_layout.addWidget(self.radio_video)
        controls_grid.addLayout(radio_layout, 2, 1); controls_grid.addWidget(self.export_btn, 3, 1)
        controls_grid.setColumnStretch(0, 1); controls_grid.setColumnStretch(1, 1); left_layout.addWidget(controls_area)
        # CANoe Controls Group
        canoe_controls_group = QWidget(); canoe_controls_layout = QGridLayout(canoe_controls_group)
        canoe_controls_layout.addWidget(self.launch_canoe_btn, 0, 0); canoe_controls_layout.addWidget(self.exit_canoe_btn, 0, 1)
        canoe_controls_layout.addWidget(self.run_sim_btn, 1, 0); canoe_controls_layout.addWidget(self.stop_sim_btn, 1, 1)
        canoe_controls_layout.addWidget(self.config_canoe_btn, 2, 0); canoe_controls_layout.addWidget(self.clear_commands_btn, 2, 1)
        canoe_controls_layout.addWidget(self.chk_canoe_hidden, 3, 0, 1, 2)
        left_layout.addWidget(canoe_controls_group)
        left_layout.addWidget(QLabel("Log Output:")); left_layout.addWidget(self.console) # Console
        left_layout.addStretch(1)
        main_hbox_layout.addWidget(left_widget, 1)

        # == Right Side Layout ==
        right_widget = QWidget(); right_layout = QVBoxLayout(right_widget)
        # Build Panel UI (Needs self.panel_layout to exist)
        self.build_switch_hmi_replica(self.panel_layout)
        right_layout.addWidget(self.panel_container)
        # Build Diag UI
        diag_layout = QVBoxLayout(self.diag_group); saved_req_layout = QHBoxLayout()
        saved_req_layout.addWidget(QLabel("Saved:")); self.diag_request_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.populate_diag_combo(); saved_req_layout.addWidget(self.diag_request_combo); saved_req_layout.addWidget(self.diag_clear_btn)
        diag_layout.addLayout(saved_req_layout)
        send_req_layout = QHBoxLayout(); send_req_layout.addWidget(QLabel("Request (Hex):")); self.diag_request_input.setPlaceholderText("e.g., 22 F1 90")
        send_req_layout.addWidget(self.diag_request_input); send_req_layout.addWidget(self.diag_send_btn); send_req_layout.addWidget(self.diag_save_btn)
        diag_layout.addLayout(send_req_layout)
        right_layout.addWidget(self.diag_group)
        # Build Test UI
        test_layout = QVBoxLayout(self.test_group); add_test_layout = QHBoxLayout()
        add_test_layout.addWidget(QLabel("Module Name:")); self.test_module_input.setPlaceholderText("Enter Test Module name")
        add_test_layout.addWidget(self.test_module_input); add_test_layout.addWidget(self.test_add_btn)
        test_layout.addLayout(add_test_layout)
        queue_control_layout = QHBoxLayout(); self.test_queue_list.setDragDropMode(QAbstractItemView.InternalMove); self.test_queue_list.setSelectionMode(QAbstractItemView.SingleSelection)
        queue_control_layout.addWidget(self.test_queue_list, 4); list_button_layout = QVBoxLayout()
        list_button_layout.addWidget(self.test_move_up_btn); list_button_layout.addWidget(self.test_move_down_btn); list_button_layout.addWidget(self.test_remove_btn); list_button_layout.addWidget(self.test_clear_queue_btn); list_button_layout.addStretch()
        queue_control_layout.addLayout(list_button_layout, 1); test_layout.addLayout(queue_control_layout)
        exec_button_layout = QHBoxLayout(); exec_button_layout.addWidget(self.test_start_btn); exec_button_layout.addWidget(self.test_stop_btn); test_layout.addLayout(exec_button_layout)
        right_layout.addWidget(self.test_group)
        right_layout.addStretch(1)
        main_hbox_layout.addWidget(right_widget, 1)

        # Add Main HBox and Progress Bar to App Layout
        app_layout.addLayout(main_hbox_layout)
        app_layout.addWidget(self.test_progress_bar)

        # --- Connect Signals ---
        self.connect_signals()

        # --- Initialize Timer ---
        self.timer = QTimer(); self.timer.timeout.connect(self.update_frame)

        # --- Initialize States ---
        self.update_canoe_button_states(); self.reset_session()


    # --- Methods ---

    def connect_signals(self):
        """ Connect all UI signals to their slots """
        # Camera
        self.threshold_slider.valueChanged.connect(self.update_threshold_label)
        self.start_btn.clicked.connect(self.start_recording)
        self.stop_btn.clicked.connect(self.stop_recording_ui)
        self.export_btn.clicked.connect(self.export_detected_frames)
        self.browse_btn.clicked.connect(self.choose_directory)
        # CANoe Core
        self.launch_canoe_btn.clicked.connect(self.launch_canoe)
        self.exit_canoe_btn.clicked.connect(self.exit_canoe)
        self.run_sim_btn.clicked.connect(self.run_simulation)
        self.stop_sim_btn.clicked.connect(self.stop_simulation)
        self.config_canoe_btn.clicked.connect(self.prompt_for_canoe_config)
        self.clear_commands_btn.clicked.connect(self.clear_commands_ui)
        self.chk_canoe_hidden.stateChanged.connect(self.save_canoe_config_settings)
        # Diagnostic
        self.diag_request_combo.currentIndexChanged.connect(self.on_diag_combo_changed)
        self.diag_send_btn.clicked.connect(self.handle_diag_send)
        self.diag_save_btn.clicked.connect(self.handle_diag_save)
        self.diag_clear_btn.clicked.connect(self.clear_diag_requests_ui)
        # Test Queue
        self.test_add_btn.clicked.connect(self.add_test_to_queue)
        self.test_move_up_btn.clicked.connect(self.move_test_up)
        self.test_move_down_btn.clicked.connect(self.move_test_down)
        self.test_remove_btn.clicked.connect(self.remove_test_from_queue)
        self.test_clear_queue_btn.clicked.connect(self.clear_test_queue)
        self.test_start_btn.clicked.connect(self.start_test_execution)
        self.test_stop_btn.clicked.connect(self.stop_test_execution)

    def build_switch_hmi_replica(self, parent_layout):
        """ Creates the PyQt widgets mirroring Switch_HMI_Panel.xvp """
        # CORRECTED Clearing loop: Robustly clear previous items
        while parent_layout.count() > 0:
            item = parent_layout.takeAt(0)
            if item is None: continue # Should not happen with count() check, but be safe
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else:
                layout_item = item.layout()
                if layout_item is not None:
                    # Recursively clear sub-layout (important for complex layouts)
                    self._clear_layout_items(layout_item)
                    # Optionally remove the layout itself after clearing
                    # parent_layout.removeItem(layout_item) # Or let takeAt handle removal? Usually yes.
        # ------------------------

        self.panel_widgets = {}
        panel_frame = QFrame()
        panel_grid = QGridLayout(panel_frame)

        # --- Add Widgets to panel_grid using more readable format ---
        # Row 0
        panel_grid.addWidget(QLabel("<b>View Switch HMI</b>"), 0, 0, 1, 2)
        panel_grid.addWidget(QLabel("Display Request"), 0, 2, 1, 2)
        # Row 1
        panel_grid.addWidget(QLabel("Read DID\n0x2024 Status:"), 1, 0)
        status_indicator = QLabel("●"); status_indicator.setStyleSheet("color: gray;")
        self.panel_widgets['status_indicator'] = status_indicator; panel_grid.addWidget(status_indicator, 1, 1)
        panel_grid.addWidget(QLabel("CameraDisplaySta2:"), 1, 2)
        combo_display = QComboBox(); combo_display.addItems(["Default", "Option1", "Option2"])
        self.panel_widgets['combo_display'] = combo_display; panel_grid.addWidget(combo_display, 1, 3)
        # Row 2
        btn_rear_view_top = QPushButton("Rear View With Top\nView (Rear 360)"); btn_rear_view_top.setObjectName("btn_rear_view_top")
        panel_grid.addWidget(btn_rear_view_top, 2, 0, 2, 2)
        btn_send_proxi = QPushButton("Send Proxi\nDID 0x2024:"); btn_send_proxi.setObjectName("btn_send_proxi")
        panel_grid.addWidget(btn_send_proxi, 2, 2)
        btn_auto_pan = QPushButton("AUTO PAN"); btn_auto_pan.setObjectName("btn_auto_pan")
        panel_grid.addWidget(btn_auto_pan, 2, 3)
        # Row 3
        btn_burv = QPushButton("BURV (Back Up\nRear View)"); btn_burv.setObjectName("btn_burv")
        panel_grid.addWidget(btn_burv, 3, 2)
        btn_right_pan = QPushButton("Right PAN"); btn_right_pan.setObjectName("btn_right_pan")
        panel_grid.addWidget(btn_right_pan, 3, 3)
        # Row 4
        btn_front_view_top = QPushButton("Front View With Top\nView (Front 360)"); btn_front_view_top.setObjectName("btn_front_view_top")
        panel_grid.addWidget(btn_front_view_top, 4, 0, 2, 2)
        btn_zoom_in = QPushButton("Zoom In"); btn_zoom_in.setObjectName("btn_zoom_in")
        panel_grid.addWidget(btn_zoom_in, 4, 2)
        btn_left_pan = QPushButton("Left PAN"); btn_left_pan.setObjectName("btn_left_pan")
        panel_grid.addWidget(btn_left_pan, 4, 3)
        # Row 5
        btn_zoom_out = QPushButton("Zoom Out"); btn_zoom_out.setObjectName("btn_zoom_out")
        panel_grid.addWidget(btn_zoom_out, 5, 2)
        btn_aux = QPushButton("AUX"); btn_aux.setObjectName("btn_aux")
        panel_grid.addWidget(btn_aux, 5, 3)
        # Row 6
        btn_rcpv = QPushButton("RCPV (Rear Cross\nPath View)"); btn_rcpv.setObjectName("btn_rcpv")
        panel_grid.addWidget(btn_rcpv, 6, 0, 2, 2)
        panel_grid.addWidget(QLabel(" "), 6, 2)
        btn_more_cams = QPushButton("More CAMs"); btn_more_cams.setObjectName("btn_more_cams")
        panel_grid.addWidget(btn_more_cams, 6, 3)
        # Row 7
        btn_exit = QPushButton("Exit"); btn_exit.setObjectName("btn_exit")
        panel_grid.addWidget(btn_exit, 7, 2)
        panel_grid.addWidget(QLabel(" "), 7, 3)
        # Row 8
        btn_fcpv = QPushButton("FCPV (Front Cross\nPath View)"); btn_fcpv.setObjectName("btn_fcpv")
        panel_grid.addWidget(btn_fcpv, 8, 0, 2, 2)
        btn_tha = QPushButton("THA"); btn_tha.setObjectName("btn_tha")
        panel_grid.addWidget(btn_tha, 8, 2)
        panel_grid.addWidget(QLabel(" "), 8, 3)
        # Row 10
        btn_ffcv = QPushButton("FFCV (Forward\nFacing Camera View)"); btn_ffcv.setObjectName("btn_ffcv")
        panel_grid.addWidget(btn_ffcv, 10, 0, 2, 2)
        # Row 12
        panel_grid.addWidget(QLabel("<b>Send Touch Coordinates</b>"), 12, 0, 1, 4)
        # Row 13
        panel_grid.addWidget(QLabel("Resolution X"), 13, 0)
        edit_res_x = QLineEdit("4132"); self.panel_widgets['edit_res_x'] = edit_res_x
        panel_grid.addWidget(edit_res_x, 13, 1)
        panel_grid.addWidget(QLabel("Resolution Y"), 13, 2)
        edit_res_y = QLineEdit("1896"); self.panel_widgets['edit_res_y'] = edit_res_y
        panel_grid.addWidget(edit_res_y, 13, 3)
        # Row 14
        btn_send_res = QPushButton("Send"); btn_send_res.setObjectName("btn_send_res")
        panel_grid.addWidget(btn_send_res, 14, 3)

        # Connect buttons
        buttons = panel_frame.findChildren(QPushButton)
        for btn in buttons:
            btn.clicked.connect(lambda checked, b=btn.objectName(): self.handle_panel_action(b))
            self.panel_widgets[btn.objectName()] = btn
        parent_layout.addWidget(panel_frame)

    def _clear_layout_items(self, layout):
        """ Helper function to recursively clear items from a layout """
        if layout is not None:
            while layout.count() > 0:
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    sub_layout = item.layout()
                    if sub_layout is not None:
                        self._clear_layout_items(sub_layout) # Recursive call

    # --- Command Handling (Panel Buttons) ---
    def load_commands(self):
        if os.path.exists(COMMAND_CONFIG_FILE):
            try:
                with open(COMMAND_CONFIG_FILE,'r') as f: self.button_commands=json.load(f)
                self.log_message(f"[INFO] Loaded panel cmds: {COMMAND_CONFIG_FILE}")
            except Exception as e: self.log_message(f"[ERR] Load cmds fail: {repr(e)}"); self.button_commands={}
        else: 
            self.log_message(f"[INFO] {COMMAND_CONFIG_FILE} not found."); self.button_commands={}
    def save_commands(self):
        try:
            with open(COMMAND_CONFIG_FILE,'w') as f: json.dump(self.button_commands,f,indent=4)
        except Exception as e: 
            self.log_message(f"[ERR] Save cmds fail: {repr(e)}"); QMessageBox.critical(self,"Error",f"Save cmd cfg fail:\n{repr(e)}")
    def clear_commands(self):
        self.button_commands={};
        if os.path.exists(COMMAND_CONFIG_FILE):
            try: os.remove(COMMAND_CONFIG_FILE); self.log_message(f"[INFO] Cleared cmds: {COMMAND_CONFIG_FILE}")
            except OSError as e: 
                self.log_message(f"[ERR] Delete cmd file fail: {repr(e)}"); QMessageBox.warning(self,"Error",f"Del cmd cfg fail:\n{repr(e)}")
        else: 
            self.log_message("[INFO] Cmd cfg cleared (no file).")
    def clear_commands_ui(self):
        if QMessageBox.question(self,'Clear Cmds',"Clear panel button cmds?",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes: self.clear_commands()
    def handle_panel_action(self,button_id):
        self.log_message(f"[PANEL] Action: {button_id}");
        if not self.canoe_app: 
            QMessageBox.warning(self,"CANoe","Not launched.")
            return
        if not WIN32COM_AVAILABLE: 
            QMessageBox.critical(self,"Error","pywin32 missing.")
            return
        if button_id in self.button_commands: 
            details=self.button_commands[button_id]
            self.log_message(f"[PANEL] Found: Set '{details.get('var_name')}'='{details.get('value')}'")
            self.execute_canoe_command(button_id, details)
        else: 
            self.log_message(f"[PANEL] No cmd. Prompting."); self.prompt_for_command(button_id)
    def prompt_for_command(self,button_id):
        var_name,ok1=QInputDialog.getText(self,"Cfg Button",f"SysVar Name for '{button_id}':");
        if ok1 and var_name:
            value,ok2=QInputDialog.getText(self,"Cfg Button",f"Value for '{var_name}':");
            if ok2 and value is not None: 
                self.log_message(f"[PANEL] User: SysVar='{var_name}',Value='{value}'")
                details={'var_name':var_name,'value':value}
                self.execute_canoe_command(button_id,details,save_on_success=True)
            else: 
                self.log_message(f"[PANEL] Cfg cancel (Value).")
        else: 
            self.log_message(f"[PANEL] Cfg cancel (Name).")
    def execute_canoe_command(self,origin_id,details,save_on_success=False):
        if self.canoe_cmd_worker and self.canoe_cmd_worker.isRunning(): 
            QMessageBox.warning(self,"Busy","Cmd worker busy.") 
            return
        self.canoe_cmd_worker=CanoeCommandWorker("set_sysvar",self.canoe_app,origin_id,details)
        self.canoe_cmd_worker.signal_message.connect(self.log_message)
        self.canoe_cmd_worker.signal_error.connect(self.on_command_error)
        if save_on_success: 
            self.canoe_cmd_worker.signal_success.connect(self.on_command_success_and_save)
        else: 
            self.canoe_cmd_worker.signal_success.connect(lambda oid,vn,v: self.log_message(f"[OK] Cmd {oid}: {vn}={v}"))
        self.canoe_cmd_worker.finished.connect(self.on_cmd_worker_finished)
        self.canoe_cmd_worker.start()
    def on_command_success_and_save(self, origin_id, var_name, value):
        if origin_id != 'diag_send':
            self.log_message(f"[OK] Panel {origin_id}: {var_name}={value}. Saving.")
            self.button_commands[origin_id]={'var_name':var_name,'value':value}
            self.save_commands()
            QMessageBox.information(self,"Saved",f"Panel cmd '{origin_id}' saved:\nSet '{var_name}'='{value}'")
        else: 
            self.log_message(f"[OK] Diag via SysVar '{var_name}'='{value}'.")

    def on_command_error(self, origin_id, error_message, is_disconnect=False): # Add is_disconnect flag
        self.log_message(f"[FAIL] Cmd {origin_id}: {error_message}")
        if not is_disconnect: # Show warning only if not handled as disconnect
            QMessageBox.warning(self,"Cmd Fail",f"Cmd fail '{origin_id}':\n{error_message}")
        if is_disconnect:
            self.handle_disconnect_error(f"Command '{origin_id}'")

    def on_cmd_worker_finished(self): 
        self.log_message("[DEBUG] Cmd worker finish.")
        self.canoe_cmd_worker=None

    # --- Diagnostic Request Handling ---
    def load_diag_requests(self):
        def_diag={'_TARGET_SYSVAR':''};
        if os.path.exists(DIAG_CONFIG_FILE):
            try:
                with open(DIAG_CONFIG_FILE,'r') as f: loaded=json.load(f)
                self.saved_diag_requests={**def_diag,**loaded}
                self.log_message(f"[INFO] Loaded diag reqs: {DIAG_CONFIG_FILE}")
                if '_TARGET_SYSVAR' not in self.saved_diag_requests: 
                    self.saved_diag_requests['_TARGET_SYSVAR']=''
            except Exception as e: 
                self.log_message(f"[ERR] Load diag fail: {repr(e)}"); self.saved_diag_requests=def_diag
        else: 
            self.log_message(f"[INFO] {DIAG_CONFIG_FILE} not found."); self.saved_diag_requests=def_diag
    def save_diag_requests(self):
        try:
            with open(DIAG_CONFIG_FILE,'w') as f: json.dump(self.saved_diag_requests,f,indent=4)
        except Exception as e: self.log_message(f"[ERR] Save diag fail: {repr(e)}"); QMessageBox.critical(self,"Error",f"Save diag reqs fail:\n{repr(e)}")
    def clear_diag_requests(self):
        target=self.saved_diag_requests.get('_TARGET_SYSVAR',"")
        self.saved_diag_requests={'_TARGET_SYSVAR':target}
        self.save_diag_requests()
        self.populate_diag_combo()
        self.diag_request_input.clear()
        self.log_message("[INFO] Cleared saved diag reqs.")
    def clear_diag_requests_ui(self):
        if QMessageBox.question(self,'Clear Diag Reqs',"Clear saved diag requests?",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:
            self.clear_diag_requests()
    def populate_diag_combo(self):
        # Ensure combo exists before populating
        if hasattr(self, 'diag_request_combo'):
            self.diag_request_combo.blockSignals(True)
            self.diag_request_combo.clear()
            self.diag_request_combo.addItem("")
            saved_names=sorted([n for n in self.saved_diag_requests if n!='_TARGET_SYSVAR'])
            self.diag_request_combo.addItems(saved_names)
            self.diag_request_combo.blockSignals(False)
    def on_diag_combo_changed(self,index):
        name=self.diag_request_combo.itemText(index)
        if name and name in self.saved_diag_requests:
            req=self.saved_diag_requests[name]
            self.diag_request_input.setText(req)
            self.log_message(f"[DIAG] Loaded '{name}': {req}")
        elif index==0: self.diag_request_input.clear()
    def handle_diag_save(self):
        req=self.diag_request_input.text().strip()
        if not req:
            QMessageBox.warning(self,"Save Diag","Request empty.")
            return
        name,ok=QInputDialog.getText(self,"Save Diag Req","Enter name:")
        if ok and name:
            name=name.strip();
            if not name: 
                QMessageBox.warning(self,"Save Diag","Name empty.")
                return
            if name=='_TARGET_SYSVAR': 
                QMessageBox.warning(self,"Save Diag","Reserved name.")
                return
            self.saved_diag_requests[name]=req
            self.save_diag_requests()
            self.populate_diag_combo()
            idx=self.diag_request_combo.findText(name)
            if idx>=0: 
                self.diag_request_combo.setCurrentIndex(idx)
            self.log_message(f"[DIAG] Saved '{name}': {req}")
            QMessageBox.information(self,"Saved",f"Request '{name}' saved.")
        else: 
            self.log_message("[DIAG] Save cancelled.")
    def handle_diag_send(self):
        req=self.diag_request_input.text().strip()
        if not req: 
            QMessageBox.warning(self,"Send Diag","Request empty.")
            return
        if not self.canoe_app: 
            QMessageBox.warning(self,"CANoe","Not launched.")
            return
        if not WIN32COM_AVAILABLE: 
            QMessageBox.critical(self,"Error","pywin32 missing.")
            return
        target=self.saved_diag_requests.get('_TARGET_SYSVAR')
        if not target:
            target,ok=QInputDialog.getText(self,"Cfg Diag Target","Enter SysVar Name to send requests to:")
            if ok and target:
                target=target.strip();
                if target: self.saved_diag_requests['_TARGET_SYSVAR']=target; self.save_diag_requests(); self.log_message(f"[DIAG] Target SysVar set: {target}")
                else: QMessageBox.warning(self,"Error","Target empty.")
                return
            else: 
                self.log_message("[DIAG] Target cfg cancelled.")
                return
        self.log_message(f"[DIAG] Send via '{target}': {req}")
        details={'var_name':target,'value':req}
        self.execute_canoe_command('diag_send',details,save_on_success=False)

    # --- Test Queue UI Logic ---
    def add_test_to_queue(self):
        name=self.test_module_input.text().strip();
        if name: 
            self.test_queue_list.addItem(name)
            self.test_module_input.clear()
            self.log_message(f"[TEST] Added '{name}'.")
        else: 
            QMessageBox.warning(self,"Add Test","Module name empty.")
    def move_test_up(self):
        row=self.test_queue_list.currentRow()
        if row>0: 
            item=self.test_queue_list.takeItem(row)
            self.test_queue_list.insertItem(row-1,item)
            self.test_queue_list.setCurrentRow(row-1)
    def move_test_down(self):
        row=self.test_queue_list.currentRow()
        if row>=0 and row<self.test_queue_list.count()-1: 
            item=self.test_queue_list.takeItem(row)
            self.test_queue_list.insertItem(row+1,item)
            self.test_queue_list.setCurrentRow(row+1)
    def remove_test_from_queue(self):
        row=self.test_queue_list.currentRow()
        if row>=0: 
            item=self.test_queue_list.takeItem(row)
            self.log_message(f"[TEST] Removed '{item.text()}'.")
            del item
    def clear_test_queue(self):
        if QMessageBox.question(self,'Clear Queue',"Clear test queue?",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:
            self.test_queue_list.clear()
            self.log_message("[TEST] Cleared queue.")

    # --- Test Execution Logic ---
    def start_test_execution(self):
        if not self.canoe_app: 
            QMessageBox.warning(self,"CANoe","Not launched.")
            return
        if not WIN32COM_AVAILABLE: 
            QMessageBox.critical(self,"Error","pywin32 missing.")
            return
        if self.test_execution_worker and self.test_execution_worker.isRunning():
            QMessageBox.warning(self,"Busy","Test already running.")
            return
        self.current_test_queue=[self.test_queue_list.item(i).text() for i in range(self.test_queue_list.count())]
        self.log_message(f"[TEST] Start exec (Visual queue: {self.current_test_queue})")
        self.log_message("[TEST] Note: CANoe runs all enabled tests.")
        self.test_progress_bar.setValue(0)
        self.test_progress_bar.setFormat("Test Starting...")
        self.test_start_btn.setEnabled(False)
        self.test_stop_btn.setEnabled(True)
        self.test_group.setEnabled(False)
        self.test_execution_worker=TestExecutionWorker(self.canoe_app,"start_poll")
        self.test_execution_worker.signal_message.connect(self.log_message)
        self.test_execution_worker.signal_error.connect(self.on_test_execution_error)
        self.test_execution_worker.signal_progress.connect(self.on_test_progress_update)
        self.test_execution_worker.signal_finished.connect(self.on_test_execution_finished)
        self.test_execution_worker.start()
    def stop_test_execution(self):
        if not self.canoe_app: 
            QMessageBox.warning(self,"CANoe","Not launched.")
            return
        if not WIN32COM_AVAILABLE:
            QMessageBox.critical(self,"Error","pywin32 missing.")
            return
        if self.test_execution_worker and self.test_execution_worker.isRunning():
            self.test_execution_worker.requestInterruption()
            self.log_message("[TEST] Requesting Test Stop...")
            self.test_progress_bar.setFormat("Stopping...")
            stop_worker=TestExecutionWorker(self.canoe_app,"stop")
            stop_worker.signal_message.connect(self.log_message)
            stop_worker.signal_error.connect(lambda err: QMessageBox.warning(self,"Stop Error",f"Stop fail:\n{err}"))
            stop_worker.finished.connect(self.on_test_stop_sent)
            stop_worker.start()
    def on_test_progress_update(self,value,state):
        self.test_progress_bar.setValue(value)
        self.test_progress_bar.setFormat(f"Test {state}: %p%")
    def on_test_execution_error(self, error_message, is_disconnect=False): # Add is_disconnect flag
        self.log_message(f"[TEST ERR] {error_message}")
        if not is_disconnect: # Show critical only if not handled as disconnect
            QMessageBox.critical(self,"Test Error",error_message)
        self.test_progress_bar.setFormat("Error!"); self.test_progress_bar.setValue(0)
        self.update_test_exec_ui_state(is_running=False) # Method to update test UI
        self.test_execution_worker=None
        if is_disconnect:
            self.handle_disconnect_error("Test Execution")

    def on_test_execution_finished(self,final_verdict):
        self.log_message(f"[TEST] Finished. Verdict: {final_verdict}")
        self.test_progress_bar.setValue(100)
        self.test_progress_bar.setFormat(f"Finished. Verdict: {final_verdict}")
        self.test_start_btn.setEnabled(True)
        self.test_stop_btn.setEnabled(False)
        self.test_group.setEnabled(True)
        self.test_execution_worker=None
    def on_test_stop_sent(self):
        self.log_message("[TEST] Stop cmd sent.")
        self.test_stop_btn.setEnabled(False)

    # --- Configuration Handling (CANoe Paths & Settings) ---
    def load_canoe_config(self):
        def_cfg={'cfg_path':'','canoe_hidden':True};
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE,'r') as f: loaded=json.load(f); self.canoe_config={**def_cfg,**loaded}
                self.log_message(f"[INFO] Loaded cfg: {CONFIG_FILE}")
                if not isinstance(self.canoe_config.get('canoe_hidden'),bool): self.canoe_config['canoe_hidden']=def_cfg['canoe_hidden']
            except Exception as e: self.log_message(f"[ERR] Load cfg fail: {repr(e)}"); self.canoe_config=def_cfg
        else: self.log_message(f"[INFO] {CONFIG_FILE} not found."); self.canoe_config=def_cfg
    def save_canoe_config_settings(self):
        if 'cfg_path' not in self.canoe_config: 
            self.canoe_config['cfg_path']=""
        self.canoe_config['canoe_hidden']=self.chk_canoe_hidden.isChecked(); self.save_canoe_config_file()
    def save_canoe_config_file(self):
        try:
            with open(CONFIG_FILE,'w') as f: json.dump(self.canoe_config,f,indent=4)
            self.log_message(f"[INFO] Saved cfg: {CONFIG_FILE}")
        except Exception as e: 
            self.log_message(f"[ERR] Save cfg fail: {repr(e)}")
            QMessageBox.critical(self,"Error",f"Save cfg fail:\n{repr(e)}")
    def prompt_for_canoe_config(self):
        cur=self.canoe_config.get('cfg_path','')
        path,ok=QFileDialog.getOpenFileName(self,"Select CANoe CFG",os.path.dirname(cur) if cur else "","CANoe Config (*.cfg);;*")
        if ok and path: 
            self.canoe_config['cfg_path']=path
            self.log_message(f"[CFG] Set path: {path}")
            self.save_canoe_config_file()
            self.update_canoe_button_states()
        elif not ok: 
            self.log_message("[INFO] CFG select cancelled.")

    # --- CANoe Action Methods & Callbacks ---
    def launch_canoe(self):
        if self.canoe_app: 
            QMessageBox.warning(self,"CANoe","Already running.")
            return
        if not WIN32COM_AVAILABLE:
            QMessageBox.critical(self,"Error","pywin32 missing.")
            return
        if self.canoe_launch_worker and self.canoe_launch_worker.isRunning():
            QMessageBox.warning(self,"Busy","Launch/exit busy.")
            return
        self.canoe_launch_worker=CanoeWorker("launch",config=self.canoe_config)
        self.canoe_launch_worker.signal_message.connect(self.log_message)
        self.canoe_launch_worker.signal_error.connect(self.handle_canoe_error)
        self.canoe_launch_worker.signal_canoe_launched.connect(self.on_canoe_launched)
        self.canoe_launch_worker.finished.connect(self.on_launch_worker_finished)
        self.set_canoe_buttons_enabled(False); self.launch_canoe_btn.setText("Launching...")
        self.canoe_launch_worker.start()
    def exit_canoe(self):
        if not self.canoe_app: 
            self.log_message("[WARN] No CANoe object.")
            self.update_canoe_button_states()
            return
        if not WIN32COM_AVAILABLE: 
            QMessageBox.critical(self,"Error","pywin32 missing.")
            return
        if self.canoe_launch_worker and self.canoe_launch_worker.isRunning():
            QMessageBox.warning(self,"Busy","Launch/exit busy.")
            return
        self.canoe_launch_worker=CanoeWorker("exit",canoe_app=self.canoe_app)
        self.canoe_launch_worker.signal_message.connect(self.log_message)
        self.canoe_launch_worker.signal_error.connect(self.handle_canoe_error)
        self.canoe_launch_worker.signal_canoe_exited.connect(self.on_canoe_exited)
        self.canoe_launch_worker.finished.connect(self.on_launch_worker_finished)
        self.set_canoe_buttons_enabled(False)
        self.exit_canoe_btn.setText("Exiting...")
        self.canoe_launch_worker.start()
    def run_simulation(self):
        if not self.canoe_app:
            QMessageBox.warning(self,"CANoe","Not launched.")
            return
        if not self.canoe_config.get('cfg_path') or not os.path.exists(self.canoe_config['cfg_path']): 
            QMessageBox.warning(self,"Config","CFG path invalid.")
            return
        if not WIN32COM_AVAILABLE: 
            QMessageBox.critical(self,"Error","pywin32 missing.")
            return
        if self.canoe_launch_worker and self.canoe_launch_worker.isRunning(): 
            QMessageBox.warning(self,"Busy","Action busy.")
            return
        if self.test_execution_worker and self.test_execution_worker.isRunning():
            QMessageBox.warning(self, "Busy", "Stop test execution first.")
            return
        self.canoe_launch_worker=CanoeWorker("run",canoe_app=self.canoe_app)
        self.canoe_launch_worker.signal_message.connect(self.log_message)
        self.canoe_launch_worker.signal_error.connect(self.handle_canoe_error)
        self.canoe_launch_worker.signal_simulation_started.connect(self.on_simulation_started)
        self.canoe_launch_worker.finished.connect(self.on_launch_worker_finished)
        self.set_canoe_buttons_enabled(False)
        self.run_sim_btn.setText("Starting...")
        self.canoe_launch_worker.start()
    def stop_simulation(self):
        if not self.canoe_app: 
            self.log_message("[WARN] Not launched.")
            return
        if not WIN32COM_AVAILABLE:
            QMessageBox.critical(self,"Error","pywin32 missing.")
            return
        if self.canoe_launch_worker and self.canoe_launch_worker.isRunning(): 
            QMessageBox.warning(self,"Busy","Action busy.")
            return
        self.canoe_launch_worker=CanoeWorker("stop",canoe_app=self.canoe_app)
        self.canoe_launch_worker.signal_message.connect(self.log_message)
        self.canoe_launch_worker.signal_error.connect(self.handle_canoe_error)
        self.canoe_launch_worker.signal_simulation_stopped.connect(self.on_simulation_stopped)
        self.canoe_launch_worker.finished.connect(self.on_launch_worker_finished)
        self.set_canoe_buttons_enabled(False)
        self.stop_sim_btn.setText("Stopping...")
        self.canoe_launch_worker.start()
    def on_canoe_launched(self,app_object): 
        self.canoe_app=app_object; self.log_message("[OK] CANoe launched.")
    def on_canoe_exited(self): 
        self.canoe_app=None; self.log_message("[OK] CANoe exited.")
    def on_simulation_started(self): 
        self.log_message("[OK] Simulation started.")
    def on_simulation_stopped(self):
        self.log_message("[OK] Simulation stopped.")
    def handle_canoe_error(self,error_message): 
        self.log_message(error_message); QMessageBox.critical(self,"CANoe Error",error_message);
    def on_launch_worker_finished(self):
        self.log_message("[DEBUG] CANoe launch worker finished.")
        self.canoe_launch_worker=None
        self.launch_canoe_btn.setText("Launch")
        self.exit_canoe_btn.setText("Exit")
        self.run_sim_btn.setText("Run Sim")
        self.stop_sim_btn.setText("Stop Sim")
        self.update_canoe_button_states()

    # --- UI State Management ---
    def update_canoe_button_states(self):
        """ Central method to update enable/disable state of all buttons """
        com_ok = WIN32COM_AVAILABLE
        launched = com_ok and (self.canoe_app is not None)
        cfg_ok = launched and bool(self.canoe_config.get('cfg_path') and os.path.exists(self.canoe_config['cfg_path']))
        sim_running = False
        test_running = self.test_execution_worker is not None and self.test_execution_worker.isRunning()

        if launched and not test_running:
            try:
                measurement = self.canoe_app.Measurement
                if measurement: sim_running = bool(measurement.Running)
            except: pass

        ena_launch = com_ok and not launched
        ena_exit = com_ok and launched
        ena_run_sim = com_ok and cfg_ok and not sim_running and not test_running
        ena_stop_sim = com_ok and cfg_ok and sim_running
        ena_cfg_path = True
        ena_clr_panel_cmd = com_ok
        ena_diag = com_ok and launched
        ena_test_controls = com_ok and launched and not sim_running # Test group active if launched & sim stopped
        ena_start_test = ena_test_controls and not test_running # Can start if group active and not already running
        ena_stop_test = ena_test_controls and test_running # Can stop if group active and running

        # Apply states
        self.launch_canoe_btn.setEnabled(ena_launch)
        self.exit_canoe_btn.setEnabled(ena_exit)
        self.run_sim_btn.setEnabled(ena_run_sim)
        self.stop_sim_btn.setEnabled(ena_stop_sim)
        self.config_canoe_btn.setEnabled(ena_cfg_path)
        self.clear_commands_btn.setEnabled(ena_clr_panel_cmd)
        if hasattr(self, 'diag_group'): self.diag_group.setEnabled(ena_diag)
        if hasattr(self, 'test_group'): self.test_group.setEnabled(ena_test_controls)
        if hasattr(self, 'test_start_btn'): self.test_start_btn.setEnabled(ena_start_test)
        if hasattr(self, 'test_stop_btn'): self.test_stop_btn.setEnabled(ena_stop_test)

        # Tooltips
        tooltip = ""
        if not com_ok: tooltip = "pywin32 missing"
        elif not launched: tooltip = "CANoe not launched"
        elif sim_running: tooltip = "Stop simulation first"
        elif test_running: tooltip = "Test execution running"

        if hasattr(self,'test_group'): self.test_group.setToolTip(tooltip if not ena_test_controls and launched else "")
        self.run_sim_btn.setToolTip(tooltip if not ena_run_sim and launched else "")
        self.test_start_btn.setToolTip(tooltip if not ena_start_test and launched else "")
        self.launch_canoe_btn.setToolTip("Launch CANoe application" if ena_launch else ("CANoe running" if launched else tooltip))


    def set_canoe_buttons_enabled(self, enabled, message=""):
         """ Coarse enable/disable, mainly used during worker operations """
         self.launch_canoe_btn.setEnabled(enabled); self.exit_canoe_btn.setEnabled(enabled)
         self.run_sim_btn.setEnabled(enabled); self.stop_sim_btn.setEnabled(enabled)
         if hasattr(self,'diag_group'): self.diag_group.setEnabled(enabled)
         if hasattr(self,'test_group'): self.test_group.setEnabled(enabled)
         # Note: Does not handle fine-grained test start/stop state

    def log_message(self, message):
        """ Appends a message to the console log """
        self.console.append(message); self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum()); print(message)

    # --- Original Camera Methods (Using readable format) ---
    def reset_session(self):
        """ Resets camera recording session variables and UI elements """
        if hasattr(self,'timer') and self.timer.isActive():
             self.timer.stop()
        if self.cap and self.cap.isOpened():
            self.cap.release()
        if self.out and self.out.isOpened():
            self.out.release()

        self.cap = None
        self.out = None
        self.prev_frame = None
        self.start_time = None
        self.frame_index = 0
        # Set output dir to current working dir if not already set
        if not hasattr(self, 'output_dir') or not self.output_dir:
             self.output_dir = os.getcwd()

        self.csv_file = os.path.join(self.output_dir, "detection_log.csv")
        self.video_file = os.path.join(self.output_dir, "recorded_video.avi")
        self.frame_folder = os.path.join(self.output_dir, "detected_frames")
        try:
             os.makedirs(self.frame_folder, exist_ok=True)
        except OSError as e:
             self.log_message(f"[ERROR] Could not create frame folder {self.frame_folder}: {e}")

        self.detected_frames.clear()

        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.label.setText("Camera Feed")

        # Reset progress bar
        if hasattr(self, 'test_progress_bar'):
            self.test_progress_bar.setValue(0)
            self.test_progress_bar.setFormat("Test Progress: %p%")

    def update_threshold_label(self):
        """ Updates the threshold label based on slider value """
        if hasattr(self, 'threshold_slider'): # Check slider exists
             self.threshold = self.threshold_slider.value()
             self.threshold_label.setText(f"Change Threshold: {self.threshold}%")

    def choose_directory(self):
        """ Opens dialog to choose save directory """
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder", self.output_dir)
        if folder:
            self.output_dir = folder
            self.log_message(f"[INFO] Output directory set to: {self.output_dir}")
            self.reset_session() # Update paths based on new directory

    def frame_difference_percentage(self, frame1, frame2):
        """ Calculates the percentage difference between two frames """
        if frame1 is None or frame2 is None or frame1.shape != frame2.shape or frame1.dtype != frame2.dtype:
            return 0.0
        try:
            diff = cv2.absdiff(frame1, frame2)
            gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray_diff, 30, 255, cv2.THRESH_BINARY)
            non_zero_count = np.count_nonzero(thresh)
            total_pixels = thresh.size
            return (non_zero_count / total_pixels) * 100 if total_pixels > 0 else 0.0
        except cv2.error as e:
            self.log_message(f"[ERROR] OpenCV diff error: {e}")
            return 0.0

    def start_recording(self):
        device_index = int(self.camera_selector.currentText())
        self.cap = cv2.VideoCapture(device_index)
        if not self.cap.isOpened():
            self.console.append("[ERROR] Could not open camera.")
            return

        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(self.cap.get(cv2.CAP_PROP_FPS)) or 30

        self.out = cv2.VideoWriter(self.video_file, cv2.VideoWriter_fourcc(*'XVID'), fps, (width, height))
        _, self.prev_frame = self.cap.read()
        self.start_time = datetime.now()
        self.timer.start(int(1000 / fps))

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        with open(self.csv_file, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "Elapsed Time (s)", "Difference (%)", "Saved Frame"])

    def update_frame(self):
        """ Reads frame from camera, processes, displays, and saves if change detected """
        if not self.cap or not self.cap.isOpened(): self.stop_recording_ui(); return
        ret, frame = self.cap.read();
        if not ret or frame is None: self.log_message("[WARN] Frame grab fail."); self.stop_recording_ui(); return

        if self.out and self.out.isOpened(): self.out.write(frame)

        now=datetime.now(); elap=(now-self.start_time).total_seconds()
        current_threshold = self.threshold_slider.value() # Get current threshold

        if self.prev_frame is not None and self.prev_frame.shape == frame.shape:
            diff = self.frame_difference_percentage(self.prev_frame, frame)
            if diff > current_threshold:
                ts=now.strftime('%Y%m%d_%H%M%S_%f')[:-3]; fn=f"change_{ts}.jpg"; fp=os.path.join(self.frame_folder, fn)
                try:
                    if cv2.imwrite(fp, frame):
                        self.detected_frames.append(fp); self.log_message(f"[DETECT] D:{diff:.1f}% > {current_threshold}% E:{elap:.1f}s S:{fn}")
                        try:
                           with open(self.csv_file,'a',newline='') as f: csv.writer(f).writerow([ts,f"{elap:.3f}",f"{diff:.2f}",fn])
                        except IOError as e: self.log_message(f"[ERR] CSV write failed: {e}")
                        # Draw on frame shown in UI
                        cv2.putText(frame,f"Chg:{diff:.1f}%",(20,30),cv2.FONT_HERSHEY_SIMPLEX,0.7,(0,0,255),2)
                except Exception as e: self.log_message(f"[ERR] Save frame error: {e}")
        self.prev_frame = frame.copy()

        # Display frame
        try:
            rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB); h,w,ch=rgb.shape; bpl=ch*w
            img=QImage(rgb.data,w,h,bpl,QImage.Format_RGB888)
            self.label.setPixmap(QPixmap.fromImage(img).scaled(self.label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception as e:
            self.log_message(f"[ERR] Display fail: {e}"); self.stop_recording_ui()

    def stop_recording_ui(self):
        """ Stops recording and releases resources """
        if hasattr(self,'timer') and self.timer.isActive(): self.timer.stop()
        if self.cap and self.cap.isOpened(): self.cap.release()
        if self.out and self.out.isOpened(): self.out.release()
        self.cap=None; self.out=None; self.start_btn.setEnabled(True); self.stop_btn.setEnabled(False); self.log_message("[INFO] Rec stop."); self.prev_frame=None; self.label.setText("Rec Stopped.")
        if self.detected_frames and QMessageBox.question(self,'Export',f"Export {len(self.detected_frames)} frames?",QMessageBox.Yes|QMessageBox.No,QMessageBox.Yes)==QMessageBox.Yes: self.auto_export_frames()

    def auto_export_frames(self):
        """ Exports frames automatically based on radio button selection """
        if not self.detected_frames: self.log_message("[INFO] No frames to auto-export."); return
        if self.radio_gif.isChecked(): self.export_as_gif()
        else: self.export_as_video()

    def export_detected_frames(self):
        """ Handles export button click """
        if not self.detected_frames: QMessageBox.information(self,"Export","No detected frames to export."); return
        if self.radio_gif.isChecked():
            dur,ok=QInputDialog.getInt(self,"GIF Duration","ms per frame:",value=self.gif_duration,min=20,max=5000,step=10);
            if ok: self.gif_duration=dur; self.export_as_gif()
        else:
             self.export_as_video()

    def export_as_gif(self):
        """ Exports detected frames as an animated GIF """
        if not self.detected_frames: return
        path=os.path.join(self.output_dir,"detected_frames_capture.gif"); self.log_message(f"[INFO] Exporting {len(self.detected_frames)} frames as GIF..."); imgs=[]
        for p in self.detected_frames:
            try: imgs.append(imageio.imread(p))
            except Exception as e: self.log_message(f"[WARN] Skipping image {p} for GIF: {e}")
        if imgs:
            try:
                imageio.mimsave(path,imgs,duration=self.gif_duration/1000.0);
                QMessageBox.information(self,"Export Successful",f"GIF saved:\n{path}")
            except Exception as e:
                QMessageBox.critical(self,"Export Error",f"Failed GIF save:\n{e}")
                self.log_message(f"[ERROR] Failed to save GIF: {e}")
        else: self.log_message("[WARN] No valid images found for GIF.")

    def export_as_video(self):
        """ Exports detected frames as an AVI video """
        if not self.detected_frames: return
        path=os.path.join(self.output_dir,"detected_frames_capture.avi"); self.log_message(f"[INFO] Exporting {len(self.detected_frames)} frames as Video...");
        try:
            first_frame = cv2.imread(self.detected_frames[0])
            if first_frame is None: raise ValueError("First frame is invalid")
            h,w,_=first_frame.shape
        except Exception as e:
            QMessageBox.critical(self,"Export Error",f"Failed read first frame:\n{e}"); return

        fourcc=cv2.VideoWriter_fourcc(*'XVID'); fps=5; out = None
        try:
            out=cv2.VideoWriter(path,fourcc,fps,(w,h));
            if not out.isOpened(): raise IOError("VideoWriter failed")
            for p in self.detected_frames:
                try:
                    fr=cv2.imread(p)
                    if fr is not None: out.write(fr) # Write frame if successfully read
                    else: self.log_message(f"[WARN] Skipping invalid frame for video: {p}")
                except Exception as read_err: self.log_message(f"[WARN] Error reading frame {p}: {read_err}") # Log error reading frame
            out.release() # Release after loop
            QMessageBox.information(self,"Export Successful",f"Video saved:\n{path}")
        except Exception as e:
            QMessageBox.critical(self,"Export Error",f"Failed video save:\n{e}");
            self.log_message(f"[ERROR] Failed to create or write video file: {e}")
            # Ensure release even on error
            if out is not None and isinstance(out,cv2.VideoWriter) and out.isOpened(): out.release()

    # --- Cleanup on Close ---
    def closeEvent(self, event):
        """ Handles application close event, ensuring cleanup """
        self.log_message("[INFO] Closing application...")
        # Stop camera timer
        if hasattr(self,'timer') and self.timer.isActive():
            self.stop_recording_ui() # This also releases camera/video writer

        # Stop worker threads gracefully
        if self.test_execution_worker and self.test_execution_worker.isRunning():
            self.log_message("[INFO] Stopping test worker...")
            self.test_execution_worker.requestInterruption(); self.test_execution_worker.wait(2000)
        if self.canoe_launch_worker and self.canoe_launch_worker.isRunning():
            self.log_message("[INFO] Waiting for CANoe launch worker...")
            self.canoe_launch_worker.quit(); self.canoe_launch_worker.wait(2000)
        if self.canoe_cmd_worker and self.canoe_cmd_worker.isRunning():
            self.log_message("[INFO] Waiting for CANoe command worker...")
            self.canoe_cmd_worker.quit(); self.canoe_cmd_worker.wait(2000)

        # Attempt graceful CANoe exit (direct COM calls on close)
        if self.canoe_app:
             self.log_message("[INFO] Attempting CANoe exit on close...")
             try:
                  measurement = self.canoe_app.Measurement
                  if measurement and measurement.Running:
                      measurement.Stop()
                      QThread.msleep(500) # Short wait
                  self.canoe_app.Quit()
                  self.log_message("[INFO] CANoe Quit command sent.")
             except Exception as e:
                  self.log_message(f"[ERROR] Failed CANoe exit on close: {repr(e)}")
             finally:
                 self.canoe_app = None # Clear reference

        event.accept() # Proceed with closing

if __name__ == "__main__":
    # --- Set the global exception hook ---
    # Important: Do this AFTER creating QApplication but BEFORE creating the main window
    app = QApplication(sys.argv)
    sys.excepthook = handle_exception
    # ------------------------------------

    if not WIN32COM_AVAILABLE:
        QMessageBox.warning(None, "Missing Dependency", "pywin32 not found.\nInstall: pip install pywin32")

    # --- Create and show the main window within try...except ---
    window = None # Initialize window to None
    try:
        window = RearCameraTester()
        window.show()
    except Exception as init_err:
        # Catch errors during window initialization specifically
        handle_exception(type(init_err), init_err, init_err.__traceback__)
        sys.exit(1) # Exit if main window creation fails
    # ---------------------------------------------------------

    # Ensure app execution only happens if window creation succeeded
    if window:
        sys.exit(app.exec_())
    else:
         sys.exit(1) # Exit if window is still None

