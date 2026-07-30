"""Race library + per-world registry — tz_world_bundle WB-13."""

from __future__ import annotations

from dataclasses import asdict, fields
from datetime import datetime, timezone

from app.application.importResult import ImportResult
from app.application.import_helpers import import_list, with_default_created_at
from app.application.worldData.bundle.errors import BundleValidationError
from app.application.worldData.worldService import WorldService
from app.dataModel.races.normalizeRaceTemplateWire import normalize_race_template_body
from app.dataModel.races.raceTemplateRegistryEntry import RaceTemplateRegistryEntry
from app.db.models.race import Race
from app.db.repositories.iRaceRepository import IRaceRepository

_RACE_FIELD_NAMES = frozenset(f.name for f in fields(Race))
_ID_KEY = Race.__pk__


def _registry_entries(world) -> list[RaceTemplateRegistryEntry]:
    out: list[RaceTemplateRegistryEntry] = []
    for raw in getattr(world, "race_template_registry", None) or []:
        try:
            out.append(RaceTemplateRegistryEntry.model_validate(raw))
        except Exception:
            continue
    return out


def _registry_uids(world) -> list[str]:
    return [e.system_template_uid for e in _registry_entries(world)]


def _to_race(row: dict) -> Race:
    canonical = normalize_race_template_body(with_default_created_at(row))
    return Race(**{k: v for k, v in canonical.items() if k in _RACE_FIELD_NAMES})


class RaceService:

    def __init__(self, repo: IRaceRepository, world_service: WorldService) -> None:
        self._repo = repo
        self._worlds = world_service

    async def get_all(self, world_uid: str) -> list[Race]:
        world = await self._worlds.get_by_id(world_uid)
        return await self._repo.get_by_uids(_registry_uids(world))

    async def get_by_id(self, world_uid: str, template_uid: str) -> Race:
        world = await self._worlds.get_by_id(world_uid)
        if template_uid not in _registry_uids(world):
            raise BundleValidationError(f"Race '{template_uid}' not bound to world")
        race = await self._repo.get_by_id(template_uid)
        if race is None:
            raise BundleValidationError(f"Race template '{template_uid}' not found")
        return race

    _IMMUTABLE = frozenset({_ID_KEY})

    async def create(self, world_uid: str, data: dict) -> Race:
        race = _to_race(data)
        await self._repo.upsert(race)
        await self._ensure_registry(world_uid, race)
        return race

    async def update(self, world_uid: str, template_uid: str, data: dict) -> Race:
        race = await self.get_by_id(world_uid, template_uid)
        for key, value in data.items():
            if hasattr(race, key) and key not in self._IMMUTABLE:
                setattr(race, key, value)
        await self._repo.update(race)
        return race

    async def delete(self, world_uid: str, template_uid: str) -> None:
        await self.get_by_id(world_uid, template_uid)
        await self._unbind_registry(world_uid, template_uid)

    async def import_bodies(self, world_uid: str, data: list[dict]) -> ImportResult:
        """Upsert library bodies + bind registry pointers (bundle library section)."""

        async def upsert_one(race: Race) -> None:
            await self._repo.upsert(race)
            await self._ensure_registry(world_uid, race)

        return await import_list(data, _to_race, upsert_one, id_key=_ID_KEY)

    async def export_bodies_for_world(self, world_uid: str) -> list[dict]:
        races = await self.get_all(world_uid)
        return [asdict(r) for r in races]

    async def _ensure_registry(self, world_uid: str, race: Race) -> None:
        world = await self._worlds.get_by_id(world_uid)
        entries = _registry_entries(world)
        if any(e.system_template_uid == race.template_uid for e in entries):
            return
        entries.append(
            RaceTemplateRegistryEntry(
                system_template_uid=race.template_uid,
                display_template_name=race.display_name,
                imported_at=datetime.now(timezone.utc).isoformat(),
            )
        )
        await self._worlds.update(
            world_uid,
            {
                "race_template_registry": [
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
                "race_template_registry": [
                    e.model_dump(mode="json") for e in entries
                ],
            },
        )

    async def import_from_json(self, world_uid: str, data: list[dict]) -> ImportResult:
        return await self.import_bodies(world_uid, data)
