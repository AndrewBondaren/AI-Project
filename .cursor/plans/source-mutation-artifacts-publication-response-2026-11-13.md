# Ответ Artifacts/publication по Source mutation

Дополнение execution-unavailable по Source P2.13 в конце уточняет RecoveryContractFault и logging projection того же семейства.

Актуальные signatures, CAS mismatch и durable single-start определены в завершающем разделе REC-2–4. Он заменяет прежний вход transaction_for_attempt(serializable owner) и неоднозначный возврат state при mismatch.

Решение пользователя от 2026-11-14: explicit recovery с тем же operation_id, original immutable request/expected и новой fenced attempt согласовано при обязательном production logging от причины до результата. Это принятие semantics; полный runtime design остаётся на приёмке. Logging contract приведён в последнем разделе.

Решение пользователя 2026-11-14: сначала полный recovery protocol. Fail-closed unresolved допускается только как промежуточный безопасный статус. Рекомендуемый полный протокол и необходимое решение о semantics повторной незавершённой попытки приведены в последнем разделе.

Последнее уточнение по Source P2.7–P2.9 находится в разделе «Согласование linkage и no-op». Для первой поставки оно фиксирует закрытый перечень допустимых исходных holders и уточняет результат eligibility. Статус предложений DESIGN OPEN.

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

SourceRootAcquireFault и SourceRootAcquireCode определяются в backend/app/dataModel/artifacts/lifecycle/sourceRootAcquireFault.py. Application exception SourceRootAcquireError в application/artifacts/errors/sourceRootAcquireError.py переносит этот fault. Fault содержит code: SourceRootAcquireCode, operation_id: EntityUid, source: SourceVersionRef | SourceCollectionVersionRef, artifact: ArtifactRef | None. Закрытые коды INVALID_SCOPE, OPERATION_MISMATCH, STALE_CLAIM, WRONG_KIND, WRONG_PHASE, ADMISSION_OPEN. Проверки exact DTO до IO используют стандартные validation errors. Active writers дают OperationBusyError; corrupt persisted chains дают PublicationInfrastructureError; transaction uncertainty остаётся UnknownCommitOutcome. Ошибки Source eligibility/closure возвращают исходный SourceFailure.

Для каждого closure artifact допустимы current OperationHolder того же полного claim lease, SourceRootHolder существующей exact revision, SnapshotHolder, ArtifactRetentionHolder sealed owner или действующий PinHolder принятого lifecycle. Чужой OperationHolder не является durable основанием reuse. SourceRootHolder проверяется по exact не-pruned mapping, PinHolder — по своему действующему owning lifecycle; нельзя создать произвольный Pin для обхода acquire. Snapshot/history и artifact-retention owners проверяются штатными typed adapters. Для artifact-retention требуется доказанная защита owner artifact, а не только seal; циклические/self-retention цепочки без anchored holder отвергаются.

Первая рекомендуемая поставка ограничивает reused dependencies доказуемыми current-operation и SourceRootHolder путями. Остальные виды допускаются после подключения их existing scoped eligibility/closure checks и negative tests; до этого их предъявление даёт SourceFailure с MISSING_HOLD через Source-owned mapping результата проверки. Это явное ограничение supported binding, перечень будущих разрешённых owners выше сам по себе его не расширяет.

Все artifact rows, seals, owner eligibility и полный closure проверяются в одном writer scope до первого root append. Source retained_refs задаёт exact closure, validate_acquisition доказывает operation→revision linkage, artifact adapter проверяет существующую защиту каждого ref. Release новых operation holds выполняется после приобретения всех roots. Reused roots иных revisions сохраняются. Historical own root исключается только из usage blockers explicit prune, но учитывается physical GC.

## Согласование linkage и no-op — 2026-11-14

P2.7–P2.9 согласуются с savepoint protocol. Полный link set записывается после revisions до root acquire в domain scope. Любой SourceFailure от link, eligibility либо root adapter пересекает domain boundary через rollback-carrier. Откатываются все domain rows, revisions, links и новые holds попытки, затем внешний owner сохраняет исходный refusal terminal.

Результат validate_acquisition None | SourceFailure не сообщает adapter, разрешено ли создание первого root. Valid link и body-bearing revision возможны для fresh revision и no-op. Предлагается internal enum SourceRootAcquisitionMode со значениями CREATE="create" и REQUIRE_EXISTING="require_existing" в backend/app/application/worldData/sourceVersioning/retention/rootEligibilityBinding.py:

```python
async def validate_acquisition(
    self, scope: CommitScope,
    source: SourceVersionRef | SourceCollectionVersionRef,
    *, operation_id: EntityUid, operation: SourceOperation,
) -> SourceRootAcquisitionMode | SourceFailure: ...
```

CREATE означает revision, созданную данной активной domain attempt. REQUIRE_EXISTING означает прежнюю revision, включая no-op/label-only. Source выводит решение из exact revision provenance и участия в текущей попытке. Способ доказательства свежести в Source storage остаётся OPEN; одного contains(operation_id, source) недостаточно.

Для REQUIRE_EXISTING Artifacts проверяет полный набор собственных SourceRootHolder(source) на всём closure и выполняет ноль holder appends. Missing own root даёт MISSING_HOLD даже при наличии другого holder. Tombstone/pruned mapping отвергается eligibility до выбора mode.

Закрытый список допустимых исходных holds первой поставки для CREATE:

- OperationHolder текущего claim с точным lease/fence/operation, closed admission и drained writers.
- SourceRootHolder другой exact revision с действующим holder, существующим не-pruned mapping и подтверждённым включением artifact в storage closure этой revision.

Другие holder kinds в этой поставке не дают основания reuse. При нескольких допустимых roots достаточно одного проверенного основания. После acquire новый root защищает каждый ref самостоятельно, прежние roots сохраняются.

Уточнённый proposed enum SourceRootAcquireCode содержит INVALID_SCOPE, OPERATION_MISMATCH, STALE_CLAIM, WRONG_KIND, WRONG_PHASE, ADMISSION_OPEN и INVALID_ATTEMPT. Последний покрывает завершённую domain phase, повторное использование capability и отсутствие связи scope с единственной attempt. Proposed SourceRootAcquireFault содержит code, operation_id, source и artifact: ArtifactRef | None. Fault frozen/strict, SourceRootAcquireError переносит его. Code/fault определены в backend/app/dataModel/artifacts/lifecycle/sourceRootAcquireFault.py, exception — в backend/app/application/artifacts/errors/sourceRootAcquireError.py.

Source status/linkage/closure errors возвращаются исходным SourceFailure. Missing допустимого hold отображается в Source-owned MISSING_HOLD с offending artifact и operation APPLY_MUTATION. Для этого требуется согласованный Source error factory либо точный конструктор в implementation map. Malformed DTO проверяется до IO. Live writer даёт OperationBusyError, corrupt persisted chain — PublicationInfrastructureError, transaction uncertainty — UnknownCommitOutcome внешней границы.

P2.7 решает no-op linkage при чужом created_by. P2.8 верно требует rollback предшествующих writes при отказе adapter. До приёмки acquire остаются доказательство свежести revision, принятие результата eligibility и конкретный Source error mapping. Crash-before-terminal сохраняет fail-closed unresolved семантику без повторного body для той же identity.

