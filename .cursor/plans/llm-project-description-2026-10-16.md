# AI RPG Platform — описание проекта для другой LLM

**Дата среза:** 2026-10-16  
**Репозиторий:** `E:/AI Project` (git root `2026-05-09`, HEAD `082cce55`, **511** коммитов, один автор).  
**Назначение этого файла:** самодостаточный onboarding. Прочитать **целиком** до правок кода. Не заменяет доменные ТЗ — после ориентации открывать SoT из §17.

**Рядом, другая задача:** оценка/скоры — [`.cursor/plans/project-characterization-2026-09-22.md`](./project-characterization-2026-09-22.md) (последний scorecard; новый датированный бриф этой серии не выпускался, дельта ниже покрывает окно). Этот документ — *что это и как устроено*, не *как ставить оценку*. Предыдущие handoff: [2026-09-22](./llm-project-description-2026-09-22.md), [2026-09-03](./llm-project-description-2026-09-03.md).

**Живой снимок кода (частично устарел, v1.3 2026-08-17):** [`docs/tz_project_snapshot.md`](../../docs/tz_project_snapshot.md). При расхождении чисел — этот файл новее.

**Дельта vs 2026-09-22 (обязательно учесть), тема окна — инфраструктура под DAG, не GM-контент:**

- **Pack-модель библиотек шаблонов** — новый подсистемный пласт `application/worldData/libraryPacks/` (~77 файлов): пак = один владелец; доступность мира = `owner_world_uid` либо default; инстанцирование = полная копия + remap UID + provenance; `.wpack` архивы (codec, UID-layout, manifest, round-trip, routes); common write pipeline (inspector/policy/planner/executor). Шаги A0–A7 и B1–B7 закрыты; шаг 6 (global canonical attach `structure_templates`) прошёл smoke 2026-10-16 — два дефекта зафиксированы в [`library-packs-67-smoke-debt.md`](./library-packs-67-smoke-debt.md) (D1 блокер `payload_kind: null` в location_type_registry, **вне scope libpack**; D2 empty-pack export). SoT: [`tz_template_library_packs.md`](../../docs/tz_template_library_packs.md), [`tz_domain_template_libraries.md`](../../docs/tz_domain_template_libraries.md).
- **Cascade / `LocationContext` из ТЗ в код** — `application/cascade/` + `dataModel/cascade/` + `dataModel/locations/context/`: декларативные `Cascade`-параметры (`cascadeParams.py`), `verify_cascade_contract` в тестах; `economic_tier`, `wall/floor/dominant material`, `city_size`, `settlement_density` проведены по цепочке settlement→district→area→building; `TierResolver` и `building_band` **удалены**. SoT: [`tz_cascade_context.md`](../../docs/tz_cascade_context.md).
- **DET-1 deterministic ids** — `app/ids` + каноническая формула, `UidKind`/`LibraryKind`, `entity_rng`/`seed_root`; ad-hoc `uuid`/`hashlib`/`random.Random` вычищены из генераторов. Прямая предпосылка gate **G4** (determinism workers 1 vs N).
- **worlddata restructure шаги 1–2** — `worldData/ids` → `app/ids`, `worldData/context` → `application/cascade`; шаги 3+ заблокированы графом зависимостей ([`plan-dependency-graph.md`](./plan-dependency-graph.md)).
- **`dataModel/`**: 326 файлов / ~18k строк / ~375 моделей; реструктурирован под `locations/`; POJO-ревью 2026-10-16 — см. §4.3 и §7.6.
- **Engine по-прежнему 0 коммитов** — gate держится. Frontend почти не тронут. Тесты **удвоились** (~46k строк) — всё на compiler/library side.

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
| Правка — только по согласованному плану в `.cursor/plans/` | Код «по мотивам обсуждения» без файла плана (`code-gates.mdc`) |

**Осознанные «нет» продукта (не чинить по умолчанию):**

- нет LLM-генерации геометрии (идея R-1 **rejected**);
- нет RAG как основной памяти мира (R-2 deferred);
- нет LLM на каждого ambient NPC / AgentCity (R-3, R-5 rejected);
- **нет** interim `scene_narration` / vertical slice игрока, пока контракт сцены и pack нестабилен;
- **нет** wiring bake/outdoor в `engine/nodes/` до снятия gate мастером;
- non-grid `street_layout` (`organic` / `radial` / …) — **намеренный cut v1**, не «дыра packing» для дефолтного фикса;
- purpose tree ≠ purpose pack: не класть `(system_name, packs)` в файл семьи (`purpose-tree-not-pack.mdc`).

