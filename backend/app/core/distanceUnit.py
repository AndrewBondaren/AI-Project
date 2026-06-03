from enum import Enum


class DistanceUnit(str, Enum):
    METERS = "meters"
    FEET   = "feet"
    YARDS  = "yards"
