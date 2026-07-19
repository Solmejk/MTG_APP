"""Small generic helpers for working with Qt layouts, shared across
screens that rebuild a grid/section list from scratch on every refresh
(Decks, DeckDetail, Availability).
"""

from PySide6.QtWidgets import QLayout


def clear_layout(layout: QLayout):
    """Removes and schedules deletion of every widget in `layout`, leaving
    it empty. Used before rebuilding a grid/section list from scratch so
    old widgets don't pile up underneath the new ones."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.deleteLater()
