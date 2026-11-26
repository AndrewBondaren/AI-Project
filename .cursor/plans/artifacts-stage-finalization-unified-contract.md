# Этап 2: единая сводка execution finalization / crash recovery

## 1. Архитектура реализации

2026-11-27. PLAN-ONLY, PROPOSED / OPEN. Координатор: Between domain operations, `01a218a4-bfc5-7012-b18b-8ed986cc786d`. Сведение не означает принятия архитектуры, возобновления этапа 2 или code-go. Существующий этап 1 и blocking cancel не меняются. Недостаток сведений означает отказ в общей приёмке по implement-plan и dag-generator-interface. Этот документ сохраняет незакрытые места вместо изобретения API.

E — existing, M — modified proposal, N — new proposal. Пути относительно `backend/app/`. Target signatures не являются actual API.

| Класс / модуль | Контракт, ответственность, зависимости и effects | Проверка / основание отказа |
|---|---|---|
| N StageAttemptService, application/artifacts/staging/stageAttemptService.py | async begin(request: StageBeginInput) -> StageAttemptResult; async recover(request: StageRecoveryInput) -> StageAttemptResult; async pending_finalizations(request: OperationCloseInput) -> OperationStageFinalizationResult; async finalize_execution(request: StageFinalizeInput) -> StageFinalizeResult. Thin delegation в один store/job | Нет SQL/OS, выбора следующего public CALL или Publication service calls |
| N SqliteStageAttemptStore, db/repositories/sqlite/artifacts/stageAttemptStore.py; IStageAttemptStore, application/artifacts/storage/stageAttemptStore.py | Constructor(scopes: SqliteArtifactScope, operations: SqliteOperationStore[R], catalog: SqliteArtifactCatalog, *, stage_drain: IStageExecutionDrain). Единственная durable stage authority, inventory, binding/generation/completion/release | Backend/gate/job dependency, OS wait, independent commit scoped метода или второй issuer — отказ |
| N ArtifactStageFinalizer, application/artifacts/staging/artifactStageFinalizer.py | Constructor(attempts: IStageAttemptStore, registry: ArtifactFormatRegistryBinding); async finalize_execution(request: StageFinalizeInput) -> StageFinalizeResult; async finish_live(claim: StageWriteClaim) -> None. Exact resolution, gate, evidence, cleanup/release | Нет successor/terminal. Guard не proof. Cleanup без proof, fake live evidence, legacy fallback — отказ |
| N ArtifactStageRecovery, application/artifacts/staging/artifactStageRecovery.py | Constructor(attempts: IStageAttemptStore, finalizer: ArtifactStageFinalizer); async recover(request: StageRecoveryInput) -> StageAttemptResult. inspect → conditional internal finalizer → finish | finalizer.attempts is attempts. Не запускает stage, не копирует SQL policy/cleanup |
| M ArtifactStageWriter, application/artifacts/staging/artifactStageWriter.py | Actual async write(self, lease: OperationLeaseRef, prepared: PreparedArtifact[C]) -> ArtifactRef. Target full/local lifetime и required finalizer dependency | Full claim не SQL transaction. Context exit не делает второй release. Backend не reacquire local claim |
| M ArtifactFormatRegistryBinding, application/artifacts/registry/artifactRegistry.py | resolve_finalizer(ref: ArtifactRef) -> ArtifactStageFinalizationBackend; одна existing registration, exact kind/key/version | Другой backend/root/authority, второй registry, hot rebind, legacy fallback — отказ |
| N ArtifactStageFinalizationBackend, application/artifacts/contracts/authorizedBackend.py | stage_authority: IStageAttemptStore; effect_gate: WindowsBlobEffectGate; async cleanup_under_guard(claim: StageWriteClaim, guard: BlobEffectGuard) -> None. Capability того же backend | Не выдаёт permit, не делает seal/release, не acquire gate повторно, не удаляет shared final |
| M ContentAddressedBlobBackend, storage/artifacts/blobBackend.py | Existing codec/path/temp/place/verify/IO; proposed authorized write/verify/cleanup. Physical effects и join | Каждый mkdir/write/fsync/rename/unlink/finally охвачен lifetime. Stale cleanup вне guard — отказ |
| N WindowsBlobEffectGate / BlobEffectGuard | acquire() -> BlobEffectGuard; close(). Root exclusion, стабильный control file | SQL→OS wait, replacement control file, отдача guard до join — отказ; lock не completion |
| N WindowsBlobProcessWitness, provider/module OPEN | wait_terminated() -> None; close() -> None. Реальный identity-bound process HANDLE до dispatch, переживающий effect owner | PID/числовой HANDLE из SQL не заменяют ресурс. Surviving owner не назначен |
| N SqliteStageExecutionDrain, db/repositories/sqlite/artifacts/stageExecutionDrain.py | Constructor(access: ScopedSqliteAccess); async is_drained(scope: CommitReadScope, operation_id: EntityUid) -> bool; async assert_drained(scope: CommitScope, operation_id: EntityUid) -> None | Stateless authoritative predicate, не worker controller/policy/registry. Same graph, без singleton requirement |
| M OperationLedger[R], application/publication/service/operationLedger.py | async close_for_cancellation(request: OperationCloseInput) -> OperationCloseResult[R]; existing cancel/recover delegation | Только Publication operation lifecycle; нет Artifacts CALL внутри cancel |
| M SqliteArtifactLeases[R], db/repositories/sqlite/artifacts/leaseStore.py | Existing cancel(operation_id: EntityUid, fence: int) -> OperationRecord[R]; finish_preparation(lease: OperationLeaseRef, refs: tuple[ArtifactRef,...]) -> OperationRecord[R]. Close/wait/final UOW | NEW terminal/release без all-fence local/full drain — отказ; own local release не ждёт full drain |
| M SqliteArtifactCatalog, db/repositories/sqlite/artifacts/catalogStore.py | reserve_in_scope(scope: CommitScope, lease: OperationLeaseRef, descriptor: ArtifactRef) -> StagingReservation; scoped seal reuse | Нет своего commit/lifecycle policy/копии predicates |
| M SqliteArtifactHolders / SqliteOperationStore[R] | release(OperationHolder)/handoff; claim_publication; record_terminal/record_refusal: scoped operation-wide guards | Current-fence-only query недостаточен; historical replay не создаёт release |
| E SqliteArtifactScope / ScopedSqliteAccess / SqlitePublicationCommitStore / SqliteScopeRegistry / SqliteTransactionDriver / GuardedConnection | Existing UOW, scope/ACK/quarantine infrastructure | Второй transaction coordinator, foreign graph, false rollback после unknown — отказ |
| M Engine InvocationCoordinator / ActiveCheckpoint / OwnedExecution / NodeRunner / ResumablePythonNode | Generic CALL/checkpoint/unknown transport, existing fenced owner и revision CAS | Нет stage safety policy, generation issuer, второго lifecycle |

