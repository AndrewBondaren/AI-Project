import unittest

from pydantic import ValidationError
from app.dataModel.time.diagnostics.events import (
    REFUSALS, TimeLogOperation, TimeRefusalCode, TimeRefusalLog, TimeCancelledLog, TimeCandidateLog,
)


class TimeLoggingContractTests(unittest.TestCase):
    def test_operation_code_matrix(self):
        for operation in TimeLogOperation:
            for code in TimeRefusalCode:
                fields = dict(operation=operation, code=code, world_uid="world", timeline_id=None,
                              operation_id="operation" if operation is TimeLogOperation.PREPARE_ADVANCE else None,
                              publication_id=None, snapshot=None)
                with self.subTest(operation=operation, code=code):
                    if code in REFUSALS[operation]:
                        TimeRefusalLog.model_validate(fields)
                    else:
                        with self.assertRaises(ValidationError):
                            TimeRefusalLog.model_validate(fields)

    def test_strictness_and_operation_policy(self):
        fields = dict(operation=TimeLogOperation.READ_CURRENT, world_uid="world", timeline_id=None,
                      operation_id=None, publication_id=None, snapshot=None)
        TimeCancelledLog.model_validate(fields)
        for update in ({"operation": "read_current"}, {"world_uid": 1}, {"operation_id": "unexpected"},
                       {"payload": "secret"}, {"activity": "operation_cancelled"}):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                TimeCancelledLog.model_validate(fields | update)

    def test_candidate_coordinates(self):
        fields = dict(world_uid="world", timeline_id="main", operation_id="operation",
                      publication_id=None, snapshot=None, start_seconds=0, start_nanoseconds=0,
                      end_seconds=1, end_nanoseconds=0)
        TimeCandidateLog.model_validate(fields)
        for update in ({"start_seconds": True}, {"end_seconds": 1 << 63},
                       {"end_nanoseconds": 1_000_000_000}, {"start_nanoseconds": -1},
                       {"operation_id": None}, {"operation": TimeLogOperation.READ_CURRENT}):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                TimeCandidateLog.model_validate(fields | update)
