"""PlaceholderScreen: a plain "not built yet" page for sidebar entries
that don't have a real screen (currently: Availability Checker's slot
before it existed — kept around for any future not-yet-built section).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class PlaceholderScreen(QWidget):
    """Used for sidebar items we haven't built yet."""

    def __init__(self, title: str):
        """title: the section name shown, e.g. "Availability Checker"."""
        super().__init__()
        layout = QVBoxLayout(self)
        label = QLabel(f"{title}\n\n(Not built yet)")
        label.setObjectName("placeholderLabel")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
