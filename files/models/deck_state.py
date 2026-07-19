"""Persists each deck's active/archived flag, independent of the deck's
own cached contents (clearing the deck cache doesn't forget this). Keyed
by deck_id in a single deck_states.json file.
"""

import cache_io
from paths import DECK_STATES_PATH

def _load_states() -> dict:
    """Reads the full deck_states.json file. Returns {} if it doesn't
    exist yet (no deck has ever been explicitly archived/reactivated)."""
    return cache_io.read_json(DECK_STATES_PATH) or {}

def _save_states(states: dict):
    """Overwrites deck_states.json with `states`."""
    cache_io.write_json(DECK_STATES_PATH, states, indent=2)

def is_active(deck_id: str) -> bool:
    """Whether `deck_id` is active. Default: True — only returns False if
    it was explicitly archived via set_active(deck_id, False)."""
    states = _load_states()
    return states.get(deck_id, {}).get("active", True)

def set_active(deck_id: str, active: bool):
    """Records `deck_id`'s active/archived state, creating its entry in
    deck_states.json if this is the first time it's been changed."""
    states = _load_states()
    if deck_id not in states:
        states[deck_id] = {}
    states[deck_id]["active"] = active
    _save_states(states)
