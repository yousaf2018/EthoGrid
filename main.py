# EthoGrid_App/main.py

import sys
from PyQt5 import QtWidgets, QtCore

from main_window import VideoPlayer

if __name__ == "__main__":
    # Set HighDPI scaling attributes
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

    app = QtWidgets.QApplication(sys.argv)
    
    # Use a modern style
    app.setStyle('Fusion')
    
    # Create and show the main window
    player = VideoPlayer()
    player.show()
    
    sys.exit(app.exec_())
