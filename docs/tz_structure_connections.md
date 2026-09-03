# ТЗ: Механика соединений (tz_structure_connections.md)

## 1. Концепция

Соединения — граф (Вариант B): узлы (`ConnectionNode`) и рёбра (`ConnectionEdge`).  
Граф иерархический: мировой → городской → районный → участок.  
Pathfinding поднимается и опускается по уровням иерархии.

**Участок** — слот из шаблона (`building_template_registry`). Назначение — любой `structure_type` (N+1): жилой дом, таверна, склад, храм, `plaza`, `portal`, `air_dock`, … Не закрытый список «дом или площадь». Состав и размер — шаблон, не хардкод assembler. Собирает `StructureAreaAssembler`. Если шаблон даёт здание, а generate вернул пустой участок — **критическая ошибка генерации участка** (assembler §7.1), не площадь.

**Площадь** — не тип соединения. Это один из `structure_type` (напр. `"plaza"`): общественная зона (сады, фонтаны, террасы — состав шаблона). В граф — `ConnectionNode` с `location_uid` площади. Участок в pack **не** `location_type` (outdoor **C3**).

**Технический шов pack** (макро-тайл / chunk) **не** режет ребро. `ConnectionEdge` живёт в мировых координатах: полотно и pathfinding-иерархия пересекают границу тайла как один путь. Нарезка bake — не новый `system_connection_type` и не обрыв. Обочина Δz — relief `road_shoulder`, тот же catalog uid. Инвариант: [`tz_terrain_relief.md`](./tz_terrain_relief.md) **C29**. SHEER на travel-полотне запрещён (R20).

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
  { "system_connection_type": "river",           "display_name": "Река"             },
  { "system_connection_type": "mountain_river",  "display_name": "Горная река"      },
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
| `river` | равнинная река; bed + polyline; autoresolve → **`classify_river_segments`** → lowland `RiverSegment` | partial (bed) | `world` |
| `mountain_river` | подтип: круче, пороги; segment from classifier (U17); graph via **`riverConnectionEmit`** (U18) | partial (steep bed) | `world` |
| `lake_shoreline` | **routing / travel** тип для берега озера в connection graph; **declare контур** — `world.hydrology.declared_lakes[]` (U20, U23) | partial (shore bands via hydrology) | `world` |
| `coastline` | **routing / travel** тип для берега моря; **declare polyline** — `world.hydrology.declared_coastlines[]` (U21, U23) | partial (shore bands via hydrology) | `world` |
| `portal` | мгновенный переход; не ребро — связи хранятся на узле (см. 4.1) | — | — |

