"""Small helpers for the cache-file read/write pattern repeated across
User, Collection, and Deck."""

import json
from pathlib import Path


def read_json(path: Path):
    """Return parsed JSON, or None if the file doesn't exist."""
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data, indent=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent)
