"""FlowLayout: a wrapping left-to-right layout (Qt has no built-in
equivalent), used everywhere a grid of variable-width tiles needs to wrap
based on the container's width (Decks, DeckDetail, Availability grids).
"""

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QSizePolicy


class FlowLayout(QLayout):
    """
    Layout that arranges widgets left-to-right, wrapping to the next row
    when it runs out of horizontal space. Like words in a paragraph.
    Based on Qt's official FlowLayout example.
    """

    def __init__(self, parent=None, margin=0, spacing=10):
        """parent: the widget this layout is installed on (if given, its
        margins are set from `margin`). spacing: gap between items, both
        horizontally and vertically."""
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._items = []

    def addItem(self, item):
        """Qt layout API: appends a layout item (called internally by
        addWidget())."""
        self._items.append(item)

    def count(self):
        """Qt layout API: number of items currently in the layout."""
        return len(self._items)

    def itemAt(self, index):
        """Qt layout API: the item at `index` without removing it, or
        None if out of range."""
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        """Qt layout API: removes and returns the item at `index` (used
        when clearing the layout — see ui.layout_utils.clear_layout), or
        None if out of range."""
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        """Qt layout API: this layout doesn't expand to fill extra space
        in either direction — its size is exactly what its items need."""
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        """Qt layout API: yes — wrapping means height depends on the
        width available (see heightForWidth)."""
        return True

    def heightForWidth(self, width):
        """Qt layout API: the height needed to lay out all items if given
        exactly `width` to work with, without actually moving anything
        (test_only=True)."""
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        """Qt layout API: positions every item within `rect`, wrapping as
        needed."""
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        """Qt layout API: same as minimumSize() — this layout has no
        preferred size beyond what its items require."""
        return self.minimumSize()

    def minimumSize(self):
        """Qt layout API: the smallest size that still fits every item's
        own minimum size, plus margins. Doesn't account for wrapping —
        just an all-items-fit-in-one-row lower bound."""
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(),
                      margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect, test_only):
        """Shared implementation for setGeometry/heightForWidth: walks
        items left-to-right within `rect`'s width, wrapping to a new row
        whenever the next item wouldn't fit. rect: the area to lay out
        within (only its width and top-left matter). test_only: if True,
        computes the resulting height without actually moving any items
        (used by heightForWidth); if False, calls setGeometry on each
        item. Returns the total height used."""
        x = rect.x()
        y = rect.y()
        line_height = 0
        spacing = self.spacing()

        for item in self._items:
            next_x = x + item.sizeHint().width() + spacing
            if next_x - spacing > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + spacing
                next_x = x + item.sizeHint().width() + spacing
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y()
