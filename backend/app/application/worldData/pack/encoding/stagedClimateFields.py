"""Check a candidate's climate addresses against the sealed fields held by its lease."""
from app.application.artifacts.contracts.blobRead import ReadableBlobBackend
from app.application.artifacts.contracts.holderPort import IArtifactHolders
from app.application.artifacts.storage.artifactCatalog import IArtifactCatalog
from app.application.worldData.generators.coordinates.convert import grid_tile_origin_x, grid_tile_origin_y
from app.application.worldData.pack.encoding.climateFieldFormat import CLIMATE_FIELD_FORMAT, decode_climate_field
from app.dataModel.artifacts.lifecycle.holders import OperationHolder
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.worldPack.meta.worldPackManifest import WorldPackManifest


class StagedClimateFields:
    def __init__(self, backend: ReadableBlobBackend, catalog: IArtifactCatalog, holders: IArtifactHolders):
        if backend.contract is not CLIMATE_FIELD_FORMAT:
            raise ValueError("expected the Pack climate field backend")
        self._backend, self._catalog, self._holders = backend, catalog, holders

    async def validate(self, lease: OperationLeaseRef, manifest: WorldPackManifest) -> None:
        span = manifest.fine_cells_per_map_cell
        addresses: list[tuple[ArtifactRef, tuple[int, int] | None]] = [
            (tile.climate_fine_ref, (grid_tile_origin_x(tile.gx, span), grid_tile_origin_y(tile.gy, span)))
            for tile in manifest.tiles if tile.climate_fine_ref is not None
        ]
        if manifest.climate_coarse_ref is not None:
            addresses.insert(0, (manifest.climate_coarse_ref, None))
        holder = OperationHolder(lease=lease)
        for ref, origin in addresses:
            async with self._catalog.guard(ref):
                if not await self._catalog.is_sealed(ref) or not await self._holders.is_held(ref, holder):
                    raise ValueError("candidate operation must hold the sealed climate field")
                payload = await self._backend.read_verified(ref, max_bytes=ref.nbytes)
            field = decode_climate_field(payload)
            if origin is None:
                if field.climate_status != "coarse":
                    raise ValueError("world climate field must be coarse")
            elif field.climate_status != "fine" or (field.origin_x, field.origin_y) != origin:
                raise ValueError("fine climate field differs from its manifest tile")
