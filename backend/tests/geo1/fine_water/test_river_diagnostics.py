from unittest import TestCase

from pydantic import ValidationError

from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType as Connection
from app.dataModel.hydrology.riverRouting import RiverPlanDiagnostic, RiverRouteDiagnostic, RiverRoutingCode as Code, RiverRoutingFailure as Failure
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnosticDisposition as D
from app.encoding.canonicalCodec import decode, encode


class RiverDiagnosticsTests(TestCase):
    def test_codes_reasons_and_disposition(self):
        for code in Code:
            for reason in Failure:
                invalid = code is Code.INVALID_CONNECTION_TYPE
                fields = dict(world_uid="w", object_uid="r", requested_mouth=None, code=code,
                              reason=reason, object_type=None if invalid else Connection.RIVER,
                              rejected_connection_type="" if invalid else None)
                if code is Code.REDIRECTED:
                    fields.update(receiver_uid="river", receiver_kind=Connection.RIVER, receiver_cell=(4, 7))
                with self.subTest(code=code, reason=reason):
                    if invalid != (reason is Failure.INVALID_CONNECTION_TYPE):
                        with self.assertRaises(ValidationError):
                            RiverRouteDiagnostic(**fields)
                        continue
                    issue = RiverRouteDiagnostic(**fields)
                    expected = D.FALLBACK if code is Code.REDIRECTED else D.ERROR
                    for d in D:
                        if d is expected:
                            carrier = RiverPlanDiagnostic(issue=issue, disposition=d)
                            self.assertEqual(decode(encode(carrier, SURFACE_MANIFEST),
                                                    RiverPlanDiagnostic, SURFACE_MANIFEST), carrier)
                        else:
                            with self.assertRaises(ValidationError):
                                RiverPlanDiagnostic(issue=issue, disposition=d)

    def test_revalidates_forged_river_identity(self):
        fact = RiverRouteDiagnostic(world_uid="w", object_uid="r", requested_mouth=None,
            code=Code.INVALID_SOURCE, reason=Failure.MISSING_GEOMETRY, object_type=Connection.RIVER)
        for update in ({"object_type": Connection.COASTLINE}, {"rejected_connection_type": "bogus"},
                       {"code": Code.REDIRECTED}, {"object_type": "river"}):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                RiverPlanDiagnostic(issue=fact.model_copy(update=update), disposition=D.ERROR)
