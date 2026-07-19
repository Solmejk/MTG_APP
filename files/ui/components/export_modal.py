from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QPlainTextEdit,
)

import availability


STATUS_LABELS = {
    availability.FREE: "Free",
    availability.USED: "Used elsewhere",
    availability.UNOWNED: "Not owned",
}
DEFAULT_INCLUDED = {availability.USED, availability.UNOWNED}

MODAL_WIDTH = 480


class ExportModal(QWidget):
    """
    Full-window overlay listing checked cards as '<qty> <name> (<set>)'
    lines — ready to paste into Cardmarket's wantlist search. Filterable
    by status; close by clicking outside, pressing Esc, or the Close button.
    """

    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("cardModal")  # reuse the dim-overlay background
        self._results = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignCenter)

        self._content = QWidget()
        self._content.setObjectName("cardModalContent")
        self._content.setFixedWidth(MODAL_WIDTH)
        self._content.setFixedHeight(560)

        content_layout = QVBoxLayout(self._content)
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

        outer.addWidget(self._content)
        self.hide()

    def show_export(self, results: list[dict]):
        self._results = results
        self._refresh_text()
        if self.parent():
            self.resize(self.parent().size())
        self.raise_()
        self.show()

    def _refresh_text(self, *_args):
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
        QGuiApplication.clipboard().setText(self._text.toPlainText())

    def _dismiss(self):
        self.hide()
        self.closed.emit()

    def mousePressEvent(self, event):
        """Clicking outside the content card closes the modal."""
        click_pos = event.position().toPoint()
        if not self._content.geometry().contains(click_pos):
            self._dismiss()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._dismiss()
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        """When the window resizes, the modal should follow."""
        super().resizeEvent(event)
