from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QColor, QImage
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from ui.image_loader import ImageLoader


def round_pixmap(pixmap: QPixmap, radius: int) -> QPixmap:
    """Kept for callers that still need it synchronously (e.g. card modal)."""
    size = pixmap.size()
    result = QPixmap(size)
    result.fill(Qt.transparent)
    
    painter = QPainter(result)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size.width(), size.height()), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    
    return result


def make_placeholder(width: int, height: int, radius: int) -> QPixmap:
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor("#2a2a2a"))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(QRectF(0, 0, width, height), radius, radius)
    painter.end()
    
    return pixmap


class ClickableLabel(QLabel):
    clicked = Signal()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ImageTile(QWidget):
    """
    Clickable image tile with caption. Image loads asynchronously via
    ImageLoader — call request_image_load() to kick it off.
    """
    
    clicked = Signal(object)
    
    def __init__(
        self,
        image_url: str,
        cache_name: str,
        caption: str,
        payload,
        width: int = 220,
        height: int = 310,
        radius: int = 12,
        status_color: QColor | None = None,
    ):
        super().__init__()
        self.payload = payload
        self._image_url = image_url
        self._cache_name = cache_name
        self._width = width
        self._height = height
        self._radius = radius
        self._loaded = False
        self._requested = False
        self._status_color = status_color

        self.setFixedWidth(width)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._image_label = ClickableLabel()
        self._image_label.setObjectName("imageTilePicture")
        self._image_label.setFixedSize(width, height)
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setPixmap(self._tinted(make_placeholder(width, height, radius)))
        self._image_label.clicked.connect(lambda: self.clicked.emit(self.payload))
        if status_color is not None:
            # Overrides just the hover-border color from the app-wide
            # stylesheet (QLabel#imageTilePicture:hover) for this instance —
            # the base border/background/radius rules still apply.
            self._image_label.setStyleSheet(
                f"QLabel#imageTilePicture:hover {{ border: 2px solid {status_color.name()}; }}"
            )
        
        caption_label = ClickableLabel(caption)
        caption_label.setObjectName("imageTileCaption")
        caption_label.setAlignment(Qt.AlignCenter)
        caption_label.setWordWrap(True)
        caption_label.setFixedHeight(32)
        caption_label.clicked.connect(lambda: self.clicked.emit(self.payload))
        
        layout.addWidget(self._image_label)
        layout.addWidget(caption_label)

    def _tinted(self, pixmap: QPixmap) -> QPixmap:
        """Apply the status color as a translucent wash. Uses SourceAtop so
        it only paints where the pixmap already has content — respects the
        rounded corners on both the placeholder and loaded card images."""
        if self._status_color is None:
            return pixmap
        result = QPixmap(pixmap)
        painter = QPainter(result)
        painter.setCompositionMode(QPainter.CompositionMode_SourceAtop)
        color = QColor(self._status_color)
        color.setAlpha(90)
        painter.fillRect(result.rect(), color)
        painter.end()
        return result

    def request_image_load(self):
        """Queue the image load on the background thread pool."""
        if self._loaded or self._requested or not self._image_url:
            return
        self._requested = True
        ImageLoader.instance().submit(
            token=id(self),
            url=self._image_url,
            cache_name=self._cache_name,
            width=self._width,
            height=self._height,
            radius=self._radius,
            on_ready=self._on_image_ready,
            on_failed=self._on_image_failed,
        )
    
    def _on_image_ready(self, token, image: QImage):
        if token != id(self):
            return  # signal not for us
        if not self._image_label:
            return  # widget already destroyed
        # QImage -> QPixmap conversion happens here, on the main thread
        pixmap = QPixmap.fromImage(image)
        self._image_label.setPixmap(self._tinted(pixmap))
        self._loaded = True
    
    def _on_image_failed(self, token):
        if token != id(self):
            return
        self._requested = False  # allow retry later
    
    # Backward-compat: old call sites may still use load_image()
    def load_image(self):
        self.request_image_load()