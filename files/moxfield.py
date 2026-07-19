"""Everything to do with talking to Moxfield: parsing deck URLs a user
pastes in, and building the API endpoint URLs used to fetch data."""

import re

API_BASE = "https://api2.moxfield.com"

_DECK_URL_RE = re.compile(r"moxfield\.com/decks/([A-Za-z0-9_-]+)")
_BARE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def extract_deck_id(url: str) -> str | None:
    """Pull the public deck ID out of a Moxfield deck URL. Also accepts a
    bare ID, in case that's what was pasted instead of a full URL."""
    url = url.strip()
    if not url:
        return None
    match = _DECK_URL_RE.search(url)
    if match:
        return match.group(1)
    if _BARE_ID_RE.match(url):
        return url
    return None


def user_api_url(username: str) -> str:
    return f"{API_BASE}/v1/users/{username}"


def decks_search_api_url() -> str:
    return f"{API_BASE}/v2/decks/search"


def collection_search_api_url(collection_id: str) -> str:
    return f"{API_BASE}/v1/collections/search/{collection_id}"


def deck_api_url(deck_id: str) -> str:
    return f"{API_BASE}/v3/decks/all/{deck_id}"
