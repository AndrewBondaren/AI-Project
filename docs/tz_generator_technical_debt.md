# Generator Technical Debt

**Тип:** инженерное ТЗ / living registry (не player-facing).  
**Scope:** `backend/app/application/worldData/generators/` — settlement, district, area, terrain, climate, structure, coordinates.  
**Adjacent (orchestration hooks):** `mapCellService.py`, `api/routes/map.py`, `backend/scripts/debug_*.py`.  
**Обновлено:** post TR-1b/DBG-1 architecture review — terrain/map orchestration smells (2026-06).

**Связанные документы:**

| Документ | Роль |
|---|---|
| [tz_assembler_hierarchy.md](./tz_assembler_hierarchy.md) | Целевая архитектура assembler stack |
| [tz_city_generation.md](./tz_city_generation.md) | Продуктовое ТЗ города |
| [tz_terrain_generation.md](./tz_terrain_generation.md) | Продуктовое ТЗ terrain |
| [tz_terrain_hydrology.md](./tz_terrain_hydrology.md) | Гидрология: моря, озёра, реки (target) |
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
| `terrain/terrainGeneratorService.py` | ~120 | thin facade + passes (was monolith — см. FM-1) |
| `climateAssembler/climateSurfaceAssembler.py` | ~220 | orchestrator + `_non_surface_anchor_cells` cell synthesis |
| `scripts/debug_settlement.py` | ~1500 | settlement + coordinates + terrain + climate smoke (см. DBG-2) |
| `climate/precipitation.py` | ~180 | physics + liquid overlay helpers |
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
| MR-7 | medium | `mapCellService.py` | CRUD/import + `save_terrain_batch` (pole, chunking, gap stats, persist) | `TerrainBatchOrchestrator` или DAG node; service → repo only | open |

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
| DR-6 | low | `terrain_set` comprehension | inline ×6 (`columnFillPass`, `heightmapPass`, `liquidOverlayPass`, `cavesGenerator`, `generate_minimal`, `_non_surface_anchor_cells`); `_terrain_set` только в `columnFillPass` | `terrain_registry_set(world)` в `terrain/terrainZ.py` | P2 |
| DR-7 | low | lazy single-cell weather MapCell | `TerrainGeneratorService.generate_minimal` ≈ `ClimateSurfaceAssembler._non_surface_anchor_cells` | shared `build_weathered_anchor_cell(...)` | P3 |
| MAP-1 | low | `api/routes/map.py` | 4× fetch world/locations; 6× `status_code`/`JSONResponse`; module-level `_terrain_generator` / `_climate_orchestrator` | route dep `load_world_context`; container factory | P3 |

---

## Fat methods / modules (FM)

| ID | Severity | Где | Fix | P |
|---|---|---|---|---|
| FM-1 | medium | `TerrainGeneratorService` monolith | thin facade → `ClimateOrchestratorService` | resolved |
| **TR-1** | **high** | Multi-pass terrain skeleton + climate pass split | ✅ impl 2026-06 — см. [`tz_terrain_generation.md`](./tz_terrain_generation.md) § Impl queue |
| **HY-1** | **high** | Liquid = global `z≤0` overlay; нет carve рек/озёр/морских basin | Phase **D HY** (H-1…H-7a) — [`tz_terrain_generation.md`](./tz_terrain_generation.md) § Phase 9+; [`.cursor/plans/hydrology-pre-dag.md`](../.cursor/plans/hydrology-pre-dag.md) | open |
| **HY-2** | medium | Cave STUB без подземной воды / ecosystem | U12: `CaveHydrologyService` в `generate-caves` (Phase B); `cave_liquid_candidate` ≠ surface mask | open |
| **HY-3** | medium | Нет LLM naming для autoresolved geography | U13: `llm_name_procedural_locations` + persist; **после DAG**, gate `materialize_named_locations` | open |
| **HY-4** | low | `type_classify` null в template без normalize | U22: import validator подставляет schema defaults и пишет explicit values; runtime fallback до validator | open |
| **TR-1b** | medium | Generator isolation: pole resolve **вне** `TerrainGeneratorService` | **resolved** — `MapCellService` / `map.py`; `pole_field` аргумент |
| **DBG-1** | medium | `debug_settlement.py` pipeline smoke in-process | **resolved** — HTTP path **2** + `debug_api_helpers.py` |
| **TR-M** | low | Magma antipode teleport (edge case) | **partial** — skeleton band + `antipode_xy`; M-3 movement ⬜ |
| FM-2 | medium | `streets.plan_city_street_grid` | split graph vs policy | P3 |
| FM-3 | low | `pick_barrier_template_type` | registry-driven pick; см. § ниже | P2 |
| DBG-2 | medium | `scripts/debug_settlement.py` monolith (~1500 строк) | split `debug_climate.py` / core settlement smoke; shared `make_test_world()` | P2 |

