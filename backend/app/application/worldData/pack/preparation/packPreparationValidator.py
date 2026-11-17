"""Pure identity and uniqueness admission of an intermediate Pack composition."""

from typing import TypeVar

from pydantic import BaseModel

from app.application.worldData.pack.preparation.errors import preparation_errors, raise_preparation_errors, validate_preparation_input
from app.application.worldData.pack.preparation.errors import valid_preparation_field, preparation_field_value
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.dataModel.sourceVersioning.sourceProofInput import SourceProofInput
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.worldPack.meta.metadataAttribution import PackStoredAssemblyProvenance
from app.dataModel.worldPack.meta.parts import PackStoredPart
from app.dataModel.worldPack.preparation.assembly import PackAssemblyInput, PackTileAssembly, PackChunkAssembly
from app.dataModel.worldPack.preparation.assembly import PackLocationAssembly, PackSettlementAssembly
from app.dataModel.worldPack.meta.wildernessRegionEntry import WildernessRegionEntry
from app.dataModel.worldPack.preparation.errors import PackPreparationDiagnostic, PackPreparationFailureReason, PackPreparationIssueCode
from app.dataModel.worldPack.preparation.metadataDependencies import PackMetadataDependencyUse, PackMetadataDescription
from app.dataModel.worldPack.preparation.metadataSubject import PackMetadataSubject
from app.dataModel.worldPack.preparation.provenance import PackStoredProvenance
from app.dataModel.worldPack.preparation.state import PackPreparationState

from app.application.worldData.pack.preparation.metadataStateValidator import MetadataStateValidator
from app.application.worldData.pack.preparation.errors import _raw_items, _coordinates, _duplicates, _issue

RootT = TypeVar("RootT", bound=BaseModel)


class PackPreparationValidator:
    def validate_state(self, state: PackPreparationState) -> PackPreparationState:
        """Structural admission followed by local identities; no final completeness or IO."""
        errors = preparation_errors()
        checked = validate_preparation_input(PackPreparationState, state, errors)
        admitted = checked if checked is not None else state
        self.check_state_identities(admitted, CheckedPath.root(PackPreparationState), errors)
        MetadataStateValidator().check_metadata_groups(admitted, CheckedPath.root(PackPreparationState), errors)
        raise_preparation_errors(errors, PackPreparationFailureReason.DEPENDENCY_MISMATCH)
        assert checked is not None
        return checked

    def check_state_identities(
        self, state: object, path: CheckedPath[RootT, PackPreparationState],
        errors: ValidatorAggregationHelper[PackPreparationDiagnostic],
    ) -> None:
        """Collect local identity issues under the calling operation's named input path."""
        base = valid_preparation_field(state, FieldRef(lambda: PackPreparationState, lambda value: value.base_publication))
        raw_base = preparation_field_value(state, FieldRef(lambda: PackPreparationState, lambda value: value.base_publication))
        world = valid_preparation_field(raw_base, FieldRef(lambda: WorldPublicationRef, lambda value: value.world_uid))
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
            provenance = preparation_field_value(part, provenance_field)
            proof_world = valid_preparation_field(preparation_field_value(provenance, proof_field), world_field)
            if world is not None and proof_world is not None and proof_world != world:
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
            provenance = preparation_field_value(entry, stored_provenance)
            proof_world = valid_preparation_field(preparation_field_value(provenance, proof_field), world_field)
            if world is not None and proof_world is not None and proof_world != world:
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
                usage = preparation_field_value(use, usage_field)
                dependency_world = valid_preparation_field(usage, usage_world)
                if world is not None and dependency_world is not None and dependency_world != world:
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
        location_uid = FieldRef(lambda: PackLocationAssembly, lambda value: value.location_uid)
        locations = tuple((index, uid) for index, row in _raw_items(assembly, locations_field)
                          if (uid := valid_preparation_field(row, location_uid)) is not None)
        for position in _duplicates(uid for _, uid in locations):
            index = locations[position][0]
            _issue(errors, PackPreparationIssueCode.DUPLICATE_ADDRESS,
                   assembly_path.field(locations_field).item(index), "duplicate location")
        settlements_field = FieldRef(lambda: PackAssemblyInput, lambda value: value.settlements)
        settlement_uid = FieldRef(lambda: PackSettlementAssembly, lambda value: value.location_uid)
        settlements = tuple((index, uid) for index, row in _raw_items(assembly, settlements_field)
                            if (uid := valid_preparation_field(row, settlement_uid)) is not None)
        for position in _duplicates(uid for _, uid in settlements):
            index = settlements[position][0]
            _issue(errors, PackPreparationIssueCode.DUPLICATE_ADDRESS,
                   assembly_path.field(settlements_field).item(index), "duplicate settlement")
        regions_field = FieldRef(lambda: PackAssemblyInput, lambda value: value.wilderness_regions)
        region_uid = FieldRef(lambda: WildernessRegionEntry, lambda value: value.region_uid)
        regions = tuple((index, uid) for index, row in _raw_items(assembly, regions_field)
                        if (uid := valid_preparation_field(row, region_uid)) is not None)
        for position in _duplicates(uid for _, uid in regions):
            index = regions[position][0]
            _issue(errors, PackPreparationIssueCode.DUPLICATE_ADDRESS,
                   assembly_path.field(regions_field).item(index), "duplicate region")
