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
import sys
import shutil
from skimage.metrics import structural_similarity as ssim

# --- Comparison Method Implementations ---

def compare_pixel_diff(frame1, frame2, **kwargs):
    """
    Compares two frames using absolute pixel difference and thresholding.
    Returns a percentage of difference.
    """
    if frame1 is None or frame2 is None: return 0
    try:
        diff = cv2.absdiff(frame1, frame2)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray_diff, 30, 255, cv2.THRESH_BINARY)
        non_zero_count = np.count_nonzero(thresh)
        total_pixels = thresh.shape[0] * thresh.shape[1]
        if total_pixels == 0: return 0
        return (non_zero_count / total_pixels) * 100
    except cv2.error as e:
        logging.error(f"OpenCV error in compare_pixel_diff: {e}")
        return 0

def compare_ssim(frame1, frame2, **kwargs):
    """
    Compares two frames using the Structural Similarity Index (SSIM).
    Returns a "dissimilarity" percentage.
    """
    if frame1 is None or frame2 is None: return 0
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    (score, _) = ssim(gray1, gray2, full=True)
    # Return dissimilarity percentage
    return (1 - score) * 100

def compare_background_subtraction(frame, back_sub_model, **kwargs):
    """
    Uses a background subtraction model to find foreground objects.
    Returns the percentage of the frame that is foreground.
    """
    if frame is None or back_sub_model is None: return 0
    fg_mask = back_sub_model.apply(frame)
    non_zero_count = np.count_nonzero(fg_mask)
    total_pixels = fg_mask.shape[0] * fg_mask.shape[1]
    if total_pixels == 0: return 0
    return (non_zero_count / total_pixels) * 100

def run_comparison_method(method, frame1, frame2, back_sub_model=None):
    """Router to call the selected comparison function."""
    if method == 'pixel_diff':
        return compare_pixel_diff(frame1, frame2)
    elif method == 'ssim':
        return compare_ssim(frame1, frame2)
    elif method == 'background_subtraction':
        return compare_background_subtraction(frame1, back_sub_model)
    else:
        logging.error(f"Unknown comparison method: {method}")
        return 0

# --- Media and File Operations ---

def export_media(detected_frames_paths, output_dir, export_format="gif", gif_duration_ms=200, video_fps=5):
    """Exports detected frames as a GIF or video."""
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
                imageio.mimsave(gif_path, images, duration=gif_duration_ms / 1000.0)
                logging.info(f"GIF saved: {gif_path}")
            except Exception as e: logging.error(f"Failed to save GIF: {e}")
        else: logging.warning("No valid images to create GIF.")
    elif export_format == "video":
        video_path = os.path.join(output_dir, "detected_changes.avi")
        try:
            if not detected_frames_paths: return
            first_frame_img = cv2.imread(detected_frames_paths[0])
            if first_frame_img is None:
                logging.error(f"Could not read first frame for video export: {detected_frames_paths[0]}")
                return
            height, width, _ = first_frame_img.shape
            video_writer = cv2.VideoWriter(video_path, cv2.VideoWriter_fourcc(*'XVID'), video_fps, (width, height))
            for img_path in detected_frames_paths:
                frame = cv2.imread(img_path)
                if frame is not None: video_writer.write(frame)
                else: logging.warning(f"Could not read frame {img_path} for video. Skipping.")
            video_writer.release()
            logging.info(f"Video saved: {video_path}")
        except Exception as e: logging.error(f"Failed to write video: {e}")
    else: logging.warning(f"Unknown export format: {export_format}. Choose 'gif' or 'video'.")

def _save_quality_issue_frame(original_path, quality_base_dir, issue_name):
    """Helper function to save a frame to a specific quality issue subfolder."""
    issue_dir = os.path.join(quality_base_dir, issue_name)
    try:
        os.makedirs(issue_dir, exist_ok=True)
        shutil.copy2(original_path, os.path.join(issue_dir, os.path.basename(original_path)))
        logging.info(f"Frame classified as {issue_name} and copied: {os.path.basename(original_path)}")
    except Exception as e:
        logging.error(f"Could not copy frame to {issue_name} folder: {e}")

# --- Core Logic and Checks ---

