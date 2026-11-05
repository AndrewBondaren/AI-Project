"""Every marked line must produce its specified pyright diagnostic."""

from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper

from tests.typing.errorContracts.models import (
    INP_METADATA, INP_NAME, INP_TAGS, META_SOURCE, OTHER_NUMBER,
    FixtureTypeError, Inp, OtherCode,
)


def invalid_paths() -> None:
    root = CheckedPath.root(Inp)
    root.field(INP_METADATA).field(META_SOURCE)  # EXPECT: reportAttributeAccessIssue
    root.field(OTHER_NUMBER)  # EXPECT: reportArgumentType
    root.field(INP_TAGS).item(0)  # EXPECT: reportAttributeAccessIssue
    root.field(INP_NAME).item(0)  # EXPECT: reportAttributeAccessIssue
    root.field(INP_TAGS).key(1)  # EXPECT: reportArgumentType


def invalid_issue_and_collector(other: object) -> None:
    FixtureTypeError(code=OtherCode.BROKEN, path=CheckedPath.root(Inp).field(INP_NAME).freeze(), message="x")  # EXPECT: reportArgumentType
    collector = ValidatorAggregationHelper((FixtureTypeError,))
    collector.add(other)  # EXPECT: reportArgumentType
