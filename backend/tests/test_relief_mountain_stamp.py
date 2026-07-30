"""Unit: mountain sides stamp from relief recipe."""

from __future__ import annotations

import unittest

from app.application.worldData.generators.terrain.mountains.reliefSidesStamp import (
    stamp_mountain_sides_from_relief,
)
from app.application.worldData.reliefTemplateLibraryService import relief_template_uid
from app.dataModel.terrain.relief import ReliefSideKind, ReliefSideSpec, ReliefTemplate
from app.dataModel.terrainMasks.mountain.specs import MountainFormBySides, MountainSpec
from app.db.models.world import World


class MountainReliefStampTest(unittest.TestCase):
    def test_empty_sides_use_recipe_fixed(self) -> None:
        tpl = ReliefTemplate.model_validate({
            "system_name": "gentle_dome",
            "display_name": "Dome",
            "context": "mountain",
            "side_recipe": {"default_side_kind": "slope"},
        })
        uid = relief_template_uid("gentle_dome")
        world = World(
            world_uid="w1",
            name="W",
            created_at="2026-01-01T00:00:00Z",
            relief_template_registry=[{
                "system_template_uid": uid,
                "context": "mountain",
            }],
            relief_pick_policy={
                "mountain": {"mode": "fixed", "default_template_uid": uid},
            },
        )
        spec = MountainSpec(
            origin_x_m=0,
            origin_y_m=0,
            radius_m=100,
            form=MountainFormBySides(side_count=4),
            sides=[],
        )
        stamped = stamp_mountain_sides_from_relief(
            spec,
            world=world,
            world_seed="w1",
            templates_by_uid={uid: tpl},
        )
        self.assertEqual(len(stamped.sides), 4)
        self.assertTrue(all(s.kind.value == "slope" for s in stamped.sides))

    def test_declare_not_overwritten(self) -> None:
        spec = MountainSpec(
            origin_x_m=0,
            origin_y_m=0,
            radius_m=100,
            form=MountainFormBySides(side_count=3),
            sides=[
                ReliefSideSpec(kind=ReliefSideKind.SHEER),
                ReliefSideSpec(kind=ReliefSideKind.SHEER),
                ReliefSideSpec(kind=ReliefSideKind.SHEER),
            ],
        )
        world = World(world_uid="w1", name="W", created_at="2026-01-01T00:00:00Z")
        stamped = stamp_mountain_sides_from_relief(
            spec, world=world, world_seed="w1", templates_by_uid={},
        )
        self.assertTrue(all(s.kind.value == "sheer" for s in stamped.sides))

    def test_r21_missing_template_all_slope(self) -> None:
        """RELIEF-T-2: empty registry → R21 all-SLOPE, not Mode D 50/50."""
        world = World(world_uid="w1", name="W", created_at="2026-01-01T00:00:00Z")
        spec = MountainSpec(
            origin_x_m=0,
            origin_y_m=0,
            radius_m=100,
            form=MountainFormBySides(side_count=4),
            sides=[],
        )
        stamped = stamp_mountain_sides_from_relief(
            spec, world=world, world_seed="w1", templates_by_uid={},
        )
        self.assertEqual(len(stamped.sides), 4)
        self.assertTrue(all(s.kind == ReliefSideKind.SLOPE for s in stamped.sides))


if __name__ == "__main__":
    unittest.main()
