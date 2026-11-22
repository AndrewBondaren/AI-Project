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

### Карточки исполнителей Source — детализация проекта 2026-11-22

#### Собственные exact contracts: batch arithmetic

Уточнение проекта 2026-11-22: SourceRevisionBatchBuilder не получает live/tombstone/phase/hold состояние и не проверяет допустимость CREATE/UPDATE/DELETE. Эта проверка предшествует вычислению. Его единственная функция — применить уже определённое revision rule к exact operands и собрать provisional refs. Для этого foreign evidence DTO не нужен; reuse existing identity/revision/hash values:

```python
# application/worldData/sourceVersioning/mutation/revisionBatchBuilder.py
class SourceRevisionBatchBuilder:
    def __init__(self, *, revisions: SourceRevisionTransitionBuilder) -> None: ...
    def build(
        self, *,
        objects: tuple[tuple[RegistryMemberId, SourceRevision | None, RevisionHex], ...],
        collections: tuple[tuple[SourceCollectionId, SourceRevision | None, RevisionHex], ...],
    ) -> SourceRevisionChanges: ...
```

Каждая тройка содержит identity, previous revision и готовый semantic hash. None означает допущенное создание; builder не выводит отсутствие объекта из None. Обязательные preconditions: обе последовательности canonical/unique по full identity, общий world и допустимый touched set уже проверены, хотя бы одна identity присутствует; semantic hash получен по owning rules, для DELETE — по Source tombstone rules. Результат содержит соответствующий exact ref для каждой входной identity в том же canonical порядке. Метод не получает ArtifactRef и не может подменить semantic hash физическим digest или заменить body mapping. Невалидные internal operands — programming failure, не SourceFailure; конкретный общий programming-error transport остаётся собственным АР-1.

Критерии: initial revision=1; unchanged сохраняет предыдущую revision; A→B→A повышает seq дважды; object и collection refs не смешиваются; каждой входной identity соответствует ровно один выход; builder не реализует сравнение hash/seq вторым алгоритмом, а вызывает SourceRevisionTransitionBuilder. Запрещены IO, latest lookup, terminal construction и определение mutation permission.

#### Собственные local POJO methods и единые правила

Проектируемые методы ниже уточняют существующие модели §1/4, не добавляют поля или новые внешние carriers. Пути относительно `backend/app/dataModel/sourceVersioning`.

| Класс / модуль | Метод / функция | Граница проверки |
|---|---|---|
| SourceRegistryCreate / sourceRegistryMutation.py | Construction по exact typed полям; дополнительный after-validator не требуется | RegistryMemberId задан полем; body проверяет owning ArtifactRef, не Source reader |
| SourceRegistryUpdate / sourceRegistryMutation.py | registry_identity(self) → Self — expected.object_id должен быть RegistryMemberId | Не проверяет актуальность expected |
| SourceRegistryDelete / sourceRegistryMutation.py | registry_identity(self) → Self — тот же локальный variant constraint | Не выполняет tombstone/prune |
| SourceCollectionMutation / sourceRegistryMutation.py | Construction strict nullable expected_revision и existing refs | None не подтверждает отсутствие storage row |
| SourceRegistryMutationInput / sourceRegistryMutation.py | batch_shape(self) → Self — nonempty/unique/canonical changes, общий world и member descriptor, world membership | Допустимость member descriptor в configuration проверяет application; POJO registry не читает |
| SourceMutationApplied / sourceMutationOutcome.py | revision_shape(self) → Self — nonempty/unique/canonical result refs, world equality | Сверка touched set/request fingerprint и commit evidence у producer, не у POJO без request |
| SourceMutationRefused / sourceMutationOutcome.py | refusal_shape(self) → Self — failure.operation=APPLY_MUTATION | Не устанавливает факт сохранения terminal |

Update/Delete делегируют проверку registry variant одной private функции `_mutationValueRules.is_registry_ref(ref: SourceVersionRef) -> bool`; один и тот же алгоритм не копируется в два validators. Для batch предлагаются функции того же dataModel модуля:

- `change_identity(change: SourceRegistryChange) -> RegistryMemberId`: извлечь identity после допуска variant, без lookup/normalization.
- `duplicate_change_positions(changes: tuple[SourceRegistryChange, ...]) -> tuple[int, ...]`: позиции повторных full identities после первого.
- `invalid_change_order_positions(changes: tuple[SourceRegistryChange, ...]) -> tuple[int, ...]`: позиции нарушений принятого canonical identity order, без сортировки/repair. Canonical key переиспользует owning canonical contract, не новый str/repr порядок.

Application diagnostics переиспользуют эти predicates и отображают позиции в original mutation paths; POJO validators проверяют те же predicates. World checks используют существующие identities и Source world checker на application boundary. Для result refs переиспользуются existing unique identity predicates `_proofValueRules`, а не новый set-алгоритм. Common canonical order helper должен быть единственным для соответствующего ref type; его exact composition проверяется при АР-6.

