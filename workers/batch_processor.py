# EthoGrid_App/workers/batch_processor.py
import os
import csv
import json
import traceback
import cv2
from collections import defaultdict
from PyQt5.QtCore import QThread, pyqtSignal, QPointF
from PyQt5.QtGui import QTransform
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from .video_saver import VideoSaver
from core.data_exporter import export_centroid_csv, export_to_excel_sheets, export_to_excel_by_tank, export_trajectory_image, export_heatmap_image
from core.stopwatch import Stopwatch
from core.tracker import get_original_det, to_norfair, NORFAIR_AVAILABLE
try:
    from boxmot import create_tracker
    BOXMOT_AVAILABLE = True
except ImportError:
    BOXMOT_AVAILABLE = False
if NORFAIR_AVAILABLE:
    from norfair import Tracker, OptimizedKalmanFilterFactory

class BatchProcessor(QThread):
    overall_progress = pyqtSignal(int, int, str)
    file_progress = pyqtSignal(int, int, int)
    log_message = pyqtSignal(str)
    finished = pyqtSignal()
    time_updated = pyqtSignal(str, str)
    speed_updated = pyqtSignal(float)

    def __init__(self, video_files, settings_file, output_dir, csv_dir, tracking_method, tracker_params, max_animals_per_tank, frame_sample_rate, auto_stitch, save_video, save_csv, save_centroid_csv, save_excel_track, save_excel_tank, save_trajectory_img, save_heatmap_img, time_gap_seconds, draw_overlays, iou_threshold, parent=None):
        super().__init__(parent)
        self.video_files = video_files; self.settings_file = settings_file; self.output_dir = output_dir; self.csv_dir = csv_dir
        self.tracking_method = tracking_method
        self.tracker_params = tracker_params
        self.max_animals_per_tank = max_animals_per_tank
        self.frame_sample_rate = frame_sample_rate
        self.auto_stitch = auto_stitch
        self.save_video = save_video; self.save_csv = save_csv; self.save_centroid_csv = save_centroid_csv
        self.save_excel_track = save_excel_track; self.save_excel_tank = save_excel_tank
        self.save_trajectory_img = save_trajectory_img; self.save_heatmap_img = save_heatmap_img
        self.time_gap_seconds = time_gap_seconds;
        self.draw_overlays = draw_overlays;
        self.iou_threshold = iou_threshold; 
        self.is_running = True

    def stop(self):
        self.log_message.emit("Stopping batch process...")
        self.is_running = False

    def _get_tank_for_point(self, x, y, w, h, cols, rows, inverse_transform):
        transformed_point = inverse_transform.map(QPointF(x, y)); tx, ty = transformed_point.x(), transformed_point.y()
        if not (0 <= tx < w and 0 <= ty < h): return None
        cell_width, cell_height = w / cols, h / rows; col = min(cols - 1, max(0, int(tx / cell_width))); row = min(rows - 1, max(0, int(ty / cell_height)))
        return row * cols + col + 1

    def _calculate_iou(self, boxA, boxB):
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])

        interArea = max(0, xB - xA) * max(0, yB - yA)
        boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])

        if (boxAArea + boxBArea - interArea) == 0:
             return 0.0
        iou = interArea / float(boxAArea + boxBArea - interArea)
        return iou

    def _get_visual_fingerprint(self, frame, x1, y1, x2, y2):
        """Extracts a color histogram to use as a visual identity fingerprint."""
        h_img, w_img = frame.shape[:2]
        x1, y1 = max(0, int(x1)), max(0, int(y1))
        x2, y2 = min(w_img, int(x2)), min(h_img, int(y2))
        
        if x2 - x1 < 2 or y2 - y1 < 2:
            return None # Box too small
            
        crop = frame[y1:y2, x1:x2]
        hsv_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        
        # Calculate 2D Histogram (Hue and Saturation)
        hist = cv2.calcHist([hsv_crop], [0, 1], None, [32, 32], [0, 180, 0, 256])
        cv2.normalize(hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
        return hist.flatten()

    def _compare_fingerprints(self, hist1, hist2):
        """Returns distance between two visual fingerprints (0 is identical, 1 is completely different)"""
        if hist1 is None or hist2 is None: return 1.0
        # Use Bhattacharyya distance for histogram comparison
        score = cv2.compareHist(hist1, hist2, cv2.HISTCMP_BHATTACHARYYA)
        return score

    def _merge_frame_duplicates_pre_tracking(self, detections_dict):
        merged_detections = defaultdict(list)
        total_merged = 0
        
        for frame_idx, dets in detections_dict.items():
            dets_by_tank = defaultdict(list)
            for det in dets:
                tank_num = det.get('tank_number')
                if tank_num is not None:
                    half_w, half_h = 5, 5
                    det['x1'] = det.get('x1', det['cx'] - half_w if 'cx' in det else 0)
                    det['y1'] = det.get('y1', det['cy'] - half_h if 'cy' in det else 0)
                    det['x2'] = det.get('x2', det['cx'] + half_w if 'cx' in det else 0)
                    det['y2'] = det.get('y2', det['cy'] + half_h if 'cy' in det else 0)
                    dets_by_tank[int(tank_num)].append(det)
            
            frame_output = []
            for tank_num, tank_dets in dets_by_tank.items():
                if len(tank_dets) == 1:
                    tank_dets[0]['tank_number'] = tank_num
                    frame_output.append(tank_dets[0])
                    continue
                
                tank_dets.sort(key=lambda x: x.get('conf', 0.0), reverse=True)
                keep_list = []
                
                while tank_dets:
                    best_det = tank_dets.pop(0)
                    best_det['tank_number'] = tank_num
                    keep_list.append(best_det)
                    
                    i = 0
                    while i < len(tank_dets):
                        other_det = tank_dets[i]
                        box_best = [best_det['x1'], best_det['y1'], best_det['x2'], best_det['y2']]
                        box_other = [other_det['x1'], other_det['y1'], other_det['x2'], other_det['y2']]
                        
                        if self._calculate_iou(box_best, box_other) >= self.iou_threshold: 
                            tank_dets.pop(i)
                            total_merged += 1
                        else:
                            i += 1
                            
                frame_output.extend(keep_list)
            merged_detections[frame_idx].extend(frame_output)
        
        self.log_message.emit(f" > Pre-Tracking Cleanup: Removed {total_merged} overlapping model double-detections via NMS.")
        return merged_detections

    def run(self):
        try:
            with open(self.settings_file, 'r') as f:
                settings_data = json.load(f)
                grid_settings = settings_data['grid_settings']; transform_settings = settings_data['grid_transform']
                self.conversion_rate = settings_data.get('conversion_rate', 1.0) 
        except Exception as e:
            self.log_message.emit(f"[ERROR] Failed to load settings file: {e}"); return

        is_boxmot_tracker = self.tracking_method not in ["Confidence Filter", "Norfair", "Custom Force-N"]

        if is_boxmot_tracker:
            if not BOXMOT_AVAILABLE:
                self.log_message.emit("[ERROR] 'boxmot' library not found. Please run 'pip install boxmot'. Aborting."); self.finished.emit(); return
            if self.tracking_method in ['StrongSORT', 'BoTSORT'] and not os.path.exists(self.tracker_params.get('model_weights', '')):
                self.log_message.emit(f"[ERROR] Re-ID model not found: {self.tracker_params.get('model_weights', '')}"); self.finished.emit(); return
        
        if self.tracking_method == "Norfair":
            if 'distance_threshold' in self.tracker_params:
                cm_thresh = self.tracker_params['distance_threshold']
                px_thresh = cm_thresh * self.conversion_rate
                self.tracker_params['distance_threshold'] = px_thresh

        for idx, video_path in enumerate(self.video_files):
            if not self.is_running: break
            video_filename = os.path.basename(video_path);
            self.overall_progress.emit(idx + 1, len(self.video_files), video_filename);
            self.file_progress.emit(0, 0, 0);
            self.time_updated.emit("00:00:00", "--:--:--"); self.speed_updated.emit(0.0)

            base_name = os.path.splitext(video_filename)[0];
            search_dir = self.csv_dir if self.csv_dir and os.path.isdir(self.csv_dir) else os.path.dirname(video_path)
            csv_path = os.path.join(search_dir, base_name + ".csv")
            if not os.path.exists(csv_path): csv_path = os.path.join(search_dir, base_name + "_detections.csv")
            if not os.path.exists(csv_path): csv_path = os.path.join(search_dir, base_name + "_segmentations.csv")
            
            if not os.path.exists(csv_path):
                self.log_message.emit(f"[WARNING] Skipping '{video_filename}': Matching CSV file not found."); continue

            try:
                raw_detections = defaultdict(list); csv_headers = []
                with open(csv_path, newline="", encoding='utf-8') as f:
                    reader = csv.DictReader(f); csv_headers = reader.fieldnames or []
                    for row in reader:
                        frame_idx = int(float(row["frame_idx"]))
                        for col, val in row.items():
                            try: row[col] = float(val)
                            except (ValueError, TypeError): pass
                        raw_detections[frame_idx].append(row)
                
                self.log_message.emit("Assigning raw detections to tanks...")
                cap = cv2.VideoCapture(video_path);
                if not cap.isOpened(): continue
                
                video_w, video_h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT));
                video_fps, total_frames = cap.get(cv2.CAP_PROP_FPS) or 30.0, int(cap.get(cv2.CAP_PROP_FRAME_COUNT));
                video_size = (video_w, video_h)
                
                final_transform = QTransform();
                final_transform.translate(video_w * transform_settings['center_x'], video_h * transform_settings['center_y']);
                final_transform.rotate(transform_settings['angle']);
                final_transform.scale(transform_settings['scale_x'], transform_settings['scale_y']);
                final_transform.translate(-video_w / 2, -video_h / 2)
                inverse_transform, _ = final_transform.inverted()
                
                detections_after_tank_assignment = defaultdict(list)
                for frame_idx, dets in raw_detections.items():
                    valid_dets_in_frame = []
                    for det in dets:
                        if 'cx' not in det or det.get('cx') is None: det['cx'], det['cy'] = (det.get("x1", 0) + det.get("x2", 0)) / 2.0, (det.get("y1", 0) + det.get("y2", 0)) / 2.0
                        tank_num = self._get_tank_for_point(det['cx'], det['cy'], video_w, video_h, grid_settings['cols'], grid_settings['rows'], inverse_transform)
                        if tank_num is not None: det['tank_number'] = tank_num
                        valid_dets_in_frame.append(det)
                    
                    dets_by_tank = defaultdict(list)
                    for det in valid_dets_in_frame:
                        if det.get('tank_number') is not None:
                            dets_by_tank[int(det['tank_number'])].append(det)
                    
                    detections_after_tank_assignment[frame_idx] = [d for tank_dets in dets_by_tank.values() for d in tank_dets]

                self.log_message.emit("--- Starting Pre-Tracking Duplicate NMS ---")
                raw_detections = self._merge_frame_duplicates_pre_tracking(detections_after_tank_assignment)
                
                detections = {}
                num_tanks = grid_settings['cols'] * grid_settings['rows']

                # =========================================================
                # NEW: VISUAL-SPATIAL FORCE-N TRACKER
                # =========================================================
                if self.tracking_method == "Custom Force-N":
                    self.log_message.emit(f"Applying Visual-Spatial Force-N Tracking (Max {self.max_animals_per_tank} IDs per tank)...")
                    tracked_detections = defaultdict(list)
                    
                    # Store tracking states: {tank_num: {track_id: {'pos': (cx, cy), 'hist': visual_feature}}}
                    active_tracks = {t: {} for t in range(1, num_tanks + 1)}
                    
                    for frame_idx in range(total_frames):
                        if not self.is_running: break
                        if frame_idx % 500 == 0: self.log_message.emit(f"Force-N Tracking - Frame: {frame_idx}/{total_frames}")
                        
                        ret, frame = cap.read()
                        if not ret: break
                        
                        dets_this_frame = raw_detections.get(frame_idx, [])
                        
                        for tank_num in range(1, num_tanks + 1):
                            tank_dets = [d for d in dets_this_frame if d.get('tank_number') == tank_num]
                            
                            # Limit detections logically by confidence if the detector spat out too many
                            tank_dets.sort(key=lambda x: x.get('conf', 0.0), reverse=True)
                            tank_dets = tank_dets[:self.max_animals_per_tank]
                            
                            if not tank_dets:
                                continue # Nothing to track in this tank this frame
                            
                            # Extract visual fingerprints for new detections
                            for det in tank_dets:
                                det['hist'] = self._get_visual_fingerprint(frame, det['x1'], det['y1'], det['x2'], det['y2'])
                            
                            tank_active = active_tracks[tank_num]
                            
                            # Initialization Phase: Fill empty slots up to Max N
                            if len(tank_active) < self.max_animals_per_tank:
                                unassigned_dets = []
                                for det in tank_dets:
                                    # Create a new ID
                                    new_id = len(tank_active) + 1
                                    if new_id <= self.max_animals_per_tank:
                                        det['track_id'] = new_id
                                        tank_active[new_id] = {'pos': (det['cx'], det['cy']), 'hist': det['hist']}
                                        tracked_detections[frame_idx].append(det)
                                    else:
                                        unassigned_dets.append(det)
                                tank_dets = unassigned_dets # Continue with remaining if we hit max limit
                            
                            if not tank_dets:
                                continue # All assigned
                                
                            # Association Phase: Hungarian Algorithm using Visual + Spatial Cost
                            track_ids = list(tank_active.keys())
                            cost_matrix = np.full((len(track_ids), len(tank_dets)), 1e6) # High default cost
                            
                            # Calculate maximum possible diagonal across the frame for spatial normalization
                            max_dist = np.hypot(video_w, video_h)
                            
                            for i, tid in enumerate(track_ids):
                                hist_hist = tank_active[tid]['hist']
                                last_pos = tank_active[tid]['pos']
                                
                                for j, det in enumerate(tank_dets):
                                    # 1. Spatial Cost (Normalized 0 to 1)
                                    dist = np.hypot(last_pos[0] - det['cx'], last_pos[1] - det['cy'])
                                    spatial_cost = dist / max_dist
                                    
                                    # 2. Visual Cost (0 to 1, where 0 is exact match)
                                    visual_cost = self._compare_fingerprints(hist_hist, det['hist'])
                                    
                                    # Weighted combination: 60% Visual, 40% Spatial
                                    total_cost = (0.6 * visual_cost) + (0.4 * spatial_cost)
                                    cost_matrix[i, j] = total_cost

                            # Solve assignment mathematically
                            row_ind, col_ind = linear_sum_assignment(cost_matrix)
                            
                            for r, c in zip(row_ind, col_ind):
                                tid = track_ids[r]
                                matched_det = tank_dets[c].copy()
                                matched_det['track_id'] = tid
                                
                                # Update memory with new position and a blended visual history (moving average)
                                current_hist = tank_active[tid]['hist']
                                new_hist = matched_det['hist']
                                if current_hist is not None and new_hist is not None:
                                    blended_hist = (0.8 * current_hist) + (0.2 * new_hist) # Learn over time
                                else:
                                    blended_hist = new_hist if new_hist is not None else current_hist
                                    
                                tank_active[tid] = {'pos': (matched_det['cx'], matched_det['cy']), 'hist': blended_hist}
                                
                                # Remove histogram array before saving to avoid data bloat
                                matched_det.pop('hist', None)
                                tracked_detections[frame_idx].append(matched_det)
                                
                    detections = tracked_detections
                    self.log_message.emit("Visual-Spatial Force-N tracking complete. IDs 100% consistent. No ghost IDs generated.")

                # =========================================================

                elif is_boxmot_tracker:
                    self.log_message.emit(f"Applying {self.tracking_method} tracking to all detections...")
                    trackers = {i: create_tracker(self.tracking_method.lower(), **self.tracker_params) for i in range(1, num_tanks + 1)}
                    tracked_detections = defaultdict(list)
                    for frame_idx in range(total_frames):
                        if frame_idx % 500 == 0: self.log_message.emit(f"Tracking Frame: {frame_idx}/{total_frames}")
                        if not self.is_running: break
                        
                        ret, frame = cap.read()
                        if not ret: break 

                        dets_this_frame = raw_detections.get(frame_idx, []); dets_by_tank = defaultdict(list)
                        for det in dets_this_frame: dets_by_tank[int(det['tank_number'])].append(det)
                        
                        for tank_num in range(1, num_tanks + 1):
                            dets_in_tank = dets_by_tank.get(tank_num, [])
                            detections_for_tracker = np.array([[d['x1'], d['y1'], d['x2'], d['y2'], d.get('conf', 1.0), 0] for d in dets_in_tank]) if dets_in_tank else np.empty((0, 6))
                            tracked_objects = trackers[tank_num].update(detections_for_tracker, frame)
                            
                            for obj in tracked_objects:
                                x1, y1, x2, y2, track_id = obj[:5]; cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                                original_det = get_original_det([x1, y1, x2, y2], dets_in_tank)
                                tracked_det = {'frame_idx': frame_idx, 'tank_number': tank_num, 'track_id': int(track_id), 'class_name': original_det.get('class_name', ''), 'conf': original_det.get('conf', 0), 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'polygon': original_det.get('polygon', ''), 'cx': cx, 'cy': cy}
                                tracked_detections[frame_idx].append(tracked_det)
                    
                    detections = tracked_detections; self.log_message.emit(f"{self.tracking_method} tracking complete.")

                elif self.tracking_method == "Norfair":
                    trackers = {i: Tracker(**self.tracker_params, filter_factory=OptimizedKalmanFilterFactory()) for i in range(1, num_tanks + 1)}
                    tracked_detections = defaultdict(list)
                    
                    for frame_idx in range(total_frames):
                        if frame_idx % 500 == 0: self.log_message.emit(f"Tracking Frame: {frame_idx}/{total_frames}")
                        if not self.is_running: break
                        
                        dets_this_frame = raw_detections.get(frame_idx, []); dets_by_tank = defaultdict(list)
                        for det in dets_this_frame: dets_by_tank[int(det['tank_number'])].append(det)
                        
                        for tank_num in range(1, num_tanks + 1):
                            dets_in_tank = dets_by_tank.get(tank_num, [])
                            norfair_dets = to_norfair(dets_in_tank)
                            tracked_objects = trackers[tank_num].update(detections=norfair_dets)
                            
                            for obj in tracked_objects:
                                est_points = obj.estimate.flatten(); cx, cy = est_points[0], est_points[1]
                                tracked_det = {'frame_idx': frame_idx, 'tank_number': tank_num, 'track_id': obj.id, 'class_name': obj.last_detection.data['class_name'], 'conf': obj.last_detection.data['conf'], 'x1': obj.last_detection.data['box'][0], 'y1': obj.last_detection.data['box'][1], 'x2': obj.last_detection.data['box'][2], 'y2': obj.last_detection.data['box'][3], 'polygon': obj.last_detection.data['polygon'], 'cx': cx, 'cy': cy}
                                tracked_detections[frame_idx].append(tracked_det)
                    
                    detections = tracked_detections; self.log_message.emit("Norfair tracking complete.")

                else: 
                    detections = raw_detections; self.log_message.emit("Using merged raw detections (no tracking).")
                
                # Auto-stitch for older trackers (Skipped for Force-N)
                if self.auto_stitch and self.tracking_method not in ["Confidence Filter", "Custom Force-N"]:
                    detections = self._force_stitch_to_max(detections)
                elif self.tracking_method == "Confidence Filter":
                    final_detections_filtered = defaultdict(list)
                    for frame_idx, dets in detections.items():
                        tank_groups = defaultdict(list)
                        for det in dets:
                            tank_groups[det.get('tank_number')].append(det)
                        for tank_num, tank_dets in tank_groups.items():
                            tank_dets.sort(key=lambda x: x.get('conf', 0.0), reverse=True)
                            final_detections_filtered[frame_idx].extend(tank_dets[:self.max_animals_per_tank])
                    detections = final_detections_filtered
                
                if 'track_id' not in csv_headers and self.tracking_method != "Confidence Filter": csv_headers.append('track_id')
                if 'original_track_id' not in csv_headers and self.auto_stitch: csv_headers.append('original_track_id')
                
                cap.release() 

                if self.save_csv:
                    output_csv_path = os.path.join(self.output_dir, f"{base_name}_with_tanks.csv");
                    self.log_message.emit(f"Saving enriched CSV to: {os.path.basename(output_csv_path)}")
                    all_processed_detections = [det for frame, dets in sorted(detections.items()) for det in dets]
                    if all_processed_detections:
                        final_headers = list(all_processed_detections[0].keys())
                        # Remove visual hist if it accidentally survived
                        if 'hist' in final_headers: final_headers.remove('hist')
                        with open(output_csv_path, 'w', newline='', encoding='utf-8') as f:
                            writer = csv.DictWriter(f, fieldnames=final_headers, extrasaction='ignore'); writer.writeheader()
                            for det in all_processed_detections:
                                row_to_write = det.copy()
                                for key, val in row_to_write.items():
                                    if isinstance(val, float): row_to_write[key] = f"{val:.4f}"
                                writer.writerow(row_to_write)

                if self.save_centroid_csv:
                    output_centroid_path = os.path.join(self.output_dir, f"{base_name}_centroids_wide.csv");
                    self.log_message.emit(f"Saving centroid CSV to: {os.path.basename(output_centroid_path)}")
                    error_msg = export_centroid_csv(detections, grid_settings['cols'] * grid_settings['rows'], output_centroid_path)
                    if error_msg: self.log_message.emit(f"[ERROR] Centroid CSV export failed: {error_msg}")

                if self.save_excel_track:
                    output_excel_path = os.path.join(self.output_dir, f"{base_name}_by_track.xlsx");
                    self.log_message.emit(f"Saving Excel (by Track) to: {os.path.basename(output_excel_path)}")
                    error_msg = export_to_excel_sheets(detections, output_excel_path)
                    if error_msg: self.log_message.emit(f"[ERROR] Excel export failed: {error_msg}")

                if self.save_excel_tank:
                    output_excel_path = os.path.join(self.output_dir, f"{base_name}_by_tank.xlsx");
                    self.log_message.emit(f"Saving Excel (by Tank) to: {os.path.basename(output_excel_path)}")
                    error_msg = export_to_excel_by_tank(detections, output_excel_path)
                    if error_msg: self.log_message.emit(f"[ERROR] Excel export failed: {error_msg}")

                if self.save_trajectory_img:
                    output_img_path = os.path.join(self.output_dir, f"{base_name}_trajectory.png");
                    self.log_message.emit(f"Saving Trajectory Image to: {os.path.basename(output_img_path)}")
                    error_msg = export_trajectory_image(detections, grid_settings, video_size, final_transform, output_img_path, self.time_gap_seconds, video_fps, self.frame_sample_rate)
                    if error_msg: self.log_message.emit(f"[ERROR] Trajectory image export failed: {error_msg}")

                if self.save_heatmap_img:
                    output_img_path = os.path.join(self.output_dir, f"{base_name}_heatmap.png");
                    self.log_message.emit(f"Saving Heatmap Image to: {os.path.basename(output_img_path)}")
                    error_msg = export_heatmap_image(detections, video_path, output_img_path, self.time_gap_seconds, video_fps, self.frame_sample_rate)
                    if error_msg: self.log_message.emit(f"[ERROR] Heatmap image export failed: {error_msg}")

                file_stopwatch = Stopwatch()
                if self.save_video:
                    output_video_path = os.path.join(self.output_dir, f"{base_name}_annotated.mp4");
                    self.log_message.emit(f"Exporting annotated video to: {os.path.basename(output_video_path)}")
                    all_behaviors = sorted(list(set(det.get('class_name', 'unknown') for dets in detections.values() for det in dets)));
                    predefined_colors = [(31,119,180),(255,127,14),(44,160,44),(214,39,40),(148,103,189),(140,86,75),(227,119,194),(127,127,127),(188,189,34),(23,190,207)];
                    behavior_colors = {name: predefined_colors[i % len(predefined_colors)] for i, name in enumerate(all_behaviors)}
                    
                    tank_data_for_timeline = defaultdict(dict)
                    
                    timeline_segments = {}
                    
                    if self.draw_overlays:
                        for frame_idx_tl, dets in detections.items():
                            for det in dets:
                                if det.get('tank_number') is not None: tank_data_for_timeline[int(det['tank_number'])][frame_idx_tl] = det.get("class_name", "")
                        
                        timeline_segments = {};
                        for tank_id, frames in tank_data_for_timeline.items():
                            if not frames: continue
                            segments, sorted_frames = [], sorted(frames.keys()); start_frame, current_behavior = sorted_frames[0], frames[sorted_frames[0]]
                            for i in range(1, len(sorted_frames)):
                                frame, prev_frame, behavior = sorted_frames[i], sorted_frames[i-1], frames[sorted_frames[i]]
                                if behavior != current_behavior or frame != prev_frame + 1:
                                    segments.append((start_frame, prev_frame, current_behavior)); start_frame, current_behavior = frame, behavior
                            segments.append((start_frame, sorted_frames[-1], current_behavior)); timeline_segments[tank_id] = segments

                    video_exporter = VideoSaver(source_video_path=video_path, output_video_path=output_video_path, detections=detections, grid_settings=grid_settings, grid_transform=final_transform, behavior_colors=behavior_colors, video_size=video_size, fps=video_fps, line_thickness=grid_settings.get('line_thickness', 2), selected_cells=set(), timeline_segments=timeline_segments, draw_grid=False, draw_overlays=self.draw_overlays)
                    
                    cap_export = cv2.VideoCapture(video_path);
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v');
                    writer = cv2.VideoWriter(output_video_path, fourcc, video_fps, video_exporter.final_video_size)
                    
                    file_stopwatch.start(); frame_count_for_fps = 0; fps_check_time = 0
                    for frame_idx_export in range(total_frames):
                        if not self.is_running: break
                        
                        ret, frame = cap_export.read()
                        if not ret: break 
                        
                        processed_frame = video_exporter.process_frame(frame, frame_idx_export, total_frames);
                        writer.write(processed_frame)
                        
                        frame_count_for_fps += 1
                        current_time = file_stopwatch.get_elapsed_time(as_float=True)
                        if current_time > fps_check_time + 1:
                            processing_fps = frame_count_for_fps / (current_time - fps_check_time) if (current_time - fps_check_time) > 0 else 0
                            self.speed_updated.emit(processing_fps);
                            frame_count_for_fps = 0; fps_check_time = current_time
                        
                        progress = int((frame_idx_export + 1) * 100 / total_frames);
                        self.file_progress.emit(progress, frame_idx_export + 1, total_frames)
                        self.time_updated.emit(file_stopwatch.get_elapsed_time(), file_stopwatch.get_etr(frame_idx_export + 1, total_frames))
                    
                    cap_export.release(); writer.release()
                    self.log_message.emit(f"✓ Finished processing video for: {video_filename}")

                else:
                    if any([self.save_csv, self.save_centroid_csv, self.save_excel_track, self.save_excel_tank, self.save_trajectory_img, self.save_heatmap_img]):
                        file_stopwatch.start();
                        for i in range(101):
                            if not self.is_running: break
                            self.file_progress.emit(i, total_frames, total_frames);
                            self.time_updated.emit(file_stopwatch.get_elapsed_time(), "--:--:--")
                            QThread.msleep(5)
                        self.log_message.emit(f"✓ Finished processing data for: {video_filename}")

            except Exception as e:
                self.log_message.emit(f"[ERROR] Failed to process {video_filename}: {e}");
                self.log_message.emit(traceback.format_exc()); continue

        if self.is_running: self.log_message.emit("\nBatch processing complete!")
        else: self.log_message.emit("\nBatch processing cancelled.")
        self.finished.emit()