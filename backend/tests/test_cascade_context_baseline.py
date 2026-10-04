"""S1 characterization before LocationContext wiring (tz_cascade_context §1, §5).

These assertions describe legacy behavior, including its missing inheritance.
S4 must deliberately replace the tier expectations; envelope/barrier policies
remain outside v1. Run this module as a script to save the full local snapshot.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import unittest
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
from random import Random
from unittest.mock import patch

from app.application.worldData.context.locationScope import empty_location_chain
from app.application.worldData.generators.assemblers.areaAssembler.areaSlot import AreaSlot
from app.application.worldData.generators.assemblers.areaAssembler.structureAreaAssembler import derive_structure_context
from app.application.worldData.generators.assemblers.buildingAssembler.structureContext import StructureContext
from app.application.worldData.generators.assemblers.citySkeleton import city_skeleton_from_settlement
from app.application.worldData.generators.assemblers.settlementAssembler.settlementAssembler import SettlementAssembler
from app.application.worldData.generators.assemblers.settlementAssembler.planner.barriers import _pick_template_material
from app.application.worldData.generators.structure import structureGeneratorService as service
from app.application.worldData.generators.structure.foundation.foundationBuilder import FoundationBuilder
from app.application.worldData.generators.structure.roof.roofBuilder import RoofBuilder
from app.application.worldData.generators.utils import materialResolver
from app.application.worldData.generators.utils.tierResolver import TierResolver
from app.dataModel.economy.economyTier.economyTierEntry import EconomyTierEntry
from app.dataModel.locations.context.scopeLevel import ScopeLevel
from app.dataModel.economy.economyTier.worldEconomyTierRegistry import WorldEconomyTierRegistry
from app.dataModel.materials.enums.materialCategory import MaterialCategory
from app.dataModel.materials.materialRegistryEntry import MaterialRegistryEntry
from app.dataModel.materials.worldMaterialRegistry import WorldMaterialRegistry
from app.dataModel.spatial.facing import Facing
from app.dataModel.locations.structure.barrier.barrierTemplateEntry import BarrierTemplateEntry
from app.dataModel.locations.structure.building.plotLayoutTemplate import PlotLayoutTemplate
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from tests.structureWire import level_wire, room_wire


def fixture():
    tiers = WorldEconomyTierRegistry([
        EconomyTierEntry(system_tier=f"t{i}", display_tier=f"Tier {i}", base_value=i * 10)
        for i in range(10)
    ])
    materials = WorldMaterialRegistry([
        MaterialRegistryEntry(
            system_material=f"{use}_{entry.system_tier}", display_name=f"{use} {entry.system_tier}",
            material_category=MaterialCategory.SOLID, tags=["construction"],
            use_type=[use], economic_tier=entry.system_tier,
        )
        for entry in tiers.root for use in ("wall", "floor", "window_glass")
    ])
    world = World(
        world_uid="cascade-baseline-world", name="Cascade baseline", created_at="2026-10-03",
        economic_tier_registry=tiers.model_dump(mode="json"),
        material_registry=materials.model_dump(mode="json"),
    )
    building = NamedLocation(
        location_uid="cascade-baseline-building", world_uid=world.world_uid,
        display_name="Building", system_location_type="building", created_at=world.created_at,
        map_x=20, map_y=30, map_z=7, parent_wall_material="parent_wall",
        parent_floor_material="parent_floor",
    )
    structure = StructureTemplate(
        system_name="00000000-0000-4000-8000-000000000021", display_name="Cascade baseline",
        levels=[
            level_wire(rooms=[room_wire(
                size={"width_range": [11, 15], "depth_range": [9, 13]},
                entry_point={"wall": "south", "passage_type": "main_entrance"},
            )]),
            level_wire(z_offset=1, display_name="Upper", rooms=[room_wire(
                room_id="upper", size={"width_range": [11, 11], "depth_range": [9, 9]},
                economic_tier="t9",
            )]),
        ],
        staircases=[{
            "staircase_id": "stairs", "staircase_type": "u_shape", "stops": ["hall", "upper"],
            "in_a_room": True, "embed_in": "hall", "embed_at": "center",
        }],
    )
    return world, building, structure


def snapshot(*, band=None, building_tier=None):
    world, building, structure = fixture()
    building.system_economic_tier = building_tier
    tier_trace, material_trace, room_trace = [], [], []
    original_tier = TierResolver.resolve
    original_material = materialResolver.resolve_material
    original_rooms = service.instantiate_level_rooms
    original_shafts = service.instantiate_shaft_rooms

    def resolve_tier(*args, **kwargs):
        frame = inspect.currentframe().f_back
        while frame.f_code.co_filename == inspect.getfile(patch):
            frame = frame.f_back
        caller = frame.f_code.co_name
        value = original_tier(*args, **kwargs)
        tier_trace.append({"caller": caller, "tier": value, "room_tier": kwargs.get("room_tier"),
                           "city_supplied": kwargs.get("city") is not None,
                           "district_supplied": kwargs.get("district") is not None})
        return value

    def resolve_material(world, use_type, effective_tier, rng, default, context=""):
        value = original_material(world, use_type, effective_tier, rng, default, context)
        material_trace.append({"use": use_type, "tier": effective_tier, "material": value, "room": context})
        return value

    def record_rooms(fn, *args, **kwargs):
        rooms = fn(*args, **kwargs)
        room_trace.extend({"id": r.room_id, "tier": r.economic_tier, "wall": r.wall_material,
                           "floor": r.floor_material, "size": [r.width, r.depth, r.z_height]}
                          for r in rooms)
        return rooms

    with ExitStack() as stack:
        stack.enter_context(patch.object(TierResolver, "resolve", side_effect=resolve_tier))
        stack.enter_context(patch.object(materialResolver, "resolve_material", side_effect=resolve_material))
        stack.enter_context(patch("app.application.worldData.generators.structure.passages.wallOpening.resolve_material",
                                  side_effect=resolve_material))
        stack.enter_context(patch.object(service, "instantiate_level_rooms",
                                        side_effect=lambda *a, **k: record_rooms(original_rooms, *a, **k)))
        stack.enter_context(patch.object(service, "instantiate_shaft_rooms",
                                        side_effect=lambda *a, **k: record_rooms(original_shafts, *a, **k)))
        layout = service.StructureGeneratorService().generate_from_template(world, building, structure, building_band=band)

    geometry = sorted((c.x, c.y, c.z, c.system_building_element, c.system_facing) for c in layout.cells)
    passages = sorted((p.system_passage_type, p.from_x, p.from_y, p.to_x, p.to_y)
                      for p in layout.passages)
    return {
        "tiers": tier_trace, "materials": material_trace, "rooms": room_trace,
        "named_location_tiers": [r.system_economic_tier for r in layout.rooms],
        "cell_count": len(layout.cells), "passage_count": len(layout.passages),
        "geometry_sha256": hashlib.sha256(json.dumps([geometry, passages]).encode()).hexdigest(),
    }


class CascadeContextBaselineTests(unittest.TestCase):
    def test_null_building_uses_median_in_every_phase_and_does_not_stamp_rooms(self):
        result = snapshot()
        phases = [row["tier"] for row in result["tiers"] if row["caller"] in
                  ("_instantiate_rooms", "_run_passages", "_place_wall_openings")]
        # Two floor calls + shaft call + passages + openings: four code sites, five calls.
        self.assertEqual(phases, ["t5"] * 5)
        self.assertEqual((result["cell_count"], result["passage_count"]), (437, 2))
        self.assertEqual(result["geometry_sha256"],
                         "4fd5a07f79d97aec173a38db42ba536b040c5376d9decf79e2f7faefe2e86ff4")
        self.assertTrue(all(not row["city_supplied"] and not row["district_supplied"]
                            for row in result["tiers"]))
        self.assertEqual([r["tier"] for r in result["rooms"]], [None, "t9", None, None])
        self.assertEqual([r["wall"] for r in result["rooms"]], ["wall_t5", "wall_t9", "wall_t5", "wall_t5"])
        self.assertEqual([r["floor"] for r in result["rooms"]], ["floor_t5", "floor_t9", "floor_t5", "floor_t5"])
        self.assertEqual(set(result["named_location_tiers"]), {None})
        self.assertEqual({m["tier"] for m in result["materials"] if m["use"] == "window_glass"}, {"t5", "t9"})

    def test_band_repeated_resolve_and_shared_rng_snapshot_are_reproducible(self):
        first = snapshot(band="common")
        self.assertEqual(first, snapshot(band="common"))
        phases = [row["tier"] for row in first["tiers"] if row["caller"] in
                  ("_instantiate_rooms", "_run_passages", "_place_wall_openings")]
        self.assertEqual(phases, ["t1", "t1", "t2", "t2", "t2"])
        self.assertEqual((first["cell_count"], first["passage_count"]), (488, 2))
        self.assertEqual(first["geometry_sha256"],
                         "b17ab566a2931a41f398bc896c81cb2b925896ffdab643e1da56a0456418e0c8")
        self.assertEqual([r["wall"] for r in first["rooms"]],
                         ["wall_t1", "wall_t9", "wall_t2", "wall_t2"])
        self.assertNotEqual(first["geometry_sha256"], snapshot()["geometry_sha256"])

    def test_authored_building_wins_and_room_override_reaches_glass(self):
        result = snapshot(band="common", building_tier="t8")
        self.assertEqual({row["tier"] for row in result["tiers"] if row["caller"] in
                          ("_instantiate_rooms", "_run_passages", "_place_wall_openings")}, {"t8"})
        self.assertEqual([r["wall"] for r in result["rooms"]], ["wall_t8", "wall_t9", "wall_t8", "wall_t8"])
        self.assertEqual({m["tier"] for m in result["materials"] if m["use"] == "window_glass"}, {"t8", "t9"})
        self.assertEqual(result["geometry_sha256"], snapshot()["geometry_sha256"])

    def test_plot_authored_tier_wins_over_range_and_band_at_area_scope(self):
        # M2: the formerly dead plot channels are live — the authored
        # economic_tier VALUE resolves at the area boundary and beats
        # the template's range and band (tz_cascade_context §4).
        world, building, structure = fixture()
        settlement = replace(building, location_uid="city", system_location_type="settlement", system_economic_tier="t1")
        skeleton = city_skeleton_from_settlement(settlement, economic_tier="t1")
        slot = AreaSlot(cells=[(20, 30)], ground_z=7, facing=Facing.SOUTH)
        district_ctx = empty_location_chain(world, ScopeLevel.DISTRICT)
        tiers = []
        for tier in ("t2", "t9"):
            plot = PlotLayoutTemplate(
                system_name="plot", display_name="Plot", economic_tier=tier,
                economic_tier_range={"min": "t6", "max": "t9"}, economic_tier_band="common",
                main_building={"structure": structure.system_name},
            )
            context = derive_structure_context(
                world, plot, skeleton, slot, None, ground_z=7,
                district_ctx=district_ctx, area_uid="area", building=building,
            )
            tiers.append(context.location_ctx.economic_tier)
        self.assertEqual(tiers, ["t2", "t9"])
        # The helper's template_tier channel works; roomFactory never supplies it.
        self.assertEqual(materialResolver.resolve_room_materials(world, None, "t2", Random(0)),
                         ("wall_t2", "floor_t2"))

    def test_envelope_material_priority_and_city_barrier_tier_are_outside_cascade(self):
        world, building, _ = fixture()
        for explicit in (False, True):
            context = StructureContext("slab", "flat", foundation_material="foundation" if explicit else None,
                                       roof_material="roof" if explicit else None)
            self.assertEqual(FoundationBuilder(world, building, context, {}, 7).mat,
                             "foundation" if explicit else "parent_wall")
            self.assertEqual(RoofBuilder(world, building, context, 7).mat,
                             "roof" if explicit else "parent_wall")
        settlement = replace(building, system_location_type="settlement", system_economic_tier="t1")
        skeleton = SettlementAssembler()._build_skeleton(world, settlement)
        self.assertEqual(skeleton.economic_tier, "t1")
        self.assertEqual(_pick_template_material(world, BarrierTemplateEntry(system_type="test"), skeleton, Random(0)), "wall_t1")

    def test_warning_only_on_missing_authored_tier(self):
        world, building, _ = fixture()
        with self.assertLogs(TierResolver.__module__, level="WARNING") as captured:
            self.assertEqual(TierResolver.resolve(world=world, building=building), "t5")
        self.assertEqual(len(captured.records), 1)
        building.system_economic_tier = "t8"
        with self.assertNoLogs(TierResolver.__module__, level="WARNING"):
            self.assertEqual(TierResolver.resolve(world=world, building=building), "t8")


if __name__ == "__main__":
    destination = Path(__file__).resolve().parents[2] / ".local" / "cascade-context-s1.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps({"null": snapshot(), "band": snapshot(band="common"),
                                       "authored": snapshot(band="common", building_tier="t8")},
                                      ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(destination)
