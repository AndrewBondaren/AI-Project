"""Native/diagnostic fragment of the approved test-only Lifecycle allocation.

The terminal root 94001 is added by the Snapshot composition, not this fragment.
"""
from app.application.worldSnapshot.encoding.coreManifest import SNAPSHOT_CORE_SCHEMA
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind, RegisteredTypeEntry
from app.dataModel.fields.validatedFieldPath import ValidatedFieldPath, ModelIdentity, FieldSegment, IndexSegment, KeySegment, VariantSegment
from app.dataModel.lifecycle.identity import LifecycleTransitionRef
from app.dataModel.lifecycle.operations.kind import LifecycleOperation
from app.dataModel.lifecycle.results.applyIssue import LifecycleApplyCode, LifecycleApplyIssue
from app.encoding.canonicalCodec import merge_manifests
from tests.lifecycle.support import mixedContracts as m
from tests.lifecycle.support import domainSections as s


MOCK_NATIVE_MANIFEST = merge_manifests(SNAPSHOT_CORE_SCHEMA, CanonicalSchemaManifest(entries=(
    RegisteredTypeEntry(type_id=94002, python_type=m.LifecycleSectionAB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94003, python_type=s.TestDomainSectionA, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94004, python_type=s.TestDomainSectionB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94006, python_type=LifecycleTransitionRef, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94008, python_type=LifecycleApplyIssue, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94010, python_type=s.MockSubjectIssue, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94011, python_type=m.RefA, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94012, python_type=m.RefB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94013, python_type=m.EntityStateA, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94014, python_type=m.EntityStateB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94015, python_type=m.AbsentA, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94016, python_type=m.AbsentB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94017, python_type=m.PresentA, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94018, python_type=m.PresentB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94019, python_type=m.ParticipantA, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94020, python_type=m.ParticipantB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94021, python_type=m.TestAReason, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94022, python_type=m.TestBReason, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94023, python_type=m.EffectA, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94024, python_type=m.EffectB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94025, python_type=m.CoverageA, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94026, python_type=m.CoverageB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94027, python_type=m.CreateIntentA, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94028, python_type=m.CreateIntentB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94029, python_type=m.ReplaceIntentA, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94030, python_type=m.ReplaceIntentB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94031, python_type=m.EndIntentA, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94032, python_type=m.EndIntentB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94033, python_type=m.ReactivateIntentA, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94034, python_type=m.ReactivateIntentB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94035, python_type=m.CreateTransitionA, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94036, python_type=m.CreateTransitionB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94037, python_type=m.ReplaceTransitionA, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94038, python_type=m.ReplaceTransitionB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94039, python_type=m.EndTransitionA, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94040, python_type=m.EndTransitionB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94041, python_type=m.ReactivateTransitionA, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94042, python_type=m.ReactivateTransitionB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94043, python_type=m.CreateA, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94044, python_type=m.CreateB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94045, python_type=m.ReplaceA, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94046, python_type=m.ReplaceB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94047, python_type=m.EndA, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94048, python_type=m.EndB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94049, python_type=m.ReactivateA, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94050, python_type=m.ReactivateB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94051, python_type=m.CreatePatchA, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94052, python_type=m.CreatePatchB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94053, python_type=m.ReplacePatchA, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94054, python_type=m.ReplacePatchB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94055, python_type=m.EndPatchA, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94056, python_type=m.EndPatchB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94057, python_type=m.ReactivatePatchA, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94058, python_type=m.ReactivatePatchB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94059, python_type=s.MockMutationA, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94060, python_type=s.MockMutationB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94061, python_type=s.TestDomainPatchA, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94062, python_type=s.TestDomainPatchB, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=90012, python_type=ValidatedFieldPath, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=90013, python_type=ModelIdentity, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=90014, python_type=FieldSegment, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=15, python_type=IndexSegment, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94090, python_type=KeySegment, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94091, python_type=VariantSegment, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=94005, python_type=LifecycleOperation, kind=CanonicalTypeKind.ENUM),
    RegisteredTypeEntry(type_id=94007, python_type=LifecycleApplyCode, kind=CanonicalTypeKind.ENUM),
    RegisteredTypeEntry(type_id=94009, python_type=s.MockSubjectCode, kind=CanonicalTypeKind.ENUM),
)))
