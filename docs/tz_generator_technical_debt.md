# Generator Technical Debt

**Тип:** инженерное ТЗ / living registry (не player-facing).  
**Scope:** `backend/app/application/worldData/generators/` — settlement, district, area, terrain, climate, structure, coordinates.  
**Обновлено:** climate v2.1 pole/local + CL-2 tier resolve (2026-06).

**Связанные документы:**

| Документ | Роль |
|---|---|
| [tz_assembler_hierarchy.md](./tz_assembler_hierarchy.md) | Целевая архитектура assembler stack |
| [tz_city_generation.md](./tz_city_generation.md) | Продуктовое ТЗ города |
| [tz_terrain_generation.md](./tz_terrain_generation.md) | Продуктовое ТЗ terrain |
| [tz_climate.md](./tz_climate.md) | Продуктовое ТЗ climate (pole/local tiers) |
| `.cursor/plans/settlement-assembler.md` | Phase-план settlement |
| `.cursor/plans/coordinate-spaces.md` | Phase-план NC-1 |

---

## Как читать registry

| Поле | Значение |
|---|---|
| **ID** | Стабильный идентификатор smell |
| **Severity** | `high` / `medium` / `low` / `info` |
| **Status** | `open` / `partial` / `resolved` |
| **P** | Приоритет polish: P1 (скоро) … P3 (когда будет время) |

**Правило:** новый smell → новый ID; resolved не удалять (история).

---

## God-object verdict

**В иерархии assembler'ов (Settlement → District → Area) god-object'ов нет.**

| Класс | Роль | Verdict |
|---|---|---|
| `SettlementAssembler` | pipeline-оркестратор | OK |
| `DistrictAssembler` | slot → areas + district roads | OK |
| `StructureAreaAssembler` | area-оркестратор | OK |
| `SettlementGeneratorService` | lazy persist facade | OK |
| `StructureGeneratorService` | полный pipeline интерьера | Fat service (**соседний домен**, не settlement stack) |

**Fat modules (следить, не god-class):**

| Модуль | ~строк | Смешение |
|---|---|---|
| `planner/streets.py` | 360+ | entry nodes + city graph + material/sidewalk policy |
| `districtAssembler/planner/areaSlots.py` | 250+ | bin-packing + tier filter + slot factory |
| `planner/placement.py` | 220+ | specialization + conditions + zone |
| `planner/barriers.py` | 175+ | size policy + tier pick + plan + emit |
| `terrain/terrainGeneratorService.py` | ~70 | thin facade → `ClimateOrchestratorService` (was monolith — см. FM-1) |
| `planner/footprint.py` | 190+ | sizing + gates + coordinate facade + deprecated aliases |

---

## Resolved smells

| ID | Было | Решение | Status |
|---|---|---|---|
| R-1 | Gate geometry в `streets.py` | `footprint.footprint_gate_coordinates` | resolved |
| R-2 | `DistrictAssembler._assign_template` dead code | удалён | resolved |
| R-3 | barriers → streets import | убран | resolved |
| R-4 | `area.barrier_cells` не persist'ились | `layoutCells` collect fix | resolved |
| R-5 | Дубли barrier ring/material | `generators/barrier/{perimeter,material,cells}.py` | resolved |
| R-6 | Per-edge sidewalk на city entry links | `connectionPolicy` + `streets` | resolved |
| R-7 | `road_tier_bonus` отсутствовал | `roadTravelResolver.py` | resolved |
| R-8 | `PLAN.md` в дереве кода | `.cursor/plans/` | resolved |
| R-9 | NC-1 anchor=0 маскирует mix grid/meters | `generators/coordinates/` Phase 1–5 | partial → см. NC-1 |
| R-10 | Terrain footprint `(map_x±1)` | `settlement_grid_rect` в terrain (removed) | resolved |
| R-13 | Terrain coupled to cities (urban fallback + city Voronoi) | wilderness + zone Voronoi only | resolved |
| R-14 | Climate logic inside terrain | `generators/climate/` + terrain delegates | resolved |
| CL-1 | Climate Voronoi from admin zones only | pole/local tiers + orchestrator + `tierResolve` | partial → CL-2b admin merge |
| CL-2 | Global local Voronoi kills pole tier | `tierResolve.py` world-relative r + temp blend | resolved |
| CL-13 | Tier resolution docs vs code | `tz_climate.md` § на ячейке | resolved |
| R-11 | `collect_map_cells` silent mix | split `collect_surface_grid_*` / `collect_geometry_meter_*` | resolved |
| R-12 | Inline `// cell_size_m` в planners | только `coordinates/convert.py` | resolved |

