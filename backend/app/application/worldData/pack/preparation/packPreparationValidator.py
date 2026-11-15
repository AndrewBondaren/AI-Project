"""Pure identity and uniqueness admission of an intermediate Pack composition."""

from collections.abc import Iterable
from typing import TypeVar

from pydantic import BaseModel

from app.application.worldData.pack.preparation.errors import preparation_errors, raise_preparation_errors, validate_preparation_input
from app.application.worldData.pack.preparation.errors import valid_preparation_field, valid_preparation_items, preparation_field_value
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
from app.dataModel.worldPack.preparation.assembly import PackAssemblyInput, PackTileAssembly, PackChunkAssembly
from app.dataModel.worldPack.preparation.errors import PackPreparationDiagnostic, PackPreparationFailureReason, PackPreparationIssue, PackPreparationIssueCode
from app.dataModel.worldPack.preparation.metadataDependencies import PackMetadataDependencyUse, PackMetadataDescription
from app.dataModel.worldPack.preparation.metadataSubject import PackMetadataSubject
from app.dataModel.worldPack.preparation.provenance import PackStoredProvenance
from app.dataModel.worldPack.preparation.state import PackPreparationState

RootT = TypeVar("RootT", bound=BaseModel)
ValueT = TypeVar("ValueT")


def _raw_items(value: object, ref: FieldRef[RootT, tuple[ValueT, ...]]) -> tuple[tuple[int, object], ...]:
    raw = preparation_field_value(value, ref)
    return tuple(enumerate(raw)) if isinstance(raw, tuple) else ()


