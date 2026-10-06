"""Deterministic uid for generated connection nodes — DET-1 plan step 6.

Graph nodes are minted by (graph level, node type, world-fine coords):
the coords are absolute, so the same physical node produced by two
generation paths folds onto the same uid. ``tag``/``parent`` disambiguate
role variants at the same coords (area paths, alleys).
"""

from __future__ import annotations

from typing import Any

from app.application.worldData.ids import UidKind, entity_uid
from app.dataModel.connections.enums.connectionNodeType import ConnectionNodeType
from app.dataModel.connections.enums.graphLevel import GraphLevel


def connection_node_uid(
    world_uid: str,
    *,
    level: GraphLevel | str,
    node_type: ConnectionNodeType | str,
    x: int,
    y: int,
    z: int,
    tag: str | None = None,
    parent: str | None = None,
) -> str:
    keys: dict[str, Any] = {
        "level": GraphLevel(level),
        "type": ConnectionNodeType(node_type),
        "x": x,
        "y": y,
        "z": z,
    }
    if tag is not None:
        keys["tag"] = tag
    if parent is not None:
        keys["parent"] = parent
    return entity_uid(world_uid, UidKind.CONN_NODE, **keys)
