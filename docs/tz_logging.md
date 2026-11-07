---
name: tz-logging
description: "ТЗ логов backend — один фасад, файл = домен/сервис; каталог консьюмеров"
metadata:
  node_type: memory
  type: project
---

> **Статус:** SoT **sinks** (куда писать). **Что** писать в событии — доменное ТЗ консьюмера (R8, R44, pack bake, dump heartbeat).  
> **Код vs SoT:** фасад `loggingConfig` пишет `{domain}/{service}.log`; uvicorn не открывает `script/*` и `render/dumpLog`. Общий `app.log` запрещён.

# Логи (sinks)

## Назначение

Один фасад (`loggingConfig` + маршрутизация). Каждый **консьюмер логов** пишет в **свой** файл:

```text
backend/logs/{domain}/{service}.log
```

`domain` — продуктовый срез. `service` — имя application-сервиса / оркестратора / хелпера (stem), не каждый `.py`.

Консоль процесса (JSON stdout) — отдельный канал на процесс, не файл консьюмера. Пишет listener-поток; эмиттер (bake) не блокируется на pipe. Per-cell / per-system storm — не stdout.

## Не путать

| Это | Не это |
|---|---|
| Консьюмер **логов** (кто эмитит в фасад) | Consumer **pack ASCII** / mask / hills ([`tz_pack_ascii_render.md`](./tz_pack_ascii_render.md); generate [`tz_terrain_relief.md`](./tz_terrain_relief.md); bake — архив v1) |
| Файл `{domain}/{service}` | Общий `app.log` на все процессы |
| Транскрипт прогона bake | Замена доменного файла |

## Инварианты

| # | Правило |
|---|---|
| L1 | **Один файл — один процесс-писатель.** Два процесса не открывают один `RotatingFileHandler` (Windows `WinError 32` на rollover). |
| L2 | Ключ файла **только** `domain` → `service`. Не плодить файл на модуль генератора. |
| L3 | Доменный хелпер (`relief_error`, `packBakeLog`, `dumpLog`, climate `warn_once`) **не** обходить через голый `logging.getLogger` для того же события. |
| L4 | Скрипт (HTTP-клиент) **не** пишет в `{domain}/{service}` сервера. Скрипт → домен `script`, сервис = stem скрипта. Bake/R44 живут в процессе uvicorn. |
| L5 | `print` / script-tee / второй logger на то же событие — запрещены (как consume R44, PAR dump). |
| L6 | Формат файла — JSON-строка на запись (тот же `JsonLogFormatter`). |
| L7 | **Консоль не блокирует эмиттера.** Stdout — `QueueHandler` с drop при переполнении. Bake-поток не ждёт pipe (`npm run dev` / Cursor). |
| L8 | Шторм не на stdout. **R44** ERROR — файл `gradeCellRays` + транскрипт. **`grade_system_create` / `grade_system_members`** — DEBUG (файл при debug). Консоль — heartbeat `packBakeLog` (sidecar / validate `0/N` при `DEBUG_GRADE_SLOT_VALIDATE` / T-3c emit). |

## Два слоя

**Целевое расширение библиотек шаблонов (2026-10-08):** события и поля fallback
определяет [tz_template_library_packs.md §7](./tz_template_library_packs.md).
Template resolve/default/unknown owner/dependency используют существующий
policy-resolve эмиттер и sink `jsonValidation/resolve`; settlement и relief
через свои существующие `packingLog`/`relief_warning` сообщают собственные
доменные последствия, не дублируя уже эмитированное событие resolve.
Нужные типизированные причины/поля добавляются в существующие контракты.
Новые canonical/pack log-функции, handlers, форматтеры и собственные файлы
не создаются. Диагностика содержит world/domain, исходный template UID,
известный pack UID, path/reason и выбранный default; generation transcript
получает штатную копию записи без второго вызова logger. Future master-mode
использует те же причины для ошибок, текущий runtime — warning + default.

| Слой | Путь | Зачем |
|---|---|---|
| **Поток консьюмера** | `backend/logs/{domain}/{service}.log` | стабильный файл сервиса |
| **Транскрипт прогона** | `backend/logs/generation/{world_uid}/bake-{mode}-{stamp}.log` + `bake-{mode}-latest.log` | склейка одного bake/dump; не делит rollover с `{domain}/{service}` |

Транскрипт вешает `generation_world_log` на время job (allowlist logger names). Это **копия** в run-файл, не общий `app.log`.

