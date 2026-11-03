from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.identity.uid import EntityUid

NANOS_PER_SECOND = 1_000_000_000
MAX_SECONDS = (1 << 63) - 1
type I64 = Annotated[int, Field(ge=-(1 << 63), le=MAX_SECONDS)]
type Nano = Annotated[int, Field(ge=0, lt=NANOS_PER_SECOND)]


class TimeRecord(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")


class TimeScope(TimeRecord):
    world_uid: EntityUid
    timeline_id: EntityUid


class TimePoint(TimeScope):
    seconds: I64
    nanoseconds: Nano

    @property
    def scope(self) -> TimeScope:
        return TimeScope(world_uid=self.world_uid, timeline_id=self.timeline_id)

    @property
    def coordinate(self) -> tuple[int, int]:
        return self.seconds, self.nanoseconds
