import logging
from random import Random

from app.application.worldData.generators.masterData import economic_tier_rows
from app.application.worldData.generators.utils.economicTierBands import materialize_band
from app.application.worldData.generators.utils.tierRegistry import median_system_tier
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)


def _loc_ref(loc: NamedLocation | None) -> str | None:
    if loc is None:
        return None
    return getattr(loc, "location_uid", None) or getattr(loc, "system_name", None)


class TierResolver:
    """
    Resolves effective system_economic_tier by cascading from most specific to most general.

    Order (explicit tier):
      room_tier → template_tier → building → district → city

    If all null, band cascade (requires world + rng):
      building_band → district_band → city_band → materialize_band

    If still null and world given:
      median_system_tier + WARNING

    See docs/tz_economic_tier.md §4–§5.
    """

    @staticmethod
    def resolve(
        world:         World | None = None,
        city:          NamedLocation | None = None,
        district:      NamedLocation | None = None,
        building:      NamedLocation | None = None,
        room_tier:     str | None = None,
        template_tier: str | None = None,
        building_tier: str | None = None,
        *,
        city_band:     str | None = None,
        district_band: str | None = None,
        building_band: str | None = None,
        rng:           Random | None = None,
    ) -> str | None:
        building_from_loc = building.system_economic_tier if building else None
        district_from_loc = district.system_economic_tier if district else None
        city_from_loc     = city.system_economic_tier if city else None

        logger.debug(
            "TierResolver.resolve | inputs"
            " room_tier=%r template_tier=%r building_tier=%r"
            " building.system_economic_tier=%r district.system_economic_tier=%r city.system_economic_tier=%r"
            " building_band=%r district_band=%r city_band=%r"
            " world=%s rng=%s"
            " building=%r district=%r city=%r",
            room_tier,
            template_tier,
            building_tier,
            building_from_loc,
            district_from_loc,
            city_from_loc,
            building_band,
            district_band,
            city_band,
            world.world_uid if world else None,
            rng is not None,
            _loc_ref(building),
            _loc_ref(district),
            _loc_ref(city),
        )

        if room_tier:
            logger.debug(
                "TierResolver.resolve | applied=%r source=room_tier",
                room_tier,
            )
            return room_tier
        if template_tier:
            logger.debug(
                "TierResolver.resolve | applied=%r source=template_tier",
                template_tier,
            )
            return template_tier
        if building_from_loc:
            logger.debug(
                "TierResolver.resolve | applied=%r source=building.system_economic_tier building=%r",
                building_from_loc,
                _loc_ref(building),
            )
            return building_from_loc
        if building_tier:
            logger.debug(
                "TierResolver.resolve | applied=%r source=building_tier",
                building_tier,
            )
            return building_tier
        if district_from_loc:
            logger.debug(
                "TierResolver.resolve | applied=%r source=district.system_economic_tier district=%r",
                district_from_loc,
                _loc_ref(district),
            )
            return district_from_loc
        if city_from_loc:
            logger.debug(
                "TierResolver.resolve | applied=%r source=city.system_economic_tier city=%r",
                city_from_loc,
                _loc_ref(city),
            )
            return city_from_loc

        if world is not None and rng is not None:
            anchor = city_from_loc
            for source, band in (
                ("building_band", building_band),
                ("district_band", district_band),
                ("city_band", city_band),
            ):
                if not band:
                    continue
                picked = materialize_band(world, band, rng, anchor_tier=anchor)
                if picked:
                    logger.debug(
                        "TierResolver.resolve | applied=%r source=materialize_band(%s)"
                        " band=%r anchor=%r world=%r",
                        picked,
                        source,
                        band,
                        anchor,
                        world.world_uid,
                    )
                    return picked
                logger.debug(
                    "TierResolver.resolve | materialize_band(%s) returned None"
                    " band=%r anchor=%r world=%r",
                    source,
                    band,
                    anchor,
                    world.world_uid,
                )

        if world is not None:
            median = median_system_tier(economic_tier_rows(world))
            if median:
                logger.warning(
                    "TierResolver: no economic tier in cascade; using median %r",
                    median,
                )
                logger.debug(
                    "TierResolver.resolve | applied=%r source=median_system_tier world=%r",
                    median,
                    world.world_uid,
                )
                return median

        logger.debug("TierResolver.resolve | applied=None source=none")
        return None

    @staticmethod
    def band_from_template(template: dict | None) -> str | None:
        "economic_tier_band from city / district / building template JSON."
        if not template:
            return None
        band = template.get("economic_tier_band")
        if band is not None:
            logger.debug(
                "TierResolver.band_from_template | template=%r band=%r",
                template.get("system_name") or template.get("system_type"),
                band,
            )
        return band
