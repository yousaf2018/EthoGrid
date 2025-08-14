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
3.  **Decoupling**: The UI (widgets) is decoupled from the business logic (workers). They communicate using Qt's signal and slot mechanism, which prevents them from having to know about each other's internal implementation.
4.  **Clear Data Flow**: Data flows in a predictable pattern: from user input (files, UI controls) -> to a background worker for processing -> back to the main window, which then updates the UI widgets.

---

## Project Structure Overview

EthoGrid_App/
├── main.py # Application entry point.
├── main_window.py # Main application window. The central coordinator.
|
├── core/
│ ├── grid_manager.py # Manages the grid's state (position, rotation, scale).
│ └── data_exporter.py # Handles specialized CSV export logic (e.g., wide format).
|
├── workers/
│ ├── video_loader.py # Thread for loading video frames for playback.
│ ├── detection_processor.py # Thread for assigning detections to grid cells.
│ ├── video_saver.py # Thread for rendering and saving annotated videos.
│ ├── yolo_processor.py # Thread for running YOLO object detection.
│ ├── yolo_segmentation_processor.py # Thread for running YOLO segmentation.
│ └── batch_processor.py # Thread for batch-annotating videos with a grid.
|
└── widgets/
├── timeline_widget.py # Custom QWidget for the behavior timeline.
├── yolo_inference_dialog.py# UI dialog for YOLO detection.
├── yolo_segmentation_dialog.py # UI dialog for YOLO segmentation.
└── batch_dialog.py # UI dialog for the batch grid annotation feature.





---

## Detailed File Breakdown

### 1. `main.py`: The Entry Point
This is the simplest file. Its only job is to:
1.  Initialize the `QApplication`.
2.  Set application-wide attributes like HighDPI scaling.
3.  Instantiate the `VideoPlayer` class from `main_window.py`.
4.  Show the main window and start the application's event loop.

### 2. `main_window.py`: The Application Hub
This is the most important file, acting as the central controller.

