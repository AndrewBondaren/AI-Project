"""Fixed Source proof/capture/selection roster: contract spec §11.4.

Requests, results, diagnostics and owning body codecs are deliberately separate.
The two Artifact entries preserve their existing shared IDs and exact owners.
"""

from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind, RegisteredTypeEntry
from app.dataModel.sourceVersioning.sourceBodyVersion import SourceBodyVersion, SourceCollectionVersion
from app.dataModel.sourceVersioning.sourceCapture import SourceCapture
from app.dataModel.sourceVersioning.sourceCaptureRef import SourceCaptureRef
from app.dataModel.sourceVersioning.sourceCaptureUsage import SourceCaptureUsage
from app.dataModel.sourceVersioning.sourceCaptureWitness import SourceCaptureWitness
from app.dataModel.sourceVersioning.sourceCollection import SourceCollectionBody
from app.dataModel.sourceVersioning.sourceDependencies import SourceDependencySet
from app.dataModel.sourceVersioning.sourceDescriptor import SourceDescriptorCategory
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.dataModel.sourceVersioning.sourceObjectId import (
    EntityObjectId, LibraryMemberId, RegistryMemberId, SourceCollectionId, SourceSettingsId,
)
from app.dataModel.sourceVersioning.sourceObjectRevision import SourceRevision
from app.dataModel.sourceVersioning.sourceProofSelection import SourceProofSelection
from app.dataModel.sourceVersioning.sourceVersionRef import SourceCollectionVersionRef, SourceVersionRef


SOURCE_PROOF_SCHEMA_V1 = CanonicalSchemaManifest(entries=tuple(
    RegisteredTypeEntry(type_id=identity, python_type=owner, kind=kind)
    for identity, owner, kind in (
        (20003, ArtifactKind, CanonicalTypeKind.ENUM),
        (20107, ArtifactRef, CanonicalTypeKind.RECORD),
        (71001, SourceDescriptorCategory, CanonicalTypeKind.ENUM),
        (71110, RegistryMemberId, CanonicalTypeKind.RECORD),
        (71111, LibraryMemberId, CanonicalTypeKind.RECORD),
        (71112, EntityObjectId, CanonicalTypeKind.RECORD),
        (71113, SourceSettingsId, CanonicalTypeKind.RECORD),
        (71114, SourceCollectionId, CanonicalTypeKind.RECORD),
        (71120, SourceRevision, CanonicalTypeKind.RECORD),
        (71121, SourceVersionRef, CanonicalTypeKind.RECORD),
        (71122, SourceCollectionVersionRef, CanonicalTypeKind.RECORD),
        (71123, SourceDependencySet, CanonicalTypeKind.RECORD),
        (71124, SourceBodyVersion, CanonicalTypeKind.RECORD),
        (71125, SourceCollectionVersion, CanonicalTypeKind.RECORD),
        (71126, SourceCollectionBody, CanonicalTypeKind.RECORD),
        (71127, SourceCapture, CanonicalTypeKind.RECORD),
        (71128, SourceCaptureWitness, CanonicalTypeKind.RECORD),
        (71129, SourceCaptureRef, CanonicalTypeKind.RECORD),
        (71130, SourceCaptureUsage, CanonicalTypeKind.RECORD),
        (71131, SourceDurableProof, CanonicalTypeKind.RECORD),
        (71138, SourceProofSelection, CanonicalTypeKind.RECORD),
    )
))
