# NC-10 — кластер «Pack / parent light»: убрать суффикс `_m` («метры») из имён — done

**Status:** ✅ done (шаги 1–4 выполнены; wire `sample_step_fine` с `AliasChoices` на чтении)
**ТЗ:** `docs/tz_generator_technical_debt.md` § NC-10 (кластер «Pack / parent light», замок); `docs/tz_map_light_bake.md` § L0 / WP-10 v2; `docs/tz_world_pack_storage.md` (Parent light SoT / WP-PERF-22)
**Замок NC-10:** один слайс = один кластер; wire breaking OK + alias старого ключа на чтении; DAG `engine/nodes/` не трогать; NC-2 parcel `*_M` не открывать; горы/relief — отдельный слайс (только импорты переименованных pack-символов).

## Проблема

`int`-поля и параметры названы метрами (`tile_m`, `light_m`, `*_radius_m`, `sample_step_m`), а значения — fine cells. Читатель принимает за SI. Пример из чата: `tile_m` читается как «тайл в метрах».

## Имена (утверждаются при review плана)

| Старое | Новое | Комментарий |
|---|---|---|
| `tile_m` (поле `LightGridScale`, `ParentLightTile`, kwargs, locals) | `tile_macro` | решение мастера из чата; alt `map_cell_span` |
| `light_m` (поле, property, locals) | `light_span` | fine cells per light cell; alt `fine_per_light_cell` (черновик NC-10) |
| `light_m_for(tile_m, side)` | `light_span_for(tile_macro, side)` | SoT в `worldMapCellsPerTile.py` |
| `tile_size_m` | `tile_macro` | та же величина (`fine_cells_per_map_cell`) |
| `cell_m` / `_cell_m` / `_tile_m` | `tile_macro` / `_tile_macro` | локалки того же смысла — в единое имя |
| `xm`/`ym` (fine-координаты) | `x_fine`/`y_fine` | только по касанию, в переименовываемых функциях |
| `meters_to_tx_ty` | `fine_to_tx_ty` | `ParentLightTile` |
| `meters_to_light` / `meters_to_macro_local` | `fine_to_light` / `fine_to_macro_local` | `lightGrid/coords.py` |
| `light_cell_origin_m` / `light_cell_center_m` | `light_cell_origin_fine` / `light_cell_center_fine` | `lightGrid/coords.py`; импорты в mountains обновить, их свои `_m` — не этот слайс |
| `resolve_meter_anchor` | `resolve_fine_anchor` | `detailedGradeCorridor.py` (`center_m=` kwarg — параметр relief-модели `EdgeRoadAnchor`, не этот слайс) |
| `depth_m`, `half_width_m`, `corridor_half_width_m` | `depth_fine`, `half_width_fine`, `corridor_half_width_fine` | `pathHeading.py`, `pathCorridorSelect.py`, `PathHeadingPolicy` |
| `radius_m`, `ring_reach_m`, `max_radius_m` | `radius_fine`, `ring_reach_fine`, `max_radius_fine` | `entryRingGeom.py`, `chunkSchedule.py`, `fineTerrainRefineOrchestrator.py` |
| `background_expand_radius_m` | `background_expand_radius_fine` | `SceneVolumePolicy` + ключи JSON в `api/routes/map.py` (breaking; front не читает) |
| `sample_step_m` | `sample_step_fine` | **wire-поле** `ClimateFieldWire` — см. шаг 3 |
| `worldGridRenderer.cell_m`, `packMapGridRender.cell_m` | `tile_macro` | render-параметры |
| `meter_surface_z` / `_meter_surface_z` | `fine_surface_z` | `detailedBakeRefine`, `fineRefineResult` (internal; persist уже пишет `l2_surface_z`) |
| `sample_meters` | `sample_fine` | `climatePackApply` / wire-reader helpers |
| `meter_segments_to_light` | `fine_segments_to_light` | `contributors/hydro/raster.py` + callers |
| `light_polyline_from_meters` | `light_polyline_from_fine` | `raster.py` + `declaredRivers.py`, `road.py` |
| `_node_meters` | `_node_fine` | `contributors/road.py` |
| `meter_cells`, `meter_orphans`, `iter_halo_meters`, `meter_grade_cell_blocked` | `fine_cells`, `fine_orphans`, `iter_halo_fine`, `fine_grade_cell_blocked` | pack/refine internals; `discover/types.py` — проверить владельца (relief → пропустить) |
| `meterGradeSurface.py` / `MeterGradeSurface` | `fineGradeSurface.py` / `FineGradeSurface` | internal модуль `pack/refine` |
| docstrings «meters/Meters per…» | «fine cells» | попутно в изменяемых функциях |

