"""Individual pure composition operations; sequencing belongs to the caller DAG."""

from typing import TypeVar

from pydantic import BaseModel
from app.dataModel.fields.fieldBinding import bind_field
from app.dataModel.worldPack.preparation.provenance import PackInheritedPartProvenance
from app.dataModel.artifacts.references import ArtifactKind
from app.dataModel.worldPack.meta.parts import PackStoredPart
from app.dataModel.worldPack.preparation.parts import PackCoarseClimatePartInput, PackLocationsIndexPartInput
from app.dataModel.worldPack.meta.locationsIndexStorageFormat import LOCATIONS_INDEX_FORMAT_KEY, LOCATIONS_INDEX_FORMAT_VERSION
from app.dataModel.worldPack.preparation.operations import PackLocationsIndexInput
from app.dataModel.worldPack.preparation.errors import PackPreparationIssue, PackPreparationIssueCode
from app.dataModel.worldPack.wire.climateFieldWire import CLIMATE_FIELD_FORMAT_KEY, CLIMATE_FIELD_FORMAT_VERSION

from app.application.worldData.pack.preparation.errors import (
    preparation_errors, raise_preparation_errors, validate_preparation_input, valid_preparation_field,
)
from app.application.worldData.pack.preparation.packPreparationValidator import PackPreparationValidator
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.worldPack.preparation.errors import PackPreparationFailureReason
from app.dataModel.worldPack.preparation.operations import (
    PackDeletePartInput, PackDeleteLocationTerrainInput, PackDeleteSettlementStructureInput, PackCoarseClimateInput,
)
from app.dataModel.worldPack.preparation.addresses import (
    PackPartAddress, PackAssemblyAddress, PackLocationMetadataAddress, PackSettlementMetadataAddress,
)
from app.dataModel.worldPack.preparation.assembly import PackAssemblyInput
from app.dataModel.worldPack.preparation.state import PackPreparationState

RequestT = TypeVar("RequestT", bound=BaseModel)


def _admit(model: type[RequestT], request: RequestT,
           state_field: FieldRef[RequestT, PackPreparationState]) -> RequestT:
    errors = preparation_errors()
    checked = validate_preparation_input(model, request, errors)
    raw_state = vars(request).get(bind_field(state_field).field) if isinstance(request, model) else None
    if isinstance(raw_state, PackPreparationState):
        validator = PackPreparationValidator()
        path = CheckedPath.root(model).field(state_field)
        validator.check_state_identities(raw_state, path, errors)
        validator.check_metadata_groups(raw_state, path, errors)
    raise_preparation_errors(errors, PackPreparationFailureReason.DEPENDENCY_MISMATCH)
    assert checked is not None
    return checked


def _without_representation(state: PackPreparationState, address: PackPartAddress,
                            metadata_address: PackAssemblyAddress, assembly: PackAssemblyInput) -> PackPreparationState:
    result = PackPreparationState(
        base_publication=state.base_publication,
        parts=tuple(part for part in state.parts if part.address != address), assembly=assembly,
        assembly_provenance=tuple(entry for entry in state.assembly_provenance if entry.address != metadata_address),
        metadata_dependencies=tuple(entry for entry in state.metadata_dependencies if entry.subject.address != metadata_address),
    )
    return PackPreparationValidator().validate_state(result)


