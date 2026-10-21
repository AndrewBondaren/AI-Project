"""Materialized directed drainage; authored system membership is independent."""

from pydantic import BaseModel, ConfigDict

from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
from app.dataModel.topology.worldTopology import Coord

RiverReceiverKind = BasinKind | HydrologyConnectionType


class RiverDrainageLink(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    river_uid: str
    receiver_uid: str
    receiver_kind: RiverReceiverKind
    receiver_cell: Coord
