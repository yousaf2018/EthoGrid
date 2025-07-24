# EthoGrid_App/workers/video_saver.py

import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal, QPointF

class VideoSaver(QThread):
    """
    Renders and saves the annotated video in a background thread.
    Draws detections, grid, legend, and timeline on each frame.
    """
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
            
        legend_x_start = original_video_width + 20
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

    def _draw_timeline_on_frame(self, frame, frame_idx, total_frames, original_video_height):
        """Draws the multi-tank timeline in a dedicated area below the video frame."""
        new_h, new_w, _ = frame.shape
        num_tanks = self.grid_settings['cols'] * self.grid_settings['rows']
        
        timeline_area_start_y = original_video_height
        
        if new_h <= timeline_area_start_y or num_tanks == 0 or total_frames <= 1:
            return

        cv2.rectangle(frame, (0, timeline_area_start_y), (new_w, new_h), (10, 10, 10), -1)

        padding_x, padding_y = 40, 20
        draw_area_x, draw_area_y = padding_x, timeline_area_start_y + (padding_y // 2)
        draw_area_w, draw_area_h = new_w - (2 * padding_x), (new_h - timeline_area_start_y) - padding_y

        if draw_area_h <= 0 or draw_area_w <= 0: return

        bar_h_total = draw_area_h / num_tanks
        bar_h_visible = bar_h_total * 0.8

        for i in range(num_tanks):
            tank_id = i + 1
            y_pos = draw_area_y + i * bar_h_total
            
            cv2.rectangle(frame, (draw_area_x, int(y_pos)), (draw_area_x + draw_area_w, int(y_pos + bar_h_visible)), (74, 74, 74), -1)

            if tank_id in self.timeline_segments:
                for start_f, end_f, behavior in self.timeline_segments[tank_id]:
                    color_rgb = self.behavior_colors.get(behavior, (100, 100, 100))
                    color_bgr = color_rgb[::-1]
                    x_start = int(draw_area_x + (start_f / total_frames) * draw_area_w)
                    x_end = int(draw_area_x + ((end_f + 1) / total_frames) * draw_area_w)
                    cv2.rectangle(frame, (x_start, int(y_pos)), (x_end, int(y_pos + bar_h_visible)), color_bgr, -1)

            label_y = int(y_pos + bar_h_visible / 2 + 5)
            cv2.putText(frame, f"T{tank_id}", (draw_area_x - 35, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (224, 224, 224), 1, cv2.LINE_AA)

        indicator_x = int(draw_area_x + (frame_idx / total_frames) * draw_area_w)
        cv2.line(frame, (indicator_x, draw_area_y), (indicator_x, draw_area_y + draw_area_h), (80, 80, 255), 2)

    def run(self):
        cap = cv2.VideoCapture(self.source_path)
        if not cap.isOpened():
            self.error_occurred.emit(f"Could not open source video: {self.source_path}")
            return

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        original_w, original_h = self.video_size
        legend_width = 250
        num_tanks = self.grid_settings['cols'] * self.grid_settings['rows']
        timeline_h = (num_tanks * 15) + 40 if num_tanks > 0 else 0
        new_w, new_h = original_w + legend_width, original_h + timeline_h
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
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

            new_frame = np.zeros((new_h, new_w, 3), dtype=np.uint8)
            new_frame[0:original_h, 0:original_w] = original_frame
            
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
            
            self._draw_legend_on_frame(new_frame, original_w)
            self._draw_timeline_on_frame(new_frame, frame_idx, total_frames, original_h)
            
            writer.write(new_frame)
            progress = int((frame_idx + 1) * 100 / total_frames)
            self.progress_updated.emit(progress)
            
        cap.release()
        writer.release()
        if self.is_running:
            self.finished.emit()