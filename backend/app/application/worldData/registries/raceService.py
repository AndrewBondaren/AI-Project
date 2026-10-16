"""Race library + per-world registry — tz_world_bundle WB-13."""

from __future__ import annotations

from dataclasses import asdict, fields
from app.application.jsonValidation.resolve import ResolveContext, UnresolvedModelError, resolve_model
from app.application.jsonValidation.types import ImportValidationError
from app.application.jsonValidation.worldSlices import resolve_registry_list_world
from app.dataModel.races.worldRaceTemplateRegistry import WorldRaceTemplateRegistry
from app.dataModel.races.raceTemplateOutline import RaceTemplateOutline
from datetime import datetime, timezone

from app.application.imports.result import ImportResult
from app.application.imports.helpers import import_list, with_default_created_at
from app.application.worldBundle.errors import BundleValidationError
from app.application.worldData.registries.worldColumnWrite import apply_world_column
from app.application.worldData.registries.worldLookup import require_world
from app.db.repositories.iWorldRepository import IWorldRepository
from app.dataModel.races.raceTemplateRegistryEntry import RaceTemplateRegistryEntry
from app.db.models.race import Race
from app.db.repositories.iRaceRepository import IRaceRepository

_RACE_FIELD_NAMES = frozenset(f.name for f in fields(Race))
_ID_KEY = Race.__pk__


def _registry_entries(world) -> list[RaceTemplateRegistryEntry]:
    try:
        return list(resolve_registry_list_world(world, WorldRaceTemplateRegistry).root)
    except UnresolvedModelError as exc:
        raise ImportValidationError(list(exc.issues)) from exc


def _registry_uids(world) -> list[str]:
    return [e.system_template_uid for e in _registry_entries(world)]


def _to_race(row: dict, *, ctx: ResolveContext | None = None) -> Race:
    canonical = resolve_model(RaceTemplateOutline, with_default_created_at(row), ctx=ctx).model_dump(mode="json")
    return Race(**{k: v for k, v in canonical.items() if k in _RACE_FIELD_NAMES})


class RaceService:

    prepare_body = staticmethod(_to_race)

    def __init__(self, repo: IRaceRepository, world_repository: IWorldRepository) -> None:
        self._repo = repo
        self._worlds = world_repository

    async def get_all(self, world_uid: str) -> list[Race]:
        world = await require_world(self._worlds, world_uid)
        return await self._repo.get_by_uids(_registry_uids(world))

    async def get_by_id(self, world_uid: str, template_uid: str) -> Race:
        world = await require_world(self._worlds, world_uid)
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
        changes = {key: value for key, value in data.items() if key not in self._IMMUTABLE}
        race = _to_race({**asdict(race), **changes})
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

        return await import_list(data, self.prepare_body, upsert_one, id_key=_ID_KEY)

    async def export_bodies_for_world(self, world_uid: str) -> list[dict]:
        races = await self.get_all(world_uid)
        return [asdict(r) for r in races]

    async def _ensure_registry(self, world_uid: str, race: Race) -> None:
        world = await require_world(self._worlds, world_uid)
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
        apply_world_column(world, "race_template_registry",
                           [e.model_dump(mode="json") for e in entries], ResolveContext())
        await self._worlds.update(world)

    async def _unbind_registry(self, world_uid: str, template_uid: str) -> None:
        world = await require_world(self._worlds, world_uid)
        entries = [
            e for e in _registry_entries(world)
            if e.system_template_uid != template_uid
        ]
        apply_world_column(world, "race_template_registry",
                           [e.model_dump(mode="json") for e in entries], ResolveContext())
        await self._worlds.update(world)

    async def import_from_json(self, world_uid: str, data: list[dict]) -> ImportResult:
        return await self.import_bodies(world_uid, data)
