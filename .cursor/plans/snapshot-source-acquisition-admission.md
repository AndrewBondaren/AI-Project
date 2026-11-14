# Snapshot: operation acquisition admission после Source finalize

2026-11-14. MINIMAL PROPOSAL для совместного review, не accepted/runtime. Закрывает отдельный design вопрос, исключённый из PACK-S1/S2. S2-TRACE-1 закрыт Source review и не переоткрывается. Владелец этого proposal — Snapshot/publication, Source проверяет только интеграционную границу своего capture owner. Код/DAG/генераторы/authored writer/миграции не меняются.

## 1. Решение: не менять SourceCaptureFinalizer

Existing finalize(request: SourceCaptureWitness, *, lease: OperationLeaseRef) → SourceCaptureRef | SourceFailure оставляется без callback, grant, target или Pack request. Его успешный return наступает после собственных commit/writer cleanup; replay ref сам по себе не даёт authority.

Admission выполняется **после** finalize отдельным Snapshot-owned internal service, который заново проверяет committed witness, exact source operation/lease, drained writers, полный capture closure и реальные operation holds под writer scope. Это observation committed acquisition, а не callback acknowledgement финализатора. Поэтому при successful replay нужны те же проверки; отсутствие hold не чинится повторной finalize или acquire.

Будущие Pack target/request не нужны этому сервису. Связь с ними появляется только при issue_operation по уже checked source context и затем register_sources. Capture workflow не знает Pack.

## 2. Durable source context до finalize

Чтобы после crash не восстанавливать право из произвольного holder UID, original capture owner регистрирует immutable контекст до вызова finalize. Proposed record `SourceAcquisitionBinding` в dataModel/publication/sourceAcquisitionBinding.py:

```python
lease: OperationLeaseRef
witness: SourceCaptureWitness
```

Strict/frozen/extra-forbid/revalidate-always; existing Source witness и lease переиспользуются, world_uid совпадает. Это relation acquisition operation↔finalize request, не новый witness/receipt/terminal. Lease fence — exact исходный owner, а не текущий автоматически подставленный fence. Target Pack, SourceProofReadInput и public execution DTO отсутствуют.

Хранение: append-only acquisition binding в **existing source operation ledger**, keyed by source operation_id, canonical binding bytes+checksum, immutable exact equality. Не второй receipt store, outcome или подтверждение finalize. Registration не создаёт/не продлевает holds. Данные не добавляются в Source witness/Source proof schema. Concrete schema extension требует приёмки отдельно от accepted READY candidate mechanism.

## 3. Exact internal ports и владельцы

`ISourceAcquisitionBindingStore` в application/publication/contracts/sourceAcquisitionBindingStore.py:

```python
async def append(self, scope: CommitScope, binding: SourceAcquisitionBinding) -> None: ...
async def read(self, scope: CommitReadScope, operation_id: EntityUid) -> SourceAcquisitionBinding | None: ...
```

Adapter SqliteSourceAcquisitionBindingStore — db/repositories/sqlite/snapshotCore/operations/sourceAcquisitionBindingStore.py. Same registered binding no-op; different witness/lease under same operation — immutable conflict. Unknown read → None; malformed/checksum/record disagreement → infrastructure. Append требует source scope operation identity, exact current lease и PREPARING/writable admission; store не выдаёт runtime capability.

`SourceAcquisitionAdmission` в application/publication/service/sourceAcquisitionAdmission.py:

```python
async def register(
    self, scope: CommitScope, binding: SourceAcquisitionBinding,
) -> None: ...

async def confirm(
    self, scope: CommitScope, operation_id: EntityUid,
) -> SourceAcquisitionAdmissionHandle: ...

async def resume(
    self, scope: CommitScope, binding: SourceAcquisitionBinding,
) -> SourceAcquisitionAdmissionHandle: ...
```

SourceAcquisitionAdmissionHandle — opaque nonserializable runtime class в application/publication/contracts/sourceAcquisitionAdmission.py, constructor закрыт; registry хранит exact instance, issuer, task/database/connection/scope, source binding, checked full acquired refs. Никакой новый публичный token. confirm/resume не finalize/acquire/release. resume additionally требует exact equality предъявленного binding и persisted registration; никакой поиск источника по holders(ref).

Trusted caller register — existing Source capture application owner, который действительно открыл source operation и владеет prepared witness, **не finalizer и не public Pack caller**. register доступен этому владельцу только через composition-bound registration interface. Generic transaction(operation_id) или знание lease не дают права на registration: сервис проверяет source-operation creation admission, выданный тем же staging/publication owner при реальном open_operation. Admission хранится в private registry; не конструируется из caller DTO. Это proposed internal composition extension к owner открытия операции, а не изменение публичного Source finalize/стадий, и требует Source owner review.

Trusted caller confirm/resume — тот же composition-bound capture acquisition owner или его явно зарегистрированная restart реализация. Проверяет originating operation registration; generic public caller не может вызвать этот internal interface. Runtime доверие здесь к application composition, не криптографическая защита от произвольного SQL writer. Public Source result не превращается в admission автоматически.

## 4. Точный жизненный цикл и acknowledgement

