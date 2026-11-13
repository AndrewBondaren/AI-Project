# Ответ Artifacts/publication по Source mutation

Актуальное уточнение refusal/recovery и root acquire от 2026-11-14 приведено в конце документа. Оно заменяет предложение отдельной refusal transaction для обычного Source expected/membership отказа. Статус DESIGN OPEN сохраняется.

2026-11-13. Контрактное предложение, DESIGN OPEN. Подготовлено по P2.3–P2.5 source-pregame-revision-staging-design.md. Приёмка SourceDurableProof и R1/R2 является исходной зависимостью. Документ фиксирует обсуждение refusal/recovery и root acquisition; реализация требует отдельной приёмки.

## Refusal после подтверждённого rollback

Рекомендуется terminal отказа. Один operation_id связывается с окончательным результатом. Exact replay возвращает исходный отказ. Исправленный запрос или новые expected revisions используют новую operation identity.

Source-owned SourceMutationRefused в backend/app/dataModel/sourceVersioning/sourceMutationOutcome.py содержит operation_id, world_uid, request_fingerprint и failure: SourceFailure. Record frozen/strict/extra-forbid/revalidate-always. Failure.operation равен APPLY_MUTATION; исходные issues и порядок сохраняются. Envelope связывает отказ с запросом в общем ledger.

Предлагается discriminator source_mutation_refused, category=None. OperationRecord проверяет SOURCE_MUTATION, world, operation identity и request fingerprint. Terminal union, StoredTerminalCodec, manifest и storage checks требуют совместной регистрации. Canonical IDs остаются OPEN.

SourceMutationRollback в backend/app/application/worldData/sourceVersioning/sourceMutationErrors.py переносит SourceFailure через внешнюю transaction boundary. ConfirmedRollback в backend/app/application/publication/contracts/rollbackEvidence.py — непрозрачная runtime capability coordinator. Она связана с database/coordinator, transaction attempt, operation identity и lease/fence. Выдаётся только после подтверждённого rollback. Точный rollback-carrier API остаётся OPEN.

Предлагаемые internal signatures:

```python
def transaction_for_claim(
    claim: PublicationOwner,
) -> AbstractAsyncContextManager[CommitScope]: ...

async def record_source_refusal(
    claim: PublicationOwner,
    rollback: ConfirmedRollback,
    outcome: SourceMutationRefused,
) -> SourceMutationRefused: ...
```

Первый метод принадлежит общему commit owner. Второй — IOperationStore, OperationLedger и SqliteOperationStore. Source apply owner вызывает их внутри одной атомарной доменной операции.

Порядок: Source поднимает rollback-carrier с failure; coordinator подтверждает rollback, отзывает scope и выдаёт capability; наружная граница формирует envelope; record_source_refusal открывает короткую bookkeeping transaction, повторно проверяет binding/claim/fence/admission/drain/evidence, освобождает только operation holds этой операции и сохраняет terminal. После подтверждённого commit caller получает исходный SourceFailure. Release и terminal атомарны; все затрагиваемые holder chains проверяются до первого release.

transaction_for_claim должен обеспечивать одну активную apply attempt на claim, после rollback переводя runtime ownership в finalizing. Отсутствие artifact writer claims само по себе не доказывает отсутствие конкурирующей domain apply attempt. Межпроцессный takeover остаётся OPEN.

Предложение RefusalFinalizationError в backend/app/application/publication/errors.py содержит operation_id и enum-код STALE_CLAIM, BINDING_MISMATCH, INVALID_ROLLBACK_EVIDENCE либо TERMINAL_MISMATCH. Live writer/недоказанная quiescence дают OperationBusyError; повреждение persisted chains — PublicationInfrastructureError; неподтверждённый commit/rollback — UnknownCommitOutcome.

Exact terminal replay возвращает сохранённый отказ до повторного cleanup. Unknown domain commit запрещает запись refusal до recovery. Recovery читает общий terminal: Applied возвращает прежний успех, Refused — прежний failure. При отсутствии terminal операция остаётся unresolved.

Аварийное окно между rollback и записью refusal остаётся OPEN: runtime evidence и failure могут быть утрачены. Требуется принятие durable recovery protocol либо fenced takeover с явно определённой семантикой повторной попытки. Повторная проверка изменившегося latest не восстанавливает исходный отказ.

