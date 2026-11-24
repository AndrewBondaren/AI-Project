# Snapshot apply: admission → fingerprint → claim

## Статус и границы — 2026-11-24

### Итоговая координаторская приёмка — PASS ограниченного среза

**Последующая enum-дельта закрыта — PASS основной координаторской сверки.** Независимо проверены actual producer field/classifier и Snapshot presentation mapping: owning enum, identity dispatch, .value только к existing ErrorType adapter, narrow ValidationError с cause, без второго allowlist/raw fallback. Координатор независимо выполнил 25 admission/tagged-path tests на 2.13.4 — OK. Owner evidence 25 OK на pinned 2.14.2 учитывается отдельно, не является независимым pinned прогоном. Typed Output → Input дельта закрыта; прежний admission PASS и границы OUT неизменны. Эта запись заменяет ожидание узкого закрытия в записях ниже.

**Consumer evidence enum-дельты получено:** Snapshot выполнил dispatch по owning enum и преобразование .value к existing Pydantic ErrorType только на presentation boundary; narrow conversion failure сохраняет cause как infrastructure fault. Отдельного allowlist/enum/string fallback нет. По отчёту владельца 25 targeted admission/tagged-path tests PASS на 2.13.4 и отдельно 25 PASS на pinned 2.14.2 с проверенными import paths/version; scoped Pyright — 0. Покрыты весь owning roster, raw-string bypass negatives и прежние mixed JSON/root loc. Это owner evidence последующей дельты, передано основному координатору для узкого закрытия; независимый повторный прогон здесь не заявляется. Ниже ожидание consumer evidence историческое и заменено этой записью.

**Последующая адресная дельта 2026-11-24:** по прямому требованию пользователя PatchSet заменил строковый PatchSetStructuralFailure.error_type на owning PatchSetStructuralErrorKind(StrEnum). JSON значения и roster сохраняются, преобразование Pydantic string → enum выполняет classifier; неизвестный код остаётся classification fault с cause. Прежний PASS сохраняется для неизменных частей, но не выдаётся за проверку этой последующей дельты. PatchSet сообщил 7 admission tests/enum JSON/адресный Pyright PASS; Snapshot назначена узкая consumer/test сверка enum mapping, mixed JSON и typing. Второй enum/allowlist и raw-string fallback не вводятся. Ожидается consumer evidence изменённой границы.

Основной координатор Between domain operations подтвердил PASS реализованного admission → fingerprint → existing claim и затронутых C0 контрактов. Приняты internal seam, typed admission/public diagnostics, C0 JSON/strict/path behavior. Эта запись имеет приоритет над историческими OPEN и ожиданием реализации ниже в пределах перечисленного среза.

Evidence разделено по источникам:

- Независимая проверка основного координатора: actual code и Output → Input review; 17 admission tests и 58 errorContracts tests PASS на Pydantic 2.13.4. Подтверждены owning границы, direct facts reuse, closed fault roster/None identities, prepared-order до hash, отдельный catch fingerprint без охвата claim, отсутствие partial public apply, нормативный public export.
- Проверка владельца Snapshot на declared pin: 64 targeted tests PASS на Pydantic 2.14.2 / pydantic-core 2.50.2 через isolated pip-target. Версии и actual import paths проверены assert в том же Python процессе. C0 JSON/carrier/subtype/rebuild/strict/tagged paths, nested fault union/mixed diagnostics и Snapshot/PatchSet admission покрыты. Команда и подробности в [owning статусе](snapshot-public-methods-contract.md), раздел «Pinned regression закрыта 2026-11-24». Общая .venv и pins не менялись. Это owner evidence, не независимый pinned прогон и не clean full requirements build.

Основной координатор принял это pinned evidence как закрытие targeted pin-version coverage OPEN. Новых concerns нет; повторная тяжёлая регрессия не требуется. Прежние owner 257 snapshotCore и другие наборы не приписываются независимому проверяющему.

Не приняты этим verdict: полный публичный apply, durable transaction/SQLite integration, DAG composition, production readiness и ARCH-0. Они не являются prerequisites данного ограниченного PASS; выполнение остальных стыков продолжается отдельными срезами.

