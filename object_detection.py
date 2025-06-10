import cv2
import numpy as np
import os
from datetime import datetime

# --- Configuration ---
KNOWN_OBJECT_WIDTH_INCHES = 6.0  # Example: Average face width in inches
FOCAL_LENGTH_PIXELS = 700        # Example: Approximate focal length of your camera
                                 # You NEED to calibrate or estimate this for your camera.

# Directory to save detected images
SAVE_DIR = "detected_objects_with_distance"

# --- Object Detector Setup ---
try:
    object_detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    if object_detector.empty():
        raise IOError("Could not load Haar cascade classifier. Make sure the path is correct.")
except Exception as e:
    print(f"Error loading classifier: {e}")
    print("Please ensure OpenCV is installed correctly and the cascade file is accessible.")
    exit()

# --- Colors for Bounding Boxes ---
COLORS = [
    (0, 255, 0), (0, 0, 255), (255, 0, 0),
    (255, 255, 0), (0, 255, 255), (255, 0, 255),
]

# --- Helper Function for Distance Estimation ---
def estimate_distance(perceived_width_pixels, actual_object_width, focal_length):
    if perceived_width_pixels == 0:
        return 0
    return (actual_object_width * focal_length) / perceived_width_pixels

# --- Main Video Processing Loop ---
def main():
    # Create the save directory if it doesn't exist
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)
        print(f"Created directory: {SAVE_DIR}")

    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Error: Could not open video stream.")
        return

    print("Starting video stream. Press 'q' to quit.")
    print(f"Detected images will be saved in the '{SAVE_DIR}' folder.")

    frame_count_since_last_save = 0
    SAVE_IMAGE_INTERVAL = 15 # Optional: Save an image at most every N frames if detection is continuous
                             # Set to 0 or 1 to save every time an object is detected.

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Can't receive frame (stream end?). Exiting ...")
            break

        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        detected_objects = object_detector.detectMultiScale(
            gray_frame,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(40, 40)
        )

        # A flag to check if any object was detected in this frame
        object_detected_in_frame = len(detected_objects) > 0
        frame_to_save = frame.copy() # Work on a copy if you intend to save it

        for i, (x, y, w, h) in enumerate(detected_objects):
            color_index = i % len(COLORS)
            box_color = COLORS[color_index]

            cv2.rectangle(frame_to_save, (x, y), (x + w, y + h), box_color, 2) # Draw on the copy

            perceived_width_pixels = w
            distance_inches = estimate_distance(perceived_width_pixels, KNOWN_OBJECT_WIDTH_INCHES, FOCAL_LENGTH_PIXELS)

            object_label = f"Obj {i+1}"
            distance_text = f"Dist: {distance_inches:.2f} in"

            cv2.putText(frame_to_save, object_label, (x, y - 25), # Draw on the copy
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, box_color, 2)
            cv2.putText(frame_to_save, distance_text, (x, y - 5), # Draw on the copy
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, box_color, 2)

        # --- Save Image Logic ---
        if object_detected_in_frame:
            if SAVE_IMAGE_INTERVAL <= 1 or frame_count_since_last_save >= SAVE_IMAGE_INTERVAL:
                # Generate a unique filename with a timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3] # YearMonthDay_HourMinuteSecond_Millisecond
                filename = os.path.join(SAVE_DIR, f"detection_{timestamp}.jpg")

                # Save the frame (which has the drawings on it)
                cv2.imwrite(filename, frame_to_save)
                print(f"Saved: {filename}")
                frame_count_since_last_save = 0 # Reset counter
            else:
                frame_count_since_last_save += 1
        else:
            # If no object is detected, you might want to reset the counter
            # or handle it based on whether you want the interval to be strict
            # even across frames with no detections. For simplicity here,
            # we only increment when an object IS detected but too soon to save.
            pass


        # Display the resulting frame (live feed)
        cv2.imshow('Live Object Detection & Distance', frame_to_save) # Show the frame with drawings

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Video stream stopped.")

if __name__ == '__main__':
    main()