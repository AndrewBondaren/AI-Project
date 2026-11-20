# Publication H2: signatures, dispatch, representations

## Принято пользователем 2026-11-21 — приоритет над историческими proposals

Прочитано полное решение в начале [H2](interdomain-refusal-transport-h2.md). Приняты W/R policy (новая запись W, old replay concrete root без adaptation); preservation format1/root20124 и existing roots20125/20126/20127; encoding config TypeError/ValueError отдельно от payload/budget CanonicalEncodingError; shared parser extraction с обязательным full decode и порядок row/size → checksum → extraction → exact reader → full decode → identity/category/operation checks. Это accepted boundaries, не готовая реализация.

Приняты canonical IDs: TimeCommitIssueCode ENUM31007; PrepareTimeAdvanceSection RECORD31139; TimeCommitRelationIssue RECORD31140; TimeSnapshotApplyResult RECORD20150. Вариант31108/31109 снят. Старые20124/20128/20131 не меняются; runtime TimeSectionRefused/validator errors без IDs. Ниже историческое «IDs не назначены», «W/R policy требует приёмки» заменено этим решением. H2-SIG/API review, legacy diagnostic roster и новая write pair ещё OPEN; code-go отсутствует.

## H2-REP freeze proposal: legacy concrete diagnostic roster

Проверены actual core manifests, terminalCodec, FieldPathError и SnapshotApplyRelationIssue declarations, tests/snapshotCore/support/diagnostics.py, test_retention_contract.py, test_codec.py и terminal fixtures. Это source inventory, не обследование БД/backups и не новый runtime test run.

| Concrete diagnostic / reachable type | Canonical ID | Manifest / evidence | Предлагаемый supported scope |
|---|---|---|---|
| SnapshotApplyRelationIssue | RECORD20307 | ARTIFACT_CORE_SCHEMA → PATCH_CORE_SCHEMA → SNAPSHOT_CORE_SCHEMA; applyIssues.py | Production legacy root20124: поддержать все текущие объявленные codes и exact context |
| SnapshotApplyCode | ENUM20306 | Та же цепочка; десять enum members в applyIssues.py | Closure предыдущего diagnostic, не самостоятельный diagnostic |
| ArtifactRef / ArtifactKind | RECORD20107 / ENUM20003 | ARTIFACT_CORE_SCHEMA; ARTIFACT_UNAVAILABLE.artifact | Closure relation issue; section_key/player_uid — scalar branded strings |
| FakeTargetIssue | RECORD90011 | TEST_ISSUE_SCHEMA = merge(SNAPSHOT_CORE_SCHEMA, FAKE_SECTION_SCHEMA, test issue entries) | Test-only legacy profile; не добавлять test type в production manifest |
| FakeTargetCode | ENUM90010 | support/diagnostics.py | Test-only closure, INVALID_NAME |
| ValidatedFieldPath / ModelIdentity / FieldSegment | RECORD90012/90013/90014 | TEST_ISSUE_SCHEMA; FakeTargetIssue.path | Test-only IDs именно этого profile; не назначать их production paths |
| FieldPathError | RECORD20137 | ARTIFACT_CORE_SCHEMA | Абстрактный carrier registration, НЕ concrete supported diagnostic: __new__ запрещает base/parameterized construction |
| ReferenceIssueContext / RuntimeIssueContext | RECORD20138/20139 | ARTIFACT_CORE_SCHEMA; test_codec standalone round trips | Не direct members result.diagnostics; не включать в diagnostic union по факту регистрации |

Production legacy roster, подтверждённый просмотренным default terminal composition: SnapshotApplyRelationIssue20307. Конкретный production FieldPathError subclass с terminal manifest binding в просмотренном контуре не найден; это не доказательство отсутствия historical subclasses. Старый root20124 сохраняет прежнее объявление diagnostics FieldPathError | SnapshotApplyRelationIssue. Фактический поддерживаемый набор concrete descendants ограничивает manifest; root declaration не обещает чтение любого неизвестного подкласса.

