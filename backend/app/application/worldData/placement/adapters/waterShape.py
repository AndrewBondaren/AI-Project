"""Existing spatial primitives, sampled in their authored unrolled frame."""

from functools import partial

from app.application.worldData.masks.regionRasterNoise import boundary_depth, smooth_field
from app.application.worldData.placement.adapters.waterTypes import WaterGeometryError, WaterPlacementContext
from app.dataModel.spatial.regionShape import AnchorRadiusShape, EllipseShape, RegionShape
from app.ids import RegionRngChannel, UidKind, seed_rng, seed_root


def shape_cells(shape: RegionShape, source_uid: str,
                context: WaterPlacementContext) -> tuple[frozenset[tuple[int, int]], float]:
    area = shape.area()
    if isinstance(shape, AnchorRadiusShape):
        anchor = context.anchors.get(shape.anchor_uid)
        if anchor is None:
            raise WaterGeometryError(f"anchor {shape.anchor_uid} is not ready")
        shape = EllipseShape(cx=anchor[0], cy=anchor[1], rx=shape.radius, ry=shape.radius,
                             edge_noise=shape.edge_noise)
    topology = context.topology
    edge = shape.edge_noise
    noise = None
    if edge is not None and edge.amplitude:
        sample = partial(seed_rng, seed_root(context), UidKind.REGION,
                         channel=RegionRngChannel.EDGE, uid=source_uid)
        noise = smooth_field(lambda **keys: sample(**keys).random(), edge.scale, topology)
    x0, y0, x1, y1 = shape.bbox()
    cells = set()
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            if not shape.contains(x, y):
                continue
            canonical = topology.canonicalize(x, y)
            if canonical is None:
                raise WaterGeometryError("authored footprint extends outside planar world; clipping is forbidden")
            if noise is None or boundary_depth(shape, x, y) >= edge.amplitude * noise(*canonical):
                cells.add(canonical)
    if not cells:
        raise WaterGeometryError("footprint has no fine cells")
    return frozenset(cells), area