**Уточнение пользователя: решение согласовано; детализация принадлежит доменам.** Распределение ответственности, admission → fingerprint → claim, неперсистентный fault, mixed diagnostics и делегирование реализации не имеют общего статуса PROPOSED и повторно не согласуются. Конкретные reason classes, mapping, structural-only adapter и синхронизацию owning нормативных документов готовят владельцы. Координатор согласует междоменные Output → Input, зависимости поставки и доказательства совместимости, не проектирует внутренние классы за владельцев. Упоминания proposed ниже относятся лишь к ещё не зафиксированным деталям реализации контракта. OPEN общей сверки означает незавершённые конкретные стыки, а не отмену принятого решения.

Порядок закрытия остатков: PatchSet предъявляет точный owning выход admission и structural facts → Snapshot подтверждает потребление без потери loc/order/cause/indices и выполняет своё отображение → владельцы синхронизируют нормативные формулировки в рамках разрешённого скоупа → координатор сверяет фактическое соответствие границы. Внутренние названия и размещение классов не требуют отдельного пользовательского выбора, пока не меняют согласованный контракт. Разногласие эскалируется только с конкретным несовместимым Output → Input или изменением принятого поведения.

### Результат общей сверки: OPEN до точных дельт

**Повторная узкая сверка основного координатора — PASS документального Output → Input.** Подтверждены root-relative facts, local revalidation fault, direct compatibility reuse и mapper на исходном месте. Runtime и нормативная синхронизация этим не объявлены выполненными. Shared C0-правку выполняет существующий чат Snapshot в пределах делегированного среза после исключения параллельного владения; архитектурное владение остаётся error-contracts C0. Размещение: dataModel/fields/checkedPath.py и existing jsonValidation/resolution/wireIssues.py. Exact unique discriminator tag/class-name branch; unknown/ambiguous — existing unresolved handling. Не переписывать исходный loc, не выдавать extra key за FieldSegment; existing VariantSegment остаётся в typed path, tag отсутствует только в rendered wire path. Callable-discriminator framework вне доказанного supported schema не вводить. C0 roster и nested/extra-key/ambiguity regression обязательны. Это актуализирует ниже первоначальный OPEN и ожидание назначения исполнителя.

**Стыки producer/consumer сведены 2026-11-24:** Snapshot подтвердил последнюю редакцию [PatchSet Output](patch-set-admission-output.md) и синхронизировал [public fault schema](snapshot-public-methods-contract.md). Root-relative loc только из root revalidation, без prefix; локальная section validation после root success не становится input shape. Public roster directly reuse PatchSetCompatibilityIssue с owning Literal codes и готовым ordered supported_versions; Snapshot зеркала/wrapper отозваны, operands/indices не меняются. Эти owning редакции имеют приоритет над ранними вариантами mapping ниже.

Оставшая shared dependency — CheckedPath.from_pydantic_loc / _resolve_loc общего error-contracts (C0-4/C0-8): declared discriminator tag должен давать existing VariantSegment, а не wire field. Пример sections/2/payload/cat/age → wire sections/2/payload/age; typed path сохраняет IndexSegment и VariantSegment. Snapshot resolver не дублирует. Проверить также extra-key под tagged union и existing core/model_identity/import_issues/resolve_issues/typing consumers. Назначение владельца минимальной shared реализации передано основному координатору; runtime исправление и tests пока не выполнены.

**Owning детализация PatchSet получена:** [точный admission Output](patch-set-admission-output.md) заменяет ранние варианты ниже с Python class objects и ValidationError внутри reasons. Reasons теперь immutable typed facts; исходное исключение остаётся только cause. Предъявленный Input единственного Snapshot mapper — PatchSetStructuralFailure(error_type, loc, message), не reconstructed ValidationError. Consumer compatibility, сохранение operands/indices и public mapping сверяет Snapshot; до его ответа полная Output → Input совместимость не заявлена.

Основной координатор прочитал план и подтвердил направление: owning predicates PatchSet, единственный mapper Snapshot, отсутствие IO до claim, prepared-order → request fingerprint → existing claim, отсутствие record_refusal до claim и запрет partial public apply. Полного разрешающего PASS зависимой реализации пока нет. До кода export/fault требуется предъявить и согласовать:

