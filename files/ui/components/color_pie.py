"""ColorPie/ColorLegend: the doughnut chart and matching text legend on
the Collection screen, showing the collection's mana-color breakdown.
"""

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QFont, QPen
from PySide6.QtWidgets import QWidget


# Color mapping for MTG mana colors → display swatches
COLOR_SWATCHES = {
    "W": ("#f8e7b1", "White"),
    "U": ("#5b9ad5", "Blue"),
    "B": ("#2d2d2d", "Black"),
    "R": ("#d96a5a", "Red"),
    "G": ("#5a9e6e", "Green"),
    "C": ("#a8a8a8", "Colorless"),
}


class ColorPie(QWidget):
    """Doughnut chart of MTG color distribution."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._counts = {}  # key -> int (e.g. {"W": 826, "U": 521, ...})
        self.setMinimumSize(180, 180)

    def setCounts(self, counts: dict):
        """Replaces the chart's data and repaints. counts: {color_code:
        card_count}, e.g. {"W": 12, "U": 0, ...} — matches CollectionScreen's
        color_counts."""
        self._counts = dict(counts)
        self.update()

    def paintEvent(self, event):
        """Draws one pie slice per nonzero color count, clockwise from 12
        o'clock, then punches a hole in the middle to make it a doughnut.
        Draws nothing (but still properly ends the painter) if there's no
        data yet."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        total = sum(self._counts.values()) if self._counts else 0
        if total == 0:
            painter.end()
            return

        # Square area centered in the widget
        side = min(self.width(), self.height())
        ring_x = (self.width() - side) // 2
        ring_y = (self.height() - side) // 2
        outer = QRectF(ring_x, ring_y, side, side)

        # Draw arcs (clockwise from 12 o'clock, going around)
        start_angle = 90 * 16  # Qt angles are in 1/16th degrees; 90*16 = top
        for key, count in self._counts.items():
            if count == 0:
                continue
            color_hex, _ = COLOR_SWATCHES.get(key, ("#888888", key))
            span = -int(360 * 16 * (count / total))  # negative = clockwise

            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(color_hex))
            painter.drawPie(outer, start_angle, span)
            start_angle += span

        # Hollow out the center to make it a doughnut
        hole_size = side * 0.55
        hole_x = ring_x + (side - hole_size) / 2
        hole_y = ring_y + (side - hole_size) / 2
        painter.setBrush(QColor("#1a1a1a"))  # page background
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(hole_x, hole_y, hole_size, hole_size))

        painter.end()


class ColorLegend(QWidget):
    """Text legend matching the pie chart."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._counts = {}

    def setCounts(self, counts: dict):
        """Replaces the legend's data and repaints. counts: same shape as
        ColorPie.setCounts."""
        self._counts = dict(counts)
        self.update()

    def paintEvent(self, event):
        """Draws one swatch-dot + "Label: count" line per color, stacked
        vertically in insertion order."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        font = QFont()
        font.setPointSize(10)
        painter.setFont(font)

        y = 4
        for key, count in self._counts.items():
            color_hex, label = COLOR_SWATCHES.get(key, ("#888888", key))

            # Swatch
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(color_hex))
            painter.drawEllipse(QRectF(0, y + 2, 10, 10))

            # Text
            painter.setPen(QColor("#e8e8e8"))
            painter.drawText(18, y + 12, f"{label}: {count}")
            y += 20

        painter.end()
