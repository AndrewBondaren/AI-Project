# Ответ Artifacts/publication по Source mutation

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

Предлагается application/artifacts/errors/sourceRootAcquireError.py с frozen strict SourceRootAcquireFault и SourceRootAcquireError, несущим fault. Fault содержит code: SourceRootAcquireCode, operation_id: EntityUid, source: SourceVersionRef | SourceCollectionVersionRef, artifact: ArtifactRef | None. Закрытые коды INVALID_SCOPE, OPERATION_MISMATCH, STALE_CLAIM, WRONG_KIND, WRONG_PHASE, ADMISSION_OPEN. Проверки exact DTO до IO используют стандартные validation errors. Active writers дают OperationBusyError; corrupt persisted chains дают PublicationInfrastructureError; transaction uncertainty остаётся UnknownCommitOutcome. Ошибки Source eligibility/closure возвращают исходный SourceFailure.

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

Уточнённый proposed enum SourceRootAcquireCode содержит INVALID_SCOPE, OPERATION_MISMATCH, STALE_CLAIM, WRONG_KIND, WRONG_PHASE, ADMISSION_OPEN и INVALID_ATTEMPT. Последний покрывает завершённую domain phase, повторное использование capability и отсутствие связи scope с единственной attempt. Proposed SourceRootAcquireFault содержит code, operation_id, source и artifact: ArtifactRef | None. Fault frozen/strict, SourceRootAcquireError переносит его. Модуль — backend/app/application/artifacts/errors/sourceRootAcquireError.py.

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

Для исключения окна после takeover разрешено commit-ить короткую takeover transaction, затем открыть fenced domain attempt. Конкурирующий recover может supersede ещё не вошедший owner: он получит stale и не выполнит body. Для предотвращения лишнего конкурентного supersede entry проверяет expected_attempt_id из recovery request; CAS mismatch возвращает актуальный recovery state, не создаёт ещё один fence. Это не таймер/автоматический retry loop.

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

async def inspect(
    operation_id: EntityUid, request_fingerprint: RevisionHex,
) -> SourceMutationRecoveryState: ...

async def claim_recovery(
    request: SourceMutationRecoveryInput,
) -> PublicationAttemptOwner | SourceMutationApplied | SourceMutationRefused: ...

