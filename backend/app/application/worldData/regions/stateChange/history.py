"""Append-only transitions; event/time domains will replace the caller's marker."""

from app.dataModel.regions.regionState import RegionState, RegionStateTransition, RegionTransitionCause
from app.dataModel.terrain.worldTerrainRegistry import TerrainKey


def append_transition(state: RegionState, target: TerrainKey, *,
                      cause: RegionTransitionCause, at: str | int) -> RegionState:
    # Переработать при появлении домена времени/событий: at is supplied explicitly.
    transition = RegionStateTransition(from_type=state.current_type, to_type=target,
                                       cause=cause, at=at)
    return RegionState.model_validate({**state.model_dump(), "current_type": target,
                                      "pending_target": None, "progress": 0,
                                      "history": (*state.history, transition)})
