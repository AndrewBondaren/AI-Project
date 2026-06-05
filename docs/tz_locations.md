---
name: tz-locations
description: "ТЗ по системе локаций — два уровня карты, иерархия, terrain, климат, ресурсы, состояния, engine flow, фронтенд"
metadata: 
  node_type: memory
  type: project
  originSessionId: 633eddca-8d16-4119-94ab-ef548d071851
---

## Два уровня карты

**Уровень 1 — `map_cells`** — сырая матрица местности (sparse 3D grid):
```sql
map_cells (
  world_id, x, y, z,            -- PK; z глобальный, 1 единица = 3м; отрицательный = ниже уровня моря
  system_terrain,               -- ref → worlds.terrain_registry (структурный тип)
  cell_material,                -- nullable; ref → worlds.material_registry; null = материал implicit в terrain
  travel_modifier_override,     -- nullable; перекрывает terrain_registry.travel_modifier
  danger_level_override,        -- nullable; перекрывает terrain_registry.danger_level
  gap_width_override,           -- nullable int (метры); перекрывает terrain_registry.gap_width
  is_structural,                -- bool; несущая ячейка; учитывается в расчёте обрушения здания
  temperature_base,             -- nullable int; заполняется нодой генерации из climate_zone + z; null для indoor
  rainfall,                     -- nullable int 0–100; null для indoor
  location_uid                  -- nullable FK → named_locations
)
INDEX (world_id, x, y, z)
```
Весь мир — единое 3D-пространство. z=0 = уровень моря. Поверхностный terrain, подземелья, интерьеры — все в одной системе координат. **x = y = z = 1м на ячейку** — единая шкала без конвертаций. Этаж здания = 3 z-юнита (конвенция). LLM сырую матрицу не получает — только `named_locations`.

### Стратегия инициализации `map_cells`

**Eager — при создании/загрузке мира:**
1. **Surface** — поверхностный heightmap; 1 ячейка на (x, y) для каждой named_location
2. **Структурные объекты** — здания, заборы, стены, деревья, камни и прочие основные объекты (ячейки выше surface z)
3. **Буфер ±10 z** — все ячейки в диапазоне `[min_z_location − 10, max_z_location + 10]` для каждой named_location; покрывает мелкие подвалы, высокие постройки, первый уровень подземелья (±10 × 3м = ±30м)

**Lazy — по первому требованию:**
- Всё за пределами буфера ±10 z: глубокие пещеры, шахты, высокие горные пики без структур
- Триггер: первый вход персонажа / боевая сцена / явная генерация мира
- Lazy-генерация идёт z-срезами (все (x,y) на одном z), не ячейками по одной

**Порядок генерации:**
- Активная локация → блокирующая генерация (SceneInitNode ждёт)
- Соседние локации → фоновая, опционально (v1: не реализуется; добавляется если генерация окажется узким местом)

**Индексы `map_cells`:**
- PRIMARY: `(world_id, x, y, z)` — точечные запросы
- Дополнительный: `(world_id, location_uid, z)` — запросы по уровню локации при lazy-инициализации и загрузке сцены
- R-tree (SQLite rtree) — отложено до реализации боёвки (AoE, line-of-sight)

`named_locations` без единой ячейки в `map_cells` — валидное состояние; локация существует нарративно.

**Уровень 2 — `named_locations`** — агрегат ячеек с именем:
```sql
named_locations (
  location_uid, world_uid,
  display_name,                 -- обязательное, отображаемое имя
  location_type,                -- ref → worlds.location_type_registry.system_type
  created_at,                   -- ISO timestamp
  parent_location_uid,          -- nullable FK → self (дерево иерархии, NULL у корней)
  location_subtype,             -- nullable
  system_description, display_description,
  glossary_ref, tag_refs,       -- JSON array
  is_discovered,                -- bool default False; скрыта до исследования
  is_accessible,                -- bool default True; управляется движком через события
  -- interior_width / interior_height убраны; размер уровня implicit из map_cells ячеек
  entry_difficulty,             -- nullable int 0–100; физическое препятствие входа
  guard_level,                  -- nullable int 0–100; охраняемость
  system_location_mood,         -- nullable; LLM-нарратив атмосферы на основе location_states
  display_location_mood,        -- "Город охватила паника. На улицах пусто."
  owner_uid,                    -- nullable FK → character_sheet; персональный владелец
  climate_zone,                 -- nullable ref → worlds.climate_zone_registry; null = наследует от parent
  state_uid,                    -- nullable; soft ref → states; orphan = ничейная, движок логирует
  city_size,                    -- nullable; ref → worlds.city_size_registry; актуально для settlement
  economic_tier,                -- nullable; ref → worlds.economic_tier_registry; null = наследует от parent; если у всех предков null → медианный тир (index = floor(count/2) по base_value ASC) + лог WARNING
  is_public,                    -- bool default false; публичная локация — NPC-занятость не блокирует старт игрока
  is_forbidden                  -- bool default false; restricted-зона — location_faction_access переходит в режим allowlist
)
-- __update_exclude__ = {"world_uid"} — world_uid неизменяем при update
-- Инвариант: is_public=true AND is_forbidden=true — невалидная комбинация; движок логирует WARNING
```

---

## Размер поселения

### `worlds.city_size_registry` (N+1)

```json
[
  { "system_size": "hamlet",      "display_size": "Хутор",       "map_cells_count": 1  },
  { "system_size": "village",     "display_size": "Деревня",     "map_cells_count": 2  },
  { "system_size": "town",        "display_size": "Городок",     "map_cells_count": 4  },
  { "system_size": "city",        "display_size": "Город",       "map_cells_count": 9  },
  { "system_size": "metropolis",  "display_size": "Метрополис",  "map_cells_count": 20 },
  { "system_size": "megalopolis", "display_size": "Мегалополис", "map_cells_count": 50 }
]
```

- `map_cells` — footprint: количество поверхностных (x,y) позиций; не 3D-объём
- Работает одинаково для hex и square — движок оперирует количеством, не формой
- `city_size` на `named_locations` — nullable; актуально только для settlement-типа

---

## Иерархия локаций

```
region       (depth 0) — корень, не показывается игроку при выборе стартовой локации
territory    (depth 1)
settlement   (depth 2)
district     (depth 3) — outdoor: городские кварталы, площади, рынки
building     (depth 4) — indoor: строение; leaf-сцена здесь если нет rooms; типичный home персонажа
room         (depth 5) — indoor: комната внутри building; leaf, здесь создаётся сцена
```

Глубина не хранится. Вычисляется через `WITH RECURSIVE` CTE по `parent_location_uid` on-demand — всегда точно, нет проблемы синхронизации.

**Три чётких понятия:**

| Тип | Пример | outdoor? | leaf? | Источник |
|---|---|---|---|---|
| `district` | Торговый квартал, Портовый район | `true` | нет | вручную / LLM |
| `building` | Таверна, Арсенал, Особняк | `false` | нет (если есть rooms) | `building_template_registry` |
| `room` | Общий зал, Кухня, Подвал | `false` | **да** | `room_type_registry` внутри building |

Строение без внутренних комнат (`room`) — `building` сам является leaf-локацией и сценой.

### `worlds.location_type_registry` (N+1)

```json
[
  { "system_type": "region",     "display_type": "Регион",     "parent_types": [null],                       "is_outdoor": true,  "subtypes": [] },
  { "system_type": "territory",  "display_type": "Территория", "parent_types": ["region"],                   "is_outdoor": true,  "subtypes": [
      { "system_subtype": "island",       "border_category": "liquid" },
      { "system_subtype": "mountain",     "border_category": null     },
      { "system_subtype": "underground",  "border_category": null     }
  ]},
  { "system_type": "settlement", "display_type": "Поселение",  "parent_types": ["territory"],                "is_outdoor": true,  "subtypes": [
      { "system_subtype": "city",             "border_category": null },
      { "system_subtype": "village",          "border_category": null },
      { "system_subtype": "dungeon",          "border_category": null },
      { "system_subtype": "underground_city", "border_category": null }
  ]},
  { "system_type": "district",   "display_type": "Район",      "parent_types": ["settlement"],               "is_outdoor": true,  "subtypes": [] },
  { "system_type": "building",   "display_type": "Строение",   "parent_types": ["settlement","district"],    "is_outdoor": false, "subtypes": [
      { "system_subtype": "residential", "border_category": null },
      { "system_subtype": "commercial",  "border_category": null },
      { "system_subtype": "military",    "border_category": null },
      { "system_subtype": "religious",   "border_category": null }
  ]},
  { "system_type": "room",       "display_type": "Помещение",  "parent_types": ["building"],                 "is_outdoor": false, "subtypes": [
      { "system_subtype": "porch",           "border_category": null },
      { "system_subtype": "entrance_steps",  "border_category": null }
  ]}
]
```

