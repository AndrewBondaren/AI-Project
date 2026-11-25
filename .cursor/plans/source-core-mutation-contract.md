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

### Единственный владелец arithmetic — проект 2026-11-25

Модуль `backend/app/application/worldData/sourceVersioning/revision/revisionRule.py` содержит одну pure функцию, не отдельный service-класс:

```python
def next_revision(
    previous: SourceRevision | None, *, semantic_hash: RevisionHex,
) -> SourceRevision: ...
```

Это единственное место правила: None → seq=1; equal semantic hash → previous; changed hash → seq+1. Функция получает structurally допустимые existing values, не world/body/status/authority и не IO. SourceRevisionTransitionBuilder.build делегирует ей; SourceRevisionBatchBuilder использует builder, не повторяет arithmetic. Internal transition __post_init__ вызывает ту же функцию и сравнивает результат с предъявленным next.source.revision. Identity/mapping constraints остаются у transition validation; их revision rule не проверяет.

DELETE отдельно требует changed semantic state: tombstone hash не может означать unchanged live state. После проверки этого предусловия ожидаемая tombstone revision получается той же next_revision, не второй формулой seq+1. Если tombstone encoding дал live hash, это postcondition/encoding failure, а не разрешение сохранить прежнюю revision. Builder не принимает флаг delete и не выбирает semantic policy.

Модуль application, как и internal transitions; существующий dataModel.SourceRevision ничего из него не импортирует и проверяет только форму seq/hash. Predicate owners в dataModel не вызывают builder. Таким образом arithmetic не переносится в POJO и не образует import cycle.

Проверки единственности: initial, unchanged (возвращается прежнее значение), A→B→A; ошибочный предъявленный transition отклоняется сравнением с общим правилом; DELETE с unchanged hash отвергается до append; отсутствуют собственные seq/hash ветвления в batch builder и дублирующие arithmetic formulas в validators. Это конкретизация architecture, не уже поставленный код или independent PASS.

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
- `duplicate_identity_positions(identities: tuple[RegistryMemberId, ...]) -> tuple[int, ...]`: позиции повторных full identities после первого.
- `invalid_identity_order_positions(identities: tuple[RegistryMemberId, ...]) -> tuple[int, ...]`: позиции нарушений принятого canonical identity order, без сортировки/repair. Canonical key переиспользует owning canonical contract, не новый str/repr порядок.

Это единственный нормативный набор predicates. POJO получает identities через change_identity; application — из пригодных leaf facts, сохраняя original positions. Функции над целыми changes отозваны и не реализуются параллельно. Ни POJO, ни checker не создаёт repaired change для проверки identity.

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

Актуальная собственная error delta 2026-11-25 — source-core-error-contract.md: exact REVISION_NOT_FOUND/REVISION_PRUNED, отсутствие дублирующего MUTATION_ID_CONFLICT и граница programming/owning transport. Это owner proposal на координацию, не runtime enum change. Раннее перечисление всех четырёх кодов ниже — история кандидатов; оно не разрешает автоматически добавлять MEMBERSHIP_MISMATCH.

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

### Собственный state admission — детализация 2026-11-24

Проект internal класса `application/worldData/sourceVersioning/mutation/validation/mutationStateChecker.py::SourceMutationStateChecker`. Одна ответственность — проверить допустимость изменения относительно предъявленного exact Source state. Он не получает право читать storage или проверять phase/holds. Request уже прошёл structural/request checks. Source state facts формируются после authoritative чтения, а не из expected полей запроса.

```python
class SourceMutationStateChecker:
    def __init__(self) -> None: ...
    def check(
        self, request: SourceRegistryMutationInput, *,
        live: tuple[SourceVersionRef, ...],
        tombstones: tuple[SourceVersionRef, ...],
        absent: tuple[RegistryMemberId, ...],
        pruned_expected: tuple[SourceVersionRef, ...],
        collection_current: SourceCollectionVersionRef | None,
    ) -> SourceFailure | None: ...
```

Это private facts existing values, не новый state DTO/authority token. Для каждой touched identity ровно один current факт: live, tombstone либо authoritative never-created absence. Категории не пересекаются, extra/duplicate identities и недостаточное покрытие — ошибка формирования internal input; отсутствующий факт **не** означает absent. collection_current=None допускается только после подтверждения отсутствия collection revision. pruned_expected сообщает отдельный факт истории exact expected ref; он не заменяет current state. Факты должны относиться к одной согласованной state observation; требования serialization перед append указаны ниже.

