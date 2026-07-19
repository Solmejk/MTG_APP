"""Entry point for the GUI app. Sets up crash logging, builds the
QApplication and MainWindow, and wires up a clean-shutdown handler so
background image/deck-load threads don't get torn down mid-flight. Run
this file directly to launch the app.
"""

import faulthandler
import sys
from pathlib import Path

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication

from app import MTGApp
from ui.main_window import MainWindow
import session


STYLE_PATH = Path(__file__).parent / "ui" / "style.qss"

_crash_log = open(Path(__file__).parent / "crash.log", "w")
faulthandler.enable(file=_crash_log)


def load_stylesheet(path: Path) -> str:
    """Reads a .qss stylesheet file as text. path: path to the .qss file.
    Returns its contents, ready to pass to QApplication.setStyleSheet()."""
    return path.read_text(encoding="utf-8")


def main():
    """Builds and runs the application: loads the last-logged-in user (if
    any) from session.py, creates the QApplication/MainWindow, and blocks
    until the window closes."""
    mtg_app = MTGApp(session.get_saved_username())
    # No eager deck.load() — each deck loads on demand when its detail screen opens

    qt_app = QApplication(sys.argv)
    qt_app.setStyleSheet(load_stylesheet(STYLE_PATH))

    window = MainWindow(mtg_app)
    window.show()

    def _shutdown():
        # Background image/deck-load tasks (ui/image_loader.py, ui/background.py)
        # hold Qt signal objects that must not be destroyed while a worker
        # thread is still using them. Drop anything not yet started and let
        # the few still-running tasks finish before Qt tears down.
        pool = QThreadPool.globalInstance()
        pool.clear()
        pool.waitForDone()

    qt_app.aboutToQuit.connect(_shutdown)
    sys.exit(qt_app.exec())


if __name__ == "__main__":
    main()
