"""L-4 orchestration: inspect/decide/prepare/apply in one caller-compatible UOW."""
from app.application.jsonValidation.resolve import ResolveContext, report_issues
from app.application.worldData.libraryPacks.writeContracts import LibraryWriteRequest, WriteStatus
from app.application.worldData.libraryPacks.writePreview import prepare_preview
from app.application.worldData.libraryPacks.writeResults import LibraryWriteOutcome, PolicyRequired, WriteRejected


class LibraryWriteService:
    def __init__(self, *, db, inspector, policy, planner, executor):
        self._db, self._inspector, self._policy = db, inspector, policy
        self._planner, self._executor = planner, executor

    async def execute(self, request: LibraryWriteRequest, *, imports=None) -> LibraryWriteOutcome:
        return await self._execute(request, imports=imports)

    async def prepare(self, request: LibraryWriteRequest, *, imports=None):
        """Prepare inside caller UOW; used when entities need the resulting UID map."""
        from app.db.database import _in_transaction
        if not _in_transaction.get() or not self._db.main_conn.owns_unit_of_work:
            raise RuntimeError("library preparation requires caller UOW")
        return await self._prepare(request, imports=imports)

    async def apply_prepared(self, plan):
        return await self._executor.apply(plan)

    async def execute_exact_member(self, request: LibraryWriteRequest, *, imports=None) -> LibraryWriteOutcome:
        """Internal compatibility for an already explicit copy/edit by UID, TZ §0.2."""
        return await self._execute(request, imports=imports, exact_operation=True)

    async def _execute(self, request, *, imports=None, exact_operation=False):
        async with self._db.transaction_if_needed():
            prepared = await self._prepare(request, imports=imports, exact_operation=exact_operation)
            if isinstance(prepared, (PolicyRequired, WriteRejected)):
                return prepared
            return await self._executor.apply(prepared)

    async def _prepare(self, request, *, imports=None, exact_operation=False):
        snapshot = await self._inspector.inspect(request, imports=imports)
        decision = self._policy.decide(snapshot, request, exact_operation=exact_operation)
        if decision.status is WriteStatus.REJECTED:
            return WriteRejected(decision.issues, decision.choices)
        if decision.status is WriteStatus.POLICY_REQUIRED:
            preview = prepare_preview(snapshot, request, decision, self._policy, self._planner)
            report_issues(ResolveContext(), tuple(dict.fromkeys(issue for variant in preview
                if variant.plan for issue in variant.plan.diagnostics)))
            return PolicyRequired(decision.preview_token, decision.choices, preview, decision.stale)
        plan = self._planner.prepare(snapshot, decision)
        report_issues(ResolveContext(), plan.diagnostics)
        return plan