Relation codes exact: OPERATION_BINDING_MISMATCH, UNSUPPORTED_REQUEST_FORMAT, SECTION_BINDING_MISMATCH, DEPENDENCY_MISMATCH, WORLD_EXPECTATION_MISMATCH, PLAYER_EXPECTATION_MISMATCH, GAMEPLAY_NOT_STARTED, ACTIVE_TIMELINE_MISMATCH, TURN_SEQUENCE_MISMATCH, ARTIFACT_UNAVAILABLE. Context fields: section_key только для SECTION_BINDING_MISMATCH/DEPENDENCY_MISMATCH; player_uid только для PLAYER_EXPECTATION_MISMATCH; artifact только для ARTIFACT_UNAVAILABLE. Это inventory owning model, не новая реализация predicates в Publication.

Evidence: test_retention_contract.test_relation_context_and_concrete_field_issue_survive_mixed_round_trip обходит все SnapshotApplyCode, проверяет mixed (FakeTargetIssue, SnapshotApplyRelationIssue), exact types/order и ошибочный context. test_codec.test_shared_diagnostics_roundtrip_and_runtime_enum_requires_explicit_owner подтверждает diagnostic round-trip и явную регистрацию enum; test_cancelled_terminal_uses_production_codec — terminal cancel format1. support/fixtures.py создаёт StoredTerminalCodec(TEST_ISSUE_SCHEMA); test_claim_mapping/test_cas/test_atomicity используют refusal/rollback fixtures. sectionCodecPreSplitGolden.json — section corpus, не terminal golden bytes. Эти тесты ранее существуют; сейчас не запускались. Ни один пункт не доказывает полный historical terminal corpus.

Для одного ключа (1,20124) нельзя регистрировать несколько readers и угадывать manifest по ошибке decode. Production reader получает один явно замкнутый legacy manifest: core + утверждённые historical concrete diagnostics без collision. Test composition использует свой TEST_ISSUE_SCHEMA отдельно. Если два historical manifests конфликтуют по одному nested ID в том же (format,root), существующая row не различает их: FAIL совместимости до решения владельца representation, без fallback/адаптации.

Минимальный вопрос владельцу данных через координатора: «Нужны ли для поддерживаемых format1/root20124 outcomes concrete FieldPathError subclasses сверх приведённого production roster? Если да, назовите exact class + ID + manifest и безопасный encoded fixture; test FakeTargetIssue не считается production ответом». Пока ответа нет, неизвестные historical subclasses не объявляются поддержанными или отсутствующими.

## Новая write pair: рекомендуем (format_version=1, root_id=20150)

Предлагаю freeze этой пары. Source основание: PublicationOutcomeRow остаётся operation_id/outcome_kind/category/format_version/outcome_data/outcome_checksum; discriminator snapshot_apply и category не меняются. canonicalCodec сохраняет TLV-v1, RECORD tag7 и embedded explicit type ID; новый root20150 различим от20124 без изменения row envelope. Time nested IDs31007/31139/31140 расширяют explicit manifest, а не TLV grammar. Поэтому несовместимость, требующая смены row format, по рассмотренной дельте не обнаружена. Version1 не означает прежний root: dispatch всегда по паре.

Это proposal pair, не утверждение runtime совместимости: existing StoredTerminalCodec жёстко выбирает SnapshotApplyResult для snapshot_apply и новый root без H2-reader delta не прочитает. Требуются согласованный concrete W declaration, полный reachable manifest, collision review и terminal golden/round-trip/replay evidence. Existing decoder не является forward-compatible по факту сохранения format1. Если дальнейшая дельта изменит envelope/TLV, этот вывод пересматривается, но automatic bump не выполняется. Старые bytes/checksum/IDs не переписываются.

