import cache_io
from paths import DECK_STATES_PATH

def _load_states():
    return cache_io.read_json(DECK_STATES_PATH) or {}

def _save_states(states):
    cache_io.write_json(DECK_STATES_PATH, states, indent=2)

def is_active(deck_id: str) -> bool:
    """Default: True. Only returns False if explicitly set."""
    states = _load_states()
    return states.get(deck_id, {}).get("active", True)

def set_active(deck_id: str, active: bool):
    states = _load_states()
    if deck_id not in states:
        states[deck_id] = {}
    states[deck_id]["active"] = active
    _save_states(states)