from typing import Literal

from pydantic import field_validator

from app.dataModel.identity.uid import EntityUid
from app.dataModel.time.values.point import TimeRecord


class InitialTimeFacts(TimeRecord):
    world_uid: EntityUid
    seconds: Literal[0]
    nanoseconds: Literal[0]

    @field_validator("seconds", "nanoseconds", mode="before")
    @classmethod
    def strict_zero(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("clock origin requires integer zero")
        return value