| Действие / current state | Решение Source | Диагностика |
|---|---|---|
| CREATE / absent | Допустить создание с previous=None | Нет ошибки; не создаёт revision |
| CREATE / live | Отказать: identity уже занята | REVISION_CONFLICT, source=current ref |
| CREATE / tombstone | Отказать: restore-контракт не принят | TOMBSTONE, source=current ref |
| UPDATE или DELETE / live равен expected целиком | Допустить переход | Сравниваются seq и semantic hash, не только seq |
| UPDATE или DELETE / live отличается от expected | Отказать stale/conflicting expected | REVISION_CONFLICT, source=expected |
| UPDATE или DELETE / tombstone | Отказать изменению уже tombstoned identity | TOMBSTONE, source=current ref |
| UPDATE или DELETE / absent | Отказать отсутствующему объекту | Предложенный REVISION_NOT_FOUND, source=expected |
| Exact expected содержится в pruned_expected | Отказать до арифметики | Предложенный REVISION_PRUNED, source=expected; для этой change не дублировать stale/absence диагноз |
| Collection expected=None / current отсутствует | Допустить initial membership revision | Не доказывает отсутствие body bytes |
| Collection expected=None / current существует | Отказать expected absence | REVISION_CONFLICT, source=current collection ref |
| Collection expected задан / current совпадает | Допустить membership transition | Full identity/revision equality |
| Collection expected задан / current отличается или отсутствует | Отказать | REVISION_CONFLICT либо предложенный REVISION_NOT_FOUND по exact expected collection ref |

group_index/use_index всегда None, artifact=None: state checker не делает выводов о физических bodies. Failure.operation=APPLY_MUTATION. Независимые changes и membership проверяются все; stable порядок — исходные changes, затем membership. Коды REVISION_NOT_FOUND/REVISION_PRUNED уже предложены §6, но ещё не добавлены в enum; до приёмки этой дельты реализовать checker с подменёнными кодами нельзя. Совпадающие issues стабильно сводятся; unknown/incomplete state не диагностируется как business absence.

Semantic equality content_hash не разрешает stale expected: admission сравнивает exact revision до вызова builder. Rename остаётся delete+create, recreation tombstone запрещена. Actual after-membership/ref-integrity — самостоятельная проверка полных предъявленных bodies, не задача этого checker.

Проверки ответственности: все строки таблицы; two independent stale changes + stale membership дают три различимых source contexts; missing observation не разрешает CREATE; pruned expected не даёт одновременно REVISION_CONFLICT; ни одна ветвь не вызывает builder/writer/projector. После успешного check нельзя применять изменения к другой state observation без повторного допуска или owning атомарного guard.

### Appender, runner, resolver: собственные обязательства и внешний предел

#### Source append transitions — собственный проект 2026-11-24

Existing SourceBodyVersion и SourceCollectionVersion уже задают exact live revision→body mapping; они переиспользуются целиком. SourceRevisionChanges содержит только refs и не подходит для записи mappings. Не расширять его body/scope/status полями и не выдавать его за append request.

Internal frozen records размещаются в `backend/app/application/worldData/sourceVersioning/revision/revisionTransitions.py`. Они не persisted/public POJO и не canonical terminal payload; их собственная ответственность — предыдущее ожидаемое состояние плюс предлагаемый переход, а не новый вариант live ref.

```python
@dataclass(frozen=True, slots=True)
class SourceLiveRevisionTransition:
    expected: SourceVersionRef | None
    next: SourceBodyVersion

@dataclass(frozen=True, slots=True)
class SourceTombstoneRevisionTransition:
    expected: SourceVersionRef
    next: SourceVersionRef

@dataclass(frozen=True, slots=True)
class SourceCollectionRevisionTransition:
    expected: SourceCollectionVersionRef | None
    next: SourceCollectionVersion

type SourceObjectTransition = (
    SourceLiveRevisionTransition | SourceTombstoneRevisionTransition
)
```

