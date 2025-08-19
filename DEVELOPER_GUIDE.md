# EthoGrid: Developer's Guide & Code Architecture

Welcome, developer! This document provides a high-level overview of the EthoGrid application's architecture. It is intended to help you understand how the different components interact so you can easily navigate the codebase, fix bugs, or add new features.

## Table of Contents
- [Core Philosophy](#core-philosophy)
- [Project Structure Overview](#project-structure-overview)
- [Detailed File Breakdown](#detailed-file-breakdown)
  - [1. `main.py`: The Entry Point](#1-mainpy-the-entry-point)
  - [2. `main_window.py`: The Application Hub](#2-main_windowpy-the-application-hub)
  - [3. The `core/` Directory: Central Logic & Utilities](#3-the-core-directory-central-logic--utilities)
    - [`core/grid_manager.py`](#coregrid_managerpy)
    - [`core/data_exporter.py`](#coredata_exporterpy)
    - [`core/stopwatch.py`](#corestopwatchpy)
  - [4. The `widgets/` Directory: Custom UI Components](#4-the-widgets-directory-custom-ui-components)
    - [`widgets/timeline_widget.py`](#widgetstimeline_widgetpy)
    - [`widgets/yolo_inference_dialog.py`](#widgetsyolo_inference_dialogpy)
    - [`widgets/yolo_segmentation_dialog.py`](#widgetsyolo_segmentation_dialogpy)
    - [`widgets/batch_dialog.py`](#widgetsbatch_dialogpy)
  - [5. The `workers/` Directory: The Background Powerhouses](#5-the-workers-directory-the-background-powerhouses)
    - [`workers/video_loader.py`](#workersvideo_loaderpy)
    - [`workers/detection_processor.py`](#workersdetection_processorpy)
    - [`workers/video_saver.py`](#workersvideo_saverpy)
    - [`workers/yolo_processor.py`](#workersyolo_processorpy)
    - [`workers/yolo_segmentation_processor.py`](#workersyolo_segmentation_processorpy)
    - [`workers/batch_processor.py`](#workersbatch_processorpy)
- [Data Flow and Signal/Slot Mechanism](#data-flow-and-signalslot-mechanism)
- [How to Add a New Feature (Example)](#how-to-add-a-new-feature-example)

---

## Core Philosophy

EthoGrid is built on a few key principles:

1.  **Modularity**: Each file and class has a single, clear responsibility. This makes the code easier to read, test, and maintain.
2.  **Responsive UI**: The user interface must never freeze. All long-running tasks (video I/O, AI inference, data processing) are offloaded to background threads (`QThread`).
3.  **Decoupling**: The UI (widgets) is decoupled from the business logic (workers). They communicate using Qt's signal and slot mechanism.
4.  **Clear Data Flow**: Data flows predictably: from user input -> to a background worker for processing -> back to the main window, which then updates the UI.

---

## Project Structure Overview
EthoGrid_App/
├── main.py
├── main_window.py
|
├── core/
│ ├── grid_manager.py
│ ├── data_exporter.py
│ └── stopwatch.py
|
├── workers/
│ ├── video_loader.py
│ ├── detection_processor.py
│ ├── video_saver.py
│ ├── yolo_processor.py
│ ├── yolo_segmentation_processor.py
│ └── batch_processor.py
|
└── widgets/
├── timeline_widget.py
├── yolo_inference_dialog.py
├── yolo_segmentation_dialog.py
└── batch_dialog.py



---

## Detailed File Breakdown

### 1. `main.py`: The Entry Point
This is the simplest file. Its only job is to initialize and run the `QApplication`.

### 2. `main_window.py`: The Application Hub
The central controller of the application.
-   **Class**: `VideoPlayer(QtWidgets.QWidget)`
-   **Responsibilities**:
    -   **UI Construction**: Builds the main window, toolbars, and control sidebar.
    -   **State Management**: Holds the application's current state (`self.raw_detections`, `self.processed_detections`, etc.).
    -   **Worker/Dialog Management**: Instantiates and launches all dialogs and worker threads.
    -   **Data Display**: The `update_display` method uses OpenCV to render the video frame with all annotations (grid, boxes, masks, centroids).

### 3. The `core/` Directory: Central Logic & Utilities

#### `core/grid_manager.py`
-   **Class**: `GridManager(QObject)`
-   **Responsibilities**: Encapsulates the state of the interactive grid (`center`, `angle`, `scale`). It maintains the `QTransform` matrix used for coordinate mapping.

#### `core/data_exporter.py`
-   **Functions**: `export_...(...)`
-   **Responsibilities**: Contains all logic for creating the final output files.
    -   `export_centroid_csv`: Creates the wide-format CSV for statistical software.
    -   `export_to_excel_sheets`: Creates the multi-sheet `.xlsx` file.
    -   `export_trajectory_image`: Generates the final trajectory plot image, correctly handling grid transformations and margins.

#### `core/stopwatch.py`
-   **Class**: `Stopwatch`
-   **Responsibilities**: A reusable helper class to calculate elapsed time and Estimated Time Remaining (ETR) for long processes.

### 4. The `widgets/` Directory: Custom UI Components

#### `widgets/timeline_widget.py`
-   **Class**: `TimelineWidget(QtWidgets.QWidget)`
-   **Responsibilities**: A fully custom-painted widget that uses `QPainter` to draw the multi-tank behavior timeline.

#### `widgets/yolo_inference_dialog.py`
-   **Class**: `YoloInferenceDialog(QtWidgets.QDialog)`
-   **Responsibilities**: Manages the UI and launches the `YoloProcessor` worker for **object detection**.

#### `widgets/yolo_segmentation_dialog.py`
-   **Class**: `YoloSegmentationDialog(QtWidgets.QDialog)`
-   **Responsibilities**: Manages the UI and launches the `YoloSegmentationProcessor` worker for **instance segmentation**.

#### `widgets/batch_dialog.py`
-   **Class**: `BatchProcessDialog(QtWidgets.QDialog)`
-   **Responsibilities**: Manages the UI and launches the `BatchProcessor` worker for applying a saved grid configuration to many videos at once.

### 5. The `workers/` Directory: The Background Powerhouses

All classes here are `QThread` subclasses. Their `run()` method executes on a separate thread.

#### `workers/video_loader.py`
-   **Class**: `VideoLoader(QThread)`
-   **Purpose**: Handles video file reading for live playback, emitting frames via signals.

#### `workers/detection_processor.py`
-   **Class**: `DetectionProcessor(QThread)`
-   **Purpose**: Maps raw detections to grid cells based on their centroid using the inverted grid transformation matrix.

#### `workers/video_saver.py`
-   **Class**: `VideoSaver(QThread)`
-   **Purpose**: Renders and saves the final annotated video. It can conditionally draw masks or boxes, and include or omit overlays.

#### `workers/yolo_processor.py`
-   **Class**: `YoloProcessor(QThread)`
-   **Purpose**: To run YOLO **object detection**. It performs a minor inset on bounding boxes to improve centroid accuracy before saving high-precision CSV data.

#### `workers/yolo_segmentation_processor.py`
-   **Class**: `YoloSegmentationProcessor(QThread)`
-   **Purpose**: To run YOLO **instance segmentation**. It calculates centroids from mask moments and saves polygon data to the CSV.

#### `workers/batch_processor.py`
-   **Class**: `BatchProcessor(QThread)`
-   **Purpose**: To orchestrate a non-interactive grid annotation workflow. It loads data, applies grid logic, and calls the relevant functions from `data_exporter.py`.

---

## Data Flow and Signal/Slot Mechanism

The application relies heavily on Qt's signal and slot mechanism for communication between threads.

**Example Flow: Batch Processing**
1.  **User**: Fills out the `BatchProcessDialog` and clicks "Start".
2.  **`batch_dialog.py`**: The `start_processing` slot creates a `BatchProcessor` instance, moves it to a `QThread`, connects signals (`overall_progress`, `file_progress`, `time_updated`, etc.) to its own update slots, and starts the thread.
3.  **`batch_processor.py`**: The `run()` method starts its main loop. For each video, it `emit`s an `overall_progress` signal. Inside the video processing loop, it continuously `emit`s `file_progress` and `time_updated` signals.
4.  **`batch_dialog.py`**: The dialog's slots (`update_file_progress`, `update_time_labels`) receive these signals and update the GUI elements (progress bars and labels) in real-time, keeping the user informed without freezing the UI.

---

## How to Add a New Feature (Example)

Let's say you want to add a feature to export a summary report (e.g., total time spent on each behavior per tank).

1.  **Add a UI Element**: In `main_window.py`'s `setup_ui`, add a `self.export_report_btn = QPushButton("Export Report")`.
2.  **Create a Utility Function**: In `core/data_exporter.py`, add a new function `export_summary_report(...)`. This function would take `processed_detections` and `fps` as input, calculate the statistics using `pandas`, and save them to a CSV.
3.  **Connect in Main Window**: In `main_window.py`, create a new slot `export_report`. In `setup_connections`, connect the button's `clicked` signal to this slot.
4.  **Implement the Slot**: The `export_report` method would:
    -   Open a file save dialog.
    -   Call the `export_summary_report` function from the `core` module.
    -   Show a success or failure message box based on the return value.