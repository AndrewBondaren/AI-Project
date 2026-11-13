import unittest
from unittest.mock import patch

from app.application.cache.backends.memoryCache import MemoryCache
from app.application.cache.contracts.cacheBackend import CacheBinding
from app.application.cache.contracts.manifestBytesCodec import ManifestBytesCodec
from app.application.cache.service.cacheBindingRegistry import CacheBindingRegistry
from app.application.cache.service.cacheService import CacheService
from app.application.engine.nodes.cache.createCacheEntryNode import make_create_cache_entry_node
from app.application.engine.nodes.cache.readCacheEntryNode import make_read_cache_entry_node
from app.application.engine.nodes.cache.registration import CREATE_MANIFEST_CACHE_ENTRY_CONTRACT, register_manifest_cache_nodes
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
from app.dataModel.cache.contracts.cacheEntry import CacheAdmission, CacheEntry
from app.dataModel.cache.contracts.cacheError import CacheFailureReason, CacheIssueCode, CacheOperation
from app.dataModel.cache.contracts.cacheLookup import CacheMiss
from app.dataModel.cache.identity.cacheKey import CacheKey
from app.dataModel.cache.policy.cachePolicy import CachePolicy
from app.dataModel.engine.dag.identity import ExecutionId, PlanRevision
from app.dataModel.engine.dag.invocations.record import InvocationStatus
from app.dataModel.engine.dag.nodeStatus import NodeStatus
from app.dataModel.engine.nodes.cache.contracts import CacheNodeError
from app.dataModel.engine.nodes.cache.manifestContracts import CreateManifestCacheEntryInput, CreateManifestCacheEntryOutput
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.fields.validatedFieldPath import ModelIdentity
from app.dataModel.worldPack.meta.manifestCacheContract import MANIFEST_BYTES_CONTRACT
from tests.dag_typing.fixtures import GraphBindings, GraphRuleState


class CreateCacheNodeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.backend = MemoryCache(CachePolicy(max_entry_bytes=16000, max_retained_bytes=32000))
        self.cache = CacheService(self.backend, CacheBindingRegistry((CacheBinding(MANIFEST_BYTES_CONTRACT, ManifestBytesCodec()),)))
        self.key = CacheKey[bytes](contract=MANIFEST_BYTES_CONTRACT, item_key=bytes([255]) * 32)
        self.entry = CacheEntry[bytes](key=self.key, value=bytes(range(256)))
        self.request = CreateManifestCacheEntryInput(kind="create", request=self.entry)
        self.node = make_create_cache_entry_node(self.cache)
        self.registry = NodeRegistry()
        register_manifest_cache_nodes(self.registry)
        self.contract = CREATE_MANIFEST_CACHE_ENTRY_CONTRACT
        self.registration = self.registry.get(self.node.id, self.contract)
        self.runner = NodeRunner(ContractValidator(), NodeValidator())

    async def run_request(self, request):
        catalog = DAGContext(ExecutionId("create-test"), self.registry)
        identity = catalog.begin_attempt(self.node.id, PlanRevision("1"))
        return await self.runner.run(self.node, catalog.read_view(self.node.id), identity,
                                     self.registration, PythonNodeExecutor(), explicit_input=request)

    async def test_stored_and_already_present_preserve_owning_outcomes(self):
        restored = self.contract.input_type.model_validate_json(InvocationCoordinator.encode(self.request, self.contract.input_type))
        with patch.object(self.cache, "create", wraps=self.cache.create) as create:
            first = await self.run_request(restored)
            self.assertEqual(create.call_count, 1)
            create.assert_called_with(restored.request)
            second = await self.run_request(restored)
        self.assertEqual(first.status, NodeStatus.SUCCESS)
        self.assertEqual(first.output.kind, "create")
        self.assertEqual(first.output.value.outcome, CacheAdmission.STORED)
        self.assertEqual(second.output.value.outcome, CacheAdmission.ALREADY_PRESENT)
        self.assertEqual(self.cache.get(self.key).entry.value, self.entry.value)
        wire = InvocationCoordinator.encode(first.output, self.contract.output_type)
        self.assertEqual(self.contract.output_type.model_validate_json(wire), first.output)

    async def test_oversize_is_successful_admission_outcome_without_storage(self):
        request = CreateManifestCacheEntryInput(kind="create", request=CacheEntry[bytes](key=self.key, value=b"x" * 16001))
        outcome = await self.run_request(request)
        self.assertEqual(outcome.status, NodeStatus.SUCCESS)
        self.assertEqual(outcome.output.value.outcome, CacheAdmission.SKIPPED_OVERSIZE)
        self.assertIsInstance(self.cache.get(self.key), CacheMiss)

    async def test_conflict_preserves_entry_and_declared_error(self):
        self.cache.create(self.entry)
        request = CreateManifestCacheEntryInput(kind="create", request=CacheEntry[bytes](key=self.key, value=b"different"))
        outcome = await self.run_request(request)
        self.assertEqual(outcome.status, NodeStatus.FAILED)
        self.assertIsNone(outcome.output)
        self.assertEqual(outcome.error.error.operation, CacheOperation.CREATE)
        self.assertEqual(outcome.error.error.reason, CacheFailureReason.CONTRACT_MISMATCH)
        self.assertEqual(outcome.error.error.issues[0].code, CacheIssueCode.KEY_OCCUPIED_DIFFERENT_VALUE)
        self.assertEqual(self.cache.get(self.key).entry.value, self.entry.value)
        self.assertEqual(CacheNodeError.model_validate_json(outcome.error.model_dump_json()), outcome.error)

    async def test_invalid_command_and_nested_payload_fail_before_write(self):
        bad_entry = CacheEntry[bytes].model_construct(key=self.key, value="not bytes")
        request = CreateManifestCacheEntryInput.model_construct(kind="update", request=bad_entry)
        with patch.object(self.cache, "create", wraps=self.cache.create) as create:
            outcome = await self.run_request(request)
        create.assert_not_called()
        self.assertEqual(outcome.status, NodeStatus.FAILED)
        self.assertGreaterEqual(len(outcome.validation.errors), 2)
        self.assertIsInstance(self.cache.get(self.key), CacheMiss)

    async def test_missing_input_fails_before_write(self):
        with patch.object(self.cache, "create", wraps=self.cache.create) as create:
            outcome = await self.run_request(None)
        create.assert_not_called()
        self.assertEqual(outcome.status, NodeStatus.FAILED)

    async def test_backend_failure_is_not_stored_success(self):
        with patch.object(self.backend, "create", side_effect=OSError("unavailable")):
            outcome = await self.run_request(self.request)
        self.assertEqual(outcome.status, NodeStatus.FAILED)
        self.assertEqual(outcome.error.error.reason, CacheFailureReason.BACKEND_FAILURE)
        self.assertIsNone(outcome.output)

    async def test_invocation_replay_after_eviction_does_not_repeat_write(self):
        bindings = GraphBindings()
        bindings.nodes[self.node.id] = self.node
        read_node = make_read_cache_entry_node(self.cache)
        bindings.nodes[read_node.id] = read_node
        from app.application.engine.nodes.cache.updateCacheEntryNode import make_update_cache_entry_node
        update_node = make_update_cache_entry_node(self.cache)
        bindings.nodes[update_node.id] = update_node
        compiler = GraphCompiler(self.registry, bindings, compile_rules=lambda _: (), evaluate_rules=lambda *_: True)
        compiler.precompile()
        plan = compiler.compile(GraphRuleState(), invocation_root=self.node.id)
        executor = DAGExecutor(self.runner, {PythonNodeExecutor: PythonNodeExecutor()})
        store = MemoryExecutionStore()
        with patch.object(self.cache, "create", wraps=self.cache.create) as create:
            first = await executor.run_invocation(plan, ExecutionId("create-replay"), self.node.id, PlanRevision("1"),
                                                  store, owner="test", workers=1, invocation_limit=1, input=self.request)
            self.cache.evict(self.key)
            replay = await executor.run_invocation(plan, ExecutionId("create-replay"), self.node.id, PlanRevision("1"),
                                                   store, owner="test", workers=1, invocation_limit=1, input=self.request)
        create.assert_called_once_with(self.entry)
        self.assertEqual(first.status, InvocationStatus.SUCCEEDED)
        self.assertEqual(replay.terminal_payload(), first.terminal_payload())
        self.assertIsInstance(self.cache.get(self.key), CacheMiss)
        self.assertEqual(self.contract.output_type.model_validate_json(replay.terminal_payload()).value.outcome, CacheAdmission.STORED)

    def test_named_contracts_and_paths(self):
        for model in (CreateManifestCacheEntryInput, CreateManifestCacheEntryOutput):
            self.assertEqual(ModelIdentity.of(model).qualname, model.__name__)
        path = CheckedPath.root(CreateManifestCacheEntryInput).field(
            FieldRef(lambda: CreateManifestCacheEntryInput, lambda value: value.request)).freeze()
        self.assertEqual(path.projection(), ("request",))
        self.assertEqual(self.contract.calls, ())
        self.assertEqual(self.contract.reads, ())
        self.assertIsNone(self.contract.lifecycle)
        self.assertFalse(self.node.skip_on_replan)
