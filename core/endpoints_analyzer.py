# EthoGrid_App/core/endpoints_analyzer.py

import math
import numpy as np
import pandas as pd
from collections import defaultdict
from PyQt5.QtCore import QPointF

EPSILON = 1e-10

# Helper functions (unchanged)
def calculate_turning_angle(p1, p2, p3):
    v1 = (p1[0] - p2[0], p1[1] - p2[1]); v2 = (p3[0] - p2[0], p3[1] - p2[1])
    dot_product = v1[0] * v2[0] + v1[1] * v2[1]; mag_v1 = math.sqrt(v1[0]**2 + v1[1]**2); mag_v2 = math.sqrt(v2[0]**2 + v2[1]**2)
    if mag_v1 * mag_v2 == 0: return 0.0
    cos_theta = max(-1.0, min(1.0, dot_product / (mag_v1 * mag_v2))); angle_rad = math.acos(cos_theta)
    return math.degrees(angle_rad)

def calculate_fractal_dimension_and_entropy(coords_df):
    x_list, y_list = coords_df['cx'], coords_df['cy']
    frames = len(x_list)
    if frames < 3: return 1.0, 0.0
    delta_x, delta_y, delta_r, thetas = {}, {}, {}, {}
    for i in range(1, frames):
        temp_x, temp_y = x_list.iloc[i] - x_list.iloc[i-1], y_list.iloc[i] - y_list.iloc[i-1]
        temp_r = math.sqrt(temp_x**2 + temp_y**2); delta_x[i], delta_y[i], delta_r[i] = temp_x, temp_y, temp_r
        if i > 1:
            dot = delta_x[i] * delta_x[i-1] + delta_y[i] * delta_y[i-1]; prod_mag = delta_r[i] * delta_r[i-1]
            value = dot / (prod_mag + EPSILON); thetas[i] = math.acos(max(-1, min(1, value))) * 180 / math.pi
    points = np.array(list(zip(x_list, y_list)))
    if len(points) < 2: return 1.0, 0.0
    min_coords, max_coords = np.min(points, axis=0), np.max(points, axis=0)
    size = np.max(max_coords - min_coords, initial=0.0)
    if size < 1e-6: return 1.0, 0.0
    log_size_half = np.log10(size / 2) if (size / 2) > 0 else 0
    scales = np.logspace(0.01, log_size_half, num=10, base=10.0)
    counts, valid_scales = [], []
    for scale in scales:
        if scale < 1e-6: continue
        H, _, _ = np.histogram2d(points[:, 0], points[:, 1], bins=(np.arange(min_coords[0], max_coords[0] + scale, scale), np.arange(min_coords[1], max_coords[1] + scale, scale)))
        counts.append(np.sum(H > 0)); valid_scales.append(scale)
    if len(counts) < 2: return 1.0, 0.0
    log_counts = np.log([c for c in counts if c > 0]); log_scales = np.log([s for i, s in enumerate(valid_scales) if counts[i] > 0])
    if len(log_counts) < 2: return 1.0, 0.0
    coeffs = np.polyfit(log_scales, log_counts, 1)
    fractal_dimension = -coeffs[0] if len(coeffs) > 0 and not np.isnan(coeffs[0]) else 1.0
    if not thetas: return fractal_dimension, 0.0
    G_array = np.array(list(thetas.values()))
    p1 = (G_array >= 90).sum() / G_array.size if G_array.size > 0 else 0
    p2 = 1.0 - p1; entropy = 0.0
    if p1 > 0: entropy -= p1 * np.log2(p1)
    if p2 > 0: entropy -= p2 * np.log2(p2)
    return fractal_dimension if not np.isnan(fractal_dimension) else 1.0, entropy if not np.isnan(entropy) else 0.0

