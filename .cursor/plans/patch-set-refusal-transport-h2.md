# PatchSet: итоговый owning proposal H2-1/H2-6

## Актуализация статуса по решениям координатора — 2026-11-21

Источник: начало [общего H2-плана](interdomain-refusal-transport-h2.md), включая принятое разделение construction checks и сверку SectionHandlerContractError. Этот статус заменяет прежние OPEN/ожидание ответов ниже в перечисленных частях.

**Пункт 4: архитектурный выбор representation закрыт пользователем.** Текущая пара — (format_version=1, root_id=20150), concrete TimeSnapshotApplyResult для записи и exact replay текущего Snapshot-маршрута. Пометки «кандидат»/«freeze пары OPEN» ниже исторические и не являются действующими вопросами. No-legacy, прежние IDs и актуальные Pack/Gameplay/Cancelled неизменны. Полный manifest closure/collision audit, runtime binding, strict bounded decode, round-trip/replay и unsupported root/format failure без повторного apply остаются implementation/evidence задачами, а не повторным выбором пары. Полная приёмка H2/code-go этим не объявляется.

**Construction: узкий builder принят пользователем.** build_time_snapshot_binding(*, publication_binding: PublicationResultBinding[TimeSnapshotApplyResult]) -> TimeSnapshotBinding возвращает frozen binding с одним owning полем. PublicationResultBinding проверяет собственную конфигурацию при construction; TimeSnapshotBinding — exact Time result/root/diagnostic compatibility через публичные данные. Чужой __post_init__ вручную не вызывается. Snapshot проверяет registry/refusal/D/result; Publication/Artifacts constructors — свои codec/store/ledger/staging/leases identities. Application composition соединяет экземпляры; builder не собирает и не проверяет общий граф сервисов. Прежнее расхождение вариантов builder снято этим решением; exact owning validation API/интеграция ещё уточняются отдельно.

**Fault mapping: получен owning ответ Snapshot и координаторская сверка PASS ограниченной цепочки.** BoundSectionHandler выдаёт SectionHandlerContractError; Snapshot переводит его в PublicationInfrastructureError с cause внутри transaction body, без record_refusal/business terminal. Transaction owner завершает rollback/drain/revoke. После owner public boundary различает подтверждённый rollback -> INFRASTRUCTURE_FAILURE, UnknownCommitOutcome -> OUTCOME_UNKNOWN и распространяемую runtime cancellation. UnknownCommitOutcome обрабатывается раньше generic PublicationInfrastructureError. Далее SnapshotPublicError -> PythonNodeError(SnapshotNodeError(error=fault)); успешный ApplySnapshotOutput не создаётся. Это Snapshot ответственность, не дополнительный алгоритм registry. Интеграционное evidence отдельно; exact durable OperationCancelled engine transport отложен по owning решению, обычная cancellation/unknown семантика сохраняется.

## Актуальное решение 2026-11-21 — без legacy

ACCEPTED пользователем, источник — начало [общего H2-плана](interdomain-refusal-transport-h2.md). Заменяет прежнюю W/R compatibility policy и все требования old read roster ниже. Реализация, удаление данных и миграции не разрешены; H2 целиком ещё OPEN.

Одна целевая concrete модель TimeSnapshotApplyResult используется для новой записи и replay текущего Snapshot маршрута. Нет OldSnapshotApplyResult union, legacy readers/manifests, old→new adapters/fallback или двух независимых W/R наборов ради compatibility. Legacy roster/corpus больше не gate. Неподдерживаемый сохранённый root/format означает явную инфраструктурную несовместимость: не отсутствие terminal, не повод повторно вызвать handler/операцию.

Актуальная PatchSet boundary неизменна: SectionRegistry[TimeCommitRelationIssue](TimeSectionRefused), public refusal_model/diagnostic_types и exact local subset/output checks из §1–2. Единственная composition/snapshotTime связывает одну result_model: type[TimeSnapshotApplyResult] у Snapshot и Publication codec/store с одним текущим format/manifest/limits binding. Проверяется exact identity этой модели и согласованность domain D с registry; проверки включения W в отдельный old read roster больше нет. Admission roster Snapshot остаётся отдельным от domain D. Полные упрощённые Snapshot/Publication/store/node signatures предъявляют их владельцы; PatchSet не сохраняет прежнее требование apply[S,R] ради legacy.

Replay сохраняет concrete типы, значения, operation identity/category и diagnostics текущего результата без повторного handler/state read. Pack/Gameplay/Cancelled остаются отдельными актуальными kinds и автоматически не удаляются. Принятые IDs 31007/31139/31140/20150 неизменны; прежние 20124/20128/20131 не переназначаются; runtime TimeSectionRefused без ID.

