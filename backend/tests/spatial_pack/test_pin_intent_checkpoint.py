"""Pack pin intent carried by an invocation across a SQLite store reopen."""
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.dataModel.engine.dag.identity import (
    ContractId, ContractVersion, ExecutionId, InvocationId, NodeId, PlanInstanceId, PlanRevision,
)
from app.dataModel.engine.dag.invocations.record import InvocationGraph, InvocationRecord, InvocationStatus, RegisteredContract
from app.db.repositories.sqlite.dagExecutions.executionStore import SQLiteExecutionStore


class ProbePinIntent(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    pin_id: UUID
    world_uid: str


class PinIntentCheckpointTests(IsolatedAsyncioTestCase):
    async def test_reopen_preserves_owner_and_logical_read_identity(self):
        schema = Path(__file__).resolve().parents[2] / "app/db/migrations/0001_initial.sql"
        execution = ExecutionId("test-execution")
        invocation = InvocationId("test-invocation")
        record = InvocationRecord(execution_id=execution, invocation_id=invocation,
                                  node_id=NodeId("test-node"), plan_instance_id=PlanInstanceId("test-plan"),
                                  contract_id=ContractId("test-input"), version=ContractVersion("1"),
                                  status=InvocationStatus.RUNNING, plan_revision=PlanRevision("r"))
        contract = RegisteredContract(node_id=record.node_id, contract_id=record.contract_id, version=record.version,
                                      continuation=(ContractId("test-pin-intent"), ContractVersion("1")),
                                      input_wait=None)
        graph = InvocationGraph(execution_id=execution, root=invocation, revision=record.plan_revision,
                                registry=(contract,), records={invocation: record})
        intent = ProbePinIntent(pin_id=UUID(int=23), world_uid="world")
        with TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.sqlite"
            with closing(sqlite3.connect(path)) as connection:
                connection.executescript(schema.read_text(encoding="utf-8"))
                store = SQLiteExecutionStore(connection)
                await store.create(execution, graph.model_dump_json().encode())
                claim = await store.claim(execution, "worker", 60)
                graph.records[invocation].state_contract = contract.continuation
                graph.records[invocation].continuation = intent.model_dump_json()
                await store.checkpoint(claim, 0, InvocationStatus.RUNNING, graph.model_dump_json().encode())

            with closing(sqlite3.connect(path)) as reopened:
                checkpoint = await SQLiteExecutionStore(reopened).load(execution)
                self.assertEqual(checkpoint.revision, 1)
                restored = InvocationGraph.model_validate_json(checkpoint.blob).records[invocation]
                self.assertEqual((restored.execution_id, restored.invocation_id), (execution, invocation))
                self.assertEqual(restored.state_contract, (ContractId("test-pin-intent"), ContractVersion("1")))
                self.assertIsNotNone(restored.continuation)
                self.assertEqual(ProbePinIntent.model_validate_json(restored.continuation), intent)