`porch` и `entrance_steps` — субтипы `room` с `is_outdoor` override на уровне `NamedLocation` (поле `is_outdoor` на записи, не из реестра). `entrance_steps` дополнительно имеет `is_transit=true`.

- `system_type` — immutable ключ движка; `display_type` — редактируемое имя; N+1 — пользователь добавляет свои типы
- `is_outdoor: true` — применяются weather, travel_ticks, danger_level, terrain-правила
- `is_outdoor: false` — indoor: нет weather, навигация через `location_passages`, ячейки типа floor/wall/door
- `border_category` — граничные ячейки локации должны быть этой terrain_category
- `is_public` / `is_forbidden` — живут на `building`; на `room` — переопределения для конкретных комнат
- Пользователь добавляет кастомные типы на любом уровне

**Правила валидации:**
- `named_locations.parent.location_type` обязан входить в `child.location_type_registry.parent_types`
- `location_subtype` обязан существовать в `location_type_registry[location_type].subtypes`
- `room` без `building`-родителя — невалидно

### Вертикальное наложение локаций

Две named_locations могут иметь одинаковый (x,y) footprint но разные z — это валидно. Каждая ячейка `(x, y, z)` уникальна и принадлежит ровно одной named_location:

```
Наземный город:    map_cells (x, y, z=33) → location_uid = "city_surface"
Подземный город:   map_cells (x, y, z=28) → location_uid = "city_underground"
```

- `named_locations.state_uid` — отдельное поле на каждой; наземный и подземный город могут принадлежать разным государствам
- Вход с поверхности в подземный город — `location_entry_points` на z=33 с `leads_to_level_uid` подземного города
- Нарративный пример: оккупированная поверхность (государство A) + подземное сопротивление (государство B) — полностью в рамках схемы

---

## Terrain

### `worlds.danger_level_registry` (N+1)

```json
[
  { "system_danger": "none",   "display_danger": "Безопасно", "priority": 0 },
  { "system_danger": "low",    "display_danger": "Низкая",    "priority": 1 },
  { "system_danger": "medium", "display_danger": "Средняя",   "priority": 2 },
  { "system_danger": "high",   "display_danger": "Высокая",   "priority": 3 }
]
```

`priority` — числовой порядок; движок вычисляет `danger_level` маршрута через `max(segment.priority)`.  
N+1: пользователь добавляет кастомные уровни (sci-fi: `"irradiated"` priority=2, `"lethal"` priority=4).

---

### `worlds.terrain_category_registry` (N+1)
```json
[
  { "system_category": "solid",   "passable": true,  "jumpable": false, "climbable": false, "breakable": false },
  { "system_category": "liquid",  "passable": false, "jumpable": false, "climbable": false, "breakable": false },
  { "system_category": "aerial",  "passable": false, "jumpable": false, "climbable": false, "breakable": false },
  { "system_category": "crevice", "passable": false, "jumpable": true,  "climbable": false, "breakable": false },
  { "system_category": "barrier", "passable": false, "jumpable": false, "climbable": true,  "breakable": true  }
]
```
`underground` убран — ячейка при z < 0 уже физически под землёй; категория дублировала z.
- `passable: false` → непроходимо без спец. способности (`terrain_access`)
- `jumpable: true` → jump action через gap_width; `aerial` terrain_access обходит все категории
- `climbable: true` → climb action; возможна без спец. способности, модифицируется статами
- `breakable: true` → break/destroy action; `map_cells.system_terrain` → `"rubble"`; `cell_state` → `"destroyed"`; `cell_material` не меняется; если `is_structural=true` → движок пересчитывает структурную целостность здания

**Структурная целостность здания:**
```
total_structural   = COUNT(map_cells WHERE location_uid=X AND is_structural=true AND system_terrain != "rubble")
avg_strength       = AVG(material_registry[cell_material].structural_strength
                         for is_structural=true AND system_terrain != "rubble" cells)
collapse_threshold = max(1, round(total_structural × avg_strength))
destroyed_count    = COUNT(map_cells WHERE location_uid=X AND is_structural=true AND system_terrain = "rubble")

if destroyed_count >= collapse_threshold:
    → все ячейки location_uid выше foundation z → "rubble"
    → location_state: "destroyed"
    → урон персонажам внутри (fall_formula × g)
else:
    → локальный расчёт: ячейки над разрушенной без боковой опоры → "rubble"
```
`structural_strength` default при создании нового материала = `0.1` (консервативный).

### `worlds.material_registry` (N+1)

**`material_category`** — фиксированный enum движка, **не расширяется пользователем**. Движок строит физику на этих трёх категориях:

| `material_category` | Физика движка |
|---|---|
| `solid` | падает если `g > 0` и нет опоры снизу; всплывает если `density < liquid.density`; горит если `flammable`; замерзает если `freezable`; разрушается кислотой если `corrodible`; плавится от жара если `meltable`; добывается если `mineable`; блокирует обзор если `transparent: false` |
| `liquid` | течёт вниз по z; слоение: более плотная жидкость опускается ниже; утопание; температурный урон если `temp_damage`; блокирует видимость если `vision_block` |
| `gas` | движение по z определяется `density` относительно соседей: тяжелее → оседает вниз, легче → поднимается; блокирует видимость если `vision_block`; токсичность если `temp_damage` |

Конкретные материалы — N+1; пользователь добавляет любые, указывая **одну из трёх** фиксированных категорий.  
При создании материала пользователем — дефолты если поле не указано:

| Поле | Default | Логика |
|---|---|---|
| `flammable` | `false` | только явно горючие материалы горят |
| `freezable` | `false` | только явно замерзаемые замерзают |
| `corrodible` | `true` | большинство материалов поддаются коррозии |
| `meltable` | `false` | только явно плавкие плавятся |
| `mineable` | `false` | только явно добываемые добываются |
| `transparent` | `false` | материал непрозрачен по умолчанию |

В БД все поля всегда хранятся явно — пустых значений нет.

```json
[
  { "system_material": "stone",     "display_name": "Камень",        "glossary_ref": null, "material_category": "solid",  "tags": ["construction", "mineral"],          "use_type": ["wall", "floor", "column"], "economic_tier": "standard", "hardness": 3, "density": 250, "structural_strength": 0.8,  "flammable": false, "freezable": false, "corrodible": true,  "meltable": false, "mineable": true,  "transparent": false, "components": null },
  { "system_material": "wood",      "display_name": "Дерево",        "glossary_ref": null, "material_category": "solid",  "tags": ["construction", "organic"],           "use_type": ["wall", "floor", "door", "railing"], "economic_tier": "basic", "hardness": 2, "density": 60,  "structural_strength": 0.3,  "flammable": true,  "freezable": false, "corrodible": true,  "meltable": false, "mineable": false, "transparent": false, "components": null },
  { "system_material": "iron",      "display_name": "Железо",        "glossary_ref": null, "material_category": "solid",  "tags": ["metal", "mineral"],                  "use_type": ["wall", "door", "gate", "railing"], "economic_tier": "standard", "hardness": 4, "density": 800, "structural_strength": 0.9,  "flammable": false, "freezable": false, "corrodible": true,  "meltable": true,  "mineable": false, "transparent": false, "components": null },
  { "system_material": "earth",     "display_name": "Земля",         "glossary_ref": null, "material_category": "solid",  "tags": ["raw", "mineral"],                    "use_type": ["floor"], "economic_tier": "poor", "hardness": 1, "density": 150, "structural_strength": 0.2,  "flammable": false, "freezable": false, "corrodible": true,  "meltable": false, "mineable": true,  "transparent": false, "components": null },
  { "system_material": "crystal",   "display_name": "Кристалл",      "glossary_ref": null, "material_category": "solid",  "tags": ["mineral", "magic"],                  "use_type": ["wall", "floor"], "economic_tier": "premium", "hardness": 3, "density": 260, "structural_strength": 0.4,  "flammable": false, "freezable": false, "corrodible": false, "meltable": false, "mineable": false, "transparent": true, "components": null },
  { "system_material": "water",     "display_name": "Вода",          "glossary_ref": null, "material_category": "liquid", "tags": [],                                    "use_type": [], "economic_tier": null, "hardness": null, "density": 100, "structural_strength": null, "flammable": false, "freezable": true,  "corrodible": false, "meltable": false, "temp_damage": false, "vision_block": false, "components": null },
  { "system_material": "lava",      "display_name": "Лава",          "glossary_ref": null, "material_category": "liquid", "tags": [],                                    "use_type": [], "economic_tier": null, "hardness": null, "density": 270, "structural_strength": null, "flammable": false, "freezable": false, "corrodible": false, "meltable": false, "temp_damage": true,  "vision_block": false, "components": null },
  { "system_material": "air",       "display_name": "Воздух",        "glossary_ref": null, "material_category": "gas",    "tags": [],                                    "use_type": [], "economic_tier": null, "hardness": null, "density": 1,   "structural_strength": null, "flammable": false, "freezable": false, "corrodible": false, "meltable": false, "temp_damage": false, "vision_block": false, "components": null },
  { "system_material": "smoke",     "display_name": "Дым",           "glossary_ref": null, "material_category": "gas",    "tags": [],                                    "use_type": [], "economic_tier": null, "hardness": null, "density": 2,   "structural_strength": null, "flammable": false, "freezable": false, "corrodible": false, "meltable": false, "temp_damage": false, "vision_block": true,  "components": null },
  { "system_material": "toxic_gas", "display_name": "Токсичный газ", "glossary_ref": null, "material_category": "gas",    "tags": [],                                    "use_type": [], "economic_tier": null, "hardness": null, "density": 3,   "structural_strength": null, "flammable": true,  "freezable": false, "corrodible": false, "meltable": false, "temp_damage": true,  "vision_block": true,  "components": null }
]
```

