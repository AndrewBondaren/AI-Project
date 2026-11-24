"""Concrete mock Lifecycle DAG bindings; no production registration."""
from pydantic import BaseModel, ConfigDict

from app.dataModel.artifacts.lifecycle.operation.record import OperationCancelled
from app.dataModel.engine.dag.errors.nodeError import NodeError
from app.dataModel.patch.results.assembly import PatchSetAssemblyRefused
from app.dataModel.worldSnapshot.errors.publicFault import SnapshotPublicFault
from tests.lifecycle.support.snapshotContracts import MockAssemblyInput, MockPatchSet, MockSnapshotApplyResult


class MockAssemblePatchSetInput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    request: MockAssemblyInput


class MockAssemblePatchSetOutput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    value: MockPatchSet | PatchSetAssemblyRefused


class MockApplySnapshotInput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    patch_set: MockPatchSet


class MockApplySnapshotOutput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    value: MockSnapshotApplyResult


class SnapshotPublicNodeError(NodeError):
    fault: SnapshotPublicFault


class SnapshotOperationCancelledNodeError(NodeError):
    outcome: OperationCancelled
