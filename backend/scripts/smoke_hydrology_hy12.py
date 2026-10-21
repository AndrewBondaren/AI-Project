"""Offline HY-12 coarse acceptance, with replay and optional diagnostic render.

Reads a bundle without importing/persisting it; never starts the backend.
Run from the repository: python backend/scripts/smoke_hydrology_hy12.py --render
L0 masks/bands remain the separate HY-10 acceptance.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import fields
from html import escape
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "backend") not in sys.path:
    sys.path.insert(0, str(REPO / "backend"))

from app.application.worldData.generators.hydrology.hydrologyGeneratorService import HydrologyGeneratorService
from app.application.worldData.generators.hydrology.load.resolveHydrologyTopology import resolve_hydrology_topology
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import prepare_surface_terrain_context
from app.dataModel.topology.topologyGeometry import canonical_neighbors4
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def load_fixture(path: Path) -> tuple[World, list[NamedLocation]]:
    bundle = json.loads(path.read_text(encoding="utf-8"))
    world_fields = {item.name for item in fields(World)}
    location_fields = {item.name for item in fields(NamedLocation)}
    world = World(**({"name": "HY-12 smoke", "created_at": ""}
                     | {key: value for key, value in bundle["world"].items() if key in world_fields}))
    locations = [NamedLocation(**{key: value for key, value in row.items() if key in location_fields})
                 for row in bundle["locations"]]
    return world, locations


class SmokeHydrology(HydrologyGeneratorService):
    """Capture the real facade output for assertions, without a second fill."""

    def apply(self, *args, **kwargs):
        self.result = super().apply(*args, **kwargs)
        return self.result


def coarse_snapshot(world, locations) -> dict:
    service = SmokeHydrology()
    context = prepare_surface_terrain_context(world, locations, hydrology_generator=service)
    if context is None:
        raise AssertionError("empty coarse heightmap")
    topology = resolve_hydrology_topology(world, context.coarse_hm, locations=locations)
    index = context.coarse_hydro
    water = {cell: entry for cell, entry in index.items()
             if entry.role is not None and entry.role.is_open_water_role()}
    for cell, entry in water.items():
        assert entry.water_body_uid and entry.z_water_level is not None, (cell, entry)
        assert context.coarse_hm.surface_z[cell] < entry.z_water_level, (cell, entry)
    shores = {cell: entry for cell, entry in index.items() if entry.role and entry.role.value == "shore"}
    for cell, entry in shores.items():
        assert not entry.liquid_candidate and entry.water_body_uid, (cell, entry)
        assert entry.z_water_level is not None, (cell, entry)
        assert context.coarse_hm.surface_z[cell] >= entry.z_water_level, (cell, entry)
        assert any(neighbor in water for neighbor in canonical_neighbors4(topology, cell)), cell
    result = service.result
    cells = [{"x": x, "y": y, "base_z": context.coarse_relief_z[(x, y)], "z": z,
              "hydrology": index[(x, y)].model_dump(mode="json", exclude_none=True)
              if (x, y) in index else None}
             for (x, y), z in sorted(context.coarse_hm.surface_z.items(), key=lambda item: (item[0][1], item[0][0]))]
    return {
        "world_uid": world.world_uid, "topology": topology.model_dump(mode="json"),
        "roles": dict(sorted(Counter(entry.role.value for entry in index.values() if entry.role).items())),
        "water_cells": len(water), "shore_cells": len(shores), "cells": cells,
        "bodies": [body.model_dump(mode="json") for body in result.water_bodies],
        "unions": [union.model_dump(mode="json") for union in result.physical_unions],
        "rivers": [{"cells": segment.polyline_cells, "uid": segment.location_uid,
                    "edge": segment.edge_uid} for segment in result.river_segments],
        "drops": [drop.model_dump(mode="json") for drop in result.waterfall_drops],
    }


def render_svg(snapshot: dict) -> str:
    cells = snapshot["cells"]
    x_min, x_max = min(cell["x"] for cell in cells), max(cell["x"] for cell in cells)
    y_min, y_max = min(cell["y"] for cell in cells), max(cell["y"] for cell in cells)
    step, left, top = 105, 45, 85
    panel_width = (x_max - x_min + 1) * step + 65
    height = (y_max - y_min + 1) * step + 145
    content = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{panel_width * 2}" height="{height}" viewBox="0 0 {panel_width * 2} {height}">',
               '<rect width="100%" height="100%" fill="#101923"/>',
               '<g font-family="sans-serif" fill="#eef4ff">',
               f'<text x="25" y="28" font-size="19">{escape(snapshot["world_uid"])} · coarse HY-12 · {escape(snapshot["topology"]["mode"])}</text>']
    for panel, title in enumerate(("Base terrain before relief", "Post-carve floor / water level")):
        offset = panel * panel_width
        content.append(f'<text x="{offset + left}" y="60" font-size="15">{title}</text>')
        for cell in cells:
            x = offset + left + (cell["x"] - x_min) * step
            y = top + (cell["y"] - y_min) * step
            hydro = cell["hydrology"] or {}
            role = hydro.get("role", "land") if panel else "base"
            color = {"shore": "#776747", "river_bed": "#285c73", "land": "#3f5144", "base": "#3b4657"}.get(role, "#234e88")
            z = cell["z"] if panel else cell["base_z"]
            level = hydro.get("z_water_level")
            content.append(f'<rect x="{x}" y="{y}" width="102" height="102" rx="5" fill="{color}"/>')
            for dy, text in ((19, f'({cell["x"]}, {cell["y"]})'), (43, f'z={z}'),
                             (65, role), (86, f'level={level}' if panel and level is not None else "")):
                content.append(f'<text x="{x + 7}" y="{y + dy}" font-size="12">{escape(text)}</text>')
    content.append('</g></svg>')
    return "\n".join(content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=REPO / "fixtures/world_test_004.json")
    parser.add_argument("--output", type=Path, default=REPO / ".local/map-render/hy12-coarse")
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    world, locations = load_fixture(args.fixture)
    first = coarse_snapshot(world, locations)
    second = coarse_snapshot(world, locations)
    assert first == second, "coarse re-bake changed physical facts"
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "acceptance.json").write_text(json.dumps(first, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.render:
        (args.output / "coarse.svg").write_text(render_svg(first), encoding="utf-8")
    print(json.dumps({"replay_equal": True, "water_cells": first["water_cells"],
                      "shore_cells": first["shore_cells"], "roles": first["roles"],
                      "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
