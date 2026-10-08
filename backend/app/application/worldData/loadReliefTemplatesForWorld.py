"""Preload relief template bodies for bake consumers (R33/R35) — RELIEF-T-4 / T-18.

Lives in application/worldData (not generators): async IO + library access.
"""

from __future__ import annotations

import logging
from app.application.jsonValidation.resolve import ResolveContext, resolve_model, reject_unresolved
from app.application.jsonValidation.types import FieldPathError

from app.application.jsonValidation.worldRow import relief_template_registry
from app.application.worldData.reliefTemplateLibraryService import ReliefTemplateLibraryService
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.db.models.world import World

logger = logging.getLogger(__name__)


async def load_relief_templates_for_world(
    library: ReliefTemplateLibraryService,
    world: World,
) -> dict[str, ReliefTemplate]:
    """Resolve registry pointers → library bodies (missing/invalid body rejects dependent bake)."""
    reg = relief_template_registry(world)
    out: dict[str, ReliefTemplate] = {}
    for entry in reg.root:
        uid = entry.system_template_uid
        row = await library.find_by_uid(uid)
        ctx = ResolveContext(path_prefix=("relief_template_registry", uid))
        if row is None:
            reject_unresolved(ctx, [FieldPathError(ctx.path_prefix, "library reference unavailable", code="REF_W_UNKNOWN")])
        out[uid] = resolve_model(ReliefTemplate, row.data, ctx=ctx)
    return out