Не стартовать backend (`python start.py`, `uvicorn`, `npm run backend`) — это делает мастер. Smoke по HTTP — мастер прогоняет сам (последний — library packs, 2026-10-16).

---

## 1. Что это за продукт

**AI RPG Platform** — симуляционная платформа, не «игра-чат».

Мастер мира задаёт **правила** (статы, формулы, реестры, terrain, шаблоны зданий) JSON-импортом (позже — тот же validator в UI редактора). Движок **симулирует** мир. LLM — **мастер игры по этим правилам**: предлагает события и прозу, не является источником истины.

Аналогия в репозитории: **Foundry VTT + AI-GM + процедурный геометрический мир**.

| Роль | Что делает | Что видит |
|---|---|---|
| **Мастер мира** | Реестры, импорт JSON, библиотеки шаблонов (packs), bake/debug, баланс, выпуск пресета | N+1, `system_*`, validator, pack |
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
  application/chat/                   ход, pending, crash recovery (~112 строк)
  application/engine/                 DAG runtime (compile / phase / repair / replan)
  application/contracts/              LLM wire-контракты нод (см. §7.6 — отдельный слой)
  application/cascade/                runtime resolve LocationContext (extend/fold)
  application/canonicalLibrary/       canonical attach/spec инфраструктура
  application/jsonValidation/         import + runtime resolve (POJO-first)
  application/worldData/
    generators/                       pure library (terrain, relief, hydro, settlement…)
    pack/                             bake / refine / read immutable pack
    settlementOutdoor/                эталон города на pack + SQL-дерево
    libraryPacks/                     pack-модель библиотек шаблонов (§9.5)
    bundle/                           world/library archive export-import
  ids/                                DET-1: canonical uid formula, UidKind, entity_rng
  dataModel/                          Pydantic — единственный контракт полей
  db/                                 repos, models, 0001_initial.sql, bulkSql.py
  core/                               Container, config, logging
  dsl/                                промпты LLM-нод (сейчас тонкие)

frontend/src/features/{session,chat,settings}
fixtures/                             world_test*.json, seed, characters, templates/
relief_templates/                     пакеты шаблонов grade (не смешивать с buildings)
structures_templates/                 библиотека структур (base/, rogue/, smoke_*…)
```

**Две «продукта» в одном репо (это норма, не баг):** (1) world compiler + pack + библиотеки; (2) validation-first GM. Связка задумана так: session start **читает pack**, который bake уже умеет писать. Сегодня связки нет — и это не дрейф: gate DAG требует сначала приёмки генераторов + persist (§7.5).

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

### 4.3 `dataModel/` — SoT полей (ревью 2026-10-16)

Pydantic в `backend/app/dataModel/` — единственный источник builtin-полей, defaults, wire-ключей. Resolve (world + fallback + merge) **поверх** модели — `resolve_model` никогда не construct unchecked POJO (Pydantic владеет aliases/validators/`model_fields_set`).

Запрещено дублировать `Field(default=…)` литералом в генераторе, DAG, `db/`, route. Читать `entry_for()`, `canonical_defaults()`, `fallback()`, типизированные поля. Реестр расхождений: [`tz_datamodel_pojo_discrepancies.md`](../../docs/tz_datamodel_pojo_discrepancies.md) (POJO-D-*).

Новое builtin-значение → сначала POJO (+ SQL/dataclass если колонка), потом тонкий потребитель.

**Конвенционный слой (сильный):** `annotationPolicy.py` — per-field wire-политика `StrictOnWire` / `DefaultWhenMissing` / `EnumWire`; `constrained_field`; `RegistryKey[T]`; `SCHEMA_ID` на wire-моделях. Frozen преобладает; `extra="ignore"` ~145 файлов vs `extra="forbid"` ~27 — неизвестные ключи wire молча дропаются (открытый план `json-validation-unknown-keys.md`).

**Известные швы слоя (факт, не для самодеятельного фикса):**

- `StructureTemplate.levels/staircases/connections` — `list[dict]` на поле: after-валидаторы парсят в `LevelDef`/`StaircaseSpec`/`RoomConnection` и результат **выбрасывают**; потребитель парсит item заново через `resolve_model` (двойной парсинг, POJO-D-16 остаток).
- **POJO опережает consumer:** реестр уже хранит footprint-таблицы per subtype (`_FOOTPRINT_CITY`/`_FOOTPRINT_VILLAGE`/…), но planner передаёт `_size_only_morphology()` — LOC-T-2 в чеклисте дыр.
- `LocationContext` — frozen POJO с `provenance` и opaque `PrivateAttr` runtime-хэндлами (`_world`, `_links`, `_node_results`) — единственный POJO с таким швом, задокументировано.

### 4.4 Слои хранения мира (целевые)

| Слой | Что | Мутация |
|---|---|---|
| **World Pack** (immutable files, zstd/mmap) | L0 карта, L2 fine terrain/grades, **city-structure** эталон города | master bake / outdoor materialize |
| **SQLite OLTP** | сессии, персонажи, `named_locations` (имена/дерево), граф `connection_*`, библиотеки (packs/members), сообщения | CRUD + generate persist |
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

Переходы между локациями — `transitions` (typed endpoints source/destination, projection на геометрию): [`tz_location_transitions.md`](../../docs/tz_location_transitions.md).

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
worldData           orchestrators persist + pack I/O + libraryPacks write pipeline
        ↓
generators/         (World, LocationContext…) → layout / cells / graph.
                    Без async, SQL, HTTP, ExecutionState.
        ↓
dataModel + db
```

