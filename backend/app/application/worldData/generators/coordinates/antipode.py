"""Antipode mapping for closed planet grid (M-1)."""

from app.application.worldData.generators.climate.climatePoleField import GridBBox


def antipode_xy(gx: int, gy: int, bbox: GridBBox) -> tuple[int, int]:
    """
    Opposite point on a closed rectangular planet grid.
    Uses half-width/half-height offset with wrap within bbox.
    """
    width  = bbox.x_max - bbox.x_min + 1
    height = bbox.y_max - bbox.y_min + 1
    lx     = gx - bbox.x_min
    ly     = gy - bbox.y_min
    ax     = bbox.x_min + (lx + width // 2) % width
    ay     = bbox.y_min + (ly + height // 2) % height
    return ax, ay