**Реки — geometry vs routing:** declare geometry — `declared_rivers[]` ([`tz_terrain_hydrology.md`](./tz_terrain_hydrology.md) U27). Routing polyline — **`ConnectionEdge`** после carve/**emit** (autoresolve). **`NamedLocation` optional** — только если мастер дал имя. См. [`tz_locations.md`](./tz_locations.md), U9/U11.

**Озёра / море (U20/U21, U23):** declare форма — **`world.hydrology.declared_lakes` / `declared_coastlines`** (waypoints в метрах). Типы `lake_shoreline` / `coastline` в registry — для **routing graph** и travel, не для declare wire. Имя — optional `NamedLocation`. Anchor-only без `declared_*` — invalid для declare (validator future).

**Повороты реки (U14, [`tz_terrain_hydrology.md`](./tz_terrain_hydrology.md)):** строже дорог. Между **соседними** сегментами polyline угол **≤ 45°**; **> 45° запрещён** (import validator для declare; autoresolve — `smooth_river_polyline` перед persist). Не путать с `max_turn_angle` дорог (default до 90° per step в § split).

#### Плавный поворот реки (river curve)

Тот же принцип, что § «Плавный поворот» дорог, но **`max_turn_angle_deg = 45`** (жёстко для `river` / `mountain_river`):

```
max_turn_per_segment = 45°   -- U14; не настраивается выше
n_segments           = max(2, ceil(total_turn / max_turn_per_segment))
angle_per_step       = total_turn / n_segments          -- каждый ≤ 45°
```

Waypoint-узлы на изломах; `RiverBedCarver` и edge emit — по **smoothed** polyline. Водопады — перепад `surface_z` между соседними cells на плавной траектории, не острый 90° излом в plan view.

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
| `node_type` | string | Роль узла в connection graph: `"intersection"`, `"settlement_gate"`, `"portal"`, `"building_entrance"`, `"location_hub"`, `"waypoint"`. **Todo:** wire rename → `connection_node_type` ([`tz_generator_technical_debt.md`](./tz_generator_technical_debt.md) CONN-1); enum `ConnectionNodeType` |
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

Ширина и вся геометрия generate — в **клетках** (целое). Метры и имперские единицы — только display (онлайн / UI), не вход packing и не `width_cells`.

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
  └─ cache оболочек → проход 1 (бронь) → рамка / _plan_streets → проход 2 → граф
                                1. коридор through_road (запрет застройки; шаг 1 пайплайна)
                                2. бронь приоритетных во внутреннем bbox (не через коридор)
                                3. внутренняя сетка вокруг коридора и броней, не сквозь них
                                4. подключает entry_point-узлы к этой сети

StructureAreaAssembler
  └─ _resolve_threshold()    → стык улицы с участком (дверь / ворота / край)
  └─ _build_paths()          → ConnectionNode[] + ConnectionEdge[] уровня "area"
                                улица → порог (не всегда building_entrance)
                                (алгоритм z — §5.1.1)

WorldGenerator (отдельно)
  └─ _plan_world_routes()    → highway, air_route, sea_route, portal между NamedLocation
```

Порядок в районе **по z / порогу (C21, код сейчас):** packing xy участков → `_plan_streets` (z узла = terrain колонки, не пин района) → на каждый участок: `StructureAreaAssembler` (порог, опц. здание, `_build_paths`).

**Целевой порядок модуля улицы и фасада (C22, §5.1.3–§5.1.4):** вычет прямых **поселения** из площади района → якоря / прямые **района** → **cache оболочек** → **проход 1 (бронь приоритетных)** → **рамка вокруг броней** → **проход 2 (остальная коллекция)** → **граф улиц** (рамка + внутренние аллеи, не сквозь участки) → слоту только касающиеся отрезки. Не «пустая сетка кварталов до зданий». Не «улицы целиком до packing» и не «packing по AABB района, потом overlay сетки». Код сейчас packing→overlay — расхождение. C21 по z не отменяется.

### 5.1.1 Подъезд к участку (`_build_paths`)

**Не делать:** копировать z улицы / пин района на `AreaSlot.ground_z` (outdoor **C21**).

Участок **не** всегда равен зданию: двор + забор, двор без забора, или дом 1:1 с участком. **Порог** (где улица стыкуется с участком) выбирает `StructureAreaAssembler._resolve_threshold` по топологии зоны — не формула «всегда facing-ребро footprint».

| Кейс | Когда | `kind` | Клетка порога | Конец первого `yard_path` |
|---|---|---|---|---|
| 1 | двор + калитка | `gate` | середина facing-ребра **участка** | `waypoint` на воротах |
| 2 | двор, забора нет | `parcel_edge` | **то же xy**, открытый край | `waypoint` |
| 3 | размер участка = размер дома (bbox + число клеток) | `door` | проём двери (`entry_xy`) | `building_entrance` |

Кейс 2: контекст входа другой, место то же, что у калитки.

Кейс 3: улица стыкуется с домом **через дверь**. Крыльцо / тамбур в геометрии здания **пока нет** — заглушка, `TODO` в `approach_material` (не четвёртый `kind`). Packing v1 (`YARD_PADDING_M=1`) участок больше дома → generate даёт кейсы 1–2, пока packing не отдаст pad=0.

«Дорога через двор к медиане bbox, пока дверь сидит на фасаде» — бессмысленна **для kind=door**. Для `gate` / `parcel_edge` путь по двору нужен: улица → порог на крае → двор → дверь.

Generate leftover (прочие): [tz_settlement_outdoor.md](./tz_settlement_outdoor.md) **C21-T\***.

Три слоя z:

| Слой | Кто | z |
|---|---|---|
| Полотно улицы | `DistrictAssembler._plan_streets` | узел: `column_surface[(x,y)]` |
| Подъезд xy | `_build_paths` | луч порог→улица **только при** `slot.ground_z ≠ z` примыкающей улицы; иначе стык без профиля |
| Порог | assembler участка | median `column_surface` по **клеткам порога** (не обязательно фасад здания) |
| Дверь в глубине | building `access_type` | `gap = building.map_z − terrain[entry]` |

`AreaSlot.ground_z` — опорная плоскость участка (двор / общая земля). `building.map_z` — пол этого здания (footprint). Могут не совпадать. Оба задаёт assembler участка.

**Алгоритм `_build_paths`:** луч — тонкий и **не всегда**. Не L-ломаная, не mill «тело × 8».

Сначала z примыкающей улицы **без луча:** клетка полотна перед порогом (один шаг `facing` в `street_xy`, иначе `node.z` этого ребра). Сравнить с `AreaSlot.ground_z`.

| | |
|---|---|
| `slot.ground_z == z_улицы` | луча **нет**. `StreetApproach` = `NONE`. Граф: порог стыкуется с улицей на той же z. Нет grade, лестницы, clamp на этом hop |
| `slot.ground_z != z_улицы` | **один** `walk_grid_ray` от порога вдоль `facing` до полотна / края / `max_k`. Дальше §5.1.2 |

1. Origin = клетка порога. Направление = `facing` к улице. Один луч = один вход.
2. Клетки — `walk_grid_ray`. Стоп: полотно / край участка / `max_k`.
3. Выравнивание — z-профиль по клеткам луча (CITY_STRUCTURE). Pack-землю не резать (C1). Не SHEER на travel (R20).
4. Граф: `yard_path` по клеткам луча. Конец — по `kind`. Нет здания → нет `building_entrance`.
5. Дом в глубине: второй hop дверь→ворота — **тот же критерий**: луч только если `building.map_z ≠ z` порога (ворот). Двор на уровне улицы, дом выше — улицу не лучим, двор→дверь лучим.

`walk_grid_ray` — `generators/coordinates/` (сетка + Facing). Mill — свой stop. Assembler участка **не** импортирует `relief/discover`.

#### 5.1.2 Профиль на луче: grade ≤30° / лестница ~45°

Порядок: **сравнить z → (если Δz) луч → онтология порога → вход**. Нет Δz — §5.1.2 не применяется.

`h = 0` на стыке (участок и улица на одной z) — не ходить лучом «чтобы получить L».

Честный угол с луча (как grade C3, формула та же):

```
h = |Δz|                         # |z_порога − z_на_дальнем_конце_луча|
L = длина луча в клетках         # после walk_grid_ray
θ = atan(h / L)                  # L≥1; h=0 → входа-подъёма нет
```

Не подгонять θ литералом. Считать с фактических h и L.

| θ | Форма | Геометрия |
|---|---|---|
| **θ ≤ 30°** | плавный подъём | SLOPE-geom: `partition_height(h, L)` / `geom_resolve` (dataModel `reliefSlopeGeom` + helper). Честный θ на клетках луча |
| **30° < θ ≤ 45°** | лестница | канон 45° при `h=L` (1 xy = 1 z). `L_stairs = h` клеток от порога |
| **θ > 45°** | править **только `map_z`** (вверх или вниз) | `|Δz| = L` → θ = 45°, дальше лестница. **Не** сдвигать здание в xy к улице. Не mill SHEER |

**≤30° — «по grade», не mill.** Тот же треугольник h/L/θ и нарезка ступеней высоты, что у SLOPE. Клетки — CITY_STRUCTURE (вход). **Не** Q1/`_rim_shots`, **не** `ReliefGradeInstance`, **не** `location_terrain` (C1). Assembler **не** импортирует `relief/discover`.

**θ > 45° — выровнять перепад по z, не позицию на плане.** «К улице» здесь **не** xy: дом на участке не двигаем (это ломает район). Меняем только `building.map_z`, чтобы спуск или подъём по лучу был **ровно 45°**, дом выше улицы или ниже — не важно.

На кубе 45° ⇔ `h = L`. Helper (генераторный, не POJO / не колонка SQL):

```
clamp_near_z_to_45(z_near, z_far, L) -> int
# если |z_near - z_far| > L:
#     return z_far + sign(z_near - z_far) * L
# иначе z_near
```

`z_far` = z полотна на дальнем конце луча. `z_near` = `building.map_z` если дом есть, иначе `AreaThreshold.z`. Выше улицы → опустить; ниже → поднять. **Xy не двигать.**

Нет здания: clamp пишет в `threshold.z`, не в `AreaSlot.ground_z` и не в `DistrictSlot`.

Pack-землю не режем (C1); фундамент закрывает зазор. Соседей по xy не трогаем (C21). После правки θ = 45° → лестница.

**Материал** — тир + онтология порога (не relief-конверт). Для grade и лестницы одна таблица:

| Онтология | Материал (ступени / полотно grade) |
|---|---|
| Вход **в дом** (`door`) | `parent_floor_material` (тир `floor` если нет). **TODO:** крыльцо/тамбур — нет геометрии здания; когда появятся клетки — `porch_material` |
| Калитка (`gate`), внутри участка есть дорога | `material` этой дороги |
| Калитка, дороги внутри нет (просто участок) | `find_candidates("road")` + `economic_tier`, fallback тир вниз |
| `parcel_edge` | как калитка без внутренней дороги → тир |

Assembler участка резолвит таблицу. Не хардкодить литерал камня.

Клетки полотна в v1 не обязательны для persist (C10); граф SQL обязателен.

`AreaLayout.connection_nodes` / `connection_edges` — выход `_build_paths`; extract пишет вместе с district graph. C20 (`front` дверь) — только если шаблон участка даёт **здание** с входом. Площадь / сад (`plaza` и аналоги) — порог как открытый край или калитка по `perimeter_barrier` шаблона, не обязательная дверь. У площади все примыкающие улицы **равны** по приоритету: `frontage` и `frontage_type_order` **не** выбирают парадную. Facing посадки — к полосе, куда район поставил слот; не «главная нитка района».

### 5.1.3 Стык улица↔участок: граф, приоритет, фасад (C22)

Склейка: [tz_settlement_outdoor.md](./tz_settlement_outdoor.md) **C22**. Не путать с C21 (z / порог / луч).

**Граница ответственности.** Дорога (граф района, полотно) кончается на **стыке с участком**. Внутри двора (калитка→дверь, позже крыльцо) — assembler участка. Улица не кладёт дверь. Участок не прокладывает сетку улиц.

**Совместная онтология.** Генератор/assembler улиц ближайшему участку отдаёт **факт**: примыкающие рёбра графа (координаты полотна на гранях `slot.cells`). Не готовый `facing` и не «тебе можно парадный». Дорог может быть несколько, с разных сторон.

Assembler участка назначает роли C20: **парадный** (`front`) / **чёрный** (`service`) — **если** шаблон — здание с входами. Тогда `slot.facing` и стена главного входа **выводятся** из выбранного парадного ребра (вариант 1: `entry_point.wall` = эта грань; **интерьер не крутить**). Packer **может** повернуть оболочку 90° — «Поворот оболочки» ниже. Чёрный — вторая дорога: **напротив или с угла**. Invert facing — если чёрный напротив.

Нет здания / `plaza`: C20 нет; все касающиеся улицы **равны**; `frontage` не выбирает парадную. Facing слота — полоса, куда packing посадил участок. Стык `parcel_edge` / `gate`. «Нет здания» — только если шаблон здания не даёт; шаблон даёт здание, участок пустой — ошибка generate (assembler §7.1).

**Приоритет — иерархия типов (CONN-FRONT-1).** Не колонка на каждом ребре и не ранг, зашитый только в строку типа.

Дефолт движка (выше = главнее для парадного), только типы стыка с участком:

`highway` > `road` > `dirt_road` > `alley` > `trail`

Не участвуют в сравнении фасада: `air_route`, `sea_route`, `portal`, `yard_path` (двор). `bridge` / `settlement_gate` — ранг **наследуют** у продолжаемого ребра. `sidewalk` — ранг **родителя** (`parent_edge`), не своя ступень. Кастомный тип, которого нет в активном списке — ниже всех перечисленных (как ниже `trail`).

Автор **переставляет список** (стиль урбанизации): например только `["road", "alley", …]` — парадные к обычной улице, даже если рядом `highway`.

Резолв (первый заданный список): **район** (`district_template.frontage_type_order`) → **город** (`CitySkeleton.frontage_type_order` с поселения) → **дефолт движка** (`FrontageTypeOrder.canonical_defaults()`, dataModel). Пустой/null = наследовать. SoT значений — POJO, не литерал в генераторе.

Неизвестный ключ в списке: **skip** + `warning` (не валить generate). Если после skip список пуст — наследовать уровень выше. Ключ должен быть в `connection_type_registry` мира.

**Поле города.** Не колонка ребра и не строка типа. Импорт на **поселении**, как `settlement_density` (JSON / `getattr` → `CitySkeleton`; SQL на `NamedLocation` — при persist скелета, `0001`, не блокер generate). Район: `district_template.frontage_type_order`. Мировой N+1-список «на все города» в v1 нет.

Два ребра с одним `connection_type` — один ранг → `frontage`.

**Касание ребра.** Не фасад и не диагональ.

- Полотно ребра `E` = клетки rasterize этого `ConnectionEdge` (`street_xy` этого ребра, с `width_cells`).
- Участок `P` = `slot.cells`.
- `P` **касается** `E` ⇔ есть клетка участка и клетка полотна с манхэттен-расстоянием **1** (общий бок, 4-сосед). Наложение (одна xy в обоих) тоже касание. Только угол (диагональ, расстояние √2) — **нет**.

Счёт до назначения facing: геометрия, не «кто уже смотрит».

**Зачем нитка (`frontage`).** Угол дома: две улицы **одного** типа (`road` и `road`). Парадный смотрит на ту, вдоль которой в районе **больше участков**.

Граф хранит улицу кусками «перекрёсток–перекрёсток». Если считать куски по отдельности: на этом квартале главной — 2 дома, на боковой — 4 → фасад на боковую, хотя главная на всю длину района — 15 домов. Это и есть ошибка. Нитка = одна улица целиком в районе (склеить куски одной линии), не один квартал.

Пример: шаг 80 клеток, север района y=0, три куска `(0,0)–(80,0)` … `(160,0)–(240,0)` — одна нитка. Не три улицы.

`through_road` по той же линии — та же нитка, не вторая улица в счёте.

**Квартал** — клетка сетки между улицами. Счёт «только этот квартал» как раз даёт ошибку выше. v1 так не считает.

**v1 счёт `frontage`:** по **всему району**, по **нитке** (не по одному сегменту, не по кварталу). Квартальный счёт — не v1. **`plaza`:** счёт и иерархия типов **не** применяются (все улицы равны).

**Третья улица.** После парадного и чёрного третье (четвёртое) примыкание **не** даёт третью роль входа. Игнор для C22. Порог к улице — со стороны парадного.

Если ранги примыкающих **равны**, участок не гадает. Tie-break (**CONN-FRONT-4**):

1. Счёт участков района, **касающихся нитки** каждого кандидата. Парадный к нитке с большим счётом.
2. Счёт равный: rng. Seed: `world_uid` + uid поселения + координаты слота. Геометрию не пропускать.

**Где вход на грани (CONN-FRONT-3).** Отрезок стыка = клетки **периметра** участка, 4-соседние к полотну выбранного ребра. Длина = число таких клеток.

Шаблон здания (корень шаблона, не комната): `max_front_entries` (default **1**), `max_service_entries` (default **0**, **1** если есть `back_entry_point`). C20: ≥1 front на здании после generate.

| `max_*_entries` для роли | Раскладка на отрезке |
|---|---|
| **1** (или меньше; 0 = нет роли) | строго **1** проём, середина отрезка |
| **>1** | тот же приём, что окна §3.10: зоны по длине (`count = max(1, n // 3)` ограничен `max_*`), слоты по центрам зон. Не вторая формула |

**Cache и facing.** Интерьер зависит от `entry_point.wall` = грань парадного. Один cache на шаблон без facing (сейчас) врёт bbox, если стена входа меняет раскладку комнат.

Целевое: ключ cache **`(template, facing)`** — до 4 layout на шаблон. Packing берёт footprint **этого** facing.

Цикл: facing из примыкающих улиц, улицы из посадки, footprint из facing. Разрыв v1: **бронь прохода 1 до рамки** (AABB из cache, 90°); рамка обходит бронь, не режет её; после рамки грань брони к полосе → facing посадки; ключ `(template, facing)` — на этом шаге, не на шаге cache. `frontage` только если слот уже касается двух ниток **равного** ранга. Generate «на place» без cache — запасной путь, не основной.

Код сейчас: cache по `system_name`, facing `SOUTH`, packing→overlay. Целевое C22 — пайплайн §5.1.3; ключ `(template, facing)` после рамки. Если footprint этого facing не влезает в уже забронированный прямоугольник — `warning`, бронь не двигать.

Peek `node.z` в §5.1.1 — **не этот контракт** (C21 leftover / отдельный вопрос).

**Посадка и шаг сетки.** Шаг улицы района = `block_size` плотности (**50 / 80 / 120 клеток**). Это **модуль сетки** (прямоугольник между узлами), не особый «суперблок». Generate считает клетками; метры/футы — display.

Размер участка — **шаблон** из `building_template_registry` (`occupied_footprint` + опц. двор), в клетках. Любой `structure_type`, любой размер. Нет хардкода 200×200.

**Один модуль ≠ один участок.** Модуль сетки — **двумерный бин** `(block_size × block_size)`, рамка главной улицы, не лот. Участок — прямоугольник из cache (`occupied_footprint` + опц. двор), любой `structure_type` и любой размер.

#### Пайплайн посадки

SoT полного порядка района (C22). Внутренность **под** приоритетные здания. Размер `DistrictSlot` на карте города — `size_pct` ячейки (§9.6 city); **не** расти слот под усадьбу (это город, не packing).

1. Площадь района и якоря — **`SettlementAssembler`**: слот по `size_pct`; если барьер **поселения** валиден — вычесть прямые footprint ∩ слот из площади района. Затем шаблон этого района (`density` → шаг; барьер района → прямые **урезанного** слота). Нет поля района / `template` null — скип прямых района. Иначе **v1 packing:** внутренний bbox = урезанный слот минус прямые района `width_cells` **внутрь** (нет `sides` / `null` / `[]` → все 4 прямые слота; иначе указанные грани) минус коридор `through_road`. Клетки барьера района — **TODO** `DistrictAssembler`. Коридор запрещён для участков (в т.ч. брони прохода 1). Зоны трёх инстансов не пересекаются. Не забор участка, не стены здания.
2. **Коллекция оболочек.** Cache кандидатов: `w`,`h`. Интерьер комнат — не этот скоуп. Ключ `(template, facing)` — после рамки (§ «Cache и facing»). Из cache — список токенов (§ «Число токенов»). Полный generate всех домов до района — нет.
3. **Проход 1 — бронь приоритетных.** Решётка будущих модулей — тот же шаг `block_size`, что у `entry_nodes` (§5.2), во внутреннем bbox. Для каждого приоритетного — связный прямоугольник клеток этой решётки, куда влезает оболочка (спан, 90°). Не нарезать сначала все кварталы пустыми. Нет места во внутреннем bbox — `warning` / leftover; слот района не увеличивать. `position: center` — только у центра внутреннего bbox. SoT: «Два прохода посадки».
4. **Рамка вокруг броней.** Полосы главной сетки по **той же** решётке + пустые кварталы на земле без брони. Не резать бронь и не резать коридор якорей главной улицей (суперблок из нескольких модулей — одна земля). Слот-квартал без здания — пустая бронь земли под проход 2, не дом. Ещё не полотно сквозь дома. `grid` — ортогональная решётка. `radial` / `organic` — та же бронь; нарезка остатка — **CONN-PACK-1** (§8).
5. **Проход 2 — остальная коллекция.** В оставшиеся пустые кварталы / дырки. Влезло — вынуть, не вытеснять. Спан только ещё пустые слоты.
6. **Граф улиц** — главные по рамке, аллеи внутри модуля, не через клетки участков.
7. `StructureAreaAssembler` — слот уже стоит; только касающиеся отрезки.

**Коллекция токенов.** После cache — упорядоченный пул. Посадка **вынимает** токен. Не декартово пары. Сколько копий — ниже.

#### Число токенов (копии `system_name`)

SoT. Поля JSON — [tz_city_generation.md](./tz_city_generation.md) §3 (`CitySkeleton.structure_counts`), §9.2 / §9.4 (район). Здесь — резолв **N** для каждого `system_name`.

Пул: для каждого кандидата cache — **N** одинаковых токенов (один footprint). Кандидаты = `allowed_structure_types` ∩ тир ∪ шаблоны из `required_structures`. Нет в cache — нет токенов.

**N** — первое заданное:

| № | Источник | Когда |
|---|---|---|
| 1 | `required_structures[].count` | этот шаблон есть в `required_structures` района (`building_template` = `system_name`) |
| 2 | `district_template.structure_counts[system_name]` | ключ есть |
| 3 | `CitySkeleton.structure_counts[system_name]` | ключ есть |
| 4 | **1** | иначе |

Нет поля / нет ключа — **не** ноль: смотреть уровень ниже. Явный `0` — ноль токенов (не сажать). Запись в `required_structures` включает уровень 1 (нет `count` → 1) и **не** смотрит `structure_counts` для этого имени, даже если там больше.

`structure_counts` — `{ "<system_name>": int }`, optional. Район перекрывает город **по ключу**, не целиком map.

Не добивать район копиями «пока есть место». Не влезло — `warning`; лишние токены не превращаются в ещё N копий других шаблонов.

Пример: город `{ "house_std": 4 }`, район `{ "house_std": 2, "tavern_1": 3 }`, `required_structures`: `town_hall` `count` 1 → house 2, tavern 3, town_hall 1, прочие кандидаты по 1.

#### Приоритет посадки

SoT. Не путать с N: priority **не** меняет число токенов. Поля JSON — [tz_city_generation.md](./tz_city_generation.md) §3 (`CitySkeleton.structure_priority`), §9.2 / §9.4 (район).

**Очередь:**

1. **Приоритетные** (проход 1, до рамки пустых кварталов): `required_structures` (порядок массива) и шаблоны с `structure_priority` **> 0**. Для каждого — бронь во внутреннем bbox. Не «взять первый из кучи». Не «сначала нарезать район, потом втиснуть».
2. **Остальная коллекция** (проход 2, после рамки): остальные токены (`priority` ≤ 0 и не required).

`structure_priority` — `{ "<system_name>": int }`, optional. Больше = раньше **внутри прохода 1**. Нет поля / нет ключа — **0** (проход 2). Район перекрывает город **по ключу**. Явный `0` = остальная коллекция. Отрицательное — тоже проход 2, после нуля в списке коллекции.

Не делает шаблон `required_structures`. Не встал в проходе 1 — `warning`, в проход 2 как затычку щели **не** класть.

**Порядок внутри прохода 1** (после required). 90° не дублирует токен (`max`/`min` одинаковы для `100×500` и `500×100`):

1. `priority` — больше первым
2. при равенстве — `max(w, h)` — больше первым
3. при равенстве — `min(w, h)` — больше первым
4. при равенстве — `uid` по возрастанию

`(60,60)` раньше `(18,18)` при одном priority; `(100,20)` раньше `(80,80)` (max 100>80). Площадь `w*h` в ключ не входит.

Пример: `structure_priority`: `{ "manor_rich": 10 }` → усадьба в **проходе 1** до прочих приоритетных с меньшим числом. Ратуша в `required_structures` — раньше усадьбы. Дома с priority 0 — только проход 2.

#### Два прохода посадки

SoT. Не «берём первый токен». Два смысла подряд:

**Проход 1 — приоритетные (до рамки).** Состав: все `required_structures`, затем токены с `structure_priority` **> 0** (порядок — «Приоритет посадки»). Для **каждого** — бронь связного блока клеток решётки `block_size` во внутреннем bbox (спан `ceil(w/step)×ceil(d/step)`, 90°). Не через коридор якорей. Поставили — вынуть, не вытеснять. Нет места в bbox слота — `warning` / leftover; **не** отдавать это место обычной коллекции «пока ищем»; **не** расти `DistrictSlot`. `position: center` — только у центра внутреннего bbox; не встал — не класть куда попало и **не** в проход 2. AABB брони — из cache; facing к полосе рамки — после шага рамки («Поворот оболочки»). Какой AABB до полосы — **CONN-PACK-3** (§8).

**Проход 2 — остальная коллекция (после рамки).** Только токены, которых не было в проходе 1 (`priority` ≤ 0, не required). Оставшиеся пустые кварталы / дырки: для каждой — с начала этого списка, кто влезает (таблица ниже). Leftover после прохода — `warning`.

Усадьба (priority > 0) забирает 3×4 **до** нарезки остальных кварталов, если внутренний bbox позволяет. Рамка обходит эту бронь. Дома коллекции добивают щели в проходе 2.

**Токен — структура, не строка с геометрией.** Не кодировать `w`/`h` в uid (не «шифровать» в ключ): padding, разбор строки, коллизии. Поля:

| Поле | Зачем |
|---|---|
| `uid` | идентичность экземпляра: `system_name` + индекс копии |
| `w`, `h` | bbox из cache, **клетки**; влезание в дырку — пара осей |
| `priority` | резолв «Приоритет посадки», не в uid |

**Влезание — обе оси; 90° оболочки можно.** Дырка `(W, H)`, токен `(w, h)`. Влезает, если `w ≤ W` **и** `h ≤ H`, **или** `h ≤ W` **и** `w ≤ H`. Одна ориентация не влезла — пробовать вторую. Обе нет — конфликт. Не площадь и не узкая сторона. Какую ориентацию брать и как согласовать вход — «Поворот оболочки» ниже.

Один список не бисектится «в точку дырки» (ограничение 2D). **Проход 2 (остальная коллекция)** — куда смотреть:

| Участки в квартале | Где в списке |
|---|---|
| Ещё ни одного | **начало оставшейся коллекции** — первый, кто влезает |
| Уже есть участок, дырка `(W, H)` | С начала пропускать, пока не влезет с учётом 90°; `max(w,h) > max(W,H)` можно отсечь. Первый подошедший = FFD |
| Мелочь (обе оси малы) | **конец** — корзина «остаток» |

Не говорить «пустой модуль»: квартал сетки с рамкой улиц, **без посаженных участков**.

#### Поворот оболочки (90°)

SoT. C22 вариант 1 **не** отменяется: после generate **не** крутить клетки интерьера / граф комнат.

Packer **может** класть оболочку как `w×h` или `h×w` (поворот AABB на 90°). Пример: `100×500` и `500×100` — два положения одной оболочки в квартале. Ориентацию в `uid` не кодировать.

**Нельзя:** повернуть готовый layout на 180° «чтобы влезло» (AABB тот же, парадный окажется вглубь квартала). Зеркало / произвольный угол — нет.

**После посадки — одна сторона.** Грань участка к улице рамки (вход на участок: `gate` / `parcel_edge`) и парадный вход **основного** дома (`front`, `entry_point.wall`) — **та же** сторона, к этой улице. Двор: улица → калитка → двор → дверь дома, все на этой оси. Не калитка на юг, а парадный на восток.

Как согласовать, не крутя интерьер: generate/cache `(template, facing)` с `entry_point.wall` = грань к улице посадки. 90° в бине = другой cardinal → **другой** ключ cache, не rotate клеток `SOUTH`. Envelope другого facing может ≠ swap осей предыдущего; в бин идёт фактический footprint **этого** facing.

Ориентацию, где AABB влезает, но фасад не выходит на улицу посадки, **отбросить**. Обе ориентации годны (квадрат; или обе ставят front на полосу) — взять cache facing полосы рамки, 0° этого footprint.

Нет здания (`plaza` и аналоги): только вход участка к улице посадки; согласовывать `front` нечего.

Чёрный ход — по-прежнему напротив или с угла (C20), не вместо этого правила.

Три корзины — те же три зоны одного списка, не три разрозненных мешка.

**Классификация по бину (заранее, шаг известен).** Три корзины:

| Корзина | Когда |
|---|---|
| Спан | `ceil(w/step) × ceil(d/step)` по **посаженным** осям (после выбора 90°). Только **пустые** слоты |
| Один модуль | целиком в одном бине |
| Остаток | влезает в свободный прямоугольник внутри уже занятого модуля |

**Спан и слот.** Снимать можно только **ещё не занятое** (проход 1: модуль будущей сетки без брони; проход 2: пустой квартал рамки). Поставленное здание / занятый слот — нет. Не путать с домом после assembler: его тоже не двигают, но вытеснение fill к нему не относится (fill уже закончен). Токен с занятого слота в список не возвращать.

**Упаковка.** Два прохода (§ «Два прохода посадки»): бронь приоритетных, затем рамка, затем остальная коллекция. Семейство packer (shelf / guillotine / MaxRects) — impl выбирает один, не NP-перебор. Organic / radial: тот же квартал ячейки layout.

**Аллея.** Если в одном модуле ≥2 участка и между ними нужен проезд — ребро `alley` из `connections` города/района и ширины §3.4. Нет аллеи в настройках — не выдумывать; либо щель packing без новой нитки, либо не делить модуль. Аллея ≠ `PARCEL_GAP_M` и ≠ вторая главная улица. Грань участка 4-соседствует с главной сеткой **или** с этой внутренней аллеей.

Иллюстрация (не спецификация размеров): шаг 80 клеток, токены 60×60 и 18×18, аллея 2 клетки → оба в одном бине.

Улицы главной сетки не чертят сквозь клетки участков. Код v1: packing не знает `block_size`; улицы overlay по bbox. Целевое — §5.1.4.

#### Debug packing (C22)

SoT **событий** (что писать). **Куда** писать и как эмитить — [tz_logging.md](./tz_logging.md) (L1–L8). Не свой sink, не `print` / tee (L5), не голый `logging.getLogger` на те же события (L3). Шторм `fit` (каждая попытка) — **файл**, не stdout (L8). Сводка района (`area_slots`, `street_xy`) — `INFO` (heartbeat). Не влезло / civic не встал — `WARNING`, не exception. Поток попыток **не** на INFO.

**Фасад:** [`loggingConfig.py`](../backend/app/core/loggingConfig.py) (`JsonLogFormatter`, маршрут `{domain}/{service}`), [`generationLogging.py`](../backend/app/core/generationLogging.py) (транскрипт bake), [`logLevel.py`](../backend/app/core/logLevel.py).

**Хелперы консьюмеров** (тот же контракт; packing **не** пишет в их файлы):

| Модуль | API |
|---|---|
| [`relief/log/log.py`](../backend/app/application/worldData/generators/terrain/relief/log/log.py) | `relief_debug` / `relief_info` / `relief_warning` / `relief_error` |
| [`climate/loggingHelpers.py`](../backend/app/application/worldData/generators/climate/loggingHelpers.py) | `debug_once` / `warn_once` |
| [`packBakeLog.py`](../backend/app/application/worldData/pack/bake/packBakeLog.py) | heartbeat bake |
| [`dumpLog.py`](../backend/app/application/worldData/render/dumpLog.py) | `log_dump` |
| [`terrainParallelLog.py`](../backend/app/application/worldData/terrainParallelLog.py) | parallel ticks |

C22: консьюмер каталога **`settlement` / `settlementAssembler`**. Эмит — доменный хелпер того же вида (⬜ impl), не `getLogger(__name__)` в planner. Не второй движок debug HTTP.

Префикс сообщения: `C22 packing | district=%s step=%s`. Не писать полный `StructureLayout` / все клетки полотна. Счётчики, bbox, uid, `reason=`.

`step` и поля:

| `step` | Когда | Поля |
|---|---|---|
| `anchors` | якоря | `entry_nodes`, коридор `through_road` bbox или `reason=skip_no_entry_nodes` |
| `district_barrier` | инстанс барьера района | нет поля или `template` null → `reason=skip_no_perimeter_barrier`; иначе `reason=district_barrier_always` + `template` + `sides` + `width_cells` (v1 вычет прямых слота; клетки generate TODO) |
| `cache` | каждый кандидат | `system_name`, `facing`, `w`,`h`, `hit`/`miss` |
| `tokens` | пул после резолва N | `uid`, `w`,`h`, `N`, `priority`, `n_from=…`, порядок списка |
| `pass1` | проход 1, бронь до рамки | `uid`, бронь да/нет, `span=`, `reason=place\|skip_no_hole\|center` |
| `frame` | рамка вокруг броней | `block_size`, число пустых кварталов, длина полос сетки (клетки), внутренний bbox (после полосы барьера и коридора), число броней прохода 1 |
| `pass2` | проход 2, каждая дырка после рамки | `hole=`, кто из коллекции влез или `reason=empty_list` |
| `fit` | **каждая** попытка в дырку | квартал/`hole=%dx%d`, `token`, `try=0\|90`, `fit=yes\|no`, `reason=ok\|reject_axis\|reject_facade` |
| `place` | сел | `uid`, origin xy, посаженные `w×h`, `facing`, грань к улице рамки, `pass_id=1\|2` |
| `leftover` | токен не сел | те же поля, что WARNING; плюс оставшаяся дырка. `reason=leftover` |
| `alley` | после ≥1 посадки в квартале | `n_plots`, `alley=yes\|no`, `reason=from_connections\|not_in_settings\|single_plot`, ширина §3.4 |
| `graph` | граф после packing | `nodes`, `edges`, `street_xy`, занятые клетки участков (count) |
| `area` | каждый слот → assembler участка | `template`, `slot.facing`, касающиеся рёбра (тип+нить), `threshold.kind`, парадный дома vs вход участка (`align=yes\|no`) |
| `frontage` | tie равных рангов | счёт по ниткам, выбор или `reason=rng` + seed |

Якоря / барьер района без данных — одна строка `skip` с `reason`, не молчание. Cache без кандидатов — `warning`, не молчание.

### 5.1.4 Контракт района (`DistrictAssembler`)

Не дублировать алгоритм улицы (§5.1, layout). Здесь **обязанности района** в C22. Логи шагов — §5.1.3 «Debug packing».

**Вход:** `DistrictSlot` (bbox, шаблон, `entry_nodes`, `required_structures`), cache оболочек (ключ `(template, facing)` — после рамки), `CitySkeleton`, terrain колонок.

**Первоначальные проверки** (иначе район не влезает «внутрь себя»). Слот на входе уже без xy барьера **поселения** (`SettlementAssembler` вычел `footprint ∩ слот`). Нет поля района / `template` null — **скип** прямых района. Класс тот же, что у поселения и участка; инстанс и периметр — **района** ([tz_locations.md](./tz_locations.md)). Барьер поселения — прямые footprint, другой список клеток; packing района его не вычитает.

| Есть в данных | Район делает | Нет |
|---|---|---|
| `entry_nodes` не пуст | клетки якорей входа/выхода и коридор пары `through_road` **запрещены** для участков | скип резерва якорей |
| поле есть и `template` задан | инстанс **района** (прямые слота). v1 packing вычитает прямые района. Клетки — TODO `DistrictLayout.barrier_cells`. Не список поселения; общая xy запрещена | нет поля / `template` null — скип |
| оба (якоря + валидный инстанс) | inner bbox = урезанный слот минус прямые района минус коридоры; дырки под якоря в прямых (ворота). Внутренность ≤ 0 → `warning`. Влезание `required_structures` — проход 1 **после** cache | — |

**Кто какой размер знает (assembler, не «кэш»).**

| | Кто |
|---|---|
| Считает оболочку (`occupied_cells` / footprint) | `StructureAssembler` (вызов из района; полный интерьер комнат — не этот скоуп) |
| Держит словарь layout на поселение | `SettlementAssembler` (передаёт вниз) |
| **Читает размер и сажает участки** | **`DistrictAssembler`**. Сначала cache всех кандидатов района, потом бронь прохода 1, потом рамка, потом проход 2 (тип = фильтр + `required_structures`, не зона внутри района в v1). Число копий — §5.1.3 «Число токенов» |
| Чертит улицы вокруг уже занятого | `DistrictAssembler`: **рамка** после брони прохода 1 (обходит бронь); **граф/полотно** после всей посадки (инструмент — генератор улиц; слоты не ставит) |
| Собирает один уже посаженный слот | `StructureAreaAssembler`. Районную сетку и чужие участки не знает |

Кэш — только ящик с готовыми оболочками. Про размер района «знает» `DistrictAssembler`.

**Порядок посадки (единица = квартал сетки / модуль `block_size`, не AABB района).** Тот же, что §5.1.3 «Пайплайн посадки»:

1. Слот уже урезан поселением; якоря (`SettlementAssembler`, скип если нет). Инстанс барьера района: нет поля / `template` null — скип прямых. Иначе inner bbox **минус прямые района** (нет `sides` / `null` / `[]` = 4 грани слота) и не растёт.
2. Закэшировать **все** шаблоны-кандидаты района (`allowed_structure_types` ∩ тир, плюс `required_structures`) — `StructureAssembler` считает оболочки. Интерьер комнат — не этот скоуп.
3. Проход 1: бронь приоритетных в решётке `block_size` внутреннего bbox (не через коридор якорей). Не пустая сетка «всех кварталов» до этого шага.
4. Рамка: полосы и пустые кварталы **вокруг** броней. Не rasterize сквозь бронь / будущие дома прохода 2.
5. Проход 2: остальная коллекция в оставшиеся кварталы. Аллея из `connections` при ≥2 участках. Два прохода — «Два прохода посадки».
6. Граф улиц по факту: главные по рамке, аллеи между слотами модуля, не через клетки участков. Нитка `frontage` (не для `plaza`).
7. `StructureAreaAssembler` — слот уже стоит; только касающиеся отрезки.

Bin-pack всего района без модулей и шаг fill = `max(ширина)` — не этот алгоритм.

Тип участка **учитывается** так:

| Что | Учитывает `structure_type` / шаблон |
|---|---|
| Какие шаблоны вообще можно | да: `allowed_structure_types`, тир ±1 |
| Обязательные (ратуша, рынок, `plaza` в `required_structures`) | да: конкретный шаблон + `position` `center` \| `any` |
| Куда на плане обычный дом vs склад vs площадь при fill | **нет в v1:** после required и `structure_priority` — packing по размеру и щели, не «площадь в центр потому что plaza» |

Геометрия fill — 2D-упаковка в модуль (`DistrictAssembler`). Не генератор улиц как автор слотов и не `StructureAreaAssembler`.

**TODO (переход кода, не эта сессия):** [tz_city_generation.md](./tz_city_generation.md) **§6.3**.

**Семантика счёта vs слота.** Район видит все участки и все нитки: считает, сколько участков **касаются** каждой нитки (`frontage`). Участок **не** знает чужих участков и чужих рёбер. Ему только диапазоны координат рёбер, которых **он** касается, плюс то, что район уже решил по нитке (ранг / счёт для tie-break), не сырой граф района.

`through_road`: коридор между входом и выходом — запрет застройки + полоса нитки, к которой якорь snap’нут. Не дублирующее ребро поверх сетки.

Код: `barrier_cells` района пустые; якоря packing не резервирует; участку весь `street_xy`. Расхождение с этим §. Переход — **TODO** в [tz_city_generation.md](./tz_city_generation.md) §6.3.

### 5.2 ConnectionEntry — точки входа в район

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

`SettlementAssembler` создаёт `entry_nodes` **до** generate районов и кладёт их в `DistrictSlot`. Это **город**: поднять шаблон **этого** района, не копировать шаг с соседнего.

**Шаг:** `block_size_for_density(district_template.density)` ; нет `density` → `CitySkeleton.settlement_density`. Та же константа, что решётка packing / рамки `grid` в `DistrictAssembler`. Узлы совпадают с решёткой без snap.

**Где на грани:** валидный `perimeter_barrier` района → на **внутренней** стороне прямой района (`width_cells`, `sides`; нет `sides` / `null` / `[]` = четыре прямые слота). Нет инстанса района → на внешней грани **урезанного** `DistrictSlot`. Бронь прохода 1 не занимает коридор; рамка не режет бронь. `radial` / `organic` — **CONN-PACK-1** (§8).

`block_size` dense=50 / medium=80 / sparse=120 **клеток**.

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
   Алгоритм: равномерная сетка пересечений; block_size из `settlement_density` (dense=50 / medium=80 / sparse=120 клеток)

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
| Подъезд участок↔улица при разном z | **closed §5.1.1–§5.1.2:** луч только при Δz участок↔улица; иначе стык; ≤30° grade / 45° лестница; >45° только `map_z` |
| **CONN-PACK-1** — рамка `radial` / `organic` вокруг брони прохода 1; snap `entry_nodes` §5.2 вне `grid` | **открыт:** бронь та же, что у `grid`; нарезка остатка по `street_layout` не описана; совпадение узел↔решётка для non-grid не гарантировано |
| **CONN-PACK-2** — два (и более) `required_structures` с `position: center` | **открыт:** кто занимает геометрический центр внутреннего bbox; второй — leftover / смещение / `warning` |
| **CONN-PACK-3** — envelope `(template, facing)` на проходе 1, пока полосы рамки нет | **открыт:** бронь по AABB cache + 90°; после рамки ключ facing; если footprint не влезает в бронь — `warning`, бронь не двигать. Какой AABB брать до полосы (один facing / max / все 4) — нет |
| **CONN-FRONT-1** — приоритет главная/побочная | **closed:** упорядоченный список типов (дефолт движка); override город → район. Не поле `ConnectionEdge` |
| **CONN-FRONT-2** — вторая дорога с угла | **closed:** чёрный вход с угла можно |
| **CONN-FRONT-3** — число входов на отрезке | **closed:** `max_front_entries` / `max_service_entries` на шаблоне здания; 1 → середина; >1 → приём окон §3.10 |
| **CONN-FRONT-4** — две нитки **одного** ранга | **closed:** касание = 4-сосед клеток участка и полотна; счёт = район × нитка; равенство → rng. Лог `step=frontage` |
