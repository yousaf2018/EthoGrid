import sys
import os
import cv2
import csv
import json # Used for saving/loading settings
import numpy as np
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QTimer, QPointF
from PyQt5.QtGui import QTransform, QImage, QPixmap

# Set HighDPI scaling before creating QApplication
QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

class VideoLoader(QThread):
    video_loaded = pyqtSignal(int, int, float)  # width, height, fps
    frame_loaded = pyqtSignal(int, np.ndarray)  # frame index, frame
    error_occurred = pyqtSignal(str)

    def __init__(self, video_path):
        super().__init__()
        self.video_path = video_path
        self.running = True
        self.mutex = QMutex()
        self.cap = None
        self.total_frames = 0
        self.current_frame_idx = 0
        self.seek_requested = False
        self.seek_frame = 0
        self.playing = False
        self.fps = 30.0

    def run(self):
        self.mutex.lock()
        try:
            self.cap = cv2.VideoCapture(self.video_path)
            if not self.cap.isOpened():
                self.error_occurred.emit("Failed to open video file")
                return

            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
            if self.fps == 0: self.fps = 30.0
            self.video_loaded.emit(width, height, self.fps)
        except Exception as e:
            self.error_occurred.emit(f"Video loading error: {str(e)}")
        finally:
            self.mutex.unlock()

        frame_duration_ms = int(1000 / self.fps if self.fps > 0 else 33)
        while self.running:
            self.mutex.lock()
            try:
                if self.seek_requested:
                    self.current_frame_idx = self.seek_frame
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame_idx)
                    self.seek_requested = False
                    ret, frame = self.cap.read()
                    if ret:
                        self.frame_loaded.emit(self.current_frame_idx, frame.copy())
                        if self.playing: self.current_frame_idx += 1
                
                elif self.playing:
                    if self.current_frame_idx >= self.total_frames:
                        self.playing = False
                        self.mutex.unlock()
                        continue
                    
                    ret, frame = self.cap.read()
                    if not ret:
                        self.playing = False
                        self.mutex.unlock()
                        continue

                    self.frame_loaded.emit(self.current_frame_idx, frame.copy())
                    self.current_frame_idx += 1
            except Exception as e:
                self.error_occurred.emit(f"Frame loading error: {str(e)}")
            finally:
                self.mutex.unlock()
            
            if self.playing:
                self.msleep(frame_duration_ms)
            else:
                self.msleep(20)

    def seek(self, frame_idx):
        self.mutex.lock()
        self.seek_requested = True
        self.seek_frame = frame_idx
        self.mutex.unlock()

    def set_playing(self, playing_state):
        self.mutex.lock()
        self.playing = playing_state
        if playing_state:
            if self.current_frame_idx >= self.total_frames -1:
                self.seek_requested = True
                self.seek_frame = 0
        self.mutex.unlock()

    def stop(self):
        self.mutex.lock()
        self.running = False
        if self.cap and self.cap.isOpened():
            self.cap.release()
        self.mutex.unlock()
        self.wait()

