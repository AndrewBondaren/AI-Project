---
name: tz-terrain-generation
description: "ТЗ генерации terrain — TerrainGeneratorService, eager/lazy/repair, координаты surface grid, граница с settlement"
metadata:
  node_type: memory
  type: project
---

> **Архитектура нод:** terrain-ноды пишут в `state.terrain_context: TerrainContext`. См. `tz_engine_node_context.md`.

## Назначение

`TerrainGeneratorService` — **pure utility** (без репозиториев, без async).  
Вход: `(World, list[NamedLocation])` → выход: `list[MapCell]`.

**Задача:** heightmap **дикой местности** — elevation (`z`), `system_terrain`.

**Климат** — отдельный модуль [`ClimateGeneratorService`](docs/tz_climate.md); terrain вызывает его per cell (`temperature_base`, `rainfall`, `typical_elevation_z`).

**Не задача terrain:**

- urban footprint и форма города — `SettlementAssembler`, явные `map_cells`, lazy occupancy;
- улицы, здания, заборы — settlement pipeline (см. `tz_city_generation.md`).

**Почему отделено от городов:** поселение может быть построено или уничтожено; климат и elevation региона не должны пересчитываться от списка городов.

**Why utility, not service:** нужен и в worldData (eager API), и в engine-нодах (lazy/repair) без DI-контейнера.

---

## Расположение в проекте

```
app/application/worldData/generators/
  climate/climateGeneratorService.py   ← climate (Voronoi, temperature, rainfall)
  terrain/terrainGeneratorService.py   ← pure generator (wilderness heightmap)
  coordinates/                           ← convert hub (grid ↔ meters)
  assemblers/settlementAssembler/        ← urban occupancy + geometry

app/application/worldData/
  mapCellService.py                      ← persist (INSERT OR IGNORE)

app/api/routes/map.py                    ← POST …/map/generate-surface

app/application/engine/nodes/pojo/python/terrain/
  lazyTerrainNode.py                     ← repair / minimal anchor
  eagerTerrainNode.py                    ← проверка согласованности DB
  lazySettlementNode.py                  ← полная геометрия поселения (не terrain)
```

**Tech debt / smells:** `tz_generator_technical_debt.md`  
**Coordinate implementation plan:** `.cursor/plans/coordinate-spaces.md`

---

## Terrain vs Settlement

| Слой | Кто генерирует | Когда | `MapCell` semantics |
|---|---|---|---|
| Surface heightmap | `TerrainGeneratorService.generate_surface` | Eager admin | `x,y` grid index; `z` meters; `system_terrain` |
| Climate params | `ClimateGeneratorService` (via terrain) | Eager admin | `temperature_base`, `rainfall`; см. `tz_climate.md` |
| Urban footprint occupancy | `plan_footprint_occupancy_cells` | Lazy settlement / world create | grid index; `system_terrain=urban` (или explicit fixture) |
| Streets, buildings, barriers | `SettlementAssembler` | Lazy settlement (gameplay) | **world local meters** (fine 1m step) |

**Приоритет источников формы города:**

1. **Явные** `map_cells` в БД / fixture — канон (любая форма).
2. **Lazy settlement** — occupancy + geometry при первом входе.
3. **Terrain** — **не** участвует в urban.

`save_generated` использует `INSERT OR IGNORE` — явные ячейки не перезаписываются при повторном `generate-surface`.

---

## Три кейса использования

### 1. Eager init (admin, не gameplay)

**Триггер:** `POST /worlds/{world_uid}/map/generate-surface` после импорта мира без surface cells.

**Flow:**

```
POST /worlds/{world_uid}/map/generate-surface
  └─ TerrainGeneratorService.generate_surface(world, locations)
  └─ MapCellService.save_generated(cells)   # INSERT OR IGNORE
```

**Eager steps (roadmap):**

| Step | Содержание | Статус |
|---|---|---|
| 1 | Wilderness heightmap + climate via ClimateGenerator | ✅ |
| 2 | Структурные объекты (деревья, камни, …) | ⬜ отложено |
| 3 | Буфер ±10z вокруг anchor | ⬜ отложено |

