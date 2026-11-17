"""Local chunk transitions over admitted inputs; no IO or public-stage calls."""

from app.application.worldData.pack.preparation.errors import preparation_errors, raise_preparation_errors
from app.application.worldData.pack.preparation.metadataProjection import metadata_value_fingerprint
from app.application.worldData.pack.preparation.metadataStateValidator import MetadataStateValidator
from app.application.worldData.pack.preparation.packPreparationValidator import PackPreparationValidator
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.sourceVersioning.sourceProofInput import SourceProofInput
from app.dataModel.worldPack.bake.wildernessRefineStatus import wilderness_refine_status_without_expected
from app.dataModel.worldPack.meta.metadataAttribution import PackMetadataGroup, PackWildernessStatusBasis
from app.dataModel.worldPack.meta.parts import PackStoredPart
from app.dataModel.worldPack.preparation.addresses import PackAssemblyAddress, PackChunkAddress, PackChunkMetadataAddress, PackTileMetadataAddress
from app.dataModel.worldPack.preparation.assembly import PackChunkAssembly, PackTileAssembly
from app.dataModel.worldPack.preparation.errors import PackPreparationFailureReason
from app.dataModel.worldPack.preparation.metadataDependencies import (
    PackMetadataDependencyUse, PackMetadataDescription, PackMetadataInputField, PackMetadataValueInputSelector,
)
from app.dataModel.worldPack.preparation.metadataSubject import PackMetadataSubject
from app.dataModel.worldPack.preparation.operations import PackWildernessChunkWrite
from app.dataModel.worldPack.preparation.provenance import PackNewPartProvenance
from app.dataModel.worldPack.preparation.state import PackPreparationState
from app.dataModel.worldPack.wire.climateFieldWire import ClimateBakeStatusMixin
from app.dataModel.worldPack.meta.worldPackManifest import WildernessRefineStatus