1. Нормативный public stable facts contract PatchSetInvariantViolation: docs/tz_patch_system.md ещё обозначает его Internal; actual docstring тоже Internal. Не переносить модуль и не создавать зеркало. Сначала предъявить точную нормативную дельту; разрешение на правки ТЗ не подразумевается автоматически.
2. Приоритетную синхронизацию snapshot-public-methods-contract.md: ADMISSION_REFUSED, mixed closed roster, JSON serialization всех concrete details, validators обеих None identities. Две противоречащие public schema недопустимы.
3. Полную таблицу concrete runtime reason → public diagnostic: exact classes, operands, codes и исходные indices; unknown section/model/version не теряют section_index, фиктивные paths запрещены. Unknown ctx.error не считается structural автоматически.
4. Exact согласованный способ передать structural-only subset единственному mapper с сохранением loc/order/cause. Полный mixed ValidationError нельзя передавать прежнему shape mapper.

Владельцы сначала готовят эти документальные deliverables; после них координатор повторяет узкую сверку. Неизменные H2/C2 и whole ARCH-0/production не переоткрываются. Нижнее делегирование реализации сохраняется с этим обязательным gate.

Пользователь поручил подробно зафиксировать сведённое предложение и делегировать реализацию доменам. Это разрешение на описанный срез, не на полный public apply. Владельцы Snapshot/PatchSet/Publication дали обратную связь; основной координатор Between domain operations (01a1ef35-3287-7a12-89e2-76273eaa043d) выполняет обязательную общую сверку перед зависимой реализацией. Не считать отправку задания PASS. При конфликте с ТЗ или незакрытом обязательном критерии зависимый шаг останавливается, контракт не меняется молча.

Источники: [atomic trace](snapshot-public-apply-atomic-trace.md), [public methods](snapshot-public-methods-contract.md), [PatchSet H2](patch-set-refusal-transport-h2.md), [Snapshot H2](snapshot-refusal-transport-h2.md), [Publication H2](publication-h2-persistence-proposed.md); docs/tz_patch_system.md и docs/tz_world_snapshot.md. Actual источники: PatchSet.coherent_request, PatchSetInvariants, PatchSetCodec, SectionRegistry, WorldSnapshotService._claim_publication, IOperationStore. Перед кодом владельцы читают применимые ТЗ целиком по implement-plan и сверяют актуальные файлы.

IN: неперсистентный admission, owning errors, configuration checks, request hash и передача в existing claim. OUT: полный apply, transaction/source/assigned refs/handoff, остальные четыре стыка atomic trace, новые DAG nodes/IDs, producers, Pack completion, rollout, SQL/migrations, новые terminal IDs, изменение H2/H3/C2/D1–D7. Backend не запускать; commit/push запрещены.

## 1. Распределение ответственности

| Владелец / класс | Ответственность и зависимости | Признак отказа при приёмке |
|---|---|---|
| PatchSet / PatchSet и PatchSetInvariants | Existing core predicates и prepared-order; данные и pure checks | Повторная реализация predicate в Snapshot, повторный assemble |
| PatchSet / PatchSetCodec | Configuration, request admission, canonical encoding/fingerprint; owning registry/codecs | IO/claim/handlers, смешение encoder faults с ожидаемыми input errors |
| PatchSet / SectionRegistry | Exact key/model/version registration admission; public metadata | Private introspection consumer, второй независимый roster |
| PatchSet / typed admission carriers | Runtime перенос причины и исходных invariant facts | Mirror diagnostics, Python classes/ValidationError в публичном wire |
| Snapshot / SnapshotPublicInputValidation | Единственный structural mapper | Превращение произвольного model ValueError или relations в shape errors |
| Snapshot / SnapshotRequestValidator | Owning admission API → prepared-order → public fault/checked request | Hash/IO/claim/domain semantics, потеря исходных индексов |
| Snapshot / WorldSnapshotService | Один request codec, соединение validate → hash → existing claim | Повторный mapping fault, record_refusal до claim, synthetic hash |
| Publication / IOperationStore и existing implementation | Claim, immutable identity, busy/cancel/exact replay | Новый claim для admission refusal, скрытый retry/domain execution |

