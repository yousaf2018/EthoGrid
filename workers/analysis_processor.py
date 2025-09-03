# EthoGrid_App/workers/analysis_processor.py

import os
import csv
import json
import traceback
import pandas as pd
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QTransform
from core.endpoints_analyzer import EndpointsAnalyzer

class AnalysisProcessor(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal()
    log = pyqtSignal(str)

    def __init__(self, csv_files, settings_path, params, output_dir, parent=None):
        super().__init__(parent)
        self.csv_files = csv_files
        self.settings_path = settings_path
        self.params = params
        self.output_dir = output_dir
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        total_files = len(self.csv_files)
        try:
            with open(self.settings_path, 'r') as f:
                settings_data = json.load(f)
            
            self.params['grid_rows'] = settings_data['grid_settings']['rows']
            self.params['grid_cols'] = settings_data['grid_settings']['cols']
            
            if 'video_dimensions' not in settings_data:
                self.log.emit("[ERROR] Your settings.json is outdated. Please re-save it from the main window after loading a video to include dimensions.")
                self.finished.emit()
                return
                
            self.params['video_width'] = settings_data['video_dimensions']['width']
            self.params['video_height'] = settings_data['video_dimensions']['height']

            transform_settings = settings_data['grid_transform']
            w, h = self.params['video_width'], self.params['video_height']
            
            final_transform = QTransform()
            final_transform.translate(w * transform_settings['center_x'], h * transform_settings['center_y'])
            final_transform.rotate(transform_settings['angle'])
            final_transform.scale(transform_settings['scale_x'], transform_settings['scale_y'])
            final_transform.translate(-w / 2, -h / 2)
            self.params['grid_transform'] = final_transform

        except KeyError as e:
            self.log.emit(f"[ERROR] Your settings.json file is missing a required key: {e}. Please re-save your settings from the main window after loading a video.")
            self.finished.emit()
            return
        except Exception as e:
            self.log.emit(f"[ERROR] Could not load or parse settings.json: {e}")
            self.finished.emit()
            return

        for i, file_path in enumerate(self.csv_files):
            if not self._is_running: self.log.emit("Analysis cancelled."); break
            
            filename = os.path.basename(file_path)
            self.progress.emit(i, total_files, filename)
            self.log.emit(f"\nAnalyzing file {i+1}/{total_files}: {filename}")

            try:
                df = pd.read_csv(file_path)
                required_cols = ['frame_idx', 'cx', 'cy', 'tank_number']
                if not all(col in df.columns for col in required_cols):
                    self.log.emit(f"[WARNING] Skipping {filename}: missing required columns."); continue
                
                file_results = []
                for tank_num in sorted(df['tank_number'].unique()):
                    if pd.isna(tank_num): continue
                    if not self._is_running: break
                    
                    self.log.emit(f"  - Processing Tank {int(tank_num)}...")
                    tank_df = df[df['tank_number'] == tank_num].copy()
                    
                    if len(tank_df) < 3:
                        self.log.emit(f"  - Skipping Tank {int(tank_num)}: not enough data points."); continue

                    analyzer = EndpointsAnalyzer(tank_df, self.params)
                    endpoints = analyzer.analyze()
                    
                    endpoints['File'] = filename; endpoints['Tank'] = int(tank_num)
                    file_results.append(endpoints)
                
                if file_results:
                    base_name = os.path.splitext(filename)[0].replace("_with_tanks", "")
                    output_filename = f"{base_name}_endpoints.csv"
                    output_path = os.path.join(self.output_dir, output_filename)
                    with open(output_path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=file_results[0].keys())
                        writer.writeheader(); writer.writerows(file_results)
                    self.log.emit(f"✓ Saved results to {output_filename}")
            except Exception as e:
                self.log.emit(f"[ERROR] Failed to process {filename}: {e}"); self.log.emit(traceback.format_exc()); continue
        
        if self._is_running:
            self.progress.emit(total_files, total_files, "Finished")
        
        self.finished.emit()