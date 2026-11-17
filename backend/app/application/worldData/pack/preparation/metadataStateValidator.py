"""Metadata group and basis checks contributing to the caller's diagnostics."""

from collections.abc import Iterable
from typing import TypeVar

from pydantic import BaseModel

from app.application.worldData.pack.preparation.errors import valid_preparation_field, preparation_field_value
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.worldPack.meta.metadataAttribution import (
    PackStoredAssemblyProvenance, PackMetadataAttribution, PackMetadataGroup,
    PackMetadataGroupAdmission, PackWildernessStatusBasis,
)
from app.dataModel.worldPack.preparation.addresses import PackAssemblyAddress, PackTileMetadataAddress
from app.dataModel.worldPack.preparation.errors import PackPreparationDiagnostic, PackPreparationIssueCode
from app.dataModel.worldPack.preparation.metadataDependencies import PackMetadataDependencyUse, PackMetadataDescription
from app.dataModel.worldPack.preparation.metadataSubject import PackMetadataSubject
from app.dataModel.worldPack.preparation.state import PackPreparationState

from app.application.worldData.pack.preparation.errors import _duplicates, _issue

RootT = TypeVar("RootT", bound=BaseModel)
ValueT = TypeVar("ValueT")


class MetadataStateValidator:
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