`WorldBundleService.import_bundle()` **не** вызывает terrain — только импорт данных.

---

### 2. Lazy init (gameplay) — частично

**Задумка:** z-срез при первом входе игрока в регион без cells.

**Сейчас:** `generate_z_slice` **не реализован**. В gameplay:

- `lazy_terrain` → `generate_minimal` (repair anchor)
- `lazy_settlement` → полная геометрия поселения (`SettlementGeneratorService`)

**Целевой flow (отложен):**

```
MovementNode / AreaLoadNode
  └─ map_cell_repo.get_z_slice(…) → пусто?
  └─ TerrainGeneratorService.generate_z_slice(…)   ← API TBD
  └─ map_cell_repo.upsert_bulk(cells)
```

---

### 3. Broken location repair (gameplay)

**Триггер:** named_location без единой `map_cell` (orphan-tolerant design, `tz_locations.md`).

**Flow:** `lazyTerrainNode` → `generate_minimal(world, location)` → upsert одной anchor cell (wilderness terrain, не urban).

---

## Алгоритм `generate_surface` (v1)

### Вход

```python
def generate_surface(
    self,
    world: World,
    locations: list[NamedLocation],
    padding: int = 2,
) -> list[MapCell]:
```

### Шаги

1. **Anchors** — `map_x/y/z IS NOT NULL`, `is_mobile=False`.
2. **Zone centers** — типы `region`, `kingdom`, `empire`, `duchy` с координатами → grid index через `meters_to_grid_*`.
3. **Bounding box** — min/max grid coords **всех** anchors (города только расширяют bbox своей anchor-точкой, без footprint) ± `padding`.
4. **Fill grid** — для каждого `(gx, gy)` в bbox:
   - Voronoi климат от ближайшей **зоны** (не города);
   - `z = base_z(climate) + noise`, `system_terrain` от z;
   - `location_uid` = uid зоны (или `None`, если zone anchors нет).
5. **Non-surface anchors** (`map_z != 0`) — одна cell на `(map_x, map_y, map_z)` (шахты, подземные точки).

### Voronoi (v1)

- Центры: **zone-type** locations с `map_x/y`.
- Расстояние: евклидово в grid space.
- Города **не** участвуют — добавление/удаление settlement не меняет климат соседних tiles.
- Если zone anchors нет → `world.default_climate_zone`.
- **Ограничение v1:** центр = grid index anchor-точки зоны — см. NC-1d в tech debt.

### Noise (детерминированный)

```python
h = (world_seed ^ (gx * 73856093) ^ (gy * 19349663)) & 0xFFFFFFFF
noise = (h % (2 * amplitude + 1)) - amplitude  # amplitude=1
z = clamp(base_z + noise, z_min, z_max)
```

### Terrain от z

| z | terrain (приоритет) |
|---|---|
| ≥ 2 | tundra → plains |
| 1 | forest → plains |
| 0 | plains |
| ≤ -1 | liquid_body → plains |

Fallback если тип отсутствует в `world.terrain_registry`.

### Температура (v1, упрощённая)

```
temperature_base = climate_base_temp - z × lapse_rate
lapse_rate = world.elevation_lapse_rate ?? 7.0
```

Полная формула с сезонами — отложена.

---

## `generate_minimal`

Одна anchor cell для repair. Координаты: **`map_x`, `map_y`, `map_z` как в БД**.

Wilderness `system_terrain` от z — **не urban**. Urban — settlement или explicit import.

**Ограничение v1:** не конвертирует в grid index — см. NC-1c в tech debt.

---

## Система координат

### Три оси (не смешивать)

| Ось | Суть |
|---|---|
| `measurement_system` | imperial/metric — **только display/LLM**; generators не ветвятся |
| `INTERIOR_CELL_SIZE_M = 1` | fine step = 1 m — **константа движка**, не настройка мира |
| **Coordinate spaces** | разная семантика одного `int` в разных слоях |

### Coordinate spaces (v1)

