# EthoGrid_App/widgets/yolo_segmentation_dialog.py

import os
from PyQt5 import QtWidgets
from PyQt5.QtCore import QThread

from workers.yolo_segmentation_processor import YoloSegmentationProcessor

class YoloSegmentationDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("YOLO Segmentation")
        self.setMinimumSize(700, 550)
        self.video_files, self.yolo_thread, self.yolo_worker = [], None, None

        self.video_list_widget = QtWidgets.QListWidget()
        self.model_line_edit = QtWidgets.QLineEdit(); self.model_line_edit.setPlaceholderText("Click 'Browse' to select a YOLO segmentation model (.pt)")
        self.output_dir_line_edit = QtWidgets.QLineEdit(); self.output_dir_line_edit.setPlaceholderText("Click 'Browse' to select an output folder")
        self.add_videos_btn = QtWidgets.QPushButton("Add Videos..."); self.browse_model_btn = QtWidgets.QPushButton("Browse..."); self.browse_output_btn = QtWidgets.QPushButton("Browse...")
        self.confidence_spinbox = QtWidgets.QDoubleSpinBox(); self.confidence_spinbox.setRange(0.0, 1.0); self.confidence_spinbox.setSingleStep(0.05); self.confidence_spinbox.setValue(0.4)
        
        self.save_video_checkbox = QtWidgets.QCheckBox("Save Segmented Video"); self.save_video_checkbox.setChecked(True)
        self.save_csv_checkbox = QtWidgets.QCheckBox("Save Segmentations CSV"); self.save_csv_checkbox.setChecked(True)

        self.start_btn = QtWidgets.QPushButton("Start Segmentation"); self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.overall_progress_bar = QtWidgets.QProgressBar(); self.overall_progress_label = QtWidgets.QLabel("Waiting to start...")
        self.file_progress_bar = QtWidgets.QProgressBar(); self.file_progress_label = QtWidgets.QLabel("Frame: 0 / 0")
        self.log_text_edit = QtWidgets.QTextEdit(); self.log_text_edit.setReadOnly(True)

        layout = QtWidgets.QVBoxLayout(self)
        form_layout = QtWidgets.QGridLayout()
        form_layout.addWidget(QtWidgets.QLabel("Video Files:"), 0, 0); form_layout.addWidget(self.video_list_widget, 1, 0, 1, 2); form_layout.addWidget(self.add_videos_btn, 1, 2)
        form_layout.addWidget(QtWidgets.QLabel("YOLO Model File (-seg.pt):"), 2, 0); form_layout.addWidget(self.model_line_edit, 3, 0); form_layout.addWidget(self.browse_model_btn, 3, 1)
        form_layout.addWidget(QtWidgets.QLabel("Output Directory:"), 4, 0); form_layout.addWidget(self.output_dir_line_edit, 5, 0); form_layout.addWidget(self.browse_output_btn, 5, 1)
        form_layout.addWidget(QtWidgets.QLabel("Confidence Threshold:"), 6, 0); form_layout.addWidget(self.confidence_spinbox, 6, 1)
        
        output_options_group = QtWidgets.QGroupBox("Output Options"); output_options_layout = QtWidgets.QHBoxLayout(output_options_group)
        output_options_layout.addWidget(self.save_video_checkbox); output_options_layout.addWidget(self.save_csv_checkbox); output_options_layout.addStretch()
        form_layout.addWidget(output_options_group, 7, 0, 1, 2)
        layout.addLayout(form_layout)
        
        progress_group = QtWidgets.QGroupBox("Progress"); progress_layout = QtWidgets.QVBoxLayout(progress_group)
        progress_layout.addWidget(self.overall_progress_label); progress_layout.addWidget(self.overall_progress_bar)
        file_progress_layout = QtWidgets.QHBoxLayout(); file_progress_layout.addWidget(QtWidgets.QLabel("Current Video Progress:")); file_progress_layout.addWidget(self.file_progress_label); file_progress_layout.addStretch()
        progress_layout.addLayout(file_progress_layout); progress_layout.addWidget(self.file_progress_bar); layout.addWidget(progress_group)

        log_group = QtWidgets.QGroupBox("Log"); log_layout = QtWidgets.QVBoxLayout(log_group); log_layout.addWidget(self.log_text_edit); layout.addWidget(log_group)
        button_layout = QtWidgets.QHBoxLayout(); button_layout.addStretch(); button_layout.addWidget(self.cancel_btn); button_layout.addWidget(self.start_btn); layout.addLayout(button_layout)

        self.add_videos_btn.clicked.connect(self.add_videos); self.browse_model_btn.clicked.connect(self.browse_model); self.browse_output_btn.clicked.connect(self.browse_output)
        self.start_btn.clicked.connect(self.start_processing); self.cancel_btn.clicked.connect(self.cancel_processing)
        self.cancel_btn.setEnabled(False)

    def add_videos(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Select Video Files", "", "Video Files (*.mp4 *.avi *.mov)");
        if files: self.video_files.extend(files); self.video_list_widget.addItems([os.path.basename(f) for f in files])
    def browse_model(self):
        file, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select YOLO Segmentation Model", "", "PyTorch Models (*.pt)");
        if file: self.model_line_edit.setText(file)
    def browse_output(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Directory");
        if directory: self.output_dir_line_edit.setText(directory)
            
    def start_processing(self):
        if not self.video_files: QtWidgets.QMessageBox.warning(self, "Input Error", "Please add at least one video file."); return
        if not self.model_line_edit.text() or not os.path.exists(self.model_line_edit.text()): QtWidgets.QMessageBox.warning(self, "Input Error", "Please select a valid YOLO model (.pt) file."); return
        if not self.output_dir_line_edit.text() or not os.path.isdir(self.output_dir_line_edit.text()): QtWidgets.QMessageBox.warning(self, "Input Error", "Please select a valid output directory."); return
        if not self.save_video_checkbox.isChecked() and not self.save_csv_checkbox.isChecked(): QtWidgets.QMessageBox.warning(self, "Input Error", "Please select at least one output option."); return

        self.toggle_controls(False); self.log_text_edit.clear()
        self.yolo_worker = YoloSegmentationProcessor(self.video_files, self.model_line_edit.text(), self.output_dir_line_edit.text(), self.confidence_spinbox.value(), save_video=self.save_video_checkbox.isChecked(), save_csv=self.save_csv_checkbox.isChecked())
        self.yolo_thread = QThread(); self.yolo_worker.moveToThread(self.yolo_thread)
        self.yolo_worker.overall_progress.connect(self.update_overall_progress); self.yolo_worker.file_progress.connect(self.update_file_progress); self.yolo_worker.log_message.connect(self.log_text_edit.append); self.yolo_worker.error.connect(self.on_processing_error); self.yolo_worker.finished.connect(self.on_processing_finished); self.yolo_thread.started.connect(self.yolo_worker.run)
        self.yolo_thread.start()

    def cancel_processing(self):
        if self.yolo_worker: self.yolo_worker.stop()
        self.cancel_btn.setEnabled(False)
    def on_processing_error(self, message):
        QtWidgets.QMessageBox.critical(self, "Error", message); self.on_processing_finished()
    def on_processing_finished(self):
        if self.yolo_thread: self.yolo_thread.quit(); self.yolo_thread.wait()
        self.toggle_controls(True)
        if self.yolo_worker and self.yolo_worker.is_running: QtWidgets.QMessageBox.information(self, "Finished", "YOLO segmentation has completed.")
    def update_overall_progress(self, current_num, total, filename):
        self.overall_progress_bar.setValue(int(current_num * 100 / total)); self.overall_progress_label.setText(f"Processing file {current_num} of {total}: {filename}")
        self.file_progress_bar.setValue(0); self.file_progress_label.setText("Frame: 0 / 0")
    def update_file_progress(self, percentage, current_frame, total_frames):
        self.file_progress_bar.setValue(percentage); self.file_progress_label.setText(f"Frame: {current_frame} / {total_frames}")
    def toggle_controls(self, enabled):
        self.start_btn.setEnabled(enabled); self.add_videos_btn.setEnabled(enabled); self.browse_model_btn.setEnabled(enabled); self.browse_output_btn.setEnabled(enabled)
        self.cancel_btn.setEnabled(not enabled)
    def closeEvent(self, event):
        if self.yolo_thread and self.yolo_thread.isRunning():
            self.cancel_processing(); self.yolo_thread.quit(); self.yolo_thread.wait()
        event.accept()