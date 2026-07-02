"""Root POJO for `worlds.weather_type_registry`.

Builtin table — project_data_storage_tz.md, tz_climate.md § Pick.
``clear`` (priority 99) — engine fallback when no rule matches; future
``weatherResolve`` must take fallback from this registry (``entry_for("clear")``),
not a literal ``"clear"`` in generators/DAG/db.
"""

from __future__ import annotations

from pydantic import RootModel

from app.dataModel.climate.weatherType.weatherTypeEntry import WeatherTypeEntry

_CANONICAL_ENTRIES: tuple[WeatherTypeEntry, ...] = (
    WeatherTypeEntry(
        system_weather="blizzard",
        temp_max=-5,
        rainfall_min=60,
        priority=1,
        travel_modifier=3.0,
        need_modifiers={"warmth": 70},
        glossary_ref="weather_blizzard",
    ),
    WeatherTypeEntry(
        system_weather="snow",
        temp_max=0,
        rainfall_min=20,
        priority=2,
        travel_modifier=2.0,
        need_modifiers={"warmth": 40},
        glossary_ref="weather_snow",
    ),
    WeatherTypeEntry(
        system_weather="fog",
        temp_max=15,
        rainfall_min=70,
        priority=3,
        travel_modifier=1.5,
        glossary_ref="weather_fog",
    ),
    WeatherTypeEntry(
        system_weather="rain",
        temp_max=25,
        rainfall_min=40,
        priority=4,
        travel_modifier=1.3,
        need_modifiers={"warmth": 10},
        glossary_ref="weather_rain",
    ),
    WeatherTypeEntry(
        system_weather="heat_wave",
        temp_min=35,
        priority=5,
        travel_modifier=1.5,
        need_modifiers={"thirst": 40},
        glossary_ref="weather_heat",
    ),
    WeatherTypeEntry(
        system_weather="clear",
        priority=99,  # fallback row — lowest check order; see module docstring
        travel_modifier=1.0,
        glossary_ref="weather_clear",
    ),
)


class WorldWeatherTypeRegistry(RootModel[list[WeatherTypeEntry]]):
    """Root POJO for `worlds.weather_type_registry`. Wire shape: JSON array."""

    root: list[WeatherTypeEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldWeatherTypeRegistry:
        """project_data_storage_tz.md — engine fallback weather table."""
        return cls(list(_CANONICAL_ENTRIES))

    def entry_for(self, system_weather: str) -> WeatherTypeEntry | None:
        for entry in self.root:
            if entry.system_weather == system_weather:
                return entry
        return None

    def sorted_by_priority(self) -> list[WeatherTypeEntry]:
        return sorted(self.root, key=lambda e: e.priority)