## Каталог консьюмеров

### Time — TL-R (2026-11-07)

`app.time.operations` → `time/operations`, server sink `backend/logs/time/operations.log`. Producer — `application/time/logging/timeOperationLog.py`, зарегистрирован как LogConsumer.TIME_OPERATIONS. DEBUG candidate/cancel фильтруется общим уровнем; refusal WARNING, fault ERROR. Общий formatter добавляет request_id. Script profile сохраняет свой script sink. Time не добавлен в generation transcript allowlist: это отдельное решение, не часть TL-R. Production bindings TL-B ещё не подключены; регистрация не означает runtime acceptance.

### Patch/Snapshot и artifacts — target регистрации шага 2 (2026-10-30)

Статус: contract freeze принят 2026-10-30. Маршрут app.artifacts и transcript allowlist реализованы подготовительным срезом D2-3 2026-11-06 (21 logging-тест OK); маршрут app.snapshot этим срезом не реализован. Полный artifact GC emitter/failure correlation и локальный I0 ещё требуют D2-2.
Используется тот же loggingConfig/JsonLogFormatter/router, без локальных
handlers и без общего app.log. Domain emitters не дублируются.

- Logger `app.snapshot` → `world_snapshot/snapshotLifecycle`, server sink
  `logs/world_snapshot/snapshotLifecycle.log`.
  Producer — Snapshot application lifecycle, семантика в
  `tz_world_snapshot.md` § «Логирование и проверка контрактов».
- Logger `app.artifacts` → `artifacts/artifactLifecycle`, server sink
  `logs/artifacts/artifactLifecycle.log`.
  Producer — общий artifact/staging/holder/GC application owner.

Для регистрации используется каталог LogRoute. Script profile сохраняет собственный
script sink; не открывает server files. Logger names — явный контракт
маршрутизации, не названия классов и не автоопределение домена по payload.

Activity — domain-owned StrEnum, передача в JSON через `.value`:
`SnapshotLogActivity` содержит APPLY_STARTED, APPLY_COMMITTED,
APPLY_CONFLICT, APPLY_REJECTED, APPLY_FAILED, APPLY_OUTCOME_UNKNOWN,
OPERATION_BUSY, OPERATION_RECOVERED; wire lowercase snake_case.
`ArtifactLogActivity` содержит ARTIFACT_SEALED, LEASE_RELEASED,
GC_DELETED, GC_FAILED; wire lowercase snake_case.
P-4 outcome типизирован общим SnapshotApplyOutcomeKind; activity не
подменяет outcome и не становится ещё одним state/revision store.

Уровни определяет producer: STARTED/BUSY/SEALED — DEBUG;
COMMITTED/RECOVERED/LEASE_RELEASED/GC_DELETED — INFO;
CONFLICT/REJECTED — WARNING; FAILED/OUTCOME_UNKNOWN/GC_FAILED — ERROR.
Используется existing core.logLevel.LogLevel в application emitter,
dataModel events не импортируют core. Snapshot refusal log — один
aggregate lifecycle event без повторной эмиссии domain WarningError.
Runtime unresolved domain reason пишет его существующий producer;
validate_only возвращает diagnostics без runtime WarningError emit.

Обязательная корреляция lifecycle: operation_id, world_uid и request_id
общего фасада; после binding — request_fingerprint; при наличии — timeline_id,
snapshot_id, section key, target ref, artifact hash и outcome enum value.
Нет фиктивных UID вместо отсутствующего контекста. Для общего GC world_uid
может быть None (artifact дедуплицирован между мирами), а operation_id
передаётся maintenance caller; не подставляется произвольный world.
Domain payload/raw SQL
в record не копируются. APPLY_COMMITTED — только после подтверждённого
COMMIT; retry терминального outcome не выдаёт новый APPLY_COMMITTED,
а восстановление результата отмечается OPERATION_RECOVERED.
Exact event-field POJO и emitter files относятся к implementation map.
Отказ доставки лога после COMMIT не превращает committed operation в
rejected и не запускает повторное применение; outcome восстанавливается
по operation storage. Логирование не обещает exactly-once delivery записи.

### DAG execution — DAG-TYPING-1 A2.5