1. Capture owner открывает source operation штатным staging путём, получает exact lease и creation admission. В source writer scope register сохраняет SourceAcquisitionBinding; commit подтверждается до finalize. Этот scope заканчивается: finalizer запрещает ambient UOW, его transaction не вкладывается сюда.
2. Тот же owner вызывает existing finalize ровно как сейчас. Signature/algorithm/SourceFailure/unknown semantics не меняются. Если finalize отказал, был отменён, unknown или cleanup завершился ошибкой, **никакой handle не выдаётся**. Registration может остаться без acquisition — это не success.
3. После полного успешного return owner открывает новый writer scope и confirm. Store.read → exact current operation/lease/fence → writers drained → registered Source committed witness reader/collector → full capture refs → sealed states и exact OperationHolder(registered lease) каждого ref. Source semantics не копируются. Existing scope S2/explicit reads используется согласно принятому отдельно proposal; проверка scope не заменяет origin admission.
4. Только после всех проверок создаётся handle. В пределах одного scope его можно связать с target/request позже; вне scope он не остаётся usable. Сменив transaction/task/database, нужно resume, а не сохранять handle. Rollback/unknown/quarantine/revoke/cleanup error аннулируют handle в finally. Handle не заявляет новый durable event; он является checked view уже committed acquisition.
5. Когда известны Pack target и Source proof, PreparationAuthorityIssuer.issue_operation должен принимать **этот handle** явно, а не извлекать право из произвольного scope. Proposed замена прежней ambiguous signature:

```python
async def issue_operation(
    self, scope: CommitScope, source: SourceAcquisitionAdmissionHandle,
    target: OperationLeaseRef, request: SourceProofReadInput,
) -> PreparationAuthorityGrant: ...
```

Вызов происходит в target writer transaction. Если source context был подтверждён ранее в другой transaction, сначала resume его binding в текущем target scope через разрешённый owner-facing read admission. confirm/resume в этом режиме read-only относительно source ledger; scope operation принадлежит target, source operation проверяется explicit reads. register, напротив, требует source scope. Так target operation не притворяется source owner и source transaction не знает будущий Pack workflow.

Источник Source request membership/closure проверяется Source-only семантикой; scope-local S2 preflight и полный origin coverage обязательны. Issuer не принимает target/request как доказательство прав на источник. Затем register_sources→resolve_sources→adopt→READY остаются по текущему совместному proposal.

## 5. Crash/restart без finalizer replay

Crash после source commit до target registration: source binding уже persisted, grant/handle могли не существовать. Trusted restart owner загружает exact source binding, открывает writer transaction и вызывает resume. Он проверяет committed witness/closure и всё перечисленное в confirm заново, а не повторяет finalize. При успехе выдаётся свежий transient handle и grant для известного target/request.

Crash до source finalize commit либо после unknown: registration не доказывает success. Resume видит отсутствие committed witness/hold или недренированного writer и отказывает. Если был unknown cleanup, пока quiescence не доказана owning lifecycle, resume не выдаёт handle. При confirmed source commit+cleanup после crash resume допустим независимо от того, был ли доставлен прежний ответ caller.

Unknown commit регистрации: fresh read exact binding различает committed/missing; missing нельзя восстановить из одного finalized ref. Новая register после crash допускается только trusted operation creation/resume authority владельца, а не произвольным adoption caller. Старые операции без registration не конвертируются автоматически; no legacy backfill/fallback. Это явная цена новой checked restart семантики.

Source hold должен оставаться live до target adoption; registration сама lifetime не продлевает. Concurrent cancel/release/fence change приводит к явному отказу или сериализуется writer guard. После READY target holds защищают результат независимо от source lifetime; READY replay не resume-ит acquisition.

## 6. Exact отказ и границы принятия

Предлагается reuse PreparationAuthorityError/fault roster: missing acquisition binding → AUTHORITY_NOT_REGISTERED; different registered binding → IMMUTABLE_BINDING_CONFLICT; чужая creation admission/handle → INVALID_GRANT; lease superseded → STALE_ORIGIN; released source operation → ORIGIN_CLOSED; ref без hold → MISSING_SOURCE_HOLD. Live writers/quiescence unresolved → OperationBusyError. Corrupt binding/witness storage → PublicationInfrastructureError; Source semantic check → existing SourceFailure через owning rollback carrier; unknown transaction → UnknownCommitOutcome. Ни один отказ не создаёт нового terminal/capture/ref.

Публичная Source finalize signature и Source witness не меняются. Однако **capture application owner integration и operation creation admission являются proposed изменениями**, не уже готовой частью current runtime. Без их Source review full operation-origin path не принят. Новый record здесь — конкретное предложение вместо неопределённого provider; механизм candidate/READY и S1/S2 не переоткрываются.

Review вопросы Source: допустимость owner-local register до finalize с завершением scope; какой existing capture application owner получает operation lease и является точкой подключения; какие exact committed witness/collector методы используются confirm/resume без повторной finalize. Ни Pack target, ни issuer callback внутрь finalizer не вводятся. Если существующая Source composition не даёт owner issuance evidence, требуется согласовать именно создание admission на open_operation, не менять finalize return на Pack grant.

Evidence: read-only сверка accepted finalize §12.2–12.3, lease/operation records и текущего authority proposal. Runtime/typing/tests не запускались. Проверки будущей реализации: crash во всех промежутках register/finalize/cleanup/confirm/target register; fake/reused/cross-task handle; source release между scopes; exact restart без finalize; два SQLite connections; no authority из одного SourceCaptureRef. Код/Source spec не менялись.
