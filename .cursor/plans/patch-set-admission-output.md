# PatchSet admission: owning Output для Snapshot

## Actual producer readiness — 2026-11-24

Реализованы validate_configuration/__post_init__/validate_request и encode reuse в PatchSetCodec; SectionRegistry.section_models и admission_issues(section, *, section_index); closed admissionReasons, PatchSetAdmissionError, PatchSetValidationClassificationError; root classifier и PatchSetCoreInvariantError с исходными facts. Нормативная internal→public дельта синхронизирована в tz_patch_system.md и docstring. Configuration использует named exact models и registered subset: старые consumers с непосредственным PatchSet[S] должны перейти на named specialization. Snapshot/Publication и shared CheckedPath не менялись.

Команда `python -B -m unittest tests.snapshotCore.contracts.test_patch_admission tests.snapshotCore.contracts.test_section_h2 tests.lifecycle.test_patch_transport tests.snapshotCore.contracts.test_patch_assembly tests.snapshotCore.contracts.test_patch_invariants` из backend: 26 PASS. Адресный Pyright пяти изменённых компонентов: 0 errors/warnings. Дополнительно закрыт review P2 ModelContractChecks: сравнивается decorator.info, тест смены mode той же функции отвергает configuration. Это producer readiness, не полная regression/consumer/public apply приёмка. Broad consumer migration и Snapshot mapper/claim wiring проверяют владельцы отдельно.

2026-11-24. Детализация принятого admission → fingerprint → claim. Код не изменён. Этот документ заменяет предыдущие варианты с ValidationError/class objects внутри агрегируемых reasons. Snapshot подтвердил Input PatchSetStructuralFailure для единственного structural mapper. Направление операции не переоткрывается.

## Уточнение owning Output: root loc и public reuse — 2026-11-24

### Единственный источник structural facts

`PatchSetModelValidationErrors.classify` вызывается исключительно для ValidationError непосредственного `codec.request_model.model_validate(request, strict=True)` в validate_request. Его loc уже относится к корневому request. Никакой prefix не добавляется: сохраняются исходные segments, section/patch indices и Pydantic union tags, включая повторяющиеся имена. Пустой loc остаётся пустым. Core carrier разрешён только на этой boundary и при loc=(); во вложенной ветви такой carrier даёт classification fault. Нельзя определять scope по строковому началу loc: поле секции также может называться sections.

После успешной revalidation полного request вызовы registry.resolve_codec и защитная model_validate секции не являются вторым источником structural input facts. ValidationError в них означает нарушение уже установленного validation contract (например, недетерминированный validator или изменение конфигурации); ошибка сохраняется как cause infrastructure/contract fault. Её НЕ передают classify/map_structural и НЕ оборачивают PatchSetAdmissionError. Таким образом в принятом маршруте prefix ('sections', i) не добавляется ни разу, двойной prefix невозможен. Локальные ValidationError из BoundSectionCodec во время fingerprint также остаются execution faults.

Unknown key/model/version — отдельные compatibility facts, а не ValidationError: codec назначает section_index ровно один раз из enumerate(checked.sections), registry отвечает за локальный predicate. Прямой caller registry без request не получает фиктивного root loc. Поддержка самостоятельной local-section structural admission с восстановлением отсутствующих outer union tags НЕ вводится этим срезом. Если потребуется такой маршрут, ему нужен отдельный явный scope API; объединять его с текущим classify по эвристике запрещено.

Обязательные regression cases: root nested union loc с sections/index/branch/patches/index/branch/field сохраняется byte-for-byte по segments; root loc=() не превращается в sections/index; после успешной root validation локально падающий model validator даёт contract fault, не input reason; unknown section key/model/version сохраняют исходный index.

### Четыре compatibility facts используются публично напрямую

PatchSetRequestVersionUnsupported, PatchSetSectionKeyUnknown, PatchSetSectionModelMismatch, PatchSetSectionVersionUnsupported становятся публичными immutable compatibility facts PatchSet для неперсистентного Snapshot fault. Семантических препятствий в operands нет: ModelIdentity — уже immutable JSON-compatible record; actual_type_name — inert string; остальные поля — версии, ключи и индексы. Вторые Snapshot* details с теми же operands не нужны.

