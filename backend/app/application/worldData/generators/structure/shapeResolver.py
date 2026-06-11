from app.application.worldData.generators.structure.shapeType import ShapeType

_SQUARE_SIZE_TYPES: frozenset[str] = frozenset({
    "sq_small", "sq_medium", "sq_large",
    "spiral_3", "spiral_4", "spiral_5",
})


class SizeShapeResolver:
    """Выводит ShapeType из size-определения когда shape_type явно не задан."""

    @classmethod
    def from_size_def(cls, size: dict) -> ShapeType:
        size_type = size.get("size_type")
        if size_type:
            return cls.from_size_type(size_type)
        return cls.from_ranges(
            size.get("width_range", [1, 1]),
            size.get("depth_range"),
        )

    @classmethod
    def from_size_type(cls, size_type: str) -> ShapeType:
        if size_type in _SQUARE_SIZE_TYPES:
            return ShapeType.SQUARE
        return ShapeType.RECTANGLE

    @classmethod
    def from_ranges(
        cls,
        width_range: list[int],
        depth_range: list[int] | None,
    ) -> ShapeType:
        if depth_range is None:
            return ShapeType.RECTANGLE
        if width_range == depth_range:
            return ShapeType.SQUARE
        return ShapeType.RECTANGLE
