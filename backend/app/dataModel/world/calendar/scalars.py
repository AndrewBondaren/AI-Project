import re
from typing import Annotated, TypeVar

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.dataModel.registryKey import RegistryKey


class CalendarRecord(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")


type Nat = Annotated[int, Field(ge=0)]
type Pos = Annotated[int, Field(gt=0)]
type Label = Annotated[str, StringConstraints(pattern=r"\S")]


def _valid_key[R](value: RegistryKey[R]) -> RegistryKey[R]:
    import re
    if not re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", value):
        raise ValueError("expected snake_case key")
    return value


# Keep RegistryKey visible to the shared REF-W annotation inspector.
R = TypeVar("R")
Key = Annotated[RegistryKey[R], AfterValidator(_valid_key)]
