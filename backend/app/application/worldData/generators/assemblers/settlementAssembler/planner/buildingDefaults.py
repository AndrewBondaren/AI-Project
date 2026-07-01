"""Builtin building layouts when world.building_template_registry is empty."""

from app.dataModel.structure.building.worldBuildingLayoutDefaults import canonical_defaults


def merge_building_registry(world) -> list[dict]:
    """World registry + defaults (world wins on name collision)."""
    by_name: dict[str, dict] = {t["system_name"]: t for t in canonical_defaults()}
    for t in world.building_template_registry or []:
        key = t.get("system_name") or t.get("system_template_uid")
        if key:
            by_name[key] = t
    return list(by_name.values())


def lookup_building_template(world, system_name: str) -> dict | None:
    for t in merge_building_registry(world):
        if t.get("system_name") == system_name:
            return t
    return None
