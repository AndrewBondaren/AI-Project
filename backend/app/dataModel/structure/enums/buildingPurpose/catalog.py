"""Assemble BuildingPurpose from family leaf files + match/coerce helpers.

tz_building_generator.md §2.1. Drawing tags are leaves only. Families are catalog metadata.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from typing import Union

from . import agrarian as _agrarian
from . import craft as _craft
from . import defense as _defense
from . import diplomatic as _diplomatic
from . import dwelling as _dwelling
from . import extract as _extract
from . import factory as _factory
from . import government as _government
from . import harbor as _harbor
from . import knowledge as _knowledge
from . import process as _process
from . import public as _public
from . import trade as _trade
from . import transit as _transit
from . import utility as _utility
from .family import BuildingPurposeFamily
from .packs import PurposePack, coerce_purpose_packs

_FAMILY_LEAVES: tuple[tuple[BuildingPurposeFamily, tuple[tuple[str, str], ...]], ...] = (
    (BuildingPurposeFamily.DWELLING, _dwelling.LEAVES),
    (BuildingPurposeFamily.PUBLIC, _public.LEAVES),
    (BuildingPurposeFamily.GOVERNMENT, _government.LEAVES),
    (BuildingPurposeFamily.KNOWLEDGE, _knowledge.LEAVES),
    (BuildingPurposeFamily.DIPLOMATIC, _diplomatic.LEAVES),
    (BuildingPurposeFamily.TRADE, _trade.LEAVES),
    (BuildingPurposeFamily.CRAFT, _craft.LEAVES),
    (BuildingPurposeFamily.FACTORY, _factory.LEAVES),
    (BuildingPurposeFamily.EXTRACT, _extract.LEAVES),
    (BuildingPurposeFamily.PROCESS, _process.LEAVES),
    (BuildingPurposeFamily.AGRARIAN, _agrarian.LEAVES),
    (BuildingPurposeFamily.UTILITY, _utility.LEAVES),
    (BuildingPurposeFamily.DEFENSE, _defense.LEAVES),
    (BuildingPurposeFamily.HARBOR, _harbor.LEAVES),
    (BuildingPurposeFamily.TRANSIT, _transit.LEAVES),
)


def _enum_members() -> dict[str, str]:
    members: dict[str, str] = {}
    for _family, leaves in _FAMILY_LEAVES:
        for key, _display in leaves:
            members[key.upper()] = key
    return members


_LEAF_VALUES = {key for key in _enum_members().values()}
_FAMILY_VALUES = {member.value for member in BuildingPurposeFamily}
if _LEAF_VALUES & _FAMILY_VALUES:
    raise RuntimeError(
        "BuildingPurpose leaf keys collide with BuildingPurposeFamily: "
        f"{sorted(_LEAF_VALUES & _FAMILY_VALUES)}"
    )

BuildingPurpose = StrEnum("BuildingPurpose", _enum_members())  # type: ignore[misc]


def _purpose_from_wire(key: object) -> BuildingPurpose | None:
    if key is None:
        return None
    if isinstance(key, BuildingPurpose):
        return key
    norm = str(key).strip().lower()
    if not norm:
        return None
    return BuildingPurpose._value2member_map_.get(norm)


@classmethod  # type: ignore[misc]
def _building_purpose_from_wire(cls, key: object) -> BuildingPurpose | None:
    return _purpose_from_wire(key)


BuildingPurpose.from_wire = _building_purpose_from_wire  # type: ignore[method-assign, assignment]


class BuildingPurposeMatch(StrEnum):
    """How a plot purpose array is tested against a filter (district allowed / need)."""

    LIKE = "like"
    STRICT = "strict"

    @classmethod
    def from_wire(cls, key: object) -> BuildingPurposeMatch | None:
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


AllowedToken = Union[BuildingPurpose, BuildingPurposeFamily]

HOUSE = BuildingPurpose.HOUSE
DEFAULT_BUILDING_PURPOSES: tuple[BuildingPurpose, ...] = (HOUSE,)
DEFAULT_PURPOSE_MATCH = BuildingPurposeMatch.LIKE

FAMILY_OF: dict[BuildingPurpose, BuildingPurposeFamily] = {}
PURPOSE_DISPLAY: dict[BuildingPurpose, str] = {}
for _family, _leaves in _FAMILY_LEAVES:
    for _key, _display in _leaves:
        _leaf = BuildingPurpose(_key)
        FAMILY_OF[_leaf] = _family
        PURPOSE_DISPLAY[_leaf] = _display

_CHILDREN: dict[BuildingPurposeFamily, tuple[BuildingPurpose, ...]] = {}
for _leaf, _fam in FAMILY_OF.items():
    _CHILDREN[_fam] = _CHILDREN.get(_fam, ()) + (_leaf,)


def children_of(family: BuildingPurposeFamily) -> tuple[BuildingPurpose, ...]:
    return _CHILDREN.get(family, ())


def _as_family(token: object) -> BuildingPurposeFamily | None:
    if isinstance(token, BuildingPurpose):
        return None
    if isinstance(token, BuildingPurposeFamily):
        return token
    return BuildingPurposeFamily.from_wire(token)


def expand_allowed(tokens: Iterable[AllowedToken | str]) -> list[BuildingPurpose]:
    """Family → all children; leaf stays. Unknown dropped. Order preserved."""
    out: list[BuildingPurpose] = []
    seen: set[BuildingPurpose] = set()
    for token in tokens:
        family = _as_family(token)
        if family is not None:
            for leaf in children_of(family):
                if leaf not in seen:
                    seen.add(leaf)
                    out.append(leaf)
            continue
        purpose = (
            token
            if isinstance(token, BuildingPurpose)
            else BuildingPurpose.from_wire(token)
        )
        if purpose is None or purpose in seen:
            continue
        seen.add(purpose)
        out.append(purpose)
    return out


def coerce_purpose_list(
    raw: object,
    *,
    empty_as_house: bool = True,
) -> list[BuildingPurpose]:
    """Wire → unique **leaves**. Family names dropped. Drawing omit → ``[house]``."""
    if raw is None:
        return list(DEFAULT_BUILDING_PURPOSES) if empty_as_house else []
    if isinstance(raw, BuildingPurpose):
        return [raw]
    if isinstance(raw, BuildingPurposeFamily) or _as_family(raw) is not None:
        return list(DEFAULT_BUILDING_PURPOSES) if empty_as_house else []
    items: list[object]
    if isinstance(raw, str):
        items = [raw]
    elif isinstance(raw, (list, tuple)):
        items = list(raw)
    else:
        return list(DEFAULT_BUILDING_PURPOSES) if empty_as_house else []
    out: list[BuildingPurpose] = []
    seen: set[BuildingPurpose] = set()
    for item in items:
        if isinstance(item, BuildingPurposeFamily) or (
            not isinstance(item, BuildingPurpose) and _as_family(item) is not None
        ):
            continue
        purpose = BuildingPurpose.from_wire(item)
        if purpose is None or purpose in seen:
            continue
        seen.add(purpose)
        out.append(purpose)
    if not out and empty_as_house:
        return list(DEFAULT_BUILDING_PURPOSES)
    return out


def coerce_allowed_list(raw: object) -> list[AllowedToken]:
    """District ``allowed_structure_types``: leaves and/or families. Empty stays empty."""
    if raw is None:
        return []
    if isinstance(raw, (BuildingPurpose, BuildingPurposeFamily)):
        return [raw]
    items: list[object]
    if isinstance(raw, str):
        items = [raw]
    elif isinstance(raw, (list, tuple)):
        items = list(raw)
    else:
        return []
    out: list[AllowedToken] = []
    seen: set[str] = set()
    for item in items:
        family = _as_family(item)
        if family is not None:
            key = str(family)
            if key not in seen:
                seen.add(key)
                out.append(family)
            continue
        purpose = item if isinstance(item, BuildingPurpose) else BuildingPurpose.from_wire(item)
        if purpose is None:
            continue
        key = str(purpose)
        if key in seen:
            continue
        seen.add(key)
        out.append(purpose)
    return out


def coerce_purpose_match(raw: object) -> BuildingPurposeMatch:
    parsed = BuildingPurposeMatch.from_wire(raw)
    return parsed if parsed is not None else DEFAULT_PURPOSE_MATCH


def union_plot_purposes(
    buildings: Iterable[object],
) -> tuple[BuildingPurpose, ...]:
    """Union of ``structure_types`` on every building of a plot."""
    out: list[BuildingPurpose] = []
    seen: set[BuildingPurpose] = set()
    for building in buildings:
        types = getattr(building, "structure_types", None)
        if not types:
            raw = getattr(building, "structure_type", None)
            types = coerce_purpose_list(raw, empty_as_house=True)
        for purpose in types:
            parsed = purpose if isinstance(purpose, BuildingPurpose) else BuildingPurpose.from_wire(purpose)
            if parsed is None or parsed in seen:
                continue
            seen.add(parsed)
            out.append(parsed)
    return tuple(out) if out else DEFAULT_BUILDING_PURPOSES


def purposes_match(
    plot: Iterable[BuildingPurpose],
    filt: Iterable[AllowedToken | str],
    mode: BuildingPurposeMatch,
) -> bool:
    """``like`` = nonempty intersection. ``strict`` = plot ⊆ expanded filter."""
    plot_set = set(plot)
    filter_set = set(expand_allowed(filt))
    if not filter_set:
        return False
    if mode is BuildingPurposeMatch.STRICT:
        return bool(plot_set) and plot_set <= filter_set
    return bool(plot_set & filter_set)


def primary_purpose(types: Iterable[BuildingPurpose]) -> BuildingPurpose:
    for purpose in types:
        return purpose
    return HOUSE


def _pack_set(*keys: str) -> frozenset[BuildingPurpose]:
    return frozenset(BuildingPurpose(key) for key in keys)


def _family_set(family: BuildingPurposeFamily) -> frozenset[BuildingPurpose]:
    return frozenset(children_of(family))


_FANTASY_PUBLIC = _pack_set(
    "town_hall", "plaza", "temple", "shrine", "theater", "library",
    "bathhouse", "courthouse",
)
_FANTASY_TRADE = _pack_set(
    "shop", "market", "guild", "warehouse", "granary",
    "bakery", "butcher", "fishmonger", "greengrocer", "apothecary",
    "tailor", "cobbler", "jeweler", "bookseller", "tavern",
)
_MODERN_EXTRAS = _pack_set(
    "church", "hospital", "school",
    "cafe", "restaurant", "hypermarket",
    "embassy", "water_treatment",
    "academy", "laboratory",
)

PACK_PURPOSES: dict[PurposePack, frozenset[BuildingPurpose]] = {
    PurposePack.FANTASY: (
        _family_set(BuildingPurposeFamily.DWELLING)
        | _FANTASY_PUBLIC
        | _FANTASY_TRADE
        | _family_set(BuildingPurposeFamily.CRAFT)
        | _family_set(BuildingPurposeFamily.EXTRACT)
        | _family_set(BuildingPurposeFamily.PROCESS)
        | _family_set(BuildingPurposeFamily.AGRARIAN)
        | _family_set(BuildingPurposeFamily.GOVERNMENT)
        | _family_set(BuildingPurposeFamily.DEFENSE)
        | _family_set(BuildingPurposeFamily.HARBOR)
        | _pack_set("academy")
    ),
    PurposePack.MAGIC: _pack_set("portal", "temple", "shrine", "arcane_lab", "academy"),
    PurposePack.STEAMPUNK: (
        _family_set(BuildingPurposeFamily.CRAFT)
        | _pack_set("assembly_plant", "water_treatment", "laboratory")
    ),
    PurposePack.MODERN: _MODERN_EXTRAS,
    PurposePack.SCI_FI: _MODERN_EXTRAS | _pack_set("assembly_plant", "portal", "air_dock"),
}


def purposes_for_world(packs: Iterable[PurposePack | str] | None) -> frozenset[BuildingPurpose]:
    """Omit / empty → canon ``fantasy``. Mix = union. Unknown pack id dropped."""
    enabled: set[BuildingPurpose] = set()
    for pack in coerce_purpose_packs(packs):
        enabled |= PACK_PURPOSES[pack]
    return frozenset(enabled)
