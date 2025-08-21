# EthoGrid: An AI-Powered Spatial Behavior Analysis Tool

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![UI Framework](https://img.shields.io/badge/UI-PyQt5-green.svg)](https://pypi.org/project/PyQt5/)
[![Deep Learning](https://img.shields.io/badge/AI-YOLOv11-purple.svg)](https://ultralytics.com/)

**EthoGrid** is a desktop application designed for researchers to analyze animal behavior from video recordings. It provides a complete end-to-end pipeline, from running AI-based **object detection and segmentation (YOLO)** on raw videos to interactively assigning detections to grid cells (tanks/arenas) and exporting multiple formats of annotated data and videos.

<p align="center">
  <img src="https://raw.githubusercontent.com/yousaf2018/EthoGrid/main/images/android-chrome-512x512.png" alt="EthoGrid Logo" width="200">
</p>

![Tool Overview](https://raw.githubusercontent.com/yousaf2018/EthoGrid/main/images/EthoGridGUI.png)
*A snapshot of the EthoGrid interface showing a video with an overlaid grid, detections with centroids, a behavior legend, and a multi-tank timeline.*

---

## Table of Contents
- [Key Features](#key-features)
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

- **Dual YOLO Inference Modes**:
  - **Object Detection**: Run standard YOLO models to generate bounding boxes.
  - **Instance Segmentation**: Run YOLO segmentation models (`-seg.pt`) to generate precise pixel-level masks and polygon outlines.
- **Powerful Batch Processing**:
  - **Batch Inference**: Process entire folders of videos with either detection or segmentation models, automatically generating annotated videos and corresponding CSV files.
  - **Batch Annotation**: Apply a saved grid configuration to a batch of videos and their detection/segmentation files, automating the tank assignment process for large datasets.
- **Interactive Grid System**: Define a virtual grid to match your experimental setup. Interactively translate, rotate, and scale the grid with sliders or direct mouse control for perfect alignment.
- **Centroid-Based Tank Assignment**: Accurately maps each object to its grid cell (tank/arena) based on its precise centroid, eliminating ambiguity from overlapping bounding boxes.
- **Rich Data Visualization**:
  - **Live Annotations**: View bounding boxes, segmentation masks (as semi-transparent overlays), behavior labels, and large centroids directly on the video player.
  - **Multi-Tank Timeline**: A powerful widget that visualizes the sequence of behaviors for each tank over the entire video duration.
- **Flexible & Comprehensive Data Export**:
  - **Annotated Videos**: Generate publication-ready videos. Choose to include full overlays (legend, timeline) or export a minimal version with only object annotations.
  - **Enriched CSV (Long Format)**: Export your detection data with new columns for `tank_number`, and high-precision `cx`, `cy` coordinates (formatted to 4 decimal places).
  - **Centroid CSV (Wide Format)**: Export a processed CSV with one row per frame, and `x` and `y` columns for each tank, perfect for direct import into statistical software like GraphPad Prism.
  - **Excel Export (By Tank)**: Export all data into a single `.xlsx` file, with the detections for each tank neatly organized on its own separate sheet.
  - **Trajectory Image Export**: Generate a high-quality image plotting the centroid path of animals within their assigned tanks, ideal for visualizing spatial usage.
- **Settings Persistence**: Save and load complex grid configurations to a JSON file, ensuring reproducibility across multiple experiments.

---

## Getting Started for Users (No Installation Needed)

Follow these steps to get up and running in minutes.

### 1. Download the Application

-   **[Download EthoGrid.exe for Windows]([https://github.com/yousaf2018/EthoGrid/releases/download/v1.1.4/EthoGrid-APP.zip](https://github.com/yousaf2018/EthoGrid/releases/download/V1.1.5/EthoGrid-APP.exe)**

Simply download the ZIP file, extract it, and double-click `EthoGrid.exe` to run. There is no installation process.

### 2. Download Sample Files

To test the full functionality of the application immediately, download this complete set of sample files. It's recommended to place them all in the same folder for easy access.

-   **Sample YOLOv11 Detection Model (`.pt` file):**
    -   *This is required for the "YOLO Detection" feature.*
    -   **[Download Detection Model](https://drive.google.com/file/d/1-vmkZXYQQsS9cgR9E-OZURbYQVzyoSr7/view?usp=sharing)**
-   **Sample Raw Video (`.mp4` file):**
    -   *This is the video you will analyze.*
    -   **[Download Sample Video](https://drive.google.com/file/d/1ImicvjG2tSUdRys2nu_XtJ7B9jcZpnaI/view?usp=sharing)**
-   **Pre-Generated Detection CSV (for Annotation Testing):**
    -   *Use this to skip the inference step and go directly to grid annotation.*
    -   **[Download Detection CSV](https://drive.google.com/file/d/1nih-USaZ6P_Cn06CqzXZhyNynoPn0WCd/view?usp=sharing)**
-   **Pre-Configured Grid Settings File (for Annotation Testing):**
    -   *Use this to instantly align the grid with the sample video.*
    -   **[Download Grid Settings .json](https://drive.google.com/file/d/1nPepLlHvBuyjzYqWehX1lnBLRMe-rEAW/view?usp=sharing)**

---

## How to Use EthoGrid: A Step-by-Step Workflow

This workflow demonstrates how to use the sample files you downloaded.

1.  **Run AI Inference (Optional - if you want to generate your own CSV)**
    -   Launch `EthoGrid.exe`.
    -   Click **🔮 Run YOLO Detection...**.
    -   **Add Videos**: Select the `Sample Video.mp4`.
    -   **YOLO Model File**: Select the `detection_model.pt` you downloaded.
    -   **Output Directory**: Choose a folder to save the results.
    -   Click **Start Inference**. This will create a new CSV file.

2.  **Load Video and Detections for Grid Annotation**
    -   Click **🎬 Load Video** and select the `Sample Video.mp4`.
    -   Click **📄 Load Detections** and select the **pre-generated `Detection CSV`** you downloaded.

3.  **Align the Grid**
    -   Click **📂 Load Settings** and select the `grid_settings.json` file.
    -   The grid will snap into perfect alignment on the video. You can fine-tune it with the sliders or by dragging the red center point.

4.  **Analyze and Export Results**
    -   Play the video to see the live annotations, timeline, and legend.
    -   Click **📝 Save w/ Tanks** to save the enriched CSV.
    -   Click **📈 Save Centroid CSV** to save the wide-format CSV for statistical software.
    -   Click **📗 Save to Excel** to save a multi-sheet Excel file organized by tank.
    -   Click **📹 Export Video** to create the final annotated video.

---

## For Developers

If you wish to run or modify the tool from source code:

1.  **Prerequisites**: Python 3.8+, Git.
2.  **Setup**:
    ```bash
    # Clone the repository
    git clone https://github.com/yousaf2018/EthoGrid.git
    cd EthoGrid

    # Create and activate a virtual environment
    python -m venv venv
    source venv/bin/activate  # On macOS/Linux
    # venv\Scripts\activate    # On Windows

    # Install dependencies
    # The requirements.txt file should contain: PyQt5, opencv-python, numpy, ultralytics, pandas, openpyxl
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
2.  **From Grid Annotation**:
    -   `{video_name}_with_tanks.csv`: The final "long-format" data file with tank numbers and high-precision coordinates.
    -   `{video_name}_centroids_wide.csv`: The final "wide-format" data file for statistical software.
    -   `{video_name}_by_tank.xlsx`: An Excel file with data for each tank on a separate sheet.
    -   `{video_name}_trajectory.png`: A high-quality image plotting the centroid paths within their assigned tanks.
    -   `{video_name}_annotated.mp4`: A clean final video, with or without overlays.

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

