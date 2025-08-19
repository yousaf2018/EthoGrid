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

def export_trajectory_image(processed_detections, grid_settings, video_size, grid_transform, output_path, time_gap_seconds, video_fps):
    if video_fps <= 0:
        return "Cannot generate trajectories, video FPS is zero or invalid."
    try:
        video_w, video_h = video_size
        cols, rows = grid_settings['cols'], grid_settings['rows']
        untransformed_layer = np.full((video_h, video_w, 3), 255, dtype=np.uint8)
        padding = int(min(video_w, video_h) * 0.05) 
        draw_area_x1, draw_area_y1 = padding, padding
        draw_area_w, draw_area_h = video_w - (2 * padding), video_h - (2 * padding)
        cell_w, cell_h = draw_area_w / cols, draw_area_h / rows
        for r in range(rows):
            for c in range(cols):
                x1 = int(draw_area_x1 + c * cell_w)
                y1 = int(draw_area_y1 + r * cell_h)
                x2 = int(draw_area_x1 + (c + 1) * cell_w)
                y2 = int(draw_area_y1 + (r + 1) * cell_h)
                cv2.rectangle(untransformed_layer, (x1, y1), (x2, y2), (0, 0, 0), 2)
                tank_num = r * cols + c + 1
                cv2.putText(untransformed_layer, f"Tank {tank_num}", (x1 + 15, y1 + 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
        tank_points = defaultdict(list)
        all_dets = [det for frame_dets in processed_detections.values() for det in frame_dets]
        inverse_transform, _ = grid_transform.inverted()
        for det in all_dets:
            tank_num, cx, cy = det.get('tank_number'), det.get('cx'), det.get('cy')
            if tank_num is not None and cx is not None and cy is not None:
                p = inverse_transform.map(QPointF(float(cx), float(cy)))
                scaled_x = draw_area_x1 + (p.x() / video_w) * draw_area_w
                scaled_y = draw_area_y1 + (p.y() / video_h) * draw_area_h
                tank_points[int(tank_num)].append({'frame_idx': int(det['frame_idx']), 'point': (scaled_x, scaled_y)})
        if tank_points:
            np.random.seed(42)
            colors = {tank_num: tuple(np.random.randint(0, 200, 3).tolist()) for tank_num in tank_points.keys()}
            frame_gap_threshold = int(time_gap_seconds * video_fps)
            for tank_num, detections in sorted(tank_points.items()):
                detections.sort(key=lambda d: d['frame_idx'])
                if not detections: continue
                current_segment = [detections[0]['point']]
                for i in range(1, len(detections)):
                    prev_det, curr_det = detections[i-1], detections[i]
                    if (curr_det['frame_idx'] - prev_det['frame_idx']) > frame_gap_threshold:
                        if len(current_segment) > 1:
                            pts = np.array(current_segment, np.int32).reshape((-1, 1, 2))
                            cv2.polylines(untransformed_layer, [pts], isClosed=False, color=colors[tank_num], thickness=2)
                        current_segment = [curr_det['point']]
                    else:
                        current_segment.append(curr_det['point'])
                if len(current_segment) > 1:
                    pts = np.array(current_segment, np.int32).reshape((-1, 1, 2))
                    cv2.polylines(untransformed_layer, [pts], isClosed=False, color=colors[tank_num], thickness=2)
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
                adjusted_tank = tank - 1
                if 0 <= adjusted_tank < total_tanks:
                    frame_data[frame][adjusted_tank] = (cx, cy)
        
        int_frame_data = {int(k): v for k, v in frame_data.items()}
        all_frames = sorted(int_frame_data.keys())
        if not all_frames: return "No valid detections with tank numbers found to export."
        
        output_rows = []
        for frame_idx in range(all_frames[0], all_frames[-1] + 1):
            row_dict = {'position': frame_idx}
            for tank_idx in range(total_tanks):
                # ### THE FIX IS HERE ###
                # Use .get() for safe dictionary access to prevent errors
                tank_coords = int_frame_data.get(frame_idx, {}).get(tank_idx)
                
                if tank_coords:
                    cx, cy = tank_coords
                    cx_str = f"{cx:.4f}" if isinstance(cx, float) else cx
                    cy_str = f"{cy:.4f}" if isinstance(cy, float) else cy
                else:
                    cx_str, cy_str = '', ''
                row_dict[f'x{tank_idx}'] = cx_str
                row_dict[f'y{tank_idx}'] = cy_str
            output_rows.append(row_dict)

        output_df = pd.DataFrame(output_rows)
        output_df.to_csv(output_path, index=False)
        return None
    except Exception as e:
        print(traceback.format_exc())
        return f"An unexpected error occurred during centroid export: {e}"

def export_to_excel_sheets(processed_detections, output_path):
    if not PANDAS_AVAILABLE: return "The 'pandas' and 'openpyxl' libraries are required. Please run: pip install pandas openpyxl"
    try:
        tank_data = defaultdict(list)
        all_dets = [det for frame_dets in processed_detections.values() for det in frame_dets]
        for det in all_dets:
            tank_num = det.get('tank_number')
            if tank_num is not None:
                tank_data[int(tank_num)].append(det)
        if not tank_data:
            return "No detections with tank numbers found to export."
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            for tank_num in sorted(tank_data.keys()):
                sheet_name = f'Tank_{tank_num}'
                tank_df = pd.DataFrame(tank_data[tank_num])
                for col in ['x1', 'y1', 'x2', 'y2', 'cx', 'cy', 'conf']:
                    if col in tank_df.columns:
                        tank_df[col] = pd.to_numeric(tank_df[col], errors='coerce').map(lambda x: f'{x:.4f}' if pd.notnull(x) else '')
                if 'tank_number' in tank_df.columns:
                    tank_df = tank_df.drop(columns=['tank_number'])
                tank_df.to_excel(writer, sheet_name=sheet_name, index=False)
        return None
    except Exception as e:
        print(traceback.format_exc())
        return f"An unexpected error occurred during Excel export: {e}"