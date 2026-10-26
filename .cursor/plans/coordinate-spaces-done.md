# План: coordinate spaces (NC-1) ✅ DONE

**Статус:** draft — к имплементации после vertical slice ТЗ  
**Связано:** `.cursor/plans/settlement-assembler-done.md` § NC-1, smell LC-*  
**Продуктовые ТЗ (обновить после Phase 6):** `docs/tz_terrain_generation.md` § Система координат, `docs/tz_city_generation.md`, `docs/tz_locations.md`

---

## 1. Проблема

### 1.1 Что сломано / рискованно

Сейчас `MapCell.x`, `MapCell.y`, `ConnectionNode.x/y` — голый `int` без семантики **пространства координат**.

| Consumer | Что кладёт в `x`, `y` | Space |
|---|---|---|
| `TerrainGeneratorService` | индекс тайла + `±1` от anchor | **world surface grid** (предположительно) |
| `plan_footprint_occupancy_cells` | `gx`, `gy` = `ox // map_cell_fine_span` | **world surface grid** |
| Settlement planners (districts, streets, barriers) | абсолютные **fine cells** | **world fine grid** |
| Building cells после `translate_layout` | абсолютные **fine cells** | **world fine grid** |
| `collect_map_cells_from_layout` | **оба** в одном `list[MapCell]` | смешение без tag |

При `NamedLocation.map_x = 0` (smoke) grid index 0 и meter 0 совпадают → баг **не виден**.

При `map_x = 3000` (2-й тайл, по ТЗ) terrain footprint и merged persist дают неверную геометрию.

### 1.2 Три независимые оси (не смешивать)

| Ось | Что это | Связь с NC-1 |
|---|---|---|
| **`measurement_system`** | imperial / metric — **только перевод при display / LLM**; generate в coarse/fine cells | **Нет.** Не создаёт вторую сетку, не меняет `x/y`. |
| **`FINE_CELL_SIZE = 1`** | В **fine** пространстве шаг сетки = 1 int | **Не** imperial. Движковая константа (`constants.py`), не настройка мира. |
| **NC-1 (coarse vs fine)** | **Разная семантика одного `int`**: индекс world-тайла vs fine-grid anchor | **Да.** Это и чиним typed spaces + convert hub. |

Imperial переводит «3 м» → «~10 ft» при показе.  
Fine space «клетка (80, 40)» = 80 fine-клеток от origin — не потому что мир metric.

### 1.3 Что это НЕ

| Вопрос | Ответ |
|---|---|
| Imperial vs metric? | **Нет.** Только display-layer. |
| «1 блок = 1 метр» = metric mode? | **Нет.** Совпадение `FINE_CELL_SIZE`; от imperial не зависит. |
| Новая единица измерения? | **Нет.** Coarse tile = `fine_cells_per_map_cell` fine-клеток; fine step = 1 по константе движка. |
| Переписать PK `map_cells`? | **Не в v1.** Typed layer в Python; БД пока `int`. |

### 1.4 Целевая модель (3 space, по ТЗ)

```
WORLD_SURFACE_GRID     gx, gy          индекс тайла; span = fine_cells_per_map_cell
WORLD_FINE_GRID        x, y, z         fine grid мира (outdoor settlement, nodes, gates)
LOCATION_FINE_GRID     x, y, z         относительно origin локации (interior, passages) — v2
```

**v1 scope:** первые два space + convert hub.  
**v2:** `LOCATION_FINE_GRID` когда interior persist без принудительного `translate_layout` в world meters.

---

## 2. Архитектурное решение

### 2.1 Паттерн (industry standard)

- **CoordinateSpace** — enum *роли* (не enum на значении координаты).
- **Typed wrappers** — `NewType` или frozen dataclass; не `GridX(IntEnum)`.
- **Convert hub** — единственный модуль, где `int` ↔ typed; planners не делают `// map_cell_fine_span` inline.
- **Explicit boundaries** — DB/API отдают `int` → сразу wrap/validate.

