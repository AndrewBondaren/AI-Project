"""One public Cache create operation with the owning admission outcome."""

from dataclasses import dataclass, field

from app.application.cache.service.cacheService import CacheFailure, CacheService
from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.engine.runtime.execution.pythonNodeError import PythonNodeError
from app.dataModel.engine.dag.identity import NodeId
from app.dataModel.engine.nodes.cache.contracts import CacheNodeError
from app.dataModel.engine.nodes.cache.manifestContracts import (
    CreateManifestCacheEntryInput, CreateManifestCacheEntryOutput,
)


@dataclass(frozen=True, kw_only=True)
class CreateCacheEntryNode(PythonNode[CreateManifestCacheEntryInput, CreateManifestCacheEntryOutput, CacheNodeError]):
    id: NodeId = NodeId("create_cache_entry")
    skip_on_replan: bool = False
    cache: CacheService = field(repr=False, compare=False)

    async def prepare_input(self, view: DAGReadView) -> CreateManifestCacheEntryInput:
        raise RuntimeError("create_cache_entry requires explicit invocation input")

    async def execute(self, input: CreateManifestCacheEntryInput) -> CreateManifestCacheEntryOutput:
        try:
            result = self.cache.create(input.request)
        except CacheFailure as exc:
            raise PythonNodeError(CacheNodeError(error=exc.error)) from exc
        return CreateManifestCacheEntryOutput(kind=input.kind, value=result)


def make_create_cache_entry_node(cache: CacheService) -> CreateCacheEntryNode:
    return CreateCacheEntryNode(cache=cache)
