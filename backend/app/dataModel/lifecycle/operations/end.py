from pydantic import BaseModel, ConfigDict

from app.dataModel.lifecycle.operations.intents import LifecycleEnd
from app.dataModel.lifecycle.reads.capture import LifecycleCapture
from app.dataModel.lifecycle.evidence.admission import DomainAdmission


class PrepareLifecycleEnd[T, R: BaseModel](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    intent: LifecycleEnd[T, R]
    capture: LifecycleCapture[T]
    admission: DomainAdmission[T]
