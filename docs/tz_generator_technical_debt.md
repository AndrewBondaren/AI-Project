# Generator Technical Debt

**Тип:** инженерное ТЗ / living registry (не player-facing).  
**Scope:** `backend/app/application/worldData/generators/` — settlement, district, area, terrain, climate, structure, coordinates.  
**Adjacent (orchestration hooks):** `mapCellService.py`, `api/routes/map.py`, `backend/scripts/debug_*.py` / `render_maps.py`, `worldBundleService.py`, relief library/import, pack render / parent-light refine.  
**Обновлено:** 2026-08-26 — SoT generate: [`tz_terrain_relief.md`](./tz_terrain_relief.md) (очереди, стрелки). Bake R36/R43 — архив [`tz_terrain_relief_v1_superseded.md`](./tz_terrain_relief_v1_superseded.md). **R41-T-25** алгоритм+валидатор+тесты **open** (следующая разработка с мастером). **R41-T-17** leftover→COUPLE + валидатор не из z ✅ (не конечный occupancy). **R41-T-18** / **T-19** mill Q1/Q2 ✅. Полиш mill **R41-T-20…T-23** ✅. Rename heightmap **R41-T-24** (`z_height_map`) ✅. **R41-T-13…T-16** ✅. Очередь v2 полиш **R41-T-1…T-12** ✅. Consume dump: [`tz_terrain_relief_consume.md`](./tz_terrain_relief_consume.md).  
**Связанные документы:**

| Документ | Роль |
|---|---|
| [tz_assembler_hierarchy.md](./tz_assembler_hierarchy.md) | Целевая архитектура assembler stack |
| [tz_city_generation.md](./tz_city_generation.md) | Продуктовое ТЗ города |
| [tz_terrain_relief.md](./tz_terrain_relief.md) | Relief generate SoT (Q1/Q2, стрелки, шаблоны, canal/obstacle, SQL catalog). Bake R36u–w — архив v1 |
| [tz_terrain_relief_technical_debt.md](./tz_terrain_relief_technical_debt.md) | Relief **код**: dual sidecar, god/жирные классы, хардкоды (не R41-T-25 алгоритм) |
| [tz_pack_ascii_render.md](./tz_pack_ascii_render.md) | Pack ASCII SoT (**PAR-G\***); L2 location grade; debt **PAR-T-*** · **R36u-T-*** |
| [tz_locations.md](./tz_locations.md) | `barrier_template_registry`; perimeter barriers |
| [tz_terrain_hydrology.md](./tz_terrain_hydrology.md) | Гидрология: моря, озёра, реки (target) |
| [tz_climate.md](./tz_climate.md) | Продуктовое ТЗ climate (pole/local tiers) |
| [tz_world_pack_storage.md](./tz_world_pack_storage.md) | World Pack; § WP-FIX-DEBT (в т.ч. WP-DELETE-1 → DEBT-10); terrain mask carry |
| `.cursor/plans/full-bake-seam-halo-shoulder.md` | отдельные шаги: шов мира L0 · halo grid-соседа · T-10 |
| `.cursor/plans/settlement-assembler.md` | Phase-план settlement |
| `.cursor/plans/coordinate-spaces.md` | Phase-план NC-1 |
| `.cursor/plans/grade-detailed-location-render.md` | L2 location grade ASCII impl |
| `.cursor/plans/r36u-grade-detailed-migrate.md` | R36u migrate L0 ribbon → detailed geometry |
| `.cursor/plans/r36u-post-impl-debt.md` | R36u-T-1…T-10 post-impl polish |
| `.cursor/plans/r36v-grade-chunk-pool.md` | R36v pool sample → stitch → materialize; post-impl **R36v-T-*** |
| `.cursor/plans/detailed-grade-volume-canal.md` | Post-R36w GradeFormation apply; **R36i-T**; post-impl **T-4…T-15** ✅ |
| `.cursor/plans/relief-pipeline-v2.md` | R41 discover в worker; **R41-T-1…T-12** ✅; слой 5 ravine ✅; shore онтология+paint ✅; **ShorePlugin тело ✅**; v1 sample/stitch срезан |

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
| `worldData/worldBundleService.py` | ~190 | validate/remap/tx + N section imports + **inline relief export** — см. **BUNDLE-2** (не god-class generators) |
| `worldData/reliefTemplateLibraryService.py` | ~135 | CRUD + R29 FS + validate + **HTTPException** — см. **RELIEF-T-3** |
| `pack/refine/fineChunkRunner.py` | ~390 | pool + persist; grade sample+materialize в том же compute task (**R36w**) |
| `relief/discover/core.py` | ~160 | тонкий фасад: leftover walk + `run_mill_schedule` + sheer/C38 — **R41-T-20** ✅ |

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
WORLD_SURFACE_GRID     gx, gy     tile index; step = map_cell_size_m (dynamic, ≥1000, ×1000)
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
| MR-7 | medium | `mapCellService.py` | CRUD/import + `save_terrain_batch` (pole, chunking, gap stats, persist) | `TerrainBatchOrchestrator` или DAG node; service → repo only | **resolved** |

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
| **HY-5** | medium | **Smoke 2026-07-17:** rivers/lakes cells=0 (flat z, absolute detect, min_z=20). | **partial (Pass 1.4 + debt fixes):** relief_objects_z before hydro; `coarse_relief_z` vs post-1.4 (no light double-rise); shared footprint/depression; explicit `ProminenceScale`; pole required on coarse mountain. **Smoke checklist:** rebake `world_test_gen` → `world-height` max ≫ plains; rivers/lakes cells>0 **or** sources/basins in log. **HY-5b:** light procedural RIVER paint still open | partial |
| **HY-BATH-1** | medium | Light SEA (`~`) с `surface_z` как у plains: hydro paint role без bathymetry z; Relief читает `coarse_relief_z` (намеренно). | **partial (stub 2026-07-19):** `HydrologySeasPolicy.stub_drop_fraction_of_span` + `resolve_open_water_surface_z`; light `apply_coarse_open_water` пишет floor (prefer coarse ≤ z_sea, else stub drop). **TZ:** full DepressionForm pipeline still open | partial |
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
| MR-7 | medium | P2 | `MapCellService.save_terrain_batch` / `save_z_slice`: persist layer знает pole, chunking, gap logging | extract `TerrainBatchOrchestrator` (симметрия с `ClimateOrchestratorService`) | **resolved** |
| TR-5 | low | P3 | `TerrainGeneratorService.generate_minimal` — terrain facade + inline climate (lazy gameplay) | lazy node: stub + climate pass или shared DR-7 helper; document until DAG | open |
| TR-8 | medium | P2 | `ClimateSurfaceAssembler._non_surface_anchor_cells` — orchestrator синтезирует MapCell (imports вынесены — CL-11 ✅, pass extraction — нет) | `passes/nonSurfaceAnchorPass.py` | open |
| MAP-2 | low | P3 | `map.py` — HTTP + pipeline wiring + module singleton generators | container / deps | open |

### Implicit contracts / side effects

| ID | Severity | P | Проблема | Fix | Status |
|---|---|---|---|---|---|
| TR-6 | medium | P2 | `save_pass(layer: str)` — `"terrain"`/`"climate"`/`"ore"`/`"cave"`; какие поля перезаписывает — только в repo, не в типе | enum + documented upsert field matrix (`tz_terrain_generation.md` или repo docstring) | open |
| TR-7 | low | P3 | Три insert-пути terrain (`insert_bulk_ignore`, `insert_terrain_bulk`, `upsert_terrain_skeleton`) + DAG bypass repo | `BulkInsertMode` + scope enum; см. [`tz_terrain_generation.md`](./tz_terrain_generation.md) § TR-PERF-DEBT-4 | open (was: dual API) |

### TR-PAR bootstrap DB (resolved)

| ID | Severity | P | Проблема | Fix | Status |
|---|---|---|---|---|---|
| TR-PAR-5 | high | P2 | PRAGMA bulk session на shared connection — concurrent jobs перетирали PRAGMA | `_bootstrap_conn` + `asyncio.Lock`; dual conn foundation | **resolved** — см. [`tz_terrain_generation.md`](./tz_terrain_generation.md) § TR-PAR-5 |
| TR-PAR-DEBT-1 | medium | P2 | ContextVar ambient conn routing на `db.conn` (TR-PAR-5 v1 interim) | **TR-PAR-6** `BootstrapMapCellWriter` + explicit `conn` on repo bulk methods | **resolved** — см. § TR-PAR-6 |
| TR-PAR-6 | medium | P2 | Implicit bulk persist contract (repos via magic `db.conn`) | `BootstrapMapCellWriter` port; orchestrator `writer.session()` | **resolved** — [`bootstrapMapCellWriter.py`](../backend/app/application/worldData/bootstrapMapCellWriter.py) |
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
| **R41-T-25** | Pack: алгоритм **полного** заполнения 8 слотов (каскад mill ≠ тело×8; не игнор восьмёрки) | **open** |
| **R41-T-17** | Pack 8 слотов: leftover-only → SLOPE/SHEER + COUPLE; first-wins на слоте | **resolved** |
| **R41-T-18** | Seed: вёдра Q1 leftover/claimed + Q2 `(z_q1, uid)`; сетка один раз | **resolved** |
| **R41-T-19** | Снос mill-очереди Q3 (`is_q3_seed`, `q3_s`, `q3_parent`); бок-attach persist оставить | **resolved** |
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
| **R41-T-13, T-15** | Ravine equal-z на envelope; L=1 vs якорь R36t | **resolved** |
| **R41-T-20…T-23** | Полиш mill: планировщик / typed report / enum вёдер / SRP vertices+apron | **resolved** |

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
| **R41-T-14, T-16** | один `seam[]`; `slope_fits` vs L_min | **resolved** |
| **R41-T-24** | `z_at` → `z_height_map` (relief heightmap, не T-17) | **resolved** |
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

**Fix (2026-06):** `hydrologyLocations.py` — `system_location_type == GEOGRAPHIC_LOCATION_TYPE`; `GeographicSubtype` StrEnum + `from_wire` в `dataModel/locations/enums/`.

**Остаток:** split edges по `HydrologyConnectionType`, полный `HydrologyMasterInput` по ТЗ — HY-S-3; сравнения по `GeographicSubtype.*` в hydrology pipeline — HY-5 P2.

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

### WP-DELETE-1 — `DELETE /worlds/{uid}` не FK-safe / не atomic

**Severity:** high · **P:** P1 · **Status:** open  
**Cross-ref:** [`tz_world_pack_storage.md`](./tz_world_pack_storage.md) § Fix debt **WP-FIX-DEBT-10**; API TODO в `api/routes/worlds.py` → `delete_world`.

**Симптом (smoke 2026-07-19):** `DELETE /api/worlds/{world_uid}` → HTTP 500, `sqlite3.IntegrityError: FOREIGN KEY constraint failed`.

**Причина:**

1. Много child-таблиц ссылаются на `worlds(world_uid)` **без** `ON DELETE CASCADE`.
2. `WorldService.delete` / repo удаляют только строку `worlds`.
3. Debug helper (`api_delete_world`) сначала purge'ит `locations`, потом вызывает API delete → при FK fail мир остаётся **half-deleted** (локации уже снесены, другие children + `worlds` row живы) → последующий bake: `surface terrain context unavailable`.

**Целевое решение:**

| Вариант | Идея |
|---|---|
| **A (предпочтительно)** | Ordered purge всех world-scoped children в одной транзакции, затем `worlds` row; либо schema `ON DELETE CASCADE` где безопасно |
| **B** | Перед delete — probe blockers; HTTP **409** со списком, не 500 |
| **C (smoke)** | Не полагаться на partial delete; wipe pack + clear map без `DELETE world`, либо полный recreate DB |

**Размещение fix:** `WorldService.delete` (+ при необходимости schema `0001_initial.sql`); route остаётся thin.

**Связь:** BUNDLE-1 (duplicate-import remap) — ортогонально; оба бьют master smoke lifecycle (import → bake → reset).

---

### HY-S-2 — connections import вне `sections` loop

**Severity:** low · **P:** P2 · **Status:** open

`ConnectionGraphService` не реализует `import_from_json(world_uid, data)` как races/locations → `WorldBundleService` держит два if-блока после цикла.

| Вариант | Fix |
|---|---|
| A | `ConnectionGraphService.import_from_json(world_uid, {"nodes":…,"edges":…})` |
| B | Единый `BundleSectionImporter` registry: `key → (optional preprocess, import_fn)` |

**Связь:** поглощается / уточняется **BUNDLE-2** (section handlers).

---

### BUNDLE-2 — `WorldBundleService` → section handlers по доменам

**Severity:** medium · **P:** P2 · **Status:** **resolved** (2026-07-30)  
**Product SoT:** [`tz_world_bundle.md`](./tz_world_bundle.md) (WB-1…WB-15) · plan [`.cursor/plans/bundle-2-section-handlers.md`](../.cursor/plans/bundle-2-section-handlers.md)

**Сделано:** `WorldBundleService` = thin facade (no FastAPI); `build_bundle_handlers` + entity/library kinds; skeleton keys `race_templates` / `perk_templates` / `building_templates` / `relief_templates`; global `race_templates` / `perk_templates` SQL + world pointer registries; HY-S-2 via two connection handlers; remap skips library UIDs.

**Follow-up (не BUNDLE-2):** fixture/scripts rename `races`→`race_templates`; subgraph location transfer API; ImportResult import sweep (T-29).
---

### HY-5 — wire enum (JSON ↔ StrEnum, без string literals в коде)

**Severity:** medium · **P:** P1 · **Status:** **partial** — structure/roads/climate slices в `dataModel`; shims + string literals в generators ⬜; `jsonValidation` ENUM gate (JV-0) ⬜

**Scope:** только **generators / worldData** с реальным потребителем. `engine/`, `contracts/` — **не трогаем** до JV-0: engine-closed enum (`node_category`, DAG vocabulary) — после валидации, не через bulk-перенос `wireEnums`.

**Полный контракт:** [`tz_json_validation.md`](./tz_json_validation.md) — **§0 ENUM-E / N1-S / N1-W**; backlog HY-5 в generators — этот §.

**Канон:** `backend/app/dataModel/**/enums/*.py` — StrEnum + `from_wire()` где нужен default/legacy.  
**Barrel (только для jsonValidation):** `generators/registries/wireEnums.py` — re-export из `dataModel`; **generators не импортируют** (grep → 0).  
**Импорт в generators:** прямой `from app.dataModel...`; shims удалять после переключения call sites.

**Симптом без этого:** magic strings в коде; doc пишет `geographic.lake`, JSON хранит два поля; опечатка → silent empty filter (HY-GEO-1).

#### Дисциплина scope (2026-07)

| Правило | Суть |
|---|---|
| **Grep-first** | Переносим enum только если есть потребитель в `generators/` или jsonValidation slice |
| **Не пакетом wireEnums** | Не дублировать весь barrel в `dataModel` «на будущее» |
| **Engine later** | Если enum живёт в DAG / `npc_fields.node_category` — JV-0 + engine, не HY-5 generators |
| **`NodeCategory`** | **Удалён** из dataModel (ошибочный домен `connections/`; свалка соц. полей NPC, путаница с engine node). Wire `node_category` — см. [`project_data_storage_tz.md`](./project_data_storage_tz.md); StrEnum позже как `NpcFieldCategory` в `character/` |

#### Контракт двух слоёв

| Слой | Что хранится | Пример |
|---|---|---|
| **Wire** (bundle, SQLite TEXT, API JSON) | `str` | `"lake"`, `"lake_shoreline"` |
| **Domain** (generators, orchestrators) | `StrEnum` member | `GeographicSubtype.LAKE` |
| **Граница** | parse / serialize | `GeographicSubtype.from_wire(wire)` → member; `member.value` → wire |

```python
# jsonValidation/wire.py (JV-0) или from_wire на границе layout/template row
ptype = PassageType.from_wire(conn.get("passage_type"), default=PassageType.DOORWAY)

# generator — NO "doorway" literal (кроме enum definition / .value на persist)
if ptype is PassageType.STAIRCASE:
    ...
```

**Правило:** engine-known vocabulary в `generators/` — только через enum; grep wire-key в generators → 0 (кроме enum definition и `.value` на export).

#### Сделано (2026-06 — 2026-07)

| Домен | `dataModel` | Generators |
|---|---|---|
| **Structure** | `PassageType`, `StaircaseType`, `StructureElement`, `BuildingContext` | `from_wire` в passages, `layoutEngine`, `staircase/builder`; `PassageType` shim **удалён**; `StructureElement` — частично прямой import |
| **Spatial** | `Facing` (`spatial/facing.py`) | shim `utils/facing.py`; часть файлов уже напрямую |
| **Settlement / roads** | `DistrictEntryRole`, `DistrictDensity`, `StreetLayout`, `SidewalkSide`, `GapPolicy`, `BridgeSubtype` | `streets.py`, `gridLayout` — `ConnectionNodeType`, `GraphLevel`, `DistrictEntryRole`; `blockSize` — `DistrictDensity` |
| **Connections graph** | `ConnectionNodeType`, `GraphLevel`, `PortalType` | `streets.py`, `connectionEntry`; `PortalType` — только barrel |
| **Locations** | `GeographicSubtype`, `BorderCategory` | `hydrologyLocations` — `from_wire`; `BorderCategory` — только barrel |
| **Hydrology** | `HydrologyConnectionType` | re-export в `hydrology/types.py` |
| **Terrain** | `CellStateCategory` | только barrel |
| **Climate** | `SeasonKey`, `ClimatePoleMode`, `PoleKind`, `PoleSource` | `poleResolve` — `ClimatePoleMode`, `PoleKind` |
| **Materials** | `MaterialCategory` | `precipitation.py` |
| **Character (wire)** | `SystemGender` → `dataModel/character/enums/` (не `shared/`) | только barrel; engine/NPC — после JV |
| **Shared (world platform)** | `MeasurementSystem`, `StatConflictMode` | только barrel |

**Исправления по ревью:** `NodeCategory` убран; `SystemGender` вынесен из `shared/` в `character/`; over-migration из `wireEnums` без generator consumers откатана по смыслу (barrel ok, код generators не трогать).

#### Остаток — generators (приоритет)

**P1 — shims (механика, enum уже в dataModel)** — ✅ **done (2026-07)**

| Shim | Статус |
|---|---|
| `generators/utils/facing.py` | удалён → `dataModel.spatial.facing` |
| `generators/structure/structureElement.py` | удалён → `dataModel.structure.enums.buildingElement` |
| `generators/structure/staircase/staircaseType.py` | удалён → `dataModel.structure.enums.staircaseType` |
| `generators/structure/staircase/staircaseSize.py` | удалён (call sites уже на dataModel) |
| `generators/structure/room/roomSize.py` | удалён (call sites уже на dataModel) |

**P1 — enum в dataModel, в коде ещё string literals**

| Enum | Где literals | Статус |
|---|---|---|
| `StreetLayout` | `districtRoadGenerator`, assembler/placement logs | ✅ `StreetLayout.for_generator` + enum map |
| `GraphLevel` | `gridLayout`, `settlementLayoutExtract`, persist | ✅ `GraphLevel.*.value` / frozenset members |
| `StaircaseType` | defaults в structure | ✅ `parse_template` / `generator_default` в POJO |
| `Facing` | defaults / direction dicts в passages, shapes | ✅ `parse_facing_or_default`, `CARDINAL_*` |
| `PassageType` | orchestrator UUID | ✅ `PassageType.ARCHWAY.value` |

**P2 — внутренний vocabulary (не wire ENUM-E, перенос опционален)**