Это внутренняя реализация одной операции Snapshot. Прямой публичный caller остаётся согласованным DAG binding через IWorldSnapshotApply[S,T]; никакие foreign public pipelines из admission не вызываются. Чистые PatchSet helpers/codecs переиспользуются по существующему разделению C1. Полный runtime caller этим срезом не объявляется готовым.

## 2. PatchSet: proposed exact методы

```python
PatchSetCodec[S].validate_configuration(self) -> None
PatchSetCodec[S].validate_request(self, request: PatchSet[S]) -> PatchSet[S]
SectionRegistry[D].section_models  # read-only frozenset[type[DomainSection]]
```

Codec.__post_init__ вызывает validate_configuration. Проверяется named closed concrete PatchSet model, ordered tuple sections с closed concrete native classes и subset exact models в registry. Registry extras допустимы, но не расширяют request union. Registry уже запрещает повторные key/model registrations. Construction errors: TypeError для недопустимой формы модели, ValueError для несовместимой регистрации. Не public input faults. Snapshot не вызывает чужой __post_init__ и не копирует model introspection.

validate_request: exact request model → strict revalidation (check_core выполняется моделью) → supported request version → registry admission секций в исходном порядке. Independent checks агрегируются существующим ValidatorAggregationHelper; зависимые проверки пропускаются только при нарушенном предусловии. Ни encoding, ни prepared-order в этот метод не добавляются. encode переиспользует validate_request; защитная повторная revalidation допустима, predicates остаются единственными.

### Typed errors и сохранение core facts

Proposed dataModel/patch/validation/PatchSetCoreInvariantError(ValueError) содержит исходный tuple[PatchSetInvariantViolation,...]. PatchSet.coherent_request поднимает его вместо ValueError(tuple(details)), не меняя predicates. Owning adapter извлекает exact carrier из structured ValidationError ctx.error; строка исключения не разбирается, check_core повторно не запускается. Доступ к Pydantic структуре изолирован в одном PatchSet adapter и покрывается regression test установленной версии.

Proposed application/patch error boundary: PatchSetAdmissionError(Exception), непустой ordered reasons tuple закрытых runtime причин:

| Причина | Поля |
|---|---|
| Request model mismatch | expected_model:type[BaseModel], actual_model:type |
| Unsupported request version | actual_version:FormatVersion, supported_versions:frozenset[FormatVersion] |
| Unknown section key | section_index:Annotated[StrictInt,Field(ge=0)], section_key:SectionKey |
| Section model mismatch | section_index, section_key, expected_model:type[DomainSection], actual_model:type |
| Unsupported section version | section_index, section_key, actual_version, supported_versions |
| Confirmed structural validation | Только соответствующие structural entries ValidationError; без relation entries |
| Core relation | Existing PatchSetInvariantViolation с исходными details и индексами |

Имена concrete runtime reason classes и reuse существующих типов предъявляет PatchSet перед записью кода; таблица задаёт семантику, не разрешает дублировать уже существующие POJO. Registry формирует typed local причины в owning check sites; codec добавляет request section index. Нельзя повторять predicates ради классификации в Snapshot. Неизвестный validator exception не считается structural автоматически. Сохраняются все доступные независимые причины и их порядок; нельзя обещать model after-validator execution, если structural prerequisites не прошли.

Prepared-order возвращает existing tuple violations; Snapshot использует его напрямую. В публичный fault экспортируются PatchSetInvariantViolation и закрытый PatchSetInvariantDetails как immutable diagnostic facts (владелец поддержал изменение internal → public). Модуль не переносится, зеркальная модель не создаётся. Индексы section/dependency/related/patch/player относятся к исходному request. Canonical IDs/terminal manifest не добавляются автоматически.

Encoder exception, invalid encoder output и нарушение после успешного admission не превращаются в PatchSetAdmissionError. Сохраняется причина infrastructure/contract fault.

## 3. Snapshot: adapter и неперсистентный transport

Proposed application/worldSnapshot/validation/snapshotRequestValidator.py:

```python
SnapshotRequestValidator[S](codec: PatchSetCodec[S])
SnapshotRequestValidator[S].validate(request: PatchSet[S]) -> PatchSet[S]
```

