from app.application.jsonValidation.resolve import ResolveContext, resolve_model
from app.application.jsonValidation.resolution.diagnostics import reject_unresolved
from app.application.time.calendar.validation import CalendarValidator
from app.dataModel.world.calendar.projection.errors import CalendarBudgetExceeded, CalendarInvalid
from app.dataModel.world.calendar.projection.request import CalendarBudget, ValidateCalendarInput
from app.dataModel.world.settings.timeSettings import WorldTimeSettings


def resolve_world_time_settings(raw: dict[str, object], ctx: ResolveContext, budget: CalendarBudget
                                ) -> WorldTimeSettings | CalendarBudgetExceeded:
    """Resolve a complete authored settings document under the caller's policy."""
    settings = resolve_model(WorldTimeSettings, raw, ctx=ctx)
    result = CalendarValidator.validate(ValidateCalendarInput(settings=settings, budget=budget))
    if isinstance(result, CalendarInvalid):
        reject_unresolved(ctx, result.issues)
    if isinstance(result, CalendarBudgetExceeded):
        return result
    return result.settings