Новый read_record_root_id API не требуется только ради legacy dispatch. Его необходимость пересматривается владельцами; обязательны strict expected root, full bounded decode, проверка budgets и ранее принятая граница configuration TypeError/ValueError против bytes/budget CanonicalEncodingError. Не копировать parser и не вводить trial decode/fallback. Exact текущая format/root pair и финальная упрощённая цепочка требуют общей сверки.

Статус: registry/composition proposal согласован с решением без legacy; остаток — final signatures/configuration/node output, текущая representation pair и encoding API review. Historical compatibility не является остаточным prerequisite.

## Принятые решения пользователя — 2026-11-21

**SUPERSEDED в части legacy:** прежние W/R policy, old readers/roster и обязательный отдельный root dispatch ниже заменены актуальным разделом «без legacy». IDs, ограничения budgets/ошибок и инфраструктурное положение Publication сохраняются.

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

Исторический proposal; назначения заменены принятыми IDs от 2026-11-21, а W/R/read-roster policy SUPERSEDED решением «без legacy». Таблица кандидатов и audit сохранены только как evidence того прохода, не актуальная карта IDs или construction requirements.

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

Полная output admission (PROPOSED, уточнение ревью 2026-11-21) принадлежит BoundSectionHandler: validate допускает только exact SectionAccepted или exact handler.refusal_model; apply — только exact SectionApplyReceipt или exact handler.refusal_model. Сначала проверяется ветвь/exact type, затем owning model_validate(..., strict=True); subclasses без отдельного согласования не принимаются. Receipt из validate, Accepted из apply, None/чужой объект и structurally corrupted output дают SectionHandlerContractError. Accepted и receipt проходят существующие structural model invariants; refusal — описанные local diagnostic checks, затем перенос в composition carrier. Это не проверка receipt provenance: соответствие receipt входной section/assigned targets и C2 rollback остаются у Snapshot. Ошибки проверки после return сохраняют cause; исключения/cancellation, возникшие внутри await handler, этой проверкой не перехватываются.

Предлагаемый application/patch/errors.py::SectionHandlerContractError(RuntimeError) означает нарушение output contract, не business refusal. Оборачиваются с cause только ошибки проверки возвращённого output; infrastructure exceptions/cancellation самого handler не перехватываются. Mapping этой ошибки во внешнюю Snapshot fault boundary согласует Snapshot; durable business refusal из неё создавать нельзя.

ACCEPTED: TimeSectionRefused содержит только общие structural invariants; Time validator перед return проверяет общий request, codes/order/category. Инварианты отдельного TimeCommitRelationIssue остаются у модели. Registry/Snapshot не повторяют Time predicates. Validator exact API принимается в Time H2-T.

## 3. Единая локальная composition

Принято пользователем 2026-11-21: composition/snapshotTime/contracts.py — TimeSnapshotApplyResult(SnapshotApplyResult[TimeCommitRelationIssue]); composition/snapshotTime/binding.py — TimeSnapshotBinding и builder ниже. Прежнее предложение PatchSet composition/timeSnapshot заменено этим размещением. Владелец сборки — application composition root, не generic PatchSet и не DAG-нода.

**Принято пользователем 2026-11-21 — узкий builder:** TimeSnapshotBinding хранит один owning publication_binding: PublicationResultBinding[TimeSnapshotApplyResult] из application/publication/contracts/resultBinding.py. Не объявлять независимые result_model/manifest/format/limits/record_model поля. Refusal фиксирован локальной composition: TimeSectionRefused, не второй carrier и не пользовательская настройка. Exact builder:

```python
def build_time_snapshot_binding(
    *, publication_binding: PublicationResultBinding[TimeSnapshotApplyResult],
) -> TimeSnapshotBinding: ...
```

TimeSnapshotBinding — frozen application dataclass; __post_init__ проверяет exact publication_binding.result_model is TimeSnapshotApplyResult, наличие принятой declaration root20150 и совместимость domain diagnostic roster с TimeCommitRelationIssue через публичные данные owning binding. Собственный constructor PublicationResultBinding отвечает за schema/snapshot_format_version/manifest/record_model/limits; TimeSnapshotBinding не дублирует эти predicates и не вызывает чужой __post_init__ вручную. Builder создаёт только TimeSnapshotBinding, не принимает registry/services/store/ledger/staging/leases и не выдаёт runtime/service/node bindings. Некорректный тип — TypeError, несовместимые значения/identity — ValueError, до IO. Exact имя поля версии берётся у Publication: snapshot_format_version, не предварительное format_version из Snapshot proposal. Финальный owning validation API остаётся отдельным H2-уточнением; private introspection и выдуманный unchecked admission запрещены.