Assembly: scopes/access → stateless drain → operations/catalog → attempts → leases/holders → gate → backend → existing registry → finalizer → recovery → service/writer. Store не получает обратной зависимости. Same graph/root/authority проверяются до IO. Полный before/after inventory всех reachable signatures ещё не замкнут; Q1 provider и Q4 handoff нельзя скрыть в defaults. Общий архитектурный PASS запрещён.

Internal store boundaries: async inspect_finalization(request: StageFinalizeInput) -> StageWriteClaim | StageFinalizeResult; async inspect_recovery(request: StageRecoveryInput) -> StageAttemptResult | StageFinalizeInput; async finish_recovery(request: StageRecoveryInput) -> StageAttemptResult; async reserve_stage(claim: StageWriteClaim) -> StagingReservation; async prohibit_effects(claim: StageWriteClaim, guard: BlobEffectGuard) -> None; async release_finalized(claim: StageWriteClaim, guard: BlobEffectGuard) -> None; async release_live(claim: StageWriteClaim, guard: BlobEffectGuard) -> None. Wrappers открывают один existing UOW, scoped primitives не коммитят сами. COMP-02 уже задаёт local_writer(claim: StageWriteClaim, reservation: StagingReservation) -> AbstractAsyncContextManager[StageLocalWriter] и async release_local_in_scope(scope: CommitScope, claim: StageWriteClaim, local: StageLocalWriter) -> None; это не OPEN отсутствующей сигнатуры. Target async seal_stage(claim: StageWriteClaim, local: StageLocalWriter, reservation: StagingReservation) -> ArtifactRef заменяет двухаргументный stage-1 вариант только в этапе 2. Store не исполняет physical finalization/recovery job.

## 2. Public Input / Result / Error

Publication owner/module: `dataModel/publication/operationClose.py` (proposal).

| Тип | Собственные поля |
|---|---|
| OperationCloseInput | operation_id: EntityUid; fence: strict int >= 1 |
| OperationCloseTerminal[R] | kind=TERMINAL; record: OperationRecord[R] |
| OperationCloseReady | kind=CLOSED_DRAINED; request: OperationCloseInput |
| OperationClosePending | kind=CLOSED_PENDING; request: OperationCloseInput; pending: OperationDrainPending |
| OperationDrainPending | FULL_STAGE / BOTH / LOCAL_WRITERS |
| OperationCloseResult[R] | discriminated union трёх результатов |

Artifacts owner/module: `dataModel/artifacts/staging/stageAttempt.py` (proposal).

| Тип | Собственные поля |
|---|---|
| StageBinding | stage_id: EntityUid; lease: OperationLeaseRef; artifact: ArtifactRef |
| StageBeginInput | binding: StageBinding |
| StageRecoveryInput / StageAttemptPermit / StageFinalizeInput | binding: StageBinding; generation: strict int >= 1 |
| StageAttemptAllowed | kind='allowed'; permit: StageAttemptPermit |
| StageConfirmed | kind='confirmed'; binding: StageBinding; completed_generation: strict int >= 1 |
| StageRecoveryRefused | kind='refused'; binding: StageBinding; code: StageRecoveryRefusalCode; cancelled: OperationCancelled \| None |
| StageRecoveryUnresolved | kind='unresolved'; binding: StageBinding; code: StageRecoveryUnresolvedCode |
| StageAttemptResult | Allowed / Confirmed / Refused / Unresolved |
| StageBindingConflict | requested: StageBinding; registered: StageBinding |
| ArtifactStageAdmissionFailure | permit: StageAttemptPermit; code: StageAdmissionCode |
| OperationStageFinalizationBatch | kind='batch'; request: OperationCloseInput; pending: tuple[StageFinalizeInput,...] |
| OperationStageFinalizationRefused | kind='refused'; request: OperationCloseInput; code: ArtifactLeaseFailureCode, только OPERATION_MISSING/FENCE_MISMATCH/ADMISSION_OPEN |
| OperationStageFinalizationResult | Batch / Refused |
| StageExecutionFinalized | kind='finalized'; binding: StageBinding; generation: strict int >= 1 |
| StageFinalizeUnresolved | kind='unresolved'; binding: StageBinding; generation: strict int >= 1; code: StageFinalizeUnresolvedCode |
| StageFinalizeResult | StageExecutionFinalized / StageFinalizeUnresolved |

