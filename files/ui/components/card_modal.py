"""CardModal: the full-size card popout used across the app (Collection,
Decks/DeckDetail, and Availability screens all open the same instance via
MainWindow.card_modal). Shows the card art plus, when the clicked card
carries that data (only the Availability screen's results do), how many
of each printing you own and which of your decks use it.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QScrollArea

import scryfall
from image_cache import get_image_path
from ui.components.image_tile import round_pixmap
from ui.components.overlay_modal import OverlayModal


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


class CardModal(OverlayModal):
    """Popout showing one card at large size. Call show_card(card) to
    populate and display it. See OverlayModal for dismissal/resize
    behavior (outside-click, Esc, close button)."""

    def __init__(self, parent=None):
        """Builds the (initially empty/hidden) popout chrome — image slot,
        name/meta labels, a scrollable owned/used-in info area, and a
        Close button. Content is filled in later by show_card()."""
        super().__init__(parent)

        content = QWidget()
        content.setObjectName("cardModalContent")
        content.setFixedWidth(MODAL_CONTENT_WIDTH)
        content.setFixedHeight(MODAL_MIN_HEIGHT)

        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(30, 30, 30, 16)
        content_layout.setSpacing(12)

        # Everything above Close scrolls together as one unit — image, name,
        # meta, owned, used-in — with static spacing between them. Only
        # kicks in if a card has enough owned-printings/used-in text to not
        # fit the fixed popout height.
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

        self._init_overlay(content)

    def show_card(self, card: dict):
        """Populates the popout for `card` and displays it.

        card: a flat dict with at least name/set/cn/price/image_url — the
        shape produced by Collection/Deck/Availability screens for their
        clicked-card payloads. If it also carries owned_printings/
        used_in_decks (only Availability results do), those sections show;
        otherwise they're hidden.
        """
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
        self._show_overlay()

    def _resize_to_fit(self):
        """Sets the popout's height to fit this card's actual content,
        clamped between MODAL_MIN_HEIGHT and MODAL_MAX_HEIGHT — small by
        default, growing only as far as needed. Content beyond the max
        still scrolls (see the scroll area in __init__)."""
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
