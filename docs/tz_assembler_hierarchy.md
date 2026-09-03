# ТЗ: Иерархия ассемблеров

## 1. Структура

```
SettlementAssembler
    └── DistrictAssembler
            └── StructureAreaAssembler
                    └── StructureAssembler
                            └── StructureGenerator (BuildingGeneratorService)
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
**Знает:** `AreaSlot` (клетки **участка** + facing), шаблон, city skeleton, terrain  
**Делает:**
- полностью понимает топологию своей зоны: тип — из шаблона, любое назначение (`structure_type`). Не «всегда жилой дом». Примеры геометрии: здание у улицы; двор+забор+здание в глубине; общественная площадь (`plaza`: сады, фонтаны, террасы); только оболочка, если так задан шаблон
- знает facing area (сторона к улице)
- **решает порог** (где улица стыкуется с участком) — `_resolve_threshold`: дверь / ворота забора / край участка. Формула «всегда фасад здания» запрещена
- при наличии здания: координаты из шаблона, `StructureContext` (`ground_z` = `building.map_z` после clamp), вызов `StructureAssembler`. Шаблон даёт здание, участок без NL — **ошибка generate**, не пустой двор
- планировка: двор, забор (`barrier_template_registry`), малые постройки
- `_build_paths`: улица → **порог** (не обязательно `building_entrance`); θ > 45° — clamp только z

**Источник `StructureContext`:** этот слой. Только он знает достаточно для вывода контекста и порога.  
**`AreaSlot`:** список (x, y) участка (здание ∪ двор ∪ линия забора) + `ground_z` (**этого** участка) + `facing`. Не копия z района.  
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
| Полная городская генерация | `SettlementAssembler` |
| Отдельный квартал | `DistrictAssembler` |
| Здание на участке (ручное размещение, редактор) | `StructureAreaAssembler` |
| Корабль, данж, изолированное здание | `StructureAssembler` |
| Срез мегаздания (`foundation="none"`, `roof="none"`) | `StructureGenerator` |
| Наполнение уже сгенерированного здания (предметы, NPC) | `StructureInteriorAssembler` |

---

## 4. Поток данных

```
SettlementAssembler
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
    facing:              Facing | None = None  # сторона главного входа; None → определяется шаблоном
    foundation_depth:    int   = 1         # z-юниты вглубь; для "slab"/"hull" — фикс. толщина
    slope_step:          float = 1.0       # shrink за 1 z-юнит; 1.0 ≈ 45°; только для скатных крыш
    foundation_material: str | None = None # fallback: building.parent_wall_material
    roof_material:       str | None = None # fallback: building.parent_wall_material
    porch_material:      str | None = None # fallback: building.parent_floor_material
    porch_has_roof:      bool = False      # навес над крыльцом
    ground_z:            int | None = None # None → building.map_z
```

`facing` пробрасывается из `AreaSlot.facing` через `StructureAreaAssembler._derive_context`.
`None` означает что шаблон сам определяет расположение входа (для изолированных структур без улицы).

`StructureContext` не хранится в шаблоне — шаблон описывает только interior.
Источник: `StructureAreaAssembler` (из city-пайплайна) или ручной выбор в UI.

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
# вычисляется StructureAssembler из terrain_cells
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
    frontage_type_order:  list[str] | None          # C22; null = дефолт движка
    structure_counts:     dict[str, int] | None     # C22; городской дефолт N
    structure_priority:   dict[str, int] | None     # C22; городской дефолт очереди
    perimeter_barrier:    PerimeterBarrier | None   # барьер **поселения** (прямые footprint); вычет из площади района — SettlementAssembler, не район
```

Источник данных: поля `NamedLocation` поселения. Собирается `SettlementAssembler` и передаётся вниз без изменений.

C22-поля: перечень и persist — [tz_city_generation.md](tz_city_generation.md) §3 (`⬜` в коде). Резолв N / очереди / фасада — [tz_structure_connections.md](tz_structure_connections.md) §5.1.3 (не дублировать таблицы здесь). Район перекрывает город **по ключу** (`district_template`) для counts/priority/frontage. `perimeter_barrier` на скелете — барьер **поселения** (прямые footprint), не района. `display_location_mood` / `state_uid` — city §3; в этот dataclass не входят (`state_uid` ⬜ в скелете отдельно).

---

**`AreaSlot`** — участок, выделенный `DistrictAssembler` (не синоним здания):

```python
@dataclass
class AreaSlot:
    cells:    list[tuple[int, int]]   # (x, y) участок из шаблона, любой structure_type; без z
    ground_z: int                      # опорная плоскость ЭТОГО участка (не порог улицы сам по себе)
    facing:   Facing                   # сторона участка к улице
```

`ground_z` — онтология **участка**, не района. Район не копирует одну z на слоты. Как считать z и **где порог к улице** — только `StructureAreaAssembler` (топология зоны). SoT порога: [tz_structure_connections.md](./tz_structure_connections.md) §5.1.1. Склейка: [tz_settlement_outdoor.md](./tz_settlement_outdoor.md) **C21**. `DistrictSlot.ground_z` — пин района, не пол участка.