Records strict/frozen/extra-forbid/revalidate_instances=always; поля обязательны. Foreign lease/ref/record/cancelled reuse, не mirrors. Транзитивные operands не скрыты:
- existing dataModel/artifacts/lifecycle/lease.py::OperationLeaseRef: operation_id: EntityUid, world_uid: EntityUid, kind: OperationKind, preparation_fingerprint: RevisionHex, fence: strict int >= 1;
- там же StagingReservation: artifact_id: EntityUid, lease: OperationLeaseRef, ref: ArtifactRef;
- existing dataModel/artifacts/references.py::ArtifactRef: kind: ArtifactKind, format_key: ArtifactFormatKey, format_version: FormatVersion, content_hash: RevisionHex, nbytes: strict int >= 0, row_count: strict int >= 0 | None. SQL_ROWS требует row_count, BLOB запрещает его. Existing default row_count=None сохраняется;
- proposed dataModel/artifacts/staging/stageInput.py::ArtifactAuthorizedStageInput[C]: permit: StageAttemptPermit, prepared: PreparedArtifact[C]; sibling existing lease-based input, не его наследник. PreparedArtifact/content проходят existing identity-preserving validation;
- proposed stageAttempt.py::ArtifactStageBindingIssue(permit: StageAttemptPermit, descriptor: ArtifactRef) — relation двух input operands; StageBindingConflict — requested/registered durable binding. Это разные отношения, не дубли;
- ArtifactStageInputFailure(fields: ArtifactInputError | None, binding: ArtifactStageBindingIssue | None) требует непустой компонент. Сбор независимых content/format/relation через existing ValidatorAggregationHelper до raise; codec только после admission.
StageAttemptErrors carriers: ArtifactStageInputRejected(error: ArtifactStageInputFailure), ArtifactStageAdmissionRejected(error: ArtifactStageAdmissionFailure), StageBindingRejected(error: StageBindingConflict). Existing ArtifactLeaseRefused/ArtifactLeaseFailure сохраняются. Root content: authorized input.prepared → PreparedArtifactBase.content; descriptor: prepared → descriptor. Relations не маскируются FieldPathError. Cold allowlist/schema IDs и полный Engine wire cause остаются конкретным integration OPEN, а не основанием объявить DTO дублирующимися.

StageFinalizeUnresolvedCode: STAGE_UNTRACKED, GENERATION_UNTRACKED, EFFECTS_NOT_QUIESCENT, INSUFFICIENT_EVIDENCE. StageRecoveryUnresolvedCode: STAGE_UNTRACKED, ATTEMPT_NOT_QUIESCENT, INSUFFICIENT_EVIDENCE. StageRecoveryRefusalCode: OPERATION_CANCELLED, ADMISSION_CLOSED, STALE_OPERATION_FENCE, STALE_STAGE_ATTEMPT. cancelled непустой iff OPERATION_CANCELLED. StageAdmissionCode: PERMIT_UNREGISTERED, GENERATION_STALE, GENERATION_ACTIVE, GENERATION_COMPLETED плюс explicit proposed EXECUTION_PROHIBITED.

`application/artifacts/staging/stageAttemptErrors.py::StageBindingRejected(error: StageBindingConflict)` — durable mismatch. Malformed — ValidationError. Integrity — ArtifactStorageInvariantError; infrastructure — PublicationInfrastructureError с cause. UnknownCommitOutcome/CancelledError не становятся Unresolved/refusal/empty batch. Close сохраняет OperationBusyError; missing/stale close — PublicationInfrastructureError, existing cancel stale — ValueError. Exact Engine wire cause/diagnostics mapping OPEN.

Completion = historical seal/hold commit; finalization = прекращение exact execution effects и release claims; terminal = operation lifecycle. Эти гарантии не взаимозаменяемы.

## 3. Exact Output → Input