Application composition root создаёт registry с TimeSectionRefused и связывает экземпляры через публичные read-only properties; новая универсальная factory не требуется. SnapshotApplyBinding[TimeAdvanceSection, TimeCommitRelationIssue, TimeSnapshotApplyResult] получает section_adapter закрытой Time секции, тот же TimeSectionRefused и publication_binding.result_model. Это required owning view Snapshot, а не второй независимо настраиваемый result. Snapshot constructor сверяет registry.refusal_model is binding.refusal_model, exact D и operations.result_binding.result_model is binding.result_model. Publication codec/store получают тот же publication_binding object; store/ledger/staging consistency и record_model identity, включая leases.record_model, проверяют owning constructors по [Publication H2, актуальным signatures](publication-h2-persistence-proposed.md#актуальная-упрощённая-цепочка--2026-11-21-proposed-signatures). Manifest/limits нигде не выбираются повторно. Принято разделение ответственности; точные owning signatures и сквозное runtime evidence остаются отдельными H2 gates.

Уточнение остаётся в отложенном H2 и не расширяет текущую независимую реализацию: подключение write_changes, подготовка входов и production composition rollout сюда не добавляются. Порядок DAG и доменная семантика не меняются.

D=TimeCommitRelationIssue; Snapshot admission roster добавляется только result model. В core нет Time imports. Builder не создаёт storage/services, не вызывает IO/domain pipelines и не выбирает следующий runtime шаг. Поля каждого owning binding и их validation не копируются в новый универсальный configuration POJO.

Canonical roots: сохраняется concrete Snapshot result с diagnostics, а не локальный SectionRefused. Поэтому TimeSectionRefused не получает ID только ради registration/return handler. Регистрируются реально сериализуемый result root и достижимая closure; internal bindings/validators/exceptions не получают IDs. IDs 31007/31139/31140/20150 приняты, existing IDs не переназначаются. Полный manifest/current format pair и runtime evidence остаются отдельными gates.

### Матрица ответственности и приёмки классов

Пути относительно backend/app. Для объединённой строки критерий применяется к каждому классу; зависимости только указанные owning types/contracts. Общая последовательность: construction до IO; section admission -> owning handler -> output admission -> Snapshot обработка. Refusal lifecycle после confirmed rollback остаётся в [Snapshot H2, актуальной цепочке](snapshot-refusal-transport-h2.md); новые стадии DAG не добавляются.

| Класс / место | Ответственность, зависимости/эффекты | Критерий приёмки / нарушение |
|---|---|---|
| SectionRefused; SectionAccepted; SectionApplyReceipt — dataModel/patch/results/sectionResult.py | Immutable owning records, только типы полей и structural invariants; без IO | Refusal непустой, Accepted пустой, receipt сохраняет существующие constraints; отказ при Time predicates, IO или утверждении durable commit |
| DomainSectionHandler — application/patch/contracts/sectionHandler.py | ABC semantic validate/apply, owning section/context/result types; эффекты concrete handler определяет owning план | Exact S/D/refusal_model согласованы; отказ при orchestration чужого public pipeline |
| SectionContract — тот же модуль | Existing key/model/version/schema binding, не diagnostic registry | Существующие C1 invariants сохранены; отказ при переносе diagnostic semantics в contract |
| SectionCodec — application/patch/contracts/sectionCodec.py | Existing pure representation, зависит от SectionContract | C1 exact contract identity сохранена; отказ при вызове semantic handler/IO |
| SectionRegistry — application/patch/registry/sectionRegistry.py | Construction subset checks и dispatch; in-memory registration bindings | Проверки до публикации binding, публичный roster производен от модели; отказ при независимом roster/Time logic |
| BoundSectionHandler — тот же модуль | Section/output admission и вызов зарегистрированного handler; эффекты только делегированного owning вызова | Все ветви §2 проверены; отказ при незаметном subtype slicing, C2 provenance вместо Snapshot или перехвате cancellation |
| SectionHandlerContractError — application/patch/errors.py | Execution exception с cause, без нового diagnostic DTO/IO | Только output-contract failures; отказ при переводе business conflict в exception либо durable refusal из неё |
| TimeSnapshotApplyResult — composition/snapshotTime/contracts.py | Named specialization owning Snapshot result; без новых полей и IO | Exact concrete root20150 и закрытый diagnostic набор; отказ при копии полей/Time semantics |
| TimeSnapshotBinding — composition/snapshotTime/binding.py | Frozen ссылка на owning PublicationResultBinding, pure construction checks §3 | Нет независимых manifest/result/limits; mismatch отвергается до IO |
| build_time_snapshot_binding — тот же модуль, функция | Создание проверенного TimeSnapshotBinding; без запуска сервисов | Делегирует construction checks; отказ при storage/registration side effects или pipeline calls |
| TimeCommitRelationIssue; TimeSectionRefused; TimeRefusalValidator — owning Time модули из time-domain.md, H2-T | Issue operands/invariants, structural carrier, отдельно set semantics | Reuse owning POJO; exact API и проверки — [Time H2](time-domain.md); отказ при копировании predicates в registry/Snapshot |
| SnapshotApplyBinding; WorldSnapshotService — owning paths в Snapshot H2 | Binding consistency, apply/rollback/result; existing accepted transaction effects | [Snapshot H2](snapshot-refusal-transport-h2.md), актуальные signatures: exact model и registry D, C2 и rollback у Snapshot; refusal не означает commit |
| PublicationResultBinding; StoredTerminalCodec; IOperationStore/SqliteOperationStore; OperationRecord — owning paths в Publication H2 | Configuration; pure representation; инфраструктурный persistence; immutable operation record соответственно | [Publication H2](publication-h2-persistence-proposed.md), актуальная цепочка: одна result identity/format/manifest/limits, explicit unknown-format failure; отказ при fallback или повторном handler |

SectionValidation — alias union, не отдельный POJO. Дополнительные CRUD данных/настроек C/R/U/D для этого carrier-среза N/A; registry registration — construction API, не новая предметная CRUD операция. Внешние owning проверки в последних трёх строках не объявляются закрытыми этим планом: их exact contracts/evidence принимает координатор с владельцами.

## 4. Переходы и внешние условия

### Сводка signatures по поручению пользователя — 2026-11-21

Нормализация обозначений только для сверки: S=TimeAdvanceSection, D=TimeCommitRelationIssue, T=TimeSnapshotApplyResult. Publication называет свой единственный current-result параметр R; R=T здесь, это не исторический read union. Источники: актуальные верхние разделы [Snapshot H2](snapshot-refusal-transport-h2.md) и [Publication H2](publication-h2-persistence-proposed.md). Все signatures TARGET/PROPOSED, не evidence runtime.

| Boundary / owning путь относительно backend/app | Exact signature / mapping | Сверка |
|---|---|---|
| application/patch/contracts/sectionHandler.py | DomainSectionHandler[S,D].validate(section:S, context:SnapshotValidationContext) -> SectionAccepted \| SectionRefused[D], async; apply(section:S, context:SnapshotApplyContext) -> SectionApplyReceipt \| SectionRefused[D], async | Local refusal_model=TimeSectionRefused; exact output admission §2 |
| application/patch/registry/sectionRegistry.py | SectionRegistry[D](refusal_model:type[SectionRefused[D]]); require(key:SectionKey)/resolve(section:DomainSection) -> BoundSectionHandler[D]; bound validate/apply signatures §1 | D совпадает; carrier не становится Snapshot result |
| application/worldSnapshot/contracts/applyBinding.py | SnapshotApplyBinding[S,D,T]: section_adapter:TypeAdapter[S], refusal_model:type[SectionRefused[D]], result_model:type[T] | T и D согласованы с registry; S привязан instance |
| application/worldSnapshot/service/worldSnapshotService.py | WorldSnapshotService[S,D,T].__init__(registry:SectionRegistry[D], world:IWorldPublicationStore, players:IPlayerPublicationStore, history:ISnapshotHistoryStore, *, binding:SnapshotApplyBinding[S,D,T], operations:IOperationStore[T]); async apply(self, patch_set:PatchSet[S])->T | Один public apply; operations — узкий инфраструктурный store, не ledger |
| application/worldSnapshot/contracts/applyPort.py | IWorldSnapshotApply[S,T].apply(self, patch_set:PatchSet[S])->T, async | Совпадает с Publication proposal после R=T |
| application/publication/contracts/resultBinding.py | PublicationResultBinding[T](result_model:type[T], snapshot_format_version:FormatVersion, manifest:CanonicalSchemaManifest, record_model:type[OperationRecord[T]], limits:DecodeLimits) | Имя snapshot_format_version сверено; нет readers/W-R |
| application/publication/contracts/operationStore.py | read(operation_id:EntityUid)->OperationRecord[T]\|None; claim_publication(kind:OperationKind, operation_id:EntityUid, world_uid:EntityUid, preparation_fingerprint:RevisionHex, request_fingerprint:RevisionHex)->OperationClaim[T]; record_refusal(claim:PublicationOwner,outcome:T)->None; record_terminal(scope:CommitScope,outcome:T\|PackActivationResult\|GameplayStarted\|OperationCancelled)->None — все async | T сохраняется во вложенных claim/terminal; foreign operation kind не выдаётся как Snapshot T |
| db/repositories/sqlite/snapshotCore/operations/terminalCodec.py | StoredTerminalCodec[T](*,binding:PublicationResultBinding[T]); encode(outcome:T\|PackActivationResult\|GameplayStarted\|OperationCancelled)->PublicationOutcomeRow; decode(row:PublicationOutcomeRow)->тот же union; result_binding read-only | Kind выбирает exact expected model; unsupported root/format — infrastructure failure, не None/retry |
| dataModel/engine/nodes/snapshot/contracts.py | ApplySnapshotInput[S].patch_set:PatchSet[S] -> await IWorldSnapshotApply[S,T].apply -> ApplySnapshotOutput[T].value:T | Concrete TimeApplySnapshotInput/TimeApplySnapshotOutput в composition/snapshotTime/contracts.py; replay тот же T |

Порядок сохраняется: handler refusal -> registry output admission -> confirmed rollback -> construction T -> record_refusal(claim,T) -> confirmed persistence -> return T. Replay существующего текущего terminal возвращает T без handler/state reads. Section receipt идёт через Snapshot C2; не принимается за commit. Codec/store result_binding is один owning configuration object; operations.record_model is result_binding.record_model. Exact record_model возвращается также leases/staging по Publication owning matrix; recover/cancel не добавляются в обычный apply.

**Результат локальной сверки:** type flow S/D/T, public apply, record_refusal/terminal codec и node output согласованы на уровне proposals. Не закрыты: (а) exact composition factory signature/return — наш builder принимает только publication_binding, актуальный Snapshot factory также проверяет runtime wiring registry/store/codec/ledger/staging/leases; нужно одно construction API; (б) mapping SectionHandlerContractError; (в) отдельный Snapshot/engine cancellation transport и freeze current format/root pair. Type flow PASS не означает приёмку всей boundary.

**Адресные запросы отправлены по явному поручению пользователя:** construction/factory — Between domain operations (2), thread 01a1f529-898c-7342-82f4-1e68983b3a9c; error mapping — snapshot, thread 01a1eeb1-392b-7a02-8aa3-c3fa11482b02. Ответы ожидаются; PatchSet не назначает Snapshot fault policy. Точные nested adapters/transaction invariants остаются owning Publication/Snapshot, не копируются в DAG и не считаются принятыми этой таблицей.

| Переход | Owning вывод |
|---|---|
| Time issue -> TimeSectionRefused | PASS узкого принятого разделения ответственности; exact Time validator API принимается отдельно |
| Handler -> bound registry -> composition refusal | PASS согласованности предложенного дизайна; generic signatures/output checks ещё PROPOSED, runtime не реализован |
| Registry -> Snapshot result | PASS совместимости предложений: один D, public registry metadata, reuse refusal; OPEN подтверждение Snapshot construction/fault mapping |
| Snapshot result -> terminal/store/claim | OPEN: Publication обязан предъявить exact generic/closed nested containers и допустимый internal infrastructure port; одного codec недостаточно |
| Terminal -> exact replay -> DAG | OPEN: exact текущая result model/format и public result mapping; legacy roots/read compatibility не требуются. Повторный handler/state read или потеря diagnostics запрещены |

Snapshot переносит category/diagnostics после подтверждённого rollback. Publication codec обязан проверять exact root, closure, version/kind/category/operation/row-body integrity, foreign/missing types; handlers и Time semantics не вызываются. Internal terminal reads остаются внутри apply_snapshot/Snapshot.apply, read_world вне scope. Это не разрешение foreign public pipeline call: exact port и nested trace ещё требуют общей приёмки.

Source compatibility breaking: существующие SectionRegistry(), DomainSectionHandler[S], прямой SectionRefused(...) и consumers/test fixtures требуют явного binding. Не вводить открытый default для обхода миграции. Поддержка прежних Snapshot terminal representations не требуется по решению «без legacy»; неизвестный root/format — явная инфраструктурная несовместимость. БД не обследованы, отсутствие данных не утверждается, удаление/миграции не разрешены.

Проверка DAG/POJO узкого предложения: carrier только данные, handler owning semantics, registry только admission/dispatch, composition только construction; без новых CRUD/IO, hidden public pipelines, изменения порядка и зеркальных operands. Полная приёмка цепочки OPEN до внешних условий и решения пользователя. Код/миграции/тесты в этом проходе не выполнялись.
