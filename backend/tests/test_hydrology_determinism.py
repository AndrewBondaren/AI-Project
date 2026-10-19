"""Cross-process determinism — autoresolve carve paths must not depend on hash seed.

Plan: .cursor/plans/hydrology-test-fixtures.md step 4.
Spawns subprocesses with different PYTHONHASHSEED; output must be byte-identical.
"""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent

_SCRIPT = r"""
import json
import sys

sys.path.insert(0, ".")

from tests.hydrology_fixtures import (
    depression_heightmap,
    flat_heightmap,
    heightmap_from_z,
    hydro_master,
    hydro_world,
    rivers_hydrology,
    seas_hydrology,
)
from app.application.worldData.generators.hydrology.autoresolve.proceduralLakeAutoresolve import (
    autoresolve_lakes,
)
from app.application.worldData.generators.hydrology.autoresolve.proceduralSeaAutoresolve import (
    autoresolve_sea_basins,
)
from app.application.worldData.generators.hydrology.autoresolve.proceduralRiverAutoresolve import (
    autoresolve_river_segments,
)
from app.application.worldData.generators.hydrology.types import HydrologyScope
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology


def _dump(entries):
    return sorted(f"{x},{y}:{e.water_body_uid}" for (x, y), e in entries.items())


world = hydro_world(hydrology=seas_hydrology())

lakes, _ = autoresolve_lakes(
    world,
    depression_heightmap(),
    hydro_master(scopes=frozenset({HydrologyScope.LAKES})),
    {},
)
sea, _ = autoresolve_sea_basins(
    world,
    flat_heightmap(0, 10, 0, 6),
    hydro_master(),
    {},
    autoresolve_coastal=True,
    autoresolve_open_ocean=True,
)

surface_z = {(gx, gy): 10 for gx in range(8) for gy in range(8)}
for gy in range(1, 8):
    surface_z[(4, gy)] = 10 + gy * 6
occupied = {
    (gx, 0): MapCellHydrology(role=HydrologyCellRole.OPEN_OCEAN)
    for gx in range(8)
}
segments = autoresolve_river_segments(
    hydro_world(hydrology=rivers_hydrology()),
    heightmap_from_z(surface_z),
    hydro_master(scopes=frozenset({HydrologyScope.RIVERS})),
    occupied,
)

print(json.dumps({
    "lakes": _dump(lakes),
    "sea": _dump(sea),
    "rivers": sorted(
        {"edge": s.edge_uid, "cells": s.polyline_cells} for s in segments
    ),
}))
"""


class CrossProcessDeterminismTest(unittest.TestCase):

    def _run(self, hashseed: str) -> str:
        env = {**os.environ, "PYTHONHASHSEED": hashseed}
        out = subprocess.run(
            [sys.executable, "-c", _SCRIPT],
            cwd=BACKEND_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout

    def test_autoresolve_carves_identical_across_hash_seeds(self):
        runs = [self._run(seed) for seed in ("0", "1", "42")]
        payload = json.loads(runs[0])
        self.assertTrue(payload["lakes"])
        self.assertTrue(payload["sea"])
        self.assertTrue(payload["rivers"])
        self.assertEqual(runs[0], runs[1])
        self.assertEqual(runs[0], runs[2])


if __name__ == "__main__":
    unittest.main()
