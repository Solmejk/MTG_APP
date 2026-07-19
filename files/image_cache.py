from pathlib import Path
import requests

from paths import IMAGES_DIR as CACHE_DIR
from scryfall import HEADERS  # also used for non-Scryfall images (e.g. Moxfield profile pics) — Scryfall's User-Agent requirement is the strictest, so it works everywhere


def get_image_path(url: str, name: str) -> Path | None:
    """
    Return a local path to the image, downloading if not cached.
    `name` is used as the filename (e.g. username for profile pics).
    Returns None if there's no URL or the fetch fails.
    """
    if not url:
        return None
    
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Use the URL's extension if present, otherwise default to png
    ext = Path(url).suffix or ".png"
    path = CACHE_DIR / f"{name}{ext}"
    
    if path.exists():
        return path
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        path.write_bytes(response.content)
        return path
    except requests.RequestException:
        return None