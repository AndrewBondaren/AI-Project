# TIME-LOG — отдельный implementation-план

Дата ревью: 2026-11-07. Статус: TL-1…TL-3 и TL-R реализованы по поручению пользователя; общий typing gate имеет существующие ошибки tests/time/test_time_core.py (см. evidence ниже). TL-B не реализован.
Основание: [Time §47](time-domain.md#47-time-log--обязательное-логирование-через-общий-фасад-проекта-2026-11-03), §48; [logging](../../docs/tz_logging.md).

## 1. Границы и фактическая база

Независимый срез TL-1…TL-3: typed logging contracts, семантический producer и изолированные тесты. Он не требует production reader, Snapshot transaction, DAG binding или закрытия SN-TIME gates. Завершение этого среза означает готовность библиотеки наблюдения, а не runtime TIME-LOG acceptance.

Уже существуют TimeRecord (strict/frozen/extra=forbid/revalidate_instances=always), I64/Nano, TimeCapture/HistoricalTimeCapture, PrepareAdvance/TimeAdvanceProposal и типизированные отказы. Использовать их из dataModel/time, без копий. CalendarFieldIssue/CalendarIssueCode, ValidatedFieldPath и ValidatorAggregationHelper уже реализуют календарную диагностику; resolve_world_time_settings использует общий resolver с WarningError. Это не новые logging events и не повод повторять их сообщения. Отдельного dataModel/time/diagnostics/events.py и application/time/logging пока нет.

Общие LogLevel/to_logging_level, JsonLogFormatter, request_id_var и router остаются единственным механизмом. SnapshotLifecycleLog служит образцом best-effort delivery и строгого admission; DAG emit — только проекции по объявленной схеме (его logger.log не защищён try/except), но целые Time POJO через model_dump в extra не передаются.

Artifacts уже имеет prefix app.artifacts → artifacts/artifactLifecycle и SERVER_SINKS entry; docs/tz_logging.md отмечает выполненную регистрацию D2-3. В текущем рабочем дереве изменены loggingConfig.py, generationLogging.py, docs/tz_logging.md и tests/test_logging_routes.py. Их не менять и не откатывать в независимом срезе. Не переносить устаревший список routes целиком и не добавлять Artifacts повторно.

## 2. Контракты событий (TL-1)

Создать dataModel/time/diagnostics/events.py и __init__.py. Все пути реализации далее относительно backend/app.

- Закрытые StrEnum: TimeLogOperation, TimeLogActivity, TimeRefusalCode.
- TimeLogOperation: PREPARE_ADVANCE, READ_CURRENT, READ_HISTORICAL, PROJECT, RESOLVE.
- TimeLogRecord — discriminated union по activity из четырех вариантов ниже; Literal enum activity, без произвольного status/severity/message.
- Основа — существующий TimeRecord. Общие поля: world_uid:EntityUid; timeline_id, operation_id, publication_id:EntityUid | None; snapshot:WorldSnapshotRef | None. Nullable означает неизвестное/неприменимое, а не сгенерированный идентификатор.
- Candidate допускает только PREPARE_ADVANCE; operation_id обязателен для prepare и запрещён для остальных операций. Refusal валидирует допустимую пару operation/code по таблице. Не требовать равенства timeline активной публикации и унаследованного snapshot head.

| Вариант / activity | Уровень | Дополнительные поля / условие |
|---|---|---|
| TimeCandidateLog / ADVANCE_PREPARED | DEBUG | start_seconds:I64, start_nanoseconds:Nano, end_seconds:I64, end_nanoseconds:Nano из proposal.interval; только успешная подготовка |
| TimeRefusalLog / OPERATION_REFUSED | WARNING | code:TimeRefusalCode; только возвращённый typed отказ наблюдаемой операции; не WarningError и не continuation |
| TimeCancelledLog / OPERATION_CANCELLED | DEBUG | Нет; cancellation до результата |
| TimeFaultLog / OPERATION_FAILED | ERROR | Нет; непредвиденное исключение |

| Операция | Тип отказа → TimeRefusalCode |
|---|---|
| PREPARE_ADVANCE | TimeAdvanceMustBePositive → ADVANCE_NONPOSITIVE; TimeRangeOverflow → RANGE_OVERFLOW |
| READ_CURRENT | TimePublicationConflict → PUBLICATION_CONFLICT; TimeInactiveTimeline → INACTIVE_TIMELINE; TimeStateUnavailable → STATE_UNAVAILABLE |
| READ_HISTORICAL | TimeStateUnavailable → STATE_UNAVAILABLE |
| PROJECT | CalendarSourceMismatch → CALENDAR_SOURCE_MISMATCH; CalendarScopeMismatch → CALENDAR_SCOPE_MISMATCH; CalendarBudgetExceeded → CALENDAR_BUDGET; CalendarInvalid → CALENDAR_INVALID; CalendarTimeOverflow → CALENDAR_OVERFLOW |
| RESOLVE | CalendarSourceMismatch → CALENDAR_SOURCE_MISMATCH; CalendarInvalid → CALENDAR_INVALID; CalendarBudgetExceeded → CALENDAR_BUDGET; CalendarTimeOverflow → CALENDAR_OVERFLOW |

Не расширять error unions операций ради логирования. CalendarInvalid остаётся существующим typed outcome с issues; в лог попадает только его код, без повторного сериализованного дерева диагностик.

## 3. Семантические методы и owning boundary (TL-2)

Создать application/time/logging/timeOperationLog.py и __init__.py. TimeOperationLog.emit(record:TimeLogRecord) → None — единственная точка доставки в logger app.time.operations. Семантические методы того же producer выбирают activity/level и создают record; вызывающий код не собирает произвольные dict и не выбирает severity.

Контракт доменного адаптера (каждый метод возвращает None):

| Метод | Typed вход |
|---|---|
| emit_advance_prepared | proposal:TimeAdvanceProposal |
| emit_advance_refused | request:PrepareAdvance, refusal:TimeAdvanceMustBePositive \| TimeRangeOverflow |
| emit_current_refused | expected:WorldPublicationRef, refusal:TimePublicationConflict \| TimeInactiveTimeline \| TimeStateUnavailable |
| emit_historical_refused | snapshot:WorldSnapshotRef, refusal:TimeStateUnavailable |
| emit_project_refused | request:CalendarProjectionInput, refusal:union пяти PROJECT отказов таблицы |
| emit_resolve_refused | request:CalendarResolveInput, refusal:union четырех RESOLVE отказов таблицы |
| emit_cancelled / emit_fault | context:TimeLogContext |

TimeLogContext — frozen strict discriminated union пяти контекстов наблюдения в events.py: prepare с PrepareAdvance, current с expected:WorldPublicationRef, historical с WorldSnapshotRef, project с CalendarProjectionInput, resolve с CalendarResolveInput. Это внутренний typed input producer, не wire record; никогда не сериализуется целиком. Не вводить Any, dict[str, object], строковый operation, универсальный Exception→code mapper. Контексты создаются до вызова, чтобы cancellation/fault могли использовать исходные доступные ссылки. Исключение в emitter не передавать: §47 исключает текст исключения из события.

Проекция корреляции: prepare — base.publication/base.point + operation_id; current — expected; historical — запрошенный snapshot; project — capture; resolve — resolved.source и scope. У current source publication_id и snapshot_head, timeline от active_timeline_id; у historical нет publication_id. Для конфликтов описывается запрошенный источник, не выдуманный успешный результат. request_id и wall-clock ts добавляет общий formatter, не Time.

Методы используют исчерпывающее сопоставление типов отказов без parsing message. emit повторно валидирует объявленный вариант и явно проецирует разрешённые поля; исключает subclass extras, model_construct обходы и mutable nested подмены. В extra только поля §47; snapshot проецируется по существующему типу ссылки, не весь capture. LogLevel задан закрытой таблицей activity. Не передавать exc_info, raw calendar, issues, settings, patch, payload или численные состояния вне четырех координат candidate.

Admission находится перед best-effort delivery: неправильный контракт должен быть обнаружим в unit-тесте; исключение штатной доставки перехватывается как Exception без повторной записи. Будущая binding boundary отдельно защищает исходный outcome от любого сбоя producer, в том числе конструирования записи; не глотает исходную cancellation. Не создавать второй sink для ошибок logging.

Owning boundary — вызывающая application-граница конкретной будущей DAG binding. Она наблюдает ровно один вызов и сообщает факт ровно один раз. Producer не вызывает Time повторно, не читает БД, не выполняет advance и не deduplicate operation_id. Импорты: binding → typed outcomes/producer → diagnostics/общий logging. Чистые Time services и DAG engine не импортируют producer; сигнатуры публичного Time API не меняются.

Успешные read/project/resolve не пишут событий. Candidate не COMMIT. После возврата candidate cancellation DAG и unknown commit принадлежат DAG/Snapshot. Структурные ошибки до вызова принадлежат admission. Уже эмитированный resolver отказ не получает второй Time event: это определяется owning call path будущего binding, не глобальным cache или поиском по логам. World settings остаются World-owned.

## 4. Независимые проверки (TL-3)

Новые файлы: backend/tests/time/test_time_logging_contracts.py и backend/tests/time/test_time_operation_log.py. Существующий test_time_core.py — регрессия без обязательных изменений. Production composition/factory.py, reads, pure, calendar, changes и World resolver не менять.

Проверить все четыре схемы, пять operations, каждую допустимую пару отказа и запрещённые пары; strict enum/scalars, I64/Nano bounds, extra fields, fixed activity, candidate-only operation, operation_id policy, malformed constructed экземпляры и subclass payload. Семантические методы проверять на реальных typed requests/outcomes.

Перехват logger.log в тесте: одна запись, точный level, allowlist полей; текущий headless source, унаследованный head и historical без publication_id. Форматировать перехваченный LogRecord существующим JsonLogFormatter под заданным request_id_var, проверяя JSON и отсутствие payload/exception. Это не доказательство server routing. Ошибка доставки не вызывает retry; чистые операции и штатные defaults не вызывают producer. Не устанавливать собственный production handler.

Команды из backend, явно через backend/.venv (Python 3.12+ для существующих type aliases; зависимости backend/requirements.txt и pyright должны быть установлены). Отсутствующий pyright — незавершённая проверка, не PASS:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests/time -p 'test_*.py'
.\.venv\Scripts\python.exe -m pyright app/dataModel/time app/application/time app/dataModel/world/calendar app/application/worldData/timeSettings tests/time
```

Из корня репозитория — проверка границ изменений:

```powershell
git diff --check
git diff -- .cursor/plans/time-log-implementation.md
rg -n 'TimeOperationLog|app.time.operations' backend/app/application/time backend/app/dataModel/time
```

При реализации сверить diff общих файлов с исходным состоянием рабочего дерева, а не требовать, чтобы они были чистыми: там уже есть чужие изменения. Приёмка TL-1…3: тесты и typing проходят, нет runtime wiring/route изменений, нет объявлений SN-TIME или TIME-LOG runtime acceptance. Команды здесь запланированы, не заявлены выполненными.

## 5. Отдельная регистрация TL-R (после независимого среза)

**Выполнено, предъявлено на приёмку 2026-11-07.** Добавлены prefix/server allowlist Time и запись каталога; два теста используют настоящий TimeOperationLog и временные файлы. Проверены request_id, DEBUG/INFO filtering, отсутствие Time в core/runtime и transcript, отсутствие дублирования и сохранение script sink. Из backend с TEMP/TMP=backend/.tmp_snapshot_core: `.\.venv\Scripts\python.exe -m unittest tests.test_logging_routes tests.test_generation_logging` — **24 tests OK** (0.934s), включая прежние Artifacts/Physics проверки. Generation allowlist и runtime wiring не менялись. Production TL-B/acceptance не закрыты.

Состав TL-R: loggingConfig.py — prefix (app.time.operations,time,operations) и SERVER_SINKS (time,operations); docs/tz_logging.md — consumer catalog; tests/test_logging_routes.py — адресные проверки. До регистрации unknown prefix уходил в core/runtime; этот пробел закрыт. Подключение producer к production остаётся отдельным TL-B.

Сохранить текущий Artifacts route и transcript allowlist. Time transcript регистрацию не добавлять автоматически: §47 согласует server sink backend/logs/time/operations.log. Никакого нового router/formatter/handler.

Проверки TL-R: фактический JSON-файл во временном logs_dir с общим setup_logging(profile=server), request_id, DEBUG/INFO filtering, отсутствие fallback/дублирования; сохранение script profile и Artifacts route/transcript. Из backend:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_logging_routes.py'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_generation_logging.py'
```

Регистрация сама по себе не зависит от SN-TIME и может быть принята отдельно; runtime proof требует binding.

## 6. Согласованный план TL-B — 2026-11-08

**Вход из §5.** TL-1 задаёт четыре record и пять контекстов в `backend/app/dataModel/time/diagnostics/events.py`. TL-2 доставляет их через `backend/app/application/time/logging/timeOperationLog.py`, TL-3 проверяет контракты и producer в `backend/tests/time/test_time_logging_contracts.py` и `test_time_operation_log.py`. Evidence 36 тестов Time и 24 тестов TL-R в §5 и в конце документа относится к 7 ноября. После реорганизации общего фасада фактическая цепочка — `TimeOperationLog.emit` → `get_consumer_logger(LogConsumer.TIME_OPERATIONS)` (`core/logging/consumers.py`, `contracts.py`) → регистрация в `core/logging/routes.py` с `generation=False` → server sink `time/operations.log`. Проверяют `test_time_emitter_server_route_and_filtering` и `test_time_emitter_preserves_script_profile`. Эта регистрация работает независимо от наличия caller.

### 6.1. Владельцы вызовов и исходов

Пути приложения ниже относительно `backend/app`. Матрица operation/code в §2 задаёт точный mapping. Сейчас ни одна из пяти операций не вызывает producer. Фабрики в `application/time/composition/factory.py` конструируют чистые сервисы. Поиск их использований, конструкторов и вызовов в приложении и тестах дал следующие границы.

| Operation | Цепочка в текущем дереве | Где наблюдать и что проверить |
|---|---|---|
| READ_CURRENT | Production caller и реализация Time source отсутствуют. `ReadPortTests.test_pinned_reads` → `make_time_reader(source)` → `application/time/reads/reader.py:TimeReader.read_current(CurrentTimeRead)` → один await одноимённого метода `ITimeReadSource` в `reads/sourcePort.py`. Возвращает исходный TimeCapture либо TimePublicationConflict / TimeInactiveTimeline / TimeStateUnavailable. | После SN-TIME-READ внешний caller наблюдает результат await. На отказе `emit_current_refused(request.expected, result)`, на capture тишина. Тест для каждого варианта — идентичность объекта, один await, 0/1 записей, включая head=None и унаследованный head. |
| READ_HISTORICAL | Те же test caller, factory и port, `TimeReader.read_historical(HistoricalTimeRead)` → HistoricalTimeCapture либо TimeStateUnavailable. Production caller отсутствует. | После SN-TIME-READ внешний caller вызывает `emit_historical_refused(request.snapshot, result)` только на отказе. Проверить один await, идентичность и корреляцию по запрошенному историческому snapshot. |
| PREPARE_ADVANCE | Production caller отсутствует. `TimeCoreTests.test_prepare` → `make_time_advance_pipeline()` → `application/time/changes/advancePipelineOpenPipeline.py:TimeAdvancePipelineOpenPipeline.prepare_advance(PrepareAdvance)`. Нулевая duration → TimeAdvanceMustBePositive, иначе TimeArithmetic.add → TimeRangeOverflow либо TimeAdvanceProposal с интервалом. | У будущего caller после возврата одна из двух ветвей — `emit_advance_prepared(proposal)` или `emit_advance_refused(request, result)`. Проверить значения концов интервала, operation_id, ровно один DEBUG candidate либо WARNING отказ. Pure prepare доступен сейчас. Production apply требует SN-TIME-APPLY и handler в CommitScope. |
| PROJECT | В `application/worldData/timeSettings/factory.py` функции `make_calendar_settings_pipeline` и `make_hours_settings_pipeline` принимают готовый CalendarProjector. В `preparation/calendarPipelineOpenPipeline.py:WorldCalendarSettingsPipelineOpenPipeline.prepare_calendar_update` и `preparation/hoursPipelineOpenPipeline.py:WorldHoursSettingsPipelineOpenPipeline.prepare_hours_change` есть общий caller `preparation/shared/candidate.py:projected`. Внешний production entry, собирающий эти pipeline, отсутствует. `projected` → `application/worldData/timeSettings/reader.py:WorldCalendarResolver.resolve_at(ResolveCalendarAt)` → SettingsInvalid (немедленный return) либо ResolvedCalendarAt → `application/time/calendar/projection.py:CalendarProjector.project(CalendarProjectionInput)`. | Предлагаемый единственный owner PROJECT — `projected`, строго вокруг вызова project. CalendarProjection и CalendarBudgetExceeded возвращаются как есть, CalendarInvalid → SettingsInvalid с теми же issues, прочий отказ → существующий `issue(base, "capture", "inconsistent projection source")`. До преобразования отказа один `emit_project_refused(input, result)`. CalendarTimeOverflow объявлен в union PROJECT, явной ветви его возврата здесь нет. |
| RESOLVE | Production caller отсутствует. `CalendarTests.test_round_trip` → `make_calendar_projector()` → `CalendarProjector.resolve(CalendarResolveInput)` в том же projection.py → PointResult либо CalendarSourceMismatch / CalendarInvalid / CalendarBudgetExceeded / CalendarTimeOverflow. | Только у будущего caller после возврата — `emit_resolve_refused(request, result)` на отказе. Проверять round-trip и overflow на наносекунду за каждым пределом, отсутствие события на PointResult. WorldCalendarResolver.resolve_at в предыдущей строке не вызывает эту операцию. |

У Time-вызовов нет ResolveContext. Для каждой строки collect_only неприменим, флаг в Time request не добавляется. Для четырёх отсутствующих callers приведены условия будущего подключения и тесты, production-файлы для них пока не назначаются. Restore/new branch отдельно зависит от SN-TIME-BRANCH.

### 6.2. Кто уже сообщает отказ

`application/worldData/timeSettings/admission/settings.py:resolve_world_time_settings` → `application/jsonValidation/resolve.py:resolve_model` / `_resolve_defaultable_wire` → `application/jsonValidation/resolution/diagnostics.py:report_continuation` либо `reject_unresolved` → `report_issues` / `log_issues` → LogConsumer.RESOLVE. После успешного разбора CalendarValidator.validate может вернуть CalendarInvalid (тот же reject_unresolved) или CalendarBudgetExceeded (возврат). Это отдельный World admission. Здесь ноль Time events в любом режиме. В отличие от него WorldCalendarResolver.resolve_at при отсутствии версии просто возвращает SettingsInvalid, также без Time event: project ещё не вызывался.

Характеризация AdmissionTests: отсутствующий hours_per_day → 24 без warning. Недопустимый 0 в runtime → 24 и одна continuation, в preview → UnresolvedModelError. Ошибочная from_minute=75 → в runtime разрешённый default без мутации raw, в preview блокируется. При независимых ошибках selected/periods семантическая проверка после fallback продолжается и возвращает обе причины через исключение (в runtime всего три warning). Отсутствующий обязательный selected блокирует. Повторить те же входы с collect_only=True при обоих validate_only: сравнить результат/исключение, пути, порядок blocking и continuations с соответствующим исходным режимом, проверить ноль resolver records и Time records. При collect_only=False сохранить существующее количество WarningError. Не перехватывать UnresolvedModelError как Time fault.

### 6.3. Предлагаемый diff после согласования и приёмка

1. **Файлы первого среза** — только `backend/app/application/worldData/timeSettings/preparation/shared/candidate.py` (наблюдение одного вызова в projected) и новый `backend/tests/time/test_time_logging_bindings.py` (characterization до подключения, затем проверки событий). Фабрики, обе внешние подготовки, admission, projector, emitter и общий router правок не требуют. В текущей итерации меняется только этот план.
2. В projected сохранить локальный CalendarProjectionInput. До вызова project и после получения результата World-ветви остаются за границей наблюдения исключений. Только вокруг самого вызова: CancelledError → одна попытка emit_cancelled(ProjectLogContext), bare raise; Exception → emit_fault и bare raise; успешный возврат → только typed refusal mapping выше. Ошибка создания producer/контекста или самого emit обрабатывается отдельно от исполнения операции, без повторной отправки и без подмены результата/первичного исключения. Не ловить произвольный BaseException. Проверить бросающий producer (включая сбой admission) во всех трёх ветвях и исходную cancellation по идентичности. У read применять этот порядок вокруг await после появления caller. Cancellation DAG после готового proposal не является cancellation prepare.
3. В новом suite вызывать обе World подготовки через существующие фабрики. Сначала зафиксировать значения результата и число вызовов projector. При отсутствии версии — исходные SettingsInvalid.issues, ноль project/Time. При успехе — прежние date/time, допустимые weekday=None и epoch/epoch_year=None, ноль Time. При каждом отказе проверить точный внешний outcome по §6.1, один WARNING с PROJECT и кодом §2, ноль RESOLVE WarningError. Недостижимый в реальном projector вариант проверить подстановкой typed результата и отдельно пометить как проверку границы. Источник/исключение/счётчик проверять также при поломке emitter. Не оборачивать целиком подготовку: ошибка последующего validator не создаёт Time fault.
4. Проверить часы с несколькими календарями: явный origin обходит project, origin=None восстанавливается из projection; после успеха обработать следующую запись, при слишком большом часе вернуть SettingsAnchorRequired, при отказе остановиться на той же записи. Calendar update сохраняет explicit anchor либо строит прежний origin, при исключительно anchor/origin issues выдаёт SettingsAnchorRequired. Успешный вложенный project во всех этих случаях тихий. Сопоставить before/after/effective_at и неизменность исходных settings. Для ошибок до project, последующей валидации и независимых World операций — ноль Time. Один вызов сервиса, одна взаимоисключающая ветвь наблюдения; cache, fingerprint и дедупликация по operation_id не нужны.
5. Для будущих bindings применить те же проверки первичного результата, исходного exception и cancellation при исправном и бросающем producer. Дополнительно §47.3 — реальный JSON, корреляция inherited/headless/historical, DEBUG filtering, отсутствие per-tick/stdout storm, две конкурентные подготовки и retry после unknown commit. Считать завершённые подготовки, публикации сверять только по Snapshot. Срез PROJECT не закрывает эти gates.

**Команды из backend** (новый suite запускается до и после production diff, когда в нём уже есть тесты):

```powershell
.\.venv\Scripts\python.exe -m unittest tests.time.test_time_core tests.time.test_time_logging_contracts tests.time.test_time_operation_log
.\.venv\Scripts\python.exe -m unittest tests.time.test_time_logging_bindings
$env:TEMP=(Resolve-Path .tmp_snapshot_core).Path
$env:TMP=$env:TEMP
.\.venv\Scripts\python.exe -m unittest tests.test_logging_routes tests.test_generation_logging
node ../node_modules/pyright/index.js app/dataModel/time app/application/time app/dataModel/world/calendar app/application/worldData/timeSettings
node ../node_modules/pyright/index.js app/dataModel/time app/application/time app/dataModel/world/calendar app/application/worldData/timeSettings tests/time
```

Сверка 8 ноября: 35 синхронных тестов Time и 28 тестов routes/generation прошли. Асинхронный ReadPortTests.test_pinned_reads в этом прогоне не запускался. Production typing — 0 ошибок, вместе с tests/time — 320 ошибок. Для нового файла требовать ноль новых diagnostics; общий gate остаётся открытым.

**Решения пользователя от 2026-11-08.** Первым срезом TL-B согласовано наблюдение PROJECT в `candidate.projected` до появления внешней production composition. Подключение READ_CURRENT, READ_HISTORICAL, PREPARE_ADVANCE и RESOLVE отложено до появления соответствующих production callers. Полная runtime-приёмка §47.3 проводится отдельно. Реализация первого среза предстоит.

## 7. Предлагаемая фиксация реализации (не новое согласование §47.1–2)

1. Сохранить §47 events, route и severity без расширения Time error unions.
2. Переиспользовать реализованную диагностику; новый logging слой отображает outcomes, не заменяет resolver/validator.
3. Дать producer семантические методы с конкретными typed входами и единый emit; activity/code/level не определяет caller.
4. Наблюдение оставить будущей application binding; pure Time и DAG engine без logging зависимости.
5. Использовать явную allowlist JSON и общий formatter; не логировать исключения и payload.
6. Разделить строгий admission и best-effort delivery; binding сохраняет первичный outcome даже при дефекте producer.
7. Принять независимый срез без production и SN-TIME; регистрацию и интеграционные доказательства учитывать отдельно.
8. Общие logging-файлы сейчас не менять; будущий минимальный route diff должен сохранить уже добавленный Artifacts.


## 8. Результат сверки TL-1…TL-3 и точные зависимости (2026-11-07)

Все пути в таблице относительно `backend/app`; это существующие источники для импорта/чтения, не список правок.

| Reuse | Файл |
|---|---|
| TimeRecord, I64, Nano, TimeScope | `dataModel/time/values/point.py` |
| PrepareAdvance, TimeAdvanceProposal | `dataModel/time/changes/advance.py` |
| TimeCapture, HistoricalTimeCapture | `dataModel/time/reads/capture.py` |
| Time typed отказы | `dataModel/time/results/errors.py` |
| EntityUid | `dataModel/identity/uid.py` |
| WorldPublicationRef / WorldSnapshotRef | `dataModel/worldSnapshot/identity/publication.py` / `refs.py` |
| CalendarProjectionInput, CalendarResolveInput, ResolvedCalendarAt | `dataModel/world/calendar/projection/request.py` |
| Calendar отказы, CalendarFieldIssue, CalendarIssueCode | `dataModel/world/calendar/projection/errors.py` |
| CheckedPath / ValidatedFieldPath | `dataModel/fields/checkedPath.py` / `validatedFieldPath.py` |
| ValidatorAggregationHelper | `dataModel/validation/diagnostics/validatorAggregationHelper.py` |
| LogLevel, to_logging_level | `core/logLevel.py` |
| JsonLogFormatter, request_id_var, router/setup | `core/loggingConfig.py` |

Фактические операции для сверки unions: `application/time/changes/advancePipelineOpenPipeline.py`, `application/time/reads/reader.py`, `application/time/reads/sourcePort.py`, `application/time/calendar/projection.py`. Матрица §2 совпадает с ними. RESOLVE здесь означает CalendarProjector.resolve, а не jsonValidation.resolve. `application/worldData/timeSettings/admission/settings.py` вызывает общий resolver и reject_unresolved; этот World-owned путь не включается в пять Time operations. CalendarFieldIssue.at уже использует CheckedPath; TL не мигрирует его повторно.

Разрешённый diff TL-1…3 — ровно шесть новых файлов: `backend/app/dataModel/time/diagnostics/{__init__.py,events.py}`, `backend/app/application/time/logging/{__init__.py,timeOperationLog.py}` и два тестовых файла §4. Существующие публичные экспорты и runtime wiring не нужны. Документация отражает фактическую реализацию после её отдельного согласования.

Done по шагам:

- TL-1: четыре строгих варианта и пять контекстов; discriminator activity для record и operation для context; imports из таблицы; обязательные nullable поля допускают явный None, но не подстановку ID; все допустимые/запрещённые пары проверены.
- TL-2: восемь семантических методов §3 и единый emit; точный тип варианта и повторная строгая валидация перед delivery; явная проекция snapshot kind/world_uid/timeline_id/snapshot_id. Статическое сообщение без входных payload; общий formatter добавляет стандартные поля. Ошибка доставки не меняет результат и не повторяется.
- TL-3: оба новых suite действительно обнаружены и содержат выполненные тесты; полный tests/time и typing проходят. Unit-тесты producer доказывают схему/проекцию/delivery, но не поведение ещё отсутствующей binding. Проверка неизменности runtime здесь — ограниченный diff и регрессия существующего core; characterization fallback/continuation и сохранения исходной cancellation при сбое producer обязательны перед TL-B, а не объявляются доказанными mock emitter-тестом.

Пересечения: TL-R владеет общими routes/catalog/tests; TL-B — наблюдением вызова и защитой outcome; Snapshot — COMMIT, unknown commit и SN-TIME gates; DAG — execution/cancellation после candidate. Error/World resolver треки владеют issues/collect_only/validate_only, TL не меняет их условия. TIME-DEBT-01…06 из `time-domain-review-debt.md` не устраняются под видом logging (writers, history markers, counters, batch remainder, legacy требования, branch storage). Чужие Physics/Artifacts правки сохраняются.

## 9. Решения и оставшиеся границы

1. Независимый объём TL-1…3 и контракт доменного адаптера / контекст из §3 разрешены командой пользователя «Делай» 2026-11-07; архитектура событий и route уже согласована в time-domain §47.
2. Реализована политика admission: точный тип четырёх record-вариантов (subclass отвергается), повторная валидация вложенных ссылок, отсутствие утечки extras. Отказ admission виден в unit-тесте, но будущая binding обязана защищать первичный outcome.
3. До TL-R назначить владельца/очерёдность минимального изменения общих logging-файлов. Это не блокер изолированного среза.
4. До TL-B назвать конкретные bindings, composition и путь однократной эмиссии: какой owner уже сообщил resolver отказ и где Time event подавляется. Это устанавливается call graph, без runtime cache/dedup и без изменения domain outcomes. Конкретных production binding файлов данный план пока не утверждает.
5. До TL-B закрепить characterization для реально затронутых default/None/fallback/continuation и cancellation путей. Если для диагностики потребуется изменить условие продолжения, остановить зависимую работу и вынести отдельное поведенческое решение.

Предыдущая итерация завершилась согласованием; после команды «Делай» реализованы TL-1…3 с evidence ниже. Полная приёмка typing остаётся открытой; TL-R/TL-B и production wiring не входят в выполненный срез.

## Инвариант миграции диагностики: runtime не меняется (2026-11-06)

**Прямое требование пользователя, обязательное для error/logging треков этого домена:** новые типы ошибок, доменные адаптеры, collectors, события и logging integrations не должны переписывать текущую логику runtime. Условия fallback и продолжения обработки не меняются.

- Сохраняются существующие условия допустимости default/None, fallback и выбора альтернативного результата, продолжения batch/независимых проверок, отказа и распространения исключения. Нельзя ужесточать или ослаблять их из-за нового типа диагностики, severity, наличия лога или удобства нового адаптера.
- Сохраняются вычисленные значения/UID, порядок и условия доменных действий, права на запись, commit/rollback, cancellation и retry. Диагностика отражает фактический исход; не становится новой причиной выбора исхода.
- В POJO/import-цепочках переиспользуются ResolveContext/ResolveReport: blocking issues и continuations не смешиваются; collect_only меняет только эмиссию, а validate_only сохраняет принятую политику соответствующего режима. Разрешённое runtime-продолжение не превращается в blocking error после миграции.
- До переключения producer закрепить characterization текущих сценариев: обычный успех, штатный default/None, разрешённый fallback/continuation, blocking отказ и независимая последующая обработка. После переключения сопоставить значения, эффекты и outcome; допустимы только согласованные изменения формы/доставки диагностики. Изменение диагностики в fingerprint проверяется отдельно и не оправдывает изменение доменного payload/маршрута.
- Исправление сломанного конструктора диагностики должно восстановить уже предусмотренную ветвь, а не сохранять случайный TypeError как доменную политику. Где текущая поломка мешает получить результат, evidence берётся из утверждённого доменного контракта, фактов до сбоя и адресных тестов; новый fallback не придумывается.
- Если для реализации требуется изменить runtime-условие, это **отдельный явно согласуемый поведенческий срез**: зафиксировать расхождение и остановить зависимую правку. Не вносить его попутно под названием error migration или logging. Отрицательная проверка нового диагностического контракта не расширяет область перехвата операционных ошибок.

Приёмка каждого затронутого шага включает evidence сохранения runtime-семантики. Это ограничение миграции ошибок и логов, а не запрет ранее согласованной самостоятельной функциональной разработки домена. Статус реализации и пользовательская приёмка этим пунктом не изменяются.


## Решение пользователя: без legacy-компонентов — 2026-11-07

### Evidence реализации TL-1…TL-3

Уточнение после ревью пользователя: поля logging.extra не собирать вручную в словарь и не дублировать отдельным DTO. После exact-type admission и strict revalidation единственный TimeLogRecord сериализуется через model_dump(mode="json", serialize_as_any=False) на границе stdlib logging. Allowlist — объявленные поля четырёх concrete событий и WorldSnapshotRef; subclass records отвергаются, дополнительные поля вложенного subclass не сериализуются. Полные requests/captures/outcomes в extra не передаются. Доменные вычисления и event schema не меняются.

Созданы только шесть файлов §2–4: events, emitter, package markers и два тестовых модуля. Runtime wiring, pure operations, общие routes и другие домены не менялись. Semantic methods покрывают все объявленные typed refusal mappings, candidate и cancellation/fault; admission предшествует best-effort delivery. Проверены strict activity/context enums, forged records/nested refs, subclass rejection, корреляция inherited/headless/historical и JsonLogFormatter/request_id без payload/exception.

Из backend: `.\.venv\Scripts\python.exe -m unittest discover -s tests/time -p 'test_*.py'` — **36 tests OK**, 0.220s. Sandbox-запуск завис в существующем ReadPortTests.test_pinned_reads; faulthandler подтвердил socket.accept → _fallback_socketpair → proactor _make_self_pipe до выполнения теста. Повтор той же команды вне sandbox прошёл; runtime/test loop не менялись. Адресные новые модули — **7 tests OK**.

`python -m pyright` недоступен (No module named pyright). Установленный `node ../node_modules/pyright/index.js` по точной области §4, включая tests/time: **320 errors**, все в неизменённом tests/time/test_time_core.py; новых diagnostic файлов ошибок нет. Отдельно та же production область без tests: **0 errors, 0 warnings**. Общий typing gate не объявляется зелёным; исправление старых test annotations вне шестифайлового scope. TL-R, TL-B, production/SN-TIME acceptance остаются открытыми.

Для текущего перехода внутренних error/logging и Planning/source контрактов используется один целевой контракт. Не создавать старые декодеры, compatibility adapters/re-exports, двойные readers или параллельные версии компонентов. Действующих потребителей переводить вместе с контрактом; тестовые fixtures обновлять или пересоздавать. Суффикс v1 сам по себе не означает legacy и не требует ни поддержки старого формата, ни косметического переименования.

Для Planning/source P1 проверяются целевая schema closure, явный diff lock, encode/decode и согласованность fingerprint; поддержка прежнего внутреннего source wire не является критерием Done. Изменения bytes объяснять, а не скрывать регенерацией эталонов. Runtime, условия fallback и продолжение обработки сохраняются.

Это решение не отменяет отдельное требование docs/tz_world_snapshot.md §20 к читаемости snapshot-оболочек и доменных секций. Если переход затрагивает именно эту границу, отдельно показать пересечение; не распространять её автоматически на внутренние контракты движка. Код и сохранённые пользовательские данные этой документальной правкой не удаляются. Остальные gates согласования и реализации сохраняются.