### `worlds.terrain_registry` (N+1)

Структурный тип ячейки. `cell_material` на `map_cells` указывает из чего сделан. `has_state: true` — ячейка имеет динамическое состояние.

```json
[
  { "system_terrain": "plains",      "glossary_ref": "terrain_plains",      "terrain_category": "solid",   "travel_modifier": 1.5, "danger_level": "none",   "has_state": false, "default_state": null,     "default_material": "earth"  },
  { "system_terrain": "forest",      "glossary_ref": "terrain_forest",      "terrain_category": "solid",   "travel_modifier": 2.5, "danger_level": "medium", "has_state": false, "default_state": null,     "default_material": "wood"   },
  { "system_terrain": "liquid_body", "glossary_ref": "terrain_liquid_body", "terrain_category": "liquid",  "travel_modifier": null,"danger_level": "high",   "has_state": false, "default_state": null,     "default_material": "water"  },
  { "system_terrain": "crevice",     "glossary_ref": "terrain_crevice",     "terrain_category": "crevice", "travel_modifier": null,"danger_level": "high",   "has_state": false, "default_state": null,     "default_material": "stone", "gap_width": 2 },
  { "system_terrain": "floor",       "glossary_ref": "terrain_floor",       "terrain_category": "solid",   "travel_modifier": 1.0, "danger_level": "none",   "has_state": false, "default_state": null,     "default_material": null     },
  { "system_terrain": "roof",        "glossary_ref": "terrain_roof",        "terrain_category": "solid",   "travel_modifier": 1.0, "danger_level": "none",   "has_state": false, "default_state": null,     "default_material": null     },
  { "system_terrain": "wall",        "glossary_ref": "terrain_wall",        "terrain_category": "barrier", "travel_modifier": null,"danger_level": "none",   "has_state": false, "default_state": null,     "default_material": null     },
  { "system_terrain": "door",        "glossary_ref": "terrain_door",        "terrain_category": "barrier", "travel_modifier": null,"danger_level": "none",   "has_state": true,  "default_state": "closed", "default_material": null     },
  { "system_terrain": "gate",        "glossary_ref": "terrain_gate",        "terrain_category": "barrier", "travel_modifier": null,"danger_level": "none",   "has_state": true,  "default_state": "closed", "default_material": null     },
  { "system_terrain": "window",      "glossary_ref": "terrain_window",      "terrain_category": "barrier", "travel_modifier": null,"danger_level": "none",   "has_state": true,  "default_state": "closed", "default_material": null     },
  { "system_terrain": "open_space",  "glossary_ref": "terrain_open_space",  "terrain_category": "aerial",  "travel_modifier": null,"danger_level": "none",   "has_state": false, "default_state": null,     "default_material": null     },
  { "system_terrain": "rubble",      "glossary_ref": "terrain_rubble",      "terrain_category": "solid",   "travel_modifier": 2.0, "danger_level": "low",    "has_state": false, "default_state": null,     "default_material": null     }
]
```

**Эффективный материал:**
```
effective_material = cell_material ?? terrain_registry[terrain].default_material
```
Если оба null — движок считает ячейку non-flammable, non-mineable. Interior terrain (floor, wall, door, gate, window) — материал всегда задаётся явно при генерации здания; `default_material: null`. Outdoor terrain — резолвится через `default_material` (forest → wood → flammable: true; liquid_body → water → flammable: false). Пользователь может переопределить liquid_body с `cell_material = "oil"` — тогда водоём горит.

`roof` vs `floor`: оба solid, проходимы. `floor` — indoor; `roof` — внешняя поверхность, открыта погоде. Без `roof`-ячейки на верхнем z здания — крыша отсутствует, `open_space` выше.  
**Потолок** — не terrain type. Потолок комнаты = нижняя грань solid-ячейки на z+1. Имплицитен в 3D-сетке.

`has_state: true` — terrain нативно интерактивен (door, gate, window); при создании ячейки движок вставляет запись в `cell_states` с `system_state = default_state`.  
Fallback: если `cell_states` пуст для `has_state: true` ячейки — движок использует `default_state` из реестра и логирует WARNING. Environmental-состояния (пожар, затопление, разрушение) — в `cell_states` для **любой** ячейки независимо от `has_state`.

- `travel_modifier: null` → непроходимо по умолчанию; `display_terrain` из `lore_registry` по `glossary_ref`
- Переопределения на уровне ячейки: `map_cells.travel_modifier_override`, `danger_level_override`, `gap_width_override`

**Эффективный модификатор:**
```
base_modifier      = map_cells.travel_modifier_override ?? terrain_registry[terrain].travel_modifier
state_delta        = Σ(cell_state_registry[s].travel_modifier_delta
                       for s in active_cell_states WHERE travel_modifier_delta IS NOT NULL)
effective_modifier = base_modifier + state_delta   -- если base_modifier = null → остаётся null (terrain непроходим)

effective_danger_level = max(
  map_cells.danger_level_override ?? terrain_registry[terrain].danger_level,
  max(cell_state_registry[s].danger_level for s in active_cell_states WHERE danger_level IS NOT NULL)
)  -- сравнение через danger_level_registry.priority
```

### `cell_states` — состояния ячеек

```sql
cell_states (
  id,
  world_uid,
  x, y, z,        -- composite ref → map_cells (world_uid, x, y, z)
  system_state,   -- ref → worlds.cell_state_registry
  display_state,
  started_at,     -- игровое время; nullable = с начала мира
  ended_at        -- nullable = активное состояние
)
INDEX (world_uid, x, y, z)
```

- Одна ячейка может иметь несколько одновременных состояний (дверь `broken` + `burning`)
- Активные = `ended_at IS NULL`; история сохраняется для нарратива
- Работает для любой ячейки — не только `has_state: true` terrain
- Soft ref → `map_cells`: orphan-tolerant. В штатном флоу orphan невозможен — событие на ячейке требует присутствия персонажа, которое гарантирует инициализацию `map_cells`.
- Orphan recovery (аномальный случай):
  ```
  similar_neighbors   = COUNT(map_cells WHERE system_terrain = orphan_terrain
                              AND distance(x,y,z) <= 1 AND world_uid = orphan.world_uid)
  substitution_chance = min(similar_neighbors / 4, 1.0)

  roll < substitution_chance → перенос cell_state на ближайшую похожую ячейку; лог INFO
  roll >= substitution_chance → состояние игнорируется; лог WARNING
  ```

### `worlds.cell_state_registry` (N+1)

