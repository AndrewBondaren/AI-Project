"""Expose computed coating issues to the existing validation/runtime reporting sink."""
from app.application.jsonValidation.resolve import ResolveContext, report_issues
from app.dataModel.terrain.relief.surfaceCoating.surfaceCoatingFacts import CoatingPlan


class SurfacePlanValidator:
    def validate_coating(self, plan: CoatingPlan, *, ctx: ResolveContext) -> None:
        plan = CoatingPlan.model_validate(plan, strict=True)
        report_issues(ctx, (issue for cell in plan.cells for issue in cell.decision.issues))