1. Confirmed close Pending(FULL_STAGE/BOTH).request целиком → pending_finalizations(request). Coordinates operation_id/fence, не lease.
2. Artifacts проверяет current fence/closed и читает один coherent cut retained bindings/acquisitions/releases. Inventory P(S)=A(S) минус exact X(S) для ВСЕХ stages/generations/historical fences. Completion/current generation/link/temp/hold не фильтры.
3. Полный StageBinding берётся из immutable persisted binding: stage_id; lease.operation_id/world_uid/kind/preparation_fingerprint/historical fence; полный ArtifactRef. Generation — exact acquisition. Current request.fence не подменяет historical fence. Duplicate acquisition пары stage/generation — fault.
4. batch.request == close.request; item.binding.lease.operation_id == request.operation_id. Каждый готовый item целиком → finalize_execution(item). DAG ничего не достраивает и не читает storage.
5. Refused/exception без partial batch; без pagination/truncation. Невозможность материализации полного набора — ошибка. Concurrent release может уменьшить повторный inventory; empty не доказывает local drain.
6. LOCAL_WRITERS не запускает finalization. BOTH сохраняет local blocker. Ready → existing cancellation handling с final recheck; Terminal не запускает automatic inventory. Busy никогда не close proof.
7. Финальный cancel получает ровно cancel(close_result.request.operation_id, close_result.request.fence) -> OperationRecord[R], без stage results в качестве authority. Значение fence не обновляется DAG.
8. Recover получает сохранённые binding/generation, не derived operands из lost_attempt. Allowed.permit → authorized stage вместе с prepared; successor сохраняет stage_id. Confirmed не фабрикует success старого unknown child.

Q5 sections от 2026-11-27 согласованы по pending_finalizations / StageFinalizeInput / finalize_execution. Старые settlement-написания исторических RC sections не aliases. В этой сводке canonical имена едины. Исторические разделы не переписываются: owning RC-CONSTRUCTION отменяет physical методы store, Q5 отменяет lease-вход inventory, Publication Q5/Q6 отменяют Busy→settle и nonblocking-cancel кандидат. Если старый раздел используется как действующий контракт вопреки этим explicit overrides, это отказ; aliases не предусмотрены.

## 4. Traces, states, transaction order

Normal target: DAG public stage → writer → full acquisition A → reserve_stage → atomic local acquisition/link L → authorized write/verify → atomic seal/hold/completion C → stop dispatch/join/cleanup → finish_live внутри ОБОИХ contexts → один local/full release X → exits. Failed cleanup/prohibition оставляет pending. Context exits не делают release повторно. Repeated cancellation Q4 не закрыта happy path.

Finalization: public delegation либо internal recovery job → inspect (закрыть scope) → registry.resolve_finalizer → OS gate → short prohibition UOW P, confirmed ACK → NO_LOCAL proof либо barrier ВСЕХ old writer/cleanup owners → exact own-temp cleanup/join → short release UOW X → close guard. FINALIZE не разрешает WRITE/VERIFY/seal. Shared final/operation holds не удаляются.

Recovery: inspect → direct outcome либо exact StageFinalizeInput → internal finalizer → только после StageExecutionFinalized finish_recovery(original request) → owning result → DAG. Error/cancellation/unresolved не вызывают finish в finally. EFFECTS_NOT_QUIESCENT → ATTEMPT_NOT_QUIESCENT с сохранением cause; wire OPEN.

| Crash boundary | Действие |
|---|---|
| До A / confirmed rollback A | Не создавать execution для release; shared reservations возможны |
| A без L, до/после committed reserve | Под gate confirmed P + authoritative reread + NO_LOCAL proof → только X, R/holds сохраняются |
| Unknown reserve/local/P/X | Existing quarantine/reconcile на здоровом scope, без dependent effects |
| L commit до ACK/dispatch | Durable facts не отличают от dispatch; linked barrier, не «не успел» |
| Dispatch / C / cleanup до X | P плюс completion writer И предыдущих cleanup owners; C не drain |
| Matching X после lost ACK | Integrity/exact chain → finalized без cleanup/нового release |
| Malformed present link/history | Fault; lawful missing link не corruption |

NO_LOCAL: A+confirmed P, отсутствие X/L в coherent reread; local event+link atomic; каждый physical effect требует committed link; history retained; reserve/local/P/X сериализованы. reserve_stage → reserve_in_scope в том же UOW после check. P первым запрещает reserve/local mutation; local первым требует linked path. Precheck перед independently committing reserve недостаточен. Не переносить NO_LOCAL на legacy writers.

| Recovery facts, после integrity/binding checks | Outcome |
|---|---|
| Applicable historical C | Confirmed, не hold/drain; residual finalization отдельно |
| Closed/cancel/stale | Owning refusal, не stage permission |
| Existing successor | Exact replay; второй successor запрещён |
| Live owner либо неизвестен lawful lifetime handoff | ATTEMPT_NOT_QUIESCENT, не takeover |
| Current consumed A без X/successor, exact binding, положительное lawful admission evidence | StageFinalizeInput; physical proof ещё требуется |
| Недостаточно иных evidence | INSUFFICIENT_EVIDENCE |
| Finalized | Atomic recheck C/authority/chain/X/local release/partial safety → retire g + register g+1 |

