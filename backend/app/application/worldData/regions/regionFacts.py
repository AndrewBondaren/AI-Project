"""Typed facts; absent observations stay unknown rather than becoming defaults."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ClimateFacts:
    rainfall_mean: float | None = None
    temperature: float | None = None
    drought_trend: float | None = None

    @property
    def rainfall(self) -> float | None:
        """Canonical eligibility channel ``climate.rainfall``."""
        return self.rainfall_mean


@dataclass(frozen=True)
class HydroFacts:
    water_table: float | None = None
    flooding: float | None = None
    open_water_fraction: float | None = None


@dataclass(frozen=True)
class ReliefFacts:
    elevation_plain: bool | None = None
    elevation_mean: float | None = None
    lowland_fraction: float | None = None


@dataclass(frozen=True)
class DeclarationFacts:
    present: bool = False
    strength: float = 0.0


@dataclass(frozen=True)
class RegionFacts:
    climate: ClimateFacts | None = None
    hydrology: HydroFacts | None = None
    relief: ReliefFacts | None = None
    # Канал flora.* ожидает flora-трек, tz_flora FL3b; consumer не зарегистрирован.
    flora: None = None
    declaration: DeclarationFacts | None = None
    # Переработать при появлении домена времени/LOD; callers pass ticks explicitly.
    elapsed_ticks: int = 0

    def value_for(self, fact: str) -> float | bool | None:
        """Only public numeric fields on typed domains are eligibility channels."""
        if fact == "elapsed_ticks":
            return self.elapsed_ticks
        domain, separator, field = fact.partition(".")
        if not separator or domain not in ("climate", "hydrology", "relief", "flora", "declaration"):
            return None
        if field.startswith("_"):
            return None
        value = getattr(getattr(self, domain), field, None)
        return value if isinstance(value, (float, int, bool)) else None
