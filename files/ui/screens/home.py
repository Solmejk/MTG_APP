from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)

from app import MTGApp


class HomeScreen(QWidget):
    refresh_requested = Signal()
    
    def __init__(self, app: MTGApp):
        super().__init__()
        self.app = app
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        
        welcome_text = f"Welcome, {app.username}" if app.is_logged_in else "Welcome"
        title = QLabel(welcome_text)
        title.setObjectName("homeTitle")
        layout.addWidget(title)

        if not app.is_logged_in:
            hint = QLabel("Log in via the avatar in the sidebar to load your collection.")
            hint.setObjectName("homeHint")
            layout.addWidget(hint)
        
        stats_frame = QFrame()
        stats_frame.setObjectName("statsFrame")
        stats_layout = QVBoxLayout(stats_frame)
        
        total_cards = sum(c["quantity"] for c in app.collection.cards)
        unique_cards = len(app.collection.cards)
        total_decks = len(app.decks)
        active_decks = sum(1 for d in app.decks if d.active)
        
        stats_layout.addWidget(QLabel(f"Collection: {total_cards} cards ({unique_cards} unique)"))
        stats_layout.addWidget(QLabel(
            f"Decks: {total_decks} total "
            f"({active_decks} active, {total_decks - active_decks} archived)"
        ))
        layout.addWidget(stats_frame)
        
        # Refresh button
        button_row = QHBoxLayout()
        self._refresh_btn = QPushButton("Refresh from Moxfield")
        self._refresh_btn.setEnabled(app.is_logged_in)
        self._refresh_btn.clicked.connect(self.refresh_requested.emit)
        button_row.addWidget(self._refresh_btn)
        button_row.addStretch()
        layout.addLayout(button_row)

        layout.addStretch()

    def set_refresh_enabled(self, enabled: bool):
        self._refresh_btn.setEnabled(enabled)
        self._refresh_btn.setText("Refresh from Moxfield" if enabled else "Refreshing…")