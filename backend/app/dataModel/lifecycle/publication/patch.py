from pydantic import BaseModel
from app.dataModel.patch.changes.patchData import PatchData


class LifecycleTransitionPatch[P: BaseModel](PatchData):
    prepared: P
