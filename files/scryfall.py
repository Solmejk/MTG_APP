"""Scryfall image URL / cache-key / pricing helpers, shared across the
collection grid, deck detail, card modal, and availability check."""

import threading
import time

import requests

BASE_IMAGE_URL = "https://cards.scryfall.io/normal/front"
SEARCH_URL = "https://api.scryfall.com/cards/search"

# Scryfall rejects requests using the HTTP library's default User-Agent.
HEADERS = {
    "User-Agent": "MTGCollectionManager/1.0",
    "Accept": "*/*",
}


class _RateLimiter:
    """Throttles calls to at most `max_per_second`, shared across threads.

    Scryfall requires staying under 10 requests/sec and explicitly warns
    that violating it repeatedly gets the IP network-blocked — this is not
    optional. Concurrent price lookups (availability.check_availability)
    can fire many requests from a thread pool at once; this makes sure
    the actual outbound requests still land at a safe rate regardless of
    how many threads are waiting on them.
    """

    def __init__(self, max_per_second: float):
        self._interval = 1.0 / max_per_second
        self._lock = threading.Lock()
        self._next_slot = 0.0

    def wait(self):
        with self._lock:
            now = time.monotonic()
            start = max(now, self._next_slot)
            self._next_slot = start + self._interval
            delay = start - now
        if delay > 0:
            time.sleep(delay)


_rate_limiter = _RateLimiter(max_per_second=3)
BATCH_SIZE = 15  # names per Scryfall query, combined with "or" — see cheapest_prices_eur


def image_url(scryfall_id: str) -> str:
    if not scryfall_id:
        return ""
    return f"{BASE_IMAGE_URL}/{scryfall_id[0]}/{scryfall_id[1]}/{scryfall_id}.jpg"


def card_key(card: dict) -> str:
    """Unique per printing: set + collector number."""
    return f"{card.get('set', '')}_{card.get('cn', '')}"


def card_image_cache_name(card: dict) -> str:
    return f"card_{card_key(card)}"


def _search_prints(query: str) -> list[dict]:
    for attempt in range(2):  # one retry, since a burst can trip the limit even under it
        try:
            _rate_limiter.wait()
            response = requests.get(
                SEARCH_URL,
                params={"q": query, "unique": "prints", "order": "eur", "dir": "asc"},
                headers=HEADERS,
                timeout=15,
            )
            if response.status_code == 429:
                if attempt == 0:
                    time.sleep(5)  # back off well past the momentary burst, then retry once
                    continue
                return []
            if response.status_code == 404:  # nothing in the batch has a eur price at all
                return []
            response.raise_for_status()
            return response.json().get("data", [])
        except Exception:
            return []
    return []


def cheapest_prices_eur(card_names: list[str]) -> dict[str, float | None]:
    """Cheapest EUR price for each name, one Scryfall request per BATCH_SIZE
    names (an "or"-combined query) instead of one request per card — this
    is what keeps a deck with 70+ missing cards from firing 70+ requests
    and tripping Scryfall's rate limit.

    The query filters to eur>0 server-side rather than sorting all prints
    ascending and filtering nulls client-side: with dir=asc, unpriced
    printings (digital-only, promos with no paper release, etc.) sort
    first, so a card with many of those would otherwise never reach a
    priced entry and wrongly look like it has no price at all."""
    unique_names = list(dict.fromkeys(card_names))  # de-dup, keep order
    prices: dict[str, float | None] = {name: None for name in unique_names}

    for i in range(0, len(unique_names), BATCH_SIZE):
        batch = unique_names[i:i + BATCH_SIZE]
        name_clauses = " or ".join(f'!"{name}"' for name in batch)
        prints = _search_prints(f"({name_clauses}) eur>0")
        for p in prints:
            name = p.get("name", "")
            price = p.get("prices", {}).get("eur")
            # Results are sorted ascending, so the first hit per name is its
            # cheapest — later duplicates of the same name are only pricier.
            if name in prices and prices[name] is None and price is not None:
                prices[name] = float(price)

    return prices