---

## Terrain / map orchestration — smells registry (TR)

**Status:** post TR-1b + DBG-1 review (2026-06). Terrain generator isolation ✅; smells сместились в orchestration, debug harness, implicit pass contracts.

**Refs:** [tz_terrain_generation.md](./tz_terrain_generation.md), [tz_world_generation_dag.md](./tz_world_generation_dag.md) § «Три входа».

### Hardcodes

| ID | Severity | P | Проблема | Fix | Status |
|---|---|---|---|---|---|
| TR-3 | medium | P2 | ~~Defaults разбросаны: padding, chunk, N_base, z bounds~~ | `World` fields + `terrain/worldMapSettings.py` (`world_z_min/max` fallback −8000…8000) | **resolved** |
| TR-H1 | low | P3 | Terrain type fallbacks в `terrainZ.py`: `"plains"`, `["earth","plains"]`, `"magma"` | registry-driven или explicit world default terrain | open |
| TR-H2 | info | P3 | Stubs ores/caves: 3%, `"iron"`, XOR magic constants | OK до Phase B; пометить в terrain TZ | accepted |

### God-object / concentration

| ID | Severity | P | Проблема | Fix | Status |
|---|---|---|---|---|---|
| TR-G1 | low | P3 | `ClimateGeneratorService` utility god (sampling + weather + legacy Voronoi) | см. **CL-9** — split physics | open |
| DBG-2 | medium | P2 | `debug_settlement.py` — mega harness (settlement + NC + terrain + climate) | split modules + test factories | open |

### Large modules (terrain/climate zone)

Passes (`surfacePass`, `columnFillPass`, …) — OK (40–96 строк). Fat: `climateSurfaceAssembler` ~220, `precipitation` ~180, `poleResolve` ~180, `debug_settlement` ~1500.

### Duplication

| ID | Severity | P | Проблема | Fix | Status |
|---|---|---|---|---|---|
| DR-6 | low | P2 | `terrain_set` inline ×6 | `terrain_registry_set(world)` | open |
| DR-7 | low | P3 | lazy anchor cell builder duplicated | shared helper | open |
| MAP-1 | low | P3 | `map.py` route boilerplate | deps / helper | open |
| TR-2 | medium | P2 | Debug path S→CL: double `run_pole_resolve_pass` | **deferred** — snapshot-run (§ `tz_city_generation.md` §11.4); не orchestrated HTTP | deferred |

### Mixed responsibility

| ID | Severity | P | Проблема | Fix | Status |
|---|---|---|---|---|---|
| MR-7 | medium | P2 | `MapCellService.save_terrain_batch` / `save_z_slice`: persist layer знает pole, chunking, gap logging | extract `TerrainBatchOrchestrator` (симметрия с `ClimateOrchestratorService`) | open |
| TR-5 | low | P3 | `TerrainGeneratorService.generate_minimal` — terrain facade + inline climate (lazy gameplay) | lazy node: stub + climate pass или shared DR-7 helper; document until DAG | open |
| TR-8 | medium | P2 | `ClimateSurfaceAssembler._non_surface_anchor_cells` — orchestrator синтезирует MapCell (imports вынесены — CL-11 ✅, pass extraction — нет) | `passes/nonSurfaceAnchorPass.py` | open |
| MAP-2 | low | P3 | `map.py` — HTTP + pipeline wiring + module singleton generators | container / deps | open |

