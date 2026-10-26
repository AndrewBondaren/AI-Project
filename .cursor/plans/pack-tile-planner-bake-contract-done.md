# Impl: PackTilePlanner → контракт мастера (bake modes) ✅ DONE

**ТЗ SoT (утверждено 2026-07-19):**

| Mode | Scope |
|---|---|
| `light` | все macro-tiles с `named_locations` |
| `full` | все macro-tiles, покрывающие `world_bounds` (resolved AABB) |
| `detailed` | L2 одной локации (без изменений) |

Docs: [`tz_world_pack_storage.md`](../../docs/tz_world_pack_storage.md) § Bake modes; [`tz_terrain_generation.md`](../../docs/tz_terrain_generation.md) § Bake modes.

## Расхождение кода

| Компонент | Сейчас | Target |
|---|---|---|
| [`PackTilePlanner`](../../backend/app/application/worldData/pack/bake/packTilePlanner.py) `scope=light` | `bootstrap_macro_tiles` + `max_tiles` cap | все location tiles (**без** cap, который отрезает локации) |
| `scope=full` | `full_location_l0_tiles` | tiles covering entire `world_bounds` / resolved bbox |
| [`PackCompletenessClassifier`](../../backend/app/application/worldData/pack/bake/packCompletenessClassifier.py) | `expected_l0_light` / `_full` под старый WP-27 | sync к новым expected sets |
| Smoke `initialize_world.py --max-tiles 16` | режет light | не использовать как product semantics; debug-only override или убрать из «канонического» smoke |

## Порядок работ

1. Helper: macro tiles from `grid_bbox_from_locations` / `world_bounds` → full tile list.
2. `PackTilePlanner.plan(scope="light")` → `full_location_l0_tiles` (или эквивалент «все location tiles»).
3. `plan(scope="full")` → all tiles in resolved world AABB.
4. Classifier + unit tests (`test_pack_bake_modes.py`) — обновить ожидания.
5. Smoke scripts: default без cap; `--max-tiles` только как явный debug override (документировать).
6. Mosaic frame prefer `world_bounds` — отдельный follow-up (MLB-12), не блокер planner.

## Вне scope

- Rename `wilderness_chunk` / layer ids в коде
- Renderer X-axis
- DAG nodes
