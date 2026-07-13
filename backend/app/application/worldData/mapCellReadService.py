"""Pack read entry for ``MapCellService`` — REVIEW-6."""

from __future__ import annotations

from app.application.worldData.pack.read.packReadServices import PackReadServices
from app.db.models.world import World


class MapCellReadService:
    """Thin wrapper over gameplay / debug / loading pack facades."""

    def __init__(self, services: PackReadServices) -> None:
        self._services = services

    @property
    def pack(self) -> PackReadServices:
        return self._services

    def has_pack_for(self, world: World) -> bool:
        return self._services.context.has_pack_for(world)
