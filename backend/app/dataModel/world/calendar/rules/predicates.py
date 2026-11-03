from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from app.dataModel.annotationPolicy import StrictOnWire
from app.dataModel.world.calendar.scalars import CalendarRecord, Nat, Pos
from app.dataModel.world.calendar.enums.rules import CalendarPredicateKind


class AlwaysPredicate(CalendarRecord):
    kind: StrictOnWire[Literal[CalendarPredicateKind.ALWAYS]]


class YearModuloPredicate(CalendarRecord):
    kind: StrictOnWire[Literal[CalendarPredicateKind.YEAR_MODULO]]
    modulus: StrictOnWire[Pos]
    residue: StrictOnWire[Nat]
    offset: StrictOnWire[int]

    @model_validator(mode="after")
    def valid_residue(self) -> Self:
        if self.residue >= self.modulus:
            raise ValueError("residue exceeds modulus")
        return self


class YearRangePredicate(CalendarRecord):
    kind: StrictOnWire[Literal[CalendarPredicateKind.YEAR_RANGE]]
    first: StrictOnWire[int]
    last: StrictOnWire[int]

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.last < self.first:
            raise ValueError("reversed year range")
        return self


type Predicate = Annotated[AlwaysPredicate | YearModuloPredicate | YearRangePredicate, Field(discriminator="kind")]


class CalendarCondition(CalendarRecord):
    all_of: StrictOnWire[tuple[Predicate, ...]]
    none_of: StrictOnWire[tuple[Predicate, ...]]