```json
[
  { "system_state": "open",      "display_state": "Открыто",    "state_category": "interactive",   "travel_modifier_delta": null, "danger_level": null   },
  { "system_state": "closed",    "display_state": "Закрыто",    "state_category": "interactive",   "travel_modifier_delta": null, "danger_level": null   },
  { "system_state": "locked",    "display_state": "Заперто",    "state_category": "interactive",   "travel_modifier_delta": null, "danger_level": null   },
  { "system_state": "broken",    "display_state": "Сломано",    "state_category": "interactive",   "travel_modifier_delta": null, "danger_level": null   },
  { "system_state": "boarded",   "display_state": "Заколочено", "state_category": "interactive",   "travel_modifier_delta": null, "danger_level": null   },
  { "system_state": "damaged",   "display_state": "Повреждено", "state_category": "environmental", "travel_modifier_delta": 0.3,  "danger_level": null   },
  { "system_state": "burning",   "display_state": "Горит",      "state_category": "environmental", "travel_modifier_delta": 1.0,  "danger_level": "high" },
  { "system_state": "flooded",   "display_state": "Затоплено",  "state_category": "environmental", "travel_modifier_delta": 0.5,  "danger_level": "low"  },
  { "system_state": "collapsed", "display_state": "Обрушено",   "state_category": "environmental", "travel_modifier_delta": null, "danger_level": "low"  },
  { "system_state": "destroyed", "display_state": "Разрушено",  "state_category": "environmental", "travel_modifier_delta": null, "danger_level": null   }
]
```

`travel_modifier_delta` — аддитивная добавка к `base_modifier`; null = нет механического эффекта (fallback = 0)  
`danger_level` — ref → `worlds.danger_level_registry`; null = не меняет danger ячейки  
`state_category: "interactive"` — нативный для конкретного terrain type (door, window); проходимость управляется движком отдельно  
`state_category: "environmental"` — любая ячейка; пожар, потоп, радиация, магическое проклятие  
Пользователь добавляет свои через N+1 (sci-fi: `irradiated`, `depressurized`; fantasy: `cursed`)

---

### Проходимость (terrain_access)

Три источника; движок агрегирует:
```
character_terrain_access = union(race.terrain_access, active_perks[].terrain_access, equipped_items[].terrain_access)
can_traverse(category)   = category.passable OR category IN character_terrain_access
```

**Прыжок через расщелину** (jumpable=true):
```
effective_gap_width = map_cells.gap_width_override ?? terrain_registry[terrain].gap_width
jump_result         = jump_formula(character_stats)    -- из worlds.action_formulas; null = отключено
```
- `jump_result >= effective_gap_width` → перепрыгивает
- `jump_result < gap_width` → assessment event ("персонаж оценивает как невозможный"); попытка доступна → падение → `fall_formula`
- NPC решает через `system_npc_goal` + `system_traits`
- `aerial` terrain_access → обходит расщелину без прыжка

---

## Точки входа

### `location_entry_points`
```sql
location_entry_points (
  entry_uid,
  location_uid,                -- FK → named_locations; к какой локации относится вход
  x, y, z,                    -- координата ячейки в map_cells (физическая позиция входа)
  leads_to_level_uid,          -- nullable FK → location_levels; на каком уровне оказываемся; null = ground floor
  display_name,                -- "Северные ворота", "Пролом в стене"
  entry_difficulty_override,   -- nullable int 0–100
  guard_level_override,        -- nullable int 0–100
  is_discovered,               -- туман войны
  is_accessible,               -- управляется движком
  glossary_ref, tag_refs
)
```

**Effective значения:**
```
effective_entry_difficulty = entry_point.entry_difficulty_override ?? location.entry_difficulty ?? 0
effective_guard_level      = entry_point.guard_level_override      ?? location.guard_level      ?? 0
```

**Семантика:**
- `entry_difficulty` — физическое препятствие: стены, засов, узкий лаз; action-путь: climbing, lockpick
- `guard_level` — охраняемость: стража, ловушки, барьер; action-путь: stealth, social, combat
- `effective = 0` → обычное передвижение без action
- `leads_to_level_uid = null` → ground floor локации (location_levels с минимальным z ≥ terrain z входа)

**Pathfinding:**
- К локации → ближайший `is_discovered AND is_accessible` entry point → A* цель по (x, y, z)
- Несколько известных entry points → движок передаёт все варианты с difficulty/guard_level; выбор за игроком/NPC
- Нет известных entry points → A* по центроиду ячеек локации; z = среднее z всех ячеек (outdoor territory)

---

## Дороги

### `worlds.road_type_registry` (N+1)
```json
[
  { "system_road_type": "royal_road",  "glossary_ref": "road_royal",  "travel_modifier": 0.8 },
  { "system_road_type": "common_road", "glossary_ref": "road_common", "travel_modifier": 1.0 },
  { "system_road_type": "trail",       "glossary_ref": "road_trail",  "travel_modifier": 1.3 }
]
```
`display_road_type` и лор-описание — из `lore_registry` по `glossary_ref`; `travel_modifier < 1.0` = быстрее базы.

### `roads`
```sql
roads (
  road_uid, world_id, display_name,
  road_type,                    -- ref → worlds.road_type_registry
  travel_modifier_override,     -- nullable
  from_location, to_location,   -- FK → named_locations
  is_bidirectional,
  danger_level,
  glossary_ref, tag_refs
)
```

### Маршрутный отчёт LLM

Движок считает оба варианта, LLM не навигирует граф самостоятельно:
```json
{
  "direct": { "terrain_sequence": ["plains","forest","swamp"], "danger_level": "high", "travel_ticks": 24 },
  "road":   { "waypoints": ["Деревня","Перекрёсток","Столица"], "road_names": ["Тракт"], "danger_level": "low", "travel_ticks": 16 }
}
```
`danger_level` маршрута = максимальный по всем сегментам пути.

---

## Внутренние пространства (interior)

Локации с `is_outdoor: false` (building, room) — в той же 3D-системе координат что и terrain. Ячейки `map_cells` с `location_uid` образуют физическое пространство уровня.

**Правило `map_cells.location_uid` для interior:**

| Ячейка | `location_uid` | Логика |
|---|---|---|
| wall, roof, `is_structural=true` | **building** | несущие и общие элементы; граница между комнатами |
| floor/потолок комнаты | **room** | физическая граница конкретной комнаты |
| open_space внутри здания | **building** | не принадлежит ни одной комнате |

Здание — родитель. Комната — дочерний именованный объём. Физический объём здания = `map_cells WHERE location_uid = building_uid` + union всех `map_cells WHERE location_uid IN (child_room_uids)`.

`room.map_cells` — физическая граница комнаты: SceneContextBuilderNode запрашивает `WHERE location_uid = room_uid` чтобы знать размер и форму комнаты для scene context.

Structural integrity formula не меняется: `COUNT(map_cells WHERE location_uid = building_uid AND is_structural=true ...)` — несущие ячейки всегда принадлежат зданию.

### `location_levels` — уровни (этажи) локации
```sql
location_levels (
  level_uid,
  location_uid,   -- FK → named_locations ON DELETE CASCADE
  z,              -- int; глобальный абсолютный; тот же масштаб что map_cells.z (1 ед. = 3м)
  display_name,   -- "Подвал", "Первый этаж", "Крыша"
  is_accessible   -- bool; управляется движком
)
```
- `z` глобальный в метрах: здание на terrain z=100м → ground floor level.z=100, второй этаж z=103, подвал z=97 (этаж = 3 z-юнита = 3м)
- Размер уровня (ширина/высота) implicit из принадлежащих ему `map_cells` ячеек
- Локация без `location_levels` → только нарратив, без позиционирования

### `location_passages` — переходы между локациями
```sql
location_passages (
  passage_uid, world_id,
  from_level_uid, from_x, from_y,   -- позиция входа (уровень + локальные координаты)
  to_level_uid,   to_x,   to_y,     -- позиция выхода
  is_bidirectional,
  passage_type,                     -- ref → worlds.passage_type_registry
  display_name,                     -- "Дубовая дверь", "Лестница на крышу", "Верёвка"
  glossary_ref, tag_refs
)
```
- Вертикальные переходы (лестница, верёвка): from_level.z ≠ to_level.z
- Горизонтальные (дверь, коридор): from_level.z = to_level.z
- Нет `travel_ticks` — interior-переходы логические, без временной стоимости