---

## Implicit contracts (NC)

### NC-1 — Coordinate spaces (grid index vs world meters)

**Status:** `partial` (Phase 1–6 docs ✅; persist tag NC-1a — open)

**Три независимые оси (не смешивать):**

| Ось | Суть |
|---|---|
| `measurement_system` | imperial/metric — **только display/LLM**; БД в метрах |
| `INTERIOR_CELL_SIZE_M = 1` | fine step = 1 м — **совпадение масштаба**, не imperial |
| **NC-1 core** | `MapCell.x/y` = grid index **или** absolute meters — разная семантика |

**Модель (v1):**

```
WORLD_SURFACE_GRID     gx, gy     tile index; step = map_cell_size_m (dynamic, ≥2000, ×1000)
WORLD_LOCAL_METERS     x, y, z    settlement outdoor, nodes, barriers, buildings after translate
LOCATION_LOCAL_METERS  x, y, z    interior — v2, отложено
```

**Сделано (Phase 1–5):**

- `generators/coordinates/` — convert hub, typed rects, `settlement_origin_m`
- Terrain decoupled from cities; urban via settlement / explicit `map_cells`
- Persist split Option A (grid occupancy + meter geometry)
- Smoke `map_x=0` и `map_x=3000`, `cell_m=5000`

**Открыто (NC-1 follow-up):**

| Sub-ID | Severity | Проблема | Fix |
|---|---|---|---|
| NC-1a | medium | `MapCell` PK без `coordinate_space`; merged upsert без tag | v2 DB column или Option B |
| NC-1b | ~~medium~~ | ~~Product docs § coordinates~~ | ✅ `tz_terrain_generation.md` rework |
| NC-1c | medium | Non-city anchors в terrain: `x=anchor.map_x` (meters?) vs cities (grid) | `meters_to_grid` или явный point-anchor contract |
| NC-1d | low | Voronoi climate: grid corner of **zone** anchor, не центр rect | doc или center-of-rect |
| NC-1e | low | Half-open meter rect `[x0,x1)` vs gates **on** boundary `y=side_m` | inclusive boundary helper или doc |
| NC-1f | info | NewType phantom — ORM/`ConnectionNode`/`DistrictSlot` still `int` | discipline + boundaries; optional strict mypy |
| NC-1g | low | `map_settings.global_cell_size_m` — ghost override, нет на `World` | поле модели или удалить ветку |
| NC-1h | low | `needs_geometry` только `system_building_element`; barriers-only → re-gen | расширить heuristic или doc limitation |

**Refs:** `.cursor/plans/coordinate-spaces.md`

---

### NC-2 — `AreaSlot.cells` ≠ «участок с двором»

**Status:** `open` | **Severity:** medium | **P:** P1

Docstring `AreaSlot`: «здание + двор + забор». `_make_area_slot` заполняет **только bbox `occupied_footprint`**.  
Area barrier: `_PARCEL_MARGIN_M = 1` снаружи bbox — workaround.

**Fix:** расширять cells в `areaSlots._make_area_slot` (parcel = footprint + padding).

---

### NC-3 — Три barrier pipeline, разная gate-политика

**Status:** `open` | **Severity:** medium | **P:** P2

| Уровень | Gate coords | Template pick |
|---|---|---|
| Settlement | `footprint_gate_coordinates` | `pick_barrier_template_type` heuristic |
| Area | `gate_on_facing_edge` (1 gate) | `building.perimeter_barrier` |
| District | не реализован | — |

