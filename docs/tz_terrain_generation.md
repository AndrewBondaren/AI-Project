---
name: tz-terrain-generation
description: "ТЗ генерации terrain — TerrainGeneratorService, eager/lazy/repair, координаты surface grid, связь с settlement"
metadata:
  node_type: memory
  type: project
---

> **Архитектура нод:** terrain-ноды пишут в `state.terrain_context: TerrainContext`. См. `tz_engine_node_context.md`.

## Назначение

`TerrainGeneratorService` — **pure utility** (без репозиториев, без async).  
Вход: `(World, list[NamedLocation])` → выход: `list[MapCell]`.

**Задача:** heightmap поверхности мира — elevation (`z`), `system_terrain`, климат, urban **fallback** footprint для городов без явных ячеек.

**Не задача terrain:** улицы, здания, заборы поселения — это `SettlementAssembler` / lazy settlement (см. `tz_city_generation.md`).

**Why utility, not service:** нужен и в worldData (eager API), и в engine-нодах (lazy/repair) без DI-контейнера.

---

## Расположение в проекте

```
app/application/worldData/generators/
  terrain/terrainGeneratorService.py     ← pure generator
  coordinates/                           ← convert hub (grid ↔ meters)
  assemblers/settlementAssembler/        ← lazy geometry (отдельный pipeline)

app/application/worldData/
  mapCellService.py                      ← persist, skip_location_uids

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
| Surface heightmap + climate | `TerrainGeneratorService.generate_surface` | Eager admin / первичная карта | `x,y` = **world surface grid index**; `z` = метры |
| Urban fallback footprint | тот же `generate_surface` | Если у города нет явных cells | grid tiles `urban` в rect footprint |
| Footprint occupancy mark | `plan_footprint_occupancy_cells` | Lazy settlement / world create | grid index (как terrain urban) |
| Streets, buildings, barriers | `SettlementAssembler` | Lazy settlement (gameplay) | **world local meters** (fine 1m step) |

**Приоритет источников формы города:**

1. **Явные** `map_cells` в БД / fixture (`skip_location_uids`) — канон.
2. **Lazy settlement** — geometry + occupancy при первом входе.
3. **Terrain fallback** — прямоугольный urban rect, если города ещё нет в DB.

Terrain **не перезаписывает** явные ячейки. Settlement **добавляет** meter-geometry поверх occupancy.

---

## Три кейса использования

### 1. Eager init (admin, не gameplay)

**Триггер:** `POST /worlds/{world_uid}/map/generate-surface` после импорта мира без surface cells.

**Flow:**

```
POST /worlds/{world_uid}/map/generate-surface
  └─ MapCellService.get_location_uids_with_cells(world_uid)  → skip_location_uids
  └─ TerrainGeneratorService.generate_surface(world, locations, skip_location_uids=…)
  └─ MapCellService.save_generated(cells)
```

**Eager steps (roadmap):**

| Step | Содержание | Статус |
|---|---|---|
| 1 | Surface heightmap + urban fallback | ✅ реализовано |
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

**Flow:** `lazyTerrainNode` → `generate_minimal(world, location)` → upsert одной anchor cell.

---

## Два уровня sourcing ячеек города

### 1. Явные (canonical)

`map_cells` с `location_uid = city_uid` в fixture/БД — **источник истины**. Любая форма (L-shape, дыры, …).

```python
skip_location_uids = await map_cell_repo.get_location_uids_with_cells(world_uid)
cells = generator.generate_surface(world, locations, skip_location_uids=skip_location_uids)
```

Город из `skip_location_uids`:

- **не** получает urban fallback footprint;
- **остаётся** в Voronoi для климата вокруг.

### 2. Fallback (generated)

Если у города **нет** cells в DB — urban rect из **`settlement_grid_rect`** (тот же контракт, что settlement occupancy).

**Не используется** legacy `city_size_registry.radius` и шаг ±1 от `(map_x, map_y)`.

---

## Алгоритм `generate_surface` (v1)

### Вход

```python
def generate_surface(
    self,
    world: World,
    locations: list[NamedLocation],
    padding: int = 2,
    skip_location_uids: frozenset[str] = frozenset(),
) -> list[MapCell]:
```

### Footprint rect (fallback urban)

Согласован с `tz_city_generation.md` §6.1 и `SettlementAssembler`:

```
cell_m   = world.map_cell_size_m  (override: map_settings.global_cell_size_m)
side_m   = footprint_multiplier(system_city_size) × cell_m
n_tiles  = grid_dimension(side_m, cell_m)   # ≥ 1

