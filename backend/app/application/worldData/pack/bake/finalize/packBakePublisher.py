"""L0 pack publication: freshness check and finalization in a short UOW."""

from collections.abc import Callable

from app.application.jsonValidation.resolve import ResolveContext
from app.application.worldData.pack.bake.finalize.packBakeFinalize import finalize_pack_on_world
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.read.packReadContext import PackReadContext
from app.application.worldData.planning.contracts.surfacePlanningView import SurfacePlanningView
from app.application.worldData.planning.guards.sourcePublication import SourcePublicationGuard
from app.dataModel.terrain.relief.planning.reliefPlan import MountainTemplateInput
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from app.db.database import Database
from app.db.repositories.iWorldRepository import IWorldRepository


class PackBakePublisher:
    def __init__(
        self,
        *,
        db: Database,
        world_repository: IWorldRepository,
        publication_guard: SourcePublicationGuard,
        read_context_for: Callable[[str], PackReadContext] | None = None,
    ) -> None:
        if db is None or world_repository is None or publication_guard is None:
            raise ValueError("pack publication requires database, world repository and source publication guard")
        self._db = db
        self._world_repository = world_repository
        self._publication_guard = publication_guard
        self._read_context_for = read_context_for

    async def publish(
        self,
        captured: SurfacePlanningView,
        writer: WorldPackWriter,
        *,
        mountain_templates: tuple[MountainTemplateInput, ...],
        resolve_ctx: ResolveContext,
    ) -> None:
        read_context = (self._read_context_for(captured.world_uid)
                        if self._read_context_for is not None else None)
        async with self._db.transaction_if_needed():
            current = await self._publication_guard.require_fresh(
                captured, mode=ResolutionMode.RUNTIME,
                mountain_templates=mountain_templates, resolve_ctx=resolve_ctx,
            )
            writer.recalc_manifest_counters()
            await finalize_pack_on_world(
                self._world_repository, current, writer,
                db_path=self._db.path, read_context=read_context,
            )
