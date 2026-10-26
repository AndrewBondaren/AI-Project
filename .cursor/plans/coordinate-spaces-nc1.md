# NC-1: Coordinate spaces — план решения

Связано: `.cursor/plans/settlement-assembler-done.md` § NC-1, `docs/tz_terrain_generation.md` § Система координат, `docs/tz_city_generation.md` §6.1, `docs/tz_locations.md` (local↔global bridging).

**Проблема:** в коде смешиваются два смысла одних и тех же полей `MapCell.x/y` (и иногда `ConnectionNode.x/y`):

| Space | Семантика | Примеры в коде |
|---|---|---|
| `WORLD_SURFACE_GRID` | индекс тайла мира; физически `fine_cells_per_map_cell` м на шаг | `plan_footprint_occupancy`, `TerrainGeneratorService` |
| `WORLD_FINE_GRID` | абсолютные метры мира, fine 1 m | `NamedLocation.map_*`, districts, streets, barriers, buildings после `translate_layout` |

**Не путать с `measurement_system`:** metric/imperial — только display/LLM при чтении; generators и БД работают в **канонических метрах**.

---

## Целевая модель

### Три space (полная модель по ТЗ)

| `CoordinateSpace` | Оси | Когда |
|---|---|---|
| `WORLD_SURFACE_GRID` | gx, gy | terrain eager, urban occupancy tile |
| `WORLD_FINE_GRID` | x, y, z | settlement outdoor, connection graph, outdoor barriers, здания после размещения |
| `LOCATION_FINE_GRID` | x, y, z | interior generator до translate; `location_passages`; offset = MIN(cells) по TZ |

**v1 scope:** внедрить первые два + зафиксировать контракт для третьего. Interior пока через `translate_layout` → world meters (as-is).

### Typed layer (Python)

Не `IntEnum` на значении x/y — **NewType + dataclass + явные convert**.

```
generators/coordinates/
  __init__.py
  spaces.py       # CoordinateSpace StrEnum
  types.py        # GridX, FineX, SurfaceGridCoord, FineGridCoord, ...
  convert.py      # meters_to_grid, grid_tile_origin_m, grid_rect_from_origin_m
  persist.py      # (v1.2) normalize MapCell ↔ space при collect/persist
```

**Правила:**

1. Planner/assembler API принимает typed coords, не «голый int с комментарием».
2. Convert **только** в `convert.py` / `footprint.py` (тонкая обёртка).
3. DB `map_cells` пока `int`; опционально `coordinate_space` — фаза 1.2.
4. Imperial — display adapter, не в generators.

---

## Фазы

### Фаза 0 — Документирование контракта (без кода) ✅ частично

- [x] NC-1 описан в `settlement-assembler-done.md`
- [x] Proposal typed coordinates
- [ ] **Продуктовый параграф в `docs/tz_terrain_generation.md` § Система координат** — явно: world tile index vs world meters vs location-local; когда какой `MapCell` (отдельный PR в docs)

**Текст для docs (черновик):**

> World surface: `map_cells.(x,y)` для terrain/occupancy — **индекс тайла** `[0..N)`, не метры.  
> Settlement geometry: абсолютные **метры** от anchor `named_location.map_x/y`.  
> Связь: `grid_x = map_x_m // fine_cells_per_map_cell`.  
> Interior: локальные метры относительно footprint локации; bridge через offset (см. tz_locations).

---

### Фаза 1 — Typed layer + footprint (без DB migration)

**Цель:** typechecker + явный API; smoke с `map_x=3000`.

| # | Задача | Файлы |
|---|---|---|
| 1.1 | Создать `generators/coordinates/` (spaces, types, convert) | new |
| 1.2 | Refactor `footprint.py`: `footprint_grid_rect` → returns `SurfaceGridRect`; `footprint_fine_rect` → `FineGridRect` | `planner/footprint.py` |
| 1.3 | Alias/re-export старых tuple API с `@deprecated` comment или thin wrappers для постепенной миграции | `footprint.py` |
| 1.4 | Обновить call sites: `districts.py`, `mapOccupancy.py`, `streets.py`, `barriers.py`, `layoutCells.py` | grep `footprint_` |
| 1.5 | Smoke: `test_coordinate_convert()` + `test_settlement_at_map_x_3000()` в `debug_settlement.py` | script |
| 1.6 | mypy/pyright на `generators/coordinates/` + `footprint.py` | CI optional |

**Acceptance фазы 1:**

- `meters_to_grid(FineX(3000), 3000) == GridX(1)`
- town at `map_x=3000`: district `origin_x=3000`, occupancy `gx=1`
- Ни один planner не делает `ox // cell_m` inline — только через convert

---

### Фаза 2 — Persist contract (`collect_map_cells_from_layout`)

**Проблема:** один list смешивает occupancy (grid index) и geometry (meters).

**Варианты (выбрать один):**

| Вариант | Описание | Плюсы | Минусы |
|---|---|---|---|
| **A. Normalize to meters** | occupancy пишет `MapCell` с x/y = corner tile в метрах `(gx * cell_m, gy * cell_m)` | один space в persist | меняет семантику terrain PK если merge |
| **B. Tag space** | поле `coordinate_space` на MapCell или parallel metadata | честно | migration + repo |
| **C. Split lists** | `SettlementLayout.occupancy_cells` grid; geometry meters; merge только в repo с tag | без изменения tile PK | больше полей в layout |