`cell_center_m` (`relief/volume/edgeRoadAnchor.py`) — **relief-кластер**, НЕ этот слайс. То же для собственных `*_m` в `generators/terrain/mountains/*` и `relief/*`.

**Вне scope:** горы/relief `*_m` (свой кластер NC-10); `measurement_system` (UI/LLM метры — легально); `sparse_fine_hydro` и пр. — уже переименовано; `NC-2` `*_M` parcel-константы.

## Шаг 1 — ядро scale: `LightGridScale` / `ParentLightTile` / helpers

**Цель:** переименовать `tile_m`/`light_m`/`meters_to_*`/`light_cell_*_m`-семейство в полях и сигнатурах + все call sites.

**Файлы:**
- `app/dataModel/worldPack/wire/parentLightTile.py` — `tile_m`, `light_m`, `meters_to_tx_ty`, docstring
- `app/dataModel/worldPack/wire/worldMapCellsPerTile.py` — `light_m_for`, параметры, docstring; export в `worldPack/__init__.py`
- `app/application/worldData/pack/bake/lightGrid/coords.py` — `LightGridScale`, `cell_center_m`, `light_cell_center_m`
- `app/application/worldData/pack/bake/lightGrid/compose.py` — properties `tile_m`/`light_m`
- Call sites `scale.tile_m`/`scale.light_m`/`parent.tile_m`/`parent.light_m`/`from_tile(tile_m=)`/`load_parent_light(tile_m=)`/`require_parent_light(tile_m=)`/`meters_to_tx_ty`/`light_m_for` — `pack/bake`, `pack/climate`, `pack/read`, `pack/refine`, `render/`, `masks/regionRaster*`, `landcover/*`, `generators/hydrology/shore`, `generators/terrain/passes`, `generators/terrain/{mountains,reliefObjects}` (только импорт/вызов), `materialize/terrainBatchOrchestrator`
- Тесты: `test_light_grid_compose`, `test_parent_light_refine`, `test_landcover_fine_paint`, `test_detailed_grade_generate`, `test_open_land_hills`, `test_terrain_hills_registry_cutover`, `test_region_rasterizer`, `test_wilderness_region_index`, `test_light_bake_cleanup` (имя теста `test_wp10_side_ignores_tile_m` — тоже переименовать)

**Контракт:** `LightGridScale(tile_macro, side, light_span)`; `ParentLightTile(tile_macro, side)` + property `light_span` + `fine_to_tx_ty(x_fine, y_fine)`; `light_span_for(tile_macro, side)`.

**Проверка:** `python -m compileall app`; `python -m unittest` по списку выше + `test_wilderness_*` + `test_pack_render_read_facade`; `grep -nE "\b(tile_m|light_m|tile_size_m|meters_to_tx_ty|cell_center_m|light_cell_center_m)\b" app/` → только mountains-локалки, не из этой таблицы.

**Done:** rename чистый, тесты зелёные, значений/поведения нет — rename only.

## Шаг 2 — refine/render/policy хвосты

**Цель:** остаток кластера — policy-поля и параметры без `_m`.

