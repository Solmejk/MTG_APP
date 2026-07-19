"""ExportModal: popout opened from the Availability screen's Export
button. Lists checked cards as '<qty> <name> (<SET>)' lines — the format
Cardmarket's wantlist search accepts — filterable by status, with a
one-click copy to clipboard.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QPlainTextEdit,
)

import availability
from ui.components.overlay_modal import OverlayModal


STATUS_LABELS = {
    availability.FREE: "Free",
    availability.USED: "Used elsewhere",
    availability.UNOWNED: "Not owned",
}
DEFAULT_INCLUDED = {availability.USED, availability.UNOWNED}

MODAL_WIDTH = 480
MODAL_HEIGHT = 560


class ExportModal(OverlayModal):
    """Popout listing checked cards as copyable '<qty> <name> (<set>)'
    lines. Call show_export(results) to populate and display it. See
    OverlayModal for dismissal/resize behavior (outside-click, Esc, close
    button)."""

    def __init__(self, parent=None):
        """Builds the (initially empty/hidden) popout chrome — status
        checkboxes, a read-only text box, and Copy/Close buttons. Content
        is filled in later by show_export()."""
        super().__init__(parent)
        self._results = []

        content = QWidget()
        content.setObjectName("cardModalContent")  # reuse CardModal's box styling
        content.setFixedWidth(MODAL_WIDTH)
        content.setFixedHeight(MODAL_HEIGHT)

        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(14)

        title = QLabel("Export Cards")
        title.setObjectName("cardModalName")
        title.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(title)

        checks_row = QHBoxLayout()
        checks_row.setSpacing(16)
        checks_row.addStretch()
        self._checks = {}
        for status in (availability.FREE, availability.USED, availability.UNOWNED):
            checkbox = QCheckBox(STATUS_LABELS[status])
            checkbox.setChecked(status in DEFAULT_INCLUDED)
            checkbox.stateChanged.connect(self._refresh_text)
            checks_row.addWidget(checkbox)
            self._checks[status] = checkbox
        checks_row.addStretch()
        content_layout.addLayout(checks_row)

        self._count_label = QLabel()
        self._count_label.setObjectName("cardModalMeta")
        self._count_label.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(self._count_label)

        self._text = QPlainTextEdit()
        self._text.setObjectName("exportText")
        self._text.setReadOnly(True)
        content_layout.addWidget(self._text, 1)

        button_row = QHBoxLayout()
        self._copy_btn = QPushButton("Copy to Clipboard")
        self._copy_btn.clicked.connect(self._copy)
        button_row.addWidget(self._copy_btn)
        button_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setObjectName("backButton")
        close_btn.clicked.connect(self._dismiss)
        button_row.addWidget(close_btn)
        content_layout.addLayout(button_row)

        self._init_overlay(content)

    def show_export(self, results: list[dict]):
        """Populates the export list from `results` (the same list
        check_availability() produced for the grid) and displays the
        popout. Re-filtering via the checkboxes afterward doesn't need
        this again — it just re-reads self._results."""
        self._results = results
        self._refresh_text()
        self._show_overlay()

    def _refresh_text(self, *_args):
        """Rebuilds the text box from self._results, keeping only rows
        whose status checkbox is checked. Called on show_export() and
        whenever a checkbox is toggled. *_args absorbs the unused int
        QCheckBox.stateChanged sends."""
        active = {status for status, checkbox in self._checks.items() if checkbox.isChecked()}
        lines = []
        for r in self._results:
            if r["status"] not in active:
                continue
            if r["status"] == availability.FREE:
                # Already owned — list the deck's needed quantity and its
                # own printing (nothing to buy, so "cheapest" is moot).
                quantity = r.get("quantity", 1)
                set_code = r.get("set", "")
            else:
                # Needs buying — list how many, and the cheapest printing
                # to buy them from.
                quantity = r["missing"]
                set_code = r.get("cheapest_set") or r.get("set", "")
            if quantity <= 0:
                continue
            lines.append(f"{quantity} {r['name']} ({set_code.upper()})")

        self._text.setPlainText("\n".join(lines))
        self._count_label.setText(f"{len(lines)} line{'s' if len(lines) != 1 else ''}")
        self._copy_btn.setEnabled(bool(lines))

    def _copy(self):
        """Copies the text box's current contents to the system clipboard."""
        QGuiApplication.clipboard().setText(self._text.toPlainText())
