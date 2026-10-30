"""Prepare-on-demand lifecycle over the shared dependency queue and spatial checker."""

from collections.abc import Callable
from enum import Enum

from app.application.worldData.placement.constraints import check_candidate
from app.application.worldData.placement.dependencies import DependencyQueue
from app.application.worldData.placement.diagnostics import diagnostic
from app.application.worldData.placement.geometry import PlacementGeometry
from app.application.worldData.placement.lifecycle.outcomes import admission_outcome, causes, dependency_outcome
from app.dataModel.placement.batch import PlacementBatchV2
from app.dataModel.placement.intent import PlacementIdentity
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.lifecycle.causal import PlacementOutcomeRef, PlacementOutcomeStatus
from app.dataModel.placement.lifecycle.header import PlacementHeader
from app.dataModel.placement.prepared import PreparedPlacementV2
from app.dataModel.placement.result import (
    DisabledPlacement, PlacementBatchResultV2, PlacementDiagnostic, PlacementIssueCode, PlacementOutcomeV2,
    ResolvedPlacementV2, UnresolvedPlacementV2,
)
from app.dataModel.policy.policyDecision import ObjectAdmissionDecision
from app.dataModel.policy.policyEnums import PolicyState

type SupportReevaluation = Callable[[PlacementHeader, tuple[PlacementOutcomeRef, ...]], ObjectAdmissionDecision[Enum, Enum]]


