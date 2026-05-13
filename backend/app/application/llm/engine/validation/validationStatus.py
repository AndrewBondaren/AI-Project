from dataclasses import dataclass
from enum import Enum

class ValidationStatus:
    OK = "ok"
    RETRY = "retry"
    FAIL = "fail"


@dataclass
class ValidationResult:
    status: str
    reason: str | None = None
    dsl_patch: list[str] | None = None