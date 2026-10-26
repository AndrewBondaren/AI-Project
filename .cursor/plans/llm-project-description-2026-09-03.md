# AI RPG Platform — описание проекта для другой LLM

**Дата среза:** 2026-09-03  
**Репозиторий:** `E:/AI Project` (git root `2026-05-09`, HEAD `0342edb` `city tz` 2026-09-02, ~316 коммитов, один автор).  
**Назначение этого файла:** самодостаточный onboarding. Прочитать **целиком** до правок кода. Не заменяет доменные ТЗ — после ориентации открывать SoT из §17.

**Рядом, другая задача:** оценка/скоры — [`.cursor/plans/project-characterization-2026-09-03.md`](./project-characterization-2026-09-03.md). Этот документ — *что это и как устроено*, не *как ставить оценку*.

**Живой снимок кода (частично устарел, v1.3 2026-08-17):** [`docs/tz_project_snapshot.md`](../../docs/tz_project_snapshot.md). При расхождении чисел — characterization 2026-09-03.

---

## 0. Как себя вести в этом репозитории

Ты ассистент в репозитории **платформы AI RPG**, не чат-фронтенда с lorebook.

| Делай | Не делай |
|---|---|
| Читать SoT в `docs/tz_*.md` по домену | Выдумывать геометрию, `system_*` ключи, дефолты, которые уже есть в Pydantic |
| Генераторы = pure materialize | Сбор LLM prompt / `display_name` для чата / HTTP внутри генератора |
| API = тонкий HTTP | Второй движок в `api/routes/` |
| `dataModel/` = единственный контракт полей | Литералы `_DEFAULT_*`, `dict.get("connection_type")` вместо POJO |
| Массовый SQL через `app.db.bulkSql` | Свой `executemany` и свой размер пачки |
| SQL-схема только `0001_initial.sql` + sync dataclass | Файлы `0002_*.sql` |
| Код — только если мастер явно сказал «делай / напиши / имплементируй» | Код «заодно» после «прочитай ТЗ» или согласия с планом |
| DAG-ноды `application/engine/nodes/` — **не трогать** | Wiring bake/outdoor в engine до снятия gate мастером |

**Осознанные «нет» продукта (не чинить по умолчанию):**

- нет LLM-генерации геометрии (идея R-1 **rejected**);
- нет RAG как основной памяти мира (R-2 deferred);
- нет LLM на каждого ambient NPC / AgentCity (R-3, R-5 rejected);
- **нет** interim `scene_narration` / vertical slice игрока, пока контракт сцены и pack нестабилен;
- **нет** C22 packing-кода, пока мастер не сказал «делай».

Не стартовать backend (`python start.py`, `uvicorn`, `npm run backend`) — это делает мастер.

---

## 1. Что это за продукт

**AI RPG Platform** — симуляционная платформа, не «игра-чат».

Мастер мира задаёт **правила** (статы, формулы, реестры, terrain, шаблоны зданий) JSON-импортом (позже — тот же validator в UI редактора). Движок **симулирует** мир. LLM — **мастер игры по этим правилам**: предлагает события и прозу, не является источником истины.

Аналогия в репозитории: **Foundry VTT + AI-GM + процедурный геометрический мир**.

| Роль | Что делает | Что видит |
|---|---|---|
| **Мастер мира** | Реестры, импорт JSON, bake/debug, баланс, выпуск пресета | N+1, `system_*`, validator, pack |
| **Игрок** | Выбрать мир → персонаж → чат с AI-GM | Narrative и тонкий UI. Реестры и DAG не видит |

**Тезис истины:** движок + геометрия (SQLite + immutable **World Pack**) — source of truth. LLM **рендерит факты**, не придумывает клетки, uid и ключи движка.

Цепочка (целевая): LLM propose structured JSON → validate → engine commit. Сейчас Apply патчей LLM **не пишет мир** (см. §7.4).

