# EthoGrid_App/workers/track_corrector_worker.py

from PyQt5.QtCore import QThread, pyqtSignal
import pandas as pd
import numpy as np

class TrackCorrectorWorker(QThread):
    finished = pyqtSignal(pd.DataFrame)
    log = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self, df, operation, params, parent=None):
        super().__init__(parent)
        self.df = df.copy()
        self.operation = operation
        self.params = params
        
        # Ensure a global_id exists for safe manipulation
        if 'global_id' not in self.df.columns:
            self.df['global_id'] = self.df.apply(
                lambda row: f"{int(row['tank_number'])}_{int(row['track_id'])}", axis=1
            )

    def run(self):
        try:
            if self.operation == 'swap':
                self.log.emit("Performing ID Swap...")
                self._perform_swap()
            elif self.operation == 'stitch_list':
                self.log.emit(f"Stitching IDs...")
                self._perform_stitch_list()
            elif self.operation == 'delete':
                self.log.emit("Performing Track Deletion...")
                self._perform_delete()
            elif self.operation == 'enforce_max':
                self._enforce_max_animals()
            elif self.operation == 'interpolate':
                self._perform_interpolation()
            
            self.log.emit("Operation complete.")
            self.finished.emit(self.df)
        except Exception as e:
            self.error.emit(f"Failed to perform {self.operation}: {e}")

    def _perform_swap(self):
        frame_idx = self.params['frame_idx']
        gid1 = self.params['global_id1']
        gid2 = self.params['global_id2']
        
        mask1 = (self.df['frame_idx'] >= frame_idx) & (self.df['global_id'] == gid1)
        mask2 = (self.df['frame_idx'] >= frame_idx) & (self.df['global_id'] == gid2)
        
        id1_indices = self.df[mask1].index
        id2_indices = self.df[mask2].index
        
        self.df.loc[id1_indices, 'global_id'] = gid2
        self.df.loc[id2_indices, 'global_id'] = gid1
        
        self.df.loc[id1_indices, 'track_id'] = int(gid2.split('_')[1])
        self.df.loc[id2_indices, 'track_id'] = int(gid1.split('_')[1])

    def _perform_stitch_list(self):
        target_gid = self.params['target_global_id']
        merge_gids = self.params['merge_global_ids']
        
        mask = self.df['global_id'].isin(merge_gids)
        self.df.loc[mask, 'global_id'] = target_gid
        self.df.loc[mask, 'track_id'] = int(target_gid.split('_')[1])

    def _perform_delete(self):
        frame_idx = self.params['frame_idx']
        gid_to_delete = self.params['global_id_to_delete']
        
        indices_to_drop = self.df[(self.df['frame_idx'] >= frame_idx) & (self.df['global_id'] == gid_to_delete)].index
        self.df.drop(indices_to_drop, inplace=True)

    def _enforce_max_animals(self):
        max_animals = self.params['max_animals']
        total_frames = int(self.df['frame_idx'].max())
        self.log.emit(f"Starting auto-correction to enforce max {max_animals} animals per tank...")
        
        track_ages = self.df.groupby('global_id')['frame_idx'].count().to_dict()
        
        for frame_idx in range(total_frames + 1):
            if not self.isInterruptionRequested():
                if frame_idx % 100 == 0: self.progress.emit(int(frame_idx * 100 / total_frames))
                
                frame_df = self.df[self.df['frame_idx'] == frame_idx]
                if frame_df.empty: continue
                
                for tank_num in frame_df['tank_number'].dropna().unique():
                    tank_dets = frame_df[frame_df['tank_number'] == tank_num]
                    active_tracks = tank_dets['global_id'].tolist()
                    
                    if len(active_tracks) > max_animals:
                        active_tracks.sort(key=lambda gid: track_ages.get(gid, 0), reverse=True)
                        primary_tracks = active_tracks[:max_animals]
                        ghost_tracks = active_tracks[max_animals:]
                        
                        for g_track in ghost_tracks:
                            ghost_det = tank_dets[tank_dets['global_id'] == g_track].iloc[0]
                            min_dist = float('inf')
                            best_primary_match = primary_tracks[0]
                            
                            for p_track in primary_tracks:
                                primary_det = tank_dets[tank_dets['global_id'] == p_track].iloc[0]
                                dist = np.sqrt((ghost_det['cx'] - primary_det['cx'])**2 + (ghost_det['cy'] - primary_det['cy'])**2)
                                if dist < min_dist:
                                    min_dist = dist
                                    best_primary_match = p_track
                            
                            self.df.loc[self.df['global_id'] == g_track, 'track_id'] = int(best_primary_match.split('_')[1])
                            self.df.loc[self.df['global_id'] == g_track, 'global_id'] = best_primary_match
            else:
                break
        self.progress.emit(100)

    def _perform_interpolation(self):
        method = self.params['method']
        limit = self.params['limit']
        max_animals = self.params['max_animals']
        
        self.log.emit(f"Applying {method} interpolation (Max Gap: {limit} frames) based on {max_animals} animals per tank...")
        
        if self.df.empty: return

        # 1. Clean data: Ensure unique rows per track per frame
        self.df['frame_idx'] = pd.to_numeric(self.df['frame_idx'], errors='coerce')
        self.df = self.df.dropna(subset=['frame_idx'])
        self.df['frame_idx'] = self.df['frame_idx'].astype(int)
        self.df = self.df.sort_values(by=['frame_idx', 'global_id'])
        self.df = self.df.drop_duplicates(subset=['frame_idx', 'global_id'], keep='first')

        global_first_frame = int(self.df['frame_idx'].min())
        global_last_frame = int(self.df['frame_idx'].max())
        full_index = pd.Index(range(global_first_frame, global_last_frame + 1), name='frame_idx')

        interpolated_dfs = []
        
        # ### THE FIX IS HERE ###
        # Group by TANK first, then only process the top 'max_animals' tracks
        all_tanks = self.df['tank_number'].dropna().unique()

        for tank_idx, tank_num in enumerate(all_tanks):
            if self.isInterruptionRequested(): break
            self.progress.emit(int((tank_idx + 1) * 100 / len(all_tanks)))
            
            tank_df = self.df[self.df['tank_number'] == tank_num].copy()
            if tank_df.empty: continue
            
            # Identify the primary tracks for this tank (most frequent)
            # Only interpolate these. Ignore short-lived ghost tracks.
            track_counts = tank_df['global_id'].value_counts()
            primary_gids = track_counts.nlargest(max_animals).index.tolist()
            
            for gid in primary_gids:
                animal_df = tank_df[tank_df['global_id'] == gid].copy()
                
                animal_df.set_index('frame_idx', inplace=True)
                animal_df = animal_df.reindex(full_index)

                numeric_cols = ['cx', 'cy', 'x1', 'y1', 'x2', 'y2']
                existing_num_cols = [col for col in numeric_cols if col in animal_df.columns]
                
                if existing_num_cols:
                    if method == 'linear':
                        animal_df[existing_num_cols] = animal_df[existing_num_cols].interpolate(method='linear', limit=limit, limit_direction='forward')
                    elif method == 'ffill':
                        animal_df[existing_num_cols] = animal_df[existing_num_cols].ffill(limit=limit)
                    elif method == 'bfill':
                        animal_df[existing_num_cols] = animal_df[existing_num_cols].bfill(limit=limit)

                meta_cols = ['tank_number', 'track_id', 'class_name', 'conf', 'polygon', 'global_id']
                existing_meta_cols = [col for col in meta_cols if col in animal_df.columns]
                
                if existing_meta_cols:
                    animal_df[existing_meta_cols] = animal_df[existing_meta_cols].ffill(limit=limit).bfill(limit=limit)

                animal_df.dropna(subset=['cx'], inplace=True)
                interpolated_dfs.append(animal_df.reset_index())

        if interpolated_dfs:
            self.df = pd.concat(interpolated_dfs, ignore_index=True)
            self.df = self.df.sort_values(by=['frame_idx', 'global_id']).reset_index(drop=True)
            
            if 'tank_number' in self.df.columns:
                self.df['tank_number'] = self.df['tank_number'].fillna(-1).astype(int)
            if 'track_id' in self.df.columns:
                self.df['track_id'] = self.df['track_id'].fillna(-1).astype(int)

        self.progress.emit(100)