## Полный recovery protocol — предложение 2026-11-14

Этот раздел заменяет fail-closed как конечный результат первой поставки. Рекомендуется durable original request + fenced attempt takeover + повтор только незавершённого transaction body под исходными expected refs. Terminal replay всегда читает уже сохранённый outcome и не выполняет Source checks. Recovery attempt может получить новый отказ относительно изменившегося окружения; это новый результат восстановления незавершённой попытки, а не восстановленный in-memory failure.

### Durable записи и состояния

Общий operation ledger сохраняет kind/world/preparation/request fingerprints и единственный terminal. Дополнение общего ledger: immutable request record с canonical SourceRegistryMutationInput bytes, schema version и checksum, записанный до первого claim, и append-only attempt chain. Request record не содержит копии terminal и не образует второй receipt store.

Attempt record содержит operation_id, attempt_id, predecessor_attempt_id, fence, status. Предлагаемые statuses ACTIVE, SUPERSEDED, COMPLETED. Каждому operation соответствует максимум одна latest ACTIVE attempt; latest terminal запрещает новую attempt. PREPARING→READY сохраняет существующую подготовку; READY→APPLYING атомарно создаёт первый ACTIVE attempt; recovery APPLYING/RECOVERY_REQUIRED→APPLYING создаёт следующий fence/attempt и supersedes прежний. Terminal commit атомарно пишет outcome, COMPLETED и operation TERMINAL. Изменения phase/fence chains и SQL guards требуют owning acceptance.

Request digest проверяется при записи, claim и recovery decode. Expected refs, membership, body refs и operation identity берутся из сохранённого запроса. Request bytes/параметры, необходимые для повторения owning deterministic apply, должны быть полны; ambient/latest-derived inputs запрещены. Если projector/config version влияет на execution, она должна входить в принятый request binding или доступный exact immutable dependency. Это обязательный Source prerequisite, не автоматически закрытый текущим input.

### Ownership и fenced takeover

PublicationAttemptOwner — предлагаемый frozen internal DTO (lease: OperationLeaseRef, attempt_id: EntityUid, request_fingerprint: RevisionHex). Он описывает durable ownership, но не является SQL capability. Coordinator выдаёт runtime domain scope только после проверки latest ACTIVE attempt в BEGIN IMMEDIATE.

Scope registry связывает issued scope с operation/attempt/fence и phase DOMAIN либо CONTROL. Все domain reads/writes, Source links, root acquire и terminal calls используют проверенный scope. После domain exit его поколение отзывается. Повтор domain() одной runtime attempt запрещён. Повторное создание runtime attempt с тем же owner требует проверки durable latest и принятого single-start enforcement: в текущем процессе registry помнит issued attempt, после restart возобновление идёт только через recovery с новым fence.

Recovery получает BEGIN IMMEDIATE на том же физическом SQLite database и повторно читает terminal/attempt. Полученный writer lock исключает активную прежнюю write transaction. Пока прежний writer жив и держит transaction, recovery возвращает busy при bounded lock timeout. Когда lock получен, recovery увеличивает fence и supersedes прежний owner внутри той же transaction. Старый процесс может жить, но его последующий вход в transaction обязан отвергнуть stale attempt. Отсутствие lock само по себе не доказывает смерть процесса; безопасность достигается fencing всех доступов, а не предположением о смерти.

В этой publication phase нет внешних side effects и artifact writers: admission закрыт, тела sealed, writer claims drained. Любой обнаруженный live writer блокирует takeover. Crash orphan writer recovery принадлежит staging owner и должен завершиться до publication recovery. Worker без scope не может выполнять domain SQL; physical artifact writers не возобновляются этим протоколом.

Для исключения окна после takeover разрешено commit-ить короткую takeover transaction, затем открыть fenced domain attempt. Конкурирующий recover может supersede ещё не вошедший owner: он получит stale и не выполнит body. Для предотвращения лишнего конкурентного supersede entry проверяет expected_attempt_id из recovery request; CAS mismatch даёт RecoveryContractError(ATTEMPT_CHANGED); новый fence не создаётся. Для актуального state caller отдельно вызывает inspect. Это не таймер/автоматический retry loop.

### Holds и смена fence

Операция READY/APPLYING сохраняет все operation holds request bodies и closure dependencies до terminal. Takeover должен атомарно перенести собственные active operation holds со старого fence на новый, сохраняя их непрерывную видимость в одной commit transaction. Старые handles становятся stale. Новые acquisitions и releases валидируют latest fence. Это требует принятого internal lease transfer primitive с закрытым admission и drain; простая смена operation event fence недостаточна.

Source roots, capture/publication и чужие holders не переносятся и не освобождаются. Partial domain writes/roots/links предыдущей попытки отсутствуют после rollback/crash внешней transaction. Сохранившиеся committed Source links без соответствующего terminal при атомарном protocol означают corruption и дают infrastructure error.

После successful terminal root holds защищают published revisions, ненужные operation holds освобождаются согласно exact retained mapping. После refused terminal operation holds освобождаются атомарно с refusal. При failure recovery/unknown outcome они сохраняются до установления результата.

### Typed internal APIs

Предлагаемые ports application/publication/contracts/sourceMutationRecovery.py и implementation application/publication/service/sourceMutationRecovery.py. SQLite storage использует existing operationStore, commit coordinator, lease/holder adapters.

```python
class SourceMutationRecoveryInput:
    operation_id: EntityUid
    request_fingerprint: RevisionHex
    expected_attempt_id: EntityUid
    reason: RecoveryReason

async def inspect(request: SourceMutationInspectInput) -> SourceMutationRecoveryState: ...

async def claim_recovery(
    request: SourceMutationRecoveryInput,
) -> SourceMutationRecoveryClaim: ...

def transaction_for_attempt(
    grant: PublicationExecutionGrant,
) -> AbstractAsyncContextManager[PublicationAttempt]: ...
```

SourceMutationRecoveryState — discriminated immutable union Terminal(outcome), Active(attempt_id, fence), PreparationRequired(phase). Это status, не authorization и не второй outcome. claim_recovery возвращает terminal первым после сверки binding. Иначе под writer serialization проверяет expected attempt, closed admission/drain, immutable request и exact required artifacts, затем переводит fence/holds и выдаёт нового owner.

Source internal apply owner загружает сохранённый request через checked ledger reader и выполняет transaction_for_attempt. Domain savepoint и refuse/succeed semantics предыдущего раздела сохраняются. Внешний recovery entry выполняет не более одной recovery attempt за вызов; busy/unknown/stale явно выходят caller. Он не создаёт новую operation identity.

Предлагаемый RecoveryContractError переносит RecoveryContractFault из backend/app/dataModel/publication/recoveryFault.py с полями operation_id/code; там же определён RecoveryContractCode со значениями BINDING_MISMATCH, ATTEMPT_CHANGED, WRONG_PHASE, INVALID_REQUEST_BINDING, STALE_OWNER. Busy writer/lock — OperationBusyError. Corrupt immutable request/checksum/schema или holders — PublicationInfrastructureError. Неизвестный COMMIT/ROLLBACK — UnknownCommitOutcome. Source expected/membership отказ сохраняется как SourceMutationRefused с исходным для этой attempt failure. Нет конвертации infrastructure faults в SourceFailure.