**Caller'ы одной library — целевая картина vs факт** ([`docs/tz_world_generation_dag.md`](../../docs/tz_world_generation_dag.md)):

Целевые три входа в TZ: Engine DAG (production), Debug HTTP, unit tests. **Факт:** debug API + тесты; DAG — целевой caller после gate.

1. **Debug HTTP — текущий live вход**: `map.py` bake/refine, `locations.py` `generate-settlement`. Harness **постоянный**. Обязан **симулировать вызов как в DAG** — тот же интерфейс оркестратора, который вызовет нода.
2. **Engine DAG — целевой, не реализован** для bake/outdoor (gate). `lazy_*` → `map_cells` — тестовый путь под переделку, не эталон; DAG будет дорабатываться.
3. **Unit tests** — in-process, без HTTP (~46k строк, compiler/library side).

**Атомарность — в DAG** (мастер, 2026-09-23): materialization = один вызов оркестратора атомарен сам (C19: `.tmp` → SQL tx → `os.replace`), нода триггерит целиком, не дробит internals; ход = `pending_patches` → apply. Детали wiring отложены до имплементации DAG мастером; возможна переделка части функций — не проектировать оркестраторы под гипотетический контракт ноды.

---

## 6. Backend по слоям — факт кода

### 6.1 API `/api`

Игровой контур: sessions CRUD; `POST /chat` и `POST /chat/stream` (SSE: node status, thinking, result, error, cancelled); cancel; history/pending; LLM settings.

Мастер: worlds import/export (+ `.wpack` archive); locations + **`POST …/generate-settlement`**; characters; races/perks; map pack bake `light|full|detailed`, refine-from-entry, render; connections; seed; **library packs / members / templates CRUD + import** (`library-packs`, `structure-templates`, `relief-templates`); debug generate-structure.

`ChatRequest`: `session_id`, `message`, provider/model, `request_id`, `resume`, опционально `task_type` (минует intent).

### 6.2 Frontend

~1.8k строк. Умеет: список сессий, выбор мира/персонажа, стрим статуса нод, cancel; client под library write-контракт (409 negotiation) добавлен в окне L-5. Не умеет: редактор мира, карта продукта, реестры мастера. Electron-специфика только в `platform/fileSystem.js`.

---

## 7. Движок (GM machine)

SoT flow: [`docs/tz_engine_flow.md`](../../docs/tz_engine_flow.md). Код: `backend/app/application/engine/`. **Файлы engine не менялись с 2026-08-14** (gate). Машина закрыта, **контентный граф тонкий** — и это задуманный порядок (§7.5), не дрейф.

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

**LLM-ноды (2):** `context_snap_gatherer`, `intent_detection` (контракты — `application/contracts/`).  
**Нет** зарегистрированной ноды `scene_narration`. `ResponseResolver` уже мапит `SCENE_NARRATION` → `"scene_narration"`. Intent может вернуть `scene_narration_render` → «задача без результата». Это **осознанный блокер**, не дырка «надо срочно закрыть». Не предлагать vertical slice наррации по умолчанию.

Climate `generate_climate` / `recalculate_climate` зарегистрированы с **пустым** `supported_tasks` — на ходе не выбираются. `resolve_weather` живой на scene tasks.

