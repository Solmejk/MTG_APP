from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
)

from app import MTGApp
from ui.flow_layout import FlowLayout
from ui.components.image_tile import ImageTile
from ui.components.toggle_switch import ToggleSwitch


TILE_WIDTH = 220
TILE_HEIGHT = 310


class DecksScreen(QWidget):
    """Grid of clickable deck tiles, with active/format filters."""
    
    deck_selected = Signal(object)
    
    def __init__(self, app: MTGApp):
        super().__init__()
        self.app = app
        self._active_only = True
        self._commander_only = True
        
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        
        # Top bar: title + filter toggles
        top_bar = QWidget()
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(40, 30, 40, 20)
        top_layout.setSpacing(20)
        
        header = QLabel("Decks")
        header.setObjectName("screenTitle")
        top_layout.addWidget(header)
        top_layout.addStretch()
        
        # Filter: Active only
        active_label = QLabel("Active only")
        active_label.setObjectName("filterLabel")
        top_layout.addWidget(active_label)
        
        self._active_toggle = ToggleSwitch(checked=True)
        self._active_toggle.toggled.connect(self._on_active_toggled)
        top_layout.addWidget(self._active_toggle)
        
        # Filter: Commander only
        commander_label = QLabel("Commander only")
        commander_label.setObjectName("filterLabel")
        top_layout.addWidget(commander_label)
        
        self._commander_toggle = ToggleSwitch(checked=True)
        self._commander_toggle.toggled.connect(self._on_commander_toggled)
        top_layout.addWidget(self._commander_toggle)
        
        outer.addWidget(top_bar)
        
        # Scrollable grid
        scroll = QScrollArea()
        scroll.setObjectName("decksScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self._grid_container = QWidget()
        self._flow = FlowLayout(self._grid_container, margin=0, spacing=20)
        self._grid_container.setContentsMargins(40, 0, 40, 40)
        
        scroll.setWidget(self._grid_container)
        outer.addWidget(scroll, 1)
        
        self._rebuild_grid()
    
    def _on_active_toggled(self, value: bool):
        self._active_only = value
        self._rebuild_grid()
    
    def _on_commander_toggled(self, value: bool):
        self._commander_only = value
        self._rebuild_grid()
    
    def _filtered_decks(self):
        for deck in self.app.decks:
            if self._active_only and not deck.active:
                continue
            if self._commander_only and deck.format != "commander":
                continue
            yield deck
    
    def _rebuild_grid(self):
        # Clear existing tiles
        while self._flow.count():
            item = self._flow.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        # Add tiles for filtered decks
        for deck in self._filtered_decks():
            commander_url = self._commander_url(deck)
            tile = ImageTile(
                image_url=commander_url,
                cache_name=f"commander_{deck.deck_id}",
                caption=deck.name,
                payload=deck,
                width=TILE_WIDTH,
                height=TILE_HEIGHT,
                radius=12,
            )
            tile.clicked.connect(self.deck_selected.emit)
            tile.load_image()
            self._flow.addWidget(tile)
    
    def _commander_url(self, deck):
        if deck.commanders and "image_url" in deck.commanders[0]:
            return deck.commanders[0]["image_url"]
        return ""