`facing` — сторона к улице. Что на ней (дверь, ворота, открытый край) решает assembler участка.

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
| `gate` | двор + забор | ворота на facing забора (центр грани) | `waypoint` на воротах (`graph_level=area`); участок не `location_type` (C3) |
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

Здание не обязательно: участок = шаблон любого назначения (дом, таверна, площадь, …), не leftover packing. `building_location is None` — **только** если шаблон **не** даёт NamedLocation (типично `plaza` / сад: состав шаблона без здания). **Если шаблон даёт здание, а generate собрал участок без него** (`building_location is None`, пустой двор) — **критическая ошибка генерации участка**. Не plaza, не silent skip, не «участок без дома допустим». Слои не мешать. `threshold` / `approach` — рантайм assembler; extract пишет граф и `AreaSlotWire.ground_z` (плоскость участка), не kind порога. C20 — только если шаблон даёт здание с входом (здание без `front` — тоже ошибка generate, не этот кейс).

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
        world:         World,
        slot:          AreaSlot,
        template:      dict,
        city_skeleton: CitySkeleton,
        terrain_cells: list[MapCell] | None = None,
        *,
        street_xy:     AbstractSet[tuple[int, int]],  # полотно после DistrictAssembler._plan_streets
        cached_layout: StructureLayout | None = None,
        building_x:    int | None = None,
        building_y:    int | None = None,
    ) -> AreaLayout:
        # 1. _resolve_threshold() — топология; без street_xy
        # 2. slot.ground_z = median_surface_z(двор)
        # 3. _place_building() — черновой map_z с footprint
        # 4. measure_street_approach — peek z улицы; луч только при Δz
        # 5. θ > 45° → clamp_near_z_to_45 в map_z или threshold.z; measure ещё раз
        # 6. translate + context.ground_z = map_z + envelope
        # 7. stamp_approach_cells — grade/лестница
        # 8. _build_paths — только граф
        # 9. _build_barrier — slot.ground_z
```

Район зовёт assembler участка **после** `_plan_streets` и передаёт `street_xy`. Лог `INFO` на входе: `template.system_name`, `slot.facing`, `len(slot.cells)`.

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
cell_size_m = World.map_cell_size_m   # через generators/coordinates/cell_size_m(world)
```

> **Не** `world.map_settings["global_cell_size_m"]` — ghost key (NC-1g). См. [tz_city_generation.md](./tz_city_generation.md) §9.6, [tz_terrain_generation.md](./tz_terrain_generation.md) § coordinates.

Разграничение по слоям:

| Слой | Единица | Тип в коде |
|---|---|---|
| `SettlementAssembler` | планирует в глобальных ячейках `(cell_x, cell_y)` сетки города | `int` |
| `DistrictSlot` | мировые метры — `SettlementAssembler` вычисляет и укладывает в слот вместе с шаблоном | `int` |
| `DistrictAssembler` | работает в мировых метрах из `slot.origin_x/y, width_m, depth_m` | `int` |
| `AreaSlot` | абсолютные (x, y) в метрах; список ячеек | `list[tuple[int,int]]` |

Один район может занимать всю глобальную ячейку: `width_m = depth_m = cell_size_m`.

**Координаты:** hub `generators/coordinates/` — WORLD_SURFACE_GRID vs WORLD_LOCAL_METERS ([`.cursor/plans/coordinate-spaces.md`](../.cursor/plans/coordinate-spaces.md)).

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

#### Решение: generate-first, place-second

`DistrictAssembler` считает **оболочки** кандидатов до посадки (cache), затем сажает по реальным `w`,`h`. Полный интерьер всех домов до района — нет (C22). Порядок посадки — [connections](./tz_structure_connections.md) §5.1.3 «Пайплайн посадки», не bin-pack AABB `DistrictSlot`.

#### Алгоритм `DistrictAssembler`

```
1. Слот уже урезан поселением; якоря в слоте (`SettlementAssembler`). Инстанс барьера района — скип если нет поля / template null. Иначе inner bbox = слот минус прямые района (`sides` + `width_cells`) минус коридор
2. Кандидаты: allowed_structure_types ∩ тир ∪ required_structures
3. Cache оболочек (StructureAssembler; интерьер комнат — не этот скоуп)
4. Проход 1 — бронь приоритетных во внутреннем bbox (решётка block_size)
5. Рамка вокруг броней (не сквозь бронь / коридор якорей)
6. Проход 2 — остальная коллекция
7. Граф улиц → StructureAreaAssembler из cache (не второй generate)
8. Не влезло → warning, не exception
```

#### Кэш

- Живёт на уровне сборки одного поселения (`SettlementAssembler.assemble` создаёт и передаёт вниз)
- Ключ целевой: `(template, facing)` — connections §5.1.3 «Cache и facing». Код сейчас: `system_name`
- Значение: оболочка / `StructureLayout` (комнатная нарезка — не packing)
- Один шаблон (+ facing) → не генерировать заново на каждый слот

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
| Два `required_structures` с `position: center` | **CONN-PACK-2** — connections §8 |
| Envelope `(template, facing)` на проходе 1, пока полосы рамки нет | **CONN-PACK-3** — connections §8 |
| `DistrictSlot.facing` — нужна ли ориентация к главной улице города на уровне района | отложено |
