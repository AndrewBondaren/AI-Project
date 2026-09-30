# ТЗ: Иерархия ассемблеров

## 1. Структура

```
SettlementAssembler
    └── DistrictAssembler
            └── StructureAreaAssembler
                    └── BuildingAssembler                  # здание целиком: контекст + оркестрация
                            └── домен structure           # геометрия: geometry / foundation / roof (interior = наполнение, другой слой)
                                    └── StructureInteriorAssembler
```

Каждый слой самодостаточен. Вход в иерархию — на нужном уровне.

---

## 1.1 Архитектурный принцип: semantic-first generation

`economic_tier` — это **семантический дескриптор намерения**, а не конфигурация конкретных деталей. Разработчик описывает *что* (бедный район, богатый квартал), генератор сам разворачивает из этого *как*:

- материал дороги и покрытие
- тип и плотность освещения
- ширина тротуара, наличие бордюра
- тип и качество забора
- шаблон здания из `building_template_registry`

Этот принцип действует на всех уровнях иерархии. Ни один слой не хардкодит конкретные значения — все детали резолвятся через реестры по тиру и стилю.

---

## 2. Слои

### SettlementAssembler
**Знает:** city skeleton (в т.ч. барьер **поселения**); шаблон каждого района (`density`, барьер **района**) — `entry_nodes` / `DistrictSlot`  
**Делает:**
- занимает ячейки карты мира под поселение
- планирует поселение на ячейках; понимает топологию по z (наземный / подземный / воздушный — одновременно)
- управляет топологией соединения ячеек поселения между собой (улицы, мосты, тоннели)
- городская сетка и `DistrictSlot`; вычет прямых барьера **поселения** (`footprint ∩ слот`) из площади района; `entry_nodes` (шаг района, на урезанном слоте). Барьер поселения → `SettlementLayout.barrier_cells` (прямые footprint). Участки сажает `DistrictAssembler`

**Подробнее:** [tz_city_generation.md](tz_city_generation.md)

### DistrictAssembler
**Знает:** тип квартала, city skeleton, **фактический размер участка** (из cache оболочек, packing)  
**Делает:**
- вызывается несколько раз на каждой ячейке города — формирует несколько районов на одной ячейке
- управляет топологией соединения районов между собой
- **сажает** `AreaSlot` в **2D-бин** модуля: cache → бронь приоритетных → рамка вокруг → проход 2 → граф улиц после
- назначает шаблон слоту по `structure_type` + `economic_tier`
- имеет собственный шаблон типа района
- улицы: рамка после брони приоритетных, полотно после всей посадки; генератор улиц не ставит слоты

**Не делает:** не выравнивает **участки** (и здания на них) под одну плоскость; `ground_z` и порог считает `StructureAreaAssembler` (outdoor **C21**). Не кладёт дверь дома. Не отдаёт участку чужие рёбра.

**C22 (район):** city §6.3. **`PerimeterBarrier` района** — прямые **уже урезанного** `DistrictSlot`; packing вычитает их из слота; клетки `DistrictLayout.barrier_cells` (TODO). Барьер поселения — другой инстанс: вычет из площади района делает `SettlementAssembler` **до** этого слоя. Зоны не пересекаются. Якоря — город. Стены здания — не этот класс. Переход packing — TODO city §6.3. Контракт: connections §5.1.4.

**Подробнее:** [tz_city_generation.md](tz_city_generation.md) — раздел 6 (алгоритм заполнения кварталов)

### StructureAreaAssembler
**Знает:** `AreaSlot` (клетки **участка** + facing), **`PlotLayoutTemplate`** (чертёж участка: footprint, забор, `plot_type`, `economic_tier_band`, `main_building: BuildingBodyTemplate | None`, `secondary_buildings` — stub), `StructureCatalog` (резолв `main_building.structure` → `StructureTemplate`), city skeleton, terrain  
**Владеет зданиями участка:** объявляет `NamedLocation`, резолвит ссылку `structure`, собирает `StructureContext` из полей body + runtime (`facing`, `ground_z`), передаёт `body` + `structure` в `BuildingAssembler`. Ссылка не резолвится → ошибка generate (422), не оболочка.  
**Делает:**
- полностью понимает топологию своей зоны: тип — из шаблона, любое назначение (`structure_type`). Не «всегда жилой дом». Примеры геометрии: здание у улицы; двор+забор+здание в глубине; общественная площадь (`plaza`: сады, фонтаны, террасы); только оболочка, если так задан шаблон
- знает facing area (сторона к улице)
- **решает порог** (где улица стыкуется с участком) — `_resolve_threshold`: дверь / ворота забора / край участка. Формула «всегда фасад здания» запрещена
- при наличии здания: координаты из шаблона, `StructureContext` (`ground_z` = `building.map_z` после clamp), вызов `BuildingAssembler`. Шаблон даёт здание, участок без NL — **ошибка generate**, не пустой двор
- планировка: двор, забор (`barrier_template_registry`), малые постройки
- `_build_paths`: улица → **порог** (не обязательно `building_entrance`); θ > 45° — clamp только z

**Источник `StructureContext`:** этот слой. Только он знает достаточно для вывода контекста и порога.  
**`AreaSlot`:** список (x, y) участка (здание ∪ двор ∪ линия забора) + `ground_z` (**этого** участка) + `facing` + `height` / `z_deep` (пролёт выше / ниже `ground_z`) + `deck` (копия яруса чертежа района). Не копия z района.  
**Подробнее:** [tz_building_generator.md](tz_building_generator.md) — раздел 11 (BuildingAssembler, StructureContext)

