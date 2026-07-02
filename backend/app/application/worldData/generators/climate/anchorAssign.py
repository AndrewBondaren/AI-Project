from app.application.worldData.generators.climate.climateAnchor import ClimateAnchorPoint
from app.application.worldData.generators.climate.climateGeneratorService import ClimateGeneratorService
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.application.worldData.generators.climate.anchorDetect import TerrainFeaturePoint
from app.application.worldData.generators.climate.climateAnchor import AnchorSource
from app.application.jsonValidation import climate_scalars
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


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
            gx=feature.gx,
            gy=feature.gy,
            system_climate_zone=zone,
            location_uid=None,
            source=AnchorSource.AUTO,
        ))
    return points