def find_available_camera(max_indices_to_check=5):
    """Finds the first available camera index."""
    for i in range(max_indices_to_check):
        cap_test = cv2.VideoCapture(i)
        if cap_test.isOpened():
            logging.info(f"Found available camera at index: {i}")
            cap_test.release()
            return i
        cap_test.release()
    return None

def handle_script_failure(message, instance_lock_obj, pid_file_path_to_clean, cap_obj, writer_obj):
    """Centralized failure handler for graceful shutdown."""
    logging.error(f"SCRIPT FAILURE: {message}")
    if cap_obj and cap_obj.isOpened(): cap_obj.release()
    if writer_obj: writer_obj.release()
    if instance_lock_obj and instance_lock_obj.is_locked:
        instance_lock_obj.release()
        try:
            if os.path.exists(pid_file_path_to_clean): os.remove(pid_file_path_to_clean)
        except OSError as e:
            logging.warning(f"Could not remove PID file {pid_file_path_to_clean}: {e}")
    logging.info(f"--- Application instance PID {os.getpid()} exiting with FAILURE STATUS ---")
    sys.exit(1)

def check_frame_distortion(frame, black_thresh, edge_margin_factor, solid_area_thresh, std_dev_thresh, output_dir_for_tuning=None, save_tuning_frames=False, current_filename_base="distorted"):
    """Checks for basic frame distortion like large solid/black bars at edges."""
    if frame is None: return True
    h, w = frame.shape[:2]
    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    margin_h, margin_w = int(h * edge_margin_factor), int(w * edge_margin_factor)
    regions_to_check = {
        "top": gray_frame[0:margin_h, :], "bottom": gray_frame[h - margin_h:h, :],
        "left": gray_frame[:, 0:margin_w], "right": gray_frame[:, w - margin_w:w]
    }
    for name, region in regions_to_check.items():
        if region.size == 0: continue
        dark_pixels = np.sum(region < black_thresh)
        if (dark_pixels / region.size) >= solid_area_thresh and np.std(region) < std_dev_thresh:
            logging.warning(f"Distortion suspected: Solid/dark bar detected in '{name}' region.")
            if save_tuning_frames and output_dir_for_tuning:
                try:
                    os.makedirs(output_dir_for_tuning, exist_ok=True)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
                    save_path = os.path.join(output_dir_for_tuning, f"{current_filename_base}_{timestamp}.jpg")
                    cv2.imwrite(save_path, frame)
                    logging.info(f"Saved suspected distorted frame for tuning: {save_path}")
                except Exception as e:
                    logging.error(f"Could not save frame for distortion tuning: {e}")
            return True
    return False

def check_lighting_and_color(frame, dark_thresh, bright_thresh, black_screen_std_dev, output_dir_quality, original_frame_path, save_issues=False):
    """Checks for overall brightness issues and saves problematic frames."""
    if frame is None: return ["frame_none"]
    issues = []
    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean_brightness = np.mean(gray_frame)

    if mean_brightness < (dark_thresh / 2) and np.std(gray_frame) < black_screen_std_dev:
        issues.append("black_screen")
        if save_issues: _save_quality_issue_frame(original_path, output_dir_quality, "black_screen")
    elif mean_brightness < dark_thresh:
        issues.append("too_dark")
        if save_issues: _save_quality_issue_frame(original_path, output_dir_quality, "too_dark")
    elif mean_brightness > bright_thresh:
        issues.append("too_bright")
        if save_issues: _save_quality_issue_frame(original_path, output_dir_quality, "too_bright")
    return issues

