from enum import Enum


class ShapeType(str, Enum):
    """
    Форма footprint комнаты. Определяет алгоритм генерации map_cells.

    v1:
      RECTANGLE  — прямоугольник; x ∈ [x0, x0+w) AND y ∈ [y0, y0+d)
      SQUARE     — квадрат; w = d = min(width, depth)
      CIRCLE     — круг; (x−cx)² + (y−cy)² ≤ r²; r = width/2;
                   chord flattening если задан entry_point
      SEMICIRCLE — полукруг; r = width/2; плоская стена на стороне среза
      SEMI_OVAL  — полуовал; (x/a)² + (y/b)² ≤ 1 AND y ≥ 0
      L_SHAPE    — Г-образный; R1 ∪ R2; arm задаётся через shape_params
      T_SHAPE    — Т-образный; R1 ∪ R2; stem задаётся через shape_params

    v3:
      POLYGON    — произвольный полигон; ray-casting по вершинам из шаблона
    """
    RECTANGLE  = "rectangle"
    SQUARE     = "square"
    CIRCLE     = "circle"
    SEMICIRCLE = "semicircle"
    SEMI_OVAL  = "semi_oval"
    L_SHAPE    = "l_shape"
    T_SHAPE    = "t_shape"
    POLYGON    = "polygon"   # v3

    @property
    def is_supported(self) -> bool:
        return self in _V1_SHAPES


_V1_SHAPES: frozenset[ShapeType] = frozenset({
    ShapeType.RECTANGLE,
    ShapeType.SQUARE,
    ShapeType.CIRCLE,
    ShapeType.SEMICIRCLE,
    ShapeType.SEMI_OVAL,
    ShapeType.L_SHAPE,
    ShapeType.T_SHAPE,
})