**Положение Publication — зафиксировано пользователем 2026-11-21.** Publication является общей инфраструктурной частью ядра Snapshot, а не самостоятельным предметным доменом. Оно обслуживает operation identity/immutable request binding, lifecycle выполнения, транзакционную фиксацию, terminal persistence и exact replay для Snapshot apply, Pack activation и gameplay start. Выражение «владелец Publication» означает владельца этой инфраструктурной части; отдельные чат и каталог application/publication не задают отдельный домен. Snapshot владеет применением готовых изменений и моделью apply result; предметные домены — семантикой своих данных/diagnostics; Artifacts — хранением artifacts и их защитой; DAG — оркестрацией. Зависимость Snapshot → внутренний Publication operation store классифицируется как инфраструктурная связь внутри ядра, но exact capability, nested calls и H2 contracts ещё проверяются. Эта классификация не разрешает произвольные foreign public pipeline calls, не передаёт Publication доменную семантику и не закрывает H2.

2026-11-20. PROPOSED, не code-go. Ответ владельца Publication координатору Between domain operations. Пользователь принимает общую цепочку через координатора. Общий H2-план не изменяется. H3, reuse TimeSectionRefused и Time-owned semantic validator не переоткрываются.

Источники: [H2](interdomain-refusal-transport-h2.md), [write flow](dag-multidomain-patch-publication-draft.md), [координация](../rules/interdomain-contract-coordination.mdc). Ниже пути относительно backend/app. Actual declarations проверены read-only; БД и backups не исследовались, runtime tests не запускались.

## H2-SIG — единый binding

W — concrete текущий Snapshot write result; R — closed union поддерживаемых Snapshot read roots, включающий W; D — closed diagnostics текущей composition. Предложение: R = прежний result root20124 | W, без adaptation. Это не выбор production union. Generic параметры в runtime обязательно конкретизированы; Any/dict/open BaseModel не carrier. Ниже annotations — целевой контракт, не уже компилируемый патч.

