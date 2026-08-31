import sys
import os
from pathlib import Path
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import Qt

from drdo_anc.gui.bridge import GUIBridge

def run_gui(bridge: GUIBridge = None):
    """Runs the standalone GUI application."""
    # Set high DPI scaling
    QGuiApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QGuiApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    
    app = QGuiApplication(sys.argv)
    app.setOrganizationName("DRDO")
    app.setOrganizationDomain("drdo.gov.in")
    app.setApplicationName("DRDO-ANC Monitor")
    
    engine = QQmlApplicationEngine()
    
    # Initialize the bridge and expose to QML
    if bridge is None:
        bridge = GUIBridge()
        
    engine.rootContext().setContextProperty("guiBridge", bridge)
    
    # Start the bridge update timer
    bridge.start_timer()
    
    # Load Main.qml
    qml_file = Path(__file__).parent / "qml" / "Main.qml"
    engine.load(os.fspath(qml_file))
    
    if not engine.rootObjects():
        print("CRITICAL ERROR: Failed to load QML.")
        sys.exit(-1)
        
    sys.exit(app.exec())

if __name__ == "__main__":
    run_gui()
