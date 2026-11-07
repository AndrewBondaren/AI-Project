"""Source identity/admission only: no producer, storage parser or publication."""
import hashlib
from pydantic import PlainValidator, SerializeAsAny
from typing import Annotated, Any, get_args
from typing import TypeAliasType
from unittest import TestCase
from unittest.mock import patch

from app.encoding.canonicalCodec import CanonicalEncodingError, encode, decode
from app.application.planning.service.planFingerprints import output_fingerprint
from app.application.worldData.generators.hydrology.encoding import sourceBindings, sourceShape, sourceSchema as schema
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.planning.identity.planKey import PlanKey, WorldPlanScope
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.waterBody import WaterBody
from app.dataModel.hydrology.declaredRiver import HydrologyMouth
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.query.source import WaterMembershipRun
from app.dataModel.hydrology import waterDiagnostics as w
from app.dataModel.hydrology.riverRouting import RiverPlanDiagnostic, RiverRouteDiagnostic, RiverRoutingCode, RiverRoutingFailure
from app.dataModel.hydrology.waterKindMismatchIssue import WaterKindMismatchIssue
from app.dataModel.terrain.designedWater.waterDesignTypeError import WaterDesignTypeError
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.application.encoding.boundedCanonicalDecode import decode_bounded
from app.dataModel.encoding.decodeLimits import DecodeLimits
from app.dataModel.hydrology.query.source import CanonicalOpenWaterSource
from tests.geo1.canonical_source.test_source_models import source


SLOTS = ('fine_water', 'hydrology_routes', 'native_final', 'pre_water_surface',
         'prepared_natural', 'river_relief', 'water_placement')


def ref(contract='hydrology.canonical_open_water', fingerprint=b'o' * 32):
    return PlanRef(key=PlanKey(world_uid='w', scope=WorldPlanScope(), contract_id=contract,
                              schema_version=1, algorithm_version=1, input_fingerprint=b'i' * 32),
                   output_fingerprint=fingerprint)


def diagnostics():
    issue = w.WaterLevelSpill(code=w.WaterDiagnosticCode.WATER_LEVEL_SPILL, source_uid="authored",
                             requested_level=5, spill_limited_level=2)
    return (w.WaterLevelSpillDiagnostic(issue=issue, disposition=PlanDiagnosticDisposition.FALLBACK),)


def envelope(dry=False):
    payload = source(wet_runs=()) if dry else source()
    deps = tuple(PlanDependency(slot=s, ref=ref(s)) for s in SLOTS)
    issues = diagnostics()
    schema.require_source_schema_v1()
    schema.require_source_diagnostics_v1(issues)
    fingerprint = output_fingerprint(payload, deps, issues, sourceBindings.OPEN_WATER_SOURCE_SCHEMA_V1)
    return PlanEnvelope[CanonicalOpenWaterSource](ref=ref(fingerprint=fingerprint),
                                                 dependencies=deps, diagnostics=issues, payload=payload)


