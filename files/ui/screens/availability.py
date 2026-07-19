from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QAction, QActionGroup
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QToolButton, QMenu,
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

SORT_PRICE_DESC = "price_desc"
SORT_PRICE_ASC = "price_asc"
SORT_NAME = "name"
SORT_LABELS = {
    SORT_PRICE_DESC: "Price high-low",
    SORT_PRICE_ASC: "Price low-high",
    SORT_NAME: "Name",
}
INACTIVE_COLOR = QColor("#444444")


class _LegendChip(QWidget):
    """A swatch + label that doubles as a status filter toggle — click to
    show/hide that status in the grid below."""

    toggled = Signal(str, bool)  # status, is_active

    def __init__(self, status: str, color: QColor, label_text: str, parent=None):
        super().__init__(parent)
        self._status = status
        self._color = color
        self._active = True
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self._swatch = QLabel()
        self._swatch.setFixedSize(12, 12)
        layout.addWidget(self._swatch)

        self._label = QLabel(label_text)
        layout.addWidget(self._label)

        self._refresh_style()

    def is_active(self) -> bool:
        return self._active

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._active = not self._active
            self._refresh_style()
            self.toggled.emit(self._status, self._active)
        super().mousePressEvent(event)

    def _refresh_style(self):
        color = self._color if self._active else INACTIVE_COLOR
        self._swatch.setStyleSheet(f"background-color: {color.name()}; border-radius: 3px;")
        text_color = "#e8e8e8" if self._active else "#666666"
        self._label.setStyleSheet(f"color: {text_color};")


class AvailabilityScreen(QWidget):
    """Paste a Moxfield deck URL and see which of its cards are free to
    use, already tied up in another active deck, or not owned at all."""

    card_clicked = Signal(dict)
    export_requested = Signal(list)

    def __init__(self, app: MTGApp):
        super().__init__()
        self.app = app
        self._bg_tasks = []  # keeps background tasks alive — see ui/background.py

        # Cached from the last successful check, so toggling a legend chip
        # or the sort order re-renders instantly instead of re-fetching.
        self._last_deck_name = None
        self._last_commander_names = set()
        self._last_results = None
        self._active_statuses = {availability.FREE, availability.USED, availability.UNOWNED}
        self._sort_mode = SORT_NAME

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QLabel("Availability Checker")
        header.setObjectName("screenTitle")
        header.setContentsMargins(40, 30, 40, 10)
        outer.addWidget(header)

        # Row 1: URL input, Check, Sort
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

        self._sort_btn = self._build_sort_button()
        self._sort_btn.setFixedHeight(self._check_btn.sizeHint().height())
        input_layout.addWidget(self._sort_btn)

        # Only appears once there are results to export — see _on_check_finished
        self._export_btn = QPushButton("Export")
        self._export_btn.clicked.connect(self._on_export_clicked)
        self._export_btn.hide()
        input_layout.addWidget(self._export_btn)

        outer.addWidget(input_row)

        # Row 2: status/summary text (left) + legend chips, which double as
        # status filters (right)
        status_row = QWidget()
        status_layout = QHBoxLayout(status_row)
        status_layout.setContentsMargins(40, 0, 40, 16)
        status_layout.setSpacing(12)

        self._status_label = QLabel()
        self._status_label.setObjectName("resultCount")
        self._status_label.setWordWrap(True)
        status_layout.addWidget(self._status_label, 1)

        self._legend_chips = {}
        for status in (availability.FREE, availability.USED, availability.UNOWNED):
            chip = _LegendChip(status, STATUS_COLORS[status], STATUS_LABELS[status])
            chip.toggled.connect(self._on_legend_toggled)
            status_layout.addWidget(chip)
            self._legend_chips[status] = chip

        outer.addWidget(status_row)

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

    def _build_sort_button(self) -> QToolButton:
        button = QToolButton()
        button.setText("Sort")
        button.setPopupMode(QToolButton.InstantPopup)

        menu = QMenu(button)
        group = QActionGroup(menu)
        group.setExclusive(True)
        self._sort_actions = {}
        for mode in (SORT_PRICE_DESC, SORT_PRICE_ASC, SORT_NAME):
            action = QAction(SORT_LABELS[mode], menu)
            action.setCheckable(True)
            action.setChecked(mode == self._sort_mode)
            action.triggered.connect(lambda checked, m=mode: self._on_sort_changed(m))
            group.addAction(action)
            menu.addAction(action)
            self._sort_actions[mode] = action

        button.setMenu(menu)
        return button

    def _on_sort_changed(self, mode: str):
        self._sort_mode = mode
        if self._last_results is not None:
            self._apply_filter()

    def _on_legend_toggled(self, status: str, is_active: bool):
        if is_active:
            self._active_statuses.add(status)
        else:
            self._active_statuses.discard(status)
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
        self._export_btn.show()
        self._apply_filter()

    def _on_check_failed(self, message: str):
        self._check_btn.setEnabled(True)
        self._status_label.setText(f"Couldn't load that deck: {message}")

    def _on_export_clicked(self):
        if self._last_results is not None:
            self.export_requested.emit(self._last_results)

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
            cards = self._sorted_cards(cards)
            total = sum(c["quantity"] for c in cards)
            section = self._build_section(bucket_name, total, cards)
            self._sections_layout.addWidget(section)

    def _sorted_cards(self, cards: list[dict]) -> list[dict]:
        if self._sort_mode == SORT_PRICE_DESC:
            return sorted(cards, key=lambda c: c["missing_cost"], reverse=True)
        if self._sort_mode == SORT_PRICE_ASC:
            return sorted(cards, key=lambda c: c["missing_cost"])
        return sorted(cards, key=lambda c: c["name"].lower())

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
