"""Assembly presentation of shared invariant details."""

from pydantic import BaseModel, ConfigDict, StrictStr
from app.dataModel.fields.validatedFieldPath import ValidatedFieldPath
from app.dataModel.patch.validation.invariantDetails import PatchSetInvariantDetails


class PatchSetAssemblyRelationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")
    details: PatchSetInvariantDetails
    path: ValidatedFieldPath
    related_path: ValidatedFieldPath | None
    message: StrictStr
