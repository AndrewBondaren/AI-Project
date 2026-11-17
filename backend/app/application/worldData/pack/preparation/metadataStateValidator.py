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
from app.dataModel.worldPack.preparation.assembly import PackAssemblyInput, PackTileAssembly, PackChunkAssembly
from app.dataModel.worldPack.preparation.assembly import PackLocationAssembly, PackSettlementAssembly
from app.dataModel.worldPack.meta.wildernessRegionEntry import WildernessRegionEntry
from app.dataModel.worldPack.preparation.addresses import PackChunkAddress
from app.dataModel.worldPack.preparation.addresses import PackAssemblyHeaderAddress, PackChunkMetadataAddress, PackLocationMetadataAddress, PackSettlementMetadataAddress, PackRegionMetadataAddress
from app.application.worldData.pack.preparation.metadataProjection import metadata_value_fingerprint
from app.application.worldData.pack.preparation.errors import valid_preparation_items
from app.dataModel.worldPack.bake.wildernessRefineStatus import wilderness_refine_status_for_counts, wilderness_refine_status_without_expected

from app.application.worldData.pack.preparation.errors import _duplicates, _issue, _raw_items, _coordinates

RootT = TypeVar("RootT", bound=BaseModel)
ValueT = TypeVar("ValueT")
ItemT = TypeVar("ItemT", bound=BaseModel)