### Crash matrix

| Момент остановки | Durable состояние | Recovery/caller |
|---|---|---|
| До commit claim | READY и исходные holds | Claim обычным протоколом, body ещё не выполнялся |
| После claim до domain BEGIN | ACTIVE attempt и immutable request | Explicit claim_recovery, новый fence, прежний owner stale |
| Во время domain writes | Outer transaction откатывается SQLite | Recovery после writer lock восстанавливает из original request |
| После ROLLBACK TO до refusal COMMIT | Outer transaction откатывается, durable terminal отсутствует | Recovery attempt с original expected, прежний in-memory failure не восстанавливается |
| После successful/refused COMMIT до acknowledgement | Terminal и соответствующие holds атомарно сохранены | Exact terminal replay, ноль domain calls |
| Во время takeover COMMIT | Старый либо новый attempt/fence/holds целиком | inspect на fresh connection; CAS по actual attempt; никаких предположений по timeout |
| Во время release/terminal storage failure | Outer transaction rollback либо unknown | Holds сохраняются при rollback; fresh recovery определяет terminal при unknown |

### Требования к fresh revision provenance

Source revision rows должны позволять проверить создание revision именно current attempt, а не только operation_id. Предлагается internal created_attempt_id, связанный с durable attempt record и записанный в domain scope. Source refs/proof identities от этого не меняются. Eligibility получает проверенную attempt identity из scope binding. CREATE mode разрешён только для revision current domain attempt; no-op на прежнюю revision возвращает REQUIRE_EXISTING. Recovery uncommitted revisions прежней attempt уже откатились; published revisions имеют terminal и идут по replay без нового acquire.

SourceMutationLinkStore сохраняет предложенный operation_id + exact ref состав. Для eligibility freshness используется revision provenance, link не дублирует attempt outcome. Присвоение seq и проверка original expected выполняются заново только в recovery незавершённой attempt, под новым fence, в общей transaction. Ни одна provisional revision не выдаётся наружу до commit.

### Решение, требующее пользователя

Рекомендуемый выбор: разрешить explicit recovery заново исполнить незавершённое transactional body с прежним immutable request/expected и новым fenced attempt, сохранив тот же operation_id. Результат может отличаться от утраченного provisional failure, но ранее durable terminal всегда replay-ится точно. Это явное изменение предыдущего запрета повторного body для той же identity.

Если требуется восстановление именно прежнего отказа даже до terminal commit, предложенный savepoint protocol эту гарантию не даёт. Потребуется отдельно спроектировать durable decision до domain rollback с доказанным сохранением исходного read-set и сериализацией решения; текущий SQLite single-writer не позволяет просто commit-ить второй connection decision при удержанном writer lock. Выдавать такое свойство за реализуемое добавлением одной строки в той же transaction нельзя.

Контракт остаётся DESIGN OPEN до выбора semantics recovery, приёмки attempt/fence/hold-transfer API и Source completeness/versioning immutable request. Общие recovery runtime тесты и fault injection обязательны перед приёмкой реализации.

## Scoped attempt identity для Source P2.11

Предлагается internal port backend/app/application/publication/contracts/domainAttemptBinding.py::IDomainAttemptBinding и SQLite реализация backend/app/db/repositories/sqlite/snapshotCore/operations/domainAttemptBinding.py::SqliteDomainAttemptBinding:

```python
async def require_domain_attempt(
    self, scope: CommitScope, *, operation_id: EntityUid,
) -> EntityUid: ...
```

Выбран async, поскольку кроме runtime registry требуется прочитать durable latest attempt/start и operation binding в том же scope. Возвращаемый attempt_id — identity для provenance, не новая capability. Source revision writer и SourceRootEligibilityBinding получают один экземпляр port, связанный с их общим coordinator/registry/access.

Порядок guards: registry.check(scope, write=True) → scope.operation_id совпадает с аргументом → scope принадлежит текущему DOMAIN generation active PublicationAttempt → persisted operation APPLYING и SOURCE_MUTATION → persisted latest ACTIVE attempt_id/fence/request fingerprint совпадают с registry binding и текущим record → closed admission/drained assertion, установленный coordinator на входе attempt. Если writer claims могут появиться вопреки закрытому admission, это corruption, не новое разрешение. Query через ScopedSqliteAccess повторно проверяет scope до доступа.

Registry хранит attempt identity/fence/request binding из проверенного BEGIN IMMEDIATE. Durable повторная проверка выполняется под тем же writer lock: recovery не может supersede attempt между проверкой и последующей записью. DOMAIN capability отзывается при выходе savepoint; CONTROL scope отвергается. Read-only, foreign DB, child task, revoked scope и stale domain generation отвергаются до записи. Старый owner, который ещё не открыл transaction после takeover, получает STALE_OWNER на входе coordinator и не получает domain scope.

Ошибки — typed DomainAttemptBindingError в application/publication/errors.py переносит DomainAttemptBindingFault(operation_id, code); fault и DomainAttemptBindingCode определяются в backend/app/dataModel/publication/domainAttemptFault.py. Предлагаемые коды INVALID_SCOPE, OPERATION_MISMATCH, WRONG_PHASE, STALE_ATTEMPT. Повреждённый durable start/chain/request binding даёт PublicationInfrastructureError. Binding не открывает UOW, не меняет fence, не выдаёт новую attempt и не читает latest Source revision.

P2.11 совместим с рекомендуемым recovery. Новый attempt_id получает только свежие записи собственной transaction. Старые uncommitted rows откатились; ранее committed creation допустима для REQUIRE_EXISTING только с successful terminal и текущим touched link. Committed revision rows без successful creation terminal — infrastructure inconsistency. Refusal terminal не подтверждает создание revision. Terminal replay acquisition не запускает. Bootstrap требует отдельного контракта provenance.

## Обязательный logging contract recovery — актуальный roster 2026-11-14

Этот раздел целиком заменяет прежние logging roster и дополнения. По повторному Source review в source-recovery-logging-review-2026-11-14.md замечания RLOG-1–4 закрыты статически. Пользователь принял explicit recovery semantics и обязательность production logging. Нормативный узкий amendment уже внесён в docs/tz_logging.md. Полная приёмка recovery/runtime остаётся отдельной; runtime evidence пока отсутствует.

### Владелец, модули и транспорт

OperationRecoveryLog — backend/app/application/publication/logging/operationRecoveryLog.py. Event и служебные enum — backend/app/dataModel/artifacts/recoveryEvents.py. Source projection принадлежит Source, предлагаемый backend/app/application/worldData/sourceVersioning/logging/diagnosticProjection.py. Projection не эмитирует lifecycle event. Общий emitter использует get_consumer_logger(LogConsumer.ARTIFACTS), existing router, JsonLogFormatter и destination logs/artifacts/artifactLifecycle.log. Новый handler/file/logger не требуется.

