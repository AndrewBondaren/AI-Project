from dataclasses import dataclass

from app.application.worldData.generators.coordinates.approachZ import ApproachForm

__all__ = ["ApproachForm", "StreetApproach"]


@dataclass
class StreetApproach:
    """Результат луча порог→улица. DTO only — no stamp / graph methods."""

    ray:       tuple[tuple[int, int], ...]
    length:    int
    z_far:     int
    z_near:    int
    theta_rad: float
    form:      ApproachForm
