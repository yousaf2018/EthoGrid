# EthoGrid: An AI-Powered Spatial Behavior Analysis Tool

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![UI Framework](https://img.shields.io/badge/UI-PyQt5-green.svg)](https://pypi.org/project/PyQt5/)
[![Deep Learning](https://img.shields.io/badge/AI-YOLOv11-purple.svg)](https://ultralytics.com/)

**EthoGrid** is a desktop application designed for researchers to analyze animal behavior from video recordings. It provides a complete end-to-end pipeline, from running AI-based **object detection and segmentation (YOLO)** on raw videos to interactively assigning detections to grid cells (tanks/arenas) and exporting multiple formats of annotated data, visualizations, and scientific endpoints.

<p align="center">
  <img src="https://raw.githubusercontent.com/yousaf2018/EthoGrid/main/images/android-chrome-512x512.png" alt="EthoGrid Logo" width="200">
</p>

![Tool Overview](https://raw.githubusercontent.com/yousaf2018/EthoGrid/main/images/EthoGridGUI.png)
*A snapshot of the EthoGrid interface showing a video with an overlaid grid, detections with centroids, a behavior legend, and a multi-tank timeline.*

---

## Table of Contents
- [Key Features](#key-features)
- [Standalone Utilities](#standalone-utilities)
- [Getting Started for Users (No Installation Needed)](#getting-started-for-users-no-installation-needed)
  - [1. Download the Application](#1-download-the-application)
  - [2. Download Sample Files](#2-download-sample-files)
- [How to Use EthoGrid: A Step-by-Step Workflow](#how-to-use-ethogrid-a-step-by-step-workflow)
- [For Developers](#for-developers)
- [Output Files](#output-files)
- [Contributing](#contributing)
- [License](#license)

---

## Key Features

-   **High-Performance YOLO Inference**:
    -   **GPU Accelerated**: Automatically detects and utilizes NVIDIA GPUs for massive speed improvements, while gracefully falling back to CPU if a GPU is not available.
    -   **Object Detection & Instance Segmentation**: Supports both standard bounding box models and precise pixel-level segmentation models (`-seg.pt`).
-   **Powerful & Flexible Data Input**:
    -   **Batch File Handling**: Add individual videos/CSVs or entire directories. The application will recursively find all relevant files.
    -   **File List Management**: Easily remove selected files or clear the entire list before processing.
-   **Advanced Batch Processing & Data Cleaning**:
    -   **Batch Annotation**: Apply a saved grid configuration to a batch of videos and their detection files, automating the tank assignment process for large datasets.
    -   **Single Animal per Tank**: Automatically filter detections within each tank to keep only the one with the highest confidence score per frame, ensuring clean data for single-animal tracking.
-   **Interactive Grid System**:
    -   Define a virtual grid to match your experimental setup. Interactively translate, rotate, and scale the grid with sliders or direct mouse control for perfect alignment.
    -   **Settings Persistence**: Save and load complex grid configurations (including video dimensions) to a JSON file, ensuring reproducibility.
-   **Comprehensive Data Export & Visualization**:
    -   **Annotated Videos**: Generate publication-ready videos with or without overlays (legend, timeline).
    -   **Enriched CSV (Long Format)**: Export detection data with added columns for `tank_number` and high-precision `cx`, `cy` coordinates.
    -   **Centroid CSV (Wide Format)**: Export a processed CSV with one row per frame and `x`/`y` columns for each tank, perfect for direct import into statistical software like GraphPad Prism.
    -   **Excel Export (By Tank)**: Export all data into a single `.xlsx` file, with the detections for each tank neatly organized on its own separate sheet.
    -   **Trajectory Plots**: Generate a high-quality image plotting the centroid path of animals. The plot correctly handles grid transformations and respects a user-defined time gap to prevent erroneous lines during tracking loss.
    -   **Heatmaps**: Create scientific heatmaps superimposed on the first frame of the video to visualize spatial usage, complete with a clear color legend.
-   **Scientific Endpoints Analysis**:
    -   A dedicated module to batch-calculate a wide range of behavioral endpoints from your annotated CSV files.
    -   Calculations are performed correctly on a **per-tank basis** using the geometric center of each tank derived from your saved grid settings.
    -   Endpoints include: Total Distance, Average Speed, Time spent Moving/Freezing, Angular Velocity, Meandering, Time spent in Center, Fractal Dimension, Entropy, and more.

---

## Standalone Utilities

EthoGrid also includes powerful, standalone tools for preparing your data.

-   **Video Splitter**: A utility to split long video recordings into smaller, manageable chunks (e.g., 60-minute segments) without re-encoding, preserving the original quality.
-   **Frame Extractor**: A tool for creating datasets. It can recursively find all videos in a directory structure and extract a specified number of random frames from each, creating uniquely named image files that are traceable to their source video and subfolder.

---

## Getting Started for Users (No Installation Needed)

Follow these steps to get up and running in minutes.

### 1. Download the Application

-   **[Download EthoGrid.zip for Windows](https://github.com/yousaf2018/EthoGrid/releases/download/V1.1.5/EthoGrid.zip)**

Simply download the ZIP file, extract it, and double-click `EthoGrid.exe` to run. There is no installation process.

### 2. Download Sample Files

To test the full functionality immediately, download this complete set of sample files. It's recommended to place them all in the same folder for easy access.

-   **Sample YOLOv11 Detection Model (`.pt` file):**
    -   *This is required for the "YOLO detection model for betta fish" feature.*
    -   **[Download Detection Model](https://drive.google.com/file/d/17WDbQ72Rn-DFkIKcp7ECL0ZfPHE84oGV/view?usp=sharing)**
-   **Sample Raw Video (`.mp4` file):**
    -   *This is the video you will analyze.*
    -   **[Download Sample Video](https://drive.google.com/file/d/1ImicvjG2tSUdRys2nu_XtJ7B9jcZpnaI/view?usp=sharing)**
-   **Pre-Generated Detection CSV (for Annotation Testing):**
    -   *Use this to skip inference and go directly to grid annotation.*
    -   **[Download Detection CSV](https://drive.google.com/file/d/1ImicvjG2tSUdRys2nu_XtJ7B9jcZpnaI/view?usp=sharing)**
-   **Pre-Configured Grid Settings File (for Annotation Testing):**
    -   *Use this to instantly align the grid with the sample video.*
    -   **[Download Grid Settings .json](https://drive.google.com/file/d/1nPepLlHvBuyjzYqWehX1lnBLRMe-rEAW/view?usp=sharing)**

---

## How to Use EthoGrid: A Step-by-Step Workflow

This workflow demonstrates how to use the sample files you downloaded.

1.  **Run AI Inference (Optional - if you want to generate your own CSV)**
    -   Launch `EthoGrid.exe`.
    -   Click **🎨 Run YOLO Segmentation...**.
    -   Use **Add Video(s)...** or **Add Directory...** to add the `Sample Video.mp4`.
    -   **YOLO Model File**: Select the `segmentation_model.pt` you downloaded.
    -   **Output Directory**: Choose a folder to save the results.
    -   Click **Start Segmentation**. This will create a new CSV file and an annotated video.

2.  **Load Video and Detections for Grid Annotation**
    -   Click **🎬 Load Video** and select the `Sample Video.mp4`.
    -   Click **📄 Load Detections** and select the pre-generated `Segmentation CSV` you downloaded.

3.  **Align the Grid**
    -   Click **📂 Load Settings** and select the `grid_settings.json` file.
    -   The grid will snap into perfect alignment on the video. You can fine-tune it with the sliders or by dragging the red center point.

4.  **Batch Export with a Clean Grid**
    -   Click **🚀 Batch Annotation...**.
    -   Add your video(s) and select the same `grid_settings.json`.
    -   Choose your output folder and select which files to export (e.g., Trajectory Plot, Heatmap, Excel).
    -   Click **Start Processing**.

---

## For Developers

If you wish to run or modify the tool from source code:

1.  **Prerequisites**: Python 3.9+, Git.
2.  **Setup**:
    ```bash
    # Clone the repository
    git clone https://github.com/yousaf2018/EthoGrid.git
    cd EthoGrid

    # Create and activate a virtual environment (recommended)
    python -m venv venv
    source venv/bin/activate  # On macOS/Linux
    # venv\Scripts\activate    # On Windows

    # Install dependencies
    pip install -r requirements.txt

    # Run the application
    python main.py
    ```
3.  **Developer Documentation**: For a full breakdown of the code architecture, see the [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md).

---

## Output Files

1.  **From AI Inference**:
    -   `{video_name}_inference.mp4` / `_segmentation.mp4`: Videos showing the raw AI results.
    -   `{video_name}_detections.csv` / `_segmentations.csv`: The data files for the next stage.
2.  **From Batch Annotation**:
    -   `{video_name}_with_tanks.csv`: The final "long-format" data file with tank numbers.
    -   `{video_name}_centroids_wide.csv`: The final "wide-format" data file for statistical software.
    -   `{video_name}_by_tank.xlsx`: An Excel file with data for each tank on a separate sheet.
    -   `{video_name}_trajectory.png`: A high-quality image plotting the centroid paths.
    -   `{video_name}_heatmap.png`: A high-quality heatmap image superimposed on the video's first frame.
    -   `{video_name}_annotated.mp4`: A clean final video, with or without overlays.
3.  **From Endpoints Analysis**:
    -   `{video_name}_endpoints.csv`: A CSV file containing all calculated behavioral endpoints for each tank.

---

## Contributing

Contributions are welcome! Please fork the repository, create a feature branch, and submit a pull request.

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/NewFeature`)
3.  Commit your Changes (`git commit -m 'Add some NewFeature'`)
4.  Push to the Branch (`git push origin feature/NewFeature`)
5.  Open a Pull Request

---

## License


Distributed under the MIT License. See the `LICENSE` file for more information.




