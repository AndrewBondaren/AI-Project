"""World bundle import/export levels — WP-24."""

from __future__ import annotations

from typing import Literal

ImportLevel = Literal["registry", "skeleton"]

SKELETON_SECTIONS: frozenset[str] = frozenset({
    "world",
    "races",
    "perks",
    "states",
    "locations",
    "connection_nodes",
    "connection_edges",
})

REGISTRY_SECTIONS: frozenset[str] = frozenset({"world"})


def sections_for_level(level: ImportLevel) -> frozenset[str]:
    if level == "registry":
        return REGISTRY_SECTIONS
    return SKELETON_SECTIONS


def filter_bundle_for_export(bundle: dict, level: ImportLevel) -> dict:
    allowed = sections_for_level(level)
    return {key: value for key, value in bundle.items() if key in allowed}


def validate_bundle_for_import(data: dict, level: ImportLevel) -> None:
    allowed = sections_for_level(level)
    unknown = set(data.keys()) - allowed
    if unknown:
        raise ValueError(
            f"Bundle sections {sorted(unknown)} not allowed for import level '{level}'",
        )
