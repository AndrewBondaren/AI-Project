"""SCH-CONNECTION-NODE-ROW — docs/tz_json_validation.md JV-2."""

from __future__ import annotations

from typing import Any

from app.application.worldData.generators.registries.wireEnums import (
    ConnectionNodeType,
    GraphLevel,
    PortalType,
)
from app.application.worldData.jsonValidation.types import SectionKey, ValidationContext, ValidationIssue
from app.application.worldData.jsonValidation.validators._issues import error
from app.application.worldData.jsonValidation.validators._rowHelpers import (
    check_fk,
    check_wire_enum,
    collect_duplicate_uids,
)

SCHEMA_ID = "SCH-CONNECTION-NODE-ROW"


class ConnectionNodeRowValidator:
    schema_id = SCHEMA_ID
    sections = frozenset({SectionKey.CONNECTION_NODES})

    def validate(self, ctx: ValidationContext) -> None:
        if ctx.has_errors:
            return
        bundle = _bundle(ctx)
        if bundle is None:
            return
        nodes = bundle.get("connection_nodes")
        if not isinstance(nodes, list):
            return
        location_uids = _location_uids(bundle)
        ctx.issues.extend(collect_node_issues(nodes, location_uids))


def _bundle(ctx: ValidationContext) -> dict[str, Any] | None:
    blob = ctx.normalized if isinstance(ctx.normalized, dict) else ctx.bundle
    return blob if isinstance(blob, dict) else None


def _location_uids(bundle: dict[str, Any]) -> set[str]:
    locations = bundle.get("locations")
    if not isinstance(locations, list):
        return set()
    return {
        row["location_uid"]
        for row in locations
        if isinstance(row, dict) and isinstance(row.get("location_uid"), str)
    }


def collect_node_issues(
    nodes: list[Any],
    location_uids: set[str],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    issues.extend(collect_duplicate_uids(nodes, "node_uid", "connection_nodes", SCHEMA_ID))

    for i, row in enumerate(nodes):
        if not isinstance(row, dict):
            issues.append(error(
                SCHEMA_ID, f"connection_nodes[{i}]", "INVALID_ROW", "node row must be an object",
            ))
            continue
        base = f"connection_nodes[{i}]"

        if not isinstance(row.get("node_uid"), str):
            continue

        for field in ("x", "y", "z"):
            val = row.get(field)
            if not isinstance(val, int) or isinstance(val, bool):
                issues.append(error(
                    SCHEMA_ID, f"{base}.{field}", "MISSING_FIELD",
                    f"{field} must be an integer",
                ))

        node_type = row.get("node_type")
        issues.extend(check_wire_enum(
            ConnectionNodeType, node_type, f"{base}.node_type", SCHEMA_ID, field_name="node_type",
        ))
        issues.extend(check_wire_enum(
            GraphLevel, row.get("graph_level"), f"{base}.graph_level", SCHEMA_ID, field_name="graph_level",
        ))
        issues.extend(check_fk(
            row.get("location_uid"), location_uids, f"{base}.location_uid",
            SCHEMA_ID, field_name="location_uid",
        ))

        if node_type == ConnectionNodeType.PORTAL.value:
            issues.extend(check_wire_enum(
                PortalType, row.get("portal_type"), f"{base}.portal_type", SCHEMA_ID,
                field_name="portal_type",
            ))
            if row.get("portal_destinations") is None:
                issues.append(error(
                    SCHEMA_ID, f"{base}.portal_destinations", "MISSING_FIELD",
                    "portal_destinations is required for portal nodes",
                ))

    return issues
