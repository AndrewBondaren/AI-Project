"""Unrolled round-capped polyline geometry, shared by spatial consumers.

Area is the geometric union of segment rectangles and vertex disks. Green's
formula on exposed boundary pieces avoids raster-area and overlap counting.
"""

from functools import lru_cache
from math import atan2, cos, hypot, pi, sin, sqrt

Point = tuple[float, float]


def segment_distance2(p: Point, a: Point, b: Point) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2)) if length2 else 0
    return (p[0] - a[0] - t * dx) ** 2 + (p[1] - a[1] - t * dy) ** 2


def polyline_distance2(p: Point, path: list[Point]) -> float:
    return min(segment_distance2(p, a, b) for a, b in zip(path, path[1:]))


def _cross(a: Point, b: Point) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _sub(a: Point, b: Point) -> Point:
    return a[0] - b[0], a[1] - b[1]


def _point(a: Point, b: Point, t: float) -> Point:
    return a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])


def _line_cuts(a: Point, b: Point, c: Point, d: Point) -> list[float]:
    v, w, delta = _sub(b, a), _sub(d, c), _sub(c, a)
    det = _cross(v, w)
    if abs(det) > 1e-12 * hypot(*v) * hypot(*w):
        t, u = _cross(delta, w) / det, _cross(delta, v) / det
        return [t] if 0 <= t <= 1 and 0 <= u <= 1 else []
    if abs(_cross(delta, v)) > 1e-10 * hypot(*v):
        return []
    length2 = v[0] ** 2 + v[1] ** 2
    return [t for p in (c, d) if 0 <= (t := sum(x * y for x, y in zip(_sub(p, a), v)) / length2) <= 1]


def _disk_cuts(a: Point, b: Point, center: Point, radius: float) -> list[float]:
    v, offset = _sub(b, a), _sub(a, center)
    aa = v[0] ** 2 + v[1] ** 2
    bb = 2 * sum(x * y for x, y in zip(v, offset))
    cc = offset[0] ** 2 + offset[1] ** 2 - radius ** 2
    disc = bb * bb - 4 * aa * cc
    if disc < 0:
        return []
    return [t for sign in (-1, 1) if 0 <= (t := (-bb + sign * sqrt(disc)) / (2 * aa)) <= 1]


def _rect_distance(p: Point, vertices: tuple[Point, ...]) -> float:
    return -min(_cross(_sub(b, a), _sub(p, a)) / hypot(*_sub(b, a))
                for a, b in zip(vertices, vertices[1:] + vertices[:1]))


@lru_cache(maxsize=256)
def corridor_area(path: tuple[Point, ...], width: int) -> float:
    """Exact curved-boundary union area, including bends, crossings and retrace."""
    origin = path[0]
    points = [_sub(p, origin) for p in path]
    radius = width / 2
    disks = list(dict.fromkeys(points))
    rectangles = []
    seen = set()
    for a, b in zip(points, points[1:]):
        key = tuple(sorted((a, b)))
        if a == b or key in seen:
            continue
        seen.add(key)
        dx, dy = _sub(b, a)
        length = hypot(dx, dy)
        nx, ny = -dy * radius / length, dx * radius / length
        rectangles.append(((a[0] - nx, a[1] - ny), (b[0] - nx, b[1] - ny),
                           (b[0] + nx, b[1] + ny), (a[0] + nx, a[1] + ny)))
    lines = [(i, a, b) for i, vertices in enumerate(rectangles)
             for a, b in zip(vertices, vertices[1:] + vertices[:1])]
    epsilon = radius * 1e-8

    def exposed(p: Point, outward: Point, owner: int) -> bool:
        for i in range(len(rectangles) + len(disks)):
            if i == owner:
                continue

            def distance(q: Point) -> float:
                if i < len(rectangles):
                    return _rect_distance(q, rectangles[i])
                return hypot(*_sub(q, disks[i - len(rectangles)])) - radius

            depth = distance(p)
            if depth < -epsilon:
                return False
            if abs(depth) <= epsilon:
                probe = p[0] + outward[0] * epsilon * 4, p[1] + outward[1] * epsilon * 4
                if distance(probe) < -epsilon or i < owner:
                    return False
        return True

    area2 = 0.0
    for owner, a, b in lines:
        cuts = {0.0, 1.0}
        for other, c, d in lines:
            if other != owner:
                cuts.update(_line_cuts(a, b, c, d))
        for center in disks:
            cuts.update(_disk_cuts(a, b, center, radius))
        dx, dy = _sub(b, a)
        length = hypot(dx, dy)
        outward = dy / length, -dx / length
        ordered = sorted(cuts)
        for low, high in zip(ordered, ordered[1:]):
            if exposed(_point(a, b, (low + high) / 2), outward, owner):
                area2 += _cross(_point(a, b, low), _point(a, b, high))

    for index, center in enumerate(disks):
        owner = len(rectangles) + index
        angles = {0.0, 2 * pi}
        for _, a, b in lines:
            for t in _disk_cuts(a, b, center, radius):
                q = _sub(_point(a, b, t), center)
                angles.add(atan2(q[1], q[0]) % (2 * pi))
        for other in disks:
            delta = _sub(other, center)
            distance = hypot(*delta)
            if not 0 < distance <= 2 * radius:
                continue
            midpoint = (center[0] + other[0]) / 2, (center[1] + other[1]) / 2
            height = sqrt(max(0, radius ** 2 - distance ** 2 / 4))
            for sign in (-1, 1):
                q = (midpoint[0] - sign * delta[1] * height / distance - center[0],
                     midpoint[1] + sign * delta[0] * height / distance - center[1])
                angles.add(atan2(q[1], q[0]) % (2 * pi))
        ordered = sorted(angles)
        for low, high in zip(ordered, ordered[1:]):
            mid = (low + high) / 2
            outward = cos(mid), sin(mid)
            p = center[0] + radius * outward[0], center[1] + radius * outward[1]
            if exposed(p, outward, owner):
                area2 += (radius * center[0] * (sin(high) - sin(low))
                          - radius * center[1] * (cos(high) - cos(low))
                          + radius ** 2 * (high - low))
    return max(0.0, area2 / 2)
