"""Remembers which Moxfield username was last logged in, so the app can
restore the session on the next launch instead of requiring a login."""

import cache_io
import paths


def get_saved_username() -> str | None:
    data = cache_io.read_json(paths.SESSION_PATH)
    return data.get("username") if data else None


def save_username(username: str):
    cache_io.write_json(paths.SESSION_PATH, {"username": username})


def clear_username():
    if paths.SESSION_PATH.exists():
        paths.SESSION_PATH.unlink()