class VideoSaver(QThread):
    progress_updated = pyqtSignal(int)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, source_video_path, output_video_path, detections, 
                 grid_settings, grid_transform, behavior_colors, 
                 video_size, fps, line_thickness, selected_cells, 
                 timeline_segments, parent=None):
        super().__init__(parent)
        self.source_path = source_video_path
        self.output_path = output_video_path
        self.detections = detections
        self.grid_settings = grid_settings
        self.grid_transform = grid_transform
        self.behavior_colors = behavior_colors
        self.video_size = video_size
        self.fps = fps
        self.line_thickness = line_thickness
        self.selected_cells = selected_cells
        self.timeline_segments = timeline_segments
        self.is_running = True

    def stop(self):
        self.is_running = False

    def _draw_legend_on_frame(self, frame, original_video_width):
        """Draws the behavior color legend on the right side of the frame."""
        if not self.behavior_colors:
            return
            
        legend_x_start = original_video_width + 20  # Start drawing in the new blank area
        legend_y_start = 20
        box_size = 20
        y_offset = 0
        
        for behavior, color_rgb in self.behavior_colors.items():
            y_pos = legend_y_start + y_offset
            color_bgr = color_rgb[::-1]
            cv2.rectangle(frame, (legend_x_start, y_pos), (legend_x_start + box_size, y_pos + box_size), color_bgr, -1)
            cv2.putText(frame, behavior, (legend_x_start + box_size + 10, y_pos + box_size - 4), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (240, 240, 240), 1, cv2.LINE_AA)
            y_offset += box_size + 5

    # --- MODIFIED: The _draw_timeline_on_frame method is updated to draw below the video ---
    def _draw_timeline_on_frame(self, frame, frame_idx, total_frames, original_video_height):
        """Draws the multi-tank timeline in a dedicated area below the video frame."""
        new_h, new_w, _ = frame.shape
        num_tanks = self.grid_settings['cols'] * self.grid_settings['rows']
        
        timeline_area_start_y = original_video_height
        
        # Exit if there's no dedicated timeline area or no data to draw
        if new_h <= timeline_area_start_y or num_tanks == 0 or total_frames <= 1:
            return

        # Draw a solid background for the entire timeline panel
        cv2.rectangle(frame, (0, timeline_area_start_y), (new_w, new_h), (10, 10, 10), -1)

        # Define the main drawing area within the panel, adding padding
        padding_x = 40
        padding_y = 20
        draw_area_x = padding_x
        draw_area_y = timeline_area_start_y + (padding_y // 2)
        draw_area_w = new_w - (2 * padding_x)
        draw_area_h = (new_h - timeline_area_start_y) - padding_y

        if draw_area_h <= 0 or draw_area_w <= 0: return # Not enough space to draw

        bar_h_total = draw_area_h / num_tanks
        bar_h_visible = bar_h_total * 0.8  # The colored bar is 80% of the allocated space for the row

        for i in range(num_tanks):
            tank_id = i + 1
            # Calculate the top-left y-coordinate for this tank's timeline row
            y_pos = draw_area_y + i * bar_h_total
            
            # Draw the gray background bar for the entire timeline duration
            cv2.rectangle(frame, (draw_area_x, int(y_pos)), (draw_area_x + draw_area_w, int(y_pos + bar_h_visible)), (74, 74, 74), -1)

            # Draw colored segments for recorded behaviors
            if tank_id in self.timeline_segments:
                for start_f, end_f, behavior in self.timeline_segments[tank_id]:
                    color_rgb = self.behavior_colors.get(behavior, (100, 100, 100))
                    color_bgr = color_rgb[::-1]
                    # Map frame numbers to x-coordinates
                    x_start = int(draw_area_x + (start_f / total_frames) * draw_area_w)
                    x_end = int(draw_area_x + ((end_f + 1) / total_frames) * draw_area_w)
                    cv2.rectangle(frame, (x_start, int(y_pos)), (x_end, int(y_pos + bar_h_visible)), color_bgr, -1)

            # Draw the tank label (e.g., "T1") to the left of the bar
            label_y = int(y_pos + bar_h_visible / 2 + 5) # Vertically center the text
            cv2.putText(frame, f"T{tank_id}", (draw_area_x - 35, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (224, 224, 224), 1, cv2.LINE_AA)

        # Draw the red vertical line indicating the current frame
        indicator_x = int(draw_area_x + (frame_idx / total_frames) * draw_area_w)
        cv2.line(frame, (indicator_x, draw_area_y), (indicator_x, draw_area_y + draw_area_h), (80, 80, 255), 2)


    def run(self):
        cap = cv2.VideoCapture(self.source_path)
        if not cap.isOpened():
            self.error_occurred.emit(f"Could not open source video: {self.source_path}")
            return

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # --- MODIFIED: Define new video dimensions for legend AND timeline ---
        original_w, original_h = self.video_size
        legend_width = 250
        
        # Calculate timeline height dynamically based on the number of tanks.
        num_tanks = self.grid_settings['cols'] * self.grid_settings['rows']
        timeline_h = (num_tanks * 15) + 40 if num_tanks > 0 else 0 # 15px per tank + 40px padding

        new_w = original_w + legend_width
        new_h = original_h + timeline_h # Increase height for the timeline area
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        # Initialize writer with the new, taller and wider dimensions
        writer = cv2.VideoWriter(self.output_path, fourcc, self.fps, (new_w, new_h))

        if not writer.isOpened():
            self.error_occurred.emit(f"Could not open video writer for: {self.output_path}")
            cap.release()
            return
            
        def transform_point(x, y):
            p = self.grid_transform.map(QPointF(x, y))
            return int(p.x()), int(p.y())

        for frame_idx in range(total_frames):
            if not self.is_running: break
            ret, original_frame = cap.read()
            if not ret: break

            # --- MODIFIED: Create a new, larger canvas for video, legend, and timeline ---
            new_frame = np.zeros((new_h, new_w, 3), dtype=np.uint8)
            # Copy the original video frame to the top-left corner
            new_frame[0:original_h, 0:original_w] = original_frame
            
            # All drawing from now on happens on the `new_frame`
            # The grid coordinates are absolute, so they draw correctly on the left part
            for i in range(self.grid_settings['cols'] + 1):
                cv2.line(new_frame, transform_point(original_w*i/self.grid_settings['cols'],0), transform_point(original_w*i/self.grid_settings['cols'],original_h), (0,255,0), self.line_thickness)
            for i in range(self.grid_settings['rows'] + 1):
                cv2.line(new_frame, transform_point(0,original_h*i/self.grid_settings['rows']), transform_point(original_w,original_h*i/self.grid_settings['rows']), (0,255,0), self.line_thickness)
            
            if frame_idx in self.detections:
                for det in self.detections[frame_idx]:
                    tank_number = det.get('tank_number')
                    if tank_number is not None and (not self.selected_cells or str(tank_number) in self.selected_cells):
                        x1, y1, x2, y2 = map(int, (det["x1"], det["y1"], det["x2"], det["y2"]))
                        behavior = det["class_name"]
                        color_rgb = self.behavior_colors.get(behavior, (255, 255, 255))
                        color_bgr = color_rgb[::-1]
                        
                        label = f"{tank_number}"
                        cv2.rectangle(new_frame, (x1, y1), (x2, y2), color_bgr, 2)
                        font_face, font_scale, font_thickness = cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2
                        (tw, th), _ = cv2.getTextSize(label, font_face, font_scale, font_thickness)
                        cv2.rectangle(new_frame, (x1, y1 - th - 12), (x1 + tw, y1), color_bgr, -1)
                        cv2.putText(new_frame, label, (x1, y1 - 7), font_face, font_scale, (0,0,0), font_thickness, cv2.LINE_AA)
            
            # Draw the legend (right) and timeline (bottom) on the new, composed frame
            self._draw_legend_on_frame(new_frame, original_w)
            # --- MODIFIED: Pass the original video height to the timeline drawing function ---
            self._draw_timeline_on_frame(new_frame, frame_idx, total_frames, original_h)
            
            # Write the final composed frame to the video file
            writer.write(new_frame)
            progress = int((frame_idx + 1) * 100 / total_frames)
            self.progress_updated.emit(progress)
            
        cap.release()
        writer.release()
        if self.is_running:
            self.finished.emit()

class TimelineWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)
        self.timeline_segments = {}
        self.behavior_colors = {}
        self.total_frames = 0
        self.current_frame = 0
        self.num_tanks = 0

    def setData(self, timeline_segments, behavior_colors, total_frames, num_tanks):
        self.timeline_segments = timeline_segments
        self.behavior_colors = behavior_colors
        self.total_frames = total_frames
        self.num_tanks = num_tanks
        if self.num_tanks > 0:
            self.setMinimumHeight(max(40, self.num_tanks * 12 + 20))
            self.setMaximumHeight(self.num_tanks * 12 + 20)
        else:
            self.setMinimumHeight(0)
        self.update()

    def setCurrentFrame(self, frame_idx):
        if self.current_frame != frame_idx:
            self.current_frame = frame_idx
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.total_frames <= 1 or self.num_tanks == 0: return

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = self.rect().adjusted(30, 10, -10, -10)
        if not rect.isValid(): return

        bar_height_total = rect.height() / self.num_tanks
        bar_height_visible = bar_height_total * 0.8

        for i in range(self.num_tanks):
            tank_id = i + 1
            y_pos = rect.top() + i * bar_height_total
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QBrush(QtGui.QColor("#4a4a4a")))
            painter.drawRect(QtCore.QRectF(rect.left(), y_pos, rect.width(), bar_height_visible))
            if tank_id in self.timeline_segments:
                for start_frame, end_frame, behavior in self.timeline_segments[tank_id]:
                    color_tuple = self.behavior_colors.get(behavior, (100, 100, 100))
                    color = QtGui.QColor(*color_tuple)
                    x_start = rect.left() + (start_frame / self.total_frames) * rect.width()
                    x_end = rect.left() + ((end_frame + 1) / self.total_frames) * rect.width()
                    segment_width = max(1.0, x_end - x_start)
                    painter.setBrush(QtGui.QBrush(color))
                    painter.drawRect(QtCore.QRectF(x_start, y_pos, segment_width, bar_height_visible))
            painter.setPen(QtGui.QColor("#e0e0e0"))
            font = painter.font()
            font.setPointSize(7)
            painter.setFont(font)
            label_rect = QtCore.QRectF(rect.left() - 25, y_pos, 20, bar_height_visible)
            painter.drawText(label_rect, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight, f"T{tank_id}")
        
        if self.total_frames > 0:
            indicator_x = rect.left() + (self.current_frame / self.total_frames) * rect.width()
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 80, 80, 220), 2))
            painter.drawLine(QtCore.QPointF(indicator_x, rect.top()), QtCore.QPointF(indicator_x, rect.bottom()))

