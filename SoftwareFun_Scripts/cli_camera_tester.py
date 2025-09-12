import cv2
import numpy as np
import os
import csv
import imageio
from datetime import datetime
import argparse
import time
import logging
import filelock
import tempfile
import psutil
import sys # For sys.exit()
import shutil # For copying files


def frame_difference_percentage(frame1, frame2):
    if frame1 is None or frame2 is None: return 0
    try:
        diff = cv2.absdiff(frame1, frame2)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray_diff, 30, 255, cv2.THRESH_BINARY) # Binary threshold
        non_zero_count = np.count_nonzero(thresh)
        total_pixels = thresh.shape[0] * thresh.shape[1]
        if total_pixels == 0: return 0
        return (non_zero_count / total_pixels) * 100
    except cv2.error as e:
        logging.error(f"OpenCV error in frame_difference_percentage: {e}")
        return 0
    except Exception as e:
        logging.error(f"Unexpected error in frame_difference_percentage: {e}")
        return 0

def export_media(detected_frames_paths, output_dir, export_format="gif", gif_duration_ms=200, video_fps=5):
    if not detected_frames_paths:
        logging.warning("No frames detected to export.")
        return

    if export_format == "gif":
        gif_path = os.path.join(output_dir, "detected_changes.gif")
        images = []
        for img_path in detected_frames_paths:
            try: images.append(imageio.imread(img_path))
            except FileNotFoundError: logging.warning(f"Image file not found for GIF: {img_path}. Skipping.")
            except Exception as e: logging.warning(f"Could not read image {img_path} for GIF: {e}. Skipping.")
        if images:
            try:
                imageio.mimsave(gif_path, images, duration=gif_duration_ms / 1000.0) # imageio duration is in seconds
                logging.info(f"GIF saved: {gif_path}")
            except Exception as e: logging.error(f"Failed to save GIF: {e}")
        else: logging.warning("No valid images to create GIF.")
    elif export_format == "video":
        video_path = os.path.join(output_dir, "detected_changes.avi")
        try:
            if not detected_frames_paths: # Guard against empty list for imread
                logging.warning("No detected frames to create a video from.")
                return
            first_frame_img = cv2.imread(detected_frames_paths[0])
            if first_frame_img is None:
                logging.error(f"Could not read first frame for video export: {detected_frames_paths[0]}")
                return
            height, width, _ = first_frame_img.shape
        except IndexError: logging.warning("No frames to export as video (IndexError)."); return
        except Exception as e: logging.error(f"Could not get dimensions from first frame: {e}"); return

        video_writer = None
        try:
            video_writer = cv2.VideoWriter(video_path, cv2.VideoWriter_fourcc(*'XVID'), video_fps, (width, height))
            for img_path in detected_frames_paths:
                frame = cv2.imread(img_path)
                if frame is not None: video_writer.write(frame)
                else: logging.warning(f"Could not read frame {img_path} for video. Skipping.")
            logging.info(f"Video saved: {video_path}")
        except Exception as e: logging.error(f"Failed to write video: {e}")
        finally:
            if video_writer: video_writer.release()
    else: logging.warning(f"Unknown export format: {export_format}. Choose 'gif' or 'video'.")


def find_available_camera(max_indices_to_check=5):
    for i in range(max_indices_to_check):
        cap_test = cv2.VideoCapture(i)
        if cap_test.isOpened():
            logging.info(f"Found available camera at index: {i}")
            cap_test.release()
            return i
        cap_test.release() # Release if not opened or if opening failed
    return None

def handle_script_failure(message, instance_lock_obj, pid_file_path_to_clean, cap_obj, writer_obj):
    logging.error(f"SCRIPT FAILURE: {message}")
    if cap_obj and cap_obj.isOpened():
        cap_obj.release()
        logging.info("Camera released due to failure.")
    if writer_obj:
        try:
            writer_obj.release()
            logging.info("Video writer released due to failure.")
        except Exception as e:
            logging.warning(f"Error releasing video writer during failure: {e}")

    if instance_lock_obj and instance_lock_obj.is_locked:
        instance_lock_obj.release()
        logging.info(f"Instance lock {instance_lock_obj.lock_file} released due to failure.")
        try:
            if os.path.exists(pid_file_path_to_clean):
                os.remove(pid_file_path_to_clean)
                logging.debug(f"PID file {pid_file_path_to_clean} removed.")
        except OSError as e:
            logging.warning(f"Could not remove PID file {pid_file_path_to_clean} during failure handling: {e}")
    logging.info(f"--- Application instance PID {os.getpid()} exiting with FAILURE STATUS ---")
    sys.exit(1)


