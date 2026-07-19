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
    return path.read_text(encoding="utf-8")


def main():
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