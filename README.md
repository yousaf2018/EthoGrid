# 📊 EthoGrid: A Spatial Behavior Analysis Tool

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![UI Framework](https://img.shields.io/badge/UI-PyQt5-green.svg)](https://pypi.org/project/PyQt5/)

**EthoGrid** is a desktop application designed for researchers to analyze animal behavior from video recordings. It provides an intuitive interface to overlay a customizable grid onto a video, automatically assign animal detections to grid cells (tanks/arenas), and visualize the resulting spatio-temporal data.

*The EthoGrid interface showing a video with an overlaid grid, detections, a behavior legend, and a multi-tank timeline.*

---

## Table of Contents
- [Key Features](#key-features)
- [Getting Started](#getting-started)
  - [For Users (Recommended)](#for-users-recommended)
  - [For Developers](#for-developers)
- [How to Use EthoGrid: A Step-by-Step Workflow](#how-to-use-ethogrid-a-step-by-step-workflow)
- [Detailed Guide to the Interface](#detailed-guide-to-the-interface)
  - [File Operations](#1-file-operations)
  - [Settings Management](#2-settings-management)
  - [Tank Configuration Panel](#3-tank-configuration-panel)
  - [Playback & Navigation](#4-playback--navigation)
  - [Data Visualization](#5-data-visualization)
- [Required Input File Formats](#required-input-file-formats)
  - [Video File](#video-file)
  - [Detections CSV File](#detections-csv-file)
- [Output Files](#output-files)
- [Building EthoGrid from Source](#building-ethogrid-from-source-for-developers)
- [Contributing](#contributing)
- [License](#license)
- [Full Application Source Code (EthoGrid)](#full-application-source-code-ethogrid)

---

## Key Features

- **Interactive Video Playback**: Standard controls to play, pause, stop, and seek through your video.
- **Customizable Grid System**: Define any number of rows and columns to create a grid that matches the tank setup in your video.
- **Dynamic Tank Assignment**: Automatically assigns object detections from a CSV file to the corresponding grid cell (tank) they fall within.
- **Interactive Grid Adjustment**: Easily translate, rotate, and scale the grid using intuitive sliders or direct mouse manipulation to perfectly align it with your video.
- **Data Export**:
    - **Annotated Video**: Export a new video file with the grid, bounding boxes, a behavior legend, and a multi-tank timeline burned in.
    - **Enriched CSV**: Save a new CSV file containing all original detection data plus the newly assigned `tank_number` for each detection.
- **Multi-Tank Timeline**: A powerful visualization showing which behaviors are occurring in each tank over the entire video duration.
- **Settings Persistence**: Save and load your grid configuration to a JSON file, allowing you to easily re-apply the same setup to multiple videos.
- **Behavior-based Coloring**: Automatically assigns unique colors to different behaviors for clear visual distinction in both the video and the timeline.

## Getting Started

### For Users (Recommended)

The easiest way to use EthoGrid is to download the pre-built executable. No installation or Python knowledge is required.

1.  Navigate to the **[Releases Page](https://github.com/YOUR_USERNAME/EthoGrid/releases)** of this repository.
2.  Download the `EthoGrid.exe` file from the latest release.
3.  Double-click the file to run the application.

### For Developers

If you want to run EthoGrid from the source code:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/YOUR_USERNAME/EthoGrid.git
    cd EthoGrid
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    # Using venv
    python -m venv venv
    .\venv\Scripts\activate

    # Or using Conda
    conda create --name ethogrid_env python=3.9
    conda activate ethogrid_env
    ```

3.  **Install the required dependencies:**
    ```bash
    pip install pyqt5 opencv-python numpy
    ```

4.  **Run EthoGrid:**
    ```bash
    python ethogrid_app.py 
    ```
    *(Assuming you save the code below as `ethogrid_app.py`)*

## How to Use EthoGrid: A Step-by-Step Workflow

Follow these steps for a typical analysis session.

1.  **Load Video**: Click `🎬 Load Video` to open your raw video file (`.mp4`, `.avi`, etc.).
2.  **Load Detections**: Click `📄 Load Detections` to open your corresponding CSV file. EthoGrid will immediately process the detections and assign them to tanks based on the current grid.
3.  **Configure the Grid**: This is the most important interactive step.
    - Use the **Tank Configuration** panel to set the correct number of `Columns` and `Rows`.
    - Use the `Rotation`, `Scale`, and `Move` sliders to align the green grid with the tanks in your video.
    - **Alternatively**, adjust the grid directly with the mouse:
        - **Drag the red center dot** to move the entire grid.
        - **Click and drag anywhere else** on the video to rotate the grid around its center.
    - Detections and the timeline will update in real-time as you adjust the grid.
4.  **Analyze and Review**:
    - Use the playback controls (`▶ Play`, `⏸ Pause`, `⏹ Stop`) and the frame slider to navigate the video.
    - Observe the color-coded bounding boxes and the assigned tank number above each box.
    - Watch the red indicator on the **Timeline Widget** move in sync with the video.
5.  **Export Results**: Once you are satisfied with the alignment:
    - Click `📝 Save w/ Tanks` to generate a new CSV file with the `tank_number` column.
    - Click `📹 Export Video` to render a new, fully annotated video file.

---

## Detailed Guide to the Interface

### 1. File Operations

-   **`🎬 Load Video`**: Opens a dialog to select your video file.
-   **`📄 Load Detections`**: Opens a dialog to select your CSV detection data.
-   **`📝 Save w/ Tanks`**: Saves a new CSV file including the `tank_number` for each detection.
-   **`📹 Export Video`**: Renders a new video with all visual annotations burned in.

### 2. Settings Management

-   **`📂 Load Settings`**: Loads a grid configuration (`.json` file) to restore the grid's layout.
-   **`💾 Save Settings`**: Saves the current grid configuration to a `.json` file for later use.

### 3. Tank Configuration Panel

This panel is the primary control center for aligning the grid.

-   **`Columns` / `Rows`**: Set the dimensions of the grid.
-   **`Line Thickness`**: Adjusts the thickness of the grid lines in the exported video.
-   **`Rotation`, `Scale X/Y`, `Move X/Y` Sliders**: Fine-tune the grid's orientation and position.
-   **`Reset Grid`**: Instantly resets all grid transformations to their default state.

### 4. Playback & Navigation

-   **`▶ Play` / `⏸ Pause` / `⏹ Stop`**: Standard controls for video playback.
-   **Frame Slider & Counter**: Seek to any frame and view the current position.

### 5. Data Visualization

-   **Main Video Display**: Shows the video with the overlaid grid and colored bounding boxes.
-   **Behavior Legend**: A panel on the right listing each behavior and its assigned color.
-   **Timeline Widget**: A multi-lane timeline at the bottom showing the behavior sequence for each tank.

---

## Required Input File Formats

### Video File

Standard video formats (e.g., `.mp4`, `.avi`, `.mov`) are supported. A static camera view is recommended.

### Detections CSV File

The input CSV **must** contain the following headers: `frame_idx`, `x1`, `y1`, `x2`, `y2`, `class_name`.

**Example `detections.csv`:**
```csv
frame_idx,x1,y1,x2,y2,class_name,confidence
0,150,220,180,250,walking,0.95
0,450,225,480,255,resting,0.88
1,152,221,182,251,walking,0.96