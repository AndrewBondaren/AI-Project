"""Single state writer; external owners trigger evaluation and consume signals.

Callers serialize evaluation per world/region in their UOW. No sweep, read-time
evaluation, worldEdit wiring or background clock is installed here (10c / LOD).
"""

from dataclasses import dataclass

from app.application.worldData.regions.coverageResolver import resolve
from app.application.worldData.regions.factConsumers import collect_facts
from app.application.worldData.regions.factConsumers.context import FactConsumerContext
from app.application.worldData.regions.regionStateLog import log_evaluation, log_transition
from app.application.worldData.regions.regionStateMapping import state_from_row, state_to_row
from app.application.worldData.regions.stateChange.contracts import ChildRegion, RegionEvaluation
from app.application.worldData.regions.stateChange.history import append_transition
from app.application.worldData.regions.stateChange.morphEffects import MaterializeSignal, signal_for
from app.application.worldData.regions.stateChange.progress import advance
from app.dataModel.regions.regionState import RegionState, RegionTransitionCause
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrain.terrainRegistryEntry import TerrainRegistryEntry
from app.dataModel.terrainMasks.landcoverRegionsCategoryPolicy import LandcoverRegionsCategoryPolicy
from app.db.repositories.iRegionStateRepository import IRegionStateRepository
from app.ids import state_fingerprint
from app.ids.deterministicIds import entity_uid
from app.ids.uidKind import UidKind


def child_uid(world_uid: str, parent_region_uid: str, seed_xy: tuple[int, int]) -> str:
    return entity_uid(world_uid, UidKind.REGION, parent_region_uid=parent_region_uid,
                      seed_xy=seed_xy)


@dataclass(frozen=True)
class EvaluationResult:
    state: RegionState
    children: tuple[ChildRegion, ...] = ()
    materialize: tuple[MaterializeSignal, ...] = ()