def draw_change_rectangles(original_frame, prev_frame_for_diff, min_contour_area, output_dir_changes_boxed, original_frame_path_to_copy, save_boxed_frames=False):
    """Draws green rectangles around areas of significant change."""
    if original_frame is None or prev_frame_for_diff is None: return original_frame
    frame_with_boxes = original_frame.copy()
    try:
        diff = cv2.absdiff(prev_frame_for_diff, original_frame)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh_diff = cv2.threshold(gray_diff, 30, 255, cv2.THRESH_BINARY)
        dilated_thresh = cv2.dilate(thresh_diff, np.ones((5, 5), np.uint8), iterations=2)
        contours, _ = cv2.findContours(dilated_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        num_boxes_drawn = 0
        for contour in contours:
            if cv2.contourArea(contour) > min_contour_area:
                x, y, w, h = cv2.boundingRect(contour)
                cv2.rectangle(frame_with_boxes, (x, y), (x + w, y + h), (0, 255, 0), 2)
                num_boxes_drawn += 1
        if save_boxed_frames and num_boxes_drawn > 0:
            os.makedirs(output_dir_changes_boxed, exist_ok=True)
            viz_save_path = os.path.join(output_dir_changes_boxed, os.path.basename(original_frame_path_to_copy).replace(".jpg", "_viz.jpg"))
            cv2.imwrite(viz_save_path, frame_with_boxes)
            logging.info(f"Saved frame with change boxes: {viz_save_path}")
    except Exception as e:
        logging.error(f"Could not save/process frame with change boxes: {e}")
    return frame_with_boxes

# --- Main Application Logic ---
def main():
    parser = argparse.ArgumentParser(description="Automated Camera Tester for CI/CD environments like Jenkins.")
    # --- REQUIRED ARGUMENT FOR JENKINS ---
    parser.add_argument("--master_image", type=str, required=True, help="[REQUIRED] Path to the master image file for comparison.")
    
    # --- General and Optional Arguments ---
    parser.add_argument("--camera_index", type=int, default=None, help="Specify camera index. Auto-detects if not set.")
    parser.add_argument("--output_dir", type=str, default=os.path.join(os.getcwd(), "camera_test_output"), help="Directory for all outputs.")
    parser.add_argument("--duration", type=int, default=60, help="Maximum recording duration in seconds.")
    parser.add_argument("--log_level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Logging level.")
    parser.add_argument("--no_console_log", action="store_true", help="Disable console logging.")
    
    # Capture & Export Args
    parser.add_argument("--fps_capture", type=int, default=30, help="Desired FPS for camera capture.")
    parser.add_argument("--video_codec", type=str, default="XVID", help="Codec for raw video output (e.g., XVID, mp4v).")
    parser.add_argument("--export_format", type=str, default="none", choices=["gif", "video", "none"], help="Export format for detected changes.")
    parser.add_argument("--gif_frame_duration", type=int, default=200, help="Duration (ms) per frame in exported GIF.")
    parser.add_argument("--video_export_fps", type=int, default=5, help="FPS for exported video of changes.")
    
    # Comparison & Detection Args
    parser.add_argument("--compare_method", type=str, default="pixel_diff", choices=["pixel_diff", "ssim", "background_subtraction"], help="Method for frame comparison.")
    parser.add_argument("--threshold", type=float, default=10.0, help="Difference percentage (0-100) to trigger change detection.")
    parser.add_argument("--draw_change_boxes", action="store_true", default=True, help="Draw boxes on changed frames and save visualizations.")
    parser.add_argument("--min_change_area", type=int, default=100, help="Minimum contour area to be considered a change.")
    
    # Performance & Failure Args
    parser.add_argument("--min_fps_factor", type=float, default=0.70, help="Script fails if measured FPS drops below (desired_fps * this factor).")
    parser.add_argument("--fps_eval_interval", type=int, default=10, help="Interval (seconds) to evaluate FPS.")
    
    # Quality Check Args
    parser.add_argument("--enable_distortion_check", action="store_true", default=True, help="Enable checks for edge/bar distortion.")
    parser.add_argument("--distortion_black_threshold", type=int, default=30, help="Pixel intensity below this is 'black' for distortion.")
    parser.add_argument("--distortion_edge_margin", type=float, default=0.15, help="Percentage of frame to check as edge margin.")
    parser.add_argument("--distortion_solid_area_threshold", type=float, default=0.85, help="Percentage of margin that must be 'black' to flag distortion.")
    parser.add_argument("--distortion_std_dev_thresh", type=int, default=10, help="Max standard deviation for a 'solid' bar.")
    parser.add_argument("--save_tuning_frames", action="store_true", help="Save frames flagged by distortion check for tuning.")
    
    parser.add_argument("--enable_lighting_check", action="store_true", default=True, help="Enable checks for lighting issues.")
    parser.add_argument("--brightness_dark_thresh", type=int, default=60, help="Mean brightness below this is 'too_dark'.")
    parser.add_argument("--brightness_bright_thresh", type=int, default=200, help="Mean brightness above this is 'too_bright'.")
    parser.add_argument("--black_screen_std_dev_thresh", type=int, default=5, help="Max standard deviation for a 'black_screen' frame.")

    args = parser.parse_args()
    
    # --- Setup Output Directories ---
    os.makedirs(args.output_dir, exist_ok=True)
    detected_frames_output_dir = os.path.join(args.output_dir, "detected_frames_capture")
    quality_issues_base_dir = os.path.join(args.output_dir, "quality_issues")
    tuning_distortion_output_dir = os.path.join(quality_issues_base_dir, "for_tuning_distortion")
    changes_boxed_output_dir = os.path.join(quality_issues_base_dir, "significant_change_with_boxes")

    # --- Setup Logging ---
    log_file_path = os.path.join(args.output_dir, "camera_tester_activity.log")
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, args.log_level.upper()))
    if logger.hasHandlers(): logger.handlers.clear()
    file_handler = logging.FileHandler(log_file_path, mode='a')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - PID:%(process)d - %(message)s'))
    logger.addHandler(file_handler)
    if not args.no_console_log:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s: %(message)s', datefmt='%H:%M:%S'))
        logger.addHandler(console_handler)

    logging.info(f"--- Application instance started with PID {os.getpid()} in AUTOMATED mode ---")
    logging.debug(f"Full command line arguments: {sys.argv}")

    # --- Setup Singleton Lock ---
    lock_dir = os.path.join(tempfile.gettempdir(), "camera_tester_locks")
    os.makedirs(lock_dir, exist_ok=True)
    
    camera_idx_to_use = args.camera_index if args.camera_index is not None else find_available_camera()
    if camera_idx_to_use is None:
        logging.error("Could not find an available camera.")
        sys.exit(1)

    lock_file_path = os.path.join(lock_dir, f"camera_instance_cam{camera_idx_to_use}.lock")
    pid_file_path = os.path.join(lock_dir, f"camera_instance_cam{camera_idx_to_use}.pid")
    instance_lock = filelock.FileLock(lock_file_path, timeout=0.1)
    
    cap, raw_video_writer, master_frame = None, None, None

    try:
        instance_lock.acquire()
        with open(pid_file_path, "w") as f: f.write(str(os.getpid()))
        logging.info(f"Lock acquired by PID {os.getpid()} for camera index {camera_idx_to_use}.")
        
        # --- Load Master Image ---
        logging.info(f"Loading master image from: {args.master_image}")
        master_frame = cv2.imread(args.master_image)
        if master_frame is None:
            raise FileNotFoundError(f"Master image not found or could not be read: {args.master_image}")
        logging.info("Master image loaded successfully.")

        os.makedirs(detected_frames_output_dir, exist_ok=True)
        csv_file_path = os.path.join(args.output_dir, "detection_log.csv")
        with open(csv_file_path, mode='w', newline='') as f:
            csv.writer(f).writerow(["Timestamp", "Session Elapsed (s)", "Difference (%)", "Method", "Saved Frame", "Quality Issues"])

        # --- Camera and Video Writer Initialization ---
        cap = cv2.VideoCapture(camera_idx_to_use)
        if not cap.isOpened(): raise RuntimeError(f"Could not open camera index {camera_idx_to_use}.")
        
        cap.set(cv2.CAP_PROP_FPS, args.fps_capture)
        desired_fps = cap.get(cv2.CAP_PROP_FPS) or float(args.fps_capture)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if width == 0 or height == 0: raise RuntimeError("Camera returned invalid frame dimensions.")
        
        logging.info(f"Camera opened: {width}x{height} @ {desired_fps:.2f} FPS (target).")

        raw_video_path = os.path.join(args.output_dir, "full_recorded_video.avi")
        raw_video_writer = cv2.VideoWriter(raw_video_path, cv2.VideoWriter_fourcc(*args.video_codec), desired_fps, (width, height))
        
        # --- Main Loop ---
        logging.info(f"Starting monitoring for {args.duration} seconds.")
        
        back_sub_model = None
        if args.compare_method == 'background_subtraction':
            back_sub_model = cv2.createBackgroundSubtractorKNN()
            logging.info("Using Background Subtraction method. Allowing model to warm up.")

        session_start_time = time.time()
        fps_eval_start_time = time.time()
        fps_eval_frame_count, distortion_strikes = 0, 0
        detected_frames_paths = []

        while True:
            elapsed = time.time() - session_start_time
            if elapsed > args.duration:
                logging.info(f"Configured duration of {args.duration}s reached.")
                break

            ret, frame = cap.read()
            if not ret:
                logging.warning("Could not read frame from camera stream.")
                if not cap.isOpened(): break
                time.sleep(0.5)
                ret, frame = cap.read()
                if not ret: raise RuntimeError("Failed to read frame persistently.")
            
            fps_eval_frame_count += 1
            if raw_video_writer: raw_video_writer.write(frame)

            # --- Run Checks and Comparison ---
            if args.enable_distortion_check:
                if check_frame_distortion(frame, args.distortion_black_threshold, args.distortion_edge_margin, args.distortion_solid_area_threshold, args.distortion_std_dev_thresh, tuning_distortion_output_dir, args.save_tuning_frames):
                    distortion_strikes += 1
                    if distortion_strikes >= 3: raise RuntimeError("Max distortion strikes reached.")
                else:
                    distortion_strikes = 0

            # Compare current frame to the pre-loaded master frame
            diff_percent = run_comparison_method(args.compare_method, frame, master_frame, back_sub_model)
            
            if diff_percent > args.threshold:
                timestamp = datetime.now()
                ts_str = timestamp.strftime('%Y%m%d_%H%M%S_%f')[:-3]
                filename = f"change_{ts_str}.jpg"
                save_path = os.path.join(detected_frames_output_dir, filename)
                
                cv2.imwrite(save_path, frame)
                detected_frames_paths.append(save_path)
                logging.info(f"CHANGE DETECTED vs MASTER ({diff_percent:.2f}%): Saved frame {filename}")

                quality_issues = []
                if args.enable_lighting_check:
                    os.makedirs(quality_issues_base_dir, exist_ok=True)
                    quality_issues = check_lighting_and_color(frame, args.brightness_dark_thresh, args.brightness_bright_thresh, args.black_screen_std_dev_thresh, quality_issues_base_dir, save_path, True)
                
                if args.draw_change_boxes and args.compare_method != 'background_subtraction':
                    draw_change_rectangles(frame, master_frame, args.min_change_area, changes_boxed_output_dir, save_path, True)

                with open(csv_file_path, 'a', newline='') as f:
                    csv.writer(f).writerow([ts_str, f"{elapsed:.2f}", f"{diff_percent:.2f}", args.compare_method, save_path, ", ".join(quality_issues) or "None"])

            # --- FPS Evaluation ---
            eval_interval = time.time() - fps_eval_start_time
            if eval_interval >= args.fps_eval_interval:
                actual_fps = fps_eval_frame_count / eval_interval
                logging.info(f"FPS Check: Measured ~{actual_fps:.2f} FPS over last {eval_interval:.1f}s.")
                if actual_fps < (desired_fps * args.min_fps_factor):
                    raise RuntimeError(f"Measured FPS ({actual_fps:.2f}) is below threshold.")
                fps_eval_frame_count = 0
                fps_eval_start_time = time.time()

    except (KeyboardInterrupt, SystemExit) as e:
        logging.info(f"Script stopped by user or system exit: {type(e).__name__}")
    except filelock.Timeout:
        logging.warning(f"Another instance is already running for camera {camera_idx_to_use}. This instance will exit.")
    except Exception as e:
        handle_script_failure(f"A critical error occurred: {e}", instance_lock, pid_file_path, cap, raw_video_writer)
    finally:
        if cap and cap.isOpened(): cap.release()
        if raw_video_writer: raw_video_writer.release()
        logging.info("Camera and video writer released.")

        if args.export_format != "none" and detected_frames_paths:
            logging.info(f"Exporting {len(detected_frames_paths)} frames as {args.export_format}...")
            export_media(detected_frames_paths, args.output_dir, args.export_format, args.gif_frame_duration, args.video_export_fps)
        
        if instance_lock.is_locked:
            instance_lock.release()
            try:
                if os.path.exists(pid_file_path): os.remove(pid_file_path)
            except OSError: pass
            logging.info(f"Lock released by PID {os.getpid()}.")
        
        logging.info(f"--- Application instance PID {os.getpid()} ended ---")

if __name__ == "__main__":
    main()