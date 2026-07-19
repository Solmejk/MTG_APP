from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QStackedWidget, QMessageBox, QInputDialog,
)

from app import MTGApp
from models.user import User
from ui.sidebar import Sidebar
from ui.screens.home import HomeScreen
from ui.screens.decks import DecksScreen
from ui.screens.deck_detail import DeckDetailScreen
from ui.screens.collection import CollectionScreen
from ui.screens.availability import AvailabilityScreen
from ui.screens.settings import SettingsScreen
from ui.components.card_modal import CardModal
from ui.components.export_modal import ExportModal
from ui.background import run_in_background
import clearCache
import session


class MainWindow(QMainWindow):
    def __init__(self, app: MTGApp):
        super().__init__()
        self.app = app
        self.setWindowTitle("MTG Collection Manager")
        self.resize(1100, 750)
        self._bg_tasks = []  # keeps background tasks alive — see ui/background.py
        self._login_in_progress = False
        
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        
        self.sidebar = Sidebar(app)
        self.stack = QStackedWidget()
        
        self.home_screen = HomeScreen(app)
        self.decks_screen = DecksScreen(app)
        self.collection_screen = CollectionScreen(app)
        self.availability_screen = AvailabilityScreen(app)
        self.settings_screen = SettingsScreen()
        
        self.deck_detail_screen = DeckDetailScreen()
        
        self._add_page("Home",         self.home_screen)
        self._add_page("Decks",        self.decks_screen)
        self._add_page("Collection",   self.collection_screen)
        self._add_page("Availability", self.availability_screen)
        self._add_page("Settings",     self.settings_screen)
        
        self.stack.addWidget(self.deck_detail_screen)
        
        self.sidebar.nav_changed.connect(self.stack.setCurrentIndex)
        self.sidebar.set_current(0)
        self.sidebar.login_requested.connect(self._on_login_requested)
        
        self.decks_screen.deck_selected.connect(self._open_deck_detail)
        self.deck_detail_screen.back_requested.connect(self._close_deck_detail)
        
        # Refresh from Moxfield (home screen button)
        self.home_screen.refresh_requested.connect(self._refresh_from_moxfield)
        
        # Cache clearing (settings screen)
        self.settings_screen.clear_cache_requested.connect(self._clear_cache)
        
        root_layout.addWidget(self.sidebar)
        root_layout.addWidget(self.stack, 1)
        
        self.setCentralWidget(root)
        
        # Card modal
        self.card_modal = CardModal(self)
        self.deck_detail_screen.card_clicked.connect(self.card_modal.show_card)
        self.collection_screen.card_clicked.connect(self.card_modal.show_card)
        self.availability_screen.card_clicked.connect(self.card_modal.show_card)

        # Export modal (availability screen)
        self.export_modal = ExportModal(self)
        self.availability_screen.export_requested.connect(self.export_modal.show_export)

        QTimer.singleShot(50, self._lazy_load_decks)
    
    def _add_page(self, name: str, widget: QWidget):
        self.sidebar.add_item(name)
        self.stack.addWidget(widget)
    
    def _open_deck_detail(self, deck):
        if not deck.cards:        # ← not loaded yet
            deck.load()
            if not deck.cards:     # cache missing (e.g. cache was cleared) — fetch it
                try:
                    deck.load(force=True)
                except Exception as e:
                    QMessageBox.warning(self, "Load failed", str(e))
        self.deck_detail_screen.show_deck(deck)
        self.stack.setCurrentWidget(self.deck_detail_screen)
    
    def _close_deck_detail(self):
        self.stack.setCurrentWidget(self.decks_screen)
    
    def _refresh_from_moxfield(self):
        if not self.app.is_logged_in:
            QMessageBox.information(self, "Not logged in", "Log in first via the sidebar avatar.")
            return
        self.home_screen.set_refresh_enabled(False)
        run_in_background(
            lambda: self.app.user.load(force=True),
            self._bg_tasks,
            on_finished=self._on_refresh_finished,
            on_failed=self._on_refresh_failed,
        )

    def _on_refresh_finished(self, _result):
        self._rebuild_data_screens()
        self.home_screen.set_refresh_enabled(True)

    def _on_refresh_failed(self, message: str):
        self.home_screen.set_refresh_enabled(True)
        QMessageBox.warning(self, "Refresh failed", message)

    def _on_login_requested(self):
        if self._login_in_progress:
            return
        current = self.app.username or ""
        username, ok = QInputDialog.getText(
            self, "Log in to Moxfield", "Moxfield username:", text=current,
        )
        if not ok:
            return
        username = username.strip()
        if not username:
            return

        self._login_in_progress = True
        self._pending_login_username = username
        self.sidebar.set_login_pending(True)
        run_in_background(
            lambda: self._fetch_user(username),
            self._bg_tasks,
            on_finished=self._on_login_finished,
            on_failed=self._on_login_failed,
        )

    @staticmethod
    def _fetch_user(username: str) -> User:
        # Build the new session off to the side rather than mutating
        # self.app directly — if the fetch fails partway (bad username,
        # network hiccup), we must not clobber a working prior session
        # with a half-loaded empty one.
        user = User(username)
        user.load(force=True)
        return user

    def _on_login_finished(self, user: User):
        self._login_in_progress = False
        self.app.set_user(user)
        session.save_username(self._pending_login_username)
        self._rebuild_data_screens()

    def _on_login_failed(self, message: str):
        self._login_in_progress = False
        self.sidebar.set_login_pending(False)
        self.sidebar.refresh_profile(self.app)  # untouched by the failed attempt — just restore its display
        QMessageBox.warning(self, "Login failed", message)

    def _clear_cache(self, targets: list):
        for target in targets:
            if target == "collection":
                clearCache.clear_collection()
            elif target == "decks":
                clearCache.clear_decks()
            elif target == "profile":
                clearCache.clear_profile()
            elif target == "images":
                clearCache.clear_images()

        if "profile" in targets:
            # The username itself lives in session.py, independent of the
            # user_<name>.json cache file — clearing profile data without
            # this would leave the sidebar showing the old username with no
            # way to tell the app has actually forgotten everything about them.
            self.app.logout()
            session.clear_username()

        self._rebuild_data_screens()

    def _rebuild_data_screens(self):
        """Reflect whatever is currently on disk (after a cache clear or a
        Moxfield refresh) without requiring an app restart. Home, Decks, and
        Collection each snapshot app data once at construction time, so they
        need to be rebuilt; the sidebar's avatar/username and each deck's
        contents are refreshed in place instead."""
        if self.app.username:  # nothing to (re)read if no one's logged in
            self.app.load(self.app.username)
        self.sidebar.refresh_profile(self.app)

        self._replace_screen("home_screen", HomeScreen(self.app))
        self.home_screen.refresh_requested.connect(self._refresh_from_moxfield)

        self._replace_screen("decks_screen", DecksScreen(self.app))
        self.decks_screen.deck_selected.connect(self._open_deck_detail)

        self._replace_screen("collection_screen", CollectionScreen(self.app))
        self.collection_screen.card_clicked.connect(self.card_modal.show_card)

        self._lazy_load_decks()  # re-fetch each deck's contents in the background

    def _replace_screen(self, attr_name: str, new_widget: QWidget):
        old_widget = getattr(self, attr_name)
        was_current = self.stack.currentWidget() is old_widget
        index = self.stack.indexOf(old_widget)

        self.stack.insertWidget(index, new_widget)
        self.stack.removeWidget(old_widget)
        old_widget.deleteLater()
        if was_current:
            self.stack.setCurrentWidget(new_widget)

        setattr(self, attr_name, new_widget)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "card_modal") and self.card_modal.isVisible():
            self.card_modal.resize(self.size())
        if hasattr(self, "export_modal") and self.export_modal.isVisible():
            self.export_modal.resize(self.size())

    def _lazy_load_decks(self):
        """Load deck contents off the main thread so the UI stays responsive."""
        run_in_background(
            self._load_all_deck_contents,
            self._bg_tasks,
            on_finished=self._on_decks_loaded,
        )

    def _load_all_deck_contents(self):
        for deck in self.app.decks:
            if not deck.cards:
                deck.load()
                if not deck.cards:  # cache missing (e.g. cache was cleared) — fetch it
                    try:
                        deck.load(force=True)
                    except Exception:
                        pass  # one deck failing to fetch shouldn't block the rest

    def _on_decks_loaded(self, _result):
        # Trigger the decks screen to refresh now that data is available
        if hasattr(self.decks_screen, "_rebuild_grid"):
            self.decks_screen._rebuild_grid()