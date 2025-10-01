# EthoGrid: Your Complete, One-Stop Solution for Behavioral Analysis

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![UI Framework](https://img.shields.io/badge/UI-PyQt5-green.svg)](https://pypi.org/project/PyQt5/)
[![Deep Learning](https://img.shields.io/badge/AI-YOLO-purple.svg)](https://ultralytics.com/)

**EthoGrid** is a comprehensive desktop application engineered for researchers to perform end-to-end analysis of animal behavior from video recordings. It is designed as a **one-stop solution**, guiding you from raw, unlabeled videos to final, publication-ready statistical reports and graphs.

Every stage of the EthoGrid pipeline is designed to be **transparent, customizable, and reviewable**, giving you full scientific control over your data.

<p align="center">
  <img src="https://raw.githubusercontent.com/yousaf2018/EthoGrid/main/images/android-chrome-512x512.png" alt="EthoGrid Logo" width="200">
</p>

![Tool Overview](https://raw.githubusercontent.com/yousaf2018/EthoGrid/main/images/EthoGridGUI.png)
*A snapshot of the EthoGrid interface showing a video with an overlaid grid, detections with centroids, a behavior legend, and a multi-tank timeline.*


## The EthoGrid Philosophy: A Complete, Controllable Workflow

EthoGrid eliminates the need to stitch together multiple scripts and software. It provides a single, unified platform for the entire research pipeline:

1.  **Video Preparation**: Split long videos and extract frames for AI model training.
2.  **AI-Powered Tracking**: Run high-performance YOLO models for object detection or segmentation to generate raw tracking data.
3.  **Data Annotation & Cleaning**: Interactively align a virtual grid to your experimental setup, assign tracking data to specific arenas, and clean the data.
4.  **Endpoint Calculation**: Compute a rich set of scientific endpoints with a powerful interactive tool that allows for fine-tuning of parameters and visual validation.
5.  **Statistical Analysis & Visualization**: Perform robust statistical tests (T-test, ANOVA, Mann-Whitney, etc.) on your endpoint data, with intelligent test selection and full control over publication-quality plots.

---

## Table of Contents
- [Key Features](#key-features)
- [Standalone Utilities](#standalone-utilities)
- [The Complete Workflow](#the-complete-workflow-a-step-by-step-guide)
- [Output Files](#output-files)
- [Getting Started for Users (No Installation Needed)](#getting-started-for-users-no-installation-needed)
- [For Developers](#for-developers)
- [Contributing](#contributing)
- [License](#license)

---

## Key Features

-   **High-Performance YOLO Inference**:
    -   **GPU Accelerated**: Automatically detects and utilizes NVIDIA GPUs for massive speed improvements, while gracefully falling back to CPU if a GPU is not available.
    -   **Object Detection & Instance Segmentation**: Supports both standard bounding box models and precise pixel-level segmentation models (`-seg.pt`).
-   **Interactive Grid System**:
    -   Define a virtual grid to match your experimental setup. Interactively translate, rotate, and scale the grid with sliders or direct mouse control for perfect alignment.
    -   **Settings Persistence**: Save and load complex grid configurations to a JSON file, ensuring reproducibility.
-   **Advanced Batch Processing & Data Cleaning**:
    -   **Batch Annotation**: Apply a saved grid configuration to a batch of videos and their detection files, automating the tank assignment process for large datasets.
    -   **Data Filtering**: Automatically filter detections within each tank to keep only the one with the highest confidence score per frame, ensuring clean data for single-animal tracking.
-   **Comprehensive Data Export**:
    -   Generate annotated videos, trajectory plots, heatmaps, and multiple formats of raw and processed data (`.csv`, `.xlsx`), giving you full access to your results at every stage.
-   **Interactive & Customizable Endpoints Analysis**:
    -   A dedicated module to calculate a wide range of behavioral endpoints.
    -   **Visually Validate**: Load a sample video and your grid settings to see your setup and interactively fine-tune key parameters like the exact center of each tank.
    -   **Flexible Analysis Modes**: Switch between "Top View" and "Side View" modes, which dynamically changes the available parameters and calculated endpoints to match your experiment type (e.g., open field vs. novel tank diving).
    -   **Per-Tank Customization**: Define different zone division axes and percentages for each individual tank to account for complex camera angles.
-   **Publication-Ready Statistical Analysis**:
    -   **Intelligent Test Selection**: Automatically performs normality tests (e.g., Shapiro-Wilk) on your data and selects the appropriate significance test (T-test/ANOVA for normal data, Mann-Whitney/Kruskal-Wallis for non-normal data).
    -   **Full User Control**: Provides the option to override the automatic selection and "force" a parametric test, along with full control over plot aesthetics (colors, fonts, sizes, error bars).
    -   **One-Click Analysis**: Analyze all relevant endpoints across multiple control and treatment groups with a single click.
    -   **Professional Outputs**: Generates high-quality bar plots with individual data points and significance annotations, plus a detailed statistical report in a clean `.csv` format.

---

## Standalone Utilities

EthoGrid also includes powerful, standalone tools for preparing your data.

-   **Video Splitter**: A utility to split long video recordings into smaller, manageable chunks (e.g., 60-minute segments) without re-encoding, preserving the original quality.
-   **Frame Extractor**: A tool for creating datasets. It can recursively find all videos in a directory structure and extract a specified number of random frames from each, creating uniquely named image files that are traceable to their source video and subfolder.

---

## The Complete Workflow: A Step-by-Step Guide

This workflow demonstrates how to go from a raw video to a final statistical graph.

1.  **Prepare Video (Optional)**: Use the **✂️ Video Splitter** to cut a long recording into 1-hour segments.
2.  **Generate Tracking Data**: Use **🎨 Run YOLO Segmentation...** to run your trained model on the video segments. This produces a raw `_segmentations.csv` file for each.
3.  **Annotate Data**: In the main window, **🎬 Load** a sample video and the corresponding `_segmentations.csv`. Interactively create and align the grid, then **💾 Save Settings** to a `grid.json` file.
4.  **Batch Process**: Use **🚀 Batch Annotation...** to apply your saved `grid.json` to all your video segments and their `_segmentations.csv` files. This will generate the final, clean `_with_tanks.csv` files.
5.  **Calculate Endpoints**: Use **📈 Run Analysis...** to process your `_with_tanks.csv` files. In this interactive dialog, you can fine-tune tank centers and other parameters, then run the analysis to produce a `consolidated_endpoints.xlsx` file.
6.  **Perform Statistics**: Use **📊 Statistical Analysis...** to load your `consolidated_endpoints.xlsx` files, assign them to Control and Treatment groups, select the endpoints you want to compare, and run the analysis. The result is a folder of publication-quality plots and a final statistical report.

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
    -   **[Download Detection CSV](https://drive.google.com/file/d/1nhEFKvDwPQzx4OWcioKXqTdT5EgD98eg/view?usp=sharing)**
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

## Documentation

For a deeper dive into the application's architecture and methods, please see the following guides:

-   **[Developer's Guide & Code Architecture](DEVELOPER_GUIDE.md)**: A comprehensive overview of the project structure, class responsibilities, and data flow. Essential reading for anyone looking to modify or contribute to the codebase.
-   **[Statistical Analysis Guide](STATISTICAL_ANALYSIS_GUIDE.md)**: A detailed explanation of every statistical test and calculation performed by the analysis module, including the formulas used and their scientific purpose.

---


## Contributing

Contributions are welcome! Please fork the repository, create a feature branch, and submit a pull request.

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/NewFeature`)
3.  Commit your Changes (`git commit -m 'Add some NewFeature'`)
4.  Push to the Branch (`git push origin feature/NewFeature`)
5.  Open a Pull Request

---

---

## Acknowledgements

This application was developed in the **[Laboratory of Professor Chung-Der Hsiao](https://cdhsiao.weebly.com/pi-cv.html)** in collaboration with **Chung Yuan Christian University, Taiwan 🇹🇼**.

Special credit and sincere gratitude are extended to **Professor Hsiao**, who shared his extensive research experience in biology and multiple domains, providing invaluable guidance and supervision throughout the development of this application.

<p align="center">
  <a href="https://www.cycu.edu.tw/">
    <img src="https://raw.githubusercontent.com/yousaf2018/EthoGrid/main/images/cycu.jpg" alt="Chung Yuan Christian University Logo" width="250">
  </a>
</p>

---

## License


Distributed under the MIT License. See the `LICENSE` file for more information.










