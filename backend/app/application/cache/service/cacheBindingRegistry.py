"""Composition-time codec registration for a single cache instance."""
from collections.abc import Iterable
from typing import Any, cast

from app.application.cache.contracts.cacheBackend import CacheBinding
from app.dataModel.cache.contracts.cacheContract import CacheContract, CacheContractMetadata
from app.dataModel.cache.contracts.cacheError import CacheIssueCode
from app.dataModel.validation.immutableValue import _complete_record


class CacheBindingResolutionError(ValueError):
    def __init__(self, code: CacheIssueCode):
        self.code = code
        super().__init__(code.value)


class CacheBindingRegistry:
    def __init__(self, bindings: Iterable[CacheBinding[Any]]):
        entries: dict[str, CacheBinding[Any]] = {}
        for binding in bindings:
            contract = binding.contract
            _complete_record(contract)
            CacheContractMetadata.model_validate(contract, strict=True)
            if contract.id in entries:
                raise ValueError(f"duplicate cache contract id: {contract.id}")
            entries[contract.id] = binding
        self._entries = entries

    def resolve[T](self, contract: CacheContract[T]) -> CacheBinding[T]:
        _complete_record(contract)
        CacheContractMetadata.model_validate(contract, strict=True)
        binding = self._entries.get(contract.id)
        if binding is None:
            raise CacheBindingResolutionError(CacheIssueCode.UNKNOWN_NAMESPACE)
        if contract.schema_version != binding.contract.schema_version:
            raise CacheBindingResolutionError(CacheIssueCode.SCHEMA_VERSION_MISMATCH)
        # Namespace and version select the trusted codec; it admits the actual payload.
        return cast(CacheBinding[T], binding)