Проверка чистоты: один invalid expected variant и независимый duplicate change не должны скрывать друг друга в application diagnostics; malformed ветвь не чинится; ни один POJO validator не создаёт SourceFailure/terminal, не вызывает application и не присваивает revision. Concrete mapping mutation relation diagnostics остаётся собственным пунктом §6, не долгом X-READ.

Корень путей ниже — `backend/app/application/worldData/sourceVersioning/`. Это конкретизация собственных ролей, не новые публичные междоменные контракты. Сигнатуры с неустановленным authoritative operand не подменяются Any/Protocol/пустой реализацией; отсутствие exact типа явно блокирует приёмку соответствующей карточки. Общий порядок проверки целого ядра сохраняется.

| Класс / файл | Методы: функция и действие | Зависимости / эффекты | Проверка ответственности |
|---|---|---|---|
| SourceRegistryMutationRequestChecker / mutation/validation/registryMutationRequestChecker.py (предлагаемое размещение) | check — проверить исходный SourceRegistryMutationInput: world, descriptor, уникальность touched identities, допустимость variants и связь membership descriptor; вернуть SourceFailure либо отсутствие ошибок | Общие identity/world rules и descriptor lookup; pure. Structural paths от mutation request | Несколько независимых ошибок сохраняются; не назначает revisions, не читает latest, не подтверждает expected revision без authoritative данных |
| SourceRevisionBatchBuilder / mutation/revisionBatchBuilder.py (предлагаемое размещение) | build — применить revision rule к проверенным operand triples и собрать SourceRevisionChanges; exact signature выше | RevisionTransitionBuilder; pure; live/tombstone admission — до builder | Не вычисляет owning semantic hash, не проверяет phase/holds, не пишет; unchanged hash не заменяет immutable mapping; output остаётся provisional |
| SourceRevisionAppender / revision/revisionAppender.py (предлагаемое размещение) | append — сохранить проверенные immutable revision transitions через Source revision store в разрешённой write boundary | Только owning revision storage; exact store/transition input contract OPEN | Повтор exact transition идемпотентен, другой body той же revision не перезаписывает запись; нет commit/latest выбора/semantic policy |
| SourceMutationOutcomeResolver / mutation/mutationOutcomeResolver.py (предлагаемое размещение) | resolve — сопоставить request binding с authoritative terminal observation; вернуть существующий подтверждённый outcome либо сохранить состояние без подтверждённого terminal | Owning terminal read/evidence contract OPEN; не собственный ledger | Нет mutation/retry/takeover; отсутствие terminal не равно rollback; unknown не превращается в SourceFailure |
| SourceRegistryMutationPipelineOpenPipeline / registryMutationPipelineOpenPipeline.py | apply — выполнить одну разрешённую mutation; exact public input/result §8.1 | Request validation, preparation, разрешённые execution/terminal bindings; полные constructors OPEN | Только confirmed outcome выдаётся как Applied/Refused; нет второго commit owner или автоматического вызова Snapshot |
| SourceMutationRecoveryPipelineOpenPipeline / mutationRecoveryPipelineOpenPipeline.py | recover — установить или законно завершить исход того же immutable request; exact public input/result §8.1 | Outcome resolver и owning recovery/attempt binding; полные constructors OPEN | Не вызывает public apply; replay не пересчитывает revisions/latest; новая попытка требует owning grant |

`__init__` каждого executor только фиксирует immutable collaborators и не выполняет IO. Строки с OPEN не имеют завершённого constructor contract; это запрет implementation placeholder, а не разрешение спрятать зависимость внутри метода. Для RequestChecker общий failure carrier известен, но точная агрегация mutation relation diagnostics должна быть сведена с §6 до приёмки. Нельзя записывать индекс mutation change в proof group_index/use_index ради совместимости.

Исторический SourceRegistryMutationApplier из staging P3 объединял required_refs и apply_in_scope и возвращал provisional Applied. Эта форма не является альтернативой данной декомпозиции: provisional payload — SourceRevisionChanges, а разрешённая вложенная цепочка writer/terminal ещё проверяется отдельно. Старый scoped execution не разрешает прямые междоменные вызовы.

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

### Request diagnostics: собственная детализация, 2026-11-22

Exact mutation inspect-functions, nullable slots, nested trace и критерии — [source-mutation-traversal-contract.md](source-mutation-traversal-contract.md). Его §4 уточняет общие predicates: duplicate_identity_positions/invalid_identity_order_positions заменяют ранние duplicate_change_positions/invalid_change_order_positions из §3, чтобы malformed branches не требовали repaired records. Это одна реализация правил для POJO и application, не дополнительный алгоритм.

Проект exact boundary в `application/worldData/sourceVersioning/mutation/validation/registryMutationRequestChecker.py`:

```python
class SourceRegistryMutationRequestChecker:
    def __init__(self, *, descriptors: SourceDescriptorLookup,
                 identities: SourceIdentityChecker,
                 worlds: SourceWorldChecker) -> None: ...
    def check(self, request: SourceRegistryMutationInput) -> SourceFailure | None: ...
```

