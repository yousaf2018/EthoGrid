# EthoGrid_App/main_window.py

import os
import cv2
import csv
import json
import numpy as np
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QImage, QPixmap

# Local imports from the new modules
from workers.video_loader import VideoLoader
from workers.video_saver import VideoSaver
from workers.detection_processor import DetectionProcessor
from widgets.timeline_widget import TimelineWidget
from core.grid_manager import GridManager

class VideoPlayer(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(VideoPlayer, self).__init__(parent)
        self.setWindowTitle("EthoGrid")

        # --- State Management (No changes here) ---
        self.raw_detections = {}
        self.processed_detections = {}
        self.csv_headers = []
        self.current_frame = None
        self.current_frame_idx = 0
        self.total_frames = 0
        self.video_size = (0, 0)
        self.behavior_colors = {}
        self.predefined_colors = [(31,119,180),(255,127,14),(44,160,44),(214,39,40),(148,103,189),(140,86,75),(227,119,194),(127,127,127),(188,189,34),(23,190,207)]
        self.grid_settings = {'cols': 5, 'rows': 2}
        self.selected_cells = set()
        self.line_thickness = 2
        
        self.dragging_mode = None
        self.last_mouse_pos = None

        self.grid_manager = GridManager()
        self.video_loader = None
        self.video_saver = None
        self.detection_processor = None
        self.timeline_widget = None
        self.legend_group_box = None

        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        ### --- UI REORGANIZATION START --- ###
        # The entire UI structure is refactored for a better layout.

        self.setStyleSheet("""
            QWidget { background-color: #2b2b2b; color: #e0e0e0; font-family: Segoe UI; font-size: 12px; border: none; }
            QGroupBox { border: 1px solid #4a4a4a; margin-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top center; padding: 0 3px; }
            QLabel#statusLabel { color: #ffc107; background-color: transparent; border: none; }
            QLabel#videoLabel { background-color: #1e1e1e; border: 1px solid #3e3e3e; }
            QPushButton { background-color: #3a3a3a; border: 1px solid #4a4a4a; border-radius: 3px; padding: 5px 10px; min-width: 80px; }
            QPushButton:hover { background-color: #4a4a4a; }
            QPushButton:pressed { background-color: #2a2a2a; }
            QPushButton:disabled { background-color: #2f2f2f; color: #6a6a6a; }
            QSlider::groove:horizontal { height: 6px; background: #3a3a3a; border-radius: 3px; }
            QSlider::handle:horizontal { width: 14px; height: 14px; background: #5a5a5a; border-radius: 7px; margin: -4px 0; }
            QSpinBox, QLineEdit { background-color: #252525; border: 1px solid #3a3a3a; border-radius: 3px; padding: 3px 5px; selection-background-color: #3a6ea5; }
            QProgressBar { border: 1px solid #3a3a3a; border-radius: 3px; text-align: center; }
            QProgressBar::chunk { background-color: #3a6ea5; width: 10px; }
        """)
        
        # --- Create All Widgets First ---
        self.video_label = QtWidgets.QLabel()
        self.video_label.setObjectName("videoLabel")
        self.video_label.setAlignment(QtCore.Qt.AlignCenter)
        self.video_label.setMinimumSize(640, 480) # Give it a reasonable minimum size

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        
        # Playback Controls
        self.play_btn = QtWidgets.QPushButton("▶ Play")
        self.pause_btn = QtWidgets.QPushButton("⏸ Pause")
        self.stop_btn = QtWidgets.QPushButton("⏹ Stop")
        self.frame_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.frame_slider.setEnabled(False)
        self.frame_label = QtWidgets.QLabel("Frame: 0/0")
        
        # Timeline
        self.timeline_widget = TimelineWidget(self)
        self.progress_bar = QtWidgets.QProgressBar(); self.progress_bar.setRange(0, 100); self.progress_bar.setTextVisible(False)
        
        # --- Right Sidebar Widgets ---
        self.legend_group_box = QtWidgets.QGroupBox("Behavior Legend")
        self.legend_layout = QtWidgets.QVBoxLayout()
        self.legend_layout.setAlignment(QtCore.Qt.AlignTop)
        self.legend_group_box.setLayout(self.legend_layout)

        grid_config_group = QtWidgets.QGroupBox("Tank Configuration")
        self.grid_cols_spin = QtWidgets.QSpinBox(); self.grid_cols_spin.setRange(1, 20); self.grid_cols_spin.setValue(5)
        self.grid_rows_spin = QtWidgets.QSpinBox(); self.grid_rows_spin.setRange(1, 20); self.grid_rows_spin.setValue(2)
        self.line_thickness_spin = QtWidgets.QSpinBox(); self.line_thickness_spin.setRange(1, 5); self.line_thickness_spin.setValue(2)
        self.reset_grid_btn = QtWidgets.QPushButton("Reset Grid")
        self.rotate_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.rotate_slider.setRange(-180, 180); self.rotate_slider.setValue(0)
        self.scale_x_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.scale_x_slider.setRange(10, 200); self.scale_x_slider.setValue(100)
        self.scale_y_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.scale_y_slider.setRange(10, 200); self.scale_y_slider.setValue(100)
        self.move_x_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.move_x_slider.setRange(-100, 100); self.move_x_slider.setValue(0)
        self.move_y_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.move_y_slider.setRange(-100, 100); self.move_y_slider.setValue(0)
        
        self.tank_selection_label = QtWidgets.QLabel("Selected Tanks: None")
        self.select_all_btn = QtWidgets.QPushButton("Select All")
        self.clear_selection_btn = QtWidgets.QPushButton("Clear Selection")

        # --- Top Toolbar Widgets ---
        self.load_video_btn = QtWidgets.QPushButton("🎬 Load Video")
        self.load_csv_btn = QtWidgets.QPushButton("📄 Load Detections")
        self.save_csv_btn = QtWidgets.QPushButton("📝 Save w/ Tanks"); self.save_csv_btn.setEnabled(False)
        self.export_video_btn = QtWidgets.QPushButton("📹 Export Video"); self.export_video_btn.setEnabled(False)
        self.save_settings_btn = QtWidgets.QPushButton("💾 Save Settings")
        self.load_settings_btn = QtWidgets.QPushButton("📂 Load Settings")


        # --- Assemble Layouts ---
        
        ### NEW: Main layout is a vertical box
        main_layout = QtWidgets.QVBoxLayout(self)

        ### NEW: Top toolbars for file/settings operations
        file_layout = QtWidgets.QHBoxLayout()
        file_layout.addWidget(self.load_video_btn)
        file_layout.addWidget(self.load_csv_btn)
        file_layout.addWidget(self.save_csv_btn)
        file_layout.addWidget(self.export_video_btn)
        file_layout.addStretch()

        settings_layout = QtWidgets.QHBoxLayout()
        settings_layout.addWidget(self.load_settings_btn)
        settings_layout.addWidget(self.save_settings_btn)
        settings_layout.addStretch()

        main_layout.addLayout(file_layout)
        main_layout.addLayout(settings_layout)

        ### NEW: Main horizontal layout for the left (video) and right (controls) panes
        main_h_layout = QtWidgets.QHBoxLayout()
        
        # --- Left Pane (Video and Playback) ---
        left_pane_layout = QtWidgets.QVBoxLayout()
        left_pane_layout.addWidget(self.video_label, stretch=1) # The video label takes all available vertical space
        left_pane_layout.addWidget(self.status_label)
        
        controls_layout = QtWidgets.QHBoxLayout()
        controls_layout.addWidget(self.play_btn)
        controls_layout.addWidget(self.pause_btn)
        controls_layout.addWidget(self.stop_btn)
        controls_layout.addWidget(self.frame_slider, stretch=1)
        controls_layout.addWidget(self.frame_label)
        
        left_pane_layout.addLayout(controls_layout)
        left_pane_layout.addWidget(self.timeline_widget)
        left_pane_layout.addWidget(self.progress_bar)

        # --- Right Pane (Configuration and Tools) ---
        right_pane_widget = QtWidgets.QWidget()
        right_pane_widget.setFixedWidth(280) # Give sidebar a fixed width
        right_pane_layout = QtWidgets.QVBoxLayout(right_pane_widget)
        
        right_pane_layout.addWidget(self.legend_group_box)
        
        ### MOVED: Grid config moved to the right sidebar
        grid_config_layout = QtWidgets.QGridLayout(grid_config_group)
        grid_config_layout.addWidget(QtWidgets.QLabel("Columns:"), 0, 0); grid_config_layout.addWidget(self.grid_cols_spin, 0, 1)
        grid_config_layout.addWidget(QtWidgets.QLabel("Rows:"), 1, 0); grid_config_layout.addWidget(self.grid_rows_spin, 1, 1)
        grid_config_layout.addWidget(QtWidgets.QLabel("Line Thickness:"), 2, 0); grid_config_layout.addWidget(self.line_thickness_spin, 2, 1)
        grid_config_layout.addWidget(QtWidgets.QLabel("Rotation:"), 3, 0); grid_config_layout.addWidget(self.rotate_slider, 3, 1)
        grid_config_layout.addWidget(QtWidgets.QLabel("Scale X:"), 4, 0); grid_config_layout.addWidget(self.scale_x_slider, 4, 1)
        grid_config_layout.addWidget(QtWidgets.QLabel("Scale Y:"), 5, 0); grid_config_layout.addWidget(self.scale_y_slider, 5, 1)
        grid_config_layout.addWidget(QtWidgets.QLabel("Move X:"), 6, 0); grid_config_layout.addWidget(self.move_x_slider, 6, 1)
        grid_config_layout.addWidget(QtWidgets.QLabel("Move Y:"), 7, 0); grid_config_layout.addWidget(self.move_y_slider, 7, 1)
        grid_config_layout.addWidget(self.reset_grid_btn, 8, 0, 1, 2)
        right_pane_layout.addWidget(grid_config_group)

        ### MOVED: Tank selection moved to the right sidebar
        selection_layout = QtWidgets.QHBoxLayout()
        selection_layout.addWidget(self.tank_selection_label, stretch=1)
        selection_layout.addWidget(self.select_all_btn)
        selection_layout.addWidget(self.clear_selection_btn)
        right_pane_layout.addLayout(selection_layout)
        
        right_pane_layout.addStretch() # Push all controls to the top

        # --- Add Panes to Main Horizontal Layout ---
        main_h_layout.addLayout(left_pane_layout, stretch=1) # Left pane should expand
        main_h_layout.addWidget(right_pane_widget)      # Right pane is fixed width

        main_layout.addLayout(main_h_layout)

        ### NEW: Adjust window size for the new layout
        self.setMinimumSize(1280, 800)
        ### --- UI REORGANIZATION END --- ###

    # The rest of the file (setup_connections, all methods, etc.) remains unchanged.
    # Just copy everything from your original file from this point onward.
    def setup_connections(self):
        # Playback controls
        self.play_btn.clicked.connect(self.start_playback)
        self.pause_btn.clicked.connect(self.pause_playback)
        self.stop_btn.clicked.connect(self.stop_playback)
        self.frame_slider.sliderMoved.connect(self.seek_frame)
        
        # File I/O
        self.load_video_btn.clicked.connect(self.load_video)
        self.load_csv_btn.clicked.connect(self.load_detections)
        self.save_csv_btn.clicked.connect(self.save_detections_with_tanks)
        self.export_video_btn.clicked.connect(self.export_video)
        self.save_settings_btn.clicked.connect(self.save_settings)
        self.load_settings_btn.clicked.connect(self.load_settings)
        
        # Grid Configuration UI
        self.grid_cols_spin.valueChanged.connect(self.update_grid_settings)
        self.grid_rows_spin.valueChanged.connect(self.update_grid_settings)
        self.line_thickness_spin.valueChanged.connect(self.update_line_thickness)
        self.reset_grid_btn.clicked.connect(self.reset_grid_transform_and_ui)
        
        # Grid Transform UI
        self.rotate_slider.valueChanged.connect(self.update_grid_rotation)
        self.scale_x_slider.valueChanged.connect(self.update_grid_scale)
        self.scale_y_slider.valueChanged.connect(self.update_grid_scale)
        self.move_x_slider.valueChanged.connect(self.update_grid_position)
        self.move_y_slider.valueChanged.connect(self.update_grid_position)
        
        # Re-process detections when transform sliders are released
        self.rotate_slider.sliderReleased.connect(self.start_detection_processing)
        self.scale_x_slider.sliderReleased.connect(self.start_detection_processing)
        self.scale_y_slider.sliderReleased.connect(self.start_detection_processing)
        self.move_x_slider.sliderReleased.connect(self.start_detection_processing)
        self.move_y_slider.sliderReleased.connect(self.start_detection_processing)
        
        # Tank selection
        self.select_all_btn.clicked.connect(self.select_all_tanks)
        self.clear_selection_btn.clicked.connect(self.clear_tank_selection)

        # Connect GridManager signal to update display
        self.grid_manager.transform_updated.connect(self.update_display)

        # Mouse events on video label for grid manipulation
        self.video_label.mousePressEvent = self.handle_mouse_press
        self.video_label.mouseMoveEvent = self.handle_mouse_move
        self.video_label.mouseReleaseEvent = self.handle_mouse_release

    # --- Display and Drawing ---

    def update_display(self):
        if self.current_frame is None: return
        try:
            frame = self.current_frame.copy()
            h, w, _ = frame.shape
            
            current_transform = self.grid_manager.transform
            
            def transform_point(x, y):
                p = current_transform.map(QPointF(x, y))
                return int(p.x()), int(p.y())

            for i in range(self.grid_settings['cols'] + 1):
                cv2.line(frame, transform_point(w*i/self.grid_settings['cols'],0), transform_point(w*i/self.grid_settings['cols'],h), (0,255,0), self.line_thickness)
            for i in range(self.grid_settings['rows'] + 1):
                cv2.line(frame, transform_point(0,h*i/self.grid_settings['rows']), transform_point(w,h*i/self.grid_settings['rows']), (0,255,0), self.line_thickness)
            
            center_px = self.grid_manager.center.x() * w, self.grid_manager.center.y() * h
            cv2.circle(frame, (int(center_px[0]), int(center_px[1])), 8, (0, 0, 255), -1)
            
            if self.current_frame_idx in self.processed_detections:
                for det in self.processed_detections[self.current_frame_idx]:
                    tank_number = det.get('tank_number')
                    if tank_number is not None and (not self.selected_cells or str(tank_number) in self.selected_cells):
                        x1, y1, x2, y2 = map(int, (det["x1"], det["y1"], det["x2"], det["y2"]))
                        behavior = det["class_name"]
                        color_rgb = self.behavior_colors.get(behavior, (128,128,128))
                        color_bgr = color_rgb[::-1]
                        
                        label = f"{tank_number}"
                        cv2.rectangle(frame, (x1, y1), (x2, y2), color_bgr, 2)
                        font_face, f_scale, f_thick = cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2
                        (t_w, t_h), _ = cv2.getTextSize(label, font_face, f_scale, f_thick)
                        cv2.rectangle(frame, (x1, y1 - t_h - 12), (x1 + t_w, y1), color_bgr, -1)
                        cv2.putText(frame, label, (x1, y1 - 7), font_face, f_scale, (0,0,0), f_thick, cv2.LINE_AA)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            qimg = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg).scaled(self.video_label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            self.video_label.setPixmap(pixmap)
        except Exception as e:
            print(f"Error updating display: {e}")

    def get_color_for_behavior(self, behavior_name):
        if behavior_name not in self.behavior_colors:
            color_index = len(self.behavior_colors) % len(self.predefined_colors)
            self.behavior_colors[behavior_name] = self.predefined_colors[color_index]
        return self.behavior_colors[behavior_name]

    def update_legend_widget(self):
        while self.legend_layout.count():
            item = self.legend_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for behavior, color_rgb in sorted(self.behavior_colors.items()):
            item_layout = QtWidgets.QHBoxLayout()
            
            color_label = QtWidgets.QLabel()
            color_label.setFixedSize(20, 20)
            color_label.setStyleSheet(f"background-color: rgb({color_rgb[0]}, {color_rgb[1]}, {color_rgb[2]}); border: 1px solid #5a5a5a;")
            
            text_label = QtWidgets.QLabel(behavior)
            
            item_layout.addWidget(color_label)
            item_layout.addWidget(text_label, stretch=1)
            self.legend_layout.addLayout(item_layout)

    # --- Playback Control Slots ---
    
    def start_playback(self):
        if self.video_loader: self.video_loader.set_playing(True)

    def pause_playback(self):
        if self.video_loader: self.video_loader.set_playing(False)

    def stop_playback(self):
        if self.video_loader:
            self.video_loader.set_playing(False)
            self.video_loader.seek(0)

    def seek_frame(self, pos):
        if self.video_loader:
            self.video_loader.set_playing(False)
            self.video_loader.seek(pos)
            
    def reset_playback(self):
        if self.video_loader: self.video_loader.stop()
        self.current_frame, self.current_frame_idx, self.total_frames = None, 0, 0
        self.frame_slider.setValue(0); self.frame_slider.setEnabled(False)
        self.frame_label.setText("Frame: 0/0")
        self.progress_bar.setValue(0)
        self.video_label.clear()
        self.behavior_colors.clear()
        self.update_legend_widget()
        if self.timeline_widget:
            self.timeline_widget.setData({}, {}, 0, 0)
        self._update_button_states()

    # --- File and Data Handling Slots ---

    def load_video(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Video File", "", "Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)")
        if file_path:
            self.reset_playback()
            self.video_loader = VideoLoader(file_path)
            self.video_loader.video_loaded.connect(self.on_video_loaded)
            self.video_loader.frame_loaded.connect(self.on_frame_loaded)
            self.video_loader.error_occurred.connect(self.show_error)
            self.video_loader.finished.connect(self.video_loader.deleteLater)
            self.video_loader.start()
            self.progress_bar.setRange(0, 0)
            self.video_label.setText("Loading video...")

    def on_video_loaded(self, width, height, fps):
        self.video_size = (width, height)
        self.total_frames = self.video_loader.total_frames
        self.frame_slider.setRange(0, self.total_frames - 1); self.frame_slider.setEnabled(True)
        self.frame_label.setText(f"Frame: 0/{self.total_frames - 1}")
        self.progress_bar.setRange(0, 100)
        
        self.grid_manager.set_video_size(width, height)
        
        self._update_button_states()
        self.video_loader.seek(0)
        if self.raw_detections:
            self.start_detection_processing()

    def on_frame_loaded(self, frame_idx, frame):
        self.current_frame_idx, self.current_frame = frame_idx, frame
        self.update_display()
        self.frame_slider.blockSignals(True)
        self.frame_slider.setValue(frame_idx)
        self.frame_slider.blockSignals(False)
        self.frame_label.setText(f"Frame: {frame_idx}/{self.total_frames - 1}")
        if self.total_frames > 0:
            progress = int((frame_idx + 1) * 100 / self.total_frames)
            if self.progress_bar.value() != progress:
                self.progress_bar.setValue(progress)
        if self.timeline_widget:
            self.timeline_widget.setCurrentFrame(frame_idx)

    def load_detections(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Detection CSV", "", "CSV Files (*.csv)")
        if file_path:
            try:
                detections = {}
                with open(file_path, newline="", encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    self.csv_headers = reader.fieldnames[:]
                    for row in reader:
                        idx = int(float(row["frame_idx"]))
                        row["x1"], row["y1"], row["x2"], row["y2"] = map(float, (row["x1"], row["y1"], row["x2"], row["y2"]))
                        detections.setdefault(idx, []).append(row)
                
                self.raw_detections = detections
                self.processed_detections = {}

                self.behavior_colors.clear()
                all_behaviors = sorted(list(set(det['class_name'] for dets in self.raw_detections.values() for det in dets)))
                for behavior in all_behaviors:
                    self.get_color_for_behavior(behavior)
                
                self.update_legend_widget()
                self.start_detection_processing()
                QtWidgets.QMessageBox.information(self, "Success", f"Loaded {len(self.raw_detections)} frames of detections.")
            except Exception as e:
                self.show_error(f"Error loading detections: {str(e)}")

    def start_detection_processing(self):
        if not self.raw_detections or self.video_size[0] == 0:
            return
        if self.detection_processor and self.detection_processor.isRunning():
            self.detection_processor.stop()
            self.detection_processor.wait()
        
        self.status_label.setText("Processing detections...")
        self.detection_processor = DetectionProcessor(
            self.raw_detections, self.grid_manager.transform, self.grid_settings, self.video_size
        )
        self.detection_processor.processing_finished.connect(self.on_processing_complete)
        self.detection_processor.error_occurred.connect(self.on_processing_error)
        
        self.detection_processor.finished.connect(self.detection_processor.deleteLater)
        self.detection_processor.finished.connect(self.on_processor_thread_finished)
        
        self.detection_processor.start()
        self._update_button_states()

    def on_processor_thread_finished(self):
        self.detection_processor = None
        self._update_button_states()

    def on_processing_complete(self, processed_detections, timeline_segments):
        self.processed_detections = processed_detections
        if self.timeline_widget:
            num_tanks = self.grid_settings['cols'] * self.grid_settings['rows']
            self.timeline_widget.setData(timeline_segments, self.behavior_colors, self.total_frames, num_tanks)
        self.status_label.setText("")
        self._update_button_states()
        self.update_display()

    def on_processing_error(self, message):
        self.status_label.setText("")
        self.show_error(message)
        self._update_button_states()

    def save_detections_with_tanks(self):
        if not self.processed_detections or self.video_size[0] == 0:
            self.show_error("Please load and process detections before saving.")
            return
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Detections with Tank Info", "detections_with_tanks.csv", "CSV Files (*.csv)")
        if not file_path: return
        try:
            all_detections = [det for frame_dets in self.processed_detections.values() for det in frame_dets]
            new_headers = self.csv_headers[:]
            if 'tank_number' not in new_headers: new_headers.append('tank_number')
            
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=new_headers, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(all_detections)
            QtWidgets.QMessageBox.information(self, "Success", f"Successfully saved to:\n{file_path}")
        except Exception as e:
            self.show_error(f"Failed to save file: {str(e)}")

    def export_video(self):
        if not self.video_loader or not self.video_loader.video_path or not self.processed_detections:
            self.show_error("Please load a video and detections, and wait for processing to finish.")
            return

        default_name = os.path.splitext(os.path.basename(self.video_loader.video_path))[0] + "_annotated.mp4"
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Annotated Video", default_name, "MP4 Video Files (*.mp4);;AVI Video Files (*.avi)")
        if not file_path: return

        self.toggle_controls(False)
        self.progress_bar.setValue(0); self.progress_bar.setFormat("Exporting video... %p%"); self.progress_bar.setTextVisible(True)
        
        self.video_saver = VideoSaver(
            source_video_path=self.video_loader.video_path,
            output_video_path=file_path,
            detections=self.processed_detections,
            grid_settings=self.grid_settings,
            grid_transform=self.grid_manager.transform,
            behavior_colors=self.behavior_colors,
            video_size=self.video_size,
            fps=self.video_loader.fps,
            line_thickness=self.line_thickness,
            selected_cells=self.selected_cells,
            timeline_segments=self.timeline_widget.timeline_segments,
            parent=self
        )
        self.video_saver.progress_updated.connect(self.progress_bar.setValue)
        self.video_saver.finished.connect(self.on_video_export_finished)
        self.video_saver.error_occurred.connect(self.on_video_export_error)
        self.video_saver.start()

    def on_video_export_finished(self):
        self.toggle_controls(True)
        self.progress_bar.setFormat(""); self.progress_bar.setTextVisible(False)
        QtWidgets.QMessageBox.information(self, "Success", "Video has been exported successfully.")
        self.progress_bar.setValue(0)
        self.video_saver.deleteLater(); self.video_saver = None

    def on_video_export_error(self, message):
        self.toggle_controls(True)
        self.progress_bar.setFormat(""); self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)
        self.show_error(f"Video export failed: {message}")
        if self.video_saver:
            self.video_saver.deleteLater(); self.video_saver = None

    # --- Settings Management Slots ---
    
    def save_settings(self):
        settings_data = {
            'grid_settings': self.grid_settings,
            'line_thickness': self.line_thickness,
            'grid_transform': {
                'center_x': self.grid_manager.center.x(),
                'center_y': self.grid_manager.center.y(),
                'angle': self.grid_manager.angle,
                'scale_x': self.grid_manager.scale_x,
                'scale_y': self.grid_manager.scale_y,
            }
        }
        
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Environment Settings", "settings.json", "JSON Files (*.json)")
        if not file_path: return
            
        try:
            with open(file_path, 'w') as f:
                json.dump(settings_data, f, indent=4)
            QtWidgets.QMessageBox.information(self, "Success", f"Settings saved to {file_path}")
        except Exception as e:
            self.show_error(f"Failed to save settings: {e}")

    def load_settings(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load Environment Settings", "", "JSON Files (*.json)")
        if not file_path: return
            
        try:
            with open(file_path, 'r') as f:
                settings_data = json.load(f)

            self.grid_settings = settings_data['grid_settings']
            self.line_thickness = settings_data['line_thickness']
            
            transform_settings = settings_data['grid_transform']
            self.grid_manager.update_center(QPointF(transform_settings['center_x'], transform_settings['center_y']))
            self.grid_manager.update_rotation(transform_settings['angle'])
            self.grid_manager.update_scale(transform_settings['scale_x'], transform_settings['scale_y'])
            
            self._block_signals_for_controls(True)
            self.grid_cols_spin.setValue(self.grid_settings['cols'])
            self.grid_rows_spin.setValue(self.grid_settings['rows'])
            self.line_thickness_spin.setValue(self.line_thickness)
            self.rotate_slider.setValue(int(self.grid_manager.angle))
            self.scale_x_slider.setValue(int(self.grid_manager.scale_x * 100))
            self.scale_y_slider.setValue(int(self.grid_manager.scale_y * 100))
            self.move_x_slider.setValue(int((self.grid_manager.center.x() - 0.5) * 200))
            self.move_y_slider.setValue(int((self.grid_manager.center.y() - 0.5) * 200))
            self._block_signals_for_controls(False)

            self.start_detection_processing()
            self.update_display()
            QtWidgets.QMessageBox.information(self, "Success", "Settings loaded successfully.")

        except Exception as e:
            self.show_error(f"Failed to load or apply settings: {e}")

    # --- Grid and Tank Control Slots ---
    
    def update_grid_settings(self):
        self.grid_settings = {'cols': self.grid_cols_spin.value(), 'rows': self.grid_rows_spin.value()}
        self.selected_cells.clear(); self.update_tank_selection_label()
        self.start_detection_processing()
        self.update_display()

    def update_line_thickness(self):
        self.line_thickness = self.line_thickness_spin.value()
        self.update_display()

    def update_grid_rotation(self, angle):
        self.grid_manager.update_rotation(angle)

    def update_grid_scale(self):
        scale_x = self.scale_x_slider.value() / 100.0
        scale_y = self.scale_y_slider.value() / 100.0
        self.grid_manager.update_scale(scale_x, scale_y)

    def update_grid_position(self):
        x_offset = self.move_x_slider.value() / 200.0
        y_offset = self.move_y_slider.value() / 200.0
        self.grid_manager.update_center(QPointF(0.5 + x_offset, 0.5 + y_offset))

    def reset_grid_transform_and_ui(self):
        self._block_signals_for_controls(True)
        self.rotate_slider.setValue(0)
        self.scale_x_slider.setValue(100)
        self.scale_y_slider.setValue(100)
        self.move_x_slider.setValue(0)
        self.move_y_slider.setValue(0)
        self._block_signals_for_controls(False)
        
        self.grid_manager.reset()
        self.start_detection_processing()
    
    def select_all_tanks(self):
        self.selected_cells = {str(i + 1) for i in range(self.grid_settings['rows'] * self.grid_settings['cols'])}
        self.update_tank_selection_label(); self.update_display()

    def clear_tank_selection(self):
        self.selected_cells.clear()
        self.update_tank_selection_label(); self.update_display()

    def update_tank_selection_label(self):
        text = "Selected Tanks: " + (', '.join(sorted(self.selected_cells, key=int)) if self.selected_cells else "None")
        self.tank_selection_label.setText(text)

    # --- Mouse Event Handlers ---
    
    def handle_mouse_press(self, event):
        if self.current_frame is None or self.video_size[0] == 0: return
        pos, pixmap = event.pos(), self.video_label.pixmap()
        if not pixmap: return
        
        label_size, pixmap_size = self.video_label.size(), pixmap.size()
        offset_x, offset_y = (label_size.width()-pixmap_size.width())//2, (label_size.height()-pixmap_size.height())//2
        if not (offset_x <= pos.x() < offset_x + pixmap_size.width() and 
                offset_y <= pos.y() < offset_y + pixmap_size.height()):
            return
        
        x = (pos.x() - offset_x) / pixmap_size.width()
        y = (pos.y() - offset_y) / pixmap_size.height()
        
        center_px_x = self.grid_manager.center.x() * pixmap_size.width()
        center_px_y = self.grid_manager.center.y() * pixmap_size.height()
        click_px_x = (pos.x() - offset_x)
        click_px_y = (pos.y() - offset_y)
        
        if ((click_px_x - center_px_x)**2 + (click_px_y - center_px_y)**2)**0.5 < 15:
             self.dragging_mode = "center"
        else:
             self.dragging_mode = "rotate"
        self.last_mouse_pos = QPointF(x, y)

    def handle_mouse_move(self, event):
        if self.dragging_mode is None or self.last_mouse_pos is None or not self.video_label.pixmap(): return
        
        pos, pixmap = event.pos(), self.video_label.pixmap()
        label_size, pixmap_size = self.video_label.size(), pixmap.size()
        offset_x, offset_y = (label_size.width() - pixmap_size.width())//2, (label_size.height() - pixmap_size.height())//2
        
        if not (offset_x <= pos.x() < offset_x + pixmap_size.width() and 
                offset_y <= pos.y() < offset_y + pixmap_size.height()):
            return
            
        x, y = (pos.x() - offset_x) / pixmap_size.width(), (pos.y() - offset_y) / pixmap_size.height()
        current_pos = QPointF(x, y)
        
        if self.dragging_mode == "center":
            self.grid_manager.update_center(current_pos)
            self.move_x_slider.blockSignals(True); self.move_y_slider.blockSignals(True)
            self.move_x_slider.setValue(int((current_pos.x() - 0.5) * 200))
            self.move_y_slider.setValue(int((current_pos.y() - 0.5) * 200))
            self.move_x_slider.blockSignals(False); self.move_y_slider.blockSignals(False)
        else:
            self.grid_manager.handle_mouse_drag_rotate(self.last_mouse_pos, current_pos)
            self.rotate_slider.blockSignals(True)
            self.rotate_slider.setValue(int(self.grid_manager.angle))
            self.rotate_slider.blockSignals(False)

        self.last_mouse_pos = current_pos

    def handle_mouse_release(self, event):
        if self.dragging_mode:
            self.start_detection_processing()
        self.dragging_mode = self.last_mouse_pos = None

    # --- Utility and Helper Methods ---
    
    def _block_signals_for_controls(self, should_block):
        """Helper to block/unblock signals for all transform-related controls."""
        widgets = [self.grid_cols_spin, self.grid_rows_spin, self.line_thickness_spin,
                   self.rotate_slider, self.scale_x_slider, self.scale_y_slider,
                   self.move_x_slider, self.move_y_slider, self.reset_grid_btn]
        for widget in widgets:
            widget.blockSignals(should_block)

    def _update_button_states(self):
        video_loaded = self.total_frames > 0
        csv_loaded = bool(self.raw_detections)
        is_processing = self.detection_processor is not None and self.detection_processor.isRunning()
        
        can_save = video_loaded and csv_loaded and not is_processing
        self.save_csv_btn.setEnabled(can_save)
        self.export_video_btn.setEnabled(can_save)
        self.save_settings_btn.setEnabled(True)

        self.load_video_btn.setEnabled(not is_processing)
        self.load_csv_btn.setEnabled(not is_processing)
        
        self.toggle_controls(not is_processing)

    def toggle_controls(self, enabled):
        is_processing = self.detection_processor is not None and self.detection_processor.isRunning()
        final_state = enabled and not is_processing
        
        self.play_btn.setEnabled(final_state)
        self.pause_btn.setEnabled(final_state)
        self.stop_btn.setEnabled(final_state)
        self.frame_slider.setEnabled(final_state and self.total_frames > 0)

    def show_error(self, message):
        QtWidgets.QMessageBox.critical(self, "Error", message)

    def closeEvent(self, event):
        if self.video_loader: self.video_loader.stop()
        if self.video_saver: self.video_saver.stop()
        if self.detection_processor: self.detection_processor.stop()
        if self.video_loader: self.video_loader.wait()
        if self.video_saver: self.video_saver.wait()
        if self.detection_processor: self.detection_processor.wait()
        event.accept()