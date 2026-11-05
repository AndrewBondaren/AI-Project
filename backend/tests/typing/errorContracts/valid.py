"""Positive static contracts of the error core (error-contracts-1 §3.9)."""

from typing import assert_type

from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper

from tests.typing.errorContracts.models import (
    INP_BLOBS, INP_ITEMS, INP_METADATA, INP_NAME, INP_TAGS, INP_VALUES, INP_WEIGHTS,
    ITEM_SOURCE, META_SOURCE, FixtureCode, FixtureTypeError, Inp,
)


def valid_paths() -> None:
    root = CheckedPath.root(Inp)
    assert_type(root, CheckedPath[Inp, Inp])
    assert_type(root.field(INP_NAME), CheckedPath[Inp, str])
    assert_type(root.field(INP_METADATA).present().field(META_SOURCE), CheckedPath[Inp, str])
    assert_type(root.field(INP_ITEMS).item(3).field(ITEM_SOURCE), CheckedPath[Inp, str])
    assert_type(root.field(INP_VALUES).item(0), CheckedPath[Inp, int])
    assert_type(root.field(INP_WEIGHTS).item(0), CheckedPath[Inp, float])
    assert_type(root.field(INP_TAGS).key("a"), CheckedPath[Inp, int])
    assert_type(root.field(INP_BLOBS).key("a"), CheckedPath[Inp, bytes])


def valid_issue_and_collector() -> None:
    issue = FixtureTypeError(
        code=FixtureCode.MISSING,
        path=CheckedPath.root(Inp).field(INP_NAME).freeze(),
        message="name is required",
    )
    assert_type(issue.code, FixtureCode)
    collector = ValidatorAggregationHelper((FixtureTypeError,))
    collector.add(issue)
    assert_type(collector.snapshot(), tuple[FixtureTypeError, ...])