## Historical roots и acquire

Уточнение прежнего предложения по P2.4: root каждой body-bearing revision сохраняется до explicit prune. A→B приобретает root B и сохраняет root A. DELETE сохраняет roots исторических live revisions. Label-only использует прежний exact ref/root.

Предложение SourceRootHolder в backend/app/dataModel/artifacts/lifecycle/sourceRootHolder.py содержит kind=SOURCE_ROOT и source: SourceVersionRef | SourceCollectionVersionRef. Полный source ref задаёт holder identity. Artifacts владеет representation/codec, Source — eligibility и lifetime.

Предлагаемая signature в backend/app/application/artifacts/contracts/sourceRootPort.py:

```python
async def acquire(
    self,
    scope: CommitScope,
    claim: PublicationOwner,
    holder: SourceRootHolder,
) -> None | SourceFailure: ...
```

Реализация — предлагаемый backend/app/db/repositories/sqlite/artifacts/sourceRootStore.py. Scope проверяется по task/database/lifetime/write authority. Registry operation_id должен совпасть с claim. Persisted record должен иметь SOURCE_MUTATION, APPLYING и тот же полный lease/fence. Admission закрыт, writer claims drained, world holder совпадает с operation world.

Предлагаемый SourceRootReadBinding.retained_refs(scope, source, operation=...) вычисляет exact canonical storage closure без writes/latest. Для полномочия fresh uncommitted mapping дополнительно нужна Source-owned проверка:

```python
async def validate_acquisition(
    self,
    scope: CommitScope,
    source: SourceVersionRef | SourceCollectionVersionRef,
    *,
    operation_id: EntityUid,
    operation: SourceOperation,
) -> None | SourceFailure: ...
```

Предлагаемое размещение — backend/app/application/worldData/sourceVersioning/retention/rootEligibilityBinding.py. Проверяются persisted operation→exact revision linkage, world/descriptor/status mapping и участие revision в текущей mutation. Для no-op требуется связь текущей операции с прежней revision; одного created_by_operation недостаточно. Конкретное хранение linkage остаётся OPEN. Использовать Source index linkage P1, без второй копии terminal outcome.

Порядок acquire: scope/claim validation → Source eligibility → retained_refs → проверка всего closure → holder appends. До первого append проверяются catalog identity, sealed состояние, holder chains и защита bytes. Fresh bodies имеют operation hold claim. Для переиспользуемых dependencies нужно согласовать набор допустимых исходных durable holders. Общий writer scope сериализован с GC. SourceFailure до записи возвращается caller; storage failure после начала appends пересекает transaction boundary и вызывает rollback.

Source failures используют existing codes для world/descriptor/status/mapping/body. Для отсутствующего operation→revision linkage предложен MUTATION_BINDING_MISMATCH, решение OPEN. Scope/lease/fence/phase ошибки требуют owning typed infrastructure contract, его enum OPEN. Busy, infrastructure corruption и unknown outcome сохраняют общие исключения.

Mutation binding не содержит release. Explicit-prune binding отдельно повторяет latest/external usage checks, затем атомарно отмечает mapping pruned и снимает root выбранного exact ref. Собственный archival root исключается только из причин запрета prune. До release он защищает bytes от physical GC. Roots других revisions и capture/publication holders сохраняются.

Collection root удерживает storage closure collection body. Member bodies удерживаются по принятому capture-контракту. Refusal cleanup после rollback освобождает operation holds; новые Source mappings/roots уже откатились вместе, исторические roots продолжают действовать.

## Открытые решения до приёмки

- Canonical регистрация refusal envelope и точный rollback-carrier API.
- Единственная apply attempt на claim и recovery аварийного окна до записи refusal.
- Scoped operation→revision linkage, включая no-op.
- Source eligibility и согласование MUTATION_BINDING_MISMATCH.
- Допустимые исходные holders переиспользуемых closure artifacts.
- Typed infrastructure errors root acquire.
- Отдельный explicit-prune/usage контракт release.

