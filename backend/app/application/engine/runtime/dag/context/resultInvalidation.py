"""Pure invalidation over execution evidence; no catalog or payload ownership."""

from collections.abc import Collection, Mapping

from app.dataModel.engine.dag.identity import DomainRevision, ExecutionIdentity, NodeId
from app.dataModel.engine.dag.records import DependencyRead, DomainReadEvidence


class ResultInvalidation:
    @staticmethod
    def affected(
        current: Mapping[NodeId, ExecutionIdentity],
        reads: Mapping[NodeId, tuple[DependencyRead, ...]],
        removed: Collection[NodeId] = (),
    ) -> frozenset[NodeId]:
        available = dict(current)
        invalidated = set(current).intersection(removed)
        for node_id in invalidated:
            available.pop(node_id)
        while True:
            stale = {
                node_id for node_id in available
                if any(read.result != available.get(read.producer) for read in reads.get(node_id, ()))
            }
            if not stale:
                return frozenset(invalidated)
            invalidated.update(stale)
            for node_id in stale:
                available.pop(node_id)

    @staticmethod
    def unconfirmed_domains(
        reads: Mapping[NodeId, tuple[DomainReadEvidence, ...]],
        confirmed_revisions: Mapping[str, DomainRevision],
    ) -> frozenset[NodeId]:
        return frozenset(
            node_id for node_id, evidence in reads.items()
            if any(read.revision is None or confirmed_revisions.get(read.domain) != read.revision for read in evidence)
        )
