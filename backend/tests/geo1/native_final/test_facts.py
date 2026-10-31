from copy import replace
from unittest import TestCase

from app.application.encoding.canonicalCodec import encode, decode
from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.hydrology.planning.assembly.hydrologyFactsAssembler import HydrologyFactsAssembler
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.hydrology.declaredRiver import DeclaredRiver
from app.dataModel.hydrology.planning.hydrologyPlan import GeoHydrologyPlan
from tests.geo1.fine_water.test_fill import source, fill, basin
from tests.geo1.fine_water.fixtures import physical_inputs, decisions
from tests.geo1.source_projection.test_projection import assemble
from tests.geo1.native_relief.test_beds import run
from tests.geo1.terrain_base.fixtures import Control


class NativeFinalTests(TestCase):
    def setUp(self):
        self.before, _, top = source(hills=False)
        river = DeclaredRiver.model_validate(dict(location_uid="river", declare_mode="segments",
            segments=[{"from": dict(x=2, y=11), "to": dict(x=11, y=11), "connection_type": "river"}]))
        self.inputs = replace(physical_inputs(top), enabled=True, declared_rivers=(river,))
        specs = (basin("lake", {(x, y) for y in range(10, 14) for x in range(10, 14)}),)
        self.water = fill(self.before, top, specs, physical=self.inputs)
        self.routes = assemble(self.inputs, self.water, specs, decisions(self.inputs))
        self.river = run(self.inputs, self.water, self.routes)

    def final(self, **changes):
        return HydrologyFactsAssembler().assemble_fine(**(dict(inputs=self.inputs,
            before=self.before.payload, water=self.water.payload, routes=self.routes.payload,
            river=self.river.payload, control=Control()) | changes)).payload

    def test_actual_chain_preserves_unsampled_water_and_reconstructs_final_heights(self):
        before = encode((self.water, self.routes, self.river), SURFACE_MANIFEST)
        result = self.final()
        water = dict(self.water.payload[1].materialized.cells)
        fine = dict(result.sparse_fine_hydro)
        bed_cells = {c for bed in self.river.payload.fine_beds for c, _ in bed.bed_z}
        for cell, fact in water.items():
            if cell not in bed_cells:
                self.assertEqual(fine[cell], fact)
            else:
                self.assertFalse(fact.liquid_candidate)
        route = self.routes.payload.base.fine_routes[0]
        self.assertEqual(fine[route.receiver_cell].water_body_uid, "lake")
        for bed in self.river.payload.fine_beds:
            for cell, _ in bed.bed_z:
                self.assertEqual(fine[cell].water_body_uid, bed.river_uid)
        full = dict(self.water.payload[0].surface_z) | dict(self.river.payload.fine_surface_z)
        self.assertEqual(dict(self.before.payload.surface_z) | dict(result.fine_z_overrides), full)
        self.assertEqual(result.source_mapping, self.water.payload[1].materialized.source_mapping)
        self.assertEqual(result.water_bodies, self.water.payload[1].materialized.bodies)
        self.assertEqual(decode(encode(result, SURFACE_MANIFEST), GeoHydrologyPlan, SURFACE_MANIFEST), result)
        self.assertEqual(encode((self.water, self.routes, self.river), SURFACE_MANIFEST), before)

    def test_coarse_facts_are_exact_samples_of_merged_fine_facts(self):
        result = self.final()
        fine, span = dict(result.sparse_fine_hydro), self.inputs.grid.fine_span
        expected = tuple((c, fine[c.gx*span+span//2, c.gy*span+span//2]) for c, _ in result.coarse_surface_z
                         if (c.gx*span+span//2, c.gy*span+span//2) in fine)
        self.assertEqual(result.coarse_hydro, expected)
        self.assertFalse(self.routes.payload.base.coarse_open_water)
        top = self.before.payload.topology
        river = DeclaredRiver.model_validate(dict(location_uid="sampled-river", declare_mode="segments",
            segments=[{"from": dict(x=8, y=8), "to": dict(x=24, y=8), "connection_type": "river"}]))
        inputs = replace(self.inputs, declared_rivers=(river,))
        specs = (basin("lake", {(x, y) for y in range(8, 12) for x in range(24, 28)}),)
        water = fill(self.before, top, specs, physical=inputs)
        routes = assemble(inputs, water, specs, decisions(inputs))
        relief = run(inputs, water, routes)
        sampled = self.final(inputs=inputs, water=water.payload, routes=routes.payload, river=relief.payload)
        by_coord = {(c.gx, c.gy): v for c, v in sampled.coarse_hydro}
        self.assertEqual(by_coord[1, 0].water_body_uid, "lake")
        merged = dict(sampled.sparse_fine_hydro)
        self.assertEqual(by_coord, {(c.gx, c.gy): merged[c.gx*span+span//2, c.gy*span+span//2]
            for c, _ in sampled.coarse_surface_z if (c.gx*span+span//2, c.gy*span+span//2) in merged})

    def test_missing_actual_beds_fail(self):
        with self.assertRaisesRegex(ValueError, "outside actual beds"):
            self.final(river=replace(self.river.payload, fine_beds=()))

    def test_fine_receiver_cannot_be_fabricated_from_coarse_membership(self):
        receiver = self.routes.payload.base.fine_routes[0].receiver_cell
        window, assembled = self.water.payload
        missing = replace(assembled.materialized, cells=tuple(row for row in assembled.materialized.cells if row[0] != receiver))
        with self.assertRaises(PlanBuildFailure):
            self.final(water=(window, replace(assembled, materialized=missing)))

    def test_inconsistent_coarse_geometry_and_disabled_input_fail(self):
        cell, z = self.river.payload.surface_z[0]
        bad = replace(self.river.payload, surface_z=((cell, z+1), *self.river.payload.surface_z[1:]))
        with self.assertRaises(ValueError):
            self.final(river=bad)
        with self.assertRaises(ValueError):
            self.final(inputs=replace(self.inputs, enabled=False))

    def test_cancellation(self):
        class Stop:
            def raise_if_shutdown(self):
                raise InterruptedError()
        with self.assertRaises(InterruptedError):
            self.final(control=Stop())