Все поля обязательны; входные existing values проверяются строго, tuple containers immutable. `__post_init__(self) -> None` каждого record проверяет только локальную форму перехода общими predicates модуля, без IO, assignment seq или вычисления hash. Live переход: expected=None требует next.source.revision.seq=1; иначе полная object identity совпадает, при unchanged semantic hash next.source=expected, при changed hash seq=expected.seq+1. Collection переход имеет те же правила по collection identity. Tombstone: identity совпадает, seq=expected.seq+1; body отсутствует по структуре типа, а не fake ArtifactRef. Его semantic hash определяется Source tombstone encoding до construction; record не принимает body hash вместо этого.

Эти predicates проверяют arithmetic через единое revision rule, не копируют алгоритм SourceRevisionTransitionBuilder в application. До реализации нужно вынести общее rule в единственный pure Source owner и использовать его из builder/transition validation, сохранив dataModel→application запрет. Records находятся в application, поэтому обращение к existing builder rule не создаёт обратного импорта. Tombstone обязан быть отдельным semantic state; совпадение его hash с live state не разрешает unchanged DELETE.

Store batch вход — `objects: tuple[SourceObjectTransition, ...]` и `collections: tuple[SourceCollectionRevisionTransition, ...]`. Это полные operands append, без нового batch DTO. Canonical/unique touched identities, единый world, наличие transitions и correspondence checked request обязательны. CREATE соответствует live expected=None; UPDATE — live expected=заявленный expected; DELETE — tombstone с exact expected. Membership соответствует request.membership identity/expected. Application не восстанавливает эти соответствия по position двух разных tuples: сравнивает полные identity keys.

**Ответственность SourceRevisionAppender.append:** принять проверенный batch в легитимной write boundary, атомарно сравнить expected/current и append immutable history/latest для всего batch; вернуть provisional SourceRevisionChanges из next refs. Получение scope/authority остаётся внешним binding, не полем transition. Полная executable signature до этого binding не объявляется; собственные два typed batch operands и результат определены здесь, без Any writer/callback.

Обязательные Source store инварианты:

1. Compare expected и запись входят в одну разрешённую атомарную boundary. Положительный preflight state check не заменяет compare при append.
2. expected=None означает подтверждённое never-created состояние; tombstoned или pruned history не превращается в CREATE slot.
3. Один exact revision имеет один immutable status/mapping. Другой body того же live ref — BODY_MAPPING_CONFLICT; live↔tombstone под тем же ref запрещён. Исторические mappings/roots при DELETE не удаляются.
4. Unchanged UPDATE сохраняет прежний exact body mapping, даже если candidate request body другой. Новый body не привязывается к старой revision. Owning authored/audit writes относятся к своему writer, не меняют это правило.
5. Повторный append не разрешается только по совпадению next rows. Идемпотентность новой попытки зависит от подтверждённого immutable operation binding; terminal replay идёт через resolver, без повторного append. Partial rows не признаются успешным batch.
6. Любой поздний конфликт/сбой отменяет весь batch через owning rollback. Return provisional не удостоверяет outer commit; unknown outcome не трактуется как отсутствие записей.

Store-level conflict codes переиспользуют REVISION_CONFLICT/BODY_MAPPING_CONFLICT; ошибки missing/pruned и недопустимого tombstone сохраняют §7 state-admission mapping. Infrastructure exceptions не преобразуются в эти коды. Сама SQL schema/transaction capability не проектируется этим record contract.

Проверки: mixed CREATE+UPDATE+DELETE+membership; stale expected одного элемента отменяет весь batch; unchanged hash с другим candidate body сохраняет old mapping; A→B→A имеет разные seq; DELETE не содержит fabricated live body; same seq/different hash и same ref/different body отвергаются; tombstone CREATE не допускается; возврат provisional при unknown commit не становится Applied. Эти сценарии фиксируют own store semantics независимо от конкретного external writer transport.

