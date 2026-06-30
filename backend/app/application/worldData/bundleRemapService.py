"""Duplicate-import UID remapping for world bundles — BUNDLE-1 variant A (section registry)."""

from __future__ import annotations

import copy
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UidCollectSpec:
    """Register primary (and referenced) UIDs before deepcopy apply."""

    section_key: str
    pk_field: str
    extra_uid_fields: tuple[str, ...] = ()


UID_COLLECT_REGISTRY: tuple[UidCollectSpec, ...] = (
    UidCollectSpec("locations", "location_uid"),
    UidCollectSpec("states", "state_uid"),
    UidCollectSpec("races", "race_uid"),
    UidCollectSpec("perks", "perk_uid"),
    UidCollectSpec("connection_nodes", "node_uid"),
    UidCollectSpec(
        "connection_edges", "edge_uid", ("from_node_uid", "to_node_uid"),
    ),
)

ApplyItemFn = Callable[[dict[str, Any], dict[str, str], str], None]


def _remap_ref(item: dict[str, Any], uid_map: dict[str, str], field: str) -> None:
    ref = item.get(field)
    if ref in uid_map:
        item[field] = uid_map[ref]


def _apply_pk_world(
    item: dict[str, Any], uid_map: dict[str, str], new_world_uid: str, pk: str,
) -> None:
    item[pk] = uid_map[item[pk]]
    item["world_uid"] = new_world_uid


def _apply_location(
    item: dict[str, Any], uid_map: dict[str, str], new_world_uid: str,
) -> None:
    _apply_pk_world(item, uid_map, new_world_uid, "location_uid")
    _remap_ref(item, uid_map, "parent_location_uid")
    _remap_ref(item, uid_map, "state_uid")


def _apply_connection_node(
    item: dict[str, Any], uid_map: dict[str, str], new_world_uid: str,
) -> None:
    _apply_pk_world(item, uid_map, new_world_uid, "node_uid")
    _remap_ref(item, uid_map, "location_uid")


def _apply_connection_edge(
    item: dict[str, Any], uid_map: dict[str, str], new_world_uid: str,
) -> None:
    item["edge_uid"] = uid_map[item["edge_uid"]]
    item["from_node_uid"] = uid_map[item["from_node_uid"]]
    item["to_node_uid"] = uid_map[item["to_node_uid"]]
    item["world_uid"] = new_world_uid
    item.pop("location_uid", None)


def _apply_map_cell(
    item: dict[str, Any], uid_map: dict[str, str], new_world_uid: str,
) -> None:
    item["world_uid"] = new_world_uid
    _remap_ref(item, uid_map, "location_uid")


APPLY_ITEM_REGISTRY: dict[str, ApplyItemFn] = {
    "locations":         _apply_location,
    "states":            lambda i, m, w: _apply_pk_world(i, m, w, "state_uid"),
    "races":             lambda i, m, w: _apply_pk_world(i, m, w, "race_uid"),
    "perks":             lambda i, m, w: _apply_pk_world(i, m, w, "perk_uid"),
    "connection_nodes":  _apply_connection_node,
    "connection_edges":  _apply_connection_edge,
}


def remap_bundle(
    data: dict[str, Any],
    version_n: int,
    strip_suffix: Callable[[str], str],
) -> dict[str, Any]:
    """Return a deep copy of the bundle with all UIDs replaced and name versioned."""
    uid_map = _build_uid_map(data)
    result = copy.deepcopy(data)
    original_world_uid = data["world"]["world_uid"]
    new_world_uid = uid_map[original_world_uid]

    world = result["world"]
    world["world_uid"] = new_world_uid
    world["name"] = f"{strip_suffix(world.get('name', ''))} v{version_n}"

    for spec in UID_COLLECT_REGISTRY:
        apply_fn = APPLY_ITEM_REGISTRY[spec.section_key]
        for item in result.get(spec.section_key, []):
            apply_fn(item, uid_map, new_world_uid)

    for cell in result.get("map_cells", []):
        _apply_map_cell(cell, uid_map, new_world_uid)

    return result


def _build_uid_map(data: dict[str, Any]) -> dict[str, str]:
    uid_map: dict[str, str] = {}

    def register(old: str) -> str:
        if old not in uid_map:
            uid_map[old] = str(uuid.uuid4())
        return uid_map[old]

    register(data["world"]["world_uid"])
    for spec in UID_COLLECT_REGISTRY:
        for item in data.get(spec.section_key, []):
            register(item[spec.pk_field])
            for field in spec.extra_uid_fields:
                register(item[field])

    return uid_map