### `worlds.passage_type_registry` (N+1)
```json
[
  { "system_type": "door",      "display_type": "Дверь"               },
  { "system_type": "doorway",   "display_type": "Дверной проём"       },
  { "system_type": "archway",   "display_type": "Арочный проём"       },
  { "system_type": "corridor",  "display_type": "Коридор"             },
  { "system_type": "staircase", "display_type": "Лестница"            },
  { "system_type": "ladder",    "display_type": "Лестница-стремянка"  },
  { "system_type": "rope",      "display_type": "Верёвка"             },
  { "system_type": "bridge",    "display_type": "Мост / переход"      },
  { "system_type": "portal",    "display_type": "Портал"              },
  { "system_type": "fall",      "display_type": "Провал"              }
]
```
`fall` — однонаправленный; создаётся движком при разрушении пола/появлении ямы в бою.

### `placement_type_registry` (глобальный фиксированный)

Движок строит физику размещения на этих типах. Не расширяется пользователем.

```json
[
  { "system_placement": "floor",          "default_takeable": true,  "needs_direction": false, "needs_parent": false },
  { "system_placement": "wall",           "default_takeable": true,  "needs_direction": true,  "needs_parent": false },
  { "system_placement": "ceiling",        "default_takeable": false, "needs_direction": false, "needs_parent": false },
  { "system_placement": "embedded_wall",  "default_takeable": false, "needs_direction": true,  "needs_parent": false },
  { "system_placement": "embedded_floor", "default_takeable": false, "needs_direction": false, "needs_parent": false },
  { "system_placement": "embedded_ceil",  "default_takeable": false, "needs_direction": false, "needs_parent": false },
  { "system_placement": "on_object",      "default_takeable": true,  "needs_direction": false, "needs_parent": true  }
]
```

`embedded_*` — вделано в поверхность (фреска, роспись, мозаика, витраж); не берётся, часть интерьера.  
`on_object` — на/в другом объекте; требует `parent_object_uid`.

### `location_objects` — статические объекты
```sql
location_objects (
  object_uid,
  level_uid,              -- FK → location_levels ON DELETE CASCADE
  display_name,           -- "Полка с книгами", "Картина «Закат»"
  x, y,                   -- локальная позиция внутри footprint уровня
  placement_type,         -- ref → placement_type_registry
  wall_direction,         -- nullable; "north"|"south"|"east"|"west"; для wall/embedded_wall
  height_offset,          -- nullable int; z-единицы над полом; для wall и ceiling объектов
  parent_object_uid,      -- nullable FK → location_objects; только для on_object
  display_as_group,       -- bool; true = LLM видит только display_name, дети скрыты до взаимодействия
  system_description, display_description,
  is_interactive,         -- bool
  is_takeable,            -- bool; дефолт из placement_type.default_takeable; можно переопределить
  item_uid,               -- nullable FK → items
  is_accessible           -- bool
)
```

**Логика рендеринга для LLM:**
```
Объекты без parent_object_uid (корневые):
  display_as_group = false → LLM видит объект + description сразу
  display_as_group = true  → LLM видит только display_name ("Полка с книгами")
    └─ дети (on_object) скрыты; раскрываются при is_interactive + действии игрока
```

Принцип: не грузить детей пока не нужно — тот же паттерн что lazy-инициализация map_cells.

**Пример LLM-контекста комнаты:**
```
north wall: "Закат над морем" (картина)
floor (2,1): Полка с книгами (интерактивна)
floor (3,1): Стойка с оружием (интерактивна)
embedded_floor: Мозаика с гербом (не берётся)
ceiling: Железная люстра
```

Игрок: "посмотрю что на полке" → движок достаёт детей по `parent_object_uid` → LLM получает список с названиями и описаниями.

`items.placement_types` (JSON array) — куда предмет CAN быть размещён; движок валидирует при создании `location_objects`.  
Примеры: картина `["wall","embedded_wall"]`; люстра `["ceiling"]`; книга `["floor","on_object"]`; мозаика `["embedded_floor"]`.

---

## Экономические уровни

### `worlds.economic_tier_registry` (N+1)

Универсальная шкала ценности — работает в любом сеттинге. `display_tier` пользователь переименовывает под мир (фэнтези: "Крестьянский/Благородный"; sci-fi: "Базовый имплант/Военная разработка").

```json
[
  { "system_tier": "poor",        "display_tier": "Хлам",          "base_value": 0    },
  { "system_tier": "basic",       "display_tier": "Базовый",        "base_value": 1    },
  { "system_tier": "standard",    "display_tier": "Стандартный",    "base_value": 10   },
  { "system_tier": "quality",     "display_tier": "Качественный",   "base_value": 100  },
  { "system_tier": "premium",     "display_tier": "Премиальный",    "base_value": 500  },
  { "system_tier": "exceptional", "display_tier": "Исключительный", "base_value": 2000 }
]
```

`display_tier` — редактируемое название, пользователь переименовывает под сеттинг.  
Порядок тиров всегда определяется `base_value` ASC — никакой сортировкой по имени.

`base_value` — в базовых единицах валюты мира. Пользователь добавляет свои уровни через N+1.

**Использование:**
- `items.item_value_tier` — ценность предмета
- `named_locations.economic_tier` — ценовой уровень локации/здания
- `building_template_registry[].economic_tier_range` — диапазон при генерации

**Фактическая цена** (отложено до системы экономики):
```
price = tier.base_value × location.economic_modifier × supply_demand_modifier × currency_conversion
```

---

## Генерация структур

Три режима генерации — не взаимоисключающие, компонуются:

| Режим | Как работает |
|---|---|
| **Import** | Пользователь поставляет готовый JSON мира/локации/здания; движок парсит → map_cells; валидация на входе |
| **LLM** | Пользователь описывает словами → LLM получает terrain/material/template реестры в контексте → генерирует JSON ячеек → валидация → repair loop |
| **Template engine** | Пользователь выбирает шаблон + параметры → движок рандомизирует в рамках диапазонов → генерирует map_cells |

Шаблоны — всегда per-world (ссылаются на `material_registry` мира).

### `worlds.room_type_registry` (N+1)

Реестр типов комнат. Чисто семантический — только ключ и лор для LLM. Механические правила (размер, смежность, уровень, доступ) — в шаблоне здания, не здесь.

```json
[
  { "system_room": "entrance",    "glossary_ref": "room_entrance"    },
  { "system_room": "common_hall", "glossary_ref": "room_common_hall" },
  { "system_room": "kitchen",     "glossary_ref": "room_kitchen"     },
  { "system_room": "guest_room",  "glossary_ref": "room_guest"       },
  { "system_room": "cellar",      "glossary_ref": "room_cellar"      },
  { "system_room": "corridor",    "glossary_ref": "room_corridor"    },
  { "system_room": "balcony",     "glossary_ref": "room_balcony"     }
]
```

`display_name` и описание типа комнаты → `lore_registry[glossary_ref]`.

**Роль реестра:** валидация при импорте шаблона в мир — `room_type` каждой комнаты шаблона должен существовать в реестре. Неизвестный тип → `ImportError`.

**`is_public` / `is_forbidden`** — определяются в шаблоне на каждой комнате, не в реестре. Один и тот же `room_type = "common_hall"` может быть публичным в таверне и закрытым в частном доме.

### `worlds.building_template_registry` (N+1)

Чертежи зданий с interior. Загружаются из JSON-файлов. Template engine создаёт `named_location` типа `building` (с `is_public` / `is_forbidden` из `default_*` шаблона) + дочерние `named_location` типа `room` по `room_type_registry` (с `is_public` / `is_forbidden` из `default_*` типа комнаты).

