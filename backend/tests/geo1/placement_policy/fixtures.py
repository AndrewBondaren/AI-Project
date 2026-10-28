"""Explicit final-fill snapshots; no production mapping inference."""
from app.application.worldData.generators.hydrology.policy.hydrologyPlacementBinding import bind_hydrology_placement_policy
from app.application.policy.policyResolver import PolicyResolver
from app.dataModel.hydrology.declaredCoastline import CoastlinePurpose, DeclaredCoastline
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan, DeclaredWaterPaint
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping, SourceBodyMappingEntry
from app.dataModel.hydrology.policy.hydrologyPlacementPolicy import HydrologyPlacementBehaviorInputs, HydrologyPlacementGateInputs, HydrologyPolicySnapshot
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.hydrology.sources.waterDesignSource import CoastlineWaterSource
from app.dataModel.hydrology.waterBody import WaterBody
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.identity.planKey import PlanKey, WorldPlanScope
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.policy.policyBindings import PolicySupportFact
from app.dataModel.policy.policyEnums import PolicySupportState
from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord, FineXY
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.validation.enums.resolutionMode import ResolutionMode


def coastline(boundary=False, *, target="source", priority=None):
    value = DeclaredCoastline(location_uid="boundary" if boundary else "source", kind=BasinKind.SEA,
        purpose=CoastlinePurpose.BODY_BOUNDARY if boundary else CoastlinePurpose.WATER_SOURCE,
        target_source_uid=target if boundary else None, placement_specificity=priority,
        path=(HydrologyWaypoint(x=0,y=0), HydrologyWaypoint(x=2,y=0)))
    return value if boundary else CoastlineWaterSource(value=value)


def snapshot(state=PolicySupportState.ACCEPTED, *, bodies=("physical",), mapped=("physical",),
             wet=True, fine=False, mapping=True, hydro=True, target="source"):
    ref = PlanRef(key=PlanKey(world_uid="world", scope=WorldPlanScope(), contract_id="hydrology",
        schema_version=1, algorithm_version=1, input_fingerprint=b"i"*32), output_fingerprint=b"o"*32)
    cell = MapCellHydrology(liquid_candidate=wet, water_body_uid=bodies[0]) if bodies else None
    plan = HydrologyPlan(coarse_surface_z=((SurfaceGridCoord(0,0),0),),
        coarse_hydro=((SurfaceGridCoord(0,0),cell),) if cell and not fine else (),
        sparse_fine_hydro=(((0,0),cell),) if cell and fine else (), fine_z_overrides=(),
        water_bodies=tuple(WaterBody(water_body_uid=uid,kind=BasinKind.SEA,
            declared_level=0,z_water_level=0,declared_basin_uid="source",location_uid="source") for uid in bodies),
        physical_unions=(), declared_paint=DeclaredWaterPaint(lakes=(),coastlines=(),segments=(),intents=()))
    return HydrologyPolicySnapshot(world_uid="world",
        supports=() if state is None else (PolicySupportFact(uid=target,state=state),),
        hydrology=PlanEnvelope[HydrologyPlan](ref=ref,payload=plan,dependencies=(),diagnostics=()) if hydro else None,
        source_mapping=SourceBodyMapping(entries=() if mapped is None else (
            SourceBodyMappingEntry(source_uid=target,body_uids=mapped),)) if mapping and hydro else None,
        mapping_hydrology_ref=ref if mapping and hydro else None)


def bind(source=None, evidence=None, category=None, *, enabled=True, category_enabled=True, strategy=Strategy.PLATE):
    return bind_hydrology_placement_policy(source if source is not None else coastline(),
        category if category is not None else HydrologySeasPolicy(placement_specificity=3),
        HydrologyPlacementGateInputs(world_enabled=enabled,category_enabled=category_enabled),
        HydrologyPlacementBehaviorInputs(strategy=strategy),
        evidence if evidence is not None else snapshot(None,mapping=False,hydro=False),
        source_path=("hydrology","sources",0),category_path=("hydrology","default_seas"))


def execute(binding, mode=ResolutionMode.VALIDATE_ONLY):
    return PolicyResolver().resolve(binding.spec,binding.inputs,binding.facts,mode=mode)
