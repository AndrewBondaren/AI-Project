"""Single declaration of composition fields; not a public request or result."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.validation.immutableValue import validate_immutable
from app.dataModel.worldPack.meta.metadataAttribution import PackStoredAssemblyProvenance
from app.dataModel.worldPack.meta.parts import PackStoredPart
from app.dataModel.worldPack.preparation.assembly import PackAssemblyInput


class _PackCompositionFields(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    parts: tuple[PackStoredPart, ...]
    assembly: PackAssemblyInput
    assembly_provenance: tuple[PackStoredAssemblyProvenance, ...]

    @model_validator(mode="after")
    def immutable_value(self) -> Self:
        validate_immutable(self)
        return self