| Компонент | Собственный input/result и действие | Что остаётся external/deferred |
|---|---|---|
| SourceRevisionAppender.append | Checked request/touched set, допущенные previous refs, SourceRevisionChanges и exact body mappings. Проверить полное соответствие identities/seq/mapping до записи; применить один атомарный append batch. Результат только provisional SourceRevisionChanges; identical revision/mapping повтор не перезаписывает историю, другой mapping — отказ | Exact write capability и Source store binding; generic callable/Any writer не вводится |
| SourceMutationAttemptRunner.run | Одна разрешённая попытка: request/state admission → owning semantic evidence → batch arithmetic → permitted append. Не выбирает новую попытку и не делает recovery takeover. После domain refusal не допускает дальнейших writes/успешного результата | Выдача grant, допустимая write boundary, подтверждение rollback/commit; foreign domain calls из runner запрещены |
| SourceMutationOutcomeResolver.resolve | Сопоставить immutable request identity/fingerprint и предъявленный authoritative terminal observation. При exact binding вернуть существующий outcome без повторной arithmetic. Отсутствие terminal остаётся отсутствием наблюдаемого terminal, не разрешением новой попытки | Actual terminal observation type/reader и owning mismatch/unknown transport; resolver не читает чужой ledger самостоятельно |

Эти строки уточняют собственные обязанности, но не выдаются за exact исполнимые signatures трёх интеграционных компонентов. В частности, одним SourceRevisionChanges нельзя выразить body mappings, expected-state guard или authority. Не создавать урезанный append(request, changes), который скроет эти зависимости. Конкретные Source transition records/store input ещё требуют собственной детализации; это не внешний долг. Exact execution capability/terminal types остаются внешним binding.

Serialization requirement принадлежит Source семантически: между проверкой expected state и append не может измениться допускаемая revision/membership или фаза разрешённой новой pregame attempt. Реализует его согласованный owning commit/guard механизм. Ранний read phase/state без защиты не достаточен. Для replay готового terminal эта проверка не запускается повторно. Unknown commit/rollback не создаёт SourceMutationRefused и не разрешает автоматическую новую попытку.

Полные tests этой композиции должны подменять observation между admission и append и доказывать отказ без partial commit; отдельно проверять append success с unknown outer outcome, повтор exact terminal после смены latest и другой fingerprint. До owning binding эти сценарии — требования интеграционной приёмки, не блокер pure state checker design.

### АР-2: единый trace попытки и границы authority

Уточнение P2, 2026-11-22. Batch arithmetic не завершает композицию попытки. Ниже trace одной **новой разрешённой попытки**, а не утверждение готовности runner или новый порядок DAG. Request binding/terminal replay/recovery grant проверяются до выбора новой попытки по существующему §7/8: подтверждённый terminal возвращается без повторного state admission/projector/revision calculation; отсутствие terminal само по себе не разрешает выполнение. Маршрут между публичными доменными операциями остаётся у DAG.

| Стадия | Собственный owner и метод | Вход → выход | Источник authority / граница отказа |
|---|---|---|---|
| 1. Request validation | SourceRegistryMutationRequestChecker.check | SourceRegistryMutationInput → None либо SourceFailure | Pure original request checks, не authority. При refusal dependent stages не запускаются; terminal не выдумывается |
| 2. Authoritative state admission | Source: проверка expected object/membership, live/tombstone и допустимости действия; concrete class/signature пока OPEN | Проверенный request + exact authoritative state → допущенные previous revisions либо relation refusal | Source revision store facts; phase guard/serialization с gameplay start — owning внешний контракт INT-WRITER/INT-DAG. Caller pregame flag/старый preview недостаточны |
| 3. Semantic evidence | Source проверяет identity/version correlation входа; hash/projector — owning body domain | Допущенные изменения + owning semantic evidence → exact identity/previous/semantic_hash operands | Owning projector и immutable format/execution binding; Source tombstone rule для DELETE. Не читать чужой latest и не вызывать foreign projector напрямую из Source |
| 4. Revision calculation | SourceRevisionBatchBuilder.build → SourceRevisionTransitionBuilder.build | Exact operand tuples → SourceRevisionChanges | Pure calculation, не новое разрешение. Нарушенные internal preconditions/postconditions — programming failure; output provisional |
| 5. Permitted append | SourceRevisionAppender.append; внутренний SourceMutationAttemptRunner.run — proposed composition, exact contracts OPEN | Checked transitions + разрешённая write boundary → provisional append result | Owning writer/attempt authority; state preconditions должны быть защищены от изменения между admission и append. Atomicity с gameplay transition должна быть гарантирована владельцем, не одним ранним phase read |
| 6. Terminal resolution | SourceMutationOutcomeResolver.resolve | Immutable operation/request binding + authoritative outcome observation → подтверждённый outcome либо сохранённый unknown | Terminal registration/read/commit — publication/Artifacts. Source не объявляет Applied по успешному append; unknown не превращает в refusal/rollback |

