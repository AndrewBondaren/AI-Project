from enum import Enum


class StaircaseType(str, Enum):
    def __str__(self) -> str:
        return self.value

    STRAIGHT               = "straight"
    U_SHAPE                = "u_shape"
    SPIRAL                 = "spiral"
    VERTICAL_LADDER        = "vertical_ladder"
    EXTERNAL_VERTICAL_LADDER = "external_vertical_ladder"
