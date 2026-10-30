"""Publication lifecycle categories, independent of apply outcomes and revisions."""

from enum import StrEnum


class OperationKind(StrEnum):
    SNAPSHOT_APPLY = "snapshot_apply"
    PACK_ACTIVATION = "pack_activation"
    GAMEPLAY_START = "gameplay_start"


class OperationPhase(StrEnum):
    PREPARING = "preparing"
    READY = "ready"
    APPLYING = "applying"
    TERMINAL = "terminal"
    RECOVERY_REQUIRED = "recovery_required"


class OperationClaimKind(StrEnum):
    OWNER = "owner"
    TERMINAL = "terminal"
    BUSY = "busy"
