# Stable logging consumers — DONE

2026-11-07. **Репозиторный переход выполнен и предъявлен на приёмку.** Владелец маршрутизации — инфраструктура logging. Домены владеют событиями и адаптерами. Таблица §2 фиксирует исходные точки создания logger и их целевые идентичности.

Все 33 адреса перешли на get_consumer_logger. Relief выбирает отдельный consumer для R44. Каталог содержит 34 доменные идентичности, 112 явных регистраций существующих runtime-источников и 21 регистрацию для корневых, скриптовых и внешних logger. У оставшихся module-named runtime producers сохраняются исходные имена и файлы. Их перенос под другим именем обнаруживает проверка inventory. Для доменных consumers точного совпадения достаточно, дочерние имена поддержаны в явно перечисленных namespaces (HTTP, DAG и внешние библиотеки). Root и __main__ зарегистрированы точно.

route_for возвращает LogRoute или поднимает UnknownLogConsumerError до открытия файла в обоих профилях. Router проверяет server_enabled прямо на маршруте. Transcript читает generation_enabled того же маршрута. Time, Artifacts и Snapshot различают нарушение контракта и штатный best-effort отказ доставки. Внутренний кеш файлового router использует конечный Path, общий для обоих профилей.

В backend/config.toml найден активный родительский override DEBUG для Pack. В конфигурацию добавлены обе новые идентичности Pack с тем же уровнем. Существующий родительский ключ по-прежнему обслуживает оставшиеся pack-модули. Сбор предупреждений генераторов в отладочных вызовах обновлён для перенесённых имён. Пользовательские overrides вне репозитория требуют сверки при развёртывании.

До изменения адресные route/transcript tests — 28 OK. Итоговый общий набор — **112 tests, 106 OK, 6 errors**, все шесть в прежних library-pack сценариях с базовым FieldPathError. Проверены новый strict contract, отсутствие записи для неизвестного logger, реальные файлы и transcript, R44, debug capture, Pack levels и получение logger после перемещения адаптера. Все 33 модуля producers импортированы. Pyright по общему logging, generationLogging и middleware — **0 errors, 0 warnings**.

