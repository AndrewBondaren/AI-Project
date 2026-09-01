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

| Слой | Путь | Зачем |
|---|---|---|
| **Поток консьюмера** | `backend/logs/{domain}/{service}.log` | стабильный файл сервиса |
| **Транскрипт прогона** | `backend/logs/generation/{world_uid}/bake-{mode}-{stamp}.log` + `bake-{mode}-latest.log` | склейка одного bake/dump; не делит rollover с `{domain}/{service}` |

Транскрипт вешает `generation_world_log` на время job (allowlist logger names). Это **копия** в run-файл, не общий `app.log`.

## Каталог консьюмеров

Писатель: **server** = процесс uvicorn (`npm run backend` / `dev`). **script** = `backend/scripts/*.py`.

| Домен | Сервис | Файл (target) | Процесс | События (SoT) | Код (ориентир) |
|---|---|---|---|---|---|
| `http` | `api` | `logs/http/api.log` | server | `request_start` / `request_end` | [`logMiddleware.py`](../backend/app/core/logMiddleware.py) |
| `pack` | `packBakeLog` | `logs/pack/packBakeLog.log` | server | heartbeat light/full/detailed, chunk done, **sidecar / R44 validate 0/N / T-3c emit start-done** (консоль). Не замена R44 ERROR | [`packBakeLog.py`](../backend/app/application/worldData/pack/bake/packBakeLog.py) · [`tz_world_pack_storage.md`](./tz_world_pack_storage.md) · [`tz_map_light_bake.md`](./tz_map_light_bake.md) · SQL persist — [`tz_terrain_relief.md`](./tz_terrain_relief.md) § SQL catalog |
| `pack` | `packDetailedBake` | `logs/pack/packDetailedBake.log` | server | detailed scope / refine tiles | [`packDetailedBakeOrchestrator.py`](../backend/app/application/worldData/pack/bake/packDetailedBakeOrchestrator.py) · [`tz_terrain_relief_v1_superseded.md`](./tz_terrain_relief_v1_superseded.md) (R36v/w) |
| `pack` | `fineChunkPersist` | `logs/pack/fineChunkPersist.log` | server | persist chunk / sidecar; **не** подмена R44 | [`fineChunkPersist.py`](../backend/app/application/worldData/pack/refine/fineChunkPersist.py) |
| `relief` | `reliefLog` | `logs/relief/reliefLog.log` | server | R8 INFO/DEBUG/WARNING generate | [`relief/log/log.py`](../backend/app/application/worldData/generators/terrain/relief/log/log.py) · [`tz_terrain_relief_v1_superseded.md`](./tz_terrain_relief_v1_superseded.md) § Logging (R8) |
| `relief` | `gradeCellRays` | `logs/relief/gradeCellRays.log` | server | R44 `grade_cell_empty_ray` (`slots` / `open` 3×3) | [`gradeCellRays.py`](../backend/app/application/worldData/generators/terrain/relief/validate/gradeCellRays.py) · [`gradeCellSlotValidate.py`](../backend/app/application/worldData/generators/terrain/relief/validate/gradeCellSlotValidate.py) · [`tz_terrain_relief_consume.md`](./tz_terrain_relief_consume.md) |
| `render` | `dumpLog` | `logs/render/dumpLog.log` | **script** | debug ASCII dump **для разработчика** (не мастер мира, не игрок, не DAG); ticks, heartbeat ≤5 с | [`dumpLog.py`](../backend/app/application/worldData/render/dumpLog.py) · [`tz_pack_ascii_render.md`](./tz_pack_ascii_render.md) |
| `terrain` | `terrainParallelLog` | `logs/terrain/terrainParallelLog.log` | server | parallel column / worker ticks | [`terrainParallelLog.py`](../backend/app/application/worldData/terrainParallelLog.py) · [`tz_terrain_generation.md`](./tz_terrain_generation.md) |
| `climate` | `climateLog` | `logs/climate/climateLog.log` | server | pass INFO, `warn_once` / `debug_once` | [`loggingHelpers.py`](../backend/app/application/worldData/generators/climate/loggingHelpers.py) · [`tz_climate.md`](./tz_climate.md) § Логирование |
| `settlement` | `settlementAssembler` | `logs/settlement/settlementAssembler.log` | server | C22 packing DEBUG/INFO/WARNING; шторм `fit` только файл (L8) | ⬜ хелпер по образцу relief `log.py` / climate `loggingHelpers` · [connections](./tz_structure_connections.md) §5.1.3 «Debug packing» |
| `structure` | `headroom` | `logs/structure/headroom.log` | server | post-gen ERROR, не abort | [`tz_building_generator.md`](./tz_building_generator.md) § Headroom (образец R44) |
| `core` | `runtime` | `logs/core/runtime.log` | server | непойманные server-логгеры (uvicorn / fastapi / …); **не** `app.log` | [`loggingConfig.py`](../backend/app/core/loggingConfig.py) |
| `script` | `detailedBake` | `logs/script/detailedBake.log` | script | poll HTTP, summary скрипта | [`detailed_bake.py`](../backend/scripts/detailed_bake.py) |
| `script` | `lightAndFullBake` | `logs/script/lightAndFullBake.log` | script | light→full smoke | [`light_and_full_bake.py`](../backend/scripts/light_and_full_bake.py) |
| `script` | `initializeWorld` | `logs/script/initializeWorld.log` | script | import + bake harness | [`initialize_world.py`](../backend/scripts/initialize_world.py) |
| `script` | `entryBgRefine` | `logs/script/entryBgRefine.log` | script | entry refine smoke | [`entry_bg_refine.py`](../backend/scripts/entry_bg_refine.py) |
| `script` | `renderMaps` | `logs/script/renderMaps.log` | script | CLI dump без bake | [`render_maps.py`](../backend/scripts/render_maps.py) |