**Attempt runner:** отвечает только за локальную согласованную попытку Source, не за выбор новой публичной операции, recovery takeover или вызов чужих доменов. Предлагаемый путь `application/worldData/sourceVersioning/mutation/mutationAttemptRunner.py`; имя SourceMutationAttemptRunner переиспользовано из staging design. Старые scoped run/apply_in_scope signatures не объявляются автоматически действующими. Для завершения нужны exact permitted write input/result/error, внутренние collaborators и trace до подтверждённого terminal. Не создавать placeholder runner, исполняющий только arithmetic.

До первого write ошибки request/state/evidence не допускают append. После любого write отказ требует подтверждённого owning rollback либо предусмотренного terminal refusal; возвращать голый preflight failure с частичными writes запрещено. Cancellation/неподтверждённый commit или rollback сохраняют owning transport и unknown outcome. Логи различают stage, operation_id, cause и provisional/confirmed/unknown, без второго Source terminal store.

Критерии завершения АР-2: exact state-admission class/input/result/error; concrete appender/runner/resolver contracts; подтверждённые foreign методы вместо описания роли; доказательство serialization admission→append с gameplay transition; failure trace каждой стадии; replay без повторной arithmetic; отсутствие прямого Source→foreign domain call. Проверки race: expected state изменилось после admission; gameplay стартовал до append; append прошёл, commit outcome unknown. Ни один из этих случаев не может дать ложный Applied. Этот trace конкретизирует оставшуюся композицию, но P2 не закрывается до получения перечисленных контрактов.

Разделить функции: SourceMutationOutcomeResolver сопоставляет уже предъявленный authoritative terminal с request binding; сам ledger не читает. Отдельный approved attempt runner исполняет разрешённую локальную попытку. Resolver не вызывает mutation и не делает takeover по отсутствию terminal. Recovery state machine/claims/fences принадлежит существующей publication инфраструктуре, не дублируется Source. Актуальная композиция — §9; прежние формулировки о чтении ledger самим resolver отозваны.

1. Проверить operation id и immutable request fingerprint.
2. При committed terminal вернуть сохранённый outcome; executor прежней версии для replay не нужен.
3. При отсутствии terminal не объявлять операцию новой/неприменённой. Продолжение возможно только по подтверждённому owning recovery grant, exact execution_version, closure/hold evidence.
4. При неизвестном результате сохранить unknown и данные восстановления. Не применять request к latest повторно и не освобождать holds как после подтверждённого завершения.

Logging requirement сохраняется: причина и исходные diagnostics, operation_id/request binding, stage, confirmed/provisional/unknown durability и итог. Initial preflight без attempt не получает synthetic attempt id. Exact event roster/sink остаются интеграционным долгом, не новой системой логирования Source.

## 8. Что заменяется и что остаётся открытым

### 8.1. Публичные методы — конкретное предложение

Актуализация error boundary apply 2026-11-25: Publication предъявил конкретный proposal PregameMutationRefusedError(.refusal: PregameMutationRefusal); exact поля/imports и окончательный proposed return/declared exception roster — source-mutation-node-pojo-card.md. Source подтверждает unchanged propagation, без добавления return variant и без Source error mirror. Указания ниже на отсутствующий typed phase refusal исторически заменены этим proposal; приёмка и runtime/authority readiness не объявляются. Эта дельта относится только к apply, не назначает recovery маршрут.

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

## 9. Единая композиция mutation — актуальный проект 2026-11-25

Этот раздел сводит §1–8; не вводит новую попытку или самостоятельную междоменную оркестрацию. Immutable request один, operation_id/fingerprint/execution_version не заменяются между стадиями. Read/write/terminal capabilities — EXTERNAL / DEFERRED. Собственные обязанности ниже не ждут выбора foreign API, но не считаются уже реализованными.

### 9.1. Граница владельцев и данных