- Logger: `app.engine.dag`; domain `engine`, service `dagExecution`, профиль `server`; файл `backend/logs/engine/dagExecution.log`.
- Producer: единый `backend/app/application/engine/diagnostics/dagLog.py`, owner engine runtime. Координатор формирует итоговые события; причины/поля — `docs/tz_engine_node_context.md` §10.
- Регистрация LogConsumer.DAG в каталоге `ROUTES` файла `backend/app/core/logging/routes.py`; тот же JsonLogFormatter и router, без нового handler/собственного файла на ноду. L1–L8 действуют без исключений.
- Статус: route, server allowlist и emitter реализованы и проверены 2026-10-31 (DAG-TYPING-1 A2.5). Используются прежние router/JsonLogFormatter, без нового handler. Payload Input/Output/error POJO в лог не копируется; обязательная диагностика отмены доступна без DEBUG. Production handoff runtime — GEN-DAG-1.

### Существующие консьюмеры

Шаг wilderness 9c (согласовано 2026-10-18): `regions/regionStateLog.py`
эмитит WARNING `region_state | overlap_rerank_deferred | world_uid=… region_uid=… neighbors=…`.
Маршрут общего фасада: `app.application.worldData.regions.regionStateLog` →
домен `region_state`, сервис `regionStateLog`, файл
`logs/region_state/regionStateLog.log` (server). JSON содержит `activity`,
`world_uid`, `region_uid`, отсортированный список `neighbors`. Один record на
изменившийся UID за batch-запрос, не на клетку. Событие file-only по L8;
отдельных handlers/форматтеров у доменного хелпера нет. Семантика —
`tz_world_pack_storage.md` § Region state overlay.

Писатель: **server** = процесс uvicorn (`npm run backend` / `dev`). **script** = `backend/scripts/*.py`.

