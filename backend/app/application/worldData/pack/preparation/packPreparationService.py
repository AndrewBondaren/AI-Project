"""Individual pure composition operations; sequencing belongs to the caller DAG."""

from typing import TypeVar

from pydantic import BaseModel

from app.application.worldData.pack.preparation.errors import (
    preparation_errors, raise_preparation_errors, validate_preparation_input,
)
from app.application.worldData.pack.preparation.packPreparationValidator import PackPreparationValidator
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.worldPack.preparation.errors import PackPreparationFailureReason
from app.dataModel.worldPack.preparation.operations import (
    PackDeletePartInput, PackDeleteLocationTerrainInput, PackDeleteSettlementStructureInput,
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
    if checked is not None:
        validator = PackPreparationValidator()
        path = CheckedPath.root(model).field(state_field)
        validator.check_state_identities(state_field.select(checked), path, errors)
        validator.check_metadata_groups(state_field.select(checked), path, errors)
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