class EndpointsAnalyzer:
    def __init__(self, detections_df, params):
        self.df = detections_df.copy()
        self.params = params
        self.results = {}
        self.tank_centers = self._calculate_tank_centers()
        self.tank_radii_px = self._calculate_tank_radii()

    def _calculate_tank_centers(self):
        w, h = self.params['video_width'], self.params['video_height']
        rows, cols = self.params['grid_rows'], self.params['grid_cols']
        transform = self.params['grid_transform']
        centers = {}
        for r in range(rows):
            for c in range(cols):
                tank_num = r * cols + c + 1
                center_x_local, center_y_local = (c + 0.5) * w / cols, (r + 0.5) * h / rows
                p = transform.map(QPointF(center_x_local, center_y_local))
                centers[tank_num] = (p.x(), p.y())
        return centers

    def _calculate_tank_radii(self):
        w, h = self.params['video_width'], self.params['video_height']
        rows, cols = self.params['grid_rows'], self.params['grid_cols']
        transform = self.params['grid_transform']
        radii = {}
        for r in range(rows):
            for c in range(cols):
                tank_num = r * cols + c + 1
                p1 = transform.map(QPointF(c * w / cols, r * h / rows))
                p2 = transform.map(QPointF((c + 1) * w / cols, r * h / rows))
                p3 = transform.map(QPointF(c * w / cols, (r + 1) * h / rows))
                transformed_width = math.sqrt((p2.x() - p1.x())**2 + (p2.y() - p1.y())**2)
                transformed_height = math.sqrt((p3.x() - p1.x())**2 + (p3.y() - p1.y())**2)
                shorter_dim = min(transformed_width, transformed_height)
                radii[tank_num] = (shorter_dim / 2.0) * (self.params['center_radius_percent'] / 100.0)
        return radii

    def analyze(self):
        self.df = self.df.sort_values(by='frame_idx').reset_index(drop=True)
        cx_np, cy_np, frame_idx_np = self.df['cx'].to_numpy(), self.df['cy'].to_numpy(), self.df['frame_idx'].to_numpy()
        
        # ### FULLY ROBUST CALCULATIONS ###

        # 1. Distance & Speed
        if len(cx_np) > 1:
            distances = np.sqrt(np.diff(cx_np)**2 + np.diff(cy_np)**2) / self.params['conversion_rate']
            self.results['Total Distance (cm)'] = np.sum(distances)
            frame_rate = self.params['frame_rate']
            time_intervals = np.diff(frame_idx_np) / frame_rate
            speeds = np.divide(distances, time_intervals, out=np.zeros_like(distances), where=time_intervals!=0)
            self.results['Average Speed (cm/s)'] = np.mean(speeds) if len(speeds) > 0 else 0.0
        else:
            self.results['Total Distance (cm)'] = 0.0
            speeds = np.array([])
            self.results['Average Speed (cm/s)'] = 0.0

        # 2. Freezing & Moving Time
        total_duration_of_tracking = (frame_idx_np[-1] - frame_idx_np[0]) / self.params['frame_rate'] if len(frame_idx_np) > 1 else 0.0
        if total_duration_of_tracking > 0:
            moving_mask = speeds > self.params['freezing_threshold']
            moving_time = np.sum(time_intervals[moving_mask])
            self.results['Moving Time (%)'] = (moving_time / total_duration_of_tracking) * 100
            self.results['Freezing Time (%)'] = 100.0 - self.results['Moving Time (%)']
        else:
            self.results['Moving Time (%)'] = 0.0
            self.results['Freezing Time (%)'] = 100.0 # If no duration, it was freezing the whole time
        
        # 3. Angular Calculations
        if len(cx_np) > 2:
            coords = np.column_stack((cx_np, cy_np))
            angles = [calculate_turning_angle(coords[i], coords[i+1], coords[i+2]) for i in range(len(coords) - 2)]
            self.results['Total Absolute Turn Angle (degree)'] = np.sum(np.abs(angles))
            angular_velocities = np.abs(angles) / (1 / self.params['frame_rate']) if self.params['frame_rate'] > 0 else np.zeros(len(angles))
            self.results['Average Angular Velocity (degree/s)'] = np.mean(angular_velocities)
            slow_angular_mask = angular_velocities <= self.params['slow_angular_velocity_threshold']
            self.results['Slow Angular Velocity Percentage (%)'] = np.sum(slow_angular_mask) / len(angular_velocities) * 100
            self.results['Fast Angular Velocity Percentage (%)'] = 100.0 - self.results['Slow Angular Velocity Percentage (%)']
        else:
            self.results['Total Absolute Turn Angle (degree)'] = 0.0
            self.results['Average Angular Velocity (degree/s)'] = 0.0
            self.results['Slow Angular Velocity Percentage (%)'] = 0.0
            self.results['Fast Angular Velocity Percentage (%)'] = 0.0
        
        # 4. Meandering
        self.results['Meandering (degree/m)'] = (self.results['Total Absolute Turn Angle (degree)'] / (self.results['Total Distance (cm)'] / 100)) if self.results['Total Distance (cm)'] > 0 else 0.0
        
        # 5. Center Zone Analysis
        def distance_to_tank_center(row):
            tank_num = int(row['tank_number'])
            if tank_num in self.tank_centers:
                center_x, center_y = self.tank_centers[tank_num]
                return np.sqrt((row['cx'] - center_x)**2 + (row['cy'] - center_y)**2)
            return np.nan
        self.df['dist_to_center_px'] = self.df.apply(distance_to_tank_center, axis=1)
        
        # Check for NaN before calculating mean
        if self.df['dist_to_center_px'].notna().any():
            self.results['Average distance to Center of the Tank (cm)'] = self.df['dist_to_center_px'].mean() / self.params['conversion_rate']
        else:
            self.results['Average distance to Center of the Tank (cm)'] = 0.0
        
        def check_in_center(row):
            tank_num = int(row['tank_number'])
            if tank_num in self.tank_radii_px:
                return row['dist_to_center_px'] <= self.tank_radii_px[tank_num]
            return False
        
        in_center_mask = self.df.apply(check_in_center, axis=1).to_numpy()
        time_in_center = np.sum(in_center_mask) / self.params['frame_rate']
        self.results['Time spent in Center (%)'] = (time_in_center / total_duration_of_tracking) * 100 if total_duration_of_tracking > 0 else 0.0
        entries = (in_center_mask[:-1] < in_center_mask[1:]).sum()
        self.results['Total entries to the Center (times)'] = entries
        
        # 6. Fractal Dimension and Entropy
        fd, entropy = calculate_fractal_dimension_and_entropy(self.df)
        self.results['Fractal Dimension'] = fd
        self.results['Entropy'] = entropy

        # Final check to replace any potential lingering NaNs from calculations
        final_results = {}
        for k, v in self.results.items():
            if isinstance(v, (float, np.floating)) and np.isnan(v):
                final_results[k] = 0.0
            else:
                final_results[k] = v

        return {k: f"{v:.4f}" if isinstance(v, (float, np.floating)) else v for k, v in final_results.items()}