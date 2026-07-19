"""Clears cached data by category (collection/decks/profile/images).
Used both by the Settings screen's "Clear cache" checkboxes and as a
standalone CLI: `python clearCache.py [collection|decks|profile|images|all]`.
"""

import os
import shutil

from paths import CACHE_DIR, DECKS_DIR, IMAGES_DIR


def clear_collection():
    """Deletes every cached collection_*.json file."""
    if not os.path.exists(CACHE_DIR):
        return
    for filename in os.listdir(CACHE_DIR):
        if filename.startswith("collection_") and filename.endswith(".json"):
            os.remove(os.path.join(CACHE_DIR, filename))
    print("Cleared collection cache.")


def clear_decks():
    """Deletes the cached deck list(s) (decks_*.json), any leftover
    single-deck cache files (deck_*.json), and the whole per-deck content
    folder (DECKS_DIR)."""
    if not os.path.exists(CACHE_DIR):
        return
    # Deck-list files at top level
    for filename in os.listdir(CACHE_DIR):
        if (filename.startswith("decks_") or filename.startswith("deck_")) and filename.endswith(".json"):
            os.remove(os.path.join(CACHE_DIR, filename))
    # Per-deck folder
    if DECKS_DIR.exists():
        shutil.rmtree(DECKS_DIR)
    print("Cleared deck caches.")


def clear_profile():
    """Deletes every cached user_*.json profile file. Note: this does not
    forget which username is logged in — that's session.py's job, handled
    separately by MainWindow._clear_cache when "profile" is cleared."""
    if not os.path.exists(CACHE_DIR):
        return
    for filename in os.listdir(CACHE_DIR):
        if filename.startswith("user_") and filename.endswith(".json"):
            os.remove(os.path.join(CACHE_DIR, filename))
    print("Cleared profile cache.")


def clear_images():
    """Deletes the entire cached-images folder (card art, commander art,
    profile pictures)."""
    if IMAGES_DIR.exists():
        shutil.rmtree(IMAGES_DIR)
    print("Cleared image cache.")


def clear_all():
    """Clears every cache category."""
    clear_collection()
    clear_decks()
    clear_profile()
    clear_images()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python clearCache.py [collection|decks|profile|images|all]")
        sys.exit(1)

    target = sys.argv[1].lower()
    if target == "collection":
        clear_collection()
    elif target == "decks":
        clear_decks()
    elif target == "profile":
        clear_profile()
    elif target == "images":
        clear_images()
    elif target == "all":
        clear_all()
    else:
        print(f"Unknown: {target}")
        sys.exit(1)
