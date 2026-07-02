from dataclasses import dataclass

from app.application.jsonValidation import climate_scalars
from app.db.models.world import World


@dataclass(frozen=True)
class WeatherSnapshot:
    """Runtime weather — output of resolve_weather (see tz_climate.md § runtime)."""

    season:                str | None
    temperature_base:      int
    effective_temperature: int
    rainfall:              int
    system_weather:        str | None = None
    intensity:             int = 0   # 0 until tick loop; contract reserved


class ClimateRuntimeAssembler:
    """
    Season + weather overlay — does not rewrite map_cells.temperature_base.
    Future DAG nodes call these methods; no engine code here.
    """

    def resolve_effective_temperature(
        self,
        world: World,
        temperature_base: int,
        season: str | None = None,
    ) -> int:
        if not season:
            return temperature_base
        offsets = climate_scalars(world).season_temp_offsets
        if offsets is None:
            return temperature_base
        value = getattr(offsets, season, None)
        return temperature_base + int(value if value is not None else 0)

    def resolve_weather(
        self,
        world: World,
        temperature_base: int,
        rainfall: int,
        season: str | None = None,
    ) -> WeatherSnapshot:
        effective = self.resolve_effective_temperature(world, temperature_base, season)
        return WeatherSnapshot(
            season=season,
            temperature_base=temperature_base,
            effective_temperature=effective,
            rainfall=rainfall,
            system_weather=None,
        )
