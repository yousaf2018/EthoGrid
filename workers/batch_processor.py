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
from scipy.optimize import linear_sum_assignment # Hungarian Algorithm
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

    def _merge_frame_duplicates_pre_tracking(self, detections_dict):
        """ Uses NMS to remove AI double-detections before tracking """
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
                        
                        iou = self._calculate_iou(box_best, box_other)
                        
                        if iou >= self.iou_threshold: 
                            tank_dets.pop(i)
                            total_merged += 1
                        else:
                            i += 1
                            
                frame_output.extend(keep_list)

            merged_detections[frame_idx].extend(frame_output)
        
        self.log_message.emit(f" > Pre-Tracking Cleanup: Removed {total_merged} overlapping model double-detections via NMS.")
        return merged_detections

    def _force_stitch_to_max(self, detections_dict):
        """ Optimized Auto-Stitch for Standard Trackers using the Hungarian Algorithm """
        self.log_message.emit(f" > Post-processing: Optimizing Track Stitching (Hungarian Algorithm)...")
        all_rows = []
        for frame_idx, dets in detections_dict.items():
            for d in dets:
                d['frame_idx'] = frame_idx; all_rows.append(d)
        if not all_rows: return detections_dict
        
        df = pd.DataFrame(all_rows)
        if 'track_id' not in df.columns: return detections_dict
        if 'original_track_id' not in df.columns: df['original_track_id'] = df['track_id']
        
        all_tanks = df['tank_number'].dropna().unique()
        for tank_num in all_tanks:
            tank_df = df[df['tank_number'] == tank_num]
            if tank_df.empty: continue
            
            # 1. Build track metadata
            track_meta = {}
            for tid in tank_df['track_id'].unique():
                t_data = tank_df[tank_df['track_id'] == tid]
                track_meta[tid] = {
                    'start_frame': t_data['frame_idx'].min(),
                    'end_frame': t_data['frame_idx'].max(),
                    'start_pos': (t_data.iloc[0]['cx'], t_data.iloc[0]['cy']),
                    'end_pos': (t_data.iloc[-1]['cx'], t_data.iloc[-1]['cy']),
                    'frames': set(t_data['frame_idx'].tolist())
                }
                
            # 2. Sort tracks by duration to initialize primaries
            track_durations = tank_df.groupby('track_id')['frame_idx'].count().sort_values(ascending=False)
            all_sorted_tids = track_durations.index.tolist()
            
            active_primaries = set(all_sorted_tids[:self.max_animals_per_tank])
            unmatched_ghosts = set(all_sorted_tids[self.max_animals_per_tank:])
            
            if unmatched_ghosts:
                self.log_message.emit(f" - Tank {int(tank_num)}: Attempting to stitch {len(unmatched_ghosts)} ghost tracks.")
            
            # 3. Hungarian Master Loop
            while True:
                merged_in_iteration = True
                
                # A. Stitching Loop
                while merged_in_iteration:
                    merged_in_iteration = False
                    list_primaries = list(active_primaries)
                    list_ghosts = list(unmatched_ghosts)
                    
                    if not list_primaries or not list_ghosts:
                        break
                        
                    # Build Cost Matrix
                    cost_matrix = np.full((len(list_primaries), len(list_ghosts)), 1e6)
                    for i, p_id in enumerate(list_primaries):
                        for j, g_id in enumerate(list_ghosts):
                            t_p = track_meta[p_id]
                            t_g = track_meta[g_id]
                            
                            # VITAL FIX: If they exist in the same frame, they CANNOT be merged. Prevents box corruption.
                            if not t_p['frames'].isdisjoint(t_g['frames']):
                                continue 
                                
                            gap = 0
                            dist = 0
                            # Ghost starts after Primary ends
                            if t_g['start_frame'] > t_p['end_frame']:
                                gap = t_g['start_frame'] - t_p['end_frame']
                                dist = np.hypot(t_g['start_pos'][0] - t_p['end_pos'][0], t_g['start_pos'][1] - t_p['end_pos'][1])
                            # Primary starts after Ghost ends
                            elif t_p['start_frame'] > t_g['end_frame']:
                                gap = t_p['start_frame'] - t_g['end_frame']
                                dist = np.hypot(t_p['start_pos'][0] - t_g['end_pos'][0], t_p['start_pos'][1] - t_g['end_pos'][1])
                                
                            cost_matrix[i, j] = dist + (gap * 2.0) # Penalty: 2 px per frame missed
                            
                    # Solve Hungarian Global Optimization
                    row_ind, col_ind = linear_sum_assignment(cost_matrix)
                    
                    for r, c in zip(row_ind, col_ind):
                        if cost_matrix[r, c] < 1e5: # If a valid assignment exists (not overlapping)
                            p_id = list_primaries[r]
                            g_id = list_ghosts[c]
                            
                            self.log_message.emit(f"LOG: Tank {int(tank_num)}: Hungarian Stitched Ghost ID {g_id} -> Primary ID {p_id}")
                            
                            # Apply Merge to dataframe
                            mask = (df['tank_number'] == tank_num) & (df['track_id'] == g_id)
                            df.loc[mask, 'track_id'] = p_id
                            
                            # Update Metadata boundaries so it can absorb more ghosts
                            track_meta[p_id]['frames'].update(track_meta[g_id]['frames'])
                            if track_meta[g_id]['start_frame'] < track_meta[p_id]['start_frame']:
                                track_meta[p_id]['start_frame'] = track_meta[g_id]['start_frame']
                                track_meta[p_id]['start_pos'] = track_meta[g_id]['start_pos']
                            if track_meta[g_id]['end_frame'] > track_meta[p_id]['end_frame']:
                                track_meta[p_id]['end_frame'] = track_meta[g_id]['end_frame']
                                track_meta[p_id]['end_pos'] = track_meta[g_id]['end_pos']
                                
                            unmatched_ghosts.remove(g_id)
                            merged_in_iteration = True
                            
                # B. Promotion Check
                if unmatched_ghosts and len(active_primaries) < self.max_animals_per_tank:
                    longest_ghost = max(unmatched_ghosts, key=lambda x: len(track_meta[x]['frames']))
                    active_primaries.add(longest_ghost)
                    unmatched_ghosts.remove(longest_ghost)
                    self.log_message.emit(f"LOG: Tank {int(tank_num)}: Promoted Ghost ID {longest_ghost} to Primary slot.")
                    continue # Re-run Hungarian with new primary
                else:
                    break # Optimization complete
            
            # 4. Discard remaining noise ghosts that physically could not be stitched
            if unmatched_ghosts:
                self.log_message.emit(f"LOG: Tank {int(tank_num)}: Dropped {len(unmatched_ghosts)} tracker noise ghosts (Failed chronological constraints or max slots full).")
                for g_id in unmatched_ghosts:
                    mask = (df['tank_number'] == tank_num) & (df['track_id'] == g_id)
                    df = df.drop(df[mask].index)
                    
            # 5. Normalize IDs to 1..N
            final_tank_indices = df[df['tank_number'] == tank_num].index
            id_map = {old_id: new_id for new_id, old_id in enumerate(sorted(list(active_primaries)), 1)}
            df.loc[final_tank_indices, 'track_id'] = df.loc[final_tank_indices, 'track_id'].map(id_map)

        new_detections = defaultdict(list)
        for _, row in df.iterrows():
            d = row.to_dict();
            if 'frame_idx' in d:
                f_idx = int(d['frame_idx'])
                new_detections[f_idx].append(d)
        return new_detections

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
                # CUSTOM FORCE-N TRACKER (Spatial Fallback)
                # =========================================================
                if self.tracking_method == "Custom Force-N":
                    self.log_message.emit("Applying Custom Force-N tracking...")
                    tracked_detections = defaultdict(list)
                    
                    active_tracks = {t: {} for t in range(1, num_tanks + 1)}
                    
                    for frame_idx in range(total_frames):
                        if not self.is_running: break
                        if frame_idx % 1000 == 0: self.log_message.emit(f"Force-N Tracking - Frame: {frame_idx}/{total_frames}")
                        
                        ret, frame = cap.read()
                        if not ret: break
                        
                        dets_this_frame = raw_detections.get(frame_idx, [])
                        
                        for tank_num in range(1, num_tanks + 1):
                            tank_dets = [d for d in dets_this_frame if d.get('tank_number') == tank_num]
                            tank_dets.sort(key=lambda x: x.get('conf', 0.0), reverse=True)
                            tank_dets = tank_dets[:self.max_animals_per_tank]
                            
                            tank_active = active_tracks[tank_num]
                            
                            if len(tank_active) < self.max_animals_per_tank:
                                unassigned_dets = []
                                for det in tank_dets:
                                    new_id = len(tank_active) + 1
                                    if new_id <= self.max_animals_per_tank:
                                        det['track_id'] = new_id
                                        tank_active[new_id] = {'pos': (det['cx'], det['cy'])}
                                        tracked_detections[frame_idx].append(det)
                                    else:
                                        unassigned_dets.append(det)
                                tank_dets = unassigned_dets 
                            
                            if not tank_dets:
                                continue 
                                
                            track_ids = list(tank_active.keys())
                            cost_matrix = np.full((len(track_ids), len(tank_dets)), 1e6) 
                            
                            for i, tid in enumerate(track_ids):
                                last_pos = tank_active[tid]['pos']
                                for j, det in enumerate(tank_dets):
                                    dist = np.hypot(last_pos[0] - det['cx'], last_pos[1] - det['cy'])
                                    cost_matrix[i, j] = dist

                            row_ind, col_ind = linear_sum_assignment(cost_matrix)
                            
                            for r, c in zip(row_ind, col_ind):
                                tid = track_ids[r]
                                matched_det = tank_dets[c].copy()
                                matched_det['track_id'] = tid
                                tank_active[tid] = {'pos': (matched_det['cx'], matched_det['cy'])}
                                tracked_detections[frame_idx].append(matched_det)
                                
                    detections = tracked_detections

                elif is_boxmot_tracker:
                    self.log_message.emit(f"Applying {self.tracking_method} tracking...")
                    trackers = {i: create_tracker(self.tracking_method.lower(), **self.tracker_params) for i in range(1, num_tanks + 1)}
                    tracked_detections = defaultdict(list)
                    for frame_idx in range(total_frames):
                        if frame_idx % 1000 == 0: self.log_message.emit(f"Tracking Frame: {frame_idx}/{total_frames}")
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
                    self.log_message.emit(f"Applying Norfair tracking...")
                    trackers = {i: Tracker(**self.tracker_params, filter_factory=OptimizedKalmanFilterFactory()) for i in range(1, num_tanks + 1)}
                    tracked_detections = defaultdict(list)
                    
                    for frame_idx in range(total_frames):
                        if frame_idx % 1000 == 0: self.log_message.emit(f"Tracking Frame: {frame_idx}/{total_frames}")
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
                
                # Auto-stitch for Norfair/Boxmot using Hungarian Algorithm
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