| Enum | Модуль | Вердикт |
|---|---|---|
| `HydrologyScope`, `HydrologyCellRole` | `generators/hydrology/types.py` | pipeline hydrology; dataModel — когда стабилизируем HY-S-3 API |
| `AnchorSource` | `climate/climateAnchor.py` | climate pipeline |
| `CellZone` | `settlementAssembler/planner/defaults.py` | planner-internal (center/edge/inner) |
| `CoordinateSpace` | `coordinates/space.py` | теги координатных систем |
| `PoleMode` | `climate/climatePole.py` | ✅ удалён; `ClimatePoleMode` из dataModel |

**P3 — без dataModel enum пока**

| Literal | Где | Примечание |
|---|---|---|
| `room_type == "corridor"` | `corridorConnector`, `corridorTrimmer` | внутренняя таксономия комнат; enum — только при контракте в ТЗ |
| `_GLASS_USE_TYPE` strings | `wallOpening.py` | material use-type; OQ-3 / N1-W ref |

**Не HY-5 (barrel only, ждут JV-0):** `BorderCategory`, `BuildingContext`, `CellStateCategory`, `PortalType`, `GapPolicy`, `BridgeSubtype`, `SidewalkSide`, `SeasonKey`, `MeasurementSystem`, `StatConflictMode`, `SystemGender`.

#### Три класса vocabulary (§0)

| Класс | ID | Примеры | Контракт |
|---|---|---|---|
| **Engine-closed** | ENUM-E | `MaterialCategory`, `GraphLevel`, `node_category` *(engine, post-JV)* | StrEnum; unknown на import → reject |
| **N1-S schema** | N1-S | `stat_schema[]`, `npc_fields[]` | `system_name`/`display_name`; type field → ENUM-E |
| **N1-W vocabulary** | N1-W | `material_registry[]`, `climate_zone_registry[]` | мастер добавляет строки; refs → REF-W index |

Hydrology declare (U20–U27): wire keys **ENUM-E E-10**; display в N1-W-06 — не смешивать.

#### Варианты

| Вариант | Суть | Когда |
|---|---|---|
| **A — StrEnum + parse at boundary** | `from_wire()` в import + master input | **сейчас** (generators) |
| **A+ — Pydantic BeforeValidator** | DTO import rows с typed fields | JV-0 / jsonValidation |
| **B — Policy dataclass** | `HydrologyWorldPolicy.model_validate(...)` | HY-4 blob |
| **C — Codegen из schema** | fixture → Python + TS enums | editor v2 |

**Рекомендация:** **A** в generators; **A+** на bundle rows; engine enum — **после A+**, не параллельно HY-5.

#### Производительность

Parse на location/edge/policy — не на map cell. Bottleneck — LLM + grid; просадки нет.

#### Migration checklist

**Generators (HY-5):**

1. ✅ `PassageType`, `StaircaseType`, `StructureElement` → `dataModel/structure/enums/`
2. ✅ Roads/settlement graph enums → `dataModel`; `streets.py` slice
3. ✅ `wireEnums.py` — pure re-export barrel
4. ✅ Удалить shims: `facing`, `structureElement`, `staircaseType`, `staircaseSize`, `roomSize`
5. ✅ Roads literals: `StreetLayout`, `GraphLevel` в `districtRoadGenerator` / `gridLayout` / `settlementLayoutExtract`
6. ✅ Structure literals: `StaircaseType`, `Facing`, `PassageType.ARCHWAY`

**jsonValidation (JV-0, не generators)** — детали: [`tz_json_validation.md`](./tz_json_validation.md) § JV-0:

7. ✅ **JV-0a** — `resolve` hook → `wire.parse_enum`; 422 `UNKNOWN_ENUM` (`StrictOnWire[T]` unwrap)
8. ✅ **JV-0b** — bundle DTO `connection_nodes` / edges + `WorldBundleService` hook
9. ⬜ `node_category` → `NpcFieldCategory` в `dataModel/character/` + engine hook (**post-JV-0**)

**Прочее:**

10. ✅ `CLIMATE_POLE_TYPE` alias убран; `locations.py` → `CLIMATE_POLE_LOCATION_TYPE` из dataModel
11. ⬜ `generators/registries/locationTypes.py` — `LocationType.GEOGRAPHIC` (если появится второй consumer)

#### Персонаж vs мир (TZ storage § character_sheet, players, npcs)

По [`project_data_storage_tz.md`](./project_data_storage_tz.md): **character_sheet импорт/экспорт независим от мира**; `players` — глобальные; `npcs` — в world bundle; связка **только в runtime** (`game_sessions`: `world_uid` + `player_character_id`).

| Сущность | JSON import | Enum / wire | jsonValidation пакет |
|---|---|---|---|
| World bundle | `POST /worlds/import` | `dataModel/**/enums` (simulation-closed) | **`application/jsonValidation/`** |
| Character sheet | `POST /characters/import` | platform + refs на ключи реестров мира | **`character/jsonValidation/`** (future) |
| NPC rows | часть world bundle | `npc_fields.node_category` + engine DAG | world bundle validator + engine context (**post-JV**) |

**Правило:** ключи персонажа (`system_colour`, stats, perks) **validate vs `world.*_registry` при bind/migrate**, не смешивать с world bundle enum. `character.world_schema_version` ↔ `world.schema_version` — отдельный pipeline (TZ § Schema versioning).

**Не класть** simulation wire enums в `engine/`; **не класть** character enums в `generators/registries/` — barrel re-export для jsonValidation only.

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

### HY-S-3 — `HydrologyMasterInput` vs TZ target

**Severity:** low · **P:** P1 · **Status:** **resolved (2026-07, U23)**

Declare geometry: `declared_coastline_segments`, `declared_lake_specs`, `declared_river_edges`, `declared_river_intents` из `loadDeclaredHydrology` — см. `types.py` / `buildHydrologyMasterInput.py`. `connection_graph` в master input — placeholder для roads; hydrology declare **не** из graph.

---

### HY-S-5 — `LoadedConnectionGraph.edges: list[dict]`

**Severity:** low · **P:** P2 · **Status:** open

Nodes typed (`ResolvedConnectionNode`), edges — `asdict(ConnectionEdge)`. Неявный контракт polyline / width для rasterize.

**Fix:** `ResolvedConnectionEdge` frozen dataclass; или reuse `ConnectionEdge` если generator layer may import DB models (climate pattern).

---

### CONN-1 — rename `connection_nodes.node_type` → `connection_node_type`

**Severity:** low (naming) · **P:** P2 · **Status:** **open** (todo; не HY-5 literals)

**Суть:** wire-ключ `node_type` на `ConnectionNode` путают с engine DAG node и с `npc_fields.node_category`.  
Переименование в **`connection_node_type`** согласовано; вариант `connection_type` **отклонён** — коллизия с `connection_edges.connection_type` (`road`, `lake_shoreline`, …).

| Слой | Сейчас | Цель |
|---|---|---|
| SQL / bundle JSON | `node_type` | `connection_node_type` |
| Python dataclass | `ConnectionNode.node_type` | `connection_node_type` |
| ENUM-E | `ConnectionNodeType` (имя enum ок) | без переименования класса |
| Engine DAG | — | **не трогать** |

**Scope rename (один PR + recreate БД):**

1. `db/migrations/0001_initial.sql` — колонка `connection_node_type`
2. `db/models/connectionNode.py`
3. `fixtures/world_template.json` — все `connection_nodes[]`
4. Generators: `streets.py`, `gridLayout.py`, hydrology loaders, persist/import paths
5. `docs/tz_structure_connections.md`, `docs/tz_terrain_hydrology.md` — wire-таблицы
6. `jsonValidation` — bundle row DTO для `connection_nodes` (**после** JV slice на connections)

**Не в scope:** alias `node_type` на import (мастер пересобирает bundle); engine; `ConnectionNodeType` StrEnum rename.

**План агента:** [`.cursor/plans/connection-node-type-rename.md`](../.cursor/plans/connection-node-type-rename.md)

---

### Sprint 1 registry (summary)

| ID | Severity | P | Проблема | Status |
|---|---|---|---|---|
| HY-GEO-1 | high | P1 | geographic filter doc↔DB notation | **partial** (filter ✅; `GeographicSubtype` in dataModel; hydrology member compares — HY-5) |
| BUNDLE-1 | medium | P2 | `_remap_bundle` monolith | **resolved** — `bundleRemapService.py` registry |
| HY-S-2 | low | P2 | connections import special-case | **resolved** (BUNDLE-2 connection handlers) |
| **BUNDLE-2** | medium | P2 | WorldBundleService → section handlers | **resolved** — handlers + library domains (relief/building/race/perk); see [`tz_world_bundle.md`](./tz_world_bundle.md) |
| HY-5 | medium | P1 | StrEnum / policy parse (Retrofit 2) | **partial** — dataModel ✅; shims + literals ⬜; JV-0 ⬜ |
| HY-BATH-1 | medium | P1 | light SEA z = plains; Depression forms TZ | **partial** — stub drop ✅; full Form pipeline ⬜ |
| HY-S-4 | low | P2 | `HYDROLOGY_SCHEMA_DEFAULTS` scatter | open |
| HY-S-3 | medium | P1 | MasterInput stub vs TZ | open |
| HY-S-5 | low | P2 | edges as dict | open |
| CONN-1 | low | P2 | `node_type` → `connection_node_type` wire rename | open |

---

## Relief ↔ barrier — smells registry (RELIEF-BAR)

| ID | Sev | Status | P | Суть | Связь ТЗ |
|---|---|---|---|---|---|
| **RELIEF-BAR-1** | medium | **resolved** | P2 | Intent `structure_refs` → light wall via `ribbonFence` + `ribbonBarrierApply` (не в relief). Stamp/obstacle keys ← `WorldTerrainRegistry` (`require_engine_terrain_key` / `canonical_barrier_terrain_keys`), не литералы wall/gate. | [`tz_terrain_relief.md`](./tz_terrain_relief.md) Wave C · [`tz_locations.md`](./tz_locations.md) § barrier registry |

**Не путать:** `earthen_canal` ≠ lined/`structure_refs`; R36n clearance ≠ R36p canal policy; `canal_template_registry` ≠ `barrier_template_registry`.

---

## Relief templates — post-impl architecture smells (RELIEF-T)

**Scope:** `dataModel/terrain/relief`, `generators/terrain/relief`, mountains stamp, library/import, bundle R35, bake preload / road_shoulder, JV relief accessors.  
**Refs:** [`tz_terrain_relief.md`](./tz_terrain_relief.md) R8/R20–R36q · audits 2026-07-30 (×2) · **SOLID+dataModel 2026-08-02** · **canal R36p/q audit 2026-08-05** · **BUNDLE-2** · **RELIEF-BAR-1**.  
**Plan фиксов (round 1–2):** [`.cursor/plans/relief-tech-debt-fixes.md`](../.cursor/plans/relief-tech-debt-fixes.md).  
**Не в scope здесь:** UI R30; climb gameplay; DAG nodes; full barrier materialize (→ RELIEF-BAR-1); footprint scan для R36n в bake (helper `obstacleClearance` есть — wire gap later).

**Verdict (god-object):** 500+ LOC **relief generator** god-class нет. Round-1 + round-2 — **resolved**.  
**Round-3 (2026-08-02):** generators остаются мелкие/typed; долг сместился в (1) JV facades `worldRow` / `worldSlices`, (2) bake multi-concern (`roadShoulderApply`, `RoadContributor`), (3) DRY knobs Mode A vs `ReliefGradeKnobs`, (4) value-fallback мимо POJO. Эталон scalars: `WorldReliefGradeObstacleScalars` (не долг).

### Registry — round 1 (закрыто / accepted)

| ID | Sev | Status | P | Суть |
|---|---|---|---|---|
| **RELIEF-T-1** | high | **resolved** | P1 | `RadialGradeDecision` vs `RibbonGradeDecision`; package `__init__` exports both. |
| **RELIEF-T-2** | high | **resolved** | P1 | R21 miss/empty body → all-SLOPE via `fallback_kind`; Mode D only for live template empty recipe. |
| **RELIEF-T-3** | high | **resolved** | P1 | `ReliefNotFoundError` / `ReliefValidationError`; HTTP mapping in `api/routes/reliefTemplates.py` only. |
| **RELIEF-T-4** | high | **resolved** | P1 | Preload → `application/worldData/loadReliefTemplatesForWorld.py` (not generators). |
| **RELIEF-T-5** | medium | **resolved** | P2 | TZ R31: v1 = world→object; side-level deferred (documented). `side_policy` reserved. |
| **RELIEF-T-6** | medium | **resolved** | P2 | Bundle export via typed registry + WARNING on miss (`bundle/reliefSection.py`). |
| **RELIEF-T-7** | medium | **resolved** | P2 | `import_path` enforces `resolve_relief_domain_root()` (env `RELIEF_TEMPLATES_ROOT` or `cwd/relief_templates`); pack = direct child; relative paths under root. |
| **RELIEF-T-8** | medium | **resolved** | P2 | `MountainSideRecipe.EMPTY_*_WEIGHT`; logs use `mode.log_label()` (weights\|pattern\|fixed\|empty). |
| **RELIEF-T-9** | medium | **resolved** | P2 | `roadShoulderApply` after `RoadContributor` paint: segmentize → grade → stamp `system_facing`; intents on `BakeContext.road_shoulder_intents` (barrier = RELIEF-BAR-1). **Остаток width → T-16.** |
| **RELIEF-T-10** | medium | **resolved** | P2 | `resolved_sides` empty → WARNING + all-SLOPE defaults (stamp path required for R33). |
| **RELIEF-T-11** | medium | **resolved** | P3 | Bake seed SoT = `bake_seed(world)` → `world_uid` (см. T-17). |
| **RELIEF-T-12** | medium | **resolved** | P2 | FS/pack → `reliefTemplateFsImport.py`; library = SQL upsert/CRUD + thin `import_path` delegate. |
| **RELIEF-T-13** | low | **resolved** | P3 | `terrainMap` from enum; row version from POJO; invalid edge policy → WARNING. |
| **RELIEF-T-14** | low | **resolved** | P3 | Schedule hole → R21 safe SLOPE (`schedule_hole_safe_slope`), not skip. |
| **RELIEF-T-15** | low | **accepted** | P3 | Logging in pick/grade kept intentionally (R8 apply diagnostics); not extracted. |

### Registry — round 2 (re-audit → fixed 2026-07-30)

| ID | Sev | Status | P | Категория | Суть |
|---|---|---|---|---|---|
| **RELIEF-T-16** | **high** | **resolved** | P1 | неявный контракт | `expand_shoulder_ring` + apply after grade: width outward ray; pocket between roads = seeds only. |
| **RELIEF-T-17** | medium | **resolved** | P2 | неявный контракт | `bake_seed(world)` в `relief/bakeSeed.py`; materializer + roadShoulderApply. |
| **RELIEF-T-18** | medium | **resolved** | P2 | неявный контракт | Empty/partial preload WARNING; unbound library WARNING в pack orchestrator. |
| **RELIEF-T-19** | medium | **resolved** | P2 | неявный контракт | TZ: v1 consumers = mountain + road_shoulder; open_land/shore = H later. |
| **RELIEF-T-20** | medium | **resolved** | P2 | неявный контракт | `parseObjectReliefPickPolicy` на bake boundary; RoadContributor передаёт typed policy. |
| **RELIEF-T-21** | medium | **resolved** | P2 | слои | `ImportResult` в `application/`; reliefSection без api; relief errors → `api/routes/worlds.py`. |
| **RELIEF-T-22** | medium | **resolved** | P2 | dataModel | Defaults ширины из `ReliefGradeKnobs` → RoleCase / Template / DeltaInterval. |
| **RELIEF-T-23** | low–med | **resolved** | P3 | неявный контракт | TZ: range laterals declare-only; stamp только `peaks[]`. |
| **RELIEF-T-24** | low | **resolved** | P3 | слои | `RoadShoulderIntent` на bake boundary; `sideFill.__all__` без profile re-exports. |
| **RELIEF-T-25** | low | **resolved** | P3 | dataModel | Pick/stamp/grade paths: `ReliefContext` enum (`.value` только в логах). |
| **RELIEF-T-26** | low | **accepted** | P3 | dataModel | Sentinel → `UNBOUNDED_DELTA_Z_MAX`; wire letters A–D **не** меняем (breaking persist); logs = `log_label`. |
| **RELIEF-T-27** | low | **resolved** | P3 | неявный контракт | `relief_dz(ref, adjacent)` в `shoulderWidth.py`; sampler зовёт helper. |

### Registry — round 3 (SOLID + dataModel audit, 2026-08-02)

Оси: god-object · SRP · DRY · wire keys ≠ dataModel · values ≠ dataModel.  
IDs **RELIEF-T-28…T-41** — open backlog; resolved не удалять.

