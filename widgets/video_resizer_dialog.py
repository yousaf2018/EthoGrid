# EthoGrid_App/widgets/video_resizer_dialog.py

import os
import cv2
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import QThread
from workers.video_resizer import VideoResizer
from widgets.base_dialog import BaseDialog
from widgets.custom_widgets import CustomDoubleSpinBox

class VideoResizerDialog(BaseDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Video Quality Control (Downscaler)")
        self.setMinimumSize(700, 600)
        self.video_files = []
        self.resizer_worker = None
        self.worker_thread = None # Renamed from self.thread to avoid conflict

        main_widget = QtWidgets.QWidget()
        form_layout = QtWidgets.QGridLayout(main_widget)
        
        self.video_list_widget = QtWidgets.QListWidget()
        self.video_list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.add_videos_btn = QtWidgets.QPushButton("Add Video(s)...")
        self.add_directory_btn = QtWidgets.QPushButton("Add Directory...")
        self.remove_video_btn = QtWidgets.QPushButton("Remove Selected")
        self.clear_videos_btn = QtWidgets.QPushButton("Clear All")
        
        self.output_dir_line_edit = QtWidgets.QLineEdit()
        self.output_dir_line_edit.setPlaceholderText("Select a folder to save the processed videos")
        self.browse_output_btn = QtWidgets.QPushButton("Browse...")
        
        self.resize_checkbox = QtWidgets.QCheckBox("Downscale Video(s)")
        self.resolution_combo = QtWidgets.QComboBox(toolTip="Select a target resolution. Videos smaller than this will be copied.")
        resolutions = {"4K (UHD)": 2160, "2K (QHD)": 1440, "1080p (FHD)": 1080, "720p (HD)": 720, "480p": 480, "360p": 360}
        for name, h_val in resolutions.items():
            self.resolution_combo.addItem(f"{name} ({h_val}p)", h_val)
        self.resolution_combo.setCurrentIndex(2)
        
        self.speed_checkbox = QtWidgets.QCheckBox("Change Speed")
        self.speed_spinbox = CustomDoubleSpinBox(value=1.0, minimum=0.1, maximum=100.0, singleStep=0.1, decimals=2, suffix="x")
        
        self.start_btn = QtWidgets.QPushButton("Start Processing")
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.overall_progress_bar = QtWidgets.QProgressBar()
        self.overall_progress_label = QtWidgets.QLabel("Waiting to start...")
        self.file_progress_bar = QtWidgets.QProgressBar()
        self.file_progress_label = QtWidgets.QLabel("Status: Idle")
        self.elapsed_time_label = QtWidgets.QLabel("Elapsed: 00:00:00")
        self.etr_label = QtWidgets.QLabel("ETR: --:--:--")
        self.speed_label = QtWidgets.QLabel("Speed: 0.00 FPS")
        self.log_text_edit = QtWidgets.QTextEdit()
        self.log_text_edit.setReadOnly(True)

        file_buttons_layout = QtWidgets.QVBoxLayout(); file_buttons_layout.addWidget(self.add_videos_btn); file_buttons_layout.addWidget(self.add_directory_btn); file_buttons_layout.addWidget(self.remove_video_btn); file_buttons_layout.addWidget(self.clear_videos_btn); file_buttons_layout.addStretch()
        form_layout.addWidget(QtWidgets.QLabel("Video Files to Process:"), 0, 0); form_layout.addWidget(self.video_list_widget, 1, 0, 1, 2); form_layout.addLayout(file_buttons_layout, 1, 2)
        form_layout.addWidget(QtWidgets.QLabel("Output Folder:"), 2, 0); form_layout.addWidget(self.output_dir_line_edit, 3, 0); form_layout.addWidget(self.browse_output_btn, 3, 1)
        
        options_group = QtWidgets.QGroupBox("Processing Options"); options_layout = QtWidgets.QFormLayout(options_group)
        resize_layout = QtWidgets.QHBoxLayout(); resize_layout.addWidget(self.resize_checkbox); resize_layout.addWidget(self.resolution_combo); options_layout.addRow(resize_layout)
        speed_layout = QtWidgets.QHBoxLayout(); speed_layout.addWidget(self.speed_checkbox); speed_layout.addWidget(self.speed_spinbox); options_layout.addRow(speed_layout)
        form_layout.addWidget(options_group, 4, 0, 1, 3)

        scroll_area = QtWidgets.QScrollArea(); scroll_area.setWidgetResizable(True); scroll_area.setWidget(main_widget)
        main_dialog_layout = QtWidgets.QVBoxLayout(self); main_dialog_layout.addWidget(scroll_area)
        
        progress_group = QtWidgets.QGroupBox("Progress"); progress_layout = QtWidgets.QVBoxLayout(progress_group)
        progress_layout.addWidget(self.overall_progress_label); progress_layout.addWidget(self.overall_progress_bar)
        file_progress_layout = QtWidgets.QHBoxLayout(); file_progress_layout.addWidget(self.file_progress_label, 1); file_progress_layout.addStretch(); file_progress_layout.addWidget(self.speed_label); file_progress_layout.addWidget(self.elapsed_time_label); file_progress_layout.addWidget(self.etr_label)
        progress_layout.addLayout(file_progress_layout); progress_layout.addWidget(self.file_progress_bar)
        main_dialog_layout.addWidget(progress_group)
        log_group = QtWidgets.QGroupBox("Log"); log_layout = QtWidgets.QVBoxLayout(log_group); log_layout.addWidget(self.log_text_edit)
        main_dialog_layout.addWidget(log_group)
        button_layout = QtWidgets.QHBoxLayout(); button_layout.addStretch(); button_layout.addWidget(self.cancel_btn); button_layout.addWidget(self.start_btn)
        main_dialog_layout.addLayout(button_layout)

        self.add_videos_btn.clicked.connect(self.add_videos); self.add_directory_btn.clicked.connect(self.add_directory); self.remove_video_btn.clicked.connect(self.remove_selected); self.clear_videos_btn.clicked.connect(self.clear_all)
        self.browse_output_btn.clicked.connect(self.browse_output); self.start_btn.clicked.connect(self.start_processing); self.cancel_btn.clicked.connect(self.cancel_resizing)
        self.resize_checkbox.stateChanged.connect(self.resolution_combo.setEnabled); self.speed_checkbox.stateChanged.connect(self.speed_spinbox.setEnabled)
        self.resolution_combo.setEnabled(False); self.speed_spinbox.setEnabled(False); self.cancel_btn.setEnabled(False)

    def add_videos(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Select Video Files", "", "Video Files (*.mp4 *.avi *.mov *.mkv)")
        if files:
            for f in files:
                if f not in self.video_files: self.video_files.append(f); self.video_list_widget.addItem(os.path.basename(f))
    
    def add_directory(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory Containing Videos")
        if directory:
            video_extensions = ('.mp4', '.avi', '.mov', '.mkv')
            for root, _, files in os.walk(directory):
                for file in files:
                    if file.lower().endswith(video_extensions):
                        full_path = os.path.join(root, file)
                        if full_path not in self.video_files: self.video_files.append(full_path); self.video_list_widget.addItem(os.path.basename(full_path))

    def remove_selected(self):
        selected_items = self.video_list_widget.selectedItems()
        if not selected_items: return
        for item in selected_items:
            row = self.video_list_widget.row(item); self.video_list_widget.takeItem(row)
            base_name = item.text(); self.video_files = [f for f in self.video_files if os.path.basename(f) != base_name]
    
    def clear_all(self):
        self.video_list_widget.clear(); self.video_files.clear()
    
    def browse_output(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory: self.output_dir_line_edit.setText(directory)

    def start_processing(self):
        if not self.video_files: QtWidgets.QMessageBox.warning(self, "Input Error", "Please add at least one video file."); return
        if not self.output_dir_line_edit.text() or not os.path.isdir(self.output_dir_line_edit.text()): QtWidgets.QMessageBox.warning(self, "Input Error", "Please select a valid output directory."); return
        if not self.resize_checkbox.isChecked() and not self.speed_checkbox.isChecked(): QtWidgets.QMessageBox.warning(self, "Input Error", "Please select at least one processing option (Downscale or Change Speed)."); return
        
        target_height = self.resolution_combo.currentData() if self.resize_checkbox.isChecked() else None
        speed_multiplier = self.speed_spinbox.value() if self.speed_checkbox.isChecked() else 1.0

        self.toggle_controls(False); self.log_text_edit.clear()
        
        self.resizer_worker = VideoResizer(self.video_files, self.output_dir_line_edit.text(), target_height, speed_multiplier)
        self.worker_thread = QThread() # Renamed
        self.resizer_worker.moveToThread(self.worker_thread) # Renamed
        
        self.resizer_worker.overall_progress.connect(self.update_overall_progress)
        self.resizer_worker.file_progress.connect(self.update_file_progress)
        self.resizer_worker.log_message.connect(self.log_text_edit.append)
        self.resizer_worker.finished.connect(self.on_resizing_finished)
        self.resizer_worker.error.connect(self.on_processing_error)
        self.resizer_worker.time_updated.connect(self.update_time_labels)
        self.resizer_worker.speed_updated.connect(self.update_speed_label)
        
        self.worker_thread.started.connect(self.resizer_worker.run) # Renamed
        self.worker_thread.start() # Renamed

    def cancel_resizing(self):
        if self.resizer_worker: self.resizer_worker.stop(); self.cancel_btn.setEnabled(False)

    def on_processing_error(self, message):
        QtWidgets.QMessageBox.critical(self, "Error", message)
        self.on_resizing_finished()

    def on_resizing_finished(self):
        if self.worker_thread: # Renamed
            self.worker_thread.quit() # Renamed
            self.worker_thread.wait() # Renamed
        self.toggle_controls(True)
        if self.resizer_worker and self.resizer_worker.is_running:
            QtWidgets.QMessageBox.information(self, "Finished", "Video processing has completed.")

    def update_overall_progress(self, current_num, total, filename):
        self.overall_progress_bar.setValue(int(current_num * 100 / total)); self.overall_progress_label.setText(f"Processing file {current_num} of {total}: {filename}")
        self.file_progress_bar.setValue(0); self.file_progress_label.setText("Status: Idle"); self.elapsed_time_label.setText("Elapsed: 00:00:00"); self.etr_label.setText("ETR: --:--:--"); self.speed_label.setText("Speed: 0.00 FPS")

    def update_file_progress(self, percentage, status_text):
        self.file_progress_bar.setValue(percentage); self.file_progress_label.setText(f"Status: {status_text}")

    def update_time_labels(self, elapsed, etr):
        self.elapsed_time_label.setText(f"Elapsed: {elapsed}"); self.etr_label.setText(f"ETR: {etr}")

    def update_speed_label(self, fps):
        self.speed_label.setText(f"Speed: {fps:.2f} FPS")

    def toggle_controls(self, enabled):
        self.start_btn.setEnabled(enabled); self.add_videos_btn.setEnabled(enabled); self.add_directory_btn.setEnabled(enabled); self.remove_video_btn.setEnabled(enabled); self.clear_videos_btn.setEnabled(enabled); self.browse_output_btn.setEnabled(enabled)
        self.cancel_btn.setEnabled(not enabled)
        
    def closeEvent(self, event):
        if self.worker_thread and self.worker_thread.isRunning(): # Renamed
            self.cancel_resizing()
            self.worker_thread.quit() # Renamed
            self.worker_thread.wait() # Renamed
        event.accept()