| Исполнитель / файл под application/worldData/sourceVersioning | Единственная функция | Собственные входы → выход | Не делает |
|---|---|---|---|
| SourceRegistryMutationRequestChecker / mutation/validation/registryMutationRequestChecker.py | check: проверить исходный request | SourceRegistryMutationInput → SourceFailure или None; §6 | Не читает state, не назначает revisions |
| SourceMutationStateChecker / mutation/validation/mutationStateChecker.py | check: допустить действия относительно exact observation | Request + live/tombstones/absent/pruned_expected/collection_current → SourceFailure или None; §7 | Не получает state сам, не подтверждает phase |
| SourceMutationAfterGraphChecker / mutation/validation/mutationAfterGraphChecker.py | check: проверить согласованность итоговых Source relations до calculation/append | Request + before/after membership + references + surviving_targets → tuple[SourceLogicIssue, ...]; exact signature и internal input failures §9.4 | Не извлекает foreign references, не читает storage, не вычисляет revisions; descriptors — единственная constructor dependency; CREATE/UPDATE/DELETE корреляция обязательна |
| SourceRevisionBatchBuilder / mutation/revisionBatchBuilder.py | build: применить одно revision rule | Checked operand triples → SourceRevisionChanges; §3 | Не вычисляет hashes, не проверяет permission |
| SourceRevisionTransitionBuilder / revision/revisionTransitionBuilder.py | build: построить одну revision | previous + semantic_hash → SourceRevision через next_revision; §2 | Не дублирует arithmetic в batch/validators |
| Internal transition records / revision/revisionTransitions.py | __post_init__: локальная целостность expected→next | Existing refs/mappings → immutable transition; §7 | Не создают holds и не удостоверяют commit |
| SourceRevisionAppender / revision/revisionAppender.py | append: один atomic Source history/latest batch | objects/collections transitions + permitted write binding → provisional SourceRevisionChanges | Не выбирает semantic policy, не commit owner |
| SourceMutationAttemptRunner / mutation/mutationAttemptRunner.py | run: одна фиксированная локальная последовательность разрешённой попытки | Checked request, согласованная state observation, semantic evidence, exact mappings и permitted execution binding → provisional changes либо отказ попытки | Не reader/projector чужого домена; не выдаёт terminal; не запускает recovery |
| SourceMutationOutcomeResolver / mutation/mutationOutcomeResolver.py | resolve: проверить корреляцию предъявленного подтверждённого Source terminal | Request + canonical request fingerprint + SourceMutationApplied/Refused → тот же exact terminal | Не читает ledger, не превращает отсутствие terminal в разрешение исполнения |

Единственная точка request validation — public Source apply/recover owner в начале invocation, до terminal resolution и входа в runner. Оба owners используют один SourceRegistryMutationRequestChecker; повторный public invocation проверяет свой request заново. Runner не имеет request checker в constructor и принимает только уже допущенный request от этого owner; это внутреннее предусловие, не caller flag/новый trusted DTO. Constructor graph runner: state checker, after-graph checker, batch builder, appender. Batch builder использует revision builder, тот — next_revision. Resolver stateless (__init__ без зависимостей), ledger не читает. Owning execution binding не меняет выбранную точку validation.

**Historical validation / execution_version — уточнение 2026-11-25.** Request checker использует immutable SourceDescriptorLookup именно execution_version исходного request, а не текущую default composition. Execution version связывает descriptor definitions и правила validation, включая ordering semantics; canonical fingerprint уже включает эту версию (§1). Номер сам по себе не доказывает сохранность binding: composition обязана сохранять прежний lookup и совместимую реализацию правил на весь поддерживаемый replay lifetime. Переиспользовать version с изменённой семантикой запрещено. Public owner выбирается/связывается с этой immutable composition до check; mismatch request.execution_version с её версией отвергается до semantic validation. Checker не выбирает latest и не читает registry/storage динамически.

Это требование к binding, не утверждение о поставленном version resolver: exact внешний способ его предъявления остаётся интеграционной зависимостью. Недоступность historical composition — несовместимость поставки/binding, не новый business refusal исходной операции и не разрешение перезаписать terminal. Успешный upgrade обязан сохранять возможность проверки исходного запроса и возврата exact terminal. Replay не проходит state admission и after-graph evaluation заново. Проверки: выполнение v1 → смена default на v2 с иной definition → повтор v1 возвращает прежний terminal через v1 validation; подмена definitions под v1 и отсутствие v1 binding отклоняются как несовместимость; другой execution_version меняет fingerprint и не получает чужой terminal. Нового recovery механизма или второго request checker не вводится.

