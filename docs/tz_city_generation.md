# ТЗ: Генератор города

**Обновлено:** §11 init modes + persist plan (2026-06); sync TZ ↔ код.

**Связанные документы:**

| Документ | Роль |
|---|---|
| [tz_assembler_hierarchy.md](./tz_assembler_hierarchy.md) | Stack Settlement → District → Area → Structure |
| [.cursor/plans/settlement-assembler.md](../.cursor/plans/settlement-assembler.md) | Фазы A–H impl, acceptance |
| [tz_structure_connections.md](./tz_structure_connections.md) | Дороги settlement/district (§5) |
| [tz_generator_technical_debt.md](./tz_generator_technical_debt.md) | NC/MR smells settlement stack |

### Статус реализации (код vs это ТЗ)

| Блок TZ | Код | Статус |
|---|---|---|
| Фаза 2 lazy layout | `SettlementGeneratorService` → `SettlementAssembler` | ✅ фазы A–F plan |
| Фаза 3 lazy interior | `StructureGeneratorService` (+ area cache) | ✅ |
| Engine hook | `lazy_settlement` node | ✅ |
| §9 district templates | `planner/placement.py`, `DistrictAssembler` | ✅ core |
| §8 Eager World Bake | UI batch bake | ⬜ |
| Фаза 1 skeleton validate | import / world create | ⬜ partial |
| `dominant_material` post-assemble + DAG → LLM | layout / DAG | ✅ resolver; ⬜ DAG wire |
| Phase G organic footprint | `planner/footprint.py` v1 square | ⬜ v2 |
| Persist layout → connections + building `NamedLocation` в БД | `layoutCells` → map_cells only | ⬜ **след. цикл** — §11 |
| `world_generation.init_mode` (`config.toml` + API) | — | ⬜ spec ✅ §11 |

**Имена в коде (не путать с legacy в других TZ):**

| Legacy в старых черновиках | Фактический класс |
|---|---|
| `CityGeneratorService` | `SettlementGeneratorService` / `SettlementAssembler` |
| `BuildingGeneratorService` | `StructureGeneratorService` (см. [tz_building_generator.md](./tz_building_generator.md)) |

---

## 1. Scope

Генератор города строит наполнение поселения — здания, улицы, районы — из скелета города.  
Скелет генерируется **при создании мира** для всех поселений сразу. Детали (интерьеры, планировки) — **lazy**, при первом посещении игроком.

---

## 2. Принцип: Skeleton-first

### Проблема

Если LLM описывает город до того как он сгенерирован — она фантазирует.  
Если описание появилось раньше геометрии — они расходятся. Игрок входит и иллюзия рушится.

### Решение

```
Мир создан → скелет всех городов (instant)
LLM описывает → только из скелета (ограничена данными)
Игрок входит в город → SettlementGeneratorService.generate_layout (lazy)
Игрок входит в здание → StructureGeneratorService (lazy interior)
Описание совпадает с геометрией ✓
```

**Инвариант движка:** LLM никогда не получает данные которых нет. Скелет — минимум гарантированных данных о любом поселении.

---

## 3. Скелет города (CitySkeletonFields)

Скелет собирается в `CitySkeleton` (`generators/assemblers/citySkeleton.py`) из полей `NamedLocation`.  
**Runtime:** `SettlementAssembler._build_skeleton`; часть полей — optional JSON / `getattr` (NC-9 в tech debt).

| Поле | Тип | Откуда | Описание | Impl |
|---|---|---|---|---|
| `economic_tier` | string | `system_economic_tier` | Материалы, плотность, тип зданий | ✅ |
| `system_location_mood` | string | `NamedLocation` | `prosperous`, `declining`, … | ✅ |
| `display_location_mood` | string | `NamedLocation` | Для LLM | ✅ |
| `system_city_size` | string | `NamedLocation` | ref → `city_size_registry` | ✅ |
| `dominant_material` | string | post-assemble | ref → `material_registry`; **не** import | ✅ `resolve_dominant_material` |
| `architectural_style` | string | JSON import | ref → `architectural_style_registry`; для LLM | ✅ read |
| `settlement_density` | string | JSON import | `sparse` / `medium` / `dense` | ✅ read (NC-9) |
| `state_uid` | string | `NamedLocation` | Политический контекст LLM | ✅ location; ⬜ в `CitySkeleton` |