def transaction_for_attempt(
    owner: PublicationAttemptOwner,
) -> AbstractAsyncContextManager[PublicationAttempt]: ...
```

SourceMutationRecoveryState — discriminated immutable union Terminal(outcome), Active(attempt_id, fence), PreparationRequired(phase). Это status, не authorization и не второй outcome. claim_recovery возвращает terminal первым после сверки binding. Иначе под writer serialization проверяет expected attempt, closed admission/drain, immutable request и exact required artifacts, затем переводит fence/holds и выдаёт нового owner.

Source internal apply owner загружает сохранённый request через checked ledger reader и выполняет transaction_for_attempt. Domain savepoint и refuse/succeed semantics предыдущего раздела сохраняются. Внешний recovery entry выполняет не более одной recovery attempt за вызов; busy/unknown/stale явно выходят caller. Он не создаёт новую operation identity.

Предлагаемый RecoveryContractError с frozen fault(operation_id, code) и enum BINDING_MISMATCH, ATTEMPT_CHANGED, WRONG_PHASE, INVALID_REQUEST_BINDING, STALE_OWNER. Busy writer/lock — OperationBusyError. Corrupt immutable request/checksum/schema или holders — PublicationInfrastructureError. Неизвестный COMMIT/ROLLBACK — UnknownCommitOutcome. Source expected/membership отказ сохраняется как SourceMutationRefused с исходным для этой attempt failure. Нет конвертации infrastructure faults в SourceFailure.

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

Ошибки — typed DomainAttemptBindingError с frozen fault(operation_id, code), модуль application/publication/errors.py. Предлагаемые коды INVALID_SCOPE, OPERATION_MISMATCH, WRONG_PHASE, STALE_ATTEMPT. Повреждённый durable start/chain/request binding даёт PublicationInfrastructureError. Binding не открывает UOW, не меняет fence, не выдаёт новую attempt и не читает latest Source revision.

P2.11 совместим с рекомендуемым recovery. Новый attempt_id получает только свежие записи собственной transaction. Старые uncommitted rows откатились; ранее committed creation допустима для REQUIRE_EXISTING только с successful terminal и текущим touched link. Committed revision rows без successful creation terminal — infrastructure inconsistency. Refusal terminal не подтверждает создание revision. Terminal replay acquisition не запускает. Bootstrap требует отдельного контракта provenance.

## Обязательный logging contract recovery — 2026-11-14

Пользователь принял explicit recovery original request под новым fence и обязал логировать причину и итог на штатном production уровне. Предложение использует get_consumer_logger(LogConsumer.ARTIFACTS), existing routes.py, JsonLogFormatter и artifacts/artifactLifecycle server route. Producer — общий publication recovery owner, управляющий operation lifecycle. Требуется дополнение docs/tz_logging.md о данном producer на app.artifacts; новый logger/handler/file не вводится.

POJO — backend/app/dataModel/artifacts/recoveryEvents.py::OperationRecoveryEvent. Эмиттер — backend/app/application/publication/logging/operationRecoveryLog.py::OperationRecoveryLog. Он использует core LogLevel/facade; dataModel содержит immutable event records и enum.

OperationRecoveryEvent frozen/strict/extra-forbid/revalidate-always содержит activity: RecoveryLogActivity, recovery_id: EntityUid, reason: RecoveryReason, operation_id: EntityUid, world_uid: EntityUid | None, preparation_fingerprint: RevisionHex | None, request_fingerprint: RevisionHex, observed_phase: OperationPhase | None, old_attempt_id/new_attempt_id: EntityUid | None, old_fence/new_fence: PositiveInt | None, durability: RecoveryObservation, terminal_kind: RecoveryTerminalKind | None, source_codes: tuple[SourceFieldCode | SourceLogicCode, ...], source_paths: tuple[ValidatedFieldPath | None, ...], hold_count: NonNegativeInt | None, fault_code: RecoveryContractCode | None. Code/path tuples имеют одинаковую длину и сохраняют исходный порядок; None используется для logic issue без POJO path. Concrete imports Source code enums и accepted path projection необходимо сверить с окончательным Source errors module перед реализацией. Поле message/raw payload/SQL/полный failure/outcome отсутствует.

RecoveryReason — EXPLICIT_RESUME, UNKNOWN_COMMIT_ACK, INTERRUPTED_ATTEMPT. Caller обязан передать typed reason, без inference из текста exception. Existing recovery input дополняется reason; request_id берётся из общего logging context, не участвует в request fingerprint. recovery_id назначает recovery entry один раз на invocation и передаёт всем вложенным emitter calls. Повторный recovery получает новый recovery_id; operation_id и attempt chain связывают invocations через restart. World/fingerprints берутся из validated request/record; до успешного read отсутствующие поля None, без фиктивных UID.

RecoveryObservation — OBSERVED, PROVISIONAL, SAVEPOINT_ROLLED_BACK, OUTER_ROLLED_BACK, COMMITTED, UNKNOWN. RecoveryTerminalKind — APPLIED либо REFUSED, идентифицирует вид существующего terminal, без копии его payload.

Эмиттер имеет methods emit_inspected(event), emit_takeover_committed(event), emit_domain_rolled_back(event), emit_provisional_refusal(event), emit_terminal_committed(event), emit_terminal_replayed(event), emit_busy(event), emit_mismatch(event), emit_unknown(event, cause), emit_failed(event, cause). Каждый метод фиксирует соответствующую activity и severity и валидирует обязательный context; service не выбирает произвольный LogLevel. Internal emit выполняет typed validation до best-effort sink boundary. Поля можно собрать private factory emitter по typed arguments; public arbitrary record severity запрещён.

| Activity | Production уровень | Producer и момент |
|---|---|---|
| RECOVERY_REQUESTED | INFO | Recovery entry до inspect, причина/operation/fingerprint/recovery_id |
| RECOVERY_INSPECTED | INFO | После durable read, observed phase/attempt/fence |
| RECOVERY_TAKEOVER_COMMITTED | INFO | После confirmed takeover commit, old/new attempts/fences, число перенесённых holds |
| RECOVERY_DOMAIN_ROLLED_BACK | INFO | После подтверждённого rollback savepoint либо outer transaction, durability различает границы |
| RECOVERY_PROVISIONAL_REFUSAL | WARNING | Source получил failure; только codes/checked paths, durability PROVISIONAL, terminal_kind=None |
| RECOVERY_TERMINAL_COMMITTED | INFO для APPLIED, WARNING для REFUSED | После confirmed outer commit, durability COMMITTED |
| RECOVERY_TERMINAL_REPLAYED | INFO | Прочитан existing terminal, новый commit не утверждается |
| RECOVERY_BUSY | WARNING | Lock/writers/владелец препятствуют попытке |
| RECOVERY_MISMATCH | WARNING | Typed binding/expected attempt mismatch; request rejected до body |
| RECOVERY_OUTCOME_UNKNOWN | ERROR | Commit/rollback acknowledgement неопределён, durability UNKNOWN |
| RECOVERY_FAILED | ERROR | Infrastructure failure, exception через existing exc_info |

RECOVERY_REQUESTED также требует emit_requested, фиксирующий INFO. Hold transfer логируется только после commit takeover; промежуточный successful SQL append не даёт COMMITTED. Rollback savepoint не объявляется rollback всей операции. Replay refuse содержит REFUSED и owning codes/paths, но не повторяет COMMITTED и не выдаёт новый domain refusal event. При SourceFailure после acquire entry сохраняет исходный failure через domain rollback-carrier, эмиттер получает только projection.

Конкретный конфликт с текущим logging ТЗ: STARTED/BUSY сейчас DEBUG. Для recovery пользователь требует штатную видимость причины и итога. Предлагается узкое дополнение ТЗ: RECOVERY_REQUESTED/INSPECTED — INFO, RECOVERY_BUSY — WARNING; уровни existing Snapshot STARTED/BUSY не меняются. Production router/server transcript allowlist должны разрешить эти записи app.artifacts. Добавление публикационного recovery producer на route также требует owning logging acceptance до кода.

Состояние/результат восстанавливаются из ledger независимо от доступности логов. Ошибки sink после записи durable результата не изменяют outcome, не запускают retry/cleanup и не создают вторичную failure event. UnknownLogConsumerError является composition defect и проверяется startup/preflight до операций; обработка такого неожиданного дефекта после commit также должна сохранить наружный durable результат. Existing emitter pattern re-raise UnknownLogConsumerError нельзя безусловно перенести в postcommit recovery boundary. Invalid typed event — programming error до исполнения по возможности; postcommit reporting failure не подменяет terminal.

Возможно несколько observations одного durable terminal при retries и потеря последней записи при crash. Exactly-once delivery не обещается. Инспекция после crash обязана записать actual observed terminal/attempt и reason нового recovery; отсутствие предыдущего log event не считается доказательством rollback.

Приёмка требует реального emitter→get_consumer_logger→router→JsonLogFormatter→server sink прохода при production INFO, а не только Mock emitter. Проверить JSON-поля request_id/recovery_id/operation/world/fingerprints и old/new attempt/fence, refusal code/path projection, absence raw payload. Fault injection: lost takeover ack, lost outer commit ack, crash до terminal, terminal replay после restart, busy, fingerprint mismatch, savepoint rollback, corrupted chain, sink exception. Сверить ledger/holds на втором соединении и события: новый COMMITTED только после подтверждения; unknown затем replay связаны operation/attempt, имеют разные recovery_id; sink failure не меняет durable/caller outcome.

Logging implementation и route/spec amendment входят в обязательный recovery срез до его runtime приёмки. Эти записи фиксируют контрактное предложение, runtime проверки ещё не выполнялись.

### Поля, producer ownership и проверка итоговой записи

Точный destination — existing route app.artifacts → artifacts/artifactLifecycle → logs/artifacts/artifactLifecycle.log. JsonLogFormatter добавляет request_id из core.logging.context.request_id_var. Входной HTTP/DAG/execution boundary устанавливает реальный request context; вложенные recovery calls наследуют его. После restart используется request_id нового вызова recovery, связь с прежним вызовом восстанавливается по operation_id и durable attempt chain. Отсутствующий request context не заменяется operation_id; отсутствие реального request_id в штатном entry является дефектом composition при приёмке.

RecoveryReason находится в предлагаемом recoveryEvents.py и используется typed recovery input. Это причина конкретного вызова inspect/recovery. Если unknown был получен предыдущим процессом, новый caller вправе передать UNKNOWN_COMMIT_ACK только по доступному evidence этого запроса; иначе EXPLICIT_RESUME либо INTERRUPTED_ATTEMPT. Причина не выводится из отсутствия строки в логах.

Согласованность события проверяет model validator: old/new fence положительны; new fence строго больше old для committed takeover; attempt IDs различаются; terminal_kind обязателен для terminal committed/replayed; APPLIED/REFUSED не ставятся для UNKNOWN; hold_count для takeover описывает подтверждённо перенесённые operation holds. Событие rollback содержит конкретную SAVEPOINT_ROLLED_BACK или OUTER_ROLLED_BACK observation. Для error events unavailable state остаётся None. При mismatch observed operation state берётся из durable read, а предъявленный request_fingerprint помечается именно как request value; для сравнения добавить observed_request_fingerprint: RevisionHex | None, чтобы не смешивать ожидаемое и фактическое.

SourceMutationRecovery producer вызывает emit_requested/emit_inspected и финальные emit_busy/emit_mismatch/emit_unknown/emit_failed/emit_terminal_replayed. Takeover owner вызывает emit_takeover_committed только после commit и подтверждённого переноса holds. Source apply owner вызывает emit_provisional_refusal с проекцией уже полученного SourceFailure. PublicationAttempt coordinator вызывает emit_domain_rolled_back после acknowledgement и emit_terminal_committed после outer COMMIT. Из этих producer calls только один владелец эмитирует один факт одной попытки; повторный caller observation оформляется replay, а не вторым commit event.

Каждый завершившийся recovery invocation получает итог: replay/новый terminal, busy/mismatch, unknown либо infrastructure failure. Для отмены добавить RECOVERY_CANCELLED уровня WARNING и emit_cancelled(event): coordinator указывает подтверждённую rollback/commit observation, если она известна. Cancellation во время IO acknowledgement без установленного исхода требует UNKNOWN; CancelledError сам по себе не доказывает rollback. Committed terminal, установленный до cancellation, не переименовывается в refused/cancelled operation outcome.

Для реальной аварии процесса завершающая log запись может отсутствовать. Следующий вызов inspect всегда пишет наблюдённое durable состояние и завершает собственную цепочку событий. В fault-injection приёмке проверяется именно такое поведение, а не невозможная гарантия последней строки при аварии.

Минимальный обязательный набор production проверок:

1. INFO-фильтр сохраняет REQUESTED с typed reason и correlation, INSPECTED и успешный/replayed итог. WARNING сохраняет busy, mismatch, provisional refusal и committed refusal. ERROR сохраняет unknown/infrastructure failure.
2. После fresh takeover COMMITTED событие соответствует реально увеличенному fence, attempt_id и перенесённым holds, проверенным вторым соединением. При lost ack сначала UNKNOWN, затем inspect/replay фактического состояния.
3. При Source refusal после записи links/holds provisional событие содержит owning codes/paths; после savepoint rollback logs фиксируют эту границу; только после terminal COMMIT появляется durable REFUSED. Другой процесс читает прежние domain rows и terminal refusal.
4. При terminal replay body/acquire/commit не выполняются; logging имеет REPLAYED и тот же terminal kind, operation/fingerprint, но новый recovery_id.
5. Fault sink не меняет возвращаемый terminal, phase, holds либо исключение recovery. Проверки включают postcommit UnknownLogConsumerError и обычную sink OSError. Ошибочная route composition обнаруживается также до первого runtime вызова.

Подробная запись logging contract завершена как проект. Приняты semantics explicit recovery и обязательность production logging. Конкретные event schema, route/spec amendment и runtime implementation проходят совместную приёмку до поставки.
