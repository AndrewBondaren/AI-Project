# ТЗ: Снимок состояния проекта

**Версия:** 1.1  
**Дата:** 2026-07-20  
**Тип:** living snapshot — фиксирует *фактическое* состояние кода, не целевую архитектуру.

> Целевые спецификации по доменам — отдельные `docs/tz_*.md`.  
> Этот документ — точка отсчёта «где мы сейчас» для мастера и агента.

---

## 1. Продукт

**AI RPG Platform** — не игра-чат, а симуляционная платформа:

| Роль | Что делает | Видит |
|------|------------|-------|
| **Мастер мира** | JSON-импорт, реестры, terrain/climate/settlement rules | N+1, `system_*`, validator |
| **Игрок** | Выбор мира → персонаж → чат | Только narrative и UI |

Принцип: **движок и геометрия — source of truth**; LLM рендерит факты из БД, не придумывает мир с нуля.

---

## 2. Стек и запуск

| Слой | Технология |
|------|------------|
| Backend | Python 3.14, FastAPI, aiosqlite, SSE |
| Frontend | React 19, Vite 8, Electron, CSS Modules |
| LLM | Qwen (локально), OpenAI, Anthropic — `LLMRouter` |
| БД | SQLite, одна миграция `0001_initial.sql` |
| Dev | `npm run dev` → concurrently backend (`:8000`) + frontend (`:5173` + Electron) |

**Схема БД:** только `backend/app/db/migrations/0001_initial.sql`; после правок — recreate локальной БД, не incremental ALTER.

**Старт:** `validate_schema` на 16 dataclass-моделях при lifespan; climate/terrain scalar columns валидируются через POJO helpers.

---

## 3. Слои backend

```
api/routes          → HTTP, DTO, Depends(get_container)
application/chat    → ChatService, turns, pending, crash recovery
application/engine  → DAG runtime (phases, repair, patches)
application/worldData → CRUD сервисы, persist, generators/
application/jsonValidation → import + runtime resolve (POJO-first v1)
dataModel/          → Pydantic — единственный контракт полей и defaults
db/                 → repositories, models, migrations
core/               → Container, config, logging
```

**Границы (обязательны):**

- Генераторы — только materialize геометрии/layout; без LLM payload и без HTTP.
- API — только transport; без orchestration движка.
- Persist генераторов — в `MapCellService` / `*PersistService` / engine nodes, не внутри generator pure functions.

---

## 4. API (факт)

Префикс `/api`. DI: `request.app.state.container`.

### 4.1 Игровой контур

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/sessions` | список игровых сессий |
| POST | `/sessions` | создать сессию (`world_uid` + `character_id`) |
| GET/DELETE | `/sessions/{id}` | чтение / удаление |
| POST | `/chat` | синхронный turn |
| POST | `/chat/stream` | SSE: `NodeStatusEvent`, `ResultEvent`, `ErrorEvent`, `CancelledEvent` |
| DELETE | `/chat/stream/{request_id}` | отмена |
| GET | `/chat/history`, `/chat/pending`, `/chat/settings` | история, crash recovery, LLM settings |
| PUT | `/chat/settings` | `max_tokens`, `repair_*`, `max_passes`, `language` |

`ChatRequest`: `session_id`, `message`, `llm_provider`, `model`, `request_id`, `resume`, опционально `task_type` (минует intent detection).

### 4.2 Мастер / данные мира

| Группа | Ключевые endpoints |
|--------|-------------------|
| Worlds | CRUD, `POST /worlds/import`, `GET …/export` |
| Locations | CRUD, import, `POST …/generate-settlement` |
| Characters | CRUD, import, copy |
| Races, Perks | CRUD + import per world |
| Map | CRUD cells, `generate-surface/climate/ores/caves/z-slice` |
| Connections | nodes, edges, full graph |
| Seed | import/export таблиц |
| Settings | backend config |
| Debug | `POST /worlds/{uid}/generate-structure` |

**Важно:** `map/generate-*` — **permanent debug harness** (`map.py` docstring). Production materialization — через engine DAG nodes, не через эти HTTP routes.

---

## 5. Engine (факт)

Спека flow: [`tz_engine_flow.md`](./tz_engine_flow.md).

### 5.1 Цепочка

```
ChatService.handle_message
  → pending_repo.upsert (crash recovery)
  → LLMExecutionEngine.run(task_type, message, session)
      → for pass in max_passes:
          GraphCompiler.compile → DAGExecutor.execute
          _apply_task_transition (replan)
      → patch_applier.apply (атомарно)
      → ResponseResolver.resolve → user-facing output
  → message_repo (turn + narrative) при успехе
