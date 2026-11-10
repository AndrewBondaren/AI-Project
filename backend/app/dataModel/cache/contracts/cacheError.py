"""Serializable diagnostics for public Cache operations."""
import json
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StrictStr, ValidationInfo, field_validator, model_validator

from app.dataModel.fields.validatedFieldPath import ValidatedFieldPath
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class CacheFailureReason(StrEnum):
    CONTRACT_MISMATCH = "contract_mismatch"
    INVALID_PAYLOAD = "invalid_payload"
    BACKEND_FAILURE = "backend_failure"


class CacheOperation(StrEnum):
    GET = "get"
    CREATE = "create"
    UPDATE = "update"
    EVICT = "evict"


class CacheIssueCode(StrEnum):
    UNKNOWN_NAMESPACE = "unknown_namespace"
    SCHEMA_VERSION_MISMATCH = "schema_version_mismatch"
    KEY_OCCUPIED_DIFFERENT_VALUE = "key_occupied_different_value"
    CONTRACT_VIOLATION = "contract_violation"
    INVALID_VALUE = "invalid_value"


class CacheFieldIssue(FieldPathError[CacheIssueCode]):
    @field_validator("path", mode="before")
    @classmethod
    def restore_json_path(cls, value: object, info: ValidationInfo) -> object:
        # The shared wrap validator can otherwise pass JSON arrays to a strict tuple field.
        if info.mode == "json" and isinstance(value, dict):
            return ValidatedFieldPath.model_validate_json(json.dumps(value))
        return value


class CacheContractIssue(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    code: CacheIssueCode
    message: Annotated[StrictStr, Field(min_length=1)]


class CacheError(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    reason: CacheFailureReason
    operation: CacheOperation
    message: Annotated[StrictStr, Field(min_length=1)]
    issues: tuple[CacheFieldIssue | CacheContractIssue, ...] = ()

    @model_validator(mode="after")
    def check_issues(self) -> Self:
        if self.reason is CacheFailureReason.BACKEND_FAILURE and self.issues:
            raise ValueError("backend failure cannot carry input issues")
        for issue in self.issues:
            if (issue.code is CacheIssueCode.INVALID_VALUE) != (self.reason is CacheFailureReason.INVALID_PAYLOAD):
                raise ValueError("issue code does not match cache failure reason")
            if issue.code is CacheIssueCode.KEY_OCCUPIED_DIFFERENT_VALUE:
                if not isinstance(issue, CacheContractIssue) or self.operation not in (CacheOperation.CREATE, CacheOperation.UPDATE):
                    raise ValueError("an occupied-key conflict belongs to a create/update contract")
        return self
