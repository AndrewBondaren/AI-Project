"""Boundary declarations must not enter body geometry, merge, load or carve."""

from unittest import TestCase

from app.application.jsonValidation.resolve import ResolveContext
from app.application.worldData.placement.adapters.water import prepare_water_placements
from app.application.worldData.generators.hydrology.load.loadDeclaredHydrology import load_declared_hydrology, load_prepared_declared_hydrology
from app.application.worldData.generators.hydrology.placement.projectDeclaredHydrology import project_declared_hydrology, project_water_source
from app.application.worldData.generators.hydrology.placement.waterPlacementPass import run_water_placement_pass
from app.application.worldData.generators.hydrology.hydrologyGeneratorService import HydrologyGeneratorService
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from tests.test_water_placement_adapter import basin, coast, context
from tests.hydrology_fixtures import hydro_world, flat_heightmap


def boundary(uid="boundary", target="water-source"):
    return coast(uid, purpose="body_boundary", target_source_uid=target)


class CoastlineRoutingTests(TestCase):
    def test_boundary_is_excluded_before_source_identity_grouping(self):
        hydro = WorldHydrology(declared_basins=[basin("same")], declared_coastlines=[boundary("same")])
        prepared = prepare_water_placements(hydro, context(), ctx=ResolveContext(validate_only=True))
        self.assertEqual(len(prepared.entries), 1)
        self.assertEqual(prepared.entries[0].source.location_uid, "same")
        self.assertEqual(prepared.entries[0].prepared.candidates[0].footprint.cells,
            frozenset((x, y) for x in range(2, 6) for y in range(2, 6)))
        self.assertFalse(prepared.failures)
        self.assertFalse(any(n.code == "WATER_PLACEMENT_MERGED_SOURCES" for n in prepared.notices))

    def test_only_source_lines_enter_body_preparation(self):
        hydro = WorldHydrology(declared_coastlines=[coast("source"), boundary()])
        prepared = prepare_water_placements(hydro, context(auto={"source": 2}), ctx=ResolveContext(validate_only=True))
        self.assertEqual([e.source.location_uid for e in prepared.entries], ["source"])
        self.assertFalse(prepared.failures)

    def test_bulk_body_projection_preserves_absolute_boundary_path_and_binding(self):
        value = DeclaredCoastline.model_validate(boundary())
        hydro = WorldHydrology(declared_coastlines=[value])
        ctx = ResolveContext(validate_only=True)
        projected = project_declared_hydrology(hydro, 100, world_uid="world", ctx=ctx)
        self.assertEqual(projected.declared_coastlines[0], value)
        self.assertFalse(ctx.errors)
        with self.assertRaises(ValueError):
            project_water_source(value, 100)

    def test_declared_loader_does_not_emit_boundary_as_body_or_coastline_paint(self):
        source = DeclaredCoastline.model_validate(coast("source"))
        dependent = DeclaredCoastline.model_validate(boundary())
        loaded = load_prepared_declared_hydrology([source, dependent], [], [], [])
        self.assertEqual([s.location_uid for s in loaded.coastline_specs], ["source"])
        self.assertTrue(loaded.coastline_segments)
        loaded = load_declared_hydrology(hydro_world(hydrology={"declared_coastlines": [boundary()]}), [])
        self.assertEqual(loaded.coastline_specs, [])

    def test_boundary_only_declarations_do_not_require_body_placement_or_specs(self):
        world = hydro_world(hydrology={"enabled": True, "declared_coastlines": [boundary()],
            "default_seas": {"autoresolve_coastal_sea": False, "autoresolve_open_ocean": False},
            "default_lakes": {"autoresolve": False}})
        heightmap = flat_heightmap(0, 10, 0, 10)
        self.assertIsNone(run_water_placement_pass(world, [], heightmap))
        ctx = ResolveContext(collect_only=True)
        HydrologyGeneratorService().apply(world, [], heightmap, ctx=ctx)
        self.assertFalse(any(e.code == "WATER_PLACEMENT_REQUIRED" for e in ctx.errors))
