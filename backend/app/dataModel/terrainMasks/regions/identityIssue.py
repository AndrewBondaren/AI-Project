"""Diagnostics owned by declared region identity resolution."""

from enum import StrEnum

from pydantic import StrictStr

from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.importIssues.wireLocation import WireLocation


class RegionIdentityCode(StrEnum):
    REGION_DEGRADED_IDENTITY = "REGION_DEGRADED_IDENTITY"


class RegionIdentityIssue(FieldPathError[RegionIdentityCode]):
    location: WireLocation
    schema_id: StrictStr | None = None
