"""Consumers aggregate prepared observations without domain execution or defaults."""

from dataclasses import replace
from types import MappingProxyType
import unittest

from app.application.worldData.generators.climate.climateAnchor import AnchorSource, ClimateAnchorPoint
from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.regions.coverageResolver import resolve
from app.application.worldData.regions.factConsumers import FACT_CONSUMERS, collect_facts
from app.application.worldData.regions.factConsumers.context import FactConsumerContext
from app.application.worldData.generators.climate.materialize.climateWorkingFields import ClimateWorkingFields
from app.application.worldData.generators.hydrology.materialize.hydrologyWorkingFields import HydrologyWorkingFields
from app.application.worldData.generators.terrain.materialize.terrainWorkingFields import TerrainWorkingFields
from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from tests.planning.consumers.test_wiring import Composition, capture, world
from app.application.worldData.regions.regionFacts import DeclarationFacts, RegionFacts
from app.dataModel.climate.enums.climateZone import ClimateZone
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry


class RegionFactConsumerTests(unittest.TestCase):
    def setUp(self):
        profiles = [ClimateZone.TEMPERATE.to_profile(), ClimateZone.ARCTIC.to_profile()]
        self.profiles = {p.system_climate: p for p in profiles}
        self.cells = ((0, 0), (1, 0))
        anchors = tuple(ClimateAnchorPoint(x, y, profile.system_climate, None, AnchorSource.MANUAL)
                        for (x, y), profile in zip(self.cells, profiles))
        composition = Composition()
        self.addCleanup(composition.service.shutdown)
        self.bundle = composition.prepare(capture(world(climate_zone_registry=[vars(p) for p in profiles])))
        self.local = self.bundle.climate_local.payload.model_copy(update={"anchors": anchors})
        self.climate = ClimateWorkingFields.from_plans(self.bundle.climate_base.payload, self.local,
            lambda key: self.profiles[key])
        self.relief = {(0, 0): 5, (1, 0): 5}
        self.heights = {(0, 0): 2, (1, 0): 5}
        self.hydro = {(0, 0): MapCellHydrology(role=HydrologyCellRole.LAKE)}
        self.context = self.project()

    def project(self):
        plan = self.bundle.hydrology.payload.model_copy(update={
            "coarse_hydro": tuple((SurfaceGridCoord(*xy), value) for xy, value in self.hydro.items()),
            "coarse_surface_z": tuple((SurfaceGridCoord(*xy), value) for xy, value in self.heights.items())})
        hydrology = HydrologyWorkingFields.from_plan(plan, SurfaceGridSettings(fine_span=1000, light_side=2))
        return FactConsumerContext(cells=self.cells, climate=self.climate,
            terrain=TerrainWorkingFields(MappingProxyType(dict(self.relief))), hydrology=hydrology)

    def test_collects_typed_domains_keeps_unobserved_channels_unknown(self):
        declaration = DeclarationFacts(present=True, strength=2)
        facts = collect_facts(self.context, declaration=declaration, elapsed_ticks=7)
        self.assertEqual(facts.climate.rainfall, sum(p.base_rainfall for p in self.profiles.values()) / 2)
        self.assertEqual(facts.hydrology.open_water_fraction, .5)
        self.assertTrue(facts.relief.elevation_plain)
        self.assertEqual(facts.relief.elevation_mean, 5)
        self.assertIsNone(facts.relief.lowland_fraction)
        self.assertIsNone(facts.hydrology.water_table)
        self.assertIsNone(facts.hydrology.flooding)
        self.assertIsNone(facts.climate.drought_trend)
        self.assertIsNone(facts.flora)
        self.assertIs(facts.declaration, declaration)
        self.assertEqual(facts.elapsed_ticks, 7)
        self.assertNotIn("flora", [consumer.name for consumer in FACT_CONSUMERS])

    def test_missing_surface_empty_scope_and_unregistered_domains(self):
        self.assertEqual(collect_facts(replace(self.context, climate=None, terrain=None, hydrology=None)), RegionFacts())
        self.assertEqual(collect_facts(replace(self.context, cells=())), RegionFacts())
        self.assertEqual(collect_facts(self.context, consumers=()), RegionFacts())
        self.assertIsNone(collect_facts(replace(self.context, climate=None)).climate)

    def test_scope_permutations_duplicates_and_bake_extent_do_not_change_facts(self):
        facts = collect_facts(self.context)
        self.assertEqual(facts, collect_facts(replace(self.context, cells=tuple(reversed(self.cells)))))
        self.assertEqual(facts, collect_facts(replace(self.context, cells=self.cells * 2)))
        self.relief[(500, 500)] = 1000
        self.heights[(500, 500)] = 1000
        self.assertEqual(facts, collect_facts(self.project()))

    def test_incomplete_observations_do_not_invent_values_or_partial_averages(self):
        empty = ClimateWorkingFields.from_plans(self.bundle.climate_base.payload,
            self.local.model_copy(update={"anchors": ()}), lambda key: self.profiles[key])
        self.assertIsNone(collect_facts(replace(self.context, climate=empty)).climate)
        self.relief.pop((1, 0))
        self.assertIsNone(collect_facts(self.project()).relief)
        self.hydro = {}
        self.assertIsNone(collect_facts(self.project()).hydrology)

    def test_same_resolver_handles_region_and_cell_facts(self):
        registry = WorldTerrainRegistry.canonical_defaults()
        region = collect_facts(self.context)
        cell = collect_facts(replace(self.context, cells=((1, 0),)))
        self.assertIsNotNone(resolve(region, registry))
        self.assertEqual(resolve(cell, registry).target_key, registry.plains_terrain_key())
        self.assertEqual(cell.hydrology.open_water_fraction, 0)
        self.assertIsNone(cell.relief.elevation_plain)  # One height cannot prove flatness.


if __name__ == "__main__":
    unittest.main()
