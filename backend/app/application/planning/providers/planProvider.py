"""Application bindings; domain payload declarations stay in dataModel."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, Protocol, TYPE_CHECKING, TypeVar

from app.application.planning.service.planFingerprints import output_fingerprint
from app.application.cache.contracts.cacheBackend import CacheBinding
from app.application.cache.service.cacheService import _immutable
from app.dataModel.identity.uid import EntityUid
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest
from app.dataModel.planning.contracts.planContract import PlanContractMetadata
from app.dataModel.planning.contracts.planDependency import PlanDependency, PlanDependencyContract
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult, PlanEnvelope
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.identity.planKey import InputFingerprint, PlanScope

if TYPE_CHECKING:
    from app.application.planning.providers.planRegistry import PlanDependencyReader
    from app.application.planning.service.planningService import PlanBuildControl

I = TypeVar("I")
T = TypeVar("T")


@dataclass(frozen=True)
class RegisteredPlanContract(Generic[I, T]):
    metadata: PlanContractMetadata
    validate_inputs: Callable[[object], I]
    fingerprint_inputs: Callable[[EntityUid, PlanScope, I, tuple[PlanDependency, ...]], InputFingerprint]
    dependency_contracts: tuple[PlanDependencyContract, ...]
    cache_binding: CacheBinding[PlanEnvelope[T]]
    manifest: CanonicalSchemaManifest

    def validate_envelope(self, value: object) -> PlanEnvelope[T]:
        _immutable(value, set())
        envelope = self.cache_binding.codec.validate(value)
        _immutable(envelope, set())
        key = envelope.ref.key
        if (key.contract_id != self.metadata.id or key.schema_version != self.metadata.schema_version
                or key.algorithm_version != self.metadata.algorithm_version):
            raise ValueError("envelope metadata differs from registered contract")
        expected = output_fingerprint(envelope.payload, envelope.dependencies, envelope.diagnostics, self.manifest)
        if envelope.ref.output_fingerprint != expected:
            raise ValueError("envelope output fingerprint mismatch")
        return envelope


class PlanProvider(Protocol[I, T]):
    def build(self, request: PlanRequest[I], dependencies: PlanDependencyReader,
              control: PlanBuildControl) -> PlanBuildResult[T]: ...
