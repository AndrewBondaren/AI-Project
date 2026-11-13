"""One public Cache update; missing entries are never implicitly created."""

from dataclasses import dataclass, field

from app.application.cache.service.cacheService import CacheFailure, CacheService
from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.engine.runtime.execution.pythonNodeError import PythonNodeError
from app.dataModel.engine.dag.identity import NodeId
from app.dataModel.engine.nodes.cache.contracts import CacheNodeError
from app.dataModel.engine.nodes.cache.manifestContracts import (
    UpdateManifestCacheEntryInput, UpdateManifestCacheEntryOutput,
)


@dataclass(frozen=True, kw_only=True)
class UpdateCacheEntryNode(PythonNode[UpdateManifestCacheEntryInput, UpdateManifestCacheEntryOutput, CacheNodeError]):
    id: NodeId = NodeId("update_cache_entry")
    skip_on_replan: bool = False
    cache: CacheService = field(repr=False, compare=False)

    async def prepare_input(self, view: DAGReadView) -> UpdateManifestCacheEntryInput:
        raise RuntimeError("update_cache_entry requires explicit invocation input")

    async def execute(self, input: UpdateManifestCacheEntryInput) -> UpdateManifestCacheEntryOutput:
        try:
            result = self.cache.update(input.request)
        except CacheFailure as exc:
            raise PythonNodeError(CacheNodeError(error=exc.error)) from exc
        return UpdateManifestCacheEntryOutput(kind=input.kind, value=result)


def make_update_cache_entry_node(cache: CacheService) -> UpdateCacheEntryNode:
    return UpdateCacheEntryNode(cache=cache)
