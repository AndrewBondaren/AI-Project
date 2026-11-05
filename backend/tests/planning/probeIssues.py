"""Test-only concrete field issue for Planning carrier tests (Planning owns no field error codes)."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class ProbeCode(StrEnum):
    FACT = "fact"
    FALLBACK = "fallback"
    NOTICE = "notice"


class ProbeRoot(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    probe: tuple[str, ...] = ()


class ProbeTypeError(FieldPathError[ProbeCode]):
    pass


_PROBE = FieldRef(lambda: ProbeRoot, lambda pojo: pojo.probe)


def probe_issue(message: str, index: int = 0, code: ProbeCode = ProbeCode.FACT) -> ProbeTypeError:
    path = CheckedPath.root(ProbeRoot).field(_PROBE).item(index).freeze()
    return ProbeTypeError(code=code, path=path, message=message)