```

### 5.2 Фазы DAG

| Фаза | Кто | Replan |
|------|-----|--------|
| `pre_llm` | Python nodes (gate) | ✅ `next_task_type` / `requires_replan` |
| `llm` | LLM groups by temperature ASC | repair в `LLMAggregateExecutor` |
| `post_llm` | Python nodes (persist side effects) | ❌ never replan |

### 5.3 Зарегистрированные ноды (~17 id)

**LLM:**

| id | task | deps |
|----|------|------|
| `context_snap_gatherer` | `INTENT_DETECTION` | — |
| `intent_detection` | `INTENT_DETECTION` | `context_snap_gatherer` |

**Python — scene:**

| id | phase | роль |
|----|-------|------|
| `check_scene` | pre_llm | gate: scene exists / location selected |
| `scene_init` | — | инициализация сцены |
| `scene_location_children` | — | дочерние локации |
| `scene_start_location_select` | — | выбор стартовой локации |

**Python — terrain / settlement:**

| id | phase | роль |
|----|-------|------|
| `check_terrain` | pre_llm | gate: cells в DB |
| `eager_terrain` | pre_llm | load existing cells |
| `lazy_terrain` | pre_llm | `TerrainGeneratorService.generate_minimal` |
| `lazy_settlement` | pre_llm | `SettlementGeneratorService.generate_map_cells` |
| `terrain_context` | pre_llm | → `shared_context["terrain"]` |
| `terrain_summary` | pre_llm | summary для downstream |

**Python — climate:**

| id | phase | роль |
|----|-------|------|
| `generate_climate` | post_llm | `ClimateOrchestratorService.apply_climate_pass` |
| `recalculate_climate` | — | partial recalc |
| `resolve_weather` | — | `ClimateRuntimeAssembler` runtime weather |

**Прочее:** `prepare_analysis_context` (заготовка).

### 5.4 TaskType enum vs реализация

В `taskType.py` объявлено **~30** значений (combat, crafting, events, analysis, actions…).

**Реализован pipeline только для:**

```
INTENT_DETECTION
  → (gate) SCENE_INIT | SCENE_START_LOCATION_SELECT
  → SCENE_NARRATION | SCENE_COMBAT | SCENE_CHANGE_LOCATION | LOCAL_*_ANALYSIS
       └── terrain lazy chain (check → eager/lazy → context → summary)
```

### 5.5 Gap: `scene_narration` (осознанный блокер)

`ResponseResolver._OUTPUT_NODE` ожидает ноду `scene_narration` для `TaskType.SCENE_NARRATION`, но **LLM-нода не зарегистрирована** в `engine/nodes/__init__.py`.

Intent detection может вернуть `scene_narration_render` → engine завершит passes → resolver вернёт ошибку «задача завершилась без результата». Аналогично нет нод для большинства user-facing `TaskType`.

**Статус:** осознанный блокер / отложено. Не приоритет разработки и не «критический gap для срочного закрытия». Ранний обрезанный narration на нестабильном входе (`terrain_context` / scene / pack) даёт мало value и будет переписываться; wiring — после стабилизации контракта данных и gate на DAG ([`tz_world_generation_dag.md`](./tz_world_generation_dag.md)). Агенту **не** предлагать vertical slice / narration как следующий шаг по умолчанию.

### 5.6 Инфраструктура engine (готова)

- `GraphCompiler` + Kahn levels + LLM temperature groups
- `DAGExecutor` + parallel levels + SSE node status
- `RepairOrchestrator` + DSL patches
- `PatchApplier` — transactional pending patches
- Cancel/resume: `CancellationToken`, `SessionSnapshot`, `pending_repo`
- Repos в context: `scene_repo`, `location_repo`, `map_cell_repo`, `world_repo`, `player_repo`, `npc_repo`, `state_repo`, persist services

---

## 6. Generators (факт)

Спека иерархии: [`tz_assembler_hierarchy.md`](./tz_assembler_hierarchy.md).  
Tech debt registry: [`tz_generator_technical_debt.md`](./tz_generator_technical_debt.md).

~186 файлов в `application/worldData/generators/`.

### 6.1 Assembler stack

```
SettlementAssembler          ✅ фазы A–F
  └── DistrictAssembler      ✅
        └── StructureAreaAssembler  ✅ (StructureContext v1 stub)
              └── StructureAssembler (registry)  ✅
                    └── StructureGeneratorService  ✅ interior box
        └── DistrictRoadGenerator  ✅ (grid/organic/radial/cul-de-sac/courtyard)
  ⬜ фазы G–H: organic footprint, z-topology
  ⬜ StructureInteriorAssembler (мебель/NPC — нет ТЗ)
