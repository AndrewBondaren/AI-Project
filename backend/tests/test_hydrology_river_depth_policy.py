"""Review-debt R-4: POJO depth in cells drives both river materializers."""

import unittest

from pydantic import ValidationError

from app.application.jsonValidation.facade import normalize_world
from app.application.jsonValidation.resolve import UnresolvedModelError
from app.application.jsonValidation.types import ImportValidationError
from app.application.jsonValidation.worldRow import hydrology
from app.application.worldData.generators.coordinates.space import CoordinateSpace
from app.application.worldData.generators.hydrology.riverNetworkAssembler import assemble_rivers
from app.application.worldData.generators.hydrology.rivers.riverBedProfile import river_bed_spec
from app.application.worldData.generators.hydrology.shore.fineHydrologyIndex import apply_declared_fine_river_carves
from app.application.worldData.generators.hydrology.types import DeclaredRiverEdge, RiverSegment
from app.dataModel.hydrology.declaredRiver import DeclaredRiver
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType as Connection
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.rivers import HydrologyRiversPolicy, RiverTypeClassify
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from tests.hydrology_fixtures import heightmap_from_z, hydro_master, hydro_topology, hydro_world, river_segments_wire, waypoint


class RiverDepthPolicyTests(unittest.TestCase):
    def test_missing_depth_uses_pojo_default_through_wire_and_runtime(self):
        self.assertEqual(HydrologyRiversPolicy().channel_depth_cells, 3)
        normalized = normalize_world({"hydrology": {}})
        self.assertEqual(normalized["hydrology"]["default_rivers"]["channel_depth_cells"], 3)
        self.assertEqual(hydrology(hydro_world(hydrology={})).default_rivers.channel_depth_cells, 3)

    def test_supplied_depth_roundtrips_and_overrides_default(self):
        normalized = normalize_world({"hydrology": {"default_rivers": {"channel_depth_cells": 7}}})
        policy = hydrology(hydro_world(hydrology=normalized["hydrology"])).default_rivers
        self.assertEqual(policy.channel_depth_for(Connection.RIVER), 7)
        self.assertEqual(HydrologyRiversPolicy.model_validate_json(policy.model_dump_json()), policy)

    def test_invalid_depth_is_not_coerced_or_replaced_with_default(self):
        for value in (None, 0, -1, True, "3", 3.5, 3.0):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                HydrologyRiversPolicy.model_validate({"channel_depth_cells": value})

    def test_invalid_supplied_depth_rejects_import_and_runtime(self):
        raw = {"default_rivers": {"channel_depth_cells": None}}
        with self.assertRaises(ImportValidationError):
            normalize_world({"hydrology": raw})
        with self.assertRaises(UnresolvedModelError):
            hydrology(hydro_world(hydrology=raw))

    def test_mountain_multiplier_rounding_and_positive_minimum(self):
        self.assertEqual(HydrologyRiversPolicy().channel_depth_for(Connection.MOUNTAIN_RIVER), 4)
        policy = HydrologyRiversPolicy(channel_depth_cells=6,
            type_classify=RiverTypeClassify(mountain_bed_steepness_factor=2.0))
        self.assertEqual(policy.channel_depth_for(Connection.MOUNTAIN_RIVER), 12)
        shallow = HydrologyRiversPolicy(channel_depth_cells=1,
            type_classify=RiverTypeClassify(mountain_bed_steepness_factor=0.1))
        self.assertEqual(shallow.channel_depth_for(Connection.MOUNTAIN_RIVER), 1)

    def test_non_river_kind_cannot_silently_use_lowland_depth(self):
        with self.assertRaises(ValueError):
            HydrologyRiversPolicy().channel_depth_for(Connection.COASTLINE)

    def test_coarse_and_fine_read_custom_pojo_depth_and_preserve_mouth(self):
        cases = ((Connection.RIVER, 7, 1.5, 13), (Connection.MOUNTAIN_RIVER, 6, 2.0, 8))
        for kind, depth, factor, expected_z in cases:
            with self.subTest(kind=kind):
                policy = WorldHydrology(default_rivers=HydrologyRiversPolicy(
                    autoresolve=False, channel_depth_cells=depth,
                    type_classify=RiverTypeClassify(mountain_bed_steepness_factor=factor)),
                    declared_rivers=[DeclaredRiver.model_validate(river_segments_wire(segments=[{
                        "from": waypoint(0, 0), "to": waypoint(3, 0),
                        "connection_type": kind.value, "width_cells": 1,
                    }]))])
                world = hydro_world(fine_cells_per_map_cell=1, hydrology=policy.model_dump(mode="json"))
                original = {(x, 0): 20 for x in range(4)}
                hm = heightmap_from_z(original)
                topology = hydro_topology(hm)
                occupied = {(3, 0): MapCellHydrology(role=HydrologyCellRole.LAKE, water_body_uid="lake")}
                master = hydro_master(declared_river_edges=[
                    DeclaredRiverEdge("river-edge", ((0, 0), (3, 0)), kind.value)])
                coarse = assemble_rivers(world, hm, master, occupied, topology=topology)
                fine, fine_z = apply_declared_fine_river_carves(world, [], original, topology=topology,
                    base_space=CoordinateSpace.WORLD_SURFACE_GRID, coarse_hydro=occupied)
                self.assertEqual(hm.surface_z[(1, 0)], expected_z)
                self.assertEqual(fine_z, hm.surface_z)
                self.assertEqual(set(fine), set(coarse.by_cell))
                self.assertEqual(fine_z[(3, 0)], original[(3, 0)])
                self.assertEqual(original[(1, 0)], 20)

    def test_profile_clamp_never_raises_existing_floor_below_z_min(self):
        hm = heightmap_from_z({(0, 0): -10, (1, 0): 1})
        spec = river_bed_spec(hm, RiverSegment([(0, 0), (1, 0)], Connection.RIVER.value),
            depth_step=HydrologyRiversPolicy().channel_depth_for(Connection.RIVER),
            z_min=0, occupied={})
        self.assertEqual(spec.bed_z, (((0, 0), -10), ((1, 0), 0)))
        self.assertEqual(hm.surface_z, {(0, 0): -10, (1, 0): 1})


if __name__ == "__main__":
    unittest.main()
