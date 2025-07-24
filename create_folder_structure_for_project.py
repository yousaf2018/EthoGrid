import os
import sys

def create_project_structure():
    """
    Creates the necessary directories and empty files for the EthoGrid_App project.
    """
    base_dir = "EthoGrid_App"
    
    # Define the complete file structure
    # Paths are relative to the base_dir
    file_structure = [
        "main.py",
        "main_window.py",
        "core/__init__.py",
        "core/grid_manager.py",
        "workers/__init__.py",
        "workers/video_loader.py",
        "workers/video_saver.py",
        "workers/detection_processor.py",
        "widgets/__init__.py",
        "widgets/timeline_widget.py"
    ]

    print(f"Creating project structure in folder: '{base_dir}'...")

    # Create the base directory if it doesn't exist
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
        print(f"Created base directory: {base_dir}/")

    # Iterate through the file structure and create files and directories
    for path in file_structure:
        # Create a full path by joining the base directory and the relative path
        full_path = os.path.join(base_dir, path)
        
        # Get the directory part of the path
        directory = os.path.dirname(full_path)
        
        # Create the directory if it's not the base directory and doesn't exist
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Created sub-directory: {directory}/")
            
        # Create the empty file if it doesn't exist
        if not os.path.exists(full_path):
            with open(full_path, 'w') as f:
                # You can write a placeholder comment if you like
                if path.endswith("__init__.py"):
                    f.write("# This file makes this a Python package\n")
                else:
                    f.write(f"# EthoGrid_App/{path}\n\n")
            print(f"  - Created file: {full_path}")
        else:
            print(f"  - File already exists, skipping: {full_path}")
            
    print("\nProject structure created successfully!")
    print("You can now copy and paste the code into the generated files.")


if __name__ == "__main__":
    create_project_structure()