Все event records frozen=True, strict=True, extra="forbid", revalidate_instances="always". Все поля ниже обязательны при создании, включая nullable. Defaults запрещены. PositiveInt здесь означает Annotated[StrictInt, Field(ge=1)], NonNegativeInt — Annotated[StrictInt, Field(ge=0)]; bool и numeric strings отвергаются.

### Source diagnostics — RLOG-2

Field projection SourceFieldLogEntry(code: SourceFieldCode, path: ValidatedFieldPath) предлагается в backend/app/dataModel/sourceVersioning/sourceLogProjection.py. Это read-only logging projection без message. Owning проектор принимает SourceFieldIssue и сохраняет code и checked path. Строковый path не допускается.

Logic projection переиспользует сам SourceLogicIssue из принятого sourceErrors: code, group_index, use_index, source, artifact. Его состав уже не содержит message/body. Копировать его во второй logic DTO не требуется. Exact Source refs и ArtifactRef являются разрешёнными identities, их тела и значения owning rows не логируются.

SourceDiagnosticLogKind имеет FIELD="field" и LOGIC="logic". Точные wrapper классы в backend/app/dataModel/sourceVersioning/sourceLogProjection.py: SourceFieldDiagnosticLogEntry(kind: Literal[SourceDiagnosticLogKind.FIELD], issue: SourceFieldLogEntry) и SourceLogicDiagnosticLogEntry(kind: Literal[SourceDiagnosticLogKind.LOGIC], issue: SourceLogicIssue). SourceDiagnosticLogEntry — Annotated union этих двух классов с Field(discriminator="kind"). Оба поля обязательны, defaults отсутствуют. FieldEntry/LogicEntry являются только сокращениями описания, дополнительные классы с такими именами не вводятся. Event содержит один diagnostics tuple и source_operation.

Pure SourceDiagnosticLogProjector.project(failure: SourceFailure) -> tuple[SourceDiagnosticLogEntry, ...] находится в backend/app/application/worldData/sourceVersioning/logging/diagnosticProjection.py. Он переносит safe fields и формирует стабильный порядок ниже, без IO и lifecycle emit.

Проектор выдаёт сначала все field_issues в исходном порядке, затем все logic_issues в исходном порядке. Этот порядок воспроизводим; общего interleaved порядка SourceFailure не определяет. Два MISSING_HOLD с различными source/artifact/group/use сохраняются как две различные записи. Optional индексы не подменяются нулём. Все mandatory-nullable поля SourceLogicIssue сохраняются, даже если None. Проверки code/context делегируются owning Source contract, emitter дополнительно требует code допустимого семейства и соответствующий variant. Для field variant checked path обязателен; для logic variant поле path отсутствует.

### Infrastructure projection — RLOG-1

Единственные owning определения code/fault находятся в dataModel. Эта карта заменяет ранние предложения размещать fault/enum рядом с application exceptions:

| Owning модуль | Определения | Все поля fault |
|---|---|---|
| backend/app/dataModel/publication/recoveryFault.py | RecoveryContractCode, RecoveryContractFault | code: RecoveryContractCode, operation_id: EntityUid |
| backend/app/dataModel/publication/domainAttemptFault.py | DomainAttemptBindingCode, DomainAttemptBindingFault | code: DomainAttemptBindingCode, operation_id: EntityUid |
| backend/app/dataModel/artifacts/lifecycle/sourceRootAcquireFault.py | SourceRootAcquireCode, SourceRootAcquireFault | code: SourceRootAcquireCode, operation_id: EntityUid, source: SourceVersionRef \| SourceCollectionVersionRef, artifact: ArtifactRef \| None |

Code enum — StrEnum. Wire values соответствуют lower_snake_case имён из согласуемого roster: RecoveryContractCode — binding_mismatch, attempt_changed, wrong_phase, invalid_request_binding, stale_owner; DomainAttemptBindingCode — invalid_scope, operation_mismatch, wrong_phase, stale_attempt; SourceRootAcquireCode — invalid_scope, operation_mismatch, stale_claim, wrong_kind, wrong_phase, admission_open, invalid_attempt. Fault records frozen/strict/extra-forbid/revalidate-always, все поля обязательны, nullable artifact без default. Поля message и exception отсутствуют.

Application RecoveryContractError и DomainAttemptBindingError в backend/app/application/publication/errors.py содержат соответственно fault: RecoveryContractFault и fault: DomainAttemptBindingFault. SourceRootAcquireError в backend/app/application/artifacts/errors/sourceRootAcquireError.py содержит fault: SourceRootAcquireFault. Exception constructors проверяют соответствующий exact typed fault; application enum/fault definitions отсутствуют. DataModel зависит только от dataModel identity/ref типов.

В recoveryEvents.py объявляются следующие точные wrappers. Все поля обязательны, family без default:

```python
class RecoveryContractLogFault:
    family: Literal["recovery_contract"]
    fault: RecoveryContractFault

class DomainAttemptLogFault:
    family: Literal["domain_attempt"]
    fault: DomainAttemptBindingFault

class SourceRootAcquireLogFault:
    family: Literal["source_root_acquire"]
    fault: SourceRootAcquireFault

type RecoveryInfrastructureLogFault = Annotated[
    RecoveryContractLogFault | DomainAttemptLogFault | SourceRootAcquireLogFault,
    Field(discriminator="family"),
]
```

Wrappers — frozen strict BaseModel с extra-forbid/revalidate-always. Каждый хранит исходный safe fault POJO целиком, без повторения его полей. Event invariant: event.fault.fault.operation_id == event.operation_id. Application emitter выбирает wrapper по exact exception family и переносит exception.fault. RecoveryEvents импортирует три dataModel fault modules; exception types знает только application emitter. SourceRoot INVALID_ATTEMPT, DomainAttempt STALE_ATTEMPT и Recovery STALE_OWNER различаются family и вложенным исходным code. Проверка sink использует JSON fault.family и fault.fault.code.

Для generic PublicationInfrastructureError и непредвиденного exception fault=None. exception_type: StrictStr содержит module.qualname исходного exception; cause передаётся emitter отдельным аргументом в existing exc_info, не сериализуется в POJO. Typed fault code всегда остаётся отдельным JSON полем даже при наличии stack. UnknownCommitOutcome имеет приоритет над общим infrastructure handler и создаёт только OUTCOME_UNKNOWN. Непредвиденный exception не получает выдуманный domain code.

Source payload/body/raw SQL не передаются в extra, message events строится только из activity/operation_id. Существующий exc_info может включать exception text: producer не должен включать Source bodies в infrastructure exception message; возможность санкционированной redaction в formatter требует отдельного logging-owner решения при наличии такого producer.

### Закрытые enum wire values

RecoveryReason — EXPLICIT_RESUME="explicit_resume", UNKNOWN_COMMIT_ACK="unknown_commit_ack", INTERRUPTED_ATTEMPT="interrupted_attempt". Причина передаётся typed recovery caller и не выводится из missing log line.

RecoveryObservation — OBSERVED="observed", PROVISIONAL="provisional", SAVEPOINT_ROLLED_BACK="savepoint_rolled_back", OUTER_ROLLED_BACK="outer_rolled_back", COMMITTED="committed", UNKNOWN="unknown".