def apply_wilderness_chunks(state: PackPreparationState, entries: tuple[PackWildernessChunkWrite, ...]) -> PackPreparationState:
    """Apply a sequence already checked by WildernessChunkAdmission.

    Dict replacement preserves existing positions; insertion records first appearance.
    No intermediate state or full status basis is materialized in the item loop.
    """
    if not entries:
        return state
    parts = {part.address: part for part in state.parts}
    tiles = {(tile.gx, tile.gy): tile for tile in state.assembly.tiles}
    chunks = {key: {(chunk.cx, chunk.cy): chunk for chunk in tile.chunks} for key, tile in tiles.items()}
    descriptions = {entry.subject.address: entry for entry in state.metadata_dependencies}
    original = descriptions.copy()
    stored_bindings = {entry.address: entry for entry in state.assembly_provenance}
    description_order: dict[PackAssemblyAddress, None] = dict.fromkeys(descriptions)
    tile_groups: dict[tuple[int, int], tuple[PackMetadataDependencyUse, PackMetadataDependencyUse]] = {}
    statuses: dict[tuple[int, int], WildernessRefineStatus] = {}
    changed: set[PackAssemblyAddress] = set()
    empty_usage = SourceProofInput(world_uid=state.base_publication.world_uid, uses=())

    for item in entries:
        address = item.part.address
        key = address.gx, address.gy
        tile_address = PackTileMetadataAddress(kind="tile", gx=address.gx, gy=address.gy)
        description_order[tile_address] = None
        evidence: dict[PackMetadataInputField, SourceProofInput] = {}
        for supplied in item.metadata_inputs:
            assert isinstance(supplied.input, PackMetadataValueInputSelector)
            evidence[supplied.input.field] = supplied.source_usage
        if key not in tile_groups:
            if key in tiles:
                retained = {use.group: use for use in descriptions[tile_address].dependencies}
                tile_groups[key] = retained[PackMetadataGroup.IDENTITY], retained[PackMetadataGroup.CLIMATE_STATUS]
            else:
                tile_groups[key] = (
                    PackMetadataDependencyUse(group=PackMetadataGroup.IDENTITY,
                        source_usage=evidence[PackMetadataInputField.ADDRESS], basis=None),
                    PackMetadataDependencyUse(group=PackMetadataGroup.CLIMATE_STATUS, source_usage=empty_usage, basis=None))
                chunks[key] = {}

        assert isinstance(item.part.provenance, PackNewPartProvenance)
        parts[address] = PackStoredPart(address=address, artifact=item.part.artifact,
                                        provenance=item.part.provenance.provenance)
        chunks[key][address.cx, address.cy] = PackChunkAssembly(cx=address.cx, cy=address.cy, refine_role=item.refine_role)
        statuses[key] = wilderness_refine_status_without_expected(len(chunks[key]))
        chunk_address = PackChunkMetadataAddress(kind="chunk", gx=address.gx, gy=address.gy, cx=address.cx, cy=address.cy)
        description_order[chunk_address] = None
        description = _description(state, chunk_address, (address.cx, address.cy, item.refine_role), (
            PackMetadataDependencyUse(group=PackMetadataGroup.IDENTITY,
                source_usage=evidence[PackMetadataInputField.ADDRESS], basis=None),
            PackMetadataDependencyUse(group=PackMetadataGroup.REFINE_ROLE,
                source_usage=evidence[PackMetadataInputField.REFINE_ROLE], basis=None)))
        if original.get(chunk_address) != description:
            changed.add(chunk_address)
        descriptions[chunk_address] = description

    for key, retained_groups in tile_groups.items():
        gx, gy = key
        old_tile = tiles.get(key)
        climate = old_tile.climate_status if old_tile is not None else ClimateBakeStatusMixin().climate_status
        tile = PackTileAssembly(gx=gx, gy=gy, climate_status=climate,
            wilderness_refine_status=statuses[key], chunks=tuple(chunks[key].values()))
        tiles[key] = tile
        basis = PackWildernessStatusBasis(chunk_addresses=tuple(
            PackChunkAddress(kind="wilderness_chunk", gx=gx, gy=gy, cx=cx, cy=cy)
            for cx, cy in sorted(chunks[key])), expected_chunks=None)
        address = PackTileMetadataAddress(kind="tile", gx=gx, gy=gy)
        description = _description(state, address, (gx, gy, climate, statuses[key]), (*retained_groups,
            PackMetadataDependencyUse(group=PackMetadataGroup.WILDERNESS_REFINE_STATUS, source_usage=empty_usage, basis=basis)))
        if original.get(address) != description:
            changed.add(address)
        stored = stored_bindings.get(address)
        if stored is not None and stored.attribution is not None:
            if any(group.group is PackMetadataGroup.WILDERNESS_REFINE_STATUS and group.basis != basis
                   for group in stored.attribution.groups):
                changed.add(address)
        descriptions[address] = description

    assembly = state.assembly.model_copy(update={"tiles": tuple(tiles.values())})
    result = PackPreparationState(base_publication=state.base_publication, parts=tuple(parts.values()), assembly=assembly,
        assembly_provenance=tuple(entry for entry in state.assembly_provenance if entry.address not in changed),
        metadata_dependencies=tuple(descriptions[address] for address in description_order))
    errors = preparation_errors()
    path = CheckedPath.root(PackPreparationState)
    PackPreparationValidator().check_state_identities(result, path, errors)
    metadata = MetadataStateValidator()
    metadata.check_metadata_groups(result, path, errors)
    metadata.check_subject_values(result, path, errors)
    raise_preparation_errors(errors, PackPreparationFailureReason.DEPENDENCY_MISMATCH)
    return result


def _description(state: PackPreparationState, address: PackAssemblyAddress, projection: object,
                 dependencies: tuple[PackMetadataDependencyUse, ...]) -> PackMetadataDescription:
    return PackMetadataDescription(subject=PackMetadataSubject(base_publication=state.base_publication,
        address=address, value_fingerprint=metadata_value_fingerprint(address, projection)), dependencies=dependencies)
