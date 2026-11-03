"""Spatial dataset descriptors embedded in World Pack manifest V2."""
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef
from app.dataModel.hydrology.pack.profile import FORMAT_VERSION, ROOT_V1


class SpatialDatasetKind(StrEnum):
    HYDROLOGY_OPEN_WATER = "hydrology_open_water"


class SpatialDomainRootRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    domain: SpatialDatasetKind
    root: ArtifactRef

    @model_validator(mode="after")
    def validate_descriptor(self) -> Self:
        if (self.domain is not SpatialDatasetKind.HYDROLOGY_OPEN_WATER
                or self.root.kind is not ArtifactKind.BLOB or self.root.format_key != ROOT_V1.key
                or self.root.format_version != FORMAT_VERSION or not 0 < self.root.nbytes <= ROOT_V1.max_bytes):
            raise ValueError("unsupported spatial root descriptor")
        return self
