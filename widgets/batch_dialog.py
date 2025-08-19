# EthoGrid_App/widgets/batch_dialog.py

import os
from PyQt5 import QtWidgets
from PyQt5.QtCore import QThread
from workers.batch_processor import BatchProcessor

class BatchProcessDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Processing (Grid Annotation)"); self.setMinimumSize(700, 620)
        self.video_files, self.batch_thread, self.batch_worker = [], None, None
        
        self.video_list_widget = QtWidgets.QListWidget()
        self.settings_line_edit = QtWidgets.QLineEdit(); self.settings_line_edit.setPlaceholderText("Click 'Browse' to select a settings.json file")
        self.csv_dir_line_edit = QtWidgets.QLineEdit(); self.csv_dir_line_edit.setPlaceholderText("(Optional) Select a folder containing all your CSV files")
        self.output_dir_line_edit = QtWidgets.QLineEdit(); self.output_dir_line_edit.setPlaceholderText("Click 'Browse' to select an output folder")
        self.add_videos_btn = QtWidgets.QPushButton("Add Videos..."); self.browse_settings_btn = QtWidgets.QPushButton("Browse..."); self.browse_output_btn = QtWidgets.QPushButton("Browse..."); self.browse_csv_dir_btn = QtWidgets.QPushButton("Browse...")
        
        self.save_video_checkbox = QtWidgets.QCheckBox("Save Annotated Video"); self.save_video_checkbox.setChecked(True)
        self.show_overlays_checkbox = QtWidgets.QCheckBox("Show Overlays (Legend/Timeline)"); self.show_overlays_checkbox.setChecked(True)
        self.save_csv_checkbox = QtWidgets.QCheckBox("Save Enriched CSV (Long Format)"); self.save_csv_checkbox.setChecked(True)
        self.save_centroid_csv_checkbox = QtWidgets.QCheckBox("Save Centroid CSV (Wide Format)"); self.save_centroid_csv_checkbox.setChecked(True)
        self.save_excel_checkbox = QtWidgets.QCheckBox("Save to Excel (by Tank)"); self.save_excel_checkbox.setChecked(True)
        self.save_trajectory_img_checkbox = QtWidgets.QCheckBox("Save Trajectory Image"); self.save_trajectory_img_checkbox.setChecked(True)

        self.time_gap_spinbox = QtWidgets.QDoubleSpinBox()
        self.time_gap_spinbox.setToolTip("Max time gap in seconds. Trajectory lines will break if the time between points is greater than this.")
        self.time_gap_spinbox.setRange(1, 99999.0); self.time_gap_spinbox.setValue(1.0); self.time_gap_spinbox.setSingleStep(0.1)
        self.time_gap_spinbox.setMinimumWidth(80)
        self.time_gap_spinbox.setFixedHeight(20) # Set a fixed height for the input field

        self.start_btn = QtWidgets.QPushButton("Start Processing"); self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.overall_progress_bar = QtWidgets.QProgressBar(); self.overall_progress_label = QtWidgets.QLabel("Waiting to start...")
        self.file_progress_bar = QtWidgets.QProgressBar(); self.file_progress_label = QtWidgets.QLabel("Frame: 0 / 0")
        
        self.elapsed_time_label = QtWidgets.QLabel("Elapsed: 00:00:00")
        self.etr_label = QtWidgets.QLabel("ETR: --:--:--")
        self.speed_label = QtWidgets.QLabel("Speed: 0.00 FPS")
        
        self.log_text_edit = QtWidgets.QTextEdit(); self.log_text_edit.setReadOnly(True)

        layout = QtWidgets.QVBoxLayout(self)
        form_layout = QtWidgets.QGridLayout()
        form_layout.addWidget(QtWidgets.QLabel("Video Files (must have matching .csv):"), 0, 0); form_layout.addWidget(self.video_list_widget, 1, 0, 1, 2); form_layout.addWidget(self.add_videos_btn, 1, 2)
        form_layout.addWidget(QtWidgets.QLabel("Grid Settings File (.json):"), 2, 0); form_layout.addWidget(self.settings_line_edit, 3, 0); form_layout.addWidget(self.browse_settings_btn, 3, 1)
        form_layout.addWidget(QtWidgets.QLabel("CSV Detections Folder (Optional):"), 4, 0); form_layout.addWidget(self.csv_dir_line_edit, 5, 0); form_layout.addWidget(self.browse_csv_dir_btn, 5, 1)
        form_layout.addWidget(QtWidgets.QLabel("Output Directory:"), 6, 0); form_layout.addWidget(self.output_dir_line_edit, 7, 0); form_layout.addWidget(self.browse_output_btn, 7, 1)
        
        output_options_group = QtWidgets.QGroupBox("Output Options")
        output_options_layout = QtWidgets.QVBoxLayout(output_options_group)
        output_options_layout.addWidget(self.save_video_checkbox); output_options_layout.addWidget(self.show_overlays_checkbox)
        output_options_layout.addWidget(self.save_csv_checkbox); output_options_layout.addWidget(self.save_centroid_csv_checkbox)
        output_options_layout.addWidget(self.save_excel_checkbox)
        traj_layout = QtWidgets.QHBoxLayout(); traj_layout.addWidget(self.save_trajectory_img_checkbox); traj_layout.addStretch(); traj_layout.addWidget(QtWidgets.QLabel("Max Time Gap (s):")); traj_layout.addWidget(self.time_gap_spinbox)
        output_options_layout.addLayout(traj_layout)
        form_layout.addWidget(output_options_group, 8, 0, 1, 2); layout.addLayout(form_layout)
        
        progress_group = QtWidgets.QGroupBox("Progress"); progress_layout = QtWidgets.QVBoxLayout(progress_group)
        progress_layout.addWidget(self.overall_progress_label); progress_layout.addWidget(self.overall_progress_bar)
        file_progress_layout = QtWidgets.QHBoxLayout(); file_progress_layout.addWidget(QtWidgets.QLabel("Current File Progress:")); file_progress_layout.addWidget(self.file_progress_label); file_progress_layout.addStretch(); file_progress_layout.addWidget(self.speed_label); file_progress_layout.addWidget(self.elapsed_time_label); file_progress_layout.addWidget(self.etr_label)
        progress_layout.addLayout(file_progress_layout); progress_layout.addWidget(self.file_progress_bar); layout.addWidget(progress_group)
        log_group = QtWidgets.QGroupBox("Log"); log_layout = QtWidgets.QVBoxLayout(log_group); log_layout.addWidget(self.log_text_edit); layout.addWidget(log_group)
        button_layout = QtWidgets.QHBoxLayout(); button_layout.addStretch(); button_layout.addWidget(self.cancel_btn); button_layout.addWidget(self.start_btn); layout.addLayout(button_layout)

        self.add_videos_btn.clicked.connect(self.add_videos); self.browse_settings_btn.clicked.connect(self.browse_settings); self.browse_csv_dir_btn.clicked.connect(self.browse_csv_dir); self.browse_output_btn.clicked.connect(self.browse_output)
        self.start_btn.clicked.connect(self.start_processing); self.cancel_btn.clicked.connect(self.cancel_processing)
        self.cancel_btn.setEnabled(False); self.save_video_checkbox.stateChanged.connect(self.on_save_video_changed); self.save_trajectory_img_checkbox.stateChanged.connect(self.on_save_trajectory_changed)
        self.on_save_video_changed(); self.on_save_trajectory_changed()

    def on_save_video_changed(self):
        is_checked = self.save_video_checkbox.isChecked()
        self.show_overlays_checkbox.setEnabled(is_checked)
        if not is_checked: self.show_overlays_checkbox.setChecked(False)
    def on_save_trajectory_changed(self):
        self.time_gap_spinbox.setEnabled(self.save_trajectory_img_checkbox.isChecked())
    def add_videos(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Select Video Files", "", "Video Files (*.mp4 *.avi *.mov)");
        if files: self.video_files.extend(files); self.video_list_widget.addItems([os.path.basename(f) for f in files])
    def browse_settings(self):
        file, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Settings File", "", "JSON Files (*.json)");
        if file: self.settings_line_edit.setText(file)
    def browse_csv_dir(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Folder Containing CSV Files");
        if directory: self.csv_dir_line_edit.setText(directory)
    def browse_output(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Directory");
        if directory: self.output_dir_line_edit.setText(directory)
    def start_processing(self):
        if not self.video_files: QtWidgets.QMessageBox.warning(self, "Input Error", "Please add at least one video file."); return
        if not self.settings_line_edit.text() or not os.path.exists(self.settings_line_edit.text()): QtWidgets.QMessageBox.warning(self, "Input Error", "Please select a valid settings.json file."); return
        if not self.output_dir_line_edit.text() or not os.path.isdir(self.output_dir_line_edit.text()): QtWidgets.QMessageBox.warning(self, "Input Error", "Please select a valid output directory."); return
        if not any([self.save_video_checkbox.isChecked(), self.save_csv_checkbox.isChecked(), self.save_centroid_csv_checkbox.isChecked(), self.save_excel_checkbox.isChecked(), self.save_trajectory_img_checkbox.isChecked()]):
            QtWidgets.QMessageBox.warning(self, "Input Error", "Please select at least one output option."); return
        self.toggle_controls(False); self.log_text_edit.clear()
        self.batch_worker = BatchProcessor(
            self.video_files, self.settings_line_edit.text(), self.output_dir_line_edit.text(),
            csv_dir=self.csv_dir_line_edit.text(),
            save_video=self.save_video_checkbox.isChecked(),
            save_csv=self.save_csv_checkbox.isChecked(),
            save_centroid_csv=self.save_centroid_csv_checkbox.isChecked(),
            save_excel=self.save_excel_checkbox.isChecked(),
            save_trajectory_img=self.save_trajectory_img_checkbox.isChecked(),
            time_gap_seconds=self.time_gap_spinbox.value(),
            draw_overlays=self.show_overlays_checkbox.isChecked()
        )
        self.batch_thread = QThread(); self.batch_worker.moveToThread(self.batch_thread)
        self.batch_worker.overall_progress.connect(self.update_overall_progress); self.batch_worker.file_progress.connect(self.update_file_progress); self.batch_worker.log_message.connect(self.log_text_edit.append); self.batch_worker.finished.connect(self.on_processing_finished); self.batch_worker.time_updated.connect(self.update_time_labels); self.batch_worker.speed_updated.connect(self.update_speed_label); self.batch_thread.started.connect(self.batch_worker.run)
        self.batch_thread.start()
    def cancel_processing(self):
        if self.batch_worker: self.batch_worker.stop(); self.cancel_btn.setEnabled(False)
    def on_processing_finished(self):
        if self.batch_thread: self.batch_thread.quit(); self.batch_thread.wait()
        self.toggle_controls(True)
        if self.batch_worker and self.batch_worker.is_running: QtWidgets.QMessageBox.information(self, "Finished", "Batch processing has completed.")
    def update_overall_progress(self, current_num, total, filename):
        self.overall_progress_bar.setValue(int(current_num * 100 / total)); self.overall_progress_label.setText(f"Processing file {current_num} of {total}: {filename}")
        self.file_progress_bar.setValue(0); self.file_progress_label.setText("Frame: 0 / 0"); self.elapsed_time_label.setText("Elapsed: 00:00:00"); self.etr_label.setText("ETR: --:--:--")
        self.speed_label.setText("Speed: 0.00 FPS")
    def update_file_progress(self, percentage, current_frame, total_frames):
        self.file_progress_bar.setValue(percentage); self.file_progress_label.setText(f"Frame: {current_frame} / {total_frames}")
    def update_time_labels(self, elapsed, etr):
        self.elapsed_time_label.setText(f"Elapsed: {elapsed}"); self.etr_label.setText(f"ETR: {etr}")
    def update_speed_label(self, fps):
        self.speed_label.setText(f"Speed: {fps:.2f} FPS")
    def toggle_controls(self, enabled):
        self.start_btn.setEnabled(enabled); self.add_videos_btn.setEnabled(enabled); self.browse_settings_btn.setEnabled(enabled); self.browse_output_btn.setEnabled(enabled); self.browse_csv_dir_btn.setEnabled(enabled); self.cancel_btn.setEnabled(not enabled)
    def closeEvent(self, event):
        if self.batch_thread and self.batch_thread.isRunning():
            self.cancel_processing(); self.batch_thread.quit(); self.batch_thread.wait()
        event.accept()