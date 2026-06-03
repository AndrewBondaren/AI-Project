import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from app.application.worldData.generators.shapeType import ShapeType
from app.db.models.locationLevel import LocationLevel
from app.db.models.locationPassage import LocationPassage
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


class UnsupportedShapeError(ValueError):
    """shape_type из шаблона не реализован в текущей версии генератора."""


@dataclass
class BuildingLayout:
    cells:    list[MapCell]
    levels:   list[LocationLevel]
    passages: list[LocationPassage]
    rooms:    list[NamedLocation]


_FLOOR_ELEMENT  = "floor"
_WALL_ELEMENT   = "wall"
_DOOR_ELEMENT   = "door"

_DEFAULT_WALL_MATERIAL  = "stone"
_DEFAULT_FLOOR_MATERIAL = "wood"

_FLOOR_HEIGHT = 3  # z-units per floor (3м per ТЗ)


def _det_uuid(namespace: str, *parts: str) -> str:
    """Deterministic UUID5 from building uid + extra parts."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, namespace + "|" + "|".join(parts)))


def _world_seed(world_uid: str) -> int:
    return int(hashlib.md5(world_uid.encode()).hexdigest()[:8], 16)


class BuildingGeneratorService:
    """
    Pure utility — no repositories, no async.
    Deterministic: same world_uid + same building_uid → same layout.

    Importable by worldData services (eager init) and engine nodes (lazy/repair).
    """

    def generate_from_template(
        self,
        world: World,
        building: NamedLocation,
        template: dict,
    ) -> BuildingLayout:
        """
        Generate a full multi-level building from a building_template_registry entry.

        template — один элемент из worlds.building_template_registry (уже распакованный dict).
        Комнаты создаются как NamedLocation с location_type="room" и parent_location_uid=building.location_uid.
        Seed детерминирован: world_uid + building_uid → воспроизводимый layout.

        Raises UnsupportedShapeError если шаблон содержит shape_type не из ShapeType._V1_SHAPES.

        Not implemented in v1.
        """
        raise NotImplementedError("Template-based generation is not implemented in v1")

    def validate_template(self, data: dict) -> list[str]:
        """
        Валидирует шаблон перед сохранением в БД.
        Возвращает список ошибок. Пустой список = OK.
        Проверяет в т.ч. что все shape_type — валидные ShapeType и is_supported=True.
        """
        raise NotImplementedError("Template validation is not implemented in v1")

    # ------------------------------------------------------------------

    def _build_room(
        self,
        building: NamedLocation,
        room_uid: str,
        display_name: str,
        room_type: str,
        origin_x: int,
        origin_y: int,
        origin_z: int,
        is_public: bool = False,
        is_forbidden: bool = False,
    ) -> NamedLocation:
        """
        Создаёт комнату как NamedLocation.

        location_type = "room" → is_outdoor: false подтягивается из location_type_registry.
        is_public / is_forbidden берутся из room_type_registry.default_is_public/forbidden.
        origin_x/y/z — глобальные координаты левого нижнего угла комнаты (origin footprint).
        Фактический размер комнаты implicit из её map_cells (ТЗ: "размер implicit из map_cells").
        """
        return NamedLocation(
            location_uid=room_uid,
            world_uid=building.world_uid,
            display_name=display_name,
            system_location_type="room",
            system_location_subtype=room_type,
            created_at=datetime.now(timezone.utc).isoformat(),
            parent_location_uid=building.location_uid,
            is_accessible=True,
            is_discovered=False,
            is_public=is_public,
            is_forbidden=is_forbidden,
            map_x=origin_x,
            map_y=origin_y,
            map_z=origin_z,
        )

    def _generate_box(
        self,
        world_uid: str,
        location_uid: str,
        x0: int,
        y0: int,
        z: int,
        width: int,
        depth: int,
        wall_material: str,
        floor_material: str,
    ) -> list[MapCell]:
        """
        Generate perimeter walls + interior floor cells for a rectangular footprint.
        Door placed at south wall center.
        """
        x_max = x0 + width  - 1
        y_max = y0 + depth  - 1

        door_x = x0 + width // 2
        door_y = y0  # south wall

        cells: list[MapCell] = []

        for y in range(y0, y_max + 1):
            for x in range(x0, x_max + 1):
                on_perimeter = (
                    x == x0 or x == x_max or
                    y == y0 or y == y_max
                )

                if on_perimeter:
                    if x == door_x and y == door_y:
                        element = _DOOR_ELEMENT
                        is_structural = False
                    else:
                        element = _WALL_ELEMENT
                        is_structural = True
                    material = wall_material
                else:
                    element = _FLOOR_ELEMENT
                    is_structural = False
                    material = floor_material

                cells.append(MapCell(
                    world_uid=world_uid,
                    x=x,
                    y=y,
                    z=z,
                    system_building_element=element,
                    system_material=material,
                    is_structural=is_structural,
                    location_uid=location_uid,
                ))

        return cells

    def _resolve_wall_material(self, world: World) -> str:
        registry = world.material_registry or {}
        for candidate in (_DEFAULT_WALL_MATERIAL, "wood", "earth"):
            if candidate in registry:
                return candidate
        return _DEFAULT_WALL_MATERIAL

    def _resolve_floor_material(self, world: World) -> str:
        registry = world.material_registry or {}
        for candidate in (_DEFAULT_FLOOR_MATERIAL, "stone", "earth"):
            if candidate in registry:
                return candidate
        return _DEFAULT_FLOOR_MATERIAL
