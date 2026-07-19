"""User: one Moxfield account's profile, collection, and deck list.
Composes Collection and Deck — loading a User cascades into loading
(cache-only, or force-fetching) all three.
"""

import requests
import cache_io
import moxfield
import paths
from models.collection import Collection
from models.deck import Deck

class User:
    def __init__(self, username):
        """username: the Moxfield username this User represents. Starts
        empty — call load() to populate profile/collection/decks."""
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
        """The Moxfield public ID of this user's collection, or "-1" if
        unknown (profile not yet loaded, or the account has none)."""
        return self._collection_id

    @property
    def collection(self):
        """This user's Collection, or None if load_collection() hasn't
        run yet."""
        return self._collection

    @property
    def decks(self):
        """This user's decks (as Deck stubs — see load_decks for what's
        populated immediately vs. loaded lazily per-deck)."""
        return self._decks

    @property
    def profile_image_url(self):
        return self._profile_image_url

    def load(self, force=False):
        """Loads profile, collection, and deck list, in that order (deck
        list's cache key doesn't depend on the others, but collection's
        does — see load_profile). force: False reads from cache only;
        True re-fetches everything from Moxfield."""
        self.load_profile(force=force)
        self.load_collection(force=force)
        self.load_decks(force=force)

    def load_profile(self, force=False):
        """Loads profileImageUrl and collectionPublicId. force: False
        reads the cached user_<username>.json if present (leaves fields
        unchanged if not cached yet); True fetches from Moxfield's users
        API and overwrites the cache."""
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
        """Loads the list of this user's decks as Deck stubs (id + name
        only — each deck's cards/format load separately, on demand, via
        Deck.load()). force: False reads the cached decks_<username>.json
        if present; True fetches the deck list from Moxfield's search API
        and overwrites the cache."""
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
        """(Re)builds self._collection using the current collection_id
        (set by load_profile) and loads it. force: passed straight
        through to Collection.load()."""
        self._collection = Collection(self._collection_id)
        self._collection.load(force=force)
