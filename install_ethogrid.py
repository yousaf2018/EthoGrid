import os
import subprocess
import sys
import platform

# -------------------------------
# Configurable variables
# -------------------------------
ENV_NAME = "ethogrid-env-test"  # change if you want a different env name
PYTHON_VERSION = "3.10"
CONDA_CHANNEL = "conda-forge"

# Pip-only packages
PIP_PACKAGES = [
    "ultralytics",
    "pyinstaller",
    "pyinstaller-hooks-contrib"
]

# Conda packages (all from conda-forge)
CONDA_PACKAGES = [
    "opencv",
    "pyqt",
    "qt",
    "numpy",
    "pandas",
    "matplotlib",
    "seaborn",
    "pillow",
    "scipy",
    "openpyxl"
]

# -------------------------------
# Helper function to run shell commands
# -------------------------------
def run(cmd):
    print(f"\nRunning: {cmd}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"❌ Command failed: {cmd}")
        sys.exit(1)

# -------------------------------
# Detect OS
# -------------------------------
OS_NAME = platform.system()
print(f"Detected OS: {OS_NAME}")
print("Make sure current Conda environment is deactivated before running this script.")

# -------------------------------
# Check if environment exists
# -------------------------------
print(f"\nChecking if environment '{ENV_NAME}' exists...")
envs_list = subprocess.run("conda env list", shell=True, capture_output=True, text=True).stdout
if ENV_NAME in envs_list:
    print(f"Environment '{ENV_NAME}' exists. Removing it...")
    run(f"conda remove -n {ENV_NAME} --all -y")
else:
    print(f"Environment '{ENV_NAME}' does not exist. No need to remove.")

# -------------------------------
# Create new environment
# -------------------------------
print(f"\nCreating new environment '{ENV_NAME}' with Python {PYTHON_VERSION}...")
run(f"conda create -n {ENV_NAME} python={PYTHON_VERSION} -y")

# -------------------------------
# Install Conda packages
# -------------------------------
conda_pkg_str = " ".join(CONDA_PACKAGES)
print(f"\nInstalling Conda packages: {conda_pkg_str} ...")
run(f"conda install -n {ENV_NAME} -c {CONDA_CHANNEL} {conda_pkg_str} -y")

# -------------------------------
# Install pip-only packages
# -------------------------------
pip_pkg_str = " ".join(PIP_PACKAGES)
print(f"\nInstalling pip-only packages: {pip_pkg_str} ...")
run(f"conda run -n {ENV_NAME} pip install {pip_pkg_str}")

# -------------------------------
# Done
# -------------------------------
print("\n✅ Setup complete!")
print(f"To activate the environment, run:\n  conda activate {ENV_NAME}")
print("Then run your project:\n  python main.py")
