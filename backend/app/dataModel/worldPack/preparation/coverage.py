"""Structural chunk outcomes; producer proof belongs to the coverage binding."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.worldPack.preparation.addresses import PackChunkAddress, PackPartAddress


class _PackCoverageRecord(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")


class PackChunkMaterialized(_PackCoverageRecord):
    kind: Literal["materialized"]
    outputs: tuple[PackPartAddress, ...] = Field(min_length=1)


class PackChunkWithoutPayload(_PackCoverageRecord):
    kind: Literal["without_payload"]


PackChunkCoverageResult = Annotated[
    PackChunkMaterialized | PackChunkWithoutPayload,
    Field(discriminator="kind"),
]


class PackChunkCoverageEntry(_PackCoverageRecord):
    address: PackChunkAddress
    result: PackChunkCoverageResult
