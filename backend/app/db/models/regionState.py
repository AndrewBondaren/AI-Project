"""SQL entity-state row; the dataModel RegionState belongs to wilderness step 9b."""

from dataclasses import dataclass

from app.db.mapper import bool_col, json_col, json_list_col


@dataclass
class RegionStateRow:
    __table__ = "region_states"
    __pk__ = "world_uid"  # Composite PK; only use the repository's scoped API.

    world_uid: str
    region_uid: str
    current_type: str
    created_at: str
    updated_at: str
    pending_target: str | None = None
    progress: float = 0.0
    last_eval_tick: int = 0
    overrides: dict = json_col(default_factory=dict)
    history: list[dict] = json_list_col()
    state_fingerprint: str | None = None
    tombstone: bool = bool_col(default=False)
