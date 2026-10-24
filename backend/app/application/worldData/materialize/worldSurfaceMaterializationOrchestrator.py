"""World pack materialization facade — thin entry for debug HTTP / scripts.

Legacy map_cells ``materialize_surface_stack`` removed; use pack bake modes.
"""

from __future__ import annotations

from app.application.jsonValidation.resolve import ResolveContext
from app.application.planning.service.planningService import PlanWaitControl
from app.application.worldData.planning.composition.surfacePlanningAssembler import SurfacePlanningAssembler, prepare_captured_bundle
from app.application.worldData.planning.composition.surfacePlanningCapture import SurfacePlanningCapture, mountain_template_inputs
from app.application.worldData.planning.guards.sourcePublication import SourcePublicationGuard
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    require_surface_terrain_context,
)
from app.application.worldData.pack.bake.packBakeResult import PackBakeResult
from app.application.worldData.pack.bake.packDetailedBakeOrchestrator import (
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
from app.application.worldData.materialize.materializationContext import (
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
from app.application.worldData.pack.bake.packMaterializationOrchestrator import PackMaterializationOrchestrator
from app.application.templateLibrary.loadReliefTemplatesForWorld import load_relief_templates_for_world


class WorldSurfaceMaterializationOrchestrator:
    """Pack surface materialization entry — light / full / detailed."""

    def __init__(
        self,
        pack: PackMaterializationOrchestrator,
        *,
        detailed: PackDetailedBakeOrchestrator | None = None,
        outdoor: SettlementOutdoorOrchestrator | None = None,
        planning: SurfacePlanningAssembler | None = None,
        capture: SurfacePlanningCapture | None = None,
        db: Database | None = None,
        publication_guard: SourcePublicationGuard | None = None,
    ) -> None:
        self._planning, self._capture = planning, capture
        self._db, self._publication_guard = db, publication_guard
        self._pack = pack
        self._detailed = detailed or PackDetailedBakeOrchestrator(
            pack.terrain,
            relief_loader=pack.relief_loader,
            relief_grade_repo=pack.relief_grade_repo,
        )
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
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        wait: PlanWaitControl,
        resolve_ctx: ResolveContext | None = None,
    ):
        """Preview L0 tile set — application owns surface_ctx + planner."""
        if self._planning is None or self._capture is None:
            raise ValueError("surface planning dependencies required")
        surface_ctx = require_surface_terrain_context(
            world, locations, nodes=nodes, edges=edges,
            planning=self._planning, capture=self._capture, wait=wait, resolve_ctx=resolve_ctx,
        )
        return self._pack.tile_planner.plan(
            world, locations, surface_ctx,
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
        relief_templates = (await load_relief_templates_for_world(self._pack.relief_loader, world)
            if self._pack.relief_loader is not None else {})
        templates = mountain_template_inputs(relief_templates)
        captured = self._capture.capture(world, locations, mode=ResolutionMode.RUNTIME,
            mountain_templates=templates, resolve_ctx=request_ctx)
        surface_bundle = prepare_captured_bundle(captured, planning=self._planning, wait=wait, resolve_ctx=request_ctx)
        if surface_bundle is None:
            raise ValueError("surface terrain context unavailable")
        detailed = await self._detailed.bake(
            world, locations, pack_writer, ctx, surface_bundle, request,
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
