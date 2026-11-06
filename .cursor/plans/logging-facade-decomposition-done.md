# Logging facade — разделение по ответственностям — DONE

2026-11-07. **L0–L3 реализованы по команде пользователя; предъявлено на приёмку.** Владелец — общая инфраструктура logging. Это перенос существующего механизма, не новый logging/error framework. Доменные адаптеры, их события и runtime-политики сохранены.

## 1. Факты и scope

В [loggingConfig.py](../../backend/app/core/loggingConfig.py) 452 строки: маршруты, JSON formatter, correlation, файловая ротация, консольная очередь, process setup. Проверен текущий checkout, включая новый Time route. [ТЗ: инварианты L1–L8](../../docs/tz_logging.md#инварианты), [два слоя](../../docs/tz_logging.md#два-слоя), [маршрут](../../docs/tz_logging.md#маршрут), [код](../../docs/tz_logging.md#код-ориентиры) остаются нормативными.

В core 13 непосредственных файлов. Новых файлов в корне core не добавлять: новая подпапка logging имеет 6 файлов с __init__.py (WARN >5, лимит 10 не превышен). Не перестраивать остальные core-модули. Название app.core.logging не заменяет stdlib logging: везде абсолютные импорты, никаких sys.path-манипуляций.

Не входят: изменение event DTO, новые sinks/доменная регистрация, Time transcript/TL-B, Water/River D2, исправление очереди/shutdown, новые параметры ротации, новые error classifications, server запуск, commit/push. Existing request_id semantics, включая асинхронную консоль, не исправлять попутно.

## 2. Целевая структура и freeze

Все пути таблицы относительно backend/app/core. Новые файлы отмечены TARGET. Сигнатуры переносимых методов сохраняются, если явное новое внутреннее имя не указано ниже. Новые POJO/enum не требуются: reuse stdlib LogRecord/Handler/Formatter, ContextVar, Path и существующих строковых profile/sink ключей; здесь не проводится миграция их типов.

| Модуль | Владение и символы |
|---|---|
| loggingConfig.py, существующий | Только composition/lifecycle: setup_logging, ensure_script_logging, set_logging_level, _is_facade_handler, _remove_facade_handlers, _has_facade_handlers. Настоящий сохранённый entrypoint, не compatibility wrapper |
| logging/context.py, TARGET | Единственный request_id_var: ContextVar[str], имя request_id, default `-`. Миграция импортов не создаёт второй ContextVar |
| logging/formatting.py, TARGET | JsonLogFormatter.format(record: logging.LogRecord) -> str; _RECORD_BUILTINS; импорт context. Точная прежняя JSON-форма и exception formatting |
| logging/routes.py, TARGET | _PREFIX_ROUTES, SERVER_SINKS, _R44_ACTIVITY, _DUMP_SINK, _RUNTIME_SINK, PROFILE_SERVER/PROFILE_SCRIPT, _matches_prefix, route_for(logger_name: str, activity: object \| None = None) -> tuple[str, str] \| None |
| logging/fileRouter.py, TARGET | DomainFileRouter (перенос _DomainFileRouter с явным внутренним именем без underscore); ротация, _require_service_stem, backend_logs_dir, consumer_log_path. Импорт routes; formatter передаётся composition, обратного импорта loggingConfig нет |
| logging/console.py, TARGET | _FacadeStreamHandler, _ConsoleVolumeFilter, _DropQueueHandler; _CONSOLE_FILE_ONLY_ACTIVITIES, _CONSOLE_QUEUE_MAX и единственные globals queue/listener/handler; flush_console_queue; stop_console_listener; create_console и start_console ниже |
| logging/__init__.py, TARGET | Пустой marker, без re-export и регистрации при импорте |

Внутренние границы console:

- `create_console(*, formatter: logging.Formatter, stream: TextIO) -> logging.Handler`: создать прежний stream handler, formatter и фильтр; без запуска потока/изменения root.
- `start_console(console: logging.Handler) -> logging.Handler`: создать прежнюю очередь maxsize=4096 и drop handler с фильтром, сохранить globals, запустить прежний QueueListener, вернуть queue handler; root attachment остаётся в setup_logging.
- `stop_console_listener() -> None`: прежнее тело _stop_console_listener без изменения порядка reset/stop/close.
- `flush_console_queue(*, timeout_s: float = 2.0) -> None`: прежний bounded polling, включая min timeout и sleeps; это не новая гарантия доставки.

DomainFileRouter сохраняет `__init__(*, profile: str, logs_dir: Path, script_service: str | None = None) -> None`, методы _keys_for/_handler_for/emit/flush/close и маркер _ai_project_log_facade. `consumer_log_path(domain: str, service: str, *, logs_dir: Path | str | None = None) -> Path` и `backend_logs_dir() -> Path` переезжают вместе с единственным местом построения путей. После углубления файла default root остаётся **backend/logs**: расчёт от нового __file__ обязан учитывать дополнительный уровень. Проверить абсолютный ожидаемый путь, не только имя папки.

В loggingConfig сохраняются исходные сигнатуры setup_logging и ensure_script_logging со всеми defaults; set_logging_level(level: int) -> None меняет только root level. Импортировать новые модули как модули и обращаться к их символам квалифицированно, чтобы случайно не оставить старые formatter/context/routes exports в loggingConfig.

Зависимости: formatting → context; fileRouter → routes; console → stdlib; loggingConfig → formatting/routes/fileRouter/console. generationLogging → formatting. logMiddleware → context. Ни один новый модуль не импортирует loggingConfig, доменные адаптеры или application. Каталог routes пока централизован, без discovery/plugins и импортов доменных модулей.

## 3. Инварианты переноса

1. Сохранить порядок setup: проверка script service и создание каталога; подготовка formatter/console/router; установка root level; удаление старых facade handlers; запуск новой console queue; attachment файлов первым, console вторым; logger_levels последними. Не переносить потенциально падающие операции через границу удаления старых handlers без проверки эквивалентности.
2. Один process writer на файл, lazy handlers, 10 MiB/5 backups, UTF-8; прежние locking/flush/close и handleError. Не объявлять их более сильной best-effort гарантией.
3. Longest-prefix и граница prefix+'.', специальный relief activity; unknown server logger → core/runtime, известный неразрешённый sink отбрасывается. Script получает свой файл и отдельный dump только при прежнем условии.
4. Drop при полной console queue, те же activity filters. Transcript handlers не удаляются setup/_remove_facade_handlers, generation allowlist не меняется.
5. Сохраняются Time, Physics, Artifacts, DAG и остальные текущие маршруты; event DTO и сериализация доменных адаптеров не меняются.
6. Новые ошибки не меняют fallback, default/None, продолжение, результат и право записи. Этот refactor не изменяет обработку domain failures либо logging delivery failures.

## 4. Проверенный inventory и судьба импортов

Определения всех переносимых символов сейчас находятся в [loggingConfig.py](../../backend/app/core/loggingConfig.py). Поиск: `rg -n 'loggingConfig|_JsonFormatter' backend --glob '*.py'`. Повторить перед кодом, учитывая параллельные треки.

| AS-IS consumer | TARGET / действие |
|---|---|
| [logMiddleware](../../backend/app/core/logMiddleware.py) импортирует request_id_var | Импорт единственного экземпляра из logging.context |
| [generationLogging](../../backend/app/core/generationLogging.py) импортирует JsonLogFormatter | Импорт logging.formatting; остальная логика без изменений |
| [test_models](../../backend/tests/snapshotCore/contracts/test_models.py), [test_time_operation_log](../../backend/tests/time/test_time_operation_log.py) импортируют formatter/context | Прямые новые импорты |
| [test_settings_logging](../../backend/tests/physics/test_settings_logging.py), [test_logging_routes](../../backend/tests/test_logging_routes.py) используют смешанные symbols | Разделить импорты: setup/cleanup остаются loggingConfig; formatter/context/routes/flush приходят от новых владельцев |
| [test_library_pack_logging](../../backend/tests/test_library_pack_logging.py), [test_region_state_overlay](../../backend/tests/test_region_state_overlay.py) используют flush | flush из logging.console; setup/cleanup остаются |
| [DAG test_logging](../../backend/tests/dag_typing/execution/test_logging.py) обращается loggingConfig.route_for/flush_console_queue | Прямые routes/console imports; setup/cleanup остаются |
| [app.py](../../backend/app/core/app.py), [settingsService](../../backend/app/core/settingsService.py) | setup_logging/set_logging_level остаются, правка не нужна |
| scripts: [detailed_bake](../../backend/scripts/detailed_bake.py), [entry_bg_refine](../../backend/scripts/entry_bg_refine.py), [initialize_world](../../backend/scripts/initialize_world.py), [light_and_full_bake](../../backend/scripts/light_and_full_bake.py), [render_maps](../../backend/scripts/render_maps.py) | ensure_script_logging остаётся в действующем facade, правка не нужна; скрипты не запускать |
| `_JsonFormatter = JsonLogFormatter` | Единственный match — определение; удалить alias, replacement callers не нужны |

Docstrings DAG/region/canonicalLibrary, называющие facade владельцем доставки, остаются корректными. _DomainFileRouter нигде вне исходного файла не используется по поиску; новое имя DomainFileRouter — прямой перенос, без alias. Старые exports переносимых функций/классов удаляются сразу с миграцией callers. Никакой legacy папки, старой копии, forwarding wrapper или re-export. _remove_facade_handlers остаётся действующей orchestration-функцией, её сохранение не legacy.

## 5. Шаги

Шаги выполняются по одному с отчётом. Общие logging-файлы нельзя одновременно редактировать с новым domain route треком: сначала сверить его diff и сохранить registrations. Документ не требует отката текущего TL-R.

| Шаг / цель | ТЗ | Точные файлы | Контракт и проверка | Done |
|---|---|---|---|---|
| L0: зафиксировать baseline и карту в ТЗ | [инварианты](../../docs/tz_logging.md#инварианты), [код](../../docs/tz_logging.md#код-ориентиры) | docs/tz_logging.md, этот план | Документировать §2; выполнить команды A/B ниже до code diff, записать counts/failures | Нет несогласованных contract gaps, фактический baseline записан |
| L1: перенести correlation/formatter/routes вместе с callers | [формат L6](../../docs/tz_logging.md#инварианты), [маршрут](../../docs/tz_logging.md#маршрут) | Новые logging/{__init__,context,formatting,routes}.py; loggingConfig.py; core/{logMiddleware,generationLogging}.py; tests/{test_logging_routes,physics/test_settings_logging,snapshotCore/contracts/test_models,time/test_time_operation_log,dag_typing/execution/test_logging}.py | §2–4; убрать _JsonFormatter. Команды A/B/C | Единственный ContextVar, прежний JSON и маршруты; старых импортов перенесённых symbols нет |
| L2: выделить файловую и консольную доставку | [L1/L4/L7/L8](../../docs/tz_logging.md#инварианты), [два слоя](../../docs/tz_logging.md#два-слоя) | Новые logging/{fileRouter,console}.py; loggingConfig.py; tests/{test_logging_routes,test_library_pack_logging,test_region_state_overlay,physics/test_settings_logging,dag_typing/execution/test_logging}.py | §2–3; flush imports обновить. Команды A/B/C | Facade только composition, backend/logs не смещён, queue/close/reinit прежние; no compatibility exports |
| L3: объединённая проверка и документальный итог | [код](../../docs/tz_logging.md#код-ориентиры), [каталог](../../docs/tz_logging.md#каталог-консьюмеров) | Этот план, docs/tz_logging.md | A/B/C на итоговом дереве; inspection diff; inventory старых imports/alias | Итог и baseline delta, никакого объявления общей production/domain acceptance |

Тесты расширять в существующих модулях, только для существенных рисков: абсолютный default logs root; повторный setup не дублирует запись и сохраняет активный transcript; единый request_id/reset у formatter и middleware; настоящие file outputs и script split; queue-full drop не блокирует; shutdown не оставляет старый listener. Не добавлять mirror-тесты разбиения файлов или arbitrary лимит строк. Не менять поведение shutdown ради зелёного теста: обнаруженный дефект отдельно.

Команды A/B из backend (существующий .venv), с `$env:PYTHONPATH='.;tests'` для существующего bare import в library-pack tests. При sandbox Temp/socketpair ограничении фиксировать причину и повторять тот же набор в подходящей среде, не исключать молча тесты.

```powershell
# A: общая маршрутизация, transcript и доменные delivery consumers
.\.venv\Scripts\python.exe -m unittest tests.test_logging_routes tests.test_generation_logging tests.test_library_pack_logging tests.physics.test_settings_logging tests.time.test_time_operation_log tests.dag_typing.execution.test_logging
# B: оставшиеся consumers и DTO formatter
.\.venv\Scripts\python.exe -m unittest tests.test_region_state_overlay tests.snapshotCore.contracts.test_models
# C: typing нового механизма и facade (сравнить ошибки исходного facade до/после)
node ../node_modules/pyright/index.js app/core/loggingConfig.py app/core/logging app/core/generationLogging.py app/core/logMiddleware.py
```

Для L0 C запускать без ещё отсутствующей app/core/logging; последующие шаги — по существующим целевым файлам. Отсутствующий модуль/пустой discover не PASS. При наличии baseline typing defects перечислить их отдельно; не расширять refactor для несвязанных исправлений.

Из корня: `git diff --check`; `rg -n 'loggingConfig|_JsonFormatter' backend --glob '*.py'`. Каждый оставшийся match сверяется с inventory, общий нулевой результат не требуется: действующий setup facade остаётся. Проверить отсутствие старых dotted references и import/re-export перенесённых symbols. Новые untracked файлы просмотреть отдельно, обычный git diff их не показывает.

## 6. На приёмку

Уточнение по прямому поручению пользователя выполнено: ручная копия полей LogRecord удалена из formatting.py. Источник служебных атрибутов — экземпляр стандартного logging.LogRecord, не makeLogRecord/настраиваемая factory (её доменные extras сохраняются). message/asctime остаются отдельными служебными полями Formatter. Event DTO, JSON schema и runtime не меняются. Регрессия проверяет пользовательскую factory, предварительное форматирование той же записи и исходный traceback. Logging/generation, Time/Physics и snapshot DTO consumers — **74 tests OK**; `node ../node_modules/pyright/index.js app/core/logging` — **0 errors, 0 warnings**.

Реализованы структура §2 и прямая миграция callers §4. loggingConfig сокращён с 452 до 108 строк; шесть файлов в logging, включая пустой marker. Alias _JsonFormatter удалён, старых обращений к перенесённым symbols не найдено. Domain adapters и runtime wiring не менялись; текущий Time route сохранён.

L0: A+B с PYTHONPATH=.;tests — 102 tests, 6 errors, 0 failures, 0 skips; C — 0 errors. Все шесть ошибок — tests.test_library_pack_logging: пять LifecycleLoggingTests (common_sink, copy, preview/confirm, usage, another_world) и ReferenceIndexLoggingTests.test_index_returns_typed_facts_without_emitting. Причина — прежний referenceResolver.reference_index вызывает базовый FieldPathError, запрещённый error-контрактом; это до переноса logging. Первый запуск без PYTHONPATH дал import error, не принят за baseline. Sandbox async-прогоны зависали и были остановлены; полные сравнимые прогоны выполнены вне sandbox.

L1: тот же A+B — 102/6/0/0, те же тесты и TypeError; C — 0 errors. L2/L3: A+B — **105 tests, 6 прежних errors, 0 failures, 0 skips**; добавлены три проверки default root/shared request context, queue-full drop и reconfiguration/transcript/listener lifecycle. Адресные logging+generation — **27 OK**. C — **0 errors, 0 warnings**. Общий набор не объявляется полностью зелёным: 6 внешних baseline defects не исправлялись. Diff просмотрен, git diff --check PASS.
