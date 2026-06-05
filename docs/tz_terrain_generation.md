---
name: tz-terrain-generation
description: "ТЗ генерации terrain — архитектура TerrainGeneratorService, три кейса (eager/lazy/repair), слои инициализации"
metadata: 
  node_type: memory
  type: project
  originSessionId: 633eddca-8d16-4119-94ab-ef548d071851
---

## Назначение

`TerrainGeneratorService` — чистая утилита (pure stateless, нет репозиториев, нет async).
Принимает `(World, list[NamedLocation])` → возвращает `list[MapCell]`.
Импортируется напрямую, в контейнер не идёт.

**Why:** Генератор нужен и в worldData (eager), и в engine-нодах (lazy/repair).
Если сделать сервисом с инъекцией — нужно тащить в контейнер и в контекст движка.
Как утилита — импортируется везде без зависимостей.

---

## Три кейса использования

### 1. Eager init (не gameplay, admin)

**Триггер:** импорт бандла мира без `map_cells`.

**Три шага (по ТЗ локаций):**
1. **Surface** — heightmap; 1 ячейка на (x,y) для каждой named_location
2. **Структурные объекты** — здания, заборы, стены, деревья, камни (ячейки выше surface z); используют `building_template_registry` + `barrier_template_registry`
3. **Буфер ±10z** — все ячейки в диапазоне `[min_z − 10, max_z + 10]` для каждой named_location; покрывает мелкие подвалы, высокие постройки, первый уровень подземелья

**Flow:**
```
POST /worlds/{world_uid}/terrain/generate
  └─ MapCellService.ensure_surface(world_uid)
       ├─ get_by_world() → есть ячейки? → skip
       └─ TerrainGeneratorService.generate_surface(world, locations)   ← шаг 1
            + StructureGeneratorService.generate_structures(...)         ← шаг 2 (будущее)
            + TerrainGeneratorService.generate_buffer(...)               ← шаг 3 (будущее)
            └─ MapCellService.save_generated(cells)
```

`WorldBundleService.import_bundle()` остаётся чистым — только импорт данных.
Terrain generation вызывается отдельным endpoint'ом.

---

### 2. Lazy init (gameplay, нода движка)

**Триггер:** игрок движется в регион без `map_cells`.

**Единица генерации — z-срез** (все (x,y) на одном z), не поячеечно. Движок генерирует z-срез целиком при первом входе на него.

**Приоритет:**
- Активная локация (куда идёт игрок) → **блокирующая** генерация (нода ждёт)
- Соседние локации → фоновая, отложено до v2

**Flow:**
```
MovementNode / AreaLoadNode
  ├─ context["map_cell_repo"].get_z_slice(world_uid, x, y, z) → пусто?
  └─ TerrainGeneratorService.generate_z_slice(world, locations, z)
       └─ context["map_cell_repo"].upsert_bulk(cells)  ← блокирует до завершения
```

Нода сама отвечает за персистенс через `context["map_cell_repo"]`.

---

### 3. Broken location repair (gameplay, нода движка)

**Триггер:** в активной сессии обнаружена named_location без единой map_cell.

**Источник:** ТЗ локаций — orphan-tolerant design: локация существует нарративно, физики нет.

**Flow:**
```
SceneInitNode / MovementNode
  ├─ Обнаружена локация без ячеек
  └─ TerrainGeneratorService.generate_minimal(world, location)
       └─ context["map_cell_repo"].upsert(minimal_cells)
       → продолжает выполнение как будто ничего не было
```

`generate_minimal` создаёт 1 surface cell для локации — минимальная физическая точка присутствия.

---

## Два уровня sourcing'а ячеек города

Ячейки города могут поступать из двух источников. Приоритет — всегда у явных.

### 1. Явные (canonical) — из fixture / DB

