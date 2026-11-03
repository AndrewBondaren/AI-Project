from enum import StrEnum


class CalendarPredicateKind(StrEnum):
    ALWAYS = "always"
    YEAR_MODULO = "year_modulo"
    YEAR_RANGE = "year_range"


class CalendarEditKind(StrEnum):
    INSERT_SPAN = "insert_span"
    REPLACE_SPAN = "replace_span"
    REMOVE_SPAN = "remove_span"


class CalendarWeekMode(StrEnum):
    CONTINUOUS = "continuous"
    RESET_AT_YEAR = "reset_at_year"


class CalendarNumbering(StrEnum):
    ASTRONOMICAL = "astronomical"
    NO_YEAR_ZERO = "no_year_zero"


class CalendarSpanRole(StrEnum):
    MONTH = "month"
    INTERCALARY = "intercalary"


class CalendarInitializationKind(StrEnum):
    STANDARD = "standard"
    AUTHORED = "authored"


class CalendarConversionKind(StrEnum):
    PROJECT = "project"
    RESOLVE = "resolve"
