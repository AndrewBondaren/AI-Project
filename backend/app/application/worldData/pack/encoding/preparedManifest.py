"""Seal a candidate manifest and finish its already staged artifact set."""
from app.application.artifacts.contracts.stagingPort import IArtifactStaging
from app.application.artifacts.staging.artifactStaging import TypedArtifactStager
from app.application.worldData.pack.encoding.packManifestCodec import encode_candidate_manifest
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind, OperationPhase
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.worldPack.activation.candidate import PreparedPackCandidate
from app.dataModel.worldPack.meta.worldPackManifest import WorldPackManifest


async def finish_pack_preparation(
    lease: OperationLeaseRef, manifest: WorldPackManifest, other_members: tuple[ArtifactRef, ...],
    manifest_stager: TypedArtifactStager[bytes], staging: IArtifactStaging,
) -> PreparedPackCandidate:
    """Other members include transitive refs resolved by the preparing writer."""
    if lease.kind is not OperationKind.PACK_ACTIVATION or lease.world_uid != manifest.world_uid:
        raise ValueError("candidate manifest differs from the preparing world or operation kind")
    if manifest.content_hash is not None:
        raise ValueError("candidate manifest must not embed its own digest")
    data = encode_candidate_manifest(manifest)
    members = dict.fromkeys(other_members)
    for row in manifest.spatial_roots:
        members[row.root] = None
    for ref in manifest.climate_artifacts():
        members[ref] = None
    manifest_ref = await manifest_stager.stage(lease, data)
    members[manifest_ref] = None
    record = await staging.finish_preparation(lease, tuple(members))
    if (record.phase is not OperationPhase.READY or record.kind is not lease.kind
            or record.operation_id != lease.operation_id or record.world_uid != lease.world_uid
            or record.fence != lease.fence or record.preparation_fingerprint != lease.preparation_fingerprint
            or set(record.leased_artifacts) != members.keys()):
        raise ValueError("staging did not confirm the prepared Pack candidate")
    return PreparedPackCandidate(operation_id=record.operation_id, manifest=manifest_ref,
                                 preparation_fingerprint=record.preparation_fingerprint)