```python
# dataModel/artifacts/lifecycle/operation/record.py
class OperationRecord[R](BaseModel):
    operation_id: EntityUid
    world_uid: EntityUid
    kind: OperationKind
    preparation_fingerprint: RevisionHex
    publication_fingerprint: RevisionHex | None
    phase: OperationPhase
    fence: Annotated[StrictInt, Field(ge=1)]
    leased_artifacts: tuple[ArtifactRef, ...]
    terminal: R | PackActivationResult | GameplayStarted | OperationCancelled | None

# dataModel/artifacts/lifecycle/operation/claim.py
class PublicationTerminal[R](BaseModel):
    kind: Literal[OperationClaimKind.TERMINAL]
    record: OperationRecord[R]
class PublicationBusy[R](BaseModel):
    kind: Literal[OperationClaimKind.BUSY]
    record: OperationRecord[R]
type OperationClaim[R] = Annotated[
    PublicationOwner | PublicationTerminal[R] | PublicationBusy[R],
    Field(discriminator="kind"),
]

# application/publication/contracts/operationStore.py
class IOperationStore[W, R](Protocol):
    async def read(self, operation_id: EntityUid) -> OperationRecord[R] | None: ...
    async def claim_publication(self, kind: OperationKind, operation_id: EntityUid,
        world_uid: EntityUid, preparation_fingerprint: RevisionHex,
        request_fingerprint: RevisionHex) -> OperationClaim[R]: ...
    async def record_terminal(self, scope: CommitScope,
        outcome: W | PackActivationResult | GameplayStarted | OperationCancelled) -> None: ...
    async def record_refusal(self, claim: PublicationOwner, outcome: W) -> None: ...

# db/repositories/sqlite/snapshotCore/operations/operationStore.py
class SqliteOperationStore[W, R]:
    def __init__(self, commits: SqlitePublicationCommitStore,
        access: ScopedSqliteAccess, codec: StoredTerminalCodec[W, R],
        evidence: SqlitePublicationEvidence[R], artifacts: SqliteOperationArtifacts,
        *, record_model: type[OperationRecord[R]]) -> None: ...
    # Все четыре public метода точно IOperationStore[W,R]; recover/cancel отсутствуют.

# db/repositories/sqlite/snapshotCore/operations/publicationEvidence.py
class SqlitePublicationEvidence[R]:
    def __init__(self, commits: SqlitePublicationCommitStore,
        world: SqliteWorldPublicationStore, players: SqlitePlayerPublicationStore,
        access: ScopedSqliteAccess) -> None: ...
    async def check(self, scope: CommitReadScope | CommitScope,
        result: R | PackActivationResult | GameplayStarted | OperationCancelled) -> None: ...

# application/artifacts/storage/artifactLeases.py
class IArtifactLeases[R](Protocol):
    async def open_operation(self, operation_id: EntityUid, world_uid: EntityUid,
        kind: OperationKind, preparation_fingerprint: RevisionHex) -> OperationLeaseRef: ...
    async def assert_writable(self, lease: OperationLeaseRef) -> None: ...
    def writer(self, reservation: StagingReservation) -> AbstractAsyncContextManager[None]: ...
    async def finish_preparation(self, lease: OperationLeaseRef,
        refs: tuple[ArtifactRef, ...]) -> OperationRecord[R]: ...
    async def recover(self, operation_id: EntityUid) -> OperationRecord[R]: ...
    async def cancel(self, operation_id: EntityUid, fence: int) -> OperationRecord[R]: ...

# db/repositories/sqlite/artifacts/leaseStore.py
class SqliteArtifactLeases[W, R]:
    def __init__(self, scopes: SqliteArtifactScope,
        operations: SqliteOperationStore[W, R], artifacts: SqliteOperationArtifacts) -> None: ...
    # Методы точно IArtifactLeases[R]. W нужен concrete dependency, не lease output.

# application/publication/service/operationLedger.py
class OperationLedger[W, R]:
    def __init__(self, operations: IOperationStore[W, R], leases: IArtifactLeases[R]) -> None: ...
    # read/claim_publication/record_terminal/record_refusal точно IOperationStore[W,R].
    async def recover(self, operation_id: EntityUid) -> OperationRecord[R]: ...
    async def cancel(self, operation_id: EntityUid, fence: int) -> OperationRecord[R]: ...

# application/artifacts/contracts/stagingPort.py::IArtifactStaging[R]
# application/artifacts/staging/artifactStaging.py::ArtifactStagingService[W,R]
async def finish_preparation(self, lease: OperationLeaseRef,
    refs: tuple[ArtifactRef, ...]) -> OperationRecord[R]: ...
async def recover(self, operation_id: EntityUid) -> OperationRecord[R]: ...
async def cancel(self, operation_id: EntityUid, fence: int) -> OperationRecord[R]: ...

# application/worldSnapshot/contracts/applyPort.py
class IWorldSnapshotApply[S: DomainSection, R](Protocol):
    async def apply(self, patch_set: PatchSet[S]) -> R: ...
```

PublicationOwner остаётся прежним. Record сохраняет strict/frozen и operation/kind/category/fingerprint/phase validators. Constructors проверяют совместимость concrete roots. Старые base-model revalidation и model_dump round-trip не являются переносом diagnostics: каждый call использует связанный concrete model и сохраняет объекты/порядок.

Дополнительная constructor-матрица (остальные методы без semantic дельты):

| Класс/модуль | Binding constructor и ответственность |
|---|---|
| ArtifactStagingService[W,R], application/artifacts/staging/artifactStaging.py | __init__(registry: ArtifactFormatRegistryBinding, catalog: IArtifactCatalog, leases: IArtifactLeases[R], holders: IArtifactHolders, gc: ArtifactGarbageCollector, ledger: OperationLedger[W,R], log: ArtifactLifecycleLog, *, record_model: type[OperationRecord[R]]) -> None. Строгая revalidation через exact model, идентичную store model; не base OperationRecord.model_validate |
| SqliteArtifactCatalog[W,R], db/repositories/sqlite/artifacts/catalogStore.py | __init__(scopes: SqliteArtifactScope, operations: SqliteOperationStore[W,R], artifacts: SqliteOperationArtifacts) -> None. Storage facts, не interpreter diagnostics |
| SqliteArtifactHolders[W,R], db/repositories/sqlite/artifacts/holderStore.py | __init__(scopes: SqliteArtifactScope, operations: SqliteOperationStore[W,R], artifacts: SqliteOperationArtifacts, history: SqliteSnapshotHistoryStore) -> None. Existing constructor проверен; Artifacts подтверждает propagation своих adapters |
| SqliteOperationArtifacts | Возвращает refs, не terminal; W/R не нужен |
| Codec/evidence | Ни один не вызывает Time semantics; evidence только historical publication facts |

