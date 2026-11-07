from unittest import TestCase

from pydantic import ValidationError

from app.application.encoding.boundedCanonicalDecode import decode_bounded
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.encoding.decodeLimits import DecodeLimits
from app.dataModel.hydrology import waterDiagnostics as w
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnosticDisposition as D
from app.encoding.canonicalCodec import CanonicalEncodingError, encode


class WaterDiagnosticsTests(TestCase):
    def test_admission_and_wire_roster(self):
        C = w.WaterDiagnosticCode
        cases = (
            (w.WaterPuddle, w.WaterPuddleDiagnostic, C.WATER_PUDDLE, D.ERROR, dict(source_uid="a", cell_count=1, minimum_cells=2)),
            (w.WaterCannotHold, w.WaterCannotHoldDiagnostic, C.WATER_CANNOT_HOLD, D.ERROR, dict(source_uid="a", effective_level=3)),
            (w.WaterTerrainUnresolved, w.WaterTerrainUnresolvedDiagnostic, C.WATER_TERRAIN_UNRESOLVED, D.ERROR, dict(world_uid="w", message="terrain")),
            (w.WaterNoOceanDepression, w.WaterNoOceanDepressionDiagnostic, C.WATER_NO_OCEAN_DEPRESSION, D.ERROR, dict(world_uid="w", default_water_level=0)),
            (w.WaterLevelSpill, w.WaterLevelSpillDiagnostic, C.WATER_LEVEL_SPILL, D.FALLBACK, dict(source_uid="a", requested_level=5, spill_limited_level=2)),
            (w.WaterLevelSuperseded, w.WaterLevelSupersededDiagnostic, C.WATER_LEVEL_SUPERSEDED, D.FALLBACK, dict(source_uid="a", declared_level=2, effective_level=8, parent_system_uid=None)),
            (w.WaterWorldOcean, w.WaterWorldOceanDiagnostic, C.WATER_WORLD_OCEAN, D.NOTICE, dict(world_uid="w", water_cells=2, world_cells=4)),
            (w.WaterPlacementRequired, w.WaterPlacementRequiredDiagnostic, C.WATER_PLACEMENT_REQUIRED, D.ERROR, dict(world_uid="w")),
        )
        for fact, carrier, code, expected, fields in cases:
            with self.subTest(code=code):
                issue = fact(code=code, **fields)
                for disposition in D:
                    if disposition != expected:
                        with self.assertRaises(ValidationError):
                            carrier(issue=issue, disposition=disposition)
                with self.assertRaises(ValidationError):
                    fact(code=code.value, **fields)
                diagnostic = carrier(issue=issue, disposition=expected)
                result = PlanBuildResult[int](payload=1, diagnostics=(diagnostic,))
                self.assertIs(type(result.diagnostics[0]), carrier)
                if code is C.WATER_PLACEMENT_REQUIRED:
                    with self.assertRaises(CanonicalEncodingError):
                        encode(diagnostic, SURFACE_MANIFEST)
                else:
                    wire = encode(diagnostic, SURFACE_MANIFEST)
                    self.assertEqual(decode_bounded(wire, carrier, SURFACE_MANIFEST,
                        limits=DecodeLimits(100000, 10000, 100, 1024)), diagnostic)

    def test_invalid_water_facts(self):
        C = w.WaterDiagnosticCode
        for fact, fields in (
            (w.WaterLevelSpill, dict(code=C.WATER_LEVEL_SPILL, source_uid="a", requested_level=2, spill_limited_level=2)),
            (w.WaterLevelSuperseded, dict(code=C.WATER_LEVEL_SUPERSEDED, source_uid="a", declared_level=2, effective_level=2, parent_system_uid=None)),
            (w.WaterPuddle, dict(code=C.WATER_PUDDLE, source_uid="a", cell_count=1, minimum_cells=1)),
            (w.WaterWorldOcean, dict(code=C.WATER_WORLD_OCEAN, world_uid="w", water_cells=1, world_cells=3)),
            (w.WaterCannotHold, dict(code=C.WATER_CANNOT_HOLD, source_uid="a", effective_level=True)),
        ):
            with self.subTest(fact=fact), self.assertRaises(ValidationError):
                fact(**fields)
