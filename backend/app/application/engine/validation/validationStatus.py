from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ValidationStatus(str, Enum):
    OK = "ok"
    RETRY = "retry"
    FAIL = "fail"


@dataclass
class ValidationResult:
    status: ValidationStatus
    errors: list["NodeValidationError"] = field(default_factory=list)
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

    @property
    def reason(self) -> str | None:
        """Обратная совместимость — первый code из errors."""
        if self.errors:
            return self.errors[0].code
        return None