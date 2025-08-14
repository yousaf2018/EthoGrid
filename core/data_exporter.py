# EthoGrid_App/core/data_exporter.py

import os
from collections import defaultdict

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

def export_centroid_csv(processed_detections, total_tanks, output_path):
    if not PANDAS_AVAILABLE:
        return "The 'pandas' library is required for this feature. Please run: pip install pandas"

    try:
        frame_data = defaultdict(dict)
        all_dets = [det for frame_dets in processed_detections.values() for det in frame_dets]
        
        for det in all_dets:
            if det.get('tank_number') is not None:
                frame = int(det['frame_idx'])
                tank = int(det['tank_number'])
                cx = det.get('cx', '')
                cy = det.get('cy', '')
                
                adjusted_tank = tank - 1
                if 0 <= adjusted_tank < total_tanks:
                    frame_data[frame][adjusted_tank] = (cx, cy)

        # ### THE CRITICAL FIX IS HERE ###
        # Ensure all keys are integers before sorting
        int_frame_data = {int(k): v for k, v in frame_data.items()}
        all_frames = sorted(int_frame_data.keys())

        if not all_frames:
             return "No valid detections with tank numbers found to export."

        output_rows = []
        for frame_idx in range(all_frames[0], all_frames[-1] + 1):
            row_dict = {'position': frame_idx}
            for tank_idx in range(total_tanks):
                if frame_idx in int_frame_data and tank_idx in int_frame_data[frame_idx]:
                    cx, cy = int_frame_data[frame_idx][tank_idx]
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
        import traceback
        print(traceback.format_exc())
        return f"An unexpected error occurred during centroid export: {e}"