**Ниша 2026:** validation-first GM (как Orchestrated Reality PDVA, MnesOS, LlamaBrain, Project Lunar) **плюс** DF/Civ-класс world compiler (terrain / relief grade / hydrology / settlement / pack bake), которого у этих пиров нет. Chat-as-world (SillyTavern, AI Dungeon) — другой класс: там модель *и есть* мир.

---

## 2. Стек и запуск

| Слой | Технология |
|---|---|
| Backend | Python 3.14, FastAPI, aiosqlite, SSE |
| Frontend | React 19, Vite 8, Electron 42 или браузер, CSS Modules, feature-slices |
| LLM | `LLMRouter`: локальный Qwen, OpenAI, Anthropic |
| БД | SQLite WAL, **одна** миграция `backend/app/db/migrations/0001_initial.sql` |
| Dev | `npm run dev` → backend `:8000` + frontend `:5173` |

После правки `0001_initial.sql` локальную БД **пересоздают** (drop + restart), не ALTER-migration. `validate_schema` на старте сверяет dataclass-модели с SQL.

Игрок: `/` сессии → `/new` мир → `/new/:worldId` персонаж → `/chat/:sessionId` SSE. `/settings/world` — **placeholder** редактора. Карты как продуктового UI нет (ASCII dump — debug разработчика).

---

## 3. Карта репозитория

```
docs/tz_*.md                          доменные ТЗ (продукт; SoT алгоритмов)
docs/project_data_storage_tz.md       видение + system_/display_ + N+1 + сущности
.cursor/plans/                        планы агента (не класть в docs/)
.cursor/rules/*.mdc                   правила агента (слои, POJO, bulk SQL, DAG gate)

backend/app/
  api/routes/                         только HTTP
  application/chat/                   ход, pending, crash recovery (~96 строк)
  application/engine/                 DAG runtime (compile / phase / repair / replan)
  application/worldData/
    generators/                       pure library (terrain, relief, hydro, settlement…)
    pack/                             bake / refine / read immutable pack
    settlementOutdoor/                эталон города на pack + SQL-дерево
  application/jsonValidation/         import + runtime resolve (POJO-first)
  dataModel/                          Pydantic — единственный контракт полей
  db/                                 repos, models, 0001_initial.sql, bulkSql.py
  core/                               Container, config, logging
  dsl/                                промпты LLM-нод (сейчас тонкие)

frontend/src/features/{session,chat,settings}
fixtures/                             world_test*.json, seed, characters
relief_templates/                     пакеты шаблонов grade (не смешивать с buildings)
structures_templates/                 конвенция для зданий (отдельный корень)
```

**Две «продукта» в одном репо (это норма, не баг):** (1) world compiler + pack; (2) validation-first GM. Связка задумана так: session start **читает pack**, который bake уже умеет писать. Сегодня связки нет.

---

## 4. Контракт данных

### 4.1 `system_*` / `display_*`

SoT: [`docs/project_data_storage_tz.md`](../../docs/project_data_storage_tz.md).

| Префикс | Кто | Пример |
|---|---|---|
| `system_*` | движок, формулы, refs, валидация | `system_terrain`, `system_uid` |
| `display_*` | UI и проза LLM | `display_name`, `display_terrain` |

Движок сравнивает `system_*`. LLM получает `display_*` и lore, **не угадывает** ключи.

### 4.2 N+1 — два вида (не путать)

1. **Реестры мира** — новый *тип* в `worlds.*_registry` (terrain, materials, district templates, …).
2. **Поля экземпляра** — суффиксы `_1`, `_2` на сущности.

Аудитория N+1 — **мастер**, не игрок. Один validator на JSON-импорт и будущий UI редактора.

### 4.3 `dataModel/` — SoT полей

Pydantic в `backend/app/dataModel/` — единственный источник builtin-полей, defaults, wire-ключей. Resolve (world + fallback + merge) **поверх** модели.

Запрещено дублировать `Field(default=…)` литералом в генераторе, DAG, `db/`, route. Читать `entry_for()`, `canonical_defaults()`, `fallback()`, типизированные поля.

