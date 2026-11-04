import hashlib
import json
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from app.dataModel.identity.uid import EntityUid
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex


class BakeKind(StrEnum):
    LIGHT = "LIGHT"
    FULL = "FULL"
    DETAILED = "DETAILED"


class BakeRequest(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    version: Literal[1] = 1
    world_uid: EntityUid
    kind: BakeKind
    scope: tuple[EntityUid, ...]
    source_revision: EntityUid
    preparation_contract_version: EntityUid
    parameters_fingerprint: RevisionHex

    @field_validator("version", mode="before")
    @classmethod
    def require_integer_version(cls, value: object) -> int:
        if type(value) is not int:
            raise ValueError("version must be an integer")
        return value

    def canonical(self) -> bytes:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False,
                          separators=(",", ":")).encode()

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical()).hexdigest()