### Implicit contracts / side effects

| ID | Severity | P | Проблема | Fix | Status |
|---|---|---|---|---|---|
| TR-6 | medium | P2 | `save_pass(layer: str)` — `"terrain"`/`"climate"`/`"ore"`/`"cave"`; какие поля перезаписывает — только в repo, не в типе | enum + documented upsert field matrix (`tz_terrain_generation.md` или repo docstring) | open |
| TR-7 | low | P3 | Два persist API: `save_generated` → INSERT OR IGNORE (lazy); `save_pass` → layer upsert | document semantics; converge when DAG stable | open |
| TR-4 | medium | P3 | `save_z_slice` / `generate_z_slice`: полный heightmap + gap analysis для одной `(gx, gy)` | cache heightmap per world bbox или explicit lazy contract | open |
| CL-16 | low | P3 | `cellWeatherPass`: `location_uid` берётся из `sample.zone_location_uid`, не из исходного cell | doc или preserve cell attribution | open |
| CL-7 | medium | P2 | `recalculate`: `run_cell_weather` gate'ит liquid, не weather; нет `run_liquid_overlay` | split flags per [`tz_climate.md`](./tz_climate.md) § C2 | partial |

### Рекомендуемый порядок (без DAG)

1. ~~**TR-2**~~ — deferred → snapshot-run  
2. **MR-7** — extract terrain batch orchestrator из `MapCellService`  
3. **DR-6** — `terrain_registry_set`  
4. **DBG-2** — split debug scripts  
5. **TR-6** — upsert field matrix doc  

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
| **CL-15** | `precipitation_liquid`, `precipitation.py`, peak clamp, debug/warning logs |
| **CL-4** | `PoleMode` + `_should_autoresolve` in `poleResolve.py` |
| **CL-2b** | `include_admin_fallback=pole_field.is_empty()` |
| **CL-2a, CL-2e** | tierResolve: drop uid_map; modifier bbox fallback |
| **CL-10..CL-12, DR-5** | `climate/math.py`, `locations.py`, `terrainZ.py`; heightmap purity |
| **CL-5** | runtime fallback ✅ (>1 pole и др.); import validator ⬜ после фиксации JSON-контрактов |
| **CL-13** | `tz_climate.md` § tier resolution синхронизирован |
| **CL-14** | `tz_climate.md` § merge vs resolve admin zones |
| **R-14** | Climate вынесен из terrain → `generators/climate/` + assembler |
| **FM-1** | `TerrainGeneratorService` → thin facade (~70 строк) |
| **CL-1** | pole/local tiers, passes, orchestrator, auto без elevation→zone (остаток: **CL-2b** admin merge) |

Smoke: `test_climate_*` (11 tests) в `debug_settlement.py`.

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
| **CL-4** | `climate_pole_mode` в `poleResolve.py` | **resolved** |
| **CL-2b** | Admin не merge при active pole | **resolved** |
| **CL-10, CL-11** | heightmap: pole_field.sample only; public helpers | **resolved** |
| **CL-12, DR-5** | Shared helpers → `climate/math.py`, `locations.py`, `terrainZ.py` | **resolved** |
| **TR-2** | Double pole-resolve debug S→CL | **deferred** → snapshot |
| **MR-7, TR-8** | MapCellService orchestration; non-surface pass extraction | open |
| **DR-6, DBG-2** | `terrain_registry_set`; split `debug_settlement.py` | open |
| ~~**TR-3**~~ | Generation defaults → `worldMapSettings.py` | **resolved** |
| **TR-6** | Layer upsert matrix | open |

### P3 — когда будет время