Owning delta: каждый из четырёх классов получает обязательный Literal code соответственно `patch_set.admission.request_version_unsupported`, `patch_set.admission.section_key_unknown`, `patch_set.admission.section_model_mismatch`, `patch_set.admission.section_version_unsupported`. Новый enum не нужен. Общий plain alias PatchSetCompatibilityIssue объединяет эти четыре exact класса; Snapshot может включить его directly в input_issues с discriminated annotation по code, без wrapper/details и без переименования. Правила категории/operation/binding остаются у Snapshot. PatchSetRequestModelMismatch и PatchSetStructuralFailure остаются internal mapper inputs.

В обоих version facts supported_versions уточняется на `tuple[FormatVersion, ...]` с min_length=1, уникальностью и ascending order. Producer делает tuple(sorted(contract.supported_versions)) ровно при формировании owning fact; validator отвергает несогласованный tuple, не нормализует произвольный input. Registry/codec capability остаётся frozenset. Это одна representation множества в общем fact, а не Snapshot mirror. Frozenset технически сериализуется в JSON array, но не задаёт устойчивый порядок; deterministic tuple выбран владельцем для общего diagnostic JSON. Порядок reasons/sections/patches этим не меняется.

Snapshot mapping: для этих четырёх случаев передать тот же exact fact в public input_issues; никакого восстановления classes, ModelIdentity.of, сортировки или повторного predicate в Snapshot. Public JSON schema включает четыре branches с distinct code const, обязательными operands и extra-forbid. Canonical roots/IDs/terminal manifest не добавляются. Snapshot naming/codes ещё не реализованы: их замена owning кодами не миграция существующей wire версии. Consumer подтверждает именно эту замену proposed зеркальных details.

## Контракт и размещение

`application/patch/encoding/patchSetCodec.py::PatchSetCodec[S].validate_request(request: PatchSet[S]) -> PatchSet[S]` возвращает exact bound revalidated model либо поднимает `application/patch/errors.py::PatchSetAdmissionError`. Конструктор exception принимает непустой `tuple[PatchSetAdmissionReason, ...]`, проверяет exact closed roster; исходный ValidationError сохраняется через `raise ... from error`, вне reasons. Infrastructure exceptions не преобразуются в этот carrier.

Все новые reasons — named immutable strict Pydantic records в `dataModel/patch/validation/admissionReasons.py`, без runtime class objects/исключений. Четыре compatibility facts публичны по уточнению выше; остальные — inputs owning mapper. Canonical roots не вводятся. Существующий ValidatorAggregationHelper используется без исключений и без ослабления validate_immutable.

| Concrete class | Поля |
|---|---|
| PatchSetRequestModelMismatch | expected_model: ModelIdentity; actual_type_name: StrictStr |
| PatchSetRequestVersionUnsupported | code: Literal выше; actual_version: FormatVersion; supported_versions: tuple[FormatVersion, ...] (nonempty, unique ascending) |
| PatchSetSectionKeyUnknown | code: Literal выше; section_index: Annotated[StrictInt, Field(ge=0)]; section_key: SectionKey |
| PatchSetSectionModelMismatch | code: Literal выше; section_index; section_key; expected_model: ModelIdentity; actual_type_name: StrictStr |
| PatchSetSectionVersionUnsupported | code: Literal выше; section_index; section_key; actual_version: FormatVersion; supported_versions: tuple[FormatVersion, ...] (nonempty, unique ascending) |
| PatchSetStructuralFailure | error_type: StrictStr; loc: tuple[StrictStr | StrictInt, ...]; message: StrictStr |

`PatchSetAdmissionReason` — plain closed union шести classes и existing PatchSetInvariantViolation. `actual_type_name` = type(value).__module__ + '.' + type(value).__qualname__: только диагностическое описание, не identity для dispatch/сравнения. Проверка exact type выполняется на объекте до создания facts. Expected ModelIdentity переиспользуется; новый TypeIdentity POJO не вводится. loc сохраняется без преобразования в WireLocation: Pydantic union labels и исходные индексы ещё не проверенный field path. Snapshot отвечает за mapping loc.

## Core и structural split

`dataModel/patch/validation/coreInvariantError.py::PatchSetCoreInvariantError(ValueError)` хранит исходный непустой tuple[PatchSetInvariantViolation, ...]. PatchSet.coherent_request вызывает existing check_core ровно один раз и поднимает этот carrier. Pydantic сохраняет его в structured ctx.error; строка не разбирается.

