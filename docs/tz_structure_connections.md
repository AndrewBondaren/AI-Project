# ТЗ: Механика соединений (tz_structure_connections.md)

## 1. Концепция

Соединения — граф (Вариант B): узлы (`ConnectionNode`) и рёбра (`ConnectionEdge`).  
Граф иерархический: мировой → городской → районный → участок.  
Pathfinding поднимается и опускается по уровням иерархии.

**Площадь** — не тип соединения. Это `structure_type="plaza"` в шаблоне здания,  
собирается через `StructureAreaAssembler`. В граф попадает только как `ConnectionNode`  
со ссылкой на `location_uid` площади.

---

## 2. Типы рёбер по уровням

| Уровень | `connection_type` | Описание |
|---|---|---|
| Мировой | `highway` | Наземная трасса между городами / поселениями |
| Мировой | `air_route` | Воздушная трасса; ребро на z выше terrain |
| Мировой | `sea_route` | Морской путь; ребро по water-ячейкам |
| Мировой | `portal` | Мгновенный переход; `cells = null` |
| Городской | `main_road` | Главная магистраль города |
| Городской | `bridge` | Автогенерируется, когда дорога пересекает water-ячейки |
| Городской | `city_gate` | Вход/выход из города; соединяет городской граф с мировым |
| Районный | `district_street` | Улица внутри района |
| Районный | `alley` | Переулок между зданиями |
| Участок | `path` | Грунтовая дорожка |
| Участок | `yard_path` | Путь внутри двора к входу здания |

---

## 3. Модель данных

### 3.1 ConnectionNode

| Поле | Тип | Описание |
|---|---|---|
| `node_uid` | string | Уникальный идентификатор |
| `x` | int | Мировые координаты (метры) |
| `y` | int | Мировые координаты (метры) |
| `z` | int | Мировые координаты (метры) |
| `node_type` | string | `"intersection"`, `"city_gate"`, `"portal"`, `"building_entrance"`, `"location_hub"` |
| `location_uid` | string? | Ссылка на `NamedLocation` (площадь, город, портал и др.); `null` если просто пересечение |
| `graph_level` | string | `"world"`, `"city"`, `"district"`, `"area"` |

### 3.2 ConnectionEdge

| Поле | Тип | Описание |
|---|---|---|
| `edge_uid` | string | Уникальный идентификатор |
| `from_node_uid` | string | Начальный узел |
| `to_node_uid` | string | Конечный узел |
| `connection_type` | string | Тип ребра (см. раздел 2) |
| `bidirectional` | bool | `true` по умолчанию; `false` для порталов с односторонним выходом |
| `traversal_conditions` | dict? | Условия прохода (см. 3.3) |
| `cells` | list[tuple[int,int,int]]? | Физические ячейки вдоль ребра для рендера и коллизий; `null` у порталов |
| `graph_level` | string | `"world"`, `"city"`, `"district"`, `"area"` |

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

- `cells = null` — нет физического пути
- `bidirectional = false` если портал односторонний
- Узлы портала имеют `node_type="portal"` + `location_uid` (NamedLocation портала)
- Порталы генерируются как `structure_type="portal"` через `StructureAreaAssembler`

### 4.2 Мост

- Автогенерируется когда ребро `main_road` / `highway` / `district_street` проходит через water-ячейки
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
                                создаёт city_gate-узлы → соединяет с мировым графом

DistrictAssembler
  └─ _plan_streets()         → ConnectionNode[] + ConnectionEdge[] уровня "district"
                                входные узлы соединяются с city_gate / main_road узлами

StructureAreaAssembler
  └─ _build_paths()          → ConnectionNode[] + ConnectionEdge[] уровня "area"
                                building_entrance-узел соединяется с ближайшим district_street

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
    node_type       TEXT NOT NULL,
    location_uid    TEXT REFERENCES named_locations(location_uid),
    graph_level     TEXT NOT NULL,
    world_uid       TEXT NOT NULL REFERENCES worlds(world_uid)
)

connection_edges (
    edge_uid            TEXT PRIMARY KEY,
    from_node_uid       TEXT NOT NULL REFERENCES connection_nodes(node_uid),
    to_node_uid         TEXT NOT NULL REFERENCES connection_nodes(node_uid),
    connection_type     TEXT NOT NULL,
    bidirectional       INTEGER NOT NULL DEFAULT 1,
    traversal_conditions TEXT,   -- JSON
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

---

## 7. Открытые вопросы

| Вопрос | Статус |
|---|---|
| Алгоритм прокладки `highway` между городами — A*, прямая, с обходом terrain | не описан |
| Алгоритм городской сетки улиц — прямая сетка vs органичная (Voronoi) | не описан |
| `air_route` узлы — всегда `structure_type="air_dock"` или могут быть произвольные точки | открыт |
| Морской путь (`sea_route`) — нужен отдельный мировой WorldGenerator или часть CityAssembler | открыт |
| Связь `connection_edge_cells` с `map_cells` — общая ячейка или overlay | открыт |
| Traversal в реальном времени — как engine проверяет `traversal_conditions` при движении | нет ТЗ |
