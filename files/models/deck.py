import requests
import cache_io
import moxfield
import paths
import scryfall
from models.deck_state import is_active, set_active

class Deck:
    def __init__(self, deck_id, name):
        self._deck_id = deck_id
        self._name = name
        self._cards = []
        self._total_cards = 0
        self._commanders = []
        self._author = ""
        self._value = 0
        self._active = is_active(self._deck_id)
        self._format = ""

    @property
    def cards(self):
        return self._cards

    @property
    def format(self):
        return self._format

    @property
    def deck_id(self):
        return self._deck_id

    @property
    def value(self):
        return self._value

    @property
    def total_cards(self):
        return self._total_cards

    @property
    def name(self):
        return self._name

    @property
    def commanders(self):
        return self._commanders

    @property
    def author(self):
        return self._author

    @property
    def active(self):
        return self._active

    def set_active(self, value: bool):
        self._active = value
        set_active(self._deck_id, value)

    def load(self, force=False):
        path = paths.deck_cache_path(self._deck_id)

        if not force:
            data = cache_io.read_json(path)
            if data is None:
                return
        else:
            response = requests.get(moxfield.deck_api_url(self._deck_id), timeout=10)
            response.raise_for_status()
            data = self._trim_raw_deck(response.json())
            cache_io.write_json(path, data, indent=2)

        self._name = data["name"]
        self._format = data.get("format", "")
        self._commanders = data["commanders"]
        self._cards = data["cards"]
        self._total_cards = data["total_cards"]
        self._author = data["author"]
        self._value = data["value"]

    @staticmethod
    def _trim_raw_deck(raw: dict) -> dict:
        cards = []
        commanders = []
        total_value = 0

        for board_name, board in raw["boards"].items():
            if board_name not in ("mainboard", "commanders"):
                continue
            for entry in board["cards"].values():
                card = entry["card"]
                price = card.get("prices", {}).get("eur") or 0
                card_data = {
                    "name": card["name"],
                    "set": card["set"],
                    "cn": card["cn"],
                    "quantity": entry["quantity"],
                    "price": price,
                    "image_url": scryfall.image_url(card["scryfall_id"]),
                    "type_line": card["type_line"],
                }
                if board_name == "commanders":
                    commanders.append(card_data)
                cards.append(card_data)
                total_value += price * entry["quantity"]

        return {
            "name": raw["name"],
            "format": raw.get("format", ""),
            "commanders": commanders,
            "cards": cards,
            "total_cards": sum(c["quantity"] for c in cards),
            "author": raw.get("createdByUser", {}).get("userName", ""),
            "value": round(total_value, 2),
        }