**Рекомендация:** **C → B** — сначала не merge в один list без метки; `collect_map_cells_from_layout` возвращает `CollectedCells(grid=..., meters=...)` или tagged union; persist layer склеивает с `coordinate_space`.

| # | Задача |
|---|---|
| 2.1 | Решение A/B/C зафиксировать в этом plan (checkbox) |
| 2.2 | Refactor `layoutCells.py`, `SettlementGeneratorService`, lazy persist node |
| 2.3 | `needs_settlement_geometry` — проверять только meter-space cells |
| 2.4 | Smoke: persist round-trip или unit test на collect |

---

### Фаза 3 — Terrain alignment

**Проблема:** `TerrainGeneratorService` расширяет footprint как `(map_x+dx, map_y+dy)` с dx∈{-1,0,1} — трактует anchor как grid index, settlement — как meters.

| # | Задача |
|---|---|
| 3.1 | Anchor cities: `map_x/map_y` = **meters** (TZ city gen) |
| 3.2 | Footprint expand: `(cx + dx * map_cell_fine_span, cy + dy * map_cell_fine_span)` или convert через `meters_to_grid` then grid neighbors |
| 3.3 | `_get_city_radius` / `footprint_multiplier` — согласовать с `city_size_registry` (radius vs multiplier) |
| 3.4 | Integration test: city at (3000,0), terrain urban tiles gx=1.. |

---

### Фаза 4 — LOCATION_FINE_GRID (interior, v2)

| # | Задача |
|---|---|
| 4.1 | `StructureGeneratorService` / cache probe — явно `LocationLocalCoord` |
| 4.2 | `translate_layout(dx, dy)` — `FineGridCoord` offset |
| 4.3 | Bridge helper: `location_local_to_world(local, building)` |
| 4.4 | Align с TZ: `location_passages` local; offset = MIN(cells) |

---

## Порядок работ (рекомендуемый)

```
Фаза 0 (docs paragraph)  ──┐
Фаза 1 (typed + footprint) ──► можно параллельно
Фаза 2 (persist)         ──► после 1
Фаза 3 (terrain)         ──► после 1, можно параллельно с 2
Фаза 4 (interior local)  ──► после 2 стабилизирован
```

**Не блокирует текущую имплементацию ТЗ:** smoke `map_x=0` маскирует баг. Фаза 1 — минимальный vertical slice перед persist в prod.

---

## Конвенции кода

```python
# spaces.py
class CoordinateSpace(StrEnum):
    WORLD_SURFACE_GRID = "world_surface_grid"
    WORLD_FINE_GRID = "world_fine_grid"
    LOCATION_FINE_GRID = "location_fine_grid"

# types.py
GridX = NewType("GridX", int)
FineX = NewType("FineX", int)

@dataclass(frozen=True, slots=True)
class SurfaceGridCoord:
    gx: GridX
    gy: GridY

@dataclass(frozen=True, slots=True)
class FineGridCoord:
    x: FineX
    y: FineY
    z: FineZ

# convert.py — единственное место для //
def fine_to_grid_x(x: FineX, map_cell_fine_span: int) -> GridX: ...
def grid_tile_origin_x(gx: GridX, map_cell_fine_span: int) -> FineX: ...
```

**Именование в логах:** всегда указывать space: `origin_m=(3000,0)` vs `grid=(1,0)`.

---

## Тесты

| Test | Проверяет |
|---|---|
| `test_meters_grid_roundtrip` | convert туда-обратно для origin тайла |
| `test_settlement_second_tile` | `map_x=3000`, town 1×1, district ox=3000, occ gx=1 |
| `test_no_inline_floor_div` | grep/lint optional |
| `test_collect_separates_spaces` | после фазы 2 |
| `test_terrain_footprint_meters` | после фазы 3 |

Запуск: `python backend/scripts/debug_settlement.py` + будущий `test_coordinates.py`.

---

## Риски и mitigations

| Риск | Mitigation |
|---|---|
| Runtime не ловит mix (Python) | mypy strict на `generators/`; code review; convert hub |
| Большой refactor | фазами; wrappers в footprint; grep usages (refactor-safety.mdc) |
| DB PK менять нельзя | grid cells остаются index; normalize или tag на persist |
| Imperial confusion | не трогать generators; display layer отдельно |

---

## Definition of Done (NC-1 closed)

- [ ] Typed coordinates module в production use для footprint + districts + occupancy
- [ ] Smoke `map_x=3000` green
- [ ] Persist не смешивает grid/meters без explicit contract (фаза 2)
- [ ] Terrain footprint согласован с meter anchor (фаза 3)
- [ ] Параграф в `docs/tz_terrain_generation.md`
- [ ] NC-1 в `settlement-assembler-done.md` → ✅

---

## Out of scope

- Imperial display adapter (отдельная задача UI/LLM)
- Изменение `fine_cells_per_map_cell` regen flow (tz_terrain § regen)
- Hex grid (если появится — отдельный space)
