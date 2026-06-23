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
**Делает:** сетка улиц, типы кварталов, слоты зданий  
**Подробнее:** [tz_city_generation.md](tz_city_generation.md)

### DistrictAssembler
**Знает:** тип квартала, city skeleton  
**Делает:** назначает `building_template` каждому слоту по structure_type + economic_tier  
**Подробнее:** [tz_city_generation.md](tz_city_generation.md) — раздел 6 (алгоритм заполнения кварталов)

### StructureAreaAssembler
**Знает:** слот (позиция + размер), шаблон, city skeleton, terrain  
**Делает:**
- планировка участка: двор, забор (`barrier_template_registry`), малые постройки
- выводит `StructureContext` из `structure_type` + `architectural_style` + terrain
- вызывает `StructureAssembler`

**Источник `StructureContext`:** этот слой. Только он знает достаточно для вывода контекста.  
**Подробнее:** [tz_building_generator.md](tz_building_generator.md) — раздел 11 (StructureAssembler, StructureContext)

### StructureAssembler
**Знает:** `StructureContext`, terrain_cells  
**Делает:** фундамент + крыльцо/ступени + крыша поверх interior box  
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
