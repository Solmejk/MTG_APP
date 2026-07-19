"""Card type bucketing for deck detail view."""


TYPE_ORDER = [
    "Commander",
    "Creature",
    "Planeswalker",
    "Battle",
    "Instant",
    "Sorcery",
    "Enchantment",
    "Artifact",
    "Land",
    "Other",
]


def categorize(type_line: str) -> str:
    """Return one of the buckets in TYPE_ORDER, based on the type_line string."""
    tl = type_line.lower()
    # Order matters: a "Legendary Enchantment Creature" goes to Creature
    for bucket in ["Creature", "Planeswalker", "Battle",
                   "Instant", "Sorcery", "Enchantment", "Artifact", "Land"]:
        if bucket.lower() in tl:
            return bucket
    return "Other"


def group_cards(cards: list[dict], commander_names: set[str]) -> dict[str, list[dict]]:
    """
    Group cards by type. Commanders go in their own bucket.
    Returns dict {bucket_name: [cards]}, preserving TYPE_ORDER.
    """
    buckets = {name: [] for name in TYPE_ORDER}
    
    for card in cards:
        if card["name"] in commander_names:
            buckets["Commander"].append(card)
        else:
            buckets[categorize(card.get("type_line", ""))].append(card)
    
    # Drop empty buckets, preserve order
    return {k: v for k, v in buckets.items() if v}