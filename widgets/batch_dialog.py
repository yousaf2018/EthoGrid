# EthoGrid_App/widgets/batch_dialog.py

import os
import csv
import pandas as pd
import numpy as np
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import QThread
from workers.batch_processor import BatchProcessor
from widgets.base_dialog import BaseDialog 
from widgets.custom_widgets import CustomSpinBox, CustomDoubleSpinBox

class BatchProcessDialog(BaseDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("Batch Processing (Grid Annotation)"); self.setMinimumSize(700, 750)
        self.video_files, self.batch_thread, self.batch_worker = [], None, None
        self.setStyleSheet(""" QDoubleSpinBox, QSpinBox { padding: 4px; min-height: 20px; } """)
        
        main_dialog_layout = QtWidgets.QVBoxLayout(self)
        scroll_area = QtWidgets.QScrollArea(); scroll_area.setWidgetResizable(True)
        main_options_widget = QtWidgets.QWidget(); form_layout = QtWidgets.QGridLayout(main_options_widget)
        
        self.video_list_widget = QtWidgets.QListWidget(); self.video_list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.add_videos_btn = QtWidgets.QPushButton("Add Video(s)..."); self.add_directory_btn = QtWidgets.QPushButton("Add Directory..."); self.remove_video_btn = QtWidgets.QPushButton("Remove Selected"); self.clear_videos_btn = QtWidgets.QPushButton("Clear All")
        self.settings_line_edit = QtWidgets.QLineEdit(); self.settings_line_edit.setPlaceholderText("Click 'Browse' to select a settings.json file")
        self.csv_dir_line_edit = QtWidgets.QLineEdit(); self.csv_dir_line_edit.setPlaceholderText("(Optional) Select a folder containing all your CSV files")
        self.output_dir_line_edit = QtWidgets.QLineEdit(); self.output_dir_line_edit.setPlaceholderText("Click 'Browse' to select an output folder")
        self.browse_settings_btn = QtWidgets.QPushButton("Browse..."); self.browse_output_btn = QtWidgets.QPushButton("Browse..."); self.browse_csv_dir_btn = QtWidgets.QPushButton("Browse...")
        
        self.tracking_method_combo = QtWidgets.QComboBox(); 
        # ADDED CUSTOM FORCE-N TO DROPDOWN
        self.tracking_method_combo.addItems(["Custom Force-N", "Confidence Filter", "Norfair", "ByteTrack", "OCSORT", "BoTSORT", "StrongSORT"])
        
        self.max_animals_spinbox = CustomSpinBox(toolTip="Max animals to track per tank.", value=1, minimum=1, maximum=1000)
        self.auto_stitch_checkbox = QtWidgets.QCheckBox("Auto-Stitch to Max Animals")
        self.auto_stitch_checkbox.setToolTip("Aggressively merge broken tracks to ensure only 'Max Animals' tracks exist per tank.")
        
        self.norfair_group = QtWidgets.QGroupBox("Norfair Settings"); norfair_layout = QtWidgets.QFormLayout(self.norfair_group)
        self.norfair_distance_fn_combo = QtWidgets.QComboBox(); self.norfair_distance_fn_combo.addItems(["euclidean", "iou"])
        
        self.norfair_dist_thresh = CustomDoubleSpinBox(value=5.0, maximum=50000.0, singleStep=0.5, decimals=1)
        self.norfair_dist_thresh.setToolTip("Max distance in Centimeters an object can move between frames.")
        self.norfair_hit_counter = CustomSpinBox(value=15, minimum=1, maximum=100)
        self.norfair_init_delay = CustomSpinBox(value=3, minimum=0, maximum=50)
        self.norfair_past_detections = CustomSpinBox(value=4, minimum=0, maximum=50)
        self.calculate_dist_btn = QtWidgets.QPushButton("Calculate Optimal (Auto)")
        dist_layout = QtWidgets.QHBoxLayout(); dist_layout.addWidget(self.norfair_dist_thresh, 1); dist_layout.addWidget(self.calculate_dist_btn)
        
        norfair_layout.addRow("Distance Function:", self.norfair_distance_fn_combo)
        norfair_layout.addRow("Distance Threshold (cm):", dist_layout)
        norfair_layout.addRow("Hit Counter Max:", self.norfair_hit_counter)
        norfair_layout.addRow("Initialization Delay:", self.norfair_init_delay)
        norfair_layout.addRow("Past Detections Length:", self.norfair_past_detections)

        self.reid_group = QtWidgets.QGroupBox("Re-ID Tracker Settings (StrongSORT, BoTSORT)"); reid_layout = QtWidgets.QFormLayout(self.reid_group)
        self.reid_model_edit = QtWidgets.QLineEdit(); self.reid_model_edit.setPlaceholderText("Browse for Re-ID model weights (.pt)")
        self.browse_reid_model_btn = QtWidgets.QPushButton("Browse...")
        self.strongsort_max_dist = CustomDoubleSpinBox(value=0.2, maximum=1.0, singleStep=0.05, decimals=2)
        self.strongsort_max_age = CustomSpinBox(value=30, minimum=1, maximum=300)
        self.strongsort_n_init = CustomSpinBox(value=3, minimum=1, maximum=20)
        reid_layout.addRow("Re-ID Model:", self.create_hbox(self.reid_model_edit, self.browse_reid_model_btn)); reid_layout.addRow("Max Distance (Cosine):", self.strongsort_max_dist); reid_layout.addRow("Max Age (frames):", self.strongsort_max_age); reid_layout.addRow("Confirmation Frames (n_init):", self.strongsort_n_init)
        
        self.duplicate_merge_group = QtWidgets.QGroupBox("Pre-Tracking Duplicate Merge (NMS)")
        duplicate_merge_layout = QtWidgets.QFormLayout(self.duplicate_merge_group)
        self.iou_threshold_input = CustomDoubleSpinBox(value=0.50, singleStep=0.05, decimals=2, minimum=0.0, maximum=1.0)
        self.iou_threshold_input.setToolTip("If two model detections in the same tank overlap by >= this IoU, the lower confidence one is discarded.")
        duplicate_merge_layout.addRow("IoU Threshold (0.0 to 1.0):", self.iou_threshold_input)
        
        self.frame_sample_rate_spinbox = CustomSpinBox(toolTip="Use data from every Nth frame for image exports.", value=30, minimum=1, maximum=10000)
        self.time_gap_spinbox = CustomDoubleSpinBox(toolTip="Max time gap in seconds for trajectories.", value=1.0, minimum=0.1, maximum=99999.0, singleStep=0.1)
        self.save_video_checkbox = QtWidgets.QCheckBox("Save Annotated Video"); self.save_video_checkbox.setChecked(True); self.show_overlays_checkbox = QtWidgets.QCheckBox("Show Overlays (Legend/Timeline)"); self.show_overlays_checkbox.setChecked(True)
        self.save_csv_checkbox = QtWidgets.QCheckBox("Save Enriched CSV"); self.save_csv_checkbox.setChecked(True); self.save_centroid_csv_checkbox = QtWidgets.QCheckBox("Save Centroid CSV (Wide)"); self.save_centroid_csv_checkbox.setChecked(True)
        
        self.save_excel_track_checkbox = QtWidgets.QCheckBox("Save Excel (by Track)"); self.save_excel_track_checkbox.setChecked(True)
        self.save_excel_tank_checkbox = QtWidgets.QCheckBox("Save Excel (by Tank)"); self.save_excel_tank_checkbox.setChecked(True)
        self.draw_polygons_checkbox = QtWidgets.QCheckBox("Draw Segmentation Polygons"); self.draw_polygons_checkbox.setChecked(True)

        self.save_trajectory_img_checkbox = QtWidgets.QCheckBox("Save Trajectory Image"); self.save_trajectory_img_checkbox.setChecked(True)
        self.save_heatmap_img_checkbox = QtWidgets.QCheckBox("Save Heatmap Image"); self.save_heatmap_img_checkbox.setChecked(True)
        self.start_btn = QtWidgets.QPushButton("Start Processing"); self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.overall_progress_bar = QtWidgets.QProgressBar(); self.overall_progress_label = QtWidgets.QLabel("Waiting to start...")
        self.file_progress_bar = QtWidgets.QProgressBar(); self.file_progress_label = QtWidgets.QLabel("Frame: 0 / 0")
        self.elapsed_time_label = QtWidgets.QLabel("Elapsed: 00:00:00"); self.etr_label = QtWidgets.QLabel("ETR: --:--:--"); self.speed_label = QtWidgets.QLabel("Speed: 0.00 FPS")
        self.log_text_edit = QtWidgets.QTextEdit(); self.log_text_edit.setReadOnly(True)

        file_buttons_layout = QtWidgets.QVBoxLayout(); file_buttons_layout.addWidget(self.add_videos_btn); file_buttons_layout.addWidget(self.add_directory_btn); file_buttons_layout.addWidget(self.remove_video_btn); file_buttons_layout.addWidget(self.clear_videos_btn); file_buttons_layout.addStretch()
        form_layout.addWidget(QtWidgets.QLabel("Video Files:"), 0, 0); form_layout.addWidget(self.video_list_widget, 1, 0, 1, 2); form_layout.addLayout(file_buttons_layout, 1, 2)
        form_layout.addWidget(QtWidgets.QLabel("Grid Settings File (.json):"), 2, 0); form_layout.addWidget(self.settings_line_edit, 3, 0); form_layout.addWidget(self.browse_settings_btn, 3, 1)
        form_layout.addWidget(QtWidgets.QLabel("CSV Detections Folder (Optional):"), 4, 0); form_layout.addWidget(self.csv_dir_line_edit, 5, 0); form_layout.addWidget(self.browse_csv_dir_btn, 5, 1)
        form_layout.addWidget(QtWidgets.QLabel("Output Directory:"), 6, 0); form_layout.addWidget(self.output_dir_line_edit, 7, 0); form_layout.addWidget(self.browse_output_btn, 7, 1)
        
        tracking_group = QtWidgets.QGroupBox("Tracking Options")
        tracking_layout = QtWidgets.QVBoxLayout(tracking_group)
        tracking_options_form = QtWidgets.QFormLayout()
        tracking_options_form.addRow("Method:", self.tracking_method_combo)
        tracking_options_form.addRow("Max Animals to Track:", self.max_animals_spinbox)
        tracking_options_form.addRow(self.auto_stitch_checkbox)
        tracking_layout.addLayout(tracking_options_form)
        tracking_layout.addWidget(self.norfair_group)
        tracking_layout.addWidget(self.reid_group)
        tracking_layout.addWidget(self.duplicate_merge_group) 
        form_layout.addWidget(tracking_group, 8, 0, 1, 3)

        img_export_group = QtWidgets.QGroupBox("Image Export Options"); img_export_layout = QtWidgets.QFormLayout(img_export_group)
        img_export_layout.addRow("Sample Rate (every Nth frame):", self.frame_sample_rate_spinbox); form_layout.addWidget(img_export_group, 9, 0, 1, 3)
        
        output_options_group = QtWidgets.QGroupBox("Output Files"); output_options_layout = QtWidgets.QVBoxLayout(output_options_group)
        output_options_layout.addWidget(self.save_video_checkbox); output_options_layout.addWidget(self.draw_polygons_checkbox); output_options_layout.addWidget(self.show_overlays_checkbox)
        output_options_layout.addWidget(self.save_csv_checkbox); output_options_layout.addWidget(self.save_centroid_csv_checkbox)
        output_options_layout.addWidget(self.save_excel_track_checkbox); output_options_layout.addWidget(self.save_excel_tank_checkbox)
        output_options_layout.addWidget(self.save_heatmap_img_checkbox)
        traj_layout = QtWidgets.QHBoxLayout(); traj_layout.addWidget(self.save_trajectory_img_checkbox); traj_layout.addStretch(); traj_layout.addWidget(QtWidgets.QLabel("Max Time Gap (s):")); traj_layout.addWidget(self.time_gap_spinbox)
        output_options_layout.addLayout(traj_layout); form_layout.addWidget(output_options_group, 10, 0, 1, 3);
        
        scroll_area.setWidget(main_options_widget); main_dialog_layout.addWidget(scroll_area)
        
        progress_group = QtWidgets.QGroupBox("Progress"); progress_layout = QtWidgets.QVBoxLayout(progress_group); progress_layout.addWidget(self.overall_progress_label); progress_layout.addWidget(self.overall_progress_bar)
        file_progress_layout = QtWidgets.QHBoxLayout(); file_progress_layout.addWidget(QtWidgets.QLabel("Current File Progress:")); file_progress_layout.addWidget(self.file_progress_label); file_progress_layout.addStretch(); file_progress_layout.addWidget(self.speed_label); file_progress_layout.addWidget(self.elapsed_time_label); file_progress_layout.addWidget(self.etr_label)
        progress_layout.addLayout(file_progress_layout); progress_layout.addWidget(self.file_progress_bar); main_dialog_layout.addWidget(progress_group)
        log_group = QtWidgets.QGroupBox("Log"); log_layout = QtWidgets.QVBoxLayout(log_group); log_layout.addWidget(self.log_text_edit)
        main_dialog_layout.addWidget(log_group)
        button_layout = QtWidgets.QHBoxLayout(); button_layout.addStretch(); button_layout.addWidget(self.cancel_btn); button_layout.addWidget(self.start_btn)
        main_dialog_layout.addLayout(button_layout)
        
        self.add_videos_btn.clicked.connect(self.add_videos); self.add_directory_btn.clicked.connect(self.add_directory); self.remove_video_btn.clicked.connect(self.remove_selected); self.clear_videos_btn.clicked.connect(self.clear_all); self.browse_settings_btn.clicked.connect(self.browse_settings); self.browse_csv_dir_btn.clicked.connect(self.browse_csv_dir); self.browse_output_btn.clicked.connect(self.browse_output)
        self.start_btn.clicked.connect(self.start_processing); self.cancel_btn.clicked.connect(self.cancel_processing); self.tracking_method_combo.currentTextChanged.connect(self.on_tracking_method_changed); self.calculate_dist_btn.clicked.connect(self.calculate_optimal_distance); self.browse_reid_model_btn.clicked.connect(self.browse_reid_model)
        self.cancel_btn.setEnabled(False); self.save_video_checkbox.stateChanged.connect(self.on_save_video_changed); self.save_trajectory_img_checkbox.stateChanged.connect(self.on_save_trajectory_changed)
        self.on_save_video_changed(); self.on_save_trajectory_changed(); self.on_tracking_method_changed(self.tracking_method_combo.currentText())

    def create_hbox(self, w1, w2):
        widget = QtWidgets.QWidget(); layout = QtWidgets.QHBoxLayout(widget); layout.addWidget(w1); layout.addWidget(w2); layout.setContentsMargins(0,0,0,0); return widget
        
    def on_tracking_method_changed(self, method):
        self.norfair_group.setVisible(method == "Norfair")
        self.reid_group.setVisible(method in ["StrongSORT", "BoTSORT"])
        self.duplicate_merge_group.setVisible(True) 
        self.max_animals_spinbox.setEnabled(method != "Confidence Filter")
        self.auto_stitch_checkbox.setEnabled(method not in ["Confidence Filter", "Custom Force-N"]) # Disable auto-stitch for Force-N
        
    def on_save_video_changed(self, state=None):
        is_checked = self.save_video_checkbox.isChecked(); self.show_overlays_checkbox.setEnabled(is_checked); self.draw_polygons_checkbox.setEnabled(is_checked)
        if not is_checked: self.show_overlays_checkbox.setChecked(False)
            
    def on_save_trajectory_changed(self, state=None):
        self.time_gap_spinbox.setEnabled(self.save_trajectory_img_checkbox.isChecked())
        
    def add_videos(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Select Video Files", "", "Video Files (*.mp4 *.avi *.mov *.mkv)");
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
    
    def browse_settings(self):
        file, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Settings File", "", "JSON Files (*.json)");
        if file: self.settings_line_edit.setText(file)
        
    def browse_csv_dir(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Folder Containing CSV Files");
        if directory: self.csv_dir_line_edit.setText(directory)
        
    def browse_output(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory: self.output_dir_line_edit.setText(directory)

    def browse_reid_model(self):
        file, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Re-ID Model", "", "PyTorch Models (*.pt)");
        if file: self.reid_model_edit.setText(file)

    def calculate_optimal_distance(self):
        if not self.video_files: QtWidgets.QMessageBox.warning(self, "Input Error", "Please add at least one video file to calculate parameters from."); return
        video_path = self.video_files[0]
        csv_dir = self.csv_dir_line_edit.text() if self.csv_dir_line_edit.text() and os.path.isdir(self.csv_dir_line_edit.text()) else os.path.dirname(video_path)
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        csv_path = os.path.join(csv_dir, f"{base_name}_detections.csv")
        if not os.path.exists(csv_path): csv_path = os.path.join(csv_dir, f"{base_name}_segmentations.csv")
        if not os.path.exists(csv_path): csv_path = os.path.join(csv_dir, f"{base_name}.csv")
        if not os.path.exists(csv_path): QtWidgets.QMessageBox.warning(self, "Input Error", f"Could not find a matching detections CSV for the first video:\n{os.path.basename(video_path)}"); return
        try:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            df = pd.read_csv(csv_path);
            if 'cx' not in df.columns or 'cy' not in df.columns or 'frame_idx' not in df.columns: QtWidgets.QMessageBox.warning(self, "CSV Error", "The CSV file must contain 'frame_idx', 'cx', and 'cy' columns."); return
            df = df.sort_values('frame_idx').dropna(subset=['cx', 'cy']); speeds = np.sqrt(np.diff(df['cx'])**2 + np.diff(df['cy'])**2)
            if len(speeds) > 0:
                avg_speed = np.mean(speeds); optimal_dist = avg_speed * 3.0; self.norfair_dist_thresh.setValue(optimal_dist)
                QtWidgets.QMessageBox.information(self, "Success", f"Calculated an optimal distance threshold of {optimal_dist:.2f} based on the average inter-frame movement.")
            else: QtWidgets.QMessageBox.information(self, "Info", "Not enough movement detected to calculate an optimal distance. Using default.")
        except Exception as e: QtWidgets.QMessageBox.critical(self, "Error", f"Failed to calculate optimal distance: {e}")
        finally: QtWidgets.QApplication.restoreOverrideCursor()

    def start_processing(self):
        if not self.video_files: QtWidgets.QMessageBox.warning(self, "Input Error", "Please add at least one video file."); return
        if not self.settings_line_edit.text() or not os.path.exists(self.settings_line_edit.text()): QtWidgets.QMessageBox.warning(self, "Input Error", "Please select a valid settings.json file."); return
        if not self.output_dir_line_edit.text() or not os.path.isdir(self.output_dir_line_edit.text()): QtWidgets.QMessageBox.warning(self, "Input Error", "Please select a valid output directory."); return
        if not any([self.save_video_checkbox.isChecked(), self.save_csv_checkbox.isChecked(), self.save_centroid_csv_checkbox.isChecked(), self.save_excel_track_checkbox.isChecked(), self.save_excel_tank_checkbox.isChecked(), self.save_trajectory_img_checkbox.isChecked(), self.save_heatmap_img_checkbox.isChecked()]): QtWidgets.QMessageBox.warning(self, "Input Error", "Please select at least one output option."); return
        
        tracking_method = self.tracking_method_combo.currentText()
        if tracking_method in ["StrongSORT", "BoTSORT"] and not self.reid_model_edit.text():
            QtWidgets.QMessageBox.warning(self, "Input Error", f"Please select a Re-ID model weights file for {tracking_method}."); return
        
        self.toggle_controls(False); self.log_text_edit.clear()
        
        iou_thresh = self.iou_threshold_input.value()
        
        tracker_params = {}
        if tracking_method == "Norfair":
            tracker_params = {
                'distance_function': self.norfair_distance_fn_combo.currentText(),
                'distance_threshold': self.norfair_dist_thresh.value(),
                'hit_counter_max': self.norfair_hit_counter.value(),
                'initialization_delay': self.norfair_init_delay.value(),
                'past_detections_length': self.norfair_past_detections.value()
            }
        elif tracking_method in ["BoT-SORT", "StrongSORT"]:
             tracker_params = {'model_weights': self.reid_model_edit.text(), 'max_dist': self.strongsort_max_dist.value(), 'max_age': self.strongsort_max_age.value(), 'n_init': self.strongsort_n_init.value()}
        
        self.batch_worker = BatchProcessor(
            self.video_files, self.settings_line_edit.text(), self.output_dir_line_edit.text(), 
            csv_dir=self.csv_dir_line_edit.text(), tracking_method=tracking_method, 
            tracker_params=tracker_params,
            max_animals_per_tank=self.max_animals_spinbox.value(),
            frame_sample_rate=self.frame_sample_rate_spinbox.value(),
            auto_stitch=self.auto_stitch_checkbox.isChecked(),
            save_video=self.save_video_checkbox.isChecked(), save_csv=self.save_csv_checkbox.isChecked(), 
            save_centroid_csv=self.save_centroid_csv_checkbox.isChecked(), 
            save_excel_track=self.save_excel_track_checkbox.isChecked(), 
            save_excel_tank=self.save_excel_tank_checkbox.isChecked(),
            save_trajectory_img=self.save_trajectory_img_checkbox.isChecked(), save_heatmap_img=self.save_heatmap_img_checkbox.isChecked(), 
            time_gap_seconds=self.time_gap_spinbox.value(), draw_overlays=self.show_overlays_checkbox.isChecked(),
            iou_threshold=iou_thresh 
        )
        self.batch_worker.batch_processor = self.batch_worker 
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
        self.file_progress_bar.setValue(0); self.file_progress_label.setText("Frame: 0 / 0"); self.elapsed_time_label.setText("Elapsed: 00:00:00"); self.etr_label.setText("ETR: --:--:--"); self.speed_label.setText("Speed: 0.00 FPS")
    def update_file_progress(self, percentage, current_frame, total_frames):
        self.file_progress_bar.setValue(percentage); self.file_progress_label.setText(f"Frame: {current_frame} / {total_frames}")
    def update_time_labels(self, elapsed, etr):
        self.elapsed_time_label.setText(f"Elapsed: {elapsed}"); self.etr_label.setText(f"ETR: {etr}")
    def update_speed_label(self, fps):
        self.speed_label.setText(f"Speed: {fps:.2f} FPS")
    def toggle_controls(self, enabled):
        self.start_btn.setEnabled(enabled); self.add_videos_btn.setEnabled(enabled); self.browse_settings_btn.setEnabled(enabled); self.browse_output_btn.setEnabled(enabled); self.browse_csv_dir_btn.setEnabled(enabled); self.add_directory_btn.setEnabled(enabled); self.remove_video_btn.setEnabled(enabled); self.clear_videos_btn.setEnabled(enabled)
        self.cancel_btn.setEnabled(not enabled)
    def closeEvent(self, event):
        if self.batch_thread and self.batch_thread.isRunning():
            self.cancel_processing(); self.batch_thread.quit(); self.batch_thread.wait()
        event.accept()