"""Root POJO for `worlds.connection_type_registry`."""

from __future__ import annotations

from typing import ClassVar

from pydantic import RootModel

from app.dataModel.connections.connectionType.connectionTypeEntry import ConnectionTypeEntry

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

# tz_structure_connections.md §2.1 + §2.2 hydrology declare types
_ENGINE_ENTRIES: tuple[ConnectionTypeEntry, ...] = (
    ConnectionTypeEntry(system_connection_type="trail", display_name="Тропинка"),
    ConnectionTypeEntry(system_connection_type="dirt_road", display_name="Грунтовая дорога"),
    ConnectionTypeEntry(system_connection_type="road", display_name="Дорога"),
    ConnectionTypeEntry(system_connection_type="sidewalk", display_name="Тротуар"),
    ConnectionTypeEntry(system_connection_type="highway", display_name="Трасса"),
    ConnectionTypeEntry(system_connection_type="bridge", display_name="Мост"),
    ConnectionTypeEntry(system_connection_type="alley", display_name="Переулок"),
    ConnectionTypeEntry(system_connection_type="yard_path", display_name="Двор"),
    ConnectionTypeEntry(system_connection_type="settlement_gate", display_name="Ворота поселения"),
    ConnectionTypeEntry(system_connection_type="air_route", display_name="Воздушный путь"),
    ConnectionTypeEntry(system_connection_type="sea_route", display_name="Морской путь"),
    ConnectionTypeEntry(system_connection_type="river", display_name="Река"),
    ConnectionTypeEntry(system_connection_type="mountain_river", display_name="Горная река"),
    ConnectionTypeEntry(system_connection_type="lake_shoreline", display_name="Берег озера"),
    ConnectionTypeEntry(system_connection_type="coastline", display_name="Береговая линия"),
    ConnectionTypeEntry(system_connection_type="portal", display_name="Портал"),
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
        """TZ §2.1 built-ins + lake_shoreline / coastline from §2.2."""
        return cls(list(_ENGINE_ENTRIES))

    def entry_for(self, system_connection_type: str) -> ConnectionTypeEntry | None:
        for entry in self.root:
            if entry.system_connection_type == system_connection_type:
                return entry
        return None
