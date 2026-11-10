import json
import unittest

from pydantic import ValidationError

from app.application.cache.contracts.cacheBackend import CacheBinding
from app.application.cache.service.cacheBindingRegistry import CacheBindingRegistry, CacheBindingResolutionError
from app.dataModel.cache.contracts.cacheCreateResult import CacheCreateResult
from app.dataModel.cache.contracts.cacheEntry import CacheAdmission
from app.dataModel.cache.contracts.cacheError import (
    CacheContractIssue, CacheError, CacheFailureReason, CacheFieldIssue, CacheIssueCode, CacheOperation,
)
from app.dataModel.cache.contracts.cacheEvictResult import CacheEvictOutcome, CacheEvictResult
from app.dataModel.cache.contracts.cacheUpdateResult import CacheUpdateOutcome, CacheUpdateResult
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.worldPack.bake.worldPackCacheSettings import WorldPackCacheSettings
from tests.cache.test_memory_backend import BytesCodec, entry


class CacheV2ContractsTests(unittest.TestCase):
    def test_result_wire(self):
        for model, outcomes in ((CacheCreateResult, CacheAdmission), (CacheUpdateResult, CacheUpdateOutcome),
                                (CacheEvictResult, CacheEvictOutcome)):
            for outcome in outcomes:
                result = model(outcome=outcome)
                self.assertEqual(json.loads(result.model_dump_json()), {"outcome": outcome.value})
                self.assertEqual(model.model_validate_json(result.model_dump_json()), result)
            for raw in ({}, {"outcome": "unknown"}, {"outcome": next(iter(outcomes)).value, "extra": 1}):
                with self.assertRaises(ValidationError):
                    model.model_validate_json(json.dumps(raw))

    def test_error_round_trip(self):
        path = CheckedPath.root(CacheError).field(FieldRef(lambda: CacheError, lambda err: err.message)).freeze()
        issue = CacheFieldIssue(code=CacheIssueCode.INVALID_VALUE, path=path, message="invalid field")
        conflict = CacheContractIssue(code=CacheIssueCode.KEY_OCCUPIED_DIFFERENT_VALUE, message="occupied")
        for reason, issues in ((CacheFailureReason.INVALID_PAYLOAD, (issue,)),
                               (CacheFailureReason.CONTRACT_MISMATCH, (conflict,)),
                               (CacheFailureReason.BACKEND_FAILURE, ())):
            error = CacheError(reason=reason, operation=CacheOperation.CREATE, message="failed", issues=issues)
            restored = CacheError.model_validate_json(error.model_dump_json())
            self.assertEqual(restored, error)
            if issues:
                self.assertIs(type(restored.issues[0]), type(issues[0]))
        for reason, operation in ((CacheFailureReason.BACKEND_FAILURE, CacheOperation.CREATE),
                                  (CacheFailureReason.INVALID_PAYLOAD, CacheOperation.CREATE),
                                  (CacheFailureReason.CONTRACT_MISMATCH, CacheOperation.GET)):
            with self.assertRaises(ValidationError):
                CacheError(reason=reason, operation=operation, message="failed", issues=(conflict,))

    def test_registry_resolution(self):
        key = entry().key
        binding = CacheBinding(key.contract, BytesCodec())
        registry = CacheBindingRegistry((binding,))
        restored = type(key).model_validate_json(key.model_dump_json())
        self.assertIs(registry.resolve(restored.contract), binding)
        wrong_version = entry(version=2).key.contract
        with self.assertRaises(ValueError):
            CacheBindingRegistry((binding, CacheBinding(wrong_version, BytesCodec())))
        for contract, code in ((entry(namespace="domain.other").key.contract, CacheIssueCode.UNKNOWN_NAMESPACE),
                               (wrong_version, CacheIssueCode.SCHEMA_VERSION_MISMATCH)):
            with self.assertRaises(CacheBindingResolutionError) as raised:
                registry.resolve(contract)
            self.assertEqual(raised.exception.code, code)

    def test_pack_requires_explicit_budgets(self):
        settings = WorldPackCacheSettings.model_validate_json(
            '{"manifest_cache":{"max_entry_bytes":20,"max_retained_bytes":100}}')
        self.assertEqual(WorldPackCacheSettings.model_validate_json(settings.model_dump_json()), settings)
        for raw in ({}, {"manifest_cache": {}}, {"manifest_cache": {"max_entry_bytes": 2, "max_retained_bytes": 1}}):
            with self.assertRaises(ValidationError):
                WorldPackCacheSettings.model_validate(raw)