### BuildingAssembler
**Знает:** всё об **одном здании**: `BuildingBodyTemplate` (envelope: тип основания/крыши, материалы, porch), `StructureTemplate` (уже резолвнутая ссылка `body.structure`), `StructureContext` (runtime: `facing`, `ground_z`, `building_band`), terrain_cells  
**Делает:** владеет контекстом здания и **управляет** его сборкой — сам ничего не строит, три вызова в домен `structure`:
- геометрия здания (комнаты, стены, проходы, лестницы) → поддомен **structure / geometry** (`StructureGeneratorService`)
- фундамент + крыльцо/ступени → поддомен **structure / foundation** (`FoundationBuilder`)
- крыша → поддомен **structure / roof** (`RoofBuilder`)

Порядок и приоритет перезаписи клеток (staircase > foundation; крыша поверх) — §6.5. **Не** знает участок, **не** резолвит ссылки, **не** наполняет интерьер, **не** персистит  
**В коде:** ABC `BaseBuildingAssembler` + `BUILDING_ASSEMBLER_REGISTRY` (kind → класс: `building` → **`BuildingAssembler`**, `ruins`, `vastHull`, `resourceExtraction`; kind = вид здания, ≠ `structure_type` и ≠ `system_name`). `assemble` = три вызова выше; `attach_envelope` — фундамент + крыша поверх готового layout. Сигнатура §6.5 — контракт ABC для всех kind. Выбор kind по чертежу участка — не в v1: area зовёт `BuildingAssembler`  
**Может быть вызван вне иерархии** — для кораблей, данжей и других структур, способных к перемещению (`is_mobile=true`).  
**Подробнее:** [tz_building_generator.md](tz_building_generator.md) — раздел 11

### Домен `structure` — геометрия здания (три поддомена)
Домен производит **клетки и объекты геометрии** по заданию `BuildingAssembler`; ни один поддомен не знает ни участок, ни другие поддомены.

**Не путать:** поддомен `geometry` (комнаты как геометрия) ≠ `interior` — наполнение интерьера (мебель, предметы) делает `StructureInteriorAssembler`, отдельный слой ниже.

| Поддомен | Код | Вход | Выход |
|---|---|---|---|
| geometry | `StructureGeneratorService.generate_from_template` | `StructureTemplate`, `facing`, `building_band`, `ground_z`, `foundation_depth` | геометрия: комнаты (`NamedLocation`), стены, проходы, wall_openings, лестницы — `StructureLayout`. Раскладка в SOUTH-фрейме шаблона, затем rigid-body поворот под `facing` **до** эмиссии |
| foundation | `FoundationBuilder` (`structure/foundation/`) | `StructureContext`, terrain surface, `ground_z`, клетки geometry | клетки фундамента / крыльца; v1-типы §6.7 |
| roof | `RoofBuilder` (`structure/roof/`, `gableRoof.py`) | `StructureContext`, `ground_z`, клетки geometry | клетки крыши; v1-типы §6.7 |

Поддомены foundation / roof — как есть (v1); их развитие — отдельные ТЗ, каркас вызова через `BuildingAssembler` не меняется.  
**Подробнее:** [tz_building_generator.md](tz_building_generator.md) — разделы 3–10 (geometry), 11.2–11.3 (foundation, roof)

### StructureInteriorAssembler
**Знает:** `BuildingLayout` (готовая геометрия), шаблон, world, city skeleton  
**Делает:** наполнение интерьера — мебель, предметы, атмосфера  
- `location_objects`: столы, стулья, кровати, полки, очаги
- стартовый инвентарь комнат и контейнеров
- декор: факелы, ковры, картины

Размещение NPC — **отдельный слой**, не входит сюда.

**Статус:** нет ТЗ; реализуется после системы предметов

---

## 3. Точки входа

| Сценарий | Точка входа |
|---|---|
| Полная городская генерация | `SettlementAssembler` |
| Отдельный квартал | `DistrictAssembler` |
| Здание на участке (ручное размещение, редактор) | `StructureAreaAssembler` |
| Корабль, данж, изолированное здание | `BuildingAssembler` |
| Срез мегаздания (`foundation="none"`, `roof="none"`) | `BuildingAssembler` (foundation/roof → no-op) |
| Наполнение уже сгенерированного здания (предметы, NPC) | `StructureInteriorAssembler` |

---

## 4. Поток данных

```
SettlementAssembler
  city_skeleton → DistrictAssembler
    district_type + template_slot → StructureAreaAssembler
      StructureContext (выводится здесь) → BuildingAssembler
        terrain_cells → terrain_surface[x,y] + ground_z
        context + ground_z + foundation_depth → StructureGeneratorService(ground_z, foundation_depth)
                                                    → StructureLayout (geometry: комнаты, стены, проходы)
        FoundationBuilder(terrain_surface, ground_z) → foundation cells
        RoofBuilder(ground_z)                        → roof cells
        → StructureLayout (полный)
            BuildingLayout + world → StructureInteriorAssembler
                                         → location_objects, инвентарь, декор
```

Нижние слои **не знают** о верхних. `StructureGeneratorService` не знает существует ли город.

---

## 5. Открытые вопросы

| Вопрос | Статус |
|---|---|
| `StructureAreaAssembler` — алгоритм вывода `StructureContext` из `structure_type` + `architectural_style` | не описан |
| `DistrictAssembler` — правила выбора шаблона для слота | частично в [tz_city_generation.md](tz_city_generation.md) раздел 6 |
| Малые постройки на участке (`StructureAreaAssembler`) | нет ТЗ |
| `StructureInteriorAssembler` — алгоритм размещения мебели и предметов | нет ТЗ; зависит от системы предметов |
| Размещение NPC — отдельный слой поверх готового интерьера | нет ТЗ |