RecoveryTerminalKind — APPLIED="applied", REFUSED="refused", CANCELLED="cancelled". CANCELLED обозначает existing OperationCancelled terminal. Activity RECOVERY_CANCELLED обозначает отмену invocation.

RecoveryLogActivity:
- REQUESTED="recovery_requested"
- INSPECTED="recovery_inspected"
- TAKEOVER_COMMITTED="recovery_takeover_committed"
- DOMAIN_ROLLED_BACK="recovery_domain_rolled_back"
- PROVISIONAL_REFUSAL="recovery_provisional_refusal"
- TERMINAL_COMMITTED="recovery_terminal_committed"
- TERMINAL_REPLAYED="recovery_terminal_replayed"
- BUSY="recovery_busy"
- MISMATCH="recovery_mismatch"
- OUTCOME_UNKNOWN="recovery_outcome_unknown"
- FAILED="recovery_failed"
- CANCELLED="recovery_cancelled"

Observed phase использует существующий OperationPhase с его owning wire values. Status operation ledger не дублируется отдельным logging enum.

### Единый OperationRecoveryEvent roster — RLOG-3

| Поле | Тип, nullable |
|---|---|
| activity | RecoveryLogActivity |
| reason | RecoveryReason |
| recovery_id | EntityUid |
| operation_id | EntityUid |
| world_uid | EntityUid \| None |
| preparation_fingerprint | RevisionHex \| None |
| request_fingerprint | RevisionHex, всегда известный validated input |
| observed_request_fingerprint | RevisionHex \| None, прочитанный durable binding |
| observed_phase | OperationPhase \| None |
| old_attempt_id | EntityUid \| None |
| old_fence | StrictInt ge=1 \| None |
| new_attempt_id | EntityUid \| None |
| new_fence | StrictInt ge=1 \| None |
| durability | RecoveryObservation |
| terminal_kind | RecoveryTerminalKind \| None |
| cancellation_reason | OperationCancellationReason \| None, existing enum из artifacts/lifecycle/operation/record.py |
| source_operation | SourceOperation \| None |
| diagnostics | tuple[SourceDiagnosticLogEntry, ...] |
| hold_count | StrictInt ge=0 \| None |
| fault | RecoveryInfrastructureLogFault \| None |
| exception_type | StrictStr \| None |

request_id добавляет JsonLogFormatter из request_id_var. Его источник — реальный HTTP/DAG/execution request context на внешней границе. Он не дублируется полем event и не входит в fingerprint. При production вызове отсутствие request context — composition defect, проверяемый до IO. Новый recovery invocation имеет новый recovery_id и текущий request_id. Restart связывается по operation_id, durable attempt/fence и request fingerprint.

old_attempt_id/old_fence и new_attempt_id/new_fence допускаются только полными парами. New pair используется только для подтверждённого takeover. В остальных events old pair обозначает текущую наблюдённую attempt; первая INSPECTED после takeover будет содержать именно новый current pair. При unknown takeover new pair остаётся None до durable read, proposed значение не маскируется под confirmed. observed_phase/fingerprint — последнее подтверждённое чтение, а не предположение о результате in-flight commit.

### Activity invariants, levels и methods

В таблице «общий context» означает operation/recovery/reason/request fingerprint. Столбцы задают дополнительные mandatory поля. Всё не разрешённое в таблице из terminal/source diagnostics/new pair/hold_count/fault/exception_type должно быть None либо пустым tuple. Observed context world/preparation/phase/fingerprint/current pair сохраняется, когда он прочитан; REQUESTED исключение ниже.

| Activity / emitter method | Level | Дополнительные инварианты |
|---|---|---|
| REQUESTED / emit_requested | INFO | OBSERVED; world/preparation/observed phase/fingerprint и обе attempt pairs None; diagnostics пуст; до read |
| INSPECTED / emit_inspected | INFO | OBSERVED; observed_phase/world/preparation известны после найденного record; отсутствие record обозначается observed_phase=None и всеми durable полями None; terminal_kind пока None |
| TAKEOVER_COMMITTED / emit_takeover_committed | INFO | COMMITTED; обе пары обязательны, new fence > old fence, IDs различны; hold_count обязателен; observed_phase=APPLYING и observed fingerprint=request fingerprint |
| DOMAIN_ROLLED_BACK / emit_domain_rolled_back | INFO | SAVEPOINT_ROLLED_BACK либо OUTER_ROLLED_BACK; current pair обязательна; terminal_kind=None |
| PROVISIONAL_REFUSAL / emit_provisional_refusal | WARNING | PROVISIONAL; source_operation=APPLY_MUTATION, diagnostics непуст, current pair обязательна; terminal_kind=None |
| TERMINAL_COMMITTED / emit_terminal_committed | INFO APPLIED, WARNING REFUSED | COMMITTED, observed_phase=TERMINAL, terminal_kind/current pair/world/preparation/observed fingerprint обязательны; REFUSED требует source_operation и diagnostics; APPLIED требует пустых diagnostics и source_operation=None |
| TERMINAL_REPLAYED / emit_terminal_replayed | INFO | OBSERVED, observed_phase=TERMINAL; APPLIED/REFUSED имеют context как COMMITTED; для CANCELLED действуют правила отдельного подраздела replay cancellation ниже; новый COMMIT не утверждается |
| BUSY / emit_busy | WARNING | OBSERVED, известный durable context сохраняется; fault=None; exception_type допускается для исходного busy exception |
| MISMATCH / emit_mismatch | WARNING | OBSERVED; fault одного из трёх owning families обязателен, exception_type обязателен; terminal_kind=None; declared/observed fingerprints различимы |
| OUTCOME_UNKNOWN / emit_unknown | ERROR | UNKNOWN; terminal_kind=None, diagnostics пуст; exception_type обязателен, fault=None; только последнее подтверждённое durable observation |
| FAILED / emit_failed | ERROR | OBSERVED либо OUTER_ROLLED_BACK только при подтверждении; exception_type обязателен, fault обязателен для трёх typed families и None для generic/unexpected exception |
| CANCELLED / emit_cancelled | WARNING | OBSERVED, OUTER_ROLLED_BACK либо COMMITTED только по acknowledgement; terminal_kind=None, diagnostics пуст; exception_type указывает CancelledError; cancelled invocation не объявляет cancelled operation terminal |

Если commit confirmed до cancellation, producer отдельно эмитирует TERMINAL_COMMITTED с сохранённым result, затем CANCELLED описывает отмену invocation. При неопределённом acknowledgement эмитируется OUTCOME_UNKNOWN; CANCELLED не заменяет его. Если outer rollback подтвердился после ранее provisional refusal, failure context остаётся в предыдущей записи; он не переносится в durable terminal поля.

Для TERMINAL_COMMITTED/REPLAYED REFUSED source_operation проверяется по существующему SourceMutationRefused.failure.operation, diagnostics получается единственным Source projector. Остальные activities не допускают source_operation/diagnostics, кроме PROVISIONAL_REFUSAL. Admission полного record проверяет enum, strict numerics, пары, union family и правила таблицы.