`application/patch/validation/modelValidationErrors.py::PatchSetModelValidationErrors.classify(error: ValidationError) -> tuple[PatchSetStructuralFailure | PatchSetInvariantViolation, ...]` обходит ErrorDetails в исходном порядке. Exact PatchSetCoreInvariantError раскрывается только при loc=() на boundary проверяемого корневого PatchSet; такой carrier во вложенной модели — classification fault. Его исходные facts сохраняются без смены indices, details или порядка.

Confirmed structural allowlist первой реализации: missing, extra_forbidden, model_type, model_attributes_type, dataclass_type, dataclass_exact_type, none_required, bool_type, int_type, float_type, string_type, bytes_type, tuple_type, list_type, set_type, frozen_set_type, dict_type, enum, literal_error, is_instance_of, is_subclass_of, union_tag_invalid, union_tag_not_found, greater_than, greater_than_equal, less_than, less_than_equal, multiple_of, finite_number, too_short, too_long, string_too_short, string_too_long, string_pattern_mismatch, bytes_too_short, bytes_too_long. Allowlist принадлежит этому адаптеру и проверяется на установленной версии Pydantic. Обрабатываются только entries без ctx.error; поля error_type/loc/message копируются, input/ctx не выносятся в facts. Custom validators не должны выдавать builtin structural codes: такое использование нарушает owning schema contract.

Неизвестный ctx.error, value_error/assertion_error, custom/неизвестный code или неподдерживаемый loc дают `application/patch/errors.py::PatchSetValidationClassificationError(RuntimeError)` с исходным ValidationError как cause. Нельзя молча пропустить entry или вернуть частичный input refusal при нераспознанной причине. Дополнительные виды structural errors вводятся явно, не автоматически по отсутствию ctx. При structural failures model after-validator мог не выполняться: core facts в таком случае не выдумываются и check_core повторно не вызывается.

Snapshot consumer signature: `SnapshotPublicInputValidation.map_structural(fact: PatchSetStructuralFailure, *, model: type[BaseModel]) -> tuple[JsonFieldError | WireShapeIssue, ...]`. Вызов для каждого fact в исходном ordered reasons, без группировки вокруг relations. Это требуемая поправка прежнего proposed Input ValidationError, а не второй mapper. Полный mixed ValidationError туда не передаётся. Причина exception доступна на runtime boundary через cause и не сериализуется.

## Порядок и construction

Exact request type — prerequisite revalidation. Strict revalidation — prerequisite дальнейшего format/registry admission. При успешной модели независимые version/section compatibility checks агрегируются в request order, format первым; внутри секции key → exact model → version. Отсутствие key запрещает зависимые model/version checks, но не проверку следующей секции. Ошибка exact модели не мешает сравнению уже structurally valid header version с найденным contract. Registry owns predicates; codec adds section_index к owning local reasons. Не дублировать predicates в Snapshot.

После успешного validate_request Snapshot отдельно вызывает check_prepared_order и сохраняет исходные facts. Затем fingerprint → claim. encode reuse validate_request; encoder failures не ловятся как input errors. Повторная защитная model revalidation внутри encode допустима.

`PatchSetCodec.validate_configuration() -> None` вызывается его __post_init__: named closed request model, ordered sections tuple и exact concrete section roster subset `SectionRegistry.section_models: frozenset[type[DomainSection]]`. Registry extras допустимы; existing запрет duplicate key/model сохраняет однозначность. Snapshot проверяет только codec.registry is service_registry. Configuration TypeError/ValueError не являются admission errors.

## Минимальная нормативная дельта

В docs/tz_patch_system.md и docstring invariantViolation.py заменить internal-only характеристику: PatchSetInvariantViolation является публичным immutable фактом нарушения PatchSet для неперсистентной диагностики потребителя; details принадлежат закрытому owning union, indices относятся к исходному request, не перенумеровываются. Экспорт не означает durable outcome, canonical registration или нового terminal/wire version. Поля/модуль не меняются. Дельта предъявлена для синхронизации владельцами; в этом проходе ТЗ не изменено.

## Приёмка

Чистые records/adapters без IO, persistence, domain handlers, foreign pipeline calls и новых DAG nodes. Public invocation/order неизменны. Model/config/admission/classification/encoding failures разделены. Не добавляются CRUD/settings, caching или runtime dispatch по имени типа. Тесты должны доказать collector admission всех reasons, root core extraction once, shape/relation/shape order, unknown ctx fault, исходные indices/loc, encoder isolation и construction subset. Реализация и runtime PASS этим документом не объявлены.