---

## 6. Архитектура BuildingAssembler

### 6.1 StructureContext

```python
@dataclass
class StructureContext:
    foundation_type:     str               # "none"|"slab"|"perimeter"|"full"|"stilts"|"hull"
    roof_type:           str | list[str]   # "none"|"flat"|"gable"|"hull"|"auto" или список с приоритетом
    facing:              Facing | None = None  # сторона главного входа; None → определяется шаблоном
    foundation_depth:    int   = 1         # z-юниты вглубь; для "slab"/"hull" — фикс. толщина
    slope_step:          float = 1.0       # shrink за 1 z-юнит; 1.0 ≈ 45°; только для скатных крыш
    foundation_material: str | None = None # fallback: building.parent_wall_material
    roof_material:       str | None = None # fallback: building.parent_wall_material
    porch_material:      str | None = None # fallback: building.parent_floor_material
    porch_has_roof:      bool = False      # навес над крыльцом
    ground_z:            int | None = None # None → building.map_z
    building_band:       str | None = None # economic tier band участка (PlotLayoutTemplate.economic_tier_band); None → tier мира
```

`facing` пробрасывается из `AreaSlot.facing` через `StructureAreaAssembler._derive_context`.
`None` означает что шаблон сам определяет расположение входа (для изолированных структур без улицы) — генератор оставляет SOUTH-фрейм.

`StructureContext` не хранится в `StructureTemplate` — тот описывает только геометрию. Envelope-поля (`foundation_*`, `roof_*`, `porch_*`) — это поля `BuildingBodyTemplate` участка; runtime-поля (`facing`, `ground_z`, `building_band`) — из `AreaSlot` / `PlotLayoutTemplate` / посадки.
Источник сборки: `StructureAreaAssembler._derive_context(body, slot, building)` (city-пайплайн) или ручной выбор в UI.

---

### 6.2 ground_z — уровень земли

**Проблема:** `z = 0` не является уровнем земли. Уровень земли зависит от контекста здания и terrain.

**Определение:**

```
ground_z = context.ground_z ?? building.map_z
```

`building.map_z` — z пола входного этажа (`z_offset=0`), если на участке есть здание. Задаёт **assembler участка**, не район. Может отличаться от `AreaSlot.ground_z` (двор vs дом) и от z порога к улице (ворота vs дверь). Если входной луч даёт **θ > 45°** — править только `map_z` этого здания (опустить или поднять), пока `h = L` (connections **§5.1.2**). **Не** сдвигать дом в xy к улице. Подземный город: `map_z` уже под открытым небом другого слоя. SoT порога: connections §5.1.1, outdoor **C21**.

Явный `context.ground_z` нужен для нестандартных случаев: корабль (нет земли под килем), данж (пол пещеры выше нуля), мегаздание (срез на высоте).

**terrain_surface** — детальная карта поверхности:

```python
terrain_surface: dict[tuple[int,int], int]
# terrain_surface[x, y] = max z среди terrain-ячеек в колонке (x, y)
# вычисляется BuildingAssembler из terrain_cells
# используется FoundationBuilder для расчёта gap[x,y] = building.map_z - terrain_surface[x,y]
```

Для v1: `terrain_surface` используется только в `FoundationBuilder`.
Для v2: `terrain_surface[x, y]` позволяет определять exposed/buried стены на уровне ячейки (например, окно на стороне холма, которая смотрит в землю).

---

### 6.3 Хардкоды z=0 в генераторе — ✅ реализовано

Три места в `StructureGeneratorService` и его подсистемах используют `z = 0` как уровень земли:

| Файл | Место | Статус |
|---|---|---|
| `passages/wallOpening.py:116` | `if level.z < ground_z: return` | ✅ исправлено |
| `passages/staircaseTunnelOrchestrator.py:73` | `if level.z >= self.ground_z:` | ✅ исправлено |
| `staircase/builder.py:60-61` | `fr.z_offset >= 0 and to.z_offset < 0` | не трогать — `z_offset` относителен шаблону, всегда корректен |

`z_offset` в шаблоне (0 = ground floor) — не зависит от абсолютных координат.
`level.z` — абсолютная координата в мире — сравнивать только с `ground_z`.

`ground_z` передаётся через `generate_from_template`:

```python
StructureGeneratorService().generate_from_template(
    world, building, template,
    ground_z=ground_z,          # пробрасывается в wallOpening + tunnelOrchestrator
    foundation_depth=fd,        # пробрасывается в _compute_level_z для z_offset < 0
)
```

---

### 6.4 basement z-shift — ✅ реализовано

При наличии фундамента подвальные уровни располагаются ниже фундаментного слоя.

`_compute_level_z` для `z_offset < 0`:
```
z = building.map_z - foundation_depth - Σ(z_height for z_offset in N..-1)
```

Пример, `foundation_depth=2`, подвал `z_height=3`, `building.map_z=0`:
```
foundation:  z = -2, -1        (фундаментный слой)
basement:    z = -5, -4, -3    (ниже фундамента)
```

При `foundation_type="none"`: `fd=0` → поправка не применяется.

---

### 6.5 Интерфейс BuildingAssembler

Контракт ABC `BaseBuildingAssembler`; ниже — реализация kind `building` (`BuildingAssembler`). Остальные kind (`ruins`, `vastHull`, `resourceExtraction`) обязаны принимать ту же сигнатуру.

