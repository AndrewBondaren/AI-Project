from typing import Annotated

from pydantic import Field

from .point import MAX_SECONDS, Nano, TimeRecord

type U63 = Annotated[int, Field(ge=0, le=MAX_SECONDS)]


class TimeDuration(TimeRecord):
    seconds: U63
    nanoseconds: Nano
