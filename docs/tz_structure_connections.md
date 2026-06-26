# ТЗ: Механика соединений (tz_structure_connections.md)

## 1. Концепция

Соединения — граф (Вариант B): узлы (`ConnectionNode`) и рёбра (`ConnectionEdge`).  
Граф иерархический: мировой → городской → районный → участок.  
Pathfinding поднимается и опускается по уровням иерархии.

**Площадь** — не тип соединения. Это `structure_type="plaza"` в шаблоне здания,  
собирается через `StructureAreaAssembler`. В граф попадает только как `ConnectionNode`  
со ссылкой на `location_uid` площади.

---

## 2. Типы рёбер

`connection_type` — ref → `worlds.connection_type_registry.system_connection_type` (N+1).  
`graph_level` — отдельное поле, определяет принадлежность к pathfinding-иерархии и не ограничивает тип.

### 2.1 Реестр типов (`worlds.connection_type_registry`)

N+1: движок определяет встроенные типы со специализированным поведением; пользователь может добавлять кастомные — они получают fallback-поведение (дефолтная ширина, стандартный traversal, без специализированной геометрии).

```json
[
  { "system_connection_type": "trail",           "display_name": "Тропинка"         },
  { "system_connection_type": "dirt_road",       "display_name": "Грунтовая дорога" },
  { "system_connection_type": "road",            "display_name": "Дорога"           },
  { "system_connection_type": "sidewalk",        "display_name": "Тротуар"          },
  { "system_connection_type": "highway",         "display_name": "Трасса"           },
  { "system_connection_type": "bridge",          "display_name": "Мост"             },
  { "system_connection_type": "alley",           "display_name": "Переулок"         },
  { "system_connection_type": "yard_path",       "display_name": "Двор"             },
  { "system_connection_type": "settlement_gate", "display_name": "Ворота поселения" },
  { "system_connection_type": "air_route",       "display_name": "Воздушный путь"   },
  { "system_connection_type": "sea_route",       "display_name": "Морской путь"     },
  { "system_connection_type": "portal",          "display_name": "Портал"           }
]
```

### 2.2 Встроенные типы

| `system_connection_type` | Топология | Выравнивание terrain | Типичные `graph_level` |
|---|---|---|---|
| `trail` | тропинка; природная, зависит от terrain | нет | `area`, `district` |
| `dirt_road` | грунтовка; шире тропинки, без покрытия | нет | `area`, `district`, `city` |
| `road` | транспортная дорога; может быть мощёной | частичное | `district`, `city` |
| `sidewalk` | пешеходный тротуар; лежит параллельно `road` / `highway`; самостоятельный элемент со своим material/condition/features | частичное | `district`, `city` |
| `highway` | трасса; сложная топология — эстакады, развязки, тоннели | полное | `city`, `world` |
| `bridge` | пересечение водной преграды; самостоятельный объект с подтипами (см. 4.2) | — | любой |
| `alley` | переулок между зданиями | частичное | `district` |
| `yard_path` | путь внутри двора к входу здания | нет | `area` |
| `settlement_gate` | вход/выход из поселения; соединяет граф поселения с мировым | полное | `city` |
| `air_route` | воздушный путь; ребро на z выше terrain | — (нет контакта) | `city`, `world` |
| `sea_route` | морской путь; ребро по water-ячейкам | — (нет контакта) | `world` |
| `portal` | мгновенный переход; не ребро — связи хранятся на узле (см. 4.1) | — | — |

Материал дороги — **свойство ребра**, не тип. Торговые пути строятся отдельной механикой поверх графа.

---

## 3. Модель данных

### 3.1 ConnectionNode

| Поле | Тип | Описание |
|---|---|---|
| `node_uid` | string | Уникальный идентификатор |
| `x` | int | Мировые координаты (метры) |
| `y` | int | Мировые координаты (метры) |
| `z` | int | Мировые координаты (метры) |
| `node_type` | string | `"intersection"`, `"settlement_gate"`, `"portal"`, `"building_entrance"`, `"location_hub"`, `"waypoint"` |
| `location_uid` | string? | Ссылка на `NamedLocation` (площадь, город, портал и др.); `null` если просто пересечение |
| `graph_level` | string | `"world"`, `"city"`, `"district"`, `"area"` |

