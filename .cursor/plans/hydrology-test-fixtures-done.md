# Hydrology test fixtures — dedup + пробелы покрытия [DONE]

Источник: инвентаризация фикстур в чате wilderness-review-debt-7plus (2026-10-19).
Факт: 9–10 тест-файлов hydrology копируют приватные `_world`/`_flat_heightmap`/
`_depression_heightmap`/`_master` с расходящимися дефолтами; shared-модуля нет.

## Шаг 1 — `backend/tests/hydrology_fixtures.py`

Shared-модуль (импорт как `from tests.hydrology_fixtures import ...`, по прецеденту
`template_domain_transport_fixture.py`):

- `hydro_world(**kwargs)` — SimpleNamespace с суперсетом дефолтов:
  `world_uid`, `hydrology={"enabled": True}`, `fine_cells_per_map_cell=3000`,
  column-fill поля (`terrain_registry/masks/scalars=None`, `closed_planet_grid=False`,
  `magma_band_thickness=None`, `z_min=0`, `z_max=20`, `map_subsurface_depth=0`)
- `flat_heightmap(gx_lo, gx_hi, gy_lo, gy_hi, z=5, *, world_uid)` — bbox-вариант
- `heightmap_from_z(surface_z, *, world_uid)` — bbox из ключей
- `depression_heightmap()` — 11×11 crater (7950/8000/8010/8050)
- `hydro_master(**changes)` — `HydrologyMasterInput` all-scopes
- `waypoint(x, y, z=0)` — wire dict
- wire-константы: `SQUARE_SHORELINE`, `LAKE_WIRE`, `RIVER_SEGMENTS_WIRE`,
  `RIVER_ENDPOINTS_WIRE`, `COASTLINE_PATH_WIRE`
- `world_hydrology_dump()` — `WorldHydrology().model_dump(mode="json")`

## Шаг 2 — миграция файлов на shared-модуль

Файлы: `test_hydrology_hy1/hy2/hy3/hy4/hy5a/hy5b/hy5c`, `test_hydrology_coarse_space`,
`test_hydrology_declared_wire`, `test_hydrology_shore_paint`,
`test_hydrology_water_body_uid`, `test_bathymetry_stub`.

Правила:
- идентичные дефолты → прямой импорт/алиас; отличающийся `hydrology`-пресет —
  тонкий `def _world(**kw)` wrapper, передающий пресет в `hydro_world`;
- `coarse_space`: `FINE_PER_CELL=1000`, сигнатура `_flat_heightmap(x_hi, y_hi)` →
  `flat_heightmap(0, x_hi, 0, y_hi)`;
- `test_declared_river_topology` не трогаем (wire-builders `_stem`/`_tributary`/
  `_system` — домен-специфичны).

## Шаг 3 — новые кейсы в `test_hydrology_water_body_uid.py`

1. Два declared coastline → разные `water_body_uid` (per-spec carve).
2. Coastline без `location_uid` → fallback `auto-sea-*`.
3. `declare_mode: endpoints` → `apply_declared_fine_river_carves` стампует uid.
4. `run_column_fill` → `MapCell.hydrology` содержит `water_body_uid` (persist-уровень).

## Шаг 4 — `test_hydrology_determinism.py`

Кросс-процессный детерминизм carve-путей (`PYTHONHASHSEED` 0/1/42): subprocess
`sys.executable -c` прогоняет autoresolve lakes + sea + rivers на фикстурах из
`hydrology_fixtures`, дампит отсортированный `{cell: water_body_uid}` + river
`edge_uid`/`polyline_cells`; вывод трёх прогонов сравнивается побайтово.
Ловит set-итерацию, зависящую от hash seed (урок `_pick` из долга 0–7).

## Приёмка

- `python -m unittest` по всем hydrology-файлам — зелёные.
- Ни одного дубля `_depression_heightmap`/`hydro_master` в тестах.
- compileall app+tests чистый.
