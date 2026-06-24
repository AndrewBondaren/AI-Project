# ТЗ: Иерархия ассемблеров

## 1. Структура

```
CityAssembler
    └── DistrictAssembler
            └── StructureAreaAssembler
                    └── StructureAssembler
                            └── StructureGenerator (BuildingGeneratorService)
                                    └── StructureInteriorAssembler
```

Каждый слой самодостаточен. Вход в иерархию — на нужном уровне.

---

## 2. Слои

### CityAssembler
**Знает:** city skeleton (economic_tier, architectural_style, dominant_material, settlement_density)  
**Делает:**
- занимает ячейки карты мира под поселение
- планирует город на ячейках; понимает топологию по z (наземный / подземный / воздушный — одновременно)
- управляет топологией соединения ячеек города между собой (улицы, мосты, тоннели)
- строит сетку улиц, определяет типы кварталов, нарезает слоты под здания

**Подробнее:** [tz_city_generation.md](tz_city_generation.md)

### DistrictAssembler
**Знает:** тип квартала, city skeleton  
**Делает:**
- вызывается несколько раз на каждой ячейке города — формирует несколько районов на одной ячейке
- управляет топологией соединения районов между собой
- выделяет размеры участков (`AreaSlot`) в зависимости от шаблонов построек в районе
- назначает `building_template` каждому слоту по `structure_type` + `economic_tier`
- имеет собственный шаблон типа района (аналог `building_template` — описывает структуру квартала)

**Подробнее:** [tz_city_generation.md](tz_city_generation.md) — раздел 6 (алгоритм заполнения кварталов)

### StructureAreaAssembler
**Знает:** `AreaSlot` (список координат участка + facing), шаблон, city skeleton, terrain  
**Делает:**
- полностью понимает топологию своей зоны и что находится в ней
- знает facing area (сторона к улице = направление главного входа)
- вычисляет координаты и размеры здания внутри участка из шаблона (`footprint` из `building_template_registry`)
- выводит `StructureContext` из `structure_type` + `architectural_style` + terrain
- планировка участка: двор, забор (`barrier_template_registry`; probability из шаблона), малые постройки
- вызывает `StructureAssembler` для каждого здания на участке (главного и малых)

**Источник `StructureContext`:** этот слой. Только он знает достаточно для вывода контекста.  
**`AreaSlot`:** список (x, y) координат + `ground_z` + `facing: Facing` (какая сторона смотрит на улицу).  
**Подробнее:** [tz_building_generator.md](tz_building_generator.md) — раздел 11 (StructureAssembler, StructureContext)

### StructureAssembler
**Знает:** `StructureContext`, terrain_cells  
**Делает:** фундамент + крыльцо/ступени + крыша поверх interior box  
**Может быть вызван вне иерархии** — для кораблей, данжей и других структур, способных к перемещению (`is_mobile=true`).  
**Подробнее:** [tz_building_generator.md](tz_building_generator.md) — раздел 11

### StructureGenerator (BuildingGeneratorService)
**Знает:** шаблон, world  
**Делает:** interior box — комнаты, стены, проходы, wall_openings  
**Подробнее:** [tz_building_generator.md](tz_building_generator.md) — разделы 3–10

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
| Полная городская генерация | `CityAssembler` |
| Отдельный квартал | `DistrictAssembler` |
| Здание на участке (ручное размещение, редактор) | `StructureAreaAssembler` |
| Корабль, данж, изолированное здание | `StructureAssembler` |
| Срез мегаздания (`foundation="none"`, `roof="none"`) | `StructureGenerator` |
| Наполнение уже сгенерированного здания (предметы, NPC) | `StructureInteriorAssembler` |

---

## 4. Поток данных

```
CityAssembler
  city_skeleton → DistrictAssembler
    district_type + template_slot → StructureAreaAssembler
      StructureContext (выводится здесь) → StructureAssembler
        terrain_cells → terrain_surface[x,y] + ground_z
        context + ground_z + foundation_depth → StructureGeneratorService(ground_z, foundation_depth)
                                                    → StructureLayout (interior box)
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

## 6. Архитектура StructureAssembler

### 6.1 StructureContext

```python
@dataclass
class StructureContext:
    foundation_type:     str               # "none"|"slab"|"perimeter"|"full"|"stilts"|"hull"
    roof_type:           str | list[str]   # "none"|"flat"|"gable"|"hull"|"auto" или список с приоритетом
    foundation_depth:    int   = 1         # z-юниты вглубь; для "slab"/"hull" — фикс. толщина
    slope_step:          float = 1.0       # shrink за 1 z-юнит; 1.0 ≈ 45°; только для скатных крыш
    foundation_material: str | None = None # fallback: building.parent_wall_material
    roof_material:       str | None = None # fallback: building.parent_wall_material
    porch_material:      str | None = None # fallback: building.parent_floor_material
    porch_has_roof:      bool = False      # навес над крыльцом
    ground_z:            int | None = None # None → building.map_z
