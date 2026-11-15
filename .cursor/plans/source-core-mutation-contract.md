# Source core — revision / mutation / recovery

2026-11-15. **CONSOLIDATED PROPOSAL, не принятый runtime контракт.** Пункт 2 остатка архитектуры ядра. Источники: source-pregame-revision-staging-design.md P1–P3, source-proof-v2-contract-spec.md §11.3, existing SourceRevision/refs. Здесь сводятся Source-owned значения и различия исходов; Snapshot/Artifacts/publication контракты не изменяются. Нет кода, новых backend, миграции или DAG wiring.

## 1. Единственный вход изменения

Сохраняется проект `app.dataModel.sourceVersioning.sourceRegistryMutation`:

| Тип | Обязательные поля |
|---|---|
| SourceRegistryCreate | kind: Literal[SourceRegistryMutationKind.CREATE], identity: RegistryMemberId, body: ArtifactRef |
| SourceRegistryUpdate | kind: Literal[SourceRegistryMutationKind.UPDATE], expected: SourceVersionRef, body: ArtifactRef |
| SourceRegistryDelete | kind: Literal[SourceRegistryMutationKind.DELETE], expected: SourceVersionRef |
| SourceCollectionMutation | collection_id: SourceCollectionId, expected_revision: SourceRevision или None, body: ArtifactRef |
| SourceRegistryMutationInput | operation_id: EntityUid, world_uid: EntityUid, execution_version: Annotated[StrictInt, Field(ge=1)], changes: tuple[SourceRegistryChange, ...], membership: SourceCollectionMutation |

SourceRegistryMutationKind wire values create/update/delete; SourceRegistryChange — discriminated union по kind, без нового RegistryVersionRef. Frozen/strict/extra-forbid/revalidate-always, deep immutable; nullable не optional; defaults отсутствуют. Changes непусты, unique full identities, canonical identity order. Один world и один registry-member descriptor; update/delete разрешают только RegistryMemberId внутри existing SourceVersionRef. Membership counterpart допускает именно этот member descriptor; SET уже принят для Terrain membership, а не автоматически для всех descriptors.

Expected revision — optimistic precondition, не команда назначить новую seq. None для collection expected означает отсутствие ранее зарегистрированной collection, не отсутствие retained bytes. Rename — delete+create двух разных identities; recreate tombstoned identity не разрешается без отдельного restore-контракта. Это scope registry batch; entity/library/settings mutations не добавляются.

Fingerprint включает весь canonical request, в том числе execution_version. Candidate ArtifactRef известен до stage по exact owning bytes; stage обязан совпасть с ним. Ref в request не доказывает существование/seal/hold. Semantic hash не копируется из ArtifactRef.content_hash. Предложенные IDs721xx остаются предложенными; реестр terminal/canonical типов этим документом не принимается.

## 2. Pure revision rule

Переиспользуется existing SourceRevision(seq, content_hash), новые revision DTO не нужны. Кандидат `revision/revisionTransitionBuilder.py`:

```python
class SourceRevisionTransitionBuilder:
    def __init__(self) -> None: ...
    def build(self, previous: SourceRevision | None, *,
              semantic_hash: RevisionHex) -> SourceRevision: ...
```

Одна функция — вычислить revision из предъявленного предыдущего состояния и уже рассчитанного semantic hash: previous=None → seq=1; одинаковый hash → прежняя revision; иной hash → previous.seq+1. Strict validation, без IO/commit/latest/projector. A→B→A даёт новую seq. Не разрешает CREATE занятой identity и не классифицирует live/tombstone: допустимость действия проверяется до вызова. Для DELETE authoritative Source tombstone encoding обязан дать соответствующее semantic evidence; builder сам не создаёт tombstone.

**Уточнение декомпозиции:** отдельный SourceRevisionChangeClassifier не нужен только ради сравнения двух hashes — это дублировало бы правило builder без самостоятельного инварианта. Предлагается убрать эту отдельную обёртку. Если для подготовки появится самостоятельная классификация с иными требованиями, её сначала предъявить отдельно. Это архитектурная дельта на согласование, не код.

При semantic equality immutable mapping существующей exact revision не заменяется новым body. Не переопределять здесь политику чужих glossary/morph или иных полей. Owning projector обязан предъявить semantic evidence; до него конкретная интеграция остаётся отложенной.

