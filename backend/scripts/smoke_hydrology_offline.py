"""Offline smoke — same generators as HTTP, reads world from game.db (no server reload needed)."""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from app.application.worldData.generators.assemblers.climateAssembler.passes.poleResolvePass import (
    run_pole_resolve_pass,
)
from app.application.worldData.generators.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.application.worldData.generators.terrain.passes.columnFillPass import run_column_fill
from app.application.worldData.generators.terrain.passes.gapAnalysisPass import run_gap_analysis
from app.application.worldData.generators.terrain.passes.surfacePass import run_surface_pass
from app.application.worldData.generators.hydrology.load.buildHydrologyMasterInput import (
    build_hydrology_master_input,
)
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

WORLD_UID = "world-test-all-001"
DB = REPO / "db" / "game.db"


def _row_to_world(row: sqlite3.Row) -> World:
    data = dict(row)
    for key in (
        "map_settings",
        "hydrology",
        "terrain",
        "climate",
        "caves",
        "economic_tier_registry",
        "material_registry",
        "terrain_registry",
        "terrain_category_registry",
        "climate_zone_registry",
        "weather_type_registry",
        "location_type_registry",
        "location_mood_registry",
        "lore_registry",
        "room_type_registry",
        "building_template_registry",
        "barrier_template_registry",
        "district_template_registry",
        "city_size_registry",
        "connection_type_registry",
        "road_settings",
    ):
        if key in data and isinstance(data[key], str):
            try:
                data[key] = json.loads(data[key])
            except json.JSONDecodeError:
                pass
    return World(**{k: v for k, v in data.items() if k in World.__dataclass_fields__})


def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    wrow = conn.execute(
        "SELECT * FROM worlds WHERE world_uid = ?", (WORLD_UID,),
    ).fetchone()
    if wrow is None:
        raise SystemExit(f"world {WORLD_UID} not in {DB}")

    world = _row_to_world(wrow)
    loc_rows = conn.execute(
        "SELECT * FROM named_locations WHERE world_uid = ?", (WORLD_UID,),
    ).fetchall()
    locations = [NamedLocation(**dict(r)) for r in loc_rows]
    conn.close()

    pole = run_pole_resolve_pass(world, locations)
    heightmap = run_surface_pass(world, locations, pole)
    if heightmap is None:
        raise SystemExit("empty heightmap")

    master = build_hydrology_master_input(world, locations)
    hydro = HydrologyGeneratorService().apply(world, locations, heightmap, master=master)
    n_eff = run_gap_analysis(world, heightmap)
    cells = run_column_fill(
        world, heightmap, n_eff, hydrology_by_cell=hydro.cell_index.by_cell,
    )

    tops: dict[tuple[int, int], dict] = {}
    for c in cells:
        key = (c.x, c.y)
        if key not in tops or c.z > tops[key]["z"]:
            tops[key] = {
                "x": c.x, "y": c.y, "z": c.z,
                "system_terrain": c.system_terrain,
                "hydrology": c.hydrology,
            }

    top_list = list(tops.values())
    xs = [c["x"] for c in top_list]
    ys = [c["y"] for c in top_list]
    roles: Counter[str] = Counter()
    liquid_body = 0
    liquid_cand = 0
    meter_orphans = 0
    for c in top_list:
        h = c.get("hydrology") or {}
        if h.get("role"):
            roles[h["role"]] += 1
        if c.get("system_terrain") == "liquid_body":
            liquid_body += 1
        if h.get("liquid_candidate"):
            liquid_cand += 1
        if abs(c["x"]) > 100 or abs(c["y"]) > 100:
            meter_orphans += 1

    print("offline pipeline OK")
    print(f"hydrology cells_modified: {hydro.cells_modified}")
    print(f"coastline segments: {len(master.declared_coastline_segments)}")
    print(f"total cells (all z): {len(cells)}")
    print(f"surface-top columns: {len(top_list)}")
    print(f"grid x: [{min(xs)}, {max(xs)}]  y: [{min(ys)}, {max(ys)}]")
    print(f"hydrology roles: {dict(roles)}")
    print(f"liquid_candidate surface-top: {liquid_cand}")
    print(f"meter-scale orphan coords: {meter_orphans}")

    sea_band = [c for c in top_list if 7 <= c["x"] <= 12 and 0 <= c["y"] <= 3]
    sea_roles = Counter((c.get("hydrology") or {}).get("role") for c in sea_band)
    print(f"sea band gx7-12 gy0-3: roles={dict(sea_roles)}")


if __name__ == "__main__":
    main()