```

**Semantic-first:** `economic_tier` → материалы, освещение, дороги, заборы через реестры (`TierResolver`).

### 6.2 Сервисы-фасады

| Сервис | Статус | Выход |
|--------|--------|-------|
| `SettlementGeneratorService` | ✅ | `SettlementLayout` + `MapCell[]` |
| `TerrainGeneratorService` | ✅ | surface → gap → column fill; `generate_minimal` |
| `ClimateGeneratorService` | ✅ | pure climate math |
| `ClimateOrchestratorService` | ✅ | full_surface, recalc, apply_climate_pass |
| `StructureGeneratorService` | ✅ fat | rooms, passages, staircases — deterministic |
| `HydrologyGeneratorService` | **stub** | пустой `HydrologyResult` |

### 6.3 Terrain pipeline

```
pole_field (caller-provided)
  → surfacePass (noise heightmap)
  → gapAnalysisPass
  → columnFillPass → MapCell[]
```

Climate **отделён** от terrain shape; pole field передаётся снаружи (`MapCellService`, debug routes).

### 6.4 Координаты (NC-1)

| Space | Семантика |
|-------|-----------|
| `WORLD_SURFACE_GRID` | grid index occupancy |
| `WORLD_LOCAL_METERS` | settlement geometry (buildings, barriers) |
| `LOCATION_LOCAL_METERS` | interior |

Конверсия только через `generators/coordinates/convert.py`. Persist tag NC-1a — **open**.

### 6.5 Skeleton-first + lazy

| Фаза | Когда | Что |
|------|-------|-----|
| 1 | world create / import | `NamedLocation` skeleton + footprint occupancy |
| 2 | первый gameplay entry | `lazy_settlement` → полная геометрия |

`lazy_settlement` пишет `map_cell_repo.insert_bulk_ignore` напрямую; **connections + building NamedLocations** — через `SettlementPersistService` (отдельный master/debug путь).

### 6.6 Engine ↔ generators

```
check_terrain → eager_terrain ─┐
              → lazy_terrain  ─┼→ terrain_context → terrain_summary
              → lazy_settlement (deps: check_terrain, lazy_terrain)
generate_climate (post_llm, world-level)
resolve_weather (runtime)
```

Генераторы в нодах — module-level singleton; async persist только в `execute()` через `context`.

---

## 7. JSON Validation (факт)

Спека: [`tz_json_validation.md`](./tz_json_validation.md).

| Область | Статус |
|---------|--------|
| Код | `application/jsonValidation/` — POJO-first v1 |
| Import slice `world` | climate scalars, tiers, materials, terrain, hydrology, climate_zones ✅ |
| Runtime | `worldRow` — warn-only resolve ✅ |
| Bundle `connection_*` | JV-0b ✅ |
| Races, perks, locations bundle | ⬜ |
| `worldSlices.py` реестр | ✅ |

**Принцип:** `dataModel/` — source of truth; resolve поверх POJO, не параллельные default-таблицы.

---

## 8. Frontend (факт)

Спека: [`tz_frontend.md`](./tz_frontend.md).

| Route | Страница |
|-------|----------|
| `/` | список сессий |
| `/new` | выбор мира |
| `/new/:worldId` | выбор персонажа |
| `/chat/:sessionId` | чат (SSE stream) |
| `/settings/backend` | настройки LLM/backend |
| `/settings/world` | placeholder редактора миров |

Feature-slices: `session`, `chat`, `settings`. API base: `VITE_API_URL` (default `http://127.0.0.1:8000/api`).

