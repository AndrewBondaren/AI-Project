"""One aggregated admission boundary for single and batch chunk requests."""

from typing import TypeVar

from pydantic import BaseModel

from app.application.worldData.pack.preparation.errors import preparation_errors, raise_preparation_errors, validate_preparation_input
from app.application.worldData.pack.preparation.errors import valid_preparation_field, preparation_field_value
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.worldPack.preparation.errors import PackPreparationDiagnostic, PackPreparationFailureReason, PackPreparationIssue, PackPreparationIssueCode
from app.dataModel.worldPack.preparation.provenance import PackStoredProvenance
from app.dataModel.worldPack.preparation.state import PackPreparationState
from app.dataModel.worldPack.preparation.operations import PackWildernessChunkWrite, PackWildernessChunkInput, PackWildernessChunksInput
from app.dataModel.worldPack.preparation.parts import PackWildernessChunkPartInput
from app.dataModel.worldPack.preparation.provenance import PackNewPartProvenance, PackInheritedPartProvenance
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.artifacts.references import ArtifactKind
from app.dataModel.worldPack.meta.fineTerrainStorageFormat import FINE_TERRAIN_FORMAT_KEY, FINE_TERRAIN_STORAGE_VERSION

from app.application.worldData.pack.preparation.metadataStateValidator import MetadataStateValidator
from app.application.worldData.pack.preparation.packPreparationValidator import PackPreparationValidator
from app.application.worldData.pack.preparation.metadataEvidenceValidator import MetadataEvidenceValidator
from app.application.worldData.pack.preparation.errors import _raw_items, _issue

RootT = TypeVar("RootT", bound=BaseModel)
ItemT = TypeVar("ItemT", bound=PackWildernessChunkWrite)


class WildernessChunkAdmission:
    def validate_wilderness_chunks(self, request: PackWildernessChunksInput) -> PackWildernessChunksInput:
        errors = preparation_errors()
        checked = validate_preparation_input(PackWildernessChunksInput, request, errors)
        admitted = checked if checked is not None else request
        root = CheckedPath.root(PackWildernessChunksInput)
        state_field = FieldRef(lambda: PackWildernessChunksInput, lambda value: value.state)
        state = preparation_field_value(admitted, state_field)
        PackPreparationValidator().check_state_identities(state, root.field(state_field), errors)
        MetadataStateValidator().check_metadata_groups(state, root.field(state_field), errors)
        entries = FieldRef(lambda: PackWildernessChunksInput, lambda value: value.entries)
        seen: set[object] = set()
        for index, item in _raw_items(admitted, entries):
            path = root.field(entries).item(index)
            self.check_wilderness_chunk(PackWildernessChunkWrite, item, state, path, errors)
            part_field = FieldRef(lambda: PackWildernessChunkWrite, lambda value: value.part)
            address_field = FieldRef(lambda: PackWildernessChunkPartInput, lambda value: value.address)
            address = valid_preparation_field(preparation_field_value(item, part_field), address_field)
            if address is not None:
                if address in seen:
                    _issue(errors, PackPreparationIssueCode.DUPLICATE_ADDRESS,
                           path.field(part_field).field(address_field), "duplicate input chunk address")
                seen.add(address)
        self._raise_chunk_errors(errors)
        assert checked is not None
        return checked

    def validate_wilderness_chunk(self, request: PackWildernessChunkInput) -> PackWildernessChunkInput:
        errors = preparation_errors()
        checked = validate_preparation_input(PackWildernessChunkInput, request, errors)
        admitted = checked if checked is not None else request
        root = CheckedPath.root(PackWildernessChunkInput)
        state_field = FieldRef(lambda: PackWildernessChunkInput, lambda value: value.state)
        state = preparation_field_value(admitted, state_field)
        PackPreparationValidator().check_state_identities(state, root.field(state_field), errors)
        MetadataStateValidator().check_metadata_groups(state, root.field(state_field), errors)
        self.check_wilderness_chunk(PackWildernessChunkInput, admitted, state, root, errors)
        self._raise_chunk_errors(errors)
        assert checked is not None
        return checked

    @staticmethod
    def _raise_chunk_errors(errors: ValidatorAggregationHelper[PackPreparationDiagnostic]) -> None:
        only_addresses = all(isinstance(issue, PackPreparationIssue)
            and issue.code is PackPreparationIssueCode.DUPLICATE_ADDRESS for issue in errors.snapshot())
        raise_preparation_errors(errors, PackPreparationFailureReason.IDENTITY_CONFLICT if only_addresses
                                 else PackPreparationFailureReason.DEPENDENCY_MISMATCH)

    def check_wilderness_chunk(
        self, model: type[ItemT], item: object, state: object, path: CheckedPath[RootT, ItemT],
        errors: ValidatorAggregationHelper[PackPreparationDiagnostic],
    ) -> None:
        part_field = FieldRef(lambda: model, lambda value: value.part)
        part = preparation_field_value(item, part_field)
        part_path = path.field(part_field)
        artifact_field = FieldRef(lambda: PackWildernessChunkPartInput, lambda value: value.artifact)
        artifact = valid_preparation_field(part, artifact_field)
        if artifact is not None and (artifact.kind is not ArtifactKind.BLOB
                or artifact.format_key != FINE_TERRAIN_FORMAT_KEY or artifact.format_version != FINE_TERRAIN_STORAGE_VERSION):
            _issue(errors, PackPreparationIssueCode.FORMAT_MISMATCH, part_path.field(artifact_field), "unsupported fine terrain descriptor")
        base = preparation_field_value(state, FieldRef(lambda: PackPreparationState, lambda value: value.base_publication))
        world = valid_preparation_field(base, FieldRef(lambda: WorldPublicationRef, lambda value: value.world_uid))
        origin_field = FieldRef(lambda: PackWildernessChunkPartInput, lambda value: value.provenance)
        origin = preparation_field_value(part, origin_field)
        inherited = valid_preparation_field(origin, FieldRef(lambda: PackInheritedPartProvenance, lambda value: value.kind))
        if inherited is not None:
            _issue(errors, PackPreparationIssueCode.SOURCE_PROOF_MISMATCH, part_path.field(origin_field), "inherited input requires verified admission")
        elif valid_preparation_field(origin, FieldRef(lambda: PackNewPartProvenance, lambda value: value.kind)) is not None:
            stored = preparation_field_value(origin, FieldRef(lambda: PackNewPartProvenance, lambda value: value.provenance))
            proof = preparation_field_value(stored, FieldRef(lambda: PackStoredProvenance, lambda value: value.source_proof))
            proof_world = valid_preparation_field(proof, FieldRef(lambda: SourceDurableProof, lambda value: value.world_uid))
            if world is not None and proof_world is not None and world != proof_world:
                _issue(errors, PackPreparationIssueCode.SOURCE_PROOF_MISMATCH, part_path.field(origin_field), "proof belongs to another world")
        MetadataEvidenceValidator().check(model, item, world, path, errors)