### Replay cancellation — дополнение terminal union

Existing OperationCancelled содержит только operation_id и reason: OperationCancellationReason (сейчас REQUESTED="requested"). SourceMutationTerminal/SourceMutationRecoveryTerminal сохраняют этот outcome без добавления fingerprint/attempt полей в него.

Для его replay эмитируется TERMINAL_REPLAYED уровня INFO, durability=OBSERVED, observed_phase=TERMINAL, terminal_kind=CANCELLED, cancellation_reason=outcome.reason. source_operation=None, diagnostics=(), fault=None, exception_type=None, hold_count=None, new_attempt_id/new_fence=None. World и preparation_fingerprint берутся из проверенного OperationRecord. Old attempt pair берётся из существующей durable attempt chain либо оба поля None, если cancel произошёл в PREPARING/READY до claim. OperationRecord.fence сам по себе не превращается в attempt fence при отсутствии attempt.

request_fingerprint остаётся заявленным validated input recovery. observed_request_fingerprint отражает реальное publication binding record и может быть None при раннем cancel. При наличии binding его совпадение проверяется до replay. При отсутствии binding Source-owned immutable request registration проверяет digest, если эта регистрация существует; отсутствующий request registration у отменённой до регистрации operation не заменяется preparation_fingerprint. В этом случае inspect/claim_recovery по request-specific API возвращает INVALID_REQUEST_BINDING, а generic operation-id lifecycle read может вернуть OperationCancelled через существующий ledger API. Source recovery не утверждает принадлежность terminal непроверенному request.

Таким образом ранний cancel допускает replay Source recovery без attempt/publication fingerprint при наличии проверяемого original request record. Отмена до существования этого request record требует generic lifecycle read. Это уточняет ранее общее правило «terminal первым»: сначала проверяется доступное immutable binding, затем terminal, до execution lookup/projector.

Для остальных activities cancellation_reason обязательно None. В TERMINAL_REPLAYED APPLIED/REFUSED оно также None. Source recovery не создаёт новый cancellation terminal: TERMINAL_COMMITTED этого emitter допускает только APPLIED/REFUSED. Новый cancel принадлежит existing cancel lifecycle producer. RECOVERY_CANCELLED/emit_cancelled всегда имеет terminal_kind=None и cancellation_reason=None и описывает отмену вызова, сохраняя actual acknowledgement observation. У cancellation terminal replay отсутствует CancelledError cause.

Проверки: cancel в PREPARING и READY с immutable request registration даёт exact OperationCancelled и INFO replay с None attempt/publication fingerprint; cancel после claim использует реальную persisted pair; request mismatch отклоняется до replay; отменённая operation без request registration даёт INVALID_REQUEST_BINDING по Source request-specific API; generic ledger read возвращает её cancellation outcome. Negative schema cases: CANCELLED terminal без owning reason, reason у APPLIED/REFUSED либо RECOVERY_CANCELLED, synthetic pair для раннего cancel, source diagnostics в cancellation replay. Real sink различает activity recovery_terminal_replayed/terminal_kind cancelled от activity recovery_cancelled/terminal_kind null. Новое сообщение logging не создаёт terminal и не изменяет holds.

### Producer ownership и sink semantics

Recovery entry владеет requested/inspected/busy/mismatch/unknown/failed/replayed. Takeover coordinator эмитирует takeover_committed после подтверждённого commit переноса fence/holds. Source apply owner предоставляет provisional failure через emitter projection. PublicationAttempt coordinator владеет confirmed rollback и terminal commit. Cancellation observation принадлежит внешней recovery boundary. Domain diagnostics не эмитируются повторно собственным Source lifecycle logger.

Emitter methods фиксируют activity/level и принимают typed context плюс existing outcome/failure/fault только для проекции; arbitrary LogLevel caller не передаёт. Cause передаётся отдельным аргументом, source body не включается. Typed validation выполняется до best-effort sink. Ошибка sink, включая postcommit UnknownLogConsumerError, не меняет уже установленный durable/caller outcome и не запускает retry/cleanup. Route composition проверяется preflight. Невалидный event является programming defect; после commit он также не должен подменять результат операции.

Ledger остаётся источником recovery. Exactly-once logging не гарантируется. Crash может оставить цепочку без последней записи. Следующий inspect фиксирует actual durable state и собственный итог invocation, без вывода rollback из отсутствующего log.

### Нормативный amendment docs/tz_logging.md

Узкое уточнение уровней и корреляции внесено в docs/tz_logging.md по поручению пользователя 2026-11-14. Ниже сохранён текст предложения, послужившего основанием; действующее нормативное определение — раздел Publication recovery в ТЗ:

> Общий publication recovery producer OperationRecoveryLog использует существующий LogConsumer.ARTIFACTS и маршрут artifacts/artifactLifecycle. Для recovery REQUESTED, INSPECTED, TAKEOVER_COMMITTED, DOMAIN_ROLLED_BACK и TERMINAL_REPLAYED имеют INFO. TERMINAL_COMMITTED имеет INFO для APPLIED и WARNING для REFUSED. PROVISIONAL_REFUSAL, BUSY, MISMATCH и CANCELLED имеют WARNING. OUTCOME_UNKNOWN и FAILED имеют ERROR. Эти уровни относятся к recovery activities; existing Snapshot STARTED/BUSY сохраняют своё определение. Recovery events обязаны содержать typed reason, operation_id, validated request fingerprint и доступное durable observation, корреляцию request_id/recovery_id/attempt/fence и исходный typed failure context. COMMITTED допускается только после acknowledgement. REPLAYED фиксирует чтение terminal. Ошибка logging после durable commit не изменяет исход caller.

Route/server transcript allowlist должны пропускать весь roster при production INFO. Нормативное уточнение зафиксировано в ТЗ; проверка реального route/emitter/sink остаётся критерием реализации.

### Критерии повторной приёмки

- SourceRoot INVALID_ATTEMPT, DomainAttempt STALE_ATTEMPT и Recovery STALE_OWNER сохраняют разные family/code в реальном JSON sink и исходный exc_info.
- Два MISSING_HOLD с разными exact refs/artifacts/индексами остаются различимыми. Field entries всегда имеют checked path. Проверяется field-then-logic порядок, отсутствие messages/raw bodies.
- Table-driven negative schema checks покрывают bool/string numeric, неполные пары, неподходящие enum/family, field без path, REQUESTED с takeover fields, UNKNOWN с terminal kind, REPLAYED с durability COMMITTED, CANCELLED с неподтверждённым rollback.
- Реальный emitter→facade→router→JsonLogFormatter→server sink при production INFO, проверка request_id/recovery_id/world/fingerprints и source projection.
- Crash/lost-ack после takeover и terminal, replay после restart, busy/mismatch, rollback savepoint, cancellation и sink exceptions; сверка ledger/holds вторым SQLite-соединением.
- Postcommit sink fault сохраняет наружный terminal; unknown остаётся unknown до durable inspect. Новая successful recovery attempt и terminal replay дают различные activities.

