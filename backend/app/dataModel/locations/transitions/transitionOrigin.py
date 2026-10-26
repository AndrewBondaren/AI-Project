"""Creation source, independent of transition type and storage projection."""

from enum import StrEnum


class TransitionOrigin(StrEnum):
    AUTHORED = "authored"
    GENERATED = "generated"
    RUNTIME = "runtime"
