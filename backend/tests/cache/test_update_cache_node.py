import unittest
from unittest.mock import patch

from app.application.cache.backends.memoryCache import MemoryCache
from app.application.cache.contracts.cacheBackend import CacheBinding
from app.application.cache.contracts.manifestBytesCodec import ManifestBytesCodec
from app.application.cache.service.cacheBindingRegistry import CacheBindingRegistry
from app.application.cache.service.cacheService import CacheService
from app.application.engine.nodes.cache.createCacheEntryNode import make_create_cache_entry_node
from app.application.engine.nodes.cache.evictCacheEntryNode import make_evict_cache_entry_node
from app.application.engine.nodes.cache.readCacheEntryNode import make_read_cache_entry_node
from app.application.engine.nodes.cache.updateCacheEntryNode import make_update_cache_entry_node
from app.application.engine.nodes.cache.registration import UPDATE_MANIFEST_CACHE_ENTRY_CONTRACT, register_manifest_cache_nodes
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.context.dagContext import DAGContext
from app.application.engine.runtime.dag.dagExecutor import DAGExecutor
from app.application.engine.runtime.execution.nodeRunner import NodeRunner
from app.application.engine.runtime.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.runtime.graphs.graphCompiler import GraphCompiler
from app.application.engine.runtime.invocations.invocationCoordinator import InvocationCoordinator
from app.application.engine.runtime.invocations.memoryExecutionStore import MemoryExecutionStore
from app.application.engine.runtime.validation.contractValidator import ContractValidator
from app.application.engine.runtime.validation.nodeValidator import NodeValidator
from app.dataModel.cache.contracts.cacheEntry import CacheEntry
from app.dataModel.cache.contracts.cacheError import CacheFailureReason, CacheIssueCode, CacheOperation
from app.dataModel.cache.contracts.cacheLookup import CacheMiss
from app.dataModel.cache.contracts.cacheUpdateResult import CacheUpdateOutcome
from app.dataModel.cache.identity.cacheKey import CacheKey
from app.dataModel.cache.policy.cachePolicy import CachePolicy
from app.dataModel.engine.dag.identity import ExecutionId, PlanRevision
from app.dataModel.engine.dag.invocations.record import InvocationStatus
from app.dataModel.engine.dag.nodeStatus import NodeStatus
from app.dataModel.engine.nodes.cache.contracts import CacheNodeError
from app.dataModel.engine.nodes.cache.manifestContracts import UpdateManifestCacheEntryInput, UpdateManifestCacheEntryOutput
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.fields.validatedFieldPath import ModelIdentity
from app.dataModel.worldPack.meta.manifestCacheContract import MANIFEST_BYTES_CONTRACT
from tests.dag_typing.fixtures import GraphBindings, GraphRuleState


class UpdateCacheNodeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.backend = MemoryCache(CachePolicy(max_entry_bytes=16000, max_retained_bytes=32000))
        self.cache = CacheService(self.backend, CacheBindingRegistry((CacheBinding(MANIFEST_BYTES_CONTRACT, ManifestBytesCodec()),)))
        self.key = CacheKey[bytes](contract=MANIFEST_BYTES_CONTRACT, item_key=bytes([255]) * 32)
        self.entry = CacheEntry[bytes](key=self.key, value=bytes(range(256)))
        self.request = UpdateManifestCacheEntryInput(kind="update", request=self.entry)
        self.node = make_update_cache_entry_node(self.cache)
        self.registry = NodeRegistry()
        register_manifest_cache_nodes(self.registry)
        self.contract = UPDATE_MANIFEST_CACHE_ENTRY_CONTRACT
        self.registration = self.registry.get(self.node.id, self.contract)
        self.runner = NodeRunner(ContractValidator(), NodeValidator())

    async def run_request(self, request):
        catalog = DAGContext(ExecutionId("update-test"), self.registry)
        identity = catalog.begin_attempt(self.node.id, PlanRevision("1"))
        return await self.runner.run(self.node, catalog.read_view(self.node.id), identity,
                                     self.registration, PythonNodeExecutor(), explicit_input=request)

    async def test_missing_does_not_create(self):
        with patch.object(self.cache, "update", wraps=self.cache.update) as update, patch.object(self.cache, "create") as create:
            outcome = await self.run_request(self.request)
        update.assert_called_once_with(self.entry)
        create.assert_not_called()
        self.assertEqual(outcome.status, NodeStatus.SUCCESS)
        self.assertEqual(outcome.output.kind, "update")
        self.assertEqual(outcome.output.value.outcome, CacheUpdateOutcome.NOT_FOUND)
        self.assertIsInstance(self.cache.get(self.key), CacheMiss)

    async def test_equal_value_is_unchanged_and_binary_contract_round_trips(self):
        self.cache.create(self.entry)
        wire = InvocationCoordinator.encode(self.request, self.contract.input_type)
        outcome = await self.run_request(self.contract.input_type.model_validate_json(wire))
        self.assertEqual(outcome.status, NodeStatus.SUCCESS)
        self.assertEqual(outcome.output.value.outcome, CacheUpdateOutcome.UNCHANGED)
        self.assertEqual(self.cache.get(self.key).entry.value, self.entry.value)
        output_wire = InvocationCoordinator.encode(outcome.output, self.contract.output_type)
        self.assertEqual(self.contract.output_type.model_validate_json(output_wire), outcome.output)

    async def test_conflict_never_overwrites_and_preserves_domain_error(self):
        self.cache.create(self.entry)
        request = UpdateManifestCacheEntryInput(kind="update", request=CacheEntry[bytes](key=self.key, value=b"different"))
        with patch.object(self.cache, "create") as create:
            outcome = await self.run_request(request)
        create.assert_not_called()
        self.assertEqual(outcome.status, NodeStatus.FAILED)
        self.assertIsNone(outcome.output)
        self.assertEqual(outcome.error.error.operation, CacheOperation.UPDATE)
        self.assertEqual(outcome.error.error.reason, CacheFailureReason.CONTRACT_MISMATCH)
        self.assertEqual(outcome.error.error.issues[0].code, CacheIssueCode.KEY_OCCUPIED_DIFFERENT_VALUE)
        self.assertEqual(self.cache.get(self.key).entry.value, self.entry.value)
        self.assertEqual(CacheNodeError.model_validate_json(outcome.error.model_dump_json()), outcome.error)

    async def test_invalid_command_and_value_stop_before_update(self):
        entry = CacheEntry[bytes].model_construct(key=self.key, value="not bytes")
        request = UpdateManifestCacheEntryInput.model_construct(kind="create", request=entry)
        with patch.object(self.cache, "update", wraps=self.cache.update) as update:
            outcome = await self.run_request(request)
        update.assert_not_called()
        self.assertEqual(outcome.status, NodeStatus.FAILED)
        self.assertGreaterEqual(len(outcome.validation.errors), 2)

    async def test_missing_input_stops_before_update(self):
        with patch.object(self.cache, "update", wraps=self.cache.update) as update:
            outcome = await self.run_request(None)
        update.assert_not_called()
        self.assertEqual(outcome.status, NodeStatus.FAILED)

    async def test_backend_failure_is_not_not_found(self):
        with patch.object(self.backend, "update", side_effect=OSError("unavailable")):
            outcome = await self.run_request(self.request)
        self.assertEqual(outcome.status, NodeStatus.FAILED)
        self.assertIsNone(outcome.output)
        self.assertEqual(outcome.error.error.reason, CacheFailureReason.BACKEND_FAILURE)

    async def test_checkpoint_replay_keeps_unchanged_without_second_update(self):
        bindings = GraphBindings()
        for node in (self.node, make_read_cache_entry_node(self.cache), make_create_cache_entry_node(self.cache), make_evict_cache_entry_node(self.cache)):
            bindings.nodes[node.id] = node
        compiler = GraphCompiler(self.registry, bindings, compile_rules=lambda _: (), evaluate_rules=lambda *_: True)
        compiler.precompile()
        plan = compiler.compile(GraphRuleState(), invocation_root=self.node.id)
        executor = DAGExecutor(self.runner, {PythonNodeExecutor: PythonNodeExecutor()})
        store = MemoryExecutionStore()
        self.cache.create(self.entry)
        with patch.object(self.cache, "update", wraps=self.cache.update) as update:
            first = await executor.run_invocation(plan, ExecutionId("update-replay"), self.node.id, PlanRevision("1"),
                                                  store, owner="test", workers=1, invocation_limit=1, input=self.request)
            self.cache.evict(self.key)
            replay = await executor.run_invocation(plan, ExecutionId("update-replay"), self.node.id, PlanRevision("1"),
                                                   store, owner="test", workers=1, invocation_limit=1, input=self.request)
        update.assert_called_once_with(self.entry)
        self.assertEqual(first.status, InvocationStatus.SUCCEEDED)
        self.assertEqual(first.terminal_payload(), replay.terminal_payload())
        self.assertEqual(self.contract.output_type.model_validate_json(replay.terminal_payload()).value.outcome, CacheUpdateOutcome.UNCHANGED)
        self.assertEqual((await self.run_request(self.request)).output.value.outcome, CacheUpdateOutcome.NOT_FOUND)

    def test_named_identity_and_field_paths(self):
        for model in (UpdateManifestCacheEntryInput, UpdateManifestCacheEntryOutput):
            self.assertEqual(ModelIdentity.of(model).qualname, model.__name__)
        path = CheckedPath.root(UpdateManifestCacheEntryInput).field(
            FieldRef(lambda: UpdateManifestCacheEntryInput, lambda value: value.request)).freeze()
        self.assertEqual(path.projection(), ("request",))
        self.assertEqual(self.contract.calls, ())
        self.assertEqual(self.contract.reads, ())
        self.assertIsNone(self.contract.lifecycle)
        self.assertFalse(self.node.skip_on_replan)
