"""MainWindow: the app's top-level window. Owns the sidebar, the screen
stack (Home/Decks/Collection/Availability/Settings + the on-demand
DeckDetail screen), and the two shared popouts (CardModal, ExportModal).
Also owns every cross-screen flow that doesn't belong to a single
screen: login, logout, cache-clear, Moxfield refresh, and rebuilding the
data-snapshotting screens after any of those.
"""

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
        """Builds every screen, wires up navigation and cross-screen
        signals, and kicks off the background deck-content load. app:
        the MTGApp facade, already loaded (or logged-out) by ui.py."""
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

        # Card modal — shared by every screen that shows a clickable card
        self.card_modal = CardModal(self)
        self.deck_detail_screen.card_clicked.connect(self.card_modal.show_card)
        self.collection_screen.card_clicked.connect(self.card_modal.show_card)
        self.availability_screen.card_clicked.connect(self.card_modal.show_card)

        # Export modal (availability screen)
        self.export_modal = ExportModal(self)
        self.availability_screen.export_requested.connect(self.export_modal.show_export)

        QTimer.singleShot(50, self._lazy_load_decks)

    def _add_page(self, name: str, widget: QWidget):
        """Registers `widget` as a navigable screen: adds a sidebar entry
        labeled `name` and a matching page in the stack (same index in
        both, since Sidebar.nav_changed drives stack.setCurrentIndex)."""
        self.sidebar.add_item(name)
        self.stack.addWidget(widget)

    def _open_deck_detail(self, deck):
        """Slot for DecksScreen.deck_selected: ensures `deck`'s contents
        are loaded (cache-only first, then a forced fetch if the cache
        was empty/cleared) and switches to the detail screen."""
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
        """Slot for DeckDetailScreen.back_requested: returns to the Decks
        screen."""
        self.stack.setCurrentWidget(self.decks_screen)

    def _refresh_from_moxfield(self):
        """Slot for HomeScreen.refresh_requested: force-reloads the
        current user's profile/collection/decks from Moxfield in the
        background. No-ops with a warning if nobody's logged in."""
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
        """Background-task callback: rebuilds the data screens to show
        the freshly-fetched data and re-enables the refresh button.
        _result is User.load's return value (None), unused."""
        self._rebuild_data_screens()
        self.home_screen.set_refresh_enabled(True)

    def _on_refresh_failed(self, message: str):
        """Background-task callback: re-enables the refresh button and
        surfaces the error. message: str(exception) from the failed fetch."""
        self.home_screen.set_refresh_enabled(True)
        QMessageBox.warning(self, "Refresh failed", message)

    def _on_login_requested(self):
        """Slot for Sidebar.login_requested (clicking the avatar/name):
        prompts for a Moxfield username and, if one's entered, force-
        fetches it in the background. Pre-fills the prompt with the
        current username, so this doubles as "switch account". Ignored
        while a login is already in flight."""
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
        """Background-task body for login: builds and force-loads a new
        User for `username`. Runs off to the side rather than mutating
        self.app directly — if the fetch fails partway (bad username,
        network hiccup), a working prior session must not be clobbered
        with a half-loaded empty one. Raises on failure (caught by
        run_in_background, routed to _on_login_failed)."""
        user = User(username)
        user.load(force=True)
        return user

    def _on_login_finished(self, user: User):
        """Background-task callback for a successful login: commits the
        fetched user, persists the session, and rebuilds the data
        screens. user: the fully-loaded User from _fetch_user."""
        self._login_in_progress = False
        self.app.set_user(user)
        session.save_username(self._pending_login_username)
        self._rebuild_data_screens()

    def _on_login_failed(self, message: str):
        """Background-task callback for a failed login: restores the
        sidebar's prior display (untouched by the failed attempt) and
        surfaces the error. message: str(exception) from the failed fetch."""
        self._login_in_progress = False
        self.sidebar.set_login_pending(False)
        self.sidebar.refresh_profile(self.app)  # untouched by the failed attempt — just restore its display
        QMessageBox.warning(self, "Login failed", message)

    def _clear_cache(self, targets: list):
        """Slot for SettingsScreen.clear_cache_requested: clears each
        selected cache category on disk, then rebuilds the data screens
        to reflect it. targets: list of "collection"/"decks"/"profile"/
        "images". Clearing "profile" also logs the user out — see the
        comment below for why that's necessary."""
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
        """Swaps the screen stored at self.<attr_name> for `new_widget` in
        both the stack and the instance attribute, preserving the stack's
        page order and which page is currently visible. attr_name: e.g.
        "home_screen". new_widget: the freshly-built replacement screen."""
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
        """Keeps whichever overlay (card/export modal) is currently open
        covering the full window as it resizes."""
        super().resizeEvent(event)
        if hasattr(self, "card_modal") and self.card_modal.isVisible():
            self.card_modal.resize(self.size())
        if hasattr(self, "export_modal") and self.export_modal.isVisible():
            self.export_modal.resize(self.size())

    def _lazy_load_decks(self):
        """Kicks off loading every deck's contents in the background, so
        startup (or a post-refresh/login/clear-cache rebuild) doesn't
        block the UI. Scheduled via QTimer.singleShot after __init__ and
        called again directly from _rebuild_data_screens()."""
        run_in_background(
            self._load_all_deck_contents,
            self._bg_tasks,
            on_finished=self._on_decks_loaded,
        )

    def _load_all_deck_contents(self):
        """Background-task body: loads every deck that isn't already
        loaded, cache-only first, falling back to a forced fetch if the
        cache is missing (e.g. cleared). One deck failing to fetch
        doesn't stop the rest."""
        for deck in self.app.decks:
            if not deck.cards:
                deck.load()
                if not deck.cards:  # cache missing (e.g. cache was cleared) — fetch it
                    try:
                        deck.load(force=True)
                    except Exception:
                        pass  # one deck failing to fetch shouldn't block the rest

    def _on_decks_loaded(self, _result):
        """Background-task callback: refreshes the Decks screen's grid
        now that deck contents (format, in particular) are available.
        _result is unused (_load_all_deck_contents returns None)."""
        # Trigger the decks screen to refresh now that data is available
        if hasattr(self.decks_screen, "_rebuild_grid"):
            self.decks_screen._rebuild_grid()
