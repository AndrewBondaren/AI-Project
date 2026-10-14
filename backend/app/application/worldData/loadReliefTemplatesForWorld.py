"""Preload relief template bodies for bake consumers (R33/R35) — RELIEF-T-4 / T-18.

Lives in application/worldData (not generators): async IO + library access.
Bodies come from the membership-scoped ``ReliefTemplateSnapshot`` (B5); the
legacy world registry is no longer consulted here.
"""

from __future__ import annotations

import logging

from app.application.worldData.templateSnapshotLoader import TemplateSnapshotLoader
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.db.models.world import World

logger = logging.getLogger(__name__)


async def load_relief_templates_for_world(
    loader: TemplateSnapshotLoader,
    world: World,
) -> dict[str, ReliefTemplate]:
    """Membership-scoped relief bodies keyed by member ``template_uid``."""
    snapshot = await loader.load_relief(world)
    return {uid: entry.body for uid, entry in snapshot.templates.items()}
