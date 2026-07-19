from PySide6.QtCore import Qt, Signal, QRectF, QPropertyAnimation, Property
from PySide6.QtGui import QPainter, QColor, QBrush, QPen
from PySide6.QtWidgets import QWidget


class ToggleSwitch(QWidget):
    """An iOS-style toggle switch with an animated knob."""
    
    toggled = Signal(bool)
    
    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 24)
        self.setCursor(Qt.PointingHandCursor)
        self._checked = checked
        self._knob_pos = self._knob_pos_for_state(checked)
        
        self._anim = QPropertyAnimation(self, b"knob_pos", self)
        self._anim.setDuration(120)
    
    # Property exposed to the animation system
    def get_knob_pos(self):
        return self._knob_pos
    
    def set_knob_pos(self, value: float):
        self._knob_pos = value
        self.update()
    
    knob_pos = Property(float, get_knob_pos, set_knob_pos)
    
    def _knob_pos_for_state(self, checked: bool) -> float:
        # left edge for off, right edge for on
        return float(self.width() - self.height()) if checked else 0.0
    
    def isChecked(self) -> bool:
        return self._checked
    
    def setChecked(self, value: bool):
        if self._checked == value:
            return
        self._checked = value
        self._animate_to_state()
    
    def _animate_to_state(self):
        self._anim.stop()
        self._anim.setStartValue(self._knob_pos)
        self._anim.setEndValue(self._knob_pos_for_state(self._checked))
        self._anim.start()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setChecked(not self._checked)
            self.toggled.emit(self._checked)
        super().mousePressEvent(event)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        radius = h / 2
        
        # Track
        if self._checked:
            track_color = QColor("#e8a838")
        else:
            track_color = QColor("#444444")
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(track_color))
        painter.drawRoundedRect(QRectF(0, 0, w, h), radius, radius)
        
        # Knob
        knob_size = h - 4
        knob_x = self._knob_pos + 2
        knob_y = 2
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawEllipse(QRectF(knob_x, knob_y, knob_size, knob_size))
        
        painter.end()