"""Bundle section ``relief_templates`` — R35 bodies; R34 sync via import service.

BUNDLE-2 / RELIEF-T-6 / RELIEF-T-21: typed registry export; domain errors only.
Export bodies are membership-scoped — ``ReliefTemplateLibraryService.
export_bodies_for_world`` (B6); this module keeps the import adapter.
"""

from __future__ import annotations

from app.application.importResult import ImportResult
from app.application.worldData.libraryPacks.errors import require_no_policy
from app.application.worldData.reliefErrors import ReliefValidationError
from app.application.worldData.reliefWorldImportService import ReliefWorldImportService


async def import_relief_templates_section(
    world_uid: str,
    bodies: object,
    relief_import: ReliefWorldImportService,
) -> ImportResult:
    if not isinstance(bodies, list):
        raise ReliefValidationError("relief_templates section must be an array")
    info = require_no_policy(await relief_import.import_outlines_into_world(world_uid, bodies))
    n = int(info["imported"])
    return ImportResult(total=n, succeeded=n, failed=0)
