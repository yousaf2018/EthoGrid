# EthoGrid_App/widgets/analysis_dialog.py

import os, csv
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import QThread
from workers.analysis_processor import AnalysisProcessor

class AnalysisDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Endpoints Analysis"); self.setMinimumSize(700, 750)
        self.csv_files, self.analysis_thread, self.analysis_worker = [], None, None

        self.file_list_widget = QtWidgets.QListWidget()
        self.add_files_btn = QtWidgets.QPushButton("Add CSV Files...")
        self.output_dir_line_edit = QtWidgets.QLineEdit(); self.output_dir_line_edit.setPlaceholderText("Select a folder to save the output files")
        self.browse_output_btn = QtWidgets.QPushButton("Browse...")
        self.settings_line_edit = QtWidgets.QLineEdit(); self.settings_line_edit.setPlaceholderText("Select the settings.json file used for grid annotation")
        self.browse_settings_btn = QtWidgets.QPushButton("Browse...")
        
        self.param_frame_rate = QtWidgets.QDoubleSpinBox(value=30.0, maximum=300.0)
        self.param_conversion_rate = QtWidgets.QDoubleSpinBox(value=100.0, maximum=5000.0, toolTip="Pixels per cm")
        self.param_freezing_threshold = QtWidgets.QDoubleSpinBox(value=0.2, maximum=10.0, singleStep=0.1, toolTip="cm/s")
        self.param_angular_threshold = QtWidgets.QDoubleSpinBox(value=90.0, maximum=180.0, toolTip="degrees/s")
        self.param_center_radius_percent = QtWidgets.QSpinBox(value=50, maximum=100, toolTip="Radius of center zone as a percentage of the tank's shorter dimension")

        self.start_btn = QtWidgets.QPushButton("Start Analysis"); self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.progress_bar = QtWidgets.QProgressBar(); self.progress_label = QtWidgets.QLabel("Waiting to start...")
        self.log_text_edit = QtWidgets.QTextEdit(); self.log_text_edit.setReadOnly(True)

        main_layout = QtWidgets.QVBoxLayout(self)
        input_group = QtWidgets.QGroupBox("Inputs & Parameters")
        form_layout = QtWidgets.QFormLayout(input_group)
        file_layout = QtWidgets.QHBoxLayout(); file_layout.addWidget(self.file_list_widget); file_layout.addWidget(self.add_files_btn)
        form_layout.addRow(QtWidgets.QLabel("Input CSV Files ('_with_tanks.csv'):"), file_layout)
        output_layout = QtWidgets.QHBoxLayout(); output_layout.addWidget(self.output_dir_line_edit); output_layout.addWidget(self.browse_output_btn)
        form_layout.addRow(QtWidgets.QLabel("Output Folder:"), output_layout)
        settings_layout = QtWidgets.QHBoxLayout(); settings_layout.addWidget(self.settings_line_edit); settings_layout.addWidget(self.browse_settings_btn)
        form_layout.addRow("Grid Settings File (.json):", settings_layout)
        
        params_group = QtWidgets.QGroupBox("Analysis Parameters")
        params_layout = QtWidgets.QFormLayout(params_group)
        params_layout.addRow("Frame Rate (FPS):", self.param_frame_rate)
        params_layout.addRow("Conversion Rate (pixels/cm):", self.param_conversion_rate)
        params_layout.addRow("Freezing Threshold (cm/s):", self.param_freezing_threshold)
        params_layout.addRow("Slow Angular Velocity Threshold (deg/s):", self.param_angular_threshold)
        params_layout.addRow("Center Zone Radius (% of tank):", self.param_center_radius_percent)
        form_layout.addRow(params_group)
        main_layout.addWidget(input_group)

        progress_group = QtWidgets.QGroupBox("Progress"); progress_layout = QtWidgets.QVBoxLayout(progress_group)
        progress_layout.addWidget(self.progress_label); progress_layout.addWidget(self.progress_bar)
        main_layout.addWidget(progress_group)
        log_group = QtWidgets.QGroupBox("Log"); log_layout = QtWidgets.QVBoxLayout(log_group); log_layout.addWidget(self.log_text_edit)
        main_layout.addWidget(log_group, stretch=1)
        button_layout = QtWidgets.QHBoxLayout(); button_layout.addStretch(); button_layout.addWidget(self.start_btn); button_layout.addWidget(self.cancel_btn)
        main_layout.addLayout(button_layout)

        self.add_files_btn.clicked.connect(self.add_files); self.browse_output_btn.clicked.connect(self.browse_output); self.browse_settings_btn.clicked.connect(self.browse_settings); self.start_btn.clicked.connect(self.start_analysis); self.cancel_btn.clicked.connect(self.cancel_analysis)
        self.cancel_btn.setEnabled(False)

    def add_files(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Select Enriched CSV Files", "", "CSV Files (*_with_tanks.csv)");
        if files: self.csv_files.extend(files); self.file_list_widget.addItems([os.path.basename(f) for f in files])
    def browse_output(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Directory");
        if directory: self.output_dir_line_edit.setText(directory)
    def browse_settings(self):
        file, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Settings File", "", "JSON Files (*.json)");
        if file: self.settings_line_edit.setText(file)

    def start_analysis(self):
        if not self.csv_files: QtWidgets.QMessageBox.warning(self, "Input Error", "Please add at least one CSV file."); return
        if not self.output_dir_line_edit.text() or not os.path.isdir(self.output_dir_line_edit.text()): QtWidgets.QMessageBox.warning(self, "Input Error", "Please select a valid output directory."); return
        if not self.settings_line_edit.text() or not os.path.exists(self.settings_line_edit.text()): QtWidgets.QMessageBox.warning(self, "Input Error", "Please select a valid settings.json file."); return
        
        params = {
            'frame_rate': self.param_frame_rate.value(), 'conversion_rate': self.param_conversion_rate.value(),
            'freezing_threshold': self.param_freezing_threshold.value(), 'slow_angular_velocity_threshold': self.param_angular_threshold.value(),
            'center_radius_percent': self.param_center_radius_percent.value()
        }
        self.toggle_controls(False); self.log_text_edit.clear()
        
        self.analysis_worker = AnalysisProcessor(self.csv_files, self.settings_line_edit.text(), params, self.output_dir_line_edit.text())
        self.analysis_thread = QThread(); self.analysis_worker.moveToThread(self.analysis_thread)
        self.analysis_worker.progress.connect(self.update_progress); self.analysis_worker.log.connect(self.log_text_edit.append); self.analysis_worker.finished.connect(self.on_analysis_finished); self.analysis_thread.started.connect(self.analysis_worker.run)
        self.analysis_thread.start()

    def cancel_analysis(self):
        if self.analysis_worker: self.analysis_worker.stop()
    def update_progress(self, current, total, filename):
        self.progress_bar.setValue(int((current + 1) * 100 / total)); self.progress_label.setText(f"Processing {current+1}/{total}: {filename}...")
    def on_analysis_finished(self):
        self.toggle_controls(True)
        if self.analysis_thread: self.analysis_thread.quit(); self.analysis_thread.wait(); self.analysis_thread = None
        self.progress_label.setText("Analysis Finished.")
        if self.analysis_worker and self.analysis_worker._is_running:
             QtWidgets.QMessageBox.information(self, "Finished", f"Analysis complete. Results saved to:\n{self.output_dir_line_edit.text()}")
    def toggle_controls(self, enabled):
        self.start_btn.setEnabled(enabled); self.add_files_btn.setEnabled(enabled); self.browse_output_btn.setEnabled(enabled); self.browse_settings_btn.setEnabled(enabled)
        self.cancel_btn.setEnabled(not enabled)
    def show_error(self, message):
        QtWidgets.QMessageBox.critical(self, "Error", message)
    def closeEvent(self, event):
        if self.analysis_thread and self.analysis_thread.isRunning():
            self.cancel_analysis(); self.analysis_thread.quit(); self.analysis_thread.wait()
        event.accept()