Модель/registry берутся только из codec. Validator вызывает validate_request, затем check_prepared_order. Узкий catch только объявленных owning errors. Он один раз переводит ordered reasons в public diagnostics; ни service, ни DAG этот mapping не повторяют.

Proposed SnapshotPublicInputValidation.map_structural(error: ValidationError, *, model: type[BaseModel]) -> tuple[JsonFieldError | WireShapeIssue,...] остаётся единственным structural mapper. Принимает только подтверждённые structural entries. Отдельно проверить reuse актуального owning mapper и способы безопасного выделения entries без потери адресов/cause. Class objects, ValidationError и internal exceptions наружу не выходят. Неверный concrete request type отображается в existing WireShapeIssue по owning schema, без вымышленного поля.

Используется один proposed application/worldSnapshot/errors.py::SnapshotPublicError(fault:SnapshotPublicFault), не второй exception. Proposed модель dataModel/worldSnapshot/errors/publicFault.py сохраняет:

```python
operation: SnapshotPublicOperation
kind: SnapshotPublicFailureKind
operation_id: EntityUid | None
request_fingerprint: RevisionHex | None
input_issues: tuple[JsonFieldError | WireShapeIssue |
                   PatchSetInvariantViolation | SnapshotApplyRelationIssue, ...]
```

| kind | Ограничения |
|---|---|
| INVALID_INPUT | Непустые только shape diagnostics |
| ADMISSION_REFUSED (proposed новый kind) | Только APPLY; непустой mixed closed tuple, минимум одна relation/compatibility причина |
| Остальные existing kinds | Их прежний контракт, не расширять этим срезом |

Для обоих admission kinds operation_id=None и request_fingerprint=None. Это отказ входного вызова, не durable outcome. Даже валидный отдельный operation_id не предъявляется как claimed identity. Publication подтвердил отсутствие необходимости менять его контракт.

При mixed reasons выбирается ADMISSION_REFUSED, все shape/relation diagnostics сохраняются в исходном относительном порядке, без grouping/sorting. SnapshotApplyRelationIssue ограничивается admission-кодами UNSUPPORTED_REQUEST_FORMAT, SECTION_BINDING_MISMATCH, DEPENDENCY_MISMATCH; последний не заменяет подробные prepared-order facts. Точное соответствие каждой runtime reason этим существующим public diagnostics фиксирует Snapshot до зависимой реализации; при нехватке поля/точности не выдумывать путь. Public schema явно включает exported invariant facts. Не подменять declared typed transport Any/dict.

## 4. Composition и соединение с claim

В existing WorldSnapshotService добавляется один request_codec:PatchSetCodec[S]. Constructor проверяет request_codec.registry is registry. PatchSet-owned codec constructor отвечает за model/registry compatibility. Existing H2 result/diagnostic roster и publication_binding identity сохраняются независимо от registry extras. Нового SnapshotApplyBinding нет.

```python
checked = validator.validate(request)
request_fingerprint = request_codec.fingerprint(checked)
outcome = await self._claim_publication(
    checked.operation_id, checked.world_uid,
    checked.preparation_fingerprint, request_fingerprint,
)
```

До готовности полного apply разрешён внутренний admission→claim seam/test harness, но не публичный apply, возвращающий только terminal и бросающий NotImplemented на новой попытке. Exact размещение минимального seam определяет Snapshot без нового публичного контракта. Не имитировать успешную новую попытку.

Fingerprint fault обрабатывается отдельно от admission, с cause; не INVALID_INPUT и не business T. Claim сохраняет existing mapping: OperationBindingMismatchError → проверка carrier → T(REJECTED) без новой записи; busy → existing error; durable cancel → SnapshotOperationCancelledError; terminal T → exact replay. Общий catch ValueError вокруг всего пути запрещён (claim mismatch сам ValueError subtype).

Request fingerprint ДО claim включает request/section encoding. Actual dependency section fingerprints, handlers и source reads для исполнения — только после replay в новой попытке. Persistence integrity checks replay не отменяются. Не использовать preparation_fingerprint вместо request hash. Ни один pre-claim fault не вызывает record_refusal.