Новое builtin-значение → сначала POJO (+ SQL/dataclass если колонка), потом тонкий потребитель.

### 4.4 Слои хранения мира (целевые)

| Слой | Что | Мутация |
|---|---|---|
| **World Pack** (immutable files, zstd/mmap) | L0 карта, L2 fine terrain/grades, **city-structure** эталон города | master bake / outdoor materialize |
| **SQLite OLTP** | сессии, персонажи, `named_locations` (имена/дерево), граф `connection_*`, сообщения | CRUD + generate persist |
| **Patch Store** | ход игрока: взрыв, пристройка, `terrain_delta` | каждый ход |
| **`map_cells`** | legacy / interim OLTP-клетки | не целевой cold-load |

**Почему pack обязателен:** fine grid 1 м × макро-тайл ~3000 м → ~9M колонок/тайл. INSERT в SQLite на cold load — часы. Цель: attach pack ≤ 5 мин; **первый ответ LLM ≤ 30 s p95** от spawn, **не** ждать полный L2. Пока fine chunk нет — механика/нарратив на **L0 + L1 + patches**. Blocking «генерация мира 45%» дольше 30 s на gameplay path — **запрещён**.

LOD = *что* печь. Pack = *как* хранить. LOD без pack отвергнут.

Authored outdoor city → pack слой `locations/l.{uid}.settlement.zst`, **не** Patch Store и не occupancy-flood в `map_cells`. SoT: [`docs/tz_settlement_outdoor.md`](../../docs/tz_settlement_outdoor.md) **C1**.

### 4.5 Карта и локации

Весь мир — единое 3D, 1 клетка = 1 м, `z=0` море. LLM **сырую матрицу не получает** — именованные локации и отфильтрованный контекст.

| Слой клетки | Поле | Когда |
|---|---|---|
| Рельеф/биом outdoor | `system_terrain` | `building_element` null |
| Стройка indoor | `system_building_element` | `terrain` null |

Иерархия имён (SQL): settlement → district → building. **Участок (`AreaSlot`) — не** `location_type` и не вся сцена. `SessionScene.location_uid` — **якорь** (где числится персонаж), не bounding box симуляции (**C18**). Карта при входе в здание: оболочка здания **плюс** уже загруженное рядом (улица, соседи). Радиус событий — отдельное ТЗ.

Технический шов pack (ребро тайла) **не** граница локации. Город на шве — норма (**C29** / WP-19).

---

## 5. Границы слоёв (нарушение = антипаттерн)

```
Игрок / мастер HTTP
        ↓
api/routes          validate → service → DTO. Не generate, не LLM payload, не второй engine.
        ↓
application/chat    ход, pending, crash recovery. Не сцена.
        ↓
application/engine  compile DAG, phases, repair, patches. Ноды зовут library + persist.
        ↓
worldData           orchestrators persist + pack I/O
        ↓
generators/         (World, …) → layout / cells / graph. Без async, SQL, HTTP, ExecutionState.
        ↓
dataModel + db
```

**Три разрешённых caller одной library** ([`docs/tz_world_generation_dag.md`](../../docs/tz_world_generation_dag.md)):

1. Engine DAG — **целевой** production; bake/outdoor **ещё не** caller (gate).
2. Debug HTTP — **текущий**: `map.py` bake/refine, `locations.py` `generate-settlement`.
3. Unit tests — in-process, без HTTP.

Debug harness **постоянный** (не временный костыль): тонкая оболочка над тем же orchestrator, который потом вызовет нода.

---

## 6. Backend по слоям — факт кода

### 6.1 API `/api`

Игровой контур: sessions CRUD; `POST /chat` и `POST /chat/stream` (SSE: node status, thinking, result, error, cancelled); cancel; history/pending; LLM settings.

Мастер: worlds import/export; locations + **`POST …/generate-settlement`** (outdoor etalon); characters; races/perks; map pack bake `light|full|detailed`, refine-from-entry, render; connections; seed; relief templates; debug generate-structure.

