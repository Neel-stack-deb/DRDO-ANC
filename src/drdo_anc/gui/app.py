import os
import sys
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from drdo_anc.gui.bridge import GUIBridge


def run_gui(
  bridge: GUIBridge | None = None,
  *,
  on_ready: Callable[[], None] | None = None,
  on_shutdown: Callable[[], None] | None = None,
) -> None:
  """Run the standalone GUI application."""

  # Pick up QML edits on the next launch (no stale .qmlc).
  os.environ.setdefault("QML_DISABLE_DISK_CACHE", "1")

  QGuiApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
  QGuiApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
  QQuickStyle.setStyle("Fusion")

  app = QGuiApplication(sys.argv)
  app.setOrganizationName("DRDO")
  app.setOrganizationDomain("drdo.gov.in")
  app.setApplicationName("DRDO-ANC Monitor")

  if bridge is None:
    bridge = GUIBridge()

  engine = QQmlApplicationEngine()
  engine.rootContext().setContextProperty("guiBridge", bridge)
  bridge.start_timer()

  qml_file = Path(__file__).parent / "qml" / "Main.qml"
  engine.load(os.fspath(qml_file))

  if not engine.rootObjects():
    print("CRITICAL ERROR: Failed to load QML.")
    bridge.stop_timer()
    sys.exit(-1)

  def _handle_shutdown() -> None:
    bridge.stop_timer()
    if on_shutdown is not None:
      on_shutdown()

  app.aboutToQuit.connect(_handle_shutdown)

  if on_ready is not None:
    on_ready()

  sys.exit(app.exec())


if __name__ == "__main__":
  run_gui()