Предложения не назначают новый DAG порядок или публичные междоменные pipelines. Порядок поставки остаётся inventory → projector/body codec → mutation/error contract → lifecycle/terminal/refusal → Source index/eligibility → root binding → atomic apply/recovery tests. P2/P3 остаются OPEN до совместной приёмки перечисленных решений.

## Уточнение 2026-11-14 — рекомендуемый savepoint protocol

Рекомендуется один внешний BEGIN IMMEDIATE и внутренний domain savepoint. При Source refusal coordinator выполняет ROLLBACK TO и RELEASE domain savepoint, затем сохраняет исходный SourceMutationRefused и cleanup operation holds во внешней transaction. Единственный COMMIT делает отказ и cleanup видимыми вместе. Successful branch сохраняет domain writes, roots и SourceMutationApplied тем же внешним COMMIT.

Это изменение принятого infrastructure контракта. Сейчас SqliteTransactionDriver поддерживает begin/commit/rollback, SqlitePublicationCommitStore откатывает всю transaction при исключении, SqliteScopeRegistry отзывает все capabilities task одновременно. Требуются ack-safe savepoint commands, отдельное поколение domain scope и фазовые права control scope. Общий запрет nested/ambient transaction сохраняет силу: SAVEPOINT управляет единственный coordinator внутри собственного UOW.

Предлагаемый internal контракт в application/publication/contracts/attemptStore.py:

```python
def attempt(
    self, claim: PublicationOwner, request_fingerprint: RevisionHex,
) -> AbstractAsyncContextManager[PublicationAttempt]: ...

class PublicationAttempt:
    def domain(self) -> AbstractAsyncContextManager[CommitScope]: ...
    async def refuse(self, outcome: SourceMutationRefused) -> None: ...
    async def succeed(self, outcome: SourceMutationApplied) -> None: ...
```

PublicationAttempt — runtime capability, не DTO. Source application implementation владеет локальной последовательностью. domain() выдаётся ровно один раз. SourceMutationRollback(failure) выходит из domain(), coordinator подтверждает rollback savepoint и отзывает domain scope и все derived read scopes. Только после этого refuse разрешён. Successful domain exit переводит attempt в состояние, допускающее succeed. Outer exit без установленного terminal откатывает transaction и даёт infrastructure failure. Наружный return допускается после подтверждённого outer commit.

Generic coordinator не импортирует SourceFailure. PublicationAttempt реализация в publication binding получает уже проверенный terminal union, а SourceMutationRollback обрабатывает Source owner после завершения domain context. Callback с доступом к raw connection не вводится. Stored terminal сохраняет failure без преобразования кодов, порядка и полей. Отдельный ConfirmedRollback, переживающий outer transaction, для этого пути больше не нужен.

Ownership: driver выполняет только команды и drain acknowledgement; registry управляет phase/generation capabilities; attempt coordinator управляет единственным UOW/savepoint и допустимыми переходами; operation store проверяет binding и записывает общий terminal; Source вычисляет failure/outcome; artifact binding освобождает только operation holds. Domain scope недействителен после domain exit, включая stale references и child tasks. Control scope не выдаётся Source/domain handlers.

### Единственная apply attempt

Для Source предлагается append-only attempt-start факт в существующем operation ledger с unique(operation_id, fence). Предлагаемая модель db/models/snapshotCore/operationRows.py::PublicationAttemptStartedRow(operation_id, fence, attempt_id, request_fingerprint). Запись start выполняется вместе с READY→APPLYING в claim transaction, до выдачи owner. attempt_id хранится в выданной runtime capability publication binding; сериализуемый PublicationOwner сам по себе не даёт права повторно запускать domain().

Внешний attempt BEGIN IMMEDIATE повторно проверяет полный binding, current fence, start identity и terminal. Runtime registry допускает одну domain() на выданную capability. Другой процесс получает busy через existing claim. Terminal replay возвращается до выдачи domain scope. Запрет повторной выдачи capability существующему APPLYING обязателен, включая restart. Это требует принятия механизма выдачи attempt capability вместе с claim result; точный новый result type согласуется до implementation, existing PublicationOwner DTO не расширяется молча.

### Crash и неизвестный commit

