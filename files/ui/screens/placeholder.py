from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class PlaceholderScreen(QWidget):
    """Used for sidebar items we haven't built yet."""
    
    def __init__(self, title: str):
        super().__init__()
        layout = QVBoxLayout(self)
        label = QLabel(f"{title}\n\n(Not built yet)")
        label.setObjectName("placeholderLabel")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)