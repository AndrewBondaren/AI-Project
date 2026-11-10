"""Typed storage boundary; world currency and domain planning belong to callers."""

from contextlib import contextmanager
from dataclasses import fields, is_dataclass
from enum import Enum
from sys import getsizeof

from pydantic import BaseModel

from app.application.cache.contracts.cacheBackend import CacheBackend, CacheBinding, CacheValueConflict, CacheEncodingFailure
from app.application.cache.service.cacheBindingRegistry import CacheBindingRegistry, CacheBindingResolutionError
from app.dataModel.cache.contracts.cacheContract import CacheContractMetadata
from app.dataModel.cache.contracts.cacheCreateResult import CacheCreateResult
from app.dataModel.cache.contracts.cacheUpdateResult import CacheUpdateResult
from app.dataModel.cache.contracts.cacheEvictResult import CacheEvictResult
from app.dataModel.cache.contracts.cacheEntry import CacheEntry
from app.dataModel.cache.contracts.cacheError import CacheError, CacheIssueCode, CacheContractIssue, CacheFailureReason, CacheFieldIssue, CacheOperation
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.cache.contracts.cacheLookup import CacheHit, CacheLookup, CacheMiss
from app.dataModel.cache.identity.cacheKey import CacheKey
from app.dataModel.validation.immutableValue import (
    _complete_record as _complete_record,
    _immutable as _immutable,
    validate_immutable as validate_immutable,
)


def retained_entry_bytes(value: object) -> int:
    """Conservative retained graph accounting, including entry/key metadata.

    Each object identity is counted once within this graph. Class/schema objects
    and process globals are not owned by an entry. RAM stores no encoded copy.
    This is a retention budget, not a bound on process RSS or build memory.
    """
    visited: set[int] = set()

    def size(item: object) -> int:
        identity = id(item)
        if identity in visited:
            return 0
        visited.add(identity)
        cost = getsizeof(item)
        if isinstance(item, dict):
            return cost + sum(size(key) + size(child) for key, child in item.items())
        if isinstance(item, (tuple, list, set, frozenset)):
            return cost + sum(size(child) for child in item)
        if isinstance(item, Enum):
            return cost + size(item.value)
        if isinstance(item, BaseModel):
            return (cost + size(vars(item)) + size(item.__pydantic_fields_set__)
                    + size(item.__pydantic_extra__) + size(item.__pydantic_private__))
        if is_dataclass(item) and not isinstance(item, type):
            if hasattr(item, "__dict__"):
                return cost + size(vars(item))
            return cost + sum(size(getattr(item, field.name)) for field in fields(item))
        return cost

    return size(value)


_CONTRACT_PATH = CheckedPath.root(CacheContractMetadata)
_RESOLUTION_PATHS = {
    CacheIssueCode.UNKNOWN_NAMESPACE: _CONTRACT_PATH.field(
        FieldRef(lambda: CacheContractMetadata, lambda metadata: metadata.id)).freeze(),
    CacheIssueCode.SCHEMA_VERSION_MISMATCH: _CONTRACT_PATH.field(
        FieldRef(lambda: CacheContractMetadata, lambda metadata: metadata.schema_version)).freeze(),
}


class CacheFailure(Exception):
    def __init__(self, error: CacheError):
        self.error = error
        super().__init__(error.message)


def _failure(operation: CacheOperation, reason: CacheFailureReason, message: str,
             code: CacheIssueCode | None = None) -> CacheFailure:
    issues = () if code is None else (CacheContractIssue(code=code, message=message),)
    return CacheFailure(CacheError(operation=operation, reason=reason, message=message, issues=issues))


@contextmanager
def _backend_call(operation: CacheOperation):
    try:
        yield
    except CacheEncodingFailure as exc:
        raise _failure(operation, CacheFailureReason.INVALID_PAYLOAD,
                       "Canonical encoding failed", CacheIssueCode.INVALID_VALUE) from exc
    except CacheValueConflict as exc:
        raise _failure(operation, CacheFailureReason.CONTRACT_MISMATCH,
                       "Key holds a different value", CacheIssueCode.KEY_OCCUPIED_DIFFERENT_VALUE) from exc
    except Exception as exc:
        raise _failure(operation, CacheFailureReason.BACKEND_FAILURE, "Cache backend failed") from exc


