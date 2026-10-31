# TODO(B2/B2-L33): Удалить legacy-модуль целиком после GEN-DAG-1 handoff/B1 и проверки всех usages.
# Замена: app.application.cancellation.typed.snapshotStore.
# Реестр классов/методов: .cursor/plans/dag-typing-1.md, раздел B2.1.

from app.application.cancellation.sessionSnapshot import SessionSnapshot


class SnapshotStore:

    def __init__(self):
        self._snapshots: dict[str, SessionSnapshot] = {}

    def save(self, snapshot: SessionSnapshot) -> None:
        self._snapshots[snapshot.session_id] = snapshot

    def load(self, session_id: str) -> SessionSnapshot | None:
        return self._snapshots.get(session_id)

    def delete(self, session_id: str) -> None:
        self._snapshots.pop(session_id, None)


snapshot_store = SnapshotStore()
