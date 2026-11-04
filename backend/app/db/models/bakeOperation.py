from dataclasses import dataclass, field
from operator import attrgetter

from app.dataModel.world.bakeOperation.record import BakeStatus, DeliveryStatus, PublicationOperationId
from app.dataModel.world.bakeOperation.request import BakeKind


@dataclass
class BakeOperation:
    __table__ = "bake_operations"
    __pk__ = "operation_id"

    operation_id: str
    world_uid: str
    kind: BakeKind
    fingerprint: str
    request_version: int
    request_blob: bytes
    status: BakeStatus
    owner_id: str
    fence: int
    lease_until: float
    result_blob: str | None
    error: str | None
    publication_operation_id: PublicationOperationId | None = field(metadata={
        "to_db": attrgetter("value"), "from_db": PublicationOperationId,
    })

    def __post_init__(self) -> None:
        self.kind = BakeKind(self.kind)
        self.status = BakeStatus(self.status)


@dataclass
class BakeWorldClaim:
    __table__ = "bake_world_claims"
    __pk__ = "world_uid"

    world_uid: str
    operation_id: str


@dataclass
class BakeWaiter:
    __table__ = "bake_waiters"
    __pk__ = ("operation_id", "execution_id", "invocation_id", "step_index")

    operation_id: str
    execution_id: str
    invocation_id: str
    step_index: int
    delivery_status: DeliveryStatus

    def __post_init__(self) -> None:
        self.delivery_status = DeliveryStatus(self.delivery_status)