`map_cells` с `location_uid = city_uid` в фикстуре или БД — **каноническая форма** города.  
Город может иметь любую форму: L-образную, вдоль дороги, с дырами, с выступами.  
Явные ячейки не перезаписываются генератором — они источник истины.

**Правило:** перед генерацией сервисный слой проверяет, у каких городов уже есть ячейки в DB,  
и передаёт их в генератор как `skip_location_uids: set[str]`.

```python
# API endpoint / MapCellService, до вызова генератора:
cities_with_cells = await map_cell_repo.get_location_uids_with_cells(world_uid)
cells = generator.generate_surface(world, locations, skip_location_uids=cities_with_cells)
```

```python
# Генератор — подпись:
def generate_surface(
    self,
    world: World,
    locations: list[NamedLocation],
    padding: int = 2,
    skip_location_uids: set[str] = frozenset(),
) -> list[MapCell]:
```

Город из `skip_location_uids` исключается из `city_footprint` (его footprint не генерируется),  
но **остаётся в `city_centers`** — для Voronoi назначения климата/terrain вокруг него.

### 2. Сгенерированные (fallback) — квадратный footprint

Применяется, когда у города нет явных ячеек.  
Алгоритм: квадрат N×N ячеек вокруг `(map_x, map_y)`, где `N = 2×radius + 1`.  
`radius` берётся из `world.city_size_registry[city.city_size]["radius"]`.

```
city_size_registry:
  hamlet/village → radius=0  →  1 ячейка
  town/city      → radius=1  →  3×3 = 9 ячеек
  metropolis     → radius=2  →  5×5 = 25 ячеек
  megalopolis    → radius=3  →  7×7 = 49 ячеек
```

Это **v1** — первый вариант. Будут добавлены другие алгоритмы (см. раздел "Будущие алгоритмы генерации").

---

## Алгоритм generate_surface (v1, fallback)

Города используют реальные координаты (`map_x`, `map_y`, `map_z`) из БД — генератор их не вычисляет.
Климат влияет только на terrain и температуру окружающих ячеек, не на позиционирование.

### Шаги:

1. **Найти anchors** — named_locations с `map_z IS NOT NULL` и `is_mobile=False`
2. **Построить city_footprint** — для каждого города (типы: city/town/village/camp) из `skip_location_uids`:
   - Если город есть в `skip_location_uids` → пропустить footprint (явные fixture-ячейки)
   - Иначе → квадрат N×N ячеек вокруг `(map_x, map_y)`, `N = 2 × radius + 1`
   - `radius` из `world.city_size_registry[city.city_size]["radius"]`
3. **Bounding box** — от крайних ячеек footprint + `padding=2`
4. **Заполнить grid** — для каждой `(x, y)` в bounding box:
   - `(x,y)` в city_footprint → `terrain="urban"`, `z=city.map_z`, `location_uid=city.uid`
   - иначе → климат от ближайшего города (Voronoi по центрам городов), `z = base_z(climate) + noise(x, y)`, terrain от z
5. **Добавить non-surface anchors** — шахты, подземные города и т.д. (те что не city-type): одна ячейка на `(map_x, map_y, map_z)`

### Voronoi для климата:
Каждая terrain-ячейка берёт климат ближайшего города по евклидову расстоянию до `(map_x, map_y)`.
Зона (region/kingdom) города используется как источник `climate_zone` если у самого города его нет.
Все города (в т.ч. из `skip_location_uids`) участвуют в Voronoi — явные ячейки не мешают климату.

### Noise (детерминированный, без random):
```python
h = (world_seed ^ (x * 73856093) ^ (y * 19349663)) & 0xFFFFFFFF
noise = (h % (2 * amplitude + 1)) - amplitude  # amplitude=1
z = base_z + noise
```
Один и тот же `world_uid` + те же локации → та же карта.

### Terrain от z:
| z | terrain |
|---|---------|
| ≥ 2 | tundra |
| 1 | forest |
| 0 | plains |
| ≤ -1 | water |

