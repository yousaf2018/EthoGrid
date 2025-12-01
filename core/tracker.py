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
    """
    Converts a list of detection dicts to a list of Norfair Detections.
    The 'frame' argument is no longer needed.
    """
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