def check_frame_distortion(frame, black_thresh, edge_margin_factor, solid_area_thresh, output_dir_for_tuning=None, save_tuning_frames=False, current_filename_base="distorted"):
    """
    Checks for basic frame distortion like large solid/black bars at edges.
    Saves a copy for tuning if enabled and distortion is suspected.
    Returns True if distortion is suspected, False otherwise.
    """
    if frame is None: return True # Treat None frame as a distortion/problem
    h, w = frame.shape[:2]
    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    margin_h = int(h * edge_margin_factor)
    margin_w = int(w * edge_margin_factor)

    regions_to_check = {
        "top": gray_frame[0:margin_h, :], "bottom": gray_frame[h-margin_h:h, :],
        "left": gray_frame[:, 0:margin_w], "right": gray_frame[:, w-margin_w:w]
    }
    is_distorted = False
    for region_name, region_data in regions_to_check.items():
        if region_data.size == 0: continue # Skip if region is empty (e.g., due to small frame size and large margin)
        dark_pixels = np.sum(region_data < black_thresh)
        total_pixels_in_region = region_data.size
        if total_pixels_in_region > 0 and (dark_pixels / total_pixels_in_region) >= solid_area_thresh:
            # Check standard deviation to ensure it's a 'solid' bar, not just a dark textured area
            if np.std(region_data) < 10: # Low std dev suggests a more uniform (solid) area
                logging.warning(f"Distortion suspected: Solid/dark bar detected in '{region_name}' region.")
                is_distorted = True
                break 
    
    if is_distorted and save_tuning_frames and output_dir_for_tuning:
        try:
            os.makedirs(output_dir_for_tuning, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
            save_path = os.path.join(output_dir_for_tuning, f"{current_filename_base}_{timestamp}.jpg")
            cv2.imwrite(save_path, frame)
            logging.info(f"Saved suspected distorted frame for tuning: {save_path}")
        except Exception as e:
            logging.error(f"Could not save frame for distortion tuning: {e}")
    return is_distorted

def check_lighting_and_color(frame, dark_thresh, bright_thresh, output_dir_quality, original_frame_path, save_issues=False):
    """
    Checks for overall brightness issues.
    Saves a copy to appropriate subfolder if issues detected and save_issues is True.
    Returns a list of detected issue types (e.g., ["too_dark"]).
    """
    if frame is None: return ["frame_none"]
    issues = []
    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean_brightness = np.mean(gray_frame)
    
    quality_subfolders = {
        "too_dark": os.path.join(output_dir_quality, "too_dark"),
        "too_bright": os.path.join(output_dir_quality, "too_bright"),
        "black_screen": os.path.join(output_dir_quality, "black_screen"),
    }

    # Black Screen check (very low brightness and very low variance)
    # Use a more stringent dark_thresh (e.g., half of the general dark_thresh) and low std deviation
    if mean_brightness < (dark_thresh / 2) and np.std(gray_frame) < 5: 
        issues.append("black_screen")
        if save_issues:
            try:
                os.makedirs(quality_subfolders["black_screen"], exist_ok=True)
                shutil.copy2(original_frame_path, os.path.join(quality_subfolders["black_screen"], os.path.basename(original_frame_path)))
                logging.info(f"Frame classified as black_screen and copied: {os.path.basename(original_frame_path)}")
            except Exception as e:
                logging.error(f"Could not copy frame to black_screen folder: {e}")

    elif mean_brightness < dark_thresh:
        issues.append("too_dark")
        if save_issues and "black_screen" not in issues: # Avoid double copy if already classified as black_screen
            try:
                os.makedirs(quality_subfolders["too_dark"], exist_ok=True)
                shutil.copy2(original_frame_path, os.path.join(quality_subfolders["too_dark"], os.path.basename(original_frame_path)))
                logging.info(f"Frame classified as too_dark and copied: {os.path.basename(original_frame_path)}")
            except Exception as e:
                logging.error(f"Could not copy frame to too_dark folder: {e}")
    elif mean_brightness > bright_thresh:
        issues.append("too_bright")
        if save_issues:
            try:
                os.makedirs(quality_subfolders["too_bright"], exist_ok=True)
                shutil.copy2(original_frame_path, os.path.join(quality_subfolders["too_bright"], os.path.basename(original_frame_path)))
                logging.info(f"Frame classified as too_bright and copied: {os.path.basename(original_frame_path)}")
            except Exception as e:
                logging.error(f"Could not copy frame to too_bright folder: {e}")
    
    return issues


def draw_change_rectangles(original_frame, prev_frame_for_diff, output_dir_changes_boxed, original_frame_path_to_copy, save_boxed_frames=False):
    """
    Draws green rectangles around areas of significant change.
    Saves a copy of the frame with boxes if save_boxed_frames is True.
    """
    if original_frame is None or prev_frame_for_diff is None:
        logging.warning("Cannot draw change rectangles: one or both frames are None.")
        return original_frame 

    frame_with_boxes = original_frame.copy()
    
    try:
        diff = cv2.absdiff(prev_frame_for_diff, original_frame)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh_diff = cv2.threshold(gray_diff, 30, 255, cv2.THRESH_BINARY)
        
        kernel = np.ones((5,5),np.uint8) # Kernel for dilation
        dilated_thresh = cv2.dilate(thresh_diff, kernel, iterations = 2)
        
        contours, _ = cv2.findContours(dilated_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        min_contour_area = 100 # Filter out very small changes (noise)
        num_boxes_drawn = 0
        for contour in contours:
            if cv2.contourArea(contour) > min_contour_area:
                x, y, w, h = cv2.boundingRect(contour)
                cv2.rectangle(frame_with_boxes, (x, y), (x+w, y+h), (0, 255, 0), 2) # Green box
                num_boxes_drawn +=1

        if save_boxed_frames and num_boxes_drawn > 0 : # Only save if boxes were actually drawn
            os.makedirs(output_dir_changes_boxed, exist_ok=True)
            base_name = os.path.basename(original_frame_path_to_copy)
            # Save the frame with visualizations
            viz_save_path = os.path.join(output_dir_changes_boxed, base_name.replace(".jpg", "_viz.jpg"))
            cv2.imwrite(viz_save_path, frame_with_boxes)
            logging.info(f"Saved frame with change boxes: {viz_save_path}")
            # Optionally, copy the original frame as well for reference, if needed (currently commented out)
            # shutil.copy2(original_frame_path_to_copy, os.path.join(output_dir_changes_boxed, base_name))
            
    except cv2.error as e:
        logging.error(f"OpenCV error in draw_change_rectangles: {e}")
    except Exception as e:
        logging.error(f"Could not save/process frame with change boxes: {e}")
            
    return frame_with_boxes


# --- Main Application Logic ---
def main():
    parser = argparse.ArgumentParser(description="Advanced Camera Tester - CLI. Monitors a camera feed for changes, logs activity, saves frames, and performs quality checks.")
    parser.add_argument("--camera_index", type=int, default=None, help="Specify camera index (e.g., 0, 1). Auto-detects if not set.")
    parser.add_argument("--output_dir", type=str, default=os.path.join(os.getcwd(), "camera_test_output"), help="Directory to save logs, frames, and videos.")
    parser.add_argument("--threshold", type=float, default=5.0, help="Frame difference percentage (0-100) to trigger saving of changed frames. Default: 5.0") # Adjusted default
    parser.add_argument("--fps_capture", type=int, default=30, help="Desired FPS for camera capture. Camera's actual FPS might vary. Default: 30")
    parser.add_argument("--duration", type=int, default=None, help="Maximum recording duration in seconds. Runs indefinitely if not set.")
    parser.add_argument("--export_format", type=str, default="none", choices=["gif", "video", "none"], help="Export format for detected change sequences. Default: none")
    parser.add_argument("--gif_frame_duration", type=int, default=200, help="Duration (ms) per frame in exported GIF. Default: 200ms")
    parser.add_argument("--video_export_fps", type=int, default=5, help="FPS for exported video of detected changes. Default: 5 FPS")
    parser.add_argument("--log_level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Logging level. Default: INFO")
    parser.add_argument("--no_console_log", action="store_true", help="Disable console logging (logs will still go to file).")

    # FPS/Distortion Failure args
    parser.add_argument("--min_fps_factor", type=float, default=0.70, help="Script fails if measured FPS drops below (desired_fps * min_fps_factor). Default: 0.70") # Adjusted default
    parser.add_argument("--fps_eval_interval", type=int, default=10, help="Interval (seconds) to evaluate FPS. Default: 10s")
    parser.add_argument("--enable_distortion_check", action="store_true", default=True, help="Enable checks for edge/bar distortion (can lead to script failure). Enabled by default.")
    parser.add_argument("--distortion_black_threshold", type=int, default=30, help="Pixel intensity below this is considered 'black' for distortion. Default: 30")
    parser.add_argument("--distortion_edge_margin", type=float, default=0.15, help="Percentage of frame height/width to check as edge margin. Default: 0.15 (15%%)") # Adjusted default
    parser.add_argument("--distortion_solid_area_threshold", type=float, default=0.85, help="If this percentage of an edge margin is 'black' and uniform, it's distortion. Default: 0.85 (85%%)") # Adjusted default
    
    # Enhanced analysis and organization
    parser.add_argument("--save_tuning_frames", action="store_true", help="Save frames flagged by edge/bar distortion check to a 'for_tuning_distortion' folder.")
    parser.add_argument("--enable_lighting_check", action="store_true",default=True, help="Enable checks for too_dark/too_bright frames and organize them. Enabled by default.")
    parser.add_argument("--brightness_dark_thresh", type=int, default=60, help="Mean brightness below this is 'too_dark'. Default: 60")
    parser.add_argument("--brightness_bright_thresh", type=int, default=200, help="Mean brightness above this is 'too_bright'. Default: 200")
    parser.add_argument("--draw_change_boxes", action="store_true", default=True, help="Draw green boxes on frames saved due to significant change and save these visualizations. Enabled by default.")

    args = parser.parse_args()
    
    # --- Setup Output Directories ---
    output_dir = args.output_dir 
    # Main folder for general motion-detected frames (where originals are saved)
    detected_frames_output_dir = os.path.join(output_dir, "detected_frames_capture")
    # Base directory for all quality-related sorted frames/visualizations
    quality_issues_base_dir = os.path.join(output_dir, "quality_issues")
    # Specific subdirectories under quality_issues
    tuning_distortion_output_dir = os.path.join(quality_issues_base_dir, "for_tuning_distortion")
    changes_boxed_output_dir = os.path.join(quality_issues_base_dir, "significant_change_with_boxes")
    # Note: subfolders like "too_dark", "too_bright" will be created under quality_issues_base_dir as needed.

    try: 
        os.makedirs(output_dir, exist_ok=True)
        # Other directories like detected_frames_output_dir, quality_issues_base_dir, etc.,
        # will be created as needed by the functions that use them, with exist_ok=True.
    except OSError as e: 
        print(f"[CRITICAL] Could not create base output directory {output_dir}: {e}. Exiting.")
        sys.exit(1)

    log_file_path = os.path.join(output_dir, "camera_tester_activity.log")
    logger = logging.getLogger() # Get root logger
    logger.setLevel(getattr(logging, args.log_level.upper()))
    
    # Clear any existing handlers on the root logger to avoid duplicate logs if script is re-run in same interpreter
    if logger.hasHandlers():
        logger.handlers.clear()

    file_handler = logging.FileHandler(log_file_path, mode='a') # Append mode
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - PID:%(process)d - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    if not args.no_console_log:
        console_handler = logging.StreamHandler(sys.stdout) # Explicitly use stdout
        console_formatter = logging.Formatter('%(asctime)s - %(levelname)s: %(message)s', datefmt='%H:%M:%S')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    logging.info(f"--- Application instance started with PID {os.getpid()} ---")
    logging.info(f"Output directory: {output_dir}")
    logging.debug(f"Full command line arguments: {args}")

    camera_idx_to_use = args.camera_index
    if camera_idx_to_use is None:
        logging.info("Camera index not specified. Attempting to auto-detect...")
        camera_idx_to_use = find_available_camera()
        if camera_idx_to_use is None:
            logging.error("Could not automatically find an available camera. Please ensure it is connected and not in use.")
            logging.info(f"--- Application instance PID {os.getpid()} exiting with FAILURE STATUS ---")
            sys.exit(1)
    effective_camera_idx_str = str(camera_idx_to_use) # For use in filenames/lockfiles


    lock_dir = os.path.join(tempfile.gettempdir(), "camera_tester_locks")
    try: os.makedirs(lock_dir, exist_ok=True)
    except OSError as e:
        logging.critical(f"Could not create lock directory {lock_dir}: {e}. This is required for singleton operation. Exiting.")
        sys.exit(1)

    lock_file_path = os.path.join(lock_dir, f"camera_instance_cam{effective_camera_idx_str}.lock")
    pid_file_path = os.path.join(lock_dir, f"camera_instance_cam{effective_camera_idx_str}.pid")
    instance_lock = filelock.FileLock(lock_file_path, timeout=0.1) # Small timeout to prevent indefinite block

    cap = None 
    raw_video_writer = None

    try:
        logging.debug(f"Attempting to acquire lock: {lock_file_path} for camera index {effective_camera_idx_str}")
        instance_lock.acquire()
        logging.info(f"Lock acquired by PID {os.getpid()}.")
        try:
            with open(pid_file_path, "w") as f: f.write(str(os.getpid()))
        except IOError as e: logging.warning(f"Could not write PID file {pid_file_path}: {e}")

        logging.info(f"General detected frames will be saved in: {detected_frames_output_dir}")
        try: os.makedirs(detected_frames_output_dir, exist_ok=True)
        except OSError as e: handle_script_failure(f"Could not create detected_frames_output_directory '{detected_frames_output_dir}': {e}", instance_lock, pid_file_path, cap, raw_video_writer)


        csv_file_path = os.path.join(output_dir, "detection_log.csv")
        raw_video_file_path = os.path.join(output_dir, "full_recorded_video.avi")
        detected_frames_paths_for_export = [] 
        
        # FPS monitoring variables
        desired_fps_from_cam = 0.0
        fps_eval_frame_count = 0
        fps_eval_start_time = time.time()
        distortion_strikes = 0
        max_distortion_strikes = 3 # Allow a few consecutive distorted frames before failing

        try:
            logging.info(f"Attempting to open camera index: {camera_idx_to_use}")
            cap = cv2.VideoCapture(camera_idx_to_use)
            if not cap.isOpened():
                handle_script_failure(f"Could not open camera with index {camera_idx_to_use}.", instance_lock, pid_file_path, cap, raw_video_writer)

            cap.set(cv2.CAP_PROP_FPS, args.fps_capture) # Attempt to set desired FPS
            desired_fps_from_cam = cap.get(cv2.CAP_PROP_FPS)
            if desired_fps_from_cam == 0: 
                desired_fps_from_cam = float(args.fps_capture if args.fps_capture > 0 else 30.0)
                logging.warning(f"Camera did not report FPS or reported 0. Using configured/default: {desired_fps_from_cam:.2f} FPS for checks.")
            else:
                 logging.info(f"Camera reported FPS: {desired_fps_from_cam:.2f}. This will be used as the basis for desired FPS checks.")
            
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if width == 0 or height == 0:
                handle_script_failure(f"Camera returned invalid frame dimensions ({width}x{height}). Check camera connection and drivers.", instance_lock, pid_file_path, cap, raw_video_writer)
            logging.info(f"Camera opened. Resolution: {width}x{height}, Effective Desired FPS for checks: {desired_fps_from_cam:.2f}")

            try:
                # Use the effective desired_fps_from_cam for the raw video writer for consistency
                raw_video_writer = cv2.VideoWriter(raw_video_file_path, cv2.VideoWriter_fourcc(*'XVID'), desired_fps_from_cam, (width, height))
                logging.info(f"Raw video recording to: {raw_video_file_path}")
            except Exception as e:
                handle_script_failure(f"Could not open video writer for raw recording: {e}", instance_lock, pid_file_path, cap, raw_video_writer)
            
            logging.info(f"Starting recording and monitoring. PID: {os.getpid()}. Press Ctrl+C to stop.")
            
            # Setup CSV file with headers
            try:
                # Create/overwrite CSV at start of session for this instance
                with open(csv_file_path, mode='w', newline='') as file_csv:
                    csv_writer_obj = csv.writer(file_csv)
                    csv_writer_obj.writerow(["Timestamp", "Session Elapsed Time (s)", "Difference (%)", "Saved Frame Path", "Quality Issues Detected"])
            except IOError as e:
                # Log error but try to continue; CSV logging is not critical path for capture
                logging.error(f"Could not open or write initial CSV header to {csv_file_path}: {e}")


            ret, prev_frame = cap.read()
            if not ret or prev_frame is None:
                handle_script_failure("Could not read the first frame from the camera. Ensure it's working correctly.", instance_lock, pid_file_path, cap, raw_video_writer)
            
            # Initial frame distortion check
            if args.enable_distortion_check and check_frame_distortion(prev_frame, args.distortion_black_threshold, args.distortion_edge_margin, 
                                                                    args.distortion_solid_area_threshold, 
                                                                    tuning_distortion_output_dir, args.save_tuning_frames, "initial_frame_distorted"):
                handle_script_failure("Initial frame appears distorted by edge/bar check. Please check camera view or adjust distortion parameters.", instance_lock, pid_file_path, cap, raw_video_writer)

            session_start_time = datetime.now()
            last_status_log_time = time.time()
            fps_eval_start_time = time.time() # Reset after initial setup

            while True:
                current_time_dt = datetime.now()
                current_time_ts = time.time()
                session_elapsed_seconds = (current_time_dt - session_start_time).total_seconds()

                if args.duration and session_elapsed_seconds > args.duration:
                    logging.info(f"Specified duration of {args.duration} seconds reached. Stopping.")
                    if not args.no_console_log: print(f"\nSpecified duration of {args.duration}s reached.")
                    break

                ret, frame = cap.read()
                fps_eval_frame_count += 1

                if not ret or frame is None:
                    logging.warning("Could not read frame from camera. Stream may have ended or camera disconnected.")
                    # This will likely be caught by FPS check if persistent, or script might end if cap is truly closed.
                    time.sleep(0.5) # Brief pause before trying again or failing
                    if not cap.isOpened(): # If camera explicitly closed
                        logging.error("Camera is no longer open. Ending capture loop.")
                        break
                    # Try one more read attempt
                    ret, frame = cap.read()
                    if not ret or frame is None:
                         handle_script_failure("Failed to read frame persistently. Camera disconnected or error.", instance_lock, pid_file_path, cap, raw_video_writer)
                    # If second attempt works, log it and continue
                    logging.info("Recovered frame read after one failed attempt.")
                
                frame_base_name_for_issues = f"frame_{current_time_dt.strftime('%Y%m%d_%H%M%S_%f')[:-3]}"
                if args.enable_distortion_check:
                    if check_frame_distortion(frame, args.distortion_black_threshold, args.distortion_edge_margin, 
                                              args.distortion_solid_area_threshold, 
                                              tuning_distortion_output_dir, args.save_tuning_frames, frame_base_name_for_issues):
                        distortion_strikes += 1
                        logging.warning(f"Edge/bar distortion detected (Strike {distortion_strikes}/{max_distortion_strikes}).")
                        if distortion_strikes >= max_distortion_strikes:
                            handle_script_failure(f"Maximum edge/bar distortion strikes ({max_distortion_strikes}) reached. Check camera for persistent obstruction or corruption.", instance_lock, pid_file_path, cap, raw_video_writer)
                    else:
                        distortion_strikes = 0 # Reset strikes if frame is okay

                if raw_video_writer: raw_video_writer.write(frame)

                diff_percent = 0.0
                if prev_frame is not None:
                    diff_percent = frame_difference_percentage(prev_frame, frame)
                
                # Status Log (every ~5 seconds to console if not quiet, and to debug log)
                if current_time_ts - last_status_log_time > 5:
                    status_message = f"Time: {session_elapsed_seconds:.1f}s | Last Diff: {diff_percent:.2f}% | Frames Saved (this session): {len(detected_frames_paths_for_export)}"
                    logging.debug(status_message) # Always log to debug
                    if not args.no_console_log: 
                        sys.stdout.write(f"\r{status_message}   ") # Overwrite previous status line
                        sys.stdout.flush()
                    last_status_log_time = current_time_ts


                if diff_percent > args.threshold:
                    timestamp_str_file = current_time_dt.strftime('%Y%m%d_%H%M%S_%f')[:-3]
                    filename_base = f"change_{timestamp_str_file}"
                    original_saved_path = os.path.join(detected_frames_output_dir, f"{filename_base}.jpg")
                    
                    quality_issues_detected_list = [] # For this specific frame

                    try:
                        cv2.imwrite(original_saved_path, frame)
                        detected_frames_paths_for_export.append(original_saved_path)
                        if not args.no_console_log: 
                            sys.stdout.write("\n") # Newline after status message if printing detection
                            sys.stdout.flush()
                        logging.info(f"CHANGE DETECTED ({diff_percent:.2f}%): Saved original frame: {os.path.basename(original_saved_path)}")

                        # Advanced Analysis & Organization on Saved Frame
                        if args.draw_change_boxes and prev_frame is not None: # Need prev_frame for diff
                            draw_change_rectangles(frame, prev_frame, changes_boxed_output_dir, original_saved_path, True)
                        
                        if args.enable_lighting_check:
                            # Ensure quality_issues_base_dir exists before calling check that might write to its subfolders
                            os.makedirs(quality_issues_base_dir, exist_ok=True) 
                            lighting_issues = check_lighting_and_color(frame, args.brightness_dark_thresh, args.brightness_bright_thresh,
                                                                       quality_issues_base_dir, original_saved_path, True)
                            quality_issues_detected_list.extend(lighting_issues)
                        
                        # CSV Logging for this detected frame
                        try:
                            with open(csv_file_path, mode='a', newline='') as file_csv_append: # Append mode
                                csv_writer_obj = csv.writer(file_csv_append)
                                csv_writer_obj.writerow([timestamp_str_file, 
                                                         f"{session_elapsed_seconds:.3f}", 
                                                         f"{diff_percent:.2f}", 
                                                         original_saved_path, # Log full or relative path as preferred
                                                         ", ".join(quality_issues_detected_list) if quality_issues_detected_list else "None"])
                        except IOError as e_csv: logging.error(f"Could not append to CSV file {csv_file_path}: {e_csv}")

                    except cv2.error as e_cv: 
                        if not args.no_console_log: sys.stdout.write("\n"); sys.stdout.flush()
                        logging.error(f"OpenCV error saving frame {filename_base}.jpg: {e_cv}")
                    except Exception as e_gen:
                        if not args.no_console_log: sys.stdout.write("\n"); sys.stdout.flush()
                        logging.error(f"Could not save or process frame {filename_base}.jpg: {e_gen}")
                
                prev_frame = frame.copy() # Essential for next iteration's difference calculation

                # FPS Evaluation
                current_eval_time = time.time()
                if (current_eval_time - fps_eval_start_time) >= args.fps_eval_interval:
                    if fps_eval_frame_count > 0 and (current_eval_time - fps_eval_start_time) > 0: # Avoid division by zero
                        actual_measured_fps = fps_eval_frame_count / (current_eval_time - fps_eval_start_time)
                        logging.info(f"FPS Evaluation: Measured ~{actual_measured_fps:.2f} FPS over last {args.fps_eval_interval}s. (Target based on camera: {desired_fps_from_cam:.2f} FPS)")
                        
                        # Check if FPS is critically low
                        min_acceptable_fps = desired_fps_from_cam * args.min_fps_factor
                        if desired_fps_from_cam > 0 and actual_measured_fps < min_acceptable_fps:
                            handle_script_failure(f"Measured FPS ({actual_measured_fps:.2f}) is below threshold ({min_acceptable_fps:.2f} FPS, factor {args.min_fps_factor} of desired {desired_fps_from_cam:.2f}). Check camera performance or system load.",
                                                  instance_lock, pid_file_path, cap, raw_video_writer)
                    else:
                        logging.warning("FPS Evaluation: No frames processed in the interval or interval too short.")
                    
                    fps_eval_frame_count = 0 # Reset for next interval
                    fps_eval_start_time = current_eval_time


        except KeyboardInterrupt:
            if not args.no_console_log: sys.stdout.write("\n"); sys.stdout.flush() # Ensure newline after status
            logging.info("Recording stopped by user (Ctrl+C).")
        except Exception as e: 
            if not args.no_console_log: sys.stdout.write("\n"); sys.stdout.flush()
            # This will catch unexpected errors during the main loop
            handle_script_failure(f"An unexpected error occurred during main recording loop: {e}", instance_lock, pid_file_path, cap, raw_video_writer)
        finally: 
            # Inner finally for normal resource release from this specific session
            if not args.no_console_log and sys.stdout.isatty(): # check if tty to avoid issues if stdout is redirected
                 sys.stdout.write("\n") # Ensure a clean line after loop finishes or is interrupted
                 sys.stdout.flush()
            logging.info("Attempting to release camera and video writer resources (inner finally)...")
            if cap and cap.isOpened(): cap.release(); logging.debug("Camera released.")
            if raw_video_writer: raw_video_writer.release(); logging.debug("Raw video writer released.")
            # cv2.destroyAllWindows() # Generally not needed for CLI scripts without cv2.imshow()

            logging.info("Recording session processing finished by this instance.")
            if args.export_format != "none" and detected_frames_paths_for_export:
                logging.info(f"Exporting {len(detected_frames_paths_for_export)} detected frames as {args.export_format}...")
                export_media(detected_frames_paths_for_export, output_dir, args.export_format, args.gif_frame_duration, args.video_export_fps)
            elif args.export_format != "none":
                logging.info(f"Export requested ({args.export_format}) but no frames were saved for export.")


    except filelock.Timeout:
        pid_from_file = "UNKNOWN"
        other_instance_running = False
        try:
            with open(pid_file_path, "r") as f_pid: pid_from_file = int(f_pid.read().strip())
            if psutil.pid_exists(pid_from_file):
                 logging.warning(f"Another instance (PID {pid_from_file}) is already running for camera {effective_camera_idx_str} using lock {lock_file_path}. This instance (PID {os.getpid()}) will exit.")
                 other_instance_running = True
            else: # Stale lock
                logging.warning(f"Lock file {lock_file_path} exists but PID {pid_from_file} from {pid_file_path} is not running. This may be a stale lock. This instance (PID {os.getpid()}) will exit. Manual cleanup of lock files in {lock_dir} might be needed if this persists.")
        except (IOError, FileNotFoundError, ValueError): 
            # PID file might not exist, be unreadable, or contain invalid content
            logging.warning(f"Lock file {lock_file_path} is held, but PID file {pid_file_path} is missing or unreadable. Another instance may be running for cam {effective_camera_idx_str}. This instance (PID {os.getpid()}) will exit.")
        
        # Common exit message for lock timeout
        logging.info(f"--- Application instance PID {os.getpid()} exiting due to existing lock or stale lock condition ---")
        sys.exit(0) # Graceful exit if another instance is believed to be running

    except Exception as e: 
        # Catch any other top-level errors (e.g., during initial setup before main try block for operations)
        logging.exception(f"A critical untrapped error occurred at the top level: {e}") # .exception includes stack trace
        # Attempt cleanup even for these errors; pass None for cap/writer if they weren't initialized
        handle_script_failure(f"Critical untrapped error: {e}", instance_lock, pid_file_path, cap, raw_video_writer)
    finally: 
        # Outer finally ensures lock is released if this instance acquired it
        if instance_lock.is_locked: # Check if this specific instance holds the lock
            instance_lock.release()
            logging.info(f"Lock {lock_file_path} released by PID {os.getpid()}.")
            try:
                if os.path.exists(pid_file_path): os.remove(pid_file_path)
                logging.debug(f"PID file {pid_file_path} removed by PID {os.getpid()}.")
            except OSError as e: logging.warning(f"Could not remove PID file {pid_file_path}: {e}")
        logging.info(f"--- Application instance PID {os.getpid()} ended ---")


if __name__ == "__main__":
    main()