Exact pure resolver proposal:

```python
def resolve(
    self, request: SourceRegistryMutationInput, *,
    request_fingerprint: RevisionHex,
    terminal: SourceMutationApplied | SourceMutationRefused,
) -> SourceMutationApplied | SourceMutationRefused: ...
```

Проверяет operation_id/world_uid/request_fingerprint; для Applied также exact touched identities и collection identity относительно request, без сверки с текущим latest. request_fingerprint вычислен единственным canonical request encoder, не caller assertion публичного API. При совпадении возвращает предъявленный terminal без reconstruction/пересчёта revisions. Несовпадение здесь после owning admission означает internal correlation failure; исходный ledger binding mismatch не маскируется — его owning typed отказ возникает на интеграционной границе. Publication unknown, absence и OperationCancelled не преобразуются в Source Applied/Refused: owning boundary сохраняет их отдельный transport. Cancellation replay с проверенным request binding не требует вызова этого Source terminal resolver.

### 9.2. Порядок одной попытки и точка остановки

1. **Request:** check и все независимые diagnostics до dependent work. При failure никаких transition/append; это preflight, не persisted refusal.
2. **Admission:** внешний путь предъявляет согласованную observation/phase authority; state checker проверяет Source expected/live/tombstone/membership. Отсутствие observation не считается absent. Отказ прекращает dependent calculation.
3. **Evidence:** owning semantic evidence и mappings уже получены через разрешённый маршрут; Source сопоставляет их full identities/execution_version/request. Runner не запускает foreign projector. DELETE использует Source tombstone encoding.
   **Итоговые relations:** до revision calculation и append runner вызывает SourceMutationAfterGraphChecker.check по полным before/after membership и owning ссылочным facts. Ошибка прекращает dependent calculation/writes. Request/state admission не заменяют эту стадию; точный контракт §9.4.
4. **Calculation:** batch builder выдаёт refs. Runner формирует соответствующие internal transitions из request/observation/mappings; это упаковка одной локальной попытки, не второй revision algorithm. Unchanged UPDATE сохраняет исторический mapping, не candidate body; DELETE не содержит live body.
5. **Append:** appender повторно защищает expected/current в permitted atomic boundary и пишет весь batch. Положительный admission вне этой boundary не заменяет guard. Расхождение touched sets и mappings запрещает запись. Результат остаётся provisional.
6. **Publication/terminal:** завершение принадлежит внешнему commit owner по согласованному маршруту. Source runner не вызывает Publication/Snapshot pipeline и не пишет terminal в свой store. Только confirmed owning outcome поступает в resolver; unknown/cancellation сохраняются как отдельные исходы.

Обнаружение terminal для replay происходит до новой попытки; replay не выполняет пункты 2–5 и не зависит от latest. Recovery без terminal требует owning grant; этот документ не назначает новую recovery state machine. Внутренний run не выбирает apply/recover/publish ветвь публичного workflow.

### 9.3. Отказы, критерии и предел готовности

До writes SourceFailure останавливает попытку; после начала writes отказ нельзя вернуть как обычный preflight до подтверждённого owning rollback. Appender не завершает transaction самостоятельно. Unknown commit/rollback не даёт права повторно append или освобождать holds. При replay exact terminal не прогоняется через state admission. Same next rows не доказывают идемпотентность operation: нужен exact immutable request binding.

Проверки composition: malformed request блокирует state/calculation/append; stale state блокирует builder; неверная correlation evidence блокирует append; одна identity отсутствует в transitions — ноль writes; stale race/gameplay start между admission и append отвергается owning guard; partial write failure не возвращает успех; append success без confirmed commit не создаёт Applied; resolver не читает latest и возвращает exact terminal. Все stages имеют request-local данные, без shared mutable diagnostics. Ноль прямых foreign domain calls в Source collaborators.

**Готово как собственный проект:** роли и размещение, typed request/state/arithmetic/transitions, pure terminal correlation, последовательность и failure boundaries. **Не закрыто:** exact permitted execution/write binding и terminal admission transport, общий error transport дельт и архитектурная приёмка. Не называть эти ограничения отсутствием собственного trace, но и не выдавать таблицу за executable signature appender/run. Старые scoped applier с provisional Applied и resolver с ledger IO не являются альтернативными реализациями.

