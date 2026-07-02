"""SCH-CONNECTION-EDGE-ROW — docs/tz_json_validation.md JV-2."""

from __future__ import annotations

from typing import Any

from app.application.worldData.generators.registries.wireEnums import (
    BridgeSubtype,
    GraphLevel,
    SidewalkSide,
)
from app.application.worldData.jsonValidation.index.refKind import RefKind
from app.application.worldData.jsonValidation.types import SectionKey, ValidationContext, ValidationIssue
from app.application.worldData.jsonValidation.validators._issues import error
from app.application.worldData.jsonValidation.validators._rowHelpers import (
    check_fk,
    check_ref,
    check_wire_enum,
    collect_duplicate_uids,
)

SCHEMA_ID = "SCH-CONNECTION-EDGE-ROW"


class ConnectionEdgeRowValidator:
    schema_id = SCHEMA_ID
    sections = frozenset({SectionKey.CONNECTION_EDGES})

    def validate(self, ctx: ValidationContext) -> None:
        if ctx.has_errors or ctx.index is None:
            return
        bundle = _bundle(ctx)
        if bundle is None:
            return
        edges = bundle.get("connection_edges")
        if not isinstance(edges, list):
            return
        node_uids = _node_uids(bundle)
        edge_uids = {
            row["edge_uid"]
            for row in edges
            if isinstance(row, dict) and isinstance(row.get("edge_uid"), str)
        }
        ctx.issues.extend(collect_edge_issues(edges, node_uids, edge_uids, ctx.index))


def _bundle(ctx: ValidationContext) -> dict[str, Any] | None:
    blob = ctx.normalized if isinstance(ctx.normalized, dict) else ctx.bundle
    return blob if isinstance(blob, dict) else None


def _node_uids(bundle: dict[str, Any]) -> set[str]:
    nodes = bundle.get("connection_nodes")
    if not isinstance(nodes, list):
        return set()
    return {
        row["node_uid"]
        for row in nodes
        if isinstance(row, dict) and isinstance(row.get("node_uid"), str)
    }


def collect_edge_issues(
    edges: list[Any],
    node_uids: set[str],
    edge_uids: set[str],
    index,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    issues.extend(collect_duplicate_uids(edges, "edge_uid", "connection_edges", SCHEMA_ID))

    for i, row in enumerate(edges):
        if not isinstance(row, dict):
            issues.append(error(
                SCHEMA_ID, f"connection_edges[{i}]", "INVALID_ROW", "edge row must be an object",
            ))
            continue
        base = f"connection_edges[{i}]"
        if not isinstance(row.get("edge_uid"), str):
            continue

        conn_type = row.get("connection_type")
        issues.extend(check_ref(
            index, RefKind.CONN, conn_type, f"{base}.connection_type",
            SCHEMA_ID, field_name="connection_type",
        ))
        issues.extend(check_wire_enum(
            GraphLevel, row.get("graph_level"), f"{base}.graph_level", SCHEMA_ID, field_name="graph_level",
        ))
        issues.extend(check_fk(
            row.get("from_node_uid"), node_uids, f"{base}.from_node_uid",
            SCHEMA_ID, field_name="from_node_uid",
        ))
        issues.extend(check_fk(
            row.get("to_node_uid"), node_uids, f"{base}.to_node_uid",
            SCHEMA_ID, field_name="to_node_uid",
        ))
        issues.extend(check_ref(
            index, RefKind.MATERIAL, row.get("material"), f"{base}.material",
            SCHEMA_ID, field_name="material",
        ))
        issues.extend(check_ref(
            index, RefKind.DANGER, row.get("danger_level"), f"{base}.danger_level",
            SCHEMA_ID, field_name="danger_level",
        ))
        issues.extend(check_fk(
            row.get("parent_edge_uid"), edge_uids, f"{base}.parent_edge_uid",
            SCHEMA_ID, field_name="parent_edge_uid",
        ))

        if conn_type == "bridge":
            issues.extend(check_wire_enum(
                BridgeSubtype, row.get("bridge_subtype"), f"{base}.bridge_subtype", SCHEMA_ID,
                field_name="bridge_subtype",
            ))
        elif row.get("bridge_subtype") is not None:
            issues.append(error(
                SCHEMA_ID, f"{base}.bridge_subtype", "INVALID_FIELD",
                "bridge_subtype is only allowed when connection_type is bridge",
            ))

        if conn_type == "sidewalk":
            issues.extend(check_wire_enum(
                SidewalkSide, row.get("side"), f"{base}.side", SCHEMA_ID, field_name="side",
            ))
        elif row.get("side") is not None:
            issues.append(error(
                SCHEMA_ID, f"{base}.side", "INVALID_FIELD",
                "side is only allowed when connection_type is sidewalk",
            ))

        if row.get("location_uid") is not None:
            issues.append(error(
                SCHEMA_ID, f"{base}.location_uid", "STRIP_FIELD",
                "connection_edges must not contain location_uid (strip on import)",
            ))

        width = row.get("width_cells")
        if width is not None and (not isinstance(width, int) or isinstance(width, bool) or width < 1):
            issues.append(error(
                SCHEMA_ID, f"{base}.width_cells", "OUT_OF_RANGE", "width_cells must be an integer >= 1",
            ))

        lanes = row.get("lanes_per_side", 1)
        if not isinstance(lanes, int) or isinstance(lanes, bool) or lanes < 1:
            issues.append(error(
                SCHEMA_ID, f"{base}.lanes_per_side", "OUT_OF_RANGE",
                "lanes_per_side must be an integer >= 1",
            ))

    return issues
