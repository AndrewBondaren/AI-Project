"""Common native patch header; payload semantics belong to the producing domain."""

from pydantic import BaseModel, ConfigDict

from app.dataModel.patch.changes.header import PatchHeader


class PatchData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    header: PatchHeader