**Что LLM получает из скелета:**
- `display_location_mood` → тон описания
- `economic_tier` → богатство ("ухоженные фасады" vs "облупившаяся штукатурка")
- `architectural_style` → визуальный язык для LLM; генератором не используется (см. [tz_architectural_style.md](tz_architectural_style.md))
- `system_city_size` → масштаб

**`dominant_material`** — не из import; вычисляется **после** `SettlementAssembler.assemble` (§3.1), хранится на `SettlementLayout.dominant_material`.

### 3.1 `dominant_material` (post-assemble)

Код: `planner/dominantMaterial.py` → `resolve_dominant_material`.

После полной сборки layout:

1. **По районам** — для каждого `DistrictLayout` mode материалов из сгенерированных данных:
   - `connection_edges[].material`
   - `barrier_cells[].system_material`
   - `area_layouts`: building/small `cells[].system_material`, `barrier_cells`
2. **Город** — mode district-dominants; если в районах материалов нет — mode city-level (`connection_edges`, `barrier_cells` поселения).
3. **Fallback** — `economic_tier` города → `material_registry` (`use_type=wall`, как barriers).
4. **Fallback** — `stone` + `warn_once`, если tier отсутствует.

Import `dominant_material` на `NamedLocation` **игнорируется** генератором — иначе LLM-описание может не совпадать с фактической застройкой.

**Граница ответственности:** генератор отдаёт `SettlementLayout.dominant_material`. Прокидывание в LLM payload — **DAG** (`lazy_settlement` / scene nodes, см. `tz_engine_flow.md`, `tz_world_generation_dag.md`); пишется вместе с остальным DAG. Persist на `NamedLocation` — ⬜ (цикл §11.5), опционально для offline/скелета до layout.

---

## 4. Реестры (N+1 в `worlds`)

`worlds.architectural_style_registry` — см. [tz_architectural_style.md](tz_architectural_style.md).

### `worlds.location_mood_registry`

```json
[
  { "system_mood": "prosperous",   "display_mood": "Процветающий"   },
  { "system_mood": "declining",    "display_mood": "Приходящий в упадок" },
  { "system_mood": "militarized",  "display_mood": "Милитаризованный" },
  { "system_mood": "mysterious",   "display_mood": "Таинственный"   },
  { "system_mood": "dangerous",    "display_mood": "Опасный"        },
  { "system_mood": "abandoned",    "display_mood": "Заброшенный"    }
]
```

---

## 5. Фазы генерации

### Фаза 1 — World creation (eager)

Для каждого поселения в `locations[]` мирового JSON:
- Валидируется скелет (обязательные поля) — **⬜ import validator не полный**
- Вычисляется `dominant_material` если не задан явно (из `economic_tier` + `material_registry`) — **⬜** (перенесено на post-assemble, §3.1)
- Скелет сохраняется на `NamedLocation` (JSON import)

Опционально уже сейчас: `SettlementGeneratorService.plan_occupancy_only` — резерв footprint cells без полной геометрии.

Результат: все поселения имеют скелет. LLM может описывать любой город сразу.

### Фаза 2 — City entry (lazy)

При первом входе игрока в поселение (engine node `lazy_settlement`):
- `SettlementGeneratorService.generate_layout(world, settlement, terrain_cells?)` → `SettlementLayout`
- Оркестрация: `SettlementAssembler.assemble` — районы, улицы, barriers, building cache, map occupancy
- Читает скелет (`economic_tier`, `architectural_style`, `settlement_density`)
- После assemble: `SettlementLayout.dominant_material` — authoritative для LLM («мраморные стены»)
- Выбирает шаблоны из `building_template_registry` по `structure_type` и tier (±1)
- Persist: `collect_map_cells_from_layout` → `MapCellService` (grid occupancy + meter geometry)
- `NamedLocation` для каждого здания — **⬜ persist в БД отложен** (см. settlement-assembler plan)

**Точка входа кода:** `backend/app/application/worldData/generators/assemblers/settlementAssembler/`

### Фаза 3 — Building entry (lazy)

