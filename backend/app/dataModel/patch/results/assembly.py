"""Complete assembly result or nonempty relation refusal."""

from pydantic import BaseModel, ConfigDict, Field
from app.dataModel.patch.request.patchSet import PatchSet
from app.dataModel.patch.results.assemblyIssues import PatchSetAssemblyRelationIssue
from app.dataModel.patch.sections.section import DomainSection


class PatchSetAssemblyRefused(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")
    diagnostics: tuple[PatchSetAssemblyRelationIssue, ...] = Field(min_length=1)


type PatchSetAssemblyResult[S: DomainSection] = PatchSet[S] | PatchSetAssemblyRefused
