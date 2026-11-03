from typing import Annotated, Literal

from pydantic import Field

from app.dataModel.annotationPolicy import StrictOnWire
from app.dataModel.world.calendar.scalars import CalendarRecord, Key, Pos
from app.dataModel.world.calendar.catalogs.spans import CalendarSpanRegistry
from app.dataModel.world.calendar.catalogs.seasons import CalendarSeasonRegistry
from app.dataModel.world.calendar.enums.rules import CalendarEditKind
from .predicates import CalendarCondition


class CalendarSpan(CalendarRecord):
    span: StrictOnWire[Key[CalendarSpanRegistry]]
    days: StrictOnWire[Pos]
    counts_in_week: StrictOnWire[bool]
    season: StrictOnWire[Key[CalendarSeasonRegistry] | None]


class InsertSpanRule(CalendarRecord):
    kind: StrictOnWire[Literal[CalendarEditKind.INSERT_SPAN]]
    condition: StrictOnWire[CalendarCondition]
    after: StrictOnWire[Key[CalendarSpanRegistry] | None]
    value: StrictOnWire[CalendarSpan]


class ReplaceSpanRule(CalendarRecord):
    kind: StrictOnWire[Literal[CalendarEditKind.REPLACE_SPAN]]
    condition: StrictOnWire[CalendarCondition]
    value: StrictOnWire[CalendarSpan]


class RemoveSpanRule(CalendarRecord):
    kind: StrictOnWire[Literal[CalendarEditKind.REMOVE_SPAN]]
    condition: StrictOnWire[CalendarCondition]
    span: StrictOnWire[Key[CalendarSpanRegistry]]


type Edit = Annotated[InsertSpanRule | ReplaceSpanRule | RemoveSpanRule, Field(discriminator="kind")]
