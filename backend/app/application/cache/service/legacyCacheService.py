"""LEGACY REMOVE(CACHE-V1-BINDING): caller-bound cache used until Planning cutover."""
from app.application.cache.contracts.cacheBackend import CacheBinding, LegacyCacheBackend
from app.application.cache.service.cacheService import retained_entry_bytes
from app.dataModel.cache.contracts.cacheContract import CacheContractMetadata
from app.dataModel.cache.contracts.cacheEntry import CacheAdmission, CacheEntry
from app.dataModel.cache.contracts.cacheError import CacheFailureReason
from app.dataModel.cache.contracts.cacheLookup import CacheHit, CacheLookup, CacheMiss
from app.dataModel.cache.identity.cacheKey import CacheKey
from app.dataModel.cache.policy.cachePolicy import CachePolicy
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.immutableValue import _complete_record, _immutable


class CacheFailure(Exception):
    def __init__(self, reason: CacheFailureReason, issues: tuple[FieldPathError, ...]):
        self.reason = reason
        self.issues = issues
        super().__init__(reason.value)


def _failure(reason: CacheFailureReason, message: str) -> CacheFailure:
    return CacheFailure(reason, (FieldPathError(("cache",), message),))


class CacheService:
    # LEGACY REMOVE(CACHE-V1-BINDING): migrate get/put/evict from caller-supplied
    # bindings to Cache-owned resolution. See .cursor/plans/cache-public-contracts.md.
    def __init__(self, backend: LegacyCacheBackend, policy: CachePolicy):
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
