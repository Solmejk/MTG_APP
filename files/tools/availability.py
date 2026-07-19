"""Standalone CLI script: checks a pasted Moxfield plain-text decklist
against a user's collection + active decks and prints/saves an
availability report. Superseded in the app itself by
ui/screens/availability.py + the root-level availability.py module, but
kept as a quick command-line alternative.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # files/ root, for app.py
from app import MTGApp

BASIC_LANDS = {"plains", "island", "swamp", "mountain", "forest", "wastes"}

def parse_moxfield_text(text):
    """
    Parse Moxfield plain-text export into [(quantity, name), ...].
    Lines look like: '1 Sol Ring' or '7 Forest'.
    Blank lines and lines that don't start with a number are skipped.
    """
    cards = []
    pattern = re.compile(r"^\s*(\d+)\s+(.+?)\s*$")
    
    for line in text.splitlines():
        match = pattern.match(line)
        if match:
            quantity = int(match.group(1))
            name = match.group(2)
            cards.append((quantity, name))
    
    return cards

def count_in_collection(collection, card_name):
    """Sum quantities of a card across the collection (name match, case-insensitive)."""
    target = card_name.lower()
    total = 0
    for entry in collection.cards:
        if entry["card"]["name"].lower() == target:
            total += entry["quantity"]
    return total

def find_in_decks(decks, card_name):
    """Sum quantities of a card across all active decks (name match,
    case-insensitive). Returns (total, used_in) where used_in is a list
    of {"name", "quantity"} dicts for decks that use the card."""
    target = card_name.lower()
    total = 0
    used_in = []
    
    for deck in decks:
        if not deck.active: 
            continue
        deck_count = 0
        for card in deck.cards:
            if card["name"].lower() == target:
                deck_count += card["quantity"]
        
        if deck_count > 0:
            total += deck_count
            used_in.append({
                "name": deck.name,
                "quantity": deck_count,
            })
    
    return total, used_in

def check_availability(app, deck_text):
    """
    For each card in the input deck list, compute owned/used/needed/available
    and assign one of four flags. Returns list of result dicts.
    """
    needed_cards = parse_moxfield_text(deck_text)
    results = []
    
    for needed, name in needed_cards:
        if name.lower() in BASIC_LANDS:
            continue
        
        owned = count_in_collection(app.collection, name)
        used, used_in = find_in_decks(app.decks, name)
        available = owned - used
        
        if owned == 0:
            flag = "UNOWNED"
        elif available >= needed:
            flag = "FREE"
        elif available > 0:
            flag = "PARTIAL"
        else:
            flag = "ALL_USED"
        
        results.append({
            "name": name,
            "needed": needed,
            "owned": owned,
            "used": used,
            "available": available,
            "flag": flag,
            "used_in": used_in,
        })
    
    return results

def print_report(results):
    """Prints one line per result (flag, name, need/own/used/available)
    plus an indented sub-line for each deck it's used in."""
    for r in results:
        print(f"[{r['flag']:8}] {r['name']:35} "
              f"need {r['needed']}  own {r['owned']}  "
              f"used {r['used']}  available {r['available']}")
        for d in r["used_in"]:
            print(f"            └─ {d['quantity']}x in {d['name']}")


def save_results(results, path="files/availability_report.json"):
    """Writes `results` (as returned by check_availability) to a JSON file."""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    app = MTGApp("Solmejk")

    # Make sure every deck has its cards loaded (uses cache)
    for deck in app.decks:
        deck.load()

    deck_text = sys.stdin.read()
    results = check_availability(app, deck_text)
    print_report(results)