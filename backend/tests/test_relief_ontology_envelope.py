"""Unit: R37 ontology envelope POJO + grade_constrained facade.

Read canonical knobs from Pydantic. Literals only for TZ etalons (cubic h=1,L=1 → 45°)
or constructed cases (template L, invalid bounds).
"""

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


def _canonical_plains() -> ReliefTerrainEnvelope:
    return ReliefOntologyEnvelopes.canonical_defaults().plains


def _l1_first_sheer_abs_dz(env: ReliefTerrainEnvelope) -> int:
    for h in range(1, 32):
        if env.slope_outcome(h, 1) == "sheer":
            return h
    raise AssertionError("canonical envelope has no L=1 SHEER")


def _l1_last_slope_abs_dz(env: ReliefTerrainEnvelope) -> int:
    return _l1_first_sheer_abs_dz(env) - 1


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
    def test_canonical_plains_open_land_flags(self) -> None:
        plains = ReliefOntologyEnvelopes.canonical_defaults().plains
        self.assertIsNotNone(plains.slope_max_angle_deg)
        self.assertIsNone(plains.slope_length_max_cells)
        self.assertIsNone(plains.slope_walk_cap_cells())
        self.assertTrue(plains.sheer_allowed)
        self.assertTrue(plains.slope_preferred)
        self.assertTrue(plains.allow_l_gt_h)
        self.assertTrue(plains.sheer_ok(1))
        self.assertTrue(plains.stamps_first_step(1, ReliefContext.OPEN_LAND))
        self.assertEqual(plains.apply_in_contexts, (ReliefContext.OPEN_LAND,))
        self.assertEqual(
            plains.canonical_sheer_length_cells(), 1,
        )

    def test_forest_shares_open_land_floor(self) -> None:
        forest = ReliefOntologyEnvelopes.canonical_defaults().forest
        plains = ReliefOntologyEnvelopes.canonical_defaults().plains
        self.assertFalse(forest.is_unconstrained())
        self.assertEqual(forest.slope_max_angle_deg, plains.slope_max_angle_deg)
        self.assertEqual(forest.slope_length_min_cells, plains.slope_length_min_cells)
        self.assertEqual(forest.slope_length_max_cells, plains.slope_length_max_cells)
        self.assertEqual(forest.plateau_z_band_factor, plains.plateau_z_band_factor)
        self.assertFalse(forest.slope_preferred)
        self.assertTrue(forest.sheer_ok(int(forest.sheer_min_abs_dz)))
        self.assertFalse(forest.sheer_ok(int(forest.sheer_min_abs_dz) - 1))
        self.assertEqual(forest.apply_in_contexts, (ReliefContext.OPEN_LAND,))

    def test_pass_through_stamp_min_allows_unit(self) -> None:
        ravine = ReliefOntologyEnvelopes.canonical_defaults().ravine
        self.assertTrue(ravine.stamps_first_step(1, ReliefContext.RAVINE))
        self.assertTrue(ravine.grades_channel_bed)
        self.assertTrue(ravine.is_unconstrained())

    def test_no_legacy_shore_condition_terrain(self) -> None:
        from app.dataModel.terrain.relief.enums import ReliefConditionTerrain
        self.assertFalse(hasattr(ReliefConditionTerrain, "SHORE"))
        self.assertTrue(ReliefConditionTerrain.SHORE_SEA.is_shore_class())

    def test_shore_river_floor(self) -> None:
        river = ReliefOntologyEnvelopes.canonical_defaults().shore_river
        self.assertFalse(river.is_unconstrained())
        self.assertTrue(river.sheer_allowed)
        self.assertTrue(river.grades_channel_bed)
        self.assertIsNone(river.slope_min_angle_deg)
        self.assertEqual(river.apply_in_contexts, (ReliefContext.SHORE,))
        self.assertEqual(
            river.slope_length_for(3, template_length=1),
            river.length_from_min_cells(),
        )

    def test_shore_mountain_river_angle_band(self) -> None:
        mtn = ReliefOntologyEnvelopes.canonical_defaults().shore_mountain_river
        self.assertIsNotNone(mtn.slope_min_angle_deg)
        self.assertIsNotNone(mtn.slope_max_angle_deg)
        self.assertTrue(mtn.grades_channel_bed)
        l_min = mtn.length_from_min_cells()
        self.assertTrue(mtn.slope_fits(4, l_min))
        self.assertFalse(mtn.slope_fits(1, 10))

    def test_shore_sea_floor(self) -> None:
        sea = ReliefOntologyEnvelopes.canonical_defaults().shore_sea
        self.assertIsNotNone(sea.slope_min_angle_deg)
        self.assertIsNotNone(sea.slope_max_angle_deg)
        self.assertFalse(sea.grades_channel_bed)
        self.assertTrue(sea.sheer_ok(int(sea.sheer_min_abs_dz)))
        self.assertFalse(sea.sheer_ok(int(sea.sheer_min_abs_dz) - 1))
        l_min = sea.length_from_min_cells()
        self.assertEqual(sea.slope_length_for(4, template_length=2), l_min)
        self.assertTrue(sea.slope_fits(4, l_min))

    def test_shore_lake_floor_matches_river_numbers(self) -> None:
        env = ReliefOntologyEnvelopes.canonical_defaults()
        lake = env.shore_lake
        river = env.shore_river
        self.assertFalse(lake.is_unconstrained())
        self.assertTrue(lake.sheer_allowed)
        self.assertTrue(lake.grades_channel_bed)
        self.assertIsNone(lake.slope_min_angle_deg)
        self.assertEqual(lake.apply_in_contexts, (ReliefContext.SHORE,))
        self.assertEqual(
            lake.slope_length_for(3, template_length=1),
            lake.length_from_min_cells(),
        )
        self.assertEqual(lake.slope_length_min_cells, river.slope_length_min_cells)
        self.assertIs(env.for_terrain("shore_lake"), lake)
        self.assertIsNot(lake, river)

    def test_slope_length_for_plains_examples(self) -> None:
        """Construct L uses L_min; ``slope_fits`` is θ-only (L=1 still fits)."""
        plains = ReliefOntologyEnvelopes.canonical_defaults().plains
        l_min = plains.length_from_min_cells()
        self.assertEqual(
            plains.slope_length_for(4, template_length=2), l_min,
        )
        self.assertEqual(
            plains.slope_length_for(10, template_length=2), l_min,
        )
        self.assertEqual(
            plains.slope_length_for(12, template_length=2), l_min,
        )
        self.assertTrue(plains.slope_fits(4, l_min))
        self.assertTrue(plains.slope_fits(1, 1))
        self.assertTrue(plains.slope_fits(10, l_min))
        self.assertTrue(plains.slope_fits(12, l_min))
        self.assertEqual(plains.slope_outcome(12, l_min), "slope")
        self.assertEqual(plains.slope_outcome(1, 1), "slope")
        self.assertEqual(plains.slope_outcome(2, 1), "slope")
        last_slope = _l1_last_slope_abs_dz(plains)
        first_sheer = _l1_first_sheer_abs_dz(plains)
        self.assertEqual(plains.slope_outcome(last_slope, 1), "slope")
        self.assertEqual(plains.slope_outcome(first_sheer, 1), "sheer")
        forest = ReliefOntologyEnvelopes.canonical_defaults().forest
        self.assertEqual(forest.slope_outcome(last_slope, 1), "slope")
        self.assertEqual(forest.slope_outcome(first_sheer, 1), "sheer")
        self.assertEqual(
            plains.slope_length_for(2, template_length=2, length_cap=1), 1,
        )

    def test_geom_formulas_and_envelope_parts(self) -> None:
        self.assertAlmostEqual(angle_from_height_length(1, 1), 45.0, places=5)
        self.assertEqual(length_from_target_angle(1, 45.0), 1)
        self.assertEqual(length_from_target_angle(4, 45.0), 4)
        self.assertEqual(length_from_target_angle(10, 20.0), 28)
        self.assertAlmostEqual(
            height_from_length_angle(1, 45.0), 1.0, places=5,
        )
        plains = ReliefOntologyEnvelopes.canonical_defaults().plains
        l_min = plains.length_from_min_cells()
        self.assertEqual(
            plains.length_from_max_angle(4),
            length_from_target_angle(4, float(plains.slope_max_angle_deg)),
        )
        self.assertEqual(plains.envelope_length_floor(4), l_min)
        self.assertEqual(plains.envelope_length_floor(10), l_min)
        self.assertEqual(
            plains.length_from_template(4, template_length=2, fallback=l_min), 2,
        )
        self.assertEqual(
            plains.length_from_template(
                4, template_angle_deg=20.0, fallback=l_min,
            ),
            11,
        )
        self.assertEqual(plains.clamp_slope_length(40), 40)
        capped = ReliefTerrainEnvelope(slope_length_max_cells=7)
        self.assertEqual(capped.slope_walk_cap_cells(), 7)
        self.assertAlmostEqual(
            plains.slope_angle_deg(4, l_min),
            math.degrees(math.atan(4 / l_min)),
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

        def z_height_map(xy: tuple[int, int]) -> int | None:
            return z.get(xy)

        length, z_end = measure_terrain_descent(
            start=(2, 0),
            outward=(1, 0),
            z_peak=4,
            z_height_map=z_height_map,
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
        self.assertEqual(d.requested_length, _canonical_plains().length_from_min_cells())

    def test_short_ray_h1_is_slope(self) -> None:
        tpl = _open_land_plains()
        d = grade_constrained(
            template=tpl,
            template_uid="uid",
            terrain_key="plains",
            dz=1,
            world_seed="s",
            site_id="site",
            path_length=1,
        )
        self.assertFalse(d.skipped)
        self.assertEqual(d.kind, ReliefSideKind.SLOPE)
        self.assertEqual(d.requested_length, 1)
        assert d.geom is not None
        self.assertAlmostEqual(d.geom.angle_deg or 0.0, 45.0, places=5)

    def test_short_ray_h2_is_slope(self) -> None:
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
        self.assertEqual(d.kind, ReliefSideKind.SLOPE)
        self.assertEqual(d.requested_length, 1)
        assert d.geom is not None
        self.assertAlmostEqual(
            d.geom.angle_deg or 0.0,
            math.degrees(math.atan(2 / 1)),
            places=5,
        )

    def test_short_ray_kind_follows_envelope_l1(self) -> None:
        plains = _canonical_plains()
        last_slope = _l1_last_slope_abs_dz(plains)
        first_sheer = _l1_first_sheer_abs_dz(plains)
        tpl = _open_land_plains()
        slope = grade_constrained(
            template=tpl,
            template_uid="uid",
            terrain_key="plains",
            dz=last_slope,
            world_seed="s",
            site_id="site",
            path_length=1,
        )
        self.assertFalse(slope.skipped)
        self.assertEqual(slope.kind, ReliefSideKind.SLOPE)
        sheer = grade_constrained(
            template=tpl,
            template_uid="uid",
            terrain_key="plains",
            dz=first_sheer,
            world_seed="s",
            site_id="site",
            path_length=1,
        )
        self.assertFalse(sheer.skipped)
        self.assertEqual(sheer.kind, ReliefSideKind.SHEER)
        self.assertEqual(sheer.requested_length, 1)
        assert sheer.geom is not None
        self.assertEqual(sheer.geom.L, 1)
        self.assertAlmostEqual(
            sheer.geom.angle_deg or 0.0,
            math.degrees(math.atan(first_sheer / 1)),
            places=5,
        )

    def test_open_land_l1_kind_matches_leftover_pair(self) -> None:
        from app.dataModel.terrain.relief.gradeLeftoverPair import leftover_pair_is_sheer

        plains = _canonical_plains()
        for h in range(1, 12):
            outcome = plains.slope_outcome(h, 1)
            if leftover_pair_is_sheer(h):
                self.assertEqual(outcome, "sheer", msg=h)
            else:
                self.assertEqual(outcome, "slope", msg=h)

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
        plains = _canonical_plains()
        l_min = plains.length_from_min_cells()
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
        self.assertEqual(d.requested_length, l_min)
        assert d.geom is not None
        self.assertEqual(d.geom.L, l_min)
        self.assertEqual(sum(d.geom.steps), 4)
        self.assertEqual(len(d.geom.steps), l_min)
        self.assertAlmostEqual(
            d.geom.angle_deg or 0.0,
            math.degrees(math.atan(4 / l_min)),
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
        self.assertEqual(
            d.requested_length, _canonical_plains().length_from_min_cells(),
        )

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

    def test_forest_below_sheer_min_forces_slope_even_if_template_sheer(self) -> None:
        forest = ReliefOntologyEnvelopes.canonical_defaults().forest
        dz = int(forest.sheer_min_abs_dz) - 1
        tpl = _open_land_forest(sheer_weight=1.0)
        d = grade_constrained(
            template=tpl,
            template_uid="uid",
            terrain_key="forest",
            dz=dz,
            world_seed="s",
            site_id="site",
        )
        self.assertFalse(d.skipped)
        self.assertEqual(d.kind, ReliefSideKind.SLOPE)
        self.assertEqual(d.requested_length, forest.length_from_min_cells())

    def test_forest_short_ray_kind_follows_envelope_l1(self) -> None:
        forest = ReliefOntologyEnvelopes.canonical_defaults().forest
        last_slope = _l1_last_slope_abs_dz(forest)
        first_sheer = _l1_first_sheer_abs_dz(forest)
        tpl = _open_land_forest(sheer_weight=0.0)
        slope = grade_constrained(
            template=tpl,
            template_uid="uid",
            terrain_key="forest",
            dz=last_slope,
            world_seed="s",
            site_id="site",
            path_length=1,
        )
        self.assertFalse(slope.skipped)
        self.assertEqual(slope.kind, ReliefSideKind.SLOPE)
        sheer = grade_constrained(
            template=tpl,
            template_uid="uid",
            terrain_key="forest",
            dz=first_sheer,
            world_seed="s",
            site_id="site",
            path_length=1,
        )
        self.assertFalse(sheer.skipped)
        self.assertEqual(sheer.kind, ReliefSideKind.SHEER)
        self.assertEqual(sheer.requested_length, 1)
        assert sheer.geom is not None
        self.assertEqual(sheer.geom.L, 1)
        self.assertEqual(sheer.geom.steps, ())

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
        self.assertEqual(
            d.requested_length,
            ReliefOntologyEnvelopes.canonical_defaults().forest.length_from_min_cells(),
        )

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

    def test_ravine_kind_follows_template_weights(self) -> None:
        """Ravine envelope is pass-through; SHEER vs SLOPE is template knobs, not discover."""
        def ravine_tpl(*, slope_weight: float, sheer_weight: float) -> ReliefTemplate:
            return ReliefTemplate.model_validate({
                "system_name": "ravine_soft",
                "display_name": "Ravine",
                "context": "ravine",
                "slope_length_cells": 2,
                "conditions": [{
                    "terrain": "ravine",
                    "cases": [
                        {
                            "policy": "slope_down",
                            "delta_z": 1,
                            "slope_weight": slope_weight,
                            "sheer_weight": sheer_weight,
                            "slope_length_cells": 2,
                        },
                        {
                            "policy": "slope_up",
                            "delta_z": 1,
                            "slope_weight": 1.0,
                            "sheer_weight": 0.0,
                            "slope_length_cells": 2,
                        },
                        {
                            "policy": "slope_none",
                            "delta_z": 0,
                            "slope_weight": 1.0,
                            "sheer_weight": 0.0,
                        },
                    ],
                }],
            })

        slope = grade_constrained(
            template=ravine_tpl(slope_weight=1.0, sheer_weight=0.0),
            template_uid="uid",
            terrain_key="ravine",
            dz=4,
            world_seed="s",
            site_id="site",
        )
        self.assertFalse(slope.skipped)
        self.assertEqual(slope.kind, ReliefSideKind.SLOPE)
        assert slope.geom is not None
        self.assertEqual(slope.geom.L, 2)

        sheer = grade_constrained(
            template=ravine_tpl(slope_weight=0.0, sheer_weight=1.0),
            template_uid="uid",
            terrain_key="ravine",
            dz=4,
            world_seed="s",
            site_id="site",
        )
        self.assertFalse(sheer.skipped)
        self.assertEqual(sheer.kind, ReliefSideKind.SHEER)
        self.assertEqual(sheer.requested_length, 1)
        assert sheer.geom is not None
        self.assertEqual(sheer.geom.L, 1)

    def test_shore_sea_raises_short_knobs(self) -> None:
        tpl = ReliefTemplate.model_validate({
            "system_name": "shore_soft",
            "display_name": "Shore",
            "context": "shore",
            "slope_length_cells": 2,
            "conditions": [{
                "terrain": "shore_sea",
                "cases": [
                    {
                        "policy": "slope_down",
                        "delta_z": 1,
                        "slope_weight": 1.0,
                        "sheer_weight": 0.0,
                        "slope_length_cells": 2,
                    },
                    {"policy": "slope_up", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                    {"policy": "slope_none", "delta_z": 0, "slope_weight": 1.0, "sheer_weight": 0.0},
                ],
            }],
        })
        d = grade_constrained(
            template=tpl,
            template_uid="uid",
            terrain_key="shore_sea",
            dz=4,
            world_seed="s",
            site_id="site",
        )
        self.assertFalse(d.skipped)
        self.assertEqual(d.kind, ReliefSideKind.SLOPE)
        self.assertGreaterEqual(d.requested_length, 5)

    def test_shore_mountain_river_keeps_steep_l2(self) -> None:
        tpl = ReliefTemplate.model_validate({
            "system_name": "shore_soft",
            "display_name": "Shore",
            "context": "shore",
            "slope_length_cells": 2,
            "conditions": [{
                "terrain": "shore_mountain_river",
                "cases": [
                    {
                        "policy": "slope_down",
                        "delta_z": 1,
                        "slope_weight": 1.0,
                        "sheer_weight": 0.0,
                        "slope_length_cells": 2,
                    },
                    {"policy": "slope_up", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                    {"policy": "slope_none", "delta_z": 0, "slope_weight": 1.0, "sheer_weight": 0.0},
                ],
            }],
        })
        d = grade_constrained(
            template=tpl,
            template_uid="uid",
            terrain_key="shore_mountain_river",
            dz=4,
            world_seed="s",
            site_id="site",
        )
        self.assertFalse(d.skipped)
        self.assertEqual(d.kind, ReliefSideKind.SLOPE)
        self.assertEqual(d.requested_length, 2)


if __name__ == "__main__":
    unittest.main()
