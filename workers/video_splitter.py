import os
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
        if self.process and self.process.poll() is None:
            self.process.terminate()

    # --------------------------------------------------
    # FFmpeg availability check
    # --------------------------------------------------
    def _check_ffmpeg(self):
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            subprocess.run(
                ["ffmpeg", "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                startupinfo=startupinfo
            )
            subprocess.run(
                ["ffprobe", "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                startupinfo=startupinfo
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    # --------------------------------------------------
    # Detect unsafe formats for -c copy
    # --------------------------------------------------
    def _needs_reencode(self, video_path):
        """
        Returns True if stream copy is unsafe (e.g., H.264 High Profile)
        """
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name,profile",
                "-of", "default=nokey=1:noprint_wrappers=1",
                video_path
            ]

            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                startupinfo=startupinfo
            )

            info = result.stdout.lower()

            if "h264" in info and (
                "high" in info or
                "high 10" in info or
                "high 4:2:2" in info
            ):
                return True

            return False

        except Exception:
            # If probe fails, choose safe path
            return True

    # --------------------------------------------------
    # Main thread execution
    # --------------------------------------------------
    def run(self):
        if not self._check_ffmpeg():
            self.error.emit(
                "FFmpeg / FFprobe not found. Please install FFmpeg and add it to PATH."
            )
            return

        total_files = len(self.video_files)

        for i, video_path in enumerate(self.video_files):
            if not self.is_running:
                break

            filename = os.path.basename(video_path)
            self.overall_progress.emit(i + 1, total_files, filename)
            self.log_message.emit(f"\n--- Starting to process: {filename} ---")

            try:
                # --------------------------------------
                # Get video duration
                # --------------------------------------
                cmd = [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=nokey=1:noprint_wrappers=1",
                    video_path
                ]

                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                    startupinfo=startupinfo
                )

                duration = float(result.stdout.strip())
                self.log_message.emit(f"  - Video duration: {duration:.2f} seconds")

                if self.chunk_seconds <= 0:
                    self.log_message.emit("[ERROR] Chunk duration must be > 0. Skipping.")
                    continue

                num_chunks = int(duration // self.chunk_seconds)
                if duration % self.chunk_seconds > 1:
                    num_chunks += 1

                base_name = os.path.splitext(filename)[0]
                current_output_dir = (
                    os.path.join(self.output_dir, base_name)
                    if self.use_subfolders else self.output_dir
                )
                os.makedirs(current_output_dir, exist_ok=True)

                # --------------------------------------
                # Detect if re-encoding is required
                # --------------------------------------
                needs_reencode = self._needs_reencode(video_path)

                if needs_reencode:
                    self.log_message.emit(
                        "  ⚠ Detected H.264 High Profile – using safe re-encoding"
                    )

                # --------------------------------------
                # Split loop
                # --------------------------------------
                for chunk_idx in range(num_chunks):
                    if not self.is_running:
                        break

                    start_time = chunk_idx * self.chunk_seconds
                    output_file = os.path.join(
                        current_output_dir,
                        f"{base_name}_part_{chunk_idx + 1:02d}.mp4"
                    )

                    self.log_message.emit(
                        f"  ▶ Splitting Part {chunk_idx + 1}/{num_chunks} -> "
                        f"{os.path.basename(output_file)}"
                    )

                    if needs_reencode:
                        # -------- SAFE RE-ENCODE PATH --------
                        cmd = [
                            "ffmpeg",
                            "-ss", str(start_time),
                            "-i", video_path,
                            "-t", str(self.chunk_seconds),
                            "-map", "0",
                            "-c:v", "libx264",
                            "-preset", "veryfast",
                            "-crf", "18",
                            "-pix_fmt", "yuv420p",
                            "-movflags", "+faststart",
                            "-c:a", "aac",
                            "-y",
                            output_file
                        ]

                        self.process = subprocess.Popen(
                            cmd,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            startupinfo=startupinfo
                        )

                        self.process.wait()
                        self.file_progress.emit(
                            100, f"Part {chunk_idx + 1}/{num_chunks} Complete"
                        )

                    else:
                        # -------- ORIGINAL COPY PATH --------
                        cmd = [
                            "ffmpeg",
                            "-ss", str(start_time),
                            "-i", video_path,
                            "-t", str(self.chunk_seconds),
                            "-c", "copy",
                            "-y",
                            "-progress", "pipe:1",
                            output_file
                        ]

                        self.process = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL,
                            universal_newlines=True,
                            startupinfo=startupinfo
                        )

                        total_frames_in_chunk = self.chunk_seconds * 30  # unchanged logic

                        while self.process.poll() is None:
                            if not self.is_running:
                                self.process.terminate()
                                break

                            line = self.process.stdout.readline()
                            if "frame=" in line:
                                try:
                                    current_frame = int(line.split("=")[-1])
                                    progress = min(
                                        100,
                                        int(current_frame * 100 / total_frames_in_chunk)
                                    )
                                    self.file_progress.emit(
                                        progress,
                                        f"Part {chunk_idx + 1}/{num_chunks} | "
                                        f"Frame: {current_frame}"
                                    )
                                except ValueError:
                                    pass
                            elif "total_size" in line:
                                self.file_progress.emit(
                                    100,
                                    f"Part {chunk_idx + 1}/{num_chunks} Complete"
                                )

                        self.process.wait()

                    if self.is_running:
                        self.log_message.emit(
                            f"  ✓ Saved: {os.path.basename(output_file)}"
                        )
                    else:
                        self.log_message.emit(
                            f"  ✗ Cancelled: {os.path.basename(output_file)}"
                        )

            except subprocess.CalledProcessError as e:
                msg = (
                    f"[ERROR] Failed to read video properties for {filename}.\n"
                    f"  - File may be corrupt or unsupported."
                )
                if e.stderr:
                    msg += f"\n  - FFprobe: {e.stderr.strip()}"
                self.log_message.emit(msg)
                continue

            except Exception as e:
                self.log_message.emit(
                    f"[ERROR] Unexpected error for {filename}: {e}"
                )
                self.log_message.emit(traceback.format_exc())
                continue

        if self.is_running:
            self.log_message.emit("\n--- Video splitting complete! ---")
        else:
            self.log_message.emit("\n--- Video splitting cancelled by user. ---")

        self.finished.emit()