## 3. Подготовка и provisional result

Ни SourceRevision, ни построенный набор revisions не являются свидетельством применения. Для внутреннего batch результата предлагается **SourceRevisionChanges** в `mutation/revisionChanges.py`, frozen dataclass:

```python
@dataclass(frozen=True, slots=True)
class SourceRevisionChanges:
    object_revisions: tuple[SourceVersionRef, ...]
    collection_revisions: tuple[SourceCollectionVersionRef, ...]
```

Единственная ответственность — exact назначенные revisions затронутых identities. Проверки: tuples, strict существующие refs, unique identity/canonical order, хотя бы один ref. Request-specific checker проверяет соответствие world/touched set исходному request. Не содержит operation identity, receipt, durability flag, scope или failure. Не persisted/public DTO; не регистрируется в canonical terminal manifest. Он не зеркалирует outcome: не удостоверяет operation binding/commit, применяется как internal вычисленный payload.

`SourceRevisionTransitionBuilder` строит отдельные revisions; сборка batch агрегирует их в SourceRevisionChanges после проверки всего request. Применение в borrowed transaction возвращает тот же внутренний payload после успешных domain writes; это **provisional**, а не Applied. Его смысл не меняется на committed через поле status. Только outer commit owner способен подтвердить durable outcome.

Предложение заменяет внутри Source-проекта формулировку «provisional SourceMutationApplied» из staging P3.3. Нужен отдельный integration review transport к terminal owner: он может кодировать prospective terminal внутри транзакции, но caller не получает Applied до подтверждения commit. Не создаётся второй receipt/terminal store.

## 4. Единственные committed outcomes

Переиспользуются кандидаты `app.dataModel.sourceVersioning.sourceMutationOutcome`:

```text
SourceMutationApplied(
  operation_id: EntityUid, world_uid: EntityUid,
  request_fingerprint: RevisionHex,
  object_revisions: tuple[SourceVersionRef, ...],
  collection_revisions: tuple[SourceCollectionVersionRef, ...])

SourceMutationRefused(
  operation_id: EntityUid, world_uid: EntityUid,
  request_fingerprint: RevisionHex, failure: SourceFailure)
```

Оба strict/frozen/deep immutable; обязательные поля. Applied требует nonempty canonical unique refs и совпадения с request; Refused сохраняет existing failure.operation=APPLY_MUTATION и все diagnostics. В существующем authoritative ledger сохраняется один terminal outcome, не второй Source receipt. Same operation id/fingerprint replay возвращает exact сохранённый outcome без нового seq, latest check или запуска projector. Другой fingerprint — конфликт.

**Предлагаемая внешняя семантика mutation boundary:** успешный return — SourceMutationApplied либо SourceMutationRefused. Domain refusal после durable terminal не сворачивается в голый SourceFailure. Отказ preflight и unknown остаются отличимы (§5). Конкретные public class/method и error transport ещё подлежат архитектурной приёмке; existing public proof methods не меняются.

## 5. Ошибки и исходы — раздельно

| Ситуация | Представление / действие | Чего нельзя утверждать |
|---|---|---|
| Невалидный request на structural boundary | Existing Pydantic отказ; никаких fabricated paths | Что durable refusal записан |
| Проверяемый preflight отказ, terminal не записан | Existing proposed SourceMutationPreflightRejected(failure); exposed только после подтверждённого rollback при наличии scope | Что операция terminal REFUSED |
| Domain failure после начала writes | Internal SourceMutationRollback(failure) пересекает write boundary, требуется confirmed rollback | Нельзя return failure с частичными writes или commit после catch |
| Refusal сохранён outer commit | SourceMutationRefused с original SourceFailure | Не заменять голым failure на публичной границе |
| Успешный outer commit | SourceMutationApplied | Нельзя возвращать по одному успешному apply_in_scope |
| Неизвестен commit/rollback outcome | Existing UnknownCommitOutcome инфраструктуры | Ни success, ни confirmed refusal; никаких повторных mutation или cleanup по догадке |
| Другой infrastructure failure | Исходное typed infrastructure исключение | Не маскировать business absence/refusal |
| Cancellation | Существующая owning cancellation semantics; terminal cancellation — existing OperationCancelled | Не создавать Source cancelled DTO, не считать отмену доказанным rollback |