class DetectionProcessor(QThread):
    processing_finished = pyqtSignal(dict, dict)  # detections, timeline_segments
    error_occurred = pyqtSignal(str)

    def __init__(self, detections, grid_transform, grid_settings, video_size, parent=None):
        super().__init__(parent)
        self.detections = detections
        self.grid_transform = grid_transform
        self.grid_settings = grid_settings
        self.video_size = video_size
        self._is_running = True

    def stop(self):
        self._is_running = False

    def _get_tank_for_point(self, x, y, w, h, cols, rows, inverse_transform):
        transformed_point = inverse_transform.map(QPointF(x, y))
        tx, ty = transformed_point.x(), transformed_point.y()
        if not (0 <= tx < w and 0 <= ty < h): return None
        cell_width, cell_height = w / cols, h / rows
        col = min(cols - 1, max(0, int(tx / cell_width)))
        row = min(rows - 1, max(0, int(ty / cell_height)))
        return row * cols + col + 1

    def run(self):
        try:
            w, h = self.video_size
            cols, rows = self.grid_settings['cols'], self.grid_settings['rows']
            inverse_transform, invertible = self.grid_transform.inverted()
            if not invertible:
                self.error_occurred.emit("Grid transform is not invertible. Cannot process detections.")
                return

            tank_data_for_timeline = {}
            for frame_idx, dets in self.detections.items():
                if not self._is_running: return
                for det in dets:
                    cx = (float(det["x1"]) + float(det["x2"])) / 2
                    cy = (float(det["y1"]) + float(det["y2"])) / 2
                    tank_number = self._get_tank_for_point(cx, cy, w, h, cols, rows, inverse_transform)
                    det['tank_number'] = tank_number
                    if tank_number is not None:
                        tank_data_for_timeline.setdefault(tank_number, {})[frame_idx] = det["class_name"]

            timeline_segments = {}
            for tank_id, frames in tank_data_for_timeline.items():
                if not self._is_running: return
                if not frames: continue
                segments = []
                sorted_frames = sorted(frames.keys())
                start_frame = sorted_frames[0]
                current_behavior = frames[start_frame]
                for i in range(1, len(sorted_frames)):
                    frame = sorted_frames[i]
                    prev_frame = sorted_frames[i-1]
                    behavior = frames[frame]
                    if behavior != current_behavior or frame != prev_frame + 1:
                        segments.append((start_frame, prev_frame, current_behavior))
                        start_frame = frame
                        current_behavior = behavior
                segments.append((start_frame, sorted_frames[-1], current_behavior))
                timeline_segments[tank_id] = segments
            
            if self._is_running:
                self.processing_finished.emit(self.detections, timeline_segments)
        except Exception as e:
            self.error_occurred.emit(f"Error during detection processing: {e}")

