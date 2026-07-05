"""
Build fixtures/world_test_all.json — merge world_test.json + world_template.json.

Run from repo root:
  python backend/scripts/build_world_test_all_fixture.py
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "fixtures" / "world_test_all.json"
WORLD_TEST = REPO / "fixtures" / "world_test.json"
WORLD_TEMPLATE = REPO / "fixtures" / "world_template.json"

WORLD_UID = "world-test-all-001"


def _merge_registry_list(items_a: list[dict], items_b: list[dict], key: str) -> list[dict]:
    merged: dict[str, dict] = {}
    for item in items_a:
        merged[item[key]] = item
    for item in items_b:
        if item[key] not in merged:
            merged[item[key]] = item
    return list(merged.values())


def _merge_material_registry(test_items: list[dict], template_items: list[dict]) -> list[dict]:
    """Test entries are fuller; add template-only materials (sand, ice)."""
    merged = {item["system_material"]: item for item in test_items}
    for item in template_items:
        merged.setdefault(item["system_material"], item)
    return list(merged.values())


def _remap_section(rows: list[dict], world_uid: str) -> list[dict]:
    out = []
    for row in rows:
        copy = deepcopy(row)
        copy["world_uid"] = world_uid
        out.append(copy)
    return out


def build() -> dict:
    test = json.loads(WORLD_TEST.read_text(encoding="utf-8"))
    template = json.loads(WORLD_TEMPLATE.read_text(encoding="utf-8"))

    tw = template["world"]
    w = deepcopy(test["world"])

    # Template: climate / terrain generation / hydrology / connections vocabulary
    for key in (
        "map_subsurface_depth",
        "grid_bbox_padding",
        "terrain_chunk_columns",
        "z_min",
        "z_max",
        "elevation_lapse_rate",
        "g",
        "closed_planet_grid",
        "default_climate_zone",
        "climate_temperature_peak_min",
        "climate_temperature_peak_max",
        "climate_pole_mode",
        "climate_pole_preset",
        "climate_local_influence_fraction",
        "precipitation_liquid",
        "season_temp_offsets",
        "climate_zone_registry",
        "connection_type_registry",
        "hydrology",
        "caves",
    ):
        if key in tw:
            w[key] = deepcopy(tw[key])

    w["world_uid"] = WORLD_UID
    w["name"] = "Эйдора (полный эталон)"
    w["location_type_registry"] = {
        **tw.get("location_type_registry", {}),
        **w.get("location_type_registry", {}),
    }
    w["lore_registry"] = {**w.get("lore_registry", {}), **tw.get("lore_registry", {})}
    w["terrain_registry"] = _merge_registry_list(
        w.get("terrain_registry", []),
        tw.get("terrain_registry", []),
        "system_terrain",
    )
    w["material_registry"] = _merge_material_registry(
        w.get("material_registry", []),
        tw.get("material_registry", []),
    )
    w["city_size_registry"] = _merge_registry_list(
        w.get("city_size_registry", []),
        tw.get("city_size_registry", []),
        "system_size",
    )

    bundle: dict = {
        "_fixture_meta": {
            "version": "2026-07",
            "description": (
                "Объединение fixtures/world_test.json (gameplay: Эйдора, Ironhold, races, perks) "
                "и fixtures/world_template.json (climate, hydrology.declared_*, geographic declare). "
                "map_cells пуст — после import: debug_surface_helpers.api_materialize_surface_stack. "
                "character_test.json по-прежнему привязан к world-test-001; для этого мира — свой персонаж или remap."
            ),
            "sources": ["world_test.json", "world_template.json"],
            "world_uid": WORLD_UID,
        },
        "world": w,
        "states": _remap_section(test.get("states", []), WORLD_UID)
        + _remap_section(template.get("states", []), WORLD_UID),
        "races": _remap_section(test.get("races", []), WORLD_UID),
        "perks": _remap_section(test.get("perks", []), WORLD_UID),
        "locations": _remap_section(test.get("locations", []), WORLD_UID)
        + _remap_section(template.get("locations", []), WORLD_UID),
        "map_cells": [],
    }

    return bundle


def main() -> None:
    data = build()
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(REPO)}")
    print(f"  world_uid={WORLD_UID}")
    print(f"  locations={len(data['locations'])}")


if __name__ == "__main__":
    main()
