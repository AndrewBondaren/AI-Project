from dataclasses import dataclass


@dataclass
class DagExecution:
    __table__ = "dag_executions"
    __pk__ = "execution_id"

    execution_id: str
    schema_version: int
    revision: int
    owner_id: str | None
    fence: int
    lease_until: int | None
    status: str
    checkpoint_blob: bytes
    checksum: str
