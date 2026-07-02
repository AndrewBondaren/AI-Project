"""SCH-BUNDLE-DECLARE-TOPOLOGY — geographic declare cross-section rules (JV-2)."""

from __future__ import annotations

from typing import Any

from app.application.worldData.generators.registries.wireEnums import HydrologyConnectionType
from app.application.worldData.jsonValidation.types import SectionKey, ValidationContext, ValidationIssue
from app.application.worldData.jsonValidation.validators._issues import error

SCHEMA_ID = "SCH-BUNDLE-DECLARE-TOPOLOGY"

_LAKE_SUBTYPES = frozenset({"lake"})
_COAST_SUBTYPES = frozenset({"sea", "ocean", "inland_sea"})


class DeclareTopologyValidator:
    schema_id = SCHEMA_ID
    sections: frozenset[SectionKey] = frozenset()

    def validate(self, ctx: ValidationContext) -> None:
        if ctx.has_errors:
            return
        bundle = _bundle(ctx)
        if bundle is None:
            return
        ctx.issues.extend(collect_declare_topology_issues(bundle))


def _bundle(ctx: ValidationContext) -> dict[str, Any] | None:
    blob = ctx.normalized if isinstance(ctx.normalized, dict) else ctx.bundle
    return blob if isinstance(blob, dict) else None


def collect_declare_topology_issues(bundle: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    locations = bundle.get("locations")
    nodes = bundle.get("connection_nodes")
    edges = bundle.get("connection_edges")
    if not isinstance(locations, list):
        return issues

    node_by_uid = {
        row["node_uid"]: row
        for row in (nodes or [])
        if isinstance(row, dict) and isinstance(row.get("node_uid"), str)
    }
    edge_rows = [row for row in (edges or []) if isinstance(row, dict)]

    for i, loc in enumerate(locations):
        if not isinstance(loc, dict):
            continue
        if loc.get("system_location_type") != "geographic":
            continue
        subtype = loc.get("system_location_subtype")
        uid = loc.get("location_uid")
        if not isinstance(uid, str):
            continue
        base = f"locations[{i}]"

        if subtype in _LAKE_SUBTYPES:
            if not _has_declare_chain(
                uid, edge_rows, node_by_uid, HydrologyConnectionType.LAKE_SHORELINE.value,
            ):
                issues.append(error(
                    SCHEMA_ID, base, "MISSING_DECLARE",
                    f"geographic.lake {uid!r} requires lake_shoreline ConnectionEdge chain",
                ))
        elif subtype in _COAST_SUBTYPES:
            if not _has_declare_chain(
                uid, edge_rows, node_by_uid, HydrologyConnectionType.COASTLINE.value,
            ):
                issues.append(error(
                    SCHEMA_ID, base, "MISSING_DECLARE",
                    f"geographic.{subtype} {uid!r} requires coastline ConnectionEdge chain",
                ))

    return issues


def _has_declare_chain(
    location_uid: str,
    edges: list[dict[str, Any]],
    node_by_uid: dict[str, dict[str, Any]],
    connection_type: str,
) -> bool:
    linked_nodes = {
        uid for uid, node in node_by_uid.items()
        if node.get("location_uid") == location_uid
    }
    if not linked_nodes:
        return False
    for edge in edges:
        if edge.get("connection_type") != connection_type:
            continue
        from_uid = edge.get("from_node_uid")
        to_uid = edge.get("to_node_uid")
        if from_uid in linked_nodes or to_uid in linked_nodes:
            return True
    return False
