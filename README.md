# 📊 EthoGrid: A Spatial Behavior Analysis Tool

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![UI Framework](https://img.shields.io/badge/UI-PyQt5-green.svg)](https://pypi.org/project/PyQt5/)

**EthoGrid** is a desktop application designed for researchers to analyze animal behavior from video recordings. It provides an intuitive interface to overlay a customizable grid onto a video, automatically assign animal detections to grid cells (tanks/arenas), and visualize the resulting spatio-temporal data.
<p align="center">
  <img src="/images/android-chrome-512x512.png" alt="EthoGrid Logo" width="200">
</p>

<!-- ![Tool Overview](images/tool_overview.png)
*A snapshot of the EthoGrid interface showing a video with an overlaid grid, detections, a behavior legend, and a multi-tank timeline.* -->

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
- [Building EthoGrid from Source (for Developers)](#building-ethogrid-from-source-for-developers)
- [Contributing](#contributing)
- [License](#license)
- [Video Demo](#video-demo)
- [Full Application Source Code](#full-application-source-code)

---

## Key Features

- **Interactive Video Playback**: Standard controls to play, pause, stop, and seek through your video for detailed frame-by-frame inspection.
- **Customizable Grid System**: Define any number of rows and columns to create a virtual grid that perfectly matches the tank or arena setup in your video.
- **Dynamic Tank Assignment**: Automatically assigns object detections from a CSV file to the corresponding grid cell (tank) they fall within, adding valuable spatial context to your data.
- **Interactive Grid Adjustment**: Easily translate, rotate, and scale the grid using intuitive sliders or direct mouse manipulation (click-and-drag) to ensure perfect alignment with your experimental setup.
- **Data Export (Annotated Video + CSV)**: Generate shareable and publication-ready outputs, including a new video file with all annotations burned in and an enriched CSV file with tank assignments.
- **Multi-Tank Timeline**: A powerful visualization at the bottom of the screen showing which behaviors are occurring in each tank over the entire video duration, allowing for at-a-glance comparison between subjects.
- **Settings Persistence**: Save and load your complex grid configurations to a JSON file, allowing you to easily re-apply the same setup to multiple videos without manual reconfiguration.
- **Behavior-based Coloring**: Automatically assigns unique, consistent colors to different behaviors for clear visual distinction in both the video bounding boxes and the timeline.

---

## Getting Started

### For Users (Recommended)

No installation is needed. Simply download and run the application.

1. Download APP for windows from this **[Link](https://drive.google.com/file/d/1W1YgaLJgyYlqtTRTiLl5NHyVf-mxkm8I/view?usp=sharing)**
3. Double-click the downloaded file to launch the application.
4. Download raw video from this **[Link](https://drive.google.com/file/d/1ImicvjG2tSUdRys2nu_XtJ7B9jcZpnaI/view?usp=sharing)** for testing
5. Download Yolov11 detection csv file from this **[Link](https://drive.google.com/file/d/1nih-USaZ6P_Cn06CqzXZhyNynoPn0WCd/view?usp=sharing)**
6. Download setting json file from this **[Link](https://drive.google.com/file/d/1nPepLlHvBuyjzYqWehX1lnBLRMe-rEAW/view?usp=sharing)** for selecting grid by defualt on video 
7. After downloading all required files just load one by one by using buttons on GUI 

### For Developers

If you wish to run the tool from source code:

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/EthoGrid.git
cd EthoGrid

# 2. Create and activate a virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# 3. Install the required libraries from the requirements file
pip install -r requirements.txt

# 4. Run the application
python ethogrid_app.py 
```


## How to Use EthoGrid: A Step-by-Step Workflow

![EthoGrid Interface](/images/EthoGridGUI.png)

1. **Load Data**: Begin by clicking 🎬 Load Video to open your video file, followed by 📄 Load Detections to import your CSV data.
2. **Configure Grid**: Use the Tank Configuration panel to match the grid to your experimental setup (e.g., set Columns to 5 and Rows to 2 for a 10-tank setup).
3. **Align Grid**: Use the Rotation, Scale, and Move sliders, or click-and-drag the grid directly on the video, to perfectly align it with your arenas. The data will re-process automatically with each adjustment.
4. **Review & Analyze**: Play the video to see the live annotations. The color-coded bounding boxes and the timeline provide immediate visual feedback on the assigned behaviors and locations.
5. **Export Results**: Once satisfied, click 📝 Save w/ Tanks to get your enriched CSV data and 📹 Export Video to create a fully annotated video for presentations or publications.

---

## Detailed Guide to the Interface

### 1. File Operations
- **🎬 Load Video**: Opens a file dialog to select the primary video for analysis.
- **📄 Load Detections**: Opens a dialog to select the corresponding CSV file containing your detection data.
- **📝 Save w/ Tanks**: Exports a new CSV file that includes the original data plus the calculated tank_number for each detection.
- **📹 Export Video**: Renders and saves a new .mp4 video with all visual annotations (grid, boxes, legend, timeline) permanently burned in.

### 2. Settings Management
- **📂 Load Settings**: Loads a previously saved grid configuration from a .json file, instantly applying the grid's dimensions and transformations.
- **💾 Save Settings**: Saves the current grid layout (columns, rows, rotation, scale, position) to a .json file for future use.

### 3. Tank Configuration Panel
This is the main control center for grid alignment.

- **Columns, Rows**: Spin-boxes to define the grid's dimensions.
- **Grid Line Thickness**: A slider to adjust the thickness of the green grid lines in the final exported video.
- **Rotation / Scale / Move**: Sliders to precisely rotate, stretch, and shift the grid for perfect alignment.
- **Reset Grid**: A button to instantly revert all grid transformations to their default state.

### 4. Playback & Navigation
- **▶ Play / ⏸ Pause / ⏹ Stop**: Standard media controls for video playback. Stop also resets the video to the first frame.
- **Frame slider**: A draggable slider that allows you to quickly seek to any frame in the video for detailed inspection. The current frame number is displayed alongside it.

### 5. Data Visualization
- **Live bounding boxes**: Detections are shown on the video player with colored rectangles. The color corresponds to the behavior, and the assigned tank number is displayed above the box.
- **Behavior legend**: A panel on the right that automatically populates with each unique behavior found in your CSV file and assigns it a consistent color.
- **Multi-tank timeline**: Located at the bottom, this widget displays a dedicated timeline for each tank. Colored segments show the sequence of behaviors performed over time, providing a comprehensive overview of the entire experiment.

---

## Required Input File Formats

### Video File
Standard video formats such as .mp4, .avi, .mov, and .mkv are supported. For best results, use videos from a static, unmoving camera.

### Detections CSV File
The input CSV file must contain the following headers: `frame_idx`, `x1`, `y1`, `x2`, `y2`, `class_name`. Additional columns are allowed and will be preserved.

Example CSV format:
```csv
frame_idx,x1,y1,x2,y2,class_name,confidence
0,150,220,180,250,walking,0.95
0,450,225,480,255,resting,0.88
1,152,221,182,251,walking,0.96
```


## Output Files

### Annotated CSV
A copy of your original CSV file with a new `tank_number` column appended, linking each detection to a specific grid cell.

## Example Output Video
[![EthoGrid Demo](https://img.youtube.com/vi/hQx2iBo1Gd4/0.jpg)](https://www.youtube.com/watch?v=hQx2iBo1Gd4)

---


## Example Output

https://github.com/yourusername/EthoGrid/assets/videos/ethogrid-demo.mp4

*Video 1: EthoGrid processing sample video with behavior annotations*

## Building EthoGrid from Source (for Developers)

To create a standalone `EthoGrid.exe` from the source code, use PyInstaller:

```bash
# 1. Ensure PyInstaller is installed in your environment
pip install pyinstaller

# 2. Run the build command from the project's root directory
#    (Make sure your main script is named ethogrid_app.py)
pyinstaller --name "EthoGrid" --onefile --windowed --icon="path/to/icon.ico" ethogrid_app.py
```


## PyInstaller Options

- `--name "EthoGrid"`: Sets the final name of the executable
- `--onefile`: Packages everything into a single, portable executable file  
- `--windowed`: Prevents the black command prompt from appearing when the app is launched

The final binary (e.g., `EthoGrid.exe`) will be located in the `dist/` folder.

---

## Contributing

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are greatly appreciated.

### How to Contribute:

1. Fork the Project
2. Create your Feature Branch
```bash
git checkout -b feature/AmazingFeature

git commit -m 'Add some AmazingFeature'

git push origin feature/AmazingFeature

```