Ledger.recover сначала читает terminal; иначе delegates leases.recover. Ledger.cancel delegates leases.cancel. Lease recovery не разрешает takeover APPLYING/RECOVERY_REQUIRED. Terminal cancel возвращает прежний terminal, не обещает cleanup leftovers. W/R не меняет эти гарантии.

## Codec write/read boundary

```python
# db/repositories/sqlite/snapshotCore/operations/terminalCodec.py
class StoredTerminalCodec[W, R]:
    def __init__(self, *, binding: PublicationResultBinding[W, R]) -> None: ...
    def encode(self,
        outcome: W | PackActivationResult | GameplayStarted | OperationCancelled
    ) -> PublicationOutcomeRow: ...
    def decode(self, row: PublicationOutcomeRow
    ) -> R | PackActivationResult | GameplayStarted | OperationCancelled: ...

# Read-only covariant protocol: один concrete reader на root/model/manifest.
class StoredSnapshotResultReader[R](Protocol):
    @property
    def result_model(self) -> type[R]: ...
    @property
    def manifest(self) -> CanonicalSchemaManifest: ...
    @property
    def format_version(self) -> FormatVersion: ...
    @property
    def root_type_id(self) -> int: ...
    def decode(self, data: bytes, *, limits: DecodeLimits) -> R: ...
```

### H2-SIG уточнение 2026-11-21: одна construction configuration

Snapshot owning §8 выбрал S на экземпляре IWorldSnapshotApply[S,R]; method-generic S выше заменён. Это связывает section specialization с конкретной composition. Artifacts constructor принимает keyword record_model, и это должен быть тот же class object (`is`), что store.record_model, а не просто структурно похожая модель.

Минимальное предложение — один frozen internal application binding (не dataModel/wire, не token, не новый canonical root):

```python
# application/publication/contracts/resultBinding.py — PROPOSED
@dataclass(frozen=True)
class PublicationResultBinding[W, R]:
    write_model: type[W]
    write_format_version: FormatVersion
    write_manifest: CanonicalSchemaManifest
    readers: tuple[StoredSnapshotResultReader[R], ...]
    record_model: type[OperationRecord[R]]
    limits: DecodeLimits

    @property
    def read_models(self) -> tuple[type[R], ...]: ...
```

read_models — computed unique projection reader.result_model, не второй independently supplied roster. Readers — immutable construction bindings с публичными read-only properties result_model/manifest/format_version/root_type_id; не произвольные callbacks. PublicationResultBinding не дублирует их models/manifests отдельными mutable списками. Codec получает только binding вместо прежнего списка разрозненных constructor параметров. Параметр record_model в store/staging оставлен по owning signatures, но служит проверяемым constructor argument, а не независимой конфигурацией.

Публичная для composition (но не DAG data API) read-only инспекция:

```python
# IOperationStore[W,R], SqliteOperationStore[W,R], StoredTerminalCodec[W,R],
# OperationLedger[W,R], ArtifactStagingService[W,R]:
@property
def result_binding(self) -> PublicationResultBinding[W, R]: ...

# IArtifactLeases[R] и IArtifactStaging[R]: reader-only facet, W не добавляется.
@property
def record_model(self) -> type[OperationRecord[R]]: ...

# SqliteOperationStore[W,R] также явно предоставляет:
@property
def record_model(self) -> type[OperationRecord[R]]: ...
```

