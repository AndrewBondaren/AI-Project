"""``connection_nodes`` / ``connection_edges`` bundle import rows — JV-0b."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

from app.application.jsonValidation.resolve import ResolveContext, ResolveMode, resolve_model
from app.application.jsonValidation.types import FieldPathError, ImportValidationError
from app.dataModel.annotationPolicy import DefaultOnWire, StrictEnumOnWire, StrictOnWire
from app.dataModel.connections.connectionType.worldConnectionTypeRegistry import (
    WorldConnectionTypeRegistry,
)
from app.dataModel.connections.enums.connectionNodeType import ConnectionNodeType
from app.dataModel.connections.enums.graphLevel import GraphLevel


class ConnectionNodeImportRow(BaseModel):
    """Wire row for ``connection_nodes`` — CONN-1 keeps ``node_type`` key."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    SCHEMA_ID: ClassVar[str] = "SCH-BUNDLE-CONN-NODE"

    node_uid: StrictOnWire[str]
    x: StrictOnWire[int]
    y: StrictOnWire[int]
    z: StrictOnWire[int]
    node_type: StrictEnumOnWire[ConnectionNodeType]
    graph_level: StrictEnumOnWire[GraphLevel]
    location_uid: DefaultOnWire[str | None] = None
    portal_type: DefaultOnWire[str | None] = None
    portal_destinations: DefaultOnWire[list[Any] | None] = None
    portal_bidirectional: DefaultOnWire[int | None] = None
    portal_is_active: DefaultOnWire[int | None] = None
    portal_blocked_behavior_override: DefaultOnWire[str | None] = None


class ConnectionEdgeImportRow(BaseModel):
    """Wire row for ``connection_edges`` — ``connection_type`` is N1-W (REF-W-CONN)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    SCHEMA_ID: ClassVar[str] = "SCH-BUNDLE-CONN-EDGE"

    edge_uid: StrictOnWire[str]
    from_node_uid: StrictOnWire[str]
    to_node_uid: StrictOnWire[str]
    connection_type: StrictOnWire[str]
    graph_level: StrictEnumOnWire[GraphLevel]
    bidirectional: DefaultOnWire[bool] = True
    lanes_per_side: DefaultOnWire[int] = 1
    width_cells: DefaultOnWire[int | None] = None
    bridge_subtype: DefaultOnWire[str | None] = None
    parent_edge_uid: DefaultOnWire[str | None] = None
    side: DefaultOnWire[str | None] = None
    material: DefaultOnWire[str | None] = None
    condition: DefaultOnWire[int] = 100
    features: DefaultOnWire[list[Any] | None] = None
    lighting_type: DefaultOnWire[str | None] = None
    danger_level: DefaultOnWire[str] = "none"
    has_sidewalk: DefaultOnWire[bool] = False
    under_construction: DefaultOnWire[bool] = False
    under_repair: DefaultOnWire[bool] = False
    street_objects: DefaultOnWire[list[Any] | None] = None
    traversal_conditions: DefaultOnWire[dict[str, Any] | None] = None


def _allowed_connection_types(world_wire: dict[str, Any]) -> set[str]:
    allowed = {
        entry.system_connection_type
        for entry in WorldConnectionTypeRegistry.canonical_engine().root
    }
    rows = world_wire.get("connection_type_registry")
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict):
                key = row.get("system_connection_type")
                if key:
                    allowed.add(str(key))
    return allowed


def _normalize_rows(
    rows: Any,
    *,
    entry_cls: type[BaseModel],
    schema_id: str,
    section: str,
    ctx: ResolveContext,
) -> list[dict[str, Any]]:
    if not rows:
        return []
    if not isinstance(rows, list):
        ctx.errors.append(FieldPathError(
            path=(section,),
            message="expected list",
            schema_id=schema_id,
            code="EXPECTED_LIST",
        ))
        return []

    out: list[dict[str, Any]] = []
    for index, item in enumerate(rows):
        if not isinstance(item, dict):
            ctx.errors.append(FieldPathError(
                path=(section, index),
                message="expected object",
                schema_id=schema_id,
                code="EXPECTED_OBJECT",
            ))
            continue
        before_errors = len(ctx.errors)
        row_ctx = ResolveContext(
            mode=ctx.mode,
            partial=ctx.partial,
            path_prefix=(section, index),
            errors=ctx.errors,
            schema_id=schema_id,
        )
        resolved = resolve_model(
            entry_cls,
            item,
            label=f"{section}[{index}]",
            ctx=row_ctx,
        )
        if len(ctx.errors) > before_errors:
            continue
        out.append(resolved.model_dump(mode="json"))
    return out


def normalize_connection_nodes(
    rows: list[dict[str, Any]],
    *,
    ctx: ResolveContext,
) -> list[dict[str, Any]]:
    return _normalize_rows(
        rows,
        entry_cls=ConnectionNodeImportRow,
        schema_id=ConnectionNodeImportRow.SCHEMA_ID,
        section="connection_nodes",
        ctx=ctx,
    )


def normalize_connection_edges(
    rows: list[dict[str, Any]],
    *,
    world_wire: dict[str, Any],
    ctx: ResolveContext,
) -> list[dict[str, Any]]:
    allowed = _allowed_connection_types(world_wire)
    if not rows:
        return []
    if not isinstance(rows, list):
        ctx.errors.append(FieldPathError(
            path=("connection_edges",),
            message="expected list",
            schema_id=ConnectionEdgeImportRow.SCHEMA_ID,
            code="EXPECTED_LIST",
        ))
        return []

    out: list[dict[str, Any]] = []
    for index, item in enumerate(rows):
        if not isinstance(item, dict):
            ctx.errors.append(FieldPathError(
                path=("connection_edges", index),
                message="expected object",
                schema_id=ConnectionEdgeImportRow.SCHEMA_ID,
                code="EXPECTED_OBJECT",
            ))
            continue
        before_errors = len(ctx.errors)
        row_ctx = ResolveContext(
            mode=ctx.mode,
            partial=ctx.partial,
            path_prefix=("connection_edges", index),
            errors=ctx.errors,
            schema_id=ConnectionEdgeImportRow.SCHEMA_ID,
        )
        resolved = resolve_model(
            ConnectionEdgeImportRow,
            item,
            label=f"connection_edges[{index}]",
            ctx=row_ctx,
        )
        if len(ctx.errors) > before_errors:
            continue
        conn_type = resolved.connection_type
        if conn_type not in allowed:
            ctx.errors.append(FieldPathError(
                path=("connection_edges", index, "connection_type"),
                message=f"unknown REF-W-CONN target: {conn_type!r}",
                schema_id=ConnectionEdgeImportRow.SCHEMA_ID,
                code="REF_W_UNKNOWN",
            ))
            continue
        out.append(resolved.model_dump(mode="json"))
    return out


def normalize_bundle_connections(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize bundle connection graph sections after ``normalize_world``."""
    out = dict(data)
    errors: list[FieldPathError] = []
    ctx = ResolveContext(mode=ResolveMode.IMPORT, errors=errors)
    world_wire = out.get("world") if isinstance(out.get("world"), dict) else {}

    if "connection_nodes" in out:
        out["connection_nodes"] = normalize_connection_nodes(
            out["connection_nodes"],
            ctx=ctx,
        )
    if "connection_edges" in out:
        out["connection_edges"] = normalize_connection_edges(
            out["connection_edges"],
            world_wire=world_wire,
            ctx=ctx,
        )

    if errors:
        raise ImportValidationError(errors)
    return out