```json
[
  {
    "system_type": "inn",          "glossary_ref": "building_inn",
    "levels":    { "min": 1, "max": 3 },
    "footprint": { "width": { "min": 5, "max": 12 }, "depth": { "min": 5, "max": 10 } },
    "wall_material":  { "pick_from": ["stone", "wood"] },
    "floor_material": { "pick_from": ["wood"] },
    "default_is_public":   true,
    "default_is_forbidden": false,
    "rooms": [
      { "system_room": "entrance",    "required": true,  "count": { "min": 1, "max": 2 } },
      { "system_room": "common_hall", "required": true,  "count": { "min": 1, "max": 1 } },
      { "system_room": "kitchen",     "required": false, "count": { "min": 0, "max": 1 } },
      { "system_room": "guest_room",  "required": false, "count": { "min": 0, "max": 8 } }
    ],
    "perimeter_barrier": { "template": null, "probability": 0 },
    "economic_tier_range": { "min": "basic", "max": "premium" }
  },
  {
    "system_type": "manor",        "glossary_ref": "building_manor",
    "levels":    { "min": 2, "max": 4 },
    "footprint": { "width": { "min": 8, "max": 20 }, "depth": { "min": 8, "max": 20 } },
    "wall_material":  { "pick_from": ["stone"] },
    "floor_material": { "pick_from": ["wood", "stone"] },
    "default_is_public":   false,
    "default_is_forbidden": false,
    "rooms": [
      { "system_room": "entrance",    "required": true,  "count": { "min": 1, "max": 1 } },
      { "system_room": "common_hall", "required": true,  "count": { "min": 1, "max": 1 } },
      { "system_room": "kitchen",     "required": true,  "count": { "min": 1, "max": 1 } },
      { "system_room": "cellar",      "required": false, "count": { "min": 0, "max": 1 } },
      { "system_room": "guest_room",  "required": false, "count": { "min": 0, "max": 6 } }
    ],
    "perimeter_barrier": { "template": "stone_fence", "probability": 0.8 },
    "economic_tier_range": { "min": "quality", "max": "exceptional" }
  }
]
```

`perimeter_barrier.template` — ref → `barrier_template_registry.system_type`; null = нет забора  
`perimeter_barrier.probability` — вероятность генерации забора вокруг этого здания (0.0–1.0)

**Порядок генерации (template engine):**
1. Рандомизировать footprint и количество уровней в диапазоне
2. Выбрать материалы из `pick_from`
3. Разместить required комнаты по правилам `room_type_registry` (adjacency, level_constraint, perimeter)
4. Заполнить optional комнаты в оставшемся пространстве
5. Сгенерировать стены, двери, переходы между комнатами → map_cells + location_levels + location_passages
6. Если `perimeter_barrier.probability` → roll → при успехе сгенерировать barrier по шаблону вокруг footprint

### `worlds.barrier_template_registry` (N+1)

Чертежи барьеров без interior: заборы, стены, укрепления. Размещаются вокруг зданий (referenced из building template) или независимо вокруг district/settlement.

```json
[
  {
    "system_type": "wooden_fence", "glossary_ref": "barrier_wooden_fence",
    "wall_material":  { "pick_from": ["wood"] },
    "height_levels":  { "min": 1, "max": 1 },
    "gates": { "min": 1, "max": 2 }
  },
  {
    "system_type": "stone_fence",  "glossary_ref": "barrier_stone_fence",
    "wall_material":  { "pick_from": ["stone"] },
    "height_levels":  { "min": 1, "max": 2 },
    "gates": { "min": 1, "max": 4 }
  },
  {
    "system_type": "city_wall",    "glossary_ref": "barrier_city_wall",
    "wall_material":  { "pick_from": ["stone"] },
    "height_levels":  { "min": 2, "max": 5 },
    "gates":   { "min": 1, "max": 6 },
    "towers":  { "min": 0, "max": 20 }
  }
]
```

Городские стены и стены крепостей — `barrier_template_registry`, не часть ни одного здания; размещаются на уровне settlement/territory.

---

## Динамика мира — состояния локаций

### `location_states`
```sql
location_states (
  id,
  location_uid,                -- FK → named_locations ON DELETE CASCADE
  level_uid,                   -- nullable FK → location_levels; null = весь location, not null = конкретный уровень
  system_state,                -- ref → worlds.location_state_registry
  display_state, system_description, display_description,
  need_modifiers,              -- nullable JSON; { "safety": -50, "social": -30 }
  created_at
)
```
- `need_modifiers` — аддитивны; движок суммирует по всем активным состояниям локации
- Локация может иметь несколько состояний одновременно (`besieged` + `plague`)
- При изменении `location_states` → `named_locations.system_location_mood` помечается для перегенерации

### `worlds.location_state_registry` (N+1)

| `system_state` | `display_state` | `need_modifiers` (пример) | Описание |
|---|---|---|---|
| `besieged` | Осада | safety:-60, food:-30 | Город окружён врагом, снабжение перекрыто |
| `occupied` | Оккупация | safety:-40, social:-50 | Контролируется чужими войсками; законы оккупанта |
| `riot` | Бунт | safety:-70, social:-60 | Активные уличные столкновения, власть теряет контроль |
| `uprising` | Восстание | safety:-50, social:-40 | Организованное вооружённое сопротивление власти |
| `martial_law` | Военное положение | safety:+20, social:-60 | Армия патрулирует улицы; комендантский час, ограничения |
| `curfew` | Комендантский час | safety:+10, social:-30 | Запрет на передвижение ночью; торговля сокращена |
| `blockade` | Блокада | food:-40, trade:-50 | Экономическая или военная блокада; товары не поступают |
| `strike` | Забастовка | trade:-40, social:-20 | Работники прекратили труд; производство и услуги остановлены |
| `famine` | Голод | food:-80, health:-40 | Критическая нехватка продовольствия |
| `plague` | Эпидемия | health:-70, social:-50 | Массовое заболевание; карантинные меры |
| `quarantine` | Карантин | social:-40, trade:-30 | Изоляция по медицинским причинам; въезд/выезд ограничен |
| `rebel_controlled` | Под контролем повстанцев | safety:-30, social:-20 | Повстанцы вытеснили законную власть |
| `autonomous` | Автономия | social:+10 | Самоуправление в рамках государства; особый статус |
| `destroyed` | Разрушен | safety:-90, food:-70 | Масштабные разрушения; локация почти непригодна |
| `fire` | Пожар | safety:-80, health:-30 | Активный пожар; эвакуация, паника |
| `flooding` | Наводнение | safety:-50, food:-30 | Затопление; передвижение и торговля затруднены |
| `economic_boom` | Экономический подъём | trade:+50, social:+30 | Рост торговли, занятости, настроений |
| `economic_collapse` | Экономический коллапс | trade:-60, food:-30, social:-50 | Крах торговли, безработица, голод |

### `location_faction_influence`
```sql
location_faction_influence (
  id, location_uid,            -- FK → named_locations ON DELETE CASCADE
  faction_uid,                 -- FK → factions
  influence                    -- int 0–100
)
INDEX (location_uid)
```
`SUM(influence) WHERE location_uid = X = 100`; 0 записей = независима. LLM получает через `intensity_level_registry`.

### `location_faction_access`
```sql
location_faction_access (
  location_uid, faction_uid,
  is_allowed,                  -- семантика зависит от named_locations.is_forbidden
  PRIMARY KEY (location_uid, faction_uid)
)
```

**Двойной режим в зависимости от `is_forbidden`:**

| `is_forbidden` | Режим таблицы | Семантика `is_allowed` |
|---|---|---|
| `false` | **denylist** | `false` = фракция запрещена; всех остальных пускают |
| `true`  | **allowlist** | `true` = фракция допущена; все остальные — нарушители |

`owner_uid` всегда имеет доступ независимо от `is_forbidden`.  
Нарушитель в `is_forbidden`-зоне → guard_level-проверка; NPC реагируют враждебно.

**Точка расширения:** когда появится система рангов фракций, добавить `min_rank: nullable` — допуск только от определённого ранга внутри фракции. Сейчас достаточно фракционного уровня.

### `world_history`
```sql
world_history (
  id, world_id, location_uid,  -- nullable; событие глобальное или привязано к локации
  system_world_date, display_world_date,
  system_event_type,           -- "war" | "cataclysm" | "destruction" | ... N+1
  display_event_type, system_description, display_description, created_at
)
```
Мутация terrain (лес → пепелище) — мутация `map_cells.system_terrain` по диапазону (x, y, z), фиксируется в `world_history`. Снапшот захватывает `location_states` + затронутые `map_cells`.

---

## Ресурсы локаций

### `worlds.resource_type_registry` (N+1)
```json
[
  { "system_resource": "iron_ore", "is_renewable": false, "base_regen_per_tick": null, "default_yield": 10, "yield_item_uid": "item_iron_ore" },
  { "system_resource": "timber",   "is_renewable": true,  "base_regen_per_tick": 5,    "default_yield": 5,  "yield_item_uid": "item_log"      }
]
```
`display_*` — из `lore_registry`.