```
┌─────────────────────────────────────────────────────────────┐
│  WORLD_SURFACE_GRID                                          │
│  MapCell.x/y при eager terrain + occupancy                 │
│  gx, gy = индекс coarse tile (0, 1, 2, …)                   │
│  один tile покрывает cell_m × cell_m метров на земле          │
└─────────────────────────────────────────────────────────────┘
         │  gx = map_x // cell_m     (convert hub)
         ▼
┌─────────────────────────────────────────────────────────────┐
│  WORLD_LOCAL_METERS                                          │
│  NamedLocation.map_x/y — anchor поселения в метрах           │
│  Settlement: districts, streets, gates, barriers, buildings  │
│  ConnectionNode.x/y — метры                                  │
└─────────────────────────────────────────────────────────────┘
```

### Кто пишет какие координаты

| Generator | x/y space | z | Notes |
|---|---|---|---|
| `generate_surface` (wilderness) | grid index | meters (elevation) | zone climate |
| `plan_footprint_occupancy_cells` | grid index | surface | urban occupancy |
| `SettlementAssembler` geometry | world local meters | meters | after translate |
| `generate_minimal` | raw anchor (repair) | anchor map_z | NC-1c |

---

## Named locations — роль в terrain

| Поле | Terrain usage |
|---|---|
| `map_x/y` | anchor → grid index для bbox; zone → Voronoi center |
| `map_z` | `0` = surface (wilderness loop); `!= 0` → extra anchor cell |
| `system_location_type` | zone types → climate Voronoi; cities → только bbox point |
| `system_climate_zone` | на zone / в иерархии для `_resolve_climate` |
| `parent_location_uid` | walk-up для climate на non-surface anchors |
| `is_mobile` | true → static anchor не создаётся |

### Якорная cell (minimal / non-surface)

```python
if location.map_z is not None and not location.is_mobile:
    if map_z != 0:
        create anchor at (map_x, map_y, map_z)
```

| Локация | `map_z` | Terrain |
|---|---|---|
| Город на поверхности | `0` | wilderness tile в bbox (urban — settlement) |
| Шахта | `-20` | ✓ extra anchor |
| Подземный город | `-1000` | ✓ extra anchor |

---

## DB — индексы

```sql
CREATE INDEX idx_map_cells_location_z ON map_cells (world_uid, location_uid, z);
```

PK `(world_uid, x, y, z)` — точечные запросы; индекс по location — lazy load / scene.

---

## Реализовано / не покрыто

| Элемент | Статус |
|---|---|
| `generate_surface` wilderness + zone Voronoi | ✅ |
| Terrain decoupled from cities / settlement footprint | ✅ |
| Coordinate convert hub | ✅ |
| `POST …/map/generate-surface` | ✅ |
| `lazyTerrainNode` + `generate_minimal` | ✅ |
| `lazy_settlement` (geometry + urban occupancy) | ✅ отдельная нода |
| `generate_z_slice` lazy region | ⬜ |
| Eager step 2–3 (structures, buffer) | ⬜ |
| Non-city anchor grid alignment (NC-1c) | ⬜ |
| `coordinate_space` column | ⬜ v2 |
| Полная температурная формула | ⬜ |
| `world_map_version` после generate | ⬜ |
| Regen UX при смене `map_cell_size_m` | ⬜ |
| Фоновая генерация соседей | ⬜ v2 |

---

## Многопоточность

Без изменений: детерминизм + upsert-семантика + IRepository. Generators pure, без SQL.

---

## Регенерация при изменении `map_cell_size_m`

**Триггер:** `WorldService.update()` — старое ≠ новое.

**Поведение (не реализовано полностью):** предупреждение → `MapCellService.clear` → повторный `generate-surface`.

---

## Открытые вопросы

- `generate_z_slice` API: bounds vs `location_uid + z`.
- Non-city anchors: grid index vs meter anchor на surface PK.
- Zone без `map_x/y`: только `default_climate_zone` для Voronoi (нет полигонов).
- Option B: normalize all surface cells to meter corners `(gx * cell_m, gy * cell_m)`.

---

## Связанные документы

- `tz_city_generation.md` — settlement, occupancy, urban
- `tz_locations.md` — named_location fields
- `tz_generator_technical_debt.md` — NC-1, smells
- `project_data_storage_tz.md` — map_cells schema
