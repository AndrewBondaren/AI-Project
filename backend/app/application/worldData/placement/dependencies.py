"""Deterministic ready queue and iterative dependency components; no spatial policy."""

from collections import deque
from collections.abc import Callable, Mapping
import heapq

from app.application.worldData.placement.diagnostics import diagnostic
from app.dataModel.placement import (
    PlacementIssueCode, PlacementOutcome, PreparedPlacement, UnresolvedPlacement,
)
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.prepared import PreparedPlacementV2
from app.dataModel.placement.result import DisabledPlacement, PlacementOutcomeV2, ResolvedPlacementV2, UnresolvedPlacementV2


def cyclic_components(graph: Mapping[str, set[str]]) -> list[tuple[str, ...]]:
    """Iterative Kosaraju: cycles are distinguished from downstream blocked nodes."""
    finished, seen = [], set()
    for root in sorted(graph):
        if root in seen:
            continue
        seen.add(root)
        stack = [(root, iter(sorted(graph[root])))]
        while stack:
            uid, children = stack[-1]
            target = next(children, None)
            if target is None:
                finished.append(uid)
                stack.pop()
            elif target not in seen:
                seen.add(target)
                stack.append((target, iter(sorted(graph[target]))))
    reverse = {uid: set() for uid in graph}
    for uid, targets in graph.items():
        for target in targets:
            reverse[target].add(uid)
    seen.clear()
    components = []
    for root in reversed(finished):
        if root in seen:
            continue
        component, stack = set(), [root]
        seen.add(root)
        while stack:
            uid = stack.pop()
            component.add(uid)
            for child in sorted(reverse[uid], reverse=True):
                if child not in seen:
                    seen.add(child)
                    stack.append(child)
        if len(component) > 1 or root in graph[root]:
            components.append(tuple(sorted(component)))
    return sorted(components)


class DependencyQueue:
    def __init__(self, objects: Mapping[str, PreparedPlacement | PlacementAdmissionInput], accepted_uids: set[str], *,
                 deferred_preparation: bool = False) -> None:
        self.objects = objects
        self.deferred_preparation = deferred_preparation
        if any(isinstance(o, PlacementAdmissionInput) != deferred_preparation for o in objects.values()):
            raise ValueError("dependency queue requires one input generation")
        self.prepared: dict[str, PreparedPlacementV2] = {}
        self.pending = set(objects)
        self.outcomes: dict[str, PlacementOutcome | PlacementOutcomeV2] = {}
        self.targets = {uid: {rule.target_uid for rule in
            (obj.header.dependencies if isinstance(obj, PlacementAdmissionInput) else obj.intent.dependencies)}
            for uid, obj in objects.items()}
        self.waiting = {uid: targets - accepted_uids for uid, targets in self.targets.items()}
        self.dependents = {uid: set() for uid in objects}
        for uid, targets in self.targets.items():
            for target in targets & objects.keys():
                self.dependents[target].add(uid)
        self._ready = []
        for uid in sorted(objects):
            if not self.waiting[uid]:
                self._enqueue(uid)

    def _enqueue(self, uid: str) -> None:
        obj = self.objects[uid]
        if isinstance(obj, PlacementAdmissionInput):
            prepared = self.prepared.get(uid)
            if prepared is not None:
                heapq.heappush(self._ready, (-prepared.effective_specificity, -prepared.original_area, uid))
            return
        if obj.effective_specificity is not None:
            heapq.heappush(self._ready, (-obj.effective_specificity, -obj.original_area, uid))

    def submit(self, prepared: PreparedPlacementV2) -> None:
        uid = prepared.intent.identity.region_uid
        if not self.deferred_preparation or uid not in self.pending or self.waiting[uid] or uid in self.prepared:
            raise ValueError("placement is not awaiting preparation")
        self.prepared[uid] = prepared
        self._enqueue(uid)

    def next_ready(self) -> str | None:
        while self._ready:
            _, _, uid = heapq.heappop(self._ready)
            if uid in self.pending:
                return uid
        return None

    def _record(self, uid: str, outcome: PlacementOutcome | PlacementOutcomeV2) -> None:
        self.pending.remove(uid)
        self.outcomes[uid] = outcome
        for child in sorted(self.dependents[uid] & self.pending):
            self.waiting[child].discard(uid)
            if not self.waiting[child]:
                self._enqueue(child)

    def settle(self, outcomes: Mapping[str, PlacementOutcome | PlacementOutcomeV2]) -> None:
        if any(isinstance(o, (DisabledPlacement, ResolvedPlacementV2, UnresolvedPlacementV2))
               != self.deferred_preparation for o in outcomes.values()):
            raise ValueError("queue outcomes must match its input generation")
        failures = deque()
        # Publish all roots first; a failed cycle member must retain its cycle reason.
        for uid in sorted(outcomes):
            self._record(uid, outcomes[uid])
            if isinstance(outcomes[uid], UnresolvedPlacement):
                failures.append(uid)
        if self.deferred_preparation:
            return
        while failures:
            uid = failures.popleft()
            for child in sorted(self.dependents[uid] & self.pending):
                failed = tuple(sorted(target for target in self.targets[child]
                                      if isinstance(self.outcomes.get(target), UnresolvedPlacement)))
                obj = self.objects[child]
                if not isinstance(obj, PreparedPlacement):
                    raise ValueError("legacy failure propagation requires prepared input")
                issue = diagnostic(obj, PlacementIssueCode.FAILED_DEPENDENCY,
                                   "required placement dependency is unresolved", path=("dependencies",), related=failed)
                self._record(child, UnresolvedPlacement(prepared=obj, diagnostics=(issue,)))
                failures.append(child)

    def fail_cycles(self, make_failure: Callable[[str, tuple[str, ...]], PlacementOutcomeV2] | None = None) -> None:
        graph = {uid: self.targets[uid] & self.pending for uid in self.pending}
        outcomes = {}
        for component in cyclic_components(graph):
            for uid in component:
                if make_failure is not None:
                    outcomes[uid] = make_failure(uid, component)
                    continue
                obj = self.objects[uid]
                if not isinstance(obj, PreparedPlacement):
                    raise ValueError("deferred queue requires cycle failure factory")
                issue = diagnostic(obj, PlacementIssueCode.DEPENDENCY_CYCLE,
                                   "cyclic dependency component", path=("dependencies",), related=component)
                outcomes[uid] = UnresolvedPlacement(prepared=obj, diagnostics=(issue,))
        if not outcomes:
            raise RuntimeError("placement queue blocked without missing, failed or cyclic dependencies")
        self.settle(outcomes)