### `location_resources`
```sql
location_resources (
  id,
  location_uid,                -- FK → named_locations ON DELETE CASCADE
  level_uid,                   -- nullable FK → location_levels; null = весь location; not null = ресурс на конкретном уровне (руда на z=-5)
  system_resource,             -- ref → worlds.resource_type_registry
  quantity, max_quantity,      -- текущий запас и ёмкость
  regen_override,              -- nullable int; перекрывает base_regen_per_tick
  is_discovered, is_accessible
)
```
- Добыча: `yield = extract_formula ?? default_yield`; `quantity -= yield` (не ниже 0)
- `is_renewable: true` → регенерация до `max_quantity` за тик

---

## Климат и погода

### `worlds.climate_zone_registry` (N+1)
```json
[
  { "system_climate": "arctic",    "base_temperature": -25, "temperature_variance": 8,  "base_rainfall": 20, "rainfall_variance": 10 },
  { "system_climate": "temperate", "base_temperature": 12,  "temperature_variance": 8,  "base_rainfall": 55, "rainfall_variance": 20 }
]
```
`display_*` — из `lore_registry`. Без ограничений на значения (поддержка любого сеттинга).

**Наследование `climate_zone` по дереву:**
```
resolve_climate(location):
  if location.climate_zone != null → return location.climate_zone
  if location.parent_location_uid != null → return resolve_climate(parent)
  return worlds.default_climate_zone
```
Регион задаёт климат — все вложенные локации наследуют. Явный `climate_zone` перезаписывает для себя и детей.

**Нода генерации (per cell):**
```
temperature_base = zone.base_temperature
                 - elevation_lapse_rate × (z / 100)   -- z в метрах (1 юнит = 1м); выше = холоднее
                 + Σ(neighbor_zone.base_temperature × w(dist))
                 + random(±zone.temperature_variance)
```

### `worlds.map_settings`

```json
{
  "z_max":                 8849,       -- в единицах worlds.measurement_system (метры или футы); Эверест = 8849м
  "z_min":               -11000,       -- минимальная точка; отрицательный (Марианская впадина = -11000м)
  "elevation_lapse_rate":    0.65,     -- снижение температуры на 100м подъёма (°C); всегда в метрах
  "default_climate_zone": "temperate", -- NOT NULL; фолбек resolve_climate() когда нет climate_zone у локации и нет родителя; ref → worlds.climate_zone_registry
  "g":                       1.0       -- гравитация; 1.0 = Земля; 0.38 = Марс; 0.0 = невесомость; влияет на падение solid и урон от падения
}
```

**Конвертация (движок, при сохранении):**
```
metric:   z = value_m              -- 1 юнит = 1м, прямое хранение
imperial: z = round(value_ft × 0.3048)
```
- Пользователь вводит в `measurement_system` мира (метры / футы)
- Движок хранит метры внутри; LLM получает обратно в `measurement_system` мира
- `z_max` / `z_min` — жёсткие границы в метрах: ячейка вне диапазона не создаётся, движок логирует

### `worlds.season_temp_offsets`
```json
{ "spring": 3, "summer": 12, "autumn": -2, "winter": -18 }
```
`effective_temperature = map_cells.temperature_base + season_temp_offsets[current_season]`

### `worlds.weather_type_registry` (N+1)
```json
[
  { "system_weather": "blizzard",  "temp_max": -5,  "rainfall_min": 60, "check_order": 1,  "travel_modifier": 3.0, "need_modifiers": { "warmth": 70 }, "penetrates_shelter": true  },
  { "system_weather": "storm",     "temp_max": null,"rainfall_min": 70, "check_order": 2,  "travel_modifier": 2.5, "need_modifiers": { "warmth": 20 }, "penetrates_shelter": true  },
  { "system_weather": "rain",      "temp_max": 25,  "rainfall_min": 40, "check_order": 4,  "travel_modifier": 1.3, "need_modifiers": { "warmth": 10 }, "penetrates_shelter": false },
  { "system_weather": "clear",     "temp_max": null,"rainfall_min": null,"check_order": 99, "travel_modifier": 1.0, "need_modifiers": {},               "penetrates_shelter": false }
]
```

`penetrates_shelter: true` — погода проникает под навес (ветер, метель, ливень); при `is_sheltered=true` на локации эффект всё равно применяется.  
`penetrates_shelter: false` — навес полностью блокирует (обычный дождь, снег без ветра).
Движок перебирает по `check_order` ASC → первое совпадение = текущая погода. `clear` — фолбек.  
`check_order` ≠ `danger_level_registry.priority`: здесь меньше = проверяется первее (порядок), там больше = опаснее (агрегация через MAX).
`need_modifiers` — тот же формат что `location_states.need_modifiers`, аддитивны.
`intensity` масштабирует: `effective_modifier = 1 + (travel_modifier - 1) × intensity / 100`

### `location_weather`
```sql
location_weather (
  location_uid,    -- FK → named_locations ON DELETE CASCADE; только settlement и выше
  system_weather,  -- ref → worlds.weather_type_registry
  intensity,       -- int 0–100
  remaining_ticks  -- через сколько тиков пересчитать
)
```

Записи хранятся только для `settlement` и выше (region, territory, settlement). Все дочерние `is_outdoor: true` локации (district) наследуют погоду через:
```
resolve_weather(location):
  if location_weather EXISTS for location_uid → return it
  if parent_location_uid != null → return resolve_weather(parent)
  return null  -- погода не определена
```
Indoor-локации (`is_outdoor: false`) не имеют weather-записи; температура внутри — нарратив LLM на основе outdoor-климата родителя.

> **Вариант B (отложено):** вычисление погоды на пространственной группе локаций (chunk 3×3 ячеек по footprint). Позволяет микроклимат — долина vs холм в одном городе. Сложнее: требует spatial-группировки и раздельных `location_weather` на district-уровне. Апгрейд поверх варианта A без ломки схемы.

---

## Версионирование карты

`worlds.world_map_version` = `hash(terrain_category_registry + terrain_registry + cell_state_registry + road_type_registry + location_type_registry)`

При переименовании типов → `registry_migrations` применяет маппинг к `map_cells`, `roads`, `named_locations` в одной транзакции → пересчитывается хеш. Не влияет на `schema_version` (персонажи не хранят ссылки на terrain/road напрямую).

---

## NPC и локации

**Поля привязки персонажей** (на `character_sheet`):
- `system_home_location_uid` — nullable FK → named_locations (building/room); где живёт/спит/возвращается в idle; `null` = бездомный; у **NPC** — фильтрует стартовые варианты игрока; у **игрока** — определяет стартовую глубину в SceneInit
- `system_home_settlement_uid` — nullable FK → named_locations (тип settlement); родной город; независим от home_location; персонаж может быть бездомным но иметь родной город
- `work_location_uid` — FK → named_locations; рабочее место
- `spawn_location_uid` — FK → named_locations; первое появление; null = совпадает с home
- `respawn_location_uid` — FK → named_locations; явная точка возрождения
- `system_location` / `display_location` — текущая локация персонажа (FK → location_uid)
- `local_level_uid` — nullable FK → location_levels; на каком уровне (этаже) персонаж; null = вне interior-пространства
- `local_x`, `local_y` — nullable int; позиция внутри footprint уровня; null = вне interior-пространства

**Абсолютная высота персонажа:** `local_level_uid → location_levels.z` = метры над уровнем моря (z уже в метрах). Используется движком для расчёта падения, line-of-sight, тактического преимущества высоты.

**Idle поведение:** `system_current_target = { target_type: "idle", target_uid: system_home_location_uid }`

**Инициализация мира:** `NPC.system_location = spawn_location_uid ?? system_home_location_uid`

**`get_home_occupied_uids(world_uid, location_uids) → set[str]`** — SQL-запрос: NPC с `system_home_location_uid IN (...)` → используется при фильтрации стартовой локации для игрока (здание занято NPC — игрок не может там начать).

---

## SessionScene — состояние сцены

```sql
session_scenes (
  session_id,       -- FK → game_sessions; 1:1
  location_uid,     -- FK → named_locations; NULL = draft (локация не выбрана)
  level_uid,        -- nullable FK → location_levels; на каком уровне сцена; null = outdoor или не определён
  description,
  actors,           -- JSON array of character_uid; персонажи присутствующие в сцене
  created_at, updated_at
)
```

---

## Engine flow

### Guard: `CheckSceneNode`

Запускается при: `INTENT_DETECTION`, `SCENE_NARRATION`, `SCENE_COMBAT`, `SCENE_CHANGE_LOCATION`, `LOCAL_SCENE_ANALYSIS`, `LOCAL_REGION_ANALYSIS`.