class PlacementSession:
    def __init__(self, batch: PlacementBatchV2, reevaluate_support: SupportReevaluation | None) -> None:
        self.batch = PlacementBatchV2.model_validate(batch, strict=True)
        self.geometry = PlacementGeometry(batch.topology)
        self.objects = {o.header.identity.region_uid: o for o in batch.objects}
        self.placed = {o.identity.region_uid: o for o in batch.accepted}
        if any(self.geometry.canonical_cells(o.footprint) is None for o in batch.accepted):
            raise ValueError("accepted placement lies outside topology")
        self.queue = DependencyQueue(self.objects, set(self.placed), deferred_preparation=True)
        self._reevaluate_support = reevaluate_support
        self.offered: set[str] = set()
        self.support_versions: dict[str, tuple[PlacementOutcomeRef, ...]] = {}
        initial = {uid: terminal for uid, obj in self.objects.items()
                   if (terminal := admission_outcome(obj)) is not None}
        self.queue.settle(initial)
        self._settle_dependencies()

    @classmethod
    def start(cls, batch: PlacementBatchV2, *, reevaluate_support: SupportReevaluation | None = None) -> "PlacementSession":
        """The caller binds the callback to the same frozen spec/sources/revision."""
        return cls(batch, reevaluate_support)

    def _outcome(self, uid: str) -> PlacementOutcomeV2:
        outcome = self.queue.outcomes.get(uid) or self.placed.get(uid)
        if not isinstance(outcome, (ResolvedPlacementV2, UnresolvedPlacementV2, DisabledPlacement)):
            raise ValueError("session requires a terminal V2 outcome")
        return outcome

    def _supports(self, uid: str) -> tuple[PlacementOutcomeV2, ...]:
        return tuple(self._outcome(target) for target in sorted(self.queue.targets[uid])
                     if target in self.queue.outcomes or target in self.placed)

    def _settle_dependencies(self) -> None:
        while True:
            terminals: dict[str, PlacementOutcomeV2] = {}
            for uid in sorted(self.queue.pending):
                obj = self.objects[uid]
                missing = tuple(sorted(self.queue.targets[uid] - self.objects.keys() - self.placed.keys()))
                supports = self._supports(uid)
                # Wait for every possible cause: a later failed support outranks disable.
                if not missing and self.queue.waiting[uid]:
                    continue
                terminal = dependency_outcome(obj, supports, missing=missing)
                if terminal is None and obj.decision.state is PolicyState.WAITING_SUPPORT:
                    if self._reevaluate_support is None:
                        continue
                    refs = causes(supports)
                    if self.support_versions.get(uid) == refs:
                        continue
                    decision = self._reevaluate_support(obj.header, refs)
                    if not isinstance(decision, ObjectAdmissionDecision):
                        raise ValueError("SUPPORT reevaluation requires object admission")
                    type(decision).model_validate(decision, strict=True)
                    self.support_versions[uid] = refs
                    if decision.effective_priority != obj.decision.effective_priority:
                        raise ValueError("SUPPORT reevaluation cannot change resolved priority")
                    if any(p not in decision.provenance for p in obj.decision.provenance):
                        raise ValueError("SUPPORT reevaluation must retain provenance")
                    if any(r not in decision.reasons for r in obj.decision.reasons):
                        raise ValueError("SUPPORT reevaluation must retain resolved reasons")
                    obj = PlacementAdmissionInput(header=obj.header, decision=decision)
                    self.objects[uid] = obj
                    terminal = admission_outcome(obj)
                if terminal is not None:
                    terminals[uid] = terminal
            if not terminals:
                break
            self.queue.settle(terminals)

    def ready_for_preparation(self) -> tuple[PlacementHeader, ...]:
        self._settle_dependencies()
        ready = tuple(self.objects[uid].header for uid in sorted(self.queue.pending)
            if not self.queue.waiting[uid] and self.objects[uid].decision.state is PolicyState.READY
            and uid not in self.queue.prepared)
        self.offered.update(h.identity.region_uid for h in ready)
        return ready

    def run(self, prepare_ready: Callable[[tuple[PlacementHeader, ...]], None], *,
            check_cancelled: Callable[[], None] | None = None) -> PlacementBatchResultV2:
        """Drain whole ready portions through the caller's existing submit/fail API."""
        if self.offered:
            raise ValueError("run requires no outstanding manual preparation offers")
        while True:
            if check_cancelled is not None:
                check_cancelled()
            ready = self.ready_for_preparation()
            if ready:
                prepare_ready(ready)
                if self.offered:
                    raise ValueError("prepare_ready must submit or fail the entire offered portion")
                continue
            if self.step() is None:
                return self.finish()

    def submit(self, prepared: PreparedPlacementV2) -> None:
        prepared = PreparedPlacementV2.model_validate(prepared, strict=True)
        uid = prepared.intent.identity.region_uid
        if uid not in self.offered or uid not in self.queue.pending:
            raise ValueError("submit requires an offered ready header")
        obj = self.objects[uid]
        if PlacementHeader.from_intent(prepared.intent) != obj.header or prepared.decision != obj.decision:
            raise ValueError("prepared placement must match its admission header/decision")
        self.queue.submit(prepared)
        self.offered.discard(uid)

    def step(self) -> PlacementOutcomeV2 | None:
        if self.ready_for_preparation():
            raise ValueError("submit or fail the entire ready portion before advancing heap")
        uid = self.queue.next_ready()
        if uid is None:
            return None
        prepared = self.queue.prepared[uid]
        failures: list[PlacementDiagnostic] = []
        outcome: PlacementOutcomeV2 | None = None
        for candidate in sorted(prepared.candidates, key=lambda c: (c.preference, c.candidate_uid)):
            issues = check_candidate(prepared, candidate, self.placed, self.geometry)
            if not issues:
                resolved = ResolvedPlacementV2(prepared=prepared, candidate_uid=candidate.candidate_uid)
                self.placed[uid] = resolved
                outcome = resolved
                break
            failures.extend(issues)
        if outcome is None:
            if not failures:
                failures.append(diagnostic(prepared, PlacementIssueCode.NO_CANDIDATES,
                                           "no prepared candidates", path=("candidates",)))
            outcome = UnresolvedPlacementV2(identity=prepared.intent.identity, prepared=prepared,
                                             diagnostics=tuple(failures), causes=causes(self._supports(uid)))
        self.queue.settle({uid: outcome})
        self._settle_dependencies()
        return outcome

    def fail(self, identity: PlacementIdentity, diagnostics: tuple[PlacementDiagnostic, ...]) -> UnresolvedPlacementV2:
        uid = identity.region_uid
        if uid not in self.queue.pending or self.objects[uid].header.identity != identity:
            raise ValueError("failure must identify a pending session member")
        outcome = UnresolvedPlacementV2(identity=identity, prepared=self.queue.prepared.get(uid),
            diagnostics=diagnostics, causes=causes(self._supports(uid)))
        self.queue.settle({uid: outcome})
        self.offered.discard(uid)
        self._settle_dependencies()
        return outcome

    def _cycle_failure(self, uid: str, component: tuple[str, ...]) -> PlacementOutcomeV2:
        obj = self.objects[uid]
        return UnresolvedPlacementV2(identity=obj.header.identity, prepared=None,
            diagnostics=(diagnostic(obj.header, PlacementIssueCode.DEPENDENCY_CYCLE,
                "cyclic dependency component", path=("dependencies",), related=component),),
            causes=tuple(PlacementOutcomeRef(region_uid=target, status=PlacementOutcomeStatus.UNRESOLVED)
                         for target in sorted(self.queue.targets[uid] & set(component))))

    def finish(self) -> PlacementBatchResultV2:
        self._settle_dependencies()
        while self.queue.pending:
            ready = tuple(uid for uid in sorted(self.queue.pending) if not self.queue.waiting[uid])
            if ready:
                for uid in ready:
                    obj = self.objects[uid]
                    self.fail(obj.header.identity, (diagnostic(obj.header, PlacementIssueCode.NO_CANDIDATES,
                        "placement was not completed before finish", path=("lifecycle",)),))
            else:
                self.queue.fail_cycles(self._cycle_failure)
                self._settle_dependencies()
        results: list[PlacementOutcomeV2] = []
        for uid in sorted(self.objects):
            outcome = self._outcome(uid)
            if not isinstance(outcome, ResolvedPlacementV2) and (outcome.causes or any(
                    d.code in (PlacementIssueCode.MISSING_DEPENDENCY, PlacementIssueCode.FAILED_DEPENDENCY,
                               PlacementIssueCode.DEPENDENCY_CYCLE) for d in outcome.diagnostics)):
                missing = tuple(sorted(self.queue.targets[uid] - self.objects.keys() - self.placed.keys()))
                outcome = type(outcome).model_validate(outcome.model_copy(update={
                    "causes": causes(self._supports(uid), missing)}), strict=True)
            results.append(outcome)
        diagnostics = tuple(sorted((d for o in results if not isinstance(o, ResolvedPlacementV2)
                                    for d in o.diagnostics), key=lambda d: (d.region_uid, d.code.value, d.related_uids)))
        return PlacementBatchResultV2(world_uid=self.batch.world_uid, snapshot_uid=self.batch.snapshot_uid,
            snapshot_revision=self.batch.snapshot_revision, results=tuple(results), diagnostics=diagnostics)
