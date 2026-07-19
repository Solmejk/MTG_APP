from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QPainter, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)

import scryfall
from image_cache import get_image_path
from ui.components.image_tile import round_pixmap


CARD_IMG_WIDTH = 360
CARD_IMG_HEIGHT = 504  # 5:7 ratio, scaled up
CARD_IMG_RADIUS = 18


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
        
        # The actual content card (image + details)
        self._content = QWidget()
        self._content.setObjectName("cardModalContent")
        self._content.setFixedWidth(CARD_IMG_WIDTH + 60)
        
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(30, 30, 30, 30)
        content_layout.setSpacing(16)
        content_layout.setAlignment(Qt.AlignCenter)
        
        self._image_label = QLabel()
        self._image_label.setFixedSize(CARD_IMG_WIDTH, CARD_IMG_HEIGHT)
        self._image_label.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(self._image_label, alignment=Qt.AlignCenter)
        
        self._name_label = QLabel()
        self._name_label.setObjectName("cardModalName")
        self._name_label.setAlignment(Qt.AlignCenter)
        self._name_label.setWordWrap(True)
        content_layout.addWidget(self._name_label)
        
        self._meta_label = QLabel()
        self._meta_label.setObjectName("cardModalMeta")
        self._meta_label.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(self._meta_label)

        # Only populated (and shown) for cards from the availability check —
        # Collection/DeckDetail cards don't carry this data.
        self._owned_label = QLabel()
        self._owned_label.setObjectName("cardModalMeta")
        self._owned_label.setAlignment(Qt.AlignCenter)
        self._owned_label.setWordWrap(True)
        content_layout.addWidget(self._owned_label)

        self._used_in_label = QLabel()
        self._used_in_label.setObjectName("cardModalMeta")
        self._used_in_label.setAlignment(Qt.AlignCenter)
        self._used_in_label.setWordWrap(True)
        content_layout.addWidget(self._used_in_label)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("backButton")
        close_btn.clicked.connect(self._dismiss)
        content_layout.addWidget(close_btn, alignment=Qt.AlignCenter)
        
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
            parts = [f"{p['quantity']}x {p['set'].upper()} #{p['cn']}" for p in owned_printings]
            self._owned_label.setText("Owned: " + " · ".join(parts))
            self._owned_label.show()
        else:
            self._owned_label.hide()

        used_in_decks = card.get("used_in_decks")
        if used_in_decks:
            parts = [f"{d['deck_name']} ({d['quantity']}x)" for d in used_in_decks]
            self._used_in_label.setText("Used in: " + ", ".join(parts))
            self._used_in_label.show()
        else:
            self._used_in_label.hide()

        # Cover the full parent
        if self.parent():
            self.resize(self.parent().size())
        self.raise_()
        self.show()
    
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