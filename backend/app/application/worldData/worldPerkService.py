"""Perk library + per-world registry — tz_world_bundle WB-14."""

from __future__ import annotations

from dataclasses import asdict, fields
from datetime import datetime, timezone

from app.application.importResult import ImportResult
from app.application.import_helpers import import_list
from app.application.worldData.bundle.errors import BundleValidationError
from app.application.worldData.worldService import WorldService
from app.dataModel.perks.normalizePerkTemplateWire import normalize_perk_template_body
from app.dataModel.perks.perkTemplateRegistryEntry import PerkTemplateRegistryEntry
from app.db.models.world_perk import WorldPerk
from app.db.repositories.iWorldPerkRepository import IWorldPerkRepository

_PERK_FIELD_NAMES = frozenset(f.name for f in fields(WorldPerk))
_ID_KEY = WorldPerk.__pk__


def _registry_entries(world) -> list[PerkTemplateRegistryEntry]:
    out: list[PerkTemplateRegistryEntry] = []
    for raw in getattr(world, "perk_template_registry", None) or []:
        try:
            out.append(PerkTemplateRegistryEntry.model_validate(raw))
        except Exception:
            continue
    return out


def _registry_uids(world) -> list[str]:
    return [e.system_template_uid for e in _registry_entries(world)]


def _to_perk(row: dict) -> WorldPerk:
    canonical = normalize_perk_template_body(row)
    return WorldPerk(**{k: v for k, v in canonical.items() if k in _PERK_FIELD_NAMES})


class WorldPerkService:

    def __init__(self, repo: IWorldPerkRepository, world_service: WorldService) -> None:
        self._repo = repo
        self._worlds = world_service

    async def get_all(self, world_uid: str) -> list[WorldPerk]:
        world = await self._worlds.get_by_id(world_uid)
        return await self._repo.get_by_uids(_registry_uids(world))

    async def get_by_id(self, world_uid: str, template_uid: str) -> WorldPerk:
        world = await self._worlds.get_by_id(world_uid)
        if template_uid not in _registry_uids(world):
            raise BundleValidationError(f"Perk '{template_uid}' not bound to world")
        perk = await self._repo.get_by_id(template_uid)
        if perk is None:
            raise BundleValidationError(f"Perk template '{template_uid}' not found")
        return perk

    _IMMUTABLE = frozenset({_ID_KEY})

    async def create(self, world_uid: str, data: dict) -> WorldPerk:
        perk = _to_perk(data)
        await self._repo.upsert(perk)
        await self._ensure_registry(world_uid, perk)
        return perk

    async def update(self, world_uid: str, template_uid: str, data: dict) -> WorldPerk:
        perk = await self.get_by_id(world_uid, template_uid)
        for key, value in data.items():
            if hasattr(perk, key) and key not in self._IMMUTABLE:
                setattr(perk, key, value)
        await self._repo.update(perk)
        return perk

    async def delete(self, world_uid: str, template_uid: str) -> None:
        await self.get_by_id(world_uid, template_uid)
        await self._unbind_registry(world_uid, template_uid)

    async def import_bodies(self, world_uid: str, data: list[dict]) -> ImportResult:
        async def upsert_one(perk: WorldPerk) -> None:
            await self._repo.upsert(perk)
            await self._ensure_registry(world_uid, perk)

        return await import_list(data, _to_perk, upsert_one, id_key=_ID_KEY)

    async def export_bodies_for_world(self, world_uid: str) -> list[dict]:
        perks = await self.get_all(world_uid)
        return [asdict(p) for p in perks]

    async def _ensure_registry(self, world_uid: str, perk: WorldPerk) -> None:
        world = await self._worlds.get_by_id(world_uid)
        entries = _registry_entries(world)
        if any(e.system_template_uid == perk.template_uid for e in entries):
            return
        entries.append(
            PerkTemplateRegistryEntry(
                system_template_uid=perk.template_uid,
                display_template_name=perk.display_name,
                imported_at=datetime.now(timezone.utc).isoformat(),
            )
        )
        await self._worlds.update(
            world_uid,
            {
                "perk_template_registry": [
                    e.model_dump(mode="json") for e in entries
                ],
            },
        )

    async def _unbind_registry(self, world_uid: str, template_uid: str) -> None:
        world = await self._worlds.get_by_id(world_uid)
        entries = [
            e for e in _registry_entries(world)
            if e.system_template_uid != template_uid
        ]
        await self._worlds.update(
            world_uid,
            {
                "perk_template_registry": [
                    e.model_dump(mode="json") for e in entries
                ],
            },
        )

    async def import_from_json(self, world_uid: str, data: list[dict]) -> ImportResult:
        return await self.import_bodies(world_uid, data)