При первом входе в конкретное здание:
- `StructureGeneratorService` — полный интерьер (комнаты, ячейки, проходы)
- В city pipeline: layout часто из **building cache** (`StructureAreaAssembler` + `translate_layout`)

> **Product (2026-06):** интерьеры — **отдельный epic / STUB для режима `full`**. В «полной инициализации» мира (§11) **не входят** до отдельной реализации.

См. [tz_building_generator.md](./tz_building_generator.md) (legacy имя `BuildingGeneratorService` в тексте building TZ).

---

## 6. Алгоритм размещения зданий (v1)

> **Impl:** не монолитный алгоритм §6.2–6.3, а pipeline `SettlementAssembler` → `DistrictAssembler` → `StructureAreaAssembler`.  
> Smoke: `backend/scripts/debug_settlement.py`. Детали фаз: `.cursor/plans/settlement-assembler.md`.

### 6.1 Входные данные

- `city.map_x, map_y` — origin города на глобальной карте
- `city_size_registry[city.system_city_size].footprint_multiplier` — множитель на `world.map_cell_size_m`; сторона footprint в метрах = `footprint_multiplier × map_cell_size_m`
- `settlement_density` → плотность застройки
- `building_template_registry` — доступные шаблоны

**Значения по умолчанию `footprint_multiplier` в `city_size_registry`:**

| `system_city_size` | `footprint_multiplier` | При 3000м | При 2000м |
|---|---|---|---|
| `hamlet`     | 0.25 | 750м  | 500м  |
| `village`    | 0.5  | 1500м | 1000м |
| `town`       | 1.0  | 3000м | 2000м |
| `city`       | 2.0  | 6000м | 4000м |
| `metropolis` | 4.0  | 12000м | 8000м |

Настраивается в `worlds.city_size_registry` (N+1) — пользователь может изменить значения для своего мира.

### 6.2 Сетка улиц

> **Impl v1:** `planner/streets.py` — entry nodes, `plan_city_street_grid`, perimeter + inter-district corridors; не city-wide Voronoi.

