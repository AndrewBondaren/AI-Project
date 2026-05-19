from dataclasses import dataclass
from enum import Enum
from typing import Optional


class NodeErrorSeverity(str, Enum):
    RETRY = "retry"
    FAIL = "fail"
    USER_ERROR = "user_error"


@dataclass
class NodeValidationError:

    code: str
    message: str
    severity: NodeErrorSeverity
    field: Optional[str] = None