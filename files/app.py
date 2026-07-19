from models.user import User
from models.collection import Collection

class MTGApp:
    def __init__(self, username=None):
        self._user = None
        if username:
            self.load(username)

    def load(self, username, force=False):
        self._user = User(username)
        self._user.load(force=force)

    def set_user(self, user: User):
        self._user = user

    def logout(self):
        self._user = None

    @property
    def is_logged_in(self) -> bool:
        return self._user is not None

    @property
    def user(self):
        return self._user

    @property
    def username(self):
        return self._user.username if self._user else None

    @property
    def collection(self):
        # Null object: no logged-in user just means an empty collection,
        # so screens can read app.collection.cards without special-casing.
        if self._user is None:
            return Collection("-1")
        return self._user.collection

    @property
    def decks(self):
        return self._user.decks if self._user else []

    def get_deck(self, name: str):
        if not self._user:
            return None
        for deck in self._user.decks:
            if deck.name.lower() == name.lower():
                return deck
        return None


if __name__ == "__main__":
    app = MTGApp("Solmejk")
    app.get_deck("Edgar Markov").set_active(False)
    app.get_deck("Anikthea, Hand of Erebos").set_active(False)
    app.get_deck("Draft Cube").set_active(False)
    app.get_deck("Tempo Dandân").set_active(False)
    app.get_deck("Jorn, God of Winter").set_active(False)
    app.get_deck("Agatha").set_active(False)