`ChatRequest`: `session_id`, `message`, provider/model, `request_id`, `resume`, опционально `task_type` (минует intent).

### 6.2 Frontend

~1.5k строк. Умеет: список сессий, выбор мира/персонажа, стрим статуса нод, cancel. Не умеет: редактор мира, карта продукта, реестры мастера. Electron-специфика только в `platform/fileSystem.js`.

---

## 7. Движок (GM machine)

SoT flow: [`docs/tz_engine_flow.md`](../../docs/tz_engine_flow.md). Код: `backend/app/application/engine/`. **В окне авг–сен 2026 файлы engine не менялись** (gate). Машина закрыта, **контентный граф тонкий**.

### 7.1 Ход

```
ChatService.handle_message
  pending_repo.upsert
  LLMExecutionEngine.run(task_type, message, session)
    for pass in max_passes:
      GraphCompiler.compile(state)     # фильтр NODE_REGISTRY по TaskType
      DAGExecutor.execute(plan, state)
      replan → смена task_type → перекомпиляция
    PatchApplier.apply                 # после всех pass
    ResponseResolver.resolve           # TaskType → output node id
  message_repo (turn + narrative)
  pending_repo.delete
```

Это **не** LangGraph с двумя нодами Director/Narrator. `GraphCompiler` каждый pass **фильтрует** зарегистрированные ноды правилами (`supported_tasks`), делит pre_llm / llm / post_llm, внутри Python-фаз — уровни Кана (параллель `asyncio.gather`). LLM-ноды **батчатся по temperature ASC**: один `client.chat()` на бакет, JSON-объект ключ = node id, строгая схема.

### 7.2 Фазы

| Фаза | Кто | Replan | Смысл |
|---|---|---|---|
| `pre_llm` | Python | **да**, единственное место | Gate: нет сцены → `SCENE_INIT`; нет локации → select |
| `llm` | LLM groups | нет; **repair** | Тот же `messages[]`; DSL-патчи по error_code |
| `post_llm` | Python | политика: никогда | Persist side effects |

### 7.3 Что реально живое

`TaskType` ~29 значений (combat, crafting, events, actions…). **Живой пайплайн:**

```
INTENT_DETECTION
  → gate SCENE_INIT | SCENE_START_LOCATION_SELECT
  → задумано SCENE_NARRATION | combat | change_location | analysis
       └── terrain: check → eager/lazy → context → summary → weather
```

**LLM-ноды (2):** `context_snap_gatherer`, `intent_detection`.  
**Нет** зарегистрированной ноды `scene_narration`. `ResponseResolver` уже мапит `SCENE_NARRATION` → `"scene_narration"`. Intent может вернуть `scene_narration_render` → «задача без результата». Это **осознанный блокер**, не дырка «надо срочно закрыть». Не предлагать vertical slice наррации по умолчанию.

Climate `generate_climate` / `recalculate_climate` зарегистрированы с **пустым** `supported_tasks` — на ходе не выбираются. `resolve_weather` живой на scene tasks.

`terrain_context` пишет `shared_context["terrain"]` (untyped dict). Типизированный `TerrainContext` на `ExecutionState` — только ТЗ. `eager_terrain` грузит **`map_cells`**, не pack L0.

DSL на диске: 6 файлов. Механизм repair есть; библиотека патчей тонкая (`repair_confidence.txt` есть, часть заявленных ключей — нет файлов).

### 7.4 PDVA — честно

Идея ID-12 принята (Plan–Diff–Validate–Apply, Orchestrated Reality). В коде:

| Шаг | Факт | Оговорка |
|---|---|---|
| Plan | скомпилированный набор нод + DSL | не LLM-написанный plan object |
| Diff | JSON-секция на node id | не JSON Patch по сущностям мира |
| Validate | Pydantic + node validator + repair | нет «uid существует в БД» |
| Apply | merge в `ExecutionState.node_results` | **не пишет SQLite/pack** |