class StateChangeConsumer:
    def __init__(self, repo: IRegionStateRepository, *, registry: WorldTerrainRegistry,
                 policy: LandcoverRegionsCategoryPolicy) -> None:
        self._repo, self._registry, self._policy = repo, registry, policy

    async def evaluate(self, world_uid: str, request: RegionEvaluation) -> EvaluationResult:
        """Evaluate one complete region scope; never infer removal from its absence.

        Spatial requests evaluate each supplied cluster with the same scorer and
        hysteresis; the parent keeps its type outside those child footprints.
        The external owner retains/reconstructs these scopes for refine, rather
        than persisting a second copy of resolved Specs in the entity store.
        """
        if type(request.elapsed_ticks) is not int or request.elapsed_ticks < 0:
            raise ValueError("elapsed_ticks must be a nonnegative integer")
        self._require_key(request.entry_type)
        seeds = [part.seed_xy for part in request.spatial]
        if len(set(seeds)) != len(seeds):
            raise ValueError("duplicate spatial cluster seed")
        uids = [request.region_uid, *(child_uid(world_uid, request.region_uid, seed) for seed in seeds)]
        rows = {row.region_uid: row for row in await self._repo.get_many(world_uid, uids)}
        previous = state_from_row(rows[request.region_uid]) if request.region_uid in rows else None
        if previous is not None and previous.tombstone:
            return EvaluationResult(previous)
        state = previous or RegionState(region_uid=request.region_uid, current_type=request.entry_type,
                                        spec_fingerprint=request.spec_fingerprint)
        changed = previous is not None and state.spec_fingerprint != request.spec_fingerprint
        reset_revision = changed and request.declaration and request.declaration.present
        if reset_revision:
            if request.previous_entry_type is None:
                raise ValueError("declared revision requires previous_entry_type")
            self._require_key(request.previous_entry_type)
            if request.previous_entry_type != request.entry_type:
                state = append_transition(state, request.entry_type,
                                          cause=RegionTransitionCause.DECLARED_EDIT, at=request.at)
            state = RegionState.model_validate({**state.model_dump(), "pending_target": None,
                                               "progress": 0})
        state = RegionState.model_validate({**state.model_dump(),
                                           "spec_fingerprint": request.spec_fingerprint,
                                           "overrides": request.overrides or state.overrides})
        # A revision reset is observable as reset, without immediately spending elapsed time.
        if not reset_revision and not request.spatial:
            state = self._advance(state, request, request.context)
        else:
            state = RegionState.model_validate({**state.model_dump(),
                "last_eval_tick": state.last_eval_tick + request.elapsed_ticks})
        children, signals = [], []
        signal = signal_for(spec=request.spec, previous=previous, state=state,
                            target=self._require_key(state.current_type))
        if signal:
            signals.append(signal)
        writes = [(state, request.region_uid)]
        for part in sorted(request.spatial, key=lambda item: item.seed_xy):
            uid = child_uid(world_uid, request.region_uid, part.seed_xy)
            old = state_from_row(rows[uid]) if uid in rows else None
            if old is not None and old.tombstone:
                continue
            # Derived child specificity is not a new authored revision on replay.
            fingerprint = state_fingerprint({**part.spec.model_dump(mode="json"),
                "placement_specificity": request.spec.placement_specificity})
            child = old or RegionState(region_uid=uid, current_type=state.current_type,
                                       spec_fingerprint=fingerprint)
            if old is not None and (changed or old.spec_fingerprint != fingerprint):
                if reset_revision and request.previous_entry_type != request.entry_type:
                    child = append_transition(child, request.entry_type,
                        cause=RegionTransitionCause.DECLARED_EDIT, at=request.at)
                child = RegionState.model_validate({**child.model_dump(), "pending_target": None,
                    "progress": 0, "spec_fingerprint": fingerprint,
                    "last_eval_tick": child.last_eval_tick + request.elapsed_ticks})
            else:
                child = self._advance(child, request, part.context)
            parent_entry, child_entry = self._require_key(state.current_type), self._require_key(child.current_type)
            specificity = request.spec.placement_specificity
            if parent_entry.merge_rank == child_entry.merge_rank:
                specificity = specificity + 1 if specificity is not None else 0
            spec = part.spec.model_copy(update={"placement_specificity": specificity})
            children.append(ChildRegion(region_uid=uid, parent_region_uid=state.region_uid,
                seed_xy=part.seed_xy, entry_type=request.entry_type, spec=spec, state=child))
            writes.append((child, uid))
            signal = signal_for(spec=spec, previous=old, state=child, target=child_entry,
                                parent_region_uid=state.region_uid)
            if signal:
                signals.append(signal)
        # One repository batch (internally bulkSql), including parent and children.
        await self._repo.upsert_bulk([state_to_row(item, world_uid=world_uid,
            created_at=rows[uid].created_at if uid in rows else request.updated_at,
            updated_at=request.updated_at) for item, uid in writes])
        for item, uid in writes:
            log_evaluation(world_uid, item, request.region_uid if uid != request.region_uid else None)
            before = state_from_row(rows[uid]) if uid in rows else None
            prefix = len(before.history) if before else 0
            for transition in item.history[prefix:]:
                log_transition(world_uid, uid, transition)
        return EvaluationResult(state, tuple(children), tuple(signals))

    def _advance(self, state: RegionState, request: RegionEvaluation,
                 context: FactConsumerContext) -> RegionState:
        facts = collect_facts(context, declaration=request.declaration,
                              elapsed_ticks=request.elapsed_ticks)
        return advance(state, resolve(facts, self._registry), registry=self._registry,
                       policy=self._policy, elapsed_ticks=request.elapsed_ticks,
                       declaration=facts.declaration, cause=request.cause, at=request.at)

    def _require_key(self, key: str) -> TerrainRegistryEntry:
        entry = self._registry.entry_for(key)
        if entry is None:
            raise ValueError(f"unknown terrain key: {key}")
        return entry

    async def tombstone(self, world_uid: str, region_uid: str, *, updated_at: str) -> int:
        """Explicit removal/orphan decision by the owner; no automatic resurrection."""
        return await self._repo.mark_tombstone(world_uid, region_uid, updated_at=updated_at)
