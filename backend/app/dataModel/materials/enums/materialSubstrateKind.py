"""Material-owned substrate evidence; missing evidence remains unknown."""
from enum import StrEnum


class MaterialSubstrateKind(StrEnum):
    ROCK = "rock"
    LOOSE_SEDIMENT = "loose_sediment"
    OTHER = "other"