Store возвращает codec.result_binding, ledger — operations.result_binding, staging — ledger.result_binding; не создают копий binding. Concrete leases.record_model возвращает operations.record_model. Staging.record_model — class object, проверенный при construction. Factory создаёт binding один раз; передаёт его codec, а binding.record_model — store и staging. Store constructor отвергает record_model is not codec.result_binding.record_model; ledger отвергает leases.record_model is not operations.result_binding.record_model; staging отвергает несовпадение своего аргумента с ledger.result_binding.record_model или leases.record_model. Factory проверяет доступные свойства и identity всей собранной цепочки, не читая _codec/_operations/_ledger или Pydantic private metadata. Это fail-fast configuration fault до IO, не business refusal.

Construction validation binding: W — закрытый exact Snapshot result model; W входит в computed read_models; reader keys уникальны; каждый root ID указывает на exact reader.result_model в его manifest; write binding имеет соответствующий reader; record_model.terminal допускает ровно read_models плюс неизменные PackActivationResult/GameplayStarted/OperationCancelled/None. Проверка использует публичную schema/type API (model_fields/get_type_hints и закрытое раскрытие union), не приватное __pydantic_generic_metadata__. Неопознаваемый или открытый annotation отвергается, а не принимается по сходству. Модели/reader bindings после construction неизменны; mutable reconfiguration запрещена.

Snapshot factory сверяет выбранные W/R с этим одним binding и связывает IWorldSnapshotApply[S,R]. Она не создаёт второй конфигурационный DTO. Exact имя/путь application composition factory остаётся у Snapshot/composition owner; данное предложение предоставляет все проверяемые свойства и не назначает production union. Evidence[R] не получает второй binding: store передаёт только уже decoded/validated R, evidence проверяет общие historical facts, не выбирает root. Concrete catalog/holders получают тот же operations instance и не заводят configuration.

Результат этих трёх дельт: instance S и exact record_model синхронизированы; single-binding inspection предъявлен как PROPOSED для Snapshot/Artifacts/координатора. W/R policy, DISPATCH/REP/IDS не объявлены принятыми.

Concrete reader связывает exact model и manifest, использует shared bounded canonical decoder. Constructor отвергает незакрытые models, неполный reachable manifest, ID/owner conflicts и duplicate reader keys. W должен быть поддержан reader-ом; read-only R не разрешается записывать. Pack/Gameplay/Cancelled сохраняют собственные existing format/root bindings; write_format_version Snapshot не распространяется на них автоматически.

Store принимает W при новой записи, проверяет operation/request binding. record_terminal не сохраняет business refusal. record_refusal сохраняет только CONFLICT/REJECTED после confirmed rollback; unknown не считается rollback. При replay old result остаётся old concrete result; Snapshot/DAG принимают R. Неизвестная composition не запускает новую попытку и не удаляет diagnostics.

## H2-DISPATCH — encoding owner и bounded API

Actual technical owners: app/encoding/canonicalCodec.py (canonical TLV, CanonicalEncodingError, encode/decode/merge_manifests) и application/encoding/boundedCanonicalDecode.py (двухпроходный _Reader, header bounds, nodes/depth, shared _decode_scalar). decodeLimits.py уже задаёт DecodeLimits. Отдельный назначенный пользовательский агент-владелец encoding не установлен: координатор должен подтвердить reviewer этой дельты. Publication не присваивает себе общий encoding.

Proposed API в existing application/encoding/boundedCanonicalDecode.py:

```python
def read_record_root_id(data: bytes, *, limits: DecodeLimits) -> int: ...
```

Input: exact immutable bytes и existing DecodeLimits, конфигурация которого обязательно проверяется по правилам ниже; dataclass сам не является доказательством admission. Output: strict positive canonical type ID внешнего RECORD. Error: existing CanonicalEncodingError для malformed input/header, wrong outer tag, превышения валидного budget, noncanonical/nonpositive integer. No IO, manifest lookup, model construction, semantic checks. Это discriminator extraction, НЕ доказательство валидности полного payload.

