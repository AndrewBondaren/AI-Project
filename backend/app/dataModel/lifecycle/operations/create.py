from pydantic import BaseModel, ConfigDict

from app.dataModel.lifecycle.operations.intents import LifecycleCreate
from app.dataModel.lifecycle.reads.capture import LifecycleCapture
from app.dataModel.lifecycle.evidence.admission import DomainAdmission


class PrepareLifecycleCreate[T, R: BaseModel](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    intent: LifecycleCreate[T, R]
    capture: LifecycleCapture[T]
    admission: DomainAdmission[T]
