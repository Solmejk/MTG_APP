import os
import shutil

from paths import CACHE_DIR, DECKS_DIR, IMAGES_DIR


def clear_collection():
    if not os.path.exists(CACHE_DIR):
        return
    for filename in os.listdir(CACHE_DIR):
        if filename.startswith("collection_") and filename.endswith(".json"):
            os.remove(os.path.join(CACHE_DIR, filename))
    print("Cleared collection cache.")


def clear_decks():
    if not os.path.exists(CACHE_DIR):
        return
    # Deck-list files at top level
    for filename in os.listdir(CACHE_DIR):
        if filename.startswith("decks_") and filename.endswith(".json"):
            os.remove(os.path.join(CACHE_DIR, filename))
    # Per-deck folder
    if DECKS_DIR.exists():
        shutil.rmtree(DECKS_DIR)
    print("Cleared deck caches.")


def clear_profile():
    if not os.path.exists(CACHE_DIR):
        return
    for filename in os.listdir(CACHE_DIR):
        if filename.startswith("user_") and filename.endswith(".json"):
            os.remove(os.path.join(CACHE_DIR, filename))
    print("Cleared profile cache.")


def clear_images():
    if IMAGES_DIR.exists():
        shutil.rmtree(IMAGES_DIR)
    print("Cleared image cache.")


def clear_all():
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