| ID | Действие | Status |
|---|---|---|
| MR-4, FM-2 | Split `streets.py` | open |
| NC-6..NC-9 | Docs / model fields / validators | open |
| DR-2, DR-3, DR-4 | API cleanup после Phase 6 | open |
| **CL-7** | contracts `ClimateChangeEvent`/`ClimateRecalcRequest` ✅; node routing spec ✅; generator impl + node ⬜ |
| **CL-5, CL-6, CL-8, CL-9** | validator; pole contract; legacy deprecate; CGS split | open |
| **CL-2a, CL-2c..CL-2e** | tierResolve edge cases (см. § CL) | open / accepted |
| **TR-4, TR-5, TR-7** | z-slice full recompute; `generate_minimal`; dual persist API | open |
| **DR-7, MAP-1, MAP-2, CL-16** | lazy cell helper; map.py boilerplate; location_uid attribution | open |

---

## Climate v2.1 — smells registry (CL)

**Status:** `partial` — eager v2.3 ✅ · contracts recalc/runtime ✅ · generator impl recalc/weather ⬜ · DAG nodes ⬜  
**Refs:** [tz_climate.md](./tz_climate.md)

### Implicit contracts

| ID | Severity | P | Проблема | Fix | Status |
|---|---|---|---|---|---|
| CL-2 | high | — | ~~Global local Voronoi kills pole~~ | `tierResolve.py` | **resolved** |
| CL-3 | medium | P2 | `PoleClimateSample` vs `SurfaceClimateSample`; tier blend добавляет 3-й путь маппинга | единый spatial sample | open |
| CL-4 | medium | P2 | ~~`climate_pole_mode` не читается~~ | `PoleMode` + `_should_autoresolve` | **resolved** |
| CL-5 | medium | P3 | Import validator max 1 `climate_pole`, refs — **отложен** до фиксации JSON-контрактов | validator upsert (+ editor); runtime fallback **не убирать** | **partial** — fallback ✅ |
| CL-6 | low | P3 | `pole_kind` / `weight` через convention на `NamedLocation` | contract или doc | open |
| CL-7 | low | P3 | ~~RecalcTrigger stub~~ | contracts ✅; routing в `recalculate_climate` node; generator impl ⬜ | **partial** |
| CL-8 | low | P3 | Legacy `build_coarse_field` / `build_zone_field` в main path не используются | deprecate / v1 entry | open |
| CL-2a | low | P3 | ~~`uid_map` в `resolve_tier_sample` не используется~~ | removed param | **resolved** |
| CL-2b | medium | P2 | ~~Admin anchors мёртвые в merge~~ | `include_admin_fallback=pole_field.is_empty()` | **resolved** |
| CL-2c | info | P3 | `r` cap `dist_to_2nd/2` **per-cell** — неочевидно из ТЗ | doc / comment in `tierResolve` | open |
| CL-2d | info | — | Скачок zone/rainfall на `dist = r` (temp smooth, zone hard) | accepted v2.2 compromise; zone blend → v3 | **accepted** |
| CL-2e | info | P3 | ~~`pole_field.bbox is None` → modifiers игнорируются~~ | `_influence_diagonal` fallback from modifiers | **resolved** |

### God-object / concentration

| ID | Severity | P | Проблема | Fix | Status |
|---|---|---|---|---|---|
| CL-9 | low | P3 | `ClimateGeneratorService` utility god + lazy import cycle с `tierResolve` | pure pole sample; split physics | open |

### Mixed responsibility

| ID | Severity | P | Проблема | Fix | Status |
|---|---|---|---|---|---|
| CL-10 | medium | P2 | ~~`heightmapPass`: terrain + pole climate bias~~ | `pole_field.sample` only; no CGS import | **resolved** |
| CL-11 | medium | P2 | ~~`_non_surface_anchor_cells` private imports~~ | `locations.py` + `terrainZ.py` | **resolved** |

### Duplication (climate)

| ID | Severity | P | Проблема | Fix | Status |
|---|---|---|---|---|---|
| CL-12 | medium | P2 | ~~`_static_anchors`, `_z_to_terrain`, `_world_seed` × файлов~~ | `climate/math.py`, `locations.py`, `terrainZ.py` | **resolved** |

### Docs / product sync

