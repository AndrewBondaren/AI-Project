"""PurposePack — world setting masks. Mix = union of leaves. Not zip templates."""

from __future__ import annotations

import logging
from enum import StrEnum

logger = logging.getLogger(__name__)


class PurposePack(StrEnum):
    FANTASY = "fantasy"
    MAGIC = "magic"
    STEAMPUNK = "steampunk"
    MODERN = "modern"
    SCI_FI = "sci_fi"

    @classmethod
    def from_wire(cls, key: object) -> PurposePack | None:
        if key is None:
            return None
        if isinstance(key, cls):
            return key
        norm = str(key).strip().lower()
        if not norm:
            return None
        for member in cls:
            if member.value == norm:
                return member
        return None


def coerce_purpose_packs(raw: object) -> list[PurposePack]:
    """Omit / empty → ``[fantasy]``. Unknown ids dropped + warning."""
    if raw is None:
        return [PurposePack.FANTASY]
    if isinstance(raw, PurposePack):
        return [raw]
    items: list[object]
    if isinstance(raw, str):
        items = [raw]
    elif isinstance(raw, (list, tuple)):
        items = list(raw)
    else:
        return [PurposePack.FANTASY]
    out: list[PurposePack] = []
    seen: set[PurposePack] = set()
    for item in items:
        pack = PurposePack.from_wire(item)
        if pack is None:
            if item is not None and str(item).strip():
                logger.warning(
                    "Unknown purpose pack %r — dropped (not inventing leaves)",
                    item,
                )
            continue
        if pack in seen:
            continue
        seen.add(pack)
        out.append(pack)
    return out if out else [PurposePack.FANTASY]
