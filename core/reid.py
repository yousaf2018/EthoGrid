# EthoGrid_App/core/reid.py

import torch
import torchvision.models as models
import torchvision.transforms as T
import numpy as np
import cv2
from PIL import Image # NEW IMPORT for Pillow

class ReId:
    def __init__(self, device='cuda' if torch.cuda.is_available() else 'cpu'):
        self.device = device
        
        weights = models.ResNet50_Weights.DEFAULT
        self.model = models.resnet50(weights=weights)
        
        self.model.fc = torch.nn.Identity()
        self.model.to(self.device)
        self.model.eval()

        self.transform = weights.transforms()

    def get_embedding(self, rois):
        """ Get feature embeddings for a batch of Regions of Interest (ROIs) """
        if not rois:
            return None
            
        rois_transformed = []
        for roi_np in rois:
            # ### THE FIX IS HERE ###
            # 1. Convert OpenCV BGR NumPy array to RGB
            roi_rgb = cv2.cvtColor(roi_np, cv2.COLOR_BGR2RGB)
            # 2. Convert the RGB NumPy array to a PIL Image
            roi_pil = Image.fromarray(roi_rgb)
            # 3. Apply the transform to the PIL Image
            transformed_roi = self.transform(roi_pil)
            rois_transformed.append(transformed_roi)
        
        rois_tensor = torch.stack(rois_transformed).to(self.device)
        
        with torch.no_grad():
            embeddings = self.model(rois_tensor)
            
        return embeddings.cpu().numpy()