Одна функция — проверить original mutation request до чтения authoritative state и preparation. Здесь None означает отсутствие найденных request ошибок; в отличие от proof request checker, mutation checker не возвращает origins для proof transformation. Это не разрешение исполнить mutation без expected-state/phase/retention проверок. Operation итогового failure фиксирована APPLY_MUTATION, а не выбирается caller-флагом.

| Проверяемое нарушение | Диагностика / точный контекст | Предел |
|---|---|---|
| Непригодное известное поле/variant | INVALID_SHAPE по actual typed path поля request | Unknown root/extra без представимого path остаётся structural отказом |
| UPDATE/DELETE с object_id другого variant | INVALID_IDENTITY по changes[i].expected.object_id | Не выдавать неподходящий ref как валидный registry member |
| Повтор full identity в changes | DUPLICATE_IDENTITY на повторном identity/object_id | Повтор не удаляется; i — исходный индекс |
| Нарушен canonical порядок changes | INVALID_SHAPE по changes | Не сортировать исходный request; canonical identity order один |
| World не соответствует request | WRONG_WORLD; source — exact пригодный expected ref при наличии, artifact — соответствующий body при наличии | group_index/use_index=None; для CREATE не придумывать revision, source=None |
| Descriptor отсутствует / несовместим с category/configuration | UNKNOWN_DESCRIPTOR / DESCRIPTOR_MISMATCH через owning checker | Точный existing identity path для field errors; без default definition |
| Owning key непригоден | INVALID_IDENTITY по original owning key path | Key adapter не выполняет IO/projector |

Field paths строятся shared FieldRef/CheckedPath от SourceRegistryMutationInput. Change index не записывается в group_index/use_index. Existing SourceLogicIssue не содержит create identity без revision: нельзя создавать fake SourceVersionRef для локализации. При совпадающих logic contexts одинаковые итоговые issues сводятся стабильно; точную локализацию каждого CREATE relation этот carrier не обещает. Если нужна такая локализация, требуется явная Source error delta; она не добавляется скрыто этим проектом.

Membership request world/descriptor compatibility относится к request validation; сравнение actual before/after membership с authoritative состоянием — последующая проверка. MEMBERSHIP_MISMATCH из proposal ниже нельзя реализовать как уже существующий код. Stale expected revision, missing/pruned revision, phase denial и operation binding conflict не определяются этим checker по одному request.

Агрегатор создаётся на вызов с SourceFieldIssue/SourceLogicIssue. Structural traversal сохраняет пригодные листья; semantic checks не обходят request заново. Общие `_mutationValueRules` дают positions без копирования правил. Before effects собираются все независимые ошибки; непригодный expected не мешает проверить соседний CREATE и membership. Для полного implementation допуска нужны exact mutation inspect-functions, как для proof traversal; эта собственная детализация не скрывается X-READ.

Проверки ответственности: wrong variant + duplicate соседней identity + неверный membership world дают доступные независимые diagnostics; changes[i] paths не уплотняются; checker не вызывает builder/store/projector; одинаковые logic issues не размножаются; infrastructure key composition error не преобразуется в business INVALID_IDENTITY. Отдельные relation коды и несовпадающие exact contexts сохраняются.

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

**Фазовая граница предложения (уточнение ревью 2026-11-16):** `apply` является исключительно pregame entry для исполнения новой mutation. После gameplay отдельный Source commit запрещён: Source готовит свои данные/ревизии, а применение входит в Snapshot-owned atomic apply с единственным commit owner Snapshot. Предложение ниже не разрешает Snapshot вызывать этот публичный pregame apply и не назначает новый DAG/scoped маршрут.

| Сценарий | Требуемое поведение |
|---|---|
| Новая попытка apply до gameplay | Проверка authoritative фазы и права попытки в общей с переходом gameplay границе сериализации, до writes; затем исполнение |
| Новая попытка apply после gameplay | Отказ без Source writes/новой terminal записи; не перенаправлять автоматически в Snapshot |
| Recover или exact replay, terminal уже существует | Проверить immutable binding и вернуть сохранённый outcome; изменение фазы само по себе не отменяет исторический terminal |
| Recover без terminal требует исполняющей попытки | Owning recovery grant необходим, но недостаточен: повторная authoritative проверка разрешённой фазы обязательна; после gameplay новую pregame попытку не выполнять |
| Фаза меняется конкурентно | Проверка и исполнение не разделяются окном TOCTOU; неподтверждённый outcome остаётся unknown, не маскируется фазовым отказом |

Source владеет этими ограничениями своего API и не доверяет caller-флагу pregame. Конкретный authoritative phase reader, владелец guard перехода gameplay, exact отказ/Input/Result/Error и borrowed transaction binding должны быть подтверждены Snapshot/Artifacts-publication (INT-WRITER, INT-DAG); Source не назначает их за другой домен. До подтверждения §8.1 **NOT READY**: ни один существующий proof code не переименовывается в phase refusal и новый error DTO не выдумывается. Проверки перечисленных сценариев обязательны при приёмке будущего mutation среза. Это конкретная незакрытая зависимость, не разрешение расширить текущий pure-срез её реализацией.

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