> **Референс алгоритма:** Parish & Müller (2001) — ["Procedural Modeling of Cities"](https://www.semanticscholar.org/paper/Procedural-modeling-of-cities-Parish-M%C3%BCller/95c8a50d378638302c88baa0ad3472ee2c2306e4), SIGGRAPH.  
> Практическая реализация: [tmwhere — Procedural City Generation](https://www.tmwhere.com/city_generation.html).  
> Ключевые концепции для адаптации: **globalGoals** (направление роста улиц к зонам плотности) + **localConstraints** (проверка препятствий). Паттерны сетки: `grid`, `radial`, `organic` (Voronoi).  
> Адаптация к нашей модели: вместо population density map — `economic_tier` зон и `district_type`; вместо глобальной карты — `DistrictSlot` с `settlement_density`.

```
footprint_m    = footprint_multiplier × map_cell_size_m
city_footprint = квадрат footprint_m × footprint_m вокруг origin
главная улица  = горизонтальная или вертикальная полоса через центр (rng)
вторичные улицы = перпендикулярные ответвления; количество зависит от city_size
кварталы = прямоугольные блоки между улицами
```

### 6.3 Заполнение кварталов

> **Impl:** `DistrictAssembler` + `areaSlots.py` (bin-packing), `buildingCache.py`, `required_structures` на slot.

```
для каждого квартала:
    тип квартала: residential / commercial / civic / mixed
        (зависит от distance от центра: центр → commercial/civic, периферия → residential)
    
    для каждого слота в квартале:
        выбрать шаблон из building_template_registry
            фильтр: structure_type совместим с типом квартала
            фильтр: economic_tier совместим с city.economic_tier (±1 тир)
        разместить здание → NamedLocation (без интерьера)
        mark slot занятым
```

### 6.4 Особые объекты

Civic-здания (ратуша, храм, рынок) — `required_structures` в district template; impl ✅ (`areaSlots`, Phase C/E).

---

## 7. Интеграция с LLM

> **Impl:** сбор LLM payload — **не** в генераторе; нода DAG читает repos / результат `lazy_settlement` и кладёт поля в контекст LLM. Генератор только materialize данные (`SettlementLayout`, `NamedLocation`, cells).

**До генерации (только скелет)** — DAG может отдать:

```
display_name, display_description, display_location_mood,
architectural_style → lore_registry[glossary_ref],
economic_tier → display_tier из economic_tier_registry,
state → display_name из states
```

**После layout** — DAG добавляет (источник: `SettlementLayout.dominant_material`, §3.1):

```
dominant_material → display_name из material_registry
```

Плюс список зданий (`NamedLocation.display_name`, `system_location_type`) — когда persist cycle закрыт.

LLM **не получает** от генератора напрямую: планировку улиц, интерьеры, сырые cells.

**Инвариант:** описание LLM согласовано с данными. "Мраморные здания" → только если в payload попал `dominant_material` после assemble, не import.

---

## 8. Режим полной инициализации

**Superseded** настройкой **`world_generation.init_mode = "full"`** (§11). Отдельная UI-кнопка «Инициализировать мир» — опционально позже, тот же gate.

**Не входит в `full`:** интерьеры зданий (фаза 3) — **STUB / отдельный epic**.

Legacy UX-идеи (прогресс-бар, export) — применимы к режиму `full` после snapshot + persist.

---

## 9. Шаблоны районов (`district_template_registry`)

> **Impl:** ✅ core — `planner/placement.py`, `planner/districts.py`, `DistrictAssembler`. См. settlement-assembler Phase A–C.

Район — шаблон. `SettlementAssembler` размещает шаблоны районов на позиции глобальных ячеек города,
проверяя условия появления. `DistrictAssembler` получает уже выбранный шаблон.

### 9.1 Хранение

Аналогично `building_templates` — глобальная таблица шаблонов, не привязанная к конкретному миру.
Per-world реестр: `worlds.district_template_registry` (JSON-массив, как `building_template_registry`).

### 9.2 Схема шаблона района

| Поле | Тип | Обязательность | Описание |
|---|---|---|---|
| `system_name` | string | required | Уникальный ключ: `"port_district"`, `"merchant_quarter"` |
| `display_name` | string | required | Отображаемое название |
| `district_type` | string | required | Семантический тип: `"residential"`, `"commercial"`, `"civic"`, `"military"`, `"port"`, `"industrial"` и др. (N+1) |
| `placement_conditions` | array | optional | Условия появления района (см. 9.3). Пустой массив = всегда доступен |
| `max_per_city` | int | optional | Максимальное количество районов этого типа в одном городе. `null` = без ограничений |
| `size_pct` | object | optional | Диапазон размера района как доля глобальной ячейки: `{ "width": [0.3, 1.0], "depth": [0.3, 1.0] }`. `1.0` = вся ячейка |
| `allowed_structure_types` | string[] | optional | `structure_type` из `building_template`, допустимые в этом районе. `null` = без ограничений |
| `economic_tier_range` | object | optional | `{ "min": "poor", "max": "exceptional" }` — диапазон тиров зданий в районе |
| `density` | string | optional | `"sparse"`, `"medium"`, `"dense"`. Переопределяет `city_skeleton.settlement_density` для этого района |
| `street_layout` | string | optional | Алгоритм раскладки улиц района (см. 9.5). `null` = наследует от города |
| `connections` | array | optional | Объявления дорог внутри района: тип, sidewalk, роль. Не объявленные — генератор определяет сам. Формат — см. 9.5 |
| `required_structures` | array | optional | Особые обязательные постройки (ратуша, храм, рынок) — см. 9.4 |

### 9.3 Условия появления (`placement_conditions`)

Каждое условие — объект с полем `type`. `SettlementAssembler` проверяет все условия до размещения.
Все условия должны быть выполнены (AND-логика).

| `type` | Параметры | Описание |
|---|---|---|
| `adjacent_terrain` | `terrain_types: string[]`, `min_count: int` | Смежная с ячейкой города terrain-ячейка должна иметь один из указанных `system_terrain`. Пример: порт требует `["liquid_body"]` |
| `min_city_size` | `size: string` | ref → `city_size_registry.system_size`; город не меньше указанного размера |
| `economic_tier_min` | `tier: string` | Минимальный `system_economic_tier` города |
| `economic_tier_max` | `tier: string` | Максимальный `system_economic_tier` города |
| `requires_district_type` | `district_type: string` | В городе уже должен быть район указанного типа |
| `excludes_district_type` | `district_type: string` | В городе НЕ должно быть района указанного типа |

Пример — шаблон портового района:
```json
{
  "system_name": "port_district",
  "display_name": "Портовый район",
  "district_type": "port",
  "max_per_city": 1,
  "placement_conditions": [
    { "type": "adjacent_terrain", "terrain_types": ["liquid_body"], "min_count": 1 },
    { "type": "min_city_size", "size": "town" }
  ],
  "allowed_structure_types": ["warehouse", "tavern", "shop", "guild"],
  "density": "dense"
}
```

### 9.4 Обязательные особые постройки (`required_structures`)

Civic-постройки (ратуша, рынок, храм) объявляются в шаблоне района:

```json
"required_structures": [
  { "building_template": "town_hall",  "count": 1, "position": "center" },
  { "building_template": "market",     "count": 1, "position": "any"    }
]
```

`position`:
- `"center"` — размещается ближе к геометрическому центру района
- `"any"` — произвольная позиция

### 9.5 Типы раскладки улиц (`street_layout`)

`street_layout` — алгоритм генерации улиц внутри района. Задаётся в `district_template`; `DistrictAssembler` выбирает соответствующий sub-алгоритм.

| `street_layout` | Характер | Типичные районы |
|---|---|---|
| `grid` | Прямоугольная сетка, равные блоки, широкие прямые улицы | Бизнес-центр, индустриальный |
| `organic` | Хаотичная сеть, узкие переулки, нет планирования; следует рельефу | Клоака, старый город, трущобы |
| `radial` | Лучи от центральной точки (площадь, ратуша) с кольцевыми улицами | Богатый район, civic |
| `cul_de_sac` | Главная улица с тупиковыми ветками; закрытые кластеры | Пригород, жилой |
| `courtyard` | Закрытые кварталы с внутренними дворами; минимум уличного фронта | Медина, восточный стиль |

Референс алгоритмов: Parish & Müller (2001) — паттерны `grid / radial / organic` применяются на уровне района, а не города целиком.  
`DistrictAssembler` получает `street_layout` из шаблона и вызывает соответствующий генератор улиц.

### 9.5.1 Объявления соединений (`connections`)

Шаблон района может явно объявить нужные дороги и коннекты. Если `connections` не задан — генератор определяет их самостоятельно на основе `street_layout` и `district_type`.

```json
"connections": [
  {
    "connection_type": "road",
    "role":            "main_street",
    "sidewalk":        true,
    "lanes_per_side":  1
  },
  {
    "connection_type": "alley",
    "role":            "back_alley",
    "sidewalk":        false,
    "lanes_per_side":  null
  }
]
```

| Поле | Обязательность | Описание |
|---|---|---|
| `connection_type` | required | ref → `connection_type_registry.system_connection_type` |
| `role` | optional | Семантическая роль внутри района (`"main_street"`, `"back_alley"`, `"service_road"`, …); движок использует для приоритизации при планировке |
| `sidewalk` | optional | `true` / `false`; `null` = генератор решает по контексту |
| `lanes_per_side` | optional | Переопределяет `road_settings.default_lanes_per_side`; `null` = берётся из road_settings |

`DistrictAssembler` читает объявления и генерирует `ConnectionEdge` с `has_sidewalk` из поля `sidewalk`.  
Необъявленные дороги генератор добавляет сам если `street_layout` это предполагает.

### 9.6 Алгоритм размещения районов (`SettlementAssembler`)

```
для каждой позиции глобальной ячейки города:
    кандидаты = [t for t in district_template_registry
                 if _check_conditions(t, cell_position, city, terrain)]
    
    отсортировать кандидаты по приоритету (специализированные > общие)
    
    выбрать шаблон (rng или детерминированный выбор)
    
    DistrictSlot(
        origin_x = cell_x * cell_size_m + offset,
        origin_y = cell_y * cell_size_m + offset,
        width_m  = width_pct  * cell_size_m,
        depth_m  = depth_pct  * cell_size_m,
        ground_z = terrain_z_at(cell_x, cell_y),
        district_template = выбранный шаблон,
    )
```

`cell_size_m` — **`World.map_cell_size_m`** через `generators/coordinates/cell_size_m(world)`.  
Не `world.map_settings["global_cell_size_m"]` (ghost key — см. NC-1g в tech debt).  
Footprint и district slots — `generators/coordinates/` (WORLD_SURFACE_GRID vs WORLD_LOCAL_METERS — [tz_terrain_generation.md](./tz_terrain_generation.md) § coordinates).

---

## 10. Открытые вопросы

| Вопрос | Статус |
|---|---|
| Алгоритм сетки улиц — city-wide organic (Voronoi) vs grid | **v1 закрыт:** grid + entry nodes (`streets.py`). Organic — Phase G / §10 TODO |
| Размещение нескольких районов в одной глобальной ячейке — sub-cells | **open** — settlement-assembler Phase C |
| `dominant_material` — post-assemble из layout; fallback tier / stone | **closed** — §3.1, `dominantMaterial.py` |
| Regeneration — скелет изменился после generate | **deferred** — snapshot (§11.4) |
| Механика дорог внутри района и между районами | **closed** — [tz_structure_connections.md](./tz_structure_connections.md) §5; `DistrictAssembler` + `connectionPolicy` |
| `adjacent_terrain` — связанность воды | **open** — condition есть, connectivity не описана |
| **Footprint города — форма** | **v1 closed:** квадрат `footprint_multiplier × map_cell_size_m`. **v2:** §10 TODO organic |

### TODO: Псевдо-историчный алгоритм footprint (v2)

Реальные города не растут квадратом. Нужен алгоритм расстановки с органичной формой.

**Кандидаты паттернов роста:**

| Паттерн | Описание | Условие применения |
|---|---|---|
| `radial_organic` | Рост от ядра (замок / рынок / храм) неравномерными кольцами | дефолт для большинства |
| `river_linear` | Вытянутый вдоль реки / побережья | `adjacent_terrain` содержит воду |
| `road_linear` | Вытянутый вдоль торгового пути | есть highway через ячейку |
| `defensive_polygon` | Форма следует рельефу (гора, обрыв) для стен | горный terrain |
| `grid_planned` | Правильный квадрат / прямоугольник | имперский стиль, колония |

**Алгоритм `radial_organic` (приоритетный v2):**
1. Определить ядро — тип из `district_template_registry` с `role="civic_center"` или `"market"`
2. Разместить ядро в центре (или смещённо — rng ±20%)
3. Расти районами от ядра: civic → commercial → residential → industrial → slum
4. Форма каждого кольца деформируется на ±15-30% по terrain
5. Границы города = convex hull районов + буфер под стены

**Связь с terrain:** terrain skeleton ✅ (multi-pass); organic deformation районов — **Phase G**, после стабилизации footprint v2.

---

## 11. Инициализация мира, persist, snapshot (2026-06)

### 11.1 Настройка — `config.toml` + API (не `World`)

| Ключ | Хранение | API |
|---|---|---|
| `world_generation.init_mode` | `[world_generation]` в `config.toml` | `GET/PUT /api/settings` |

```toml
[world_generation]
init_mode = "partial"   # full | partial
```

Цепочка: `ConfigManager` ↔ `AppSettings` ↔ `SettingsService` ↔ engine gates.

### 11.2 Режимы

| `init_mode` | Поведение (target) |
|---|---|
| **`full`** | Materialization **по правилам целиком**: terrain **S→O→C→CL**, все settlements — outdoor layout + persist (§11.3). Regen при изменении terrain — **после snapshot**. |
| **`partial`** | Lazy: дозагрузка при входе в локацию. Regen уже созданных при изменении — **после snapshot** (§11.4). |

### 11.3 Scope materialization (без интерьеров)

| Слой | `full` | `partial` | Persist (след. цикл) |
|---|---|---|---|
| Terrain S→O→C→CL | ✅ | по необходимости | map_cells ✅ |
| Settlement outdoor layout | ✅ | при первом входе | map_cells ✅ |
| `connection_nodes` / `edges` | ✅ | при layout | ⬜ |
| Building `NamedLocation` | ✅ | при layout, **если ещё не init** | ⬜ |
| **Интерьеры** (фаза 3) | **⬜ STUB** | lazy отдельно | отдельный epic |

### 11.4 World Snapshot — unified module

Runtime **нет**; target — [`tz_world_snapshot.md`](./tz_world_snapshot.md).

| Принцип | Смысл |
|---|---|
| **Единый модуль** | `WorldSnapshotService` — capture / restore / branch; **не** per-domain ad-hoc snapshots |
| **Каждый ход** | После commit — **полное** сохранение мира в `world_snapshots` ([`project_data_storage_tz.md`](./project_data_storage_tz.md)) |
| **Потребители** | Regen diff, time travel, TR-2 debug replay, climate far LOD — читают **restore**, не свой формат |

**Отложено до WS-1:** change detection (`partial` init), regen matrix, time travel UI, TR-2 unblocked.

### 11.5 DoD — persist cycle (без snapshot gate)

**Контракт:** отдельный `SettlementPersistService` (+ `ConnectionPersistService` для графа) — **не** генератор, **не** DAG, **не** LLM.  
Debug API и DAG вызывают **одни и те же методы** (аналог `MapCellService.save_terrain_batch` ↔ `POST …/generate-surface` ↔ `lazy_terrain`).  
DAG подключается **в обход HTTP** — напрямую к service/repos через `context` / `Container`.

> **Не новый продуктовый scope.** Создание зданий и дорог уже в ТЗ — здесь только **persist + сервисный контракт** для подключения DAG и debug harness.

#### Связь с доменными ТЗ

| Тема | Где описано | Что делает §11.5 |
|---|---|---|
| Процедурная застройка города | [tz_assembler_hierarchy.md](./tz_assembler_hierarchy.md), §6 здесь | bootstrap persist outdoor layout |
| Граф дорог, `graph_level`, `settlement_gate` | [tz_structure_connections.md](./tz_structure_connections.md) §1–5, **§5.1** поток сборки | persist `connection_nodes` / `connection_edges` |
| Межгородские маршруты (`_plan_world_routes`, highway, sea_route) | [tz_structure_connections.md](./tz_structure_connections.md) §5.1, §8 | persist `graph_level=world`; generate — отдельно от `SettlementAssembler` |
| Игрок / мастер: новое здание, участок дороги | [tz_world_generation_dag.md](./tz_world_generation_dag.md) — `place_building`, `construct_building`, `connect_road`; правило v2 (узкие вызовы) | patch persist `add_building` / `add_road_*` |
| `under_construction` / `under_repair` | [tz_building_generator.md](./tz_building_generator.md) §14, [tz_structure_connections.md](./tz_structure_connections.md) §3.2 | поля на persist; gameplay gate — DAG |
| Строительство (ресурсы, время, мастерство) | [tz_construction.md](./tz_construction.md) | placeholder; не блокирует persist cycle |
| Новое ребро при отсутствии торгового пути | [tz_economy.md](./tz_economy.md) | вызывает тот же `connect_road` / world-route generate + persist |
| Границы слоёв (generate ≠ persist ≠ LLM) | `.cursor/rules/layer-boundaries.mdc` | генераторы materialize; service пишет в БД |
| **Модификация terrain** | [tz_terrain_generation.md](./tz_terrain_generation.md) § Persist cycle — **локальный patch** (cataclysm, combat, excavate); bootstrap S→O→C→CL отдельно | `MapCellService.persist_terrain_patch` + scopes |

DAG может materialize **разные уровни** в разных нодах/фазах — persist зеркалит granularity, а не один монолитный «save everything».

#### Уровни bootstrap (generate ↔ persist)

| Scope | Generate (сейчас) | Persist (target) | Когда DAG |
|---|---|---|---|
| `occupancy` | `plan_occupancy_only` | surface grid cells (`occupancy_cells`) | world create / `full` init — [`generate_settlement_skeleton`](./tz_world_generation_dag.md) |
| `map_cells_surface` | `collect_surface_grid_cells` | INSERT OR IGNORE footprint | с occupancy или отдельно |
| `map_cells_geometry` | `collect_geometry_meter_cells` | barriers + building shell cells | первый вход / outdoor layout — [`generate_settlement_geometry`](./tz_world_generation_dag.md) |
| `connections_city` | `SettlementLayout.connection_*` | nodes/edges `graph_level=city` | после city streets — [tz_structure_connections.md](./tz_structure_connections.md) §5.1 |
| `connections_district` | `DistrictLayout.connection_*` | nodes/edges `graph_level=district` | `DistrictRoadGenerator` |
| `buildings` | `AreaLayout.building_location` | upsert `NamedLocation`, **skip if initialized** | `StructureAreaAssembler._place_building` |
| `interiors` | `StructureGeneratorService` | ⬜ STUB | [`generate_building`](./tz_world_generation_dag.md); отдельный epic |

Удобная обёртка `persist_outdoor(layout)` = union scopes без `interiors` — для smoke и типового lazy settlement, но **не** единственная точка входа.

#### Динамическое изменение мира (growth — уже в ТЗ, impl отдельно от bootstrap)

Поселения и дороги **не статичны**. После bootstrap DAG/debug вызывают **узкие** generate + patch persist (см. [tz_world_generation_dag.md](./tz_world_generation_dag.md) § Player build, правило v2):

| Операция | Generate (target class) | `graph_level` | Persist scope | DAG node (контракт) |
|---|---|---|---|---|
| Новое здание в городе | `SettlementGrowthService.place_building` | — (cells + `NamedLocation`) | `add_building` | `place_building` / `construct_building` |
| Новая улица в городе | `SettlementGrowthService.extend_road` | `city` / `district` / `area` | `add_road_urban` | `connect_road` |
| Трасса / тропа между локациями | `WorldRouteGeneratorService` — [tz_structure_connections.md](./tz_structure_connections.md) §5.1 `_plan_world_routes` | `world` | `add_road_world` | `connect_road` (world) |
| A* highway city↔city | тот же; алгоритм | `world` | тот же | отложено — [tz_structure_connections.md](./tz_structure_connections.md) §8 |

**State loaders** (read persisted → base для growth): `SettlementStateLoader` (urban), `WorldGraphStateLoader` (world graph + gates/hubs).  
**Persist:** общий `ConnectionPersistService.persist_patch` для urban и world edges; `SettlementPersistService` — cells + building locations.

Стык urban ↔ world: `settlement_gate` на границе footprint — [tz_structure_connections.md](./tz_structure_connections.md) §2.2, §5.1.

#### Idempotency

- Buildings: skip if location уже есть / помечен initialized (geometry probe — `needs_settlement_geometry`).
- Map cells: `INSERT OR IGNORE` (как сейчас `lazy_settlement`).
- Connections: upsert by `node_uid` / `edge_uid`; не дублировать при повторном вызове того же scope.

#### Debug API (harness)

Тонкая оболочка над service — **те же scopes и классы**, что DAG (обход HTTP в production):

- `POST …/map/generate-settlement?scope=occupancy|outdoor|…` — bootstrap
- `POST …/settlements/{uid}/extend-road`, `POST …/connections/plan-world-route` — growth (TBD)
- Smoke: `GET …/locations` + `GET …/connections`

#### Checklist

- [x] `SettlementPersistService` — scope-based bootstrap API
- [x] `ConnectionPersistService` — patch persist nodes/edges (urban + world)
- [x] repos + migration: `connection_nodes`, `connection_edges`, `connection_edge_cells`
- [x] building `NamedLocation` upsert (skip if initialized)
- [ ] `SettlementStateLoader` / `WorldGraphStateLoader` — для growth (можно следом)
- [ ] `SettlementGrowthService` / `WorldRouteGeneratorService` — по контрактам DAG ТЗ (можно следом)
- [x] debug route(s) — mirror DAG entry points
- [ ] `init_mode` в `AppSettings` + API (можно параллельно)
- [ ] DAG wire — **не в этом цикле** (мастер); см. [tz_world_generation_dag.md](./tz_world_generation_dag.md)

---

## Changelog

| Дата | Изменение |
|---|---|
| 2026-06 | §11.5 — persist cycle: ссылки на tz_world_generation_dag, tz_structure_connections §5.1, tz_construction, growth/world routes, terrain modification |
| 2026-06 | Sync TZ ↔ код: `SettlementGeneratorService`, `StructureGeneratorService`, `map_cell_size_m`, статус фаз A–F, §10 |
| 2026-06 | `tz_assembler_hierarchy.md` §7.5 — `map_cell_size_m` вместо `map_settings.global_cell_size_m` |
