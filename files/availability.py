"""Cross-references a decklist against the user's collection and existing
active decks: how many of each card are owned, how many are already tied
up elsewhere, and how many are actually free to use."""

import scryfall

FREE = "free"
USED = "used"
UNOWNED = "unowned"

# Basics are always trivially available and cheap — not worth pricing.
# (Also sidesteps a real issue: batched Scryfall lookups sort by price
# across the whole query, and a basic's 800+ printings would flood page 1
# and crowd out other cards' cheapest entries if batched together.)
BASIC_LAND_NAMES = {"plains", "island", "swamp", "mountain", "forest", "wastes"}


def count_in_collection(collection, card_name: str) -> int:
    target = card_name.lower()
    return sum(
        entry["quantity"] for entry in collection.cards
        if entry["card"]["name"].lower() == target
    )


def count_in_other_decks(decks, card_name: str) -> int:
    target = card_name.lower()
    total = 0
    for deck in decks:
        if not deck.active:  # archived decks don't tie up cards
            continue
        for card in deck.cards:
            if card["name"].lower() == target:
                total += card["quantity"]
    return total


def owned_printings(collection, card_name: str) -> list[dict]:
    """Which specific printings are owned, and how many of each."""
    target = card_name.lower()
    return [
        {
            "set": entry["card"].get("set", ""),
            "cn": entry["card"].get("cn", ""),
            "quantity": entry["quantity"],
        }
        for entry in collection.cards
        if entry["card"]["name"].lower() == target
    ]


def used_in_decks(decks, card_name: str) -> list[dict]:
    """Which active decks use this card, and how many copies each."""
    target = card_name.lower()
    used = []
    for deck in decks:
        if not deck.active:
            continue
        quantity = sum(c["quantity"] for c in deck.cards if c["name"].lower() == target)
        if quantity > 0:
            used.append({"deck_name": deck.name, "quantity": quantity})
    return used


def check_availability(app, checked_cards: list[dict]) -> list[dict]:
    """checked_cards: card dicts as produced by Deck (name/quantity/...).
    Returns each card augmented with owned/used/available/missing/status/
    missing_cost/cheapest_set/owned_printings/used_in_decks, where status
    is FREE (enough free copies), USED (owned but not enough free copies —
    some/all tied up in other active decks), or UNOWNED. missing_cost is
    the cheapest-printing price (via Scryfall) of buying the missing
    copies, and cheapest_set is which set that printing is from — the
    checked decklist's own printing may not be the cheapest one available.
    owned_printings/used_in_decks are the per-printing/per-deck breakdowns
    behind the owned/used totals, for display purposes."""
    computed = []
    for card in checked_cards:
        name = card["name"]
        needed = card.get("quantity", 1)
        owned = count_in_collection(app.collection, name)
        used = count_in_other_decks(app.decks, name)
        available = max(0, owned - used)
        missing = max(0, needed - available)

        if owned == 0:
            status = UNOWNED
        elif available >= needed:
            status = FREE
        else:
            status = USED

        computed.append((card, owned, used, available, missing, status))

    # Batched into a handful of Scryfall requests (many names per query)
    # rather than one request per card — a deck with 70+ missing cards
    # firing 70+ individual requests tripped Scryfall's rate limit.
    names_needing_price = [
        c[0]["name"] for c in computed
        if c[4] > 0 and c[0]["name"].lower() not in BASIC_LAND_NAMES
    ]
    price_info = scryfall.cheapest_prices_eur(names_needing_price) if names_needing_price else {}

    results = []
    for card, owned, used, available, missing, status in computed:
        cheapest_set = card.get("set", "")  # fall back to the decklist's own printing
        if missing > 0 and card["name"].lower() not in BASIC_LAND_NAMES:
            info = price_info.get(card["name"])
            if info is not None:
                price = info["price"]
                cheapest_set = info["set"]
            else:  # lookup failed — fall back to the decklist's own price
                price = card.get("price") or 0
        else:
            price = 0

        results.append({
            **card,
            "owned": owned,
            "used": used,
            "available": available,
            "missing": missing,
            "missing_cost": missing * price,
            "status": status,
            "owned_printings": owned_printings(app.collection, card["name"]),
            "used_in_decks": used_in_decks(app.decks, card["name"]),
            "cheapest_set": cheapest_set,
        })
    return results