Запись мира сейчас внутри Python `execute()` через repos (например lazy settlement `insert_bulk_ignore`) или в orchestrator'ах bake/outdoor **вне** PDVA.

`EventBus` — очередь SSE **этого HTTP-запроса**, не мировая шина событий. Lazy sim / witness / essential NPC предполагают другую шину — спека.

### 7.5 Gate DAG

Агент **не правит** `application/engine/nodes/` без совместной сессии с мастером. Предусловие: полное тестирование генераторов G1–G5 ([`tz_world_generation_dag.md`](../../docs/tz_world_generation_dag.md)). Gate **не снят**.

---

## 8. Генераторы мира (компилятор)

Pure library. Semantic-first: мастер пишет *бедный район* (`economic_tier`), генератор резолвит материалы, свет, дороги, заборы, шаблоны через реестры. Не хардкодить «камень» в assembler.

### 8.1 Иерархия поселения

SoT: [`docs/tz_assembler_hierarchy.md`](../../docs/tz_assembler_hierarchy.md), город [`docs/tz_city_generation.md`](../../docs/tz_city_generation.md).

```
SettlementAssembler          footprint, сетка районов, барьер ПОСЕЛЕНИЯ
  └── DistrictAssembler      посадка участков + улицы района
        └── StructureAreaAssembler   участок: двор/забор/здание/plaza; C21 z и порог
              └── StructureAssembler     фундамент/крыльцо/крыша
                    └── StructureGeneratorService   interior box (комнаты, проходы)
                          └── StructureInteriorAssembler   мебель — нет ТЗ, позже
```

Вход можно делать на любом слое (корабль/данж → `StructureAssembler` напрямую, `is_mobile`).

**Skeleton-first:** при создании мира — скелет всех поселений (`NamedLocation`). LLM описывает город **только из скелета**. Полная геометрия — при входе / master outdoor materialize. Инвариант: LLM не получает данных, которых нет.

**Координаты (NC-1)** — три пространства, конверсия только `generators/coordinates/convert.py`:

| Space | Смысл |
|---|---|
| `WORLD_SURFACE_GRID` | occupancy сетки мира |
| `WORLD_FINE_GRID` | улицы, здания, барьеры поселения |
| `LOCATION_FINE_GRID` | интерьер |

### 8.2 Честный статус generate (2026-09-03)

| Домен | Статус |
|---|---|
| Terrain surface (noise → gap → column fill) | live, L0 bake сидит на этом |
| Relief grade v2 (R41 mill→paint→pack slots) | live writer; v1 sample/stitch **удалён** |
| Hills | live (новое окно) |
| Mountains | live достаточно для L0 |
| Hydrology | live generator в bake; bathymetry stubs остаются |
| Climate math + pack coarse | live; engine-нода generate пустые tasks |
| District roads | **только `grid`**; organic/radial/cul_de_sac/courtyard = `NotImplementedError` |
| Settlement phases A–F | live layout |
| C21 plot `ground_z` / порог (дверь / ворота / край участка) | ядро в `StructureAreaAssembler` + тесты |
| C22 packing (2D-бин, два прохода, рамка улиц) | **ТЗ + план**; код всё ещё AABB + overlay сетки |
| Ruins / extraction / vastHull assemblers | `NotImplementedError` |
| Часть лестниц (straight, spiral, shaft, movable ladder) | `NotImplementedError` |
| Organic footprint G–H | не готово |
| Flora / ores / caves | тонко / stubs |
| Мебель / NPC в интерьере | нет ТЗ, не начато |
| Player construction | ТЗ, не в DAG |

**C21:** район **не** выравнивает все здания в одну плоскость и не копирует `max(z)` AABB. Пол и порог к улице считает участок. θ подъезда > 45° — clamp только z дома, не сдвиг xy.

