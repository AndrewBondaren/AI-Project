"""F09 issue where no POJO or declared field exists (raw rows, removed or rejected sections)."""

from pydantic import BaseModel, ConfigDict, StrictStr

from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireLocation import WireLocation


class WireShapeIssue(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    code: JsonValidationCode
    location: WireLocation
    message: StrictStr
