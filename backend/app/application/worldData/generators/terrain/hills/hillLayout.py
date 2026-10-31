"""Prepare a hill spatial tree once; draw only accepted features touching a window."""
from collections.abc import Iterator

from app.application.worldData.generators.terrain.hills.hillRaster import raster_hill_window
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.terrain.hills.acceptedHill import AcceptedHill, HillLayout
from app.dataModel.topology.worldTopology import Coord


def build_hill_layout(hills: tuple[AcceptedHill, ...]) -> HillLayout | None:
    if not hills:
        return None
    if len(hills) == 1:
        hill = hills[0]
        x, y = hill.origin
        r = hill.radius
        return HillLayout(bounds=GridBBox(x-r, x+r, y-r, y+r), hill=hill, left=None, right=None)
    xs, ys = [h.origin[0] for h in hills], [h.origin[1] for h in hills]
    axis = 0 if max(xs)-min(xs) >= max(ys)-min(ys) else 1
    ordered = tuple(sorted(hills, key=lambda h: (h.origin[axis], h.origin[1-axis])))
    middle = len(ordered)//2
    left, right = build_hill_layout(ordered[:middle]), build_hill_layout(ordered[middle:])
    assert left is not None and right is not None
    a, b = left.bounds, right.bounds
    return HillLayout(bounds=GridBBox(min(a.x_min,b.x_min), max(a.x_max,b.x_max),
                                     min(a.y_min,b.y_min), max(a.y_max,b.y_max)),
                      hill=None, left=left, right=right)


def hills_for_window(layout: HillLayout | None, bounds: GridBBox) -> Iterator[AcceptedHill]:
    if layout is None:
        return
    b = layout.bounds
    if b.x_max < bounds.x_min or b.x_min > bounds.x_max or b.y_max < bounds.y_min or b.y_min > bounds.y_max:
        return
    if layout.hill is not None:
        yield layout.hill
    else:
        yield from hills_for_window(layout.left, bounds)
        yield from hills_for_window(layout.right, bounds)


def materialize_hills(surface: dict[Coord, int], layout: HillLayout | None, bounds: GridBBox, *,
                      z_min: int, z_max: int) -> None:
    # Only this requested row/window is copied, not its canonical tile.
    base = dict(surface)
    for hill in hills_for_window(layout, bounds):
        for cell, delta in raster_hill_window(hill, bounds).items():
            if cell in surface:
                surface[cell] = max(z_min, min(z_max, max(surface[cell], base[cell]+delta)))
