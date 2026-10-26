# Pack surface smell fixes ✅ DONE

Цель: один SoT (pack + parent light); legacy map_cells / materialize-stack **не поддерживать**.

Источник: ревью god-object / SoC / dataModel / неявные контракты (2026-07-15).

## Целевое состояние

- HTTP debug: только pack bake / refine / read / render.
- L2 surface: только `build_tile_surface_state(..., parent_light=...)`.
- Нет `_materialize_fine_tile` / `save_terrain_batch` map_cells path в live surface.
- Missing parent light → fail-closed.
- Defaults / caps — из `PackBakeDefaults` и typed surface context.

## Порядок

### P0 — блокеры

1. `map.py`: import `prepare_surface_terrain_context`.
2. `FineTerrainRefineOrchestrator`: parent miss → raise (не `PersistResult(0,0)`).

### P1 — legacy out

3. Удалить `_materialize_fine_tile` + map_cells batch callers (`save_terrain_batch` / `worldSurfaceMaterializationOrchestrator` path если только legacy).
4. HTTP: удалить 410 stubs legacy write routes (вариант A).
5. Scripts: один `api_pack_bake`; убрать `api_generate_surface` alias; climate no-op — удалить или сделать реальным.

### P2 — SoC

6. После #3: pack surface builder тонкий; не dual-era facade.
7. Refine HTTP: planning → application facade; route thin.
8. Cache: документ + при необходимости process-scoped cache на Container.

### P3 — контракты

9. Один SoT `max_tiles` / mosaic cap из POJO.
10. `tile_m` write: hard fail без `fine_cells_per_map_cell`.
11. Typed surface ctx вместо `getattr`.
12. `surface_z_at` miss — не молчаливый `0`.

## Вне скоупа

- DAG nodes.
- WP-26 map_cells read (если debug render ещё читает) — отдельным PR при необходимости.

## DoD

- [x] P0: refine HTTP не NameError; missing parent → ошибка
- [x] P1: нет live legacy fine write path; scripts на pack
- [x] P2–P3: typed SurfaceTerrainContext; process cache; tile_m hard fail; max_tiles из POJO; surface_z miss raises
- [x] Unit/тесты parent-light / refine обновлены под fail-closed

## Tails (2026-07-15 rereview) — done

- [x] Bake anchor fail-closed (no silent 0,0)
- [x] Bake surface_ctx fail-closed
- [x] max_tiles literals → PackBakeDefaults (bootstrap, scripts, smoke)
- [x] `light_m_for` SoT; LightGridScale / ParentLightTile / climateCoarseBake
- [x] Один `api_pack_bake` в debug_api_helpers; surface re-export
- [x] PathHeadingPolicy export + `path_ahead_depth` SoT
- [x] drain: only if `> 0` (no floor to 1)
- [x] Writer cache docstring (Container-scoped preferred)