Полный порядок inspect (первая применимая строка):
1. Validation/integrity/binding/unknown fault → exception, без finalizer/finish.
2. Applicable C exact g/predecessor → Confirmed, в том числе closed/stale/residual.
3. Stage есть, operation нет → integrity fault.
4. Нет обоих → STAGE_UNTRACKED.
5. Stale operation fence → STALE_OPERATION_FENCE.
6. Matching fence + cancel terminal → OPERATION_CANCELLED.
7. Matching fence + READY/closed/иной terminal → ADMISSION_CLOSED.
8. Writable, stage нет → STAGE_UNTRACKED.
9. g future/unknown/вне chain → STALE_STAGE_ATTEMPT.
10. Successor current/unconsumed → тот же Allowed successor.
11. Successor consumed без applicable C → ATTEMPT_NOT_QUIESCENT; при доказанном drain → INSUFFICIENT_EVIDENCE. recover(g) не finalizes successor и не выдаёт g+2.
12. Current unconsumed g → тот же Allowed g, без bump.
13. Current consumed g с X → StageFinalizeInput для exact идемпотентного подтверждения, затем finish; P для normal X не выдумывается.
14. Current consumed без X, известен live owner → ATTEMPT_NOT_QUIESCENT.
15. Его lifetime неизвестен → ATTEMPT_NOT_QUIESCENT.
16. Exact A, lawful admission доказан → finalizer; только finalized ведёт в finish.
17. Иная coherent недостаточность → INSUFFICIENT_EVIDENCE; consumed без обязательной A — fault строки 1.
Это перенос priority table deferred Q3 без изменения порядка. Concrete producer lawful termination/handoff отсутствует (Q1/Q4), поэтому dispatch условен.

Lock order: OS gate → short SQL → закрыть SQL → physical batch/barrier → short SQL → release gate. Legacy ArtifactStagingService.verify и ArtifactGarbageCollector.collect держат SQL catalog.guard, но НЕ ждут gate. Gate нельзя вставить в общий _io/verify/delete. Legacy immutable/no-overwrite final, раздельные temp namespaces и holds обязательны; backend с in-place final/legacy gate отклоняется.

Linearization: P commit — future effect prohibition; seal/hold/C — один commit; join/process-object evidence — completion observation; X commit — release; retire/register commit — successor; Publication final UOW — operation release/NEW terminal. Единой SQL+FS atomic точки нет.

Q1 Windows/local NTFS proposal: LockFileEx — exclusion, не drain. Владелец предлагает WAIT_OBJECT_0 реального process HANDLE как completion barrier при отсутствии внешних executors/mapped writes и surviving HANDLE до dispatch. Это условное предложение владельца, не независимая ОС-проверка этой сводки. Кто переживает writer/cleanup, как передаётся witness, что при потере surviving host — OPEN. PID/lock/timeout не proof; скрытый supervisor не назначается. Выбор manifest/climate workflow исследованию общего backend не prerequisite.

## 5. Q6 и concrete consumers

Existing blocking cancel: close → wait local+full вне write UOW → final UOW. В final UOW integrity/current fence → historical terminal replay либо cancellation/evidence/closed checks → ВСЕ local writers по operation за все fences + full drain → holds release и NEW terminal/event одним commit → ACK. Empty inventory/один finalized не proof. Legacy local-only writer блокирует terminal независимо от batch.

Consumers: SqliteArtifactLeases.cancel/finish_preparation; SqliteArtifactHolders.release(OperationHolder)/handoff; SqliteOperationStore.claim_publication/_save через record_terminal/record_refusal. Own local _release/_cleanup не ждут full drain. Ledger/ArtifactStagingService — delegation. Factories: core/container/packs.py::PacksWiring.initialize_pack_storage; tests/snapshotCore/support/fixtures.py::live_database; artifactFixtures.py::adapters; tests/typing/snapshotCore/valid.py::sqlite_composition. ManifestBlobBackend и manifest/climate registrations затронуты общим backend constructor, production binding не выбирается.

Unknown final commit допускает совершившиеся release+terminal: authoritative replay без compensation. Historical terminal replay не пишет новый terminal и не подтверждает residual cleanup. Timeout/cancellation не release authority. Exact same-graph/all-fence predicate wiring consumers остаётся OPEN.

## 6. Actual код и reuse

Проверенный ArtifactStageWriter.write: reserve → backend.write → отдельный admission.writer для verify/seal. ContentAddressedBlobBackend.write: свой leases.writer, _io shield/join, random mkstemp, direct unlink в finally; verify делает fsync. Это live cancellation, не crash proof. Поиск stageAttempt/finalization/drain модулей в backend/app результата не дал: новые authority/jobs — target.

Actual InvocationCoordinator содержит _live/identity_required/payload и __init__ RUNNING→READY. План identity §§6–7 требует адресной замены обходного cache представлением runtime/wire и owner-entry; наличие cache не доказывает реализацию этого target. Для stage существенен подтверждённый кодом unconditional RUNNING→READY: он не обеспечивает owning recovery до повторного эффекта. SR-02 REPORT_UNKNOWN/CallOrigin — target, не actual.
SR-04 namespace уже получил owning scoped compatibility: пять length-prefixed компонентов begin CALL, Unicode code-point lengths, без normalization/truncation, canonical decimal. EntityUid без max_length; результат валидируется, не исправляется hash. OPEN именно public Engine wiring/конкретный parent, а не повторный выбор формата владельцем Artifacts.
Engine target: NodeContract.interrupted_call RETRY|REPORT_UNKNOWN; persisted registry policy; OUTCOME_UNKNOWN и CallOutcomeUnknown(lost_attempt: ExecutionIdentity); эффектный stage retry_policy=None. Reconcile под existing owner → checkpoint CAS до scheduling → at-least-once parent event → deterministic recovery CALL из сохранённых binding/generation. accept dedup по parent/step/key; begin/recover RETRY допустим только при owning exact-request idempotency. Runtime/declared error/unknown не сливаются. ResumablePythonNode.start(input: I, origin: CallOrigin) -> NodeStep[O,S], resume(state: S, event: ResumeEvent, origin: CallOrigin) -> NodeStep[O,S]; CallOrigin(execution_id: ExecutionId, parent_invocation_id: InvocationId, parent_step: int). Новых нод/порядка эта сводка не назначает.

