"""Single declaration of baseline surface dependencies and contract identities."""

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

    def dependency_contracts(self) -> tuple[PlanDependencyContract, ...]:
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