class MetadataStateValidator:
    @staticmethod
    def _ambiguous_keys(value: object, collection: FieldRef[PackAssemblyInput, tuple[ItemT, ...]],
                        key: FieldRef[ItemT, ValueT]) -> set[ValueT]:
        keys = tuple(admitted for _, row in _raw_items(value, collection)
                     if (admitted := valid_preparation_field(row, key)) is not None)
        return {keys[index] for index in _duplicates(keys)}

    @staticmethod
    def _complete_keys(value: object, collection: FieldRef[PackAssemblyInput, tuple[ItemT, ...]],
                       key: FieldRef[ItemT, ValueT]) -> set[ValueT] | None:
        rows = preparation_field_value(value, collection)
        if not isinstance(rows, tuple):
            return None
        keys: set[ValueT] = set()
        for row in rows:
            admitted = valid_preparation_field(row, key)
            if admitted is None:
                return None
            keys.add(admitted)
        return keys

    def check_subject_values(
        self, state: object, path: CheckedPath[RootT, PackPreparationState],
        errors: ValidatorAggregationHelper[PackPreparationDiagnostic],
    ) -> None:
        assembly_field = FieldRef(lambda: PackPreparationState, lambda value: value.assembly)
        raw_assembly = preparation_field_value(state, assembly_field)
        # Membership admission is independent of projection values.
        tiles_field = FieldRef(lambda: PackAssemblyInput, lambda value: value.tiles)
        raw_tiles = preparation_field_value(raw_assembly, tiles_field)
        tiles = self._tile_basis_inputs(state)
        chunk_keys = {key: set(chunks) if chunks is not None else None for key, (chunks, _) in tiles.items()}
        tile_keys_complete = isinstance(raw_tiles, tuple) and all(
            valid_preparation_field(tile, FieldRef(lambda: PackTileAssembly, lambda value: value.gx)) is not None
            and valid_preparation_field(tile, FieldRef(lambda: PackTileAssembly, lambda value: value.gy)) is not None
            for tile in raw_tiles)
        locations = self._complete_keys(raw_assembly, FieldRef(lambda: PackAssemblyInput, lambda value: value.locations),
                                        FieldRef(lambda: PackLocationAssembly, lambda value: value.location_uid))
        settlements = self._complete_keys(raw_assembly, FieldRef(lambda: PackAssemblyInput, lambda value: value.settlements),
                                          FieldRef(lambda: PackSettlementAssembly, lambda value: value.location_uid))
        regions = self._complete_keys(raw_assembly, FieldRef(lambda: PackAssemblyInput, lambda value: value.wilderness_regions),
                                      FieldRef(lambda: WildernessRegionEntry, lambda value: value.region_uid))
        projections: dict[PackAssemblyAddress, object] = {}
        tile_coordinates = _coordinates(_raw_items(raw_assembly, tiles_field),
            FieldRef(lambda: PackTileAssembly, lambda value: value.gx),
            FieldRef(lambda: PackTileAssembly, lambda value: value.gy))
        duplicate_tiles = {tile_coordinates[index][1] for index in _duplicates(key for _, key in tile_coordinates)}
        ambiguous: set[PackAssemblyAddress] = set()
        ambiguous.update(PackTileMetadataAddress(kind="tile", gx=gx, gy=gy) for gx, gy in duplicate_tiles)
        ambiguous.update(PackLocationMetadataAddress(kind="location", location_uid=uid) for uid in self._ambiguous_keys(
            raw_assembly, FieldRef(lambda: PackAssemblyInput, lambda value: value.locations),
            FieldRef(lambda: PackLocationAssembly, lambda value: value.location_uid)))
        ambiguous.update(PackSettlementMetadataAddress(kind="settlement", location_uid=uid) for uid in self._ambiguous_keys(
            raw_assembly, FieldRef(lambda: PackAssemblyInput, lambda value: value.settlements),
            FieldRef(lambda: PackSettlementAssembly, lambda value: value.location_uid)))
        ambiguous.update(PackRegionMetadataAddress(kind="region", region_uid=uid) for uid in self._ambiguous_keys(
            raw_assembly, FieldRef(lambda: PackAssemblyInput, lambda value: value.wilderness_regions),
            FieldRef(lambda: WildernessRegionEntry, lambda value: value.region_uid)))
        header = PackAssemblyHeaderAddress(kind="header")
        header_values = (
            valid_preparation_field(raw_assembly, FieldRef(lambda: PackAssemblyInput, lambda value: value.last_l0_mode)),
            valid_preparation_field(raw_assembly, FieldRef(lambda: PackAssemblyInput, lambda value: value.fine_cells_per_map_cell)),
            valid_preparation_field(raw_assembly, FieldRef(lambda: PackAssemblyInput, lambda value: value.world_map_cells_per_tile)),
            valid_preparation_field(raw_assembly, FieldRef(lambda: PackAssemblyInput, lambda value: value.fine_cell_size)),
            valid_preparation_field(raw_assembly, FieldRef(lambda: PackAssemblyInput, lambda value: value.map_subsurface_depth)),
            valid_preparation_field(raw_assembly, FieldRef(lambda: PackAssemblyInput, lambda value: value.terrain_chunk_columns)),
        )
        if all(value is not None for value in header_values):
            projections[header] = header_values
        for _, tile in _raw_items(raw_assembly, FieldRef(lambda: PackAssemblyInput, lambda value: value.tiles)):
            gx = valid_preparation_field(tile, FieldRef(lambda: PackTileAssembly, lambda value: value.gx))
            gy = valid_preparation_field(tile, FieldRef(lambda: PackTileAssembly, lambda value: value.gy))
            if gx is None or gy is None:
                continue
            chunk_coordinates = _coordinates(_raw_items(tile, FieldRef(lambda: PackTileAssembly, lambda value: value.chunks)),
                FieldRef(lambda: PackChunkAssembly, lambda value: value.cx),
                FieldRef(lambda: PackChunkAssembly, lambda value: value.cy))
            ambiguous.update(PackChunkMetadataAddress(kind="chunk", gx=gx, gy=gy,
                cx=chunk_coordinates[index][1][0], cy=chunk_coordinates[index][1][1])
                for index in _duplicates(key for _, key in chunk_coordinates))
            climate = valid_preparation_field(tile, FieldRef(lambda: PackTileAssembly, lambda value: value.climate_status))
            status = valid_preparation_field(tile, FieldRef(lambda: PackTileAssembly, lambda value: value.wilderness_refine_status))
            if climate is not None and status is not None:
                projections[PackTileMetadataAddress(kind="tile", gx=gx, gy=gy)] = (gx, gy, climate, status)
            for _, chunk in valid_preparation_items(tile, FieldRef(lambda: PackTileAssembly, lambda value: value.chunks)):
                projections[PackChunkMetadataAddress(kind="chunk", gx=gx, gy=gy, cx=chunk.cx, cy=chunk.cy)] = (
                    chunk.cx, chunk.cy, chunk.refine_role)
        for _, location in valid_preparation_items(raw_assembly, FieldRef(lambda: PackAssemblyInput, lambda value: value.locations)):
            projections[PackLocationMetadataAddress(kind="location", location_uid=location.location_uid)] = location
        for _, settlement in valid_preparation_items(raw_assembly, FieldRef(lambda: PackAssemblyInput, lambda value: value.settlements)):
            projections[PackSettlementMetadataAddress(kind="settlement", location_uid=settlement.location_uid)] = settlement
        for _, region in valid_preparation_items(raw_assembly, FieldRef(lambda: PackAssemblyInput, lambda value: value.wilderness_regions)):
            projections[PackRegionMetadataAddress(kind="region", region_uid=region.region_uid)] = region
        descriptions = FieldRef(lambda: PackPreparationState, lambda value: value.metadata_dependencies)
        subject_field = FieldRef(lambda: PackMetadataDescription, lambda value: value.subject)
        address_field = FieldRef(lambda: PackMetadataSubject, lambda value: value.address)
        fingerprint_field = FieldRef(lambda: PackMetadataSubject, lambda value: value.value_fingerprint)
        for index, description in _raw_items(state, descriptions):
            subject = preparation_field_value(description, subject_field)
            address = valid_preparation_field(subject, address_field)
            fingerprint = valid_preparation_field(subject, fingerprint_field)
            subject_path = path.field(descriptions).item(index).field(subject_field)
            if address is None:
                continue
            if address in ambiguous or (isinstance(address, PackChunkMetadataAddress)
                                        and (address.gx, address.gy) in duplicate_tiles):
                continue
            if address not in projections:
                absent = False
                if isinstance(address, (PackTileMetadataAddress, PackChunkMetadataAddress)):
                    tile_key = address.gx, address.gy
                    absent = tile_keys_complete and tile_key not in tiles
                    if isinstance(address, PackChunkMetadataAddress) and tile_key in tiles:
                        chunks = chunk_keys[tile_key]
                        absent = chunks is not None and PackChunkAddress(kind="wilderness_chunk", gx=address.gx,
                            gy=address.gy, cx=address.cx, cy=address.cy) not in chunks
                elif isinstance(address, PackLocationMetadataAddress):
                    absent = locations is not None and address.location_uid not in locations
                elif isinstance(address, PackSettlementMetadataAddress):
                    absent = settlements is not None and address.location_uid not in settlements
                elif isinstance(address, PackRegionMetadataAddress):
                    absent = regions is not None and address.region_uid not in regions
                if absent:
                    _issue(errors, PackPreparationIssueCode.ADDRESS_MISMATCH, subject_path.field(address_field), "metadata projection is absent")
            elif fingerprint is not None and fingerprint != metadata_value_fingerprint(address, projections[address]):
                _issue(errors, PackPreparationIssueCode.SOURCE_PROOF_MISMATCH, subject_path.field(fingerprint_field), "metadata subject value is stale")

    def check_retained_tile_usage(
        self, state: object, addresses: Iterable[PackChunkAddress], path: CheckedPath[RootT, PackPreparationState],
        errors: ValidatorAggregationHelper[PackPreparationDiagnostic],
    ) -> None:
        existing = self._tile_basis_inputs(state)
        descriptions_field = FieldRef(lambda: PackPreparationState, lambda value: value.metadata_dependencies)
        pending: set[PackAssemblyAddress] = set()
        for _, description in _raw_items(state, descriptions_field):
            subject = preparation_field_value(description, FieldRef(lambda: PackMetadataDescription, lambda value: value.subject))
            address = valid_preparation_field(subject, FieldRef(lambda: PackMetadataSubject, lambda value: value.address))
            if address is not None:
                pending.add(address)
        stored_field = FieldRef(lambda: PackPreparationState, lambda value: value.assembly_provenance)
        address_field = FieldRef(lambda: PackStoredAssemblyProvenance, lambda value: value.address)
        stored_indices = {address: index for index, entry in _raw_items(state, stored_field)
                          if (address := valid_preparation_field(entry, address_field)) is not None}
        seen: set[tuple[int, int]] = set()
        for chunk in addresses:
            key = chunk.gx, chunk.gy
            if key in seen or key not in existing:
                continue
            seen.add(key)
            address = PackTileMetadataAddress(kind="tile", gx=chunk.gx, gy=chunk.gy)
            if address in pending:
                continue
            index = stored_indices.get(address)
            if index is None:
                _issue(errors, PackPreparationIssueCode.METADATA_ATTRIBUTION_UNAVAILABLE, path.field(stored_field), "retained tile usages must be imported before writing")
            else:
                _issue(errors, PackPreparationIssueCode.METADATA_ATTRIBUTION_UNAVAILABLE,
                       path.field(stored_field).item(index).field(FieldRef(lambda: PackStoredAssemblyProvenance, lambda value: value.attribution)),
                       "stored attribution does not provide imported usages")

    def check_metadata_groups(
        self, state: object, path: CheckedPath[RootT, PackPreparationState],
        errors: ValidatorAggregationHelper[PackPreparationDiagnostic],
    ) -> None:
        tiles = self._tile_basis_inputs(state)
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
                if isinstance(address, PackTileMetadataAddress) and key is PackMetadataGroup.WILDERNESS_REFINE_STATUS and basis is not None:
                    self._check_current_basis(address, basis, tiles, group_path.item(use_index).field(basis_ref), errors)
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
                if isinstance(address, PackTileMetadataAddress) and key is PackMetadataGroup.WILDERNESS_REFINE_STATUS and basis is not None:
                    self._check_current_basis(address, basis, tiles, group_path.item(group_index).field(basis_field), errors)
            if isinstance(raw_groups, tuple) and len(keys) == len(raw_groups):
                self._check_group_completeness(address, (key for _, key in keys if key is not None), group_path, errors)

    @staticmethod
    def _tile_basis_inputs(state: object) -> dict[tuple[int, int], tuple[tuple[PackChunkAddress, ...] | None, str | None]]:
        assembly = preparation_field_value(state, FieldRef(lambda: PackPreparationState, lambda value: value.assembly))
        result: dict[tuple[int, int], tuple[tuple[PackChunkAddress, ...] | None, str | None]] = {}
        for _, tile in _raw_items(assembly, FieldRef(lambda: PackAssemblyInput, lambda value: value.tiles)):
            gx = valid_preparation_field(tile, FieldRef(lambda: PackTileAssembly, lambda value: value.gx))
            gy = valid_preparation_field(tile, FieldRef(lambda: PackTileAssembly, lambda value: value.gy))
            if gx is None or gy is None:
                continue
            key = gx, gy
            if key in result:
                result[key] = None, None
                continue
            chunks_field = FieldRef(lambda: PackTileAssembly, lambda value: value.chunks)
            raw = preparation_field_value(tile, chunks_field)
            coordinates = _coordinates(_raw_items(tile, chunks_field),
                FieldRef(lambda: PackChunkAssembly, lambda value: value.cx),
                FieldRef(lambda: PackChunkAssembly, lambda value: value.cy))
            addresses = None
            if isinstance(raw, tuple) and len(coordinates) == len(raw) and len({xy for _, xy in coordinates}) == len(raw):
                addresses = tuple(PackChunkAddress(kind="wilderness_chunk", gx=gx, gy=gy, cx=cx, cy=cy)
                                  for cx, cy in sorted(xy for _, xy in coordinates))
            status = valid_preparation_field(tile, FieldRef(lambda: PackTileAssembly, lambda value: value.wilderness_refine_status))
            result[key] = addresses, status
        return result

    @staticmethod
    def _check_current_basis(
        address: PackTileMetadataAddress, basis: PackWildernessStatusBasis,
        tiles: dict[tuple[int, int], tuple[tuple[PackChunkAddress, ...] | None, str | None]],
        path: CheckedPath[RootT, PackWildernessStatusBasis | None],
        errors: ValidatorAggregationHelper[PackPreparationDiagnostic],
    ) -> None:
        current = tiles.get((address.gx, address.gy))
        if current is None:
            return
        addresses, status = current
        # Existing group checks already report duplicate and foreign-tile basis addresses.
        if len(set(basis.chunk_addresses)) != len(basis.chunk_addresses) or any(
                (c.gx, c.gy) != (address.gx, address.gy) for c in basis.chunk_addresses):
            return
        expected_status = (wilderness_refine_status_without_expected(len(basis.chunk_addresses))
                           if basis.expected_chunks is None else
                           wilderness_refine_status_for_counts(len(basis.chunk_addresses), basis.expected_chunks))
        if ((addresses is not None and addresses != basis.chunk_addresses)
                or (status is not None and status != expected_status)):
            _issue(errors, PackPreparationIssueCode.METADATA_BASIS_MISMATCH, path,
                   "basis differs from current membership or status policy")

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