**C22:** целевой пайплайн района — cache оболочек → бронь приоритетных → рамка `grid` вокруг → проход 2 → граф улиц. Фасад из касающихся рёбер, не «всегда длинная сторона AABB». План: [`.cursor/plans/c22-district-packing-migration-done.md`](./c22-district-packing-migration-done.md). Код packing **не** мигрирован.

### 8.3 Relief grade (дискретный склон для AI-GM)

SoT generate: [`docs/tz_terrain_relief.md`](../../docs/tz_terrain_relief.md). Consume/dump: [`tz_terrain_relief_consume.md`](../../docs/tz_terrain_relief_consume.md). Архив v1: `tz_terrain_relief_v1_superseded.md`.

Это **не** Gaea/Unity landscape. Продукт: сущность **Grade** — один uid, один угол θ, occupancy; клетка pack — **8 слотов** (лучи). Mill строит Instance; pack пишет коды в sidecar; dump только читает. Один context на шаблон: `mountain | open_land | shore | road_shoulder | ravine`.

Живой writer: discover в chunk worker (rim → lockstep → ray seam → paint → один fill). ShorePlugin, ravine, emit `ReliefGradeSystem` при ≥2 Instance одной вершины, hills. Открыто: полный occupancy 8 слотов (**R41-T-25**).

Dump ASCII — **debug разработчика**, не мастер, не игрок, не DAG.

На ходе игрока Grade **ещё не** факты для LLM (`terrain_summary` ближе к ключам биома).

### 8.4 Outdoor settlement на pack

SoT: [`docs/tz_settlement_outdoor.md`](../../docs/tz_settlement_outdoor.md). Код: `worldData/settlementOutdoor/`.

После bake земли: `SettlementOutdoorOrchestrator.materialize(world_uid, location_uid)`:

1. generate layout (та же library);
2. extract дерева имён;
3. pack city-structure + SQL (районы, здания, `location_levels`, `location_entry_points`);
4. протокол C19: encode `.tmp` → SQL tx → `os.replace`.

Caller сегодня: debug HTTP. `lazy_settlement` в DAG по-прежнему пишет клетки в repo — **два persist-рассказа**. Это риск drift, пока session start не станет тем же orchestrator.

---

## 9. Pack bake (джоба, не скрипт)

SoT: [`docs/tz_world_pack_storage.md`](../../docs/tz_world_pack_storage.md), light: [`tz_map_light_bake.md`](../../docs/tz_map_light_bake.md).

| Job | Что | Кто зовёт сейчас |
|---|---|---|
| `light_bake` | L0 карта + climate coarse + скелеты; SLO ≤ 2 мин типичный мир | debug HTTP |
| `full_bake` | тот же L0 на весь `world_bounds` | master/CI |
| `detailed_bake` | L2 fine + grades | debug HTTP |
| Entry refine | L2 от точки спавна наружу (hot path **по задумке**) | debug HTTP |
| Outdoor materialize | city-structure, не 4-й bake mode | debug HTTP locations |

L0 light grid — **binding blueprint**, не превью. L2 — fine terrain и grade. Слой города — выше `location_terrain`, ниже patches.

Orchestrators: `PackMaterializationOrchestrator`, `WorldMapBakeOrchestrator` (вклад: terrain, hydro, relief, mountain, ravine, road, settlement, climate, landcover; шов мира по рёбрам тайлов), detailed/refine/entry, `ClimatePackBakeOrchestrator`, `SettlementOutdoorOrchestrator`.

---

## 10. JSON import и authoring

Код: `application/jsonValidation/`. Import **strict → 422**; runtime resolve **warn-only**. `worldSlices.py` — реестр слайсов колонок `worlds`. Новый ключ мира = POJO + SQL + slice, не вторая default-таблица в генераторе.

Покрытие: world scalars/tiers/materials/terrain/hydrology/climate_zones и bundle connections. Races/perks/locations bundle — не полностью. Поля C22 на скелете (`frontage_type_order`, `structure_counts`, …) — ТЗ впереди POJO.

