"""Unit: R37 ontology envelope POJO + grade_constrained facade."""

from __future__ import annotations

import math
import unittest

from pydantic import ValidationError

from app.application.worldData.generators.terrain.relief.pick.gradeConstrained import (
    grade_constrained,
)
from app.application.worldData.generators.terrain.relief.pick.gradePass import (
    grade_from_template,
)
from app.dataModel.terrain.relief.enums import ReliefContext, ReliefSideKind
from app.dataModel.terrain.relief.reliefSlopeGeom import (
    angle_from_height_length,
    height_from_length_angle,
    length_from_target_angle,
)
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.terrain.relief.reliefTerrainEnvelope import (
    ReliefOntologyEnvelopes,
    ReliefTerrainEnvelope,
)


def _open_land_plains(
    *,
    slope_length: int = 2,
    sheer_weight: float = 0.15,
    context: str = "open_land",
    extra_terrain: dict | None = None,
) -> ReliefTemplate:
    slope_w = round(1.0 - sheer_weight, 6)
    conditions = [{
        "terrain": "plains",
        "cases": [
            {
                "policy": "slope_down",
                "delta_z": 1,
                "slope_weight": slope_w,
                "sheer_weight": sheer_weight,
                "slope_length_cells": slope_length,
            },
            {
                "policy": "slope_up",
                "delta_z": 1,
                "slope_weight": 1.0,
                "sheer_weight": 0.0,
                "slope_length_cells": slope_length,
            },
            {
                "policy": "slope_none",
                "delta_z": 0,
                "slope_weight": 1.0,
                "sheer_weight": 0.0,
            },
        ],
    }]
    if extra_terrain is not None:
        conditions.append(extra_terrain)
    return ReliefTemplate.model_validate({
        "system_name": "open_land_soft",
        "display_name": "Open land soft",
        "context": context,
        "slope_length_cells": slope_length,
        "conditions": conditions,
    })


def _open_land_forest(
    *,
    slope_length: int = 2,
    sheer_weight: float = 0.0,
) -> ReliefTemplate:
    return _open_land_plains(
        slope_length=slope_length,
        sheer_weight=0.0,
        extra_terrain={
            "terrain": "forest",
            "cases": [
                {
                    "policy": "slope_down",
                    "delta_z": 1,
                    "slope_weight": round(1.0 - sheer_weight, 6),
                    "sheer_weight": sheer_weight,
                    "slope_length_cells": slope_length,
                },
                {
                    "policy": "slope_up",
                    "delta_z": 1,
                    "slope_weight": 1.0,
                    "sheer_weight": 0.0,
                    "slope_length_cells": slope_length,
                },
                {
                    "policy": "slope_none",
                    "delta_z": 0,
                    "slope_weight": 1.0,
                    "sheer_weight": 0.0,
                },
            ],
        },
    )


