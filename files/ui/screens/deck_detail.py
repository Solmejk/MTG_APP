"""DeckDetailScreen: full-page view of a single deck's contents, opened
from DecksScreen. Shows the deck's name/value, an active/archived toggle,
and its cards grouped by type in a scrollable grid (via
ui.components.card_section).
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
)

from ui.components.toggle_switch import ToggleSwitch
from ui.components.card_section import rebuild_card_sections, quantity_caption


class DeckDetailScreen(QWidget):
    """Detail view for a single deck. Call show_deck(deck) to swap
    content — the same instance is reused for whichever deck was clicked
    in DecksScreen (see MainWindow._open_deck_detail)."""

    back_requested = Signal()  # emitted when the Back button is clicked
    card_clicked = Signal(dict)  # emitted with a card dict when a tile is clicked

    def __init__(self):
        """Builds the (initially empty) screen chrome — back button,
        name/value header, active/archived toggle, and the scrollable
        section container. Populated later by show_deck()."""
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
        """Swaps the screen to show `deck`: updates the header/toggle and
        rebuilds the card grid. `deck` is a models.deck.Deck with its
        contents already loaded (callers load it first if needed)."""
        self.deck = deck
        self.title_label.setText(deck.name)
        self.value_label.setText(f"€{deck.value:.2f}")
        self._refresh_active_button()
        self._rebuild_sections()

    def _refresh_active_button(self):
        """Syncs the active/archived toggle and label to self.deck's
        current state, without re-triggering _toggle_active (blocked
        signals) since this is a display update, not a user action."""
        self.active_toggle.blockSignals(True)
        self.active_toggle.setChecked(self.deck.active)
        self.active_toggle.blockSignals(False)
        self.active_label.setText("Active" if self.deck.active else "Archived")

    def _toggle_active(self, is_active: bool):
        """Slot for the active/archived toggle: persists the change on
        the deck (Deck.set_active writes it to deck_states.json) and
        updates the label. is_active: the toggle's new checked state."""
        if not self.deck:
            return
        self.deck.set_active(is_active)
        self.active_label.setText("Active" if is_active else "Archived")

    def _rebuild_sections(self):
        """Rebuilds the type-grouped card grid for the current deck. Its
        commanders form their own bucket; the rest are grouped by type."""
        commander_names = {c["name"] for c in self.deck.commanders}
        rebuild_card_sections(
            self._sections_layout,
            self.deck.cards,
            commander_names,
            caption_fn=quantity_caption,
            on_click=self.card_clicked.emit,
        )
