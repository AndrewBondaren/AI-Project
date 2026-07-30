"""Bundle section ``relief_templates`` — R35 bodies; R34 sync via import service.

BUNDLE-2 / RELIEF-T-6 / RELIEF-T-21: typed registry export; domain errors only.
"""

from __future__ import annotations

import logging

from app.application.importResult import ImportResult
from app.application.jsonValidation.worldRow import relief_template_registry
from app.application.worldData.reliefErrors import ReliefValidationError
from app.application.worldData.reliefTemplateLibraryService import ReliefTemplateLibraryService
from app.application.worldData.reliefWorldImportService import ReliefWorldImportService
from app.db.models.world import World

logger = logging.getLogger(__name__)


async def export_relief_template_bodies(
    world: World,
    library: ReliefTemplateLibraryService,
) -> list[dict]:
    """Self-contained bodies for registry pointers; miss → WARNING, skip."""
    bodies: list[dict] = []
    reg = relief_template_registry(world)
    for entry in reg.root:
        uid = entry.system_template_uid
        row = await library.find_by_uid(uid)
        if row is None:
            logger.warning(
                "relief | bundle export miss template_uid=%s world=%s context=%s",
                uid,
                world.world_uid,
                entry.context.value,
            )
            continue
        bodies.append(dict(row.data))
    return bodies


async def import_relief_templates_section(
    world_uid: str,
    bodies: object,
    relief_import: ReliefWorldImportService,
) -> ImportResult:
    if not isinstance(bodies, list):
        raise ReliefValidationError("relief_templates section must be an array")
    info = await relief_import.import_outlines_into_world(world_uid, bodies)
    n = int(info["imported"])
    return ImportResult(total=n, succeeded=n, failed=0)
