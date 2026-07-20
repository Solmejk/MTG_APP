"""Shared pixmap helpers (round_pixmap, make_placeholder,
paint_tint_overlay) plus ImageTile: the clickable image+caption widget
used for deck tiles, deck-detail card tiles, and availability-check card
tiles. CardGridView (the Collection screen's virtualized grid) uses the
pixmap helpers directly rather than ImageTile itself, for performance.
"""

from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QColor, QImage, QLinearGradient
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
    """Builds a plain dark rounded-rect pixmap shown before a card image
    has loaded (or if it fails to load)."""
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor("#2a2a2a"))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(QRectF(0, 0, width, height), radius, radius)
    painter.end()

    return pixmap


def paint_tint_overlay(painter: QPainter, rect: QRectF, radius: float, color: QColor, color2: QColor | None = None):
    """Draws a translucent rounded-rect wash over `rect` onto an
    already-open `painter` — the status-color overlay in the availability
    grid and the foil overlay in the collection grid both use this.
    `color`'s alpha controls how strong the wash is. `radius` should match
    the underlying image's own corner radius so the tint doesn't spill
    past its rounded corners. If `color2` is given, paints a diagonal
    (top-left to bottom-right) gradient from `color` to `color2` instead
    of a flat wash."""
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    if color2 is not None:
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0, color)
        gradient.setColorAt(1, color2)
        painter.setBrush(gradient)
    else:
        painter.setBrush(color)
    painter.drawRoundedRect(rect, radius, radius)
    painter.restore()


class ClickableLabel(QLabel):
    """A QLabel that emits `clicked` on left-click — used wherever a plain
    label (image, caption, sidebar avatar/username) needs to act as a
    button."""

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
        """image_url: image to fetch (request_image_load() kicks this
        off — not automatic, since callers may want to defer loading
        offscreen tiles). cache_name: on-disk cache key for the image.
        caption: text shown below the image. payload: arbitrary value
        passed back on `clicked` (typically the card/deck dict this tile
        represents). width/height/radius: tile image size and corner
        rounding. status_color: optional translucent tint + matching
        hover-border color (used by the availability screen; omit for a
        plain tile)."""
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
        """Apply the status color as a translucent wash, matching the
        pixmap's own corner radius (it's always exactly self._radius,
        whether it's the placeholder or a loaded card image)."""
        if self._status_color is None:
            return pixmap
        result = QPixmap(pixmap)
        painter = QPainter(result)
        color = QColor(self._status_color)
        color.setAlpha(90)
        paint_tint_overlay(painter, QRectF(0, 0, result.width(), result.height()), self._radius, color)
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
        """ImageLoader callback (main thread) for a successful fetch.
        token: echoed back from submit() — id(self), checked to ignore
        stray results after the tile's been reused/destroyed. image: the
        decoded, scaled, rounded QImage."""
        if token != id(self):
            return  # signal not for us
        if not self._image_label:
            return  # widget already destroyed
        # QImage -> QPixmap conversion happens here, on the main thread
        pixmap = QPixmap.fromImage(image)
        self._image_label.setPixmap(self._tinted(pixmap))
        self._loaded = True

    def _on_image_failed(self, token):
        """ImageLoader callback (main thread) for a failed fetch — resets
        _requested so a later request_image_load() call can retry."""
        if token != id(self):
            return
        self._requested = False  # allow retry later

    # Backward-compat: old call sites may still use load_image()
    def load_image(self):
        self.request_image_load()