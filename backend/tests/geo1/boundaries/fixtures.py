"""Explicit post-fill fine evidence, with real common policy and immutable accepted supports."""
from dataclasses import dataclass

from app.application.worldData.generators.hydrology.policy.hydrologyPlacementBinding import bind_hydrology_placement_policy
from app.application.policy.policyResolver import PolicyResolver
from app.dataModel.hydrology.boundaries.attachedCoastline import CoastlineBoundaryInput
from app.dataModel.hydrology.boundaries.boundaryWaterSnapshot import BoundaryWaterSnapshot, FineBoundaryWaterCell
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline, CoastlinePurpose
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan, DeclaredWaterPaint
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping, SourceBodyMappingEntry
from app.dataModel.hydrology.policy.hydrologyPlacementPolicy import HydrologyPolicySnapshot, HydrologyPlacementGateInputs, HydrologyPlacementBehaviorInputs
from app.dataModel.hydrology.waterBody import WaterBody
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.placement.intent import PlacementIdentity, PlacementDependency, PlacementOverlap, PlacementIntent
from app.dataModel.placement.common import PlacementMode, DependencyRelation, OverlapRelation
from app.dataModel.placement.lifecycle.header import PlacementHeader
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.prepared import PreparedPlacementV2, PlacementCandidate, PlacementFootprint
from app.dataModel.placement.result import ResolvedPlacementV2, DisabledPlacement, UnresolvedPlacementV2, PlacementDiagnostic, PlacementIssueCode
from app.dataModel.planning.identity.planKey import PlanKey, WorldPlanScope
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.policy.policyBindings import PolicySupportFact
from app.dataModel.policy.policyEnums import PolicySupportState, PolicyDisableReason
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode as Mode
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from tests.geo1.placement_policy.fixtures import bind, execute, coastline


@dataclass(frozen=True)
class Case:
    source: DeclaredCoastline
    snapshot: BoundaryWaterSnapshot
    input: CoastlineBoundaryInput
    admission: PlacementAdmissionInput


def accepted(uid, region, cells):
    source = coastline().model_copy(update={"value":coastline().value.model_copy(update={"location_uid":uid})})
    decision = execute(bind(source))
    intent = PlacementIntent(identity=PlacementIdentity(world_uid="world",source_uid=uid,region_uid=region),
        mode=PlacementMode.ABSOLUTE,shape=None,dependencies=(),permitted_overlaps=(),separations=())
    prepared = PreparedPlacementV2(intent=intent,original_area=float(len(cells)),decision=decision,
        candidates=(PlacementCandidate(candidate_uid=uid,preference=0,footprint=PlacementFootprint(cells=frozenset(cells),z_min=None,z_max=None)),))
    return ResolvedPlacementV2(prepared=prepared,candidate_uid=uid)


