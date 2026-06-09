"""
Spiral staircase — путь по периметру квадратного void-пространства.
ТЗ: docs/tz_staircase_generation.md § 6
"""
from app.application.worldData.generators.structure.staircase._base import StaircaseBuilder


def spiral_perimeter(ax: int, ay: int, W: int, H: int, start: int = 0) -> list[tuple[int, int]]:
    """
    Обход периметра прямоугольника W×H от якоря (ax,ay)=SW-угол по ЧС (N→E→S→W).
    Длина = 2*(W+H)-4. start сдвигает точку входа.
    """
    pts: list[tuple[int, int]] = []
    for dy in range(H):
        pts.append((ax, ay + dy))
    for dx in range(1, W):
        pts.append((ax + dx, ay + H - 1))
    for dy in range(H - 2, -1, -1):
        pts.append((ax + W - 1, ay + dy))
    for dx in range(W - 2, 0, -1):
        pts.append((ax + dx, ay))
    if start:
        n = len(pts)
        s = start % n
        pts = pts[s:] + pts[:s]
    return pts


class SpiralBuilder(StaircaseBuilder):
    def build(self) -> tuple[tuple[int, int], tuple[int, int]]:
        raise NotImplementedError("SpiralBuilder not yet implemented")
