from PySide6.QtCore import (
    Qt, QAbstractListModel, QModelIndex, QSize, QRect, QRectF, Signal,
)
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QPen, QImage, QFontMetrics,
)
from PySide6.QtWidgets import (
    QListView, QStyledItemDelegate, QStyle, QStyleOptionViewItem,
)

import scryfall
from ui.image_loader import ImageLoader
from ui.components.image_tile import make_placeholder


CELL_WIDTH = 140
CELL_HEIGHT = 196 + 40  # image height + caption space
IMAGE_HEIGHT = 196
IMAGE_RADIUS = 12
CAPTION_HEIGHT = 36


class CollectionModel(QAbstractListModel):
    """Wraps a list of card entries with optional name filtering."""
    
    def __init__(self, cards: list, parent=None):
        super().__init__(parent)
        self._all_cards = cards
        self._filtered = cards
        self._filter = ""
    
    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._filtered)
    
    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._filtered):
            return None
        entry = self._filtered[index.row()]
        if role == Qt.UserRole:
            # Return the full entry; the delegate / consumers decode it
            return entry
        if role == Qt.DisplayRole:
            return entry["card"]["name"]
        return None
    
    def setFilter(self, query: str):
        query = query.strip().lower()
        if query == self._filter:
            return
        self._filter = query
        self.beginResetModel()
        if not query:
            self._filtered = self._all_cards
        else:
            self._filtered = [
                e for e in self._all_cards
                if query in e["card"]["name"].lower()
            ]
        self.endResetModel()


class CardThumbnailDelegate(QStyledItemDelegate):
    """Paints a card cell: rounded image + caption. Loads images via ImageLoader."""
    
    repaint_requested = Signal(int)  # row index — fires when an image arrives
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap_cache = {}  # token -> QPixmap
        self._requested = set()  # tokens already requested
        self._placeholder = make_placeholder(CELL_WIDTH, IMAGE_HEIGHT, IMAGE_RADIUS)
        self._view = None

    def attach_view(self, view: QListView):
        """Used so the delegate can tell the view to repaint a specific row."""
        self._view = view

    def sizeHint(self, option, index):
        return QSize(CELL_WIDTH, CELL_HEIGHT)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        entry = index.data(Qt.UserRole)
        if entry is None:
            return
        
        token = scryfall.card_key(entry["card"])
        rect = option.rect
        
        # Compute paint positions
        img_x = rect.x()
        img_y = rect.y()
        caption_y = img_y + IMAGE_HEIGHT + 4
        
        # Image
        pixmap = self._pixmap_cache.get(token, self._placeholder)
        # Center horizontally if narrower than cell
        x = img_x + (CELL_WIDTH - pixmap.width()) // 2
        painter.drawPixmap(x, img_y, pixmap)
        
        # Hover border around image
        if option.state & QStyle.State_MouseOver:
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing)
            pen = QPen(QColor("#e8a838"))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(
                QRectF(x, img_y, pixmap.width(), pixmap.height()),
                IMAGE_RADIUS + 2, IMAGE_RADIUS + 2,
            )
            painter.restore()
        
        # Caption
        painter.save()
        painter.setPen(QColor("#e8e8e8"))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(9)
        painter.setFont(font)
        
        name = entry["card"]["name"]
        metrics = QFontMetrics(font)
        elided = metrics.elidedText(name, Qt.ElideRight, CELL_WIDTH)
        caption_rect = QRect(img_x, caption_y, CELL_WIDTH, CAPTION_HEIGHT)
        painter.drawText(caption_rect, Qt.AlignTop | Qt.AlignHCenter, elided)
        painter.restore()
        
        # Trigger an image load if we haven't yet
        if token not in self._pixmap_cache and token not in self._requested:
            url = scryfall.image_url(entry["card"].get("scryfall_id", ""))
            if url:
                self._requested.add(token)
                row = index.row()
                ImageLoader.instance().submit(
                    token=(token, row),
                    url=url,
                    cache_name=scryfall.card_image_cache_name(entry["card"]),
                    width=CELL_WIDTH,
                    height=IMAGE_HEIGHT,
                    radius=IMAGE_RADIUS,
                    on_ready=self._on_image_ready,
                    on_failed=lambda tok: None,
                )
    
    def _on_image_ready(self, packed_token, image: QImage):
        token, row = packed_token
        self._pixmap_cache[token] = QPixmap.fromImage(image)
        # Tell the view to repaint just this row
        if self._view is not None:
            model = self._view.model()
            if model and row < model.rowCount():
                index = model.index(row, 0)
                self._view.update(index)


class CardGridView(QListView):
    """Virtualized icon-grid view backed by a CollectionModel."""
    
    card_clicked = Signal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setMovement(QListView.Static)
        self.setUniformItemSizes(True)
        self.setSpacing(8)
        self.setSelectionMode(QListView.NoSelection)
        self.setMouseTracking(True)  # needed for State_MouseOver
        
        self._delegate = CardThumbnailDelegate(self)
        self._delegate.attach_view(self)
        self.setItemDelegate(self._delegate)
        
        self.clicked.connect(self._on_clicked)
    
    def setCardData(self, cards: list):
        model = CollectionModel(cards, self)
        self.setModel(model)
    
    def setFilter(self, query: str):
        model = self.model()
        if isinstance(model, CollectionModel):
            model.setFilter(query)
    
    def filtered_count(self) -> int:
        model = self.model()
        return model.rowCount() if model else 0
    
    def _on_clicked(self, index: QModelIndex):
        entry = index.data(Qt.UserRole)
        if entry is None:
            return
        card = entry["card"]
        # Reshape to the flat dict the card modal expects
        payload = {
            "name": card["name"],
            "set": card.get("set", ""),
            "cn": card.get("cn", ""),
            "quantity": entry["quantity"],
            "price": card.get("prices", {}).get("eur") or 0,
            "image_url": scryfall.image_url(card.get("scryfall_id", "")),
        }
        self.card_clicked.emit(payload)