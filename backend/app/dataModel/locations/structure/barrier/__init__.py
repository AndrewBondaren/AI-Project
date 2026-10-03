from app.dataModel.locations.structure.barrier.barrierTemplateEntry import BarrierTemplateEntry
from app.dataModel.locations.structure.barrier.worldBarrierTemplateRegistry import (
    BarrierTemplateKey,
    WorldBarrierTemplateRegistry,
)
from app.dataModel.locations.settlement.area.perimeterBarrier import PerimeterBarrier
import app.dataModel.locations.settlement.area.perimeterBarrier as _pb_mod

_pb_mod.WorldBarrierTemplateRegistry = WorldBarrierTemplateRegistry
PerimeterBarrier.model_rebuild()

__all__ = ["BarrierTemplateEntry", "BarrierTemplateKey", "WorldBarrierTemplateRegistry"]
