"""Pure hysteresis, shared by whole-region and spatial child evaluations."""

from math import isfinite

from app.application.worldData.regions.coverageResolver import TargetCoverage
from app.application.worldData.regions.regionFacts import DeclarationFacts
from app.application.worldData.regions.stateChange.history import append_transition
from app.dataModel.regions.regionState import RegionState, RegionTransitionCause
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrainMasks.landcoverRegionsCategoryPolicy import LandcoverRegionsCategoryPolicy


def advance(state: RegionState, target: TargetCoverage | None, *,
            registry: WorldTerrainRegistry, policy: LandcoverRegionsCategoryPolicy,
            elapsed_ticks: int, declaration: DeclarationFacts | None,
            cause: RegionTransitionCause, at: str | int) -> RegionState:
    # Переработать при появлении домена времени/LOD: no clock or implicit elapsed.
    if type(elapsed_ticks) is not int or elapsed_ticks < 0:
        raise ValueError("elapsed_ticks must be a nonnegative integer")
    if state.tombstone:
        return state
    entry = registry.entry_for(state.current_type)
    if entry is None:
        raise ValueError(f"unknown current terrain key: {state.current_type}")
    weight = declaration.strength if declaration and declaration.present else 0.0
    if not isfinite(weight) or weight < 0:
        raise ValueError("declaration strength must be finite and nonnegative")
    updated = {"last_eval_tick": state.last_eval_tick + elapsed_ticks}
    if target is not None:
        if registry.entry_for(target.target_key) is None:
            raise ValueError(f"unknown target terrain key: {target.target_key}")
        if not isfinite(target.strength) or not 0 <= target.strength <= 1:
            raise ValueError("target strength must be finite and in 0..1")
        delta = target.strength * elapsed_ticks / (entry.inertia + weight)
        if target.target_key == state.current_type:
            progress = max(0.0, state.progress - delta)
            updated.update(progress=progress,
                           pending_target=state.pending_target if progress else None)
        else:
            progress = (state.progress if state.pending_target == target.target_key else 0.0) + delta
            if progress >= policy.transition_threshold:
                transitioned = append_transition(state, target.target_key, cause=cause, at=at)
                return RegionState.model_validate({**transitioned.model_dump(), **updated})
            updated.update(progress=progress, pending_target=target.target_key)
    return RegionState.model_validate({**state.model_dump(), **updated})