class VideoPlayer(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(VideoPlayer, self).__init__(parent)
        self.setWindowTitle("📊 Animal Behavior Analyzer Tool")
        
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
        self.grid_transform = QTransform()
        self.grid_center = QPointF(0.5, 0.5)
        self.grid_angle = 0
        self.grid_scale_x = 1.0
        self.grid_scale_y = 1.0
        self.dragging = None
        self.last_pos = None
        
        self.video_loader = None
        self.video_saver = None
        self.detection_processor = None
        
        self.timeline_widget = None
        self.legend_group_box = None # NEW: Placeholder for the legend widget

        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
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
        self.video_label = QtWidgets.QLabel()
        self.video_label.setObjectName("videoLabel")
        self.video_label.setAlignment(QtCore.Qt.AlignCenter)
        self.video_label.setMinimumSize(640, 360)
        
        # NEW: Create the legend GroupBox
        self.legend_group_box = QtWidgets.QGroupBox("Behavior Legend")
        self.legend_group_box.setFixedWidth(200)
        self.legend_layout = QtWidgets.QVBoxLayout()
        self.legend_layout.setAlignment(QtCore.Qt.AlignTop)
        self.legend_group_box.setLayout(self.legend_layout)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)

        grid_config_group = QtWidgets.QGroupBox("Tank Configuration")
        # ... (rest of grid config UI is unchanged)
        self.grid_cols_spin = QtWidgets.QSpinBox(); self.grid_cols_spin.setRange(1, 20); self.grid_cols_spin.setValue(5)
        self.grid_rows_spin = QtWidgets.QSpinBox(); self.grid_rows_spin.setRange(1, 20); self.grid_rows_spin.setValue(2)
        self.line_thickness_spin = QtWidgets.QSpinBox(); self.line_thickness_spin.setRange(1, 5); self.line_thickness_spin.setValue(2)
        self.reset_grid_btn = QtWidgets.QPushButton("Reset Grid")
        self.rotate_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.rotate_slider.setRange(-180, 180); self.rotate_slider.setValue(0)
        self.scale_x_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.scale_x_slider.setRange(10, 200); self.scale_x_slider.setValue(100)
        self.scale_y_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.scale_y_slider.setRange(10, 200); self.scale_y_slider.setValue(100)
        self.move_x_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.move_x_slider.setRange(-100, 100); self.move_x_slider.setValue(0)
        self.move_y_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.move_y_slider.setRange(-100, 100); self.move_y_slider.setValue(0)
        grid_config_layout = QtWidgets.QGridLayout()
        grid_config_layout.addWidget(QtWidgets.QLabel("Columns:"), 0, 0); grid_config_layout.addWidget(self.grid_cols_spin, 0, 1)
        grid_config_layout.addWidget(QtWidgets.QLabel("Rows:"), 1, 0); grid_config_layout.addWidget(self.grid_rows_spin, 1, 1)
        grid_config_layout.addWidget(QtWidgets.QLabel("Line Thickness:"), 2, 0); grid_config_layout.addWidget(self.line_thickness_spin, 2, 1)
        grid_config_layout.addWidget(QtWidgets.QLabel("Rotation:"), 3, 0); grid_config_layout.addWidget(self.rotate_slider, 3, 1)
        grid_config_layout.addWidget(QtWidgets.QLabel("Scale X:"), 4, 0); grid_config_layout.addWidget(self.scale_x_slider, 4, 1)
        grid_config_layout.addWidget(QtWidgets.QLabel("Scale Y:"), 5, 0); grid_config_layout.addWidget(self.scale_y_slider, 5, 1)
        grid_config_layout.addWidget(QtWidgets.QLabel("Move X:"), 6, 0); grid_config_layout.addWidget(self.move_x_slider, 6, 1)
        grid_config_layout.addWidget(QtWidgets.QLabel("Move Y:"), 7, 0); grid_config_layout.addWidget(self.move_y_slider, 7, 1)
        grid_config_layout.addWidget(self.reset_grid_btn, 8, 0, 1, 2)
        grid_config_group.setLayout(grid_config_layout)
        
        self.tank_selection_label = QtWidgets.QLabel("Selected Tanks: None")
        self.select_all_btn = QtWidgets.QPushButton("Select All")
        self.clear_selection_btn = QtWidgets.QPushButton("Clear Selection")
        self.play_btn = QtWidgets.QPushButton("▶ Play")
        self.pause_btn = QtWidgets.QPushButton("⏸ Pause")
        self.stop_btn = QtWidgets.QPushButton("⏹ Stop")
        self.frame_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.frame_slider.setEnabled(False)
        self.frame_label = QtWidgets.QLabel("Frame: 0/0")
        self.load_video_btn = QtWidgets.QPushButton("🎬 Load Video")
        self.load_csv_btn = QtWidgets.QPushButton("📄 Load Detections")
        self.save_csv_btn = QtWidgets.QPushButton("📝 Save w/ Tanks"); self.save_csv_btn.setEnabled(False)
        self.progress_bar = QtWidgets.QProgressBar(); self.progress_bar.setRange(0, 100); self.progress_bar.setTextVisible(False)
        self.export_video_btn = QtWidgets.QPushButton("📹 Export Video"); self.export_video_btn.setEnabled(False)
        self.save_settings_btn = QtWidgets.QPushButton("💾 Save Settings")
        self.load_settings_btn = QtWidgets.QPushButton("📂 Load Settings")
        
        self.timeline_widget = TimelineWidget(self)

        # CHANGE: Main content area is now a horizontal layout
        content_layout = QtWidgets.QHBoxLayout()
        
        video_and_controls_vbox = QtWidgets.QVBoxLayout()
        video_and_controls_vbox.addWidget(self.video_label, stretch=1) # Video takes most space
        video_and_controls_vbox.addWidget(self.status_label)
        
        content_layout.addLayout(video_and_controls_vbox, stretch=1)
        content_layout.addWidget(self.legend_group_box) # Add legend widget to the right

        controls_layout = QtWidgets.QHBoxLayout()
        controls_layout.addWidget(self.play_btn); controls_layout.addWidget(self.pause_btn); controls_layout.addWidget(self.stop_btn)
        controls_layout.addWidget(self.frame_slider); controls_layout.addWidget(self.frame_label)
        
        file_layout = QtWidgets.QHBoxLayout()
        file_layout.addWidget(self.load_video_btn); file_layout.addWidget(self.load_csv_btn)
        file_layout.addWidget(self.save_csv_btn); file_layout.addWidget(self.export_video_btn)
        
        settings_layout = QtWidgets.QHBoxLayout()
        settings_layout.addWidget(self.load_settings_btn)
        settings_layout.addWidget(self.save_settings_btn)
        settings_layout.addStretch()

        selection_layout = QtWidgets.QHBoxLayout()
        selection_layout.addWidget(self.tank_selection_label); selection_layout.addWidget(self.select_all_btn); selection_layout.addWidget(self.clear_selection_btn)
        
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addLayout(file_layout)
        main_layout.addLayout(content_layout) # Add the new content layout here
        main_layout.addLayout(settings_layout)
        main_layout.addWidget(grid_config_group)
        main_layout.addLayout(selection_layout)
        main_layout.addLayout(controls_layout)
        main_layout.addWidget(self.timeline_widget)
        main_layout.addWidget(self.progress_bar)
        self.setLayout(main_layout)
        self.setMinimumSize(1000, 750) # Increased min size to accommodate legend

    def setup_connections(self):
        self.play_btn.clicked.connect(self.start_playback)
        self.pause_btn.clicked.connect(self.pause_playback)
        self.stop_btn.clicked.connect(self.stop_playback)
        self.frame_slider.sliderMoved.connect(self.seek_frame)
        self.load_video_btn.clicked.connect(self.load_video)
        self.load_csv_btn.clicked.connect(self.load_detections)
        self.save_csv_btn.clicked.connect(self.save_detections_with_tanks)
        self.export_video_btn.clicked.connect(self.export_video)
        
        self.save_settings_btn.clicked.connect(self.save_settings)
        self.load_settings_btn.clicked.connect(self.load_settings)
        
        self.grid_cols_spin.valueChanged.connect(self.update_grid_settings)
        self.grid_rows_spin.valueChanged.connect(self.update_grid_settings)
        self.line_thickness_spin.valueChanged.connect(self.update_line_thickness)
        self.select_all_btn.clicked.connect(self.select_all_tanks)
        self.clear_selection_btn.clicked.connect(self.clear_tank_selection)
        self.reset_grid_btn.clicked.connect(self.reset_grid_transform)
        
        self.rotate_slider.valueChanged.connect(self.update_grid_rotation)
        self.scale_x_slider.valueChanged.connect(self.update_grid_scale_x)
        self.scale_y_slider.valueChanged.connect(self.update_grid_scale_y)
        self.move_x_slider.valueChanged.connect(self.update_grid_position)
        self.move_y_slider.valueChanged.connect(self.update_grid_position)
        self.rotate_slider.sliderReleased.connect(self.start_detection_processing)
        self.scale_x_slider.sliderReleased.connect(self.start_detection_processing)
        self.scale_y_slider.sliderReleased.connect(self.start_detection_processing)
        self.move_x_slider.sliderReleased.connect(self.start_detection_processing)
        self.move_y_slider.sliderReleased.connect(self.start_detection_processing)

        self.video_label.mousePressEvent = self.handle_mouse_press
        self.video_label.mouseMoveEvent = self.handle_mouse_move
        self.video_label.mouseReleaseEvent = self.handle_mouse_release
    
    def get_color_for_behavior(self, behavior_name):
        if behavior_name not in self.behavior_colors:
            color_index = len(self.behavior_colors) % len(self.predefined_colors)
            self.behavior_colors[behavior_name] = self.predefined_colors[color_index]
        return self.behavior_colors[behavior_name]

    # NEW: Method to dynamically update the UI legend widget
    def update_legend_widget(self):
        # Clear existing legend items
        while self.legend_layout.count():
            item = self.legend_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        # Re-populate with new items
        for behavior, color_rgb in self.behavior_colors.items():
            item_layout = QtWidgets.QHBoxLayout()
            
            color_label = QtWidgets.QLabel()
            color_label.setFixedSize(20, 20)
            color_label.setStyleSheet(f"background-color: rgb({color_rgb[0]}, {color_rgb[1]}, {color_rgb[2]}); border: 1px solid #5a5a5a;")
            
            text_label = QtWidgets.QLabel(behavior)
            
            item_layout.addWidget(color_label)
            item_layout.addWidget(text_label, stretch=1)
            self.legend_layout.addLayout(item_layout)

    def update_display(self):
        if self.current_frame is None: return
        try:
            frame = self.current_frame.copy()
            h, w, _ = frame.shape
            
            def transform_point(x, y):
                p = self.grid_transform.map(QPointF(x, y))
                return int(p.x()), int(p.y())
            for i in range(self.grid_settings['cols'] + 1):
                cv2.line(frame, transform_point(w*i/self.grid_settings['cols'],0), transform_point(w*i/self.grid_settings['cols'],h), (0,255,0), self.line_thickness)
            for i in range(self.grid_settings['rows'] + 1):
                cv2.line(frame, transform_point(0,h*i/self.grid_settings['rows']), transform_point(w,h*i/self.grid_settings['rows']), (0,255,0), self.line_thickness)
            cv2.circle(frame, (int(self.grid_center.x() * w), int(self.grid_center.y() * h)), 8, (0, 0, 255), -1)
            
            if self.current_frame_idx in self.processed_detections:
                for det in self.processed_detections[self.current_frame_idx]:
                    tank_number = det.get('tank_number')
                    if tank_number is not None and (not self.selected_cells or str(tank_number) in self.selected_cells):
                        x1, y1, x2, y2 = map(int, (det["x1"], det["y1"], det["x2"], det["y2"]))
                        behavior = det["class_name"]
                        color_rgb = self.behavior_colors.get(behavior, (128,128,128))
                        color_bgr = color_rgb[::-1]
                        
                        # CHANGE: Simplified label, only the number.
                        label = f"{tank_number}"
                        cv2.rectangle(frame, (x1, y1), (x2, y2), color_bgr, 2)
                        font_face, f_scale, f_thick = cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2
                        (t_w, t_h), _ = cv2.getTextSize(label, font_face, f_scale, f_thick)
                        cv2.rectangle(frame, (x1, y1 - t_h - 12), (x1 + t_w, y1), color_bgr, -1)
                        cv2.putText(frame, label, (x1, y1 - 7), font_face, f_scale, (0,0,0), f_thick, cv2.LINE_AA)

            # REMOVED: Legend is no longer drawn on the live preview frame
            
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            qimg = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg).scaled(self.video_label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            self.video_label.setPixmap(pixmap)
        except Exception as e:
            print(f"Error updating display: {e}")

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
        self.update_legend_widget() # Clear the legend UI
        if self.timeline_widget:
            self.timeline_widget.setData({}, {}, 0, 0)
        self._update_button_states()

    def _update_button_states(self):
        video_loaded = self.total_frames > 0
        csv_loaded = bool(self.raw_detections)
        processing = self.detection_processor is not None and self.detection_processor.isRunning()
        
        can_save = video_loaded and csv_loaded and not processing
        self.save_csv_btn.setEnabled(can_save)
        self.export_video_btn.setEnabled(can_save)
        self.save_settings_btn.setEnabled(True)

        self.load_video_btn.setEnabled(not processing)
        self.load_csv_btn.setEnabled(not processing)

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
        self._update_grid_transform_matrix()
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
                
                self.update_legend_widget() # NEW: Update the UI legend
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
            self.raw_detections, self.grid_transform, self.grid_settings, self.video_size
        )
        self.detection_processor.processing_finished.connect(self.on_processing_complete)
        self.detection_processor.error_occurred.connect(self.on_processing_error)
        
        self.detection_processor.finished.connect(self.detection_processor.deleteLater)
        self.detection_processor.finished.connect(self.on_processor_thread_finished)
        
        self.detection_processor.start()
        self._update_button_states()

    def on_processor_thread_finished(self):
        """Clears the reference to the detection processor to prevent runtime errors."""
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
            grid_transform=self.grid_transform,
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
        self.video_saver.deleteLater()
        self.video_saver = None

    def on_video_export_error(self, message):
        self.toggle_controls(True)
        self.progress_bar.setFormat(""); self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)
        self.show_error(f"Video export failed: {message}")
        if self.video_saver:
            self.video_saver.deleteLater()
            self.video_saver = None
    
    def toggle_controls(self, enabled):
        is_processing = self.detection_processor is not None and self.detection_processor.isRunning()
        final_state = enabled and not is_processing
        
        self.load_video_btn.setEnabled(final_state)
        self.load_csv_btn.setEnabled(final_state)
        self.play_btn.setEnabled(final_state)
        self.pause_btn.setEnabled(final_state)
        self.stop_btn.setEnabled(final_state)
        self.frame_slider.setEnabled(final_state and self.total_frames > 0)
        
        video_loaded = self.total_frames > 0
        csv_loaded = bool(self.raw_detections)
        can_save = video_loaded and csv_loaded and final_state
        self.save_csv_btn.setEnabled(can_save)
        self.export_video_btn.setEnabled(can_save)

    def save_settings(self):
        """Saves the current grid and transform settings to a JSON file."""
        settings_data = {
            'grid_settings': self.grid_settings,
            'line_thickness': self.line_thickness,
            'grid_transform': {
                'center_x': self.grid_center.x(),
                'center_y': self.grid_center.y(),
                'angle': self.grid_angle,
                'scale_x': self.grid_scale_x,
                'scale_y': self.grid_scale_y,
            }
        }
        
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Environment Settings", "settings.json", "JSON Files (*.json)")
        if not file_path:
            return
            
        try:
            with open(file_path, 'w') as f:
                json.dump(settings_data, f, indent=4)
            QtWidgets.QMessageBox.information(self, "Success", f"Settings saved to {file_path}")
        except Exception as e:
            self.show_error(f"Failed to save settings: {e}")

    def load_settings(self):
        """Loads grid and transform settings from a JSON file and applies them."""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load Environment Settings", "", "JSON Files (*.json)")
        if not file_path:
            return
            
        try:
            with open(file_path, 'r') as f:
                settings_data = json.load(f)

            for widget in [self.grid_cols_spin, self.grid_rows_spin, self.line_thickness_spin,
                           self.rotate_slider, self.scale_x_slider, self.scale_y_slider,
                           self.move_x_slider, self.move_y_slider]:
                widget.blockSignals(True)

            self.grid_settings = settings_data['grid_settings']
            self.line_thickness = settings_data['line_thickness']
            
            transform_settings = settings_data['grid_transform']
            self.grid_center = QPointF(transform_settings['center_x'], transform_settings['center_y'])
            self.grid_angle = transform_settings['angle']
            self.grid_scale_x = transform_settings['scale_x']
            self.grid_scale_y = transform_settings['scale_y']
            
            self.grid_cols_spin.setValue(self.grid_settings['cols'])
            self.grid_rows_spin.setValue(self.grid_settings['rows'])
            self.line_thickness_spin.setValue(self.line_thickness)
            self.rotate_slider.setValue(int(self.grid_angle))
            self.scale_x_slider.setValue(int(self.grid_scale_x * 100))
            self.scale_y_slider.setValue(int(self.grid_scale_y * 100))
            self.move_x_slider.setValue(int((self.grid_center.x() - 0.5) * 200))
            self.move_y_slider.setValue(int((self.grid_center.y() - 0.5) * 200))

            for widget in [self.grid_cols_spin, self.grid_rows_spin, self.line_thickness_spin,
                           self.rotate_slider, self.scale_x_slider, self.scale_y_slider,
                           self.move_x_slider, self.move_y_slider]:
                widget.blockSignals(False)

            self._update_grid_transform_matrix()
            self.start_detection_processing()
            self.update_display()
            QtWidgets.QMessageBox.information(self, "Success", "Settings loaded successfully.")

        except Exception as e:
            self.show_error(f"Failed to load or apply settings: {e}")

    def update_grid_settings(self):
        self.grid_settings = {'cols': self.grid_cols_spin.value(), 'rows': self.grid_rows_spin.value()}
        self.selected_cells.clear(); self.update_tank_selection_label()
        self.start_detection_processing()
        self.update_display()

    def update_line_thickness(self):
        self.line_thickness = self.line_thickness_spin.value()
        self.update_display()

    def update_grid_rotation(self, angle):
        self.grid_angle = angle
        self._update_grid_transform_matrix()
        self.update_display()

    def update_grid_scale_x(self):
        self.grid_scale_x = self.scale_x_slider.value() / 100.0
        self._update_grid_transform_matrix()
        self.update_display()

    def update_grid_scale_y(self):
        self.grid_scale_y = self.scale_y_slider.value() / 100.0
        self._update_grid_transform_matrix()
        self.update_display()

    def update_grid_position(self):
        x_offset = self.move_x_slider.value() / 200.0
        y_offset = self.move_y_slider.value() / 200.0
        self.grid_center = QPointF(0.5 + x_offset, 0.5 + y_offset)
        self._update_grid_transform_matrix()
        self.update_display()

    def reset_grid_transform(self):
        for widget in [self.rotate_slider, self.scale_x_slider, self.scale_y_slider, self.move_x_slider, self.move_y_slider]:
            widget.blockSignals(True)
            
        self.grid_center = QPointF(0.5, 0.5); self.grid_angle = 0
        self.grid_scale_x, self.grid_scale_y = 1.0, 1.0
        self.rotate_slider.setValue(0); self.scale_x_slider.setValue(100)
        self.scale_y_slider.setValue(100); self.move_x_slider.setValue(0); self.move_y_slider.setValue(0)
        
        for widget in [self.rotate_slider, self.scale_x_slider, self.scale_y_slider, self.move_x_slider, self.move_y_slider]:
            widget.blockSignals(False)

        self._update_grid_transform_matrix()
        self.start_detection_processing()
        self.update_display()

    def _update_grid_transform_matrix(self):
        self.grid_transform.reset()
        if self.video_size[0] > 0:
            w, h = self.video_size
            center_x, center_y = self.grid_center.x() * w, self.grid_center.y() * h
            self.grid_transform.translate(center_x, center_y)
            self.grid_transform.rotate(self.grid_angle)
            self.grid_transform.scale(self.grid_scale_x, self.grid_scale_y)
            self.grid_transform.translate(-w/2, -h/2)


    def select_all_tanks(self):
        self.selected_cells = {str(i + 1) for i in range(self.grid_settings['rows'] * self.grid_settings['cols'])}
        self.update_tank_selection_label(); self.update_display()

    def clear_tank_selection(self):
        self.selected_cells.clear()
        self.update_tank_selection_label(); self.update_display()

    def update_tank_selection_label(self):
        text = "Selected Tanks: " + (', '.join(sorted(self.selected_cells, key=int)) if self.selected_cells else "None")
        self.tank_selection_label.setText(text)

    def handle_mouse_press(self, event):
        if self.current_frame is None or self.video_size[0] == 0: return
        pos, pixmap = event.pos(), self.video_label.pixmap()
        if not pixmap: return
        label_size, pixmap_size = self.video_label.size(), pixmap.size()
        offset_x, offset_y = (label_size.width()-pixmap_size.width())//2, (label_size.height()-pixmap_size.height())//2
        if (offset_x <= pos.x() < offset_x + pixmap_size.width() and offset_y <= pos.y() < offset_y + pixmap_size.height()):
            x = (pos.x() - offset_x) / pixmap_size.width()
            y = (pos.y() - offset_y) / pixmap_size.height()
            
            center_px_x = self.grid_center.x() * pixmap_size.width()
            center_px_y = self.grid_center.y() * pixmap_size.height()
            click_px_x = (pos.x() - offset_x)
            click_px_y = (pos.y() - offset_y)
            
            if ((click_px_x - center_px_x)**2 + (click_px_y - center_px_y)**2)**0.5 < 15:
                 self.dragging = "center"
            else:
                 self.dragging = "rotate"
            self.last_pos = QPointF(x, y)

    def handle_mouse_move(self, event):
        if self.dragging is None or self.last_pos is None or not self.video_label.pixmap(): return
        pos, pixmap = event.pos(), self.video_label.pixmap()
        label_size, pixmap_size = self.video_label.size(), pixmap.size()
        offset_x, offset_y = (label_size.width() - pixmap_size.width())//2, (label_size.height() - pixmap_size.height())//2
        if (offset_x <= pos.x() < offset_x + pixmap_size.width() and offset_y <= pos.y() < offset_y + pixmap_size.height()):
            x, y = (pos.x() - offset_x) / pixmap_size.width(), (pos.y() - offset_y) / pixmap_size.height()
            current_pos = QPointF(x, y)
            
            if self.dragging == "center":
                self.grid_center = current_pos
                self.move_x_slider.blockSignals(True)
                self.move_y_slider.blockSignals(True)
                self.move_x_slider.setValue(int((current_pos.x() - 0.5) * 200))
                self.move_y_slider.setValue(int((current_pos.y() - 0.5) * 200))
                self.move_x_slider.blockSignals(False)
                self.move_y_slider.blockSignals(False)
            else:
                center_x, center_y = self.grid_center.x() * self.video_size[0], self.grid_center.y() * self.video_size[1]
                vec_prev = QPointF(self.last_pos.x() * self.video_size[0] - center_x, self.last_pos.y() * self.video_size[1] - center_y)
                vec_curr = QPointF(x * self.video_size[0] - center_x, y * self.video_size[1] - center_y)
                angle_change = np.degrees(np.arctan2(vec_curr.y(), vec_curr.x()) - np.arctan2(vec_prev.y(), vec_prev.x()))
                self.grid_angle = (self.grid_angle + angle_change + 180) % 360 - 180
                self.rotate_slider.blockSignals(True)
                self.rotate_slider.setValue(int(self.grid_angle))
                self.rotate_slider.blockSignals(False)

            self._update_grid_transform_matrix()
            self.update_display()
            self.last_pos = current_pos

    def handle_mouse_release(self, event):
        if self.dragging:
            self.start_detection_processing()
        self.dragging = self.last_pos = None

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

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    player = VideoPlayer()
    player.show()
    sys.exit(app.exec_())