### DISPATCH уточнение budget admission — 2026-11-21

Actual DecodeLimits — frozen dataclass без проверки значений. _Reader.header проверяет фактические depth/nodes/length, но не доказывает валидность configuration. Предлагается shared internal helper в application/encoding/boundedCanonicalDecode.py, до создания reader:

```python
def validate_decode_limits(limits: DecodeLimits) -> None: ...
```

Все scalar budgets max_bytes/max_nodes/max_depth/max_items — exact int (bool запрещён), строго >0. field_sizes — tuple RecordLimits; owner — concrete BaseModel class, owners не повторяются; collections — tuple CollectionLimit; minimum/maximum exact int, 0 <= minimum <= maximum; bound принадлежит объявленному owner, указывает на существующее tuple/frozenset поле; один bound field не задан дважды. Адmission проверяет конфигурацию, не payload. Дополнительные reader-specific поля/manifest closure проверяет concrete reader constructor. Новые defaults не назначаются.

Ошибка конфигурации: TypeError для неверных типов, ValueError для недопустимых значений/противоречий. Helper вызывается при construction PublicationResultBinding и на входе root helper/full decoder ДО wrapper, переводящего ошибки payload в CanonicalEncodingError. Поэтому arbitrary ValueError не перехватывается как malformed payload. Config failure до IO не business refusal и не persisted corruption. Для full decoder это proposed изменение общей admission boundary, требует encoding owner review, а не утверждение existing поведения.

Header extraction проверяет max_bytes для input, depth/nodes только посещённых заголовков, минимальность/знак root integer и точные границы outer record/inner pair/fields tuple. Не обещает max_items/field_sizes для содержимого fields tuple, total nodes/depth всего документа, порядок/уникальность полей, registered schema или canonical re-encoding. max_items и field_sizes проходят только configuration admission на этом этапе. Полный bounded decode выбранного concrete reader применяет budgets ко всему обходу и declared collections, проверяет schema/значения/canonical bytes. Защита от большого root integer ограничена max_bytes; отдельного scalar budget в actual DecodeLimits нет и здесь он не выдумывается.

Malformed header либо превышение payload budget при корректной configuration — CanonicalEncodingError; terminal boundary переводит это в PublicationInfrastructureError с причиной. Ни extraction success, ни checksum не означают успешный full decode. Общий encoding owner остаётся внешним согласующим; это адресное proposal расширение existing shared reader, не передача Publication владения encoding.

Implementation constraint: выделить/reuse existing _Reader.header и _decode_scalar внутри того же encoding module. Не копировать TLV reader в terminalCodec. Проверить max_bytes до обхода; outer RECORD tag7 занимает весь input; вложенный tuple tag8 занимает всё record body; первый member — canonical integer tag2 >0; следующий member имеет tuple tag8 и занимает остаток внешнего tuple. Length bounds/depth/node checks выполняются shared reader-ом. Значения полей не декодировать и большие integer не строить сверх разрешённого scalar/input budget. Полный bounded decode выбранного reader затем проверяет весь body/canonical round-trip. Root extraction не проверяет nested fields и не обещает их canonical validity.

Publication порядок: row fields/version и configured budget → checksum → bounded root extraction → exact (format_version, root_id) reader selection → full typed bounded decode → row/body category/id → store operation-kind/request evidence. Нет пробных decode/fallback/Any carrier. Hash проверяется над существующими bytes, без нового payload copy. Неподдерживаемые пары — infrastructure failure, bytes не переписываются.

Остаток DISPATCH: encoding owner review API/reuse/limits; runtime malformed/budget cases. Числовые budgets не назначены: trusted composition policy. До review API PROPOSED, existing public root-tag helper не найден.

## H2-REP — source inventory и политика