class ReliefOntologyEnvelopePojoTest(unittest.TestCase):
    def test_canonical_plains_locked_numbers(self) -> None:
        plains = ReliefOntologyEnvelopes.canonical_defaults().plains
        self.assertEqual(plains.plateau_z_band_factor, 0)
        self.assertEqual(plains.slope_max_angle_deg, 20.0)
        self.assertEqual(plains.slope_length_min_cells, 20)
        self.assertIsNone(plains.slope_length_max_cells)
        self.assertTrue(plains.sheer_allowed)
        self.assertTrue(plains.slope_preferred)
        self.assertTrue(plains.allow_l_gt_h)
        self.assertEqual(plains.sheer_min_abs_dz, 0)
        self.assertEqual(plains.apply_in_contexts, (ReliefContext.OPEN_LAND,))
        self.assertEqual(
            plains.canonical_sheer_length_cells(), 1,
        )

    def test_forest_same_slope_floor_sheer_min_4(self) -> None:
        forest = ReliefOntologyEnvelopes.canonical_defaults().forest
        plains = ReliefOntologyEnvelopes.canonical_defaults().plains
        self.assertFalse(forest.is_unconstrained())
        self.assertEqual(forest.slope_max_angle_deg, plains.slope_max_angle_deg)
        self.assertEqual(forest.slope_length_min_cells, plains.slope_length_min_cells)
        self.assertEqual(forest.slope_length_max_cells, plains.slope_length_max_cells)
        self.assertEqual(forest.plateau_z_band_factor, plains.plateau_z_band_factor)
        self.assertFalse(forest.slope_preferred)
        self.assertEqual(forest.sheer_min_abs_dz, 4)
        self.assertTrue(forest.sheer_ok(4))
        self.assertFalse(forest.sheer_ok(3))
        self.assertEqual(forest.apply_in_contexts, (ReliefContext.OPEN_LAND,))

    def test_slope_length_for_plains_examples(self) -> None:
        plains = ReliefOntologyEnvelopes.canonical_defaults().plains
        self.assertEqual(
            plains.slope_length_for(4, template_length=2), 20,
        )
        self.assertEqual(
            plains.slope_length_for(10, template_length=2), 28,
        )
        self.assertEqual(
            plains.slope_length_for(12, template_length=2), 33,
        )
        self.assertTrue(plains.slope_fits(4, 20))
        self.assertTrue(plains.slope_fits(10, 28))
        self.assertTrue(plains.slope_fits(12, 33))
        self.assertEqual(plains.slope_outcome(12, 33), "slope")
        self.assertEqual(
            plains.slope_length_for(2, template_length=2, length_cap=1), 1,
        )
        self.assertEqual(plains.slope_outcome(2, 1), "sheer")

    def test_geom_formulas_and_envelope_parts(self) -> None:
        self.assertAlmostEqual(angle_from_height_length(1, 1), 45.0, places=5)
        self.assertEqual(length_from_target_angle(10, 20.0), 28)
        self.assertAlmostEqual(
            height_from_length_angle(1, 45.0), 1.0, places=5,
        )
        plains = ReliefOntologyEnvelopes.canonical_defaults().plains
        self.assertEqual(plains.length_from_min_cells(), 20)
        self.assertEqual(plains.length_from_max_angle(4), 11)
        self.assertEqual(plains.envelope_length_floor(4), 20)
        self.assertEqual(plains.envelope_length_floor(10), 28)
        self.assertEqual(
            plains.length_from_template(4, template_length=2, fallback=20), 2,
        )
        self.assertEqual(
            plains.length_from_template(
                4, template_angle_deg=20.0, fallback=20,
            ),
            11,
        )
        self.assertEqual(plains.clamp_slope_length(40), 40)
        self.assertAlmostEqual(
            plains.slope_angle_deg(4, 20),
            math.degrees(math.atan(4 / 20)),
            places=5,
        )

    def test_min_gt_max_reject(self) -> None:
        with self.assertRaises(ValidationError):
            ReliefTerrainEnvelope(
                slope_length_min_cells=30,
                slope_length_max_cells=20,
            )


class TerrainDescentRayTest(unittest.TestCase):
    def test_four_to_two_stops_at_rising_voxel(self) -> None:
        from app.application.worldData.generators.terrain.relief.geom.terrainDescent import (
            measure_terrain_descent,
        )

        z = {(1, 0): 4, (2, 0): 2, (3, 0): 3}

        def z_at(xy: tuple[int, int]) -> int | None:
            return z.get(xy)

        length, z_end = measure_terrain_descent(
            start=(2, 0),
            outward=(1, 0),
            z_peak=4,
            z_at=z_at,
        )
        self.assertEqual(length, 1)
        self.assertEqual(z_end, 2)
        self.assertAlmostEqual(
            angle_from_height_length(4 - z_end, length),
            math.degrees(math.atan(2 / 1)),
            places=5,
        )