### 3.2 ConnectionEdge

| Поле | Тип | Описание |
|---|---|---|
| `edge_uid` | string | Уникальный идентификатор |
| `from_node_uid` | string | Начальный узел |
| `to_node_uid` | string | Конечный узел |
| `connection_type` | string | ref → `worlds.connection_type_registry.system_connection_type` (см. раздел 2) |
| `bidirectional` | bool | Двустороннее движение; `true` по умолчанию; `false` для односторонних дорог |
| `lanes_per_side` | int | Кол-во полос в одну сторону; `1` по умолчанию; применимо к транспортным типам (`road`, `highway`) |
| `width_cells` | int? | Ширина в клетках. `null` только для `portal`. Правила по типу — см. раздел 3.4. |
| `bridge_subtype` | string? | Только для `bridge`: `"pedestrian"` \| `"transport"` \| `"viaduct"`. `null` для всех остальных типов |
| `parent_edge_uid` | string? | Только для `sidewalk`: UID родительского ребра (`road` / `highway`), вдоль которого идёт тротуар |
| `side` | string? | Только для `sidewalk`: сторона относительно направления родительского ребра (`from_node → to_node`); `"left"` \| `"right"` |
| `material` | string? | ref → `material_registry`; покрытие дороги; `null` = природный terrain. Резолвится через тот же алгоритм что для зданий: `find_candidates("road")` по `tags["construction"]` + `economic_tier` из `CitySkeleton`. Fallback — ближайший тир вниз. |
| `condition` | int | Состояние дороги 0–100%; влияет на бонус к передвижению (100% = полный бонус) |
| `features` | list[string] | Дополнительные атрибуты дороги: `"curb"`, … Открытый список; освещение — отдельное поле |
| `lighting_type` | string? | ref → `worlds.lighting_type_registry`; тип освещения вдоль ребра; `null` = нет освещения. См. [tz_lighting.md](tz_lighting.md) |
| `traversal_conditions` | dict? | Условия прохода (см. 3.3) |
| `cells` | list[tuple[int,int,int]]? | Физические ячейки вдоль ребра для рендера и коллизий; `null` у порталов |
| `danger_level` | string | ref → `worlds.danger_level_registry.system_danger`; динамически вычисляется из условий (активность банд, засады, события). Логика вычисления — вне scope этого ТЗ |
| `has_sidewalk` | bool | Тротуар вдоль ребра присутствует; решается генератором per-edge на основе контекста (district_type, плотность застройки); `false` по умолчанию |
| `under_construction` | bool | Дорога строится (новая); недоступна для движения до завершения |
| `under_repair` | bool | Дорога на ремонте (существующая); может ограничивать движение |
| `graph_level` | string | `"world"`, `"city"`, `"district"`, `"area"` |

> `under_construction` / `under_repair` — часть общей механики строительства и ремонта,  
> применимой ко всем постройкам (не только дорогам). ТЗ по этой механике будет описано отдельно.

### 3.3 Условия прохода (`traversal_conditions`)

```json
{ "requires_flying": true }
{ "requires_item": "portal_key_uid" }
{ "requires_vehicle": ["ship", "boat"] }
{ "min_reputation": { "faction_uid": "...", "value": 50 } }
```

Поле открытое — список условий расширяется по мере появления механик.

### 3.4 Ширина ребра (`width_cells`)

Ширина измеряется в клетках (1 клетка = 1 м в мировых координатах).

**Фиксированные ширины:**

| `connection_type` | `width_cells` | Правило |
|---|---|---|
| `trail` | 1 | Всегда 1. `lanes_per_side` игнорируется |
| `dirt_road` | 2 | Одна полоса = 2. `lanes_per_side` игнорируется (грунтовка без разметки) |
| `road` | 2 per lane | `width_cells = 2` — ширина одной полосы. Итог: `lanes_per_side × 2 × 2` (обе стороны) |
| `highway` | 2 per lane | Аналогично `road` |
| `alley` | 2 | Фиксированная; без полос |
| `yard_path` | 1 | Фиксированная |
| `settlement_gate` | наследует | `width_cells` ребра которое продолжает за воротами |
| `bridge` | см. 4.2 | `pedestrian`=2; `transport`/`viaduct`=`lanes × 2` [× 2 если bidirectional] [+sidewalk для transport] |
| `air_route` | — | Не применимо; нет физических ячеек |
| `sea_route` | — | Не применимо; нет физических ячеек |
| `portal` | `null` | Нет физических ячеек |

