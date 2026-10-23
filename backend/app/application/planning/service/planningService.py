"""Revision-keyed planning, bounded single-flight and independent waiters."""

from concurrent.futures import CancelledError, Future, ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from threading import Event, RLock, local
from typing import Protocol

from app.application.cache.service.cacheService import CacheService, _complete_record, _immutable
from app.application.planning.providers.planProvider import RegisteredPlanContract
from app.application.planning.providers.planRegistry import PlanDependencyReader, PlanRegistry
from app.application.planning.service.planFingerprints import cache_item_key, input_fingerprint, output_fingerprint
from app.dataModel.cache.contracts.cacheEntry import CacheEntry
from app.dataModel.cache.contracts.cacheLookup import CacheHit
from app.dataModel.cache.identity.cacheKey import CacheKey
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.identity.planKey import PlanKey
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.planning.policy.planningExecutionPolicy import PlanningExecutionPolicy
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class PlanContractFailureReason(StrEnum):
    UNKNOWN_CONTRACT = "unknown_contract"
    INVALID_INPUT = "invalid_input"
    DEPENDENCY_MISMATCH = "dependency_mismatch"
    KEY_MISMATCH = "key_mismatch"


class PlanContractFailure(Exception):
    def __init__(self, reason: PlanContractFailureReason, issues: tuple[FieldPathError, ...]):
        self.reason, self.issues = reason, issues
        super().__init__(reason.value)


class PlanBuildFailure(Exception):
    def __init__(self, issues: tuple[FieldPathError, ...]):
        if not issues:
            raise ValueError("PlanBuildFailure requires nonempty issues")
        self.issues = issues
        super().__init__("plan build failed")


class PlanWaitCancelled(Exception):
    pass


class PlanWaitTimeout(Exception):
    pass


class PlanningBusy(Exception):
    pass


class PlanBuildControl(Protocol):
    def raise_if_shutdown(self) -> None: ...


class PlanWaitControl(Protocol):
    def raise_if_cancelled(self) -> None: ...
    def remaining_seconds(self) -> float | None: ...


@dataclass(frozen=True)
class _BuildControl:
    stopping: Event

    def raise_if_shutdown(self) -> None:
        if self.stopping.is_set():
            raise PlanWaitCancelled("planning service shutdown")


@dataclass
class _Flight:
    future: Future[object]
    waiters: int = 0


def _failure(reason: PlanContractFailureReason, message: str) -> PlanContractFailure:
    return PlanContractFailure(reason, (FieldPathError(("planning",), message),))


