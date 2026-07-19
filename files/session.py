"""Remembers which Moxfield username was last logged in, so the app can
restore the session on the next launch instead of requiring a login."""

import cache_io
import paths


def get_saved_username() -> str | None:
    """Reads the last-logged-in username from disk. Returns None if
    nobody's logged in (fresh install, or logged out via clear_username)."""
    data = cache_io.read_json(paths.SESSION_PATH)
    return data.get("username") if data else None


def save_username(username: str):
    """Persists `username` as the current session, overwriting whatever
    was saved before. Called on successful login."""
    cache_io.write_json(paths.SESSION_PATH, {"username": username})


def clear_username():
    """Forgets the saved session (deletes the session file if present).
    Called on logout / when the profile cache is cleared."""
    if paths.SESSION_PATH.exists():
        paths.SESSION_PATH.unlink()