Повторное статическое Source review закрыло RLOG-1–4. Exact names Source projection синхронизированы с владельцем. Logging amendment нормативно внесён в ТЗ. Полная приёмка recovery protocol и runtime implementation, включая emitter→sink evidence, остаётся открытой.

## REC-2–4 — точные infrastructure boundaries

Этот раздел заменяет противоречащие ранние signatures. DESIGN OPEN до повторной приёмки. Recovery semantics и RLOG-1–4 сохраняются.

### REC-2. Scoped transfer

Новый internal port IOperationHoldTransfer в backend/app/application/artifacts/contracts/operationHoldTransfer.py, implementation SqliteOperationHoldTransfer в backend/app/db/repositories/sqlite/artifacts/operationHoldTransfer.py. Existing IArtifactLeases остаётся владельцем обычных staging operations; наличие transfer метода в нём не предполагается.

```python
async def transfer(
    self, scope: CommitScope,
    previous: PublicationAttemptOwner,
    successor: PublicationAttemptOwner,
) -> tuple[ArtifactRef, ...]: ...
```

Output — canonical полный набор перенесённых refs. Caller не передаёт subset. Adapter получает set из scoped operation-artifact reader и проверенных holder chains, включая refs, не являющиеся direct body запроса. Required immutable request storage closure должен быть под защитой до takeover; его проверяет recovery owner перед transfer через Source-owned execution binding.

Prewrite: scope CONTROL recovery generation, совпадающий operation_id/database/task; оба owner относятся к одному world/kind/preparation/request binding; successor.fence=previous.fence+1, разные attempt_id; durable latest ещё previous ACTIVE и terminal отсутствует; admission closed, writer claims всех fences drained. Проверяются все catalog identities/seals и все relevant holder chains. Active operation hold с чужим fence, missing required protection либо corrupt chain отвергаются. Отсутствующий hold нельзя заменить acquire. Пустой set допустим только если required closure также не требует operation holds и это доказано owning validation.

Adapter append-ит release прежних operation holds и acquire successor holds через специальный internal transfer transition guard. Нормальный acquire со stale/new lease использовать для этого перехода нельзя. Guard проверяет выданную coordinator transfer phase, exact predecessor acquire events и полную immutable transfer selection, вычисленную выше. Существующие SQL guards требуют согласованного расширения для этого атомарного перехода.

Nested trace recovery: BEGIN IMMEDIATE → read/validate latest previous → validate durable request/required closure → transfer prewrite checks → append transfer events → append successor operation fence/closed admission и supersede predecessor/create ACTIVE successor → verify resulting exact set → COMMIT. Весь trace выполняет SourceMutationRecovery через scoped stores одного coordinator. Transfer возвращает refs до commit только как provisional result. При любой ошибке outer rollback обязателен; operation fence никогда не коммитится отдельно от holds. GC другого соединения видит old либо new set целиком.

Transfer повторяется только через fresh inspect/recovery CAS, а не вызовом transfer на уже successor latest. При unknown commit caller читает durable attempt/fence/set; нельзя автоматически повторить release. Existing unrelated root/capture/publication holders сохраняются.

Ошибки: OperationBusyError при writer claims; RecoveryContractError с существующими BINDING_MISMATCH/ATTEMPT_CHANGED/WRONG_PHASE/STALE_OWNER при неверном запросе перехода; DomainAttemptBindingError INVALID_SCOPE при чужом control scope; PublicationInfrastructureError при corrupt/missing persisted protection; UnknownCommitOutcome только outer coordinator. Собственный зеркальный transfer error enum не создаётся.

### REC-3. Единственный input/result roster

DTO module backend/app/dataModel/publication/sourceMutationRecovery.py. Все records frozen/strict/extra-forbid/revalidate-always. Все поля обязательны, defaults отсутствуют. Strict positive numeric исключает bool/строки.

- SourceMutationInspectInput(operation_id: EntityUid, request_fingerprint: RevisionHex, reason: RecoveryReason).
- SourceMutationRecoveryInput(operation_id: EntityUid, request_fingerprint: RevisionHex, expected_attempt_id: EntityUid, reason: RecoveryReason).
- PublicationAttemptOwner(lease: OperationLeaseRef, attempt_id: EntityUid, request_fingerprint: RevisionHex) — описание durable ownership.

RecoveryStateKind StrEnum: ABSENT="absent", PREPARATION_REQUIRED="preparation_required", ACTIVE="active", TERMINAL="terminal".

SourceMutationAbsent(kind: Literal[ABSENT], operation_id: EntityUid).
SourceMutationPreparationRequired(kind: Literal[PREPARATION_REQUIRED], record: OperationRecord), validator разрешает только PREPARING/READY.
SourceMutationActive(kind: Literal[ACTIVE], owner: PublicationAttemptOwner, phase: OperationPhase), validator разрешает APPLYING/RECOVERY_REQUIRED.
SourceMutationTerminal(kind: Literal[TERMINAL], outcome: SourceMutationApplied | SourceMutationRefused | OperationCancelled). Union outcome различим по обязательным уникальным полям; model validators исключают mixed fields. Existing OperationCancelled необходим для корректного inspect отменённой SOURCE_MUTATION operation. SourceMutationRecoveryState — Annotated union четырёх variants с discriminator="kind".

RecoveryClaimKind StrEnum: OWNER="owner", TERMINAL="terminal". SourceMutationRecoveryOwner(kind: Literal[OWNER], owner: PublicationAttemptOwner), SourceMutationRecoveryTerminal(kind: Literal[TERMINAL], outcome: тот же existing outcome union). Claim result — discriminated union этих двух wrappers, без повторных outcome records.

```python
async def inspect(request: SourceMutationInspectInput) -> SourceMutationRecoveryState: ...
async def claim_recovery(request: SourceMutationRecoveryInput) -> SourceMutationRecoveryClaim: ...
```

inspect возвращает ABSENT, если operation отсутствует. Для найденной operation проверяет SOURCE_MUTATION и request binding, возвращает соответствующий state. PREPARING/READY допускает ещё не установленный publication_fingerprint; immutable request store должен уже позволять проверить запрошенный digest, иначе INVALID_REQUEST_BINDING. Так фиксируется отличие unknown operation от повреждённой регистрации.

claim_recovery: full binding checks → existing terminal возвращается как TERMINAL → absent/preparation phase дают WRONG_PHASE → несовпадение expected_attempt_id даёт RecoveryContractError(ATTEMPT_CHANGED) → scoped takeover → OWNER только после confirmed commit. Возврат актуального state при mismatch отменён. Caller при необходимости отдельно вызывает inspect. MISMATCH logging сохраняет existing fault code. Busy/unknown не возвращаются как успешный union variant.

RecoveryReason определяется единожды в backend/app/dataModel/publication/recoveryReason.py; recoveryEvents.py и recovery input импортируют его. Это устраняет зависимость request от event schema. Wire values explicit_resume/unknown_commit_ack/interrupted_attempt сохраняются.

### REC-4. Durable single-start