def _coordinates(items: tuple[tuple[int, object], ...], x: FieldRef[RootT, int],
                 y: FieldRef[RootT, int]) -> tuple[tuple[int, tuple[int, int]], ...]:
    result = []
    for index, item in items:
        a, b = valid_preparation_field(item, x), valid_preparation_field(item, y)
        if a is not None and b is not None:
            result.append((index, (a, b)))
    return tuple(result)


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
        admitted = checked if checked is not None else state
        self.check_state_identities(admitted, CheckedPath.root(PackPreparationState), errors)
        self.check_metadata_groups(admitted, CheckedPath.root(PackPreparationState), errors)
        raise_preparation_errors(errors, PackPreparationFailureReason.DEPENDENCY_MISMATCH)
        assert checked is not None
        return checked

    def check_metadata_groups(
        self, state: object, path: CheckedPath[RootT, PackPreparationState],
        errors: ValidatorAggregationHelper[PackPreparationDiagnostic],
    ) -> None:
        transient = FieldRef(lambda: PackPreparationState, lambda value: value.metadata_dependencies)
        dependencies = FieldRef(lambda: PackMetadataDescription, lambda value: value.dependencies)
        raw_descriptions = preparation_field_value(state, transient)
        for index, description in enumerate(raw_descriptions if isinstance(raw_descriptions, tuple) else ()):
            group_path = path.field(transient).item(index).field(dependencies)
            subject = preparation_field_value(description, FieldRef(lambda: PackMetadataDescription, lambda value: value.subject))
            address = valid_preparation_field(subject, FieldRef(lambda: PackMetadataSubject, lambda value: value.address))
            raw_uses = preparation_field_value(description, dependencies)
            group_field = FieldRef(lambda: PackMetadataDependencyUse, lambda value: value.group)
            keys = tuple((i, key) for i, use in enumerate(raw_uses if isinstance(raw_uses, tuple) else ())
                         if (key := valid_preparation_field(use, group_field)) is not None)
            for position in _duplicates(key for _, key in keys):
                _issue(errors, PackPreparationIssueCode.METADATA_GROUP_MISMATCH,
                       group_path.item(keys[position][0]).field(group_field), "duplicate metadata group")
            if address is None:
                continue
            for key_index, key in keys:
                self._check_group_kind(address, key, group_path.item(key_index).field(group_field), errors)
            for use_index, key in keys:
                use = (raw_uses if isinstance(raw_uses, tuple) else ())[use_index]
                basis_ref = FieldRef(lambda: PackMetadataDependencyUse, lambda value: value.basis)
                basis = valid_preparation_field(use, basis_ref)
                if basis is None and preparation_field_value(use, basis_ref) is not None:
                    continue
                self._check_group(address, key, basis,
                    group_path.item(use_index).field(FieldRef(lambda: PackMetadataDependencyUse, lambda value: value.group)),
                    group_path.item(use_index).field(FieldRef(lambda: PackMetadataDependencyUse, lambda value: value.basis)), errors)
            if isinstance(raw_uses, tuple) and len(keys) == len(raw_uses):
                self._check_group_completeness(address, (key for _, key in keys), group_path, errors)
        stored = FieldRef(lambda: PackPreparationState, lambda value: value.assembly_provenance)
        attribution = FieldRef(lambda: PackStoredAssemblyProvenance, lambda value: value.attribution)
        groups = FieldRef(lambda: PackMetadataAttribution, lambda value: value.groups)
        group_field = FieldRef(lambda: PackMetadataGroupAdmission, lambda value: value.group)
        basis_field = FieldRef(lambda: PackMetadataGroupAdmission, lambda value: value.basis)
        raw_stored = preparation_field_value(state, stored)
        for index, entry in enumerate(raw_stored if isinstance(raw_stored, tuple) else ()):
            detail = preparation_field_value(entry, attribution)
            if detail is None:
                continue
            group_path = path.field(stored).item(index).field(attribution).present().field(groups)
            raw_groups = preparation_field_value(detail, groups)
            keys = tuple((i, key) for i, group in enumerate(raw_groups if isinstance(raw_groups, tuple) else ())
                         if (key := valid_preparation_field(group, group_field)) is not None)
            for position in _duplicates(key for _, key in keys):
                _issue(errors, PackPreparationIssueCode.METADATA_GROUP_MISMATCH,
                       group_path.item(keys[position][0]).field(group_field), "duplicate stored metadata group")
            address = valid_preparation_field(entry, FieldRef(lambda: PackStoredAssemblyProvenance, lambda value: value.address))
            if address is None:
                continue
            for key_index, key in keys:
                if key is not None:
                    self._check_group_kind(address, key, group_path.item(key_index).field(group_field), errors)
            for group_index, key in keys:
                group = (raw_groups if isinstance(raw_groups, tuple) else ())[group_index]
                basis = valid_preparation_field(group, basis_field)
                if key is None or (basis is None and preparation_field_value(group, basis_field) is not None):
                    continue
                self._check_group(address, key, basis,
                                  group_path.item(group_index).field(group_field),
                                  group_path.item(group_index).field(basis_field), errors)
            if isinstance(raw_groups, tuple) and len(keys) == len(raw_groups):
                self._check_group_completeness(address, (key for _, key in keys if key is not None), group_path, errors)

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

    def _check_group_kind(self, address: PackAssemblyAddress, group: PackMetadataGroup,
                          path: CheckedPath[RootT, PackMetadataGroup],
                          errors: ValidatorAggregationHelper[PackPreparationDiagnostic]) -> None:
        if group not in self._required_groups(address):
            _issue(errors, PackPreparationIssueCode.METADATA_GROUP_MISMATCH, path,
                   "metadata group does not belong to address kind")

    def _check_group(
        self, address: PackAssemblyAddress, group: PackMetadataGroup, basis: PackWildernessStatusBasis | None,
        group_path: CheckedPath[RootT, PackMetadataGroup],
        basis_path: CheckedPath[RootT, PackWildernessStatusBasis | None],
        errors: ValidatorAggregationHelper[PackPreparationDiagnostic],
    ) -> None:
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
        self, state: object, path: CheckedPath[RootT, PackPreparationState],
        errors: ValidatorAggregationHelper[PackPreparationDiagnostic],
    ) -> None:
        """Collect local identity issues under the calling operation's named input path."""
        base = valid_preparation_field(state, FieldRef(lambda: PackPreparationState, lambda value: value.base_publication))
        world = base.world_uid if base is not None else None
        parts_field = FieldRef(lambda: PackPreparationState, lambda value: value.parts)
        raw_parts = preparation_field_value(state, parts_field)
        parts = tuple(enumerate(raw_parts if isinstance(raw_parts, tuple) else ()))
        parts_path = path.field(parts_field)
        address_field = FieldRef(lambda: PackStoredPart, lambda value: value.address)
        addresses = tuple((index, address) for index, part in parts
                          if (address := valid_preparation_field(part, address_field)) is not None)
        for position in _duplicates(address for _, address in addresses):
            index = addresses[position][0]
            _issue(errors, PackPreparationIssueCode.DUPLICATE_ADDRESS,
                   parts_path.item(index).field(address_field), "duplicate part address")
        provenance_field = FieldRef(lambda: PackStoredPart, lambda value: value.provenance)
        proof_field = FieldRef(lambda: PackStoredProvenance, lambda value: value.source_proof)
        world_field = FieldRef(lambda: SourceDurableProof, lambda value: value.world_uid)
        for index, part in parts:
            provenance = valid_preparation_field(part, provenance_field)
            if world is not None and provenance is not None and world_field.select(proof_field.select(provenance)) != world:
                _issue(errors, PackPreparationIssueCode.SOURCE_PROOF_MISMATCH,
                       parts_path.item(index).field(provenance_field).field(proof_field).field(world_field),
                       "part proof belongs to another world")

        stored_field = FieldRef(lambda: PackPreparationState, lambda value: value.assembly_provenance)
        stored = _raw_items(state, stored_field)
        stored_path = path.field(stored_field)
        stored_address = FieldRef(lambda: PackStoredAssemblyProvenance, lambda value: value.address)
        stored_provenance = FieldRef(lambda: PackStoredAssemblyProvenance, lambda value: value.provenance)
        addresses = tuple((index, address) for index, entry in stored
                          if (address := valid_preparation_field(entry, stored_address)) is not None)
        for position in _duplicates(address for _, address in addresses):
            index = addresses[position][0]
            _issue(errors, PackPreparationIssueCode.DUPLICATE_ADDRESS,
                   stored_path.item(index).field(stored_address), "duplicate metadata provenance address")
        for index, entry in stored:
            provenance = valid_preparation_field(entry, stored_provenance)
            if world is not None and provenance is not None and world_field.select(proof_field.select(provenance)) != world:
                _issue(errors, PackPreparationIssueCode.SOURCE_PROOF_MISMATCH,
                       stored_path.item(index).field(stored_provenance).field(proof_field).field(world_field),
                       "metadata proof belongs to another world")

        descriptions_field = FieldRef(lambda: PackPreparationState, lambda value: value.metadata_dependencies)
        descriptions = _raw_items(state, descriptions_field)
        descriptions_path = path.field(descriptions_field)
        subject_field = FieldRef(lambda: PackMetadataDescription, lambda value: value.subject)
        subject_address = FieldRef(lambda: PackMetadataSubject, lambda value: value.address)
        subject_base = FieldRef(lambda: PackMetadataSubject, lambda value: value.base_publication)
        addresses = tuple((index, address) for index, entry in descriptions if (address := valid_preparation_field(
            preparation_field_value(entry, subject_field), subject_address)) is not None)
        for position in _duplicates(address for _, address in addresses):
            index = addresses[position][0]
            _issue(errors, PackPreparationIssueCode.DUPLICATE_ADDRESS,
                   descriptions_path.item(index).field(subject_field).field(subject_address),
                   "duplicate metadata dependency address")
        dependencies_field = FieldRef(lambda: PackMetadataDescription, lambda value: value.dependencies)
        group_field = FieldRef(lambda: PackMetadataDependencyUse, lambda value: value.group)
        usage_field = FieldRef(lambda: PackMetadataDependencyUse, lambda value: value.source_usage)
        usage_world = FieldRef(lambda: SourceProofInput, lambda value: value.world_uid)
        for index, entry in descriptions:
            entry_path = descriptions_path.item(index)
            entry_base = valid_preparation_field(preparation_field_value(entry, subject_field), subject_base)
            if base is not None and entry_base is not None and entry_base != base:
                _issue(errors, PackPreparationIssueCode.BASE_PUBLICATION_MISMATCH,
                       entry_path.field(subject_field).field(subject_base), "metadata subject uses another base")
            dependencies = _raw_items(entry, dependencies_field)
            dependency_path = entry_path.field(dependencies_field)
            for use_index, use in dependencies:
                usage = valid_preparation_field(use, usage_field)
                if world is not None and usage is not None and usage_world.select(usage) != world:
                    _issue(errors, PackPreparationIssueCode.SOURCE_PROOF_MISMATCH,
                           dependency_path.item(use_index).field(usage_field).field(usage_world),
                           "metadata usage belongs to another world")

        assembly_path = path.field(FieldRef(lambda: PackPreparationState, lambda value: value.assembly))
        tiles_field = FieldRef(lambda: PackAssemblyInput, lambda value: value.tiles)
        assembly = preparation_field_value(state, FieldRef(lambda: PackPreparationState, lambda value: value.assembly))
        tiles = _raw_items(assembly, tiles_field)
        tiles_path = assembly_path.field(tiles_field)
        coordinates = _coordinates(tiles, FieldRef(lambda: PackTileAssembly, lambda value: value.gx),
                                   FieldRef(lambda: PackTileAssembly, lambda value: value.gy))
        for position in _duplicates(key for _, key in coordinates):
            index = coordinates[position][0]
            _issue(errors, PackPreparationIssueCode.DUPLICATE_ADDRESS, tiles_path.item(index), "duplicate tile")
        chunks_field = FieldRef(lambda: PackTileAssembly, lambda value: value.chunks)
        raw_tiles = preparation_field_value(assembly, tiles_field)
        for index, tile in enumerate(raw_tiles if isinstance(raw_tiles, tuple) else ()):
            chunks = _coordinates(_raw_items(tile, chunks_field), FieldRef(lambda: PackChunkAssembly, lambda value: value.cx),
                                  FieldRef(lambda: PackChunkAssembly, lambda value: value.cy))
            for position in _duplicates(key for _, key in chunks):
                duplicate = chunks[position][0]
                _issue(errors, PackPreparationIssueCode.DUPLICATE_ADDRESS,
                       tiles_path.item(index).field(chunks_field).item(duplicate), "duplicate chunk in tile")
        locations_field = FieldRef(lambda: PackAssemblyInput, lambda value: value.locations)
        locations = valid_preparation_items(assembly, locations_field)
        for position in _duplicates(row.location_uid for _, row in locations):
            index = locations[position][0]
            _issue(errors, PackPreparationIssueCode.DUPLICATE_ADDRESS,
                   assembly_path.field(locations_field).item(index), "duplicate location")
        settlements_field = FieldRef(lambda: PackAssemblyInput, lambda value: value.settlements)
        settlements = valid_preparation_items(assembly, settlements_field)
        for position in _duplicates(row.location_uid for _, row in settlements):
            index = settlements[position][0]
            _issue(errors, PackPreparationIssueCode.DUPLICATE_ADDRESS,
                   assembly_path.field(settlements_field).item(index), "duplicate settlement")
        regions_field = FieldRef(lambda: PackAssemblyInput, lambda value: value.wilderness_regions)
        regions = valid_preparation_items(assembly, regions_field)
        for position in _duplicates(row.region_uid for _, row in regions):
            index = regions[position][0]
            _issue(errors, PackPreparationIssueCode.DUPLICATE_ADDRESS,
                   assembly_path.field(regions_field).item(index), "duplicate region")
