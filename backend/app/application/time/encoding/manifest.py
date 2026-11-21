from app.application.patch.encoding.coreManifest import PATCH_CORE_SCHEMA
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind, RegisteredTypeEntry
from app.dataModel.time.values.point import TimePoint
from app.dataModel.time.values.interval import TimeInterval
from app.dataModel.time.reads.capture import TimeCapture
from app.dataModel.time.changes.advance import TimeAdvanceProposal
from app.dataModel.time.changes.section import TimeAdvancePatch, TimeAdvanceSection
from app.encoding.canonicalCodec import merge_manifests

TIME_SECTION_SCHEMA = merge_manifests(PATCH_CORE_SCHEMA, CanonicalSchemaManifest(entries=tuple(
    RegisteredTypeEntry(type_id=identity, python_type=model, kind=CanonicalTypeKind.RECORD)
    for identity, model in (
        (31100, TimePoint), (31102, TimeInterval), (31103, TimeCapture),
        (31104, TimeAdvanceProposal), (31105, TimeAdvanceSection), (31107, TimeAdvancePatch),
    )
)))
