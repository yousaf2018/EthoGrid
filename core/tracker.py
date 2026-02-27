# EthoGrid_App/core/tracker.py

import numpy as np

try:
    from norfair import Detection
    NORFAIR_AVAILABLE = True
except ImportError:
    NORFAIR_AVAILABLE = False
    class Detection:
        def __init__(self, **kwargs):
            pass

def to_norfair(detections):
    """Converts a list of detection dicts to a list of Norfair Detections."""
    if not NORFAIR_AVAILABLE:
        return []
    
    norfair_detections = []
    for det in detections:
        centroid = np.array([det['cx'], det['cy']])
        
        data = {
            "class_name": det.get('class_name', ''),
            "conf": det.get('conf', 0.0),
            "box": [det.get('x1',0), det.get('y1',0), det.get('x2',0), det.get('y2',0)],
            "polygon": det.get('polygon', '')
        }
        norfair_detections.append(Detection(points=centroid, data=data))
    return norfair_detections

def get_original_det(tracked_box, detections_in_frame):
    """
    Finds the original detection dict that is closest to the tracked bounding box center.
    This is used to retrieve metadata like class_name and polygon that the tracker might not preserve perfectly.
    """
    tx1, ty1, tx2, ty2 = tracked_box
    t_cx, t_cy = (tx1 + tx2) / 2, (ty1 + ty2) / 2
    
    min_dist = float('inf')
    best_match = {}
    
    if not detections_in_frame:
        return best_match

    for det in detections_in_frame:
        # Ensure cx, cy exist in the original detection (calculated if missing)
        det_cx = det.get('cx')
        det_cy = det.get('cy')
        
        if det_cx is None or det_cy is None:
             det_cx = (det.get("x1", 0) + det.get("x2", 0)) / 2.0
             det_cy = (det.get("y1", 0) + det.get("y2", 0)) / 2.0

        dist = np.sqrt((det_cx - t_cx)**2 + (det_cy - t_cy)**2)
        if dist < min_dist:
            min_dist = dist
            best_match = det
            
    return best_match