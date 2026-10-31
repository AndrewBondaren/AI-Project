from copy import replace
from unittest import TestCase
from unittest.mock import patch

from app.application.encoding.canonicalCodec import encode
from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.hydrology.query.nativeFinalWaterQuery import NativeFinalWaterQuery
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.policy.policyFacts import KnownFact, UnknownFact
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from tests.geo1.final_publication import test_publication as published
from tests.geo1.source_projection.test_projection import resign
from tests.geo1.terrain_base.fixtures import Control


class QueryTests(TestCase):
    def setUp(self):
        published.PublicationTests.setUp(self)
        self.final = published.PublicationTests.publish(self)

    def query(self, **changes):
        return NativeFinalWaterQuery(**(dict(final=self.final, water=self.water,
            expected_final=self.final.ref, expected_water=self.water.ref, control=Control()) | changes))

    def test_actual_pipeline_distinguishes_water_river_dry_and_unknown(self):
        before = encode((self.final, self.water), SURFACE_MANIFEST)
        query = self.query()
        route = self.routes.payload.base.fine_routes[0]
        self.assertEqual(query.water_at(route.receiver_cell).value, "lake")
        bed_cell = self.river.payload.fine_beds[0].bed_z[0][0]
        self.assertEqual(query.water_at(bed_cell).value, "river")
        self.assertIsNone(query.water_at((0, 0)).value)
        self.assertIsInstance(query.water_at((-1, -1)), UnknownFact)
        self.assertIsInstance(query.water_at((10000, 10000)), UnknownFact)
        beds = {c for b in self.river.payload.fine_beds for c, _ in b.bed_z}
        shore = next(c for c, fact in self.water.payload[1].materialized.cells
                     if fact.role is HydrologyCellRole.SHORE and c not in beds)
        self.assertIsNone(query.water_at(shore).value)
        self.assertEqual(encode((self.final, self.water), SURFACE_MANIFEST), before)
        self.assertTrue(self.final.diagnostics)  # Route errors do not erase successful physical observation.

    def test_reads_do_not_scan_hash_or_revalidate_sources(self):
        query = self.query()
        class Indexed(tuple):
            def __iter__(self):
                raise AssertionError("query scanned all observations")
        query._rows = Indexed(query._rows)
        query._coverage = Indexed(query._coverage)
        with patch("app.application.worldData.generators.hydrology.query.nativeFinalWaterQuery.output_fingerprint",
                   side_effect=AssertionError("rehash")):
            for _ in range(20):
                self.assertEqual(query.water_at(self.routes.payload.base.fine_routes[0].receiver_cell).value, "lake")
                self.assertIsNone(query.water_at((0, 0)).value)

    def test_stale_foreign_and_tampered_sources_are_rejected(self):
        with self.assertRaises(ValueError):
            self.query(expected_water=self.before.ref)
        with self.assertRaises(ValueError):
            self.query(expected_final=self.before.ref)
        with self.assertRaises(ValueError):
            self.query(final=replace(self.final, diagnostics=()))
        foreign = resign(self.water, ref=replace(self.water.ref, key=replace(self.water.ref.key, world_uid="other")))
        with self.assertRaises(ValueError):
            self.query(water=foreign, expected_water=foreign.ref)

    def test_missing_dependency_is_not_dry(self):
        final = resign(self.final, dependencies=())
        with self.assertRaises(ValueError):
            self.query(final=final, expected_final=final.ref)

    def test_source_error_blocks_even_if_final_references_it(self):
        issue = PlanDiagnostic(issue=FieldPathError(("water",), "failed"), disposition=PlanDiagnosticDisposition.ERROR)
        water = resign(self.water, diagnostics=(*self.water.diagnostics, issue))
        deps = tuple(replace(d, ref=water.ref) if d.slot == "fine_water" else d for d in self.final.dependencies)
        final = resign(self.final, dependencies=deps)
        with self.assertRaises(PlanBuildFailure):
            self.query(final=final, expected_final=final.ref, water=water, expected_water=water.ref)

    def test_cancellation_during_admission(self):
        class Stop:
            def raise_if_shutdown(self):
                raise InterruptedError()
        with self.assertRaises(InterruptedError):
            self.query(control=Stop())
