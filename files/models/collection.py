"""Collection: one Moxfield collection's card list. Loaded from cache or
fetched fresh — see load() for the two modes.
"""

import requests
import cache_io
import moxfield
import paths

class Collection:
    def __init__(self, collection_id):
        """collection_id: the Moxfield public ID of this collection, or
        "-1" for "no collection" (e.g. a logged-out placeholder — see
        MTGApp.collection). Starts empty — call load() to populate."""
        self._collection_id = collection_id
        self._cards = []
        self._value = 0
        self._total_cards = 0

    @property
    def cards(self):
        """Raw Moxfield collection entries: each has at least "quantity"
        and "card" (with name/set/cn/prices/etc.)."""
        return self._cards

    @property
    def valued(self):
        return self._value

    @property
    def total_cards(self):
        return self._total_cards

    def load(self, force=False):
        """Populates cards/total_cards. force: False reads the cached
        collection_<id>.json if present (leaves the collection empty if
        not cached yet); True fetches the full collection from Moxfield's
        search API and overwrites the cache. A collection_id of "-1" (no
        real collection) makes the force branch a no-op."""
        path = paths.collection_cache_path(self._collection_id)

        if not force:
            data = cache_io.read_json(path)
            if data is None:
                return
        else:
            if self._collection_id == "-1":
                return
            url = moxfield.collection_search_api_url(self._collection_id)
            params = {
                "pageSize": 0,
                "sortType": "cardName",
                "sortDirection": "ascending",
            }
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data == {}:
                return
            cache_io.write_json(path, data)

        self._total_cards = data["totalOverall"]
        self._cards = data["data"]
