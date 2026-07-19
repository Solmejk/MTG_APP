from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QToolButton, QMenu, QWidgetAction, QCheckBox,
)

import availability
import moxfield
import scryfall
from app import MTGApp
from models.deck import Deck
from ui.background import run_in_background
from ui.card_type import group_cards
from ui.flow_layout import FlowLayout
from ui.components.image_tile import ImageTile


CARD_TILE_WIDTH = 140
CARD_TILE_HEIGHT = 196

STATUS_COLORS = {
    availability.FREE: QColor("#4caf50"),
    availability.USED: QColor("#e8a838"),
    availability.UNOWNED: QColor("#d9534f"),
}
STATUS_LABELS = {
    availability.FREE: "Free",
    availability.USED: "Used elsewhere",
    availability.UNOWNED: "Not owned",
}


class AvailabilityScreen(QWidget):
    """Paste a Moxfield deck URL and see which of its cards are free to
    use, already tied up in another active deck, or not owned at all."""

    card_clicked = Signal(dict)

    def __init__(self, app: MTGApp):
        super().__init__()
        self.app = app
        self._bg_tasks = []  # keeps background tasks alive — see ui/background.py

        # Cached from the last successful check, so toggling the status
        # filter re-renders instantly instead of re-fetching from Moxfield.
        self._last_deck_name = None
        self._last_commander_names = set()
        self._last_results = None
        self._active_statuses = {availability.FREE, availability.USED, availability.UNOWNED}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QLabel("Availability Checker")
        header.setObjectName("screenTitle")
        header.setContentsMargins(40, 30, 40, 10)
        outer.addWidget(header)

        # URL input row
        input_row = QWidget()
        input_layout = QHBoxLayout(input_row)
        input_layout.setContentsMargins(40, 0, 40, 16)
        input_layout.setSpacing(12)

        self._url_input = QLineEdit()
        self._url_input.setObjectName("searchInput")
        self._url_input.setPlaceholderText("Paste a Moxfield deck URL…")
        self._url_input.returnPressed.connect(self._on_check_clicked)
        input_layout.addWidget(self._url_input, 1)

        self._check_btn = QPushButton("Check")
        self._check_btn.clicked.connect(self._on_check_clicked)
        input_layout.addWidget(self._check_btn)

        self._filter_btn = self._build_filter_button()
        input_layout.addWidget(self._filter_btn)

        self._sort_price_btn = QToolButton()
        self._sort_price_btn.setObjectName("sortPriceButton")
        self._sort_price_btn.setText("€")
        self._sort_price_btn.setCheckable(True)
        self._sort_price_btn.setToolTip("Sort by price (highest missing cost first)")
        self._sort_price_btn.toggled.connect(self._on_sort_changed)
        input_layout.addWidget(self._sort_price_btn)

        outer.addWidget(input_row)

        self._status_label = QLabel()
        self._status_label.setObjectName("resultCount")
        self._status_label.setContentsMargins(40, 0, 40, 16)
        self._status_label.setWordWrap(True)
        outer.addWidget(self._status_label)

        # Scrollable, sectioned card grid (grouped by type, like deck detail)
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

    def _build_filter_button(self) -> QToolButton:
        button = QToolButton()
        button.setText("▾")
        button.setPopupMode(QToolButton.InstantPopup)

        menu = QMenu(button)
        self._status_checks = {}
        for status in (availability.FREE, availability.USED, availability.UNOWNED):
            checkbox = QCheckBox(STATUS_LABELS[status])
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(self._on_filter_changed)
            # QWidgetAction so the checkbox handles its own clicks — a plain
            # checkable QAction would close the menu on every toggle.
            action = QWidgetAction(menu)
            action.setDefaultWidget(checkbox)
            menu.addAction(action)
            self._status_checks[status] = checkbox

        button.setMenu(menu)
        return button

    def _on_filter_changed(self, *_args):
        self._active_statuses = {
            status for status, checkbox in self._status_checks.items()
            if checkbox.isChecked()
        }
        if self._last_results is not None:
            self._apply_filter()

    def _on_sort_changed(self, *_args):
        if self._last_results is not None:
            self._apply_filter()

    def _on_check_clicked(self):
        url = self._url_input.text().strip()
        deck_id = moxfield.extract_deck_id(url)
        if not deck_id:
            self._status_label.setText("That doesn't look like a Moxfield deck URL.")
            return
        if not self.app.is_logged_in:
            self._status_label.setText("Log in first via the sidebar avatar.")
            return

        self._check_btn.setEnabled(False)
        self._status_label.setText("Checking…")
        run_in_background(
            lambda: self._fetch_and_check(deck_id),
            self._bg_tasks,
            on_finished=self._on_check_finished,
            on_failed=self._on_check_failed,
        )

    def _fetch_and_check(self, deck_id: str):
        deck = Deck(deck_id, "")
        deck.load(force=True)
        results = availability.check_availability(self.app, deck.cards)
        commander_names = {c["name"] for c in deck.commanders}
        return deck.name, commander_names, results

    def _on_check_finished(self, result):
        self._check_btn.setEnabled(True)
        self._last_deck_name, self._last_commander_names, self._last_results = result
        self._apply_filter()

    def _on_check_failed(self, message: str):
        self._check_btn.setEnabled(True)
        self._status_label.setText(f"Couldn't load that deck: {message}")

    def _apply_filter(self):
        filtered = [r for r in self._last_results if r["status"] in self._active_statuses]
        self._render_results(self._last_deck_name, self._last_commander_names, filtered)

    def _render_results(self, deck_name: str, commander_names: set, results: list[dict]):
        while self._sections_layout.count():
            item = self._sections_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # Counts/cost always reflect the full check, not just what's shown
        # after filtering — "how much would it cost to finish this deck"
        # shouldn't change just because you hid the free cards.
        all_results = self._last_results or []
        free = sum(1 for r in all_results if r["status"] == availability.FREE)
        used = sum(1 for r in all_results if r["status"] == availability.USED)
        unowned = sum(1 for r in all_results if r["status"] == availability.UNOWNED)
        missing_cost = sum(r["missing_cost"] for r in all_results)
        self._status_label.setText(
            f"{deck_name} — {free} free · {used} used elsewhere · {unowned} not owned"
            f"  ·  missing cards cost ≈ €{missing_cost:,.2f}"
        )

        groups = group_cards(results, commander_names)
        for bucket_name, cards in groups.items():
            if self._sort_price_btn.isChecked():
                cards = sorted(cards, key=lambda c: c["missing_cost"], reverse=True)
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
            if card["missing_cost"] > 0:
                caption += f" (€{card['missing_cost']:,.2f})"
            tile = ImageTile(
                image_url=card.get("image_url", ""),
                cache_name=scryfall.card_image_cache_name(card),
                caption=caption,
                payload=card,
                width=CARD_TILE_WIDTH,
                height=CARD_TILE_HEIGHT,
                radius=14,
                status_color=STATUS_COLORS[card["status"]],
            )
            tile.clicked.connect(self.card_clicked.emit)
            flow.addWidget(tile)
            tile.request_image_load()

        layout.addWidget(grid_container)
        return section