class PlanningService:
    def __init__(self, registry: PlanRegistry, cache: CacheService, policy: PlanningExecutionPolicy):
        self._registry, self._cache = registry, cache
        self._policy = PlanningExecutionPolicy.model_validate(policy)
        self._executor = ThreadPoolExecutor(max_workers=self._policy.max_workers, thread_name_prefix="planning")
        self._flights: dict[tuple[str, int, bytes], _Flight] = {}
        self._lock, self._stopping, self._worker = RLock(), Event(), local()

    def _request[I, T](self, contract: RegisteredPlanContract[I, T], request: PlanRequest[I],
                        dependencies: PlanDependencyReader) -> PlanRequest[I]:
        self._registry.check(contract)
        try:
            _complete_record(request)
            _immutable(request, set())
            key = PlanKey.model_validate(request.key)
            checked = type(request).model_validate(request)
            _immutable(checked.inputs, set())
            inputs = contract.validate_inputs(checked.inputs)
            _immutable(inputs, set())
        except Exception as exc:
            raise _failure(PlanContractFailureReason.INVALID_INPUT, str(exc)) from exc
        metadata = contract.metadata
        if (key.contract_id != metadata.id or key.schema_version != metadata.schema_version
                or key.algorithm_version != metadata.algorithm_version):
            raise _failure(PlanContractFailureReason.KEY_MISMATCH, "request metadata differs from registered contract")
        if dependencies.registry is not self._registry:
            raise _failure(PlanContractFailureReason.DEPENDENCY_MISMATCH, "foreign dependency registry")
        dependencies.validate_for(checked.dependencies, contract.dependency_contracts, key.world_uid, key.scope)
        try:
            fingerprint = contract.fingerprint_inputs(key.world_uid, key.scope, inputs, checked.dependencies)
            exact = input_fingerprint(metadata, key.world_uid, key.scope, inputs, checked.dependencies, contract.manifest)
            if fingerprint != exact or fingerprint != key.input_fingerprint:
                raise ValueError("input fingerprint mismatch")
        except Exception as exc:
            raise _failure(PlanContractFailureReason.KEY_MISMATCH, str(exc)) from exc
        return PlanRequest[I](key=key, inputs=inputs, dependencies=checked.dependencies)

    def _envelope[I, T](self, contract: RegisteredPlanContract[I, T], value: object,
                         request: PlanRequest[I]) -> PlanEnvelope[T]:
        try:
            envelope = contract.validate_envelope(value)
            _immutable(envelope, set())
            if envelope.ref.key != request.key or envelope.dependencies != request.dependencies:
                raise ValueError("envelope key/dependencies differ from expected request")
            return envelope
        except Exception as exc:
            raise _failure(PlanContractFailureReason.KEY_MISMATCH, str(exc)) from exc

    def _build[I, T](self, contract: RegisteredPlanContract[I, T], request: PlanRequest[I],
                      dependencies: PlanDependencyReader, key: CacheKey[PlanEnvelope[T]]) -> object:
        self._worker.active = True
        control = _BuildControl(self._stopping)
        try:
            control.raise_if_shutdown()
            try:
                result = self._registry.build(contract, request, dependencies, control)
                _immutable(result, set())
                output = output_fingerprint(result.payload, request.dependencies, result.diagnostics, contract.manifest)
                envelope = PlanEnvelope[T](ref=PlanRef(key=request.key, output_fingerprint=output),
                    dependencies=request.dependencies, payload=result.payload, diagnostics=result.diagnostics)
                envelope = self._envelope(contract, envelope, request)
            except (PlanBuildFailure, PlanWaitCancelled, PlanContractFailure):
                raise
            except Exception as exc:
                raise PlanBuildFailure((FieldPathError(("provider",), str(exc)),)) from exc
            with self._lock:
                control.raise_if_shutdown()
                self._cache.put(contract.cache_binding, CacheEntry[PlanEnvelope[T]](key=key, value=envelope))
            return envelope
        finally:
            self._worker.active = False

    def _cleanup(self, address: tuple[str, int, bytes], flight: _Flight) -> None:
        with self._lock:
            if flight.future.done() and flight.waiters == 0 and self._flights.get(address) is flight:
                del self._flights[address]

    def _completed(self, address: tuple[str, int, bytes], future: Future[object]) -> None:
        with self._lock:
            flight = self._flights.get(address)
            if flight is not None and flight.future is future:
                self._cleanup(address, flight)

    def _check_wait(self, wait: PlanWaitControl) -> float:
        if self._stopping.is_set():
            raise PlanWaitCancelled("planning service shutdown")
        wait.raise_if_cancelled()
        remaining = wait.remaining_seconds()
        if remaining is not None:
            if not isfinite(remaining):
                raise ValueError("wait deadline must be finite")
            if remaining <= 0:
                raise PlanWaitTimeout()
        return 0.05 if remaining is None else min(0.05, remaining)

    def get_or_build[I, T](self, contract: RegisteredPlanContract[I, T], request: PlanRequest[I],
                            dependencies: PlanDependencyReader, *, wait: PlanWaitControl) -> PlanEnvelope[T]:
        if getattr(self._worker, "active", False):
            raise _failure(PlanContractFailureReason.DEPENDENCY_MISMATCH, "recursive provider planning is forbidden")
        self._check_wait(wait)
        checked = self._request(contract, request, dependencies)
        key = CacheKey[PlanEnvelope[T]](contract=contract.cache_binding.contract,
            item_key=cache_item_key(checked.key, contract.manifest))
        address = (key.contract.id, key.contract.schema_version, key.item_key)
        with self._lock:
            self._check_wait(wait)
            lookup = self._cache.get(contract.cache_binding, key)
            if isinstance(lookup, CacheHit):
                return self._envelope(contract, lookup.entry.value, checked)
            flight = self._flights.get(address)
            if flight is None:
                limit = self._policy.max_workers + self._policy.max_pending_builds
                if len(self._flights) >= limit:
                    raise PlanningBusy("planning execution queue is full")
                flight = _Flight(self._executor.submit(self._build, contract, checked, dependencies, key))
                self._flights[address] = flight
            flight.waiters += 1
            flight.future.add_done_callback(lambda future: self._completed(address, future))
        try:
            while True:
                delay = self._check_wait(wait)
                try:
                    value = flight.future.result(timeout=delay)
                    self._check_wait(wait)
                    return self._envelope(contract, value, checked)
                except TimeoutError:
                    continue
                except CancelledError as exc:
                    raise PlanWaitCancelled("planning service shutdown") from exc
        finally:
            with self._lock:
                flight.waiters -= 1
                self._cleanup(address, flight)

    def shutdown(self, *, wait: bool = True) -> None:
        with self._lock:
            self._stopping.set()
        self._executor.shutdown(wait=wait, cancel_futures=True)