`barrier_template_registry.gates/height_levels/towers` **не читаются** (v1).

---

### NC-4 — `location_uid` на outdoor barrier cells

**Status:** `open` | **Severity:** low | **P:** P2

| Уровень | `location_uid` |
|---|---|
| Settlement walls | `settlement.location_uid` |
| Area fence | `building.location_uid` |

Persist через `collect_map_cells_from_layout` — контракт не в product docs.

---

### NC-5 — Probe cache → rebind

**Status:** `open` | **Severity:** low | **P:** P2

`buildingCache` → probe uid → `translate_layout` → **`rebind_layout_to_building`** обязателен.  
Double rebind на persist path (idempotent, неочевидно).

---

### NC-6 — RNG seeds (детерминизм)

**Status:** `open` | **Severity:** info | **P:** P3

Разные seed per sub-system (streets, barriers, area, district) — работает, но контракт не документирован.

---

### NC-7 — Sidewalk policy split

**Status:** `open` | **Severity:** info | **P:** P3

City perimeter: density; city entry links: district template; district edges: `connectionPolicy`.  
Perimeter не учитывает template района — v1 compromise.

---

### NC-8 — `World` registry shapes

**Status:** `open` | **Severity:** low | **P:** P3

`building_template_registry` / `barrier_template_registry` — dict в модели, list-like в коде.  
**Fix:** validator при JSON import.

---

### NC-9 — `settlement_density` на NamedLocation

**Status:** `open` | **Severity:** low | **P:** P3

`getattr(settlement, "settlement_density", None)` — не поле модели, dynamic attr.

---

## Mixed responsibility (MR)

| ID | Severity | Где | Проблема | Fix | Status |
|---|---|---|---|---|---|
| MR-1 | medium | `buildingCache.py` | cache + registry import + probe + `derive_structure_context` | split cache / context | open |
| MR-2 | medium | `layoutCells.py` | collect + rebind + `needs_geometry` | rebind → structure; probe → service | partial (split collect ✅) |
| MR-3 | low | `StructureAreaAssembler` | 4 шага в оркестраторе | OK as orchestrator | accepted |
| MR-4 | low | `streets.py` | graph + policy | policy → `road/` | open |
| MR-5 | info | `settlementAssembler/planner/` defaults | smoke defaults cross-import | `generators/defaults/` | open |
| MR-6 | medium | `footprint.py` | sizing + gates + facade + deprecated + `district_templates` | split `footprintSizing.py` + thin facade | open |

---

## Layer coupling (LC)

**Целевое направление:** neutral packages (`generators/barrier/`, `generators/registries/`, `generators/structure/`, `generators/coordinates/`).

| ID | From → To | Severity | Fix | Status |
|---|---|---|---|---|
| LC-1 | area → settlement.barrierDefaults | medium | `generators/barrier/defaults.py` | open |
| LC-2 | district → settlement.buildingDefaults | medium | `generators/registries/buildingDefaults.py` | open |
| LC-3 | area → settlement.layoutCells.rebind | medium | `generators/structure/layoutRebind.py` | open |
| LC-4 | settlement.buildingCache → area.derive_structure_context | medium | `structureAssembler/structureContext.py` | open |
| LC-5 | settlement.barriers → settlement.barrierDefaults | low | same as LC-1 | open |
| LC-6 | terrain → settlement.planner.footprint | medium | removed — terrain uses `coordinates/` only | resolved |

---

## Duplication (DR)

| ID | Severity | Где | Суть | Fix | P |
|---|---|---|---|---|---|
| DR-1 | medium | `footprint_gate_line_coords` vs `streets._grid_lines` | один алгоритм span lines, разный step | `span_lines(origin, side_m, step)` | P2 |
| DR-2 | low | `footprint.py` facade | 3 слоя rect API + deprecated names | удалить deprecated после миграции smoke | P3 |
| DR-3 | low | `settlement_origin_m` + `settlement_origin()` tuple | dual API | один путь | P3 |
| DR-4 | low | `(cell_m, side_m, size)` в каждом caller | повтор bundle resolution | `SettlementFootprintContext` dataclass | P3 |
| DR-5 | low | `_smoothstep`, `_dist` (hypot) | `climatePoleField.py` + `tierResolve.py` | `generators/climate/math.py` или shared | P2 |

