"""Own authored paint geometry and reject incomplete paths without synthetic anchors."""

from collections.abc import Mapping

from app.application.jsonValidation.resolve import ResolveContext
from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.hydrology.load.loadDeclaredHydrology import (
    LoadedDeclaredHydrology, load_prepared_declared_hydrology,
)
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.hydrology.declaredRiver import DeclaredRiver
from app.dataModel.hydrology.planning.hydrologyPlan import (
    CoastlinePaint, DeclaredWaterPaint, IntentRiverPaint, LakePaint, SegmentRiverPaint,
)
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyAnchorInput
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.spatial.grid.coordinateTypes import FineDelta, FineX, FineXY, FineY
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.worldPack.wire.hydrologyMaskWire import HydrologyMaskWire


class DeclaredWaterPaintProjector:
    def project(self, *, rivers: tuple[DeclaredRiver, ...], coastlines: tuple[DeclaredCoastline, ...],
                lakes: tuple[DeclaredLake, ...], anchors: tuple[HydrologyAnchorInput, ...],
                ) -> PlanBuildResult[DeclaredWaterPaint]:
        loaded = load_prepared_declared_hydrology(list(coastlines), list(lakes), list(rivers), [])
        locations = {anchor.location_uid: anchor.position for anchor in anchors if anchor.position is not None}
        ctx = ResolveContext(collect_only=True)
        intents = []
        width = HydrologyMaskWire(width=1).width
        if width is None:
            raise PlanBuildFailure((FieldPathError(("declared_paint",), "river paint width requires resolved wire clamp"),))
        for river in loaded.river_intents:
            path = self._intent_path(river, locations)
            if path is None:
                ctx.errors.append(FieldPathError(("hydrology", "rivers", river.location_uid),
                    "declared paint requires complete authored anchors", code="RIVER_MISSING_PAINT_GEOMETRY"))
                continue
            intents.append(IntentRiverPaint(river_uid=river.location_uid, path=path, width_wire=width))
        segments = self._segments(loaded, ctx)
        paint = DeclaredWaterPaint(
            lakes=tuple(LakePaint(location_uid=lake.location_uid, shoreline_segments=tuple(
                ((FineX(a[0]), FineY(a[1])), (FineX(b[0]), FineY(b[1]))) for a, b in lake.shoreline_segments))
                for lake in loaded.lake_specs),
            coastlines=tuple(CoastlinePaint(location_uid=coast.location_uid, segments=tuple(
                ((FineX(a[0]), FineY(a[1])), (FineX(b[0]), FineY(b[1]))) for a, b in coast.segments))
                for coast in loaded.coastline_specs), segments=segments, intents=tuple(intents))
        # This projector only emits issues when it rejects authored geometry.
        # ERROR is its explicit domain outcome, independent of the issue code.
        return PlanBuildResult[DeclaredWaterPaint](payload=paint, diagnostics=tuple(
            PlanDiagnostic(issue=issue, disposition=PlanDiagnosticDisposition.ERROR) for issue in dict.fromkeys(ctx.errors)))

    def _intent_path(self, river: DeclaredRiver, anchors: Mapping[EntityUid, FineXY]) -> tuple[FineXY, ...] | None:
        path: list[FineXY] = []
        if river.source is not None:
            path.append((FineX(river.source.x), FineY(river.source.y)))
        for uid in river.route_location_uids:
            point = anchors.get(uid)
            if point is None:
                return None
            path.append(point)
        if river.mouth is not None:
            mouth = river.mouth
            point = anchors.get(mouth.location_uid) if mouth.location_uid else (
                (FineX(mouth.x), FineY(mouth.y)) if mouth.x is not None and mouth.y is not None else None)
            if point is None:
                return None
            path.append(point)
        return tuple(path) if len(path) >= 2 else None

    def _segments(self, loaded: LoadedDeclaredHydrology, ctx: ResolveContext) -> tuple[SegmentRiverPaint, ...]:
        segments = []
        for edge in loaded.river_edges:
            if edge.width_cells <= 0:
                ctx.errors.append(FieldPathError(("hydrology", "rivers", edge.edge_uid),
                    "declared paint requires positive fine width", code="RIVER_INVALID_PAINT_WIDTH"))
                continue
            a, b = edge.segment
            segments.append(SegmentRiverPaint(edge_uid=edge.edge_uid, location_uid=edge.location_uid,
                segment=((FineX(a[0]), FineY(a[1])), (FineX(b[0]), FineY(b[1]))), width_fine=FineDelta(edge.width_cells)))
        return tuple(segments)
