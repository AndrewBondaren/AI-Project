from copy import replace

from app.application.cache.backends.memoryCache import MemoryCache
from app.application.cache.service.cacheService import CacheService
from app.application.planning.providers.planRegistry import PlanRegistry, PlanDependencyReader
from app.application.planning.service.planFingerprints import output_fingerprint
from app.application.planning.service.planningService import PlanningService
from app.application.worldData.planning.composition.planProviders import register_world_plan_providers
from app.application.worldData.planning.composition.natural.preparedTerrain import register_natural_terrain
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.cache.policy.cachePolicy import CachePolicy
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.identity.planKey import PlanKey
from app.dataModel.planning.policy.planningExecutionPolicy import PlanningExecutionPolicy
from tests.geo1.terrain_base.fixtures import inputs
from tests.planning.providers.test_domain_providers import Wait


def values(*, shape=None, mountain=True):
    v = list(inputs(mountain=mountain))
    if shape is not None:
        v[2] = replace(v[2], terrain_entries=tuple(replace(e, hills=replace(e.hills, shapes=(shape,)))
                       if e.hills else e for e in v[2].terrain_entries))
    return v


class ReadyPlans:
    def __init__(self, case, v=None):
        self.values = v or values()
        registry = PlanRegistry()
        p = register_world_plan_providers(registry)
        climate, terrain = self.values[3:]
        def bound(envelope, handle, deps):
            meta = handle.metadata
            return replace(envelope, dependencies=deps, ref=replace(envelope.ref,
                key=replace(envelope.ref.key, contract_id=meta.id, schema_version=meta.schema_version,
                            algorithm_version=meta.algorithm_version),
                output_fingerprint=output_fingerprint(envelope.payload, deps, envelope.diagnostics, SURFACE_MANIFEST)))
        climate = bound(climate, p.climate_base, ())
        terrain = bound(terrain, p.terrain_base, (PlanDependency(slot="climate_base", ref=climate.ref),))
        self.values[3:] = climate, terrain
        policy = CachePolicy(max_retained_bytes=20_000_000, max_entry_bytes=10_000_000)
        self.backend = MemoryCache(policy)
        self.service = PlanningService(registry, CacheService(self.backend, policy),
            PlanningExecutionPolicy(max_workers=2, max_pending_builds=2))
        case.addCleanup(self.service.shutdown)
        self.binding = register_natural_terrain(registry, climate=p.climate_base, terrain=p.terrain_base)
        self.reader = PlanDependencyReader(registry).with_plan("climate_base", p.climate_base, climate).with_plan(
            "terrain_base", p.terrain_base, terrain)
        self.deps = (PlanDependency(slot="climate_base", ref=climate.ref),
                     PlanDependency(slot="terrain_base", ref=terrain.ref))

    def build(self, source_inputs=None):
        inputs = source_inputs or tuple(self.values[:3])
        m = self.binding.metadata
        scope = self.values[-1].ref.key.scope
        request = PlanRequest[type(inputs)](key=PlanKey(world_uid="world", scope=scope,
            contract_id=m.id, schema_version=m.schema_version, algorithm_version=m.algorithm_version,
            input_fingerprint=self.binding.fingerprint_inputs("world", scope, inputs, self.deps)),
            inputs=inputs, dependencies=self.deps)
        return self.service.get_or_build(self.binding, request, self.reader, wait=Wait())
