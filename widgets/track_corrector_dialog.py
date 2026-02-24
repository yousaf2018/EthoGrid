# EthoGrid_App/widgets/track_corrector_dialog.py

import os
import cv2
import json # Ensure json is imported
import pandas as pd
from collections import defaultdict
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import QThread, QPoint
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QTransform
from workers.track_corrector_worker import TrackCorrectorWorker
from workers.video_saver import VideoSaver
from widgets.base_dialog import BaseDialog
from widgets.custom_widgets import CustomSpinBox
import numpy as np

class TrackCorrectorDialog(BaseDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Interactive Track Corrector (Excel Database)")
        self.setMinimumSize(1400, 900)
        
        self.video_path = None; self.df = None; self.cap = None; self.current_frame_idx = 0; self.total_frames = 0
        self.grid_settings = {'cols': 1, 'rows': 1}
        self.grid_transform = QTransform()
        
        self.play_timer = QtCore.QTimer(self)
        
        # Thread management
        self.worker_thread = None
        self.corrector_worker = None
        self.video_saver_thread = None
        self.video_saver_worker = None
        
        # Consistent Color Generation
        np.random.seed(42)
        self.track_colors = defaultdict(lambda: tuple(np.random.randint(50, 255, 3).tolist()))
        
        main_layout = QtWidgets.QHBoxLayout(self)
        
        left_pane_scroll = QtWidgets.QScrollArea(); left_pane_scroll.setWidgetResizable(True)
        left_pane_scroll.setMinimumWidth(450)
        left_pane_widget = QtWidgets.QWidget(); left_pane = QtWidgets.QVBoxLayout(left_pane_widget)
        left_pane_scroll.setWidget(left_pane_widget)
        
        right_pane = QtWidgets.QVBoxLayout()
        
        input_group = QtWidgets.QGroupBox("1. Input Files"); input_layout = QtWidgets.QFormLayout(input_group)
        self.video_line_edit = QtWidgets.QLineEdit(); self.video_line_edit.setPlaceholderText("Load a video file (.mp4, .avi)")
        self.browse_video_btn = QtWidgets.QPushButton("Browse...")
        self.excel_line_edit = QtWidgets.QLineEdit(); self.excel_line_edit.setPlaceholderText("Load a _by_track.xlsx file")
        self.browse_excel_btn = QtWidgets.QPushButton("Browse...")
        self.settings_line_edit = QtWidgets.QLineEdit(); self.settings_line_edit.setPlaceholderText("Load settings.json (for video export)")
        self.browse_settings_btn = QtWidgets.QPushButton("Browse...")
        
        input_layout.addRow("Video File:", self.create_hbox(self.video_line_edit, self.browse_video_btn))
        input_layout.addRow("Tracking Excel:", self.create_hbox(self.excel_line_edit, self.browse_excel_btn))
        input_layout.addRow("Settings JSON:", self.create_hbox(self.settings_line_edit, self.browse_settings_btn))
        left_pane.addWidget(input_group)
        
        navigation_group = QtWidgets.QGroupBox("2. Navigation"); nav_layout = QtWidgets.QVBoxLayout(navigation_group)
        self.frame_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.frame_label = QtWidgets.QLabel("Frame: 0 / 0")
        playback_layout = QtWidgets.QHBoxLayout(); self.prev_frame_btn = QtWidgets.QPushButton("◀"); self.play_pause_btn = QtWidgets.QPushButton("▶"); self.next_frame_btn = QtWidgets.QPushButton("▶▶")
        playback_layout.addWidget(self.prev_frame_btn); playback_layout.addWidget(self.play_pause_btn); playback_layout.addWidget(self.next_frame_btn)
        nav_layout.addLayout(playback_layout); nav_layout.addWidget(self.frame_slider); nav_layout.addWidget(self.frame_label); left_pane.addWidget(navigation_group)
        
        tracks_group = QtWidgets.QGroupBox("3. Active Tracks (Sorted by Tank)"); tracks_layout = QtWidgets.QVBoxLayout(tracks_group)
        self.track_list = QtWidgets.QListWidget(); self.track_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        tracks_layout.addWidget(self.track_list)
        left_pane.addWidget(tracks_group)

        manual_group = QtWidgets.QGroupBox("4. Frame-Forward Operations"); manual_layout = QtWidgets.QHBoxLayout(manual_group)
        self.swap_btn = QtWidgets.QPushButton("Swap Selected IDs"); self.swap_btn.setToolTip("Select exactly two tracks from the SAME tank to swap their IDs.")
        self.delete_btn = QtWidgets.QPushButton("Delete Selected Tracks"); self.delete_btn.setToolTip("Select tracks to delete from this frame forward.")
        manual_layout.addWidget(self.swap_btn); manual_layout.addWidget(self.delete_btn)
        left_pane.addWidget(manual_group)
        
        self.stitch_group = QtWidgets.QGroupBox("5. Per-Tank Batch Stitching")
        stitch_main_layout = QtWidgets.QVBoxLayout(self.stitch_group)
        self.stitch_scroll = QtWidgets.QScrollArea(); self.stitch_scroll.setWidgetResizable(True); self.stitch_scroll.setMinimumHeight(200)
        self.stitch_widget = QtWidgets.QWidget(); self.stitch_layout = QtWidgets.QVBoxLayout(self.stitch_widget)
        self.stitch_scroll.setWidget(self.stitch_widget)
        stitch_main_layout.addWidget(self.stitch_scroll)
        left_pane.addWidget(self.stitch_group)
        
        auto_correct_group = QtWidgets.QGroupBox("6. Global Auto-Correction"); auto_correct_layout = QtWidgets.QFormLayout(auto_correct_group)
        self.max_animals_spinbox = CustomSpinBox(value=1, minimum=1, maximum=100)
        self.enforce_max_btn = QtWidgets.QPushButton("Enforce Max Animals")
        auto_correct_layout.addRow("Max Animals Per Tank:", self.max_animals_spinbox); auto_correct_layout.addRow(self.enforce_max_btn); left_pane.addWidget(auto_correct_group)
        
        interpolation_group = QtWidgets.QGroupBox("7. Gap Filling (Interpolation)"); interp_layout = QtWidgets.QFormLayout(interpolation_group)
        self.interp_method_combo = QtWidgets.QComboBox(); self.interp_method_combo.addItems(["Linear", "Forward Fill (ffill)", "Backward Fill (bfill)"])
        self.interp_limit_spinbox = CustomSpinBox(value=15, minimum=1, maximum=1000, toolTip="Max number of consecutive missing frames to fill.")
        self.apply_interp_btn = QtWidgets.QPushButton("Apply Interpolation")
        interp_layout.addRow("Method:", self.interp_method_combo); interp_layout.addRow("Max Gap (frames):", self.interp_limit_spinbox); interp_layout.addRow(self.apply_interp_btn); left_pane.addWidget(interpolation_group)
        
        save_group = QtWidgets.QGroupBox("8. Export"); save_layout = QtWidgets.QVBoxLayout(save_group)
        self.save_excel_btn = QtWidgets.QPushButton("Save Corrected Excel (by Track)")
        video_export_layout = QtWidgets.QHBoxLayout()
        self.export_video_btn = QtWidgets.QPushButton("Export Corrected Video")
        self.draw_overlays_checkbox = QtWidgets.QCheckBox("Draw Overlays"); self.draw_overlays_checkbox.setChecked(True)
        video_export_layout.addWidget(self.export_video_btn); video_export_layout.addWidget(self.draw_overlays_checkbox)
        save_layout.addWidget(self.save_excel_btn); save_layout.addLayout(video_export_layout); left_pane.addWidget(save_group); left_pane.addStretch()

        self.video_display = QtWidgets.QLabel("Load a video and tracking Excel file to begin."); self.video_display.setAlignment(QtCore.Qt.AlignCenter); self.video_display.setMinimumSize(800, 600)
        
        self.bottom_tabs = QtWidgets.QTabWidget(); self.bottom_tabs.setMaximumHeight(200)
        log_widget = QtWidgets.QWidget(); log_layout = QtWidgets.QVBoxLayout(log_widget)
        self.log_text = QtWidgets.QTextEdit(); self.log_text.setReadOnly(True); log_layout.addWidget(self.log_text)
        self.bottom_tabs.addTab(log_widget, "Log")
        self.progress_bar = QtWidgets.QProgressBar()
        
        right_pane.addWidget(self.video_display, stretch=1)
        right_pane.addWidget(self.bottom_tabs)
        right_pane.addWidget(self.progress_bar)
        
        main_layout.addWidget(left_pane_scroll, 1); main_layout.addLayout(right_pane, 3)
        
        self.browse_video_btn.clicked.connect(self.load_video); self.browse_excel_btn.clicked.connect(self.load_excel); self.browse_settings_btn.clicked.connect(self.load_settings)
        self.frame_slider.valueChanged.connect(self.slider_value_changed); self.track_list.itemSelectionChanged.connect(self.update_visualization)
        self.swap_btn.clicked.connect(self.perform_swap); self.delete_btn.clicked.connect(self.perform_delete)
        self.save_excel_btn.clicked.connect(self.save_corrected_excel); self.export_video_btn.clicked.connect(self.export_video)
        self.play_timer.timeout.connect(self.next_frame); self.play_pause_btn.clicked.connect(self.toggle_play); self.next_frame_btn.clicked.connect(self.next_frame); self.prev_frame_btn.clicked.connect(self.prev_frame)
        self.enforce_max_btn.clicked.connect(self.enforce_max_animals); self.apply_interp_btn.clicked.connect(self.apply_interpolation)
        self.set_controls_enabled(False)
    
    def set_controls_enabled(self, enabled):
        for widget in [self.frame_slider, self.track_list, self.swap_btn, self.delete_btn, self.save_excel_btn, self.play_pause_btn, self.next_frame_btn, self.prev_frame_btn, self.enforce_max_btn, self.apply_interp_btn, self.export_video_btn, self.draw_overlays_checkbox]:
            widget.setEnabled(enabled)

    def create_hbox(self, w1, w2): widget = QtWidgets.QWidget(); layout = QtWidgets.QHBoxLayout(widget); layout.addWidget(w1); layout.addWidget(w2); layout.setContentsMargins(0,0,0,0); return widget

    def load_video(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Video File", "", "Video Files (*.mp4 *.avi *.mov)");
        if path:
            self.video_path = path; self.video_line_edit.setText(path)
            if self.cap: self.cap.release()
            self.cap = cv2.VideoCapture(self.video_path)
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)); self.frame_slider.setMaximum(self.total_frames - 1)
            if self.df is not None: self.set_controls_enabled(True); self.update_frame(0)

    def load_excel(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Tracking Excel", "", "Excel Files (*_by_track.xlsx *_by_tank.xlsx)")
        if path:
            try:
                self.excel_line_edit.setText(path)
                QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
                xls_data = pd.read_excel(path, sheet_name=None)
                dfs = []
                for sheet_name, sheet_df in xls_data.items():
                    tank_num = 1; track_id = 1
                    if "Tank_" in sheet_name:
                        tank_num = int(sheet_name.split("_")[1]); track_id = tank_num
                    elif "Track_" in sheet_name:
                        try:
                            tid = int(sheet_name.split("_")[1])
                            track_id = tid
                            tank_num = tid // 1000 if tid >= 1000 else 1
                        except: pass
                    
                    if 'tank_number' not in sheet_df.columns: sheet_df['tank_number'] = tank_num
                    if 'track_id' not in sheet_df.columns: sheet_df['track_id'] = track_id
                    dfs.append(sheet_df)
                
                self.df = pd.concat(dfs, ignore_index=True)
                
                if 'global_id' not in self.df.columns:
                    self.df['global_id'] = self.df.apply(lambda row: f"{int(row['tank_number'])}_{int(row['track_id'])}", axis=1)
                
                self.build_tank_stitching_ui()
                if self.cap is not None: self.set_controls_enabled(True); self.update_frame(0)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"Failed to load or parse Excel file:\n{e}")
            finally:
                QtWidgets.QApplication.restoreOverrideCursor()

    def load_settings(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Settings File", "", "JSON Files (*.json)");
        if path:
            try:
                with open(path, 'r') as f: settings_data = json.load(f)
                self.grid_settings = settings_data['grid_settings']
                tf = settings_data['grid_transform']
                w = settings_data['video_dimensions']['width']; h = settings_data['video_dimensions']['height']
                self.grid_transform = QTransform()
                self.grid_transform.translate(w * tf['center_x'], h * tf['center_y'])
                self.grid_transform.rotate(tf['angle'])
                self.grid_transform.scale(tf['scale_x'], tf['scale_y'])
                self.grid_transform.translate(-w / 2, -h / 2)
                self.settings_line_edit.setText(path)
                self.log_text.append("Grid settings loaded successfully.")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"Failed to load settings file: {e}")

    def build_tank_stitching_ui(self):
        while self.stitch_layout.count():
            item = self.stitch_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        if self.df is None: return
        
        tanks = sorted(self.df['tank_number'].dropna().unique())
        self.stitch_widgets = {} 
        
        for tank_num in tanks:
            tank_df = self.df[self.df['tank_number'] == tank_num]
            unique_ids = sorted(tank_df['track_id'].dropna().unique())
            
            group = QtWidgets.QGroupBox(f"Tank {int(tank_num)}")
            layout = QtWidgets.QHBoxLayout(group)
            
            target_combo = QtWidgets.QComboBox()
            target_combo.addItems([str(int(tid)) for tid in unique_ids])
            target_combo.setToolTip("Target ID (Keep)")
            
            merge_edit = QtWidgets.QLineEdit()
            merge_edit.setPlaceholderText("e.g. 1002, 1003")
            merge_edit.setToolTip("Comma-separated IDs to MERGE into target")
            
            apply_btn = QtWidgets.QPushButton("Apply")
            
            layout.addWidget(QtWidgets.QLabel("Target:")); layout.addWidget(target_combo)
            layout.addWidget(QtWidgets.QLabel("Merge:")); layout.addWidget(merge_edit)
            layout.addWidget(apply_btn)
            
            self.stitch_widgets[tank_num] = {'combo': target_combo, 'edit': merge_edit}
            apply_btn.clicked.connect(lambda checked, t=tank_num: self.handle_stitch_click(t))
            
            self.stitch_layout.addWidget(group)

    def handle_stitch_click(self, tank_num):
        widgets = self.stitch_widgets.get(tank_num)
        if not widgets: return
        
        target_id_str = widgets['combo'].currentText()
        merge_ids_str = widgets['edit'].text()
        
        if not merge_ids_str: return
        try:
            target_id = int(target_id_str)
            merge_ids = [int(i.strip()) for i in merge_ids_str.split(',') if i.strip()]
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Input Error", "IDs must be integers."); return
            
        if target_id in merge_ids:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Target ID cannot be in the list of IDs to merge."); return
            
        reply = QtWidgets.QMessageBox.question(self, 'Confirm Stitch', f"Merge histories of IDs {merge_ids} into Target ID {target_id} in Tank {int(tank_num)} globally?", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.No: return
        
        target_global_id = f"{int(tank_num)}_{target_id}"
        merge_global_ids = [f"{int(tank_num)}_{mid}" for mid in merge_ids]
        
        params = {'target_global_id': target_global_id, 'merge_global_ids': merge_global_ids}
        self.run_worker('stitch_list', params)

    def slider_value_changed(self, value): self.update_frame(value)

    def update_frame(self, frame_idx):
        if self.cap is None or self.df is None: return
        self.current_frame_idx = frame_idx; self.frame_slider.setValue(frame_idx); self.frame_label.setText(f"Frame: {self.current_frame_idx} / {self.total_frames}")
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx); ret, frame = self.cap.read()
        if not ret: return
        
        self.current_frame_detections = self.df[self.df['frame_idx'] == frame_idx]
        sorted_dets = self.current_frame_detections.sort_values(by=['tank_number', 'track_id'])
        
        self.track_list.blockSignals(True); self.track_list.clear()
        if not sorted_dets.empty:
            for _, row in sorted_dets.iterrows():
                self.track_list.addItem(f"Tank {int(row['tank_number'])} - ID {int(row['track_id'])}")
        self.track_list.blockSignals(False); self.update_visualization()

    def update_visualization(self):
        if self.cap is None or self.df is None: return
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame_idx); ret, frame = self.cap.read()
        if not ret: return
        selected_text = [item.text() for item in self.track_list.selectedItems()]
        if not self.current_frame_detections.empty:
            for _, row in self.current_frame_detections.iterrows():
                track_id = int(row['track_id']); item_text = f"Tank {int(row['tank_number'])} - ID {track_id}"
                
                # ### THE FIX IS HERE ###
                # Consistent color generation
                color_bgr = self.track_colors[track_id]
                
                # If selected, override with green
                if item_text in selected_text:
                    color_bgr = (0, 255, 0)
                
                x1, y1, x2, y2 = int(row['x1']), int(row['y1']), int(row['x2']), int(row['y2'])
                cv2.rectangle(frame, (x1, y1), (x2, y2), color_bgr, 2)
                cv2.putText(frame, str(track_id), (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color_bgr, 2)
                
        h, w, ch = frame.shape; bytes_per_line = ch * w
        q_img = QtGui.QImage(frame.data, w, h, bytes_per_line, QtGui.QImage.Format_BGR888)
        self.video_display.setPixmap(QPixmap.fromImage(q_img).scaled(self.video_display.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))

    def toggle_play(self):
        if self.play_timer.isActive(): self.play_timer.stop(); self.play_pause_btn.setText("▶")
        else: self.play_timer.start(1000 // 30); self.play_pause_btn.setText("⏸")
    def next_frame(self):
        if self.current_frame_idx < self.total_frames - 1: self.frame_slider.setValue(self.current_frame_idx + 1)
    def prev_frame(self):
        if self.current_frame_idx > 0: self.frame_slider.setValue(self.current_frame_idx - 1)
        
    def on_worker_finished(self, corrected_df):
        self.df = corrected_df; self.update_frame(self.current_frame_idx)
        self.build_tank_stitching_ui() 
        self.set_controls_enabled(True); self.progress_bar.setValue(0)
        # Clean up the thread
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None
        self.corrector_worker = None
        
    def on_worker_error(self, message):
        QtWidgets.QMessageBox.critical(self, "Error", message)
        self.set_controls_enabled(True)
        self.worker_thread = None
        self.corrector_worker = None
    
    def run_worker(self, operation, params):
        if self.worker_thread is not None and self.worker_thread.isRunning():
            self.log_text.append("[WARNING] Waiting for previous operation to cancel...")
            self.corrector_worker.requestInterruption()
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None

        self.set_controls_enabled(False)
        self.progress_bar.setValue(0)
        
        self.corrector_worker = TrackCorrectorWorker(self.df, operation, params)
        self.worker_thread = QThread()
        self.corrector_worker.moveToThread(self.worker_thread)
        
        self.corrector_worker.finished.connect(self.on_worker_finished)
        self.corrector_worker.error.connect(self.on_worker_error)
        self.corrector_worker.log.connect(self.log_text.append)
        self.corrector_worker.progress.connect(self.progress_bar.setValue)
        
        self.worker_thread.started.connect(self.corrector_worker.run)
        # We manually handle cleanup in on_worker_finished, so we don't connect finished signals here
        
        self.worker_thread.start()

    def perform_swap(self):
        selected = self.track_list.selectedItems()
        if len(selected) != 2: QtWidgets.QMessageBox.warning(self, "Selection Error", "Please select exactly two tracks to swap."); return
        tank1 = int(selected[0].text().split("Tank ")[1].split(" - ")[0])
        tank2 = int(selected[1].text().split("Tank ")[1].split(" - ")[0])
        if tank1 != tank2: QtWidgets.QMessageBox.warning(self, "Selection Error", "You can only swap IDs within the same tank."); return
        id1 = int(selected[0].text().split("ID ")[1]); id2 = int(selected[1].text().split("ID ")[1])
        params = {'frame_idx': self.current_frame_idx, 'global_id1': f"{tank1}_{id1}", 'global_id2': f"{tank1}_{id2}"}
        self.run_worker('swap', params)

    def perform_delete(self):
        selected = self.track_list.selectedItems()
        if not selected: QtWidgets.QMessageBox.warning(self, "Selection Error", "Please select at least one track to delete."); return
        reply = QtWidgets.QMessageBox.question(self, 'Confirm Deletion', "Delete future path of selected track(s)?", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.No: return
        for item in selected:
            tank = int(item.text().split("Tank ")[1].split(" - ")[0])
            tid = int(item.text().split("ID ")[1])
            params = {'frame_idx': self.current_frame_idx, 'global_id_to_delete': f"{tank}_{tid}"}
            self.run_worker('delete', params)
            
    def enforce_max_animals(self):
        if self.df is None: return
        reply = QtWidgets.QMessageBox.question(self, 'Confirm Auto-Correction', "Process entire dataset to merge excess tracks?", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.No: return
        params = {'max_animals': self.max_animals_spinbox.value()}; self.run_worker('enforce_max', params)
        
    def apply_interpolation(self):
        if self.df is None: return
        reply = QtWidgets.QMessageBox.question(self, 'Confirm Interpolation', "Fill gaps in all tracks up to the specified limit based on max animals?", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.No: return
        method_str = self.interp_method_combo.currentText()
        if 'Linear' in method_str: method = 'linear'
        elif 'ffill' in method_str: method = 'ffill'
        else: method = 'bfill'
        params = {'method': method, 'limit': self.interp_limit_spinbox.value(), 'max_animals': self.max_animals_spinbox.value()}
        self.run_worker('interpolate', params)

    def save_corrected_excel(self):
        if self.df is None: return
        original_path = self.excel_line_edit.text()
        default_name = os.path.splitext(original_path)[0] + "_corrected.xlsx"
        save_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Corrected Excel", default_name, "Excel Files (*.xlsx)")
        if save_path:
            try:
                QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
                animal_data = defaultdict(list)
                for _, row in self.df.iterrows():
                    det = row.to_dict(); key = int(det.get('track_id', det.get('tank_number', 1))); animal_data[key].append(det)

                with pd.ExcelWriter(save_path, engine='openpyxl') as writer:
                    for animal_id in sorted(animal_data.keys()):
                        sheet_name = f"Track_{animal_id}"
                        animal_df = pd.DataFrame(animal_data[animal_id])
                        if 'global_id' in animal_df.columns: animal_df = animal_df.drop(columns=['global_id'])
                        animal_df.to_excel(writer, sheet_name=sheet_name, index=False, float_format='%.4f')
                QtWidgets.QMessageBox.information(self, "Success", f"Corrected data saved to:\n{save_path}")
            except Exception as e: QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save Excel file: {e}")
            finally: QtWidgets.QApplication.restoreOverrideCursor()

    def export_video(self):
        if self.df is None or self.video_path is None: return
        if not self.settings_line_edit.text() or not os.path.exists(self.settings_line_edit.text()):
            QtWidgets.QMessageBox.warning(self, "Input Error", "Please load a Settings JSON file to export a video with overlays.")
            return

        save_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Corrected Video", os.path.splitext(self.video_path)[0] + "_corrected.mp4", "MP4 Videos (*.mp4)")
        if not save_path: return
        
        self.log_text.append(f"Starting video export to {os.path.basename(save_path)}...")
        self.set_controls_enabled(False)
        
        # Clean up any existing video saver thread
        if self.video_saver_thread is not None and self.video_saver_thread.isRunning():
            self.video_saver_worker.stop()
            self.video_saver_thread.quit()
            self.video_saver_thread.wait()
            self.video_saver_thread = None

        cap = cv2.VideoCapture(self.video_path); fps = cap.get(cv2.CAP_PROP_FPS) or 30.0; video_size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))); cap.release()
        detections_dict = defaultdict(list)
        for _, row in self.df.iterrows():
            det = row.to_dict()
            detections_dict[int(row['frame_idx'])].append(det)
            
        all_behaviors = sorted(list(set(self.df['class_name'].dropna().unique())))
        predefined_colors = [(31,119,180),(255,127,14),(44,160,44),(214,39,40),(148,103,189),(140,86,75),(227,119,194),(127,127,127),(188,189,34),(23,190,207)]
        behavior_colors = {name: predefined_colors[i % len(predefined_colors)] for i, name in enumerate(all_behaviors)}
        
        timeline_segments = {}
        draw_overlays = self.draw_overlays_checkbox.isChecked()
        if draw_overlays:
            tank_data_for_timeline = defaultdict(lambda: defaultdict(str))
            for frame_idx, dets in detections_dict.items():
                for det in dets:
                    if det.get('tank_number') is not None:
                        tank_data_for_timeline[int(det['tank_number'])][frame_idx] = det.get("class_name", "")
            for tank_id, frames in tank_data_for_timeline.items():
                if not frames: continue
                segments, sorted_frames = [], sorted(frames.keys())
                start_frame, current_behavior = sorted_frames[0], frames[sorted_frames[0]]
                for i in range(1, len(sorted_frames)):
                    frame, prev_frame, behavior = sorted_frames[i], sorted_frames[i-1], frames[sorted_frames[i]]
                    if behavior != current_behavior or frame != prev_frame + 1:
                        segments.append((start_frame, prev_frame, current_behavior))
                        start_frame, current_behavior = frame, behavior
                segments.append((start_frame, sorted_frames[-1], current_behavior))
                timeline_segments[tank_id] = segments

        self.video_saver_worker = VideoSaver(
            source_video_path=self.video_path,
            output_video_path=save_path,
            detections=dict(detections_dict),
            grid_settings=self.grid_settings,
            grid_transform=self.grid_transform,
            behavior_colors=behavior_colors,
            video_size=video_size,
            fps=fps,
            line_thickness=self.grid_settings.get('line_thickness', 2),
            selected_cells=set(),
            timeline_segments=timeline_segments,
            draw_grid=False,
            draw_overlays=draw_overlays
        )
        
        self.video_saver_thread = QThread()
        self.video_saver_worker.moveToThread(self.video_saver_thread)
        
        # Local handler to safely cleanup
        def handle_vid_finish():
            self.log_text.append("Video export finished.")
            self.set_controls_enabled(True)
            self.video_saver_thread.quit()
            
        def handle_vid_err(msg):
            self.log_text.append(f"ERROR: {msg}")
            self.set_controls_enabled(True)
            self.video_saver_thread.quit()

        self.video_saver_worker.finished.connect(handle_vid_finish)
        self.video_saver_worker.error_occurred.connect(handle_vid_err)
        self.video_saver_worker.progress_updated.connect(self.progress_bar.setValue)
        
        self.video_saver_thread.started.connect(self.video_saver_worker.run)
        self.video_saver_worker.finished.connect(self.video_saver_worker.deleteLater)
        self.video_saver_thread.finished.connect(self.video_saver_thread.deleteLater)
        
        self.video_saver_thread.start()
        
    def closeEvent(self, event):
        if self.play_timer.isActive(): self.play_timer.stop()
        if self.cap: self.cap.release()
        
        if self.worker_thread and self.worker_thread.isRunning():
            if self.corrector_worker: self.corrector_worker.requestInterruption()
            self.worker_thread.quit()
            self.worker_thread.wait()
            
        if self.video_saver_thread and self.video_saver_thread.isRunning():
            if self.video_saver_worker: self.video_saver_worker.stop()
            self.video_saver_thread.quit()
            self.video_saver_thread.wait()
            
        event.accept()