Фикстуры: `fixtures/world_test.json`, `world_test_gen.json`, `world_test_gen_003.json`, `seed.json`, `character_test.json`.

---

## 11. Что работает end-to-end vs что закрыто

| Контур | 2026-09-03 |
|---|---|
| Dev stack, session CRUD, SSE chat, cancel skeleton | да |
| Import мира/персонажа (частичный JV) | да |
| Intent LLM + repair | да |
| Scene gate (init / выбор стартовой локации) | да |
| Pack light/full/detailed + entry refine (debug HTTP) | да |
| Relief v2 в detailed/refine | да (T-25 occupancy открыт) |
| Outdoor etalon generate-settlement | да (C22 packing нет) |
| Terrain в `shared_context` на scene task | да, если task дойдёт; источник `map_cells` |
| **Ход игрока / narration** | **нет** — нет ноды `scene_narration` |
| Bake/outdoor из DAG / session start | **нет** — gate |
| LLM читает pack L0 / Grade / city-structure | **нет** |
| Редактор мира | placeholder |
| Большинство TaskType | enum only |
| Автотесты engine/DAG | почти нет (~15.5k строк тестов на pack/relief) |
| Multiplayer | только ТЗ |
| World snapshot runtime (слепок мира на ход) | schema, модуля нет |

---

## 12. Идеи vs код (кратко)

Registry: [`docs/tz_ideas.md`](../../docs/tz_ideas.md).

Уже в runtime: 3-фазный compiled DAG, temperature-batched LLM, repair DSL (механизм), SSE cancel/resume, `dataModel`+N+1, generator library + pack bake, Grade как сущность, outdoor city на pack.

Спека, не код: Director/Narrator внутри `llm`, scene notebook, witness, beliefs/rumors, plot-lock, authority на patches, perception-фильтр геометрии, NPC LOD, world snapshot/replay, cartridge smoke.

---

## 13. Правила агента, которые ломают чужой код, если их игнорировать

Полные тексты: `.cursor/rules/*.mdc`. Сжато:

1. **Architecture first** — для пайплайна сначала целевые слои/контракты, не слайс «сначала только X».
2. **Assembler hierarchy** — не вызывать Structure в обход Area, когда нужен участок; порог и `ground_z` — Area (C21); packing района — District (C22), улицы не ставят слоты.
3. **Template packs:** `relief_templates/` ≠ `structures_templates/` ≠ world map pack.
4. **Logging:** доменные файлы по `tz_logging.md`, не общий `app.log`. Dump render — `logs/render/dumpLog.log`.
5. **Не коммитить** без явной просьбы.

---

## 14. Глоссарий (не путать термины)

| Термин | Значение здесь |
|---|---|
| TZ | доменное ТЗ в `docs/tz_*.md` |
| Pack | immutable файлы мира (не npm pack, не zip шаблонов зданий) |
| Snapshot (проект) | `tz_project_snapshot.md` — факт кода |
| Snapshot (мир) | `tz_world_snapshot.md` — слепок мира на ход (другой модуль) |
| Snapshot (frontend) | in-memory resume чата |
| Grade | дискретная сущность склона, не heightmap art |
| System (relief) | `ReliefGradeSystem` — несколько Instance одной вершины, не `system_*` поле |
| L0/L1/L2 | LOD bake в ТЗ; в коде — читаемые id, не поля `L0` |
| Scene | якорь + объём симуляции (C18), не «этаж = весь мир» |
| Etalon | authored city в pack; ход — patch |
| Gate DAG | запрет агенту трогать engine nodes |
| N+1 | расширение реестров/полей мастером, не «ещё один NPC» |
| PDVA | Plan-Diff-Validate-Apply; Apply у нас пока state-merge |

---

## 15. Масса кода (ориентир, 2026-09-03)

Примерно: generators 25k строк, docs 24k, tests 15.5k (не DAG), pack 10.5k, dataModel 8.7k, engine **2.9k неизменно**, frontend 1.6k, chat 96. Дисбаланс **задуман**: три+ месяца в компилятор мира после закрытия runtime DAG.

