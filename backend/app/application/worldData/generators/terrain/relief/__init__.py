"""Relief grade generators — tz_terrain_relief."""

from app.application.worldData.generators.terrain.relief.bakeSeed import bake_seed
from app.application.worldData.generators.terrain.relief.facing import (
    facing_wire,
    uphill_facing_toward,
)
from app.application.worldData.generators.terrain.relief.gradePass import (
    RibbonGradeDecision,
    grade_from_template,
)
from app.application.worldData.generators.terrain.relief.profiles import (
    profile_side_fraction,
    sheer_band_m,
    sheer_fraction_lateral,
    sheer_fraction_radial,
    slope_fraction,
)
from app.application.worldData.generators.terrain.relief.ribbonSegmentize import (
    RibbonSegment,
    segmentize_by_terrain,
)
from app.application.worldData.generators.terrain.relief.roadShoulderGrade import (
    RoadShoulderGradeResult,
    grade_road_shoulder_segments,
)
from app.application.worldData.generators.terrain.relief.shoulderWidth import (
    expand_shoulder_ring,
    relief_dz,
)
from app.application.worldData.generators.terrain.relief.sideGradeDecision import (
    RadialGradeDecision,
    decide_radial_grade,
    format_sides_summary,
    plateau_hat_decision,
)

__all__ = [
    "RadialGradeDecision",
    "RibbonGradeDecision",
    "RibbonSegment",
    "RoadShoulderGradeResult",
    "bake_seed",
    "decide_radial_grade",
    "expand_shoulder_ring",
    "facing_wire",
    "format_sides_summary",
    "grade_from_template",
    "grade_road_shoulder_segments",
    "plateau_hat_decision",
    "profile_side_fraction",
    "relief_dz",
    "segmentize_by_terrain",
    "sheer_band_m",
    "sheer_fraction_lateral",
    "sheer_fraction_radial",
    "slope_fraction",
    "uphill_facing_toward",
]