`terrain_context` пишет `shared_context["terrain"]` (untyped dict). Типизированный `TerrainContext` на `ExecutionState` — только ТЗ (`tz_engine_node_context.md`). `eager_terrain` грузит **`map_cells`**, не pack L0.

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

### 7.5 Gate DAG — и почему текущее окно это его precondition chain

Агент **не правит** `application/engine/nodes/` без совместной сессии с мастером. Предусловие: полное тестирование генераторов G1–G5 ([`tz_world_generation_dag.md`](../../docs/tz_world_generation_dag.md)). Gate **не снят**.

**G1–G5:** G1 terrain pipeline smoke → G2 TR-PERF bulk persist benchmark → G3 TR-LAZY-LOAD service/repo через HTTP → G4 determinism (workers 1 vs N) → G5 мастер снимает явно.

Маппинг текущих треков на gate (сессия 2026-10-16): **DET-1 ids → G4** (детерминизм невозможен с ad-hoc uuid); **cascade `LocationContext` → typed context** вместо `shared_context`-строк; **library packs / effective catalog → identity и каталог** для materialize-нод; **W2 scoped writes → один persist-путь** (рассосать «трёх писателей» map_cells / pack / city-structure до wiring ноды `lazy_settlement`).

### 7.6 POJO ↔ DAG seam (решения сессии 2026-10-16, оформление в ТЗ — позже)

Факт: `application/engine` **не импортирует** `dataModel` — ноль импортов. `NodeResult.data: Any`; `shared_context: dict` со строковыми ключами; `application/contracts/contracts.py` — LLM wire-контракты вне dataModel (`location: str`).

Согласованная мастером рамка для будущей типизации (дизайн, не код):

**Три слоя типов — не смешивать:**

| Слой | Что | Истина? |
|---|---|---|
| Domain SoT (`dataModel/`) | мир, реестры, шаблоны, defaults, wire-импорт | да, единственный |
| Turn context (ExecutionState domain contexts) | снапшот хода: ссылки на domain-объекты + runtime-поля (`is_loaded`, `source`, `provenance`) | нет — view |
| LLM wire (`contracts`) | JSON-схема входа/выхода модели | нет — transport |

**Два инварианта:**

1. **Context компонует, не переопределяет:** `TerrainContext` хранит `WorldMapCellWire`/uid, не объявляет `system_terrain: str`. Поле контекста, дублирующее доменное, — сигнал перенести его в dataModel. Контекстные типы — engine-adjacent (dataclass по ТЗ), импортируют dataModel, не наоборот (dataModel — без app/db deps).
2. **Нода — не вторая истина:** ни один выход ноды/LLM не становится фактом, минуя тот же resolve/валидацию, что JSON-импорт. LLM-контракт валидируется → резолвится в доменные типы → только результат попадает в контекст. Сырой LLM-выход в `shared_context` не кладётся. Нода — функция: typed in → typed out; uid/rng только через DET-1; persist — только через сервисы.

Не покрыто действующим ТЗ (кандидаты на дополнение `tz_engine_node_context.md`): типы `node_results` (§1 ТЗ объявил проблемой, §2 решил только `shared_context`); правило «resolve-before-context» и место LLM-контрактов относительно dataModel.

---

## 8. Генераторы мира (компилятор)

Pure library. Semantic-first: мастер пишет *бедный район* (`economic_tier`), генератор резолвит материалы, свет, дороги, заборы, шаблоны через реестры **и cascade `LocationContext`** (tier → … → building; `TierResolver`/`building_band` удалены). Не хардкодить «камень» в assembler.

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

**Детерминизм (DET-1):** uid/rng только через `app/ids` — `entity_uid`, `entity_rng`, `seed_root`, `world_uid` проброшен через assembler-цепочку. Ad-hoc `uuid`/`hashlib`/`random.Random` в генераторах — антипаттерн.

### 8.2 Честный статус generate (2026-10-16)

