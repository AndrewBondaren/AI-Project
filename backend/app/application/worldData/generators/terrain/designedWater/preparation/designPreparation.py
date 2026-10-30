"""Ready-source design and joint spatial competition (GEO-1 J05–J07)."""

from collections.abc import Callable

from pydantic import TypeAdapter

from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.terrain.designedWater.preparation.placementPreparation import DesignedWaterPlacementPreparer
from app.application.worldData.generators.terrain.designedWater.strategies.strategyFactory import DesignedWaterStrategyFactory
from app.application.worldData.placement.diagnostics import diagnostic
from app.application.worldData.placement.lifecycle.session import PlacementSession, SupportReevaluation
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import WaterDesignDecision
from app.dataModel.identity.uid import EntityUid
from app.dataModel.placement.batch import PlacementBatchV2
from app.dataModel.placement.common import PlacementPhase
from app.dataModel.placement.intent import PlacementIntent
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.lifecycle.header import PlacementHeader
from app.dataModel.placement.prepared import PreparedPlacementV2
from app.dataModel.placement.result import PlacementBatchResultV2, PlacementIssueCode
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.terrain.designedWater.input import WaterStrategyInput
from app.dataModel.terrain.designedWater.preparation.result import WaterDesignPreparation
from app.dataModel.terrain.designedWater.settings.fieldSelectionPolicy import WaterFieldSelectionPolicy
from app.dataModel.terrain.designedWater.strategyKind import WaterDesignIssueCode
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError

_INPUT = TypeAdapter(WaterStrategyInput)
_ADMISSION = TypeAdapter(WaterDesignDecision)


def _invalid(message: str) -> PlanBuildFailure:
    return PlanBuildFailure((FieldPathError(("water_design", "universe"), message,
        code=WaterDesignIssueCode.INVALID_PREPARATION_INPUT.value),))


def prepare_designed_water(
    batch: PlacementBatchV2, *, water_intents: tuple[PlacementIntent, ...],
    pre_hydrology: PlanEnvelope[TerrainPlan], grid: SurfaceGridSettings, seed_root: EntityUid,
    prepare_input: Callable[[PlacementAdmissionInput], WaterStrategyInput],
    prepare_competitor: Callable[[PlacementAdmissionInput], PreparedPlacementV2],
    strategies: DesignedWaterStrategyFactory, selection_policy: WaterFieldSelectionPolicy,
    control: PlanBuildControl, reevaluate_support: SupportReevaluation | None = None,
) -> tuple[tuple[WaterDesignPreparation, ...], PlacementBatchResultV2]:
    """Design each ready water source once, in the same P2 session as competitors.

    The input owner supplies J01–J05 evidence only when admission permits design.
    It receives the session's current decision after SUPPORT reevaluation. Neither
    callback resolves placement. The returned design results retain metadata,
    profiles and notices even for spatial losers; the common result retains every
    terminal outcome. No water placement record or production schema is projected.
    """
    control.raise_if_shutdown()
    batch = PlacementBatchV2.model_validate(batch, strict=True)
    pre_hydrology = PlanEnvelope[TerrainPlan].model_validate(pre_hydrology, strict=True)
    grid = SurfaceGridSettings.model_validate(grid, strict=True)
    selection_policy = WaterFieldSelectionPolicy.model_validate(selection_policy, strict=True)
    if (batch.phase is not PlacementPhase.PRE_RELIEF
            or batch.world_uid != pre_hydrology.ref.key.world_uid
            or batch.snapshot_revision != pre_hydrology.ref.output_fingerprint):
        raise _invalid("design requires the same world/pre-relief terrain revision")
    bounds, bbox = batch.topology.bounds, pre_hydrology.payload.bbox
    if (bounds.x_min, bounds.x_max, bounds.y_min, bounds.y_max) != (
            bbox.x_min, bbox.x_max, bbox.y_min, bbox.y_max):
        raise _invalid("design requires whole-scope terrain matching batch topology")
    intents = tuple(PlacementIntent.model_validate(intent, strict=True) for intent in water_intents)
    by_region = {intent.identity.region_uid: intent for intent in intents}
    if (len(by_region) != len(intents)
            or len({intent.identity.source_uid for intent in intents}) != len(intents)):
        raise _invalid("water source and placement identities must be unique")
    admissions = {item.header.identity.region_uid: item for item in batch.objects}
    for uid, intent in by_region.items():
        if uid not in admissions or PlacementHeader.from_intent(intent) != admissions[uid].header:
            raise _invalid("every water intent must retain its exact batch admission header")

    session = PlacementSession.start(batch, reevaluate_support=reevaluate_support)
    preparer = DesignedWaterPlacementPreparer()
    designs: dict[EntityUid, WaterDesignPreparation] = {}

    def prepare_ready(headers: tuple[PlacementHeader, ...]) -> None:
        for header in headers:
            control.raise_if_shutdown()
            uid = header.identity.region_uid
            admission = session.objects[uid]
            try:
                if uid not in by_region:
                    session.submit(prepare_competitor(admission))
                    continue
                decision = _ADMISSION.validate_python(admission.decision, strict=True)
                value = _INPUT.validate_python(prepare_input(admission), strict=True)
                if (value.pre_hydrology != pre_hydrology or value.topology != batch.topology
                        or value.grid != grid or value.seed_root != seed_root
                        or value.metadata.source_uid != header.identity.source_uid
                        or decision.require_behavior() is not value.strategy):
                    raise _invalid("ready water input must retain batch terrain/topology/grid/seed/source/strategy")
                control.raise_if_shutdown()
                draft = strategies.get(value.strategy).design(value)
                control.raise_if_shutdown()
                design = preparer.prepare(value, draft, selection_policy=selection_policy)
                prepared = preparer.bind_admission(value, design, intent=by_region[uid], admission=admission)
                session.submit(prepared)
                designs[uid] = design
            except PlanBuildFailure as failure:
                session.fail(header.identity, tuple(diagnostic(header, PlacementIssueCode.CONSTRAINT_VIOLATION,
                    f"{issue.code}: {issue.message}", path=issue.path) for issue in failure.issues))

    result = session.run(prepare_ready, check_cancelled=control.raise_if_shutdown)
    return tuple(designs[uid] for uid in sorted(designs)), result
