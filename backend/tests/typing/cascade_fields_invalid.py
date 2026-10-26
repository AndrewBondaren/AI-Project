"""Expected diagnostics, checked by scripts/check-cascade-types.cjs."""

from pydantic import BaseModel

from app.dataModel.cascade.cascadeSpec import FieldRef


class Source(BaseModel):
    value: str = "value"


class Other(BaseModel):
    number: int = 1


missing = FieldRef(lambda: Source, lambda pojo: pojo.missing)  # expect: reportAttributeAccessIssue
self_missing = FieldRef(lambda: Later, lambda pojo: pojo.missing)  # expect: reportAttributeAccessIssue


class Later(BaseModel):
    value: str = "value"


def wrong_selector(pojo: Other) -> str:
    return str(pojo.number)


wrong_model: FieldRef[Source, str] = FieldRef(lambda: Source, wrong_selector)  # expect: reportArgumentType
wrong_value: FieldRef[Source, int] = FieldRef(lambda: Source, lambda pojo: pojo.value)  # expect: reportAssignmentType