---

## Fat methods / modules (FM)

| ID | Severity | Где | Fix | P |
|---|---|---|---|---|
| FM-1 | medium | `TerrainGeneratorService` monolith | thin facade → `ClimateOrchestratorService` | resolved |
| FM-2 | medium | `streets.plan_city_street_grid` | split graph vs policy | P3 |
| FM-3 | low | `pick_barrier_template_type` | registry-driven pick; см. § ниже | P2 |

---

## `pick_barrier_template_type` — review pass

**Файл:** `planner/barriers.py`. v1 smoke-эвристика; `docs/tz_locations.md` § `barrier_template_registry` не полностью отражён.

**As-is:**

```
economic_tier rank ≤ basic     → wooden_fence
economic_tier rank ≥ quality   → city_wall
system_city_size ∈ city+       → city_wall
иначе                          → stone_fence
```

**Checklist:** tier vs city_size priority; empty registry fallback; unused `rng`; hardcoded system_type; `should_have_settlement_wall` 0.75; template fields ignored.

---

## Polish backlog (сводная)

Легенда: **✅** — пройдено в текущем цикле; без пометки — open.

### ✅ Climate sprint (2026-06) — пройдено

| ID | Результат |
|---|---|
| **CL-2** | `tierResolve.py`: pole base + world-relative `climate_local_influence_fraction` + temp smoothstep band |
| **CL-13** | `tz_climate.md` § tier resolution синхронизирован |
| **R-14** | Climate вынесен из terrain → `generators/climate/` + assembler |
| **FM-1** | `TerrainGeneratorService` → thin facade (~70 строк) |
| **CL-1** | pole/local tiers, passes, orchestrator, auto без elevation→zone (остаток: **CL-2b** admin merge) |

Smoke: `test_climate_*`, `test_climate_tier_resolve` в `debug_settlement.py`.

### P1 — settlement / coordinates

| ID | Действие | Status |
|---|---|---|
| ~~NC-1b~~ | ✅ `tz_terrain_generation.md` rework | resolved |
| NC-1a | Persist contract / optional `coordinate_space` column | open |
| LC-1..LC-4 | Neutral packages | open |
| NC-2 | Parcel cells в `areaSlots` | open |

### P2 — ближайший polish

| ID | Действие | Status |
|---|---|---|
| MR-1, MR-2, MR-6 | Split cache / rebind / footprint facade | open |
| NC-3, NC-4 | Barrier contract в product docs | open |
| DR-1, FM-3 | span_lines; barrier pick | open |
| **CL-3** | Единый `ClimateSpatialSample` / Protocol | open |
| **CL-4** | `climate_pole_mode` читать или удалить поле | open |
| **CL-2b** | Admin в `build_merged_field`, но не в tier resolve — мёртвые anchors | open |
| **CL-10, CL-11** | heightmap pass purity; `_non_surface_anchor_cells` | open |
| **CL-12, DR-5** | Shared helpers: anchors, z_to_terrain, seed, smoothstep/dist | open |

### P3 — когда будет время

| ID | Действие | Status |
|---|---|---|
| MR-4, FM-2 | Split `streets.py` | open |
| NC-6..NC-9 | Docs / model fields / validators | open |
| DR-2, DR-3, DR-4 | API cleanup после Phase 6 | open |
| **CL-5..CL-9** | pole runtime validation; RecalcTrigger; legacy coarse; CGS split | open |
| **CL-2a, CL-2c..CL-2e, CL-14** | tierResolve edge cases + doc (см. § CL) | open / accepted |

---

## Climate v2.1 — smells registry (CL)