def make(*, source=None, wet=None, dry=False, split=False, mapping=True, merged=False,
         support=PolicySupportState.ACCEPTED, priority=None, mode=Mode.PLANAR, missing_samples=(),
         resolution=ResolutionMode.VALIDATE_ONLY):
    width = 4 if mode is Mode.SPHERE else 3
    fine_width = width*2
    topology = WorldTopology(mode=mode,bounds=WorldBounds(x_min=0,x_max=width-1,y_min=0,y_max=2))
    boundary_x = fine_width//2-1
    source = source if source is not None else DeclaredCoastline(location_uid="boundary",kind=BasinKind.SEA,
        purpose=CoastlinePurpose.BODY_BOUNDARY,target_source_uid="water-source",placement_specificity=priority,
        path=(HydrologyWaypoint(x=boundary_x,y=1),HydrologyWaypoint(x=boundary_x,y=4)))
    if wet is None:
        wet = {} if dry else {(x,y):("body-b" if split and y>=3 else "body-a") for y in range(6) for x in range(fine_width//2,fine_width)}
    bodies = tuple(sorted(set(wet.values())))
    target = accepted("water-source","water-region",set(wet) or {(0,0)})
    targets = (target,accepted("other-source","other-region",set(wet) or {(0,0)})) if merged else (target,)
    outcomes = targets
    if support is PolicySupportState.DISABLED:
        disabled_source = coastline(priority=0).model_copy(update={"value":coastline(priority=0).value.model_copy(update={"location_uid":"water-source"})})
        decision = execute(bind(disabled_source))
        outcomes = (DisabledPlacement(identity=target.identity,reason=PolicyDisableReason.ZERO_PRIORITY,decision=decision),)
    elif support in (PolicySupportState.FAILED,PolicySupportState.CYCLE):
        outcomes = (UnresolvedPlacementV2(identity=target.identity,prepared=None,
            diagnostics=(PlacementDiagnostic(code=PlacementIssueCode.NO_CANDIDATES,region_uid=target.identity.region_uid,detail="water source failed"),)),)
    elif support is not PolicySupportState.ACCEPTED:
        outcomes = ()
    if support is not PolicySupportState.ACCEPTED:
        targets = ()
    entries = []
    if mapping and targets:
        if merged: entries.append(SourceBodyMappingEntry(source_uid="other-source",body_uids=bodies))
        entries.append(SourceBodyMappingEntry(source_uid="water-source",body_uids=bodies))
    mapping_value = SourceBodyMapping(entries=tuple(entries))
    placement_ref = PlanRef(key=PlanKey(world_uid="world",scope=WorldPlanScope(),contract_id="water_placement",
        schema_version=1,algorithm_version=1,input_fingerprint=b"p"*32),output_fingerprint=b"p"*32)
    ref = PlanRef(key=PlanKey(world_uid="world",scope=WorldPlanScope(),contract_id="hydrology",
        schema_version=1,algorithm_version=1,input_fingerprint=b"h"*32),output_fingerprint=b"h"*32)
    hydro = HydrologyPlan(coarse_surface_z=tuple((SurfaceGridCoord(x,y),0) for y in range(3) for x in range(width)),
        coarse_hydro=((SurfaceGridCoord(width//2,1),MapCellHydrology(liquid_candidate=True,water_body_uid=bodies[0])),) if bodies else (),
        sparse_fine_hydro=(),fine_z_overrides=(),physical_unions=(),
        water_bodies=tuple(WaterBody(water_body_uid=body,kind=BasinKind.SEA,declared_level=index,z_water_level=index) for index,body in enumerate(bodies)),
        declared_paint=DeclaredWaterPaint(lakes=(),coastlines=(),segments=(),intents=()))
    envelope = PlanEnvelope[HydrologyPlan](ref=ref,payload=hydro,
        dependencies=(PlanDependency(slot="water_placement",ref=placement_ref),),diagnostics=())
    grid = SurfaceGridSettings(fine_span=2,light_side=3)
    snapshot = BoundaryWaterSnapshot(hydrology=envelope,source_mapping=mapping_value,mapping_hydrology_ref=ref,
        placement_ref=placement_ref,coordinate_space=CoordinateSpace.WORLD_FINE_GRID,water_outcomes=outcomes,grid=grid,topology=topology,
        fine_cells=tuple(FineBoundaryWaterCell(cell=(x,y),body_uid=wet.get((x,y))) for y in range(6) for x in range(fine_width) if (x,y) not in missing_samples))
    policy = HydrologyPolicySnapshot(world_uid="world",hydrology=envelope,source_mapping=mapping_value,mapping_hydrology_ref=ref,
        supports=() if support is None else (PolicySupportFact(uid="water-source",state=support),))
    binding = bind_hydrology_placement_policy(source,HydrologySeasPolicy(placement_specificity=3),
        HydrologyPlacementGateInputs(world_enabled=True,category_enabled=True),
        HydrologyPlacementBehaviorInputs(strategy=Strategy.AUTHORED_REGION),policy,source_path=("boundaries",0),category_path=("seas",))
    decision = PolicyResolver().resolve(binding.spec,binding.inputs,binding.facts,mode=resolution)
    header = PlacementHeader(identity=PlacementIdentity(world_uid="world",source_uid=source.location_uid,region_uid="boundary-region"),
        mode=PlacementMode.ABSOLUTE,dependencies=(PlacementDependency(target_uid="water-region",relation=DependencyRelation.CONNECTED_TO),),
        permitted_overlaps=tuple(PlacementOverlap(target_uid=target.identity.region_uid,relation=OverlapRelation.SHARED_BOUNDARY) for target in targets),separations=())
    input = CoastlineBoundaryInput(sources=(source,),resolution_mode=resolution,grid=grid,topology=topology)
    return Case(source,snapshot,input,PlacementAdmissionInput(header=header,decision=decision))
