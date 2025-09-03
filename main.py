# EthoGrid_App/main.py

import os
import sys

# ### THE FIX IS HERE ###
# This environment variable must be set BEFORE importing numpy, cv2, etc.
# which are imported indirectly by main_window.
# This resolves the "OMP: Error #15" crash on some systems.
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

from PyQt5 import QtWidgets, QtCore
from main_window import VideoPlayer

if __name__ == "__main__":
    # Enable High DPI scaling
    # Use hasattr to prevent errors on older PyQt versions
    if hasattr(QtCore.Qt, 'AA_EnableHighDpiScaling'):
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    if hasattr(QtCore.Qt, 'AA_UseHighDpiPixmaps'):
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

    app = QtWidgets.QApplication(sys.argv)
    
    # Use a modern, consistent style across different OS
    app.setStyle('Fusion')
    
    # Create and show the main window
    player = VideoPlayer()
    player.showMaximized() # Start maximized for a better user experience
    
    sys.exit(app.exec_())