```python
@ASSEMBLER_REGISTRY.register("building")
class BuildingAssembler(BaseBuildingAssembler):

    def assemble(
        self,
        world:         World,
        building:      NamedLocation,
        body:          BuildingBodyTemplate,   # envelope: foundation/roof/материалы/porch
        structure:     StructureTemplate,      # резолвнутая body.structure — резолвит caller (area)
        context:       StructureContext,       # runtime: facing, ground_z, building_band
        terrain_cells: list[MapCell] | None = None,
    ) -> StructureLayout:
        ground_z        = context.ground_z if context.ground_z is not None else building.map_z
        terrain_surface = _build_terrain_surface(terrain_cells) if terrain_cells else {}
        fd              = context.foundation_depth if context.foundation_type != "none" else 0

        layout = StructureGeneratorService().generate_from_template(
            world, building, structure,
            ground_z=ground_z,
            foundation_depth=fd,
            facing=context.facing,
            building_band=context.building_band,
        )

        # Работаем с dict для корректной перезаписи (staircase > foundation > roof)
        cells: dict[tuple, MapCell] = {(c.x, c.y, c.z): c for c in layout.cells}

        if context.foundation_type != "none":
            for cell in FoundationBuilder(world, building, context, terrain_surface, ground_z).build(layout):
                if (cell.x, cell.y, cell.z) not in cells:   # staircase-ячейки не перезаписываются
                    cells[(cell.x, cell.y, cell.z)] = cell

        if context.roof_type != "none":
            for cell in RoofBuilder(world, building, context, ground_z).build(layout):
                cells[(cell.x, cell.y, cell.z)] = cell       # крыша всегда поверх

        layout.cells = list(cells.values())
        return layout
```

**Приоритет перезаписи:** staircase (из генератора) > foundation > terrain. Крыша не конфликтует — всегда выше.

---

### 6.6 Файловая структура

```
structure/
  structureContext.py          # StructureContext dataclass
  structureAssembler.py        # Оркестратор
  foundation/
    foundationBuilder.py       # Диспатч по foundation_type; вычисляет gap[x,y]
  roof/
    roofBuilder.py             # Диспатч + авто-резолв roof_type из списка
    gableRoof.py               # Shrink-алгоритм для двускатной крыши
```

`flat`, `hull`, `none` — тривиальны, живут в `roofBuilder.py`.
`gable` — отдельный файл (shrink по короткой оси + конёк).
`stilts`, `hip`, `pyramid`, `mansard`, `battlements` — v2.

---

### 6.7 Scope v1

| Фундамент | Крыша |
|---|---|
| `none` | `none` |
| `slab` | `flat` |
| `perimeter` | `gable` |
| `full` | `hull` |
| `hull` | ~~`auto`~~ — v2 |
| ~~`stilts`~~ — v2 | ~~`hip`, `pyramid`, `mansard`, `battlements`~~ — v2 |

`auto` (анализ coverage/aspect ratio footprint) реализуется вместе с `hip` в v2.

---

### 6.8 Контракт StructureGeneratorService

```python
def generate_from_template(
    self,
    world:            World,
    building:         NamedLocation,
    structure:        StructureTemplate,        # только геометрия; участок/body сервис не видит
    *,
    ground_z:         int | None = None,
    foundation_depth: int        = 0,
    facing:           Facing | None = None,     # None/SOUTH → фрейм шаблона; иначе поворот перед эмиссией
    building_band:    str | None = None,        # → TierResolver.resolve(building_band=…)
) -> StructureLayout: ...
```

Внутри:
1. `ground_z = ground_z if ground_z is not None else building.map_z`
2. `_compute_level_z`: для `z_offset < 0` вычитать `foundation_depth`
3. `place_wall_openings(... ground_z=ground_z)` — `level.z < ground_z`
4. `StaircaseTunnelOrchestrator(... ground_z=ground_z)` — `level.z >= ground_z`
5. После раскладки (`layoutEngine`) и до эмиссии `NamedLocation`/клеток/passages — `rotate_instances(rooms, shafts, facing)`: rigid-body поворот вокруг origin входной комнаты, стена главного входа → `facing`, `width↔depth` при 90°/270° (building §8.6)
6. `building_band` подставляется в каждый `TierResolver.resolve(...)` сервиса; сам сервис band не выводит (нет доступа к участку)

Сервис **не** принимает `dict` и **не** разворачивает участок (`coerce_building_layout`/`interior_of` удалены): bare JSON валидируется `StructureTemplate.model_validate` у caller.

---

## 7. Архитектура StructureAreaAssembler

### 7.1 Контракты и типы данных

**`CitySkeleton`** — поля скелета города, передаются сверху вниз по всей иерархии:

```python
@dataclass
class CitySkeleton:
    economic_tier:        EconomyTierKey | None
    architectural_style:  str | None   # ref → worlds.architectural_style_registry (POJO нет)
    dominant_material:    MaterialKey | None
    settlement_density:   DistrictDensity | None
    system_city_size:     SettlementSizeKey | None
    system_location_mood: LocationMoodKey | None
    frontage_type_order:  list[ConnectionTypeKey] | None  # C22; null = дефолт движка; POJO-C-5
    plot_counts:          dict[DrawingKey, int] | None
    plot_priority:        dict[DrawingKey, int] | None
    perimeter_barrier:    PerimeterBarrier | None
```

Источник данных: поля `NamedLocation` поселения. Собирается `SettlementAssembler` и передаётся вниз без изменений.