| ID | Severity | P | Проблема | Fix | Status |
|---|---|---|---|---|---|
| CL-13 | info | — | Tier resolution docs vs code | synced in `tz_climate.md` | **resolved** |
| CL-14 | info | P3 | ~~Таблица tier-2 lists admin fallback; cell resolve admin off~~ | merge vs resolve в `tz_climate.md` | **resolved** |
| CL-15 | medium | — | Rainfall = raw zone moisture; Earth freeze hardcoded | `precipitation_liquid` + `precipitation.py` + peak clamp | **resolved** |
| CL-16 | low | P3 | `cellWeatherPass` `location_uid` from zone sample, not source cell | doc or preserve cell attribution | open |
| CL-17 | medium | P2 | `SurfaceClimateField` — spec C6 ✅, impl ⬜; optional in **world snapshot** blob (CL-17) | `build_surface_climate_field`; ≠ unified snapshot module | open |
| CL-18 | medium | P2 | Climate LOD — `ClimateLODPolicy`, zone routing near/medium/far | orchestrator / DAG tick; **Todo** с lazy sim LS-T2/T9 ([`tz_lazy_simulation.md`](./tz_lazy_simulation.md)) | open |
| WS-1 | high | P1 | **World snapshot runtime** — schema ✅, `WorldSnapshotService` ⬜ | [`tz_world_snapshot.md`](./tz_world_snapshot.md) WS-0..WS-2 | open |

### Mixed responsibility (post CL-11)

| ID | Severity | P | Проблема | Fix | Status |
|---|---|---|---|---|---|
| TR-8 | medium | P2 | `_non_surface_anchor_cells` still in assembler | `passes/nonSurfaceAnchorPass.py` | open |

---

## Hydrology / world bundle — smells registry (HY-S)

**Scope:** Sprint 1 (D HY-0…HY-1) + `WorldBundleService` connection import.  
**Refs:** [`tz_terrain_hydrology.md`](./tz_terrain_hydrology.md), [`.cursor/plans/hydrology-pre-dag.md`](../.cursor/plans/hydrology-pre-dag.md).

### HY-GEO-1 — geographic notation (type vs subtype)

**Severity:** high (был runtime bug) · **Status:** **partial** (filter fixed; enum split — HY-5)

**Суть:** в ТЗ таблица пишет `geographic.lake` — это **нотация документа** (type + subtype), не значение одного поля. В БД / bundle:

| Поле | Пример |
|---|---|
| `system_location_type` | `"geographic"` |
| `system_location_subtype` | `"lake"` |

Ошибочный фильтр `subtype.startswith("geographic.")` давал **пустой** `geographic_locations` на [`fixtures/world_template.json`](../fixtures/world_template.json).

**Fix (2026-06):** `hydrologyLocations.py` — `system_location_type == GEOGRAPHIC_LOCATION_TYPE`; `GeographicSubtype` StrEnum для subtype.

**Остаток:** split edges по `HydrologyConnectionType`, полный `HydrologyMasterInput` по ТЗ — HY-S-3.

---

### BUNDLE-1 — `_remap_bundle` growth in `WorldBundleService`

**Severity:** medium · **P:** P2 (когда секций bundle > 8) · **Status:** **resolved** (variant A — `bundleRemapService.py`)

**Симптом:** при duplicate-import (`world_uid` уже есть) `_remap_bundle` вручную знает PK и FK каждой секции: `locations`, `states`, `races`, `perks`, `map_cells`, `connection_nodes`, `connection_edges`. Каждая новая секция (cave graph, climate field cache export…) — ещё ~10 строк в одной функции (~72 строки сейчас).

**Почему не god-class:** orchestration остаётся в `WorldBundleService`; проблема — **монолитный remap helper**, не доменная логика.

#### Варианты — `BundleRemapService`

