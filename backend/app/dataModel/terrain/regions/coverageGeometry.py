"""Canonical half-open fine-cell row intervals (GEO-1 §6.29-E)."""

from typing import Annotated, Self

from pydantic import Field, model_validator

from app.dataModel.identity.uid import EntityUid
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY
from app.dataModel.terrain.regions.terrainRegionExtent import TerrainRegionModel


class CoverageSpan(TerrainRegionModel, frozen=True):
    y: Annotated[FineY, Field(strict=True)]
    x0: Annotated[FineX, Field(strict=True)]
    x1: Annotated[FineX, Field(strict=True)]

    @model_validator(mode="after")
    def nonempty_interval(self) -> Self:
        if self.x0 >= self.x1:
            raise ValueError("coverage span requires x0 < x1")
        return self


class RegionCoverage(TerrainRegionModel, frozen=True):
    region_uid: EntityUid
    spans: tuple[CoverageSpan, ...]

    @model_validator(mode="after")
    def canonical_intervals(self) -> Self:
        previous: CoverageSpan | None = None
        for span in self.spans:
            if previous is not None and (
                    span.y < previous.y or span.y == previous.y and span.x0 <= previous.x1):
                raise ValueError("coverage spans must be sorted, disjoint and non-adjacent")
            previous = span
        return self