Reuse: worker join, registry, lease/holder/catalog predicates, UOW/ACK/quarantine, checkpoint CAS/owner loop. Target replacement этапа 2: backend local lifetime → writer full/local lifetime; duplicated seal → scoped seal; unconditional interrupted replay → согласуемый REPORT_UNKNOWN. Ни второго registry/lifecycle, ни general CRUD. History binding/generation/completion retain; terminal/GC не deletion authority.

## 7. Источники и происхождение решений

[Deferred](artifacts-stage-finalization-deferred.md), [owning](artifacts-stage-recovery-owning-resolution.md), [Publication](artifacts-stage-recovery-publication-resolution.md), [fencing](artifacts-stage-recovery-backend-fencing.md), [recovery contract](artifacts-stage-recovery-contract.md), [Engine transition](dag-stage-recovery-transition-resolution.md), [identity](dag-artifacts-identity-transport.md); [координация](../rules/interdomain-contract-coordination.mdc), [DAG критерии](../rules/dag-generator-interface.mdc), [implement-plan](../../.agents/skills/implement-plan/SKILL.md).

| Документ / раздел | Происхождение и статус |
|---|---|
| Owning «Приоритетный статус», deferred вводная | Зафиксированное решение пользователя отделить этап 2; DEFERRED, не code-go |
| Owning терминология перед RC-CONSTRUCTION | Зафиксированное решение пользователя execution finalization; не приёмка всего API |
| Publication «Принятое пользователем разделение поставки — вариант 2» | Штатная запись и blocking cancel отдельно от crash recovery |
| Owning Q1 | Process-object barrier и отсутствие surviving owner — proposal/ограничение, не accepted automatic recovery |
| Deferred Q2/Q3 | Приоритетные no-link и recovery dispatch уточнения; заменяют старый blanket insufficient evidence и неполный dispatch |
| Owning COMP-01…05 / RC-CONSTRUCTION | Один registration, SQL-only store, отдельные jobs, один release commit; physical store/repeated local acquire WITHDRAWN |
| Owning Q5 + Publication Q5 | Совпадающие current close→inventory→finalization contracts, предъявленные для общей приёмки |
| Publication Q6 | Existing cancel с all-fence local/full final recheck; не новый lifecycle |
| Owning SR-04-CALLER | Scoped compatibility namespace уже подтверждена; public Engine delivery ещё OPEN |
| Engine transition + identity §§6–7 | Target generic transport/recovery, не evidence выполненной реализации |
| Fencing RC-01…04 | Исторический аудит и границы; при расхождении применяются explicit owning уточнения Q1–Q6, не «последняя дата = acceptance» |

Источники приёмки — явно записанные пользовательские решения в документах. Предложения владельцев и scoped compatibility не повышаются до общей пользовательской приёмки. Чтение переписки не prerequisite этой сводки.

## 8. Вердикты, OPEN и пакет приёмки

| Вопрос | Вердикт / владелец / зависимость |
|---|---|
| Q1 / DF-01 / RC-01 | OPEN Artifacts: surviving witness owner/association/lifetime/failure model. Блокирует linked cleanup/release/automatic recovery |
| Q2 / DF-02 / RC-03 | Scoped PASS логике NO_LOCAL и reserve/local/P сериализации; требуется совместно принять proposed reserve_in_scope. Реализация/caller coverage ещё не выполнены, это не пробел алгоритма |
| Q3 / DF-03 | Таблица есть, OPEN producer lawful lifetime admission Q1/Q4. SQL absence/timeout не dispatch proof |
| Q4 / DF-04 | OPEN Artifacts: repeated cancellation ownership/handoff gate/join/cleanup/release ACK, task affinity; stage-1 shield недостаточен |
| Q5 / RC-02 | Scoped PASS exact close→inventory→finalize mapping, полноте и canonical именам. Full route OPEN только concrete DAG/error transport и Q1/Q4 |
| Q6 | Scoped PASS operation-wide final recheck и existing cancel reuse. OPEN exact scoped local-predicate reuse для остальных consumers; full safety зависит от Q1/Q4 |
| RC-04 | Target lock order совместим при legacy no-gate; runtime/concurrency не подтверждены |

| Обязательный критерий | Вердикт |
|---|---|
| Нет pipeline branching следующей операции | Target соблюдён; concrete parent OPEN |
| Нет скрытого запуска вне DAG | Target соблюдён; witness provider не может стать hidden orchestrator |
| Нет foreign public service calls | Target соблюдён через POJO/scoped infrastructure; integration отсутствует |
| Ответственность каждого класса | Роли/store/jobs/registry разделены; OPEN конкретный witness owner и Q4 lifetime |
| Public / pipeline / implementation boundaries | Claim/guard/scope не экспортируются; Q1 provider/Q4 lifetime и wire OPEN |
| Утверждённый порядок | Этап 1 сохранён; concrete новый route не назначен/не принят |
| CRUD данных и настроек | General CRUD/settings не добавляются; полная доменная CRUD приёмка не проведена |
| Междоменный protocol | Close→inventory→finalize operands замкнуты; CALL targets/parent/consumers OPEN |
| POJO/field/relation без дублей | Reuse описан; field/relation/input/durable различены без mirrors; cold schema allowlist/Engine cause OPEN |

