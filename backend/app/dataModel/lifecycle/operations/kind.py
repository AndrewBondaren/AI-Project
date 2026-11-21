from enum import StrEnum


class LifecycleOperation(StrEnum):
    CREATE = "create"
    REPLACEMENT = "replacement"
    END = "end"
    REACTIVATE = "reactivate"


# TODO LIFECYCLE-TRANSFORMATION: approve cross-kind identity, evidence and history
# before adding a runtime transformation operation.
