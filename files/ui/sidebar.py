"""Sidebar: the left-hand navigation column — profile avatar/username
(doubling as the login button), and the page nav list MainWindow builds
via add_item().
"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QRegion
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
)

from image_cache import get_image_path
from ui.components.image_tile import ClickableLabel, make_placeholder


def make_circular(pixmap: QPixmap, size: int) -> QPixmap:
    """Crops and masks `pixmap` into a circle of side length `size`
    (scaling to fill, center-cropping any excess). Used for the sidebar
    avatar."""
    scaled = pixmap.scaled(
        size, size,
        Qt.KeepAspectRatioByExpanding,
        Qt.SmoothTransformation,
    )
    x = (scaled.width() - size) // 2
    y = (scaled.height() - size) // 2
    scaled = scaled.copy(QRect(x, y, size, size))

    result = QPixmap(size, size)
    result.fill(Qt.transparent)

    painter = QPainter(result)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)

    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    painter.setClipPath(path)

    painter.drawPixmap(0, 0, scaled)
    painter.end()

    return result


class Sidebar(QWidget):
    nav_changed = Signal(int)  # emitted with the clicked nav row's index
    login_requested = Signal()  # emitted when the avatar/username is clicked

    def __init__(self, app):
        """Builds the profile header and (initially empty) nav list.
        app: the MTGApp facade, used to populate the header immediately."""
        super().__init__()
        self.setObjectName("sidebar")
        self.setFixedWidth(180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_header(app))
        self._list = self._build_nav_list()
        layout.addWidget(self._list, 1)

    def _build_header(self, app) -> QWidget:
        """Builds the avatar + username block and populates it via
        refresh_profile(). Both are clickable (login_requested)."""
        header = QWidget()
        header.setObjectName("sidebarHeader")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(16, 20, 16, 20)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignCenter)

        self._avatar = ClickableLabel()
        self._avatar.setObjectName("sidebarAvatar")
        self._avatar.setFixedSize(64, 64)
        self._avatar.setAlignment(Qt.AlignCenter)
        self._avatar.setCursor(Qt.PointingHandCursor)
        self._avatar.clicked.connect(self.login_requested.emit)

        self._name_label = ClickableLabel()
        self._name_label.setObjectName("sidebarUsername")
        self._name_label.setAlignment(Qt.AlignCenter)
        self._name_label.setCursor(Qt.PointingHandCursor)
        self._name_label.clicked.connect(self.login_requested.emit)

        layout.addWidget(self._avatar, alignment=Qt.AlignCenter)
        layout.addWidget(self._name_label)

        self.refresh_profile(app)

        return header

    def refresh_profile(self, app):
        """Re-read the profile pic/username — call after a cache clear,
        Moxfield refresh, or login so the sidebar doesn't need an app
        restart. Clicking the avatar/name always opens the login prompt
        (pre-filled with the current username when already logged in, so
        it doubles as "switch account")."""
        if app.is_logged_in:
            self._name_label.setText(app.username)
            img_path = get_image_path(app.user.profile_image_url, app.username)
            if img_path:
                raw = QPixmap(str(img_path))
                self._avatar.setPixmap(make_circular(raw, 64))
            else:
                self._avatar.setPixmap(make_placeholder(64, 64, 32))
        else:
            self._name_label.setText("Log in")
            self._avatar.setPixmap(make_placeholder(64, 64, 32))

    def set_login_pending(self, pending: bool):
        """Immediate feedback while a login fetch is in flight — it can take
        a few seconds (profile + collection + decks), and without this the
        UI looks unresponsive after submitting a username."""
        if pending:
            self._name_label.setText("Logging in…")

    def _build_nav_list(self) -> QListWidget:
        """Builds the (initially empty) nav list — pages are added later
        via add_item(), one per MainWindow._add_page() call."""
        nav = QListWidget()
        nav.setObjectName("sidebarList")
        nav.setFocusPolicy(Qt.NoFocus)
        nav.currentRowChanged.connect(self.nav_changed.emit)
        return nav

    def add_item(self, label: str):
        """Appends a nav entry labeled `label` (its row index becomes the
        page's index in MainWindow's stack)."""
        QListWidgetItem(label, self._list)

    def set_current(self, index: int):
        """Selects the nav row at `index`, switching the visible page."""
        self._list.setCurrentRow(index)