Общий вердикт: ОТКАЗ В ПРИЁМКЕ полного implementation plan этапа 2 до закрытия OPEN. Unresolved — безопасная остановка, не завершённое automatic recovery.

Пакет совместных решений: подтвердить scoped Q5 формы/имена и три разных результата; рассмотреть Q2 reserve/link/NO_LOCAL transaction дельту; определить failure model и допустимого surviving evidence owner Q1; закрыть exact Q4 lifetime и producer Q3; согласовать all-fence guards Q6; отдельно принять Engine parent/CallOrigin/REPORT_UNKNOWN/error mapping по актуальному identity-плану; повторить полную архитектурную приёмку. Новые поручения доменам не отправлены.

Будущие проверки: crash на A/R/L/P/C/X; lost ACK; writer и повторный cleanup process loss; старый writer после P; concurrent finalizers; repeated cancellation всех handle/commit границ; NO_LOCAL shared reserve; BOTH с unresolved stage; empty batch с legacy writer; all-fence local query; два cancel; seal vs P; unknown terminal; отсутствие SQL→OS; replay без второго successor; Engine at-least-once без stage retry. Тесты proposed API не выполнялись.

## 9. Адресные разногласия и решения, требуемые до code-go

| ID | Точный остаток | Владелец / решение / зависимая часть |
|---|---|---|
| U1 | Q1 требует process HANDLE до dispatch, переживающий writer и каждый cleanup owner; composition такого lifetime не содержит | Artifacts обязан предъявить конкретного кандидата surviving owner, constructor/provider, association/передачу/release и failure model, включая потерю самого owner. Координатор сверяет цепочку, пользователь принимает или отклоняет предъявленную дельту. Задача проектирования не переносится на пользователя/DAG. Без этого linked automatic finalization OPEN; общий backend исследуется независимо от workflow |
| U2 | Q4 содержит happy-path release, но не полный repeated-cancellation handoff/task-affinity/ACK протокол | Artifacts: для каждого await gate/join/cleanup/release определить одного владельца handle, подтверждение завершения и повторное распространение cancellation/fault. Блокирует normal error exit и Q3 lawful admission |
| U3 | Q3 строка 16 требует positive lawful runtime termination/handoff; SQL store этого не производит | Artifacts writer/finalizer lifetime и composition предъявляют producer, форму, lifetime и передачу evidence; SqliteStageAttemptStore проверяет доступные ему facts. ArtifactStageRecovery только ведёт inspect/finalizer/finish, не присваивает брошенный lifetime. До замыкания стыка строка 15, без takeover |
| U4 | Q2 вводит reserve_in_scope и FINALIZE view без reservation, тогда как ранний RC-CONSTRUCTION требует reservation | Принять explicit Q2 override: reservation только для linked view, no-link не synthetic acquire. Нужна точная nominal форма internal view от Artifacts; не добавлять optional public lease/DTO. Блокирует реализацию no-link handle, не логическое доказательство NO_LOCAL |
| U5 | Q6 назвал all-operation _writers(scope,operation_id), но reuse этой private query в holders/operationStore не оформлен полным scoped port | Publication/Artifacts: exact internal query/constructor dependency и same-graph consumers без второй policy. Блокирует полную consumer migration |
| U6 | Finalize EFFECTS_NOT_QUIESCENT → recovery ATTEMPT_NOT_QUIESCENT требует сохранения cause, но result POJO имеет только binding/code | Artifacts/Fields/Engine: exact существующий diagnostic transport либо отдельно согласованная DTO дельта. Не вставлять поле самостоятельно. Блокирует lossless error round-trip |
| U7 | Engine target REPORT_UNKNOWN/CallOrigin ещё не даёт concrete accepted parent/leaf/continuation mapping | Engine/DAG: точные CALL targets и POJO в отдельной совместной приёмке без новых нод из этой сводки. Namespace Artifacts не переоткрывается |

Устранённые разногласия не остаются OPEN: полный lease на inventory input отозван; Busy как close proof отозван; stage-2 seal имеет full/local/reservation; store не получает backend; legacy verify/GC не ждут gate; local/full release один; имена Q5 совпадают. Отсутствие реализации proposed API само по себе не дефект плановой спецификации.

### Критерии проверки по Q1–Q6

| Проверка | Ожидаемое evidence / основание отказа |
|---|---|
| Q1 writer и cleanup process loss; old writer после P | Каждый submitted effect owner покрыт witness/join; lock/timeout/P без barrier не разрешают cleanup/X |
| Q2 crash до A, A ACK, reserve commit, local/link commit, dispatch | No-L release только после P и полного NO_LOCAL; shared R/holds сохранены; L commit до ACK идёт через barrier |
| Q3 inspect→finalizer→finish и concurrent recover | Все 17 приоритетов; после errors/unresolved finish не вызывается; единственный successor, lost ACK exact replay |
| Q4 repeated cancel на всех await | Ни потерянного handle, ни detached cleanup, ни двойного release, ни false confirmed ACK; основной fault/cancellation сохранён |
| Q5 несколько stages/generations/fences, C без X, no-link, partial batch progress | Inventory ровно A минус X; никакого latest-only фильтра, pagination/partial success, lease reconstruction |
| Q6 empty inventory + legacy local writer, BOTH, concurrent cancel/finalization | Ноль NEW terminal/release до local+full drain в том же UOW; historical replay не пишет повторно |

