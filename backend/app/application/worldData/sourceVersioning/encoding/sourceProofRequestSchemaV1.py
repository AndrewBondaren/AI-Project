"""Source-owned request registration; proof v1 and admission remain unchanged."""

from app.application.worldData.sourceVersioning.encoding.sourceProofSchemaV1 import SOURCE_PROOF_SCHEMA_V1
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind, RegisteredTypeEntry
from app.dataModel.sourceVersioning.sourceProofInput import SourceProofReadInput
from app.encoding.canonicalCodec import merge_manifests


SOURCE_PROOF_REQUEST_SCHEMA_V1: CanonicalSchemaManifest = CanonicalSchemaManifest(entries=(
    RegisteredTypeEntry(type_id=71201, python_type=SourceProofReadInput, kind=CanonicalTypeKind.RECORD),
))

SOURCE_PROOF_REQUEST_ENCODING_V1: CanonicalSchemaManifest = merge_manifests(
    SOURCE_PROOF_SCHEMA_V1, SOURCE_PROOF_REQUEST_SCHEMA_V1,
)