| Вариант | Идея | Плюсы | Минусы |
|---|---|---|---|
| **A — Section registry** | `BundleSectionSpec(name, pk_field, fk_fields: list[tuple[field, uid_map_key]])` + один generic loop `deepcopy → remap PKs → rewrite world_uid` | Минимальный diff; добавление секции = одна строка в registry | FK-логика сложных секций (parent_location_uid, edge endpoints) всё равно нуждается в hooks |
| **B — Strategy per section** | `RemapStrategy.remap_items(items, uid_map, new_world_uid) -> list[dict]`; `LocationRemapStrategy`, `ConnectionEdgeRemapStrategy`, … | Явные контракты; тестируемо по секции | Больше файлов; overkill пока секций мало |
| **C — Defer** | Оставить `_remap_bundle` inline до N≥10 секций или второго duplicate-import bug | Нулевая стоимость сейчас | Долг растёт линейно |
| **D — Graph remap** | Построить `EntityGraph(world → children)`; generic traverse по declared edges в spec | Единый алгоритм для любого bundle | Высокий upfront; нужен machine-readable FK map (schema или codegen) |

**Рекомендация (draft):** **A** при следующей секции bundle (caves / snapshots); **B** только если hook'и registry > 3 на секцию. **C** допустим до HY-4 закрыт.

**Размещение:** `application/worldData/bundleRemapService.py` (не generator); `WorldBundleService` вызывает `remap_bundle(data, version_n, strip_suffix)`.

**Связь:** connections import special-case (HY-S-2) — отдельный smell; remap и import order ортогональны.

---

### HY-S-2 — connections import вне `sections` loop

**Severity:** low · **P:** P2 · **Status:** open

`ConnectionGraphService` не реализует `import_from_json(world_uid, data)` как races/locations → `WorldBundleService` держит два if-блока после цикла.

| Вариант | Fix |
|---|---|
| A | `ConnectionGraphService.import_from_json(world_uid, {"nodes":…,"edges":…})` |
| B | Единый `BundleSectionImporter` registry: `key → (optional preprocess, import_fn)` |

---

### HY-5 — wire enum (JSON ↔ StrEnum, без string literals в коде)

**Severity:** medium · **P:** P1 · **Status:** **partial** — hydrology enums начаты; `jsonValidation` + shared registries ⬜

**Scope:** только **master / world JSON** (`worldData`). `engine/`, `contracts/` — не трогаем.

**Полный контракт:** [`tz_json_validation.md`](./tz_json_validation.md) — **§0 ENUM-E / N1-S / N1-W**; backlog HY-5 в generators — этот §.

**Размещение:** `application/worldData/jsonValidation/` (не `validation/` — в системе валидаторов несколько семейств).

**Симптом без этого:** magic strings в коде; doc пишет `geographic.lake`, JSON хранит два поля; опечатка → silent empty filter (HY-GEO-1).

#### Контракт двух слоёв

| Слой | Что хранится | Пример |
|---|---|---|
| **Wire** (bundle, SQLite TEXT, API JSON) | `str` | `"lake"`, `"lake_shoreline"` |
| **Domain** (generators, orchestrators) | `StrEnum` member | `GeographicSubtype.LAKE` |
| **Граница** | parse / serialize | `GeographicSubtype(wire)` → member; `member.value` → wire |

```python
# generators/registries/wire.py (target)
def parse_enum(enum_cls: type[StrEnum], wire: str, *, field: str) -> StrEnum:
    try:
        return enum_cls(wire)
    except ValueError as e:
        raise WireEnumError(field, wire, enum_cls) from e

# generator — NO "lake" literal
if geographic_subtype(loc) is GeographicSubtype.LAKE:
    ...

# persist / export
row["connection_type"] = HydrologyConnectionType.LAKE_SHORELINE.value
```

**Правило:** engine-known vocabulary в `generators/` — только через enum; grep `"lake_shoreline"` в generators → 0 (кроме enum definition).

#### Три класса vocabulary (§0)

| Класс | ID | Примеры | Контракт |
|---|---|---|---|
| **Engine-closed** | ENUM-E | `MaterialCategory`, `NodeCategory`, `GraphLevel` | StrEnum; unknown на import → reject |
| **N1-S schema** | N1-S | `stat_schema[]`, `npc_fields[]` | `system_name`/`display_name`; type field → ENUM-E |
| **N1-W vocabulary** | N1-W | `material_registry[]`, `climate_zone_registry[]` | мастер добавляет строки; refs → REF-W index |