| Домен | Статус |
|---|---|
| Terrain surface (noise → gap → column fill) | live, L0 bake сидит на этом |
| Relief grade v2 (R41 mill→paint→pack slots) | live writer; **R41-T-25** occupancy открыт |
| Hills / Mountains | live |
| Hydrology | live generator в bake; bathymetry stubs остаются |
| Climate math + pack coarse | live; engine-нода generate пустые tasks |
| Cascade context (tier/materials/size/density) | **live** — `LocationContext` через цепочку settlement→building |
| District roads | **только `grid`** (+ roles spine/fill/alley); organic/radial/… = `NotImplementedError` (cut v1) |
| Settlement phases A–F | live layout; специализация → `district_subtype` на слотах |
| C21 plot `ground_z` / порог | ядро в `StructureAreaAssembler` + тесты |
| C22 packing (lattice → pass1 → grid frame → pass2 → frontage) | live; plan-файл может лагать — **верить `DistrictAssembler`** |
| BuildingPurpose + `purpose_packs` | закрыто |
| Library identity в generate | переход на member UID в packing/planner (5b B3); persist `system_template_uid`/`system_structure_template_uid` (B4) |
| Ruins / extraction / vastHull assemblers | `NotImplementedError` |
| Часть лестниц | `NotImplementedError` |
| Settlement walls / `barrier_cells` | дыра **CITY-T-1c** |
| Footprint by subtype | дыра **LOC-T-2** — POJO-таблицы есть, planner шлёт size-only (§4.3) |
| Legacy extract parent=settlement | дыра **CITY-T-5a/5g** (ложный authored-skip) |
| Flora / ores / caves | тонко / stubs |
| Мебель / NPC в интерьере | нет ТЗ |
| Player construction | ТЗ, не в DAG |

Живой чеклист: [`.cursor/plans/city-generation-remaining-holes.md`](./city-generation-remaining-holes.md).

### 8.3 Relief grade (дискретный склон для AI-GM)

SoT generate: [`docs/tz_terrain_relief.md`](../../docs/tz_terrain_relief.md). Consume/dump: [`tz_terrain_relief_consume.md`](../../docs/tz_terrain_relief_consume.md). Архив v1: `tz_terrain_relief_v1_superseded.md`.

Это **не** Gaea/Unity landscape. Продукт: сущность **Grade** — один uid, один угол θ, occupancy; клетка pack — **8 слотов** (лучи). Mill строит Instance; pack пишет коды в sidecar; dump только читает. Один context на шаблон: `mountain | open_land | shore | road_shoulder | ravine`.

Живой writer: discover в chunk worker (rim → lockstep → ray seam → paint → один fill). ShorePlugin, ravine, emit `ReliefGradeSystem` при ≥2 Instance одной вершины, hills. Открыто: полный occupancy 8 слотов (**R41-T-25**), relief Q-attach.

Dump ASCII — **debug разработчика**, не мастер, не игрок, не DAG. На ходе игрока Grade **ещё не** факты для LLM.

### 8.4 Outdoor settlement на pack

SoT: [`docs/tz_settlement_outdoor.md`](../../docs/tz_settlement_outdoor.md). Код: `worldData/settlementOutdoor/` (facade + jobs, DET-1 uid на district/city_node/area/building/level/entry).

После bake земли facade зовёт:

1. **C23** `SettlementOutdoorTopologyJob` — слоты → extract → SQL районов + city graph (обязателен до packing);
2. **C24** `SettlementOutdoorPackingJob` — per-district packing frames → pack `l.{uid}.settlement.zst`;
3. протокол C19: encode `.tmp` → SQL tx → `os.replace`.

Caller materialize сегодня: debug HTTP (`locations.py`). **`full_bake` также зовёт C23 `plan_topology`**. `lazy_settlement` в DAG по-прежнему пишет клетки в repo — **два persist-рассказа** (схлопываются через W2/gate, §7.5). Legacy extract вешает здания на settlement вместо district (**CITY-T-5a**).

---

## 9. Pack bake (джоба, не скрипт)

SoT: [`docs/tz_world_pack_storage.md`](../../docs/tz_world_pack_storage.md), light: [`tz_map_light_bake.md`](../../docs/tz_map_light_bake.md).

| Job | Что | Кто зовёт сейчас |
|---|---|---|
| `light_bake` | L0 карта + climate coarse + скелеты; SLO ≤ 2 мин типичный мир | debug HTTP |
| `full_bake` | L0 на весь `world_bounds` + **C23 plan_topology** | master/CI / debug HTTP |
| `detailed_bake` | L2 fine + grades; settlement-like может поверх C11 packing | debug HTTP |
| Entry refine | L2 от точки спавна наружу (hot path **по задумке**) | debug HTTP |
| Outdoor materialize | C23+C24 city-structure, не 4-й bake mode | debug HTTP locations |

L0 light grid — **binding blueprint**, не превью. L2 — fine terrain и grade. Слой города — выше `location_terrain`, ниже patches.

Orchestrators: `PackMaterializationOrchestrator`, surface/world map bake, detailed/refine/entry, `ClimatePackBakeOrchestrator`, outdoor facade (C23/C24).

