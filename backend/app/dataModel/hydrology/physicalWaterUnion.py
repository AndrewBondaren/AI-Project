"""Physical producer facts; W/L owns lifecycle records and their persistence."""

from typing import Self

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictOnWire


class PhysicalWaterUnion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    water_system_uid: StrictOnWire[str]
    member_uids: StrictOnWire[tuple[str, ...]]
    child_system_uids: StrictOnWire[tuple[str, ...]]
    z_water_level: StrictOnWire[int]
    parent_system_uid: DefaultWhenMissing[str | None] = None

    def with_identity(self, water_system_uid: str, member_uids: tuple[str, ...]) -> Self:
        return type(self).model_validate(self.model_dump(round_trip=True, by_alias=True) | {
            "water_system_uid": water_system_uid, "member_uids": member_uids,
        })

    def with_parent_system(self, parent_system_uid: str | None) -> Self:
        return type(self).model_validate(self.model_dump(round_trip=True, by_alias=True) | {
            "parent_system_uid": parent_system_uid,
        })

    def with_child_systems(self, child_system_uids: tuple[str, ...]) -> Self:
        return type(self).model_validate(self.model_dump(round_trip=True, by_alias=True) | {
            "child_system_uids": child_system_uids,
        })

    def with_water_level(self, z_water_level: int) -> Self:
        return type(self).model_validate(self.model_dump(round_trip=True, by_alias=True) | {
            "z_water_level": z_water_level,
        })