gx0 = map_x // cell_m
gy0 = map_y // cell_m
rect = [gx0, gy0, gx0 + n_tiles, gy0 + n_tiles)   # grid indices
```

Реализация: `generators/coordinates/` + `settlement_grid_rect(world, city)`.

**Пример** (`cell_m=3000`, town `footprint_multiplier=1.0`, `map_x=3000`):

| Поле | Значение |
|---|---|
| Meter origin | `(3000, 0)` |
| Grid rect | `(1, 0) – (2, 1)` — одна coarse tile |
| Urban cells | `(gx, gy) = (1, 0)` |

### Шаги

1. **Anchors** — `map_x/y/z IS NOT NULL`, `is_mobile=False`.
2. **City list** — типы `city`, `town`, `village`, `camp`.
3. **City footprint** — для каждого города: все `(gx, gy)` в `settlement_grid_rect`; если `location_uid ∉ skip_location_uids` → urban.
4. **Bounding box** — min/max grid coords всех footprints ± `padding`.
5. **Fill grid** — для каждого `(gx, gy)` в bbox:
   - в `city_footprint` → `urban`, `z=city.map_z`, `location_uid=city.uid`;
   - иначе → Voronoi климат от ближайшего города, `z = base_z(climate) + noise`, terrain от z.
6. **Non-city anchors** — одна cell на `(map_x, map_y, map_z)` для типов вне `_CITY_TYPES` (шахты, …).

### Voronoi (v1)

- Центры городов: `(meters_to_grid_x(map_x), meters_to_grid_y(map_y))` — **grid index**, не meter anchor.
- Расстояние: евклидово в grid space (шаг = один coarse tile, не `cell_m` метров).
- **Ограничение v1:** центр = угол anchor-тайла, не geometric center footprint — см. `tz_generator_technical_debt.md` NC-1d.

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

Одна anchor cell для repair. Координаты: **`map_x`, `map_y`, `map_z` как в БД** (метры для anchor позиции named_location).

Для city-type при наличии `urban` в registry → `system_terrain=urban`.

**Ограничение v1:** не конвертирует в grid index — см. NC-1c в tech debt (несогласованность с surface loop для non-city).

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
         │  translate_layout (MeterDelta)
         ▼
┌─────────────────────────────────────────────────────────────┐
│  LOCATION_LOCAL_METERS (v2, interior)                      │
│  generator cache (0,0) → translate → world meters            │
└─────────────────────────────────────────────────────────────┘
```

### Таблица: кто что пишет в `MapCell`

| Producer | `x`, `y` | `z` | Space |
|---|---|---|---|
| `generate_surface` (wilderness) | grid index | meters (elevation) | surface grid + z meters |
| `generate_surface` (urban fallback) | grid index | `city.map_z` | surface grid |
| `plan_footprint_occupancy` | grid index | `settlement.map_z` | surface grid |
| Settlement geometry (buildings, barriers) | meters | meters | world local meters |
| `generate_minimal` | `location.map_x/y` | `location.map_z` | anchor meters (v1) |
| Non-city anchor in step 6 | `anchor.map_x/y` | `anchor.map_z` | anchor meters (v1, NC-1c) |

**PK:** `(world_uid, x, y, z)` — разные z не конфликтуют.

Persist v1 (**Option A**): grid occupancy и meter geometry могут coexist в одной таблице без колонки `coordinate_space`; split только на уровне generator (`collect_surface_grid_cells` / `collect_geometry_meter_cells`). Колонка `coordinate_space` — v2 (optional).

### `map_cell_size_m`

- Хранится: `worlds.map_cell_size_m` (default **3000** в модели).
- Override: `world.map_settings["global_cell_size_m"]` (если задан).
- **Динамический** per world: целое, **кратно 1000** (типично 2000, 3000, 5000…).
- Валидация при save: `WorldService` — минимум и кратность (см. код).
- Conversion **только** в `generators/coordinates/convert.py`:

```python
gx = map_x_meters // cell_m
meter_origin_of_tile = gx * cell_m
```

### z всегда в метрах

`z` — elevation / этажность в **метрах** (Эверест 8849, шахта -20).  
Конвенция этажа ≈ 3 z-units (3 m потолок) — display, не отдельная сетка.

---

## Многослойные локации на одной `(x, y)`

Вертикальное стекирование валидно (город z=0, шахта z=-20 на той же surface tile — разные PK по z).

### Поля `named_locations`

| Поле | Семантика |
|---|---|
| `map_x`, `map_y` | позиция anchor в **метрах** |
| `map_z` | базовый z (нижняя граница); null у нарративных / mobile |
| `is_mobile` | true → static anchor не создаётся |

### Якорная cell (step 6 / minimal)

```python
if location.map_z is not None and not location.is_mobile:
    create anchor at (map_x, map_y, map_z)
```

| Локация | `map_z` | `is_mobile` | Якорь |
|---|---|---|---|
| Город на поверхности | `0` | false | ✓ (surface через footprint / minimal) |
| Шахта | `-20` | false | ✓ |
| Подземный город | `-1000` | false | ✓ |
| Дрейфующий корабль | null | true | ✗ |

### Мобильные локации

Runtime позиция — `mobile_location_positions` (архитектурный задел, не реализовано). См. прежний § в истории документа.

---

## Будущие алгоритмы footprint (v2+)

Текущий v1 — **прямоугольный rect** = `settlement_grid_rect`. Планируемые замены **внутри** `TerrainGeneratorService`:

| Алгоритм | Принцип |
|---|---|
| Road-following | urban вдоль дорожной сети |
| Organic growth | рост от центра + noise |
| Coastline | обрезка по берегу |
| LLM-assisted | JSON список grid cells |

Выбор — через `location_subtype` или world policy. Coordinate contract (grid index on surface) сохраняется.

---

## Подсистемы по типу локации (roadmap)

Стратегия `LocationSubGenerator` для mine/cave/dungeon — без изменений концепции; реализация отложена. См. предыдущие примеры в tech debt.

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
| `generate_surface` + `skip_location_uids` | ✅ |
| Footprint = `settlement_grid_rect` | ✅ |
| Coordinate convert hub | ✅ |
| `POST …/map/generate-surface` | ✅ |
| `lazyTerrainNode` + `generate_minimal` | ✅ |
| `lazy_settlement` (geometry) | ✅ отдельная нода |
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
- Option B: normalize all surface cells to meter corners `(gx * cell_m, gy * cell_m)`.
- Terrain decouple from `settlementAssembler.planner.footprint` → neutral package (LC-6).

---

## Связанные документы

| Документ | Связь |
|---|---|
| `tz_city_generation.md` | footprint_multiplier, lazy settlement |
| `tz_locations.md` | anchors, orphan repair |
| `tz_assembler_hierarchy.md` | assembler stack |
| `tz_generator_technical_debt.md` | NC-1, LC-6, open smells |
| `.cursor/plans/coordinate-spaces.md` | implementation phases |
