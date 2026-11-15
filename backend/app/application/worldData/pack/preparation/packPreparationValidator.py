"""Pure identity and uniqueness admission of an intermediate Pack composition."""

from collections.abc import Iterable
from typing import TypeVar

from pydantic import BaseModel

from app.application.worldData.pack.preparation.errors import preparation_errors, raise_preparation_errors, validate_preparation_input
from app.application.worldData.pack.preparation.errors import valid_preparation_field, valid_preparation_items
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.dataModel.sourceVersioning.sourceProofInput import SourceProofInput
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.worldPack.meta.metadataAttribution import (
    PackStoredAssemblyProvenance, PackMetadataAttribution, PackMetadataGroup,
    PackMetadataGroupAdmission, PackWildernessStatusBasis,
)
from app.dataModel.worldPack.preparation.addresses import PackAssemblyAddress, PackTileMetadataAddress
from app.dataModel.worldPack.meta.parts import PackStoredPart
from app.dataModel.worldPack.preparation.assembly import PackAssemblyInput, PackTileAssembly
from app.dataModel.worldPack.preparation.errors import PackPreparationDiagnostic, PackPreparationFailureReason, PackPreparationIssue, PackPreparationIssueCode
from app.dataModel.worldPack.preparation.metadataDependencies import PackMetadataDependencyUse, PackMetadataDescription
from app.dataModel.worldPack.preparation.metadataSubject import PackMetadataSubject
from app.dataModel.worldPack.preparation.provenance import PackStoredProvenance
from app.dataModel.worldPack.preparation.state import PackPreparationState

RootT = TypeVar("RootT", bound=BaseModel)
ValueT = TypeVar("ValueT")


def _duplicates(keys: Iterable[object]) -> Iterable[int]:
    seen: set[object] = set()
    for index, key in enumerate(keys):
        if key in seen:
            yield index
        seen.add(key)


def _issue(errors: ValidatorAggregationHelper[PackPreparationDiagnostic], code: PackPreparationIssueCode,
           path: CheckedPath[RootT, ValueT], message: str) -> None:
    errors.add(PackPreparationIssue(code=code, path=path.freeze(), message=message))


