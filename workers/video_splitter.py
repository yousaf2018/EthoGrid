# EthoGrid_App/workers/video_splitter.py

import os
import re
import subprocess
import traceback
from PyQt5.QtCore import QThread, pyqtSignal

class VideoSplitter(QThread):
    overall_progress = pyqtSignal(int, int, str)
    file_progress = pyqtSignal(int, str)
    log_message = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, video_files, output_dir, chunk_seconds, use_subfolders, parent=None):
        super().__init__(parent)
        self.video_files = video_files
        self.output_dir = output_dir
        self.chunk_seconds = chunk_seconds
        self.use_subfolders = use_subfolders
        self.is_running = True
        self.process = None

    def stop(self):
        self.log_message.emit("Stopping split process...")
        self.is_running = False
        if hasattr(self, 'process') and self.process.poll() is None:
            self.process.terminate()

    def _check_ffmpeg(self):
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            # Check for both ffmpeg and ffprobe
            subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, startupinfo=startupinfo)
            subprocess.run(["ffprobe", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, startupinfo=startupinfo)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def run(self):
        if not self._check_ffmpeg():
            self.error.emit("FFmpeg/FFprobe not found. Please install FFmpeg and ensure it's in your system's PATH.")
            return

        total_files = len(self.video_files)
        for i, video_path in enumerate(self.video_files):
            if not self.is_running: break
            
            filename = os.path.basename(video_path)
            self.overall_progress.emit(i + 1, total_files, filename)
            self.log_message.emit(f"\n--- Starting to process: {filename} ---")

            try:
                # 1. Get video duration using ffprobe
                cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path]
                
                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, startupinfo=startupinfo)
                duration = float(result.stdout.strip())
                self.log_message.emit(f"  - Video duration: {duration:.2f} seconds")

                if self.chunk_seconds <= 0:
                    self.log_message.emit("[ERROR] Chunk duration must be greater than zero. Skipping.")
                    continue

                num_chunks = int(duration // self.chunk_seconds) + (1 if duration % self.chunk_seconds > 1 else 0)
                
                # Split the filename and extension to ensure the output matches the input format
                base_name, extension = os.path.splitext(filename)
                current_output_dir = os.path.join(self.output_dir, base_name) if self.use_subfolders else self.output_dir
                os.makedirs(current_output_dir, exist_ok=True)
                
                for chunk_idx in range(num_chunks):
                    if not self.is_running: break
                    
                    start_time = chunk_idx * self.chunk_seconds
                    # Use the original extension instead of hardcoded .mp4
                    output_file = os.path.join(current_output_dir, f"{base_name}_part_{chunk_idx+1:02d}{extension}")
                    self.log_message.emit(f"  ▶ Splitting Part {chunk_idx+1}/{num_chunks} -> {os.path.basename(output_file)}")
                    
                    cmd = ["ffmpeg", "-ss", str(start_time), "-i", video_path, "-t", str(self.chunk_seconds), "-c", "copy", output_file, "-y", "-progress", "pipe:1"]
                    self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True, startupinfo=startupinfo)
                    
                    total_frames_in_chunk = self.chunk_seconds * 30
                    while self.process.poll() is None:
                        if not self.is_running: self.process.terminate(); break
                        
                        line = self.process.stdout.readline()
                        if "total_size" in line:
                            self.file_progress.emit(100, f"Part {chunk_idx+1}/{num_chunks} Complete")
                        elif "frame=" in line:
                            current_frame = int(line.strip().split('=')[-1])
                            progress = min(100, int(current_frame * 100 / total_frames_in_chunk)) if total_frames_in_chunk > 0 else 0
                            self.file_progress.emit(progress, f"Part {chunk_idx+1}/{num_chunks} | Frame: {current_frame}")
                    self.process.wait()
                    if self.is_running: self.log_message.emit(f"  ✓ Saved: {os.path.basename(output_file)}")
                    else: self.log_message.emit(f"  ✗ Cancelled split for: {os.path.basename(output_file)}")

            # ### THE FIX IS HERE ###
            # Catch the specific error from ffprobe and provide a better message
            except subprocess.CalledProcessError as e:
                error_details = e.stderr.strip()
                log_msg = (f"[ERROR] Failed to read video properties for {filename}.\n"
                           f"  - Reason: The file may be corrupt, in an unsupported format, or have incorrect permissions.\n"
                           f"  - The file will be skipped.")
                if error_details:
                    log_msg += f"\n  - FFprobe Details: {error_details}"
                self.log_message.emit(log_msg)
                continue # Explicitly continue to the next file

            except Exception as e:
                self.log_message.emit(f"[ERROR] An unexpected error occurred while processing {filename}: {e}")
                self.log_message.emit(traceback.format_exc())
                continue
        
        if self.is_running: self.log_message.emit("\n--- Video splitting complete! ---")
        else: self.log_message.emit("\n--- Video splitting cancelled by user. ---")
        self.finished.emit()