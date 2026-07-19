"""DecksScreen: a wrapping grid of deck tiles (commander art + name),
with active/archived and commander-format toggles. Clicking a tile opens
DeckDetailScreen (wired up in MainWindow).
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
)

from app import MTGApp
from ui.flow_layout import FlowLayout
from ui.layout_utils import clear_layout
from ui.components.image_tile import ImageTile
from ui.components.toggle_switch import ToggleSwitch


TILE_WIDTH = 220
TILE_HEIGHT = 310


class DecksScreen(QWidget):
    """Grid of clickable deck tiles, with active/format filters."""

    deck_selected = Signal(object)  # emitted with a models.deck.Deck on click

    def __init__(self, app: MTGApp):
        """Builds the screen and its (initially both-on) filters, then
        does the first grid build from `app.decks`."""
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
        """Slot for the "Active only" toggle: updates the filter and
        rebuilds the grid. value: the toggle's new checked state."""
        self._active_only = value
        self._rebuild_grid()

    def _on_commander_toggled(self, value: bool):
        """Slot for the "Commander only" toggle: updates the filter and
        rebuilds the grid. value: the toggle's new checked state."""
        self._commander_only = value
        self._rebuild_grid()

    def _filtered_decks(self):
        """Yields decks from self.app.decks matching the current
        active/commander-only filters."""
        for deck in self.app.decks:
            if self._active_only and not deck.active:
                continue
            if self._commander_only and deck.format != "commander":
                continue
            yield deck

    def _rebuild_grid(self):
        """Clears and rebuilds the tile grid from _filtered_decks(). Note
        that a deck's `format` is only known once its contents have
        loaded — MainWindow's background deck-content load calls this
        again once that data is available, which is why decks can appear
        to "pop in" shortly after the app starts."""
        clear_layout(self._flow)

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

    def _commander_url(self, deck) -> str:
        """The deck's commander art URL for its tile, or "" if the deck
        has no commander data loaded yet."""
        if deck.commanders and "image_url" in deck.commanders[0]:
            return deck.commanders[0]["image_url"]
        return ""
