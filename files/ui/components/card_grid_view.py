"""CardGridView: the Collection screen's card grid. Unlike the tile-based
grids elsewhere (Decks, DeckDetail, Availability — see ImageTile), this
one is a virtualized QListView + custom delegate, since a full collection
can be thousands of cards and building a real widget per card would be
far too slow/memory-heavy.
"""

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
from ui.components.image_tile import make_placeholder, paint_tint_overlay
from ui.components.card_section import quantity_caption


CELL_WIDTH = 140
CELL_HEIGHT = 196 + 40  # image height + caption space
IMAGE_HEIGHT = 196
IMAGE_RADIUS = 12
CAPTION_HEIGHT = 36

FOIL_COLOR = QColor("#9b59b6")  # purple, gradient start
FOIL_COLOR2 = QColor("#f1c40f")  # yellow, gradient end
FOIL_ALPHA = 50  # Foil transparency


class CollectionModel(QAbstractListModel):
    """Wraps a list of card entries with optional name filtering."""
    
    def __init__(self, cards: list, parent=None):
        """cards: raw Moxfield collection entries (list of {"quantity":
        int, "card": {...}, ...})."""
        super().__init__(parent)
        self._all_cards = cards
        self._filtered = cards
        self._filter = ""

    def rowCount(self, parent=QModelIndex()):
        """Qt model API: number of rows currently shown (post-filter)."""
        if parent.isValid():
            return 0
        return len(self._filtered)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        """Qt model API: Qt.UserRole returns the full entry dict (what
        the delegate paints from); Qt.DisplayRole returns just the card
        name (used for accessibility/sorting, not painted directly)."""
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
        """Narrows the visible rows to cards whose name contains `query`
        (case-insensitive); an empty query shows everything. No-ops if
        `query` matches the current filter."""
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
        """Qt delegate API: paints one cell — the (possibly still-loading
        placeholder) image, a foil tint if applicable, a hover border,
        and the elided card-name caption. Also lazily kicks off an
        ImageLoader fetch the first time a given card's image is needed."""
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

        # Foil tint — a very slight translucent purple-to-yellow fade, rounded to match the image
        if entry.get("isFoil"):
            color = QColor(FOIL_COLOR)
            color.setAlpha(FOIL_ALPHA)
            color2 = QColor(FOIL_COLOR2)
            color2.setAlpha(FOIL_ALPHA)
            paint_tint_overlay(
                painter, QRectF(x, img_y, pixmap.width(), pixmap.height()), IMAGE_RADIUS, color, color2,
            )

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
        
        caption = quantity_caption({"quantity": entry["quantity"], "name": entry["card"]["name"]})
        metrics = QFontMetrics(font)
        elided = metrics.elidedText(caption, Qt.ElideRight, CELL_WIDTH)
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
        """ImageLoader callback (main thread): caches the decoded image
        and repaints just the affected row. packed_token: (card_token,
        row) as passed to ImageLoader.submit()."""
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
    
    card_clicked = Signal(dict)  # emitted with a flat card payload dict on click

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
        """(Re)populates the grid. cards: raw Moxfield collection entries
        (see CollectionModel)."""
        model = CollectionModel(cards, self)
        self.setModel(model)

    def setFilter(self, query: str):
        """Narrows the grid to cards matching `query` — see
        CollectionModel.setFilter."""
        model = self.model()
        if isinstance(model, CollectionModel):
            model.setFilter(query)

    def filtered_count(self) -> int:
        """Number of cards currently visible (post-filter)."""
        model = self.model()
        return model.rowCount() if model else 0
    
    def _on_clicked(self, index: QModelIndex):
        """Qt view signal handler: reshapes the raw collection entry at
        `index` into the flat dict CardModal.show_card expects, and
        emits card_clicked."""
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