"""Typed storage boundary; world currency and domain planning belong to callers."""

from dataclasses import fields, is_dataclass
from enum import Enum, StrEnum
from math import isfinite
from sys import getsizeof

from pydantic import BaseModel

from app.application.cache.contracts.cacheBackend import CacheBackend, CacheBinding
from app.dataModel.cache.contracts.cacheContract import CacheContractMetadata
from app.dataModel.cache.contracts.cacheEntry import CacheAdmission, CacheEntry
from app.dataModel.cache.contracts.cacheLookup import CacheHit, CacheLookup, CacheMiss
from app.dataModel.cache.identity.cacheKey import CacheKey
from app.dataModel.cache.policy.cachePolicy import CachePolicy
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class CacheFailureReason(StrEnum):
    CONTRACT_MISMATCH = "contract_mismatch"
    INVALID_PAYLOAD = "invalid_payload"
    BACKEND_FAILURE = "backend_failure"


class CacheFailure(Exception):
    def __init__(self, reason: CacheFailureReason, issues: tuple[FieldPathError, ...]):
        self.reason = reason
        self.issues = issues
        super().__init__(reason.value)


def _failure(reason: CacheFailureReason, message: str) -> CacheFailure:
    return CacheFailure(reason, (FieldPathError(("cache",), message),))


def _complete_record(value: BaseModel) -> None:
    """Instance revalidation alone may silently restore missing default fields."""
    if set(vars(value)) != set(type(value).model_fields) or value.model_extra:
        raise ValueError("missing or extra record fields")


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


def _immutable(value: object, active: set[int]) -> None:
    """Reject shared mutable state, opaque live objects and cyclic graphs."""
    if value is None or isinstance(value, (str, bytes, bool, int)):
        return
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("non-finite cached number")
        return
    if isinstance(value, Enum):
        _immutable(value.value, active)
        return
    identity = id(value)
    if identity in active:
        raise ValueError("cyclic cached payload")
    active.add(identity)
    try:
        if isinstance(value, (tuple, frozenset)):
            for child in value:
                _immutable(child, active)
        elif isinstance(value, BaseModel):
            if not type(value).model_config.get("frozen"):
                raise ValueError("mutable cached model")
            _complete_record(value)
            for name in type(value).model_fields:
                _immutable(getattr(value, name), active)
        elif is_dataclass(value) and not isinstance(value, type):
            if not getattr(type(value), "__dataclass_params__").frozen:
                raise ValueError("mutable cached dataclass")
            if hasattr(value, "__dict__") and set(vars(value)) != {field.name for field in fields(value)}:
                raise ValueError("missing or extra dataclass fields")
            for field in fields(value):
                _immutable(getattr(value, field.name), active)
        else:
            raise ValueError("unsupported or mutable cached value")
    finally:
        active.remove(identity)


def validate_immutable(value: object) -> None:
    """Public admission check for complete, immutable records and nested values."""
    _immutable(value, set())


class CacheService:
    def __init__(self, backend: CacheBackend, policy: CachePolicy):
        self._backend = backend
        self._policy = CachePolicy.model_validate(policy)

    def _key[T](self, binding: CacheBinding[T], key: CacheKey[T]) -> CacheKey[T]:
        try:
            _complete_record(binding.contract)
            _complete_record(key)
            _complete_record(key.contract)
            CacheContractMetadata.model_validate(binding.contract)
            validated = type(key).model_validate(key)
            if validated.contract != binding.contract:
                raise ValueError("key does not match the supplied cache binding")
            return validated
        except Exception as exc:
            raise _failure(CacheFailureReason.CONTRACT_MISMATCH, str(exc)) from exc

    def _entry[T](self, binding: CacheBinding[T], entry: CacheEntry[T],
                  expected: CacheKey[T]) -> CacheEntry[T]:
        try:
            _complete_record(entry)
        except Exception as exc:
            raise _failure(CacheFailureReason.INVALID_PAYLOAD, str(exc)) from exc
        key = self._key(binding, entry.key)
        if key != expected:
            raise _failure(CacheFailureReason.CONTRACT_MISMATCH, "backend returned a different cache key")
        try:
            # The codec checks concrete schema invariants, even on already-typed
            # values. The service independently enforces immutable admission.
            _immutable(entry.value, set())
            value = binding.codec.validate(entry.value)
            _immutable(value, set())
            return CacheEntry[T](key=key, value=value)
        except Exception as exc:
            raise _failure(CacheFailureReason.INVALID_PAYLOAD, str(exc)) from exc

    def get[T](self, binding: CacheBinding[T], key: CacheKey[T]) -> CacheLookup[T]:
        expected = self._key(binding, key)
        try:
            lookup = self._backend.get(expected)
        except Exception as exc:
            raise _failure(CacheFailureReason.BACKEND_FAILURE, str(exc)) from exc
        try:
            _complete_record(lookup)
            # Revalidate the discriminator as well as the actual record shape.
            type(lookup).model_validate(lookup)
        except Exception as exc:
            raise _failure(CacheFailureReason.INVALID_PAYLOAD, str(exc)) from exc
        if isinstance(lookup, CacheMiss):
            return CacheMiss()
        if isinstance(lookup, CacheHit):
            return CacheHit[T](entry=self._entry(binding, lookup.entry, expected))
        raise _failure(CacheFailureReason.INVALID_PAYLOAD, "invalid backend lookup")

    def put[T](self, binding: CacheBinding[T], entry: CacheEntry[T]) -> CacheAdmission:
        try:
            _complete_record(entry)
        except Exception as exc:
            raise _failure(CacheFailureReason.INVALID_PAYLOAD, str(exc)) from exc
        expected = self._key(binding, entry.key)
        validated = self._entry(binding, entry, expected)
        try:
            cost = binding.codec.retained_bytes(validated.value)
            if type(cost) is not int or cost < 0:
                raise ValueError("retained byte cost must be a nonnegative integer")
            cost = max(cost, retained_entry_bytes(validated))
        except Exception as exc:
            raise _failure(CacheFailureReason.INVALID_PAYLOAD, str(exc)) from exc
        if cost > self._policy.max_entry_bytes:
            return CacheAdmission.SKIPPED_OVERSIZE
        try:
            self._backend.put(validated)
        except Exception as exc:
            raise _failure(CacheFailureReason.BACKEND_FAILURE, str(exc)) from exc
        return CacheAdmission.STORED

    def evict[T](self, binding: CacheBinding[T], key: CacheKey[T]) -> None:
        expected = self._key(binding, key)
        try:
            self._backend.evict(expected)
        except Exception as exc:
            raise _failure(CacheFailureReason.BACKEND_FAILURE, str(exc)) from exc