Hydrology declare (U20–U27): wire keys **ENUM-E E-10**; display в N1-W-06 — не смешивать.

#### Варианты

| Вариант | Суть | Когда |
|---|---|---|
| **A — StrEnum + parse at boundary** | manual `parse_enum()` в import + master input | **сейчас** |
| **A+ — Pydantic BeforeValidator** | DTO import rows с typed fields | HY-4 validator |
| **B — Policy dataclass** | `HydrologyWorldPolicy.model_validate(...)` | HY-4 blob |
| **C — Codegen из schema** | fixture → Python + TS enums | editor v2 |

**Рекомендация:** **A** немедленно; **A+** на bundle rows; **B** для `world.hydrology`.

#### Производительность

Parse на location/edge/policy — не на map cell. Bottleneck — LLM + grid; просадки нет.

#### Migration checklist

1. `generators/registries/locationTypes.py` — `LocationType.GEOGRAPHIC`
2. `generators/registries/connectionTypes.py`
3. `worldData/jsonValidation/models/` — bundle row DTOs
4. `worldData/jsonValidation/bundleValidator.py` — hook в `WorldBundleService`
5. Убрать `CLIMATE_POLE_TYPE = "climate_pole"` string const → enum

#### Персонаж vs мир (TZ storage § character_sheet, players, npcs)

По [`project_data_storage_tz.md`](./project_data_storage_tz.md): **character_sheet импорт/экспорт независим от мира**; `players` — глобальные; `npcs` — в world bundle; связка **только в runtime** (`game_sessions`: `world_uid` + `player_character_id`).

| Сущность | JSON import | Enum / wire | jsonValidation пакет |
|---|---|---|---|
| World bundle | `POST /worlds/import` | `generators/registries/` (simulation-closed) | **`worldData/jsonValidation/`** |
| Character sheet | `POST /characters/import` | platform + refs на ключи реестров мира | **`character/jsonValidation/`** (future) — **не** worldData |
| NPC rows | часть world bundle | world `npc_fields` + engine node_category | world bundle validator + world context |

**Правило:** ключи персонажа (`system_colour`, stats, perks) **validate vs `world.*_registry` при bind/migrate**, не смешивать с world bundle enum. `character.world_schema_version` ↔ `world.schema_version` — отдельный pipeline (TZ § Schema versioning).

**Не класть** character enums в `generators/registries/` — там только world simulation wire.

---

### HY-S-4 — `HYDROLOGY_SCHEMA_DEFAULTS` centralization

**Severity:** low · **P:** P2 · **Status:** open

**Симптом:** defaults размазаны:

| Место | Что |
|---|---|
| `resolveRiverTypeClassify._SCHEMA_DEFAULTS` | `mountain_min_source_z=40`, … |
| `resolveHydrologyBands._BAND_MIN/_BAND_MAX` | `1`, `99` |
| `is_hydrology_enabled` | `enabled` default `True` |
| [`fixtures/world_template.json`](../fixtures/world_template.json) | `type_classify` null → runtime fallback |
| [`tz_terrain_hydrology.md`](./tz_terrain_hydrology.md) § U22 | таблица schema defaults (doc-only) |

**Риск:** drift doc ↔ code ↔ fixture; HY-4 validator должен писать те же числа, что runtime.

#### Варианты

| Вариант | Идея |
|---|---|
| **A — `hydrologySchemaDefaults.py`** | Один модуль: `RIVER_TYPE_CLASSIFY_DEFAULTS`, `BAND_LIMITS`, `DEFAULT_ENABLED`; loaders import оттуда; TZ ссылается на module |
| **B — `HydrologyWorldPolicy` dataclass** | Defaults as `field(default_factory=…)`; `resolve_*` принимают typed policy, не `dict` |
| **C — Explicit constants in fixture only** | Validator on import заполняет null; runtime **без** fallback (fail loud) |
| **D — A + B** | Module constants → construct default `HydrologyWorldPolicy`; parse merges overrides |

