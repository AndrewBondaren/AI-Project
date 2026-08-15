"""Unit: R36p/q canal registry, knobs XOR, typed Canal resolve."""

from __future__ import annotations

import unittest

from app.application.worldData.generators.terrain.relief.canal.attachments import (
    aggregate_canals,
    build_canal,
    resolve_knobs_canal,
)
from app.application.worldData.generators.terrain.relief.canal.obstacleResolve import (
    canal_entity_from_terrain,
    resolve_canal_obstacle_cut,
)
from app.application.worldData.generators.terrain.relief.canal.seedResolve import (
    resolve_seed_canal,
)
from app.dataModel.terrain.relief import (
    CanalObstacleEntity,
    CanalObstaclePolicyRule,
    CanalTemplateEntry,
    EarthenCanal,
    ReliefGradeKnobs,
    StructureCanal,
    WorldCanalTemplateRegistry,
    WorldReliefPickPolicy,
)


class CanalKnobsXorTest(unittest.TestCase):
    def test_earthen_ok(self) -> None:
        knobs = ReliefGradeKnobs.model_validate({
            "slope_weight": 1.0,
            "sheer_weight": 0.0,
            "earthen_canal": True,
        })
        self.assertTrue(knobs.earthen_canal)
        self.assertIsNone(knobs.structure_canal)

    def test_structure_canal_ok(self) -> None:
        knobs = ReliefGradeKnobs.model_validate({
            "slope_weight": 1.0,
            "sheer_weight": 0.0,
            "structure_canal": "forest_ditch",
        })
        self.assertEqual(knobs.structure_canal, "forest_ditch")
        self.assertIsNone(knobs.earthen_canal)

    def test_omit_earthen(self) -> None:
        knobs = ReliefGradeKnobs.model_validate({
            "slope_weight": 1.0,
            "sheer_weight": 0.0,
        })
        self.assertIsNone(knobs.earthen_canal)

    def test_both_reject(self) -> None:
        with self.assertRaises(Exception):
            ReliefGradeKnobs.model_validate({
                "slope_weight": 1.0,
                "sheer_weight": 0.0,
                "earthen_canal": True,
                "structure_canal": "forest_ditch",
            })

    def test_structure_canal_rejects_flat_refs(self) -> None:
        with self.assertRaises(Exception):
            ReliefGradeKnobs.model_validate({
                "slope_weight": 1.0,
                "sheer_weight": 0.0,
                "structure_canal": "forest_ditch",
                "structure_refs": ["fence_wood"],
            })


class CanalEntryXorTest(unittest.TestCase):
    def test_entry_both_reject(self) -> None:
        with self.assertRaises(Exception):
            CanalTemplateEntry.model_validate({
                "system_type": "x",
                "earthen_canal": True,
                "structure": {"structure_refs": ["a"]},
            })

    def test_entry_neither_reject(self) -> None:
        with self.assertRaises(Exception):
            CanalTemplateEntry.model_validate({"system_type": "x"})


class CanalRegistryResolveTest(unittest.TestCase):
    def test_resolve_structure_canal(self) -> None:
        reg = WorldCanalTemplateRegistry.model_validate([
            {
                "system_type": "lined_cut",
                "structure": {"structure_refs": ["lined_canal_stone"]},
            },
        ])
        canal = resolve_knobs_canal(
            earthen_canal=None,
            structure_canal="lined_cut",
            structure_refs=(),
            registry=reg,
        )
        self.assertIsInstance(canal, StructureCanal)
        assert isinstance(canal, StructureCanal)
        self.assertEqual(canal.structure_refs, ["lined_canal_stone"])
        self.assertEqual(canal.system_type, "lined_cut")
        drawn = build_canal(canal)
        self.assertFalse(drawn.earthen_canal)
        self.assertEqual(drawn.structure_refs, ("lined_canal_stone",))