C22-поля: перечень и persist — [tz_city_generation.md](tz_city_generation.md) §3 (`⬜` в коде). Резолв N / очереди / фасада — [tz_structure_connections.md](tz_structure_connections.md) §5.1.3 (не дублировать таблицы здесь). Типы ключей фасада — [tz_pojo_city_typing.md](tz_pojo_city_typing.md) **POJO-C-5**. Район перекрывает город **по ключу** (`district_template`) для counts/priority/frontage. `perimeter_barrier` на скелете — барьер **поселения** (прямые footprint), не района. `display_location_mood` / `state_uid` — city §3; в этот dataclass не входят (`state_uid` ⬜ в скелете отдельно).

---

**`AreaSlot`** — участок, выделенный `DistrictAssembler` (не синоним здания):

```python
@dataclass
class AreaSlot:
    cells:    list[tuple[int, int]]   # (x, y) участок из шаблона, любой structure_type; без z
    ground_z: int                      # опорная плоскость ЭТОГО участка (не порог улицы сам по себе)
    facing:   Facing                   # сторона участка к улице
    height:   int                      # fine cells выше ground_z; packing 0
    z_deep:   int                      # fine cells ниже ground_z; packing 0
    deck:     int                      # копия DistrictTemplateEntry.deck; 0 = поверхность
```

`ground_z` — онтология **участка**, не района. Район не копирует одну z на слоты. Как считать z и **где порог к улице** — только `StructureAreaAssembler` (топология зоны). SoT порога: [tz_structure_connections.md](./tz_structure_connections.md) §5.1.1. Склейка: [tz_settlement_outdoor.md](./tz_settlement_outdoor.md) **C21**. `DistrictSlot.ground_z` — пин района, не пол участка.

`facing` — сторона участка к улице. Калитка / край порога на этой грани. Ось смотрит на **`main_building`**: улица → калитка или `parcel_edge` → двор → вход главного дома. Пристройки ось не задают. Что именно на грани (дверь, ворота, открытый край) решает assembler участка.

`height` — вертикальный пролёт участка **выше** `ground_z` (fine cells). Сумма `z_height` каждого этажа, который выступает над землёй: этаж занимает `[z, z+z_height)`; целиком под землёй — 0; пересекает землю — только часть в `[ground_z, top)`. Нет здания / packing — `0`.

`z_deep` — то же **ниже** `ground_z`: часть этажа в `[z, ground_z)`. Плоскость `ground_z` не входит в подвал — чтобы ground не накладывался на участок снизу. Целиком над землёй — 0.

Считает `StructureAreaAssembler` по `building_layout.levels` после translate. Pack-wire: `AreaSlotWire.height` / `z_deep` / `deck` (omit → 0).

`deck` — **ярус** района. SoT: `DistrictTemplateEntry.deck` (city §9.2; omit → 0). `AreaSlot.deck` — копия при packing, не своя настройка участка. Не этаж здания (`LocationLevel`), не `economic_tier`, не climate z-band hive/spire, не AABB-разведение двух поселений ([`tz_locations.md`](./tz_locations.md) **LOC-T-3**). Канон omit → все участки `0`. Коллизия xy ∩ z (`[ground_z - z_deep, ground_z + height)`) — только если в районе **два+ различных** `deck` среди участков. Один ярус: 2D packing, проверка не бежит. Generate при ударе — warning, не abort. Несколько ярусов на одном чертеже / наложение районов — позже; сейчас у района один `deck`.

---

**Порог (`AreaThreshold`)** — стык улицы с участком, не «всегда дверь». Не поле `AreaSlot` (packing не знает топологию). Не SQL и не `AreaSlotWire` v1.

```python
class AreaThresholdKind(StrEnum):
    DOOR        = "door"
    GATE        = "gate"
    PARCEL_EDGE = "parcel_edge"

@dataclass
class AreaThreshold:
    kind:  AreaThresholdKind
    cells: list[tuple[int, int]]  # xy порога
    z:     int                    # median колонок порога; clamp §5.1.2 если нет здания
```

| `kind` | Когда | Клетки порога | Конец `_build_paths` |
|---|---|---|---|
| `door` | участок = дом (bbox + число клеток) | проём `entry_point` | `building_entrance` |
| `gate` | двор + забор | ворота на facing забора (центр грани), к **`main_building`** | `waypoint` на воротах (`graph_level=area`); участок не `location_type` (C3) |
| `parcel_edge` | двор без забора | **то же xy**, что калитка | `waypoint` на крае |

**Подъезд (`StreetApproach`)** — результат луча, не mill-инстанс:

```python
class ApproachForm(StrEnum):
    NONE   = "none"    # h = 0
    GRADE  = "grade"   # θ ≤ 30°
    STAIRS = "stairs"  # 30° < θ ≤ 45° (после clamp всегда ≤ 45°)

@dataclass
class StreetApproach:
    ray:       tuple[tuple[int, int], ...]
    length:    int     # L
    z_far:     int     # полотно на дальнем конце
    z_near:    int     # порог или building.map_z (уже после clamp)
    theta_rad: float
    form:      ApproachForm
```

`clamp_near_z_to_45(z_near, z_far, L) → int` — helper coordinates, не метод DTO. SoT: connections **§5.1.2**. `StreetApproach` / `AreaThreshold` — только поля.

Дальше по участку (ворота → дверь в глубине) — второй луч от двери.

`AreaSlot.ground_z` и `building.map_z` **могут различаться**: двор по земле внутри, дом на своём footprint. Оба считает assembler участка, не район. `StructureContext.ground_z` = `building.map_z` после clamp (фундамент к полу дома), не копия `slot.ground_z`.

---

**`AreaLayout`** — результат сборки участка:

```python
@dataclass
class AreaLayout:
    slot:              AreaSlot
    threshold:         AreaThreshold
    approach:          StreetApproach | None  # нет луча / L=0
    building_location: NamedLocation | None   # NL из шаблона; None только если шаблон NL не даёт; иначе ошибка generate
    building_layout:   StructureLayout | None
    barrier_cells:     list[MapCell]          # прямые **участка**, не района, не поселения, не wall здания
    yard_cells:        list[MapCell]
    small_layouts:     list[StructureLayout]
    connection_nodes:  list[ConnectionNode]   # area graph, §5.1.1
    connection_edges:  list[ConnectionEdge]
```

Здание не обязательно: участок = шаблон любого назначения (дом, таверна, площадь, …), не leftover packing. `building_location is None` — **только** если шаблон **не** даёт `main_building` (типично `plaza` / сад). **Если шаблон даёт `main_building`, а generate собрал участок без него** (`building_location is None`, пустой двор) — **критическая ошибка генерации участка**. Не plaza, не silent skip, не «участок без дома допустим». Слои не мешать. `threshold` / `approach` — рантайм assembler; extract пишет граф и `AreaSlotWire.ground_z` (плоскость участка), не kind порога. C20 — только если главное здание с входом (здание без `front` — тоже ошибка generate, не этот кейс).

---

**`DistrictLayout`** — результат `DistrictAssembler` (в коде: `districtLayout.py`; в этом § сниппет не был — дырка ТЗ).

```python
@dataclass
class DistrictLayout:
    slot:             DistrictSlot
    area_layouts:     list[AreaLayout]
    connection_nodes: list[ConnectionNode]
    connection_edges: list[ConnectionEdge]
    barrier_cells:    list[MapCell]   # прямые **района** (v1: включённые грани слота); пишет DistrictAssembler (TODO generate)
```

Не `AreaLayout.barrier_cells` (участок). Не `SettlementLayout.barrier_cells` (прямые **поселения**). Зоны не пересекаются: слот уже урезан поселением. Не wall здания.

---

**`SettlementLayout`** — результат `SettlementAssembler`:

```python
@dataclass
class SettlementLayout:
    district_layouts:  list[DistrictLayout]
    connection_nodes:  list[ConnectionNode]
    connection_edges:  list[ConnectionEdge]
    occupancy_cells:   list[MapCell]
    barrier_cells:     list[MapCell]  # барьер **поселения** (прямые footprint); не район
    dominant_material: str | None
```

Пишет только `SettlementAssembler` (клетки + вычет из площади района). `DistrictAssembler` этот список не трогает.

---

### 7.2 Интерфейс StructureAreaAssembler

```python
class StructureAreaAssembler:

    def assemble(
        self,
        world:             World,
        slot:              AreaSlot,
        plot:              PlotLayoutTemplate,        # чертёж участка; здания объявлены здесь
        city_skeleton:     CitySkeleton,
        terrain_cells:     list[MapCell] | None = None,
        *,
        street_xy:         AbstractSet[tuple[int, int]],  # полотно после DistrictAssembler._plan_streets
        structure_catalog: StructureCatalog,              # резолв plot.main_building.structure
        cached_layout:     StructureLayout | None = None, # envelope района — только occupied_footprint
        building_x:        int | None = None,
        building_y:        int | None = None,
    ) -> AreaLayout:
        # 1. slot.ground_z = median_surface_z(двор); footprint = plot.occupied_footprint (объявленный)
        # 2. _place_building() — NamedLocation, черновой map_z = медиана поверхности под footprint
        # 3. body = plot.main_building; None → _shell_layout (plaza, без здания) → шаги 7–9
        #    structure = structure_catalog.resolve(body.structure); None → GenerationError (422: plot, structure)
        # 4. context = _derive_context(body, slot, building)  — envelope из body + facing + ground_z + band
        # 5. layout = BuildingAssembler.assemble(world, building, body, structure, context, terrain_cells)
        #    внутри: generate (SOUTH-фрейм) → поворот под slot.facing → fit-check (§7.7) → envelope
        # 6. entry_xy = main_entrance из layout (реальная дверь) → _resolve_threshold(slot, entry_xy, fp_cells)
        # 7. measure_street_approach; θ > 45° → clamp_near_z_to_45; при Δz → translate_layout(layout, 0, 0, dz)
        # 8. stamp_approach_cells; _build_paths — только граф
        # 9. _build_barrier — slot.ground_z; калитка на стороне slot.facing (та же, что дверь)
```

Район зовёт assembler участка **после** `_plan_streets` и передаёт `street_xy`. Лог `INFO` на входе: `plot.system_name`, `slot.facing`, `len(slot.cells)`.

Ветка «перенос готового layout из cache» (`_cache_has_rooms` / `translate_layout` из cache) — **удалена**: cache района envelope-only (§7.7), геометрия генерируется на посадке. `cached_layout` остаётся только как источник `occupied_footprint` при отсутствии объявленного.

---

### 7.3 Методы assembler vs helpers

Assembler **не** считает θ, median, шаг сетки. Формулы — helpers (план C21 §2.0).

| Метод assembler | Делает | Не делает |
|---|---|---|
| `_resolve_threshold` | `kind` + клетки порога | `street_xy`; луч; z-формула (z = `median_surface_z` снаружи) |
| `_place_building` | `NamedLocation` xy + черновой `map_z` | clamp; envelope; граф |
| `_derive_context` | `StructureContext`; `ground_z = building.map_z` после clamp | луч |
| `_build_paths` | nodes/edges area | grade-клетки; `partition_height` |
| `_build_barrier` | забор на `slot.ground_z` | порог; улица |

