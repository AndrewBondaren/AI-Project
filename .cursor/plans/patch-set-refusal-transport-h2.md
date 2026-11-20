# PatchSet: итоговый owning proposal H2-1/H2-6

## Принятые решения пользователя — 2026-11-21

Источник — [решения в общем H2-плане](interdomain-refusal-transport-h2.md#решения-пользователя-2026-11-21--encoding--representations--ids). Этот раздел имеет приоритет над историческими предложениями ниже. H2 целиком OPEN; code-go/миграции не разрешены.

| ACCEPTED ID | Concrete type / kind |
|---|---|
| 31007 | TimeCommitIssueCode / ENUM |
| 31139 | PrepareTimeAdvanceSection / RECORD |
| 31140 | TimeCommitRelationIssue / RECORD |
| 20150 | TimeSnapshotApplyResult (W) / RECORD |

Альтернативы 31108/31109 сняты. Existing 20124/20128/20131 и ранее принятые native IDs не меняются; runtime TimeSectionRefused и validator errors IDs не получают. Принятие назначений не является evidence runtime registration/closure/round-trip. Исторический source audit ниже относится именно к прежним кандидатам: его результат не переносится на 31139/31140 как будто эти номера проверялись тем поиском.

W/R policy ACCEPTED: новые записи используют W; replay возвращает исходный поддерживаемый concrete член R без old→new adaptation. Сохраняются old root20124 format1 и roots20125/20126/20127 в existing формате; declaration/identity/meaning старого root не заменяются generic/new W. Registry D остаётся набором diagnostics текущих handlers; R не расширяет этот D. Полный legacy diagnostic roster ещё OPEN, неизвестные historical subclasses не обещаны. БД не обследованы.

Encoding boundary ACCEPTED: DecodeLimits проверяет encoding при создании binding до чтения, включая прямой публичный helper; значения задаёт composition. Budgets — strict положительные int без bool; collection bounds 0 <= minimum <= maximum; field limits согласованы с моделями/полями, противоречивые дубликаты запрещены. Неверный тип конфигурации — TypeError, значение/отношения — ValueError. Malformed bytes/tag/length и превышение корректного бюджета — CanonicalEncodingError. Publication сохраняет cause при infrastructure mapping, не создаёт business refusal.

Shared parser root extraction read_record_root_id проверяет размер, внешнюю RECORD-оболочку/границы и положительный canonical ID с budgets прочитанной части; не создаёт модель и не доказывает nested validity. После dispatch обязателен full bounded decode. Принятый read order: row/size -> checksum -> root extraction -> exact (format_version, root_id) reader -> full decode -> row/body identity/category и owning operation checks. Пробные decode/fallback/копия parser в SQL codec запрещены. Техническая граница находится в encoding; exact API проходит coordinator и Publication consumer review, новый предметный домен не назначается.

Publication — принятая общая инфраструктурная часть ядра Snapshot, а не самостоятельный предметный домен. Snapshot -> internal operation store является внутренней инфраструктурной связью; exact capability/nested calls ещё проверяются. Это не разрешение произвольных foreign public pipeline calls. Terminal read/replay остаётся внутри apply_snapshot, read_world вне scope.

OPEN только соответствующий остаток: final signatures/configuration/node output и encoding API review; полный supported legacy diagnostic roster; exact новая write format/root pair. format1 + root20150 остаётся кандидатом при подтверждении неизменной оболочки/encoding, automatic bump не назначен. Самостоятельная serialization support 20128/20131 требует отдельного consumer. Принятые IDs/W-R/parser/error boundaries повторно не открываются.

## Апдейт H2-SIG / H2-IDS — 2026-11-20, PROPOSED

Исторический proposal; назначения и policy заменены принятым разделом от 2026-11-21 выше. Таблица кандидатов и audit сохранены только как evidence того прохода, не актуальная карта IDs.

W — TimeSnapshotApplyResult, D — TimeCommitRelationIssue, R — closed read roots, включающий W (proposal: old root20124 | W). Registry работает только с D и текущими handlers: добавление старого root в R не расширяет registry D и не требует legacy handler. Ниже прежнее упоминание одного result binding для codec уточняется разделением write W/read R.

Точная PatchSet construction boundary остаётся SectionRegistry[D](refusal_model: type[SectionRefused[D]]); публичные refusal_model и diagnostic_types имеют signatures из §1. Единственный локальный instance: SectionRegistry[TimeCommitRelationIssue](TimeSectionRefused). Связь с Snapshot constructor — registry: SectionRegistry[D], result_model: type[W], где W является именованным concrete child SnapshotApplyResult[D]. Это точные параметры boundary, не замена полного owning constructor Snapshot. Snapshot сравнивает свой domain D с registry.diagnostic_types по exact class identities; admission types принадлежат отдельному Snapshot roster. Binding.refusal_model is registry.refusal_model; binding.result_model is Snapshot result_model is Publication write_result_model. Сверяется также включение W в read roster R; R не подменяет D. Ошибка до первого apply — configuration TypeError/ValueError, не refusal. Read-only metadata registry вычисляется из модели, caller не задаёт вторую копию roster.

Единственное рекомендуемое размещение остаётся composition/snapshotTime/{contracts.py,binding.py}; reuse TimeSectionRefused, отдельный W. Publication предоставляет owning typed read/write representation binding для R/W: его exact тип не выдумывается в PatchSet и остаётся H2-SIG prerequisite. Старые результаты не преобразуются в W силами registry. Snapshot определяет apply[S,R] и DAG return; PatchSet не выбирает место привязки S за Snapshot.

### Source collision audit и предложенные номера

До записи этого раздела выполнен `rg -n --hidden '31007|31108|31109|20150' backend .cursor docs .agents`: exit 1, совпадений нет. Это аудит доступных исходников/планов/документов с обычными ignore rules rg, не всех persisted БД, удалённых веток или глобального allocator. Проверены Time §43 и actual artifacts coreManifest: Time enum proposal 31000–31006; records 31100–31106, отдельно принято 31107; calendar records 31110–31138. Actual соседние shared records включают 20140 ArtifactGcFailure и 20141 PinHolder; plans предлагают отдельные pack IDs 20201–20205. Соседние диапазоны не являются доказательством формального владения всеми свободными номерами.

| Proposed ID | Concrete owner / kind | Основание |
|---|---|---|
| 31007 | dataModel/time/results/commit.py::TimeCommitIssueCode / ENUM | Следующий свободный по source audit номер после Time enum proposal |
| 31108 | dataModel/time/changes/section.py::PrepareTimeAdvanceSection / RECORD | Достижим через issue.request, не пересекает accepted native IDs или calendar proposal |
| 31109 | dataModel/time/results/commit.py::TimeCommitRelationIssue / RECORD | Достижим через W.diagnostics |
| 20150 | composition/snapshotTime/contracts.py::TimeSnapshotApplyResult / RECORD | Новый W root, свободен по source audit; 20124 не переиспользуется |

Номера только предложены, НЕ зарезервированы. Closure W включает shared Snapshot result fields/admission issue и Time issue -> request -> proposal/capture/interval/point/publication refs; используются прежние IDs этих dependencies. TimeSectionRefused не сериализуется этим terminal path; binding, validator, exceptions не регистрируются. OperationRecord[R] не получает новый ID автоматически: Publication подтверждает его фактическую persist reachability, прежде чем расширять минимальную карту. Existing 20124/20128/20131 не изменяются. Полный manifest merge/round-trip с новыми concrete классами сейчас не выполнен; source no-collision не доказывает runtime closure или historical compatibility.

### Encoding dispatch owner и итог

Фактический общий механизм — backend/app/encoding/canonicalCodec.py: decode[T](encoded: bytes, expected: type[T], manifest: CanonicalSchemaManifest) -> T; private _decode_one разбирает TLV. Публичного bounded root-tag dispatch API в проверенном модуле нет. Указания на назначенного владельца/агента этой новой границы не установлено; PatchSet не присваивает себе владение. Publication подтверждает owning encoding участника через координатора. Не копировать private parser в terminal codec и не перебирать roots пробными decode.

H2-SIG registry -> W: PASS совместимости предложенного boundary, приёмка и полный W/R construction остаются OPEN. H2-IDS: source no-collision PASS для четырёх кандидатов в указанной области; reservation/closure/IDs acceptance OPEN. H2-DISPATCH/REP остаются внешними gates. Ни code-go, ни migration/version decision этот аудит не создаёт.

2026-11-20. PROPOSED, не code-go и не приёмка H2 целиком. Источники: [общая постановка](interdomain-refusal-transport-h2.md), [Snapshot H2](snapshot-refusal-transport-h2.md), [write flow](dag-multidomain-patch-publication-draft.md). Принятые assembler/native/codec/IDs и H3 не переоткрываются.

## 1. Точные публичные контракты

Пути относительно backend/app. В dataModel/patch/results/sectionResult.py: SectionRefused[D: BaseModel] сохраняет category: SnapshotApplyOutcomeKind и diagnostics: tuple[D, ...] с min_length=1; strict/frozen/extra-forbid/revalidate-always и existing запрет COMMITTED. SectionValidation[D] = SectionAccepted | SectionRefused[D]. Accepted/receipt не меняются. Bound BaseModel не разрешает открытый runtime carrier.

В application/patch/contracts/sectionHandler.py:

```python
class DomainSectionHandler[S: DomainSection, D: BaseModel](ABC):
    @property
    def contract(self) -> SectionContract[S]: ...
    @property
    def refusal_model(self) -> type[SectionRefused[D]]: ...
    async def validate(self, section: S, context: SnapshotValidationContext) -> SectionValidation[D]: ...
    async def apply(self, section: S, context: SnapshotApplyContext) -> SectionApplyReceipt | SectionRefused[D]: ...
```

В existing application/patch/registry/sectionRegistry.py:

```python
class SectionRegistry[D: BaseModel]:
    def __init__(self, refusal_model: type[SectionRefused[D]]) -> None: ...
    @property
    def refusal_model(self) -> type[SectionRefused[D]]: ...
    @property
    def diagnostic_types(self) -> frozenset[type[BaseModel]]: ...
    def register[S: DomainSection, L: BaseModel](self, contract: SectionContract[S], handler: DomainSectionHandler[S, L], codec: SectionCodec[S]) -> None: ...
    def require(self, key: SectionKey) -> BoundSectionHandler[D]: ...
    def resolve(self, section: DomainSection) -> BoundSectionHandler[D]: ...

class BoundSectionHandler[D: BaseModel]:
    def __init__[S: DomainSection, L: BaseModel](self, contract: SectionContract[S], handler: DomainSectionHandler[S, L], refusal_model: type[SectionRefused[D]]) -> None: ...
    async def validate(self, section: DomainSection, context: SnapshotValidationContext) -> SectionValidation[D]: ...
    async def apply(self, section: DomainSection, context: SnapshotApplyContext) -> SectionApplyReceipt | SectionRefused[D]: ...
```

Read-only properties registry — проверяемый construction contract для Snapshot: diagnostic_types вычисляется из принятой refusal_model один раз, не задаётся вторым независимым roster. Это metadata классов, не payload carrier. Snapshot сверяет свой D с этим набором и exact refusal_model с composition binding без доступа к приватным полям registry. Codec methods остаются прежними.

## 2. Проверки и ответственность

Construction: именованные concrete refusal children без новых полей/семантических validators; ограничения общего carrier сохранены. L/D — закрытые наборы named concrete immutable diagnostic classes. Открытые BaseModel/FieldPathError, Any/dict/unbound generic запрещены. Локальный набор exact class identities является subset композиционного; наследование само по себе не разрешает новый subtype. Все проверки до регистрации. Ошибки конфигурации — TypeError/ValueError.

Bound handler сохраняет existing section admission. После вызова проверяет exact local refusal class, strict structural validity и exact diagnostic types. Переносит category и tuple в composition refusal без model_dump/dict/cast и без coercion одной diagnostic ветви в другую. Типы, все operands и порядок сохраняются; object identity не обещается. Concrete field-error subclasses сохраняют свои paths; Time relation issues paths не получают.

Предлагаемый application/patch/errors.py::SectionHandlerContractError(RuntimeError) означает нарушение output contract, не business refusal. Оборачиваются с cause только ошибки проверки возвращённого output; infrastructure exceptions/cancellation самого handler не перехватываются. Mapping этой ошибки во внешнюю Snapshot fault boundary согласует Snapshot; durable business refusal из неё создавать нельзя.

ACCEPTED: TimeSectionRefused содержит только общие structural invariants; Time validator перед return проверяет общий request, codes/order/category. Инварианты отдельного TimeCommitRelationIssue остаются у модели. Registry/Snapshot не повторяют Time predicates. Validator exact API принимается в Time H2-T.

## 3. Единая локальная composition

Поддерживается единственный путь Snapshot proposal: composition/snapshotTime/contracts.py — TimeSnapshotApplyResult(SnapshotApplyResult[TimeCommitRelationIssue]); composition/snapshotTime/binding.py — build_time_snapshot_binding() -> TimeSnapshotBinding. Прежнее предложение PatchSet composition/timeSnapshot заменено этим размещением. Owner предлагается application composition root, подтверждает координатор с пользователем.

TimeSnapshotBinding — immutable application configuration: result_model: type[TimeSnapshotApplyResult], refusal_model: type[TimeSectionRefused], manifest: CanonicalSchemaManifest. Reuse Time-owned TimeSectionRefused из dataModel/time/results/commit.py; второго refusal record нет. Registry получает refusal_model, Snapshot result_model и ту же registry, Publication тот же result_model и согласованный manifest. D=TimeCommitRelationIssue. Snapshot admission roster добавляется только Snapshot result model. В core нет Time imports, builder не вызывает IO/domain pipelines и не выбирает следующий runtime шаг.

Canonical roots: сохраняется concrete Snapshot result с diagnostics, а не локальный SectionRefused. Поэтому TimeSectionRefused не получает ID только ради registration/return handler. Регистрируются реально сериализуемый result root и достижимая closure; internal bindings/validators/exceptions не получают IDs. Existing IDs не переназначаются. Новые root identities и полный manifest остаются на согласовании encoding/Publication/координатора.

## 4. Переходы и внешние условия

| Переход | Owning вывод |
|---|---|
| Time issue -> TimeSectionRefused | PASS узкого принятого разделения ответственности; exact Time validator API принимается отдельно |
| Handler -> bound registry -> composition refusal | PASS согласованности предложенного дизайна; generic signatures/output checks ещё PROPOSED, runtime не реализован |
| Registry -> Snapshot result | PASS совместимости предложений: один D, public registry metadata, reuse refusal; OPEN подтверждение Snapshot construction/fault mapping |
| Snapshot result -> terminal/store/claim | OPEN: Publication обязан предъявить exact generic/closed nested containers и допустимый internal infrastructure port; одного codec недостаточно |
| Terminal -> exact replay -> DAG | OPEN: supported persisted roots, read compatibility и exact public result mapping; повторный handler/state read или потеря diagnostics запрещены |

Snapshot переносит category/diagnostics после подтверждённого rollback. Publication codec обязан проверять exact root, closure, version/kind/category/operation/row-body integrity, foreign/missing types; handlers и Time semantics не вызываются. Internal terminal reads остаются внутри apply_snapshot/Snapshot.apply, read_world вне scope. Это не разрешение foreign public pipeline call: exact port и nested trace ещё требуют общей приёмки.

Source compatibility breaking: существующие SectionRegistry(), DomainSectionHandler[S], прямой SectionRefused(...) и consumers/test fixtures требуют явного binding. Не вводить открытый default для обхода миграции. Persisted compatibility отдельно H2-5: БД не обследованы, version bump/migration не назначены, отсутствие данных не утверждается.

Проверка DAG/POJO узкого предложения: carrier только данные, handler owning semantics, registry только admission/dispatch, composition только construction; без новых CRUD/IO, hidden public pipelines, изменения порядка и зеркальных operands. Полная приёмка цепочки OPEN до внешних условий и решения пользователя. Код/миграции/тесты в этом проходе не выполнялись.