### 9.4. Итоговые Source relations — адресная дельта

`application/worldData/sourceVersioning/mutation/validation/mutationAfterGraphChecker.py::SourceMutationAfterGraphChecker` отвечает за согласованность итогового membership с batch и разрешимость предъявленных ссылочных отношений. Не извлекает ссылки из Terrain/material/settings bodies: их смысл и полноту extraction подтверждает owning domain. Предложение pure signature:

```python
class SourceMutationAfterGraphChecker:
    def __init__(self, *, descriptors: SourceDescriptorLookup) -> None: ...
    def check(
        self, request: SourceRegistryMutationInput, *,
        before: SourceCollectionBody | None,
        after: SourceCollectionBody,
        references: tuple[tuple[ArtifactRef, SourceObjectId], ...],
        surviving_targets: tuple[SourceObjectId, ...],
    ) -> tuple[SourceLogicIssue, ...]: ...
```

before=None только для authoritative initial collection. After коррелирует с request.membership.body; before — с допущенной previous membership. Source проверяет точный итог membership: CREATE добавляет identity, DELETE удаляет, UPDATE не меняет identity; не затронутые identities сохраняются. SET сравнивается по membership; для SEQUENCE ordering policy принадлежит immutable descriptor execution binding, checker не сортирует after по догадке. Отсутствующее правило sequence не считается успешным допуском.

references — owning-extracted отношения (ref ссылающегося **итогового** body, target identity). surviving_targets — полный допущенный live target set для области проверки, не только newly created members. Между ними и request/evidence должен быть exact binding; missing/неподтверждённый coverage не превращается в пустой references. Source проверяет, что каждый target остаётся разрешимым, и не применяет hidden rename old→new. Удаление старого материала при сохранённой ссылке settings на него даёт отказ даже при валидных revisions всех changes. Подтверждение полного набора затронутых входящих ссылок — внешний evidence binding; Source не строит чужой reverse index и не объявляет arbitrary caller tuple полным графом.

**Корреляция surviving_targets с batch:** область проверки включает все touched identities и все предъявленные reference targets; producer не может исключить CREATE из области произвольным утверждением. До проверки разрешимости ссылок тот же checker проверяет: ни одна DELETE identity не присутствует в surviving_targets; каждая CREATE identity присутствует; UPDATE сохраняет identity и также присутствует. Сравнение по полным SourceObjectId, без переименования или сопоставления только по local key. Для незатронутых identities полноту live observations удостоверяет owning evidence; эти локальные условия не доказывают её самостоятельно. Противоречивый materialized target set — internal input contract failure по error contract, а не успешный граф или semantic отказ корректного request. Только согласованный set используется для проверки references. Проверки: удалённая identity, ошибочно оставленная в set, блокирует append даже если все references разрешимы по этому set; пропущенная CREATE/UPDATE блокирует append; CREATE new + DELETE old с корректным set и retarget проходит; одинаковый local key другой полной identity не считается совпадением. Новые класс, DTO и error code для этой проверки не вводятся.

Предлагаемые SourceLogicCode: MEMBERSHIP_MISMATCH (membership_mismatch) при неверном after membership, artifact=request.membership.body; MUTATION_REFERENCE_CONFLICT (mutation_reference_conflict) при неразрешимой связи, artifact=ref ссылающегося body. source=None, group/use=None: существующий carrier не имеет target identity без revision, fake SourceVersionRef запрещён. Однотипные конфликты одного artifact стабильно сводятся; точную target-per-issue локализацию публичный carrier не обещает. Дельта кодов требует координации, не подменяется DEPENDENCY_NOT_CAPTURED/INVALID_SHAPE.

Issues агрегирует runner в APPLY_MUTATION failure до writes. Проверки: delete old/create new без retarget settings — отказ; same batch с owning-подтверждённым retarget — допускает relations; незатронутый member потерян — MEMBERSHIP_MISMATCH; empty references без completeness evidence — не success; checker не вызывает projector/storage и не вычисляет revisions. Полная validation выполняется один раз у public owner; runner только использует допущенный request. Это собственный проект, не уже принятый foreign evidence transport.
