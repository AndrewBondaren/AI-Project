"""Validated dataModel ↔ SQL row boundary; no persistence or transition policy."""

from app.dataModel.regions.regionState import RegionState
from app.db.models.regionState import RegionStateRow


def state_from_row(row: RegionStateRow) -> RegionState:
    wire = {name: getattr(row, name) for name in RegionState.model_fields}
    if row.overrides == {}:
        wire["overrides"] = None
    return RegionState.model_validate(wire)


def state_to_row(state: RegionState, *, world_uid: str, created_at: str,
                 updated_at: str) -> RegionStateRow:
    state = RegionState.model_validate(state)
    wire = state.model_dump(mode="json")
    # SQL's established empty-object representation denotes absent overrides.
    if state.overrides is None:
        wire["overrides"] = {}
    return RegionStateRow(world_uid=world_uid, created_at=created_at,
                          updated_at=updated_at, **wire)
