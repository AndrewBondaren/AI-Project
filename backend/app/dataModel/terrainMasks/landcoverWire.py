"""Read-only legacy aliases: output has one default_landcover source."""

from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrainMasks.landcoverRegionsCategoryPolicy import LandcoverRegionsCategoryPolicy
from pydantic import BaseModel


def landcover_patch_to_wire(value):
    """Keep supplied fields when collection validation returns typed overrides."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_unset=True)
    if isinstance(value, dict):
        return {key: landcover_patch_to_wire(item) for key, item in value.items()}
    if isinstance(value, list):
        return [landcover_patch_to_wire(item) for item in value]
    return value


def normalize_landcover_wire(value, *, partial: bool = False):
    if not isinstance(value, dict):
        return value
    aliases = {
        "default_forests": WorldTerrainRegistry.forest_terrain_key(),
        "default_plains": WorldTerrainRegistry.plains_terrain_key(),
    }
    if not any(key in value for key in aliases):
        return value
    result = dict(value)
    explicit = result.get("default_landcover", {})
    if not isinstance(explicit, dict):
        return result  # Let the typed field report invalid authored input.
    policy = {} if partial else LandcoverRegionsCategoryPolicy.canonical_defaults().model_dump(mode="json")
    policy.update(explicit)
    authored_overrides = policy.get("terrain_policies", {})
    if not isinstance(authored_overrides, dict):
        return result
    overrides = dict(authored_overrides)
    for alias, source in aliases.items():
        if alias not in result:
            continue
        raw = result.pop(alias)
        if not isinstance(raw, dict):
            raise ValueError(f"{alias} must be an object")
        converted = dict(raw)
        if "forest_min_rainfall" in converted:
            if converted["forest_min_rainfall"] is None:
                raise ValueError(f"{alias}.forest_min_rainfall must be numeric")
            converted["min_rainfall"] = converted.pop("forest_min_rainfall")
        converted.setdefault("system_terrain", source)
        newer = overrides.get(source, {})
        if not isinstance(newer, dict):
            return result
        overrides[source] = {**converted, **newer}
        if alias == "default_plains" and "fallback_terrain" not in explicit:
            policy["fallback_terrain"] = converted["system_terrain"]
    policy["terrain_policies"] = overrides
    result["default_landcover"] = policy
    return result
