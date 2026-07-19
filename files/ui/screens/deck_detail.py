from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
)

import scryfall
from ui.components.toggle_switch import ToggleSwitch
from ui.flow_layout import FlowLayout
from ui.components.image_tile import ImageTile
from ui.card_type import group_cards


CARD_TILE_WIDTH = 140
CARD_TILE_HEIGHT = 196  # roughly 5:7 like the deck grid


class DeckDetailScreen(QWidget):
    """Detail view for a single deck. Call show_deck() to swap content."""
    
    back_requested = Signal()
    card_clicked = Signal(dict)

    def __init__(self):
        super().__init__()
        self.deck = None
        
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        
        # Top bar (back button)
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(40, 30, 40, 10)
        
        back_btn = QPushButton("← Back")
        back_btn.setObjectName("backButton")
        back_btn.clicked.connect(self.back_requested.emit)
        top_bar.addWidget(back_btn)
        top_bar.addStretch()
        outer.addLayout(top_bar)
        
        # Header (name + value on left, active toggle on right)
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(40, 0, 40, 20)
        header_layout.setSpacing(20)
        
        # Left column: title stacked over value
        left_column = QWidget()
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(2)
        
        self.title_label = QLabel()
        self.title_label.setObjectName("screenTitle")
        left_layout.addWidget(self.title_label)
        
        self.value_label = QLabel()
        self.value_label.setObjectName("deckDetailValue")
        left_layout.addWidget(self.value_label)
        
        header_layout.addWidget(left_column)
        header_layout.addStretch()
        
        # Right: active label + toggle
        toggle_row = QWidget()
        toggle_layout = QHBoxLayout(toggle_row)
        toggle_layout.setContentsMargins(0, 0, 0, 0)
        toggle_layout.setSpacing(8)
        
        self.active_label = QLabel("Active")
        self.active_label.setObjectName("activeLabel")
        toggle_layout.addWidget(self.active_label)
        
        self.active_toggle = ToggleSwitch()
        self.active_toggle.toggled.connect(self._toggle_active)
        toggle_layout.addWidget(self.active_toggle)
        
        header_layout.addWidget(toggle_row)
        
        outer.addWidget(header)
        
        # Scrollable card sections
        scroll = QScrollArea()
        scroll.setObjectName("decksScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self._sections_container = QWidget()
        self._sections_layout = QVBoxLayout(self._sections_container)
        self._sections_layout.setContentsMargins(40, 0, 40, 40)
        self._sections_layout.setSpacing(24)
        self._sections_layout.setAlignment(Qt.AlignTop)
        
        scroll.setWidget(self._sections_container)
        outer.addWidget(scroll, 1)
    
    def show_deck(self, deck):
        self.deck = deck
        self.title_label.setText(deck.name)
        self.value_label.setText(f"€{deck.value:.2f}")
        self._refresh_active_button()
        self._rebuild_sections()
    
    def _refresh_active_button(self):
        self.active_toggle.blockSignals(True)
        self.active_toggle.setChecked(self.deck.active)
        self.active_toggle.blockSignals(False)
        self.active_label.setText("Active" if self.deck.active else "Archived")

    def _toggle_active(self, is_active: bool):
        if not self.deck:
            return
        self.deck.set_active(is_active)
        self.active_label.setText("Active" if is_active else "Archived")
    
    def _rebuild_sections(self):
        # Clear old sections
        while self._sections_layout.count():
            item = self._sections_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        # Group cards
        commander_names = {c["name"] for c in self.deck.commanders}
        groups = group_cards(self.deck.cards, commander_names)
        
        # Build sections, collecting tiles for lazy loading
        self._pending_tiles = []
        for bucket_name, cards in groups.items():
            total = sum(c["quantity"] for c in cards)
            section = self._build_section(bucket_name, total, cards)
            self._sections_layout.addWidget(section)
        
    def _build_section(self, name: str, count: int, cards: list[dict]) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        header_label = QLabel(f"{name} ({count})")
        header_label.setObjectName("deckSectionHeader")
        layout.addWidget(header_label)
        
        grid_container = QWidget()
        flow = FlowLayout(grid_container, margin=0, spacing=16)
        
        for card in cards:
            quantity = card.get("quantity", 1)
            caption = f"{quantity}x {card['name']}" if quantity > 1 else card["name"]
            tile = ImageTile(
                image_url=card.get("image_url", ""),
                cache_name=scryfall.card_image_cache_name(card),
                caption=caption,
                payload=card,
                width=CARD_TILE_WIDTH,
                height=CARD_TILE_HEIGHT,
                radius=14,
            )
            tile.clicked.connect(self.card_clicked.emit)
            flow.addWidget(tile)
            tile.request_image_load()   # ← the new line
        
        layout.addWidget(grid_container)
        return section