```

`StructureContext` не хранится в шаблоне — шаблон описывает только interior.
Источник: `StructureAreaAssembler` (из city-пайплайна) или ручной выбор в UI.

---

### 6.2 ground_z — уровень земли

**Проблема:** `z = 0` не является уровнем земли. Уровень земли зависит от контекста здания и terrain.

**Определение:**

```
ground_z = context.ground_z ?? building.map_z
```

`building.map_z` — z-координата пола ground floor (`z_offset=0`). Это и есть уровень земли по умолчанию.

Явный `context.ground_z` нужен для нестандартных случаев: корабль (нет земли под килем), данж (пол пещеры выше нуля), мегаздание (срез на высоте).

**terrain_surface** — детальная карта поверхности:

```python
terrain_surface: dict[tuple[int,int], int]
# terrain_surface[x, y] = max z среди terrain-ячеек в колонке (x, y)
# вычисляется StructureAssembler из terrain_cells
# используется FoundationBuilder для расчёта gap[x,y] = building.map_z - terrain_surface[x,y]
```

Для v1: `terrain_surface` используется только в `FoundationBuilder`.
Для v2: `terrain_surface[x, y]` позволяет определять exposed/buried стены на уровне ячейки (например, окно на стороне холма, которая смотрит в землю).

---

### 6.3 Хардкоды z=0 в генераторе — баги и фикс

Три места в `StructureGeneratorService` и его подсистемах используют `z = 0` как уровень земли:

| Файл | Место | Проблема | Фикс |
|---|---|---|---|
| `passages/wallOpening.py:115` | `if level.z < 0: return` | Нет окон на подземных уровнях | `level.z < ground_z` |
| `passages/staircaseTunnelOrchestrator.py:71` | `if level.z >= 0:` | Выбор surface vs underground стратегии тоннеля | `level.z >= ground_z` |
| `staircase/builder.py:60-61` | `fr.z_offset >= 0 and to.z_offset < 0` | Авто-выбор типа лестницы (old schema) | `fr.z_offset` относителен шаблону — **ok**, не трогать |

`z_offset` в шаблоне (0 = ground floor) — всегда корректен, не зависит от абсолютных координат.
`level.z` — абсолютная координата в мире — сравнивать только с `ground_z`.

**Интерфейс:** `ground_z` передаётся через `generate_from_template`:

```python
StructureGeneratorService().generate_from_template(
    world, building, template,
    ground_z=ground_z,          # пробрасывается в wallOpening + tunnelOrchestrator
    foundation_depth=fd,        # пробрасывается в _compute_level_z для z_offset < 0
)
```

---

### 6.4 basement z-shift — сдвиг подвалов под фундамент

**Проблема:** при наличии фундамента подвальные уровни должны располагаться ниже фундаментного слоя.

Текущий `_compute_level_z` для `z_offset < 0`:
```
z = building.map_z - Σ(z_height for z_offset in N..-1)
```

Нужно:
```
z = building.map_z - foundation_depth - Σ(z_height for z_offset in N..-1)
```

Фикс: добавить `foundation_depth: int = 0` в `generate_from_template` → пробросить в `_compute_level_z`.

Пример, `foundation_depth=2`, подвал `z_height=3`, `building.map_z=0`:
```
foundation:  z = -2, -1        (фундаментный слой)
basement:    z = -5, -4, -3    (ниже фундамента)
```

При `foundation_type="none"`: `fd=0` → поправка не применяется.

---

### 6.5 Интерфейс StructureAssembler

```python
class StructureAssembler:

    def assemble(
        self,
        world:         World,
        building:      NamedLocation,
        template:      dict,
        context:       StructureContext,
        terrain_cells: list[MapCell] | None = None,
    ) -> StructureLayout:
        ground_z        = context.ground_z if context.ground_z is not None else building.map_z
        terrain_surface = _build_terrain_surface(terrain_cells) if terrain_cells else {}
        fd              = context.foundation_depth if context.foundation_type != "none" else 0

        layout = StructureGeneratorService().generate_from_template(
            world, building, template,
            ground_z=ground_z,
            foundation_depth=fd,
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

### 6.8 Изменения в StructureGeneratorService (минимальные)

```python
def generate_from_template(
    self,
    world:            World,
    building:         NamedLocation,
    template:         dict,
    ground_z:         int | None = None,      # новый параметр
    foundation_depth: int        = 0,          # новый параметр
) -> StructureLayout: ...
```

Внутри:
1. `ground_z = ground_z if ground_z is not None else building.map_z`
2. `_compute_level_z`: для `z_offset < 0` вычитать `foundation_depth`
3. `place_wall_openings(... ground_z=ground_z)` — заменить `level.z < 0` на `level.z < ground_z`
4. `StaircaseTunnelOrchestrator(... ground_z=ground_z)` — заменить `level.z >= 0` на `level.z >= ground_z`

---

## 7. Архитектура StructureAreaAssembler

### 7.1 Контракты и типы данных

**`CitySkeleton`** — поля скелета города, передаются сверху вниз по всей иерархии:

```python
@dataclass
class CitySkeleton:
    economic_tier:        str | None   # ref → worlds.economic_tier_registry
    architectural_style:  str | None   # ref → worlds.architectural_style_registry
    dominant_material:    str | None   # ref → worlds.material_registry
    settlement_density:   str | None   # "sparse" | "medium" | "dense"
    system_city_size:     str | None   # ref → worlds.city_size_registry
    system_location_mood: str | None   # ref → worlds.location_mood_registry
```

Источник данных: поля `NamedLocation` поселения. Собирается `CityAssembler` и передаётся вниз без изменений.

---

**`AreaSlot`** — участок, выделенный `DistrictAssembler`:

```python
@dataclass
class AreaSlot:
    cells:    list[tuple[int, int]]   # (x, y) координаты участка без z
    ground_z: int                      # уровень земли
    facing:   Facing                   # сторона участка к улице → ориентация главного входа
```

`facing` определяет:
- на какой стене здания будет `entry_point`
- откуда идёт ворота в заборе

---

**`AreaLayout`** — результат сборки участка:

```python
@dataclass
class AreaLayout:
    building_location: NamedLocation          # создан StructureAreaAssembler
    building_layout:   StructureLayout        # главное здание (из StructureAssembler)
    barrier_cells:     list[MapCell]          # забор / стена (пусто до реализации)
    yard_cells:        list[MapCell]          # двор (нет ТЗ)
    small_layouts:     list[StructureLayout]  # малые постройки (нет ТЗ)
```

Возвращается вместо плоского `StructureLayout` — участок многоуровневый, слои не мешать.

---

### 7.2 Интерфейс StructureAreaAssembler

```python
class StructureAreaAssembler:

    def assemble(
        self,
        world:         World,
        slot:          AreaSlot,
        template:      dict,
        city_skeleton: CitySkeleton,
        terrain_cells: list[MapCell] | None = None,
    ) -> AreaLayout:
        # 1. _place_building() — создаёт NamedLocation здания
        #    вычисляет map_x/map_y/map_z из slot.cells + template footprint + slot.facing
        # 2. _derive_context() — выводит StructureContext
        #    из structure_type + architectural_style + terrain
        # 3. ASSEMBLER_REGISTRY.get(structure_type).assemble(...)
        #    → StructureLayout главного здания
        # 4. _build_barrier() — генерирует забор по периметру slot.cells
        #    probability из template["perimeter_barrier"]
        # 5. yard_cells — нет ТЗ → []
        # 6. small_layouts — нет ТЗ → []
```

Лог `INFO` на входе: `template.system_name`, `slot.facing`, `len(slot.cells)`.

---

### 7.3 Приватные методы (все скелетные — raise NotImplementedError)

| Метод | Вход | Выход | Что делает |
|---|---|---|---|
| `_place_building` | `world, slot, template` | `NamedLocation` | Вычисляет позицию здания внутри участка; создаёт `NamedLocation` с `map_x/y/z` |
| `_derive_context` | `template, city_skeleton, slot, terrain_cells` | `StructureContext` | Алгоритм: `structure_type` + `architectural_style` → foundation/roof; не описан (см. открытые вопросы) |
| `_build_barrier` | `world, slot, template` | `list[MapCell]` | Забор по периметру slot.cells; читает `template["perimeter_barrier"]` + probability roll |

---

### 7.4 Файловая структура

```
generators/assemblers/
  __init__.py
  citySkeleton.py                     # CitySkeleton dataclass (shared; течёт City→District→Area)

  cityAssembler/                      # скелет — следующий этап
    __init__.py
    cityAssembler.py
    cityLayout.py                     # результат CityAssembler

  districtAssembler/                  # скелет — следующий этап
    __init__.py
    districtSlot.py                   # входной контракт (от CityAssembler)
    districtAssembler.py
    districtLayout.py                 # результат DistrictAssembler

  areaAssembler/                      # реализовано (скелет)
    __init__.py
    areaSlot.py                       # входной контракт (от DistrictAssembler)
    areaLayout.py                     # результат StructureAreaAssembler
    structureAreaAssembler.py

  structureAssembler/                 # реализовано
    __init__.py
    assemblerRegistry.py
    baseStructureAssembler.py
    buildingAssembler.py
    ruinsAssembler.py
    resourceExtractionAssembler.py
    vastHullAssembler.py
    structureContext.py               # входной контракт (от StructureAreaAssembler)
```

**Принцип именования:**
- `*Slot` живёт у **получателя** — это его входной контракт
- `*Layout` живёт там же — это его выходной контракт
- `citySkeleton` — исключение; cross-cutting, на уровне `assemblers/`

---

### 7.5 Система координат

Единая система координат (x, y, z) в метрах — одна для всего движка (map_cells, NamedLocation, всё).

**Глобальная ячейка карты** — конфигурируемая единица планирования города:
```
cell_size_m = world.map_settings["global_cell_size_m"]   # из БД; не хардкодится
```

Разграничение по слоям:

| Слой | Единица | Тип в коде |
|---|---|---|
| `CityAssembler` | планирует в глобальных ячейках `(cell_x, cell_y)` сетки города | `int` |
| `DistrictSlot` | мировые метры — `CityAssembler` вычисляет и укладывает в слот вместе с шаблоном | `int` |
| `DistrictAssembler` | работает в мировых метрах из `slot.origin_x/y, width_m, depth_m` | `int` |
| `AreaSlot` | абсолютные (x, y) в метрах; список ячеек | `list[tuple[int,int]]` |

Один район может занимать всю глобальную ячейку: `width_m = depth_m = cell_size_m`.

**`worlds.map_settings`** — добавить ключ:
```json
{ "global_cell_size_m": <int> }
```
Это новый ключ в существующем JSON-поле `worlds.map_settings` — схема БД не меняется, миграция не нужна. Устанавливается при создании мира.

---

### 7.6 Порядок реализации (снизу вверх)

1. `citySkeleton.py` — чистый dataclass, нет зависимостей
2. `areaSlot.py` — чистый dataclass, зависит только от `Facing`
3. `areaLayout.py` — dataclass, зависит от `StructureLayout`, `MapCell`, `NamedLocation`
4. `structureAreaAssembler.py` — оркестратор, зависит от всего выше + `ASSEMBLER_REGISTRY` + `StructureContext`

Каждый шаг компилируется и импортируется независимо до следующего. Контракты зафиксированы на уровне типов — реализацию приватных методов дописывать по мере появления ТЗ.

---

### 7.6 Открытые вопросы

| Вопрос | Статус |
|---|---|
| `_derive_context` — алгоритм вывода `StructureContext` из `structure_type` + `architectural_style` | не описан |
| `_place_building` — правила позиционирования здания внутри участка (центрирование, offset от забора, facing-alignment) | не описан |
| `_build_barrier` — алгоритм генерации ячеек забора по списку координат участка | не описан |
| Малые постройки на участке | нет ТЗ |
| `AreaLayout` ↔ `DistrictAssembler` — как район агрегирует результаты нескольких участков | нет ТЗ |
| `DistrictAssembler` — механика дорог (внутренние улицы, тротуары, соединение с городскими магистралями) | нет ТЗ; `street_cells` в `DistrictLayout` зарезервированы |
| `DistrictSlot.facing` — нужна ли ориентация к главной улице города на уровне района | отложено |
