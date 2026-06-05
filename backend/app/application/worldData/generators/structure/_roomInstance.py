from __future__ import annotations

from dataclasses import dataclass, field

from app.application.worldData.generators.structure._shapes import room_footprint


@dataclass
class _RoomInstance:
    """
    Внутреннее состояние комнаты во время генерации.
    Создаётся из room_def шаблона; координаты проставляются на этапе layout.
    """
    room_id:       str
    instance_idx:  int          # 0-based; для count=1 всегда 0
    z_offset:      int
    shape_type:    str
    width:         int
    depth:         int
    z_height:      int          # высота потолка этой комнаты (≤ z_height уровня)

    display_name:  str
    room_type:     str
    is_public:     bool
    is_forbidden:  bool
    required:      bool

    wall_material:  str
    floor_material: str
    economic_tier:  str | None = None

    # Layout — проставляются в _layoutEngine
    origin_x: int | None = None
    origin_y: int | None = None

    # Опциональные поля из room_def
    attach_to:           str | None = None
    attach_wall:         str | None = None
    perimeter_required:  bool = False
    underground_fallback: bool = False
    entry_point:         dict | None = None
    back_entry_point:    dict | None = None
    shape_params:        dict = field(default_factory=dict)

    @property
    def placed(self) -> bool:
        return self.origin_x is not None

    @property
    def uid_key(self) -> str:
        """Уникальный ключ для детерминированного UUID (room_id + instance_idx)."""
        return f"{self.room_id}_{self.instance_idx}"

    def get_footprint(self) -> set[tuple[int, int]]:
        if not self.placed:
            return set()
        return room_footprint(
            self.shape_type,
            self.origin_x,
            self.origin_y,
            self.width,
            self.depth,
            self.shape_params,
        )
