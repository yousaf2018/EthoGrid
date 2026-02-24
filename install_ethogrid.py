import subprocess
import platform
import sys


ENV_NAME = "ethogrid-env-test"


def run(cmd):
    print(f"\n>>> Running: {cmd}\n")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print("\n❌ Command failed. Stopping installer.")
        sys.exit(result.returncode)


def check_conda():
    try:
        subprocess.run("conda --version", shell=True, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print("❌ Conda not found. Please install Anaconda/Miniconda first.")
        sys.exit(1)


def main():

    os_name = platform.system()
    print("=" * 60)
    print("EthoGrid Automatic Installer")
    print(f"Detected OS: {os_name}")
    print("=" * 60)

    check_conda()

    print("\n⚠ IMPORTANT:")
    print("Deactivate any active Conda environment before continuing.")
    print("Run this if needed:")
    print("   conda deactivate\n")

    input("Press ENTER to continue...")

    # STEP 1 — Environment setup
    print("\n✅ STEP 1 — Creating fresh environment")

    run(f"conda remove -n {ENV_NAME} --all -y")
    run(f"conda create -n {ENV_NAME} python=3.10 -y")

    # STEP 2 — Conda packages
    print("\n✅ STEP 2 — Installing Qt/OpenCV stack")

    run(
        f'conda install -n {ENV_NAME} -c conda-forge '
        'opencv pyqt qt numpy pandas matplotlib seaborn pillow scipy openpyxl -y'
    )

    # STEP 3 — Pip packages
    print("\n✅ STEP 3 — Installing pip packages")

    if os_name == "Windows":
        activate_cmd = f"conda activate {ENV_NAME} && "
    else:
        activate_cmd = f"source $(conda info --base)/etc/profile.d/conda.sh && conda activate {ENV_NAME} && "

    run(
        activate_cmd +
        "pip install ultralytics pyinstaller pyinstaller-hooks-contrib filterpy norfair"
    )

    # DONE
    print("\n" + "=" * 60)
    print("🎉 INSTALLATION COMPLETE!")
    print("=" * 60)

    print("\nTo run EthoGrid:")
    print(f"conda activate {ENV_NAME}")
    print("python main.py\n")


if __name__ == "__main__":
    main()
