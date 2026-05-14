from dataclasses import dataclass
from enum import Enum


class ValidationStatus(str, Enum):
    OK = "ok"
    RETRY = "retry"
    FAIL = "fail"


@dataclass
class ValidationResult:
    status: ValidationStatus
    reason: str | None = None
    dsl_patch: list[str] | None = None

    @property
    def ok(self) -> bool:
        return self.status == ValidationStatus.OK

    @property
    def retryable(self) -> bool:
        return self.status == ValidationStatus.RETRY

    @property
    def failed(self) -> bool:
        return self.status == ValidationStatus.FAIL