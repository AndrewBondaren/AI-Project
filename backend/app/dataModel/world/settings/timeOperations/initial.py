from typing import Annotated, Literal

from pydantic import Field

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictOnWire
from app.dataModel.identity.uid import EntityUid
from app.dataModel.world.calendar.dates.anchor import CalendarOrigin
from app.dataModel.world.calendar.enums.rules import CalendarInitializationKind
from app.dataModel.world.calendar.projection.request import CalendarBudget
from app.dataModel.world.calendar.scalars import CalendarRecord, Nat, Pos
from app.dataModel.world.settings.timeSettings import WorldTimeSettings
from app.dataModel.worldSnapshot.metadata.envelope import CreatedAtUtc


class StandardTimeSettingsInput(CalendarRecord):
    kind: StrictOnWire[Literal[CalendarInitializationKind.STANDARD]]
    hours_per_day: DefaultWhenMissing[Pos] = WorldTimeSettings.model_fields["hours_per_day"].default
    origin: DefaultWhenMissing[CalendarOrigin | None] = None


class AuthoredTimeSettingsInput(CalendarRecord):
    kind: StrictOnWire[Literal[CalendarInitializationKind.AUTHORED]]
    settings: StrictOnWire[WorldTimeSettings]


type InitialInput = Annotated[StandardTimeSettingsInput | AuthoredTimeSettingsInput, Field(discriminator="kind")]


class PrepareInitialSettings(CalendarRecord):
    operation_id: EntityUid
    world_uid: EntityUid
    input: InitialInput
    captured_utc: CreatedAtUtc
    budget: CalendarBudget


class PreparedInitialSettings(CalendarRecord):
    operation_id: EntityUid
    world_uid: EntityUid
    settings: WorldTimeSettings
    captured_utc: CreatedAtUtc


class InitialAnchorRequired(CalendarRecord):
    hours_per_day: Pos
    captured_hour: Nat