**Sidewalk:**

`width_cells` тротуара — 1–8 клеток. Резолвится из `economic_tier` скелета города:

| `system_economic_tier` | `width_cells` sidewalk |
|---|---|
| `poor` | 1 |
| `basic` | 2 |
| `standard` | 3 |
| `premium` | 4–5 |
| `exceptional` | 6–8 |

Конкретное значение в диапазоне — случайный выбор при генерации (rng). Шаблон района может явно задать `sidewalk_width` для переопределения резолва.

**Итоговая ширина полосы вместе с тротуаром:**

```
one_side_width = lanes_per_side × 2         -- полос в одну сторону × 2 клетки на полосу

-- bidirectional=true:  оба направления на одном ребре
road_width = one_side_width × 2

-- bidirectional=false: одно направление; второе — отдельное ребро
road_width = one_side_width

sidewalk_left  = width_cells (sidewalk left edge)
sidewalk_right = width_cells (sidewalk right edge)
total_width    = sidewalk_left + road_width + sidewalk_right
```

### 3.5 Геометрия ребра: прямые отрезки и плавные повороты

> **Референс алгоритма routing:** weighted anisotropic shortest path — минимизация cost-функции по slope, препятствиям, длине.  
> Реализация: [tmwhere — Procedural City Generation](https://www.tmwhere.com/city_generation.html) (globalGoals + localConstraints + A*).  
> Научная база: [Procedural Generation of Roads](https://www.researchgate.net/publication/229707505_Procedural_Generation_of_Roads).  
> Адаптация к нашей модели: `localConstraints` → проверка z-delta + water-ячеек + обрывов; cost-функция → bridge cost ratio vs detour length (см. открытые вопросы §8).

**Модель:** ребро = прямой (или почти прямой) отрезок. Кривая дорога — цепочка рёбер через промежуточные узлы `node_type="waypoint"`.

**`waypoint`** — узел без семантического значения; только для геометрии. `location_uid=null` всегда.

#### Правила разбивки на отрезки (split)

**Жёсткие (всегда, не настраиваются):**
- Пересечение с другой дорогой → `node_type="intersection"`
- Смена `connection_type` или `material` → `node_type="waypoint"`

**Настраиваемые (через `worlds.road_settings`):**
- Изменение направления ≥ `max_turn_angle` (max 90°) → `node_type="waypoint"`
- Длина отрезка ≥ `max_segment_length_m` → `node_type="waypoint"`

#### Плавный поворот

Резкий поворот — весь угол меняется в одном узле. Плавный — угол распределяется по нескольким сегментам. Чем шире дорога, тем больший радиус кривизны требуется.

```
min_radius     = width_cells × curve_radius_factor
arc_length     = min_radius × angle_rad
n_segments     = max(2, arc_length / max_segment_length_m)
angle_per_step = total_angle / n_segments          -- всегда ≤ 90°
```

**`curve_radius_factor` по `connection_type`:**

| `connection_type` | `curve_radius_factor` | Характер поворота |
|---|---|---|
| `trail` | 1 | Резкие повороты допустимы |
| `dirt_road` | 2 | Умеренные |
| `alley` | 2 | Умеренные |
| `road` | 4 | Плавные |
| `highway` | 8 | Очень плавные |
| `bridge` | наследует от типа дороги | — |

`curve_radius_factor` и остальные параметры хранятся в `worlds.road_settings` — см. раздел 3.6.

### 3.6 Реестр настроек дорог (`worlds.road_settings`)

Хранится как JSON-массив в `worlds`. Настраивается per-world. Ключ — `system_connection_type` из `worlds.connection_type_registry`. При добавлении кастомного типа в реестр — добавляется и запись в `road_settings`.

| Поле | Тип | Описание |
|---|---|---|
| `connection_type` | string | Ключ записи |
| `curve_radius_factor` | int | Множитель минимального радиуса кривизны (см. 3.5) |
| `max_segment_length_m` | int | Максимальная длина прямого отрезка до принудительного split |
| `min_segment_length_m` | int | Минимальная длина отрезка; предотвращает слишком плотные waypoints |
| `default_lanes_per_side` | int\|null | Кол-во полос при генерации; `null` — тип без полос (`trail`, `alley` и др.) |
| `auto_sidewalk` | bool | Генерировать ли sidewalk-рёбра автоматически |
| `base_travel_modifier` | float | Базовый модификатор скорости движения при `condition=100%` и `economic_tier="standard"`. `< 1.0` = быстрее базы, `> 1.0` = медленнее |
| `condition_degradation` | float | Штраф при `condition=0%`: `effective = base × tier_bonus × (1 + degradation × (1 − condition/100))` |

```json
[
  {
    "connection_type":        "trail",
    "curve_radius_factor":    1,
    "max_segment_length_m":   30,
    "min_segment_length_m":   3,
    "default_lanes_per_side": null,
    "auto_sidewalk":          false,
    "base_travel_modifier":   1.4,
    "condition_degradation":  0.2
  },
  {
    "connection_type":        "dirt_road",
    "curve_radius_factor":    2,
    "max_segment_length_m":   60,
    "min_segment_length_m":   5,
    "default_lanes_per_side": null,
    "base_travel_modifier":   1.2,
    "condition_degradation":  0.4
  },
  {
    "connection_type":        "alley",
    "curve_radius_factor":    2,
    "max_segment_length_m":   30,
    "min_segment_length_m":   3,
    "default_lanes_per_side": null,
    "base_travel_modifier":   1.1,
    "condition_degradation":  0.3
  },
  {
    "connection_type":        "road",
    "curve_radius_factor":    4,
    "max_segment_length_m":   100,
    "min_segment_length_m":   10,
    "default_lanes_per_side": 1,
    "base_travel_modifier":   0.9,
    "condition_degradation":  0.6
  },
  {
    "connection_type":        "highway",
    "curve_radius_factor":    8,
    "max_segment_length_m":   200,
    "min_segment_length_m":   20,
    "default_lanes_per_side": 2,
    "base_travel_modifier":   0.7,
    "condition_degradation":  0.8
  },
  {
    "connection_type":        "yard_path",
    "curve_radius_factor":    1,
    "max_segment_length_m":   20,
    "min_segment_length_m":   2,
    "default_lanes_per_side": null,
    "base_travel_modifier":   1.3,
    "condition_degradation":  0.2
  }
]
```

> `sidewalk`, `bridge`, `air_route`, `sea_route`, `portal`, `settlement_gate` — записей нет:  
> `sidewalk` и `bridge` — производные объекты, их параметры определяются родительским ребром;  
> остальные не имеют физической геометрии или задаются явно при генерации.

`auto_sidewalk` в `road_settings` — умолчание для типа дороги. Фактическое значение — `has_sidewalk` на `ConnectionEdge`, которое генератор выставляет per-edge на основе контекста (district_type, плотность застройки). Генератор может отклониться от умолчания в любую сторону.

### 3.7 Эффективный модификатор движения (`effective_travel_modifier`)

Итоговая скорость передвижения по ребру вычисляется из трёх факторов:

```
material_tier    = material_registry[edge.material].economic_tier
tier_bonus       = economic_tier_registry[material_tier].road_tier_bonus

condition_factor = 1.0 + condition_degradation × (1 − edge.condition / 100)

effective_travel_modifier = base_travel_modifier
                          × tier_bonus
                          × condition_factor
```

`effective_travel_modifier < 1.0` — быстрее базовой скорости; `> 1.0` — медленнее.

**Два новых поля в `economic_tier_registry`:**

| `system_economic_tier` | `road_tier_bonus` | `road_tier_durability` |
|---|---|---|
| `poor`        | 1.20 | 0.6 |
| `basic`       | 1.10 | 0.8 |
| `standard`    | 1.00 | 1.0 |
| `premium`     | 0.95 | 1.3 |
| `exceptional` | 0.90 | 1.6 |

- `road_tier_bonus` — модификатор скорости движения (`< 1.0` = быстрее)
- `road_tier_durability` — сопротивление деградации (`> 1.0` = медленнее изнашивается)

Если `edge.material = null` (природный terrain) — `road_tier_bonus = 1.0`, `road_tier_durability = 1.0`.

**Формула деградации `condition`:**

```
effective_degradation_rate = base_degradation
                           / (road_tier_durability × material.structural_strength)
```

`material.structural_strength` — из `material_registry` (0–1); высокая прочность материала замедляет износ.  
Конкретный триггер и скорость деградации во времени — вне scope этого ТЗ.

---

## 4. Особые типы соединений

### 4.1 Портал

Портал — перемещение из точки A в точку B без физического пути. Не использует рёбра графа.  
Связи хранятся непосредственно на узле портала.

**Типы порталов (`portal_type`):**

| Тип | Описание |
|---|---|
| `coordinate` | Телепорт напрямую на (x, y, z); граф полностью игнорируется |
| `graph` | Телепорт на узел графа; дальнейшее движение идёт по рёбрам от этого узла — барьер на ребре означает, что персонаж застревает у точки выхода |

**Свойства портала на `ConnectionNode`:**

```python
portal_type:              str        # "coordinate" | "graph"
portal_destinations:      list[dict] # список точек назначения
bidirectional:            bool       # портал работает в обе стороны
is_active:                bool       # портал включён; False = портал не работает
blocked_behavior_override: str | None  # переопределяет world.mechanics_settings["portal_blocked_behavior"]; None = использовать мировую настройку
```

Все поля выше могут быть изменены через **игровое действие** (game action) в рантайме:
- `portal_destinations` — перенаправить портал
- `bidirectional` — запечатать / открыть обратный проход
- `is_active` — активировать / деактивировать портал
- `blocked_behavior_override` — изменить поведение при заблокированном выходе

Каждый элемент `portal_destinations`:
```json
{ "type": "coordinate", "x": 100, "y": 200, "z": 0 }
{ "type": "graph", "node_uid": "node_abc123" }
```

**Поведение при заблокированном выходе** (только для `graph`-порталов; настройка механик мира):

| `portal_blocked_behavior` | Описание |
|---|---|
| `random_portal` | Персонаж выбрасывается в случайный портал сети |
| `before_portal` | Персонаж возвращается перед порталом входа |
| `random_effect` | Случайно применяется один из вариантов выше |

Хранится в `world.mechanics_settings["portal_blocked_behavior"]`.

Узлы портала имеют `node_type="portal"` + `location_uid` (NamedLocation портала).  
Порталы генерируются как `structure_type="portal"` через `StructureAreaAssembler`.

### 4.2 Мост

Мост — самостоятельный объект со своей геометрией, по семантике аналогичен лестнице `straight`:  
два якорных узла (точки входа/выхода) + пролёт между ними, собираемый `BridgeAssembler`.  
Мост не является overlay поверх water-ячеек — он генерирует собственные ячейки (настил, перила, опоры).

Определяется полем `bridge_subtype` на ребре `connection_type="bridge"`.

**Подтипы (`bridge_subtype`):**

| `bridge_subtype` | Описание | Sidewalk | `width_cells` |
|---|---|---|---|
| `pedestrian` | Пешеходный мост; только люди | нет | 2 |
| `transport` | Транспортный мост с проезжей частью | есть (обе стороны) | `lanes_per_side × 2` [× 2 если bidirectional] + sidewalk |
| `viaduct` | Часть эстакады; только проезжая часть | нет | `lanes_per_side × 2` [× 2 если bidirectional] |

**Геометрия:**
- Ячейки моста хранятся в `connection_edge_cells`
- Настил, перила, опоры — генерируются `BridgeAssembler` из подтипа + ширины
- Для `transport`: боковые sidewalk-рёбра порождаются автоматически (как к обычному `road`)

**Триггер генерации:**  
Когда прокладываемое ребро (`road` / `highway` / `dirt_road`) пересекает water-ячейки, генератор создаёт ребро `bridge` с нужным `bridge_subtype` вместо продолжения исходного типа.

### 4.3 Воздушная трасса

- Ребро с `connection_type="air_route"` существует на z > terrain
- `traversal_conditions: { "requires_flying": true }` или конкретный тип транспорта
- Узлы — вышки / причалы / аэропорты (`structure_type="air_dock"`)

---

## 5. Интеграция с assembler-иерархией

### 5.1 Поток сборки

```
SettlementAssembler
  └─ _plan_district_slots()  → DistrictSlot[] с entry_nodes внутри каждого (см. 5.2)
  └─ _plan_street_grid()     → ConnectionNode[] + ConnectionEdge[] уровня "city"
                                settlement_gate-узлы на границах map_cell
                                through_road-узлы на стыках районов

DistrictAssembler
  └─ _plan_streets(slot)     → ConnectionNode[] + ConnectionEdge[] уровня "district"
                                1. прокладывает through_road-коридоры (жёсткие ограничения)
                                2. строит внутреннюю сетку вокруг них
                                3. подключает entry_point-узлы к внутренней сети

StructureAreaAssembler
  └─ _build_paths()          → ConnectionNode[] + ConnectionEdge[] уровня "area"
                                building_entrance-узел → ближайший road / alley района

WorldGenerator (отдельно)
  └─ _plan_world_routes()    → highway, air_route, sea_route, portal между NamedLocation
```

### 5.2 ConnectionEntry — точки входа в район

`SettlementAssembler` создаёт entry_nodes до генерации районов и вкладывает их в каждый `DistrictSlot`.

```python
@dataclass
class ConnectionEntry:
    node:            ConnectionNode
    connection_type: str         # "highway" | "road" | "alley" …
    role:            str         # "through_road" | "entry_point"
    facing:          str         # "N" | "S" | "E" | "W" — на какой грани района
    paired_exit_uid: str | None  # для through_road: uid узла выхода на противоположной грани
```

**Два типа точек входа:**

| `role` | Описание | Что делает DistrictAssembler |
|---|---|---|
| `through_road` | Сквозная дорога; пара узлов (вход + выход на противоположных гранях) | Прокладывает зарезервированный коридор между парой; остальная сетка обходит его |
| `entry_point` | Одиночный узел на грани без парного выхода | Подключает к внутренней сети района |

**Принцип расстановки entry_nodes (`through_road`):**  
SettlementAssembler ставит узлы с шагом `block_size` — той же константой, что будет использовать DistrictAssembler для внутренней сетки. Это гарантирует, что entry_nodes совпадут с узлами сетки без дополнительного snap-алгоритма.

`block_size` по `settlement_density` (см. раздел 9, фаза 3): `dense=50м / medium=80м / sparse=120м`.

**Footprint поселения:**  
`footprint_m = city_size_registry[city.system_city_size].footprint_multiplier × world.map_cell_size_m`  
Поле `footprint_multiplier` хранится в `worlds.city_size_registry` (N+1); настраивается per-world.  
Значения по умолчанию: `hamlet=0.25 / village=0.5 / town=1.0 / city=2.0 / metropolis=4.0`.  
Settlement_gate-узлы ставятся на границах map_cell (координаты кратные `map_cell_size_m`).

### 5.3 Расширение DistrictSlot

```python
entry_nodes: list[ConnectionEntry] = field(default_factory=list)
```

`SettlementLayout`, `DistrictLayout`, `AreaLayout` расширяются полями:
```python
connection_nodes: list[ConnectionNode] = field(default_factory=list)
connection_edges: list[ConnectionEdge] = field(default_factory=list)
```

---

## 6. Хранение в БД

Граф соединений хранится отдельными таблицами (не в JSON):

```sql
connection_nodes (
    node_uid        TEXT PRIMARY KEY,
    x               INTEGER NOT NULL,
    y               INTEGER NOT NULL,
    z               INTEGER NOT NULL,
    node_type       TEXT NOT NULL,   -- "intersection"|"settlement_gate"|"portal"|"building_entrance"|"location_hub"
    location_uid    TEXT REFERENCES named_locations(location_uid),
    graph_level     TEXT NOT NULL,
    world_uid       TEXT NOT NULL REFERENCES worlds(world_uid),

    -- только для node_type="portal"
    portal_type                  TEXT,        -- "coordinate" | "graph"
    portal_destinations          TEXT,        -- JSON: list[dict]
    portal_bidirectional         INTEGER,     -- 0 | 1
    portal_is_active             INTEGER,     -- 0 | 1
    portal_blocked_behavior_override TEXT     -- "random_portal"|"before_portal"|"random_effect"|null
)

connection_edges (
    edge_uid            TEXT PRIMARY KEY,
    from_node_uid       TEXT NOT NULL REFERENCES connection_nodes(node_uid),
    to_node_uid         TEXT NOT NULL REFERENCES connection_nodes(node_uid),
    connection_type     TEXT NOT NULL,
    bidirectional       INTEGER NOT NULL DEFAULT 1,
    lanes_per_side      INTEGER NOT NULL DEFAULT 1,
    width_cells         INTEGER,             -- nullable; ширина в клетках (см. раздел 3.4); null только для portal
    bridge_subtype      TEXT,                -- "pedestrian"|"transport"|"viaduct"; только для bridge
    parent_edge_uid     TEXT REFERENCES connection_edges(edge_uid),  -- только для sidewalk
    side                TEXT,                -- "left"|"right"; только для sidewalk
    material            TEXT,                -- ref → material_registry; null = природный terrain
    condition           INTEGER NOT NULL DEFAULT 100,  -- 0–100%
    features            TEXT,                -- JSON: list[string]; "curb", …
    lighting_type       TEXT,                -- ref → lighting_type_registry; null = нет освещения
    danger_level        TEXT NOT NULL DEFAULT 'none',  -- ref → danger_level_registry; динамический
    under_construction  INTEGER NOT NULL DEFAULT 0,
    under_repair        INTEGER NOT NULL DEFAULT 0,
    street_objects      TEXT,                -- JSON: черновик (раздел 7)
    traversal_conditions TEXT,               -- JSON
    graph_level         TEXT NOT NULL,
    world_uid           TEXT NOT NULL REFERENCES worlds(world_uid)
)

connection_edge_cells (
    edge_uid    TEXT NOT NULL REFERENCES connection_edges(edge_uid),
    x           INTEGER NOT NULL,
    y           INTEGER NOT NULL,
    z           INTEGER NOT NULL,
    seq         INTEGER NOT NULL   -- порядок ячеек вдоль ребра
)
```

`cells` вынесены в отдельную таблицу `connection_edge_cells` — у порталов записей нет.  
Portal-поля на `connection_nodes` заполняются только при `node_type="portal"`, иначе `null`.

---

## 7. Объекты вдоль ребра (черновик)

> **Статус:** черновик. Механика не устоялась — добавлено для фиксации идеи.  
> Неясно как это всё смотрится вместе; уточнять по мере появления ТЗ по генерации улиц.

`ConnectionEdge` может иметь список объектов, размещаемых вдоль ребра при генерации:

```python
street_objects: list[dict]  # открытый список; [] по умолчанию
```

Каждый элемент:
```json
{ "structure_type": "market_stall", "probability": 0.5, "side": "right" }
{ "structure_type": "flower_bed",   "probability": 0.3, "side": "both"  }
{ "structure_type": "fence",        "probability": 0.8, "side": "left"  }
```

**Идея разделения по стилям:**  
`street_objects` объявляет только `structure_type` + вероятность. Конкретный шаблон выбирается из `building_template_registry` по `structure_type` + `economic_tier` из `CitySkeleton` — та же механика что для зданий в районе.

Применимо к `sidewalk`, `road`, `alley` — объекты вдоль дороги существуют в любую эпоху.

---

## 9. План реализации

### Структура папок

```
generators/
  road/                              -- чистая генерация, без I/O
    __init__.py
    widthResolver.py
    sidewalkWidthResolver.py
    districtRoadGenerator.py
    layouts/
      __init__.py
      gridLayout.py
      organicLayout.py
      radialLayout.py
      culDeSacLayout.py
      courtyardLayout.py
  assemblers/
    roadAssembler/                   -- оркестратор: вызывает генератор, сохраняет в БД
      __init__.py
      roadAssembler.py
      roadLayout.py                  -- RoadLayout = list[ConnectionNode] + list[ConnectionEdge]
```

### Фаза 1 — Модели данных

1. `app/db/models/connectionNode.py` — ConnectionNode dataclass (DB-модель)
2. `app/db/models/connectionEdge.py` — ConnectionEdge dataclass (DB-модель)
3. `app/db/models/connectionEdgeCell.py` — ConnectionEdgeCell dataclass (DB-модель)
4. `app/db/migrations/0001_initial.sql` — добавить таблицы `connection_nodes`, `connection_edges`, `connection_edge_cells` + индексы
5. `generators/assemblers/districtAssembler/connectionEntry.py` — ConnectionEntry dataclass (см. 5.2)
6. `generators/assemblers/districtAssembler/districtSlot.py` — добавить `entry_nodes: list[ConnectionEntry]`

### Фаза 2 — Утилиты

5. `generators/road/widthResolver.py`  
   `resolve_width(connection_type, lanes_per_side, bidirectional) → int | None`

6. `generators/road/sidewalkWidthResolver.py`  
   `resolve_sidewalk_width(economic_tier, rng) → int`

### Фаза 3 — Layout-генераторы

7. `generators/road/layouts/gridLayout.py` — полная реализация  
   Алгоритм: равномерная сетка пересечений; block_size из `settlement_density` (dense=50 / medium=80 / sparse=120 м)

8. `generators/road/layouts/organicLayout.py` — заглушка
9. `generators/road/layouts/radialLayout.py` — заглушка
10. `generators/road/layouts/culDeSacLayout.py` — заглушка
11. `generators/road/layouts/courtyardLayout.py` — заглушка

### Фаза 4 — Основной генератор

12. `generators/road/districtRoadGenerator.py`  
    `DistrictRoadGenerator.generate(slot, skeleton, world_uid, rng) → RoadLayout`  
    Читает `street_layout` и `connections` из `district_template`; делегирует в нужный layout.  
    **Порядок в layout-генераторах:**  
    1. резервирует коридоры под `through_road` из `slot.entry_nodes`  
    2. строит внутреннюю сетку вокруг коридоров  
    3. подключает `entry_point`-узлы к сетке

### Фаза 5 — RoadAssembler

13. `assemblers/roadAssembler/roadLayout.py` — `RoadLayout = (list[ConnectionNode], list[ConnectionEdge])`
14. `assemblers/roadAssembler/roadAssembler.py` — оркестратор: вызывает `DistrictRoadGenerator`, сохраняет в БД через репозитории (репозитории — следующая итерация)

### Фаза 6 — Обновление Layout-объектов assembler-иерархии

15. `DistrictLayout` — добавить `connection_nodes: list[ConnectionNode]`, `connection_edges: list[ConnectionEdge]`
16. `SettlementLayout` — добавить `connection_nodes: list[ConnectionNode]`, `connection_edges: list[ConnectionEdge]`

### Фаза 7 — Подключение к ассемблерам

17. `DistrictAssembler._plan_streets(slot, skeleton, world_uid)` — реализовать через `DistrictRoadGenerator`

---

## 8. Открытые вопросы

| Вопрос | Статус |
|---|---|
| Резолв `material` ребра — `find_candidates("road")` по `material_registry`, тот же алгоритм что для зданий | закрыт |
| Гранулярность `condition` — закрыт через waypoint-сегменты (раздел 3.5) | закрыт |
| Алгоритм прокладки `highway` между городами — A* с weighted cost function; референс: [Procedural Generation of Roads](https://www.researchgate.net/publication/229707505_Procedural_Generation_of_Roads), tmwhere | отложено — зависит от terrain v2 |
| Алгоритм городской сетки улиц — референс: Parish & Müller (2001), tmwhere; паттерны: grid / radial / organic | отложено — реализуется при написании DistrictAssembler |
| `air_route` узлы — всегда `structure_type="air_dock"` или могут быть произвольные точки | открыт |
| Морской путь (`sea_route`) — нужен отдельный мировой WorldGenerator или часть SettlementAssembler | открыт |
| Связь `connection_edge_cells` с `map_cells` — физическое изменение terrain-ячеек при прокладке (раздел 3.5) | закрыт |
| Traversal в реальном времени — как engine проверяет `traversal_conditions` при движении | нет ТЗ |