Одна runtime registry память не является достаточным барьером. Добавляется durable start-claim event для каждой attempt, unique(operation_id, attempt_id), append-only в общем ledger. Attempt создаётся со start UNCLAIMED. Единственный успешный CAS UNCLAIMED→CLAIMED выполняет SqliteSourceMutationAttemptStore.claim_start в коротком BEGIN IMMEDIATE, проверяя latest ACTIVE attempt, phase/fence/binding/terminal. Успех commit даёт право единственному issuer создать opaque runtime execution grant.

Internal port ISourceMutationAttemptStore — application/publication/contracts/sourceMutationAttemptStore.py; SQLite implementation — db/repositories/sqlite/snapshotCore/operations/sourceMutationAttemptStore.py. PublicationAttemptIssuer — application/publication/service/publicationAttemptIssuer.py. Его зависимости: attempt store, commit coordinator и scope registry одной database binding. Только этот класс создаёт grant после успешного claim_start CAS. Конструктор grant недоступен domain/caller; registry admission проверяет exact registered object identity, issuer/database и task.

```python
async def acquire_execution(
    owner: PublicationAttemptOwner,
) -> PublicationExecutionGrant: ...

def transaction_for_attempt(
    grant: PublicationExecutionGrant,
) -> AbstractAsyncContextManager[PublicationAttempt]: ...
```

PublicationExecutionGrant — runtime capability в application/publication/contracts/attemptStore.py, непереносимая/несериализуемая. Durable owner DTO больше не принимается transaction_for_attempt. Grant одноразово потребляется при входе до выдачи domain scope. В том же BEGIN IMMEDIATE проверяются latest ACTIVE attempt/fence и persisted start-claim. domain() дополнительно однократен внутри PublicationAttempt.

Второй coordinator/registry с тем же serializable owner получает отказ start CAS: durable CLAIMED уже существует. Повтор того же grant отвергается registry. После rollback, потери grant, issuer crash или failed transaction entry старый start остаётся CLAIMED; новый execution требует explicit fenced recovery с новым attempt_id. Recovery supersedes старую attempt, переносит holds и создаёт successor UNCLAIMED. Старый живой grant отклоняется по durable latest/fence при входе; работающая domain transaction блокирует takeover writer lock.

Для повторного acquire_execution той же claimed attempt использовать существующий RecoveryContractError(ATTEMPT_CHANGED): statement означает невозможность стартовать предъявленное состояние attempt, caller обязан inspect/recover. Fault не заявляет иной actual attempt_id без чтения. При необходимости более узкого owning code это отдельное изменение roster; в текущем предложении новый enum не вводится.

claim_start result internal bool CAS; false всегда отказ без grant. Lost commit ack даёт UnknownCommitOutcome и никакого grant. Даже если CLAIMED сохранился, только explicit recovery выдаёт следующую попытку. Это закрывает повторное mint после restart и после rollback между domain savepoint и terminal.

### Concrete infrastructure owners для Source REC-5

SourceMutationRecovery (application/publication/service/sourceMutationRecovery.py) владеет inspect/takeover ordering/logging; SqliteOperationHoldTransfer переносит полный hold set; SqliteSourceMutationAttemptStore владеет durable start CAS; PublicationAttemptIssuer выдаёт runtime grant; SqlitePublicationCommitStore владеет outer UOW/savepoint и phase capabilities; SqliteDomainAttemptBinding выдаёт checked attempt identity; SqliteOperationStore сохраняет единственный terminal. Source apply implementation получает grant-bound domain scope и вызывает свои revision/link/eligibility bindings. Все эти зависимости internal. Source concrete public map и immutable execution binding остаются REC-1/REC-5 владельца Source.

Обязательные проверки REC-2–4: два independent coordinators пытаются стартовать один owner; rollback и повтор owner на другом registry; crash после start commit до выдачи grant; stale grant после recovery; hold-transfer fault после любого append; missing ref/чужой fence; takeover CAS mismatch; terminal cancel replay; unknown transfer commit. Второе SQLite-соединение проверяет durable start, exact holds и fence. Проект предъявлен на повторное статическое review, runtime evidence отсутствует.

## Source execution_version — infrastructure mapping REC-1

P2.13 совместим с recovery protocol. execution_version входит в canonical original request и его fingerprint. Existing terminal replay предшествует lookup execution binding. Незавершённая попытка требует exact descriptor/version исполнителя.

Предлагается добавить EXECUTION_UNAVAILABLE="execution_unavailable" в существующий proposed RecoveryContractCode. Единственное место определения — backend/app/dataModel/publication/recoveryFault.py. RecoveryContractFault дополняется обязательными nullable полями descriptor: SourceDescriptorKey | None и execution_version: Annotated[StrictInt, Field(ge=1)] | None. Для EXECUTION_UNAVAILABLE оба поля обязательны и non-null; для остальных codes оба None. SourceDescriptorKey переиспользуется из owning Source dataModel registration, новый descriptor mirror не вводится. RecoveryContractError в application/publication/errors.py переносит этот fault.

Это явное дополнение согласуемой schema fault. Existing RecoveryContractLogFault сохраняет весь typed fault, поэтому context автоматически остаётся в JSON fault.fault.descriptor/execution_version. Зеркальный logging enum/fault не требуется. Event activity для данного code — FAILED/ERROR, не MISMATCH: validated immutable request корректен, но exact исполнитель недоступен в текущей runtime composition. В таблице logging MISMATCH допускает остальные contract refusal codes; EXECUTION_UNAVAILABLE требует FAILED. Исходная причина передаётся в exc_info при наличии, без raw request/body. Terminal_kind=None, durable state observation сохраняется.

Порядок: inspect/binding validation → existing terminal replay → load/verify original immutable request → resolve exact Source execution binding → только при успехе recovery takeover/start/domain body. Resolver принадлежит Source; publication recovery owner получает результат exact admission через Source-owned internal binding. Отсутствие зарегистрированного исполнителя переводит в RecoveryContractError с EXECUTION_UNAVAILABLE. Проверка не запускает projector и не меняет latest/request. Arbitrary resolver exception не маскируется этим code, а выходит infrastructure failure.

Предпочтительно выдавать immutable execution handle из trusted composition с lifetime до окончания attempt. Повторная динамическая подмена binding после успешного resolve запрещена. Если runtime не может обеспечить lifetime, повторная проверка до domain entry обязательна, failure закрывает body и сохраняет operation unresolved. Выдача конкретного Source handle/signature остаётся частью Source REC-1/REC-5.

При EXECUTION_UNAVAILABLE никакого SourceMutationRefused или Applied не записывается, operation/request/holds сохраняются. В recommended ordering проверка до takeover сохраняет также прежние fence/attempt. Повтор explicit recovery после восстановления exact исполнителя использует тот же request и проходит обычные fencing checks. Новый operation_id автоматически не создаётся. Committed terminal читается при отсутствии исполнителя без projector/acquire.

Критерии: отсутствующая старая версия при наличии новой не fallback-ится; bool/строковый execution_version отвергается Source input validation; checksum/schema corruption не маскируется execution-unavailable; terminal replay без исполнителя возвращает сохранённый outcome; незавершённая operation остаётся с прежними holds/fence; JSON сохраняет code/descriptor/version. Concrete terrain execution dossier остаётся Source prerequisite, REC-1 не объявляется закрытым этим mapping.