PreflightRejected и Rollback — разные internal control carriers, не новые diagnostics. Они сохраняют strict SourceFailure без перекодирования message и не сериализуются как terminal. Для initial preflight до создания scope нельзя выдумывать rollback/attempt; transport этого случая должен явно сохранить отсутствие durable terminal. Публичный exposure exception либо именованного error envelope — ещё отдельное решение, не молчаливый экспорт infrastructure внутренностей.

## 6. Единый error roster

Existing SourceFieldIssue/SourceLogicIssue/SourceFailure остаются единственным диагностическим контрактом. Known codes WRONG_WORLD, UNKNOWN_DESCRIPTOR, DESCRIPTOR_MISMATCH, REVISION_CONFLICT, BODY_MAPPING_CONFLICT, MISSING_BODY, CORRUPT_BODY, UNSEALED_BODY, MISSING_HOLD не меняют смысл. Paths mutation строятся от original SourceRegistryMutationInput, не от синтетического proof; change index не записывается как proof group/use index.

Из staging proposals требуют отдельной дельты общего SourceLogicCode: MUTATION_ID_CONFLICT, MEMBERSHIP_MISMATCH, REVISION_PRUNED, REVISION_NOT_FOUND. Они ещё не реализованы/приняты. Не заменять их CAPTURE_ID_CONFLICT/PROOF_MISMATCH. Последние два нужны exact historical reads, не обязательны каждому mutation алгоритму. New error enum или SourceMutationFailure с копиями diagnostics не вводится.

## 7. Recovery — одна ответственность: установить или законно завершить исход

Разделить функции: SourceMutationOutcomeResolver читает authoritative terminal/binding и классифицирует исход; отдельный approved attempt runner исполняет разрешённую попытку. Resolver не вызывает mutation сам и не делает takeover по одному отсутствию terminal. Recovery state machine/claims/fences принадлежит существующей publication инфраструктуре, не дублируется Source.

1. Проверить operation id и immutable request fingerprint.
2. При committed terminal вернуть сохранённый outcome; executor прежней версии для replay не нужен.
3. При отсутствии terminal не объявлять операцию новой/неприменённой. Продолжение возможно только по подтверждённому owning recovery grant, exact execution_version, closure/hold evidence.
4. При неизвестном результате сохранить unknown и данные восстановления. Не применять request к latest повторно и не освобождать holds как после подтверждённого завершения.

Logging requirement сохраняется: причина и исходные diagnostics, operation_id/request binding, stage, confirmed/provisional/unknown durability и итог. Initial preflight без attempt не получает synthetic attempt id. Exact event roster/sink остаются интеграционным долгом, не новой системой логирования Source.

## 8. Что заменяется и что остаётся открытым

### 8.1. Публичные методы — конкретное предложение

Модули под `app.application.worldData.sourceVersioning.operations`, один публичный класс и одна операция в каждом:

```python
# registryMutationPipelineOpenPipeline.py
class SourceRegistryMutationPipelineOpenPipeline:
    async def apply(self, request: SourceRegistryMutationInput) -> (
        SourceMutationApplied | SourceMutationRefused | SourceFailure | OperationCancelled
    ): ...

# mutationRecoveryPipelineOpenPipeline.py
class SourceMutationRecoveryPipelineOpenPipeline:
    async def recover(self, request: SourceRegistryMutationInput) -> (
        SourceMutationApplied | SourceMutationRefused | SourceFailure | OperationCancelled
    ): ...
```

Это exact public signature proposal, не готовый runtime. Recover использует тот же immutable запрос для проверки fingerprint, не отдельный mirror recovery input с копией полей. Не принимает flags режима, caller refs, lease/fence/scope/backend. Apply отвечает за одну mutation; recover — за восстановление исхода той же операции. Recover не вызывает публичный apply, а применяет общий internal attempt runner только по законному owning grant; не исполняет собственный revision алгоритм. Возврат terminal при replay не является новой публичной операцией.

Предлагаемая карта результатов без нового error DTO:

| Return / exception | Точная гарантия |
|---|---|
| SourceMutationApplied | Подтверждённый committed success этой operation/fingerprint |
| SourceMutationRefused | Подтверждённый committed terminal отказ с исходным SourceFailure |
| SourceFailure | Только preflight refusal текущего вызова: terminal этим вызовом не записан; при наличии transaction rollback подтверждён. Не утверждает, что иной конкурентный вызов не мог завершить операцию |
| existing OperationCancelled | Authoritative terminal cancellation этой operation, не просто отмена await |
| existing UnknownCommitOutcome | Исход commit/rollback неизвестен; не business result и не разрешение повторного apply |
| existing OperationBusyError | Нет права исполнять попытку сейчас; не refusal/unknown terminal |
| existing OperationBindingMismatchError | Owning ledger обнаружил другое immutable binding; не переименовывать в Source error посредством перехвата любого ValueError |
| Other infrastructure exception | Пробрасывается без подмены SourceFailure |

Internal PreflightRejected переводится в public SourceFailure только после confirmed rollback и без нового terminal. Initial проверка до scope может вернуть SourceFailure без выдуманного rollback. Internal SourceMutationRollback никогда напрямую не выдаётся caller как preflight: после него либо committed Refused, либо исходная infrastructure/unknown ошибка. Async cancellation не преобразуется автоматически в OperationCancelled.

Это уточняет §4–5: неразличимость устраняется сочетанием existing SourceFailure (preflight) и SourceMutationRefused (terminal). Никакой SourcePreflightResult-копии diagnostics не требуется. Согласование этой карты ещё нужно; internal exception transport владельца publication не меняется. Code MUTATION_ID_CONFLICT из старого proposal требует проверки необходимости: не дублировать existing OperationBindingMismatchError для одного и того же ledger condition.

### 8.2. Concrete integration evidence и граница реализации

Интеграционный долг зарегистрирован отдельно: [source-technical-debt.md — INT-ARTIFACTS-TERMINAL](source-technical-debt.md#evidence-int-artifacts-terminal). Статус и условие закрытия отслеживаются там.

Чтение кода 2026-11-15: `app.dataModel.artifacts.lifecycle.operation.record.OperationRecord.terminal` содержит SnapshotApplyResult/PackActivationResult/GameplayStarted/OperationCancelled/None, но не SourceMutationApplied/Refused. Значит Source terminal serialization/registration не готова. Existing shared ошибки находятся в `app.application.publication.errors`; OperationCancelled — в `app.dataModel.artifacts.lifecycle.operation.record`. Их новые аналоги не создаются.

Это INT-ARTIFACTS terminal-binding долг: подтвердить у владельца конкретную registration/codec и receipt read для Source outcome после reopen. Source не меняет shared union и не создаёт второй ledger самостоятельно. Конструкторы публичных классов должны быть предъявлены после архитектуры internal apply/recovery dependencies; эти signatures не разрешают placeholder ports или скрытую оркестрацию. Scope текущего шага — Source contract design, без внешних реализаций.

| Старый текст/риск | Консолидированное решение-предложение |
|---|---|
| P1 request roster без execution_version | Единственный кандидат включает execution_version согласно P2.13 |
| «Provisional SourceMutationApplied» | Internal SourceRevisionChanges, без committed гарантии |
| Committed refusal и preflight возвращают неразличимый SourceFailure | Terminal SourceMutationRefused отделён от preflight transport |
| Отдельный classifier только сравнивает hashes, builder повторяет это | Один pure revision builder |
| Recovery может выглядеть как обычный повтор apply | Authoritative replay/owning grant, отсутствие terminal не разрешает повтор |

Нужна собственная приёмка Source: internal SourceRevisionChanges и его инварианты; public mutation/recovery classes/methods и error transport; общий error roster delta; canonical terminal registration; exact pure batch validation signatures. Нет автоматического принятия всего staging-проекта.

Внешние долги: INT-WRITER (Snapshot authored-write/borrowed scope), INT-ARTIFACTS (terminal/holds/root/finalization), INT-TERRAIN (body/projector evidence), INT-DAG (маршрут). Они не мешают принять независимые Source value/algorithm границы, но запрещают выдавать runtime mutation за готовую.

Приёмочные сценарии будущего среза: CREATE/UPDATE/DELETE, A→B→A, unchanged hash с другим body, stale membership, same operation/different request, confirmed rollback, unknown commit и unknown rollback, replay после изменения latest, несовместимый execution_version, сохранение всех независимых diagnostics. Здесь tests не выполнялись, код не изменён, независимая приёмка не заявлена.
