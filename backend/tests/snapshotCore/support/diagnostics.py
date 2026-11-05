"""Concrete diagnostics supplied by the test section and its private wire schema."""
from enum import StrEnum

from app.application.worldSnapshot.encoding.coreManifest import SNAPSHOT_CORE_SCHEMA
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind, RegisteredTypeEntry
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.fields.validatedFieldPath import FieldSegment, ModelIdentity, ValidatedFieldPath
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.encoding.canonicalCodec import decode, encode, merge_manifests
from tests.snapshotCore.support.fakeSection import FAKE_SECTION_SCHEMA, FakeTarget


class FakeTargetCode(StrEnum):
    INVALID_NAME = "invalid_name"


class FakeTargetIssue(FieldPathError[FakeTargetCode]):
    pass


def target_issue(message: str) -> FakeTargetIssue:
    path = CheckedPath.root(FakeTarget).field(FieldRef(lambda: FakeTarget, lambda target: target.name))
    return FakeTargetIssue(path=path.freeze(), code=FakeTargetCode.INVALID_NAME, message=message)


TEST_ISSUE_SCHEMA = merge_manifests(SNAPSHOT_CORE_SCHEMA, FAKE_SECTION_SCHEMA, CanonicalSchemaManifest(entries=(
    RegisteredTypeEntry(type_id=90010, python_type=FakeTargetCode, kind=CanonicalTypeKind.ENUM),
    *(RegisteredTypeEntry(type_id=identity, python_type=model, kind=CanonicalTypeKind.RECORD)
      for identity, model in ((90011, FakeTargetIssue), (90012, ValidatedFieldPath),
                              (90013, ModelIdentity), (90014, FieldSegment))),
)))


def diagnostic_roundtrip(record):
    return decode(encode(record, TEST_ISSUE_SCHEMA), type(record), TEST_ISSUE_SCHEMA)
