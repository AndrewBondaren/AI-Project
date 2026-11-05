from enum import StrEnum
from typing import Self

from pydantic import model_validator

from app.dataModel.fields.checkedPath import CheckedPath, CheckedPathError
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.waterBody import WaterBody
from app.dataModel.identity.uid import EntityUid
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class HydrologyMaterializationCode(StrEnum):
    WATER_KIND_MISMATCH = "WATER_KIND_MISMATCH"


_KIND_PATH = CheckedPath.from_pydantic_loc(WaterBody, ("kind",))
if _KIND_PATH is None:
    raise CheckedPathError("WaterBody.kind must be a checked field")


class WaterKindMismatchIssue(FieldPathError[HydrologyMaterializationCode]):
    source_uid: EntityUid
    authored_kind: BasinKind
    physical_kind: BasinKind

    @model_validator(mode="after")
    def check_mismatch(self) -> Self:
        if self.path != _KIND_PATH or self.authored_kind is self.physical_kind:
            raise ValueError("water kind mismatch requires different kinds at WaterBody.kind")
        return self

    @classmethod
    def retained(cls, source_uid: EntityUid, authored_kind: BasinKind, physical_kind: BasinKind) -> Self:
        return cls(code=HydrologyMaterializationCode.WATER_KIND_MISMATCH, path=_KIND_PATH,
                   message=f"authored kind={authored_kind} retained; physical class={physical_kind}",
                   source_uid=source_uid, authored_kind=authored_kind, physical_kind=physical_kind)
