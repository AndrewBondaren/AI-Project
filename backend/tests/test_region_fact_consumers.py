"""Consumers aggregate prepared observations without domain execution or defaults."""

from dataclasses import replace
from types import SimpleNamespace
import unittest

from app.application.worldData.generators.climate.climateAnchor import AnchorSource, ClimateAnchorPoint
from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.regions.coverageResolver import resolve
from app.application.worldData.regions.factConsumers import FACT_CONSUMERS, collect_facts
from app.application.worldData.regions.factConsumers.context import FactConsumerContext
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
        self.surface = SimpleNamespace(
            local_field=ClimateAnchorField(anchors),
            coarse_hydro={(0, 0): MapCellHydrology(role=HydrologyCellRole.LAKE)},
            coarse_relief_z={(0, 0): 5, (1, 0): 5},
            coarse_surface_z={(0, 0): 2, (1, 0): 5},
        )
        self.context = FactConsumerContext(self.surface, self.cells, self.profiles)

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
        self.assertEqual(collect_facts(replace(self.context, surface=None)), RegionFacts())
        self.assertEqual(collect_facts(replace(self.context, cells=())), RegionFacts())
        self.assertEqual(collect_facts(self.context, consumers=()), RegionFacts())
        self.assertIsNone(collect_facts(replace(self.context, climate_profiles=None)).climate)

    def test_scope_permutations_duplicates_and_bake_extent_do_not_change_facts(self):
        facts = collect_facts(self.context)
        self.assertEqual(facts, collect_facts(replace(self.context, cells=tuple(reversed(self.cells)))))
        self.assertEqual(facts, collect_facts(replace(self.context, cells=self.cells * 2)))
        self.surface.coarse_relief_z[(500, 500)] = 1000
        self.surface.coarse_surface_z[(500, 500)] = 1000
        self.assertEqual(facts, collect_facts(self.context))

    def test_incomplete_observations_do_not_invent_values_or_partial_averages(self):
        self.assertIsNone(collect_facts(replace(self.context, climate_profiles={})).climate)
        self.surface.coarse_relief_z.pop((1, 0))
        self.assertIsNone(collect_facts(self.context).relief)
        self.surface.coarse_hydro = {}
        self.assertIsNone(collect_facts(self.context).hydrology)

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
