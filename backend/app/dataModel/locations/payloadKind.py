"""Builtin payload contracts; location type names remain world data."""

from enum import StrEnum


class PayloadKind(StrEnum):
    SETTLEMENT = "settlement"
    DISTRICT = "district"