class GradeConstrainedTest(unittest.TestCase):
    def test_unit_step_is_gentle_slope_without_ray_cap(self) -> None:
        tpl = _open_land_plains()
        d = grade_constrained(
            template=tpl,
            template_uid="uid",
            terrain_key="plains",
            dz=1,
            world_seed="s",
            site_id="site",
        )
        self.assertFalse(d.skipped)
        self.assertEqual(d.kind, ReliefSideKind.SLOPE)
        self.assertEqual(d.requested_length, 20)

    def test_short_ray_h2_is_sheer(self) -> None:
        tpl = _open_land_plains()
        d = grade_constrained(
            template=tpl,
            template_uid="uid",
            terrain_key="plains",
            dz=2,
            world_seed="s",
            site_id="site",
            path_length=1,
        )
        self.assertFalse(d.skipped)
        self.assertEqual(d.kind, ReliefSideKind.SHEER)
        self.assertEqual(d.requested_length, 1)

    def test_inner_still_compresses_without_facade(self) -> None:
        tpl = _open_land_plains(sheer_weight=0.0)
        d = grade_from_template(
            template=tpl,
            template_uid="uid",
            terrain_key="plains",
            dz=12,
            world_seed="s",
            site_id="site",
        )
        self.assertFalse(d.skipped)
        self.assertIsNotNone(d.geom)
        assert d.geom is not None
        self.assertEqual(d.geom.L, 2)
        self.assertEqual(d.geom.steps, (6, 6))

    def test_plains_long_slope_restores_l_gt_h(self) -> None:
        tpl = _open_land_plains()
        d = grade_constrained(
            template=tpl,
            template_uid="uid",
            terrain_key="plains",
            dz=4,
            world_seed="s",
            site_id="site",
        )
        self.assertFalse(d.skipped)
        self.assertEqual(d.kind, ReliefSideKind.SLOPE)
        self.assertEqual(d.requested_length, 20)
        assert d.geom is not None
        self.assertEqual(d.geom.L, 20)
        self.assertEqual(sum(d.geom.steps), 4)
        self.assertEqual(len(d.geom.steps), 20)
        self.assertAlmostEqual(
            d.geom.angle_deg or 0.0,
            math.degrees(math.atan(4 / 20)),
            places=5,
        )

    def test_plains_h12_fits_long_slope(self) -> None:
        tpl = _open_land_plains()
        d = grade_constrained(
            template=tpl,
            template_uid="uid",
            terrain_key="plains",
            dz=12,
            world_seed="s",
            site_id="site",
        )
        self.assertFalse(d.skipped)
        self.assertEqual(d.kind, ReliefSideKind.SLOPE)
        self.assertEqual(d.requested_length, 33)

    def test_road_shoulder_plains_pass_through(self) -> None:
        tpl = _open_land_plains(context="road_shoulder", sheer_weight=0.0)
        d = grade_constrained(
            template=tpl,
            template_uid="uid",
            terrain_key="plains",
            dz=12,
            world_seed="s",
            site_id="site",
        )
        self.assertFalse(d.skipped)
        assert d.geom is not None
        self.assertEqual(d.geom.L, 2)
        self.assertEqual(d.geom.steps, (6, 6))

    def test_pass_through_sheer_forced_to_l1(self) -> None:
        tpl = _open_land_plains(context="road_shoulder", slope_length=2, sheer_weight=1.0)
        d = grade_constrained(
            template=tpl,
            template_uid="uid",
            terrain_key="plains",
            dz=12,
            world_seed="s",
            site_id="site",
        )
        self.assertEqual(d.kind, ReliefSideKind.SHEER)
        self.assertEqual(d.requested_length, 1)
        assert d.geom is not None
        self.assertEqual(d.geom.L, 1)

    def test_forest_h3_forces_slope_even_if_template_sheer(self) -> None:
        tpl = _open_land_forest(sheer_weight=1.0)
        d = grade_constrained(
            template=tpl,
            template_uid="uid",
            terrain_key="forest",
            dz=3,
            world_seed="s",
            site_id="site",
        )
        self.assertFalse(d.skipped)
        self.assertEqual(d.kind, ReliefSideKind.SLOPE)
        self.assertEqual(d.requested_length, 20)

    def test_forest_h4_allows_sheer_l1(self) -> None:
        tpl = _open_land_forest(sheer_weight=1.0)
        d = grade_constrained(
            template=tpl,
            template_uid="uid",
            terrain_key="forest",
            dz=4,
            world_seed="s",
            site_id="site",
        )
        self.assertFalse(d.skipped)
        self.assertEqual(d.kind, ReliefSideKind.SHEER)
        self.assertEqual(d.requested_length, 1)
        assert d.geom is not None
        self.assertEqual(d.geom.L, 1)
        self.assertEqual(d.geom.steps, ())

    def test_forest_h12_fits_long_slope(self) -> None:
        tpl = _open_land_forest(sheer_weight=0.0)
        d = grade_constrained(
            template=tpl,
            template_uid="uid",
            terrain_key="forest",
            dz=12,
            world_seed="s",
            site_id="site",
        )
        self.assertFalse(d.skipped)
        self.assertEqual(d.kind, ReliefSideKind.SLOPE)
        self.assertEqual(d.requested_length, 33)

    def test_gentler_template_keeps_longer_l(self) -> None:
        tpl = _open_land_plains(slope_length=30, sheer_weight=0.0)
        d = grade_constrained(
            template=tpl,
            template_uid="uid",
            terrain_key="plains",
            dz=4,
            world_seed="s",
            site_id="site",
        )
        self.assertEqual(d.kind, ReliefSideKind.SLOPE)
        self.assertEqual(d.requested_length, 30)


if __name__ == "__main__":
    unittest.main()