Refs: Python [NewType](https://docs.python.org/3/library/typing.html#newtype), phantom/frame types ([SpaceTypes](https://github.com/barneydellar/SpaceTypes), [spatial-typestate](https://docs.rs/spatial-typestate/latest/spatial_typestate/)).

### 2.2 Модульная структура

```
backend/app/application/worldData/generators/coordinates/
  __init__.py          # re-export public API
  space.py             # CoordinateSpace StrEnum
  types.py             # SurfaceGridCoord, FineGridCoord, NewTypes
  convert.py           # meters_to_grid, grid_origin_m, map_cell_fine_span wrapper
  rect.py              # SurfaceGridRect, FineGridRect
```

`planner/footprint.py` становится **facade** над `coordinates/` (deprecated aliases на 1 релиз, потом удалить дубли).

### 2.3 API (целевой)

```python
class CoordinateSpace(StrEnum):
    WORLD_SURFACE_GRID = "world_surface_grid"
    WORLD_FINE_GRID = "world_fine_grid"
    LOCATION_FINE_GRID = "location_fine_grid"  # v2

GridX = NewType("GridX", int)
GridY = NewType("GridY", int)
FineX = NewType("FineX", int)
FineY = NewType("FineY", int)
FineZ = NewType("FineZ", int)

@dataclass(frozen=True, slots=True)
class SurfaceGridCoord:
    gx: GridX
    gy: GridY

@dataclass(frozen=True, slots=True)
class FineGridCoord:
    x: FineX
    y: FineY
    z: FineZ

@dataclass(frozen=True, slots=True)
class SurfaceGridRect:
    gx0: GridX
    gy0: GridY
    gx1: GridX  # exclusive
    gy1: GridY

@dataclass(frozen=True, slots=True)
class FineGridRect:
    x0: FineX
    y0: FineY
    x1: FineX  # exclusive
    y1: FineY
    z: FineZ

def map_cell_fine_span(world: World) -> int: ...

def fine_to_grid_x(x: FineX, map_cell_fine_span: int) -> GridX: ...
def grid_tile_origin_x(gx: GridX, map_cell_fine_span: int) -> FineX: ...

def settlement_grid_rect(world, settlement) -> SurfaceGridRect: ...
def settlement_fine_rect(world, settlement) -> FineGridRect: ...
def settlement_origin_fine(settlement) -> FineGridCoord: ...  # z = map_z
```

**Правило:** planner-функции принимают/возвращают typed coords или rects; `int` только внутри `convert.py` и при записи в ORM.

### 2.4 Persist / MapCell

**v1 (без migration):**

- Generators emit typed → **flatten to int** только в persist layer.
- `collect_map_cells_from_layout` **не смешивает** spaces в одной куче без нормализации:
  - **Option A (рекомендуется):** occupancy остаётся grid; geometry cells — meters; persist в **разные** upsert batches или с runtime tag в service (не в PK).
  - **Option B:** occupancy при persist конвертировать в meter-origin угла тайла `(gx * map_cell_fine_span, gy * map_cell_fine_span)` — тогда все `MapCell` outdoor в meters, terrain eager тоже должен перейти на meters.

**Решение для v1:** **Option A** + документ «two tables mentally»; подготовить Option B как Phase 5.

**v2 (migration, опционально):**

- Колонка `coordinate_space TEXT` на `map_cells` или convention: `system_terrain` surface vs `system_building_element` implies space.
- Validator при import world JSON.

---

## 3. Фазы имплементации

### Phase 0 — Decision lock ✅ (этот документ)

- [x] Imperial вне scope coordinate fix
- [x] Typed space, не IntEnum на x/y
- [x] v1: GRID + WORLD_FINE_GRID
- [x] User review / approve plan

### Phase 1 — Convert hub (no behavior change) ✅

**Цель:** typed API существует; smoke `map_x=0` зелёный.

| Шаг | Действие |
|---|---|
| 1.1 | ✅ `generators/coordinates/` (space, types, convert, rect) |
| 1.2 | ✅ `map_cell_fine_span`, `grid_dimension`, convert — в hub; sizing/gates — в `footprint.py` |
| 1.3 | ✅ `settlement_grid_rect`; `footprint_grid_rect` = deprecated alias → `.as_tuple()` |
| 1.4 | ✅ `settlement_fine_rect`; `footprint_fine_rect` = deprecated alias |
| 1.5 | ✅ `debug_settlement.py` exit 0 |

**Acceptance:** все текущие тесты exit 0; mypy/pyright на `coordinates/` без ошибок.

**Refactor safety:** grep все call sites `footprint_*`, `settlement_origin` перед rename.

### Phase 2 — Smoke с `map_x ≠ 0` ✅

**Цель:** поймать NC-1 регрессией.

| Шаг | Действие |
|---|---|
| 2.1 | ✅ `test_coordinate_spaces_anchor_3000()` в `debug_settlement.py` |
| 2.2 | ✅ Town `map_x=3000`: grid `(1,0,2,1)`, meters `(3000,0,6000,3000,0)` |
| 2.3 | ✅ District `origin_x=3000`; city 2×2 origins `(3000|6000, 0|3000)` |
| 2.4 | ✅ Gates в метрах: x=`3000|6000`, y=`0|3000` (не anchor `(0,0)`) |

**Acceptance:** assert typed rects; document expected values in test.

### Phase 3 — Fix terrain footprint ✅

**Цель:** `TerrainGeneratorService` согласован с meter anchor + `settlement_grid_rect`.

| Шаг | Действие |
|---|---|
| 3.1 | ✅ footprint через `settlement_grid_rect`; удалён `_get_city_radius` expand |
| 3.2 | ✅ Voronoi `city_centers` в grid index (`meters_to_grid_*`) |
| 3.3 | ✅ bbox fallback anchors → grid index |
| 3.4 | ✅ `test_phase_3_terrain_footprint()` — anchor 0, 3000, city 2×2, `cell_m=5000` |

**Acceptance:** terrain urban cells == `settlement_grid_rect` == occupancy grid cells.

### Phase 4 — `collect_map_cells_from_layout` contract ✅

**Цель:** не смешивать spaces silently.

| Шаг | Действие |
|---|---|
| 4.1 | ✅ `collect_surface_grid_cells(layout)` — occupancy only |
| 4.2 | ✅ `collect_geometry_fine_cells(layout)` — buildings + barriers |
| 4.3 | ✅ `collect_map_cells_from_layout` = concat + log counts per space |
| 4.4 | ✅ `needs_settlement_geometry` — только `system_building_element` в meter rect |
| 4.5 | ✅ `test_phase_4_collect_map_cells()` |

**Acceptance:** lazy settlement smoke; `SettlementGeneratorService` logs `surface_grid` / `meter_geometry`.

### Phase 5 — Planner migration (incremental) ✅

Migrate callers to typed API (order = dependency):

1. ✅ `mapOccupancy.py` — `settlement_grid_rect`, `settlement_origin_fine`, `CoordinateSpace` log
2. ✅ `districts.py`, `districtSlot` docstrings — `coarse_cell_fine_xy`
3. ✅ `streets.py` — WORLD_FINE_GRID docstrings on nodes/grid
4. ✅ `barriers.py`, `areaBarriers.py`, `areaSlots.py`
5. ✅ `layoutTranslate.py` — `FineDelta` on dx/dy
6. ✅ `TerrainGeneratorService` (Phase 3)
7. ✅ `layoutCells.py`, `settlementAssembler.py`, `footprint.py` cell_in → rect helpers

**Acceptance:** `// cell_m` only in `coordinates/convert.py` ✅

### Phase 6 — Product docs (`docs/`) ✅

**Цель:** один источник правды для мастера мира.

Обновлён **`docs/tz_terrain_generation.md`** § coordinate spaces, footprint, terrain vs settlement.

**Acceptance:** продуктовый § согласован с кодом Phase 1–5; противоречия radius / x=1m / map_cells removed.

### Phase 7 — v2 `LOCATION_FINE_GRID` (отложено)

- Interior generator emits location-local
- `translate_layout` → explicit `to_world_meters(origin: FineGridCoord)`
- `location_passages` offset rule из `tz_locations.md` § coordinate bridging

---

## 4. Правила для агента / PR

1. **refactor-safety.mdc** — grep перед rename/delete.
2. Convert только в `coordinates/convert.py`.
3. Не добавлять `measurement_system` в generators.
4. Новые planner API — typed coords; не расширять «голый int» контракт.
5. Smoke обязателен: `map_x=0` **и** `map_x=3000` после Phase 2.
6. Планы — только `.cursor/plans/`; продукт — только `docs/`.

---

## 5. Риски и mitigations

| Риск | Mitigation |
|---|---|
| Typed layer только mypy, runtime mix возможен | Explicit constructors at boundaries; code review; smoke anchor 3000 |
| Big-bang refactor | Phased; re-export aliases in `footprint.py` |
| DB PK не знает space | Phase 4 split collect; Phase 5 Option B — отдельное решение |
| Terrain + settlement разные команды | Phase 3 explicit; grid rect shared test vectors |
| Over-engineering NewType per axis | Start with dataclass packs; add NewType per axis if needed |

---

## 6. Out of scope

- Imperial conversion in generators
- `fine_cells_per_map_cell` regen UX (отдельное ТЗ)
- Hex grid / organic footprint (Phase G settlement)
- Full `coordinate_space` DB column (v2 optional)

---

## 7. Checklist «готово»

- [x] `generators/coordinates/` merged
- [x] Smoke `map_x=0` + `map_x=3000`
- [x] Terrain footprint aligned
- [x] `collect_map_cells` split / documented
- [x] No `// map_cell_fine_span` outside convert hub
- [x] `docs/tz_terrain_generation.md` updated (Phase 6)
- [ ] NC-1 в `settlement-assembler-done.md` → status ✅ with link here

---

## 8. Связь с polish backlog

Полный registry: [docs/tz_generator_technical_debt.md](../docs/tz_generator_technical_debt.md)