-   **Class**: `VideoPlayer(QtWidgets.QWidget)`
-   **Responsibilities**:
    1.  **UI Construction**: The `setup_ui` method builds the entire main window, creating all buttons, sliders, dialogs, and layouts.
    2.  **State Management**: It holds the application's current state, such as `self.raw_detections`, `self.processed_detections`, `self.current_frame`, etc.
    3.  **Signal Aggregation**: `setup_connections` connects UI signals (e.g., a button's `clicked` signal) to handler methods (slots) within this class.
    4.  **Worker Management**: It creates, starts, and connects signals from all the background worker threads. For example, when a user clicks "Export Video," this class instantiates `VideoSaver` and starts it.
    5.  **Data Display**: Contains `update_display`, the heart of the visualization. It takes the current frame and detection data and uses OpenCV (`cv2`) to draw the grid, bounding boxes, **segmentation masks**, and centroids before displaying the result.

### 3. The `core/` Directory: Central Logic & Utilities

#### `core/grid_manager.py`
-   **Class**: `GridManager(QObject)`
-   **Responsibilities**:
    1.  **State Encapsulation**: Exclusively manages the grid's properties: `center`, `angle`, `scale_x`, and `scale_y`.
    2.  **Transformation Matrix**: Maintains a `QTransform` matrix, recalculating it whenever a property changes.
    3.  **Notification**: Emits a `transform_updated` signal whenever the grid changes, telling the `main_window` to redraw.

#### `core/data_exporter.py`
-   **Function**: `export_centroid_csv(...)`
-   **Responsibilities**:
    1.  **Data Transformation**: Contains the logic to pivot the "long-format" detection data (one row per detection) into a "wide-format" CSV (one row per frame, with `x` and `y` columns for each tank).
    2.  **Dependency Handling**: Checks if the `pandas` library is available before attempting to run.
    3.  **Reusability**: This logic is called by both the single-file export button in `main_window.py` and the batch export process in `batch_processor.py`.

### 4. The `widgets/` Directory: Custom UI Components

#### `widgets/timeline_widget.py`
-   **Class**: `TimelineWidget(QtWidgets.QWidget)`
-   **Responsibilities**:
    1.  **Custom Painting**: Uses `QPainter` in its `paintEvent` method to draw the timeline from scratch.
    2.  **Self-Contained**: Knows nothing about the rest of the application. The `main_window` gives it data via `setData(...)` and `setCurrentFrame(...)`.

#### `widgets/yolo_inference_dialog.py`
-   **Class**: `YoloInferenceDialog(QtWidgets.QDialog)`
-   **Responsibilities**: Manages the UI and worker thread for the **object detection** workflow. It allows users to select videos, a detection model, and output options, then launches the `YoloProcessor`.

#### `widgets/yolo_segmentation_dialog.py`
-   **Class**: `YoloSegmentationDialog(QtWidgets.QDialog)`
-   **Responsibilities**: Manages the UI and worker thread for the **instance segmentation** workflow. It allows users to select videos, a segmentation model, and output options, then launches the `YoloSegmentationProcessor`.

#### `widgets/batch_dialog.py`
-   **Class**: `BatchProcessDialog(QtWidgets.QDialog)`
-   **Responsibilities**: Manages the UI and worker thread for **batch grid annotation**. It allows users to apply a saved `settings.json` file to many videos and their corresponding CSVs at once.

### 5. The `workers/` Directory: The Background Powerhouses

All classes here are `QThread` subclasses, designed for long-running tasks.

#### `workers/video_loader.py`
-   **Class**: `VideoLoader(QThread)`
-   **Purpose**: Handles all video file reading for live playback, emitting frames one by one without freezing the UI.

#### `workers/detection_processor.py`
-   **Class**: `DetectionProcessor(QThread)`
-   **Purpose**: To map raw detections to grid cells based on their **centroid**.
-   **Magic**: Uses the *inverted* grid transformation matrix to convert on-screen coordinates back into the grid's local space to determine the correct tank number.

#### `workers/video_saver.py`
-   **Class**: `VideoSaver(QThread)`
-   **Purpose**: To render and save the final annotated video.
-   **Magic**: Its `process_frame` method is highly flexible. It can conditionally draw **segmentation masks** (if available) or bounding boxes, and can also conditionally add or omit the legend and timeline overlays based on user choices.

#### `workers/yolo_processor.py`
-   **Class**: `YoloProcessor(QThread)`
-   **Purpose**: To run YOLO **object detection** on videos.
-   **Magic**: Loops through videos, passes each frame to `model.predict()`, and saves the results. It calculates high-precision float coordinates for bounding boxes and centroids and formats them to 4 decimal places for the output CSV.

#### `workers/yolo_segmentation_processor.py`
-   **Class**: `YoloSegmentationProcessor(QThread)`
-   **Purpose**: To run YOLO **instance segmentation** on videos.
-   **Magic**: Similar to the detection processor, but it processes `results.masks`. It calculates centroids from the mask's geometric moments for higher accuracy and converts the pixel masks into polygon coordinate strings for the output CSV.

#### `workers/batch_processor.py`
-   **Class**: `BatchProcessor(QThread)`
-   **Purpose**: To apply a grid configuration to a batch of videos.
-   **Magic**: Orchestrates a non-interactive workflow. It loads detections, applies the grid logic to assign tank numbers, and then calls the appropriate export functions (including the new `export_centroid_csv`) based on user-selected options in the dialog.

---

## Data Flow and Signal/Slot Mechanism

Understanding the signal/slot mechanism is key to understanding EthoGrid
**Example Flow: Loading a Video**
1.  **User**: Clicks the "Load Video" button.
2.  **`main_window.py`**: The `load_video` slot is triggered. It creates a `VideoLoader` instance and `.start()`s it.
3.  **`video_loader.py`**: The `run()` method opens the video file. On success, it `emit`s the `video_loaded` signal with the video's dimensions and FPS.
4.  **`main_window.py`**: The `on_video_loaded` slot receives this signal. It updates the UI (e.g., sets the slider range) and tells the `VideoLoader` to seek to the first frame.
5.  **`video_loader.py`**: It reads frame 0 and `emit`s the `frame_loaded` signal with the frame data.
6.  **`main_window.py`**: The `on_frame_loaded` slot receives this. It calls `update_display`, which draws the frame and annotations on the screen.

---

## How to Add a New Feature (Example)

Let's say you want to add a feature to export a summary report (e.g., total time spent on each behavior per tank).

1.  **Add a UI Element**: In `main_window.py`'s `setup_ui`, add a `self.export_report_btn = QPushButton("Export Report")`.
2.  **Create a Utility Function**: Since this is a data-only task, you could add a new function to `core/data_exporter.py` called `export_summary_report(...)`. This function would take `processed_detections` and `fps` as input, calculate the statistics using `pandas`, and save them to a CSV.
3.  **Connect in Main Window**: In `main_window.py`, create a new slot `export_report`. In `setup_connections`, connect the button's `clicked` signal to this slot.
4.  **Implement the Slot**: The `export_report` method would:
    -   Open a file save dialog.
    -   Call the `export_summary_report` function from the `core` module.
    -   Show a success or failure message box based on the return value.