## 5. Делегирование и порядок поставки

1. Основной координатор: общая сверка этой ограниченной дельты, особенно public export invariant facts, новый kind, структурный mapper и допустимость pure helper calls. Не переоткрывать остальные принятые решения. При FAIL указать конкретную зависимую часть.
2. PatchSet: после общей сверки owning typed carriers/admission/configuration, registry public metadata, codec reuse, core facts и свои тесты. Предъявить exact reason classes/сигнатуры и доступные exports Snapshot. Не менять Snapshot/Publication.
3. Snapshot: после сверки контракта и готовности PatchSet exports — один mapper, fault schema, request validator, constructor identity и ограниченное соединение с existing claim. Не реализовывать остальные стадии apply. Не создавать временные PatchSet substitutes или дубликаты carriers.
4. Publication: проверить existing claim/replay compatibility и тесты; default без изменения runtime. Любая обнаруженная owning дельта сначала предъявляется координатору. Pack completion сюда не включается.
5. Координатор: свести actual Output→Input, независимую проверку и remaining gates. Зелёные локальные tests не означают public apply/ARCH-0 PASS.

Каждый исполнитель применяет implement-plan, читает AGENTS/rules/ТЗ, сверяет actual code и сохраняет чужие изменения. Все правки через apply_patch, diff перед отчётом. Если ТЗ противоречит дельте или exact carrier не замкнут — предъявить конкретное расхождение до зависимого кода, не дописывать контракт молча. Пользователь разрешил запись этого плана; правки owning ТЗ требуют явного согласования при необходимости.

## 6. Acceptance

### Адресное расширение shared regression — 2026-11-24

При consumer integration Snapshot сообщил JSON roundtrip fault nested JsonFieldError (tuple_type для path.segments/location.parts/wire_path). Основной координатор подтвердил, что устранение доказанного shared дефекта входит в разрешённый admission scope: исполнитель Snapshot после исключения parallel owner, архитектурный owner error-contracts C0-1/C0-2. Разрешены targeted fieldPathError.py и C0/Snapshot regression tests, без общего redesign. Причина пока не подтверждена: сначала minimal repro named concrete standalone и nested closed union, различить concrete handler(value) и base/generic kind.model_validate ветки. Сохранить strict Python tuples, exact CodeT/subtype, запрет base/parameterized construction и immutable paths. Запрещены strict=False, mirror, custom decoder и blanket list→tuple preprocessing. PASS scope не означает PASS реализации. Публичные гарантии не менять без предъявления конкретной дельты.

- Wrong exact request model, unsupported request/section versions, unknown key, wrong exact section model: различимые причины; никаких encoder/hash/claim effects после admission failure.
- Core facts сохраняют concrete details/индексы без повторного check_core и text parsing; неизвестный model ValueError не объявляется shape автоматически.
- Prepared-order до hash; отсутствующая/поздняя dependency сохраняет исходные section/dependency/related indices.
- Pure shape → INVALID_INPUT; pure relations и mixed shape-between-relations → ADMISSION_REFUSED; сохраняются все доступные diagnostics и их порядок. Identity обоих faults None.
- Codec fault после admission сохраняет cause, не input refusal; неверный encoder output не masked. Claim/record_refusal не вызываются.
- Extra registry entries допустимы при closed subset; missing registration, wrong exact model, чужой codec.registry отвергаются до IO; H2 roster/identity checks остаются.
- Успешный input даёт exact canonical fingerprint, переданный claim с теми же checked identity полями. Terminal replay не вызывает новую попытку, dependency hashes/handlers/source reads; обычное request encoding допустимо.
- Busy/mismatch/durable cancel/unknown сохраняют existing semantics. False terminal, synthetic hash и partial public apply запрещены.
- Positive/negative typing, scoped meaningful regression и публичная schema serialization для нового diagnostics roster. Публиковать фактические команды/результаты; не утверждать PASS до получения output. Полный apply/transaction тест здесь не заявляется.

Проверка CRUD всего Snapshot/Artifacts, runtime registration и production readiness не входят в локальный PASS; это существующие отдельные gates, не новые blockers независимого admission-среза. Изменение порядка или domain semantics означает отказ приёмки этого среза.
