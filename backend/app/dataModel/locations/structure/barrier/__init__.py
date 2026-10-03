from app.dataModel.structure.barrier.barrierTemplateEntry import BarrierTemplateEntry
from app.dataModel.structure.barrier.worldBarrierTemplateRegistry import (
    BarrierTemplateKey,
    WorldBarrierTemplateRegistry,
)
from app.dataModel.settlement.area.perimeterBarrier import PerimeterBarrier
import app.dataModel.settlement.area.perimeterBarrier as _pb_mod

_pb_mod.WorldBarrierTemplateRegistry = WorldBarrierTemplateRegistry
PerimeterBarrier.model_rebuild()

__all__ = ["BarrierTemplateEntry", "BarrierTemplateKey", "WorldBarrierTemplateRegistry"]
