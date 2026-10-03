"""Outside access to a room entrance — building generator §3.6."""
from enum import StrEnum


class EntryAccessType(StrEnum):
    AUTO = "auto"
    NONE = "none"
    STEPS = "steps"
    PORCH = "porch"
