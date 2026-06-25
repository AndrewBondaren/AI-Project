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

`connection_type` описывает **топологию** соединения, а не уровень иерархии.  
`graph_level` — отдельное поле, определяет принадлежность к pathfinding-иерархии и не ограничивает тип.

| `connection_type` | Топология | Выравнивание terrain | Типичные `graph_level` |
|---|---|---|---|
| `trail` | тропинка; природная, зависит от terrain | нет | `area`, `district` |
| `dirt_road` | грунтовка; шире тропинки, без покрытия | нет | `area`, `district`, `city` |
| `road` | транспортная дорога; может быть мощёной | частичное | `district`, `city` |
| `sidewalk` | пешеходный тротуар; лежит параллельно `road` / `highway`; самостоятельный элемент со своим material/condition/features | частичное | `district`, `city` |
| `highway` | трасса; сложная топология — эстакады, развязки, тоннели | полное | `city`, `world` |
| `bridge` | пересечение водной преграды; автогенерируется поверх `road` / `highway` | — (надстройка) | любой |
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
| `node_type` | string | `"intersection"`, `"settlement_gate"`, `"portal"`, `"building_entrance"`, `"location_hub"` |
| `location_uid` | string? | Ссылка на `NamedLocation` (площадь, город, портал и др.); `null` если просто пересечение |
| `graph_level` | string | `"world"`, `"city"`, `"district"`, `"area"` |

### 3.2 ConnectionEdge

| Поле | Тип | Описание |
|---|---|---|
| `edge_uid` | string | Уникальный идентификатор |
| `from_node_uid` | string | Начальный узел |
| `to_node_uid` | string | Конечный узел |
| `connection_type` | string | Топологический тип ребра (см. раздел 2) |
| `bidirectional` | bool | Двустороннее движение; `true` по умолчанию; `false` для односторонних дорог |
| `lanes_per_side` | int | Кол-во полос в одну сторону; `1` по умолчанию; применимо к транспортным типам (`road`, `highway`) |
| `width_m` | int? | Ширина ребра в метрах; `null` = не задана. Для `sidewalk` — ширина тротуара; для `road` / `highway` — ширина одной полосы |
| `parent_edge_uid` | string? | Только для `sidewalk`: UID родительского ребра (`road` / `highway`), вдоль которого идёт тротуар |
| `side` | string? | Только для `sidewalk`: сторона относительно направления родительского ребра (`from_node → to_node`); `"left"` \| `"right"` |
| `material` | string? | ref → `material_registry`; покрытие дороги; `null` = природный terrain |
| `condition` | int | Состояние дороги 0–100%; влияет на бонус к передвижению (100% = полный бонус) |
| `features` | list[string] | Дополнительные атрибуты дороги: `"curb"`, … Открытый список; освещение — отдельное поле |
| `lighting_type` | string? | ref → `worlds.lighting_type_registry`; тип освещения вдоль ребра; `null` = нет освещения. См. [tz_lighting.md](tz_lighting.md) |
| `traversal_conditions` | dict? | Условия прохода (см. 3.3) |
| `cells` | list[tuple[int,int,int]]? | Физические ячейки вдоль ребра для рендера и коллизий; `null` у порталов |
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

- Автогенерируется когда ребро `road` / `highway` / `dirt_road` проходит через water-ячейки
- `connection_type="bridge"` заменяет исходный тип на участке пересечения с водой
- Ячейки моста (`cells`) — отдельный `MapCell` с terrain_overlay

### 4.3 Воздушная трасса

- Ребро с `connection_type="air_route"` существует на z > terrain
- `traversal_conditions: { "requires_flying": true }` или конкретный тип транспорта
- Узлы — вышки / причалы / аэропорты (`structure_type="air_dock"`)

---

## 5. Интеграция с assembler-иерархией

```
CityAssembler
  └─ _plan_street_grid()     → ConnectionNode[] + ConnectionEdge[] уровня "city"
                                создаёт settlement_gate-узлы → соединяет с мировым графом

DistrictAssembler
  └─ _plan_streets()         → ConnectionNode[] + ConnectionEdge[] уровня "district"
                                входные узлы соединяются с settlement_gate / road-узлами города

StructureAreaAssembler
  └─ _build_paths()          → ConnectionNode[] + ConnectionEdge[] уровня "area"
                                building_entrance-узел соединяется с ближайшим road / alley района

WorldGenerator (отдельно)
  └─ _plan_world_routes()    → highway, air_route, sea_route, portal между NamedLocation
```

`CityLayout`, `DistrictLayout`, `AreaLayout` расширяются полями:
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
    width_m             INTEGER,             -- nullable; ширина в метрах
    parent_edge_uid     TEXT REFERENCES connection_edges(edge_uid),  -- только для sidewalk
    side                TEXT,                -- "left"|"right"; только для sidewalk
    material            TEXT,                -- ref → material_registry; null = природный terrain
    condition           INTEGER NOT NULL DEFAULT 100,  -- 0–100%
    features            TEXT,                -- JSON: list[string]; "curb", …
    lighting_type       TEXT,                -- ref → lighting_type_registry; null = нет освещения
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

## 8. Открытые вопросы

| Вопрос | Статус |
|---|---|
| Гранулярность `condition` — одно значение на ребро не отражает реальность для длинных трасс; нужно решить как дороги разбиваются на отрезки | не описан |
| Алгоритм прокладки `highway` между городами — A*, прямая, с обходом terrain | не описан |
| Алгоритм городской сетки улиц — прямая сетка vs органичная (Voronoi) | не описан |
| `air_route` узлы — всегда `structure_type="air_dock"` или могут быть произвольные точки | открыт |
| Морской путь (`sea_route`) — нужен отдельный мировой WorldGenerator или часть CityAssembler | открыт |
| Связь `connection_edge_cells` с `map_cells` — общая ячейка или overlay | открыт |
| Traversal в реальном времени — как engine проверяет `traversal_conditions` при движении | нет ТЗ |
