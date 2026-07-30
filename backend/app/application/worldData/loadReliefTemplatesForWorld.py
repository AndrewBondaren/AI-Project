"""Preload relief template bodies for bake consumers (R33/R35) — RELIEF-T-4 / T-18.

Lives in application/worldData (not generators): async IO + library access.
"""

from __future__ import annotations

import logging

from app.application.jsonValidation.worldRow import relief_template_registry
from app.application.worldData.reliefTemplateLibraryService import ReliefTemplateLibraryService
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.db.models.world import World

logger = logging.getLogger(__name__)


async def load_relief_templates_for_world(
    library: ReliefTemplateLibraryService,
    world: World,
) -> dict[str, ReliefTemplate]:
    """Resolve registry pointers → library bodies (missing uid skipped + WARNING)."""
    reg = relief_template_registry(world)
    out: dict[str, ReliefTemplate] = {}
    for entry in reg.root:
        uid = entry.system_template_uid
        row = await library.find_by_uid(uid)
        if row is None:
            logger.warning(
                "relief | preload miss template_uid=%s world=%s",
                uid,
                world.world_uid,
            )
            continue
        try:
            out[uid] = ReliefTemplate.model_validate(row.data)
        except Exception as exc:
            logger.warning(
                "relief | preload invalid body template_uid=%s err=%s",
                uid,
                exc,
            )
    if reg.root and not out:
        logger.warning(
            "relief | preload empty bodies world=%s registry_n=%d "
            "(mountain/road_shoulder will R21 / skip)",
            world.world_uid,
            len(reg.root),
        )
    elif reg.root and len(out) < len(reg.root):
        logger.warning(
            "relief | preload partial world=%s loaded=%d registry_n=%d",
            world.world_uid,
            len(out),
            len(reg.root),
        )
    return out
