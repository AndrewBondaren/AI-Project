"""Wire measurement system — world platform settings."""

from __future__ import annotations

from enum import StrEnum


class MeasurementSystem(StrEnum):
    METRIC = "metric"
    IMPERIAL = "imperial"
