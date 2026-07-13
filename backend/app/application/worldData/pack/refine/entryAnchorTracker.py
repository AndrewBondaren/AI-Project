"""WP-13 entry anchors for chunk refine ordering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.dataModel.worldPack.pathHeadingPolicy import PathHeadingPolicy

AnchorKind = Literal["session_start", "tile_cross", "location_entry"]

ANCHOR_KINDS: tuple[AnchorKind, ...] = ("session_start", "tile_cross", "location_entry")


def parse_anchor_kind(value: str) -> AnchorKind:
    """Wire/query string → typed anchor kind (raises ValueError if unknown)."""
    for kind in ANCHOR_KINDS:
        if value == kind:
            return kind
    raise ValueError(
        f"Unknown anchor kind {value!r}; expected one of {list(ANCHOR_KINDS)}"
    )


@dataclass
class EntryAnchor:
    kind: AnchorKind
    entry_x: int
    entry_y: int
    tile_gx: int | None = None
    tile_gy: int | None = None
    location_uid: str | None = None


class EntryAnchorTracker:
    def __init__(self) -> None:
        self._anchors: list[EntryAnchor] = []
        self._current: EntryAnchor | None = None
        self._positions: list[tuple[int, int]] = []

    def record_position(self, x: int, y: int) -> None:
        if self._positions and self._positions[-1] == (x, y):
            return
        self._positions.append((x, y))
        max_samples = PathHeadingPolicy.canonical_defaults().position_history_max
        if len(self._positions) > max_samples:
            self._positions.pop(0)

    def position_history(self) -> list[tuple[int, int]]:
        return list(self._positions)

    def set_anchor(
        self,
        kind: AnchorKind,
        entry_x: int,
        entry_y: int,
        *,
        tile_gx: int | None = None,
        tile_gy: int | None = None,
        location_uid: str | None = None,
    ) -> EntryAnchor:
        self.record_position(entry_x, entry_y)
        anchor = EntryAnchor(
            kind=kind,
            entry_x=entry_x,
            entry_y=entry_y,
            tile_gx=tile_gx,
            tile_gy=tile_gy,
            location_uid=location_uid,
        )
        self._anchors.append(anchor)
        self._current = anchor
        return anchor

    @property
    def current(self) -> EntryAnchor | None:
        return self._current

    def history(self) -> list[EntryAnchor]:
        return list(self._anchors)
