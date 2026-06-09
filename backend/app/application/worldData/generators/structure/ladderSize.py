from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class StaircaseSizePreset:
    width_range: tuple[int, int]
    depth_range: tuple[int, int] | None = None  # None = computed from z_height


# --- straight ---

class StraightSize(str, Enum):
    NARROW      = "narrow"       # 1 interior wide  (room 3×z)
    STANDARD    = "standard"     # 3 interior wide  (room 5×z)
    WIDE        = "wide"         # 5 interior wide  (room 7×z)
    LONG_NARROW = "long_narrow"  # 1 interior wide, длинная (с floor)
    LONG_WIDE   = "long_wide"    # 5 interior wide, длинная (с floor)


STRAIGHT_SIZE_PRESETS: dict[StraightSize, StaircaseSizePreset] = {
    StraightSize.NARROW:      StaircaseSizePreset(width_range=(3, 3)),
    StraightSize.STANDARD:    StaircaseSizePreset(width_range=(5, 5)),
    StraightSize.WIDE:        StaircaseSizePreset(width_range=(7, 7)),
    StraightSize.LONG_NARROW: StaircaseSizePreset(width_range=(3, 3), depth_range=(10, 15)),
    StraightSize.LONG_WIDE:   StaircaseSizePreset(width_range=(7, 7), depth_range=(10, 15)),
}


# --- u_shape ---

class UShapeSize(str, Enum):
    RECT_NARROW   = "rect_narrow"    # 2 interior wide, rectangle
    RECT_STANDARD = "rect_standard"  # 3 interior wide, rectangle
    SQ_SMALL      = "sq_small"       # 3×3 interior (5×5 room)
    SQ_MEDIUM     = "sq_medium"      # 4×4 interior (6×6 room)
    SQ_LARGE      = "sq_large"       # 5×5 interior (7×7 room)


USHAPE_SIZE_PRESETS: dict[UShapeSize, StaircaseSizePreset] = {
    UShapeSize.RECT_NARROW:   StaircaseSizePreset(width_range=(4, 4)),
    UShapeSize.RECT_STANDARD: StaircaseSizePreset(width_range=(5, 5)),
    UShapeSize.SQ_SMALL:      StaircaseSizePreset(width_range=(5, 5), depth_range=(5, 5)),
    UShapeSize.SQ_MEDIUM:     StaircaseSizePreset(width_range=(6, 6), depth_range=(6, 6)),
    UShapeSize.SQ_LARGE:      StaircaseSizePreset(width_range=(7, 7), depth_range=(7, 7)),
}


# --- spiral ---

class SpiralSize(str, Enum):
    SPIRAL_3 = "spiral_3"  # 3×3 void interior (5×5 room)
    SPIRAL_4 = "spiral_4"  # 4×4 void interior (6×6 room)
    SPIRAL_5 = "spiral_5"  # 5×5 void interior (7×7 room)


SPIRAL_SIZE_PRESETS: dict[SpiralSize, StaircaseSizePreset] = {
    SpiralSize.SPIRAL_3: StaircaseSizePreset(width_range=(5, 5), depth_range=(5, 5)),
    SpiralSize.SPIRAL_4: StaircaseSizePreset(width_range=(6, 6), depth_range=(6, 6)),
    SpiralSize.SPIRAL_5: StaircaseSizePreset(width_range=(7, 7), depth_range=(7, 7)),
}