Пакет приёмки разделён: A — scoped Q2 логика, Q5 exact data mapping, Q6 final transaction policy, RC-CONSTRUCTION/RC-04 ownership и lock order; B — решения U1–U7 до полного architecture PASS; C — implementation и проверки после отдельного разрешения пользователя. Принятие A не принимает B/C и не возобновляет этап 2.

## 10. Сведение новых таблиц владельцев — 2026-11-27

Основания: [Artifacts Q1, владельцы итогового решения](artifacts-stage-recovery-owning-resolution.md#владельцы-итогового-решения-и-оставшихся-действий-q1); [deferred, итог Q2](artifacts-stage-finalization-deferred.md#итог-q2-и-владельцы-оставшихся-проверок--2026-11-27) и таблица «Владельцы итоговых пунктов Q3» в его разделе Q3; [Publication, итоговый пакет Q5](artifacts-stage-recovery-publication-resolution.md#q5--окончательная-publication-форма-для-общей-приёмки-2026-11-27). Это уточнение распределения работы, не новые поручения и не runtime/code-go.

| Стык | Единственный владелец решения/результата | Смежная обязанность | Итог координаторской сверки |
|---|---|---|---|
| Q1 physical proof и surviving witness composition | Artifacts: backend/finalizer, владелец Q1 | Координатор проверяет последствия; пользователь принимает конкретный scope/failure model после предложения | Ответственный за доведение архитектуры определён. Runtime owner ещё не назначен; U1 остаётся OPEN. Завершён вывод исследования об ограничении, не automatic recovery |
| Q2 reserve/local/P/X и NO_LOCAL | Artifacts: attempt store/catalog/writer/finalizer | Snapshot — existing transaction infrastructure; Publication — operation holds/final drain | Владение domain predicates и transaction infrastructure не конкурирует. Не требуется выбирать backend/workflow. Scoped логическая совместимость сохраняется; nominal no-link view U4 ещё не определён |
| Q3 inspect/finalize/finish dispatch | Artifacts: ArtifactStageRecovery | Store — atomic finish/chain/replay; DAG — следующий public CALL | Локальная последовательность owning операции не второй оркестратор; таблица не меняет DAG-порядок |
| Q3 lawful admission evidence | Artifacts: writer/finalizer lifetime и composition | Store проверяет facts, recovery job принимает результат inspection | U3 не обязанность Engine/DAG и не SQL observation. Producer/форма/lifetime по-прежнему OPEN |
| Q4 cancellation/handoff | Artifacts: writer/finalizer/recovery jobs и contexts | Q1 предъявляет требования к evidence lifetime | Владелец указан, но exact repeated-cancellation trace не предъявлен. U2 не закрыт одной таблицей ответственности |
| Q5 close Input/Result/Error и ACK | Publication: OperationLedger и existing lifecycle adapter | Artifacts не принимает close за Publication | Owning итог предъявлен; дополнительных вариантов close API не требуется |
| Q5 inventory и exact finalization operands | Artifacts: StageAttemptService/store/finalizer | DAG переносит request/item целиком; Publication не строит stage inventory | Совпадение producer/consumer подтверждено; отдельного незакрытого вопроса «кто собирает lease» нет |
| Q6 operation release/terminal | Publication: lifecycle/holds | Artifacts предоставляет full-drain predicate, local-only учитывается отдельно | Один terminal owner. Закрытие Q5 не разрешает operation release; U5 касается exact внутреннего reuse/wiring, не спора о владельце |
| Q3 error/cause | Artifacts: исходная категория и owning mapping | Engine: generic checkpoint/error transport; Fields/C0: diagnostics/canonical paths | Разделение согласуется; exact wire carrier U6 пока отсутствует. Fields не определяет recovery policy, Engine не классифицирует Artifacts exceptions |
| Общая приёмка | Назначенный DAG-координатор выдаёт scoped PASS/OPEN/FAIL; окончательное решение — пользователь | Владельцы предъявляют конкретные законченные пакеты своих границ | Указание адресата не заменяет архитектурный результат и не переносит работу владельца на пользователя |

**Что изменилось в вердикте.** Снята неоднозначность ответственного за предложение surviving owner и lawful admission producer; исправлены U1/U3. Q2/Q3/Q5 имеют согласуемое распределение обязанностей без конкурирующего authority owner. Ни одна новая таблица не предъявляет недостающие resource lifetime, nominal no-link view, scoped local port или wire carrier, поэтому технические U1–U7 не объявляются закрытыми. Q1 теперь следует формулировать как «Artifacts завершил исследование текущего протокола и предъявил ограничение; должен подготовить конкретную composition дельту», а не «пользователь должен придумать surviving owner».

Следующий необходимый результат для общей приёмки — конкретный пакет Artifacts по U1/U2/U3 с учётом названных владельцев; независимые Q5 operands и Q6 policy не надо проектировать заново. Поручения в чаты не отправлялись, пользовательское согласие не предполагается.

