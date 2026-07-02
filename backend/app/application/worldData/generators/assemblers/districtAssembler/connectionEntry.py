from dataclasses import dataclass

from app.dataModel.connections.enums.connectionNodeType import ConnectionNodeType
from app.dataModel.connections.enums.graphLevel import GraphLevel
from app.dataModel.settlement.enums.districtEntryRole import DistrictEntryRole
from app.application.worldData.generators.utils.facing import Facing
from app.db.models.connectionNode import ConnectionNode


@dataclass
class ConnectionEntry:
    """
    Точка входа/выхода на границе района — создаётся SettlementAssembler и передаётся в DistrictSlot.

    role="through_road"  — сквозная дорога; paired_exit_uid указывает на узел выхода
                           на противоположной грани района. DistrictAssembler прокладывает
                           коридор между парой до построения внутренней сетки.

    role="entry_point"   — одиночная точка входа без парного выхода.
                           DistrictAssembler подключает к ней внутреннюю сеть.

    facing — грань (или угол) bbox района: Facing.NORTH … Facing.SOUTHWEST.
    """
    node:            ConnectionNode
    connection_type: str         # ref → connection_type_registry
    role:            DistrictEntryRole
    facing:          Facing
    paired_exit_uid: str | None  # uid выходного узла; None для entry_point