| ID | Sev | Status | P | Категория | Суть |
|---|---|---|---|---|---|
| **RELIEF-T-28** | **high** | **resolved** | P1 | god-object / JV | Runtime resolve via `WORLD_SLICES`: `resolve_registry_list/dict/json_blob_world` + thin `worldRow` DX. Multi_column уже JV-SCALARS-2. Special merge district/barrier → **T-29**. Package split deferred. |
| **RELIEF-T-29** | medium | **resolved** | P2 | god-object / JV | Import merge → `worldSliceMerge.py`. Runtime canonical⊕world via `WorldSlice.runtime_merge_id_field` ← POJO `RUNTIME_MERGE_ID_FIELD` (district/barrier). Catalog+resolve remain in `worldSlices`. `building_layout` out of scope. |
| **RELIEF-T-30** | medium | **resolved** | P2 | SRP | Bake split ✅: sample / materialize / stamp / intent + thin `apply_*` facade. = **T-52**. § [roadShoulderApply split](#roadshoulderapply-split-t-30--t-52). |
| **RELIEF-T-31** | medium | **resolved** | P2 | SRP | `RoadContributor` = paint only; `RoadShoulderContributor` after ROAD via `ctx.painted_road_edges` (`PaintedRoadEdge`). |
| **RELIEF-T-32** | medium | **resolved** | P2 | SRP | `ribbonSegmentize.py` (`RibbonSegment` + `owner_uid`); `ribbonGrade.py` = pick/grade only. |
| **RELIEF-T-33** | medium | **resolved** | P2 | DRY | `conditionNormalize._interval_from_grade_knobs` — one Mode A\|B builder from `ReliefGradeKnobs` |
| **RELIEF-T-34** | medium | **resolved** | P2 | DRY / dataModel | Mode A: flat wire + ``mode_a_grade_knobs()`` → ``ReliefGradeKnobs`` validate/read (T-34A). Mode B unchanged (`ReliefDeltaBand`). Nested `knobs:{}` wire rejected (product lock). |
| **RELIEF-T-35** | medium | **resolved** | P2 | DRY | `require_weights_pair` / `require_weights_sum` in `reliefGradeKnobs`; call sites: RoleCase, Template root, MountainSideRecipe, GradeKnobs |
| **RELIEF-T-36** | medium | **resolved** | P2 | DRY | `resolve_picked_template` in `templatePick`; ribbon + mountain stamp call it; R21 policy stays at callers |
| **RELIEF-T-37** | medium | **resolved** | P2 | wire keys | `worldRow` column names ← `slice_column_key` / `WorldSlice.world_keys` (T-28). Эталон scalars: `RELIEF_OBSTACLE_SCALAR_WIRE_KEYS`. |
| **RELIEF-T-38** | medium | **resolved** | P2 | values | `expand_shoulder_ring`: honor `width<=0` → empty. Hybrid D: `geom_resolve` honors explicit L=0 (no partition / no bump); `gradePass` `requested_length=0` + `geom=None`; bake skip via clearance. `expand_shoulder_ring` ≠ bake SoT. |
| **RELIEF-T-39** | medium | **resolved** | P2 | values | `conditionNormalize`: typed `delta_z` / `mode_a_grade_knobs()` — no `or 0`/`or 1`/`or 0.0` |
| **RELIEF-T-40** | low | **resolved** | P3 | DRY | `seededHash.seeded_u01`/`seeded_index`; `RibbonGradeDecision.skipped_site`; logs `ReliefSideKind.SLOPE.value` |
| **RELIEF-T-41** | low | **resolved** | P3 | values | `gradePass` skip attachments ← `ReliefGradeKnobs` defaults |

**Связь R36n (не smell):** `WorldReliefGradeObstacleScalars` + `ReliefGradeObstaclePolicy` + `obstacleClearance` — shipped; bake footprint→`free_gap` ещё нет (отдельный impl после R36 materialize).

### Registry — round 4 (R36p/q canal impl audit, 2026-08-05)

**Scope:** `canal_template_registry`, knobs XOR `earthen_canal`\|`structure_canal`, `canal_obstacle_policy`, bake clearance-path canal.  
**Wire/product lock:** [`tz_terrain_relief.md`](./tz_terrain_relief.md) R28/R36p/q / C20–C21 — **не** менять без мастера.  
**Impl:** `seedCanalResolve` / `canalObstacleResolve` / `canalAttachments` / `outlineCanalCollect`; bake thin call.  
**Fix wave:** **T-42…T-51** resolved. **Post-fix:** **T-52/T-30** ✅ · **T-54/T-56/T-59…T-65** ✅; residual opt **T-66** (+ pre-existing **T-34**).

| ID | Sev | Status | P | Категория | Суть |
|---|---|---|---|---|---|
| **RELIEF-T-42** | **high** | **resolved** | P1 | слои / SRP | Canal resolve → `seedCanalResolve.resolve_seed_canal_attachments`; bake thin call. Остаток multi-concern bake → **T-30** / **T-52**. |
| **RELIEF-T-43** | **high** | **resolved** | P1 | single-writer | Per-seed cut → Grade; Intent = `aggregate_canal_attachments` over stamped seeds (no `max_L` re-resolve). |
| **RELIEF-T-44** | medium | **resolved** | P2 | dataModel | `earthen_canal: bool\|None = None` (omit); reject flat `structure_refs` + `structure_canal` (R28). Flat refs alone = BAR-1 OK. |
| **RELIEF-T-45** | medium | **resolved** | P2 | dataModel | Map `ReliefConditionTerrain`(+`road`) → `CanalObstacleEntity` в `canalObstacleResolve._TERRAIN_TO_CANAL_ENTITY`. |
| **RELIEF-T-46** | medium | **resolved** | P2 | dataModel | Conflicting `canal_ref` reject ✅. pick+canal в одном blob — **accepted** wire TZ. |
| **RELIEF-T-47** | medium | **resolved** | P2 | DRY | `resolve_knobs_canal` → `CanalAttachments`; collect/cache; Intent aggregate (no second resolve). |
| **RELIEF-T-48** | medium | **resolved** | P2 | хардкод / R21 | Константы why/fallback в `canalAttachments` (`WHY_*` / `FALLBACK_*` / `EVENT_*`). Canal-only; bake events → **T-56**. |
| **RELIEF-T-49** | low | **resolved** | P3 | SRP | Fit/не-fit в одном `resolve_seed_canal_attachments`; knobs enrich = `resolve_knobs_canal_attachments`. Alias leftover → **T-58**. |
| **RELIEF-T-50** | **high** | **resolved** | P1 | dataModel / persist | Grade + SQL: `structure_refs` + `structure_canal` (+ R36j); persist/factory stamp same cut as Intent. **DB recreate.** Intent parity → **T-53**. |
| **RELIEF-T-51** | medium | **resolved** | P2 | SRP / UX | `roadShoulderGrade` = raw knobs only; single resolve in bake `resolve_seed_canal_attachments`. |
| **RELIEF-T-52** | medium | **resolved** | P2 | god-object / SRP | = **T-30**. Split ✅: `roadShoulderSample` / `Materialize` / `Stamp` / `Intent` + thin apply (~109 LOC). |
| **RELIEF-T-53** | medium | **resolved** | P2 | dataModel | `Canal` = `EarthenCanal` \| `StructureCanal`; Intent.`canal` + `build_canal`/`draw_canal`; Grade flat из draw. Entry XOR. |
| **RELIEF-T-54** | medium | **resolved** | P2 | dataModel / values | Intent.`earthen_canal` → `bool\|None` (omit=`None`); skipped `to_intent` не synthesize `EarthenCanal` from knobs. Wave **B4a**. |
| **RELIEF-T-55** | medium | **resolved** | P2 | хардкод | `EMPTY_EARTHEN_CUT` рядом с `EMPTY_CANAL` (policy omit ref). |
| **RELIEF-T-56** | medium | **resolved** | P2 | хардкод | Shared `reliefEvents.py` (EVENT/WHY/REASON); canalAttachments re-exports `EVENT_RESOLVE_FALLBACK`; bake/grade/mountain call sites use tokens. |
| **RELIEF-T-57** | medium | **resolved** | P2 | DRY | Один `_resolve_canal_ref` + `_r21_no_canal`; lookup = `attachments_from_registry_ref` (None→R21). Knobs и policy — тот же путь. |
| **RELIEF-T-58** | low | **resolved** | P3 | DRY / API | Alias `resolve_knobs_canal_attachments` удалён; `CanalAttachments.grade_fields()` / `intent_fields()` в bake. Persist row mapping — отдельный layer OK. |
| **RELIEF-T-59** | low | **resolved** | P3 | dataModel / mapper | `json_list_col`: always dump `[]`; NULL/`{}` → `[]`. Grade `structure_refs` + `cell_refs`. Wave **B5**. |
| **RELIEF-T-60** | medium | **resolved** | P2 | observability | Silent paths logged: stamp obstacle/column/empty; sample empty; apply early-exit (no road/templates/samples) debug; materialize empty plan + h&lt;1. Clearance/anchor warning unchanged. |
| **RELIEF-T-61** | low | **resolved** | P3 | SRP | `project_canal_draw`; no knobs→`EarthenCanal` synthesize; adapters → `roadShoulderAdapters`; `StampRibbonOutcome` + log in materialize. Wave **B5**. |
| **RELIEF-T-62** | low | **resolved** | P3 | хардкод / dataModel | `_ORTHO` ← `CARDINAL_WALL_OUTWARD_DELTA` (E,W,N,S). Wave **B5**. |
| **RELIEF-T-63** | low | **resolved** | P3 | хардкод | `project_canal_draw` / `EMPTY_DRAW` в materialize+Intent. Wave **B5**. |
| **RELIEF-T-64** | medium | **resolved** | P2 | ответственность / values | `SeedMaterializeSkip` + `SegmentMaterializeResult.skip_why`; apply `reason=mat.skip_why or WHY_NOT_STAMPED` (не всегда `clearance_skip`). Wave **B4b**. |
| **RELIEF-T-65** | low | **resolved** | P3 | DRY / observability | Empty-sample log = apply only; sample pure. Wave **B5**. |
| **RELIEF-T-66** | low | **resolved** | P3 | observability | Skip layers: `ribbon_skip_apply` \| `_grade` \| `_materialize` + closed `WHY_*` sets; monotoken `ribbon_skip` removed |
| **RELIEF-T-67** | **high** | **resolved** | P1 | observability | Bake file miss: `reliefLog` → `app.relief` не в `_GENERATION_PREFIXES` → shoulder/canal warnings не в `bake-light-*.log`. **Fix:** allowlist `app.relief`. |

**Связанный pre-existing (не новый, но в том же ревью):** **RELIEF-T-34** — `ReliefRoleCase` Mode A дублирует knobs-поля.  
**Не путать с product lock:** R36p «policy только если не вмещается» + knobs XOR — **correct**; долг = слои/POJO/DTO parity, не отмена контракта.

### Post-split review (T-30/T-52 ship, 2026-08-06)

Проверка split-модулей: логи · SRP · хардкоды · dataModel.

| Критерий | Вердикт | Open IDs |
|---|---|---|
| Логи | Silent paths → `relief_warning`/`relief_debug` | **T-60** ✅ |
| SRP | Split + adapters / StampOutcome / project_canal_draw | **T-61** ✅ |
| Хардкоды event/reason | Shared `reliefEvents` | **T-56** ✅ |
| Хардкоды ortho / draw False | Facing deltas; `project_canal_draw` | **T-62/T-63** ✅ |
| dataModel canal/kind/facing | OK (`Canal`, `ReliefSideKind`, `Facing.opposite`, registries) | — |
| Intent property coerce | omit→None (not silent False) | **T-54** ✅ |
| json list hydrate | `json_list_col` | **T-59** ✅ |

### Post-B2/B3 review (god / DRY / SRP, 2026-08-06)

Ревью изменений Wave B1–B3 (Q6 sample + T-56/T-60). **God-object регрессии нет** (apply thin; materialize = pipeline, не blob).

| # | Находка | Ось | Debt | Когда чинить | Ссылка волны |
|---|---|---|---|---|---|
| 1 | Skipped Intent omit→False via `_drawn` | dataModel | **T-54** | **B4a** ✅ | [`tz_terrain_relief.md`](./tz_terrain_relief.md) § Wave B · B4 |
| 2 | Intent `reason=clearance_skip` при любом `not mat.stamped` | ответственность | **T-64** | **B4b** ✅ | § Wave B · B4 |
| 3 | Double log `empty_sample` (sample + apply) | DRY | **T-65** | **B5** ✅ | § Wave B · B5 |
| 4 | `materialize` pipeline + bake adapters; stamp log vs outcome | SRP | **T-61** | **B5** ✅ | § Wave B · B5 |
| 5 | `_ORTHO` ≠ Facing | хардкод | **T-62** | **B5** ✅ | § Wave B · B5 |
| 6 | `CanalDrawResult(False,…)` мимо `EMPTY_DRAW` | хардкод | **T-63** | **B5** ✅ | § Wave B · B5 |
| 7 | `EVENT_RIBBON_SKIP` монотокен | observability | **T-66** | ✅ layer events + why | § Wave B · B5 |
| 8 | `json_col` structure_refs `{}` | mapper | **T-59** | **B5** ✅ | § Wave B · B5 |

#### B4 schedule (T-54 / T-64) — shipped 2026-08-06

| Step | ID | Что | Статус |
|---|---|---|---|
| **B4a** | **T-54** | Intent.`earthen_canal` omit=`None`; skipped без knobs→`EarthenCanal` synthesize | ✅ |
| **B4b** | **T-64** | `SeedMaterializeSkip` + `skip_why`; apply `reason=skip_why or WHY_NOT_STAMPED` | ✅ |

**Не смешивать с B5:** T-61 adapters, T-62 `_ORTHO`, T-63 `EMPTY_DRAW`, T-65 double log, T-66 event split.

**Не долг:** sample без `ordered` (Q6); `reliefEvents` SoT; silent-path logs (T-60).  
**Agent pointer:** [`.cursor/plans/relief-dev-plan.md`](../.cursor/plans/relief-dev-plan.md).

### roadShoulderApply split (T-30 / T-52)

**Locked:** 2026-08-06. **Shipped:** 2026-08-06 (phases 0–5 one PR). Canvas: `road-shoulder-apply-split-plan`.  
**Scope:** только `pack/bake/lightGrid/` contributor. Canal kinds / resolve — **не** трогать (уже out).  
**Правило (было):** один PR = одна phase — **waived** for this ship (full split). Stamp/adapters **не** в `generators/terrain`. Q6 dilate sample — Wave B1 ✅.

**Уже вынесено (не трогать):** `ribbonSeedResolve`, `edgeRoadAnchor`, `volumeMaterialize`, `seedCanalResolve` / `canalAttachments` (`build_canal`), `ribbonGrade`, `gradeInstanceFactory`.

**Modules (shipped)**

| Файл | Роль | Public |
|---|---|---|
| `contributors/roadShoulderApply.py` | road facade only | `apply_road_shoulder_grades` |
| `contributors/roadShoulderSample.py` | discovery | `sample_shoulder_cells` |
| `contributors/roadShoulderMaterialize.py` | seed + segment pipeline | `materialize_segment` / `materialize_seed` + contracts |
| `contributors/roadShoulderStamp.py` | compose writes | stamp ribbon / column / `grade_uid` / `cell_blocked_light` |
| `ribbonIntent.py` | DTO + emit | `RibbonIntent`, `to_intent` |
| `generators/.../ribbonGrade.py` | pick/grade | `RibbonGradeResult`, `grade_ribbon_segments` |
| `contributors/ribbonBarrierApply.py` | BAR-1 | `apply_ribbon_barriers` |

**Data flow:**  
`apply` → sample → `grade_ribbon_segments` → `materialize_segment` → per seed (`clearance` → `resolve_seed_canal` → anchor → volume → stamp → Grade) → aggregate canal → `to_intent` → `ctx.ribbon_intents`.

### World multi_column scalars — DRY (JV-SCALARS)

Клон механики (не «разные consumer одних полей»): climate / terrain / relief-obstacle — **разные** колонки `worlds`, одинаковый каркас `WIRE_KEYS` + `wire_from_mapping` + `validate_world_row_*`.

| ID | Sev | Status | P | Суть |
|---|---|---|---|---|
| **JV-SCALARS-1** | medium | **resolved** | P2 | Третий клон scalar wire boilerplate. **Fix:** `dataModel/worldScalarWire.py` — `pojo_wire_keys` / `scalar_wire_from_mapping` / `validate_world_row_pojo_columns`; climate/terrain/relief-obstacle — thin wrappers |
| **JV-SCALARS-2** | medium | **resolved** | P2 | Hand-written multi_column resolve в `worldRow` (climate/terrain/relief) дублировал `WorldSlice`. **Fix:** `resolve_multi_column_world` + `WORLD_SLICE_BY_POJO`; named accessors = thin DX. Field shorthand `relief_grade_obstacle_policy` OK. Registry/blob runtime → **T-28** ✅ |

---

### Clean (не долг / wins)

- POJO SoT: R26/R27/R32/R33 validators; I8 normalize→schedule→classify.
- R34 skip unknown terrain; R35 bodies не в world JSON.
- Domain errors в library; preload вне generators; dual Decision split.
- Thin `reliefTemplates` route; mountain declare wins; road_shoulder intents boundary для BAR-1.
- Shoulder width bake; bake_seed; typed edge policy; FS import split.
- **R36n scalars:** `WorldReliefGradeObstacleScalars`; `obstacleClearance` thin; grade path без `dict.get` knobs.
- **JV-SCALARS-1/2:** `worldScalarWire` + `resolve_multi_column_world` (import slice = runtime SoT).
- **R36p/q canal:** typed `EarthenCanal`\|`StructureCanal`; `build_canal`/`draw_canal`; Intent.`canal`; single resolve. Bake SRP: **T-30/T-52** ✅. Wave B polish **T-54…T-65** ✅. Residual opt: **T-66**.
- Generators package split (pick / normalize / classify / kindRoll / gradePass / expand) — нет 300+ LOC domain blob.

### Приоритетный backlog (sync relief waves)

**Product SoT:** [`tz_terrain_relief.md`](./tz_terrain_relief.md) § Порядок · [`.cursor/plans/relief-dev-plan.md`](../.cursor/plans/relief-dev-plan.md).  
**Post-B2/B3 review map:** § [Post-B2/B3 review](#post-b2b3-review-god--dry--srp-2026-08-06) выше.

1. ~~**Wave B1 — Q6** dilate shoulder sample~~ ✅  
2. ~~**Wave B2/B3 — T-60 / T-56**~~ ✅  
3. ~~**Wave B4 — B4a T-54 → B4b T-64**~~ ✅  
4. ~~**Wave B5 — T-59…T-63, T-65**~~ ✅ (**T-66** deferred)  
5. ~~**Wave C — RELIEF-BAR-1**~~ ✅ (`ribbonFence` + `ribbonBarrierApply`)
6. ~~**Wave D —** `open_land` / `shore`~~ ✅ (`ribbonGradeApply` + contributors)
7. ~~**Wave D polish**~~ ✅ (`contextRibbonApply` / `ribbonSampleUtil` / `ribbon_intents`+`ref_cells` / BAR-1 once)
8. ~~**Post-R36w —** GradeFormation apply~~ ✅ ([план](../.cursor/plans/detailed-grade-volume-canal.md); § R36i-T)
   ~~**Post-impl (не Wave E):** **R36i-T-4…T-11**~~ ✅ — § [R36i-T post-impl](#r36i-t--gradeformation-apply--post-impl-smells)
   ~~**R36i-T-12**~~ ✅ — write-set `reconcile` (R36j uid ↔ `cell_refs`)
   ~~**R36i-T-13…T-15**~~ ✅ — T-12 leftovers (`of` / drop-log / sorted refs)
9. **Wave E —** R36s / R36r / R36o / Q4 / R36f/k / UI R30 (later; после GradeFormation apply)
10. **Parallel eng (не gate waves):** ~~T-33…T-41, T-66~~ ✅; road-facade naming optional; fixtures `*_templates`  
~~T-28 / T-29 / T-37~~ ✅ worldRow ← slices + import merge module + runtime merge-policy  
   ~~shared `RoadShoulderIntent`/`grade_road_shoulder_*`~~ ✅ → `RibbonIntent` / `grade_ribbon_segments`  
   ~~**T-31/T-32**~~ ✅  
   **PAR-T-1…T-8** ✅ — L2 grade ASCII post-impl ([§ Pack ASCII](#pack-ascii--l2-grade-carry--post-impl-smells-par-t))  
   ~~**R36i-T-4…T-11**~~ ✅ — GradeFormation post-impl ([§ R36i-T](#r36i-t--gradeformation-apply--post-impl-smells))  
   ~~**R36i-T-12**~~ ✅ — write-set reconcile  
   ~~**R36i-T-13…T-15**~~ ✅ — T-12 leftovers
11. (optional) rename `MountainSideRecipeMode` wire A–D — breaking + migration

---

## Pack ASCII / L2 grade carry — post-impl smells (PAR-T)

**Контекст:** 2026-08-12 — L2 location grade ASCII shipped ([`tz_pack_ascii_render.md`](./tz_pack_ascii_render.md) **PAR-G7…G10**; plan `grade-detailed-location-render`). Ревью: неявные контракты · dataModel · хардкоды · SRP.

**Не долг (locked product):** grade writer = **detailed_bake geometry** ([`tz_terrain_relief_v1_superseded.md`](./tz_terrain_relief_v1_superseded.md) **R36u**; исключение из [§ Идея 2](./tz_world_pack_storage.md)); generate = **per-chunk в pool** (**R36v**, impl **T-11**); L0 **без** outdoor grade; ~~L0→L2 grade-uid nearest carry~~ superseded; FineTerrain column `system_grade_uid` → Instance; empty → omit `surface_grade` / `grade_{n}`; L2 dump `surface_grade.txt` + `z/grade_{n}.txt` (location **и** wilderness); anchors **R36t**. L0 ribbon writers **removed** (T-8). Generate mill/pack SoT — [`tz_terrain_relief.md`](./tz_terrain_relief.md).

### Legacy L0 grade — inventory (R36u migrate off)

**Статус:** §A outdoor grade writers + §C upsample helper **removed** (R36u-T-8). Pure generators (§B) reuse on detailed. **Не трогать:** terrain mask carry (`system_terrain`), hydro hard corridor, facing upsample, `surface_z` upsample. Agent plan: [`.cursor/plans/r36u-grade-detailed-migrate.md`](../.cursor/plans/r36u-grade-detailed-migrate.md).

#### A. L0 compose writers (stamp `system_grade_uid` на light) — **removed**

| Звено | Path | Status |
|---|---|---|
| Compose order | `COMPOSE_CONTRIBUTOR_ORDER` | no open_land/shore/road_shoulder |
| Enum members | `LightContributorId` | those three removed |
| Contributors + apply + stamp + BAR-1 + `ribbonIntent` | `…/contributors/openLand*`, `shore*`, `roadShoulder*`, `ribbon*`, `paintBarrier` | **deleted** |
| `painted_road_edges` | RoadContributor | **kept** for T-10 |

#### B. Pure generators (reuse in detailed geometry)

| Path | Роль | Target fix |
|---|---|---|
| `generators/terrain/relief/ribbonGrade.py` | pick/grade segments | caller = `detailedGradeGenerate` |
| `generators/terrain/relief/gradePass.py` / `volumeMaterialize.py` / `gradeInstanceFactory.py` | geom + instance | same |

#### C. L0→L2 **grade-uid** nearest carry (~~PAR-G8~~) — **removed**

| Path | Status |
|---|---|
| `upsample_grade_uid_from_parent_light` | **deleted** |
| `build_tile_surface_state` | `surface_grade_uid=None`; detailed fills bag |

**Остаётся без изменений (не grade, не «mask carry» как зонтик):** `upsample_terrain_from_parent_light` (**terrain mask carry**), `upsample_facing_from_parent_light` (facing), hydro merge, `upsample_from_parent_light` (`surface_z`).

#### D. L0 ASCII / dump `world-grade` (omit после R36u)

| Path | Роль |
|---|---|
| `render/worldMapPackRenderer.py` | `render_light_grade_mosaic` / `render_tile_light_grade_grid` |
| `render/packMapGridRender.py` | кладёт `ascii_grade` в payload |
| `render/renderPayloads.py` | поле `ascii_grade` |
| `render/mapSymbols.py` | grade symbols / legend (L0 path) |
| `scripts/render_maps.py` | пишет `world-grade.txt` |
| Tests | `tests/test_world_map_pack_renderer.py` (grade mosaic) |

**Не legacy dump:** L2 `locationTerrainPackRenderer` / `wildernessTilePackRenderer` + `fineTerrainAsciiKernel` (`surface_grade` / `grade_{n}`) — **target** product.

#### E. Wire / persist field (поле может остаться empty; writer L0 — нет)

| Path | Note |
|---|---|
| `dataModel/worldPack/worldMapCellWire.py` | `system_grade_uid` — L0 blob field; после migrate = omit/empty |
| Pack write from `LightGridCell.to_wire` | перестаёт наполнять grade с L0 |

#### F. Tests, завязанные на L0 ribbon writer

L0 harness deleted (`test_relief_road_shoulder_sample`, `test_relief_bar1`, `test_relief_intent_t54_t64`). Sample coverage → `test_detailed_grade_generate`; compose-order → `test_relief_wave_d`; pure canal → `test_relief_canal_r36pq`.

### R36u post-impl smells (R36u-T)

**Контекст:** 2026-08-13 — migrate shipped ([`.cursor/plans/r36u-grade-detailed-migrate.md`](../.cursor/plans/r36u-grade-detailed-migrate.md)); ревью 6 осей. **Scope:** только outdoor grade. **Не трогать:** terrain mask carry / hydro corridor / facing / `surface_z`.

**Agent pointer:** [`.cursor/plans/r36u-post-impl-debt.md`](../.cursor/plans/r36u-post-impl-debt.md).

| ID | Severity | Status | P | Ось | Smell | Target |
|---|---|---|---|---|---|---|
| **R36u-T-1** | **high** | **resolved** | P0 | неявный контракт | `detailedGradeGenerate` зовёт `bake_seed` / `segmentize_by_terrain` / `grade_ribbon_segments` **без импорта**; empty-templates tests зелёные | **Fix:** импорты; `test_generate_stamps_with_templates` |
| **R36u-T-2** | **high** | **resolved** | P1 | слои / DRY | L2 refine импортирует L0 `roadShoulderAdapters.plan_seed_volume` + `ribbonSampleUtil.CARDINAL_ORTHO_DELTAS` | **Fix:** `facing.CARDINAL_ORTHO_DELTAS` + `volumeMaterialize.plan_seed_volume`; L0 re-export |
| **R36u-T-3** | **high** | **resolved** | P1 | неявный контракт | `DetailedGradeResult.grade_instances` строится, `apply_detailed_grade` берёт только uid-bag; `persist_relief_grades` остался на L0 | **Fix:** persist на detailed + entry (`replace_world=False`); L0 persist тоже без world-wipe |
| **R36u-T-4** | **high** | **resolved** | P1 | неявный контракт | `FineChunkRunner` generate только `if relief_templates_by_uid`; entry/`FineTerrainRefineOrchestrator` templates не передаёт | **Fix:** preload `load_relief_templates_for_world` на FineTerrain + container |
| **R36u-T-5** | medium | **resolved** | P2 | dataModel / хардкод | `_OPEN_LAND_TERRAINS = {plains, forest}` `.value` ×2 (L0 sample + meter) | **Fix:** `open_land_terrain_keys()` ← `WorldTerrainMasks` |
| **R36u-T-6** | medium | **resolved** | P2 | SRP / typing | `apply_detailed_grade` на `TerrainBatchOrchestrator`; `relief_templates_by_uid: dict` + `model_validate` | **Fix:** generate в FineChunkRunner; `dict[str, ReliefTemplate]` |
| **R36u-T-7** | medium | **resolved** | P2 | DRY | `sample_open_land_meter` / `sample_shore_meter` ≈ L0 `openLandSample` / `shoreSample`; `meter_seed_blocked` ≈ `landward_seed_blocked`; uid stamp дважды | **Fix:** `sample_downhill_land_sites` + `sample_landward_of_refs`; blocked-адаптеры разные (compose vs meter) |
| **R36u-T-8** | medium | **resolved** | P2 | мёртвый код / dataModel | L0 ribbon files живы; `LightContributorId.OPEN_LAND/SHORE/ROAD_SHOULDER` в enum без factory; `upsample_grade_uid_from_parent_light` dead export | **Fix:** deleted L0 outdoor grade stack + enum members + upsample helper; tests on detailed/meter; `painted_road_edges` kept for T-10 |
| **R36u-T-9** | medium | **resolved** | P2 | неявный контракт | R36t = `body[:-1]`; canal args `del`; один Grade instance на сегмент (`last_plan`) vs L0 per-seed; `center_m` = cell xy; blocked = `z is None` | **Fix:** corridor = wrote − ref_cells; instance per seed; `center_m` = cell+0.5; no canal args; **`meter_grade_cell_blocked`** (missing/graded/road/hydro/barrier) |
| **R36u-T-10** | low | **resolved** | P3 | продукт / SRP | `road_shoulder` не на detailed path (TZ context есть) | **Fix:** `ReliefContext.ROAD_SHOULDER` в `_CONTEXT_SAMPLES`; `PaintedRoadEdge` → dataModel; тот же `PackJobUid` / каталог |
| **R36u-T-11** | **high** | **resolved** | P0 | perf / неявный контракт | `generate_detailed_grade` на **весь тайл** до `ChunkComputePool`; полный land-dict; per-seed instance spam | **Fix (R36v):** pool sample → stitch (один uid) → pool materialize+fill; late chunk inherit/upsert; без L0-кандидатов |

**Fix order:** ~~T-1 → T-9~~ ✅; ~~**T-11**~~ ✅; ~~**T-10**~~ ✅. **Не трогать:** terrain mask carry (`system_terrain`); hydro corridor; facing upsample; `surface_z` upsample.

**Не долг (уже locked):** L0 без outdoor grade writer; ~~PAR-G8 grade carry~~; L2 `surface_grade` / `grade_{n}` ASCII consumer; **R36v контракт** (impl = T-11).

### R36v post-impl smells (R36v-T)

**Контекст:** 2026-08-13 — T-11 shipped ([`.cursor/plans/r36v-grade-chunk-pool.md`](../.cursor/plans/r36v-grade-chunk-pool.md)); ревью 6 осей + `materialize_segment_meter`. **Scope:** только outdoor grade generate/persist на detailed. **Не трогать:** terrain mask carry / hydro corridor / facing / `surface_z`; DAG `modify_terrain`.

**Не долг:** stamp → `columnFillPass.system_grade_uid` → pack column → SQL instance — **конвейер одного writer’а**, не dual-write геометрии. Три caller’а `persist_relief_grades(..., replace_world=False)` — один persist.

| ID | Severity | Status | P | Ось | Smell | Target |
|---|---|---|---|---|---|---|
| **R36v-T-1** | **high** | **resolved** | P1 | god-object / SRP | `FineChunkRunner.refine_rects` inline two-pass; `generate_detailed_grade` второй оркестратор | **Fix:** `plan_grade_for_rects` + `materialize_grade_for_rects`; runner/фасад зовут те же helpers |
| **R36v-T-2** | medium | **resolved** | P2 | SRP | `materialize_segment_meter` одно тело; `last_plan` скрыт | **Fix:** `corridor_for_seed` → `SeedCorridor`; `resolve_segment_uid`; `commit_segment`; last successful seed явный |
| **R36v-T-3** | medium | **resolved** | P2 | dataModel | `_PRESERVE_FINE_HYDRO` литерал | **Fix:** `HydrologyCellRole.blocks_grade_seed()` (open water + `RIVER_BED`); meter blocked → POJO. L0 `PRESERVE_HYDROLOGY_ROLES` = другой enum (`WorldMapHydrologyRole`), не этот PR |
| **R36v-T-4** | medium | **resolved** | P2 | неявный контракт / DRY | `rect: object` + `_Rect` | **Fix:** `columnBounds.ColumnBounds` / `HaloRect` / `rect_contains` / `expand_rect`; `meterChunkGeom` делегирует. `ColumnRect` не выносили (цикл types→climate) |
| **R36v-T-5** | medium | **resolved** | P2 | dual-write / DRY | два union `cell_refs` | **Fix:** `gradeInstanceMerge.merge_cell_refs` + `merge_grade_instances`; persist только upsert |
| **R36v-T-6** | medium | **resolved** | P2 | неявный контракт | facade копит uid; inherit = первый CARDINAL; mint в двух местах | **Fix:** одна `resolve_segment_uid`; inherit = ровно один neighbor uid (0/2+ → mint); bag = cells этого rect |
| **R36v-T-7** | low | **resolved** | P3 | хардкод / DRY | кардиналы, raw `slope_length`, два blocked, pack origin, `copy=False` | **Fix:** `CARDINAL_ORTHO_DELTAS`; halo ← `outward_length_cells()`; `_road_grade_or_hydro_blocked`; `wilderness_chunk_origin`; `alias_heights=` |
| **R36v-T-8** | medium | **resolved** | P2 | неявный контракт | `SampleCell` = голый 3-tuple; sample/generate `item[0]` | **Fix:** `SampleCell` NamedTuple (`xy`, `terrain`, `dz`); segmentize принимает NamedTuple или tuple |
| **R36v-T-9** | medium | **resolved** | P2 | неявный контракт | result bag = `existing ∪ grid.grade_uid` (чужие клетки) | **Fix:** `materialize_planned_for_rect` / facade bag = `rect_contains` only |
| **R36v-T-10** | medium | **resolved** | P2 | неявный контракт | inherit = `min(uid)` склеивал две ленты | **Fix:** `inherit_segment_uid` — ровно один uid; иначе `None` |
| **R36v-T-11** | low | **resolved** | P3 | dataModel | `SeedCorridor.facing: str` | **Fix:** `Facing \| None`; `facing_wire` только в `commit_segment` |
| **R36v-T-12** | low | **resolved** | P3 | SRP | runner inline sample-pool + stitch | **Fix:** `_plan_tile_grade`; top-level imports из generate |
| **R36v-T-13** | low | **resolved** | P3 | DRY | persist inline union `cell_refs` | **Fix:** `apply_prior_cell_refs`; facade omit `object_policy`/`occurrence_start`; lazy `ColumnRect` |

**Fix order:** ~~T-1 → T-13~~ ✅. **Не трогать:** mask carry; DAG node.

**Agent pointer:** [`.cursor/plans/r36v-grade-chunk-pool.md`](../.cursor/plans/r36v-grade-chunk-pool.md); bake SoT [`tz_terrain_relief_v1_superseded.md`](./tz_terrain_relief_v1_superseded.md) R36v / **R36w**.

### R36w — worker stitch (resolved)

**Контекст:** 2026-08-14 — [`tz_terrain_relief_v1_superseded.md`](./tz_terrain_relief_v1_superseded.md) **R36w** / C27. Каталог граней до пула; один `ColumnRect` task; uid от `world_seed`.

| ID | Severity | Status | P | Ось | Smell | Target |
|---|---|---|---|---|---|---|
| **R36w-T-1** | **high** | **resolved** | P1 | schedule | два пула + barrier plan; lock-mint в воркере | Каталог + uid **до** пула; **один** pool task = `ColumnRect` |
| **R36w-T-2** | medium | **resolved** | P2 | неявный контракт | uid от `world_uid`+клетка / порядка воркеров | `make_seeded_uid` от `world_seed\|tile\|face` |
| **R36w-T-3** | medium | **resolved** | P2 | гонка / dual id | east A ≠ west B; межтайловый шов два uid | Канонический `face_key`; owner тайл в site_id |

**Не трогать:** mask carry; DAG; L0 grade writer. **Не** remap после persist. **Не** SW-волна как SoT порядка.

Шов `full_bake` / halo `grid_neighbor` / T-10 — [план](../.cursor/plans/full-bake-seam-halo-shoulder.md) ✅. Lookup только `WorldBounds` / `PackJobUid` / `Facing` / `ReliefContext`.

### FineChunkRunner layers (resolved)

**Контекст:** 2026-08-14 — `refine_rects` держал prep + nested compute/persist closures. SoT [`tz_terrain_relief_v1_superseded.md`](./tz_terrain_relief_v1_superseded.md) § FineChunkRunner слои.

| ID | Severity | Status | P | Ось | Smell | Target |
|---|---|---|---|---|---|---|
| **FCR-T-1** | **high** | **resolved** | P1 | SRP | `refine_rects` шесть фаз + closures на ~15 locals; второй `WorldPackReader` на inherit | `FineTileContext`; `prepare_fine_tile`; `compute_rect` → `ChunkComputeResult`; `FineChunkPersist` (`write_lock` + location flush). Grade **внутри** compute. **Не** новый grade orchestrator; **не** второй пул |

**Не трогать:** mask carry; DAG; R36w catalog-before-pool; halo = `grid_neighbor` only.

### R36i-T — volume z / canal on detailed

**Контекст:** 2026-08-14 apply shipped — [`tz_terrain_relief.md`](./tz_terrain_relief.md) § Post-R36w. Plan: [`.cursor/plans/detailed-grade-volume-canal.md`](../.cursor/plans/detailed-grade-volume-canal.md).

| ID | Severity | Status | P | Ось | Smell | Target |
|---|---|---|---|---|---|---|
| **R36i-T-1** | **high** | **resolved** | P1 | неявный контракт | uid-only; voxels = parent cliff при Grade SLOPE; canal не в apply | **Fix:** `GradeFormation` + `DetailedGradeResult.surface_z`; rect-local heightmap в `compute_rect`; `resolve_seed_canal` → factory; якоря R36t |
| **R36i-T-2** | medium | **open** | P2 | call site | BAR-1: L0 `paintBarrier` снят; нет detailed fence | **Вне** apply и **вне** C28; later, не silent impl |
| **R36i-T-3** | low | **split** | P3 | residual | был: System unused + face-graph + L0 ASCII | → **T-3a / T-3b / T-3c** |
| **R36i-T-3a** | low | **accepted** | P3 | residual | L0 `world-grade` ASCII | PAR-G5 omit; не impl. Dump cleanup later, не архитектура |
| **R36i-T-3b** | medium | **resolved** | P2 | topology | face-graph union-find; соседние грани с одним `(kind, outward, θ)` — разные instance | **Fix (v1 occupancy, срезан слой 7):** было `stitch_planned_segments` / `plan_grade_for_rects` / `ctx.planned`. Каталог `face_key` живой. Discover SoT — R41 |
| **R36i-T-3c** | low | **resolved** | P3 | entity | `ReliefGradeSystem` unused (POJO+SQL есть) | **Fix:** слой 6 — `VertexSlotSeam` на `ChunkComputeResult`; `emit_relief_grade_systems` после `merge_grade_instances` (slot intra-chunk; тело 8 на C29; UF этого refine). 1 фронт → нет строки; клетка → Instance. Макро-шов двух bake не impl. SoT [`tz_terrain_relief.md`](./tz_terrain_relief.md) § T-3c на шве чанков |
| **R41-T-1** | **high** | **resolved** | P1 | pipeline | sample пиков + stitch до пула; `compute_rect` stamp `planned` | **Fix:** `discover_and_paint` в `compute_rect` (слои 0–4). L2 apply не переписан. **T-3c ✅.** **Слой 7 ✅** (occupancy v1 удалён) |
| **R41-T-2** | **high** | **resolved** | P1 | неявный контракт / C40 | `GradePaintSpec` не единственный вход в L2 | **Fix:** `apply_grade_paint_spec(front, *, world, surface)` — `DiscoveredFront` собирает spec + identity. Подробно ниже |
| **R41-T-3** | **high** | **resolved** | P1 | неявный контракт / SRP | pick в `cap_front`; `decided` + молча skip | **Fix:** `CapFront` = length-only (L_tpl); pick + constrain в facade после discover. Подробно ниже |
| **R41-T-4** | **high** | **resolved** | P1 | SRP / plugin | `RavinePlugin.flood_member` шире `claims` | **Fix:** bank flood = bank; mask flood = terrace. Open_land не затапливает берег. Слой 5 стены — ниже |
| **R41-T-5** | medium | **resolved** | P2 | неявный контракт / SoT | walk стоп `z >` vs ТЗ `z ≥` | **Fix:** стоп на подъёме `z >`. Остаток 2026-08-19 (равная z не везде L) → **T-13** |
| **R41-T-6** | medium | **resolved** | P2 | неявный контракт | inherit uid 4-way, discover 8-way | **Fix:** канон inherit только орто (C15/C29) |
| **R41-T-7** | medium | **resolved** | P2 | dataModel | R37 `\|dz\|=1` = boolean на plugin | **Fix:** `stamp_min_abs_dz` на envelope |
| **R41-T-8** | medium | **resolved** | P2 | неявный контракт | три L: полный след / `requested_length` / `L_eff` | **Fix:** classify/stamp = коридор после C41 |
| **R41-T-9** | medium | **resolved** | P2 | SRP | `discover_and_paint` = pick + uid + paint | **Fix:** оркестратор вызывает discover / pick / uid / paint. Подробно ниже |
| **R41-T-10** | low | **resolved** | P3 | DRY | `site_id` / `terrain_key` считаются в facade; `DiscoveredFront` живой (T-2) | **Fix:** `front_bake_identity` + `discovered_front_from` |
| **R41-T-11** | low | **resolved** | P3 | dataModel / хардкод | `_TRACE_CAP=64`; `site_id` строка; `owner_uid=context.value` | **Fix:** walk cap = envelope max ∩ knobs; site `PackJobUid`; owner omit |
| **R41-T-12** | low | **resolved** | P3 | leftover | `Coord` alias в types / meter / catalog / halo | **Fix:** `planned` слой 7 ✅; новые модули без `Coord` alias; существующие не склеивали |
| **R41-T-25** | **high** | **open** | P1 | неявный контракт / consume | нет **алгоритма** полного occupancy 8 слотов; дыры на каскаде; interim `downhill_leftover` или игнор восьмёрки → dump `_` | **Target:** сначала полный fill (COUPLE + leftover каскада); mill без тела×8; узкий skip диагонали прямой W×L — **после** алгоритма, не вместо |
| **R41-T-17** | **high** | **resolved** | P1 | неявный контракт / consume | sidecar = leftover `rim∪corridor×outward`; same-z вид mill skip без записи; валидатор закрывает `+` из z | **Fix:** `couple_rim_rays` на leftover + 8-halo; merge first-wins; валидатор только pack / нет соседа |
| **R41-T-18** | **high** | **resolved** | P1 | pipeline / seed | impl: `millBuckets` + цикл `z_top`; приёмка мастера | канон § Две очереди; снос Q3 — **T-19**; полиш — **T-20…T-23** |
| **R41-T-19** | **high** | **resolved** | P1 | leftover mill | impl: нет `is_q3_seed` / `q3_s` / `q3_parent*`; бок = Q2 + `side_parent` | grep mill пуст; attach бока жив |
| **R41-T-20** | **high** | **resolved** | P2 | god-функция / SRP | `discover_fronts` = расписание + mill-события + attach + timings + sheer/C38 | **Fix:** `millSchedule.run_mill_schedule`; фасад leftover + sheer/C38 |
| **R41-T-21** | **high** | **resolved** | P2 | неявный контракт | `mill_stage_s` dict; ключ ведра `(z,uid)` без семьи; `q2_kind is None` = Q1; live corridor callback; третий вид Q2 | **Fix:** `DiscoverResult`; `BucketRef`; `MillOrigin`; `LiveCorridors`; SoT «сосед следа» = `is_side_seed` |
| **R41-T-22** | **medium** | **resolved** | P2 | хардкод | `"q1"`/`"landing"`; ключи timings в 4 местах; `UNSET_UID=0`; мёртвый `log_name`; `walks` | **Fix:** `MillFamily`/`Q2Kind`/`UNSET_SLOT`; `wire_keys()`; снят `from_mill`/`log_name`/`walks` |
| **R41-T-23** | **medium** | **resolved** | P2 | SRP / смешение | `ReliefVertices` несёт `side_parent` + timings; `fill_leftover` ходит по сетке; `is_side_seed` знает C39/посадку | **Fix:** attach+timings на `DiscoverResult`; walk `iter_rect_z_cells`; `is_q2_side_event` в scheduler |
| **R41-T-24** | low | **resolved** | P3 | naming | `z_at` читается как «z клетки», не как heightmap bake; «нет в z_at» ≠ z=0 | **Fix:** `z_height_map` метод/Mapping/Callable/`ZHeightMap`; consume TZ; `surface_z_at` / `terrain_z_at` не трогали |
| **R41-T-13** | medium | **resolved** | P2 | dataModel / хардкод | равная z: ravine = `if context` в `FrontStage`; shore = `envelope.grades_channel_bed` | **Fix:** ravine `grades_channel_bed=True`; `FrontStage` только envelope; `is_unconstrained` не включает walk-флаг |
| **R41-T-14** | low | **resolved** | P3 | неявный контракт | C41 «шерсть» и «якорь низины» — один `seam[]` | один флаг + docstring; C39 одинаков |
| **R41-T-15** | medium | **resolved** | P2 | неявный контракт / R36t | одиночный L=1 пишет uid на нижнюю клетку; ТЗ якорь низа не мутировать | **Fix:** TZ exception L=1 = первая downhill; дырка 1×1 skip C41 |
| **R41-T-16** | low | **resolved** | P3 | неявный контракт | `slope_fits` = только θ; `L_min` только в `slope_length_for`; без `path_length` unit dz → L=20 | docstring facade + stamp call sites с `path_length` |

**Fix order:** **T-25** первым (полный pack occupancy). ~~T-1…T-12~~ ✅. ~~**T-17**~~ ✅ (COUPLE + валидатор не из z — не заменяет T-25). ~~**T-18**~~ ✅. ~~**T-19**~~ ✅. ~~**T-20…T-23**~~ ✅. ~~**T-24**~~ ✅. ~~**T-13…T-16**~~ ✅. T-2 (BAR-1) не блокирует C28. **Не трогать:** Wave E; DAG; mask carry; parent `surface_z` upsample; `refresh_tile_gaps` из worker; voxel-ditch writer без plugin; Volume/`GradeFormation`; склеивать Rim/Front/Seam обратно в один `core.py`; Occupancy v1.

**Agent pointer:** [`.cursor/plans/relief-pipeline-v2.md`](../.cursor/plans/relief-pipeline-v2.md). Очередь SoT [`tz_terrain_relief.md`](./tz_terrain_relief.md) § Осталось — v2 vs L2 volume. Volume не форкать.

### R41-T — pipeline v2 post-impl smells

**Контекст:** 2026-08-17 — слои 0–4 в коде (`RimStage` / `FrontStage` / `SeamStage` / plugins / `discover_and_paint` в `compute_rect`). Ревью по осям: неявный контракт · dataModel · SRP · DRY. **Не** переоткрывать R41-T-1 (writer уже discover+paint). **Не** Wave E. **Не** склеивать стадии обратно в `core.py`.

**Не долг (сделано правильно):** стадии C39→R42→C41 как классы; `ReliefVertices` / `GradePaintSpec` не persist-POJO; маски с `WorldTerrainMasks`; барьеры с `WorldTerrainRegistry`; knobs через `grade_constrained` / `RibbonGradeDecision`; halo с `ReliefOntologyEnvelopes.canonical_defaults()` (в POJO SoT v1); L2 volume не форк; один fill после paint; DAG/schema не трогали. **T-17 ✅** закрыл leftover-only vs COUPLE и валидатор-из-z — **не** алгоритм полного occupancy (**T-25** open). **Mill T-18/T-19 ✅:** ведра не на `ReliefVertices`; `_seed_one` не копировали на очередь; предикаты посадки/бока не слиты в один `is_seed`; Rim/Front/Seam не склеены. **T-20…T-23 ✅:** цикл `z_top` в `millSchedule`; `DiscoverResult`; enum вёдер.

---

#### R41-T-17 — pack leftover-only vs 8 слотов + COUPLE

**Ось:** неявный контракт / consume. **Status:** `resolved`. **P:** P1.

**SoT (как реализовывать — не этот registry, а ТЗ):**

| Что | Где |
|---|---|
| 8 слотов клетки, kind SLOPE / SHEER / COUPLE; не leftover-only; generate пишет, dump/валидатор только читают | [`tz_terrain_relief_consume.md`](./tz_terrain_relief_consume.md) § «Pack — 8 слотов клетки» |
| Sidecar = слоты по правилам пары (оба конца leftover или COUPLE; omit без соседа); равная z = COUPLE, не invent в dump | [`tz_terrain_relief.md`](./tz_terrain_relief.md) § Правила стрелок |
| Валидатор не закрывает слот из сравнения z; пустой слот при соседе = ERROR | consume § валидатор; **R44** / **C43** |
| Вершина (live Q1 / target vertex queue): 8 видов с тела; в себя / same-z не leftover — это `+` | R41 «Не тело×8 как SLOPE/SHEER»; `_rim_shots` уже skip `nb in body` / `zn >= z_body` — **слот всё равно писать** |
| Следующие очереди (live Q2/Q3 / target derivatives): тот же 8-взгляд; занятый `(клетка, Facing)` не переписывать (first-wins) | mill `claim_facings` уже first-wins на leftover — pack `merge_grade_rim_rays` сейчас **last-wins**; имена очередей — **T-18** |

**Факт (было):** `walk_pack_senders` / `rim_rays_from_front` — только `rim ∪ corridor × outward`. Same-z вид mill отбрасывает, в sidecar не кладёт. `ReliefSideKind.COUPLE` generate не писал. Валидатор `unified_surface_facings` закрывал same-z из z.

**Fix (2026-08-25):** `couple_rim_rays` на leftover + 8-halo; persist `finish` пишет leftover затем COUPLE; `merge_grade_rim_rays` first-wins; `leftover_plus_halo` не считает COUPLE; валидатор закрывает только pack-слотом или отсутствием соседа в `z_height_map`. Dump не трогали. Consume: слот first-wins.

**Почему баг:** consume/R41 locked с 2026-08-23; код после `packSenders` (22–24 авг) уехал в leftover-only. Валидатор врёт «закрыто из z». Dump честно пустой (читает sidecar) — это не долг ASCII.

**Target:** generate пишет 8 слотов по consume TZ (leftover downhill + получатель + COUPLE оба конца same-z на leftover + 8-halo). Первый проход вершины заполняет; производные / следующие пояса только свободные слоты. Dump **не** трогать (уже только читает). Валидатор не invent закрытие из z. Не тело×8 Instance. Не второй обход тайла «добить восьмёрку» без станка. Не Occupancy v1.

**Готово когда:** sidecar содержит COUPLE (работа generate). Dump `surface_grade` с `+` на same-z — **smoke**, что слот записан, не отдельная задача рендера. R44 `empty=` не шторм на плато; валидатор не вызывает `unified_surface_facings` как закрытие слота; merge pack first-wins (или эквивалент «не затирать»). Имя карты высот — **T-24** ✅ (`z_height_map`). **Полный occupancy 8 слотов (каскад без дыр, без игнора восьмёрки) — не этот ID → R41-T-25.**

---

#### R41-T-25 — алгоритм полного заполнения 8 слотов pack

**Ось:** неявный контракт / consume. **Status:** `open`. **P:** P1. **Severity:** high (критический).

**SoT стрелок / слоёв mill vs pack / тело sidecar:** [`tz_terrain_relief.md`](./tz_terrain_relief.md) § Pack-слот; [`tz_terrain_relief_consume.md`](./tz_terrain_relief_consume.md) § Тело sidecar (`SCH-GRADE-CELL-SLOTS`). **Алгоритм заполнения, новый валидатор и golden-тесты — следующая разработка с мастером**, не этот документ закрывает код.

**Порядок:** сначала **алгоритм полного заполнения** по правилам пары (оба конца Octant/SHEER или COUPLE; нет соседа → **`SEAM` явно**). Узкий вид «прямой склон = только outward + `+`» — **после**, не вместо. Не закрывать дыры игнором восьмёрки.

**Слои (не смешивать):**

| | Mill (Instance) | Pack (слот клетки) |
|---|---|---|
| Каскад в одну сторону | одна прямая, Q2 вниз, не тело×8 | клетка всё равно **занята** с 8 сторон |
| Same-z | не leftover | **COUPLE** `+` оба конца |
| Outward фронта | один `Facing` Instance | leftover + получатель + остальные стороны по правилам пары |
| Дырка 1×1 | skip Instance (C41) | слоты по правилам пары, не «нет leftover → нет обхода» |

**Факт:** T-17 дал COUPLE + валидатор не из z. Mill каскад leftover-only на outward. На живом склоне пустые края. Код `downhill_leftover_rim_rays` / `leftover_plus_halo` / R44 — **interim**, не SoT.

**Запрещено:** тело×8 Instance; валидатор skip «потому что склон прямой»; закрывать слот из сравнения z; invent `+` в dump; Occupancy v1.

**Target (когда сядем за код):** generate пишет 8 кодов по [`tz_terrain_relief.md`](./tz_terrain_relief.md) § Pack-слот / Правила стрелок (`GradeOctant` 0…7 = поток SLOPE, `SEAM=8`, `SHEER=9`, `COUPLE=10`; не один enum; глифы только dump). θ честный `atan(h/L)`; местность (0, 90); SHEER **[80, 90)**. Новый валидатор читает коды (нет кода = ERROR, не «закрыто из z»). Эталоны ямы / W×L / каскад — в том же ТЗ. `slope_outcome(L=1)` 45° и `downhill_leftover_rim_rays` — не SoT. Locked-файл [`backend/tests/test_relief_r41_t25_locked_cases.py`](../backend/tests/test_relief_r41_t25_locked_cases.py) без правки карт до явной просьбы.

---

#### R41-T-18 — вёдра Q1 / Q2; очереди Q3 нет

**Ось:** pipeline / seed. **Status:** `resolved`. **P:** P1.

**SoT канон** — [`tz_terrain_relief.md`](./tz_terrain_relief.md) § Две очереди seed. Подробности вёдер — архив [`tz_terrain_relief_v1_superseded.md`](./tz_terrain_relief_v1_superseded.md). Этот ID — impl-тикет, не второй текст алгоритма.

**Факт:** `millBuckets` + `millSchedule.run_mill_schedule`; leftover walk `iter_rect_z_cells`; цикл `z_top`; Q2 `(z_q1, slot)`.

**Fix (2026-08-25):** сверка с § Две очереди seed — код = канон (один walk; Q2 из событий станка; нет третьей очереди seed).

**Почему баг:** покрытие heightmap не следовало из трёх проходов по сетке. Повторный walk rect за каждый drain — лишняя стоимость.

**Target:** канон ТЗ. Станок после seed не копировать. Не `OR` предикатов в одном drain.

**Готово когда:** код = § Две очереди в ТЗ (один walk; ключи `{z}_{uid}`; Q2 с `z_q1`; индекс без дубля; `z_top` = один leftover z; луч до упора). Снос `is_q3_seed` — **T-19**. Полиш god-функции/контрактов — **T-20…T-23** ✅.

---

#### R41-T-19 — удалить mill-очередь Q3

**Ось:** leftover mill. **Status:** `resolved`. **P:** P1.

**SoT очередей** — [`tz_terrain_relief.md`](./tz_terrain_relief.md) § Две очереди seed. Этот ID — **удалить третью очередь seed из кода**, не снять attach.

**Факт:** `is_q3_seed` / `q3_s` / `q3_parent*` сняты из `application/`. Бок = Q2 `is_side_seed` + bake `side_parent` / `side_parent_slot`. Grep mill/discover `is_q3_seed` пуст.

**Target:**

- Mill: нет `_drain(..., is_seed=_q3)`. Бок коридора сеется только как Q2 (T-18).
- Удалить `is_q3_seed`. Parent бока считать в mill Q2 (тот же min\|Δz\|), писать в bake-поле **без имени Q3** (`side_parent` / `side_parent_slot`).
- Убрать `q3_s` из mill timings и bake JSON.
- Тесты discover: третья очередь / `is_q3_seed` — нет; бок = Q2 + attach.
- Тесты T-3c attach: поведение то же, имена без `q3_*`.

**Не делать:** снять бок-attach (System); колонку SQL; `0002_*.sql`; Occupancy v1; вернуть drain Q3 «на всякий случай».

**Готово когда:** grep mill/discover/tests `is_q3_seed` / `q3_s` / `q3_parent` пуст; attach бока жив; schema `0001` без смены. Полиш слоёв после rename — **T-20…T-23** ✅.

---

#### R41-T-20 — `discover_fronts` god-функция

**Ось:** god-функция / SRP. **Status:** `resolved`. **P:** P2.

**Fix (2026-08-25):** `millSchedule.run_mill_schedule` держит `z_top` / enqueue / drain / `_seed_one` / attach. `discover_fronts` — leftover `iter_rect_z_cells` → schedule → sheer / finalize / C38. Rim/Front/Seam отдельные.

**Связь:** ревью mill Q1/Q2 (2026-08-25). Канон очередей — [`tz_terrain_relief.md`](./tz_terrain_relief.md) § Две очереди seed. Этот ID — вынести планировщик, не менять канон `z_top` / один walk / Q2 из mill.

**Факт:** `discover/core.py` `discover_fronts` (~190 строк тела, модуль ~295). Один вызов закрывает:

| Слой | Что делает сейчас внутри фасада |
|---|---|
| leftover | `MillBuckets.fill_leftover` |
| расписание | цикл `z_top` → C39 leftover → drain Q2 (посадки, потом бока) → `drop_leftover_z` |
| mill-события | `_enqueue_q2`: 8-соседи тела → `is_q2_seed`; 8-соседи нового SLOPE-коридора → `is_side_seed` |
| станок | `_seed_one` (plugin → flood → `add_vertex` → `propose` → `commit`) — это **оставить** одним |
| bake-attach | `_record_side` → `vertices.side_parent` |
| телеметрия | литералы `mill_stage_s` dict |
| хвост discover | `propose_sheers` / `seam.finalize` / `reconcile_members` |

Восемь closures (`_parent_sheers`, `_in_slope_trace`, `_live_corridor_slot`, `_record_side`, `_claim_body`, `_enqueue_q2`, `_mill`, плюс вложенный drain) делят мутабельные `fronts` / `buckets` / `vertices`. Это не god-**класс**; это god-**функция**. `MillBuckets` сам по себе узкий (индекс + leftover/Q2).

**Почему баг:** смена расписания, attach или таймингов правится в том же теле, что sheer/C38. Неявное состояние closures легко сломать при третьем виде Q2 (**T-21**). **T-9** уже вынес жир из `discover_and_paint`; жир уехал вниз в `discover_fronts`.

**Target:**

1. Модуль планировщика рядом с `millBuckets` (не раздувать `types.py`, не склеивать Rim/Front/Seam в `core.py`).
2. `discover_fronts` тонкий: walk leftover → `run_schedule` → sheer/finalize/C38.
3. `_seed_one` не копировать на очередь. Не второй пул. Не Occupancy v1. Не `OR` C39∨посадка∨бок в одном `is_seed`.

**Не делать:** вернуть три `_drain` по сетке; класть ведра на `ReliefVertices`; менять DAG/schema.

**Готово когда:** цикл `z_top` / enqueue / drain не в теле фасада; юниты discover + T-3c persist зелёные; Rim/Front/Seam по-прежнему отдельные стадии.

---

#### R41-T-21 — неявные контракты mill Q1/Q2

**Ось:** неявный контракт. **Status:** `resolved`. **P:** P2.

**Fix (2026-08-25):** выход `DiscoverResult` (`vertices`, `fronts`, `side_parent`, `mill: GradePipelineTimings`). `BucketRef` = семья + z + bake slot (`UNSET_SLOT`). `MillOrigin` вместо `kind=None`. Live corridor — `LiveCorridors` / `CorridorLive`. «Непокрытый сосед следа» в ТЗ = `is_side_seed`. `VertexSlotSeam.side_parent_slot` только у покрашенных слотов. `from_mill(dict)` снят.

**SoT:** § Две очереди seed — ключи leftover `(z, unset)` / claimed `(z, uid)` / Q2 `(z_q1, uid)`; клетка ∈ одно ведро; предикаты раздельно; третий вид Q2 = «непокрытый сосед следа».

**Факт — таблица контрактов, которых нет в типе:**

| Контракт | Как живёт в коде | Слом |
|---|---|---|
| Отчёт mill | `ReliefVertices.mill_stage_s: dict[str, float]` | `GradePipelineTimings.from_mill` / `detailedGradeDiscover` / `_PIPELINE_KEYS` в `detailed_bake.py` читают те же строки. Нет ключа → `0.0`. Пустой `plugins` отдаёт другой набор (`mill_setup_s`/`mill_s` only) |
| Ключ ведра | `BucketKey = tuple[int, int]` = `(z, uid)` | claimed Q1 и Q2 могут быть одним кортежем `(z_top, slot)`. Различает только строка `FAMILY_Q1`/`FAMILY_Q2` (**T-22**). `move` не в ту семью typecheck не ловит |
| `uid` в ключе | 1-based **slot** `ReliefVertices`, не SQL uid (`uids` пустые до T-3c) | SoT «bake-uid = слот» нигде не названо у `move(..., (z, slot))` |
| `q2_kind: str \| None` | `None` = mill leftover Q1; `"side"` пишет `side_parent`; `"landing"` не пишет | булев «это Q2» спрятан в optional string |
| Виды Q2 | drain: `if kind == LANDING: … else: is_side_seed` | `else` считает видов ровно два. Третий TZ-вид («непокрытый сосед следа») молча не существует: enqueue только посадка с тела + бок с коридора |
| Живой коридор | `occ` на `\|dz\|=1` — на finalize; apron берёт `in_slope_trace` / `corridor_slot` | «коридор = occ ∨ live trace» = optional callback из closures **T-20**. Забыл callback → бок на отложенном `occ` не сеется |
| Срез фронтов mill | `fronts[n_fronts:]` после `_seed_one` | «новые фронты этого seed» = append в тот же list. Побочный append ломает enqueue |
| Двойной фильтр Q2 | enqueue проверяет предикат; drain проверяет снова и `discard`; `is_side_seed` внутри зовёт `is_q2_seed` и `seed_rim` | «не OR» закодирован трижды. Расхождение enqueue vs drain vs apron → дыра или вечный discard |
| Attach → System | `build_vertex_slot_seams` идёт по `painted_uids`; `side_parent` на непокрашенном слоте в `VertexSlotSeam` не попадает | fingerprint молчит; UF в `gradeVertexSystem` не видит child (было так у `q3_parent`, контракт не записан) |

**Почему баг:** канон ТЗ есть; wire mill — словари и кортежи. Смена ключа timings или третьего вида Q2 не ломает typecheck. Третий вид Q2 в SoT vs два предиката в `apron.py` — либо дыра покрытия, либо недописанный SoT.

**Target:**

1. Выход discover — `GradePipelineTimings` (или поле этого типа), не `dict[str, float]`. `from_mill` не парсит свободные ключи.
2. Named bucket ref: семья + `(z, uid)` в одном типе; `uid` слота явно (не «просто int»).
3. Q2 kind — enum/`Literal` закрытый; mill Q1 не через `kind=None`.
4. Третий вид Q2: **либо** отдельный kind + предикат + enqueue с соседей следа, **либо** одна строка в [`tz_terrain_relief.md`](./tz_terrain_relief.md) § Две очереди, что «непокрытый сосед следа» = `is_side_seed` (same-z бок коридора). Не оставлять висящим.
5. Live corridor: один объект/метод «клетка коридора SLOPE сейчас», не пара optional callback.
6. Docstring/`VertexSlotSeam`: attach в fingerprint только если слот покрасился; это не снятие бок-attach.

**Не делать:** третий **очередь** seed; снять бок-attach; `0002_*.sql`; Occupancy v1; OR всех предикатов в одном drain.

**Готово когда:** timings без параллельного dict; ключ ведра не голый `(int,int)` + строка сбоку; третий вид Q2 закрыт (код или ТЗ); live corridor не optional «если передали».

---

#### R41-T-22 — хардкоды mill (family / kind / timings keys)

**Ось:** хардкод. **Status:** `resolved`. **P:** P2.

**Fix (2026-08-25):** `MillFamily` / `Q2Kind` / `Q2_DRAIN_ORDER`; `UNSET_SLOT`; `GradePipelineTimings.wire_keys()` + bake-only `grade_persist_s`/`l2_s`; `mill_log_fields` = `as_dict` минус `grade_s`/`materialize_s`; `log_name` / `walks` сняты; `enclosed_one_cell_pit` сравнивает `FREE_MARK`.

**Факт:**

| Литерал | Где | Риск |
|---|---|---|
| `"q1"` / `"q2"` | `millBuckets.FAMILY_*`, сравнения в `insert`/`move`/`q2_for`/`max_leftover_z` | опечатка семьи не ловится |
| `"landing"` / `"side"` | `Q2_LANDING` / `Q2_SIDE`; `_Q2_KINDS` в `core.py`; `q2_kind ==` | порядок drain = кортеж строк в фасаде |
| `UNSET_UID = 0` | leftover key `(z, 0)` | 0 = «нет uid»; слот 0 не существует — знание локальное |
| `"q1_s"`, `"q2_s"`, `"mill_sheer_s"`, … | `core.py` запись `mill_stage_s`; `GradePipelineTimings.from_mill` / `mill_log_fields`; `detailed_bake._PIPELINE_KEYS` | четыре копии wire; забытый ключ = 0 |
| `log_name(z, uid) → f"{z}_{uid}"` | `millBuckets.py` | мёртвый код; SoT имя лога никто не зовёт |
| `MillBuckets.walks` | +1 в `fill_leftover` | счётчик для теста в продовом типе |
| `at_grid[ni] == 0` | `apron.enclosed_one_cell_pit` | рядом `FREE_MARK`; не новый в T-18, тот же модуль предиката |

`WHY_SIDE_ATTACH = "side_attach"` — именованная константа, **не** этот smell.

Алгоритмические `EIGHT_DELTAS` / 1-based slot — не хардкод политики.

**Почему баг:** контракт очередей и JSON mill — строки. Enum/`Literal` + один список полей timings убирают четвёртую копию.

**Target:** `enum` или `Literal` для семьи и Q2 kind; leftover unset не голый `0` без имени типа; `GradePipelineTimings` — единственный перечень ключей mill (script bake читает dataclass/`as_dict`, не свой `_PIPELINE_KEYS` mill-части). Удалить `log_name`, если лог не пишется; `walks` не публичный продовый счётчик (тест через один вызов `fill_leftover` / inspect, не поле).

**Не делать:** литералы knobs/`stamp_min_abs_dz` в mill; второй набор default’ов параллельно POJO.

**Готово когда:** grep mill `FAMILY_Q1 = "q1"` / `"landing"` вне enum нет; timings keys не копипаст в `detailed_bake` кроме чтения `as_dict`; мёртвый `log_name` снят или реально логирует.

---

#### R41-T-23 — смешение ответственности mill / vertices / apron

**Ось:** SRP / смешение. **Status:** `resolved`. **P:** P2.

**Fix (2026-08-25):** `ReliefVertices` без `side_parent` / `mill_stage_s`. `build_vertex_slot_seams(..., side_parent=)`. Leftover walk — `rim.iter_rect_z_cells`; buckets только insert/move. `is_side_seed` = геометрия; C39/посадка — `is_q2_side_event` в scheduler. Hydro `blocks_grade_seed` на посадке и на боку.

**Факт — кто что несёт после T-18/T-19:**

| Тип / модуль | Своя зона | Чужое |
|---|---|---|
| `discover_fronts` | фасад discover | расписание очередей + writer `side_parent` + CPU-отчёт + sheer/C38 (**T-20**) |
| `ReliefVertices` | слоты / `occ` / `seam` / facing / `members` | `side_parent` (bake-след fingerprint, persist-смысл) **и** `mill_stage_s` (телеметрия orchestrator’а). План T-18: ведра **не** сюда — соблюдено; persist/timings остались |
| `MillBuckets.fill_leftover` | индекс очередей | линейный walk `origin/width/height` + `surface.z`. Раньше walk был `RimStage.buckets_high_to_low`. Теперь rim не ходит, очередь знает сетку |
| `is_side_seed` | бок same-z SLOPE-коридора | исключает C39 (`seed_rim`) и посадку (`is_q2_seed`); hydro `blocks_grade_seed` есть здесь и **нет** в `is_q2_seed` |
| `GradePipelineTimings` | typed CPU-sum | заполняется **после** парсинга dict с `vertices`, не на выходе mill |

**Почему баг:** индекс геометрии — не очередь, не JSON mill, не fingerprint T-3c. Предикат бока — не арбитр «какая очередь выиграла». Walk heightmap — не метод множества вёдер (один раз — да; владелец walk — вопрос границы).

**Target:**

1. `side_parent` не поле `ReliefVertices`: рядом с fingerprint (уже есть `VertexSlotSeam.side_parent_slot`) или узкий mill-out объект, который `build_vertex_slot_seams` читает явно.
2. Timings не на `vertices`: возврат/поле оркестратора, `from_mill(dict)` снять (**T-21**).
3. Walk leftover: либо `RimStage`/helper «клетки rect с z», `MillBuckets` только `insert`; либо явно задокументировать, что buckets — ещё и один walk (сейчас молча).
4. `is_side_seed`: геометрия бока; «не C39 / не посадка» — у планировщика при enqueue (предикаты раздельно, не вложенный вызов чужой очереди). Hydro block — один канон для посадки и бока, не асимметрия.

**Не делать:** ведра обратно на `ReliefVertices`; склеивать Rim/Front/Seam; снять бок-attach persist; колонка SQL parent.

**Готово когда:** grep `ReliefVertices.side_parent` / `mill_stage_s` пуст или поле только geometry; `is_side_seed` не вызывает `is_q2_seed`/`seed_rim`; walk сетки не спрятан как побочный смысл очереди.

---

#### R41-T-24 — `z_at` → `z_height_map`

**Ось:** naming. **Status:** `resolved`. **P:** P3.

**Fix (2026-08-25):** канон `z_height_map` — метод `ReliefSurface` / `MeterGradeSurface`, Mapping в `gradeCellRays` / `unified_surface_facings` / persist, Callable `iter_body_eight_views` / `measure_terrain_descent`, alias `ZHeightMap`. Consume: «нет в `z_height_map`». `ParentLightTile.surface_z_at` и city `terrain_z_at` не трогали. Поведение omit / R44 / T-17 без изменений.

**Почему баг:** `z_at` читалось как «высота этой клетки» или «z отсутствует». «Нет в карте» значит **нет ключа** в heightmap bake (край тайла / мира / дыра в гриде), не `z == 0`.

**Готово когда:** grep relief `z_at` (discover / validate / pack refine meter / `gradeRimRay` / тесты pack-лучей / consume) пуст; поведение то же.

---

#### R41-T-2 — C40: spec не единственный вход в L2

**Ось:** неявный контракт. **SoT:** [`tz_terrain_relief.md`](./tz_terrain_relief.md) **C40** — `GradePaintSpec` = единственное место bake-полей фронта и единственный вход в materialize.

**Факт:** `apply_grade_paint_spec(spec, *, world, surface, context, site_id, template_uid, terrain_key, system_terrain, dz, rim)`. Поля C40 на spec есть (`grade_uid`, `outward`, `front_w`, якоря, `decision`, `corridor`). Identity и геометрия для volume/canal/Instance живут **рядом**: `dz` для знака рампы, `rim` для `step_k` и `cell_refs` seeds, `terrain_*` / `site_id` / `context` для `RibbonSegment` + pick leftover.

Тип `DiscoveredFront` в `discover/types.py` как раз собирает spec + identity — **ни одного конструктора**, только re-export. Facade собирает те же поля вручную.

**Почему баг:** смена поля C40 не ломает typecheck apply; apply можно вызвать с `dz`/`rim`, расходящимися со spec.corridor / decision. C40 перестаёт быть контрактом.

**Target:** один объект на вход apply (`DiscoveredFront` или spec с недостающими C40-допустимыми полями, если ТЗ расширить). `apply_grade_paint_spec(front, world, surface)`. Не класть `occ`/slot на persist-POJO. Volume внутри не форкать.

**Fix (2026-08-17):** `apply_grade_paint_spec(front: DiscoveredFront, *, world, surface)`. Facade собирает `DiscoveredFront` после pick. `dz` / `rim` / `terrain_*` / `site_id` читаются с front, не семью kwargs. Volume/`GradeFormation` не форкали. Остаток DRY (`site_id` дважды) — **T-10**.

**Готово когда:** apply не принимает семи kwargs сверх spec/front; тесты paint/canal/fill зелёные.

---

#### R41-T-3 — pick спрятан в `cap_front`

**Ось:** неявный контракт + SRP.

**Факт:** `FrontStage.propose` зовёт `CapFront` — 6 позиционных аргументов без имён (`context, outward, first_dz, z_body, rim, trace`). Callback в `discover_and_paint` делает `pick_template` + `grade_constrained`, пишет `decided[(context, outward, rim)]`, возвращает `requested_length` (или `None` = выкинуть след до C41). Цикл paint: `packed = decided.get(...)`; нет ключа → **`continue` без лога**.

Ключ **не** содержит `slot` / `first_dz` / id следа. Два фронта с тем же `(context, outward, rim)` перезапишут pick. `pick_seq` крутится внутри walk, не в facade.

**Почему баг:** discover-пакет формально «без pick», фактически FrontStage зависит от world policy через дырку. Расхождение ключа = молча нет Instance. Truncate по `requested_length` меняет след **до** C41, поэтому pick влияет на шов лучей (занятость клеток), не только на L штампа.

**Target:** `CapFront` возвращает только max k (length), **без** pick. Pick + `grade_constrained` — в facade **после** `discover_fronts`, по `FrontGeometry`. Если нужен cap L до C41 — читать `L_tpl`/envelope **без** occurrence_seq / round-robin. Не `warnings.warn` на bake.

**Fix (2026-08-17):** `CapFront = Callable[[ReliefContext], int | None]`. Occupancy cap = **L_tpl** (`occupancy_length_cap` / `length_cap_for_context`). Envelope floor остаётся **halo** (`grade_halo_cells`): k=20 до C41 на L-месе делает все клетки швом. Pick + `grade_constrained` в `discover_and_paint` после фронтов; skip пишет `relief_debug("grade_front_skip", …)`. Нет `decided`. `fronts.py` не импортирует pick.

**Готово когда:** `fronts.py` не импортирует и не вызывает pick; нет словаря `decided`; нет silent skip по промаху ключа.

---

#### R41-T-4 — `RavinePlugin.flood_member` шире `claims`

**Ось:** SRP plugin тела. **SoT:** R41 таблица — тело ravine = берег; стрельба в маску. Не полный same-z CC суши.

**Факт:**
- `claims`: клетка не маска и не дорога **и** есть 8-сосед ниже с `terrain == ravine`.
- `flood_member`: любая клетка `terrain != ravine && != road` (та же z проверяется в `RimStage.flood`).

8-flood с берега забирает **всю** равнину той же z (меса open_land), если она 8-связана с берегом. Приоритет plugin: ravine раньше open_land → меса не сеет как `open_land`.

**Почему баг:** слой 5 «толстый ravine» на этом не построится — придётся лечить `if` в ядре. Уже сейчас низина крадёт open_land Grade. `claims` узкий, `flood` широкий — контракт plugin врёт.

**Target:** `flood_member` согласован с `claims`: берег у маски (и, если нужно, узкая полоса банка), **не** вся суша. Юнит: плато plains той же z рядом с ямой остаётся `OpenLandPlugin`. Не полный CC тайла. Не Priority-Flood пола ямы.

**Fix (2026-08-17):** `RavinePlugin.flood_member` для **банка** = `_is_bank` (не вся суша). `OpenLandPlugin(..., ravine_key=)` не claims/flood клетки с нижним соседом-ravine, когда ravine в наборе plugin (`plugins_for_keys`). Иначе open_land сеет с западной кромки и 8-flood забирает берег раньше, чем ravine. Тест `test_ravine_bank_does_not_swallow_mesa`.

**Слой 5 (тот же день):** flood маски = same-z terrace (интерьер в теле, не сеет). `claims` маски = клетка ravine с соседом ниже (стены). Пол без Δz не site. Kind (SLOPE/SHEER) — knobs шаблона, не plugin. Тесты `test_ravine_thick_inner_wall_seeds_after_bank_cap`, `test_ravine_floor_without_drop_does_not_seed`. Не Priority-Flood пола. Не `if context` в `core.py`.

**Готово когда:** тест «меса + ravine mask» — два слота / два контекста; flood ravine не содержит внутренность плато.

---

#### R41-T-5 — стоп луча `z >` против ТЗ `z ≥`

**Ось:** неявный контракт / расхождение SoT.

**ТЗ** ([`tz_terrain_relief.md`](./tz_terrain_relief.md) R37 ray): стоп если клетка отсутствует, **`z ≥ z_peak` или `z ≥ z_prev`**, упор, смена θ.

**Код** (`FrontStage._walk_trace`): стоп при `z > z_body` и при `z > zp` (k>1). **Равная** z не стопит — плоский пол идёт в lockstep как объём L.

Это сознательный фикс (пол L=2 рампы / ravine), в ТЗ не зафиксирован.

**Target:** выбрать одно. Если равная z = продолжение коридора — поправить формулировку луча в ТЗ (не «открыть чашу `|dz|=1`»). Если SoT `≥` побеждает — вернуть стоп на равенстве и починить тесты рампы иначе (не широким flood). Не Priority-Flood.

**Fix (2026-08-17):** ТЗ приведён к коду. Live lockstep стопит на **подъёме** `z > z_body` / `z > z_prev`. `|dz|=1` stamp — T-7 (позже plains = 1). Deprecated `measure_terrain_descent` оставляет `≥`. Не Priority-Flood. Не чаша на единице.

**Остаток (2026-08-19):** равная z больше не везде L (open_land стоп). Яма по-прежнему `if RAVINE` — **T-13**.

**Готово когда:** ТЗ и `_walk_trace` не расходятся по стопу подъёма.

---

#### R41-T-6 — inherit uid орто, discover 8-way

**Ось:** неявный контракт.

**Факт:** discover ходит `EIGHT_DELTAS` (R41). `inherit_segment_uid` смотрит seed + **`CARDINAL_ORTHO_DELTAS`**. Диагональный сосед с уже выданным uid не наследуется (`len(found) != 1` → mint).

**Почему баг:** шов чанка по диагональной клетке / NE-фронт может получить второй uid при том же каталожном `face_key` или наоборот не подхватить catalog uid с диагонали.

**Target:** тот же neighbor set, что discover (`EIGHT_DELTAS`), **или** явная запись в ТЗ «inherit только орто (C29 ребро чанка орто)». Не first-lock-wins внутри вершины (C41).

**Fix (2026-08-17):** канон **только орто**. Discover остаётся 8-way. Inherit по `CARDINAL_ORTHO_DELTAS`: C29 ребро чанка орто; диагональный сосед с uid — другой фронт (C15: 1 outward = 1 Instance) или угол чанка. 8-way inherit склеивал два outwards L-месы в один uid (`test_two_outwards_stay_two_instances`). Тест: орто наследует, диагональ — нет.

**Готово когда:** два outwards = два Instance; диагональный uid не наследуется; ТЗ UID это пишет.

---

#### R41-T-7 — R37 `|dz|=1` не на envelope

**Ось:** dataModel.

**SoT R37:** plains/forest `open_land` — stamp `|dz|=1` нет. Envelope (`ReliefTerrainEnvelope`) этого поля **не** имеет: есть `slope_length_min_cells`, `sheer_min_abs_dz`, `apply_in_contexts`.

**Факт:** `OpenLandPlugin.allows_unit_stamp() → False`; `FrontStage` skip при `abs(first_dz)==1`. Road/ravine/shore → `True`. Смена канона envelope не сдвинет skip.

**Target:** политика на POJO (новое поле envelope **или** skip через `grade_constrained`/knobs, если это уже следует из cases `delta_z`). Plugin не дублирует литерал `1`. Не открывать продукт «чаша на единице».

**Fix (2026-08-17):** `ReliefTerrainEnvelope.stamp_min_abs_dz` (plains/forest = 2, default 1). `FrontStage` читает `stamps_first_step` + `apply_in_contexts`; `allows_unit_stamp` снят с plugin. `grade_constrained` не skip на `h=1` (юнит «gentle SLOPE without ray cap» живой). Канон plains остаётся 2. Не чаша на единице.

**Готово когда:** skip `|dz|=1` open_land без plugin boolean; road/ravine unit stamp; override stamp_min=1 сеет (wiring).

---

#### R41-T-8 — три длины луча

**Ось:** неявный контракт.

1. `path_length` в `cap_front` — max k **полного** walk (до truncate), до C41.
2. `decision.requested_length` — cap k; `truncate_trace` до seam/occ.
3. `L_eff` в paint — max k **коридора** после C41 prefix (дырка W не режет Instance, но короче след).

Classify/`dz` pick смотрят дальний конец полного следа; штамп — усечённый коридор. SHEER L=1 на длинном обрыве может классифицироваться по полному Δz и красить одну клетку.

**Target:** задокументировать канон (classify по полному downhill до упора; stamp по `min(L_tpl, corridor)`) **или** считать `dz`/`path_length` после truncate и после C41, одним местом. Не два fill.

**Fix (2026-08-17):** один канон — коридор после C41. `SeamStage` ставит `FrontGeometry.path_length` = `max_outward_k(corridor)` и `z_end` на клетке этого k. Facade classify и paint `L_eff` читают этот span. Occupancy cap до C41 = L_tpl; halo = envelope floor. Clearance R36m может ещё укоротить stamp (L2). Не новый `plan_ribbon_volume`. Тест `test_classify_span_is_corridor_after_seam`.

**Готово когда:** `h`/`L_ray` не с дальнего конца полного следа сквозь шов; paint L_eff = тот же max k.

---

#### R41-T-9 — `discover_and_paint` три роли

**Ось:** SRP. Связан с T-2 / T-3, не отдельный пайплайн.

**Факт:** один модуль/функция: plugins+blocked, `cap_front` pick, `discover_fronts`, mint/inherit/catalog uid, сбор spec, paint, clip, merge uid bag. ~300 строк. Стадии discover тонкие; жир уехал в pack-facade.

**Target:** оркестратор вызывает (1) discover (2) pick/decision на `FrontGeometry` (3) uid (4) `apply_grade_paint_spec`. Не второй пул, не новый FineChunkRunner.

**Fix (2026-08-18):** `discover_and_paint` — оркестратор. (2) `pick_front_grade` (3) `uid_for_front` (4) `apply_grade_paint_spec`. Сигнатура для `compute_rect` та же. `fronts.py` без pick (T-3). Не второй пул, не новый FineChunkRunner.

**Готово когда:** pick+uid+paint не одним телом; `compute_rect` / generate / T-3c тесты зелёные.

---

#### R41-T-10…T-12 — low

| ID | Суть | Target |
|---|---|---|
| **T-10** | `terrain_key` / `site_id` helpers в facade; `DiscoveredFront` живой (T-2) | один builder; остаток DRY |
| **T-11** | `_TRACE_CAP = 64` не из `slope_length_max_cells`; `site_id = f"{context}\|x,y\|{facing}"` не `PackJobUid`; `RibbonSegment.owner_uid = context.value` | cap ≤ envelope/knobs; site compose из POJO; owner = реальный owner или omit |
| **T-12** | `FineTileContext.planned` ✅ слой 7; `Coord = tuple[int,int]` в types / meter / catalog / halo | не плодить alias |

**Fix (2026-08-18):**
- **T-10:** `front_bake_identity` / `discovered_front_from` — один builder. Paint читает поля front, не считает `terrain_key`/`site_id` снова.
- **T-11:** `ReliefTerrainEnvelope.slope_walk_cap_cells`; walk = min(envelope max, occupancy knobs); omit max + нет knobs → до конца heightmap. `PackJobUid.grade_front_site` / `front_grade_site`. `RibbonSegment.owner_uid` = реальный owner или omit (не `context.value`). Нет нового hash-домена / `PackJobSiteKind`.
- **T-12:** `planned` срезан слой 7. Новые модули identity/pick/uid **не** объявляют `Coord = tuple[int,int]`. Alias в types / meter / catalog / halo не склеивали (не нужно для T-9).

**Готово когда:** site_id = compose POJO; owner не токен контекста; `_TRACE_CAP` нет; новые модули без Coord alias.

**Info, не отдельный ID:** `generate_detailed_grade` копит `existing_uids` по rect подряд; `FineChunkRunner` pool этого не делает (catalog + pack inherit). Разница caller’ов — SoT пула верный; тесты фасада строже live bake.

---

#### R41-T-13 — равная z ямы не на envelope

**Ось:** dataModel / хардкод. **Status:** `resolved`. **P:** P2.

**SoT:** [`tz_terrain_relief.md`](./tz_terrain_relief.md) R41-T-5 / C34 — равная z продолжает L только ravine и берег с `grades_channel_bed`. Open_land / обочина стопят при `z == z_prev` (k>1).

**Факт (было):** `FrontStage._continue_equal_z`: `if plugin.context is ReliefContext.RAVINE`. Канон ravine — пустой envelope, `grades_channel_bed=False`.

**Fix (2026-08-25):** ravine `_ravine_canonical()` = `grades_channel_bed=True`. Walk = `bool(env.grades_channel_bed)`. `is_unconstrained` не включает walk-флаг (geom pass-through). Override `False` стопит equal-z. `fronts.py` без `ReliefContext`.

**Почему баг:** два источника политики. Shore читает POJO; яма — литерал контекста в discover. `dataModel-no-hardcode`: правило класса земли должно жить на envelope.

**Target:** поле на `ReliefTerrainEnvelope` (или явно `grades_channel_bed=True` на ravine **если** это тот же смысл и `is_unconstrained` согласован). `FrontStage` только читает envelope. Не `if context` в walk. Не Priority-Flood. Не Occupancy v1.

**Готово когда:** юнит ямы продолжает пол при override envelope `False`; open_land без поля не ходит по низине; `fronts.py` без `ReliefContext.RAVINE` в equal-z.

---

#### R41-T-14 — один `seam[]` на два смысла C41

**Ось:** неявный контракт. **Status:** `resolved`. **P:** P3.

**Факт:** `SeamStage` считает same-facing overlap и multi-facing shared anchor отдельно, пишет оба в `vertices.seam`. Occupancy = клетка ∈ ≥2 следов (как до ключа Facing). C39 не сеет с `seam≠0` в обоих случаях.

**Почему smell:** ТЗ различает шерсть и якорь низины; массив один. Debug/ASCII/`is_seed` не отличить. Пока C39 одинаков — не блокер.

**Fix (2026-08-25):** один `seam[]` locked. Docstring `ReliefVertices` / `SeamStage` + C41 в ТЗ: шерсть и якорь низа — один флаг; C39 не сеет оба. Два поля — later.

---

#### R41-T-15 — L=1 stamp vs якорь низа R36t

**Ось:** неявный контракт / R36t. **Status:** `resolved`. **P:** P2.

**Факт:** одиночный `4→3` (L=1) кладёт нижнюю клетку в коридор и `occ` (`test_canonical_plains_stamps_unit_open_land`). R36t: не мутировать верхнюю и нижнюю точку перепада. Дырка `4` вокруг одной `3` — skip (пустой коридор после шва) — **locked SoT**, не этот ID. Смешанное кольцо `6/4/3` вокруг `2` — **C41 finalize** (яма шов, не `occ` пика); не этот ID.

**Почему smell:** stamp одиночного L=1 и формулировка якорей расходятся. Чаша 1×1 не красится; изолированное ребро красится на «якоре низа».

**Fix (2026-08-25):** TZ R36t exception: L=1 corridor = первая downhill; stamp uid на неё разрешён. Дырка 1×1 / кольцо на общую `3` — C41 skip, не этот exception. Верхняя кромка без uid (C11). Юнит `test_canonical_plains_stamps_unit_open_land` остаётся.

---

#### R41-T-16 — `slope_fits` vs `L_min`

**Ось:** неявный контракт. **Status:** `resolved`. **P:** P3.

**Факт:** `slope_fits` — только θ-band (`L_min` не veto). `slope_length_for` поднимает L до `max(L_tpl, ceil(h/tan θmax), L_min)`. `grade_constrained` без `path_length` на plains `dz=1` запрашивает L=20. Discover после стопа равной z даёт короткий луч — live bake спасает cap.

**Почему smell:** unit без ray cap и bake с cap — разное L на том же envelope. Call site легко вызвать inner без `path_length`.

**Fix (2026-08-25):** docstring `slope_length_for` / `grade_constrained`: classify без луча ≠ stamp. Stamp (`ribbonGrade`, `detailedGradeFrontPick`) передаёт `path_length`. Unit без cap документирует L=20. `slope_fits` остаётся θ-only (`plains.slope_fits(1, 1)`).

---

### R36i-T — GradeFormation apply — post-impl smells

**Контекст:** 2026-08-15 — ревью apply по осям: god-object · хардкоды · dataModel · смешанная ответственность · DRY. **Не** переоткрывать R36i-T-1 (z+canal+fill работают). **Не** Wave E.

**Не долг (сделано правильно):** `resolve_seed_canal` / `project_canal_draw` / поля `ReliefGradeInstance`; `worldRow` `canal_templates` / `relief_pick_policy` / `terrain_masks`; `CARDINAL_ORTHO_DELTAS`; barrier keys с `WorldTerrainRegistry`; shared heightmap не мутировать; `n_eff` не пересчитывать. Overlay z **не** колонка `worlds` (pack write-set). `ReliefGradeInstance.facing: str` — locked POJO (не «нет dataModel»).

| ID | Severity | Status | P | Ось | Smell | Target |
|---|---|---|---|---|---|---|
| **R36i-T-4** | **high** | **resolved** | P1 | неявный контракт / dataModel | Write-set разрезан: `GradeFormation` сразу unpack в `commit_segment`; overlay — соседний `dict`; `materialize_segment_meter` → `tuple[list, dict]` вместо `DetailedGradeResult`; entity `h/L/θ` = **`last.plan`**, overlay z = **все** seed plans | **Fix:** `GradeFormation` несёт overlay; `to_write_set`; materialize → `DetailedGradeResult`; entity plan = max `plan.L` (first on tie) |
| **R36i-T-5** | medium | **resolved** | P2 | SRP / god | `corridor_for_seed` = anchors + clearance + volume + canal + wrote + R36t cut + facing | **Fix:** `volume_corridor_for_seed`; canal-cut отдельным шагом (`r36t_include_cut_end`) |
| **R36i-T-6** | medium | **resolved** | P2 | SRP | `MeterGradeSurface`: docstring read z, факт `stamp_grade` пишет uid. `commit_segment` = factory **и** stamp | **Fix:** `instance_for_formation` без stamp; `apply_grade_uids` из write-set в `materialize_planned_for_rect` |
| **R36i-T-7** | medium | **resolved** | P2 | DRY | `overlay.update` / `uids.update` last-wins vs `merge_grade_instances`; домен overlay=uid режется трижды | **Fix:** `DetailedGradeResult.merged_with` + `clipped_to_rect` |
| **R36i-T-8** | medium | **resolved** | P2 | хардкод / неявный контракт | `wrote[i]` ↔ `plan.columns[i]`; `include_cut = canal is not None and L_eff < requested`; `registry or canonical_defaults()` | **Fix:** `CorridorColumn` / `columns_for_plan`; `r36t_include_cut_end`; registry только `canal_templates(world)` |
| **R36i-T-9** | low | **resolved** | P3 | DRY | `Coord` копии в result/compute; nested rect heightmap; `_meter_outward_columns` | **Fix:** `Coord` из `meterGradeSurface`; `rect_contains` по parent keys; `outward_columns` |
| **R36i-T-10** | low | **resolved** | P3 | хардкод | `center_m=(ax+0.5, ay+0.5)`; пустой `MeterGradeSurface` в `resolve_segment_uid`; `int(plan.columns[i].surface_z)` | **Fix:** `cell_center_m`; inherit по uid bag без empty surface; z с колонки плана |
| **R36i-T-11** | low | **resolved** | P3 | god-module | `detailedGradeMaterialize.py` ~470 LOC | **Fix:** `detailedGradeCorridor` / `detailedGradeCanalCut` / write-set в `detailedGradeResult`; materialize — assemble |
| **R36i-T-12** | **high** | **resolved** | P1 | неявный контракт / R36j | `merged_with`: uid/z last-wins, instance first-wins + union refs; `clipped_to_rect` не режет `cell_refs`. Fill и persist смотрят разные срезы. In-memory first-wins ≠ SQL upsert last-wins | **Fix:** `reconciled()`; merge/clip/`to_write_set` заканчиваются им; `merge_grade_instances` last-wins поля. Не переоткрывать T-7 |
| **R36i-T-13** | medium | **resolved** | P2 | неявный контракт / SRP | Сырой ctor без сверки; `merged_with` union refs мёртв (reconcile переписывает); `h/L` vs `len(cell_refs)` не сказаны | **Fix:** `of()` всегда reconcile; merge = last-wins поля, состав из uid; docstring: h/L = formation, clip не жмёт L |
| **R36i-T-14** | low | **resolved** | P3 | неявный контракт | Drop orphan uid / uid без z без лога | **Fix:** `relief_debug("grade_write_set_reconcile")` |
| **R36i-T-15** | low | **resolved** | P3 | DRY / порядок | `cell_refs` sorted на write-set vs first-seen в merge; тройной overlay∩corridor; bag vs write-set на stamp | **Fix:** `merge_cell_refs` sorted; `to_write_set` → `of`; комментарий clearance bag ≠ clip |

**Fix order:** ~~T-4 → T-8 → T-5 / T-6 → T-7; T-9 / T-10 / T-11~~ ✅. ~~**T-12**~~ ✅. ~~**T-13…T-15**~~ ✅. **Не трогать:** Wave E; DAG; mask carry; voxel-ditch; BAR-1 (T-2). Graph stitch — ~~T-3b~~ ✅. System — ~~**T-3c**~~ ✅ (не этот apply).

**Agent pointer:** [`.cursor/plans/detailed-grade-volume-canal.md`](../.cursor/plans/detailed-grade-volume-canal.md); SoT [`tz_terrain_relief.md`](./tz_terrain_relief.md) § Post-R36w.

### R36i-T-12 — write-set reconcile — shipped

**Продукт:** [`tz_terrain_relief.md`](./tz_terrain_relief.md) **R36j / C11**. **Код ✅ 2026-08-15.** `DetailedGradeResult.reconciled()`; `merged_with` / `clipped_to_rect` / `to_write_set` заканчиваются им; `merge_grade_instances` last-wins поля + union refs.

**Запрещённый «вариант B»:** instance чанка держит полный коридор, колонки соседа «догонят». Висячие `cell_refs` без uid, если сосед ленту не материализует.

#### Целевое состояние

Домен **uid — единственный состав Grade** на данном write-set. Overlay и `cell_refs` из него. Полный объект на шове чанков/тайлов собирает **persist**, не один `ColumnRect`.

После любого merge и любого clip, до fill/persist:

1. `keys(surface_z) == keys(surface_grade_uid)`
2. клетка `xy` с uid `g` ∈ `cell_refs` **только** instance `g`
3. у instance нет клеток вне uid-домена и нет клеток, где uid другой
4. instance без клеток — нет в результате (POJO `cell_refs` min_length=1)
5. поля сущности (`kind`, `h`, `L`, `θ`, canal, facing) — **last-wins** по uid — тот же канон, что SQL upsert

Внутри **одного** `GradeFormation` канон `h/L/θ` по-прежнему max `plan.L` (T-4). Между сегментами/чанками — last writer.

`apply_grade_uids` на полный коридор (в т.ч. за rect) — **локальный bag** для clearance. Не источник `cell_refs`.

| Слой | Состав |
|---|---|
| `ColumnRect` write-set | только клетки, которые этот rect поставил в uid |
| SQL после upsert | union `cell_refs` writer с тем же catalog uid |

#### Контракт `reconcile`

Один метод на `DetailedGradeResult` (не второй filter в clip и не третий merge). `merged_with` и `clipped_to_rect` **заканчиваются** им.

```text
uid, z     → last-wins; clip: оставить xy ∈ rect, overlay ∩ эти ключи
instances  → last-wins поля по uid (поздний instance затирает поля)
reconcile  → cell_refs(g) := [xy | uid[xy] == g]  (стабильный порядок: сортировка xy)
             нет клеток → выкинуть instance
             uid g без instance → выкинуть эти uid и их z (дырявый stamp)
```

Конфликт двух uid на одной клетке закрывается last uid на карте; reconcile забирает клетку у проигравшего. Отдельный «вычеркни из g1» не нужен.

`to_write_set` уже согласован; для защиты тоже может звать `reconcile` (идемпотентно).

#### Слои имплементации (не слайс «сначала только clip»)

1. **`DetailedGradeResult.reconciled()`** — единственная сверка; без побочных stamp на `MeterGradeSurface`.
2. **`merged_with` / `clipped_to_rect`** — карты как сейчас (last-wins / rect), затем `reconciled()`. Clip **не** копирует `grade_instances` as-is.
3. **`merge_grade_instances`** — last-wins поля + union `cell_refs` (сейчас first-wins). Call sites только write-set acc: `detailedGradeResult`, `FineChunkPersist`. Согласовать с `apply_prior_cell_refs` (входящий = last). **Не** менять сигнатуру persist SQL.
4. **Тесты** в `test_detailed_grade_generate.py`:
   - clip: `cell_refs` ⊆ uid-домен rect; instance без клеток в rect исчезает;
   - два uid на одной клетке: last uid, проигравший без этой клетки;
   - тот же uid: last canal/θ, union клеток, затем reconcile по uid-карте;
   - `reconcile` идемпотентен;
   - ramp/canal/fill регрессия T-1 не ломается.
5. **Не** трогать: `persistReliefGrades` (уже last fields + union); voxel-ditch; DAG; mask carry; `n_eff`; shared heightmap; T-2/T-3.

**Не в T-12:** last z vs max-`L` при перекрытии семян **внутри** сегмента (T-4 канон плана).

**Готово когда:** любой `DetailedGradeResult` после merge/clip удовлетворяет пунктам 1–5; `merge_grade_instances` last-wins; тесты выше зелёные.

---

## Pack ASCII / L2 grade carry — post-impl smells (PAR-T)

**Контекст:** 2026-08-12 — L2 location grade ASCII shipped ([`tz_pack_ascii_render.md`](./tz_pack_ascii_render.md) **PAR-G7…G10**; plan `grade-detailed-location-render`). Ревью: неявные контракты · dataModel · хардкоды · SRP.

| ID | Severity | Status | P | Ось | Smell | Target |
|---|---|---|---|---|---|---|
| **PAR-T-1** | **high** | **resolved** | P1 | неявный контракт | facing majority ≠ uid surface | **Fix:** `_column_surface_attrs` — facing+uid surface-only (PAR-G9); majority removed |
| **PAR-T-2** | medium | **resolved** | P2 | dataModel / POJO | `terrain_resample` overload | **Fix:** `categorical_resample`; legacy `terrain_resample` migrate + property alias |
| **PAR-T-3** | medium | **resolved** | P2 | DRY / хардкод | тройной upsample + `"nearest"` | **Fix:** `_upsample_optional_str` + `_require_categorical_nearest` |
| **PAR-T-4** | medium | **resolved** | P2 | dataModel | `system_facing` as `str` on pack wire | **Fix:** `Facing \| None` on `WorldMapCellWire` / `FineTerrainColumnWire` / `LightGridCell`; `coerce_facing_wire`; upsample → `Facing`; MapCell SQL still `str` via `.value` |
| **PAR-T-5** | medium | **resolved** | P2 | хардкод / wire keys | `LEVEL_*` dup in `render_maps` | **Fix:** import `renderPayloads.LEVEL_*`; `_WILDERNESS_BUNDLE_LEVELS` |
| **PAR-T-6** | low | **resolved** | P3 | ответственность | grade legend in ASCII body + dump | **Fix:** body = grid only; dump uses `render_grade_legend()` for `LEVEL_GRADE` |
| **PAR-T-7** | low | **resolved** | P3 | SRP / typing | `TileSurfaceState` `object` bag | **Fix:** typed `SurfaceHeightmap` + `n_eff` + hydro dict |
| **PAR-T-8** | low | **resolved** | P3 | SRP | columnFill facing+grade inline | **Fix:** `_surface_carry_attrs` helper |

**Related (info, не отдельные ID пока):** dangling `system_grade_uid` без проверки SQL Instance; `grade_symbol` невалидный facing → silent sheer; legacy blob omit без schema version bump.

**Fix order (рекомендация):** ~~T-1 → T-3 → T-2 → T-5 → T-6; T-7/T-8~~ ✅; ~~**T-4**~~ ✅ (Facing pack wire, 2026-08-12).

**Agent pointer:** [`.cursor/plans/grade-detailed-location-render.md`](../.cursor/plans/grade-detailed-location-render.md); SoT [`tz_pack_ascii_render.md`](./tz_pack_ascii_render.md).

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
| 2026-08-25 | **R41-T-17 ✅:** leftover + COUPLE; first-wins; валидатор не invent из z. **T-18/T-19 ✅** mill Q1/Q2, нет `is_q3_seed`. **T-13 ✅** equal-z = envelope. **T-14** один `seam[]`. **T-15 ✅** L=1 TZ exception. **T-16** θ vs L_min в docstring |
| 2026-08-25 | **R41-T-20…T-23 ✅:** `millSchedule`; `DiscoverResult`; `BucketRef`/`MillFamily`/`Q2Kind`; `LiveCorridors`; timings без `from_mill`; leftover walk на rim; `is_side_seed` геометрия. T-18/T-19 ✅; T-13…T-16 ✅ |
| 2026-08-25 | **R41-T-19 open P1 третьим:** снос mill Q3 (`is_q3_seed`, `q3_s`, `q3_parent`); бок-attach persist оставить; rename bake-полей. После T-18 |
| 2026-08-25 | **R41-T-18 SoT:** вёдра Q1 leftover/claimed + Q2 `(z_q1, uid)`; один walk сетки; `z_top` = один leftover z; луч до упора; без отдельного clear очереди. После T-17 |
| 2026-08-25 | **T-17 уточнение:** dump `+` на same-z = smoke generate, не задача ASCII. Чинить persist COUPLE + валидатор не закрывать из z |
| 2026-08-25 | **R41-T-17 open P1 первым:** pack leftover-only vs 8 слотов + COUPLE (consume TZ / R41 C41). Валидатор invent закрытие из z. Чинить до T-13…T-16 |
| 2026-08-19 | **R41-T-13…T-16 open:** равная z ямы не на envelope (`if RAVINE`); один `seam[]` на шерсть+якорь; L=1 vs R36t; `slope_fits` vs L_min. T-5 остаток → T-13. Не Occupancy v1, не DAG |
| 2026-08-18 | **R41-T-9…T-12 ✅:** тонкий `discover_and_paint`; identity builder; walk cap envelope/knobs; site `PackJobUid`; owner omit; новые модули без `Coord` alias |
| 2026-08-18 | **Слой 7 срез v1 ✅:** sample/stitch/`planned` удалены. Next **R41-T-9…T-12** |
| 2026-08-18 | **T-3c слой 6 ✅:** `emit_relief_grade_systems` после merge; persist `systems`; intra-chunk = slot; C29 тело 8 + UF refine. Next слой 7 |
| 2026-08-18 | **T-3c шов locked** в [`tz_terrain_relief.md`](./tz_terrain_relief.md) § T-3c на шве чанков (catalog ≠ вершина; UF тайла; макро-шов двух bake — не слой 6) |
| 2026-08-18 | **ShorePlugin тело ✅** (банк + полоса; дно iff `grades_channel_bed`; terrace min с envelope). Next **T-3c**. Команда: [`.cursor/plans/relief-pipeline-v2.md`](../.cursor/plans/relief-pipeline-v2.md) |
| 2026-08-18 | **Shore онтология+paint ✅.** Команда агенту: [`.cursor/plans/relief-pipeline-v2.md`](../.cursor/plans/relief-pipeline-v2.md) |
| 2026-08-17 | **R41-T-5…T-8 resolved:** ТЗ `z >` (равная z = L); inherit только орто; `stamp_min_abs_dz`; classify/stamp = коридор после C41 |
| 2026-08-17 | **Очередь SoT в ТЗ:** [`tz_terrain_relief.md`](./tz_terrain_relief.md) § Осталось — v2 vs L2 volume (apply закрыт; ~~T-5…T-8~~ ✅ → слой 5) |
| 2026-08-17 | **R41-T-2…T-4 resolved:** apply=`DiscoveredFront`; occupancy cap = L_tpl (envelope = halo); ravine flood = bank, open_land не глотает берег |
| 2026-08-17 | **R41-T-2…T-12 open:** post-impl v2 (C40 spec≠L2-only; cap_front pick; ravine flood шире claims; walk `>` vs TZ `≥`; inherit 4 vs 8; R37 не на envelope; три L; fat facade; DRY/hardcode/leftover). SoT [`tz_terrain_relief.md`](./tz_terrain_relief.md) C40 |
| 2026-08-17 | **R41-T-1:** v1 sample/stitch/`planned` deprecated vs R41; impl [`.cursor/plans/relief-pipeline-v2.md`](../.cursor/plans/relief-pipeline-v2.md). T-3b occupancy не SoT; каталог `face_key` живой |
| 2026-08-15 | **C28 T-3b resolved:** `stitch_planned_segments`; sample до пула; rim-canonical. T-3c System later. SoT [`tz_terrain_relief.md`](./tz_terrain_relief.md) |
| 2026-08-15 | **C29:** шов технический (климат / дороги / шаг / локация·город); T-3b rim = механизм C29. SoT [`tz_terrain_relief.md`](./tz_terrain_relief.md) |
| 2026-08-15 | **C28 TZ lock:** topology → entity → stamp; T-3 split (T-3a omit / T-3b graph / T-3c System). SoT [`tz_terrain_relief.md`](./tz_terrain_relief.md) |
| 2026-08-15 | **R36i-T-13…T-15 resolved:** `of()`; merge без мёртвого union refs; h/L ≠ `len(cell_refs)`; debug drop; `merge_cell_refs` sorted; clearance bag комментарий |
| 2026-08-15 | **R36i-T-12 resolved:** `reconciled()` на write-set; clip режет `cell_refs`; `merge_grade_instances` last-wins поля как upsert |
| 2026-08-15 | **R36i-T-4…T-11 resolved:** write-set на `GradeFormation`/`DetailedGradeResult`; volume vs canal-cut; `apply_grade_uids`; `merged_with`+`clipped_to_rect`; `CorridorColumn`; `cell_center_m`; слои corridor/canalCut/result. T-2/T-3 remain |
| 2026-08-15 | **R36i-T-4…T-11 open:** GradeFormation post-impl (write-set split; corridor god; MeterGradeSurface/commit SRP; dual merge; wrote[i]↔columns / cut bool / registry or; Coord/rect DRY; 0.5 + empty surface; god-module). T-1 остаётся ✅ |
| 2026-08-14 | **R36i-T-1 resolved:** GradeFormation apply (z overlay + canal + uid); T-2/T-3 remain out of apply. План [`detailed-grade-volume-canal.md`](../.cursor/plans/detailed-grade-volume-canal.md) |
| 2026-08-14 | **FCR-T-1 resolved:** FineChunkRunner = `FineTileContext` + prep + `compute_rect` + persist; grade в ColumnRect worker |
| 2026-08-14 | **R36w edge test:** два bake смежных тайлов, семена на owner-грани → один uid (`test_two_tile_bakes_along_seam_one_uid`); bind: rim оси sample → грань оси; `< 2` chunk-родителей грани → void ≠ C18 |
| 2026-08-14 | **R36w TZ:** каталог граней + заранее uid (`world`+tile+`face_key`); T-1…T-3 open; SoT [`tz_terrain_relief.md`](./tz_terrain_relief.md) |
| 2026-08-13 | **R36v-T-8…T-13 resolved:** SampleCell NamedTuple; bag = rect cells; unique-neighbor inherit; Facing on corridor; `_plan_tile_grade`; `apply_prior_cell_refs` |
| 2026-08-13 | **R36v-T-1…T-7 resolved:** plan/materialize helpers; SeedCorridor split; `blocks_grade_seed`; ColumnBounds; merge_cell_refs; unique inherit; halo/origin/alias_heights |
| 2026-08-13 | **R36v-T-1…T-7 open:** post-impl ревью (god-method runner; materialize не разрезан; hydro литерал; duck-type rect; dual merge cell_refs; uid bag/inherit; хардкоды) |
| 2026-08-13 | **R36u-T-11 resolved:** FineChunkRunner pool sample → stitch → materialize+fill; late uid inherit |
| 2026-08-13 | **R36u-T-11 / R36v:** tile-wide serial grade → per-chunk pool + patch caller; TZ [`tz_terrain_relief.md`](./tz_terrain_relief.md) |
| 2026-08-13 | **R36u-T-9 residual:** `meter_grade_cell_blocked` (missing/graded/road/open-water/barrier) replaces `z is None` clearance adapter |
| 2026-08-13 | **R36u impl:** detailedGradeGenerate on FineChunkRunner; L0 grade contributors removed; grade carry stripped; L0 world-grade omit |
| 2026-08-13 | **R36u inventory:** legacy L0 grade paths A–F (compose writers, pure ribbon, PAR-G8 carry, world-grade ASCII, wire, tests) |
| 2026-08-12 | **PAR-T-4 resolved:** pack wire `system_facing: Facing \| None` (`WorldMapCellWire` / FineTerrain / LightGridCell); `coerce_facing_wire`; MapCell SQL remains str |
| 2026-08-13 | **R36u / C25:** grade writer = detailed_bake geometry; L0 без outdoor grade; PAR-G8 carry superseded — sync pack ASCII + debt |
| 2026-08-12 | **PAR-T-1…T-3,T-5…T-8 resolved:** surface-only facing+uid; `categorical_resample`; shared upsample; LEVEL_* from payloads; grade legend in dump only; typed TileSurfaceState; `_surface_carry_attrs`. **PAR-T-4** remains open |
| 2026-08-12 | **PAR-T-1…T-8 open:** post-impl L2 location grade ASCII (facing≠uid agg; `terrain_resample` overload; triple upsample; Facing-as-str; LEVEL_* dump dup; grade legend double; TileSurfaceState bag; columnFill fat). SoT [`tz_pack_ascii_render.md`](./tz_pack_ascii_render.md) |
| 2026-08-07 | **Grade `owner_uid`:** dataModel + `0001` + rows; drop FK to connection_edges; factory/persist/PaintedRoadEdge/`apply_road_shoulder_grades` aligned |
| 2026-08-07 | **Ribbon residual naming:** `RibbonIntent` / `RibbonGradeResult` / `grade_ribbon_segments` / `apply_ribbon_barriers`; Intent.`owner_uid` |
| 2026-08-07 | **Ribbon naming:** `RoadShoulderSegment`→`RibbonSegment`; `edge_uid`→`owner_uid` on segment; Intent/Grade `edge_uid` field still wire name (= owner value) |
| 2026-08-06 | **RELIEF-T-31/T-32 resolved:** `ribbonSegmentize`; `RoadShoulderContributor` + `painted_road_edges` after ROAD paint |
| 2026-08-06 | **Wave D polish:** `contextRibbonApply` / `ribbonSampleUtil`; `ribbon_intents` + `ref_cells`; BAR-1 once in `compose_light_grid`; road early-exit deduped |
| 2026-08-06 | **Wave D shipped:** open_land/shore contributors + `ribbonGradeApply`; compose hydro→open_land→shore→road |
| 2026-08-06 | **BAR-1 polish:** `paintBarrier` write-only; single `_may_place_fence`; terrain keys from registry; multi-ref = first material + union footprint |
| 2026-08-06 | **RELIEF-BAR-1 resolved (Wave C):** Intent refs → light `wall`; `ribbonFence` + `roadShoulderBarrierApply`; next Wave D |
| 2026-08-06 | **RELIEF-T-67 resolved:** `app.relief` in `generationLogging` allowlist → bake-light file gets relief/canal events |
| 2026-08-06 | **Wave B5 shipped:** T-65/T-63/T-62/T-61/T-59; T-66 deferred; Wave B complete → next C BAR-1 |
| 2026-08-06 | **Wave B4 shipped:** T-54 Intent omit=`None`; T-64 `SeedMaterializeSkip` + `skip_why` / `WHY_NOT_STAMPED` |
| 2026-08-06 | **B4 schedule locked:** B4a T-54 → B4b T-64 (same PR preferred; else next PR before B5/C; T-64 not deferrable to B5) |
| 2026-08-06 | **Post-B2/B3 SRP review → T-64…T-66:** false `clearance_skip`; double `empty_sample` log; EVENT монотокен; map → Wave B4/B5 |
| 2026-08-06 | **Wave B2/B3 — T-60/T-56 resolved:** `reliefEvents.py`; silent bake/grade paths → `relief_warning`/`relief_debug` |
| 2026-08-06 | **Wave B1 / Q6 shipped:** footprint-edge `sample_shoulder_cells`; apply drops `ordered_road_light` |
| 2026-08-06 | **Relief dev plan sync:** Wave A shipped; backlog → Wave B (Q6→T-60/T-56→T-54) → C BAR-1 → D consumers → E later; pointer `relief-dev-plan.md` |
| 2026-08-06 | **Post-split review → T-60…T-63 open:** silent bake logs; Intent/emit glue; `_ORTHO`≠Facing; `CanalDrawResult(False,…)` vs `EMPTY_DRAW`. T-56 loci уточнены |
| 2026-08-06 | **T-30/T-52 bake split shipped:** sample / materialize / stamp / intent + thin apply facade; god-orchestrator gone |
| 2026-08-06 | **T-30/T-52 split plan locked:** phases 0–5 (contracts → materialize_seed → stamp → sample → intent → thin apply); leave canal/grade helpers as-is |
| 2026-08-06 | **Canal kinds:** `EarthenCanal`\|`StructureCanal`; entry XOR; `draw_canal`/`build_canal`; Intent.`canal` — T-53 resolved |
| 2026-08-06 | **DRY canal single-writer:** T-55/T-57/T-58 resolved (`_resolve_canal_ref`, `EMPTY_EARTHEN_CUT`, `grade_fields`/`intent_fields`) |
| 2026-08-06 | **Post-fix smell → T-53…T-59:** Intent≠Grade `structure_canal`; skipped coerce; earthen literal; bake event strings; R21 DRY; alias/mapper. T-52 → medium (=T-30). Review canvas `canal-debt-fix-smell-review` |
| 2026-08-05 | **R36p/q fix wave T-43…T-51 resolved;** T-52 open |
| 2026-08-10 | **RELIEF-T-66 resolved:** `ribbon_skip_apply`/`_grade`/`_materialize` + closed why sets; drop monotoken |
| 2026-08-10 | **RELIEF-T-40 resolved:** `seededHash`; `RibbonGradeDecision.skipped_site`; `chosen_fallback` ← `ReliefSideKind.SLOPE.value` |
| 2026-08-10 | **RELIEF-T-38 / hybrid D:** `geom_resolve` honors explicit L=0; gradePass no wedge; bake clearance skip |
| 2026-08-10 | **RELIEF-T-38 resolved:** honor `slope_length_cells`/width 0 in `expand_shoulder_ring` (empty ring; no clamp to 1) |
| 2026-08-10 | **RELIEF-T-33/T-39 resolved:** shared `_interval_from_grade_knobs`; Mode A reads validated POJO (no silent or) |
| 2026-08-10 | **RELIEF-T-34 resolved (A flat):** Mode A compose via `mode_a_grade_knobs()` → `ReliefGradeKnobs`; wire unchanged |
| 2026-08-10 | **RELIEF-T-36 resolved:** `resolve_picked_template` shared lookup; R21 skip/fallback at callers |
| 2026-08-10 | **RELIEF-T-35 resolved:** `require_weights_pair` / `require_weights_sum` SoT in `reliefGradeKnobs` |
| 2026-08-09 | **Climate repair:** removed synthetic/`legacy_standalone` water; corrupt row → `repairWorldDefaults` (`normalize_world` + persist at batch/`WorldService`); empty `climate_zone_registry` wire → `[]` so facade merge materializes zones |
| 2026-08-07 | **RELIEF-T-29 resolved:** `worldSliceMerge`; runtime merge-id from POJO `RUNTIME_MERGE_ID_FIELD` (district/barrier) |
| 2026-08-07 | **RELIEF-T-28/T-37 resolved:** `resolve_registry_list/dict/json_blob_world` + thin `worldRow`; column keys from slices |
| 2026-08-02 | **JV-SCALARS-2 resolved:** `resolve_multi_column_world`; T-28 partial (multi_column) |
| 2026-08-02 | **JV-SCALARS-1 resolved:** `worldScalarWire` helper; climate/terrain/relief-obstacle thin wrappers |
| 2026-08-02 | **RELIEF-T-28…T-41:** SOLID+dataModel audit (god/SRP/DRY/wire keys/values); R36n obstacle POJO = clean win; backlog sync |
| 2026-07-31 | **R36** locked in TZ: SLOPE h/L/θ triangle; Geom-A\|B bake; backlog #1 = normalize POJO + materialize |
| 2026-07-30 | **BUNDLE-2 resolved:** handlers facade; library race/perk/building/relief; schema `race_templates`/`perk_templates`; HY-S-2 closed |
| 2026-07-30 | **BUNDLE-2 SoT:** [`tz_world_bundle.md`](./tz_world_bundle.md) WB-1…WB-10 + plan `bundle-2-section-handlers.md`; debt symptom sync |
| 2026-07-30 | **RELIEF-T-12 / T-16…T-27** fix wave: width bake, ImportResult, bake_seed, preload WARN, typed edge policy, knobs SoT, FS split, RoadShoulderIntent; T-26 accepted (wire letters) |
| 2026-07-30 | **RELIEF-T-16…T-27** + plan `relief-tech-debt-fixes.md`: re-audit (width dead, bundle HTTP/api, seed, knobs SoT, …) |
| 2026-07-30 | **RELIEF-T-7/T-9/T-14:** domain_root enforce; road_shoulder bake wire + intents; schedule hole → SLOPE; T-15 accepted |
| 2026-07-30 | **RELIEF-T polish:** T-1…T-6/T-8/T-10/T-11/T-13 resolved; BUNDLE-2 ReliefSection partial; T-7/T-9/T-12/T-14/T-15 open |
| 2026-07-30 | **BUNDLE-2** + **RELIEF-T-1…T-15:** post-impl audit (god-object/layers/dataModel); section handlers; R21≠Mode D; FastAPI в services; dual ReliefGradeDecision |
| 2026-07-30 | **RELIEF-BAR-1:** structure_refs stub (`system_type`); materialize deferred; link relief ↔ locations |
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
| 2026-07-19 | **WP-DELETE-1:** `DELETE /worlds/{uid}` FK/atomic gap → HTTP 500 / half-deleted world (smoke) |
| 2026-07 | **CONN-1 todo:** wire rename `node_type` → `connection_node_type` на `connection_nodes` (см. § CONN-1) |
| 2026-07 | **HY-BATH-1:** ocean Depression forms TZ; light R5b **stub** (`stub_drop_fraction_of_span`) shipped; Form pipeline open; TZ stub→target mapping |
| 2026-07 | **HY-5 progress:** structure/roads/climate enums → `dataModel`; shims removed; P1-A roads literals |
| 2026-06 | **HY-S registry:** BUNDLE-1, HY-5, HY-S-4, HY-GEO-1 |
| 2026-06 | **`docs/tz_json_validation.md` v0.1** — Field Contract Registry; ENUM-E / REF-W / N1-S / N1-W (§0) |