Проверяется против `world.terrain_registry` — fallback на "plains" если тип отсутствует.

### Climate → base_z:
| climate | base_z |
|---------|--------|
| arctic / tundra / subarctic | 3–4 |
| cold / cold_temperate | 1–2 |
| temperate / continental | 0 |
| subtropical / coastal / maritime / tropical | -1 |

### Температура (упрощённая, v1):
```
temperature_base = climate_base_temp - z × lapse_rate
lapse_rate = world.elevation_lapse_rate или 7.0
```
Финальная формула с сезонами и вариацией — отложена (см. "Не покрыто").

---

## Будущие алгоритмы генерации (v2+)

Текущий v1 (квадратный footprint) — заглушка. Планируемые варианты:

| Алгоритм | Когда | Принцип |
|---|---|---|
| **Road-following** | Город вдоль дороги | Ячейки вдоль дорожной сети, ширина от city_size |
| **Voronoi-based** | Крупные города с районами | Воронои внутри footprint → разные district_uid на ячейках |
| **Organic growth** | Исторические поселения | Случайный рост от центра с учётом рельефа (noise + walkability) |
| **Coastline** | Портовые города | Footprint обрезается по береговой линии; доки у воды |
| **LLM-assisted** | Нарративные города | Запрос к LLM с описанием города → список ячеек как JSON |

Все алгоритмы работают внутри `TerrainGeneratorService` (pure, без IO).  
Выбор алгоритма — параметр, или через `location_subtype`, или через world-level настройку.

---

## Расположение в проекте

```
app/application/worldData/
    terrainGeneratorService.py   ← pure utility, прямой import

app/application/engine/nodes/pojo/python/
    movementNode.py              ← lazy init + broken repair (будущее)

app/api/routes/
    worlds.py                    ← POST /worlds/{uid}/terrain/generate
```

---

## Система координат

**x = y = z = 1м на ячейку** — единая шкала без конвертаций.

- Расстояние в координатах = расстояние в метрах напрямую
- Этаж здания = 3 z-юнита (3м потолок — документированная конвенция, не хранится)
- Дверь = 2 z-юнита высотой
- World surface cell = `map_cell_size_m` ячеек по каждому измерению (кратное 1000, все делятся на 1 без остатка)
- Эверест = z=8849, Марианская впадина = z=-11000 — хранятся напрямую в метрах

**Почему не 3м на z:** рендера нет, кубичность не важна. 1:1 — проще.

**Температурная формула (когда будем реализовывать):**
```
temperature = climate_base_temp - elevation_lapse_rate × (z / 100)
```
`elevation_lapse_rate` в °C на 100м, z в метрах — прямое применение.

---

## Многослойные локации на одной (x, y) клетке

map_cells PK = `(world_uid, x, y, z)` — разные z не конфликтуют. Вертикальное стекирование валидно:
- Город на поверхности: ячейка at z=0
- Шахта: ячейка at z=-20
- Подземный город: ячейка at z=-1000
- Парящий остров (фикс.): ячейка at z=1000

### Новые поля на `named_locations`

**`map_x: int | None`**, **`map_y: int | None`** — позиция на глобальной карте.  
**`map_z: int | None`** — базовый z (нижняя граница footprint); null у нарративных (continent, region) и мобильных.  
**`is_mobile: bool = False`** — локация может менять положение; статический якорь не создаётся.

### Правило генератора Step 1

```python
# Якорная ячейка создаётся только если:
if location.map_z is not None and not location.is_mobile:
    create anchor cell at (map_x, map_y, map_z)
```

| Локация | `map_z` | `is_mobile` | Якорь |
|---|---|---|---|
| Город на поверхности | `0` | `false` | ✓ |
| Шахта | `-20` | `false` | ✓ |
| Подземный город | `-1000` | `false` | ✓ |
| Парящий остров (фиксированный) | `1000` | `false` | ✓ |
| Парящий остров (дрейфующий) | `null` | `true` | ✗ |
| Корабль-город | `null` | `true` | ✗ |

