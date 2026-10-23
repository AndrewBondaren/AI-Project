from app.application.worldData.generators.climate.climateAnchor import ClimateAnchorPoint
from app.application.worldData.generators.climate.climateGeneratorService import ClimateGeneratorService
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.application.worldData.generators.climate.anchorDetect import TerrainFeaturePoint
from app.application.worldData.generators.climate.climateAnchor import AnchorSource
from app.application.jsonValidation import climate_scalars
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.application.worldData.generators.climate.planning.climatePlanSampler import ClimatePlanSampler
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan
from app.dataModel.spatial.grid.coordinateTypes import GridX, GridY
from app.dataModel.registryKey import RegistryKey
from app.dataModel.climate.climateZone.worldClimateZoneRegistry import WorldClimateZoneRegistry


def auto_anchors_from_features(
    features: list[TerrainFeaturePoint],
    world: World,
    uid_map: dict[str, NamedLocation],
    pole_field: ClimatePoleField,
    climate: ClimateGeneratorService | None = None,
) -> list[ClimateAnchorPoint]:
    """
    Auto Voronoi centers inherit climate from pole field at feature point.
    No Earth elevation→arctic mapping.
    """
    svc     = climate or ClimateGeneratorService()
    default = climate_scalars(world).default_climate_zone
    points: list[ClimateAnchorPoint] = []

    for feature in features:
        sample = svc.sample_at_pole_field(world, pole_field, feature.gx, feature.gy)
        zone = sample.system_climate_zone or default
        points.append(ClimateAnchorPoint(
            gx=GridX(feature.gx),
            gy=GridY(feature.gy),
            system_climate_zone=RegistryKey[WorldClimateZoneRegistry](zone),
            location_uid=None,
            source=AnchorSource.AUTO,
        ))
    return points


def resolved_auto_anchors(features: list[TerrainFeaturePoint], base: ClimateBasePlan) -> tuple[ClimateAnchorPoint, ...]:
    """Assign frozen pole zones with the same sampler used by the legacy field."""
    return tuple(ClimateAnchorPoint(gx=GridX(point.gx), gy=GridY(point.gy),
        system_climate_zone=ClimatePlanSampler.sample(base, GridX(point.gx), GridY(point.gy)).system_climate_zone,
        location_uid=None, source=AnchorSource.AUTO) for point in features)
