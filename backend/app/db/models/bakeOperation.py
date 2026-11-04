from dataclasses import dataclass, field

from app.dataModel.world.bakeOperation.record import BakeError, BakeResult, BakeStatus, DeliveryStatus, PublicationOperationId
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
    result: BakeResult | None = field(metadata={
        "col": "result_blob", "to_db": BakeResult.encode, "from_db": BakeResult.model_validate_json,
    })
    error: BakeError | None = field(metadata={
        "to_db": BakeError.encode, "from_db": BakeError.decode,
    })
    publication_operation_id: PublicationOperationId | None = field(metadata={
        "to_db": PublicationOperationId.encode, "from_db": PublicationOperationId,
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