| Домен | Сервис | Файл (target) | Процесс | События (SoT) | Код (ориентир) |
|---|---|---|---|---|---|
| `http` | `api` | `logs/http/api.log` | server | `request_start` / `request_end` | [`logMiddleware.py`](../backend/app/core/logMiddleware.py) |
| `pack` | `packBakeLog` | `logs/pack/packBakeLog.log` | server | heartbeat light/full/detailed, chunk done, **C11/C23 stage seconds**, **sidecar / R44 validate 0/N / T-3c emit start-done** (консоль). **ERROR** uid не pin `locations_index` (skip, не abort). Не замена R44 ERROR | [`packBakeLog.py`](../backend/app/application/worldData/pack/bake/packBakeLog.py) · [`tz_world_pack_storage.md`](./tz_world_pack_storage.md) · [`tz_map_light_bake.md`](./tz_map_light_bake.md) · SQL persist — [`tz_terrain_relief.md`](./tz_terrain_relief.md) § SQL catalog · C11 keys — [`tz_settlement_outdoor.md`](./tz_settlement_outdoor.md) · [`tz_application_performance.md`](./tz_application_performance.md) |
| `pack` | `packDetailedBake` | `logs/pack/packDetailedBake.log` | server | detailed scope / refine tiles | [`packDetailedBakeOrchestrator.py`](../backend/app/application/worldData/pack/bake/packDetailedBakeOrchestrator.py) · [`tz_terrain_relief_v1_superseded.md`](./tz_terrain_relief_v1_superseded.md) (R36v/w) |
| `pack` | `fineChunkPersist` | `logs/pack/fineChunkPersist.log` | server | persist chunk / sidecar; **не** подмена R44 | [`fineChunkPersist.py`](../backend/app/application/worldData/pack/refine/fineChunkPersist.py) |
| `relief` | `reliefLog` | `logs/relief/reliefLog.log` | server | R8 INFO/DEBUG/WARNING generate | [`relief/log/log.py`](../backend/app/application/worldData/generators/terrain/relief/log/log.py) · [`tz_terrain_relief_v1_superseded.md`](./tz_terrain_relief_v1_superseded.md) § Logging (R8) |
| `relief` | `gradeCellRays` | `logs/relief/gradeCellRays.log` | server | R44 `grade_cell_empty_ray` (`slots` / `open` 3×3) | [`gradeCellRays.py`](../backend/app/application/worldData/generators/terrain/relief/validate/gradeCellRays.py) · [`gradeCellSlotValidate.py`](../backend/app/application/worldData/generators/terrain/relief/validate/gradeCellSlotValidate.py) · [`tz_terrain_relief_consume.md`](./tz_terrain_relief_consume.md) |
| `render` | `dumpLog` | `logs/render/dumpLog.log` | **script** | debug ASCII dump **для разработчика** (не мастер мира, не игрок, не DAG); ticks, heartbeat ≤5 с | [`dumpLog.py`](../backend/app/application/worldData/render/dumpLog.py) · [`tz_pack_ascii_render.md`](./tz_pack_ascii_render.md) |
| `terrain` | `terrainParallelLog` | `logs/terrain/terrainParallelLog.log` | server | parallel column / worker ticks | [`terrainParallelLog.py`](../backend/app/application/worldData/terrainParallelLog.py) · [`tz_terrain_generation.md`](./tz_terrain_generation.md) |
| `climate` | `climateLog` | `logs/climate/climateLog.log` | server | pass INFO, `warn_once` / `debug_once` | [`loggingHelpers.py`](../backend/app/application/worldData/generators/climate/loggingHelpers.py) · [`tz_climate.md`](./tz_climate.md) § Логирование |
| `jsonValidation` | `resolve` | `logs/jsonValidation/resolve.log` | server | DefaultOnWire / RegistryKey fallback (`json_validation \| …`); settlement size miss → medium; **LOC-T-3** settlement volume ERROR | [`resolve.py`](../backend/app/application/jsonValidation/resolve.py) · [`settlementSizeResolve.py`](../backend/app/application/jsonValidation/settlementSizeResolve.py) · [`tz_json_validation.md`](./tz_json_validation.md) §0 RegistryKey · [`tz_locations.md`](./tz_locations.md) **LOC-T-3** |
| `settlement` | `settlementAssembler` | `logs/settlement/settlementAssembler.log` | server | C22 packing DEBUG/INFO/WARNING; шторм `fit` только файл (L8) | ⬜ хелпер по образцу relief `log.py` / climate `loggingHelpers` · [connections](./tz_structure_connections.md) §5.1.3 «Debug packing» |
| `structure` | `headroom` | `logs/structure/headroom.log` | server | post-gen ERROR, не abort | [`tz_building_generator.md`](./tz_building_generator.md) § Headroom (образец R44) |
| `cascade` | `cascadeLog` | `logs/cascade/cascadeLog.log` | server | `scope_resolve` DEBUG на границу scope (parent/child по provenance на параметр); `default_applied` — WARNING для `REGISTRY_MEDIAN` (один раз на цепочку), DEBUG для canonical-дефолтов | [`cascadeLog.py`](../backend/app/application/worldData/context/cascadeLog.py) · [`contextResolver.py`](../backend/app/application/worldData/context/contextResolver.py) · [`tz_cascade_context.md`](./tz_cascade_context.md) §4 |
| `core` | `runtime` | `logs/core/runtime.log` | server | явно зарегистрированные runtime-источники, включая uvicorn и fastapi | [`loggingConfig.py`](../backend/app/core/loggingConfig.py) |
| `script` | `detailedBake` | `logs/script/detailedBake.log` | script | poll HTTP, summary скрипта | [`detailed_bake.py`](../backend/scripts/detailed_bake.py) |
| `script` | `lightAndFullBake` | `logs/script/lightAndFullBake.log` | script | light→full smoke | [`light_and_full_bake.py`](../backend/scripts/light_and_full_bake.py) |
| `script` | `initializeWorld` | `logs/script/initializeWorld.log` | script | import + bake harness | [`initialize_world.py`](../backend/scripts/initialize_world.py) |
| `script` | `entryBgRefine` | `logs/script/entryBgRefine.log` | script | entry refine smoke | [`entry_bg_refine.py`](../backend/scripts/entry_bg_refine.py) |
| `script` | `renderMaps` | `logs/script/renderMaps.log` | script | CLI dump без bake | [`render_maps.py`](../backend/scripts/render_maps.py) |

Позже тот же ключ (не `app.log`): `hydrology`, `chat`, прочие `script/{stem}`. `settlement` / `settlementAssembler` — в каталоге (C22).

## Маршрут

Домен получает стандартный logger через `get_consumer_logger(LogConsumer.…)`. Каталог задаёт файл и участие в transcript для каждого зарегистрированного потребителя. Поле `logger` в JSON содержит стабильное имя. Точные имена, внешние пространства имён и назначения перечислены в [контрактах](../backend/app/core/logging/contracts.py) и [каталоге](../backend/app/core/logging/routes.py).

