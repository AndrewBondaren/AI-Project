import subprocess
import sys
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from app.application.encoding.boundedCanonicalDecode import decode_bounded
from app.application.jsonValidation.resolve import ResolveContext
from app.application.worldData.generators.hydrology.water import waterDiagnostics
from app.application.worldData.generators.hydrology.water.planning.fine import execution
from app.application.worldData.generators.hydrology.water.planning.fine.publication import FineWaterPublicationJob
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.encoding.decodeLimits import DecodeLimits
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.planning.stages.openWaterPlan import FineWaterResult
from app.dataModel.hydrology.waterBody import WaterBody
from app.dataModel.hydrology.waterKindMismatchIssue import HydrologyMaterializationCode, WaterKindMismatchIssue
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.encoding.canonicalCodec import decode, encode
from tests.geo1.fine_water.test_fill import basin, fill, source
from tests.geo1.fine_water.fixtures import physical_inputs, placement
from tests.geo1.terrain_base.fixtures import Control


def cold_round_trip():
    data = sys.stdin.buffer.read()
    envelope = decode(data, PlanEnvelope[FineWaterResult], SURFACE_MANIFEST)
    sys.stdout.buffer.write(encode(envelope, SURFACE_MANIFEST))


class WaterMismatchTests(TestCase):
    def test_published_mismatch_and_assembler_delivery(self):
        window, _, topology = source()
        specs = tuple(basin(uid, {(x, y) for x in range(start, start + 6) for y in range(2, 8)})
                      for uid, start in (("a", 2), ("b", 16)))
        accepted = placement(window, specs)
        with patch.object(execution, "assemble_water_bodies", wraps=execution.assemble_water_bodies) as assembler:
            published = fill(window, topology, specs[::-1], accepted=accepted)
        self.assertEqual(fill(window, topology, specs, accepted=accepted), published)
        self.assertEqual([d.ref for d in published.dependencies], [window.ref, accepted.ref])
        water = published.payload[1]
        self.assertEqual([(b.water_body_uid, b.kind) for b in water.materialized.bodies],
                         [("a", BasinKind.LAKE), ("b", BasinKind.LAKE)])
        self.assertEqual([(e.source_uid, e.body_uids) for e in water.materialized.source_mapping.entries],
                         [("a", ("a",)), ("b", ("b",))])
        matching = tuple(replace(spec, kind=BasinKind.OCEAN) for spec in specs)
        self.assertFalse(fill(window, topology, matching).diagnostics)
        issues = [d.issue for d in published.diagnostics]
        self.assertCountEqual([i.source_uid for i in issues], ["a", "b"])
        for diagnostic in published.diagnostics:
            data = encode(diagnostic, SURFACE_MANIFEST)
            for restored in (decode(data, PlanDiagnostic, SURFACE_MANIFEST),
                             decode_bounded(data, PlanDiagnostic, SURFACE_MANIFEST,
                                            limits=DecodeLimits(100000, 10000, 100, 1024))):
                self.assertEqual(restored, diagnostic)
                self.assertEqual(encode(restored, SURFACE_MANIFEST), data)
                self.assertIs(restored.disposition, PlanDiagnosticDisposition.FALLBACK)
                issue = restored.issue
                self.assertIs(type(issue), WaterKindMismatchIssue)
                self.assertIs(issue.code, HydrologyMaterializationCode.WATER_KIND_MISMATCH)
                self.assertIs(issue.authored_kind, BasinKind.LAKE)
                self.assertIs(issue.physical_kind, BasinKind.OCEAN)
                self.assertEqual(issue.path, CheckedPath.from_pydantic_loc(WaterBody, ("kind",)))

        args, kwargs = assembler.call_args
        self.assertFalse(kwargs["ctx"].errors)
        for ctx in (ResolveContext(validate_only=True), ResolveContext(collect_only=True), ResolveContext()):
            with patch.object(waterDiagnostics, "log_issues") as log:
                emitted = []
                result = execution.assemble_water_bodies(*args, **(kwargs | {"ctx": ctx, "emit": emitted.append}))
                waterDiagnostics.report_water_diagnostics(ctx, tuple(emitted))
                self.assertEqual(result, water)
                if ctx.collect_only or ctx.validate_only:
                    self.assertEqual(ctx.errors, issues)
                    log.assert_not_called()
                else:
                    self.assertFalse(ctx.errors)
                    self.assertEqual([c.args[0] for c in log.call_args_list], [[issue] for issue in issues])

        data = encode(published, SURFACE_MANIFEST)
        cold = subprocess.run([sys.executable, "-m", __name__], input=data, capture_output=True, check=True)
        self.assertEqual(cold.stdout, data)
        restored = decode(cold.stdout, PlanEnvelope[FineWaterResult], SURFACE_MANIFEST)
        admission = dict(expected_water=published.ref, world_uid=window.ref.key.world_uid,
                         inputs=physical_inputs(topology), control=Control())
        self.assertEqual(FineWaterPublicationJob.admit_result(restored, **admission), published)
        with self.assertRaisesRegex(ValueError, "output proof"):
            FineWaterPublicationJob.admit_result(restored.model_copy(update={"diagnostics": ()}), **admission)

    def test_invalid_causes(self):
        issue = WaterKindMismatchIssue.retained("a", BasinKind.LAKE, BasinKind.OCEAN)
        for changes in ({"physical_kind": BasinKind.LAKE}, {"code": "UNKNOWN"},
                        {"path": CheckedPath.from_pydantic_loc(WaterBody, ("liquid",))},
                        {"path": CheckedPath.from_pydantic_loc(WaterKindMismatchIssue, ("code",))}):
            invalid = issue.model_copy(update=changes)
            with self.assertRaises(ValueError):
                decode(encode(invalid, SURFACE_MANIFEST), WaterKindMismatchIssue, SURFACE_MANIFEST)
        data = encode(issue, SURFACE_MANIFEST)
        unknown = data.replace(encode(323, SURFACE_MANIFEST), encode(65000, SURFACE_MANIFEST), 1)
        with self.assertRaises(ValueError):
            decode(unknown, WaterKindMismatchIssue, SURFACE_MANIFEST)


if __name__ == "__main__":
    cold_round_trip()
