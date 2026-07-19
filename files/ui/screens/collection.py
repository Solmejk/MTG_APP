"""CollectionScreen: stats header (totals, value, rarity/color breakdown)
plus a searchable, virtualized grid of every card in the collection —
see ui.components.card_grid_view for the grid itself.
"""

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
)

from app import MTGApp
from ui.components.card_grid_view import CardGridView
from ui.components.color_pie import ColorPie, ColorLegend
from ui.image_loader import ImageLoader

class CollectionScreen(QWidget):
    """Collection stats + virtualized searchable card grid."""

    card_clicked = Signal(dict)  # emitted with a flat card payload dict on click

    def __init__(self, app: MTGApp):
        """Builds and populates the screen from `app.collection` — rebuilt
        from scratch (not updated in place) whenever the underlying data
        changes, see MainWindow._rebuild_data_screens."""
        super().__init__()
        self.app = app

        self._typing_timer = QTimer(self)
        self._typing_timer.setSingleShot(True)
        self._typing_timer.setInterval(400)
        self._typing_timer.timeout.connect(self._stop_typing)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header
        header = QLabel("Collection")
        header.setObjectName("screenTitle")
        header.setContentsMargins(40, 30, 40, 10)
        outer.addWidget(header)

        # Stats column: text on top, pie + legend below
        stats_column = QWidget()
        stats_layout = QVBoxLayout(stats_column)
        stats_layout.setContentsMargins(40, 0, 40, 20)
        stats_layout.setSpacing(16)

        self._stats_label = QLabel()
        self._stats_label.setObjectName("collectionStats")
        self._stats_label.setWordWrap(True)
        stats_layout.addWidget(self._stats_label)

        # Pie + legend side-by-side
        chart_block = QWidget()
        chart_layout = QHBoxLayout(chart_block)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        chart_layout.setSpacing(12)

        self._color_pie = ColorPie()
        self._color_pie.setFixedSize(160, 160)
        chart_layout.addWidget(self._color_pie)

        self._color_legend = ColorLegend()
        self._color_legend.setFixedWidth(120)
        chart_layout.addWidget(self._color_legend)

        chart_layout.addStretch()  # keep pie + legend left-aligned

        stats_layout.addWidget(chart_block)
        outer.addWidget(stats_column)

        # Search bar — right-aligned, shorter
        search_row = QWidget()
        search_layout = QHBoxLayout(search_row)
        search_layout.setContentsMargins(40, 0, 40, 16)

        search_layout.addStretch()

        self._result_count = QLabel()
        self._result_count.setObjectName("resultCount")
        search_layout.addWidget(self._result_count)

        self._search_input = QLineEdit()
        self._search_input.setObjectName("searchInput")
        self._search_input.setPlaceholderText("Search by card name…")
        self._search_input.setFixedWidth(280)
        self._search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self._search_input)

        outer.addWidget(search_row)

        # Card grid (virtualized)
        self._grid = CardGridView()
        self._grid.setContentsMargins(40, 0, 40, 40)
        self._grid.setCardData(self.app.collection.cards)
        self._grid.card_clicked.connect(self.card_clicked.emit)
        outer.addWidget(self._grid, 1)

        self._render_stats()
        self._update_count()

    def _on_search_changed(self, query: str):
        """Slot for the search box: applies the filter to the grid and
        pauses ImageLoader while actively typing (resumed by
        _stop_typing once the user pauses for 400ms), so a fast typist
        doesn't queue up fetches for filter results they've already
        typed past."""
        if not self._typing_timer.isActive():
            ImageLoader.instance().pause()
        self._typing_timer.start()  # resets the countdown
        self._grid.setFilter(query)
        self._update_count()

    def _stop_typing(self):
        """QTimer timeout slot: resumes ImageLoader once typing has
        paused for 400ms."""
        ImageLoader.instance().resume()

    def _update_count(self):
        """Updates the "N results" label next to the search box — blank
        when the search box is empty (nothing to report)."""
        showing = self._grid.filtered_count()
        if self._search_input.text().strip():
            self._result_count.setText(f"{showing} result{'s' if showing != 1 else ''}")
        else:
            self._result_count.setText("")

    def _render_stats(self):
        """Computes and displays the stats header (total/unique cards,
        total value, rarity breakdown) and feeds the color-pie/legend
        from the full (unfiltered) collection."""
        cards = self.app.collection.cards
        total_cards = sum(c["quantity"] for c in cards)
        unique_cards = len(cards)

        total_value = 0.0
        for entry in cards:
            price = entry["card"].get("prices", {}).get("eur") or 0
            total_value += price * entry["quantity"]

        rarity_counts = {"common": 0, "uncommon": 0, "rare": 0, "mythic": 0}
        for entry in cards:
            rarity = entry["card"].get("rarity", "")
            if rarity in rarity_counts:
                rarity_counts[rarity] += entry["quantity"]

        color_counts = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 0}
        for entry in cards:
            colors = entry["card"].get("colors", [])
            qty = entry["quantity"]
            if not colors:
                color_counts["C"] += qty
            else:
                for c in colors:
                    if c in color_counts:
                        color_counts[c] += qty

        text = (
            f"<b>{total_cards}</b> cards · <b>{unique_cards}</b> unique<br>"
            f"<b>€{total_value:,.2f}</b><br><br>"
            f"Common: {rarity_counts['common']} · "
            f"Uncommon: {rarity_counts['uncommon']} · "
            f"Rare: {rarity_counts['rare']} · "
            f"Mythic: {rarity_counts['mythic']}"
        )
        self._stats_label.setText(text)

        self._color_pie.setCounts(color_counts)
        self._color_legend.setCounts(color_counts)
