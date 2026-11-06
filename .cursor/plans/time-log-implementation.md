# TIME-LOG — отдельный implementation-план

Дата: 2026-11-06. Статус: план для ревью; код не реализуется этой итерацией.
Основание: [Time §47](time-domain.md#47-time-log--обязательное-логирование-через-общий-фасад-проекта-2026-11-03), §48; [logging](../../docs/tz_logging.md).

## 1. Границы и фактическая база

Независимый срез TL-1…TL-3: typed logging contracts, семантический producer и изолированные тесты. Он не требует production reader, Snapshot transaction, DAG binding или закрытия SN-TIME gates. Завершение этого среза означает готовность библиотеки наблюдения, а не runtime TIME-LOG acceptance.

Уже существуют TimeRecord (strict/frozen/extra=forbid/revalidate_instances=always), I64/Nano, TimeCapture/HistoricalTimeCapture, PrepareAdvance/TimeAdvanceProposal и типизированные отказы. Использовать их из dataModel/time, без копий. CalendarFieldIssue/CalendarIssueCode, ValidatedFieldPath и ValidatorAggregationHelper уже реализуют календарную диагностику; resolve_world_time_settings использует общий resolver с WarningError. Это не новые logging events и не повод повторять их сообщения. Отдельного dataModel/time/diagnostics/events.py и application/time/logging пока нет.

Общие LogLevel/to_logging_level, JsonLogFormatter, request_id_var и router остаются единственным механизмом. SnapshotLifecycleLog и DAG emit служат образцами best-effort delivery и строгого admission, но целые Time POJO через model_dump в extra не передаются.

Artifacts уже имеет prefix app.artifacts → artifacts/artifactLifecycle и SERVER_SINKS entry; docs/tz_logging.md отмечает выполненную регистрацию D2-3. loggingConfig.py, generationLogging.py, docs/tz_logging.md и общие logging-тесты уже имеют рабочие изменения. Их не менять и не откатывать в независимом срезе. Не переносить устаревший список routes целиком и не добавлять Artifacts повторно.

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
| TimeRefusalLog / OPERATION_REFUSED | WARNING | code:TimeRefusalCode; только возвращённый typed отказ |
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

Планируемый API (каждый метод возвращает None):

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

Новые файлы: backend/tests/time/test_time_logging_contracts.py и test_time_operation_log.py. Существующий test_time_core.py — регрессия без обязательных изменений. Production composition/factory.py, reads, pure, calendar, changes и World resolver не менять.

Проверить все четыре схемы, пять operations, каждую допустимую пару отказа и запрещённые пары; strict enum/scalars, I64/Nano bounds, extra fields, fixed activity, candidate-only operation, operation_id policy, malformed constructed экземпляры и subclass payload. Семантические методы проверять на реальных typed requests/outcomes.

Перехват logger.log в тесте: одна запись, точный level, allowlist полей; текущий headless source, унаследованный head и historical без publication_id. Форматировать перехваченный LogRecord существующим JsonLogFormatter под заданным request_id_var, проверяя JSON и отсутствие payload/exception. Это не доказательство server routing. Ошибка доставки не вызывает retry; чистые операции и штатные defaults не вызывают producer. Не устанавливать собственный production handler.

Команды из backend, в проектном Python environment (если .venv неактивен, использовать его python.exe; pyright должен быть установлен):

```powershell
python -m unittest discover -s tests/time -p 'test_*.py'
python -m pyright app/dataModel/time app/application/time app/dataModel/world/calendar app/application/worldData/timeSettings tests/time
```

Из корня репозитория — проверка границ изменений:

```powershell
git diff --check
git diff -- .cursor/plans/time-log-implementation.md
rg -n 'TimeOperationLog|app.time.operations' backend/app/application/time backend/app/dataModel/time
```

При реализации сверить diff общих файлов с исходным состоянием рабочего дерева, а не требовать, чтобы они были чистыми: там уже есть чужие изменения. Приёмка TL-1…3: тесты и typing проходят, нет runtime wiring/route изменений, нет объявлений SN-TIME или TIME-LOG runtime acceptance. Команды здесь запланированы, не заявлены выполненными.

## 5. Отдельная регистрация TL-R (после независимого среза)

Предложить владельцу общего logging минимальный diff: loggingConfig.py — prefix (app.time.operations,time,operations) и SERVER_SINKS (time,operations); docs/tz_logging.md — consumer catalog; tests/test_logging_routes.py — адресные проверки. До этого unknown prefix уходит в core/runtime и не удовлетворяет Time contract. Известная пара без allowlist отбрасывается. Не включать producer в production раньше регистрации.

Сохранить текущий Artifacts route и transcript allowlist. Time transcript регистрацию не добавлять автоматически: §47 согласует server sink backend/logs/time/operations.log. Никакого нового router/formatter/handler.

Проверки TL-R: фактический JSON-файл во временном logs_dir с общим setup_logging(profile=server), request_id, DEBUG/INFO filtering, отсутствие fallback/дублирования; сохранение script profile и Artifacts route/transcript. Из backend:

```powershell
python -m unittest discover -s tests -p 'test_logging_routes.py'
python -m unittest discover -s tests -p 'test_generation_logging.py'
```

Регистрация сама по себе не зависит от SN-TIME и может быть принята отдельно; runtime proof требует binding.

## 6. Будущие production bindings TL-B и gates

Конкретные файлы bindings сейчас не выдумывать: отдельный integration-план обязан назвать существующую на тот момент application binding каждого из пяти вызовов, composition wiring и интеграционные тесты. Это не скрытая работа TL-1…3.

| Путь | Зависимость |
|---|---|
| current/historical production read | SN-TIME-READ + Time state reader |
| production apply Time proposal/effects | SN-TIME-APPLY + Time/World handler в CommitScope |
| restore/new branch | SN-TIME-BRANCH |
| pure prepare, contracts/emitter/unit tests | Независимы от всех трех gates |

Для bindings проверить сохранение исходного результата/исключения/cancellation при отказе producer; ровно одну запись на наблюдаемый отказ/candidate; отсутствие повторного resolver WarningError; отсутствие записи при успехе read/project/resolve/default. Две конкурентные подготовки и retry после unknown commit: candidate count соответствует завершенным подготовкам при исправном DEBUG sink; число публикаций подтверждает только Snapshot. Проверить унаследованный head, historical source, нагрузку и отсутствие per-tick/stdout DEBUG storm.

Будущий integration suite: backend/tests/time/test_time_logging_bindings.py; команда из backend: `python -m unittest discover -s tests/time -p 'test_time_logging_bindings.py'`. Создавать и запускать этот suite вместе с реальными bindings; пустой discover не является пройденным gate. Приёмка §47.3 отдельно от TL-1…3 и отдельно от закрытия SN-TIME самим Snapshot owner.

## 7. Решения для ревью

1. Сохранить §47 events, route и severity без расширения Time error unions.
2. Переиспользовать реализованную диагностику; новый logging слой отображает outcomes, не заменяет resolver/validator.
3. Дать producer семантические методы с конкретными typed входами и единый emit; activity/code/level не определяет caller.
4. Наблюдение оставить будущей application binding; pure Time и DAG engine без logging зависимости.
5. Использовать явную allowlist JSON и общий formatter; не логировать исключения и payload.
6. Разделить строгий admission и best-effort delivery; binding сохраняет первичный outcome даже при дефекте producer.
7. Принять независимый срез без production и SN-TIME; регистрацию и интеграционные доказательства учитывать отдельно.
8. Общие logging-файлы сейчас не менять; будущий минимальный route diff должен сохранить уже добавленный Artifacts.
