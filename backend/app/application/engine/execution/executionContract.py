from dataclasses import dataclass
from typing import Type, Optional


@dataclass
class ExecutionContract:

    # ------------------------
    # EXECUTION
    # ------------------------
    executor_type: str  # "llm", "python", "structured_llm"
    timeout_seconds: Optional[int] = None

    # ------------------------
    # RELIABILITY
    # ------------------------
    supports_repair: bool = True
    deterministic: bool = False

    # ------------------------
    # OUTPUT
    # ------------------------
    output_schema: Optional[Type] = None
    required_fields: list[str] = None

    # ------------------------
    # META (future)
    # ------------------------
    version: str = "v1"