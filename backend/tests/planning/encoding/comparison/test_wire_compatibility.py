"""Water and River reference bytes captured before splitting surfaceManifest."""
import unittest
from pathlib import Path

from app.application.planning.service.planFingerprints import output_fingerprint
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
from app.dataModel.hydrology.riverRouting import (
    RiverPlanDiagnostic, RiverRouteDiagnostic, RiverRoutingCode, RiverRoutingFailure,
)
from app.dataModel.hydrology.waterDiagnostics import WaterDiagnosticCode, WaterLevelSpill, WaterLevelSpillDiagnostic
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnosticDisposition
from app.encoding.canonicalCodec import encode


class WireCompatibilityTests(unittest.TestCase):
    def assert_reference(self, sample, diagnostic, fingerprint):
        path = Path(__file__).with_name("fixtures") / "wire" / f"{sample}.hex"
        self.assertEqual(encode(diagnostic, SURFACE_MANIFEST), bytes.fromhex(path.read_text(encoding="ascii")))
        self.assertEqual(output_fingerprint(5, (), (diagnostic,), SURFACE_MANIFEST).hex(), fingerprint)

    def test_water_spill(self):
        issue = WaterLevelSpill(code=WaterDiagnosticCode.WATER_LEVEL_SPILL, source_uid="a",
                                requested_level=20, spill_limited_level=2)
        diagnostic = WaterLevelSpillDiagnostic(issue=issue, disposition=PlanDiagnosticDisposition.FALLBACK)
        self.assert_reference("water", diagnostic, "abf5c963cb2260752c8afe7b193bf7630fc9672bccd7329342383d5beb102c61")

    def test_river_refusal(self):
        issue = RiverRouteDiagnostic(world_uid="w", object_uid="r", object_type=HydrologyConnectionType.RIVER,
                                     requested_mouth=None, code=RiverRoutingCode.INVALID_SOURCE,
                                     reason=RiverRoutingFailure.MISSING_GEOMETRY)
        diagnostic = RiverPlanDiagnostic(issue=issue, disposition=PlanDiagnosticDisposition.ERROR)
        self.assert_reference("river", diagnostic, "42fcbf2ba7d6a8e16bab25561c9356c53870c1d90528ad993e7d4bdef3550617")
