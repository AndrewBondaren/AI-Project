"""Exact public imports for Pack's POJO dependency, checked without storage."""

from app.dataModel.sourceVersioning.sourceCaptureRef import SourceCaptureRef
from app.dataModel.sourceVersioning.sourceCaptureUsage import SourceCaptureUsage
from app.dataModel.sourceVersioning.sourceDependencies import SourceDependencySet
from app.dataModel.sourceVersioning.sourceDescriptor import (
    SourceCollectionOrder, SourceDescriptorCategory, SourceDescriptorDefinition,
    SourceDescriptorKey, SourceDescriptorRegistry, SourceDescriptorScope,
    SourceMemberKey, SourceMemberKeyKind,
)
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.dataModel.sourceVersioning.sourceObjectId import (
    EntityObjectId, LibraryMemberId, RegistryMemberId, SourceCollectionId,
    SourceObjectId, SourceSettingsId,
)
from app.dataModel.sourceVersioning.sourceObjectRevision import SourceRevision
from app.dataModel.sourceVersioning.sourceProofGroups import SourceProofGroupsInput, SourceProofGroupsResult
from app.dataModel.sourceVersioning.sourceProofInput import SourceProofInput
from app.dataModel.sourceVersioning.sourceProofResult import SourceProofResult
from app.dataModel.sourceVersioning.sourceProofSelection import SourceProofSelection
from app.dataModel.sourceVersioning.sourceVersionRef import SourceCollectionVersionRef, SourceVersionRef
from app.dataModel.sourceVersioning.sourceBodyVersion import SourceBodyVersion, SourceCollectionVersion
from app.dataModel.sourceVersioning.sourceCollection import SourceCollectionBody
from app.dataModel.sourceVersioning.sourceCapture import SourceCapture
from app.dataModel.sourceVersioning.sourceCaptureWitness import SourceCaptureWitness
from app.dataModel.sourceVersioning.sourceProofInput import SourceProofReadInput
from app.dataModel.sourceVersioning.sourceProofSelection import SourceProofSelectInput
from app.dataModel.sourceVersioning.sourceProofGroups import SourceProofGroupsVerifyInput
from app.dataModel.sourceVersioning.sourceErrors import (
    SourceOperation, SourceFieldCode, SourceFieldIssue, SourceLogicCode, SourceLogicIssue, SourceFailure,
)
from app.application.worldData.sourceVersioning.encoding.sourceProofSchemaV1 import SOURCE_PROOF_SCHEMA_V1


def construct_values(
    capture: SourceCaptureRef, objects: tuple[SourceVersionRef, ...],
    collections: tuple[SourceCollectionVersionRef, ...], selection: SourceProofSelection,
) -> tuple[SourceProofGroupsInput, SourceProofGroupsResult]:
    use = SourceCaptureUsage(capture=capture, dependencies=SourceDependencySet(objects=objects, collections=collections))
    request = SourceProofInput(world_uid=capture.world_uid, uses=(use,))
    proof = SourceDurableProof(schema_version=1, world_uid=capture.world_uid, uses=(use,))
    # These are values only; the caller has not established a full durable closure.
    admission = SourceProofResult(proof=proof, durable_refs=(capture.artifact,))
    return SourceProofGroupsInput(groups=(request,)), SourceProofGroupsResult(admission=admission, selections=(selection,))


def discriminate(identity: SourceObjectId) -> str:
    if identity.kind is SourceDescriptorCategory.LIBRARY_MEMBER:
        return identity.template_uid
    return identity.world_uid
