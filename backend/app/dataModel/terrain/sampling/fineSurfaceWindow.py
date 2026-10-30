"""One complete fine height window; provenance belongs to its PlanEnvelope."""

from itertools import zip_longest
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.spatial.grid.coordinateTypes import FineXY, FineZ
from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage
from app.dataModel.topology.worldTopology import Coord, WorldTopology


class FineSurfaceWindow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    coverage: RegionCoverage
    surface_z: tuple[tuple[FineXY, Annotated[FineZ, Field(strict=True)]], ...]
    topology: WorldTopology
    protected_cells: frozenset[Coord]

    @model_validator(mode="after")
    def complete_surface(self) -> Self:
        expected = ((x, row.y) for row in self.coverage.spans for x in range(row.x0, row.x1))
        actual = (cell for cell, _ in self.surface_z)
        sentinel = object()
        if any(a != b for a, b in zip_longest(actual, expected, fillvalue=sentinel)):
            raise ValueError("fine surface must cover exactly its canonical row-major coverage")
        cells = frozenset(cell for cell, _ in self.surface_z)
        if not self.protected_cells <= cells or any(self.topology.canonicalize(*cell) != cell for cell in cells):
            raise ValueError("fine surface and protection require the same canonical frame/coverage")
        return self
