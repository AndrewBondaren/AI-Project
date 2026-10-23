"""Authoritative re-read/check inside the caller's short publication UOW."""

from app.application.jsonValidation.resolve import ResolveContext
from app.application.worldData.planning.composition.surfacePlanningCapture import SurfacePlanningCapture
from app.application.worldData.planning.contracts.surfacePlanningView import SurfacePlanningView
from app.application.worldData.planning.guards.sourceRevision import require_current_source
from app.application.worldData.registries.worldLookup import require_world
from app.dataModel.terrain.relief.planning.reliefPlan import MountainTemplateInput
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from app.db.models.world import World
from app.db.repositories.iNamedLocationRepository import INamedLocationRepository
from app.db.repositories.iWorldRepository import IWorldRepository


class SourcePublicationGuard:
    def __init__(self, worlds: IWorldRepository, locations: INamedLocationRepository,
                 capture: SurfacePlanningCapture) -> None:
        self._worlds, self._locations, self._capture = worlds, locations, capture

    async def require_fresh(self, captured: SurfacePlanningView, *, mode: ResolutionMode,
                            mountain_templates: tuple[MountainTemplateInput, ...],
                            resolve_ctx: ResolveContext) -> World:
        current = await require_world(self._worlds, captured.world_uid)
        locations = await self._locations.list_by_world_insert_order(captured.world_uid)
        view = self._capture.capture(current, locations, mode=mode,
            mountain_templates=mountain_templates, resolve_ctx=resolve_ctx)
        require_current_source(captured, view)
        return current
