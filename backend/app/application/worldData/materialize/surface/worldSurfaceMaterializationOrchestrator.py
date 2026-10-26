"""World pack materialization facade — thin entry for debug HTTP / scripts.

Legacy map_cells ``materialize_surface_stack`` removed; use pack bake modes.
"""

from __future__ import annotations
from app.application.worldData.planning.composition.surfacePlanningEntry import SurfacePlanningEntry

from app.application.jsonValidation.resolve import ResolveContext
from app.application.planning.service.planningService import PlanWaitControl
from app.application.worldData.planning.composition.surfacePlanningAssembler import SurfacePlanningAssembler
from app.application.worldData.planning.composition.surfacePlanningCapture import SurfacePlanningCapture, mountain_template_inputs
from app.application.worldData.planning.guards.sourcePublication import SourcePublicationGuard
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from app.application.worldData.planning.contracts.surfacePlanningView import (
    SurfacePlanningViewKind,
)
from app.application.worldData.regions.regionStateSnapshot import load_region_state_snapshot
from app.db.repositories.iRegionStateRepository import IRegionStateRepository
from app.application.worldData.pack.bake.packBakeResult import PackBakeResult
from app.application.worldData.pack.bake.detailed.packDetailedBakeOrchestrator import (
    PackDetailedBakeOrchestrator,
    PackDetailedBakeResult,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorExtract import (
    SettlementOutdoorExtractError,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorContract import (
    MaterializeResult,
    SettlementOutdoorError,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorOrchestrator import (
    SettlementOutdoorOrchestrator,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorSkip import (
    is_settlement_outdoor_target,
)
from app.application.worldData.materialize.surface.materializationContext import (
    MaterializationContext,
    MaterializationJobReport,
)
from app.dataModel.worldPack.bake.detailedBakeScope import (
    DetailedBakeRequest,
    DetailedBakeScopeKind,
    resolve_detailed_bake_request,
)
from app.dataModel.worldPack.bake.packBakeDefaults import resolve_detailed_grade_stages
from app.dataModel.worldPack.bake.packBakeMode import PackBakeApiMode
from app.dataModel.worldPack.bake.packTilePlan import PackTilePlanScope
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.db.database import Database
from app.application.worldData.pack.bake.l0.packMaterializationOrchestrator import PackMaterializationOrchestrator
from app.application.templateLibrary.loadReliefTemplatesForWorld import load_relief_templates_for_world
from app.application.templateLibrary.templateSnapshotLoader import TemplateSnapshotLoader


class WorldSurfaceMaterializationOrchestrator:
    """Pack surface materialization entry — light / full / detailed."""

    def __init__(
        self,
        pack: PackMaterializationOrchestrator,
        *,
        detailed: PackDetailedBakeOrchestrator,
        relief_loader: TemplateSnapshotLoader | None = None,
        outdoor: SettlementOutdoorOrchestrator | None = None,
        planning: SurfacePlanningAssembler | None = None,
        capture: SurfacePlanningCapture | None = None,
        db: Database | None = None,
        publication_guard: SourcePublicationGuard | None = None,
        region_state_repo: IRegionStateRepository | None = None,
    ) -> None:
        self._planning, self._capture = planning, capture
        self._db, self._publication_guard = db, publication_guard
        self._region_state_repo = region_state_repo
        self._pack = pack
        self._detailed = detailed
        self._relief_loader = relief_loader
        self._outdoor = outdoor

    async def bake_pack(
        self,
        world_uid: str,
        world: World,
        locations: list[NamedLocation],
        ctx: MaterializationContext,
        pack_writer,
        *,
        mode: PackBakeApiMode,
        max_tiles: int | None = None,
        location_uid: str | None = None,
        detailed_scope: DetailedBakeScopeKind | None = None,
        detailed_request: DetailedBakeRequest | None = None,
        tile_gx: int | None = None,
        tile_gy: int | None = None,
        grade_mill: bool | None = None,
        grade_paint: bool | None = None,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        wait: PlanWaitControl,
        resolve_ctx: ResolveContext | None = None,
        anchor_x: int | None = None,
        anchor_y: int | None = None,
    ) -> PackBakeResult:
        """Single application entry for HTTP ``mode=light|full|detailed``.

        light/full: L0 only; full then C23 topology. detailed: L2 then C11
        ``materialize`` on settlement-like ``scope=location``. Wilderness: L2 only.
        Entry → refine-from-entry.
        """
        if mode == "light":
            report = await self.materialize_pack_light(
                world_uid, world, locations, ctx, pack_writer,
                max_tiles=max_tiles,
                nodes=nodes, edges=edges,
                wait=wait, resolve_ctx=resolve_ctx,
                anchor_x=anchor_x, anchor_y=anchor_y,
            )
            return PackBakeResult(
                mode=mode,
                terrain_failed=report.terrain.failed,
                report=report,
            )
        if mode == "full":
            report = await self.materialize_pack_full(
                world_uid, world, locations, ctx, pack_writer,
                nodes=nodes, edges=edges,
                wait=wait, resolve_ctx=resolve_ctx,
            )
            return PackBakeResult(
                mode=mode,
                terrain_failed=report.terrain.failed,
                report=report,
            )
        if mode == "detailed":
            if detailed_request is None:
                stages = resolve_detailed_grade_stages(
                    grade_mill,
                    grade_paint,
                    defaults=self._detailed._defaults,
                )
                request = resolve_detailed_bake_request(
                    scope=detailed_scope,
                    location_uid=location_uid,
                    max_tiles=max_tiles or 0,
                    tile_gx=tile_gx,
                    tile_gy=tile_gy,
                    grade_mill=stages.mill,
                    grade_paint=stages.paint,
                )
            else:
                request = detailed_request
            detailed, settlement = await self.materialize_pack_detailed(
                world, locations, ctx, pack_writer, request,
                nodes=nodes, edges=edges,
                wait=wait, resolve_ctx=resolve_ctx,
            )
            return PackBakeResult(
                mode=mode,
                terrain_failed=detailed.terrain.failed,
                detailed=detailed,
                climate_fine_tiles=detailed.climate_fine_tiles or None,
                settlement=settlement,
            )
        raise ValueError(f"unknown pack bake mode '{mode}'")

    def plan_bootstrap_tiles(
        self,
        world: World,
        locations: list[NamedLocation],
        *,
        scope: PackTilePlanScope = "light",
        max_tiles: int | None = None,
    ):
        """Preview L0 tile set — extent probe only (R2); no plan prepare."""
        if self._planning is None or self._capture is None:
            raise ValueError("surface planning dependencies required")
        entry = SurfacePlanningEntry(self._planning, self._capture)
        status = entry.probe_extent(world, locations, mode=ResolutionMode.RUNTIME,
            mountain_templates=(), resolve_ctx=ResolveContext())
        if status == SurfacePlanningViewKind.NO_EXTENT:
            raise ValueError("surface terrain context unavailable")
        return self._pack.tile_planner.plan(
            world, locations,
            scope=scope,
            max_tiles=max_tiles if scope == "light" else None,
        )

    async def materialize_pack_light(
        self,
        world_uid: str,
        world: World,
        locations: list[NamedLocation],
        ctx: MaterializationContext,
        pack_writer,
        *,
        max_tiles: int | None = None,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        wait: PlanWaitControl,
        resolve_ctx: ResolveContext | None = None,
        anchor_x: int | None = None,
        anchor_y: int | None = None,
        pack_orchestrator: PackMaterializationOrchestrator | None = None,
    ) -> MaterializationJobReport:
        orch = pack_orchestrator if pack_orchestrator is not None else self._pack
        return await orch.materialize_light_pack(
            world_uid, world, locations, pack_writer, ctx,
            max_tiles=max_tiles,
            nodes=nodes, edges=edges,
            wait=wait, resolve_ctx=resolve_ctx,
            anchor_x=anchor_x, anchor_y=anchor_y,
        )

    async def materialize_pack_full(
        self,
        world_uid: str,
        world: World,
        locations: list[NamedLocation],
        ctx: MaterializationContext,
        pack_writer,
        *,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        wait: PlanWaitControl,
        resolve_ctx: ResolveContext | None = None,
    ) -> MaterializationJobReport:
        report = await self._pack.materialize_full_pack(
            world_uid, world, locations, pack_writer, ctx,
            nodes=nodes, edges=edges,
            wait=wait, resolve_ctx=resolve_ctx,
        )
        if self._outdoor is not None:
            await self._outdoor.plan_topology(world_uid)
        return report

    async def materialize_pack_detailed(
        self,
        world: World,
        locations: list[NamedLocation],
        ctx: MaterializationContext,
        pack_writer,
        request: DetailedBakeRequest,
        *,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        wait: PlanWaitControl,
        resolve_ctx: ResolveContext | None = None,
    ) -> tuple[PackDetailedBakeResult, MaterializeResult | None]:
        if self._planning is None or self._capture is None or self._db is None or self._publication_guard is None:
            raise ValueError("surface planning/publication dependencies required")
        request_ctx = resolve_ctx if resolve_ctx is not None else ResolveContext()
        if request_ctx.validate_only:
            raise ValueError("validation cannot materialize a pack")
        relief_templates = (await load_relief_templates_for_world(self._relief_loader, world)
            if self._relief_loader is not None else {})
        templates = mountain_template_inputs(relief_templates)
        entry = SurfacePlanningEntry(self._planning, self._capture)
        captured = entry.capture_view(world, locations, mode=ResolutionMode.RUNTIME,
            mountain_templates=templates, resolve_ctx=request_ctx)
        prepared = entry.prepare_captured(
            captured, world=world, wait=wait, resolve_ctx=request_ctx)
        if prepared is None:
            raise ValueError("surface terrain context unavailable")
        surface_bundle, working = prepared
        if self._region_state_repo is None:
            raise ValueError("region state repository required for materialization")
        region_states = await load_region_state_snapshot(self._region_state_repo, world.world_uid)
        detailed = await self._detailed.bake(
            world, locations, pack_writer, ctx, surface_bundle, request,
            region_state_snapshot=region_states,
            working=working,
        )
        async with self._db.transaction_if_needed():
            await self._publication_guard.require_fresh(captured, mode=ResolutionMode.RUNTIME,
                mountain_templates=templates, resolve_ctx=request_ctx)
            pack_writer.recalc_manifest_counters()
            pack_writer.save_manifest()
        settlement = await self._maybe_materialize_c11(world, locations, request)
        return detailed, settlement

    async def _maybe_materialize_c11(
        self,
        world: World,
        locations: list[NamedLocation],
        request: DetailedBakeRequest,
    ) -> MaterializeResult | None:
        """Step 2 detailed_bake: C11 packing on settlement-like location. L2 already persisted."""
        if self._outdoor is None or request.scope != "location":
            return None
        location_uid = request.location_uid
        if not location_uid:
            return None
        loc = next((item for item in locations if item.location_uid == location_uid), None)
        if loc is None or not is_settlement_outdoor_target(loc, world=world):
            return None
        try:
            return await self._outdoor.materialize(
                world.world_uid,
                location_uid,
                skip_if_initialized=True,
            )
        except (SettlementOutdoorError, SettlementOutdoorExtractError) as exc:
            return MaterializeResult(
                location_uid=location_uid,
                status="error",
                error=str(exc),
            )
