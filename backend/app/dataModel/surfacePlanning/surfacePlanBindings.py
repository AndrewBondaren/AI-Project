"""PC and explicit GEO dependency declarations; registration belongs to composition."""

from dataclasses import dataclass

from app.dataModel.cache.contracts.cacheContract import CacheContractId, CacheContractRegistry, CacheSchemaVersion
from app.dataModel.planning.contracts.planContract import PlanContractMetadata, PlanContractRegistry
from app.dataModel.planning.contracts.planDependency import PlanDependencyContract
from app.dataModel.planning.identity.planKey import AlgorithmVersion, SchemaVersion, PlanSlot
from app.dataModel.registryKey import RegistryKey
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot


@dataclass(frozen=True)
class SurfacePlanBinding:
    slot: SurfacePlanSlot
    upstream: tuple[SurfacePlanSlot, ...]
    metadata: PlanContractMetadata
    cache_id: CacheContractId
    cache_schema_version: CacheSchemaVersion
    declared_dependencies: tuple[PlanDependencyContract, ...] | None = None

    def __post_init__(self) -> None:
        if len(set(self.upstream)) != len(self.upstream):
            raise ValueError("duplicate upstream surface slot")
        if self.declared_dependencies is not None:
            slots = tuple(dependency.slot for dependency in self.declared_dependencies)
            if slots != tuple(sorted(PlanSlot(slot.value) for slot in self.upstream)):
                raise ValueError("explicit dependencies must match upstream slots in canonical order")

    def dependency_contracts(self) -> tuple[PlanDependencyContract, ...]:
        if self.declared_dependencies is not None:
            return self.declared_dependencies
        return tuple(PlanDependencyContract(slot=PlanSlot(slot.value),
            contract_id=(meta := surface_plan_binding(slot).metadata).id,
            schema_version=meta.schema_version, algorithm_version=meta.algorithm_version)
            for slot in sorted(self.upstream, key=lambda slot: slot.value.encode("utf-8")))


def _declare(slot: SurfacePlanSlot, upstream: tuple[SurfacePlanSlot, ...], *,
             schema_version: SchemaVersion = SchemaVersion(1)) -> SurfacePlanBinding:
    return SurfacePlanBinding(slot, upstream, PlanContractMetadata(
        id=RegistryKey[PlanContractRegistry](f"surface.pc.{slot.value}"),
        schema_version=schema_version, algorithm_version=AlgorithmVersion(1)),
        RegistryKey[CacheContractRegistry](f"surface.envelope.pc.{slot.value}"), CacheSchemaVersion(schema_version))


S = SurfacePlanSlot
PC_SURFACE_BINDINGS = (
    _declare(S.CLIMATE_BASE, ()),
    _declare(S.TERRAIN_BASE, (S.CLIMATE_BASE,)),
    _declare(S.WATER_PLACEMENT, (S.TERRAIN_BASE,), schema_version=SchemaVersion(2)),
    _declare(S.RELIEF, (S.CLIMATE_BASE, S.TERRAIN_BASE, S.WATER_PLACEMENT)),
    _declare(S.HYDROLOGY_ROUTES, (S.RELIEF, S.WATER_PLACEMENT)),
    _declare(S.RIVER_RELIEF, (S.RELIEF, S.HYDROLOGY_ROUTES)),
    _declare(S.HYDROLOGY, (S.RELIEF, S.HYDROLOGY_ROUTES, S.RIVER_RELIEF)),
    _declare(S.CLIMATE_LOCAL, (S.CLIMATE_BASE, S.HYDROLOGY)),
)


def surface_plan_binding(slot: SurfacePlanSlot) -> SurfacePlanBinding:
    return next(binding for binding in PC_SURFACE_BINDINGS if binding.slot is slot)


def _declare_geo(slot: SurfacePlanSlot, upstream: tuple[SurfacePlanBinding, ...]) -> SurfacePlanBinding:
    ordered = tuple(sorted(upstream, key=lambda binding: binding.slot.value.encode("utf-8")))
    return SurfacePlanBinding(slot, tuple(binding.slot for binding in ordered), PlanContractMetadata(
        id=RegistryKey[PlanContractRegistry](f"surface.geo.{slot.value}"),
        schema_version=SchemaVersion(2), algorithm_version=AlgorithmVersion(1)),
        RegistryKey[CacheContractRegistry](f"surface.envelope.geo.{slot.value}"), CacheSchemaVersion(2),
        tuple(PlanDependencyContract(slot=PlanSlot(binding.slot.value), contract_id=binding.metadata.id,
            schema_version=binding.metadata.schema_version, algorithm_version=binding.metadata.algorithm_version)
            for binding in ordered))


def _geo_bindings() -> tuple[SurfacePlanBinding, ...]:
    base, terrain = surface_plan_binding(S.CLIMATE_BASE), surface_plan_binding(S.TERRAIN_BASE)
    regions = _declare_geo(S.TERRAIN_REGIONS, ())
    water = _declare_geo(S.WATER_PLACEMENT, (terrain, regions))
    relief = _declare_geo(S.RELIEF, (base, terrain, water))
    routes = _declare_geo(S.HYDROLOGY_ROUTES, (relief, water))
    river = _declare_geo(S.RIVER_RELIEF, (relief, routes))
    final = _declare_geo(S.HYDROLOGY, (relief, routes, river))
    local = _declare_geo(S.CLIMATE_LOCAL, (base, final))
    boundary = _declare_geo(S.COASTLINE_BOUNDARIES, (final, water))
    support = _declare_geo(S.SURFACE_SUPPORT, (base, terrain, relief, river, final, local))
    coating = _declare_geo(S.COATING, (support, final))
    return base, terrain, regions, water, relief, routes, river, final, local, boundary, support, coating


# Metadata declarations only. Production registration switches as one G10-A operation.
GEO_SURFACE_BINDINGS = _geo_bindings()


def geo_surface_plan_binding(slot: SurfacePlanSlot) -> SurfacePlanBinding:
    return next(binding for binding in GEO_SURFACE_BINDINGS if binding.slot is slot)