| Representation | Actual source evidence | Supported policy proposal |
|---|---|---|
| format1 / Snapshot result20124 | artifacts/encoding/coreManifest.py; terminalCodec.py | Старый exact model + frozen declared supported diagnostic manifests, read-only при новом W |
| format1 / Pack20125, Gameplay20126, Cancel20127 | те же файлы | Сохранить existing semantics/IDs/reader bindings |
| Record20128 | зарегистрирован в Artifacts manifest; SQL _load собирает его из rows, _save пишет outcome | Не переназначать. Полный persisted consumer inventory OPEN |
| SectionRefused20131 | patch/encoding/coreManifest.py | Не переназначать; новая TimeSectionRefused runtime, ID не нужен без serialization path |
| Новый W / Time request, issue, enum closure | owning Time/Snapshot proposal | Номера/root manifest/version OPEN; automatic bump запрещён |

Проверенные fixtures: tests/snapshotCore/contracts/test_codec.py (cancel terminal round-trip, diagnostic round-trip и canonical golden tests); support/fixtures.py (StoredTerminalCodec(TEST_ISSUE_SCHEMA)); support/diagnostics.py; storage/publication/test_claim_mapping.py, test_cas.py, test_atomicity.py; support/sectionCodecPreSplitGolden.json (section bytes, НЕ полный terminal corpus). contracts/test_preparation_source_codec.py исключает 20128 из своего отдельного manifest, не из всех форматов. core/container/packs.py создаёт StoredTerminalCodec() — actual composition требует перевода. БД/backups не открывались. Отсутствие explicit record encode call не доказывает отсутствие сохранённых records.

Рекомендуем separate read/write roots без adaptation. Новый writer пишет W, reader сохраняет старые concrete types/operands/category/order. Root20124 не присваивается W по сходству полей. Старые format/IDs не меняются по факту generic refactor. Compatibility policy и numeric IDs требуют отдельной приёмки.

Минимальный вопрос владельцу данных через координатора: какие прежние terminal representations и diagnostic manifests обязаны оставаться читаемыми после H2? Рекомендация — перечисленные old roots с утверждённым old diagnostic closure; нужны безопасные golden samples/manifest declarations, не доступ к production. Альтернатива — явное ограничение новой representation с отказом чтения старой; это пользовательское решение о поддержке данных, не подразумеваемое отсутствие данных.

## Internal capability и приёмка

Предлагается Snapshot.apply → internal IOperationStore[W,R] (claim/read/replay и persistence). Store → SQL access/terminal codec/historical evidence; ни один не запускает Source/Time public pipeline. Time handler остаётся в принятом registry dispatch. Snapshot не получает весь ledger с cancel/recover только ради replay. Scope internal issued capability, не DAG payload. Эта точная infrastructure boundary подлежит приёмке, не общий bypass междоменных запретов.

| Gate | Итог |
|---|---|
| SIG | PROPOSED: единые W/R и constructor matrix; Artifacts acceptance, Snapshot R/composition/typing ещё OPEN |
| DISPATCH | PROPOSED exact API на shared reader; encoding reviewer/implementation evidence OPEN |
| REP | Inventory исходников предъявлен; supported old diagnostic closure и данные владельца OPEN |
| IDS | Old20124/20128/20131 сохраняются; новых номеров не назначено, Time/Snapshot closure и collision audit OPEN |

Роли/признаки отказа: codec — pure representation (IO/Time predicates FAIL); store — bookkeeping/persistence (pipeline execution FAIL); evidence — historical facts (Time semantics FAIL); ledger — forwarding (implicit retry/cleanup FAIL); leases — admission/fence/drain (diagnostic erasure FAIL); Snapshot — apply/replay result mapping (old→new lossy conversion FAIL). Никакой новой ноды/порядка/CRUD API этим документом не создаётся. Полная архитектурная приёмка H2 остаётся OPEN; отсутствие сведений не PASS. Дальше coordinator сводит SIG → DISPATCH → REP → IDS, пользователь принимает, реализация отдельным разрешением.
