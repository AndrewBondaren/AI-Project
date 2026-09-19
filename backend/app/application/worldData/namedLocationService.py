from fastapi import HTTPException

from app.application.importResult import ImportError, ImportResult
from app.application.import_helpers import with_default_created_at
from app.application.worldData.settlementMapOccupancy import (
    emit_settlement_volume_conflicts,
    pick_occupants,
)
from app.dataModel.locations.namedLocation import BundleNamedLocation
from app.dataModel.worldPack.territoryVolumePolicy import TerritoryVolumePolicy
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.db.repositories.iNamedLocationRepository import INamedLocationRepository
from app.db.repositories.iWorldRepository import IWorldRepository


class NamedLocationService:

    def __init__(
        self,
        repo: INamedLocationRepository,
        world_repo: IWorldRepository | None = None,
    ) -> None:
        self._repo = repo
        self._worlds = world_repo

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def get_all(self, world_uid: str) -> list[NamedLocation]:
        return await self._repo.get_by_world(world_uid)

    async def list_insert_order(self, world_uid: str) -> list[NamedLocation]:
        return await self._repo.list_by_world_insert_order(world_uid)

    async def get_by_id(self, world_uid: str, location_uid: str) -> NamedLocation:
        loc = await self._repo.get_by_id(location_uid)
        if loc is None or loc.world_uid != world_uid:
            raise HTTPException(status_code=404, detail=f"Location '{location_uid}' not found")
        return loc

    async def get_children(self, world_uid: str, parent_uid: str) -> list[NamedLocation]:
        await self.get_by_id(world_uid, parent_uid)
        return await self._repo.get_children(parent_uid)

    _IMMUTABLE = frozenset({"location_uid", "world_uid"})

    @staticmethod
    def _from_wire(row: dict, *, world_uid: str) -> NamedLocation:
        wire = BundleNamedLocation.model_validate(with_default_created_at(row))
        return NamedLocation(**{**wire.to_db_fields(), "world_uid": world_uid})

    async def create(self, world_uid: str, data: dict) -> NamedLocation:
        loc = self._from_wire(data, world_uid=world_uid)
        await self._emit_occupancy(world_uid, incoming=loc, replace_uid=None)
        await self._repo.create(loc)
        return loc

    async def update(self, world_uid: str, location_uid: str, data: dict) -> NamedLocation:
        loc = await self.get_by_id(world_uid, location_uid)
        for key, value in data.items():
            if hasattr(loc, key) and key not in self._IMMUTABLE:
                setattr(loc, key, value)
        await self._emit_occupancy(world_uid, incoming=loc, replace_uid=location_uid)
        await self._repo.update(loc)
        return loc

    async def delete(self, world_uid: str, location_uid: str) -> None:
        await self.get_by_id(world_uid, location_uid)
        await self._repo.delete(location_uid)

    # ------------------------------------------------------------------
    # Import (режимы 1 и 3)
    # ------------------------------------------------------------------

    async def import_from_json(self, world_uid: str, data: list[dict]) -> ImportResult:
        prepared: list[tuple[int, NamedLocation]] = []
        errors: list[ImportError] = []
        for index, row in enumerate(data):
            try:
                prepared.append((index, self._from_wire(row, world_uid=world_uid)))
            except Exception as exc:
                errors.append(ImportError(
                    index=index,
                    message=str(exc),
                    entity_id=row.get("location_uid") if isinstance(row, dict) else None,
                ))
        world = await self._world(world_uid)
        if world is not None and prepared:
            indexed = await self._indexed_for_import(world_uid, prepared)
            picked = pick_occupants(world, indexed)
            emit_settlement_volume_conflicts(
                world, picked.conflicts, TerritoryVolumePolicy.canonical_defaults(),
            )
        succeeded = 0
        for index, loc in prepared:
            try:
                await self._repo.upsert(loc)
                succeeded += 1
            except Exception as exc:
                errors.append(ImportError(
                    index=index,
                    message=str(exc),
                    entity_id=loc.location_uid,
                ))
        return ImportResult(
            total=len(data),
            succeeded=succeeded,
            failed=len(errors),
            errors=errors,
        )

    async def _world(self, world_uid: str) -> World | None:
        if self._worlds is None:
            return None
        return await self._worlds.get_by_id(world_uid)

    async def _emit_occupancy(
        self,
        world_uid: str,
        *,
        incoming: NamedLocation,
        replace_uid: str | None,
    ) -> None:
        world = await self._world(world_uid)
        if world is None:
            return
        existing = await self._repo.get_by_world(world_uid)
        indexed: list[tuple[int, NamedLocation]] = []
        replaced = False
        for index, loc in enumerate(existing):
            if replace_uid is not None and loc.location_uid == replace_uid:
                indexed.append((index, incoming))
                replaced = True
            else:
                indexed.append((index, loc))
        if not replaced:
            indexed.append((len(indexed), incoming))
        picked = pick_occupants(world, indexed)
        emit_settlement_volume_conflicts(
            world, picked.conflicts, TerritoryVolumePolicy.canonical_defaults(),
        )

    async def _indexed_for_import(
        self,
        world_uid: str,
        prepared: list[tuple[int, NamedLocation]],
    ) -> list[tuple[int, NamedLocation]]:
        incoming = {loc.location_uid: loc for _, loc in prepared}
        existing = await self._repo.list_by_world_insert_order(world_uid)
        merged: list[NamedLocation] = []
        seen: set[str] = set()
        for loc in existing:
            replacement = incoming.get(loc.location_uid)
            merged.append(replacement if replacement is not None else loc)
            seen.add(loc.location_uid)
        for _, loc in prepared:
            if loc.location_uid not in seen:
                merged.append(loc)
                seen.add(loc.location_uid)
        bundle_index = {loc.location_uid: index for index, loc in prepared}
        indexed: list[tuple[int, NamedLocation]] = []
        next_extra = len(prepared)
        for loc in merged:
            if loc.location_uid in bundle_index:
                indexed.append((bundle_index[loc.location_uid], loc))
            else:
                indexed.append((next_extra, loc))
                next_extra += 1
        return indexed