class SourceSchemaTests(TestCase):
    def test_replaced_plain_validator_changes_envelope_shape(self):
        def substitute(value):
            return value

        field = PlanEnvelope[CanonicalOpenWaterSource].model_fields["diagnostics"]
        carrier = Annotated[SerializeAsAny[PlanDiagnostic[Any]], PlainValidator(substitute)]
        with patch.object(field, "annotation", tuple[carrier, ...]):
            with self.assertRaisesRegex(CanonicalEncodingError, "shape drift: 60008"):
                schema.require_source_schema_v1()

    def test_reused_alias_name_cannot_hide_a_different_coordinate_type(self):
        schema.require_source_schema_v1()
        field = CanonicalOpenWaterSource.model_fields['shore_rows']
        replaced = tuple[tuple[TypeAliasType('FineXY', str), MapCellHydrology], ...]
        with patch.object(field, 'annotation', replaced), self.assertRaises(CanonicalEncodingError):
            schema.require_source_schema_v1()

    def test_puddle_error_cannot_be_substituted_with_fallback(self):
        error = w.WaterPuddleDiagnostic(issue=w.WaterPuddle(code=w.WaterDiagnosticCode.WATER_PUDDLE,
            source_uid="a", cell_count=1, minimum_cells=2), disposition=PlanDiagnosticDisposition.ERROR)
        schema.require_source_diagnostics_v1((error,))
        changed = error.model_copy(update={'disposition': PlanDiagnosticDisposition.FALLBACK})
        with self.assertRaises(CanonicalEncodingError):
            schema.require_source_diagnostics_v1((changed,))
        self.assertIs(changed.issue, error.issue)
        self.assertIs(changed.disposition, PlanDiagnosticDisposition.FALLBACK)

    def test_exact_roster_and_alias_reachability(self):
        schema.require_source_schema_v1()
        self.assertEqual(tuple(e.type_id for e in sourceBindings.OPEN_WATER_SOURCE_SCHEMA_V1.entries),
                         (23, 41, 53, 54, 55, 80, 89, 94, 95, 96, 97, 98, 101, 105, 111, 119,
                          150, 151, 152, 153, 154, 226, 227, 238, 239, 283, *range(303, 309),
                          *range(323, 337), *range(338, 345), 60004, 60007, 60008))
        surface = {e.type_id: e for e in SURFACE_MANIFEST.entries}
        for entry in sourceBindings.OPEN_WATER_SOURCE_SCHEMA_V1.entries:
            if entry.type_id < 60000:
                self.assertEqual(entry, surface[entry.type_id])
        _, aliases = sourceShape.source_snapshot()
        self.assertEqual({name for name, _ in aliases}, {
            'AlgorithmVersion', 'EntityUid', 'FineX', 'FineXY', 'FineY', 'FineZ',
            'InputFingerprint', 'MaterialKey', 'OutputFingerprint', 'PlanContractId',
            'PlanScope', 'PlanSlot', 'Count', 'PositiveCount', 'PathSegment', 'SchemaVersion'})
        self.assertNotIn('ArtifactFormatKey', dict(aliases))
        self.assertNotIn('FormatVersion', dict(aliases))

    def test_missing_extra_changed_alias_refuse(self):
        shapes, aliases = sourceShape.source_snapshot()
        for altered in (aliases[1:], aliases + (('ArtifactFormatKey', 'str'),),
                        ((aliases[0][0], 'bytes'),) + aliases[1:]):
            with self.subTest(aliases=altered), patch.object(sourceShape, 'source_snapshot', return_value=(shapes, altered)):
                with self.assertRaisesRegex(CanonicalEncodingError, 'alias drift'):
                    schema.require_source_schema_v1()

    def test_actual_alias_definition_drift_refuses(self):
        from app.dataModel.spatial.grid.coordinateTypes import FineX
        with patch.object(FineX, '__supertype__', bool):
            with self.assertRaisesRegex(CanonicalEncodingError, 'alias drift'):
                schema.require_source_schema_v1()

    def test_binding_drift_refuses(self):
        original = sourceBindings.OPEN_WATER_SOURCE_SCHEMA_V1
        first = original.entries[0].model_copy(update={'type_id': 99999})
        with patch.object(sourceBindings, 'OPEN_WATER_SOURCE_SCHEMA_V1', original.model_copy(
                update={'entries': (first,) + original.entries[1:]})):
            with self.assertRaisesRegex(CanonicalEncodingError, 'binding drift'):
                schema.require_source_schema_v1()

    def test_equal_values_with_wrong_binding_types_refuse_at_source_guard(self):
        original = sourceBindings.OPEN_WATER_SOURCE_SCHEMA_V1
        first, *rest = original.entries
        for update in ({"type_id": float(first.type_id)}, {"kind": first.kind.value}):
            entries = (first.model_copy(update=update), *rest)
            with self.subTest(update=update), patch.object(sourceBindings, "OPEN_WATER_SOURCE_SCHEMA_V1",
                    original.model_copy(update={"entries": entries})):
                with self.assertRaisesRegex(CanonicalEncodingError, "binding drift"):
                    schema.require_source_schema_v1()

    def test_field_order_default_annotation_and_enum_drift_refuse(self):
        fields = WaterMembershipRun.model_fields
        with patch.object(WaterMembershipRun, '__pydantic_fields__', dict(reversed(tuple(fields.items())))):
            with self.assertRaisesRegex(CanonicalEncodingError, 'shape drift'):
                schema.require_source_schema_v1()
        field = fields['y']
        for attribute, value in (('default', 0), ('annotation', bool)):
            with patch.object(field, attribute, value):
                with self.assertRaisesRegex(CanonicalEncodingError, 'shape drift'):
                    schema.require_source_schema_v1()
        with patch.object(PlanDiagnosticDisposition.NOTICE, '_value_', 'changed'):
            with self.assertRaisesRegex(CanonicalEncodingError, 'shape drift'):
                schema.require_source_schema_v1()

    def test_roundtrip_and_fingerprint_golden(self):
        for dry in (False, True):
            with self.subTest(dry=dry):
                item = envelope(dry)
                wire = encode(item, sourceBindings.OPEN_WATER_SOURCE_SCHEMA_V1)
                restored = decode(wire, PlanEnvelope[CanonicalOpenWaterSource], sourceBindings.OPEN_WATER_SOURCE_SCHEMA_V1)
                self.assertEqual(item, restored)
                self.assertEqual(wire, encode(restored, sourceBindings.OPEN_WATER_SOURCE_SCHEMA_V1))
                self.assertEqual(item.ref.output_fingerprint, output_fingerprint(
                    restored.payload, restored.dependencies, restored.diagnostics, sourceBindings.OPEN_WATER_SOURCE_SCHEMA_V1))
                self.assertEqual((hashlib.sha256(wire).hexdigest(), item.ref.output_fingerprint.hex()), GOLDENS[dry])
                payload_wire = encode(item.payload, sourceBindings.OPEN_WATER_SOURCE_SCHEMA_V1)
                self.assertEqual(item.payload, decode(payload_wire, CanonicalOpenWaterSource, sourceBindings.OPEN_WATER_SOURCE_SCHEMA_V1))

    def test_fingerprint_includes_payload_dependencies_diagnostics(self):
        item = envelope()
        variants = (
            (item.payload.model_copy(update={'z_max': 5}), item.dependencies, item.diagnostics),
            (item.payload, item.dependencies[:-1], item.diagnostics),
            (item.payload, item.dependencies, ()),
            (item.payload, item.dependencies, (item.diagnostics[0].model_copy(
                update={"issue": item.diagnostics[0].issue.model_copy(update={"requested_level": 6})}),)))
        for payload, deps, issues in variants:
            self.assertNotEqual(item.ref.output_fingerprint,
                                output_fingerprint(payload, deps, issues, sourceBindings.OPEN_WATER_SOURCE_SCHEMA_V1))

    def test_concrete_diagnostics_bounded_roundtrip(self):
        mismatch = PlanDiagnostic(issue=WaterKindMismatchIssue.retained("a", BasinKind.LAKE,
            BasinKind.OCEAN), disposition=PlanDiagnosticDisposition.FALLBACK)
        river = RiverPlanDiagnostic(issue=RiverRouteDiagnostic(world_uid="w", object_uid="r",
            requested_mouth=HydrologyMouth(x=1, y=2), code=RiverRoutingCode.INVALID_SOURCE,
            reason=RiverRoutingFailure.MISSING_GEOMETRY, object_type=HydrologyConnectionType.RIVER),
            disposition=PlanDiagnosticDisposition.ERROR)
        cases = (
            (w.WaterPuddleDiagnostic, dict(source_uid="a", cell_count=1, minimum_cells=2)),
            (w.WaterCannotHoldDiagnostic, dict(source_uid="a", effective_level=3)),
            (w.WaterTerrainUnresolvedDiagnostic, dict(world_uid="w", message="terrain")),
            (w.WaterNoOceanDepressionDiagnostic, dict(world_uid="w", default_water_level=0)),
            (w.WaterLevelSupersededDiagnostic, dict(source_uid="a", declared_level=2, effective_level=8,
                                                   parent_system_uid=None)),
            (w.WaterWorldOceanDiagnostic, dict(world_uid="w", water_cells=2, world_cells=4)),
        )
        items = [*diagnostics(), river, mismatch]
        for carrier, fields in cases:
            fact = carrier.model_fields["issue"].annotation
            code, = get_args(fact.model_fields["code"].annotation)
            items.append(carrier(issue=fact(code=code, **fields), disposition=carrier.expected_disposition))
        manifest = sourceBindings.OPEN_WATER_SOURCE_SCHEMA_V1
        for item in items:
            with self.subTest(carrier=type(item)):
                schema.require_source_diagnostics_v1((item,))
                wire = encode(item, manifest)
                restored = decode_bounded(wire, type(item), manifest, limits=DecodeLimits(100000, 10000, 100, 1024))
                self.assertIs(type(restored.issue), type(item.issue))
                self.assertEqual(restored, item)
                self.assertEqual(encode(restored, manifest), wire)

    def test_surface_registered_fact_is_not_admitted_for_source(self):
        issue = WaterDesignTypeError.at(WaterBody, ("kind",), "bad kind", operation="water_source")
        item = PlanDiagnostic(issue=issue, disposition=PlanDiagnosticDisposition.FALLBACK)
        self.assertEqual(item, decode(encode(item, SURFACE_MANIFEST), PlanDiagnostic, SURFACE_MANIFEST))
        with self.assertRaisesRegex(CanonicalEncodingError, "unadmitted"):
            schema.require_source_diagnostics_v1((item,))

    def test_malformed_graph_refuses(self):
        item, = diagnostics()
        forged = item.issue.model_copy(update={"requested_level": "5"})
        placement = w.WaterPlacementRequiredDiagnostic(issue=w.WaterPlacementRequired(
            code=w.WaterDiagnosticCode.WATER_PLACEMENT_REQUIRED, world_uid="w"),
            disposition=PlanDiagnosticDisposition.ERROR)
        enum_message = w.WaterTerrainUnresolvedDiagnostic(issue=w.WaterTerrainUnresolved(
            code=w.WaterDiagnosticCode.WATER_TERRAIN_UNRESOLVED, world_uid="w", message="terrain"),
            disposition=PlanDiagnosticDisposition.ERROR)
        swapped = enum_message.issue.model_copy(update={"message": PlanDiagnosticDisposition.NOTICE})
        for issues in ((enum_message.model_copy(update={"issue": swapped}),), list(diagnostics()), (object(),), (placement,), (item.model_copy(update={"issue": forged}),)):
            with self.subTest(issues=issues), self.assertRaises(CanonicalEncodingError):
                schema.require_source_diagnostics_v1(issues)


# Existing canonical TLV v1 bytes and planning output formula, fixed fixture vectors.
GOLDENS = {
    False: ('85b7ff544de2a95de32aad006e5438f8cf40c7867d95443a0c355bd62e3d1b6d',
            'c9419da738d8c7e372aa81670a405ee8e1954db7d79766c0ed336aaae22f0730'),
    True: ('5b35bb6aae0d4fc5bfe1fe87480f0d96ef32f7c5a1415612a5ce9b60424e63fa',
           'b5ed684af47d5fbafc09071dd80d4ef7003b4b788aa7a13c4454d5aa1291d257'),
}