**Файлы:**
- `app/dataModel/terrain/sceneVolumePolicy.py` — `background_expand_radius_m` → `_fine`
- `app/api/routes/map.py` — JSON-ключи `background_expand_radius_m` → `_fine` (×2)
- `app/dataModel/worldPack/bake/pathHeadingPolicy.py` — `corridor_half_width_m` → `_fine`
- `pack/refine/pathHeading.py`, `pathCorridorSelect.py` — `depth_m`, `half_width_m`, `tile_size_m`
- `pack/refine/chunks/chunkSchedule.py`, `fine/fineTerrainRefineOrchestrator.py` — `max_radius_m`, `tile_size_m`, `cell_m`
- `pack/refine/entry/entryRingGeom.py` — `radius_m`, `ring_reach_m`, `cell_m`
- `pack/refine/detailed/detailedGradeCorridor.py` — `center_m`, `resolve_meter_anchor`
- `pack/refine/meterGradeSurface.py` → `fineGradeSurface.py` (git mv, класс + импорты)
- `pack/refine/detailed/{detailedGradeDiscover,detailedGradePaint}.py`, `pack/refine/fine/{fineChunkPersist,fineChunkRunner,fineRefineResult}.py`, `pack/bake/{detailedBakeRefine,packDetailedBakeOrchestrator}.py` — `meter_surface_z`, `meter_cells`, `meter_orphans`, `meter_grade_cell_blocked`, `iter_halo_meters`
- `pack/bake/lightGrid/contributors/hydro/raster.py` + `declared{Basins,Rivers}.py`, `contributors/road.py` — `meter_segments_to_light`, `light_polyline_from_meters`, `_node_meters`
- `pack/climate/climatePackApply.py` — `sample_meters` (если метод wire-модели — переносится в шаг 3 как wire)
- `pack/refine/fine/{fineChunkGeom,fineTilePrep}.py`, `pack/bake/packTileCollect.py`, `pack/climate/climatePackApply.py`, `pack/climate/climateCoarseBake.py` — `cell_m`, `tile_size_m` locals/kwargs
- `render/pack/{worldMapPackRenderer,packMapGridRender}.py`, `render/worldMap/{worldMapMacroRender,worldMapGradeOverlay,worldGridRenderer}.py`, `render/light/{lightMosaic,lightMapPins}.py` — `tile_size_m`, `_tile_m`, `cell_m`, `fine_span` оставить (уже без `_m`)
- `scripts/render_maps.py` — `tile_size_m`
- Тесты: `test_pojo_policies`, `test_pack_wp13_entry_first`, `test_world_map_pack_renderer`, `test_wilderness_tile_pack_renderer`, `test_pack_render_read_facade`, `test_location_pin_overlay`

**Проверка:** `compileall app`; unittest по списку; `grep -rEn "\b[a-z_]*_m\b" app/application/worldData/pack app/application/worldData/render app/dataModel/worldPack app/dataModel/terrain/sceneVolumePolicy.py app/api/routes/map.py` → в кластере 0 (кроме `sample_step_m` до шага 3 и легальных `_min`/`_max`/`mode`).

**Done:** grep-аудит чист, тесты зелёные.

## Шаг 3 — wire-поле `ClimateFieldWire.sample_step_m`

**Цель:** единственное wire-переименование кластера — изолировано, с alias на чтении старых паков (замок NC-10).

**Файлы:**
- `app/dataModel/worldPack/wire/climateFieldWire.py` — `sample_step_m` → `sample_step_fine`, `Field(validation_alias=AliasChoices("sample_step_fine", "sample_step_m"))`, docstring «meters» → fine cells
- `app/application/worldData/pack/climate/climateCoarseBake.py` — kwargs `sample_step_m=` ×2
- читатели `sample_step_m` (grep по проекту)
- Тест: чтение старого ключа (`model_validate({"sample_step_m": 4})` → `sample_step_fine == 4`) + запись нового

**Проверка:** compileall; `test_pack_render_read_facade`, climate-pack тесты; сериализация пишет `sample_step_fine`, чтение принимает оба ключа.

**Done:** старые паки читаются, новые пишут новый ключ.

## Шаг 4 — доки и долговой реестр

**Цель:** синк имён в ТЗ и закрытие строки реестра.

**Файлы:**
- `docs/tz_map_light_bake.md` — `tile_m`/`light_m` формулы (~строки 124-126, 172, 1339) → новые имена
- `docs/tz_generator_technical_debt.md` — NC-10: строка «Pack / parent light» → ✅, changelog-запись, при полном закрытии кластера обновить статусные строки (кластеров остаются горы + locals)
- другие `docs/tz_*.md` с `tile_m`/`light_m` — по grep, только touch этих имён

**Проверка:** `grep -rn "tile_m\|light_m" docs/tz_map_light_bake.md docs/tz_generator_technical_debt.md` → только исторические записи/changelog.

**Done:** доки синхронизированы, NC-10 pack-строка отмечена.

## Порядок и границы

- Шаги 1 → 2 → 3 → 4 строго по одному за заход (code-gates), отчёт после каждого.
- Rename-only: не менять значения, семантику, порядок аргументов у позиционных вызовов — не менять.
- Mountains файлы: только строки импорта/вызова переименованных символов; их собственные `*_m` — НЕ трогать (свой слайс).
- Без коммита до явной просьбы мастера.