---

## 9. Данные и fixtures

- Хранение: [`project_data_storage_tz.md`](./project_data_storage_tz.md) — `system_*` / `display_*`, N+1.
- Тестовый мир: `fixtures/world_test.json` (~429 строк).
- Импорт: `/api/worlds/import`, `/api/seed/import`, `/api/characters/import`.

**Основные таблицы:** `worlds`, `game_sessions`, `players`, `npcs`, `named_locations`, `map_cells`, `connection_nodes/edges/edge_cells`, `messages/turns`, `session_pending`, `states`.

---

## 10. Что работает end-to-end (2026-07-04)

| Контур | Статус |
|--------|--------|
| Dev stack (backend + vite) | ✅ |
| Session CRUD + frontend list | ✅ |
| Chat SSE + cancel/resume skeleton | ✅ |
| World/character import | ✅ |
| Intent detection LLM + repair | ✅ |
| Scene gate (init / location select) | ✅ |
| Lazy terrain anchor cell | ✅ |
| Lazy settlement geometry (map_cells) | ✅ partial persist |
| Terrain context → shared_context | ✅ |
| Debug: map surface/climate, structure, settlement | ✅ |
| **Player narration turn** | ❌ осознанный блокер — нет `scene_narration` node (§5.5) |
| Hydrology | ❌ stub |
| Interior furnishing | ❌ не начато |
| Большинство TaskType | ❌ enum only |

---

## 11. Известные пробелы engine path (не backlog-priority)

Факт состояния кода; **не** упорядоченный план «сделать следующим»:

1. **`scene_narration` LLM-node** — осознанный блокер (§5.5, §12). `_OUTPUT_NODE` уже ждёт id; регистрация отложена до стабильного входа и gate DAG.
2. **`lazy_settlement` → полный outdoor persist** — connections graph + building `NamedLocations` через `SettlementPersistService`.
3. **Eager world surface** (опционально для wilderness) — `eager_terrain` сейчас только load; full `generate_surface` только debug HTTP / будущая engine node.

---

## 12. Сознательно отложено

| Тема | Документ | Статус |
|------|----------|--------|
| **`scene_narration` / player narration turn** | этот snapshot §5.5 | **осознанный блокер** — не пилить interim |
| Lazy simulation LOD | `tz_lazy_simulation.md` | концепция |
| Multiplayer | `tz_multiplayer.md` | концепция |
| World editor UI | `tz_frontend.md` | placeholder |
| Perception nodes | `tz_perception.md` | не в DAG |
| Crafting, economy sim | `tz_crafting.md`, `tz_economy.md` | не в engine |
| Hydrology impl | `tz_terrain_hydrology.md` | stub |
| Автотесты engine/DAG | — | почти нет |

---

## 13. Связанные документы

| Документ | Когда читать |
|----------|--------------|
| [`tz_engine_flow.md`](./tz_engine_flow.md) | детали фаз, repair, patches |
| [`tz_assembler_hierarchy.md`](./tz_assembler_hierarchy.md) | settlement stack target |
| [`tz_city_generation.md`](./tz_city_generation.md) | город, lazy phases |
| [`tz_terrain_generation.md`](./tz_terrain_generation.md) | terrain passes, persist |
| [`tz_climate.md`](./tz_climate.md) | pole/local tiers |
| [`tz_json_validation.md`](./tz_json_validation.md) | import validator |
| [`tz_generator_technical_debt.md`](./tz_generator_technical_debt.md) | smells registry |
| `.cursor/rules/project-context.mdc` | правила для агента |

---

## 14. История снимка

| Версия | Дата | Изменения |
|--------|------|-----------|
| 1.0 | 2026-07-04 | Первый снимок: API, engine, generators, JV, gaps |
| 1.1 | 2026-07-20 | Убран приоритет vertical slice; `scene_narration` зафиксирован как осознанный блокер (§5.5, §11, §12) |

**Правило обновления:** при закрытии осознанного блокера из §12 / изменении пробелов §11 — bump minor version и строка в §10–§12.
