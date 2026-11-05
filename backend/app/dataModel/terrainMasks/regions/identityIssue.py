"""Region identity diagnostics owned by the declared-regions domain.

Plan: ``.cursor/plans/error-contracts-1.md`` J3a D1(B).
"""

from enum import StrEnum

from pydantic import StrictStr

from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.importIssues.wireLocation import WireLocation


class RegionIdentityCode(StrEnum):
    REGION_DEGRADED_IDENTITY = "REGION_DEGRADED_IDENTITY"


class RegionIdentityIssue(FieldPathError[RegionIdentityCode]):
    """``path`` starts at ``RegionSpecBase``; ``location`` places the spec in the document."""

    location: WireLocation
    schema_id: StrictStr | None = None
