# main.py

import sys
import os
import time
from PyQt5 import QtWidgets, QtCore, QtGui

# This is crucial: it adds the application's folder to the Python path
# so that it can find the 'core', 'widgets', and 'workers' directories.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'EthoGrid_App'))

from main_window import VideoPlayer

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    # Correctly join the path to look inside the app's structure
    return os.path.join(base_path, relative_path)

def create_rounded_pixmap(source_pixmap):
    """Creates a rounded (circular) pixmap from a square source."""
    size = source_pixmap.size()
    mask = QtGui.QBitmap(size)
    mask.fill(QtCore.Qt.white)
    
    painter = QtGui.QPainter(mask)
    painter.setBrush(QtCore.Qt.black)
    painter.drawRoundedRect(0, 0, size.width(), size.height(), 99, 99)
    painter.end()
    
    source_pixmap.setMask(mask)
    return source_pixmap

if __name__ == "__main__":
    os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
    
    if hasattr(QtCore.Qt, 'AA_EnableHighDpiScaling'):
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    if hasattr(QtCore.Qt, 'AA_UseHighDpiPixmaps'):
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # --- Splash Screen Logic ---
    splash = None
    try:
        logo_path = resource_path("images/logo.png")
        if os.path.exists(logo_path):
            pixmap = QtGui.QPixmap(logo_path)
            
            # ### THE FIX IS HERE ###
            # Create a rounded version of the pixmap
            rounded_pixmap = create_rounded_pixmap(pixmap)
            
            splash = QtWidgets.QSplashScreen(rounded_pixmap, QtCore.Qt.WindowStaysOnTopHint)
            # The mask is now inherent to the pixmap, but setting it again is safe
            splash.setMask(rounded_pixmap.mask())
            splash.show()
            app.processEvents()
        else:
            print(f"Splash screen logo not found at: {logo_path}")
    except Exception as e:
        print(f"Could not create splash screen: {e}")

    # Load the main window (this can take a moment)
    player = VideoPlayer()
    
    # Ensure splash screen is visible for at least 3 seconds
    time.sleep(3)
    
    if splash:
        splash.finish(player)
        
    player.show()
    
    sys.exit(app.exec_())