Нормы: [ТЗ logging: L1–L8](../../docs/tz_logging.md#инварианты), [маршрут](../../docs/tz_logging.md#маршрут), [два слоя](../../docs/tz_logging.md#два-слоя). Предыдущий [рефакторинг facade](logging-facade-decomposition-done.md) разделил механизм по файлам, но не решил идентичность producers.

## 1. Целевой контракт

Пример целевого доменного кода: `get_consumer_logger(LogConsumer.TIME_OPERATIONS)`. Смысл события, severity и типизированный DTO остаются в существующем доменном адаптере. Строки имён logger/path остаются единожды объявленными значениями закрытых типов, не вычисляются из __name__, __file__ или import path.

Новые файлы:
- `backend/app/core/logging/contracts.py` — LogConsumer, LogSink, LogRoute. Это конфигурационные типы infrastructure logging, не доменные ошибки. Размещение рядом с существующим core/logLevel.py по ответственности; нового dataModel домена событий не создаётся.
- `backend/app/core/logging/consumers.py` — одна функция `get_consumer_logger(consumer: LogConsumer) -> logging.Logger`. Exact runtime admission LogConsumer; plain str/другой enum дают TypeError до вызова stdlib. Возвращает logging.getLogger(consumer.value); не настраивает level/propagate/handlers, не emit-ит и не кэширует повторно.

LogConsumer — StrEnum: значения в таблице §2 являются полным freeze. Разные producers одного sink сохраняют разные идентичности для уровня/корреляции. Совпадение текущего basename с новым value не является правилом генерации: после объявления значение остаётся при любом переносе файла.

LogSink — StrEnum, полная таблица §3. Это закрытые физические направления, не произвольные пути. `LogRoute` — frozen/strict/extra=forbid/revalidate_instances=always BaseModel; четыре обязательных поля без defaults: `consumer: LogConsumer`, `sink: LogSink`, `server_enabled: StrictBool`, `generation_enabled: StrictBool`. Не хранить рядом дублирующие string domain/service/logger_name. Здесь нет wire/persist формата или canonical IDs; новые поля config до кода записать в ТЗ logging.

`route_for(logger_name: str) -> LogRoute` возвращает зарегистрированный маршрут. Если имя не совпало ни с одним объявленным именем или разрешённым префиксом по границе точки, функция поднимает `UnknownLogConsumerError(ValueError)` с исходным `logger_name: str`. Исключение объявляется в `core/logging/contracts.py`. Router проверяет маршрут до открытия файла и до блока обработки ошибок доставки. Повторный вызов logger для сообщения об этом нарушении запрещён. Каталог проверяет полноту LogConsumer и уникальность каждой регистрации.

Router проверяет `route.server_enabled` непосредственно. Для известного маршрута с False сервер пропускает запись. `consumer_log_path(sink: LogSink, *, logs_dir: Path | str | None = None) -> Path` в fileRouter.py — единственная граница LogSink.value → относительный путь + .log. Профиль script использует отдельную `script_log_path(service: str, *, logs_dir: Path | str | None = None) -> Path` с прежней проверкой stem. Script service — открытое имя запуска, не член LogSink. Router cache допускает `LogSink | str` как внутренний ключ, где str только validated script stem; обращения разделены по profile, произвольный tuple/string sink не принимается.

## 2. Проверенный producer inventory и LogConsumer

Исследованы getLogger sites по AST backend/app и поиск rg. 33 адреса, которые route_for сейчас направляет в domain sinks. В таблице — точные изменяемые production-файлы: заменить создание logger, а не переписывать сообщения/DTO. Старый путь указан как AS-IS evidence; после перехода он не остаётся alias. У source файлов со многими методами logger используется всеми прежними вызовами этого модуля.

| LogConsumer | Значение / stable logger | LogSink | Реальный producer и AS-IS имя |
|---|---|---|---|
| ARTIFACTS | `app.artifacts` | ARTIFACTS | [artifactLog.py:13](../../backend/app/application/artifacts/logging/artifactLog.py#L13) — `app.artifacts` |
| CASCADE | `app.consumer.cascade` | CASCADE | [cascadeLog.py:15](../../backend/app/application/cascade/cascadeLog.py#L15) — `app.application.cascade.cascadeLog` |
| DAG | `app.engine.dag` | DAG | [dagLog.py:10](../../backend/app/application/engine/diagnostics/dagLog.py#L10) — `app.engine.dag` |
| RESOLVE | `app.consumer.resolve` | RESOLVE | [diagnostics.py:19](../../backend/app/application/jsonValidation/resolution/diagnostics.py#L19) — `app.application.jsonValidation.resolve` |
| SETTLEMENT_VOLUME | `app.consumer.settlement_volume` | RESOLVE | [settlementVolumeSeparation.py:11](../../backend/app/application/jsonValidation/settlementVolumeSeparation.py#L11) — `app.application.jsonValidation.settlementVolumeSeparation` |
| PHYSICS_SETTINGS | `app.consumer.physics_settings` | PHYSICS | [reporting.py:20](../../backend/app/application/physics/settings/reporting.py#L20) — `app.application.physics.settings` |
| TIME_OPERATIONS | `app.time.operations` | TIME_OPERATIONS | [timeOperationLog.py:77](../../backend/app/application/time/logging/timeOperationLog.py#L77) — `app.time.operations` |
| AREA_BARRIERS | `app.consumer.area_barriers` | SETTLEMENT | [areaBarriers.py:33](../../backend/app/application/worldData/generators/assemblers/areaAssembler/planner/areaBarriers.py#L33) — `app.application.worldData.generators.assemblers.areaAssembler.planner.areaBarriers` |
| STRUCTURE_AREA | `app.consumer.structure_area` | SETTLEMENT | [structureAreaAssembler.py:78](../../backend/app/application/worldData/generators/assemblers/areaAssembler/structureAreaAssembler.py#L78) — `app.application.worldData.generators.assemblers.areaAssembler.structureAreaAssembler` |
| BUILDING | `app.consumer.building` | SETTLEMENT | [buildingAssembler.py:22](../../backend/app/application/worldData/generators/assemblers/buildingAssembler/buildingAssembler.py#L22) — `app.application.worldData.generators.assemblers.buildingAssembler.buildingAssembler` |
| RESOURCE_EXTRACTION | `app.consumer.resource_extraction` | SETTLEMENT | [resourceExtractionAssembler.py:14](../../backend/app/application/worldData/generators/assemblers/buildingAssembler/resourceExtractionAssembler.py#L14) — `app.application.worldData.generators.assemblers.buildingAssembler.resourceExtractionAssembler` |
| RUINS | `app.consumer.ruins` | SETTLEMENT | [ruinsAssembler.py:14](../../backend/app/application/worldData/generators/assemblers/buildingAssembler/ruinsAssembler.py#L14) — `app.application.worldData.generators.assemblers.buildingAssembler.ruinsAssembler` |
| VAST_HULL | `app.consumer.vast_hull` | SETTLEMENT | [vastHullAssembler.py:15](../../backend/app/application/worldData/generators/assemblers/buildingAssembler/vastHullAssembler.py#L15) — `app.application.worldData.generators.assemblers.buildingAssembler.vastHullAssembler` |
| CLIMATE_SURFACE | `app.consumer.climate_surface` | CLIMATE | [climateSurfaceAssembler.py:30](../../backend/app/application/worldData/generators/assemblers/climateAssembler/climateSurfaceAssembler.py#L30) — `app.application.worldData.generators.assemblers.climateAssembler.climateSurfaceAssembler` |
| SETTLEMENT_LAYOUT | `app.consumer.settlement_layout` | SETTLEMENT | [layoutCells.py:23](../../backend/app/application/worldData/generators/assemblers/settlementAssembler/layoutCells.py#L23) — `app.application.worldData.generators.assemblers.settlementAssembler.layoutCells` |
| SETTLEMENT_PACKING | `app.consumer.settlement_packing` | SETTLEMENT | [packingLog.py:13](../../backend/app/application/worldData/generators/assemblers/settlementAssembler/packingLog.py#L13) — `app.application.worldData.generators.assemblers` |
| SETTLEMENT_BARRIERS | `app.consumer.settlement_barriers` | SETTLEMENT | [barriers.py:31](../../backend/app/application/worldData/generators/assemblers/settlementAssembler/planner/barriers.py#L31) — `app.application.worldData.generators.assemblers.settlementAssembler.planner.barriers` |
| SETTLEMENT_DISTRICTS | `app.consumer.settlement_districts` | SETTLEMENT | [districts.py:64](../../backend/app/application/worldData/generators/assemblers/settlementAssembler/planner/districts.py#L64) — `app.application.worldData.generators.assemblers.settlementAssembler.planner.districts` |
| SETTLEMENT_MATERIAL | `app.consumer.settlement_material` | SETTLEMENT | [dominantMaterial.py:14](../../backend/app/application/worldData/generators/assemblers/settlementAssembler/planner/dominantMaterial.py#L14) — `app.application.worldData.generators.assemblers.settlementAssembler.planner.dominantMaterial` |
| SETTLEMENT_OCCUPANCY | `app.consumer.settlement_occupancy` | SETTLEMENT | [mapOccupancy.py:19](../../backend/app/application/worldData/generators/assemblers/settlementAssembler/planner/mapOccupancy.py#L19) — `app.application.worldData.generators.assemblers.settlementAssembler.planner.mapOccupancy` |
| SETTLEMENT_PLACEMENT | `app.consumer.settlement_placement` | SETTLEMENT | [placement.py:30](../../backend/app/application/worldData/generators/assemblers/settlementAssembler/planner/placement.py#L30) — `app.application.worldData.generators.assemblers.settlementAssembler.planner.placement` |
| SETTLEMENT_STREETS | `app.consumer.settlement_streets` | SETTLEMENT | [streets.py:43](../../backend/app/application/worldData/generators/assemblers/settlementAssembler/planner/streets.py#L43) — `app.application.worldData.generators.assemblers.settlementAssembler.planner.streets` |
| SETTLEMENT_ASSEMBLY | `app.consumer.settlement_assembly` | SETTLEMENT | [settlementAssembler.py:55](../../backend/app/application/worldData/generators/assemblers/settlementAssembler/settlementAssembler.py#L55) — `app.application.worldData.generators.assemblers.settlementAssembler.settlementAssembler` |
| SETTLEMENT_GENERATION | `app.consumer.settlement_generation` | SETTLEMENT | [settlementGeneratorService.py:45](../../backend/app/application/worldData/generators/assemblers/settlementAssembler/settlementGeneratorService.py#L45) — `app.application.worldData.generators.assemblers.settlementAssembler.settlementGeneratorService` |
| CLIMATE | `app.consumer.climate` | CLIMATE | [loggingHelpers.py:5](../../backend/app/application/worldData/generators/climate/loggingHelpers.py#L5) — `app.application.worldData.generators.climate.loggingHelpers` |
| PRECIPITATION | `app.consumer.precipitation` | CLIMATE | [precipitation.py:17](../../backend/app/application/worldData/generators/climate/precipitation.py#L17) — `app.application.worldData.generators.climate.precipitation` |
| RELIEF | `app.relief` | RELIEF | [log.py:11](../../backend/app/application/worldData/generators/terrain/relief/log/log.py#L11) — `app.relief` |
| TERRAIN_PARALLEL | `app.consumer.terrain_parallel` | TERRAIN_PARALLEL | [terrainParallelLog.py:15](../../backend/app/application/worldData/materialize/terrain/terrainParallelLog.py#L15) — `app.application.worldData.materialize.terrain.terrainParallelLog` |
| PACK_BAKE | `app.consumer.pack_bake` | PACK_BAKE | [_shared.py:14](../../backend/app/application/worldData/pack/bake/log/_shared.py#L14) — `app.application.worldData.pack.bake.packBakeLog` |
| PACK_REFINE_GRADE | `app.consumer.pack_refine_grade` | PACK_REFINE | [detailedGradeGenerate.py:23](../../backend/app/application/worldData/pack/refine/detailed/grade/detailedGradeGenerate.py#L23) — `app.application.worldData.pack.refine.detailed.grade.detailedGradeGenerate` |
| REGION_STATE | `app.consumer.region_state` | REGION_STATE | [regionStateLog.py:7](../../backend/app/application/worldData/regions/regionStateLog.py#L7) — `app.application.worldData.regions.regionStateLog` |
| RENDER_DUMP | `app.consumer.render_dump` | RENDER_DUMP | [dumpLog.py:20](../../backend/app/application/worldData/render/dumpLog.py#L20) — `app.application.worldData.render.dumpLog` |
| HTTP | `http` | HTTP | [logMiddleware.py:10](../../backend/app/core/logMiddleware.py#L10) — `http` |
| RELIEF_RAYS | `app.relief.rays` | RELIEF_RAYS | Тот же [relief/log/log.py](../../backend/app/application/worldData/generators/terrain/relief/log/log.py), отдельный выбор для R44 по §4 |

Reuse неизменённых logical names ARTIFACTS/DAG/TIME_OPERATIONS/RELIEF/HTTP — это действующий целевой контракт, не old/new двойной путь. HTTP descendants (в том числе http.access) продолжают совпадать со стабильным HTTP prefix, не с Python-папкой.

Все остальные routed имена меняются на объявленные значения. Поле logger в JSON поэтому изменится намеренно; другие event fields, severity, файл и порядок эмиссии сохраняются. Проверять golden records с этой единственной metadata дельтой, не обещать byte-identical JSON.

Поиск не нашёл собственного getLogger в packDetailedBakeOrchestrator: прежний специальный prefix сейчас не имеет обнаруженного producer. `structure/headroom` находится в server allowlist, но не имеет route_for mapping. Эти записи не означают реализованные consumers: не добавлять им новые logger автоматически. До включения строгой проверки D2-0 обязан дополнить inventory ранее не маршрутизированных producers (включая pack lightGrid, Hydrology, Snapshot и внешние библиотеки) и зафиксировать их явные маршруты. Исходные 33 места охватывают только известные текущему router имена.

## 3. LogSink и разрешения

| Член | Значение |
|---|---|
| ARTIFACTS | artifacts/artifactLifecycle |
| CASCADE | cascade/cascadeLog |
| DAG | engine/dagExecution |
| RESOLVE | jsonValidation/resolve |
| PHYSICS | physics/physicsLog |
| TIME_OPERATIONS | time/operations |
| SETTLEMENT | settlement/settlementAssembler |
| CLIMATE | climate/climateLog |
| RELIEF | relief/reliefLog |
| RELIEF_RAYS | relief/gradeCellRays |
| TERRAIN_PARALLEL | terrain/terrainParallelLog |
| PACK_BAKE | pack/packBakeLog |
| PACK_REFINE | pack/fineChunkPersist |
| REGION_STATE | region_state/regionStateLog |
| RENDER_DUMP | render/dumpLog |
| HTTP | http/api |
| CORE_RUNTIME | core/runtime |
| PACK_DETAILED | pack/packDetailedBake |
| STRUCTURE_HEADROOM | structure/headroom |

Все ROUTES server_enabled=True кроме RENDER_DUMP=False. PACK_DETAILED/STRUCTURE_HEADROOM остаются reserved enum значениями без consumer; существующие synthetic route probes обновляются, не выдают эти файлы за production paths. Историческая неиспользуемая allowlist запись не служит основанием для нового writer. Для CORE_RUNTIME требуется явная регистрация имени или разрешённого пространства имён. Catch-all отсутствует.

generation_enabled=True для всех consumers §2 кроме DAG, TIME_OPERATIONS, REGION_STATE, HTTP. Это текущее фактическое покрытие generation prefix filter, не пожелание включить больше логов. RENDER_DUMP и RELIEF_RAYS generation=True. В частности Time transcript не добавляется этим D1.

## 4. Relief, transcript и logger levels

**R44.** Переиспользовать EVENT_GRADE_CELL_EMPTY_RAY из [relief/log/events.py](../../backend/app/application/worldData/generators/terrain/relief/log/events.py). В существующем relief/log/log.py доменный helper выбирает RELIEF_RAYS для этого события, RELIEF для остальных; выбор одинаков для info/warning/error/debug как прежняя core route rule. Нового event code, catch или дополнительного emit нет. Уровень события не меняется. Core не импортирует Relief. Консольный activity filter сохраняется — он решает вывод, не выбирает файл.

**Transcript.** [generationLogging.py](../../backend/app/core/generationLogging.py) сначала распознаёт typed route и применяет его generation_enabled, затем текущие правила только для ещё не мигрированных producers. Старый broad transcript prefix остаётся лишь там, где есть действующие unrelated producers (например pack/lightGrid); это не reader/alias мигрированного имени. Проверка inventory не должна объявлять всю систему transcript свободной от module paths: этот D1 устраняет зависимость для consumers §2. Для них новая идентичность и transcript admission поставляются атомарно. World scope ContextVar, вложенность, dedup/handler ownership и reset неизменны.

**Уровни.** [setup_logging](../../backend/app/core/loggingConfig.py) продолжает поддерживать внешние logger_levels; third-party keys (например aiosqlite) не превращаются в LogConsumer. [DefaultConfig.LOGGER_LEVELS](../../backend/app/core/defaultConfig.py) сейчас содержит только aiosqlite: WARNING. [configManager](../../backend/app/core/configManager.py) разворачивает dotted user keys; его алгоритм не менять. До cutover проверить фактические используемые logger_levels и вычислить прежний effective level каждого consumer с учётом родителей. На этапе настройки заменить module-path overrides явными новыми consumer.value keys с тем же effective level, включая групповые overrides, которые расходятся по descendants. Не объединять producers по sink: это потеряло бы различающиеся уровни.

Перенос пользовательских настроек выполняется отдельно и явно по найденным данным; никакой runtime alias/старый reader не остаётся. Если фактические settings deployment недоступны, production gate не закрывать. Для repository tests использовать synthetic parent/child overrides и доказать эквивалентность уровней до/после. На проверку реальных окружений этот D1 не претендует.

## 5. Порядок прямого перехода

D2-0: синхронизировать предложенный контракт в ТЗ logging; снять baseline и settings inventory; code до приёмки D1 не менять.

D2-1: contracts.py + consumers.py, unit/typing admission и единый catalog в routes.py; fileRouter.py и generationLogging.py переводятся вместе. Не подключать новый emitter без обоих каналов. Удаление всех old prefixes до миграции producers запрещено: миграционный каталог хранит только ещё действующие старые producers, без второго маршрута для уже переведённого consumer. Конечный критерий — _PREFIX_ROUTES с module paths удалён, старые routed logger names не создаются.

D2-2: партия существующих адаптеров — ARTIFACTS/DAG/TIME/PHYSICS/HTTP/RESOLVE/CASCADE/REGION_STATE/TERRAIN_PARALLEL/PACK_BAKE/RENDER_DUMP и RELIEF. Producer, свой route и transcript policy переключаются в одной партии; реальные callers доменных helper не переписывают событие.

D2-3: все оставшиеся direct producers таблицы (settlement/area/building/climate/refine), затем удаление пустых старых prefixes и неиспользуемого detailed prefix. Каждый longest-prefix group переключить целиком, чтобы climate не попал в settlement. Обновить overrides/golden metadata и доказать отсутствие path-based зависимости этих логгеров.

D2-4: итоговая регрессия, obsolete catalog строк в ТЗ и тестах больше нет, отчёт на приёмку. Не объявлять решёнными оставшиеся transcript-only producers либо новые domain activation gates.

## 6. Точная карта проверки

Core production правки: новые `backend/app/core/logging/contracts.py`, `consumers.py`; существующие `routes.py`, `fileRouter.py`, `backend/app/core/generationLogging.py`, `logMiddleware.py`. Из core config migration только документирование настроек; алгоритмы loggingConfig/configManager не меняются. 8 файлов в core/logging с __init__ (WARN >5, <=10); корень core не расширяется. Domain production правки — ровно 33 пути §2, Relief повторно не считать. Уже существующие адаптеры не заменяются новым классом.

Tests: `backend/tests/test_logging_routes.py`, `backend/tests/test_generation_logging.py`, `backend/tests/test_library_pack_logging.py`, `backend/tests/test_region_state_overlay.py`, `backend/tests/physics/test_settings_logging.py`, `backend/tests/time/test_time_operation_log.py`, `backend/tests/dag_typing/execution/test_logging.py`; новый `backend/tests/test_logging_consumers.py` — strict contracts, route catalog, relocation, level mapping. Остальные direct-producer тесты подключать адресно при обнаружении assert старого logger.name, с перечислением найденных файлов перед правкой; не обновлять snapshots массово.

Нормативная привязка: D2-0/1 — [маршрут](../../docs/tz_logging.md#маршрут) и новый раздел типов из D2-0; D2-2/3 — [L3–L8](../../docs/tz_logging.md#инварианты) и [каталог](../../docs/tz_logging.md#каталог-консьюмеров); D2-4 — обе группы. Команды ниже из backend, PYTHONPATH=.;tests. Для D2-0 не запускать ещё отсутствующий test_logging_consumers.

```powershell
$env:PYTHONPATH='.;tests'
.\.venv\Scripts\python.exe -m unittest tests.test_logging_consumers tests.test_logging_routes tests.test_generation_logging
.\.venv\Scripts\python.exe -m unittest tests.physics.test_settings_logging tests.time.test_time_operation_log tests.dag_typing.execution.test_logging tests.test_region_state_overlay tests.test_library_pack_logging
node ../node_modules/pyright/index.js app/core/logging app/core/generationLogging.py app/core/logMiddleware.py
```

Existing baseline logging refactor: 105 tests, 6 errors из старого FieldPathError в library-pack, без новых регрессий; после отдельной formatter правки 74 профильных OK. Это историческое evidence, baseline конкретного D2 снимается заново. Тесты этого D1 не запускались.

Критерии:
- Exact enums: неизвестные/string значения rejected, duplicate consumer rejected, все consumers имеют typed route, sink не задаётся producer произвольной строкой.
- Реальный доменный adapter → ожидаемый физический файл, не только route_for synthetic name. Relocation: producer получает logger по enum из тестового модуля с другим __name__; его логический logger и sink не меняются.
- По каждому producer из §2 AST/rg gate обнаруживает оставшийся getLogger(__name__) либо старый строковый logger; исключения вне scope явно перечислены. Gate покрывает creation sites, а runtime file checks — каждый sink/особую политику, не имитацию доменных вычислений.
- Проверить R44, server/script split и границу префикса. Неизвестное имя даёт UnknownLogConsumerError с точным именем до открытия файла. Отдельный тест подтверждает штатный пропуск известного server-disabled маршрута. Поддерживаемый внешний logger попадает в явно назначенный sink.
- Transcript: ровно одна запись в своём world scope, reset/вложенные scopes; Time/DAG/HTTP/region_state не включились случайно.
- Fake sink failure и malformed domain DTO сохраняют прежние границы; fallback, default/None, batch continuation, commit/rollback не меняются.
- Обзор diff, git diff --check; нет runtime compatibility lookup старых логгеров. Осознанная дельта только logger identity/настройки её имени, не event meaning.

## 7. Решения на приёмку

Принять: (1) отдельные LogConsumer/LogSink и LogRoute; (2) точную таблицу стабильных имён, включая сохранение разных producers одного sink; (3) перенос R44-выбора в существующий доменный helper; (4) атомарную миграцию producer + route + transcript + level overrides без legacy. Нового framework, handlers и error core не предлагается.

Production готовность требует проверки реальных user logger_levels; до неё можно реализовать и проверить библиотеку/репозиторные consumers, но нельзя объявлять deployment cutover безопасным для неизвестных настроек.
