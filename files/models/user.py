import requests
import cache_io
import moxfield
import paths
from models.collection import Collection
from models.deck import Deck

class User:
    def __init__(self, username):
        self._username = username
        self._profile_image_url = ""
        self._collection_id = "-1"
        self._collection = None
        self._decks = []

    @property
    def username(self):
        return self._username

    @property
    def collection_id(self):
        return self._collection_id

    @property
    def collection(self):
        return self._collection

    @property
    def decks(self):
        return self._decks

    @property
    def profile_image_url(self):
        return self._profile_image_url

    def load(self, force=False):
        self.load_profile(force=force)
        self.load_collection(force=force)
        self.load_decks(force=force)

    def load_profile(self, force=False):
        path = paths.user_cache_path(self._username)

        if not force:
            data = cache_io.read_json(path)
            if data is None:
                return
        else:
            response = requests.get(moxfield.user_api_url(self._username), timeout=10)
            response.raise_for_status()
            data = response.json()
            cache_io.write_json(path, data, indent=2)

        self._profile_image_url = data.get("profileImageUrl", "")
        self._collection_id = data.get("collectionPublicId", "-1")

    def load_decks(self, force=False):
        path = paths.decks_list_cache_path(self._username)

        if not force:
            decks = cache_io.read_json(path)
            if decks is None:
                return
        else:
            url = moxfield.decks_search_api_url()
            params = {
                "includePinned": "false",
                "showIllegal": "true",
                "authorUserNames": self._username,
                "sortType": "updated",
                "sortDirection": "descending",
                "board": "mainboard",
            }
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            decks = response.json()
            cache_io.write_json(path, decks)

        self._decks = []
        for deck in decks["data"]:
            name = deck["name"]
            deck_id = deck["publicId"]
            self._decks.append(Deck(deck_id, name))

    def load_collection(self, force=False):
        self._collection = Collection(self._collection_id)
        self._collection.load(force=force)
