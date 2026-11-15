"""Individual pure composition operations; sequencing belongs to the caller DAG."""

from typing import TypeVar

from pydantic import BaseModel, ValidationError
from app.dataModel.fields.fieldBinding import bind_field
from app.dataModel.worldPack.preparation.provenance import PackInheritedPartProvenance
from app.dataModel.artifacts.references import ArtifactKind
from app.dataModel.worldPack.meta.parts import PackStoredPart
from app.dataModel.worldPack.preparation.parts import PackCoarseClimatePartInput, PackLocationsIndexPartInput
from app.dataModel.worldPack.meta.locationsIndexStorageFormat import LOCATIONS_INDEX_FORMAT_KEY, LOCATIONS_INDEX_FORMAT_VERSION
from app.dataModel.worldPack.preparation.operations import PackLocationsIndexInput
from app.dataModel.worldPack.preparation.operations import PackPreparationEmptyInput
from app.dataModel.worldPack.preparation.errors import PackPreparationIssue, PackPreparationIssueCode
from app.dataModel.worldPack.wire.climateFieldWire import CLIMATE_FIELD_FORMAT_KEY, CLIMATE_FIELD_FORMAT_VERSION

from app.application.worldData.pack.preparation.errors import (
    preparation_errors, raise_preparation_errors, validate_preparation_input, valid_preparation_field, preparation_field_value,
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
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldPack.preparation.operations import PackSpatialRootInput
from app.dataModel.worldPack.preparation.parts import PackSpatialRootPartInput
from app.dataModel.worldPack.preparation.addresses import PackSpatialRootAddress
from app.dataModel.worldPack.meta.spatial.domainRoot import SpatialDomainRootRef

RequestT = TypeVar("RequestT", bound=BaseModel)
CollectionItemT = TypeVar("CollectionItemT")


def _admit(model: type[RequestT], request: RequestT,
           state_field: FieldRef[RequestT, PackPreparationState]) -> RequestT:
    errors = preparation_errors()
    checked = validate_preparation_input(model, request, errors)
    raw_state = preparation_field_value(checked if checked is not None else request, state_field)
    if isinstance(raw_state, (PackPreparationState, dict)):
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
    def write_spatial_root(self, request: PackSpatialRootInput) -> PackPreparationState:
        errors = preparation_errors()
        checked = validate_preparation_input(PackSpatialRootInput, request, errors)
        admitted = checked if checked is not None else request
        path = CheckedPath.root(PackSpatialRootInput)
        state_ref = FieldRef(lambda: PackSpatialRootInput, lambda value: value.state)
        part_ref = FieldRef(lambda: PackSpatialRootInput, lambda value: value.part)
        state = preparation_field_value(admitted, state_ref)
        part = preparation_field_value(admitted, part_ref)
        validator = PackPreparationValidator()
        validator.check_state_identities(state, path.field(state_ref), errors)
        validator.check_metadata_groups(state, path.field(state_ref), errors)
        address_ref = FieldRef(lambda: PackSpatialRootPartInput, lambda value: value.address)
        address = preparation_field_value(part, address_ref)
        domain = valid_preparation_field(address, FieldRef(lambda: PackSpatialRootAddress, lambda value: value.domain))
        artifact_ref = FieldRef(lambda: PackSpatialRootPartInput, lambda value: value.artifact)
        artifact = valid_preparation_field(part, artifact_ref)
        if domain is not None and artifact is not None:
            try:
                SpatialDomainRootRef(domain=domain, root=artifact)
            except ValidationError:
                errors.add(PackPreparationIssue(code=PackPreparationIssueCode.FORMAT_MISMATCH,
                    path=path.field(part_ref).field(artifact_ref).freeze(), message="unsupported spatial root descriptor"))
        provenance_ref = FieldRef(lambda: PackSpatialRootPartInput, lambda value: value.provenance)
        provenance = valid_preparation_field(part, provenance_ref)
        base = preparation_field_value(state, FieldRef(lambda: PackPreparationState, lambda value: value.base_publication))
        world = valid_preparation_field(base, FieldRef(lambda: WorldPublicationRef, lambda value: value.world_uid))
        if isinstance(provenance, PackInheritedPartProvenance):
            errors.add(PackPreparationIssue(code=PackPreparationIssueCode.SOURCE_PROOF_MISMATCH,
                path=path.field(part_ref).field(provenance_ref).freeze(),
                message="inherited input requires verified pinned-base admission; unavailable in this pure write"))
        elif provenance is not None and world is not None and provenance.provenance.source_proof.world_uid != world:
            errors.add(PackPreparationIssue(code=PackPreparationIssueCode.SOURCE_PROOF_MISMATCH,
                path=path.field(part_ref).field(provenance_ref).freeze(), message="spatial proof belongs to another world"))
        raise_preparation_errors(errors, PackPreparationFailureReason.DEPENDENCY_MISMATCH)
        assert checked is not None
        stored = PackStoredPart(address=checked.part.address, artifact=checked.part.artifact,
                                provenance=checked.part.provenance.provenance)
        parts = tuple(stored if row.address == stored.address else row for row in checked.state.parts)
        if not any(row.address == stored.address for row in checked.state.parts):
            parts = (*parts, stored)
        result = PackPreparationState(base_publication=checked.state.base_publication, parts=parts,
            assembly=checked.state.assembly, assembly_provenance=checked.state.assembly_provenance,
            metadata_dependencies=checked.state.metadata_dependencies)
        return validator.validate_state(result)

    def start_empty(self, request: PackPreparationEmptyInput) -> PackPreparationState:
        errors = preparation_errors()
        checked = validate_preparation_input(PackPreparationEmptyInput, request, errors)
        admitted = checked if checked is not None else request
        path = CheckedPath.root(PackPreparationEmptyInput)
        base_ref = FieldRef(lambda: PackPreparationEmptyInput, lambda value: value.base_publication)
        assembly_ref = FieldRef(lambda: PackPreparationEmptyInput, lambda value: value.initial_assembly)
        base = preparation_field_value(admitted, base_ref)
        pack_hash = valid_preparation_field(base, FieldRef(lambda: WorldPublicationRef, lambda value: value.pack_hash))
        if pack_hash is not None:
            errors.add(PackPreparationIssue(code=PackPreparationIssueCode.BASE_PUBLICATION_MISMATCH,
                path=path.field(base_ref).freeze(), message="empty preparation requires a publication without Pack"))
        assembly = preparation_field_value(admitted, assembly_ref)
        def require_empty(collection_ref: FieldRef[PackAssemblyInput, tuple[CollectionItemT, ...]]) -> None:
            collection = preparation_field_value(assembly, collection_ref)
            if isinstance(collection, tuple) and collection:
                errors.add(PackPreparationIssue(code=PackPreparationIssueCode.METADATA_INPUT_MISMATCH,
                    path=path.field(assembly_ref).field(collection_ref).freeze(),
                    message="empty preparation requires an empty metadata collection"))
        require_empty(FieldRef(lambda: PackAssemblyInput, lambda value: value.tiles))
        require_empty(FieldRef(lambda: PackAssemblyInput, lambda value: value.locations))
        require_empty(FieldRef(lambda: PackAssemblyInput, lambda value: value.settlements))
        require_empty(FieldRef(lambda: PackAssemblyInput, lambda value: value.wilderness_regions))
        raise_preparation_errors(errors, PackPreparationFailureReason.DEPENDENCY_MISMATCH)
        assert checked is not None
        return PackPreparationState(base_publication=checked.base_publication, assembly=checked.initial_assembly,
                                    parts=(), assembly_provenance=(), metadata_dependencies=())

    def replace_locations_index(self, request: PackLocationsIndexInput) -> PackPreparationState:
        errors = preparation_errors()
        checked = validate_preparation_input(PackLocationsIndexInput, request, errors)
        validator = PackPreparationValidator()
        state_ref = FieldRef(lambda: PackLocationsIndexInput, lambda value: value.state)
        part_ref = FieldRef(lambda: PackLocationsIndexInput, lambda value: value.part)
        admitted = checked if checked is not None else request
        part = preparation_field_value(admitted, part_ref)
        raw_state = preparation_field_value(admitted, state_ref)
        base = valid_preparation_field(raw_state, FieldRef(lambda: PackPreparationState, lambda value: value.base_publication))
        if isinstance(raw_state, (PackPreparationState, dict)):
            state_path = CheckedPath.root(PackLocationsIndexInput).field(state_ref)
            validator.check_state_identities(raw_state, state_path, errors)
            validator.check_metadata_groups(raw_state, state_path, errors)
        if part is not None:
            root = CheckedPath.root(PackLocationsIndexInput)
            part_path = root.field(FieldRef(lambda: PackLocationsIndexInput, lambda value: value.part))
            artifact_field = FieldRef(lambda: PackLocationsIndexPartInput, lambda value: value.artifact)
            artifact = valid_preparation_field(part, artifact_field)
            if artifact is not None and (artifact.kind is not ArtifactKind.BLOB or artifact.format_key != LOCATIONS_INDEX_FORMAT_KEY
                    or artifact.format_version != LOCATIONS_INDEX_FORMAT_VERSION):
                errors.add(PackPreparationIssue(code=PackPreparationIssueCode.FORMAT_MISMATCH,
                    path=part_path.field(artifact_field).freeze(), message="unsupported locations index descriptor"))
            provenance_field = FieldRef(lambda: PackLocationsIndexPartInput, lambda value: value.provenance)
            provenance = valid_preparation_field(part, provenance_field)
            if isinstance(provenance, PackInheritedPartProvenance):
                errors.add(PackPreparationIssue(code=PackPreparationIssueCode.SOURCE_PROOF_MISMATCH,
                    path=part_path.field(provenance_field).freeze(), message="inherited input requires verified pinned-base admission; unavailable in this pure write"))
            if base is not None and provenance is not None and provenance.provenance.source_proof.world_uid != base.world_uid:
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
        part_ref = FieldRef(lambda: PackCoarseClimateInput, lambda value: value.part)
        admitted = checked if checked is not None else request
        part = preparation_field_value(admitted, part_ref)
        raw_state = preparation_field_value(admitted, state_ref)
        base = valid_preparation_field(raw_state, FieldRef(lambda: PackPreparationState, lambda value: value.base_publication))
        if isinstance(raw_state, (PackPreparationState, dict)):
            state_path = CheckedPath.root(PackCoarseClimateInput).field(state_ref)
            validator.check_state_identities(raw_state, state_path, errors)
            validator.check_metadata_groups(raw_state, state_path, errors)
        if part is not None:
            root = CheckedPath.root(PackCoarseClimateInput)
            part_path = root.field(FieldRef(lambda: PackCoarseClimateInput, lambda value: value.part))
            artifact_field = FieldRef(lambda: PackCoarseClimatePartInput, lambda value: value.artifact)
            artifact = valid_preparation_field(part, artifact_field)
            if artifact is not None and (artifact.kind is not ArtifactKind.BLOB or artifact.format_key != CLIMATE_FIELD_FORMAT_KEY
                    or artifact.format_version != CLIMATE_FIELD_FORMAT_VERSION):
                errors.add(PackPreparationIssue(code=PackPreparationIssueCode.FORMAT_MISMATCH,
                    path=part_path.field(artifact_field).freeze(), message="unsupported climate field descriptor"))
            provenance_field = FieldRef(lambda: PackCoarseClimatePartInput, lambda value: value.provenance)
            provenance = valid_preparation_field(part, provenance_field)
            if isinstance(provenance, PackInheritedPartProvenance):
                errors.add(PackPreparationIssue(code=PackPreparationIssueCode.SOURCE_PROOF_MISMATCH,
                    path=part_path.field(provenance_field).freeze(), message="inherited input requires verified pinned-base admission; unavailable in this pure write"))
            if base is not None and provenance is not None and provenance.provenance.source_proof.world_uid != base.world_uid:
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
