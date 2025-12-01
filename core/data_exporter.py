# EthoGrid_App/core/data_exporter.py

import os
import traceback
from collections import defaultdict
import cv2
import numpy as np
from PyQt5.QtCore import QPointF

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

def export_heatmap_image(processed_detections, video_path, output_path, time_gap_seconds, video_fps, frame_sample_rate):
    """
    Creates and saves a heatmap image superimposed on the first frame of the video,
    using only a subsample of the frames and respecting time gaps.
    """
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened(): return f"Could not open video file: {video_path}"
        ret, base_image = cap.read()
        if not ret: cap.release(); return f"Could not read the first frame of video: {video_path}"
        video_h, video_w, _ = base_image.shape
        cap.release()

        sampled_detections = {k: v for k, v in processed_detections.items() if k % frame_sample_rate == 0}
        
        points_by_animal = defaultdict(list)
        all_dets = [det for frame_dets in sampled_detections.values() for det in frame_dets]
        for det in all_dets:
            animal_id = det.get('track_id') or det.get('tank_number')
            if animal_id is not None and det.get('cx') is not None:
                points_by_animal[animal_id].append({
                    'frame_idx': int(det['frame_idx']),
                    'point': (int(det['cx']), int(det['cy']))
                })
        
        final_points_to_draw = []
        frame_gap_threshold = int(time_gap_seconds * video_fps) if video_fps > 0 else 1

        for animal_id, detections in sorted(points_by_animal.items()):
            detections.sort(key=lambda d: d['frame_idx'])
            if not detections: continue
            
            final_points_to_draw.append(detections[0]['point'])
            for i in range(1, len(detections)):
                if (detections[i]['frame_idx'] - detections[i-1]['frame_idx']) <= frame_gap_threshold:
                    final_points_to_draw.append(detections[i]['point'])

        heatmap_accumulator = np.zeros((video_h, video_w), dtype=np.float32)
        if final_points_to_draw:
            for (cx, cy) in final_points_to_draw:
                cv2.circle(heatmap_accumulator, (cx, cy), radius=20, color=1, thickness=-1)
        
        blurred_heatmap = cv2.GaussianBlur(heatmap_accumulator, (81, 81), 0)
        normalized_heatmap = cv2.normalize(blurred_heatmap, None, 0, 255, cv2.NORM_MINMAX, cv2.CV_8U)
        heatmap_img = cv2.applyColorMap(normalized_heatmap, cv2.COLORMAP_JET)
        super_imposed_img = cv2.addWeighted(heatmap_img, 0.5, base_image, 0.5, 0)
        
        bar_w, bar_h = 40, int(video_h * 0.5)
        bar_x, bar_y = video_w - bar_w - 20, (video_h - bar_h) // 2
        gradient = np.arange(0, 256, dtype=np.uint8)[::-1].reshape(256, 1)
        color_bar_jet = cv2.applyColorMap(gradient, cv2.COLORMAP_JET)
        color_bar_resized = cv2.resize(color_bar_jet, (bar_w, bar_h))
        super_imposed_img[bar_y:bar_y+bar_h, bar_x:bar_x+bar_w] = color_bar_resized
        cv2.rectangle(super_imposed_img, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (255,255,255), 2)
        cv2.putText(super_imposed_img, "High", (bar_x - 50, bar_y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
        cv2.putText(super_imposed_img, "Low", (bar_x - 40, bar_y + bar_h - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)

        cv2.imwrite(output_path, super_imposed_img)
        return None
    except Exception as e:
        print(traceback.format_exc()); return f"An unexpected error occurred during heatmap export: {e}"

def export_trajectory_image(processed_detections, grid_settings, video_size, grid_transform, output_path, time_gap_seconds, video_fps, frame_sample_rate):
    if video_fps <= 0: return "Cannot generate trajectories, video FPS is zero or invalid."
    try:
        video_w, video_h = video_size; cols, rows = grid_settings['cols'], grid_settings['rows']
        
        sampled_detections = {k: v for k, v in processed_detections.items() if k % frame_sample_rate == 0}
        
        untransformed_layer = np.full((video_h, video_w, 3), 255, dtype=np.uint8)
        padding = int(min(video_w, video_h) * 0.05) 
        draw_area_x1, draw_area_y1 = padding, padding
        draw_area_w, draw_area_h = video_w - (2 * padding), video_h - (2 * padding)
        cell_w, cell_h = draw_area_w / cols, draw_area_h / rows
        for r in range(rows):
            for c in range(cols):
                x1, y1 = int(draw_area_x1 + c * cell_w), int(draw_area_y1 + r * cell_h)
                x2, y2 = int(draw_area_x1 + (c + 1) * cell_w), int(draw_area_y1 + (r + 1) * cell_h)
                cv2.rectangle(untransformed_layer, (x1, y1), (x2, y2), (0, 0, 0), 2)
                tank_num = r * cols + c + 1
                cv2.putText(untransformed_layer, f"Tank {tank_num}", (x1 + 15, y1 + 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
        
        animal_paths = defaultdict(list)
        inverse_transform, _ = grid_transform.inverted()
        
        all_dets = [det for frame_dets in sampled_detections.values() for det in frame_dets]
        for det in all_dets:
            animal_id = det.get('track_id')
            if animal_id is None:
                animal_id = f"frame_{det['frame_idx']}_{det.get('tank_number', 'unknown')}"

            cx, cy = det.get('cx'), det.get('cy')
            if cx is not None and cy is not None:
                p = inverse_transform.map(QPointF(float(cx), float(cy)))
                scaled_x = draw_area_x1 + (p.x() / video_w) * draw_area_w
                scaled_y = draw_area_y1 + (p.y() / video_h) * draw_area_h
                animal_paths[animal_id].append({'frame_idx': int(det['frame_idx']), 'point': (scaled_x, scaled_y)})
        
        if animal_paths:
            unique_ids = sorted(animal_paths.keys())
            np.random.seed(42); colors = {uid: tuple(np.random.randint(0, 220, 3).tolist()) for uid in unique_ids}
            frame_gap_threshold = int(time_gap_seconds * video_fps) if video_fps > 0 else 1
            
            for animal_id, detections in animal_paths.items():
                detections.sort(key=lambda d: d['frame_idx'])
                if not detections: continue
                current_segment = [detections[0]['point']]
                for i in range(1, len(detections)):
                    prev_det_frame = detections[i-1]['frame_idx']; curr_det_frame = detections[i]['frame_idx']
                    if (curr_det_frame - prev_det_frame) > frame_gap_threshold:
                        if len(current_segment) > 1:
                            pts = np.array(current_segment, np.int32).reshape((-1, 1, 2)); cv2.polylines(untransformed_layer, [pts], isClosed=False, color=colors[animal_id], thickness=2)
                        current_segment = [detections[i]['point']]
                    else:
                        current_segment.append(detections[i]['point'])
                if len(current_segment) > 1:
                    pts = np.array(current_segment, np.int32).reshape((-1, 1, 2)); cv2.polylines(untransformed_layer, [pts], isClosed=False, color=colors[animal_id], thickness=2)
        
        M = np.float32([[grid_transform.m11(), grid_transform.m12(), grid_transform.dx()], [grid_transform.m21(), grid_transform.m22(), grid_transform.dy()]])
        final_image = cv2.warpAffine(untransformed_layer, M, (video_w, video_h), borderValue=(255, 255, 255))
        cv2.imwrite(output_path, final_image)
        return None
    except Exception as e:
        print(traceback.format_exc()); return f"An unexpected error occurred during trajectory image export: {e}"

def export_centroid_csv(processed_detections, total_tanks, output_path):
    if not PANDAS_AVAILABLE: return "The 'pandas' library is required. Please run: pip install pandas"
    try:
        frame_data = defaultdict(dict)
        all_dets = [det for frame_dets in processed_detections.values() for det in frame_dets]
        
        for det in all_dets:
            if det.get('tank_number') is not None:
                frame, tank = int(det['frame_idx']), int(det['tank_number'])
                cx, cy = det.get('cx', ''), det.get('cy', '')
                track_id = det.get('track_id')
                # Create a unique column key for each track in each tank
                animal_key = f"tank_{tank}_track_{int(track_id)}" if track_id is not None else f"tank_{tank}_detection"
                frame_data[frame][animal_key] = (cx, cy)
        
        all_frames = sorted(frame_data.keys())
        if not all_frames: return "No valid detections found to export."
        
        all_animal_ids = sorted(list(set(key for frame in frame_data.values() for key in frame.keys())))
        
        output_rows = []
        for frame_idx in range(all_frames[0], all_frames[-1] + 1):
            row_dict = {'frame': frame_idx}
            frame_info = frame_data.get(frame_idx, {})
            for animal_id in all_animal_ids:
                cx, cy = frame_info.get(animal_id, ('', ''))
                row_dict[f'{animal_id}_x'] = cx
                row_dict[f'{animal_id}_y'] = cy
            output_rows.append(row_dict)
        
        output_df = pd.DataFrame(output_rows)
        output_df.to_csv(output_path, index=False, float_format='%.4f')
        return None
    except Exception as e:
        print(traceback.format_exc()); return f"An unexpected error occurred during centroid export: {e}"

def export_to_excel_sheets(processed_detections, output_path):
    if not PANDAS_AVAILABLE: return "The 'pandas' and 'openpyxl' libraries are required. Please run: pip install pandas openpyxl"
    try:
        # ### THE FIX IS HERE ###
        # Correctly flatten the dictionary of lists into a single list
        all_dets = [det for frame_dets in processed_detections.values() for det in frame_dets]

        if not all_dets: return "No detections found to export."
        
        # Group by track_id if it exists, otherwise fall back to tank_number
        use_track_id = 'track_id' in all_dets[0]
        group_key = 'track_id' if use_track_id else 'tank_number'
        
        animal_data = defaultdict(list)
        for det in all_dets:
            key = det.get(group_key)
            if key is not None:
                animal_data[int(key)].append(det)

        if not animal_data: return "No detections found to group and export."
        
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            for animal_id in sorted(animal_data.keys()):
                sheet_name = f"Track_{animal_id}" if use_track_id else f"Tank_{animal_id}"
                animal_df = pd.DataFrame(animal_data[animal_id])
                for col in ['x1', 'y1', 'x2', 'y2', 'cx', 'cy', 'conf']:
                    if col in animal_df.columns: animal_df[col] = pd.to_numeric(animal_df[col], errors='coerce')
                animal_df.to_excel(writer, sheet_name=sheet_name, index=False, float_format='%.4f')
        return None
    except Exception as e:
        print(traceback.format_exc()); return f"An unexpected error occurred during Excel export: {e}"