`route_for(logger_name) -> LogRoute` поднимает `UnknownLogConsumerError` с исходным именем, если регистрация отсутствует. Эта проверка выполняется до открытия файла в обоих профилях. Сервер пишет в `route.sink` при `server_enabled=True`. Внешние библиотеки и прежние runtime producers имеют явные регистрации в CORE_RUNTIME. Флаг `generation_enabled` применяется внутри текущего world scope.

Relief передаёт событие R44 в RELIEF_RAYS. В профиле script запись идёт в `logs/script/{stem}.log`, для RENDER_DUMP дополнительно в `logs/render/dumpLog.log`. Уровни задаются по текущему logger name с обычным наследованием stdlib.

## Запрещено

- Общий `backend/logs/app.log` на uvicorn **и** скрипт
- Скрипт пишет `relief/*` или `pack/*` (R44/bake — сервер)
- `dumpLog` в файле, который держит uvicorn
- Rollover одного файла из двух PID
- Вторые `print`/tee вместо фасада
- `StreamHandler` на root без очереди как единственный stdout bake-потока
- Per-cell / per-system storm на консоль (`grade_cell_empty_ray`, `grade_system_create`) вместо heartbeat

## Код (ориентиры)

Разделение существующего механизма (согласованный план logging-facade-decomposition): `core/loggingConfig.py` сохраняет setup/lifecycle; `core/logging/context.py` владеет единственным request_id ContextVar; `formatting.py` — JSON; `routes.py` — каталог и выбор sink; `fileRouter.py` — пути/ротация; `console.py` — drop-queue и listener. Направление импортов идёт от composition к этим компонентам, без обратных импортов и compatibility re-export. Доменные adapters и generation transcript используют прежний механизм. Перенос не меняет L1–L8.

| Модуль | Роль |
|---|---|
| [`loggingConfig.py`](../backend/app/core/loggingConfig.py) | process setup/lifecycle |
| [`logging/routes.py`](../backend/app/core/logging/routes.py) | каталог и выбор sink |
| [`logging/context.py`](../backend/app/core/logging/context.py), [`formatting.py`](../backend/app/core/logging/formatting.py) | единый request_id и JSON formatter |
| [`logging/fileRouter.py`](../backend/app/core/logging/fileRouter.py) | файловая доставка, пути и ротация |
| [`logging/console.py`](../backend/app/core/logging/console.py) | drop-queue, фильтр и listener |
| [`generationLogging.py`](../backend/app/core/generationLogging.py) | транскрипт `bake-{mode}` |
| [`logMiddleware.py`](../backend/app/core/logMiddleware.py) | `http` / `api` |

---

## Связанные документы

- [Stable logging consumers — D1](../.cursor/plans/logging-stable-consumers-done.md) — реализация типизированной маршрутизации, результаты проверок и граница проверки настроек окружения.

- [Разделение logging facade по ответственностям — DONE](../.cursor/plans/logging-facade-decomposition-done.md) — реализовано, предъявлено на приёмку; 105 тестов, те же 6 внешних baseline ошибок, typing чистый. Без legacy re-export и изменения runtime.

| Документ | Консьюмеры / зачем |
|---|---|
| [`tz_terrain_relief.md`](./tz_terrain_relief.md) | generate SoT; SQL catalog / `packBakeLog` persist; sink `reliefLog` — архив v1 R8 |
| [`tz_terrain_relief_v1_superseded.md`](./tz_terrain_relief_v1_superseded.md) | detailed bake / R8 |
| [`tz_terrain_relief_consume.md`](./tz_terrain_relief_consume.md) | `relief` / `gradeCellRays` (ERROR слотов; код R44 interim) |
| [`tz_pack_ascii_render.md`](./tz_pack_ascii_render.md) | `render` / `dumpLog` |
| [`tz_world_pack_storage.md`](./tz_world_pack_storage.md) | `pack` / транскрипт `generation/{uid}` |
| [`tz_map_light_bake.md`](./tz_map_light_bake.md) | `pack` / `packBakeLog` (light compose) |
| [`tz_terrain_generation.md`](./tz_terrain_generation.md) | `terrain` / `terrainParallelLog` |
| [`tz_json_validation.md`](./tz_json_validation.md) | `jsonValidation` / `resolve` (DefaultOnWire, size fallback; **LOC-T-3** uid/size/z) |
| [`tz_climate.md`](./tz_climate.md) | `climate` / `climateLog` |
| [`tz_structure_connections.md`](./tz_structure_connections.md) | `settlement` / `settlementAssembler` (C22 packing) |
| [`tz_building_generator.md`](./tz_building_generator.md) | `structure` / `headroom` |
| [`tz_world_generation_dag.md`](./tz_world_generation_dag.md) | три входа; скрипты только HTTP |
| [`tz_lighting.md`](./tz_lighting.md) | **не** этот файл (освещение мира) |