### 9.5 Library packs (новый подсистемный пласт окна)

SoT: [`tz_template_library_packs.md`](../../docs/tz_template_library_packs.md), [`tz_domain_template_libraries.md`](../../docs/tz_domain_template_libraries.md). Код: `application/worldData/libraryPacks/` (~77 файлов) + `application/canonicalLibrary/`.

- **Пак = ровно один владелец** (`owner_world_uid` либо global/default); bindings-таблицы нет. Инстанцирование = полная копия пака с remap UID + provenance (`source_pack_uid`/`source_template_uid`).
- Per-template pointer-реестры (`worlds.*_template_registry`) **удалены** (5b B7); identity = member UID, не name.
- Общий write pipeline: inspector → policy → planner → executor; HTTP-контракт 409 + decisions/token (L-4/L-5); bundle import переиспользует его в UOW мира (4d).
- `.wpack` архивы: UID-layout `library/{domain_root}/{pack_uid}/{template_uid}.json`, manifest typed, multi-domain; codec + round-trip + routes закрыты (C-1…C-5).
- Canonical attach (`ensure_canonical`, global fill-missing): spec-декларации + `CanonicalLibrarySpec`; smoke 2026-10-16 подтвердил attach `engine.structures.base` (13 members, идемпотент, 403 на default write).
- Domain roots не смешиваются: `structures_templates/`, `relief_templates/` — разные корни (`template-pack-layout.mdc`).

**Известные дефекты после smoke 2026-10-16** ([`library-packs-67-smoke-debt.md`](./library-packs-67-smoke-debt.md)): **D1 блокер** — `payload_kind: null` материализуется в `worlds.location_type_registry` при persist/normalize → `generate-settlement` 422 для мира после registry round-trip (вне scope libpack; fix-кандидаты: pop unset полей в `serialize_overrides` или merge по `is not None`); **D2** — export `.wpack` падает на world-owned паке с 0 членов.

---

## 10. JSON import и authoring

Код: `application/jsonValidation/`. Import **strict → 422**; runtime resolve **warn-only**. `worldSlices.py` — реестр слайсов колонок `worlds`. Новый ключ мира = POJO + SQL + slice, не вторая default-таблица в генераторе.

Покрытие: world scalars/tiers/materials/terrain/hydrology/climate_zones, purpose_packs, grid_settings, bundle connections, library sections (consumed-allowlist в bundle). Races/perks/locations bundle — не полностью. World editor UI — placeholder.

Фикстуры: `fixtures/world_test*.json`, `seed.json`, `character_test.json`, `fixtures/templates/`.

---

## 11. Что работает end-to-end vs что закрыто

| Контур | 2026-10-16 |
|---|---|
| Dev stack, session CRUD, SSE chat, cancel skeleton | да |
| Import мира/персонажа (частичный JV) | да |
| Intent LLM + repair | да |
| Scene gate (init / выбор стартовой локации) | да |
| Pack light/full/detailed + entry refine (debug HTTP) | да |
| Relief v2 в detailed/refine | да (T-25 occupancy открыт) |
| Outdoor etalon generate-settlement | да — C23+C24; **но см. D1 блокер §9.5** (payload_kind null) |
| C22 district packing | да (только `grid`) |
| BuildingPurpose + purpose_packs | да |
| Cascade `LocationContext` в generate | **да** — tier/materials/size/density по цепочке |
| DET-1 ids в генераторах | **да** |
| Library packs: attach/instantiate/write/`.wpack` round-trip | **да** (smoke 2026-10-16; дефекты D1/D2) |
| Terrain в `shared_context` на scene task | да, если task дойдёт; источник `map_cells`, untyped dict |
| **Ход игрока / narration** | **нет** — нет ноды `scene_narration` |
| Bake/outdoor из DAG / session start | **нет** — gate |
| LLM читает pack L0 / Grade / city-structure | **нет** |
| Редактор мира | placeholder |
| Большинство TaskType | enum only |
| Автотесты engine/DAG | почти нет (~46k строк тестов — pack/library/city) |
| Multiplayer / world snapshot runtime | только ТЗ / schema |
| Стены поселения / barrier_cells | дыра CITY-T-1c |

---

## 12. Идеи vs код (кратко)

Registry: [`docs/tz_ideas.md`](../../docs/tz_ideas.md).

Уже в runtime: 3-фазный compiled DAG, temperature-batched LLM, repair DSL (механизм), SSE cancel/resume, `dataModel`+N+1, generator library + pack bake, Grade как сущность, outdoor city на pack с C22 packing и C23/C24 jobs, BuildingPurpose taxonomy + purpose packs, **cascade context (LocationContext)**, **DET-1 ids**, **pack-модель библиотек шаблонов + `.wpack`**.

