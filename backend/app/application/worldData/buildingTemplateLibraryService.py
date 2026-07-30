"""Building template library + world registry bind — tz_building_generator §5–6 / WB-11."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from app.application.importResult import ImportResult
from app.application.worldData.bundle.errors import BundleValidationError
from app.application.worldData.worldService import WorldService
from app.dataModel.structure.building.buildingTemplateOutline import BuildingTemplateOutline
from app.dataModel.structure.building.buildingTemplateRegistryEntry import (
    BuildingTemplateRegistryEntry,
)
from app.db.models.buildingTemplate import BuildingTemplateRow
from app.db.repositories.iBuildingTemplateRepository import IBuildingTemplateRepository

logger = logging.getLogger(__name__)
_UID_NS = uuid.NAMESPACE_URL


def building_template_uid(system_name: str) -> str:
    return str(uuid.uuid5(_UID_NS, f"building_templates|{system_name}"))


def _registry_entries(world) -> list[BuildingTemplateRegistryEntry]:
    reg = getattr(world, "building_template_registry", None)
    if isinstance(reg, dict):
        raw_list = list(reg.values()) if reg else []
    else:
        raw_list = list(reg or [])
    out: list[BuildingTemplateRegistryEntry] = []
    for raw in raw_list:
        try:
            out.append(BuildingTemplateRegistryEntry.model_validate(raw))
        except Exception:
            continue
    return out


class BuildingTemplateLibraryService:

    def __init__(
        self,
        repo: IBuildingTemplateRepository,
        world_service: WorldService,
    ) -> None:
        self._repo = repo
        self._worlds = world_service

    async def find_by_uid(self, template_uid: str) -> BuildingTemplateRow | None:
        return await self._repo.get_by_uid(template_uid)

    async def upsert_outline(
        self,
        outline: BuildingTemplateOutline,
        *,
        source_file: str | None = None,
    ) -> BuildingTemplateRow:
        uid = building_template_uid(outline.system_name)
        row = BuildingTemplateRow(
            template_uid=uid,
            system_name=outline.system_name,
            display_name=outline.display_name,
            structure_type=outline.structure_type,
            version=outline.version,
            data=outline.model_dump(mode="json"),
            source_file=source_file,
        )
        await self._repo.upsert(row)
        return row

    async def import_bodies_into_world(
        self,
        world_uid: str,
        bodies: list[dict],
    ) -> ImportResult:
        if not isinstance(bodies, list):
            raise BundleValidationError("building_templates section must be an array")
        succeeded = 0
        errors = []
        for i, raw in enumerate(bodies):
            try:
                outline = BuildingTemplateOutline.model_validate(raw)
                row = await self.upsert_outline(outline, source_file="bundle")
                await self._ensure_registry(world_uid, row)
                succeeded += 1
            except Exception as exc:
                from app.application.importResult import ImportError
                errors.append(ImportError(index=i, message=str(exc)))
        return ImportResult(
            total=len(bodies),
            succeeded=succeeded,
            failed=len(errors),
            errors=errors,
        )

    async def export_bodies_for_world(self, world_uid: str) -> list[dict]:
        world = await self._worlds.get_by_id(world_uid)
        bodies: list[dict] = []
        for entry in _registry_entries(world):
            row = await self._repo.get_by_uid(entry.system_template_uid)
            if row is None:
                logger.warning(
                    "building | bundle export miss template_uid=%s world=%s",
                    entry.system_template_uid,
                    world_uid,
                )
                continue
            bodies.append(dict(row.data))
        return bodies

    async def _ensure_registry(self, world_uid: str, row: BuildingTemplateRow) -> None:
        world = await self._worlds.get_by_id(world_uid)
        entries = _registry_entries(world)
        if any(e.system_template_uid == row.template_uid for e in entries):
            return
        entries.append(
            BuildingTemplateRegistryEntry(
                system_template_uid=row.template_uid,
                display_template_name=row.display_name,
                imported_at=datetime.now(timezone.utc).isoformat(),
            )
        )
        await self._worlds.update(
            world_uid,
            {
                "building_template_registry": [
                    e.model_dump(mode="json") for e in entries
                ],
            },
        )
