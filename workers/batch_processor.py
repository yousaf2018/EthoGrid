# EthoGrid_App/workers/batch_processor.py

import os
import csv
import json
import traceback
from collections import defaultdict
from PyQt5.QtCore import QThread, pyqtSignal, QPointF
from PyQt5.QtGui import QTransform
import cv2

from .video_saver import VideoSaver
from core.data_exporter import export_centroid_csv

class BatchProcessor(QThread):
    overall_progress = pyqtSignal(int, int, str)
    file_progress = pyqtSignal(int, int, int)
    log_message = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, video_files, settings_file, output_dir, save_video, save_csv, save_centroid_csv, draw_overlays, parent=None):
        super().__init__(parent)
        self.video_files = video_files; self.settings_file = settings_file; self.output_dir = output_dir
        self.save_video = save_video; self.save_csv = save_csv; self.save_centroid_csv = save_centroid_csv
        self.draw_overlays = draw_overlays
        self.is_running = True

    def stop(self):
        self.log_message.emit("Stopping batch process..."); self.is_running = False

    def _get_tank_for_point(self, x, y, w, h, cols, rows, inverse_transform):
        transformed_point = inverse_transform.map(QPointF(x, y)); tx, ty = transformed_point.x(), transformed_point.y()
        if not (0 <= tx < w and 0 <= ty < h): return None
        cell_width, cell_height = w / cols, h / rows; col = min(cols - 1, max(0, int(tx / cell_width))); row = min(rows - 1, max(0, int(ty / cell_height)))
        return row * cols + col + 1

    def run(self):
        try:
            with open(self.settings_file, 'r') as f: settings_data = json.load(f)
            grid_settings = settings_data['grid_settings']; line_thickness = settings_data['line_thickness']; transform_settings = settings_data['grid_transform']
        except Exception as e: self.log_message.emit(f"[ERROR] Failed to load settings file: {e}"); return

        for idx, video_path in enumerate(self.video_files):
            if not self.is_running: break
            video_filename = os.path.basename(video_path); self.overall_progress.emit(idx + 1, len(self.video_files), video_filename); self.file_progress.emit(0, 0, 0)
            base_name = os.path.splitext(video_filename)[0]; csv_path = os.path.join(os.path.dirname(video_path), base_name + ".csv")
            if not os.path.exists(csv_path):
                csv_path = os.path.join(os.path.dirname(video_path), base_name + "_detections.csv")
                if not os.path.exists(csv_path): self.log_message.emit(f"[WARNING] Skipping '{video_filename}': Matching CSV file not found."); continue
            
            self.log_message.emit(f"Found matching detection file: {os.path.basename(csv_path)}")
            try:
                detections, csv_headers = {}, []
                with open(csv_path, newline="", encoding='utf-8') as f:
                    reader = csv.DictReader(f); csv_headers = reader.fieldnames[:]
                    coord_cols = ['x1', 'y1', 'x2', 'y2', 'cx', 'cy']
                    for row in reader:
                        # ### THE CRITICAL FIX IS HERE ###
                        # The frame index MUST be an integer key.
                        frame_idx = int(float(row["frame_idx"]))
                        
                        # Convert all potential coordinate columns to float for precision
                        for col in coord_cols:
                            if col in row and row[col]:
                                try: row[col] = float(row[col])
                                except (ValueError, TypeError): row[col] = None
                        
                        detections.setdefault(frame_idx, []).append(row)
                
                self.log_message.emit("Assigning detections to tanks based on centroid...")
                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened(): self.log_message.emit(f"[ERROR] Could not open video: {video_filename}"); continue
                video_w, video_h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)); video_fps, total_frames = cap.get(cv2.CAP_PROP_FPS) or 30.0, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); video_size = (video_w, video_h); cap.release()
                
                final_transform = QTransform(); final_transform.translate(video_w * transform_settings['center_x'], video_h * transform_settings['center_y']); final_transform.rotate(transform_settings['angle']); final_transform.scale(transform_settings['scale_x'], transform_settings['scale_y']); final_transform.translate(-video_w / 2, -video_h / 2)
                
                inverse_transform, _ = final_transform.inverted()
                for dets in detections.values():
                    for det in dets:
                        # If cx/cy are not in the CSV, calculate them
                        if 'cx' not in det or det['cx'] is None:
                            det['cx'] = (det["x1"] + det["x2"]) / 2.0
                            det['cy'] = (det["y1"] + det["y2"]) / 2.0
                        det['tank_number'] = self._get_tank_for_point(det['cx'], det['cy'], video_w, video_h, grid_settings['cols'], grid_settings['rows'], inverse_transform)

                if self.save_csv:
                    output_csv_path = os.path.join(self.output_dir, f"{base_name}_with_tanks.csv"); self.log_message.emit(f"Saving enriched CSV to: {os.path.basename(output_csv_path)}")
                    all_processed_detections = [det for frame_dets in detections.values() for det in frame_dets]; new_headers = csv_headers[:]; new_headers.extend(k for k in ['tank_number', 'cx', 'cy'] if k not in new_headers)
                    with open(output_csv_path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=new_headers, extrasaction='ignore')
                        writer.writeheader()
                        for det in all_processed_detections:
                            row_to_write = det.copy()
                            for key in ['x1', 'y1', 'x2', 'y2', 'cx', 'cy']:
                                if key in row_to_write and isinstance(row_to_write[key], float):
                                    row_to_write[key] = f"{row_to_write[key]:.4f}"
                            writer.writerow(row_to_write)

                if self.save_centroid_csv:
                    output_centroid_path = os.path.join(self.output_dir, f"{base_name}_centroids_wide.csv"); self.log_message.emit(f"Saving centroid CSV to: {os.path.basename(output_centroid_path)}")
                    error_msg = export_centroid_csv(detections, grid_settings['cols'] * grid_settings['rows'], output_centroid_path)
                    if error_msg: self.log_message.emit(f"[ERROR] Centroid CSV export failed: {error_msg}")

                if self.save_video:
                    output_video_path = os.path.join(self.output_dir, f"{base_name}_annotated.mp4"); self.log_message.emit(f"Exporting annotated video to: {os.path.basename(output_video_path)}")
                    all_behaviors = sorted(list(set(det['class_name'] for dets in detections.values() for det in dets))); predefined_colors = [(31,119,180),(255,127,14),(44,160,44),(214,39,40),(148,103,189),(140,86,75),(227,119,194),(127,127,127),(188,189,34),(23,190,207)]; behavior_colors = {name: predefined_colors[i % len(predefined_colors)] for i, name in enumerate(all_behaviors)}
                    tank_data_for_timeline = defaultdict(dict)
                    if self.draw_overlays:
                        for frame_idx_tl, dets in detections.items():
                            for det in dets:
                                if det.get('tank_number') is not None: tank_data_for_timeline[det['tank_number']][frame_idx_tl] = det["class_name"]
                    timeline_segments = {};
                    for tank_id, frames in tank_data_for_timeline.items():
                        if not frames: continue
                        segments, sorted_frames = [], sorted(frames.keys()); start_frame, current_behavior = sorted_frames[0], frames[sorted_frames[0]]
                        for i in range(1, len(sorted_frames)):
                            frame, prev_frame, behavior = sorted_frames[i], sorted_frames[i-1], frames[sorted_frames[i]]
                            if behavior != current_behavior or frame != prev_frame + 1: segments.append((start_frame, prev_frame, current_behavior)); start_frame, current_behavior = frame, behavior
                        segments.append((start_frame, sorted_frames[-1], current_behavior)); timeline_segments[tank_id] = segments
                    video_exporter = VideoSaver(source_video_path=video_path, output_video_path=output_video_path, detections=detections, grid_settings=grid_settings, grid_transform=final_transform, behavior_colors=behavior_colors, video_size=video_size, fps=video_fps, line_thickness=line_thickness, selected_cells=set(), timeline_segments=timeline_segments, draw_grid=False, draw_overlays=self.draw_overlays)
                    cap_export = cv2.VideoCapture(video_path); fourcc = cv2.VideoWriter_fourcc(*'mp4v'); writer = cv2.VideoWriter(output_video_path, fourcc, video_fps, video_exporter.final_video_size)
                    for frame_idx_export in range(total_frames):
                        if not self.is_running: break
                        ret, frame = cap_export.read()
                        if not ret: break
                        processed_frame = video_exporter.process_frame(frame, frame_idx_export, total_frames); writer.write(processed_frame)
                        progress = int((frame_idx_export + 1) * 100 / total_frames); self.file_progress.emit(progress, frame_idx_export + 1, total_frames)
                    cap_export.release(); writer.release()
                    self.log_message.emit(f"✓ Finished processing video for: {video_filename}")
                else:
                    if self.save_csv or self.save_centroid_csv:
                        for i in range(101):
                            if not self.is_running: break
                            self.file_progress.emit(i, total_frames, total_frames); QThread.msleep(2)
                    self.log_message.emit(f"✓ Finished processing data for: {video_filename}")

            except Exception as e:
                self.log_message.emit(f"[ERROR] Failed to process {video_filename}: {e}"); self.log_message.emit(traceback.format_exc())
                continue
        
        if self.is_running: self.log_message.emit("\nBatch processing complete!")
        else: self.log_message.emit("\nBatch processing cancelled.")
        self.finished.emit()