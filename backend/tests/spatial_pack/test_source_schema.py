"""Source identity/admission only: no producer, storage parser or publication."""
import dataclasses
import hashlib
from enum import StrEnum
from typing import TypeAliasType
from unittest import TestCase
from unittest.mock import patch

from app.encoding.canonicalCodec import CanonicalEncodingError, encode, decode
from app.application.planning.service.planFingerprints import output_fingerprint
from app.application.worldData.generators.hydrology.encoding import sourceSchema as schema
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.planning.identity.planKey import PlanKey, WorldPlanScope
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError, ReferenceIssueContext, ReferenceIssueReason
from app.dataModel.validation.diagnostics.runtimeIssueContext import RuntimeIssueContext
from app.dataModel.hydrology.query.source import CanonicalOpenWaterSource
from tests.geo1.canonical_source.test_source_models import source


SLOTS = ('fine_water', 'hydrology_routes', 'native_final', 'pre_water_surface',
         'prepared_natural', 'river_relief', 'water_placement')


def ref(contract='hydrology.canonical_open_water', fingerprint=b'o' * 32):
    return PlanRef(key=PlanKey(world_uid='w', scope=WorldPlanScope(), contract_id=contract,
                              schema_version=1, algorithm_version=1, input_fingerprint=b'i' * 32),
                   output_fingerprint=fingerprint)


def diagnostics():
    return (PlanDiagnostic(issue=FieldPathError(path=('water', 0), message='spill',
                                               code='WATER_LEVEL_SPILL'),
                           disposition=PlanDiagnosticDisposition.FALLBACK),)


def envelope(dry=False):
    payload = source(wet_runs=()) if dry else source()
    deps = tuple(PlanDependency(slot=s, ref=ref(s)) for s in SLOTS)
    issues = diagnostics()
    schema.require_source_schema_v1()
    schema.require_source_diagnostics_v1(issues)
    fingerprint = output_fingerprint(payload, deps, issues, schema.OPEN_WATER_SOURCE_SCHEMA_V1)
    return PlanEnvelope[CanonicalOpenWaterSource](ref=ref(fingerprint=fingerprint),
                                                 dependencies=deps, diagnostics=issues, payload=payload)