---

## 16. С чего открывать файлы (порядок для чужой LLM)

1. Этот файл.  
2. Characterization — если нужна оценка, не onboarding: [`.cursor/plans/project-characterization-2026-09-03.md`](./project-characterization-2026-09-03.md).  
3. По задаче — **одно** доменное ТЗ, не все сразу:

| Задача | SoT |
|---|---|
| Ход чата, repair, фазы | `docs/tz_engine_flow.md` |
| Ноды generate / кто caller | `docs/tz_world_generation_dag.md` |
| Pack, LOD, UX 30s | `docs/tz_world_pack_storage.md` |
| Grade mill/pack | `docs/tz_terrain_relief.md` |
| Как читать Grade | `docs/tz_terrain_relief_consume.md` |
| Город generate | `docs/tz_city_generation.md` |
| Слои assembler | `docs/tz_assembler_hierarchy.md` |
| Эталон города на pack | `docs/tz_settlement_outdoor.md` |
| Улицы, фасад, C22 | `docs/tz_structure_connections.md` §5.1.3 |
| Здание interior | `docs/tz_building_generator.md` |
| Данные / N+1 | `docs/project_data_storage_tz.md` |
| Import | `docs/tz_json_validation.md` |
| Идеи / пиры | `docs/tz_ideas.md` |

Код-вход: `dataModel/`; bake `pack/bake/packMaterializationOrchestrator.py`; outdoor `settlementOutdoor/settlementOutdoorOrchestrator.py`; engine `llmExecutionEngine.py` (не менять ноды); debug `api/routes/map.py`, `locations.py`.

---

## 17. Карта доменных ТЗ

`docs/tz_architectural_style.md`, `tz_assembler_hierarchy.md`, `tz_building_generator.md`, `tz_city_generation.md`, `tz_climate.md`, `tz_construction.md`, `tz_corridor_connect.md`, `tz_corridor_trim.md`, `tz_crafting.md`, `tz_economy.md`, `tz_economic_tier.md`, `tz_engine_flow.md`, `tz_engine_node_context.md`, `tz_flora.md`, `tz_frontend.md`, `tz_generator_technical_debt.md`, `tz_json_import.md`, `tz_json_validation.md`, `tz_lazy_simulation.md`, `tz_lighting.md`, `tz_locations.md`, `tz_logging.md`, `tz_map_light_bake.md`, `tz_materials.md`, `tz_mountain_architecture.md`, `tz_multiplayer.md`, `tz_pack_ascii_render.md`, `tz_perception.md`, `tz_project_snapshot.md`, `tz_races.md`, `tz_settlement_outdoor.md`, `tz_staircase_generation.md`, `tz_states.md`, `tz_structure_connections.md`, `tz_terrain_generation.md`, `tz_terrain_hydrology.md`, `tz_terrain_relief.md`, `tz_terrain_relief_consume.md`, `tz_terrain_relief_technical_debt.md`, `tz_terrain_relief_v1_superseded.md` (архив), `tz_world_bundle.md`, `tz_world_generation_dag.md`, `tz_world_pack_storage.md`, `tz_world_snapshot.md`, `tz_application_performance.md`, `tz_ideas.md`. Плюс `docs/project_data_storage_tz.md`.

Tech-debt генераторов: `tz_generator_technical_debt.md`. Планы имплементации не класть в `docs/`.

---

## 18. Одна фраза, если нужно пересказать продукт

Платформа, где мастер кодирует мир реестрами и процедурным компилятором в immutable pack, а LLM ведёт игрока строго по фактам движка — validation-first GM на геометрическом substrate, с закрытым DAG-runtime и пока без хода narration, потому что сцена ещё не читает тот pack, который bake уже умеет печь.

---

*Скомпилировано 2026-09-03 для передачи другой модели. Код HEAD `0342edb`; в working tree могут быть незакоммиченные правки ТЗ C22 (спека впереди packing-кода).*
