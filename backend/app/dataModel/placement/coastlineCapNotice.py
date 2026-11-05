from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.dataModel.identity.uid import EntityUid
from app.dataModel.placement.waterPreparationCode import WaterPreparationCode


class CoastlineCapNotice(BaseModel, frozen=True):
    model_config = ConfigDict(extra="forbid", strict=True, revalidate_instances="always")

    code: Literal[WaterPreparationCode.CAP_REACHED] = WaterPreparationCode.CAP_REACHED
    source_uid: EntityUid
