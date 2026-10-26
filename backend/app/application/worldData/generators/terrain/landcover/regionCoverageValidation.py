"""World-aware terrain references via the existing REF-W policy and diagnostics."""
from pydantic import TypeAdapter, ValidationError

from app.application.jsonValidation.index.worldRegistryIndex import WorldRegistryIndex
from app.application.jsonValidation.resolve import ResolveContext, reject_unresolved
from app.application.jsonValidation.sourceValidation import validate_reference_value
from app.application.jsonValidation.types import FieldPathError
from app.application.worldData.generators.terrain.landcover.types import ResolvedRegion
from app.dataModel.terrain.worldTerrainRegistry import TerrainKey, WorldTerrainRegistry

_REGION = TypeAdapter(ResolvedRegion)


def validate_region_coverage(region: ResolvedRegion, registry: WorldTerrainRegistry,
                             *, ctx: ResolveContext) -> ResolvedRegion:
    # Recheck even constructed/copied instances before accepting caller data.
    try:
        region = _REGION.validate_python(region)
    except ValidationError as exc:
        reject_unresolved(ctx, [FieldPathError(ctx.path_prefix + tuple(e["loc"]),
                                              e["msg"], code=e["type"]) for e in exc.errors()])
    references = WorldRegistryIndex(registry_vocabularies={
        WorldTerrainRegistry: frozenset(e.system_terrain for e in registry.root),
    })
    # The caller already resolved this world's registry. No second world read or fallback.
    validate_reference_value(None, TerrainKey, region.entry_type, ctx, ctx.path_prefix + ("entry_type",), references)
    validate_reference_value(None, TerrainKey, region.current_type, ctx, ctx.path_prefix + ("current_type",), references)
    return region
