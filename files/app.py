"""MTGApp: the top-level facade the UI layer talks to. Wraps the current
User (or no user, if nobody's logged in) and exposes read-only access to
their collection/decks, plus the login/logout/refresh entry points
MainWindow drives. See models/user.py for what a "user" actually loads.
"""

from models.user import User
from models.collection import Collection

class MTGApp:
    def __init__(self, username=None):
        """username: a previously-logged-in Moxfield username to load
        immediately (cache-only — see User.load), or None to start in the
        logged-out state. Session persistence (session.py) is what
        supplies this on a normal app launch."""
        self._user = None
        if username:
            self.load(username)

    def load(self, username, force=False):
        """Replaces the current user with a freshly constructed one for
        `username` and loads their data. force: False reads from the
        local cache only (fast, offline-friendly); True re-fetches
        everything from Moxfield. Used for both the initial app launch
        (force=False) and the "Refresh from Moxfield" action (force=True)."""
        self._user = User(username)
        self._user.load(force=force)

    def set_user(self, user: User):
        """Swaps in an already-loaded User object directly, bypassing
        load(). Used by the login flow, which builds and force-loads a
        User off to the side first (see MainWindow._fetch_user) so a
        failed login can't clobber a working session."""
        self._user = user

    def logout(self):
        """Drops the current user, returning the app to its logged-out
        state. Does not touch any cached files on disk."""
        self._user = None

    @property
    def is_logged_in(self) -> bool:
        """True if a user is currently loaded."""
        return self._user is not None

    @property
    def user(self):
        """The current User, or None if logged out."""
        return self._user

    @property
    def username(self):
        """The current username, or None if logged out."""
        return self._user.username if self._user else None

    @property
    def collection(self):
        """The current user's Collection. When logged out, returns an
        empty placeholder Collection (a "null object") instead of None,
        so screens can read app.collection.cards unconditionally without
        having to special-case the logged-out state."""
        if self._user is None:
            return Collection("-1")
        return self._user.collection

    @property
    def decks(self):
        """The current user's decks, or an empty list if logged out."""
        return self._user.decks if self._user else []

    def get_deck(self, name: str):
        """Looks up one of the current user's decks by name
        (case-insensitive). Returns None if logged out or no deck
        matches. name: the deck's display name to search for."""
        if not self._user:
            return None
        for deck in self._user.decks:
            if deck.name.lower() == name.lower():
                return deck
        return None
