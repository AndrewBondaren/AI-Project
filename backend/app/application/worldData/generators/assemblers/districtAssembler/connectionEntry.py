from dataclasses import dataclass

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

    facing               — грань района, на которой стоит узел: "N"|"S"|"E"|"W".
    """
    node:            ConnectionNode
    connection_type: str         # ref → connection_type_registry
    role:            str         # "through_road" | "entry_point"
    facing:          str         # "N" | "S" | "E" | "W"
    paired_exit_uid: str | None  # uid выходного узла; None для entry_point