1. `session_scene` не существует → `SceneNotFoundError` → replan → `SCENE_INIT`
2. `session_scene.location_uid = None` (draft) → `SceneLocationSelectPendingError` → replan → `SCENE_START_LOCATION_SELECT`
3. `session_scene.location_uid` указывает на несуществующую локацию → `LocationNotFoundError` (requires_replan=**False**; данные повреждены — не восстанавливаемо)
4. OK → `state.shared_context["scene"] = scene` (полный объект `SessionScene`); возвращает `NodeResult(data={ "location": display_name, "description": scene.description, "actors": scene.actors })`

`skip_on_replan = False` — нода перезапускается на каждом pass (читает из БД).
Единственная точка входа в `SCENE_INIT` и `SCENE_START_LOCATION_SELECT`.

### Таск `SCENE_INIT` → `SceneInitNode`

1. Берёт `character_id` из `state.session.meta`; читает `player_repo.get_by_id(character_id)`
2. **Определение стартовой глубины** через `WITH RECURSIVE` CTE:
```sql
WITH RECURSIVE tree(uid, depth) AS (
  SELECT location_uid, 0 FROM named_locations
    WHERE parent_location_uid IS NULL AND world_uid = :world_uid
  UNION ALL
  SELECT n.location_uid, t.depth + 1
    FROM named_locations n JOIN tree t ON n.parent_location_uid = t.uid
)
SELECT uid, depth FROM tree
```
   - `player.system_home_location_uid` (`home_uid`) — FK → named_locations; `null` = бездомный
   - Если `home_uid` задан → `target_depth = tree[home_uid].depth`; выбрать все uid где `depth = target_depth`
   - Если `home_uid = null` AND `system_home_settlement_uid` задан → `target_depth = tree[settlement_uid].depth + 1`; дочерние settlement
   - Если оба null → `target_depth = min(depth WHERE depth > 0)`
3. Фильтр по `target_depth`: `is_accessible = True`; применить тот же `can_start(location, player)` что в `SceneLocationChildrenNode`; сортировка: home первым, алфавит. `is_discovered` не проверяется — SceneInit преигровой выбор, логика discovery не применяется
4. Upsert `SessionScene(location_uid=None)` — создаёт draft
5. Output: `{ type: "select_child", parent: null, children: [{uid, name, is_home}] }`

**Поля home у персонажа** (на `character_sheet`):
- `system_home_location_uid` — FK → named_locations; `null` = бездомный; указывает на конкретное строение (building) или комнату (room); не меняется при ходьбе
- `system_home_settlement_uid` — nullable FK → named_locations (тип settlement); родной город; независим от `system_home_location_uid`; персонаж может быть бездомным но иметь родной город

Бездомный + есть родной город: SceneInit идёт в `system_home_settlement_uid` → дочерние локации. Бездомный + нет ни того ни другого: SceneInit → min-depth flow.

Ошибка: `NoLocationsAvailableError` (requires_replan=False).

### Таск `SCENE_START_LOCATION_SELECT` — drill-down

Input: `state.message` = `location_uid`.

**`SceneLocationChildrenNode`** (deps: []):
1. Валидирует uid — существует + принадлежит миру
2. `get_children(location_uid)` → фильтр `is_accessible`
3. Если дочерние есть — применить фильтр доступности для игрока:
```
can_start(location, player):
  # Фракционный доступ
  if location.is_forbidden:          # allowlist mode
    allowed = (player.faction_uid IN location_faction_access[is_allowed=true])
              OR (player.uid == location.owner_uid)
    if NOT allowed → exclude

  else:                              # denylist mode
    banned = player.faction_uid IN location_faction_access[is_allowed=false]
    if banned → exclude

  # NPC-занятость (только для приватных)
  if NOT location.is_public:
    if location.uid IN npc_home_occupied_uids → exclude

  → include
```
   - `NoAvailableChildrenError` если все отфильтрованы
4. Если дочерних нет (leaf) → возвращает `children: []` без ошибки
5. Output: `{ location_uid, location_name, location_description, children: [{uid, name}] }`

`location_description = display_description ?? system_description ?? ""`  
Ошибки: `InvalidLocationError`, `NoAvailableChildrenError` (оба requires_replan=False).

**`SceneStartLocationSelectNode`** (deps: ["scene_location_children"]):
- Children непустые → `{ type: "select_child", parent: {uid, name}, children }`
- Children пустые (leaf) → проверить `is_transit`:
  - `is_transit = true` → транзитная локация; **не останавливать сцену**:
    ```
    passage = LocationPassage WHERE from_level → this location (входящий)
    next_location = passage.to_level → NamedLocation
    рекурсивно обработать next_location как новый leaf
    LLM получает transit_description для описания прохода в контексте движения
    ```
  - `is_transit = false` → определить `level_uid`:
    - leaf = **building** → ground floor: `location_levels WHERE location_uid=building AND z = min(z) ≥ terrain_z`
    - leaf = **room** → `location_levels WHERE location_uid=parent_building AND z = room_cells.z`
    - upsert `SessionScene` с `location_uid` + `level_uid`; `scene.description = display_description ?? system_description ?? ""`
    → `{ type: "scene_ready", location: {uid, name, description} }`

**Транзитная локация** (`is_transit=true`): существует в БД (ячейки, объекты, описание), но движок никогда не создаёт `SessionScene` на ней. LLM описывает её как часть перехода ("поднимаетесь по ступеням и входите в..."), не как отдельную сцену.

### Context engine (container.py)
```python
repositories = {
    "scene_repo":    SqliteSceneRepository,
    "location_repo": SqliteNamedLocationRepository,
    "player_repo":   SqlitePlayerRepository,
    "npc_repo":      SqliteNpcRepository,
}
```

---

## Фронтенд

**ResponseResolver:** `SCENE_INIT → scene_init`, `SCENE_START_LOCATION_SELECT → scene_start_location_select`

**Рендеринг (`MessageList.jsx`):**
- `type: "select_child"` → `<LocationSelectMessage>` — кнопки выбора
- `type: "scene_ready"` → `<SceneReadyMessage>` — карточка созданной сцены

**`LocationSelectMessage`:**
- `parent = null` → "Выберите локацию:"; `parent` есть → "Выберите место в {parent.name}:"
- Кнопка с `is_home=true` получает тег "дом"
- Только последнее data-сообщение интерактивно; disabled во время стриминга
- Клик → `send(child.uid, child.name)` — uid в `state.message`, name как displayText

---

## Открытые вопросы / не реализовано

| Элемент | Статус |
|---|---|
| `SCENE_CHANGE_LOCATION` | TaskType есть, ноды нет. Обсуждение отложено |
| Система путешествий | `4/8-directional`, `base_ticks_per_cell`, расчёт travel_ticks — отложено; ложится поверх географии отдельно |
| 3D combat queries | line-of-sight через map_cells по z; высотное преимущество в бою — логика не реализована |
| Динамические уровни | создание `location_level` + `location_connection(fall)` в рантайме (яма в бою) — отложено |
| Туман войны | `is_discovered` на ячейках vs только на `named_locations` — не решено |
| `is_discovered` на локациях | поле есть, логика discovery не реализована |
| Текущая локация в UI | нет заголовка/хлебной крошки в чате |
| Нода генерации мира | вычисление `temperature_base`, `rainfall`, `location_resources` при процедурной генерации |
| Система построек | добыча ресурсов через постройки (шахта, лесопилка) — отложено |
| Магия как terrain access | магическое передвижение = действие, не пассивный перк — отложено до системы магии |
| Система последствий событий | логика `is_accessible = false` при катаклизмах — отложено до событийной системы |
| Coordinate bridging local↔global | `location_passages.(from_x, from_y)` и `location_objects.(x, y)` — локальные координаты; offset = MIN(map_cells.x/y WHERE location_uid=X AND z=Z); нигде не хранится, вычисляется при выходе из interior |
| Ранги доступа в `is_forbidden`-зонах | `location_faction_access.min_rank` — не реализовано; отложено до системы рангов фракций |
| Fallback для бездомного + hometown при пустых детях | Если все дочерние `system_home_settlement_uid.depth+1` отфильтрованы `can_start()` — `NoLocationsAvailableError`. Нет fallback на глубину+2 или другой settlement. Требует решения совместно с UI-флоу. |
