"""Reusable interior geometry template (5o split) — shared global library SoT.

``system_name`` is the template uid: a UUID string, globally unique, equal to
``structure_templates.template_uid`` in SQL (model A — no ``owner_world_uid``,
no SQL ``system_name`` column). ``display_name`` is human-readable, not unique.

``levels`` / ``staircases`` / ``connections`` stay ``list[dict]`` (POJO-D-16 /
JV-4b). Do not reuse ``BuildingTemplateRoomSlot`` as a generate room.

Purpose aggregation — tz_building_generator.md §3.4b: ``levels[].purpose``
is the default for the level's rooms; ``rooms[].purpose`` overrides, explicit
``null`` marks a service room. ``structure_types`` on wire is the authority
(derived ⊆ explicit); omitted → derived from rooms, empty → ``[house]``.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.constrainedField import constrained_field
from app.dataModel.registryKey import RegistryKey
from app.dataModel.locations.structure.building.roomConnection import RoomConnection
from app.dataModel.locations.structure.building.staircaseSpec import StaircaseSpec
from app.dataModel.locations.structure.building.levelDef import LevelDef, validate_room_ids
from app.dataModel.locations.structure.room.entryPoint import EntryPoint
from app.dataModel.locations.structure.enums.buildingPurpose import (
    DEFAULT_BUILDING_PURPOSES,
    BuildingPurpose,
    BuildingPurposeFamily,
    coerce_purpose_list,
)

DEFAULT_Z_HEIGHT = 3
DEFAULT_DOOR_HEIGHT_RATIO = 0.75
DEFAULT_DOOR_HEIGHT_MAX = 5


def _leaf_purpose(raw: Any, context: str) -> BuildingPurpose:
    parsed = BuildingPurpose.from_wire(raw)
    if parsed is None or isinstance(parsed, BuildingPurposeFamily):
        raise ValueError(
            f"{context}: purpose '{raw}' must be a BuildingPurpose leaf"
        )
    return parsed


class StructureTemplate(BaseModel):
    """Building interior geometry — levels/rooms, staircases, connections."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_name: StrictOnWire[RegistryKey[StructureTemplate]]
    display_name: StrictOnWire[str]
    description: DefaultOnWire[str | None] = None
    version: DefaultOnWire[str] = "1.0"
    structure_types: DefaultOnWire[list[BuildingPurpose]] = Field(
        default_factory=lambda: coerce_purpose_list(None),
    )
    default_z_height: DefaultOnWire[int] = constrained_field(
        default=DEFAULT_Z_HEIGHT, greater_equals=1,
    )
    door_height_ratio: DefaultOnWire[float] = constrained_field(
        default=DEFAULT_DOOR_HEIGHT_RATIO, greater=0, lesser_equals=1,
    )
    door_height_max: DefaultOnWire[int] = constrained_field(
        default=DEFAULT_DOOR_HEIGHT_MAX, greater_equals=1,
    )
    levels: DefaultOnWire[list[dict[str, Any]]] = Field(default_factory=list)
    staircases: DefaultOnWire[list[dict[str, Any]]] = Field(default_factory=list)
    connections: DefaultOnWire[list[dict[str, Any]]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_structure_wire(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        raw = payload.get("structure_types")
        if raw is None:
            raw = payload.get("structure_type")
        explicit = coerce_purpose_list(raw, empty_as_house=False)
        if explicit:
            payload["structure_types"] = explicit
        else:
            # omit / [] / all-dropped → keep absent so the after-validator
            # can detect "not given on wire" via model_fields_set (§3.4b).
            payload.pop("structure_types", None)
        return payload

    @model_validator(mode="after")
    def _derive_structure_purposes(self) -> StructureTemplate:
        pairs = self._effective_room_purposes()
        derived: list[BuildingPurpose] = []
        for _room_id, purpose in pairs:
            if purpose not in derived:
                derived.append(purpose)
        if "structure_types" in self.model_fields_set:
            for room_id, purpose in pairs:
                if purpose not in self.structure_types:
                    raise ValueError(
                        f"room '{room_id}': purpose '{purpose}' "
                        "не объявлен в structure_types здания"
                    )
        else:
            object.__setattr__(
                self,
                "structure_types",
                derived or list(DEFAULT_BUILDING_PURPOSES),
            )
        return self

    @model_validator(mode="after")
    def _validate_levels(self) -> StructureTemplate:
        parsed = []
        for index, level in enumerate(self.levels):
            try:
                parsed.append(LevelDef.model_validate(level))
            except ValidationError as exc:
                raise ValueError(f"levels[{index}]: {exc}") from exc
        validate_room_ids(parsed)
        return self

    @model_validator(mode="after")
    def _validate_connections(self) -> StructureTemplate:
        for index, conn in enumerate(self.connections):
            try:
                RoomConnection.model_validate(conn)
            except ValidationError as exc:
                raise ValueError(f"connections[{index}]: {exc}") from exc
        return self

    @model_validator(mode="after")
    def _validate_staircases(self) -> StructureTemplate:
        for index, sc in enumerate(self.staircases):
            try:
                StaircaseSpec.model_validate(sc)
            except ValidationError as exc:
                raise ValueError(f"staircases[{index}]: {exc}") from exc
        return self

    @model_validator(mode="after")
    def _validate_entry_points(self) -> StructureTemplate:
        for level in self.levels:
            rooms = level.get("rooms")
            if not isinstance(rooms, list):
                continue
            for room in rooms:
                if not isinstance(room, dict):
                    continue
                for field in ("entry_point", "back_entry_point"):
                    entry = room.get(field)
                    if entry is None:
                        continue
                    try:
                        EntryPoint.model_validate(entry)
                    except ValidationError as exc:
                        raise ValueError(
                            f"room '{room.get('room_id')}' {field}: {exc}"
                        ) from exc
        return self

    @field_validator("system_name", mode="after")
    @classmethod
    def _system_name_is_uuid(cls, value: Any) -> Any:
        try:
            canonical = str(uuid.UUID(str(value)))
        except (ValueError, AttributeError, TypeError) as exc:
            raise ValueError(
                "StructureTemplate.system_name must be a UUID (model A)"
            ) from exc
        return type(value)(canonical)

    def _effective_room_purposes(self) -> list[tuple[str | None, BuildingPurpose]]:
        """(room_id, effective purpose) — room.purpose ?? level.purpose ?? service."""
        pairs: list[tuple[str | None, BuildingPurpose]] = []
        for level in self.levels:
            level_purpose: BuildingPurpose | None = None
            if "purpose" in level and level.get("purpose") is not None:
                level_purpose = _leaf_purpose(
                    level.get("purpose"),
                    f"level z_offset={level.get('z_offset')}",
                )
            rooms = level.get("rooms")
            if not isinstance(rooms, list):
                continue
            for room in rooms:
                if not isinstance(room, dict):
                    continue
                room_id = room.get("room_id")
                if "purpose" in room:
                    raw = room.get("purpose")
                    if raw is None:
                        continue
                    purpose = _leaf_purpose(
                        raw, f"room '{room_id}'",
                    )
                else:
                    purpose = level_purpose
                if purpose is not None:
                    pairs.append(
                        (str(room_id) if room_id is not None else None, purpose)
                    )
        return pairs

    def room_purposes(self) -> dict[str, BuildingPurpose]:
        """room_id → effective purpose; service rooms (effective None) omitted."""
        return {
            room_id: purpose
            for room_id, purpose in self._effective_room_purposes()
            if room_id is not None
        }


type StructureKey = RegistryKey[StructureTemplate]
StructureTemplate.model_rebuild()
