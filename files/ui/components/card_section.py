"""Shared "grouped card grid" builder used by DeckDetailScreen and
AvailabilityScreen: both group a list of cards by type (via
ui.card_type.group_cards) and lay each group out as a header + a
FlowLayout of ImageTiles. This module owns that common structure; the two
screens only supply what differs between them (caption text, optional
per-card tint color).
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

import scryfall
from ui.card_type import group_cards
from ui.flow_layout import FlowLayout
from ui.components.image_tile import ImageTile
from ui.layout_utils import clear_layout


TILE_WIDTH = 140
TILE_HEIGHT = 196


def quantity_caption(card: dict) -> str:
    """Formats a tile caption as "<name>", or "<qty>x <name>" when more
    than one copy — the base caption both DeckDetailScreen and
    AvailabilityScreen use (the latter appends a price suffix on top)."""
    quantity = card.get("quantity", 1)
    return f"{quantity}x {card['name']}" if quantity > 1 else card["name"]


def build_card_section(name: str, count: int, cards: list[dict], caption_fn, on_click, color_fn=None) -> QWidget:
    """Builds one section: a "<name> (<count>)" header above a wrapping
    grid of card tiles.

    name: bucket label (e.g. "Creature", "Commander").
    count: total copies in this bucket, shown in the header.
    cards: card dicts belonging to this bucket.
    caption_fn(card) -> str: text shown under each tile.
    on_click: slot connected to each tile's clicked signal (receives the
    card dict as payload).
    color_fn(card) -> QColor | None: optional per-card tint overlay (the
    availability screen's status color); omit for a plain grid.

    Returns the assembled section widget, not yet attached to a layout.
    """
    section = QWidget()
    layout = QVBoxLayout(section)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)

    header_label = QLabel(f"{name} ({count})")
    header_label.setObjectName("deckSectionHeader")
    layout.addWidget(header_label)

    grid_container = QWidget()
    flow = FlowLayout(grid_container, margin=0, spacing=16)

    for card in cards:
        tile = ImageTile(
            image_url=card.get("image_url", ""),
            cache_name=scryfall.card_image_cache_name(card),
            caption=caption_fn(card),
            payload=card,
            width=TILE_WIDTH,
            height=TILE_HEIGHT,
            radius=14,
            status_color=color_fn(card) if color_fn else None,
        )
        tile.clicked.connect(on_click)
        flow.addWidget(tile)
        tile.request_image_load()

    layout.addWidget(grid_container)
    return section


def rebuild_card_sections(
    sections_layout, cards: list[dict], commander_names: set,
    caption_fn, on_click, color_fn=None, sort_fn=None,
):
    """Clears `sections_layout` and rebuilds it: groups `cards` by type
    (commanders pulled out first via `commander_names`), then adds one
    build_card_section() per non-empty bucket, in ui.card_type.TYPE_ORDER.

    sort_fn(cards) -> cards: optional per-bucket sort (e.g. by price)
    applied before building each section; omit to keep the deck's
    original order. See build_card_section() for the other parameters.
    """
    clear_layout(sections_layout)

    groups = group_cards(cards, commander_names)
    for bucket_name, bucket_cards in groups.items():
        if sort_fn:
            bucket_cards = sort_fn(bucket_cards)
        total = sum(c["quantity"] for c in bucket_cards)
        section = build_card_section(bucket_name, total, bucket_cards, caption_fn, on_click, color_fn)
        sections_layout.addWidget(section)