class PackPreparationValidator:
    def validate_state(self, state: PackPreparationState) -> PackPreparationState:
        """Structural admission followed by local identities; no final completeness or IO."""
        errors = preparation_errors()
        checked = validate_preparation_input(PackPreparationState, state, errors)
        self.check_state_identities(state, CheckedPath.root(PackPreparationState), errors)
        self.check_metadata_groups(state, CheckedPath.root(PackPreparationState), errors)
        raise_preparation_errors(errors, PackPreparationFailureReason.DEPENDENCY_MISMATCH)
        assert checked is not None
        return checked

    def check_metadata_groups(
        self, state: PackPreparationState, path: CheckedPath[RootT, PackPreparationState],
        errors: ValidatorAggregationHelper[PackPreparationDiagnostic],
    ) -> None:
        transient = FieldRef(lambda: PackPreparationState, lambda value: value.metadata_dependencies)
        dependencies = FieldRef(lambda: PackMetadataDescription, lambda value: value.dependencies)
        for index, description in enumerate(valid_preparation_field(state, transient) or ()):
            group_path = path.field(transient).item(index).field(dependencies)
            for use_index, use in enumerate(dependencies.select(description)):
                self._check_group(description.subject.address, use.group, use.basis,
                    group_path.item(use_index).field(FieldRef(lambda: PackMetadataDependencyUse, lambda value: value.group)),
                    group_path.item(use_index).field(FieldRef(lambda: PackMetadataDependencyUse, lambda value: value.basis)), errors)
            self._check_group_completeness(description.subject.address,
                (use.group for use in dependencies.select(description)), group_path, errors)
        stored = FieldRef(lambda: PackPreparationState, lambda value: value.assembly_provenance)
        attribution = FieldRef(lambda: PackStoredAssemblyProvenance, lambda value: value.attribution)
        groups = FieldRef(lambda: PackMetadataAttribution, lambda value: value.groups)
        group_field = FieldRef(lambda: PackMetadataGroupAdmission, lambda value: value.group)
        basis_field = FieldRef(lambda: PackMetadataGroupAdmission, lambda value: value.basis)
        for index, entry in enumerate(valid_preparation_field(state, stored) or ()):
            detail = attribution.select(entry)
            if detail is None:
                continue
            group_path = path.field(stored).item(index).field(attribution).present().field(groups)
            for duplicate in _duplicates(group_field.select(group) for group in groups.select(detail)):
                _issue(errors, PackPreparationIssueCode.METADATA_GROUP_MISMATCH,
                       group_path.item(duplicate).field(group_field), "duplicate stored metadata group")
            for group_index, group in enumerate(groups.select(detail)):
                self._check_group(entry.address, group_field.select(group), basis_field.select(group),
                                  group_path.item(group_index).field(group_field),
                                  group_path.item(group_index).field(basis_field), errors)
            self._check_group_completeness(entry.address,
                (group_field.select(group) for group in groups.select(detail)), group_path, errors)

    def _check_group_completeness(
        self, address: PackAssemblyAddress, groups: Iterable[PackMetadataGroup],
        path: CheckedPath[RootT, ValueT], errors: ValidatorAggregationHelper[PackPreparationDiagnostic],
    ) -> None:
        present = set(groups)
        missing = tuple(group for group in self._required_groups(address) if group not in present)
        if missing:
            _issue(errors, PackPreparationIssueCode.METADATA_GROUP_MISMATCH, path,
                   "missing metadata groups: " + ", ".join(group.value for group in missing))

    @staticmethod
    def _required_groups(address: PackAssemblyAddress) -> tuple[PackMetadataGroup, ...]:
        G = PackMetadataGroup
        allowed = {
            "header": (G.LAST_L0_MODE, G.FINE_CELLS_PER_MAP_CELL, G.WORLD_MAP_CELLS_PER_TILE,
                       G.FINE_CELL_SIZE, G.MAP_SUBSURFACE_DEPTH, G.TERRAIN_CHUNK_COLUMNS),
            "tile": (G.IDENTITY, G.CLIMATE_STATUS, G.WILDERNESS_REFINE_STATUS),
            "chunk": (G.IDENTITY, G.REFINE_ROLE),
            "location": (G.IDENTITY, G.TERRITORY_VOLUME, G.CLIMATE_STATUS),
            "settlement": (G.IDENTITY, G.TERRITORY_VOLUME, G.PACKED_DISTRICT_UIDS, G.STRUCTURE_STATUS),
            "region": (G.IDENTITY, G.ENTRY_TYPE, G.CURRENT_TYPE, G.BBOX, G.REGION_STATUS,
                       G.PARENT_REGION_UID, G.SPEC_FINGERPRINT),
        }
        return allowed[address.kind]

    def _check_group(
        self, address: PackAssemblyAddress, group: PackMetadataGroup, basis: PackWildernessStatusBasis | None,
        group_path: CheckedPath[RootT, PackMetadataGroup],
        basis_path: CheckedPath[RootT, PackWildernessStatusBasis | None],
        errors: ValidatorAggregationHelper[PackPreparationDiagnostic],
    ) -> None:
        if group not in self._required_groups(address):
            _issue(errors, PackPreparationIssueCode.METADATA_GROUP_MISMATCH, group_path,
                   "metadata group does not belong to address kind")
        if (basis is not None) != (group is PackMetadataGroup.WILDERNESS_REFINE_STATUS):
            _issue(errors, PackPreparationIssueCode.METADATA_BASIS_MISMATCH, basis_path,
                   "basis is required exactly for wilderness status")
        if basis is not None:
            chunks = FieldRef(lambda: PackWildernessStatusBasis, lambda value: value.chunk_addresses)
            chunks_path = basis_path.present().field(chunks)
            for duplicate in _duplicates(chunks.select(basis)):
                _issue(errors, PackPreparationIssueCode.METADATA_BASIS_MISMATCH,
                       chunks_path.item(duplicate), "duplicate basis chunk")
            if isinstance(address, PackTileMetadataAddress):
                for index, chunk in enumerate(chunks.select(basis)):
                    if (chunk.gx, chunk.gy) != (address.gx, address.gy):
                        _issue(errors, PackPreparationIssueCode.METADATA_BASIS_MISMATCH,
                               chunks_path.item(index), "basis chunk belongs to another tile")

    def check_state_identities(
        self, state: PackPreparationState, path: CheckedPath[RootT, PackPreparationState],
        errors: ValidatorAggregationHelper[PackPreparationDiagnostic],
    ) -> None:
        """Collect local identity issues under the calling operation's named input path."""
        base = valid_preparation_field(state, FieldRef(lambda: PackPreparationState, lambda value: value.base_publication))
        world = base.world_uid if base is not None else None
        parts_field = FieldRef(lambda: PackPreparationState, lambda value: value.parts)
        parts = valid_preparation_items(state, parts_field)
        parts_path = path.field(parts_field)
        address_field = FieldRef(lambda: PackStoredPart, lambda value: value.address)
        for position in _duplicates(address_field.select(part) for _, part in parts):
            index = parts[position][0]
            _issue(errors, PackPreparationIssueCode.DUPLICATE_ADDRESS,
                   parts_path.item(index).field(address_field), "duplicate part address")
        provenance_field = FieldRef(lambda: PackStoredPart, lambda value: value.provenance)
        proof_field = FieldRef(lambda: PackStoredProvenance, lambda value: value.source_proof)
        world_field = FieldRef(lambda: SourceDurableProof, lambda value: value.world_uid)
        for index, part in parts:
            if world is not None and world_field.select(proof_field.select(provenance_field.select(part))) != world:
                _issue(errors, PackPreparationIssueCode.SOURCE_PROOF_MISMATCH,
                       parts_path.item(index).field(provenance_field).field(proof_field).field(world_field),
                       "part proof belongs to another world")

        stored_field = FieldRef(lambda: PackPreparationState, lambda value: value.assembly_provenance)
        stored = valid_preparation_field(state, stored_field) or ()
        stored_path = path.field(stored_field)
        stored_address = FieldRef(lambda: PackStoredAssemblyProvenance, lambda value: value.address)
        stored_provenance = FieldRef(lambda: PackStoredAssemblyProvenance, lambda value: value.provenance)
        for index in _duplicates(stored_address.select(entry) for entry in stored):
            _issue(errors, PackPreparationIssueCode.DUPLICATE_ADDRESS,
                   stored_path.item(index).field(stored_address), "duplicate metadata provenance address")
        for index, entry in enumerate(stored):
            if world is not None and world_field.select(proof_field.select(stored_provenance.select(entry))) != world:
                _issue(errors, PackPreparationIssueCode.SOURCE_PROOF_MISMATCH,
                       stored_path.item(index).field(stored_provenance).field(proof_field).field(world_field),
                       "metadata proof belongs to another world")

        descriptions_field = FieldRef(lambda: PackPreparationState, lambda value: value.metadata_dependencies)
        descriptions = valid_preparation_field(state, descriptions_field) or ()
        descriptions_path = path.field(descriptions_field)
        subject_field = FieldRef(lambda: PackMetadataDescription, lambda value: value.subject)
        subject_address = FieldRef(lambda: PackMetadataSubject, lambda value: value.address)
        subject_base = FieldRef(lambda: PackMetadataSubject, lambda value: value.base_publication)
        for index in _duplicates(subject_address.select(subject_field.select(entry)) for entry in descriptions):
            _issue(errors, PackPreparationIssueCode.DUPLICATE_ADDRESS,
                   descriptions_path.item(index).field(subject_field).field(subject_address),
                   "duplicate metadata dependency address")
        dependencies_field = FieldRef(lambda: PackMetadataDescription, lambda value: value.dependencies)
        group_field = FieldRef(lambda: PackMetadataDependencyUse, lambda value: value.group)
        usage_field = FieldRef(lambda: PackMetadataDependencyUse, lambda value: value.source_usage)
        usage_world = FieldRef(lambda: SourceProofInput, lambda value: value.world_uid)
        for index, entry in enumerate(descriptions):
            entry_path = descriptions_path.item(index)
            if base is not None and subject_base.select(subject_field.select(entry)) != base:
                _issue(errors, PackPreparationIssueCode.BASE_PUBLICATION_MISMATCH,
                       entry_path.field(subject_field).field(subject_base), "metadata subject uses another base")
            dependencies = dependencies_field.select(entry)
            dependency_path = entry_path.field(dependencies_field)
            for duplicate in _duplicates(group_field.select(use) for use in dependencies):
                _issue(errors, PackPreparationIssueCode.METADATA_GROUP_MISMATCH,
                       dependency_path.item(duplicate).field(group_field), "duplicate metadata group")
            for use_index, use in enumerate(dependencies):
                if world is not None and usage_world.select(usage_field.select(use)) != world:
                    _issue(errors, PackPreparationIssueCode.SOURCE_PROOF_MISMATCH,
                           dependency_path.item(use_index).field(usage_field).field(usage_world),
                           "metadata usage belongs to another world")

        assembly_path = path.field(FieldRef(lambda: PackPreparationState, lambda value: value.assembly))
        tiles_field = FieldRef(lambda: PackAssemblyInput, lambda value: value.tiles)
        assembly = vars(state).get("assembly") if isinstance(state, PackPreparationState) else None
        tiles = valid_preparation_field(assembly, tiles_field) or ()
        tiles_path = assembly_path.field(tiles_field)
        for index in _duplicates((tile.gx, tile.gy) for tile in tiles):
            _issue(errors, PackPreparationIssueCode.DUPLICATE_ADDRESS, tiles_path.item(index), "duplicate tile")
        chunks_field = FieldRef(lambda: PackTileAssembly, lambda value: value.chunks)
        for index, tile in enumerate(tiles):
            for duplicate in _duplicates((chunk.cx, chunk.cy) for chunk in chunks_field.select(tile)):
                _issue(errors, PackPreparationIssueCode.DUPLICATE_ADDRESS,
                       tiles_path.item(index).field(chunks_field).item(duplicate), "duplicate chunk in tile")
        locations_field = FieldRef(lambda: PackAssemblyInput, lambda value: value.locations)
        for index in _duplicates(row.location_uid for row in (valid_preparation_field(assembly, locations_field) or ())):
            _issue(errors, PackPreparationIssueCode.DUPLICATE_ADDRESS,
                   assembly_path.field(locations_field).item(index), "duplicate location")
        settlements_field = FieldRef(lambda: PackAssemblyInput, lambda value: value.settlements)
        for index in _duplicates(row.location_uid for row in (valid_preparation_field(assembly, settlements_field) or ())):
            _issue(errors, PackPreparationIssueCode.DUPLICATE_ADDRESS,
                   assembly_path.field(settlements_field).item(index), "duplicate settlement")
        regions_field = FieldRef(lambda: PackAssemblyInput, lambda value: value.wilderness_regions)
        for index in _duplicates(row.region_uid for row in (valid_preparation_field(assembly, regions_field) or ())):
            _issue(errors, PackPreparationIssueCode.DUPLICATE_ADDRESS,
                   assembly_path.field(regions_field).item(index), "duplicate region")
