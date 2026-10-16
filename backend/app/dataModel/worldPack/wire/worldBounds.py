"""Declared world extent AABB — grid / macro-tile index space.

Wire: ``world.world_bounds`` JSON ``{x_min,x_max,y_min,y_max}``.
See docs/tz_terrain_generation.md § Охват мира / Форма мира.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from app.dataModel.spatial.facing import CARDINAL_FACINGS, CARDINAL_WALL_OUTWARD_DELTA, Facing


class WorldBounds(BaseModel):
    """Axis-aligned world extent (inclusive). Square = special case W==H.

Neighbor lookup (no bake literals): ``contains``, ``grid_neighbor``,
``antagonist_tile``, ``wrap_owner_and_other``, ``facing_to_antagonist``.
"""

    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-BOUNDS"

    model_config = ConfigDict(extra="ignore", frozen=True)

    x_min: int
    x_max: int
    y_min: int
    y_max: int

    @model_validator(mode="after")
    def _ordered(self) -> WorldBounds:
        if self.x_min > self.x_max or self.y_min > self.y_max:
            raise ValueError("world_bounds requires x_min<=x_max and y_min<=y_max")
        return self

    @classmethod
    def try_parse(cls, raw: object) -> WorldBounds | None:
        """Parse DB/JSON blob; invalid or incomplete → None."""
        if not isinstance(raw, dict):
            return None
        try:
            return cls.model_validate(raw)
        except (ValidationError, TypeError, ValueError):
            return None

    def contains(self, gx: int, gy: int) -> bool:
        return self.x_min <= gx <= self.x_max and self.y_min <= gy <= self.y_max

    def grid_neighbor(
        self, gx: int, gy: int, facing: Facing,
    ) -> tuple[int, int] | None:
        """AABB-adjacent tile; ``None`` at the bound (no wrap)."""
        dx, dy = CARDINAL_WALL_OUTWARD_DELTA[facing]
        nx, ny = gx + dx, gy + dy
        if self.contains(nx, ny):
            return nx, ny
        return None

    def antagonist_tile(
        self, gx: int, gy: int, facing: Facing,
    ) -> tuple[int, int] | None:
        """AABB wrap partner when this tile has no in-bounds neighbor on ``facing``.

        min x ↔ max x (same y); min y ↔ max y (same x). Not magma antipode.
        """
        if not self.contains(gx, gy):
            return None
        if self.grid_neighbor(gx, gy, facing) is not None:
            return None
        if facing is Facing.EAST and gx == self.x_max:
            return self.x_min, gy
        if facing is Facing.WEST and gx == self.x_min:
            return self.x_max, gy
        if facing is Facing.NORTH and gy == self.y_max:
            return gx, self.y_min
        if facing is Facing.SOUTH and gy == self.y_min:
            return gx, self.y_max
        return None

    def wrap_owner_and_other(
        self, gx: int, gy: int, facing: Facing,
    ) -> tuple[tuple[int, int], tuple[int, int]] | None:
        """Canonical wrap pair: owner = min ``(gx, gy)``, then antagonist.

        ``None`` when there is no wrap, or the antagonist is this same tile
        (1-wide / 1-tall AABB).
        """
        ant = self.antagonist_tile(gx, gy, facing)
        if ant is None or ant == (gx, gy):
            return None
        owner = min((gx, gy), ant)
        other = max((gx, gy), ant)
        return owner, other

    def facing_to_antagonist(
        self,
        owner: tuple[int, int],
        other: tuple[int, int],
    ) -> Facing | None:
        """Outward ``Facing`` from owner whose wrap partner is ``other``."""
        ogx, ogy = owner
        for facing in CARDINAL_FACINGS:
            if self.antagonist_tile(ogx, ogy, facing) == other:
                return facing
        return None