**Status:** `partial` — eager pipeline ✅ · tier resolve ✅ · polish CL-3..CL-12 open  
**Refs:** [tz_climate.md](./tz_climate.md)

### Implicit contracts

| ID | Severity | P | Проблема | Fix | Status |
|---|---|---|---|---|---|
| CL-2 | high | — | ~~Global local Voronoi kills pole~~ | `tierResolve.py` | **resolved** |
| CL-3 | medium | P2 | `PoleClimateSample` vs `SurfaceClimateSample`; tier blend добавляет 3-й путь маппинга | единый spatial sample | open |
| CL-4 | medium | P2 | `climate_pole_mode` не читается в `poleResolve.py` | read mode или drop field | open |
| CL-5 | medium | P3 | Max 1 `climate_pole` только на import | validator upsert + resolve assert | open |
| CL-6 | low | P3 | `pole_kind` / `weight` через convention на `NamedLocation` | contract или doc | open |
| CL-7 | low | P3 | `RecalcTrigger` stub в `recalculate()` | bbox routing или `@stub` | open |
| CL-8 | low | P3 | Legacy `build_coarse_field` / `build_zone_field` в main path не используются | deprecate / v1 entry | open |
| CL-2a | low | P3 | `uid_map` в `resolve_tier_sample` не используется | убрать или walk-up local | open |
| CL-2b | medium | P2 | Admin anchors в `build_merged_field`, но tier resolve их skip → мёртвые entries в `local_field` | не merge admin при active pole; split fields | open |
| CL-2c | info | P3 | `r` cap `dist_to_2nd/2` **per-cell** — неочевидно из ТЗ | doc / comment in `tierResolve` | open |
| CL-2d | info | — | Скачок zone/rainfall на `dist = r` (temp smooth, zone hard) | accepted v2.2 compromise; zone blend → v3 | **accepted** |
| CL-2e | info | P3 | `pole_field.bbox is None` → modifiers игнорируются | assert bbox on resolve или fallback doc | open |

### God-object / concentration

| ID | Severity | P | Проблема | Fix | Status |
|---|---|---|---|---|---|
| CL-9 | low | P3 | `ClimateGeneratorService` utility god + lazy import cycle с `tierResolve` | pure pole sample; split physics | open |

### Mixed responsibility

| ID | Severity | P | Проблема | Fix | Status |
|---|---|---|---|---|---|
| CL-10 | medium | P2 | `heightmapPass`: terrain + pole climate bias | shared sampler; pure terrain pass | open |
| CL-11 | medium | P2 | `_non_surface_anchor_cells` + private heightmap imports | fixture pass; public helpers | open |

### Duplication (climate)

| ID | Severity | P | Проблема | Fix | Status |
|---|---|---|---|---|---|
| CL-12 | medium | P2 | `_static_anchors`, `_z_to_terrain`, `_world_seed` × файлов | shared hub (см. DR-5) | open |

### Docs / product sync

| ID | Severity | P | Проблема | Fix | Status |
|---|---|---|---|---|---|
| CL-13 | info | — | Tier resolution docs vs code | synced in `tz_climate.md` | **resolved** |
| CL-14 | info | P3 | Таблица tier-2 в `tz_climate.md` всё ещё lists admin fallback; cell resolve admin off | уточнить «merge vs resolve» в docs | open |

---

## Out of scope (не tech debt этого registry)

- Imperial conversion in generators (display only)
- Hex / organic footprint (settlement Phase G/H)
- Full interior `LOCATION_LOCAL_METERS` (coordinate Phase 7)
- Persist `SettlementLayout` → connection_nodes/edges в БД (product backlog)

---

## Changelog

| Дата | Изменение |
|---|---|
| 2026-06 | NC-1 Phase 1–5; `tz_terrain_generation.md` full rework (Phase 6) |
| 2026-06 | Climate v2.1: pole/local tiers, `tierResolve.py`, CL-2/CL-13 resolved |
| 2026-06 | Polish backlog rework; CL-2a..CL-2e, CL-14, DR-5 added; FM-1 resolved |
