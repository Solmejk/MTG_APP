"""Centralized cache/data paths, anchored to this file's location rather
than the process's current working directory.

Every module used to build its own "files/cache/..." string relative to
cwd, which silently breaks (empty cache, no error) if the app is ever
launched from a different directory. Anchoring to __file__ makes launch
directory irrelevant.
"""

from pathlib import Path

FILES_ROOT = Path(__file__).parent
CACHE_DIR = FILES_ROOT / "cache"
IMAGES_DIR = CACHE_DIR / "images"
DECKS_DIR = CACHE_DIR / "decks"
DECK_STATES_PATH = CACHE_DIR / "deck_states.json"
SESSION_PATH = CACHE_DIR / "session.json"


def user_cache_path(username: str) -> Path:
    """Path to a user's cached profile JSON."""
    return CACHE_DIR / f"user_{username}.json"


def collection_cache_path(collection_id: str) -> Path:
    """Path to a cached collection's JSON."""
    return CACHE_DIR / f"collection_{collection_id}.json"


def decks_list_cache_path(username: str) -> Path:
    """Path to a user's cached deck list JSON (id/name pairs only —
    individual deck contents live under DECKS_DIR, see deck_cache_path)."""
    return CACHE_DIR / f"decks_{username}.json"


def deck_cache_path(deck_id: str) -> Path:
    """Path to one deck's cached contents JSON."""
    return DECKS_DIR / f"{deck_id}.json"