### Мобильные локации

Внутренность мобильной локации (каюты, палубы, трюм) — валидные `named_locations` с иерархией и interior-ячейками. Существуют независимо от глобальной позиции.

Глобальная позиция — runtime атрибут, не статика в map_cells:

```sql
mobile_location_positions (
    location_uid   TEXT PRIMARY KEY,  -- FK → named_locations
    world_uid      TEXT NOT NULL,
    x              INTEGER NOT NULL,
    y              INTEGER NOT NULL,
    z              INTEGER NOT NULL,
    updated_at     TEXT NOT NULL
)
```

Стыковка: когда корабль в порту → создаётся `location_entry_point` как временная связь с портом. Когда отплыл → запись убирается.

Реализация `mobile_location_positions` отложена — фиксируется как архитектурный задел.

---

## DB — индексы

По ТЗ локаций, для lazy init нужен дополнительный индекс:
```sql
CREATE INDEX idx_map_cells_location_z ON map_cells (world_uid, location_uid, z);
```
Основной PK `(world_uid, x, y, z)` — для точечных запросов.
Дополнительный `(world_uid, location_uid, z)` — для z-срезов по локации при lazy init и загрузке сцены.

---

## Подсистемы генерации по типу локации

При инициализации (Step 1 + Step 2) генератор может делегировать логику подсистемам в зависимости от `location_type` / `location_subtype`. Архитектура — стратегия/плагин:

```python
_LOCATION_GENERATORS: dict[str, type[LocationSubGenerator]] = {
    "mine":       MineGenerator,    # тоннели, рудные жилы, крепёжные балки
    "cave":       CaveGenerator,    # органичные формы, сталактиты, подземные озёра
    "cave_system":CaveSystemGenerator, # сеть пещер с переходами
    "dungeon":    DungeonGenerator, # коридоры, комнаты, ловушки
    # ... добавляются по мере реализации
}

def generate_anchor(location, world) -> list[MapCell]:
    gen_cls = _LOCATION_GENERATORS.get(location.location_type)
    if gen_cls:
        return gen_cls().generate(location, world)
    return _default_anchor(location, world)
```

**Примеры будущих подсистем:**

| Тип | Подсистема | Особенности |
|---|---|---|
| `mine` | MineGenerator | Вертикальные шахты, горизонтальные штреки, ore_vein nodes |
| `cave` | CaveGenerator | Неправильные формы, сталактиты/сталагмиты, озёра |
| `cave_system` | CaveSystemGenerator | Сеть пещер с location_passages между ними |
| `dungeon` | DungeonGenerator | BSP/combs разбивка на комнаты, коридоры |
| `crevice` | CreviceGenerator | Линейный разлом, gap_width, depth |
| `lake` / `river` | WaterBodyGenerator | Форма водоёма, depth по z, прибрежные ячейки |

Каждая подсистема — отдельный pure class, реализует интерфейс `LocationSubGenerator.generate(location, world) → list[MapCell]`. Добавляется в реестр без изменения основного генератора.

---

## Не покрыто (пробелы)

| Элемент | Статус |
|---|---|
| `skip_location_uids` в `generate_surface` | ✓ Реализовано: параметр в генераторе, `get_location_uids_with_cells` в репозитории, вызов из endpoint. `INSERT OR IGNORE` защищает явные ячейки. |
| Шаг 2 eager: структурные объекты | Отложено; требует `building_template_registry` + `barrier_template_registry` |
| Шаг 3 eager: буфер ±10z | Отложено; алгоритм прост (расширение после step 1), реализуется после структур |
| location_resources генерация | Не реализовано; явно в "Открытых вопросах" ТЗ локаций |
| location_levels | Отдельный слой; создаётся при генерации здания; заглушка `level_uid=None` в SceneStartLocationSelectNode |
| location_passages | Отдельный слой; создаётся вместе с location_levels |
| location_entry_points | Отдельный слой; точки входа в здания/подземелья |
| Температурная формула | Пока не трогаем; ТЗ требует `zone.base_temp - lapse_rate × (z×3/100) + neighbor_blend + variance` |
| world_map_version пересчёт | После генерации обновлять хеш |
| Фоновая генерация соседей | Отложено до v2; требует многопоточности |

