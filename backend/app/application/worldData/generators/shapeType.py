from enum import Enum


class ShapeType(str, Enum):
    """
    Форма footprint комнаты. Определяет алгоритм генерации map_cells.

    v1:
      RECTANGLE  — прямоугольник; x ∈ [x0, x0+w) AND y ∈ [y0, y0+d);
                   стена на границе, пол внутри
      SQUARE     — квадрат; то же, w = d = min(width, depth)

    v2:
      SEMICIRCLE — полукруг; r = width / 2; плоская стена на стороне среза;
                   (x−cx)² + (y−cy)² ≤ r² AND y ≥ cy
      SEMI_OVAL  — полуовал; a = width / 2, b = depth; плоская стена сверху;
                   (x/a)² + (y/b)² ≤ 1 AND y ≥ 0
      L_SHAPE    — Г-образный; R1 ∪ R2; R1 = main body (width × depth),
                   R2 = arm (arm_width × arm_depth) смещён в угол
      T_SHAPE    — Т-образный; R1 ∪ R2 ∪ R3; R1 = горизонтальная балка (width × arm_depth),
                   R2/R3 = столбы
      CIRCLE     — круг; (x−cx)² + (y−cy)² ≤ r²; r = width / 2

    v3:
      POLYGON    — произвольный полигон; ray-casting test по вершинам из шаблона
    """
    RECTANGLE  = "rectangle"
    SQUARE     = "square"
    SEMICIRCLE = "semicircle"   # v2
    SEMI_OVAL  = "semi_oval"    # v2
    L_SHAPE    = "l_shape"      # v2
    T_SHAPE    = "t_shape"      # v2
    CIRCLE     = "circle"       # v2
    POLYGON    = "polygon"      # v3

    @property
    def is_supported(self) -> bool:
        """True для shape_type реализованных в v1."""
        return self in _V1_SHAPES


_V1_SHAPES: frozenset[ShapeType] = frozenset({
    ShapeType.RECTANGLE,
    ShapeType.SQUARE,
})