class CanalObstaclePolicyTest(unittest.TestCase):
    def test_entity_from_terrain(self) -> None:
        self.assertEqual(
            canal_entity_from_terrain("forest"), CanalObstacleEntity.FOREST,
        )
        self.assertIsNone(canal_entity_from_terrain("swamp"))

    def test_enable_true(self) -> None:
        rules = [
            CanalObstaclePolicyRule.model_validate({
                "to_canal_cut_enable": True,
                "entities": ["forest"],
                "canal_ref": "forest_ditch",
            }),
        ]
        cut = resolve_canal_obstacle_cut(
            entity=CanalObstacleEntity.FOREST, rules=rules,
        )
        self.assertTrue(cut.enable)
        self.assertEqual(cut.canal_ref, "forest_ditch")

    def test_false_wins(self) -> None:
        rules = [
            CanalObstaclePolicyRule.model_validate({
                "to_canal_cut_enable": True,
                "entities": ["all"],
                "canal_ref": "a",
            }),
            CanalObstaclePolicyRule.model_validate({
                "to_canal_cut_enable": False,
                "entities": ["forest"],
            }),
        ]
        cut = resolve_canal_obstacle_cut(
            entity=CanalObstacleEntity.FOREST, rules=rules,
        )
        self.assertFalse(cut.enable)

    def test_pick_policy_parses_canal_block(self) -> None:
        policy = WorldReliefPickPolicy.model_validate({
            "road_shoulder": {"mode": "random"},
            "canal_obstacle_policy": [
                {
                    "to_canal_cut_enable": True,
                    "entities": ["forest"],
                    "canal_ref": "forest_ditch",
                },
            ],
        })
        self.assertEqual(len(policy.canal_obstacle_policy), 1)
        self.assertEqual(
            policy.canal_obstacle_policy[0].entities,
            [CanalObstacleEntity.FOREST],
        )

    def test_canal_ref_rejects_when_disabled(self) -> None:
        with self.assertRaises(Exception):
            CanalObstaclePolicyRule.model_validate({
                "to_canal_cut_enable": False,
                "entities": ["forest"],
                "canal_ref": "x",
            })

    def test_conflicting_canal_ref_on_policy(self) -> None:
        with self.assertRaises(Exception):
            WorldReliefPickPolicy.model_validate({
                "canal_obstacle_policy": [
                    {
                        "to_canal_cut_enable": True,
                        "entities": ["forest"],
                        "canal_ref": "a",
                    },
                    {
                        "to_canal_cut_enable": True,
                        "entities": ["all"],
                        "canal_ref": "b",
                    },
                ],
            })


class SeedCanalResolveTest(unittest.TestCase):
    def test_fit_uses_knobs(self) -> None:
        reg = WorldCanalTemplateRegistry.canonical_defaults()
        canal = resolve_seed_canal(
            requested_length=3,
            L_eff=3,
            terrain_key="forest",
            knobs_earthen=True,
            knobs_structure_canal=None,
            policy_rules=[],
            registry=reg,
            site_id="s1",
        )
        self.assertIsInstance(canal, EarthenCanal)

    def test_not_fit_uses_policy(self) -> None:
        reg = WorldCanalTemplateRegistry.model_validate([
            {"system_type": "forest_ditch", "earthen_canal": True},
        ])
        rules = [
            CanalObstaclePolicyRule.model_validate({
                "to_canal_cut_enable": True,
                "entities": ["forest"],
                "canal_ref": "forest_ditch",
            }),
        ]
        canal = resolve_seed_canal(
            requested_length=3,
            L_eff=1,
            terrain_key="forest",
            knobs_earthen=False,
            knobs_structure_canal=None,
            policy_rules=rules,
            registry=reg,
            site_id="s1",
        )
        self.assertIsInstance(canal, EarthenCanal)
        assert isinstance(canal, EarthenCanal)
        self.assertEqual(canal.system_type, "forest_ditch")

    def test_aggregate_union(self) -> None:
        canal = aggregate_canals([
            StructureCanal(system_type="c1", structure_refs=["a"]),
            StructureCanal(system_type="c1", structure_refs=["b", "a"]),
        ])
        self.assertIsInstance(canal, StructureCanal)
        assert isinstance(canal, StructureCanal)
        self.assertEqual(canal.structure_refs, ["a", "b"])

    def test_unknown_structure_canal_r21(self) -> None:
        reg = WorldCanalTemplateRegistry.canonical_defaults()
        canal = resolve_seed_canal(
            requested_length=2,
            L_eff=2,
            terrain_key="plains",
            knobs_earthen=None,
            knobs_structure_canal="missing_canal",
            policy_rules=[],
            registry=reg,
            site_id="s-unknown",
        )
        self.assertIsInstance(canal, StructureCanal)
        assert isinstance(canal, StructureCanal)
        self.assertEqual(canal.system_type, "missing_canal")
        self.assertEqual(canal.structure_refs, [])


if __name__ == "__main__":
    unittest.main()
