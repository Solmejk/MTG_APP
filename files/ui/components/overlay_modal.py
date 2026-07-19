"""Base class for full-window dimmed overlays with a centered content box
(CardModal, ExportModal). Owns the behavior every such overlay shares:
dismiss on outside-click/Esc/close-button, and resizing to cover the
window. Subclasses build their own content widget and just call
_init_overlay(content) once it's ready.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout


class OverlayModal(QWidget):
    """Full-window dimmed overlay wrapping a single centered content
    widget. Subclasses are responsible for building that content widget
    and passing it to _init_overlay(); this class handles everything about
    being an overlay (dismissal, resizing, visibility) generically."""

    closed = Signal()

    def __init__(self, parent=None):
        """parent: the window this overlay covers when shown (its size
        drives how big the overlay grows to fill)."""
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("cardModal")  # dim-overlay background, shared QSS
        self._content = None
        self.hide()

    def _init_overlay(self, content: QWidget):
        """Wires up `content` as the centered box shown over the dimmed
        background. Call once from the subclass's __init__, after content
        is fully built."""
        self._content = content
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignCenter)
        outer.addWidget(content)

    def _show_overlay(self):
        """Resizes to cover the parent window, raises above other
        widgets, and shows the overlay. Call from a subclass's public
        show_*() method after it has populated the content widget."""
        if self.parent():
            self.resize(self.parent().size())
        self.raise_()
        self.show()

    def _dismiss(self):
        """Hides the overlay and notifies listeners via the `closed`
        signal. Bound to the close button, outside-click, and Esc."""
        self.hide()
        self.closed.emit()

    def mousePressEvent(self, event):
        """Clicking outside the content box dismisses the overlay;
        clicking inside it does nothing (lets the click reach the
        content's own widgets)."""
        click_pos = event.position().toPoint()
        if not self._content.geometry().contains(click_pos):
            self._dismiss()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        """Esc dismisses the overlay; all other keys pass through."""
        if event.key() == Qt.Key_Escape:
            self._dismiss()
        super().keyPressEvent(event)
