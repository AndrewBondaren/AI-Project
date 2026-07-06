"""JV matrix — river system topology A (confluence) / B (basin)."""

import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from app.application.jsonValidation.facade import normalize_world
from app.application.worldData.generators.terrain.hydrology.buildHydrologyMasterInput import (
    build_hydrology_master_input,
)
from app.application.worldData.generators.terrain.hydrology.loadDeclaredHydrology import (
    build_river_system_index,
    load_declared_hydrology,
)
from app.dataModel.hydrology.declaredRiver import DeclaredRiver
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from types import SimpleNamespace


def _stem(uid: str, *, parent: str | None = None) -> dict:
    entry = {
        "location_uid": uid,
        "system_role": "stem",
        "declare_mode": "endpoints",
        "source": {"x": 3000, "y": 3000, "z": 0},
        "mouth": {"x": 6000, "y": 6000, "z": 0},
    }
    if parent:
        entry["parent_location_uid"] = parent
    return entry


def _tributary(uid: str, parent: str) -> dict:
    return {
        "location_uid": uid,
        "system_role": "tributary",
        "parent_location_uid": parent,
        "declare_mode": "endpoints",
        "source": {"x": 4000, "y": 4000, "z": 0},
        "mouth": {"x": 5000, "y": 5000, "z": 0},
    }


def _system(uid: str, *, topology: str | None = "basin") -> dict:
    entry = {"location_uid": uid, "system_role": "system"}
    if topology is not None:
        entry["river_system_topology"] = topology
    return entry


class TestDeclaredRiverTopology(unittest.TestCase):

    def test_basin_system_without_topology_rejected(self):
        with self.assertRaises(ValidationError):
            DeclaredRiver.model_validate(_system("sys-basin", topology=None))

    def test_system_with_confluence_topology_rejected(self):
        with self.assertRaises(ValidationError):
            DeclaredRiver.model_validate(_system("sys-bad", topology="confluence"))

    def test_stem_with_topology_rejected(self):
        with self.assertRaises(ValidationError):
            DeclaredRiver.model_validate({
                **_stem("stem-a"),
                "river_system_topology": "basin",
            })

    def test_basin_stem_with_invalid_parent_rejected(self):
        with self.assertRaises(ValidationError):
            WorldHydrology.model_validate({
                "declared_rivers": [
                    _system("sys-basin"),
                    _stem("stem-a", parent="missing-parent"),
                ],
            })

    def test_confluence_tributary_parent_not_stem_rejected(self):
        with self.assertRaises(ValidationError):
            WorldHydrology.model_validate({
                "declared_rivers": [
                    _system("sys-basin"),
                    _tributary("trib-a", "sys-basin"),
                ],
            })

    def test_valid_basin_group(self):
        hydrology = WorldHydrology.model_validate({
            "declared_rivers": [
                _system("sys-basin"),
                _stem("stem-a", parent="sys-basin"),
                _tributary("trib-a", "stem-a"),
            ],
        })
        self.assertEqual(len(hydrology.declared_rivers), 3)

    def test_valid_confluence_group(self):
        hydrology = WorldHydrology.model_validate({
            "declared_rivers": [
                _stem("stem-main"),
                _tributary("trib-a", "stem-main"),
            ],
        })
        self.assertEqual(hydrology.declared_rivers[0].parent_location_uid, None)

    def test_mixed_basin_and_confluence(self):
        hydrology = WorldHydrology.model_validate({
            "declared_rivers": [
                _system("sys-basin"),
                _stem("stem-basin", parent="sys-basin"),
                _stem("stem-conf"),
                _tributary("trib-conf", "stem-conf"),
            ],
        })
        self.assertEqual(len(hydrology.declared_rivers), 4)

    def test_world_template_imports(self):
        template_path = Path(__file__).resolve().parents[2] / "fixtures" / "world_template.json"
        raw = json.loads(template_path.read_text(encoding="utf-8"))
        normalized = normalize_world(raw["world"])
        rivers = normalized.get("hydrology", {}).get("declared_rivers", [])
        basin = [r for r in rivers if r.get("system_role") == "system"]
        self.assertTrue(basin)
        self.assertEqual(basin[0].get("river_system_topology"), "basin")
        confluence_stems = [
            r for r in rivers
            if r.get("system_role") == "stem" and not r.get("parent_location_uid")
        ]
        self.assertTrue(confluence_stems)

    def test_river_system_index_from_loader(self):
        w = SimpleNamespace(
            world_uid="test",
            map_cell_size_m=3000,
            hydrology={
                "declared_rivers": [
                    _system("sys-basin"),
                    _stem("stem-basin", parent="sys-basin"),
                    _stem("stem-conf"),
                    _tributary("trib-conf", "stem-conf"),
                ],
            },
        )
        loaded = load_declared_hydrology(w, [])
        idx = loaded.river_system_index
        self.assertIsNotNone(idx)
        self.assertEqual(idx.topology_by_system_uid, {"sys-basin": "basin"})
        self.assertIn("stem-basin", idx.children["sys-basin"])
        self.assertIn("trib-conf", idx.children["stem-conf"])

    def test_build_hydrology_master_input_carries_index(self):
        w = SimpleNamespace(
            world_uid="test",
            map_cell_size_m=3000,
            hydrology={"enabled": True, "declared_rivers": [_stem("stem-only")]},
        )
        master = build_hydrology_master_input(w, [])
        self.assertIsNotNone(master.river_system_index)
        self.assertIn("stem-only", master.river_system_index.by_location_uid)

    def test_build_river_system_index_skips_system_for_carve_children(self):
        rivers = [
            DeclaredRiver.model_validate(_system("sys")),
            DeclaredRiver.model_validate(_stem("stem", parent="sys")),
        ]
        idx = build_river_system_index(rivers)
        self.assertEqual(idx.children["sys"], ["stem"])


if __name__ == "__main__":
    unittest.main()
