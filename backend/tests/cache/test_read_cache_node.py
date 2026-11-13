import unittest
from unittest.mock import patch

from app.application.cache.backends.memoryCache import MemoryCache
from app.application.cache.contracts.cacheBackend import CacheBinding
from app.application.cache.contracts.manifestBytesCodec import ManifestBytesCodec
from app.application.cache.service.cacheBindingRegistry import CacheBindingRegistry
from app.application.cache.service.cacheService import CacheService
from app.application.engine.nodes.cache.readCacheEntryNode import make_read_cache_entry_node
from app.application.engine.nodes.cache.registration import READ_MANIFEST_CACHE_ENTRY_CONTRACT, register_manifest_cache_nodes
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.context.dagContext import DAGContext
from app.application.engine.runtime.dag.dagExecutor import DAGExecutor
from app.application.engine.runtime.graphs.graphCompiler import GraphCompiler
from app.application.engine.runtime.execution.nodeRunner import NodeRunner
from app.application.engine.runtime.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.runtime.invocations.invocationCoordinator import InvocationCoordinator
from app.application.engine.runtime.invocations.memoryExecutionStore import MemoryExecutionStore
from app.application.engine.runtime.validation.contractValidator import ContractValidator
from app.application.engine.runtime.validation.nodeValidator import NodeValidator
from app.dataModel.cache.contracts.cacheContract import CacheContract
from app.dataModel.cache.contracts.cacheEntry import CacheEntry
from app.dataModel.cache.contracts.cacheError import CacheFailureReason, CacheOperation
from app.dataModel.cache.contracts.cacheLookup import CacheHit, CacheMiss
from app.dataModel.cache.identity.cacheKey import CacheKey
from app.dataModel.cache.policy.cachePolicy import CachePolicy
from app.dataModel.engine.dag.identity import ExecutionId, PlanRevision
from app.dataModel.engine.dag.nodeStatus import NodeStatus
from app.dataModel.engine.dag.invocations.record import InvocationStatus
from app.dataModel.engine.nodes.cache.contracts import CacheNodeError
from app.dataModel.engine.nodes.cache.manifestContracts import ReadManifestCacheEntryInput, ReadManifestCacheEntryOutput
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.fields.validatedFieldPath import ModelIdentity
from app.dataModel.worldPack.meta.manifestCacheContract import MANIFEST_BYTES_CONTRACT
from tests.dag_typing.fixtures import GraphBindings, GraphRuleState


class ReadCacheNodeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.backend = MemoryCache(CachePolicy(max_entry_bytes=16000, max_retained_bytes=32000))
        self.cache = CacheService(self.backend, CacheBindingRegistry((CacheBinding(MANIFEST_BYTES_CONTRACT, ManifestBytesCodec()),)))
        self.key = CacheKey[bytes](contract=MANIFEST_BYTES_CONTRACT, item_key=bytes([255]) * 32)
        self.entry = CacheEntry[bytes](key=self.key, value=bytes(range(256)))
        self.request = ReadManifestCacheEntryInput(key=self.key)
        self.node = make_read_cache_entry_node(self.cache)
        self.registry = NodeRegistry()
        self.assertEqual(self.registry.ids(), ())
        register_manifest_cache_nodes(self.registry)
        self.contract = READ_MANIFEST_CACHE_ENTRY_CONTRACT
        self.registration = self.registry.get(self.node.id, self.contract)
        self.runner = NodeRunner(ContractValidator(), NodeValidator())

    async def run_request(self, request):
        catalog = DAGContext(ExecutionId("cache-test"), self.registry)
        identity = catalog.begin_attempt(self.node.id, PlanRevision("1"))
        return await self.runner.run(self.node, catalog.read_view(self.node.id), identity,
                                     self.registration, PythonNodeExecutor(), explicit_input=request)

    async def test_miss_is_success_without_build_or_write(self):
        with patch.object(self.cache, "get", wraps=self.cache.get) as read, patch.object(self.cache, "create") as create:
            outcome = await self.run_request(self.request)
        self.assertEqual(outcome.status, NodeStatus.SUCCESS)
        self.assertIsInstance(outcome.output.lookup, CacheMiss)
        self.assertEqual(outcome.output.key, self.key)
        read.assert_called_once_with(self.key)
        create.assert_not_called()

    async def test_hit_binary_invocation_round_trip_and_fresh_read_after_evict(self):
        self.cache.create(self.entry)
        wire = InvocationCoordinator.encode(self.request, self.contract.input_type)
        outcome = await self.run_request(self.contract.input_type.model_validate_json(wire))
        self.assertEqual(outcome.status, NodeStatus.SUCCESS)
        self.assertIsInstance(outcome.output.lookup, CacheHit)
        self.assertEqual(outcome.output.lookup.entry.value, self.entry.value)
        self.assertEqual(outcome.output.lookup.entry.key, outcome.output.key)
        output_wire = InvocationCoordinator.encode(outcome.output, self.contract.output_type)
        self.cache.evict(self.key)
        with patch.object(self.cache, "get", wraps=self.cache.get) as read:
            restored = self.contract.output_type.model_validate_json(output_wire)
            read.assert_not_called()
        self.assertEqual(restored.lookup.entry.value, self.entry.value)
        self.assertIsInstance((await self.run_request(self.request)).output.lookup, CacheMiss)

    async def test_domain_error_is_declared_and_round_trips_with_field_path(self):
        key = CacheKey[bytes](contract=CacheContract[bytes](id="unknown", schema_version=1), item_key=self.key.item_key)
        with patch.object(self.backend, "get", wraps=self.backend.get) as read:
            outcome = await self.run_request(ReadManifestCacheEntryInput(key=key))
        read.assert_not_called()
        self.assertEqual(outcome.status, NodeStatus.FAILED)
        self.assertIsNone(outcome.output)
        self.assertIsInstance(outcome.error, CacheNodeError)
        self.assertEqual(outcome.error.error.operation, CacheOperation.GET)
        self.assertEqual(outcome.error.error.reason, CacheFailureReason.CONTRACT_MISMATCH)
        wire = InvocationCoordinator.encode(outcome.error, CacheNodeError)
        self.assertEqual(CacheNodeError.model_validate_json(wire), outcome.error)
        self.assertEqual(outcome.error.error.issues[0].path.projection(), ("id",))

    async def test_engine_invocation_checkpoint_replay_does_not_repeat_lookup(self):
        bindings = GraphBindings()
        bindings.nodes[self.node.id] = self.node
        from app.application.engine.nodes.cache.createCacheEntryNode import make_create_cache_entry_node
        create = make_create_cache_entry_node(self.cache)
        bindings.nodes[create.id] = create
        from app.application.engine.nodes.cache.updateCacheEntryNode import make_update_cache_entry_node
        update = make_update_cache_entry_node(self.cache)
        bindings.nodes[update.id] = update
        compiler = GraphCompiler(self.registry, bindings, compile_rules=lambda _: (), evaluate_rules=lambda *_: True)
        compiler.precompile()
        plan = compiler.compile(GraphRuleState(), invocation_root=self.node.id)
        executor = DAGExecutor(self.runner, {PythonNodeExecutor: PythonNodeExecutor()})
        store = MemoryExecutionStore()
        self.cache.create(self.entry)
        with patch.object(self.cache, "get", wraps=self.cache.get) as read:
            first = await executor.run_invocation(plan, ExecutionId("cache-replay"), self.node.id, PlanRevision("1"),
                                                  store, owner="test", workers=1, invocation_limit=1, input=self.request)
            self.cache.evict(self.key)
            replay = await executor.run_invocation(plan, ExecutionId("cache-replay"), self.node.id, PlanRevision("1"),
                                                   store, owner="test", workers=1, invocation_limit=1, input=self.request)
        read.assert_called_once_with(self.key)
        self.assertEqual(first.status, InvocationStatus.SUCCEEDED)
        self.assertEqual(replay.terminal_payload(), first.terminal_payload())
        output = self.contract.output_type.model_validate_json(replay.terminal_payload())
        self.assertEqual(output.lookup.entry.value, self.entry.value)

    async def test_backend_failure_never_becomes_miss(self):
        with patch.object(self.backend, "get", side_effect=OSError("backend unavailable")):
            outcome = await self.run_request(self.request)
        self.assertEqual(outcome.status, NodeStatus.FAILED)
        self.assertEqual(outcome.error.error.reason, CacheFailureReason.BACKEND_FAILURE)
        self.assertIsNone(outcome.output)

    async def test_forged_nested_input_is_rejected_before_cache(self):
        key = CacheKey[bytes].model_construct(contract=MANIFEST_BYTES_CONTRACT, item_key=b"short")
        request = ReadManifestCacheEntryInput.model_construct(key=key)
        with patch.object(self.cache, "get", wraps=self.cache.get) as read:
            outcome = await self.run_request(request)
        read.assert_not_called()
        self.assertEqual(outcome.status, NodeStatus.FAILED)
        self.assertIsNone(outcome.output)

    async def test_missing_explicit_input_fails_before_cache(self):
        with patch.object(self.cache, "get", wraps=self.cache.get) as read:
            outcome = await self.run_request(None)
        read.assert_not_called()
        self.assertEqual(outcome.status, NodeStatus.FAILED)
        self.assertIsNone(outcome.output)

    async def test_wrong_key_from_backend_is_not_published(self):
        other = CacheKey[bytes](contract=MANIFEST_BYTES_CONTRACT, item_key=bytes(32))
        hit = CacheHit[bytes](entry=CacheEntry[bytes](key=other, value=b"wrong"))
        with patch.object(self.backend, "get", return_value=hit):
            outcome = await self.run_request(self.request)
        self.assertEqual(outcome.status, NodeStatus.FAILED)
        self.assertEqual(outcome.error.error.reason, CacheFailureReason.CONTRACT_MISMATCH)

    def test_concrete_identity_and_owner_field_paths(self):
        for model in (ReadManifestCacheEntryInput, ReadManifestCacheEntryOutput, CacheNodeError):
            self.assertEqual(ModelIdentity.of(model).qualname, model.__name__)
        path = CheckedPath.root(ReadManifestCacheEntryInput).field(
            FieldRef(lambda: ReadManifestCacheEntryInput, lambda value: value.key)).freeze()
        self.assertEqual(path.projection(), ("key",))
        # Nested domain diagnostics retain CacheContractMetadata ownership;
        # the node does not manufacture paths inside CacheKey[T].
        self.assertEqual(self.contract.calls, ())
        self.assertEqual(self.contract.reads, ())
        self.assertIsNone(self.contract.lifecycle)
        self.assertFalse(self.node.skip_on_replan)
        self.assertIn(self.node.id, self.registry.ids())
