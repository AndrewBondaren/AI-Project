"""PurposePack — builtin mask ids. World may add more ids; ``base`` is fabric."""

from __future__ import annotations

from enum import StrEnum


class PurposePack(StrEnum):
    """Named builtin pack ids. Enabled-list wire is not closed on this enum."""

    BASE = "base"
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


def normalize_pack_id(raw: object) -> str | None:
    """Strip + lower. Empty → None. Unknown ids stay (membership is registry)."""
    if raw is None:
        return None
    if isinstance(raw, PurposePack):
        return str(raw)
    token = str(raw).strip().lower()
    return token or None


def _with_base(packs: list[str]) -> list[str]:
    rest = [pack for pack in packs if pack != PurposePack.BASE]
    return [str(PurposePack.BASE), *rest]


def coerce_purpose_packs(raw: object) -> list[str]:
    """Omit / empty → ``[base, fantasy]``. ``base`` always first. Custom ids kept."""
    if raw is None:
        return _with_base([str(PurposePack.FANTASY)])
    if isinstance(raw, PurposePack):
        return _with_base([str(raw)])
    items: list[object]
    if isinstance(raw, str):
        items = [raw]
    elif isinstance(raw, (list, tuple)):
        items = list(raw)
    else:
        return _with_base([str(PurposePack.FANTASY)])
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        pack = normalize_pack_id(item)
        if pack is None:
            continue
        if pack in seen:
            continue
        seen.add(pack)
        out.append(pack)
    settings = [pack for pack in out if pack != PurposePack.BASE]
    if not settings and PurposePack.BASE not in seen:
        return _with_base([str(PurposePack.FANTASY)])
    return _with_base(out)
