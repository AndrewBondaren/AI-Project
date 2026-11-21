from pydantic import BaseModel, ConfigDict, Field
from app.dataModel.identity.uid import EntityUid
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef


class PrepareLifecycleSection[P: BaseModel, C: BaseModel](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    operation_id: EntityUid
    expected_world: WorldPublicationRef
    changes: tuple[P, ...] = Field(min_length=1)
    domain_evidence: tuple[C, ...]