---

## История

| Дата | Изменение |
|---|---|
| 2026-10-05 | Консьюмер `cascade` / `cascadeLog`: `scope_resolve` DEBUG на `extend()`, `default_applied` WARNING (`REGISTRY_MEDIAN`, один раз на цепочку) — эмиссия в движке, не в POJO-политике. |
| 2026-09-20 | `packBakeLog` ERROR: C11 / location L2, uid не pin `locations_index` (`reason=not_in_locations_index`); skip, не abort. |
| 2026-09-13 | `packBakeLog`: heartbeat C11/C23 (`settlement_c11_*`, `settlement_topology_*`). |
| 2026-09-07 | Консьюмер `jsonValidation` / `resolve`: DefaultOnWire + settlement size fallback (`medium`). |
| 2026-09-01 | Консьюмер `settlement` / `settlementAssembler`: C22 packing. События — connections §5.1.3 «Debug packing». |
| 2026-08-22 | SoT sinks: `{domain}/{service}.log`; один писатель на файл; каталог консьюмеров; скрипт ≠ серверный `app.log`. |
| 2026-08-22 | unmatched server → `core`/`runtime` (не `app.log`). |
| 2026-08-23 | **L7/L8:** консоль не блокирует bake (drop-queue); storm R44 / T-3c — файл; heartbeat sidecar/validate/emit — `packBakeLog` на консоль. |


### Artifact emitter — уточнение ответственности 2026-11-06

В [Artifacts D1](../.cursor/plans/world-domain-artifacts-cancel-gc-d1.md#14-freeze-и-атомарные-шаги-после-ревью) producer activity/severity — доменный emitter ArtifactLifecycleLog: emit_gc_failure фиксирует GC_FAILED/ERROR и проекцию ArtifactGcFailure. GC service определяет факт и момент эмиссии, не собирает ArtifactLogRecord и не передаёт произвольный LogLevel. create_gc_failure не логирует. Emit валидирует контракт до best-effort sink boundary; исходный exception передаётся через exc_info существующему formatter. Это уточнение целевого контракта; реализация route/transcript и локальный EC-I0 проверяются в D2-3, route/transcript registration выполнена подготовительным срезом; полная проверка нового GC emitter и локальный I0 остаются открыты.

## Physics settings: подготовительный I0 (2026-11-07)

Input operations Physics используют единственный emitter `app.consumer.physics_settings` в `application/physics/settings/reporting.py`. Общий facade маршрутизирует LogConsumer.PHYSICS_SETTINGS в `physics/physicsLog`, файл `logs/physics/physicsLog.log` (server sink). Prefix включён в existing generation transcript только внутри активного world scope. Settings input больше не emit через `jsonValidation/resolve`; общий ResolveReport и его continuation identity сохранены.

Runtime fallback пишет WARNING с concrete cause и selected default; structural refusal — distinct причины вызова. Validation/collect_only не emit; обычный успех/missing/zero тихие. Без raw input: явные code/type/location/path, gravity arguments и selected default. Request correlation — existing request_id; DAG execution correlation и production binding этим срезом не вводятся. DAG lifecycle event остаётся отдельным фактом. Доставка одного события в sink и transcript не означает повтор producer emit или exactly-once delivery.


### Physics: подготовительный I0 (§P3.22)

`app.consumer.physics_settings` → `physics/physicsLog`: server file
`backend/logs/physics/physicsLog.log`. Prefix входит в world-scoped transcript
allowlist; scope открывает caller. Script profile сохраняет script sink.
Handlers, formatter и request_id принадлежат общему logging facade.

Единственный producer — settings input через `physics/settings/reporting.py`.
Adapter сохраняет ResolveReport; новая continuation даёт один WARNING с concrete
F01 и selected default из F07. Blocking причины дедуплицируются внутри вызова,
не между вызовами. Validation/collect_only собирают facts без emit. Raw input
не пишется. Параллельной эмиссии этих причин в jsonValidation нет.
DAG lifecycle остаётся отдельным фактом существующего владельца.
Это подготовительная проверка, не production activation или execution binding.