class PackPreparationService:
    def replace_locations_index(self, request: PackLocationsIndexInput) -> PackPreparationState:
        errors = preparation_errors()
        checked = validate_preparation_input(PackLocationsIndexInput, request, errors)
        validator = PackPreparationValidator()
        state_ref = FieldRef(lambda: PackLocationsIndexInput, lambda value: value.state)
        part = valid_preparation_field(request, FieldRef(lambda: PackLocationsIndexInput, lambda value: value.part))
        raw_state = vars(request).get(bind_field(state_ref).field) if isinstance(request, PackLocationsIndexInput) else None
        base = valid_preparation_field(raw_state, FieldRef(lambda: PackPreparationState, lambda value: value.base_publication))
        if isinstance(raw_state, PackPreparationState):
            state_path = CheckedPath.root(PackLocationsIndexInput).field(state_ref)
            validator.check_state_identities(raw_state, state_path, errors)
            validator.check_metadata_groups(raw_state, state_path, errors)
        if part is not None:
            root = CheckedPath.root(PackLocationsIndexInput)
            part_path = root.field(FieldRef(lambda: PackLocationsIndexInput, lambda value: value.part))
            artifact_field = FieldRef(lambda: PackLocationsIndexPartInput, lambda value: value.artifact)
            artifact = artifact_field.select(part)
            if (artifact.kind is not ArtifactKind.BLOB or artifact.format_key != LOCATIONS_INDEX_FORMAT_KEY
                    or artifact.format_version != LOCATIONS_INDEX_FORMAT_VERSION):
                errors.add(PackPreparationIssue(code=PackPreparationIssueCode.FORMAT_MISMATCH,
                    path=part_path.field(artifact_field).freeze(), message="unsupported locations index descriptor"))
            provenance_field = FieldRef(lambda: PackLocationsIndexPartInput, lambda value: value.provenance)
            if isinstance(part.provenance, PackInheritedPartProvenance):
                errors.add(PackPreparationIssue(code=PackPreparationIssueCode.SOURCE_PROOF_MISMATCH,
                    path=part_path.field(provenance_field).freeze(), message="inherited input requires verified pinned-base admission; unavailable in this pure write"))
            if base is not None and provenance_field.select(part).provenance.source_proof.world_uid != base.world_uid:
                errors.add(PackPreparationIssue(code=PackPreparationIssueCode.SOURCE_PROOF_MISMATCH,
                    path=part_path.field(provenance_field).freeze(), message="index proof belongs to another world"))
        raise_preparation_errors(errors, PackPreparationFailureReason.DEPENDENCY_MISMATCH)
        assert checked is not None
        state = checked.state
        stored = PackStoredPart(address=checked.part.address, artifact=checked.part.artifact,
                                provenance=checked.part.provenance.provenance)
        existing = any(part.address == stored.address for part in state.parts)
        parts = tuple(stored if part.address == stored.address else part for part in state.parts)
        if not existing:
            parts = (*parts, stored)
        result = PackPreparationState(base_publication=state.base_publication, parts=parts, assembly=state.assembly,
            assembly_provenance=state.assembly_provenance, metadata_dependencies=state.metadata_dependencies)
        return validator.validate_state(result)

    def write_coarse_climate(self, request: PackCoarseClimateInput) -> PackPreparationState:
        errors = preparation_errors()
        checked = validate_preparation_input(PackCoarseClimateInput, request, errors)
        validator = PackPreparationValidator()
        state_ref = FieldRef(lambda: PackCoarseClimateInput, lambda value: value.state)
        part = valid_preparation_field(request, FieldRef(lambda: PackCoarseClimateInput, lambda value: value.part))
        raw_state = vars(request).get(bind_field(state_ref).field) if isinstance(request, PackCoarseClimateInput) else None
        base = valid_preparation_field(raw_state, FieldRef(lambda: PackPreparationState, lambda value: value.base_publication))
        if isinstance(raw_state, PackPreparationState):
            state_path = CheckedPath.root(PackCoarseClimateInput).field(state_ref)
            validator.check_state_identities(raw_state, state_path, errors)
            validator.check_metadata_groups(raw_state, state_path, errors)
        if part is not None:
            root = CheckedPath.root(PackCoarseClimateInput)
            part_path = root.field(FieldRef(lambda: PackCoarseClimateInput, lambda value: value.part))
            artifact_field = FieldRef(lambda: PackCoarseClimatePartInput, lambda value: value.artifact)
            artifact = artifact_field.select(part)
            if (artifact.kind is not ArtifactKind.BLOB or artifact.format_key != CLIMATE_FIELD_FORMAT_KEY
                    or artifact.format_version != CLIMATE_FIELD_FORMAT_VERSION):
                errors.add(PackPreparationIssue(code=PackPreparationIssueCode.FORMAT_MISMATCH,
                    path=part_path.field(artifact_field).freeze(), message="unsupported climate field descriptor"))
            provenance_field = FieldRef(lambda: PackCoarseClimatePartInput, lambda value: value.provenance)
            if isinstance(part.provenance, PackInheritedPartProvenance):
                errors.add(PackPreparationIssue(code=PackPreparationIssueCode.SOURCE_PROOF_MISMATCH,
                    path=part_path.field(provenance_field).freeze(), message="inherited input requires verified pinned-base admission; unavailable in this pure write"))
            if base is not None and provenance_field.select(part).provenance.source_proof.world_uid != base.world_uid:
                errors.add(PackPreparationIssue(code=PackPreparationIssueCode.SOURCE_PROOF_MISMATCH,
                    path=part_path.field(provenance_field).freeze(), message="climate proof belongs to another world"))
        raise_preparation_errors(errors, PackPreparationFailureReason.DEPENDENCY_MISMATCH)
        assert checked is not None
        state = checked.state
        stored = PackStoredPart(address=checked.part.address, artifact=checked.part.artifact,
                                provenance=checked.part.provenance.provenance)
        existing = any(part.address == stored.address for part in state.parts)
        parts = tuple(stored if part.address == stored.address else part for part in state.parts)
        if not existing:
            parts = (*parts, stored)
        result = PackPreparationState(base_publication=state.base_publication, parts=parts, assembly=state.assembly,
            assembly_provenance=state.assembly_provenance, metadata_dependencies=state.metadata_dependencies)
        return validator.validate_state(result)

    def delete_location_terrain(self, request: PackDeleteLocationTerrainInput) -> PackPreparationState:
        checked = _admit(PackDeleteLocationTerrainInput, request,
                         FieldRef(lambda: PackDeleteLocationTerrainInput, lambda value: value.state))
        state = checked.state
        assembly = state.assembly.model_copy(update={"locations": tuple(
            row for row in state.assembly.locations if row.location_uid != checked.address.location_uid)})
        return _without_representation(state, checked.address,
            PackLocationMetadataAddress(kind="location", location_uid=checked.address.location_uid), assembly)

    def delete_settlement_structure(self, request: PackDeleteSettlementStructureInput) -> PackPreparationState:
        checked = _admit(PackDeleteSettlementStructureInput, request,
                         FieldRef(lambda: PackDeleteSettlementStructureInput, lambda value: value.state))
        state = checked.state
        assembly = state.assembly.model_copy(update={"settlements": tuple(
            row for row in state.assembly.settlements if row.location_uid != checked.address.location_uid)})
        return _without_representation(state, checked.address,
            PackSettlementMetadataAddress(kind="settlement", location_uid=checked.address.location_uid), assembly)

    def delete_part(self, request: PackDeletePartInput) -> PackPreparationState:
        checked = _admit(PackDeletePartInput, request, FieldRef(lambda: PackDeletePartInput, lambda value: value.state))
        validator = PackPreparationValidator()
        state = checked.state
        remaining = tuple(part for part in state.parts if part.address != checked.address)
        if len(remaining) == len(state.parts):
            return state
        result = PackPreparationState(
            base_publication=state.base_publication, parts=remaining, assembly=state.assembly,
            assembly_provenance=state.assembly_provenance, metadata_dependencies=state.metadata_dependencies,
        )
        return validator.validate_state(result)