Спека, не код: Director/Narrator внутри `llm`, scene notebook, witness, beliefs/rumors, plot-lock, authority на patches, perception-фильтр геометрии, NPC LOD, world snapshot/replay, cartridge smoke, typed `node_results`/контексты на ExecutionState (§7.6 — дизайн согласован, ТЗ-дополнение позже).

---

## 13. Правила агента, которые ломают чужой код, если их игнорировать

Полные тексты: `.cursor/rules/*.mdc`. Сжато:

1. **Architecture first** — для пайплайна сначала целевые слои/контракты, не слайс «сначала только X`.
2. **Code gates** — правка только по согласованному `.cursor/plans/*.md`; один шаг за заход + отчёт.
3. **Assembler hierarchy** — не вызывать Structure в обход Area, когда нужен участок; packing района — District (C22).
4. **Template packs:** `relief_templates/` ≠ `structures_templates/` ≠ world map pack; один файл = один outline; stem == `system_name`; lone file вне пак-папки = reject.
5. **dataModel SoT** — без литералов-дублей во всех слоях (`dataModel-no-hardcode.mdc`).
6. **Bulk SQL** — только `app.db.bulkSql` (`executemany_rows` / `iter_batches`).
7. **Class size** — тело класса > 300 строк = вынести зону.
8. **Logging:** доменные файлы по `tz_logging.md`, не общий `app.log`.
9. **Не коммитить** без явной просьбы. **Не стартовать backend** — мастер прогоняет сам.

---

## 14. Глоссарий (не путать термины)

| Термин | Значение здесь |
|---|---|
| TZ | доменное ТЗ в `docs/tz_*.md` |
| Pack (world) | immutable файлы мира — baked terrain/city |
| Pack (library) | пакет шаблонов с одним владельцем — buildings/relief/structures |
| `.wpack` | архивный формат паков/мира (UID-layout, manifest) |
| Snapshot (проект) | `tz_project_snapshot.md` — факт кода |
| Snapshot (мир) | `tz_world_snapshot.md` — слепок мира на ход (другой модуль) |
| Snapshot (frontend) | in-memory resume чата |
| Grade | дискретная сущность склона, не heightmap art |
| System (relief) | `ReliefGradeSystem` — несколько Instance одной вершины |
| L0/L1/L2 | LOD bake в ТЗ; в коде — читаемые id |
| Scene | якорь + объём симуляции (C18) |
| Etalon | authored city в pack; ход — patch |
| Gate DAG | запрет агенту трогать engine nodes |
| N+1 | расширение реестров/полей мастером |
| PDVA | Plan-Diff-Validate-Apply; Apply у нас пока state-merge |
| DET-1 | детерминированные uid/rng через `app/ids` |
| Cascade / LocationContext | наследование параметров по scope-цепочке (world→…→room) |
| Purpose tree / pack | таксономия функции здания / world-маска живых листьев |

---

## 15. Масса кода (ориентир, 2026-10-16)

Примерно: tests **46k** (не DAG), generators **34k**, docs 60 файлов, dataModel **18k**, pack **13k**, libraryPacks **~7.2k**, db **4.4k**, engine **~3.6k неизменно**, jsonValidation **2.9k**, api **2.7k**, settlementOutdoor **2.1k**, frontend **1.8k**, cascade 612, chat 112.

Дисбаланс **задуман**: компилятор мира + контрактная инфраструктура растут до приёмки, потом gate G1–G5 → wiring в DAG. Прежняя формула «consumer не двигался» уточнена 2026-10-16: gate запрещает трогать ноды раньше — окно инфры и есть precondition chain (§7.5).

---

## 16. С чего открывать файлы (порядок для чужой LLM)

1. Этот файл.
2. Characterization — если нужна оценка: [`.cursor/plans/project-characterization-2026-09-22.md`](./project-characterization-2026-09-22.md).
3. По задаче — **одно** доменное ТЗ, не все сразу:

| Задача | SoT |
|---|---|
| Ход чата, repair, фазы | `docs/tz_engine_flow.md` |
| Ноды generate / кто caller / gate | `docs/tz_world_generation_dag.md` |
| Типизированные контексты нод | `docs/tz_engine_node_context.md` |
| Pack, LOD, UX 30s | `docs/tz_world_pack_storage.md` |
| Grade mill/pack | `docs/tz_terrain_relief.md` |
| Как читать Grade | `docs/tz_terrain_relief_consume.md` |
| Город generate | `docs/tz_city_generation.md` |
| Слои assembler | `docs/tz_assembler_hierarchy.md` |
| Эталон города на pack | `docs/tz_settlement_outdoor.md` |
| Улицы, фасад, C22 | `docs/tz_structure_connections.md` §5.1.3 |
| Здание interior | `docs/tz_building_generator.md` |
| Библиотеки шаблонов (packs) | `docs/tz_template_library_packs.md` + `tz_domain_template_libraries.md` |
| Cascade context | `docs/tz_cascade_context.md` |
| Архив `.wpack` / bundle | `docs/tz_world_bundle.md` |
| Данные / N+1 | `docs/project_data_storage_tz.md` |
| Import | `docs/tz_json_validation.md` |
| POJO расхождения | `docs/tz_datamodel_pojo_discrepancies.md` |
| Идеи / пиры | `docs/tz_ideas.md` |

Код-вход: `dataModel/`; bake `pack/`; outdoor `settlementOutdoor/`; library packs `libraryPacks/`; cascade `application/cascade/` + `dataModel/locations/context/`; ids `app/ids`; C22 `generators/assemblers/districtAssembler/`; engine `llmExecutionEngine.py` (не менять ноды); debug `api/routes/map.py`, `locations.py`.

---

## 17. Карта доменных ТЗ

`docs/tz_application_performance.md`, `tz_architectural_style.md`, `tz_assembler_hierarchy.md`, `tz_building_generator.md`, `tz_cascade_context.md`, `tz_cascade_technical_debt.md`, `tz_city_generation.md`, `tz_city_generation_technical_debt.md`, `tz_climate.md`, `tz_construction.md`, `tz_corridor_connect.md`, `tz_corridor_trim.md`, `tz_crafting.md`, `tz_datamodel_pojo_discrepancies.md`, `tz_domain_template_libraries.md`, `tz_economy.md`, `tz_economic_tier.md`, `tz_engine_flow.md`, `tz_engine_node_context.md`, `tz_flora.md`, `tz_frontend.md`, `tz_generator_technical_debt.md`, `tz_ideas.md`, `tz_json_import.md`, `tz_json_validation.md`, `tz_lazy_simulation.md`, `tz_library_contextual_fallback.md`, `tz_lighting.md`, `tz_location_transitions.md`, `tz_locations.md`, `tz_logging.md`, `tz_map_light_bake.md`, `tz_materials.md`, `tz_mountain_architecture.md`, `tz_multiplayer.md`, `tz_pack_ascii_render.md`, `tz_perception.md`, `tz_pojo_city_typing.md`, `tz_project_snapshot.md`, `tz_races.md`, `tz_runtime_world_edit_policy.md`, `tz_settlement_outdoor.md`, `tz_staircase_generation.md`, `tz_states.md`, `tz_structural_mutations.md`, `tz_structure_connections.md`, `tz_template_library_packs.md`, `tz_terrain_generation.md`, `tz_terrain_hydrology.md`, `tz_terrain_relief.md`, `tz_terrain_relief_consume.md`, `tz_terrain_relief_technical_debt.md`, `tz_terrain_relief_v1_superseded.md` (архив), `tz_world_bundle.md`, `tz_world_generation_dag.md`, `tz_world_pack_storage.md`, `tz_world_snapshot.md`. Плюс `docs/project_data_storage_tz.md`, `runtime_policy_field_migration.md`, `testing_technical_debt.md`.

Tech-debt генераторов: `tz_generator_technical_debt.md`. Планы имплементации не класть в `docs/`.

---

## 18. Одна фраза, если нужно пересказать продукт

Платформа, где мастер кодирует мир реестрами, библиотеками шаблонов и процедурным компилятором в immutable pack, а LLM ведёт игрока строго по фактам движка — validation-first GM на геометрическом substrate; DAG-runtime закрыт и ждёт gate, который отпирается именно той инфраструктурой (детерминированные id, cascade context, pack-модель библиотек, единый persist), что строится сейчас.

---

*Скомпилировано 2026-10-16 для передачи другой модели. Код HEAD `082cce55`, 511 коммитов. Окно: library packs (A0–A7, B1–B7, шаг 6 smoke с дефектами D1/D2), cascade в коде, DET-1, dataModel под locations/. Engine не тронут по gate. Предыдущий handoff: 2026-09-22.*
