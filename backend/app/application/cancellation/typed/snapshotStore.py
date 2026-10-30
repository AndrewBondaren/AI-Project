"""Typed memory ownership only; no capture, codec, singleton or domain mapping."""

from typing import Generic, TypeVar, cast

from pydantic import BaseModel, TypeAdapter

from app.application.cancellation.typed.sessionSnapshot import SessionSnapshot
from app.dataModel.engine.dag.identity import ExecutionId, ExecutionIdValue

S = TypeVar("S", bound=BaseModel)


def _admit_snapshot(value: object) -> None:
    if not isinstance(value, SessionSnapshot):
        raise TypeError("SnapshotStore requires a typed SessionSnapshot")
    # This boundary checks the immutable envelope; the service admitted S
    # through its declared SnapshotExtension. No generic erasure escapes it.
    cast(SessionSnapshot[BaseModel], value).__post_init__()


class SnapshotStore(Generic[S]):
    def __init__(self) -> None:
        self._snapshots: dict[ExecutionId, SessionSnapshot[S]] = {}

    def save(self, snapshot: SessionSnapshot[S]) -> None:
        _admit_snapshot(snapshot)
        self._snapshots[snapshot.metadata.execution_id] = snapshot

    def load(self, execution_id: ExecutionId) -> SessionSnapshot[S] | None:
        key = TypeAdapter[ExecutionId](ExecutionIdValue).validate_python(execution_id)
        return self._snapshots.get(key)

    def delete(self, execution_id: ExecutionId) -> None:
        key = TypeAdapter[ExecutionId](ExecutionIdValue).validate_python(execution_id)
        self._snapshots.pop(key, None)
