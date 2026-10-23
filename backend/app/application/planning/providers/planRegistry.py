"""Trusted provider handles and explicit read-only dependency selections."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from typing import TYPE_CHECKING

from app.application.planning.providers.planProvider import PlanProvider, RegisteredPlanContract
from app.application.cache.service.cacheService import _complete_record, _immutable
from app.dataModel.cache.contracts.cacheContract import CacheContractMetadata
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planContract import PlanContractId, PlanContractMetadata
from app.dataModel.planning.contracts.planDependency import PlanDependency, PlanDependencyContract
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult, PlanEnvelope
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.identity.planKey import PlanScope, PlanSlot

if TYPE_CHECKING:
    from app.application.planning.service.planningService import PlanBuildControl


def _mismatch(message: str) -> Exception:
    from app.application.planning.service.planningService import PlanContractFailure, PlanContractFailureReason
    from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
    return PlanContractFailure(PlanContractFailureReason.DEPENDENCY_MISMATCH,
                               (FieldPathError(("dependencies",), message),))


@dataclass(frozen=True)
class _Registration:
    handle: object
    build: Callable[[object, PlanDependencyReader, PlanBuildControl], object]


class PlanRegistry:
    def __init__(self) -> None:
        self._entries: dict[PlanContractId, _Registration] = {}
        self._cache_ids: set[str] = set()
        self._lock = RLock()

    def register[I, T](self, contract: RegisteredPlanContract[I, T], provider: PlanProvider[I, T]) -> None:
        _complete_record(contract.metadata)
        PlanContractMetadata.model_validate(contract.metadata)
        _complete_record(contract.cache_binding.contract)
        CacheContractMetadata.model_validate(contract.cache_binding.contract)
        declarations = contract.dependency_contracts
        if type(declarations) is not tuple or len({dep.slot for dep in declarations}) != len(declarations):
            raise ValueError("duplicate or mutable dependency declarations")
        for declaration in declarations:
            _complete_record(declaration)
            PlanDependencyContract.model_validate(declaration)

        def build(request: object, dependencies: PlanDependencyReader, control: PlanBuildControl) -> object:
            typed = PlanRequest[I].model_validate(request)
            return provider.build(typed, dependencies, control)

        with self._lock:
            if contract.metadata.id in self._entries or contract.cache_binding.contract.id in self._cache_ids:
                raise ValueError("duplicate plan or cache contract registration")
            self._entries[contract.metadata.id] = _Registration(contract, build)
            self._cache_ids.add(contract.cache_binding.contract.id)

    def check[I, T](self, contract: RegisteredPlanContract[I, T]) -> None:
        from app.application.planning.service.planningService import PlanContractFailure, PlanContractFailureReason
        from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
        with self._lock:
            registered = self._entries.get(contract.metadata.id)
            if registered is None or registered.handle is not contract:
                raise PlanContractFailure(PlanContractFailureReason.UNKNOWN_CONTRACT,
                    (FieldPathError(("contract",), "unknown or substituted registered handle"),))

    def build[I, T](self, contract: RegisteredPlanContract[I, T], request: PlanRequest[I],
                    dependencies: PlanDependencyReader, control: PlanBuildControl) -> PlanBuildResult[T]:
        self.check(contract)
        with self._lock:
            adapter = self._entries[contract.metadata.id].build
        result = adapter(request, dependencies, control)
        if not isinstance(result, PlanBuildResult):
            raise ValueError("provider must return a typed PlanBuildResult")
        _immutable(result, set())
        return PlanBuildResult[T].model_validate(result)


@dataclass(frozen=True)
class _Selected:
    slot: PlanSlot
    handle: object
    envelope: object
    validate: Callable[[object], PlanEnvelope[object]]


@dataclass(frozen=True)
class PlanDependencyReader:
    registry: PlanRegistry
    _selected: tuple[_Selected, ...] = ()

    def with_plan[I, T](self, slot: PlanSlot, contract: RegisteredPlanContract[I, T],
                         envelope: PlanEnvelope[T]) -> PlanDependencyReader:
        self.registry.check(contract)
        if any(item.slot == slot for item in self._selected):
            raise _mismatch("duplicate selected dependency slot")

        def validate(value: object) -> PlanEnvelope[object]:
            result = contract.validate_envelope(value)
            return PlanEnvelope[object].model_validate(result)

        validated = contract.validate_envelope(envelope)
        return PlanDependencyReader(self.registry, self._selected + (_Selected(slot, contract, validated, validate),))

    def validate_for(self, dependencies: tuple[PlanDependency, ...],
                     declarations: tuple[PlanDependencyContract, ...],
                     world_uid: EntityUid, scope: PlanScope) -> None:
        expected = {dependency.slot: dependency for dependency in dependencies}
        declared = {declaration.slot: declaration for declaration in declarations}
        selected = {item.slot: item for item in self._selected}
        if set(expected) != set(declared) or set(expected) != set(selected):
            raise _mismatch("extra or missing declared/selected dependency")
        for slot, dependency in expected.items():
            try:
                envelope = selected[slot].validate(selected[slot].envelope)
                if (not declared[slot].accepts(dependency) or envelope.ref != dependency.ref
                        or envelope.ref.key.world_uid != world_uid or envelope.ref.key.scope != scope):
                    raise ValueError("dependency metadata/ref/world/scope mismatch")
            except Exception as exc:
                raise _mismatch(str(exc)) from exc

    def require[I, T](self, slot: PlanSlot, contract: RegisteredPlanContract[I, T]) -> PlanEnvelope[T]:
        self.registry.check(contract)
        for selected in self._selected:
            if selected.slot == slot and selected.handle is contract:
                try:
                    return contract.validate_envelope(selected.envelope)
                except Exception as exc:
                    raise _mismatch(str(exc)) from exc
        raise _mismatch("undeclared slot or wrong dependency contract")
