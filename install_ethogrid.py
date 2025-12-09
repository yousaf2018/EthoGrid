#!/usr/bin/env python3
import os
import sys
import subprocess
import platform

ENV_NAME = "ethogrid_env_tracker"

def run(cmd):
    """Run command and exit if fails."""
    print("\n>>", cmd)
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        print("❌ Command failed:", cmd)
        sys.exit(1)

def main():

    print("==============================================================")
    print(" EthoGrid + YOLO + BoxMOT + Norfair + PyQt Installer")
    print(" (Windows & Linux Compatible)")
    print("==============================================================\n")

    system = platform.system()
    print("Detected OS:", system)

    # ----------------------------------------------------------
    # 1. Create Conda Environment
    # ----------------------------------------------------------
    run(f"conda create -n {ENV_NAME} python=3.10 -y")

    # ----------------------------------------------------------
    # 2. Install compiled libraries via conda-forge ONLY
    #    (This avoids PyQt/Qt conflicts completely!)
    # ----------------------------------------------------------
    print("\nInstalling compiled libraries via conda-forge ...")

    compiled_packages = (
        "numpy=1.26 "
        "opencv=4.8 "
        "pyqt=5 "
        "pyqt5-sip "
        "scipy "
        "pandas "
        "matplotlib "
        "seaborn "
        "scikit-learn"
    )

    run(f"conda install -n {ENV_NAME} -c conda-forge {compiled_packages} -y")

    # ----------------------------------------------------------
    # 3. Install PyTorch (pip safe – pure python wheels)
    # ----------------------------------------------------------
    print("\nInstalling PyTorch (CPU only)...")
    run(f"conda run -n {ENV_NAME} pip install torch torchvision torchaudio")

    # ----------------------------------------------------------
    # 4. Install YOLO + BoxMOT
    # ----------------------------------------------------------
    print("\nInstalling Ultralytics + BoxMOT...")
    run(f"conda run -n {ENV_NAME} pip install ultralytics")
    run(f"conda run -n {ENV_NAME} pip install boxmot")

    # ----------------------------------------------------------
    # 5. Install Norfair + FilterPy
    # ----------------------------------------------------------
    print("\nInstalling Norfair + FilterPy...")
    run(f"conda run -n {ENV_NAME} pip install norfair")
    run(f"conda run -n {ENV_NAME} pip install filterpy")

    # ----------------------------------------------------------
    # 6. Install remaining project requirements
    # ----------------------------------------------------------
    print("\nInstalling project requirements from requirements.txt ...")
    run(f"conda run -n {ENV_NAME} pip install -r requirements.txt")

    # ----------------------------------------------------------
    # 7. Launch EthoGrid
    # ----------------------------------------------------------
    print("\n✅ Installation Complete!")
    print("✅ Launching EthoGrid...\n")

    run(f"conda run -n {ENV_NAME} python main.py")


if __name__ == "__main__":
    main()