## Многопоточность — задел на мультиплеер

Цель: архитектура работает сейчас (SQLite, single-user), масштабируется на мультиплеер без смены кода нод. Позже — полная миграция на PostgreSQL.

### Инварианты, которые обеспечивают это:

**1. Детерминированный генератор**
Одни и те же входы (`world_uid` + локации) → всегда одни и те же ячейки.
Два игрока триггерят lazy init одной зоны одновременно → оба записывают идентичные данные → `upsert` делает это безопасным. Application-level локи не нужны.

**2. Upsert-семантика**
`map_cell_repo.upsert()` — конкурентные записи одинаковых данных не конфликтуют.
SQLite: `INSERT OR REPLACE`. PostgreSQL: `ON CONFLICT DO UPDATE`. Ноды не знают разницы.

**3. IRepository-интерфейсы**
Ноды работают только с `IMapCellRepository`, `IWorldRepository` и т.д.
Миграция на PostgreSQL = свап impl в `container.py`. Ноды не трогаем.

**4. Фоновая генерация соседей — `asyncio.create_task()`**
```python
# в ноде, не блокирует основной pipeline:
asyncio.create_task(generate_neighbor_zones(...))
```
Работает и с SQLite WAL, и с PostgreSQL без изменений в ноде.

### Что НЕ делать:
- Не класть SQL-специфичный код в `TerrainGeneratorService` (он pure — уже соблюдено)
- Не добавлять `threading.Lock` или глобальный мутабельный state — PostgreSQL управляет конкуренцией на уровне транзакций
- Не делать генерацию cell-by-cell в цикле с отдельным commit на каждую — использовать `upsert_bulk` в одной транзакции

### SQLite сейчас:
WAL mode: concurrent readers + один writer. Для single-user достаточно.
Если мультиплеер придёт раньше PostgreSQL — включить WAL и принять ограничение одного writer'а как временное.

---

## Масштаб и иммутабельность координат

| Пространство | Единица | Хранение | Мутабельность |
|---|---|---|---|
| Глобальная карта (`map_cells`) | `map_cell_size_m` метров | `worlds.map_cell_size_m` | Мутабелен — изменение требует регенерации |
| Interior (`location_levels`) | `INTERIOR_CELL_SIZE_M = 1` м | `app/core/constants.py` | **Иммутабелен** — движковая константа |

### Регенерация при изменении `map_cell_size_m`

**Триггер:** `WorldService.update()` — старое значение `map_cell_size_m` ≠ новому.

**Поведение (не реализовано):**
1. Предупредить пользователя: "Изменение масштаба карты удалит все map_cells. Продолжить?"
2. При подтверждении: `MapCellService.clear(world_uid)` → все map_cells удалены
3. Карта считается неинициализированной — следующий вызов `POST /worlds/{uid}/map/generate-surface` пересоздаёт её с новым масштабом

**Реализация:** отдельная задача. Потребует:
- Сохранить старое значение перед `setattr`
- Детектировать изменение
- Вернуть предупреждение из `update()` или добавить `?force=true` флаг на endpoint

---

## Открытые вопросы

- `generate_z_slice(bounds)` — API для lazy init: по bounding box или по `location_uid + z`? Решать при реализации lazy init ноды.
- Слои interior (location_levels, passages, objects) — часть `TerrainGeneratorService` или отдельная система? Решать при реализации зданий.
- Регенерация при изменении `map_cell_size_m` — механика подтверждения: предупреждение в теле ответа или `?force=true` флаг?