class SourceSchemaTests(TestCase):
    def test_diagnostic_rejects_enum_in_plain_scalar_fields(self):
        original = diagnostics()[0]
        enum = PlanDiagnosticDisposition.NOTICE
        for field, value in (('message', enum), ('schema_id', enum), ('path', (enum,))):
            with self.subTest(field=field):
                issue = dataclasses.replace(original.issue, **{field: value})
                diagnostic = original.model_copy(update={'issue': issue})
                with self.assertRaises(CanonicalEncodingError):
                    schema.require_source_diagnostics_v1((diagnostic,))
                self.assertIs(diagnostic.issue, issue)
                self.assertIs(getattr(diagnostic.issue, field), value)

    def test_reused_alias_name_cannot_hide_a_different_coordinate_type(self):
        schema.require_source_schema_v1()
        field = CanonicalOpenWaterSource.model_fields['shore_rows']
        replaced = tuple[tuple[TypeAliasType('FineXY', str), schema.MapCellHydrology], ...]
        with patch.object(field, 'annotation', replaced), self.assertRaises(CanonicalEncodingError):
            schema.require_source_schema_v1()

    def test_puddle_error_cannot_be_substituted_with_fallback(self):
        error = PlanDiagnostic(issue=FieldPathError(path=('water',), message='puddle', code='WATER_PUDDLE'),
                               disposition=PlanDiagnosticDisposition.ERROR)
        schema.require_source_diagnostics_v1((error,))
        changed = error.model_copy(update={'disposition': PlanDiagnosticDisposition.FALLBACK})
        with self.assertRaises(CanonicalEncodingError):
            schema.require_source_diagnostics_v1((changed,))
        self.assertIs(changed.issue, error.issue)
        self.assertIs(changed.disposition, PlanDiagnosticDisposition.FALLBACK)

    def test_exact_roster_and_alias_reachability(self):
        schema.require_source_schema_v1()
        self.assertEqual(tuple(e.type_id for e in schema.OPEN_WATER_SOURCE_SCHEMA_V1.entries),
                         (23,41,53,54,55,80,94,95,96,97,98,101,105,106,107,108,109,110,111,
                          119,150,151,152,153,154,226,227,238,239,283,60004,60007,60008))
        _, aliases = schema._snapshot()
        self.assertEqual({name for name, _ in aliases}, {
            'AlgorithmVersion', 'EntityUid', 'FineX', 'FineXY', 'FineY', 'FineZ',
            'InputFingerprint', 'MaterialKey', 'OutputFingerprint', 'PlanContractId',
            'PlanScope', 'PlanSlot', 'RevisionHex', 'SchemaVersion'})
        self.assertNotIn('ArtifactFormatKey', dict(aliases))
        self.assertNotIn('FormatVersion', dict(aliases))

    def test_missing_extra_changed_alias_refuse(self):
        shapes, aliases = schema._snapshot()
        for altered in (aliases[1:], aliases + (('ArtifactFormatKey', 'str'),),
                        ((aliases[0][0], 'bytes'),) + aliases[1:]):
            with self.subTest(aliases=altered), patch.object(schema, '_snapshot', return_value=(shapes, altered)):
                with self.assertRaisesRegex(CanonicalEncodingError, 'alias drift'):
                    schema.require_source_schema_v1()

    def test_actual_alias_definition_drift_refuses(self):
        from app.dataModel.spatial.grid.coordinateTypes import FineX
        with patch.object(FineX, '__supertype__', bool):
            with self.assertRaisesRegex(CanonicalEncodingError, 'alias drift'):
                schema.require_source_schema_v1()

    def test_binding_drift_refuses(self):
        original = schema.OPEN_WATER_SOURCE_SCHEMA_V1
        first = original.entries[0].model_copy(update={'type_id': 99999})
        with patch.object(schema, 'OPEN_WATER_SOURCE_SCHEMA_V1', original.model_copy(
                update={'entries': (first,) + original.entries[1:]})):
            with self.assertRaisesRegex(CanonicalEncodingError, 'binding drift'):
                schema.require_source_schema_v1()

    def test_field_order_default_annotation_and_enum_drift_refuse(self):
        fields = schema.WaterMembershipRun.model_fields
        with patch.object(schema.WaterMembershipRun, '__pydantic_fields__', dict(reversed(tuple(fields.items())))):
            with self.assertRaisesRegex(CanonicalEncodingError, 'shape drift'):
                schema.require_source_schema_v1()
        field = fields['y']
        for attribute, value in (('default', 0), ('annotation', bool)):
            with patch.object(field, attribute, value):
                with self.assertRaisesRegex(CanonicalEncodingError, 'shape drift'):
                    schema.require_source_schema_v1()
        with patch.object(schema.PlanDiagnosticDisposition.NOTICE, '_value_', 'changed'):
            with self.assertRaisesRegex(CanonicalEncodingError, 'shape drift'):
                schema.require_source_schema_v1()

    def test_roundtrip_and_fingerprint_golden(self):
        for dry in (False, True):
            with self.subTest(dry=dry):
                item = envelope(dry)
                wire = encode(item, schema.OPEN_WATER_SOURCE_SCHEMA_V1)
                restored = decode(wire, PlanEnvelope[CanonicalOpenWaterSource], schema.OPEN_WATER_SOURCE_SCHEMA_V1)
                self.assertEqual(item, restored)
                self.assertEqual(wire, encode(restored, schema.OPEN_WATER_SOURCE_SCHEMA_V1))
                self.assertEqual(item.ref.output_fingerprint, output_fingerprint(
                    restored.payload, restored.dependencies, restored.diagnostics, schema.OPEN_WATER_SOURCE_SCHEMA_V1))
                self.assertEqual((hashlib.sha256(wire).hexdigest(), item.ref.output_fingerprint.hex()), GOLDENS[dry])
                payload_wire = encode(item.payload, schema.OPEN_WATER_SOURCE_SCHEMA_V1)
                self.assertEqual(item.payload, decode(payload_wire, CanonicalOpenWaterSource, schema.OPEN_WATER_SOURCE_SCHEMA_V1))

    def test_fingerprint_includes_payload_dependencies_diagnostics(self):
        item = envelope()
        variants = (
            (item.payload.model_copy(update={'z_max': 5}), item.dependencies, item.diagnostics),
            (item.payload, item.dependencies[:-1], item.diagnostics),
            (item.payload, item.dependencies, ()),
            (item.payload, item.dependencies, (item.diagnostics[0].model_copy(
                update={'disposition': PlanDiagnosticDisposition.ERROR}),)))
        for payload, deps, issues in variants:
            self.assertNotEqual(item.ref.output_fingerprint,
                                output_fingerprint(payload, deps, issues, schema.OPEN_WATER_SOURCE_SCHEMA_V1))

    def test_real_diagnostic_shapes_preserved(self):
        issues = diagnostics() + (PlanDiagnostic(issue=FieldPathError(path=('river',),
            message='{"fallback_reason":"dry_mouth"}', code='RIVER_REDIRECTED'),
            disposition=PlanDiagnosticDisposition.FALLBACK),)
        before = encode(issues, schema.OPEN_WATER_SOURCE_SCHEMA_V1)
        schema.require_source_diagnostics_v1(issues)
        self.assertEqual(before, encode(issues, schema.OPEN_WATER_SOURCE_SCHEMA_V1))

    def test_unknown_and_known_enum_contexts_refuse_without_mutation(self):
        class Unknown(StrEnum):
            VALUE = 'unknown'
        for enum in (Unknown.VALUE, PlanDiagnosticDisposition.NOTICE):
            context = RuntimeIssueContext(world_uid='w', snapshot_uid=None, content_revision=None,
                source_uid=None, body_uids=(), cell=None, face=None, fallback_action=enum, fallback_reason=enum)
            issue = dataclasses.replace(diagnostics()[0].issue, runtime_context=context)
            diagnostic = diagnostics()[0].model_copy(update={'issue': issue})
            with self.assertRaisesRegex(CanonicalEncodingError, 'unadmitted'):
                schema.require_source_diagnostics_v1((diagnostic,))
            self.assertIs(diagnostic.issue.runtime_context, context)
        issue = dataclasses.replace(diagnostics()[0].issue,
            reference=ReferenceIssueContext(reason=ReferenceIssueReason.DEFAULT_APPLIED, domain='water'))
        with self.assertRaisesRegex(CanonicalEncodingError, 'unadmitted'):
            schema.require_source_diagnostics_v1((diagnostics()[0].model_copy(update={'issue': issue}),))

    def test_malformed_graph_refuses(self):
        for issues in (list(diagnostics()), (object(),), (diagnostics()[0].model_copy(
                update={'issue': dataclasses.replace(diagnostics()[0].issue, path=('water', []))}),)):
            with self.subTest(issues=issues), self.assertRaises(CanonicalEncodingError):
                schema.require_source_diagnostics_v1(issues)


# Existing canonical TLV v1 bytes and planning output formula, fixed fixture vectors.
GOLDENS = {
    False: ('6f9fb2468d983fdfa95749051ee4a832065987cb5a1a2685de721935adfd61fc',
            '5245f47920fff9a15d4fe176fdc3e1a6c1e65289178b0c5645624a1d4f35ff2d'),
    True: ('0f14bc3ad847f14fbd2d4c99c5d2ddac023c6e6b6601db4b3c8dfcc7f37acaac',
           '4721b77c9f3bb65f8f33ea768c3e4f785020ef565f352c062c4034e28cb84a1b'),
}
