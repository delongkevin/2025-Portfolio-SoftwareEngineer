import sys
import cv2
import numpy as np
import os
import csv
import imageio
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QSlider, QFileDialog, QTextEdit, QRadioButton, QButtonGroup,
    QInputDialog
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap

class RearCameraTester(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rear Camera Startup Performance Tester")
        self.setGeometry(100, 100, 1000, 750)

        self.output_dir = os.getcwd()
        self.detected_frames = []
        self.gif_duration = 200  # default ms

        # UI Elements
        self.label = QLabel("Camera Feed")
        self.label.setAlignment(Qt.AlignCenter)

        self.console = QTextEdit()
        self.console.setReadOnly(True)

        self.start_btn = QPushButton("Start Recording")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.export_btn = QPushButton("Export Detected Frames")

        self.camera_selector = QComboBox()
        self.camera_selector.addItems([str(i) for i in range(5)])

        self.threshold_slider = QSlider(Qt.Horizontal)
        self.threshold_slider.setMinimum(10)
        self.threshold_slider.setMaximum(100)
        self.threshold_slider.setValue(80)
        self.threshold_slider.setTickInterval(10)
        self.threshold_slider.setTickPosition(QSlider.TicksBelow)
        self.threshold_label = QLabel("Change Threshold: 80%")

        self.radio_gif = QRadioButton("Export as GIF")
        self.radio_video = QRadioButton("Export as Video")
        self.radio_gif.setChecked(True)
        self.export_format_group = QButtonGroup()
        self.export_format_group.addButton(self.radio_gif)
        self.export_format_group.addButton(self.radio_video)

        self.browse_btn = QPushButton("Browse Save Folder")

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Select Camera Index:"))
        layout.addWidget(self.camera_selector)
        layout.addWidget(self.label)
        layout.addWidget(self.console)

        controls = QHBoxLayout()
        controls.addWidget(self.start_btn)
        controls.addWidget(self.stop_btn)
        controls.addWidget(self.export_btn)
        layout.addLayout(controls)

        layout.addWidget(self.threshold_label)
        layout.addWidget(self.threshold_slider)

        radio_layout = QHBoxLayout()
        radio_layout.addWidget(self.radio_gif)
        radio_layout.addWidget(self.radio_video)
        layout.addLayout(radio_layout)

        layout.addWidget(self.browse_btn)
        self.setLayout(layout)

        # Connections
        self.threshold_slider.valueChanged.connect(self.update_threshold_label)
        self.start_btn.clicked.connect(self.start_recording)
        self.stop_btn.clicked.connect(self.stop_recording)
        self.export_btn.clicked.connect(self.export_detected_frames)
        self.browse_btn.clicked.connect(self.choose_directory)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)

        self.reset_session()

    def reset_session(self):
        self.cap = None
        self.out = None
        self.prev_frame = None
        self.start_time = None
        self.threshold = self.threshold_slider.value()
        self.frame_index = 0
        self.csv_file = os.path.join(self.output_dir, "detection_log.csv")
        self.video_file = os.path.join(self.output_dir, "recorded_video.avi")
        self.frame_folder = os.path.join(self.output_dir, "detected_frames")
        os.makedirs(self.frame_folder, exist_ok=True)
        self.detected_frames.clear()

    def update_threshold_label(self):
        self.threshold = self.threshold_slider.value()
        self.threshold_label.setText(f"Change Threshold: {self.threshold}%")

    def choose_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_dir = folder
            self.console.append(f"[INFO] Output directory set to: {self.output_dir}")
            self.reset_session()

    def frame_difference_percentage(self, frame1, frame2):
        diff = cv2.absdiff(frame1, frame2)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray_diff, 30, 255, cv2.THRESH_BINARY)
        non_zero_count = np.count_nonzero(thresh)
        total_pixels = thresh.shape[0] * thresh.shape[1]
        return (non_zero_count / total_pixels) * 100

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
        ret, frame = self.cap.read()
        if not ret:
            return

        self.out.write(frame)
        elapsed = (datetime.now() - self.start_time).total_seconds()

        if self.prev_frame is not None:
            diff_percent = self.frame_difference_percentage(self.prev_frame, frame)

            if diff_percent > self.threshold:
                timestamp = datetime.now().strftime('%H-%M-%S_%f')[:-3]
                filename = f"change_{timestamp}.jpg"
                full_path = os.path.join(self.frame_folder, filename)
                cv2.imwrite(full_path, frame)
                self.detected_frames.append(full_path)

                text = f"Change: {diff_percent:.2f}% | Elapsed: {elapsed:.2f}s"
                cv2.putText(frame, text, (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                self.console.append(f"[DETECTED] {text} | Saved: {filename}")

                with open(self.csv_file, mode='a', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow([timestamp, f"{elapsed:.3f}", f"{diff_percent:.2f}", filename])

        self.prev_frame = frame.copy()
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        q_img = QImage(rgb_frame.data, w, h, ch * w, QImage.Format_RGB888)
        self.label.setPixmap(QPixmap.fromImage(q_img))

    def stop_recording(self):
        self.timer.stop()
        if self.cap:
            self.cap.release()
        if self.out:
            self.out.release()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.console.append("[INFO] Recording stopped.")
        self.auto_export_frames()

    def auto_export_frames(self):
        if self.radio_gif.isChecked():
            duration, ok = QInputDialog.getInt(self, "GIF Frame Duration", "Enter frame duration in ms:", value=self.gif_duration, min=50, max=2000)
            if ok:
                self.gif_duration = duration
            self.export_as_gif()
        else:
            self.export_as_video()

    def export_detected_frames(self):
        if self.radio_gif.isChecked():
            duration, ok = QInputDialog.getInt(self, "GIF Frame Duration", "Enter frame duration in ms:", value=self.gif_duration, min=50, max=2000)
            if ok:
                self.gif_duration = duration
            self.export_as_gif()
        else:
            self.export_as_video()

    def export_as_gif(self):
        gif_path = os.path.join(self.output_dir, "detected_frames.gif")
        images = [imageio.imread(img) for img in self.detected_frames]
        if images:
            imageio.mimsave(gif_path, images, duration=self.gif_duration / 1000)
            self.console.append(f"[EXPORT] GIF saved: {gif_path}")
        else:
            self.console.append("[WARN] No frames to export as GIF.")

    def export_as_video(self):
        if not self.detected_frames:
            self.console.append("[WARN] No frames to export as video.")
            return

        first_frame = cv2.imread(self.detected_frames[0])
        height, width, _ = first_frame.shape
        export_path = os.path.join(self.output_dir, "detected_frames.avi")
        out = cv2.VideoWriter(export_path, cv2.VideoWriter_fourcc(*'XVID'), 5, (width, height))

        for img_path in self.detected_frames:
            frame = cv2.imread(img_path)
            out.write(frame)
        out.release()
        self.console.append(f"[EXPORT] Video saved: {export_path}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RearCameraTester()
    window.show()
    sys.exit(app.exec_())
