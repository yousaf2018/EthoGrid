# EthoGrid_App/workers/video_saver.py

import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal, QPointF

class VideoSaver(QThread):
    progress_updated = pyqtSignal(int)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, source_video_path, output_video_path, detections, 
                 grid_settings, grid_transform, behavior_colors, 
                 video_size, fps, line_thickness, selected_cells, 
                 timeline_segments, draw_grid=False, draw_overlays=True, parent=None):
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
        self.draw_grid = draw_grid
        self.draw_overlays = draw_overlays
        self.is_running = True

        original_w, original_h = self.video_size
        if self.draw_overlays:
            legend_width = 250
            num_tanks = self.grid_settings['cols'] * self.grid_settings['rows']
            timeline_h = (num_tanks * 15) + 40 if num_tanks > 0 else 0
            self.final_video_size = (original_w + legend_width, original_h + timeline_h)
        else:
            self.final_video_size = self.video_size

    def stop(self):
        self.is_running = False

    def _draw_legend_on_frame(self, frame, original_video_width):
        if not self.behavior_colors: return
        legend_x_start = original_video_width + 20; y_offset = 0
        for behavior, color_rgb in sorted(self.behavior_colors.items()):
            y_pos = 20 + y_offset
            cv2.rectangle(frame, (legend_x_start, y_pos), (legend_x_start + 20, y_pos + 20), color_rgb[::-1], -1)
            cv2.putText(frame, behavior, (legend_x_start + 30, y_pos + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (240, 240, 240), 1, cv2.LINE_AA)
            y_offset += 25

    def _draw_timeline_on_frame(self, frame, frame_idx, total_frames, original_video_height):
        new_h, new_w, _ = frame.shape
        num_tanks = self.grid_settings['cols'] * self.grid_settings['rows']
        if new_h <= original_video_height or num_tanks == 0 or total_frames <= 1: return
        cv2.rectangle(frame, (0, original_video_height), (new_w, new_h), (10, 10, 10), -1)
        draw_area_x, draw_area_y = 40, original_video_height + 10
        draw_area_w, draw_area_h = new_w - 80, new_h - original_video_height - 20
        if draw_area_h <= 0 or draw_area_w <= 0: return
        bar_h_total = draw_area_h / num_tanks; bar_h_visible = bar_h_total * 0.8
        for i in range(num_tanks):
            tank_id = i + 1; y_pos = draw_area_y + i * bar_h_total
            cv2.rectangle(frame, (draw_area_x, int(y_pos)), (draw_area_x + draw_area_w, int(y_pos + bar_h_visible)), (74, 74, 74), -1)
            if tank_id in self.timeline_segments:
                for start_f, end_f, behavior in self.timeline_segments[tank_id]:
                    color_rgb = self.behavior_colors.get(behavior, (100, 100, 100))
                    x_start = int(draw_area_x + (start_f / total_frames) * draw_area_w)
                    x_end = int(draw_area_x + ((end_f + 1) / total_frames) * draw_area_w)
                    cv2.rectangle(frame, (x_start, int(y_pos)), (x_end, int(y_pos + bar_h_visible)), color_rgb[::-1], -1)
            cv2.putText(frame, f"T{tank_id}", (draw_area_x - 35, int(y_pos + bar_h_visible / 2 + 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (224, 224, 224), 1, cv2.LINE_AA)
        indicator_x = int(draw_area_x + (frame_idx / total_frames) * draw_area_w)
        cv2.line(frame, (indicator_x, draw_area_y), (indicator_x, draw_area_y + draw_area_h), (80, 80, 255), 2)

    def process_frame(self, original_frame, frame_idx, total_frames):
        original_w, original_h = self.video_size
        
        if self.draw_overlays:
            new_w, new_h = self.final_video_size
            processed_frame = np.zeros((new_h, new_w, 3), dtype=np.uint8)
            processed_frame[0:original_h, 0:original_w] = original_frame
        else:
            processed_frame = original_frame.copy()

        overlay = processed_frame.copy() # For mask transparency

        def transform_point(x, y):
            p = self.grid_transform.map(QPointF(x, y)); return int(p.x()), int(p.y())

        if self.draw_grid:
            for i in range(self.grid_settings['cols'] + 1): cv2.line(processed_frame, transform_point(original_w*i/self.grid_settings['cols'],0), transform_point(original_w*i/self.grid_settings['cols'],original_h), (0,255,0), self.line_thickness)
            for i in range(self.grid_settings['rows'] + 1): cv2.line(processed_frame, transform_point(0,original_h*i/self.grid_settings['rows']), transform_point(original_w,original_h*i/self.grid_settings['rows']), (0,255,0), self.line_thickness)
        
        has_drawn_mask = False
        if frame_idx in self.detections:
            for det in self.detections[frame_idx]:
                if det.get('tank_number') is not None and (not self.selected_cells or str(det['tank_number']) in self.selected_cells):
                    color_bgr = self.behavior_colors.get(det["class_name"], (255, 255, 255))[::-1]
                    
                    # ### CONDITIONAL DRAWING LOGIC ###
                    if 'polygon' in det and det['polygon']:
                        try:
                            # Convert string representation of polygon points back to numpy array
                            poly_points = np.array([list(map(int, p.split(','))) for p in det['polygon'].split(';')], dtype=np.int32)
                            cv2.fillPoly(overlay, [poly_points], color_bgr)
                            has_drawn_mask = True
                        except (ValueError, IndexError):
                            # Fallback if polygon data is malformed
                            x1, y1, x2, y2 = map(int, (det["x1"], det["y1"], det["x2"], det["y2"]))
                            cv2.rectangle(processed_frame, (x1, y1), (x2, y2), color_bgr, 2)
                    else:
                        # Fallback to bounding box if no polygon data
                        x1, y1, x2, y2 = map(int, (det["x1"], det["y1"], det["x2"], det["y2"]))
                        cv2.rectangle(processed_frame, (x1, y1), (x2, y2), color_bgr, 2)

                    if det.get('cx') is not None and det.get('cy') is not None: cv2.circle(processed_frame, (int(det['cx']), int(det['cy'])), 8, (0, 0, 255), -1)
                    
                    label = f"{det['tank_number']}"
                    x1, y1 = int(det["x1"]), int(det["y1"])
                    font_face, f_scale, f_thick = cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2
                    (tw, th), _ = cv2.getTextSize(label, font_face, f_scale, f_thick)
                    cv2.rectangle(processed_frame, (x1, y1 - th - 12), (x1 + tw, y1), color_bgr, -1)
                    cv2.putText(processed_frame, label, (x1, y1 - 7), font_face, f_scale, (0,0,0), f_thick, cv2.LINE_AA)
        
        if has_drawn_mask:
            processed_frame = cv2.addWeighted(overlay, 0.4, processed_frame, 0.6, 0)

        if self.draw_overlays:
            self._draw_legend_on_frame(processed_frame, original_w)
            self._draw_timeline_on_frame(processed_frame, frame_idx, total_frames, original_h)
            
        return processed_frame

    def run(self):
        cap = cv2.VideoCapture(self.source_path)
        if not cap.isOpened(): self.error_occurred.emit(f"Could not open source video: {self.source_path}"); return
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(self.output_path, fourcc, self.fps, self.final_video_size)
        if not writer.isOpened(): self.error_occurred.emit(f"Could not open video writer for: {self.output_path}"); cap.release(); return
            
        for frame_idx in range(total_frames):
            if not self.is_running: break
            ret, original_frame = cap.read()
            if not ret: break
            
            processed_frame = self.process_frame(original_frame, frame_idx, total_frames)
            writer.write(processed_frame)
            self.progress_updated.emit(int((frame_idx + 1) * 100 / total_frames))
            
        cap.release(); writer.release()
        if self.is_running: self.finished.emit()