| Helper | Слой |
|---|---|
| `column_surface`, `median_surface_z` | coordinates |
| `walk_grid_ray` | coordinates |
| `classify_approach`, `clamp_near_z_to_45` | coordinates |
| `peek_abutting_street_z`, `measure_street_approach` | area planner |
| `approach_material`, `stamp_approach_cells` | area planner |

---

### 7.4 Файловая структура

```
generators/assemblers/
  __init__.py
  citySkeleton.py                     # CitySkeleton dataclass (shared; течёт City→District→Area)

  settlementAssembler/                # реализовано (скелет + граф дорог)
    __init__.py
    settlementAssembler.py
    settlementLayout.py               # результат SettlementAssembler

  districtAssembler/                  # реализовано (скелет + генерация улиц)
    __init__.py
    connectionEntry.py                # точка входа/выхода на грани района
    districtSlot.py                   # входной контракт (от SettlementAssembler)
    districtAssembler.py
    districtLayout.py                 # результат DistrictAssembler

  areaAssembler/                      # реализовано (скелет); C21 расширяет типы
    __init__.py
    areaSlot.py                       # вход packing: cells + facing; ground_z пишет assembler
    areaThreshold.py                  # DTO AreaThreshold + kind
    streetApproach.py                 # DTO StreetApproach + ApproachForm
    areaLayout.py
    structureAreaAssembler.py         # оркестрация
    planner/
      resolveThreshold.py             # топология порога
      measureApproach.py              # peek + measure_street_approach
      stampApproach.py                # material + CITY_STRUCTURE клетки
      areaPaths.py                    # только граф
      areaBarriers.py

  buildingAssembler/                  # слой здания (сейчас пакет structureAssembler/ — rename в срезе 5n/5o)
    __init__.py
    assemblerRegistry.py              # BUILDING_ASSEMBLER_REGISTRY: kind → класс
    baseBuildingAssembler.py          # ABC (сейчас baseStructureAssembler.py)
    buildingAssembler.py
    ruinsAssembler.py
    resourceExtractionAssembler.py
    vastHullAssembler.py
    structureContext.py               # входной контракт (от StructureAreaAssembler)

generators/structure/                 # домен structure — геометрия, три поддомена
  structureGeneratorService.py        # geometry (не interior — наполнение это StructureInteriorAssembler)
  foundation/foundationBuilder.py     # foundation
  roof/roofBuilder.py, gableRoof.py   # roof
```

**Принцип именования:**
- `*Slot` живёт у **получателя** — это его входной контракт
- `*Layout` живёт там же — это его выходной контракт
- `citySkeleton` — исключение; cross-cutting, на уровне `assemblers/`

---

### 7.5 Система координат

Единая система координат (x, y, z) в coarse- и fine-клетках — одна для всего движка (map_cells, NamedLocation, всё). Метры/футы — только UI/LLM.

**Глобальная ячейка карты** — конфигурируемая единица планирования города:
```
map_cell_fine_span = World.fine_cells_per_map_cell   # через generators/coordinates/map_cell_fine_span(world)
```

> **Не** `world.map_settings["global_cell_size_m"]` — ghost key (NC-1g). См. [tz_city_generation.md](./tz_city_generation.md) §9.6, [tz_terrain_generation.md](./tz_terrain_generation.md) § coordinates.

Разграничение по слоям:

| Слой | Единица | Тип в коде |
|---|---|---|
| `SettlementAssembler` | планирует в глобальных ячейках `(cell_x, cell_y)` сетки города | `int` |
| `DistrictSlot` | WORLD_FINE_GRID — `SettlementAssembler` вычисляет и укладывает в слот вместе с шаблоном | `int` |
| `DistrictAssembler` | работает в fine-клетках из `slot.origin_x/y, width_fine, depth_fine` | `int` |
| `AreaSlot` | абсолютные (x, y) в fine-клетках; список ячеек; `height` / `z_deep` — клетки z выше / ниже `ground_z`; `deck` — ярус | `list[tuple[int,int]]` + `int` |

Один район может занимать всю глобальную ячейку: `width_fine = depth_fine = map_cell_fine_span`.

**Координаты:** hub `generators/coordinates/` — WORLD_SURFACE_GRID vs WORLD_FINE_GRID ([`.cursor/plans/coordinate-spaces-done.md`](../.cursor/plans/coordinate-spaces-done.md)).

---

### 7.6 Порядок реализации (снизу вверх)

1. `citySkeleton.py` — чистый dataclass, нет зависимостей
2. `areaSlot.py` — чистый dataclass, зависит только от `Facing`
3. `areaLayout.py` — dataclass, зависит от `StructureLayout`, `MapCell`, `NamedLocation`
4. `structureAreaAssembler.py` — оркестратор, зависит от всего выше + `ASSEMBLER_REGISTRY` + `StructureContext`

Каждый шаг компилируется и импортируется независимо до следующего. Контракты зафиксированы на уровне типов — реализацию приватных методов дописывать по мере появления ТЗ.

---

### 7.7 Кэш зданий и стратегия расстановки

#### Проблема

Envelope здания (реальные размеры по x/y/z) нельзя надёжно объявить в шаблоне:
`floor_height` варьируется по комнатам, `floor_count` в метаданных может расходиться
с фактическим определением. Декларативный envelope рассинхронизируется.

#### Решение: envelope для packing, генерация геометрии — на посадке участка