class CacheService:
    def __init__(self, backend: CacheBackend, registry: CacheBindingRegistry):
        self._backend = backend
        self._registry = registry

    def _binding[T](self, operation: CacheOperation, key: CacheKey[T]) -> CacheBinding[T]:
        try:
            _complete_record(key)
            _complete_record(key.contract)
            type(key).model_validate(key, strict=True)
            return self._registry.resolve(key.contract)
        except CacheBindingResolutionError as exc:
            issue = CacheFieldIssue(code=exc.code, path=_RESOLUTION_PATHS[exc.code],
                                    message="Unregistered cache namespace or version")
            raise CacheFailure(CacheError(operation=operation, reason=CacheFailureReason.CONTRACT_MISMATCH,
                                          message=issue.message, issues=(issue,))) from exc
        except Exception as exc:
            raise _failure(operation, CacheFailureReason.CONTRACT_MISMATCH,
                           "Invalid cache key", CacheIssueCode.CONTRACT_VIOLATION) from exc

    def _admit[T](self, op: CacheOperation, entry: CacheEntry[T]) -> tuple[CacheEntry[T], CacheBinding[T]]:
        try:
            _complete_record(entry)
            key = entry.key
        except Exception as exc:
            raise _failure(op, CacheFailureReason.INVALID_PAYLOAD, "Invalid entry", CacheIssueCode.INVALID_VALUE) from exc
        binding = self._binding(op, key)
        try:
            _immutable(entry.value, set())
            value = binding.codec.validate(entry.value)
            _immutable(value, set())
            return CacheEntry[T](key=key, value=value), binding
        except Exception as exc:
            raise _failure(op, CacheFailureReason.INVALID_PAYLOAD, "Invalid value", CacheIssueCode.INVALID_VALUE) from exc

    def get[T](self, key: CacheKey[T]) -> CacheLookup[T]:
        op = CacheOperation.GET
        self._binding(op, key)
        with _backend_call(op):
            lookup = self._backend.get(key)
        try:
            _complete_record(lookup)
            checked = type(lookup).model_validate(lookup, strict=True)
            if isinstance(checked, CacheMiss):
                return checked
            if not isinstance(lookup, CacheHit) or not isinstance(checked, CacheHit):
                raise ValueError("unknown lookup status")
            _complete_record(lookup.entry)
            _complete_record(lookup.entry.key)
            _complete_record(lookup.entry.key.contract)
        except Exception as exc:
            raise _failure(op, CacheFailureReason.INVALID_PAYLOAD, "Invalid lookup", CacheIssueCode.INVALID_VALUE) from exc
        if lookup.entry.key != key:
            raise _failure(op, CacheFailureReason.CONTRACT_MISMATCH, "Wrong lookup key", CacheIssueCode.CONTRACT_VIOLATION)
        validated, _ = self._admit(op, lookup.entry)
        return CacheHit[T](entry=validated)

    def create[T](self, entry: CacheEntry[T]) -> CacheCreateResult:
        op = CacheOperation.CREATE
        validated, binding = self._admit(op, entry)
        try:
            cost = binding.codec.retained_bytes(validated.value)
            if type(cost) is not int or cost < 0:
                raise ValueError("invalid retention cost")
            cost = max(cost, retained_entry_bytes(validated))
        except Exception as exc:
            raise _failure(op, CacheFailureReason.INVALID_PAYLOAD, "Invalid retention cost", CacheIssueCode.INVALID_VALUE) from exc
        with _backend_call(op):
            return CacheCreateResult(outcome=self._backend.create(validated, binding.codec, cost))

    def update[T](self, entry: CacheEntry[T]) -> CacheUpdateResult:
        validated, binding = self._admit(CacheOperation.UPDATE, entry)
        with _backend_call(CacheOperation.UPDATE):
            return CacheUpdateResult(outcome=self._backend.update(validated, binding.codec))

    def evict[T](self, key: CacheKey[T]) -> CacheEvictResult:
        self._binding(CacheOperation.EVICT, key)
        with _backend_call(CacheOperation.EVICT):
            return CacheEvictResult(outcome=self._backend.evict(key))