Позже тот же ключ (не `app.log`): `hydrology`, `chat`, `engine`, прочие `script/{stem}`. `settlement` / `settlementAssembler` — в каталоге (C22).

## Маршрут

Фасад смотрит имя logger / extra → `(domain, service)` → handler файла.

| Префикс / вход | Домен | Сервис |
|---|---|---|
| `http` | `http` | `api` |
| `app.relief` | `relief` | `reliefLog`; R44 event → `gradeCellRays` |
| `app.application.worldData.pack.bake.packBakeLog` | `pack` | `packBakeLog` |
| `app.application.worldData.pack.bake.packDetailedBakeOrchestrator` | `pack` | `packDetailedBake` |
| `app.application.worldData.pack.refine` | `pack` | `fineChunkPersist` (persist/validate call site) |
| `app.application.worldData.render.dumpLog` | `render` | `dumpLog` |
| `app.application.worldData.terrainParallelLog` | `terrain` | `terrainParallelLog` |
| `app.application.worldData.generators.climate` / climate assembler | `climate` | `climateLog` |
| `app.application.worldData.generators.assemblers` (кроме `climateAssembler` → `climate`) | `settlement` | `settlementAssembler` |
| `backend/scripts/{stem}.py` после `ensure_script_logging` | `script` | camelCase stem |
| непойманный (профиль server) | `core` | `runtime` |

`ensure_script_logging` **не** открывает `app.log`. Только консоль процесса + `logs/script/{service}.log`. Если в том же PID идёт dump — ещё `logs/render/dumpLog.log`. Непойманные server-логгеры → `core` / `runtime`, не `app.log`.

## Запрещено

- Общий `backend/logs/app.log` на uvicorn **и** скрипт
- Скрипт пишет `relief/*` или `pack/*` (R44/bake — сервер)
- `dumpLog` в файле, который держит uvicorn
- Rollover одного файла из двух PID
- Вторые `print`/tee вместо фасада
- `StreamHandler` на root без очереди как единственный stdout bake-потока
- Per-cell / per-system storm на консоль (`grade_cell_empty_ray`, `grade_system_create`) вместо heartbeat

## Код (ориентиры)

| Модуль | Роль |
|---|---|
| [`loggingConfig.py`](../backend/app/core/loggingConfig.py) | фасад, JSON, handlers по ключу |
| [`generationLogging.py`](../backend/app/core/generationLogging.py) | транскрипт `bake-{mode}` |
| [`logMiddleware.py`](../backend/app/core/logMiddleware.py) | `http` / `api` |

---

## Связанные документы

| Документ | Консьюмеры / зачем |
|---|---|
| [`tz_terrain_relief.md`](./tz_terrain_relief.md) | generate SoT; SQL catalog / `packBakeLog` persist; sink `reliefLog` — архив v1 R8 |
| [`tz_terrain_relief_v1_superseded.md`](./tz_terrain_relief_v1_superseded.md) | detailed bake / R8 |
| [`tz_terrain_relief_consume.md`](./tz_terrain_relief_consume.md) | `relief` / `gradeCellRays` (ERROR слотов; код R44 interim) |
| [`tz_pack_ascii_render.md`](./tz_pack_ascii_render.md) | `render` / `dumpLog` |
| [`tz_world_pack_storage.md`](./tz_world_pack_storage.md) | `pack` / транскрипт `generation/{uid}` |
| [`tz_map_light_bake.md`](./tz_map_light_bake.md) | `pack` / `packBakeLog` (light compose) |
| [`tz_terrain_generation.md`](./tz_terrain_generation.md) | `terrain` / `terrainParallelLog` |
| [`tz_climate.md`](./tz_climate.md) | `climate` / `climateLog` |
| [`tz_structure_connections.md`](./tz_structure_connections.md) | `settlement` / `settlementAssembler` (C22 packing) |
| [`tz_building_generator.md`](./tz_building_generator.md) | `structure` / `headroom` |
| [`tz_world_generation_dag.md`](./tz_world_generation_dag.md) | три входа; скрипты только HTTP |
| [`tz_lighting.md`](./tz_lighting.md) | **не** этот файл (освещение мира) |

---

## История

| Дата | Изменение |
|---|---|
| 2026-09-01 | Консьюмер `settlement` / `settlementAssembler`: C22 packing. События — connections §5.1.3 «Debug packing». |
| 2026-08-22 | SoT sinks: `{domain}/{service}.log`; один писатель на файл; каталог консьюмеров; скрипт ≠ серверный `app.log`. |
| 2026-08-22 | unmatched server → `core`/`runtime` (не `app.log`). |
| 2026-08-23 | **L7/L8:** консоль не блокирует bake (drop-queue); storm R44 / T-3c — файл; heartbeat sidecar/validate/emit — `packBakeLog` на консоль. |
