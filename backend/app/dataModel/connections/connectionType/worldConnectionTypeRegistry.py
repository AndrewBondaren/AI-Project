"""Root POJO for `worlds.connection_type_registry`."""

from __future__ import annotations

from typing import ClassVar

from pydantic import RootModel

from app.dataModel.connections.connectionType.connectionTypeEntry import ConnectionTypeEntry
from app.dataModel.registryEngine import engine_rows

_CANONICAL_ENTRIES: tuple[ConnectionTypeEntry, ...] = (
    ConnectionTypeEntry(system_connection_type="trail", display_name="Тропинка"),
    ConnectionTypeEntry(system_connection_type="dirt_road", display_name="Грунтовая дорога"),
    ConnectionTypeEntry(system_connection_type="road", display_name="Дорога"),
    ConnectionTypeEntry(system_connection_type="sidewalk", display_name="Тротуар"),
    ConnectionTypeEntry(system_connection_type="highway", display_name="Трасса"),
    ConnectionTypeEntry(system_connection_type="bridge", display_name="Мост"),
    ConnectionTypeEntry(system_connection_type="settlement_gate", display_name="Ворота поселения"),
    ConnectionTypeEntry(system_connection_type="air_route", display_name="Воздушный путь"),
    ConnectionTypeEntry(system_connection_type="sea_route", display_name="Морской путь"),
    ConnectionTypeEntry(system_connection_type="river", display_name="Река"),
    ConnectionTypeEntry(system_connection_type="mountain_river", display_name="Горная река"),
    ConnectionTypeEntry(system_connection_type="lake_shoreline", display_name="Берег озера"),
    ConnectionTypeEntry(system_connection_type="coastline", display_name="Береговая линия"),
    ConnectionTypeEntry(system_connection_type="portal", display_name="Портал"),
)

# Engine-only street types — tz_structure_connections.md §2.1 (not in world_template).
_ENGINE_DELTA: tuple[ConnectionTypeEntry, ...] = (
    ConnectionTypeEntry(system_connection_type="alley", display_name="Переулок"),
    ConnectionTypeEntry(system_connection_type="yard_path", display_name="Двор"),
)

# Builtin key subsets — look up via ``require_engine`` so missing registry rows fail loud.
ROAD_MASK_CONNECTION_TYPE_KEYS: tuple[str, ...] = (
    "trail", "dirt_road", "road", "highway", "bridge",
)
LANE_BASED_CONNECTION_TYPE_KEYS: tuple[str, ...] = (
    "road", "highway", "bridge",
)
HYDROLOGY_CONNECTION_TYPE_KEYS: tuple[str, ...] = (
    "lake_shoreline", "coastline", "river", "mountain_river",
)


class WorldConnectionTypeRegistry(RootModel[list[ConnectionTypeEntry]]):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-CONN"
    """Root POJO for `worlds.connection_type_registry`. Wire shape: JSON array."""

    root: list[ConnectionTypeEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldConnectionTypeRegistry:
        """fixtures/world_template.json."""
        return cls(list(_CANONICAL_ENTRIES))

    @classmethod
    def canonical_engine(cls) -> WorldConnectionTypeRegistry:
        """Fixture types + alley / yard_path."""
        return cls(list(
            engine_rows(
                _CANONICAL_ENTRIES,
                _ENGINE_DELTA,
                key=lambda e: e.system_connection_type,
            ),
        ))

    def keys(self) -> frozenset[str]:
        return frozenset(e.system_connection_type for e in self.root)

    def require(self, system_connection_type: str) -> str:
        entry = self.entry_for(system_connection_type)
        if entry is None:
            raise RuntimeError(
                f"WorldConnectionTypeRegistry missing {system_connection_type!r}",
            )
        return entry.system_connection_type

    @classmethod
    def require_engine(cls, system_connection_type: str) -> str:
        return cls.canonical_engine().require(system_connection_type)

    @classmethod
    def road_mask_connection_types(cls) -> tuple[str, ...]:
        return tuple(cls.require_engine(k) for k in ROAD_MASK_CONNECTION_TYPE_KEYS)

    @classmethod
    def hydrology_connection_types(cls) -> tuple[str, ...]:
        return tuple(cls.require_engine(k) for k in HYDROLOGY_CONNECTION_TYPE_KEYS)

    def entry_for(self, system_connection_type: str) -> ConnectionTypeEntry | None:
        for entry in self.root:
            if entry.system_connection_type == system_connection_type:
                return entry
        return None
