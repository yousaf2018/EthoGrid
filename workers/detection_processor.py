# EthoGrid_App/workers/detection_processor.py

from PyQt5.QtCore import QThread, pyqtSignal, QPointF

class DetectionProcessor(QThread):
    processing_finished = pyqtSignal(dict, dict)
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
            for frame_idx, dets in list(self.detections.items()):
                if not self._is_running: return
                for det in dets:
                    # Python's / operator produces a float, so precision is maintained here.
                    cx = (float(det["x1"]) + float(det["x2"])) / 2.0
                    cy = (float(det["y1"]) + float(det["y2"])) / 2.0
                    
                    det['cx'] = cx
                    det['cy'] = cy
                    
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