Packing района работает с **объявленным** `PlotLayoutTemplate.occupied_footprint` (cache envelope-only), не с реальной геометрией: району для расстановки нужен только footprint. Геометрию здания производит `StructureAreaAssembler` → `BuildingAssembler` **при посадке** каждого участка (один generate на участок). Полный интерьер всех домов до района — нет (C22). Порядок посадки — [connections](./tz_structure_connections.md) §5.1.3 «Пайплайн посадки», не bin-pack AABB `DistrictSlot`.

Прежняя формулировка «generate-first, place-second» (cache хранит полные layout, участок переносит из cache) — **отменена** (решение `.cursor/plans/city-t-5n-5o-structure-split.md` §4.0): перенос готового layout невозможен корректно при повороте под `facing`, а идентичные uid комнат при reuse коллизируют на persist.

#### Алгоритм `DistrictAssembler`

```
1. Слот уже урезан поселением; якоря в слоте (`SettlementAssembler`). Инстанс барьера района — скип если нет поля / template null. Иначе inner bbox = слот минус прямые района (`sides` + `width_cells`) минус коридор
2. Кандидаты: allowed_structure_types ∩ тир ∪ required_structures — листья матчатся через plot.main_building.structure (StructureCatalog.leaves_of)
3. Cache envelope (occupied_footprint участка; ни комнат, ни generate)
4. Проход 1 — бронь приоритетных во внутреннем bbox (решётка block_size)
5. Рамка вокруг броней (не сквозь бронь / коридор якорей)
6. Проход 2 — остальная коллекция
7. Граф улиц → StructureAreaAssembler: generate геометрии на посадке (по slot.facing)
8. Не влезло в район → warning, не exception
```

#### Кэш

- Живёт на уровне сборки одного поселения (`SettlementAssembler.assemble` создаёт и передаёт вниз)
- Ключ: `(plot, facing)`; значение — envelope (`occupied_footprint`), не комнаты
- Кэш **не** хранит `StructureLayout` с комнатами и **не** переносится на участок

#### Fit-check на посадке

Резервация footprint в packing — всегда в SOUTH-фрейме чертежа; `facing` назначается после. При 90°/270° неквадратный чертёж меняет `width↔depth`. После generate: `layout.occupied_footprint ⊆ slot.cells`; не влезло → `packing_warning` (`plot`, `structure`, `facing`) + повторный generate на 180° (footprint тот же); не влезло и в SOUTH → `GenerationError` → 422 с именами (кривой чертёж). Резервация в правильном фрейме — итерация 2.

#### Warning-политика

Невозможность разместить здание — не исключение, `warning`-лог с причиной:
- `"недостаточно места (bbox=%dx%d, свободно=%dx%d)"`
- `"пересечение с уже размещённым зданием uid=%s"`
- `"выход за границы района"`

Это соответствует общей политике верификаторов проекта: warning без исключений.

C22: подробный DEBUG на каждом шаге packing — [connections](./tz_structure_connections.md) §5.1.3 «Debug packing». Sinks / хелперы — [tz_logging.md](./tz_logging.md) (не `getLogger` в planner).

**C22:** целевое city §6.3: cache → бронь приоритетных → рамка вокруг → проход 2 → граф после. Число копий — connections §5.1.3 «Число токенов». Код: AABB + overlay. Переход — TODO в §6.3.

---

### 7.8 Открытые вопросы

| Вопрос | Статус |
|---|---|
| `_derive_context` — алгоритм вывода `StructureContext` из `structure_type` + terrain + `economic_tier` | не описан |
| `_place_building` — правила позиционирования здания внутри участка (центрирование, offset от забора, facing-alignment) | **closed C22:** facing из графа + приоритет; `entry_point.wall` = грань парадного, интерьер не rotate. Packer 90° оболочки + вход участка = парадный основного дома — [connections](./tz_structure_connections.md) §5.1.3 «Поворот оболочки» |
| `_build_paths` — подъезд к улице при Δz | **closed:** [tz_structure_connections.md](./tz_structure_connections.md) §5.1.1; порог = assembler участка |
| Кто считает `ground_z` / порог | **closed:** `StructureAreaAssembler` (участок, не район) — C21; порог ≠ всегда дверь |
| `_build_barrier` — алгоритм клеток **барьера вокруг участка** (`AreaLayout.barrier_cells`) | не описан. Ширина — `width_cells` шаблона барьера (дефолт 1); прямые граней участка |
| `DistrictAssembler` — generate прямых **района** | **TODO**. Слот уже без xy поселения; свой список, зона не пересекается с поселением и участком |
| Малые постройки на участке | состав площади (сад, фонтан, терраса) — **шаблон**, не хардкод; алгоритм stamp — нет ТЗ |
| `AreaLayout` ↔ `DistrictAssembler` — как район агрегирует результаты нескольких участков | нет ТЗ |
| `DistrictAssembler` — механика дорог (внутренние улицы, тротуары, соединение с городскими магистралями) | **C22:** рамка после брони прохода 1; код: `DistrictRoadGenerator` + overlay. Переход — city §6.3 |
| Рамка `radial` / `organic` вокруг брони; snap `entry_nodes` вне `grid` | **CONN-PACK-1** — [connections](./tz_structure_connections.md) §8 |
| Два `required_structures` с `position: center` | **CONN-PACK-2 closed** — кластер вокруг home inner bbox; [connections](./tz_structure_connections.md) §5.1.3 / §8 |
| Envelope `(template, facing)` на проходе 1, пока полосы рамки нет | **CONN-PACK-3** — connections §8 |
| `DistrictSlot.facing` — нужна ли ориентация к главной улице города на уровне района | отложено |
