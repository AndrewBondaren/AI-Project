---
name: "source-command-impl-hy-11"
description: "Имплементирует HY-11 (TOPO-1): домен dataModel/topology/ + unrolled-сервисы (dist2/nearest_on_segment/centroid), hydrology на WorldTopology — море через шов wrapped/sphere. По плану hy-11-topology-domain-geometry.md. Новый чат: /impl-hy-11."
---

# source-command-impl-hy-11

Use this skill when the user asks to run the migrated source command `impl-hy-11`.

## Command Template

# Имплементация: HY-11 — топология как домен геометрии

Это **явная просьба писать код** (шаги плана). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/hy-11-topology-domain-geometry.md`](../plans/hy-11-topology-domain-geometry.md) — **единственный SoT по шагам**: сервисы домена, unrolled-модель, шаги 1→2a→2b→3a→3b→4. Не отклоняться.
2. [`.cursor/plans/topo-1-domain-consumers.md`](../plans/topo-1-domain-consumers.md) — родительский трек: карта консьюмеров, запреты (per-domain обход wrap = баг).
3. [`docs/tz_terrain_generation.md`](../../docs/tz_terrain_generation.md) § Форма мира / `world_topology_mode` (`planar`/`wrapped`/`sphere`, `NeighborResult`, sphere fold `w/2` + `invert_dy`). Шаг 1 — правка этого файла.
4. [`docs/tz_terrain_hydrology.md`](../../docs/tz_terrain_hydrology.md) § SeaBasinGenerator — водная сторона `(C−K)·n > 0` (HY-6, resolved).
5. Кодовое состояние (сверить с кодом, не с памятью):
   - `dataModel/worldPack/wire/worldTopology.py` — `WorldTopology.neighbor/canonicalize/seam_pairs`, `NeighborResult`, `SeamPair`
   - `dataModel/worldPack/wire/worldBounds.py` — `wrapped_coordinate`, `folded_coordinate`, `antagonist_tile`, `edge_tiles`, `grid_neighbor`
   - `dataModel/worldPack/wire/worldTopologyMode.py`, `dataModel/terrain/worldTerrainScalars.py` (`world_topology_mode`, default `wrapped`)
   - `masks/regionRasterContext.py` — `fine_topology` (эталон консьюмера; переезд в домен)
   - `masks/regionRasterizer.py` — паттерн «unrolled compute + canonical write»
   - `generators/hydrology/shore/waterSideFootprint.py` — `CoastlineWaterSide`, `water_side_footprint`, `compute_land_centroid` (HY-6 код)
   - `generators/hydrology/shore/deepeningBandCarver.py`, `autoresolve/proceduralSeaAutoresolve.py`, `geom/polylineRasterize.py`, `load/buildHydrologyMasterInput.py`
   - тесты: `backend/tests/test_hydrology_hy6.py`, hy2/hy5a (регрессии)
6. Правила (нарушение = стоп):
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/layer-boundaries.mdc`](../rules/layer-boundaries.mdc)
   - [`.cursor/rules/code-gates.mdc`](../rules/code-gates.mdc) — один шаг за заход
   - [`.cursor/rules/project-context.mdc`](../rules/project-context.mdc) — не DAG, не коммитить, **не стартовать backend**
   - [`.cursor/rules/class-size-limit.mdc`](../rules/class-size-limit.mdc)
   - [`.cursor/rules/contract-creation.mdc`](../rules/contract-creation.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Целевой контракт (кратко — SoT в плане)

**Модель: unrolled compute + canonical write.** Геометрия считает на unrolled-координатах; в grid пишется по `topology.canonicalize`. `passable(c) = canonicalize(c) ∈ heightmap` — planar получает void бесплатно.

**Сервисы домена** (`dataModel/topology/topologyGeometry.py`): `unrolled_images` (wrapped ±w/±h, sphere + fold-образы с `invert_dy`), `dist2`, `nearest_on_segment` (min евклидова по образам — одна метрика на все режимы), `centroid` (unwrap к ближайшему образу anchor), `neighbors4_unrolled`.

**Запрет:** сырые `neighbors4`/евклид на мировых координатах вне домена; потребитель не ветвится по mode.

## Порядок шагов (по плану, один за заход)

1. **ТЗ** — `tz_terrain_generation.md` § Топология поверхности: таблица сервисов + «unrolled compute + canonical write» + запрет raw adjacency; `tz_terrain_hydrology.md`: «вода только в bounds» → «через шов» + `n(K)` на шве.
2. **2a — доменный корень** — move `worldTopology.py`/`worldBounds.py`/`worldTopologyMode.py` → `dataModel/topology/`; ~11 импортёров; `fine_topology` → домен (re-export в `regionRasterContext`). Без смены API.
3. **2b — сервисы** — `topologyGeometry.py` + `test_topology_unrolled_geometry.py` (wrapped dist через шов, sphere fold, centroid через шов, planar void).
4. **3a — flood-ядро** — `waterSideFootprint` (BFS unrolled + `canonical_passable`, `at()` через `nearest_on_segment`), `deepeningBandCarver` (`+ topology`, центроид→домен), call-site resolve `WorldTopology`. Тесты `test_hydrology_hy11.py`: coastline на `x_min` в wrapped → вода на `x_max`; sphere-сдвиг; planar void+warning; регрессии hy6/hy2/hy5a.
5. **3b — consumers** — `proceduralSeaAutoresolve` (bbox-edge через `edge_tiles`/`neighbor`), `buildHydrologyMasterInput` (fine→grid через `canonicalize`), `polylineRasterize` через шов. Grep `neighbors4` по `generators/hydrology/` → 0.
6. **4 — smoke** — `world_test_004` coastline обратно на x=−1500 → в wrapped вода на gx=+2. Backend не стартовать — через мастера/поднятый сервер; проверка по coarse/acceptance (L0 band — HY-10).

## Жёсткие запреты

- Не реализовывать HY-7/HY-8/HY-9/HY-10/HY-BATH-1/COV-1 — только топология+гидрология.
- Климат/рельеф/горы/локации — **не переключать** (свои треки в TOPO-1); только сервисы домена + гидрология.
- Не DAG-ноды, не schema, не коммит, не старт backend. Класс ≤300 строк.

## Приёмка

- `test_topology_unrolled_geometry` + `test_hydrology_hy11` зелёные; hy2/hy5a/hy6 без новых падений относительно baseline.
- `compileall`, `git diff --check`; grep `neighbors4` по `generators/hydrology/` → 0.
- Smoke: вода на противоположном краю (gx=+2) при coastline x=−1500 в wrapped.
- HY-11 → `resolved`; план → `-done`. TOPO-1: домен + первый консьюмер закрыты.

## Старт

Прочитай оба плана + `worldTopology.py` + `waterSideFootprint.py`. Затем шаг 1 (ТЗ).
