from pydantic import BaseModel
from typing import ClassVar
from app.dataModel.patch.changes.patchData import PatchData


class LifecycleTransitionPatch[P: BaseModel](PatchData):
    FORMAT_VERSION: ClassVar[int] = 1
    prepared: P
