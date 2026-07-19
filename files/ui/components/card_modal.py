from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QPainter, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
)

import scryfall
from image_cache import get_image_path
from ui.components.image_tile import round_pixmap


CARD_IMG_WIDTH = 360
CARD_IMG_HEIGHT = 504  # 5:7 ratio, scaled up
CARD_IMG_RADIUS = 18

# Width stays constant; height instead adapts per card between these two
# bounds — small by default (a card with little/no owned/used-in info
# doesn't need a tall box with lots of empty space below it), growing only
# as far as actually needed, up to the max. Independent of the window
# size either way — never grows to fill a fullscreen window. Content that
# still doesn't fit at the max scrolls as one unit instead.
MODAL_CONTENT_WIDTH = CARD_IMG_WIDTH + 60
MODAL_MIN_HEIGHT = 650
MODAL_MAX_HEIGHT = 850


class CardModal(QWidget):
    """
    Full-window overlay showing a single card at large size with basic details.
    Close by clicking outside, pressing Esc, or hitting the close button.
    """

    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("cardModal")

        # Outer layout fills the screen
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignCenter)

        # The actual content card — fixed width, always centered; height is
        # set dynamically per card in _resize_to_fit()
        self._content = QWidget()
        self._content.setObjectName("cardModalContent")
        self._content.setFixedWidth(MODAL_CONTENT_WIDTH)
        self._content.setFixedHeight(MODAL_MIN_HEIGHT)

        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(30, 30, 30, 16)
        content_layout.setSpacing(12)

        # Everything above Close scrolls together as one unit — image, name,
        # meta, owned, used-in — with static spacing between them, same as
        # before. Only kicks in if a card has enough owned-printings/used-in
        # text to not fit the fixed popout height.
        self._scroll = QScrollArea()
        self._scroll.setObjectName("cardModalScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # QSS on the QScrollArea itself doesn't reach its viewport (a
        # separate internal widget) — without this the viewport falls back
        # to the app-wide background color, visibly darker than the card.
        self._scroll.viewport().setStyleSheet("background: transparent;")

        self._inner = QWidget()
        self._inner.setStyleSheet("background: transparent;")
        inner_layout = QVBoxLayout(self._inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(16)

        self._image_label = QLabel()
        self._image_label.setFixedSize(CARD_IMG_WIDTH, CARD_IMG_HEIGHT)
        self._image_label.setAlignment(Qt.AlignCenter)
        inner_layout.addWidget(self._image_label, alignment=Qt.AlignCenter)

        self._name_label = QLabel()
        self._name_label.setObjectName("cardModalName")
        self._name_label.setAlignment(Qt.AlignCenter)
        self._name_label.setWordWrap(True)
        inner_layout.addWidget(self._name_label)

        self._meta_label = QLabel()
        self._meta_label.setObjectName("cardModalMeta")
        self._meta_label.setAlignment(Qt.AlignCenter)
        inner_layout.addWidget(self._meta_label)

        # Only populated (and shown) for cards from the availability check —
        # Collection/DeckDetail cards don't carry this data.
        self._owned_label = QLabel()
        self._owned_label.setObjectName("cardModalMeta")
        self._owned_label.setAlignment(Qt.AlignCenter)
        self._owned_label.setWordWrap(True)
        inner_layout.addWidget(self._owned_label)

        self._used_in_label = QLabel()
        self._used_in_label.setObjectName("cardModalMeta")
        self._used_in_label.setAlignment(Qt.AlignCenter)
        self._used_in_label.setWordWrap(True)
        inner_layout.addWidget(self._used_in_label)

        self._scroll.setWidget(self._inner)
        content_layout.addWidget(self._scroll, 1)

        self._close_btn = QPushButton("Close")
        self._close_btn.setObjectName("backButton")
        self._close_btn.clicked.connect(self._dismiss)
        content_layout.addWidget(self._close_btn, alignment=Qt.AlignCenter)

        outer.addWidget(self._content)

        self.hide()

    def show_card(self, card: dict):
        # Load the image (we have it cached already)
        image_url = card.get("image_url", "")
        if image_url:
            cache_name = scryfall.card_image_cache_name(card)
            img_path = get_image_path(image_url, cache_name)
            if img_path:
                pixmap = QPixmap(str(img_path))
                pixmap = pixmap.scaled(
                    CARD_IMG_WIDTH, CARD_IMG_HEIGHT,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                pixmap = round_pixmap(pixmap, CARD_IMG_RADIUS)
                self._image_label.setPixmap(pixmap)

        # Details
        self._name_label.setText(card["name"])
        set_code = card.get("set", "").upper()
        cn = card.get("cn", "")
        price = card.get("price", 0)
        self._meta_label.setText(f"{set_code} · #{cn} · €{price:.2f}")

        owned_printings = card.get("owned_printings")
        if owned_printings:
            total_owned = sum(p["quantity"] for p in owned_printings)
            lines = [f"Owned {total_owned}"]
            lines += [f"{p['quantity']}x {p['set'].upper()}" for p in owned_printings]
            self._owned_label.setText("\n".join(lines))
            self._owned_label.show()
        else:
            self._owned_label.hide()

        used_in_decks = card.get("used_in_decks")
        if used_in_decks:
            lines = ["Used in:"]
            lines += [f"{d['deck_name']} ({d['quantity']}x)" for d in used_in_decks]
            self._used_in_label.setText("\n".join(lines))
            self._used_in_label.show()
        else:
            self._used_in_label.hide()

        self._resize_to_fit()

        # Cover the full parent
        if self.parent():
            self.resize(self.parent().size())
        self.raise_()
        self.show()

    def _resize_to_fit(self):
        """Size the popout to fit this card's actual content, between
        MODAL_MIN_HEIGHT and MODAL_MAX_HEIGHT — small by default, growing
        only as far as needed. Content beyond the max still scrolls."""
        self._inner.adjustSize()
        content_layout = self._content.layout()
        margins = content_layout.contentsMargins()
        chrome = (
            margins.top() + margins.bottom()
            + content_layout.spacing()
            + self._close_btn.sizeHint().height()
        )
        desired = self._inner.sizeHint().height() + chrome
        height = max(MODAL_MIN_HEIGHT, min(MODAL_MAX_HEIGHT, desired))
        self._content.setFixedHeight(height)

    def _dismiss(self):
        self.hide()
        self.closed.emit()

    def mousePressEvent(self, event):
        """Clicking outside the content card closes the modal."""
        # If the click was inside the content widget, ignore it (don't close)
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
