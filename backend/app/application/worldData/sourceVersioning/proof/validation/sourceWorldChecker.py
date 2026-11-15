"""Compare presented world identities without resolving sources."""

from pydantic import TypeAdapter

from app.dataModel.identity.uid import EntityUid
from app.dataModel.sourceVersioning.sourceErrors import SourceLogicCode, SourceLogicIssue
from app.dataModel.sourceVersioning.sourceVersionRef import SourceCollectionVersionRef, SourceVersionRef


class SourceWorldChecker:
    def check(self, actual: EntityUid, *, expected: EntityUid,
              group_index: int | None, use_index: int | None,
              source: SourceVersionRef | SourceCollectionVersionRef | None,
              ) -> tuple[SourceLogicIssue, ...]:
        TypeAdapter(EntityUid).validate_python(actual, strict=True)
        TypeAdapter(EntityUid).validate_python(expected, strict=True)
        for index in (group_index, use_index):
            if index is not None and (type(index) is not int or index < 0):
                raise ValueError("diagnostic index must be a non-negative integer")
        if actual == expected:
            return ()
        return (SourceLogicIssue(code=SourceLogicCode.WRONG_WORLD,
                                 group_index=group_index, use_index=use_index,
                                 source=source, artifact=None),)
