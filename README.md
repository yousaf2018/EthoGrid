# EthoGrid: An AI-Powered Spatial Behavior Analysis Tool

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![UI Framework](https://img.shields.io/badge/UI-PyQt5-green.svg)](https://pypi.org/project/PyQt5/)
[![Deep Learning](https://img.shields.io/badge/AI-YOLOv8-purple.svg)](https://ultralytics.com/)

**EthoGrid** is a desktop application designed for researchers to analyze animal behavior from video recordings. It provides a complete end-to-end pipeline, from running AI-based **object detection and segmentation (YOLO)** on raw videos to interactively assigning detections to grid cells (tanks/arenas) and exporting multiple formats of annotated data and videos.

<p align="center">
  <img src="https://raw.githubusercontent.com/yousaf2018/EthoGrid/main/images/android-chrome-512x512.png" alt="EthoGrid Logo" width="200">
</p>

![Tool Overview](https://raw.githubusercontent.com/yousaf2018/EthoGrid/main/images/EthoGridGUI.png)
*A snapshot of the EthoGrid interface showing a video with an overlaid grid, detections with centroids, a behavior legend, and a multi-tank timeline.*

---

## Table of Contents
- [Key Features](#key-features)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Workflow Overview](#workflow-overview)
- [How to Use EthoGrid: A Step-by-Step Guide](#how-to-use-ethogrid-a-step-by-step-guide)
  - [Part 1: AI Inference (Video to Data)](#part-1-ai-inference-video-to-data)
  - [Part 2: Grid Annotation (Data to Insights)](#part-2-grid-annotation-data-to-insights)
- [Detailed Guide to the Interface](#detailed-guide-to-the-interface)
  - [Main Toolbars](#main-toolbars)
  - [Video Player & Visuals](#video-player--visuals)
  - [Controls Sidebar](#controls-sidebar)
- [Required Input File Formats](#required-input-file-formats)
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
- **Settings Persistence**: Save and load complex grid configurations to a JSON file, ensuring reproducibility across multiple experiments.

---

## Getting Started

### Prerequisites
Before you begin, ensure you have Python 3.8+ installed on your system.

### Installation
If you are a developer or want to run from source, follow these steps:

1.  **Clone the repository**
    ```bash
    git clone https://github.com/yousaf2018/EthoGrid.git
    cd EthoGrid
    ```

2.  **Create and activate a virtual environment**
    ```bash
    python -m venv venv
    
    # On Windows:
    venv\Scripts\activate
    
    # On macOS/Linux:
    source venv/bin/activate
    ```

3.  **Install the required libraries**
    The `requirements.txt` file should contain: `PyQt5`, `opencv-python`, `numpy`, `ultralytics`, and `pandas`.
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the application**
    ```bash
    python main.py 
    ```

---

## Workflow Overview

EthoGrid is designed for a two-stage workflow:

1.  **AI Inference Stage**: Use **"Run YOLO Detection"** or **"Run YOLO Segmentation"** to process your raw videos. This crucial first step generates annotated videos and the necessary CSV data files.
2.  **Grid Annotation Stage**: Load a video and its corresponding CSV from the first stage. Use the interactive grid to assign tank numbers and then export the final, fully enriched data in multiple formats.

---

## How to Use EthoGrid: A Step-by-Step Guide

### Part 1: AI Inference (Video to Data)

This step turns your raw videos into analyzable data. Choose one of the two modes.

1.  Launch the application and click either **🔮 Run YOLO Detection...** or **🎨 Run YOLO Segmentation...**.
2.  In the dialog window:
    -   Click **Add Videos...** to select one or more raw video files.
    -   Click **Browse...** to select your trained YOLO model file (`.pt`).
    -   Click **Browse...** to choose an output directory for the results.
    -   Adjust the **Confidence Threshold** (e.g., 0.4) to filter weak detections.
    -   Use the **Output Options** checkboxes to decide whether to save the annotated video, the CSV data, or both (recommended).
3.  Click **Start Inference/Segmentation**. The application will process each video, creating your chosen output files (e.g., `{video_name}_detections.csv` or `{video_name}_segmentations.csv`).

### Part 2: Grid Annotation (Data to Insights)

This step adds spatial context (tank numbers) to your data.

1.  **Load Data**:
    -   Click **🎬 Load Video** to open an original video.
    -   Click **📄 Load Detections** and select the corresponding CSV file generated in Part 1. The application will automatically detect if it contains segmentation data and display the masks.
2.  **Configure & Align Grid**:
    -   In the **Tank Configuration** sidebar, set the **Columns** and **Rows**.
    -   Use the sliders or click-and-drag the grid on the video for perfect alignment.
3.  **Save Settings (Optional but Recommended)**:
    -   Click **💾 Save Settings** to save your grid layout to a `.json` file. This is essential for batch processing.
4.  **Review and Export**:
    -   Play the video to see the live annotations.
    -   **📝 Save w/ Tanks**: Exports the standard CSV with `tank_number` and high-precision `cx`/`cy` columns added.
    -   **📈 Save Centroid CSV**: Exports the special wide-format CSV for direct use in Prism.
    -   **📹 Export Video**: A dialog will ask if you want to include overlays (legend/timeline). Choose your preferred format for a clean or fully-detailed video.
5.  **(Optional) Batch Process Grid Annotation**:
    -   Click **🚀 Batch Process...**.
    -   Add videos, select your saved `settings.json`, and choose your output options (including the Centroid CSV). The app will automatically find the matching detection/segmentation CSV for each video and process the entire set.

---

## Detailed Guide to the Interface

### Main Toolbars

-   **🔮 Run YOLO Detection...**: Opens the dialog for bounding box inference.
-   **🎨 Run YOLO Segmentation...**: Opens the dialog for pixel-mask and polygon inference.
-   **🚀 Batch Process...**: Opens the dialog to apply a saved grid setting to multiple videos.
-   **🎬 Load Video / 📄 Load Detections**: Buttons for the interactive grid alignment workflow.
-   **📝 Save w/ Tanks**: Saves the enriched "long-format" CSV.
-   **📈 Save Centroid CSV**: Saves the analysis-ready "wide-format" CSV (requires `pandas`).
-   **📹 Export Video**: Saves the final annotated video, with or without overlays.
-   **💾 Save Settings / 📂 Load Settings**: Manages `.json` grid configuration files.

### Video Player & Visuals

-   **Main Video Display**: Shows the video with a live overlay of the grid and annotations. It automatically displays segmentation masks if they are present in the loaded CSV.
-   **Playback Controls**: Standard media controls for precise navigation.

### Controls Sidebar

-   **Behavior Legend**: Lists all behaviors and their assigned colors.
-   **Tank Configuration**: Controls for grid dimensions and transformations.
-   **Tank Selection**: Filter which tanks are visualized.

---

## Required Input File Formats

-   **For AI Inference**: Standard video files (`.mp4`, `.avi`, `.mov`).
-   **For Grid Annotation**:
    -   A video file.
    -   A CSV file. The app will automatically adapt to the columns present:
        -   **Detection CSV**: Must contain `frame_idx`, `class_name`, `conf`, `x1`, `y1`, `x2`, `y2`, `cx`, `cy`.
        -   **Segmentation CSV**: Must contain all of the above, plus a `polygon` column.
    -   Both YOLO modules in EthoGrid generate files in the correct format.

---

## Output Files

1.  **From AI Inference**:
    -   `{video_name}_inference.mp4` / `{video_name}_segmentation.mp4`: Videos showing the raw AI results.
    -   `{video_name}_detections.csv` / `{video_name}_segmentations.csv`: The data files for the next stage.
2.  **From Grid Annotation**:
    -   `{video_name}_with_tanks.csv`: The final "long-format" data file with tank numbers and high-precision coordinates.
    -   `{video_name}_centroids_wide.csv`: The final "wide-format" data file for statistical software.
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