Savepoint устраняет промежуток между двумя commits domain rollback и refusal terminal. При crash до outer COMMIT вся outer transaction откатывается. Durable start остаётся, terminal отсутствует. Исходный failure мог существовать только в памяти; его нельзя обещать восстановить. Такой record имеет unresolved attempt, повторный domain apply с тем же operation_id запрещён.

При unknown acknowledgement fresh connection читает terminal под writer serialization после освобождения предыдущей transaction. Existing terminal возвращается точно. При отсутствии terminal операция остаётся unresolved; никакой latest recheck под видом replay. Наличие свободного SQLite writer lock доказывает завершение прежней DB transaction, но не смерть прежнего процесса, поэтому одного lock для takeover недостаточно.

Рекомендуемая первая поставка использует fail-closed unresolved recovery. Новая mutation допустима с новой operation identity только по явному решению caller и обычным expected checks. Для административного завершения unresolved attempt требуется отдельный fenced abandon contract с доказанной quiescence/отзывом полномочий и drain. SourceFailure при таком abandon не фабрикуется. Exact business refusal гарантирован после durable terminal commit. Commit acknowledgement loss восстанавливается из этого terminal.

Решение пользователя требуется по гарантии crash-before-terminal: принять fail-closed unresolved и запрет повторного body для той же identity либо потребовать дальнейший durable decision protocol. Второй вариант расширяет общий ledger/transaction protocol и требует отдельного дизайна. Сохранение произвольного in-memory failure при crash до его durable записи технически невозможно. Дополнительная запись решения в той же outer SQLite transaction имеет ту же crash границу.

Критические тесты: refusal после partial domain writes; crash после savepoint rollback до outer commit; crash после outer commit до ответа; double domain() на одной capability; два claims; stale domain read/write scope; cancellation во время rollback-to/release/commit; конфликт другого terminal; release refusal при corrupt holder chain. До последнего COMMIT все публичные reads другого соединения видят прежнее domain состояние; после него refusal и cleanup видимы вместе.

## Уточнение 2026-11-14 — root acquisition errors и исходные holds

Предлагается application/artifacts/errors/sourceRootAcquireError.py с frozen strict SourceRootAcquireFault и SourceRootAcquireError, несущим fault. Fault содержит code: SourceRootAcquireCode, operation_id: EntityUid, source: SourceVersionRef | SourceCollectionVersionRef, artifact: ArtifactRef | None. Закрытые коды INVALID_SCOPE, OPERATION_MISMATCH, STALE_CLAIM, WRONG_KIND, WRONG_PHASE, ADMISSION_OPEN. Проверки exact DTO до IO используют стандартные validation errors. Active writers дают OperationBusyError; corrupt persisted chains дают PublicationInfrastructureError; transaction uncertainty остаётся UnknownCommitOutcome. Ошибки Source eligibility/closure возвращают исходный SourceFailure.

Для каждого closure artifact допустимы current OperationHolder того же полного claim lease, SourceRootHolder существующей exact revision, SnapshotHolder, ArtifactRetentionHolder sealed owner или действующий PinHolder принятого lifecycle. Чужой OperationHolder не является durable основанием reuse. SourceRootHolder проверяется по exact не-pruned mapping, PinHolder — по своему действующему owning lifecycle; нельзя создать произвольный Pin для обхода acquire. Snapshot/history и artifact-retention owners проверяются штатными typed adapters. Для artifact-retention требуется доказанная защита owner artifact, а не только seal; циклические/self-retention цепочки без anchored holder отвергаются.

Первая рекомендуемая поставка ограничивает reused dependencies доказуемыми current-operation и SourceRootHolder путями. Остальные виды допускаются после подключения их existing scoped eligibility/closure checks и negative tests; до этого их предъявление даёт SourceFailure с MISSING_HOLD через Source-owned mapping результата проверки. Это явное ограничение supported binding, перечень будущих разрешённых owners выше сам по себе его не расширяет.

Все artifact rows, seals, owner eligibility и полный closure проверяются в одном writer scope до первого root append. Source retained_refs задаёт exact closure, validate_acquisition доказывает operation→revision linkage, artifact adapter проверяет существующую защиту каждого ref. Release новых operation holds выполняется после приобретения всех roots. Reused roots иных revisions сохраняются. Historical own root исключается только из usage blockers explicit prune, но учитывается physical GC.