**Рекомендация (draft):** **D** к моменту HY-4 validator; до него **A** (один файл, ~30 строк) — cheap win.

**Связь:** HY-4 (type_classify normalize on import), CL-5 (climate import validator pattern).

---

### HY-S-3 — stub `HydrologyMasterInput` vs TZ target

**Severity:** medium · **P:** P1 (Sprint 2 entry) · **Status:** open

Stub несёт `connection_graph` + `geographic_locations`; ТЗ — `declared_lake_shorelines`, `declared_coastlines`, `declared_river_edges`, `world_policy: HydrologyWorldPolicy`, `local_profiles`.

| Вариант | Fix |
|---|---|
| A | Incremental: Sprint 2 добавляет split edges + typed policy; stub fields deprecated |
| B | Big-bang dataclass по ТЗ до generators |

**Рекомендация:** **A** — split by `HydrologyConnectionType` в `buildHydrologyMasterInput` в HY-2/3.

---

### HY-S-5 — `LoadedConnectionGraph.edges: list[dict]`

**Severity:** low · **P:** P2 · **Status:** open

Nodes typed (`ResolvedConnectionNode`), edges — `asdict(ConnectionEdge)`. Неявный контракт polyline / width для rasterize.

**Fix:** `ResolvedConnectionEdge` frozen dataclass; или reuse `ConnectionEdge` если generator layer may import DB models (climate pattern).

---

### Sprint 1 registry (summary)

| ID | Severity | P | Проблема | Status |
|---|---|---|---|---|
| HY-GEO-1 | high | P1 | geographic filter doc↔DB notation | **partial** (filter ✅; full enum registry — HY-5) |
| BUNDLE-1 | medium | P2 | `_remap_bundle` monolith | **resolved** — `bundleRemapService.py` registry |
| HY-S-2 | low | P2 | connections import special-case | open |
| HY-5 | medium | P1 | StrEnum / policy parse (Retrofit 2) | **partial** |
| HY-S-4 | low | P2 | `HYDROLOGY_SCHEMA_DEFAULTS` scatter | open |
| HY-S-3 | medium | P1 | MasterInput stub vs TZ | open |
| HY-S-5 | low | P2 | edges as dict | open |

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
| 2026-06 | `tz_city_generation.md` sync TZ ↔ код (SettlementGeneratorService, фазы A–F, §10) |
| 2026-06 | TR-3 resolved: `worldMapSettings` incl. `world_z_min/max` fallback −8000…8000 |
| 2026-06 | TR-3 partial: `grid_bbox_padding`, `terrain_chunk_columns`, `map_subsurface_depth` on `World` + `worldMapSettings.py` |
| 2026-06 | Post TR-1b/DBG-1 review: § TR registry (TR-2..TR-8, TR-H*, TR-G1), DR-6/7, MAP-1/2, MR-7, DBG-2, CL-16 |
| 2026-06 | DBG-1: debug_settlement pipeline tests → HTTP API (TZ § «Три входа») |
| 2026-06 | NC-1 Phase 1–5; `tz_terrain_generation.md` full rework (Phase 6) |
| 2026-06 | **Terrain TZ утверждено:** multi-pass skeleton, N_eff, materialization pass order; TR-1 open (код vs ТЗ) |
| 2026-06 | Climate polish sprint: CL-4, CL-2a/2b/2e, CL-10..12, DR-5 |
| 2026-06 | `tz_world_snapshot.md` — unified WorldSnapshotService; climate terminology disambiguation v2.6.1 |
| 2026-06 | Climate v2.6 TZ: LOD C6–C13; CL-17 SurfaceClimateField; CL-18 LOD policy |
| 2026-06 | Polish backlog rework; CL-2a..CL-2e, DR-5 added; FM-1 resolved |
| 2026-06 | **HY-S registry:** BUNDLE-1, HY-5, HY-S-4, HY-GEO-1 |
| 2026-06 | **`docs/tz_json_validation.md` v0.1** — Field Contract Registry; ENUM-E / REF-W / N1-S / N1-W (§0) |
