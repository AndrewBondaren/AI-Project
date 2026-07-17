---
name: tz-flora
description: "ТЗ домена flora — N+1 registries, FloraGenerator, occupancy; consumers: forest, plains, settlement, farmland, …"
metadata:
  node_type: memory
  type: project
---

# Flora (отдельный домен)

## Назначение

Зафиксировать **целевую архитектуру** растительности мира как **отдельного домена** и **pure generator**, а не подсистемы «только лес».

**FloraGenerator** используется в разных контекстах: лес, луг/равнина, парк поселения, farmland (crops), склоны `FORESTED` mountain, full_bake occupancy и т.д.

| Система | Роль |
|---|---|
| **FloraGenerator** | eligible видов ∩ climate + occupancy на клетках → `FloraLayout` |
| **Forest / plains / … masks** | region + paint `system_terrain`; **зовут** flora |
| **Climate** | вход фильтра suitability ([`tz_climate.md`](./tz_climate.md)) |
| **Locations / objects** | экземпляры на occupied cells ([`tz_locations.md`](./tz_locations.md)) |

**Не в scope:** DAG wiring; LLM payload; хардкод списков видов в contributors.

**Связь с L0:** forest mask — [`tz_map_light_bake.md`](./tz_map_light_bake.md) § Surface mask domains / forests (кратко + ссылка сюда).

---

## Слои

```text
world.tree_registry | bush_registry | grass_registry | plant_registry | crops_registry
        │
        ▼
FloraSuitabilityIndex   # build once / bake; from FloraClimateSuitability ranges
        │
        ▼
query(climate cell|zone profile) → eligible entries
        │
        ├── forest autoresolve / landcover gate (trees empty? → no forest paint)
        └── FloraGenerator(context) → FloraLayout / FloraCellOccupancy
                ├── forest domain → paint forest + type refs / full_bake noise
                ├── plains / meadow
                ├── settlement park / yard
                ├── farmland (crops only)
                └── mountain FORESTED slopes
```

| Слой | Делает | Не делает |
|---|---|---|
| **FloraSuitabilityIndex** | кэш eligible по climate query; SoT ranges из registries | paint terrain, литералы видов |
| **FloraGenerator** | mix + occupancy (tree/bush/plant/grass) через index | `system_terrain`, declare Spec маски |
| **Consumer** (forest…) | region, policy, paint, оркестрация bake | свой climate filter / свой скан реестра |
| **Registries** | N+1 виды + suitability | materialize клеток |

---

## N+1 registries (утверждено)

Корни привязаны к **движковому** `FloraKind` (не N+1). N+1 — только виды внутри kind.

| Корень | `FloraKind` (engine) | N+1 виды |
|---|---|---|
| `world.tree_registry` | `tree` | `tree_type` |
| `world.bush_registry` | `bush` | `bush_type` |
| `world.grass_registry` | `grass` | `grass_type` — покрытие на soil |
| `world.plant_registry` | `plant` | `plant_type` |
| `world.crops_registry` | `crops` | `crops_type` |

### FloraKind — движковый тип (не N+1)

**`FloraKind` = engine enum** — тот же подход, что везде в проекте: **движок = класс/дискриминатор поведения**, **N+1 = каталог экземпляров/видов** внутри класса (как `MaterialCategory` vs `material_registry`, `MountainKind` vs declare entries).  
Мастер **не** создаёт новые kinds через JSON; только выбирает kind для вида и заполняет N+1 **внутри** kind.

**SoT инварианта — `dataModel`** (не generator, не route, не string-literal в orchestrator):

```text
# target:
backend/app/dataModel/flora/enums/floraKind.py   # StrEnum FloraKind
# entry POJO: flora_kind: StrictEnumOnWire[FloraKind]
# consumers / JV / generators — только import из dataModel
```

Канон проекта: engine discriminators → `dataModel/**/enums/*.py` (`StrEnum` + wire); см. `MaterialCategory`, `GeographicSubtype`, `HydrologyCellRole`.  
Новый член `FloraKind` = PR: dataModel (+ sync JV/validators) — **не** правка world JSON.

```text
FloraKind (engine, fixed in dataModel) =
  | tree
  | bush
  | grass
  | plant
  | crops

# N+1 = виды внутри kind
world.tree_registry[]   # только flora_kind=tree
world.bush_registry[]
…
```

| | Engine (`FloraKind`) | N+1 (вид) |
|---|---|---|
| Кто задаёт | движок (PR → **dataModel**) | мастер мира |
| Примеры | `tree`, `crops` | `oak`, `wheat` |
| Новый элемент | новый kind = PR dataModel | новая строка в registry |
| Дискриминатор | поле `flora_kind` на entry = `StrictEnumOnWire[FloraKind]` | `system_tree` / `system_crop` / … |
| Запрещено | литералы `"tree"` в generators/DAG вместо enum | угадывать kind по имени/glossary |

**Как отличить crops от plant:** у записи `flora_kind: crops` vs `flora_kind: plant` — значение из **движкового** enum в dataModel, не свободная строка мастера.

```text
# OK — мастер кладёт вид в crops registry с engine kind
{ flora_kind: "crops", system_crop: "wheat", … }

# FORBIDDEN — мастер выдумывает kind
{ flora_kind: "shrubbery", … }           # не член FloraKind
{ flora_kind: "plant", system_plant: "wheat" }  # пшеница как plant — ошибка домена (farmland = crops)
```

Consumers читают **engine kind** из dataModel:

| Consumer | FloraKind |
|---|---|
| Forest wild | `tree`, `bush`, `grass`, `plant` — не `crops` |
| Farmland | `crops` |
| Meadow | `grass`, `plant` |

Registry root ↔ kind: validate `entry.flora_kind` ∈ FloraKind и совпадает с корнем.  
`glossary_ref` — optional лор **вида** (N+1); optional kind-level lore keys `flora_*` для display класса — **не** замена enum.

### `tree_type` — declare (N+1 catalog)

Каталог вида (мастер). **Не** инстанс на карте.

```text
TreeTypeEntry / tree_type:          # world.tree_registry[]
  system_tree: str                  # system_name / wire key
  display_name: str                 # display (tree_type label)
  glossary_ref: str | null          # лор вида (не дискриминатор kind)
  flora_kind: "tree"                # обязателен; = FloraKind.tree
  wood_type: ref → world material
  bark_type: ref → world bark
  leaves_type: ref → world leaves
  tree_max_age: int
  tree_max_height: float
  trunk_max_thickness: float
  canopy:
    canopy_shape: enum
    canopy_max_area: float
  reproduction: list[FloraReproduction]
  # + FloraClimateSuitability (B)
```

```text
# --- размножение: абстракция (не только плоды) ---
FloraReproduction =
  | FruitReproduction
  | …                               # later: spores, vegetative, cuttings, …

FruitReproduction:
  kind: "fruit"
  fruits: list[FruitSpec]

FruitSpec:
  system_fruit: str
  display_name: str
  seeds: SeedsSpec

SeedsSpec:
  system_seed: str
  display_name: str
```

| Поле | Смысл |
|---|---|
| `glossary_ref` | лор вида → `lore_registry`; kind-level = `flora_tree` |
| `wood_type` / `bark_type` / `leaves_type` | ссылки на world_ref |
| `tree_max_*` / `trunk_max_*` / `canopy_max_area` | потолки вида; инстанс ≤ max |
| `canopy_shape` | силуэт кроны |
| `reproduction[]` | sum type; сейчас `FruitReproduction` |

**Инвариант reproduction:** новый способ = новый variant + handler; не плоское `seeds` на типе.  
Пустой `reproduction[]` допустим.  
`reproduction` — на tree/bush/plant/crops/grass (где уместно).

**Единицы:** SoT = **метры** (SI). Display imperial — только UI/LLM.  
1 cell = 1 м → `height_cells = round(height_m)`.

### `tree` instance — init при `detailed_bake`

Создаётся при detailed/full materialize (не light_bake type ref).  
Возраст → размер ствола/высоты/кроны через **абстракцию развития** (§ Flora development) — тот же путь, что фоновый цикл роста/смерти.

```text
TreeInstance:                       # chunk flora / location_objects
  system_tree: ref → tree_type
  tree_age: int                     # rnd / policy; далее evolves via development tick
  tree_height_m: float              # derived (development.apply)
  tree_height_cells: int
  trunk_thickness: float
  trunk_area: float
  tree_weight: float
  cells_span: int
  canopy:
    canopy_shape: from type
    canopy_area: float
  vitality / phase?: from development state
```

**light_bake:** на cell только `system_tree` (type ref).  
**detailed_bake:** `FloraDevelopment.materialize_instance(type, seed)` → age + derived sizes.  
**Runtime:** фоновый цикл зовёт те же `tick` / `grow` / `die` (не дублировать формулы в bake vs sim).

---

## Flora development — абстракция роста / смерти (утверждается)

Фоновый цикл **роста и смерти** переиспользует **один** контракт развития для tree/bush/plant/crops (и later variants).  
Bake init и runtime tick — **не** две разные формулы.

### Контракт (engine protocol)

```text
FloraDevelopment          # абстракция; impl per flora kind / strategy
  materialize_instance(type_entry, seed, context) → FloraInstance
      # detailed_bake / first place: age sample + apply morphology

  tick(instance, dt, context) → DevelopmentDelta | None
      # фоновый цикл: рост, старение, смерть, regeneration hooks

  grow(instance, dt, context) → morphology patch
      # увеличить age / размеры в пределах type max

  age_phase(instance, type_entry) → phase   # seedling|mature|senescent|…

  should_die(instance, type_entry, context) → bool
  die(instance, context) → DeathResult
      # remove / snag / seed drop via FloraReproduction handlers

  apply_morphology(instance, type_entry) → void
      # age_frac → height, trunk, canopy, weight, cells_span
      # ЕДИНЫЙ SoT размеров (bake + tick)
```

| Метод | Кто зовёт | Зачем абстрактный |
|---|---|---|
| `materialize_instance` | detailed_bake, `apply_flora_cell` | один init path |
| `tick` / `grow` | background growth/death cycle | переиспользование в sim |
| `apply_morphology` | bake + tick | нет расхождения формул |
| `should_die` / `die` | background cycle | death + hooks размножения |
| `age_phase` | narration / rules | фазы без хардкода в callers |

**Запрещено:** копипаста `age_frac → trunk` в bake отдельно от runtime; caller сам считает morphologiy мимо `apply_morphology`.

### Стратегии развития (sum type / pluggable)

```text
FloraDevelopmentStrategy =
  | DefaultAgeMorphologyDevelopment   # age_frac^p → size (ниже)
  | …                                 # later: seasonal flush, drought stress, …
```

Tree/bush могут делить `DefaultAgeMorphologyDevelopment`; plant/crops — свой strategy с тем же protocol.

### Morphology от возраста (Default strategy SoT)

```text
age_frac = clamp(tree_age / tree_max_age, 0, 1)

tree_height_m     = tree_max_height     * age_frac ^ p_height
trunk_thickness   = trunk_max_thickness * age_frac ^ p_trunk
canopy_area       = canopy_max_area     * age_frac ^ p_canopy

trunk_area   = π * (trunk_thickness/2)²
tree_weight  = k_trunk*trunk_area + k_canopy*canopy_area
cells_span   = max(1, ceil(canopy_area))
tree_height_cells = max(1, round(tree_height_m))   # 1 cell = 1 m
```

`p_*` — knobs на flora development policy (DefaultOnWire).

### Фоновый цикл (caller, не generator)

```text
BackgroundFloraCycle (application / sim — не FloraGenerator pure bake)
  for instances in active/near chunks (LOD policy):
    delta = development.tick(instance, dt, context)
    apply delta → chunk flora / location_objects
    if die → reproduction handlers (FruitReproduction → seeds, …)
```

| Слой | Роль |
|---|---|
| **FloraDevelopment** | abstract methods; pure morphology + death predicates |
| **BackgroundFloraCycle** | оркестрация tick по LOD / schedule |
| **FloraGenerator** | placement bulk/per-cell; зовёт `materialize_instance`, не owns death loop |
| **FloraReproduction** | при `die` / mature fruiting — отдельные handlers |

Инварианты:

| # | Правило |
|---|---|
| D1 | Рост/смерть — через `FloraDevelopment`, не ad-hoc в contributor |
| D2 | Bake init и background tick используют **`apply_morphology`** |
| D3 | Новый режим развития = strategy/impl protocol, не ветка в cycle |
| D4 | Размножение при смерти/плодоношении — `FloraReproduction`, не внутри morphologiy |
| D5 | Cycle уважает LOD (near/full instances; light type refs не тикают как objects) |

### Прочие registry — declare + instance (по аналогии с tree; без ствола/кроны)

Тот же паттерн: **N+1 тип** (max + materials + `reproduction` + suitability) → **instance** при detailed_bake через `FloraDevelopment` (age → размеры).  
Нет `trunk_*` / `canopy_*`.

#### `bush_type` — `world.bush_registry`

```text
BushTypeEntry:
  system_bush: str
  display_name: str
  glossary_ref: str | null
  flora_kind: "bush"
  wood_type?: ref → material
  bark_type?: ref → world bark
  leaves_type: ref → world leaves
  thorn_type?: ref → world thorns
  bush_max_age: int
  bush_max_height: float
  bush_max_volume: float
  reproduction: list[FloraReproduction]
  # + FloraClimateSuitability (B)

BushInstance:
  system_bush: ref → bush_type
  bush_age: int
  bush_height_m / bush_height_cells: derived
  bush_volume: float               # ≤ max; from age_frac
  bush_weight: float               # k_bush * volume^(2/3)
  cells_span: int                  # from weight / footprint
  vitality / phase?: from development
```

Morphology (Default strategy):

```text
age_frac = bush_age / bush_max_age
bush_height_m = bush_max_height * age_frac ^ p_height
bush_volume   = bush_max_volume * age_frac ^ p_volume
bush_weight   = k_bush * bush_volume^(2/3)
cells_span    = max(1, ceil(bush_weight))   # или ceil(footprint from weight)
```

#### `plant_type` — `world.plant_registry`

```text
PlantTypeEntry:
  system_plant: str
  display_name: str
  glossary_ref: str | null
  flora_kind: "plant"
  leaves_type?: ref → world leaves
  plant_max_age: int
  plant_max_volume: float
  reproduction: list[FloraReproduction]
  # + FloraClimateSuitability (B)

PlantInstance:
  system_plant: ref → plant_type
  plant_age: int
  plant_volume: float
  plant_weight: float                # k_plant * volume^(2/3)
  cells_span: int
  vitality / phase?: from development
```

```text
age_frac = plant_age / plant_max_age
plant_volume = plant_max_volume * age_frac ^ p_volume
plant_weight = k_plant * plant_volume^(2/3)
```

#### `crops_type` — `world.crops_registry` (земледелие)

Тот же каркас, что plant; **не** wild forest mix (FL4).

```text
CropsTypeEntry:
  system_crop: str
  display_name: str
  glossary_ref: str | null
  flora_kind: "crops"
  leaves_type?: ref → world leaves
  crop_max_age: int
  crop_max_volume: float
  reproduction: list[FloraReproduction]
  # + FloraClimateSuitability (B)

CropsInstance:
  system_crop: ref → crops_type
  crop_age: int
  crop_volume: float
  crop_weight: float
  cells_span: int
  vitality / phase?: from development
```

Morphology — как plant (`p_volume`, `k_crops`).

#### Сводка vs tree

| | tree | bush | plant | crops | grass |
|---|---|---|---|---|---|
| `flora_kind` (engine) | `tree` | `bush` | `plant` | `crops` | `grass` |
| lore kind keys (optional) | `flora_tree` | `flora_bush` | `flora_plant` | `flora_crops` | `flora_grass` |
| entry `glossary_ref` | да | да | да | да | да |
| wood / bark | wood + bark | optional | — | — | — |
| leaves | да | да | optional | optional | optional |
| thorns | — | optional | — | — | — |
| height max | да | да | — | — | — |
| volume max | через canopy/trunk | да | да | да | — |
| trunk / canopy | да | — | — | — | — |
| coverage on soil | — | — | — | — | **да** |
| `reproduction[]` | да | да | да | да | optional |
| suitability B | да | да | да | да | да |
| Development | да | да | да | да | coverage/phase later |

#### `grass_type` — `world.grass_registry`

N+1 вид травы; на клетке — **покрытие**, не ствол/крона.

```text
GrassTypeEntry:
  system_grass: str
  display_name: str
  glossary_ref: str | null
  flora_kind: "grass"
  leaves_type?: ref → world leaves
  grass_max_coverage: float        # 0..1 потолок покрытия вида
  # optional: height_cm max for display
  reproduction: list[FloraReproduction]  # optional (семена трав и т.п.)
  # + FloraClimateSuitability (B)
  # только на terrain soil

GrassCellState:                    # не TreeInstance; coverage на cell
  system_grass: ref → grass_type
  coverage: float                  # ≤ grass_max_coverage; light = type ref + optional coverage later
```

**light_bake:** `system_grass` = type ref.  
**full/detailed:** coverage на cell (и development coverage later, если понадобится).

### Climate suitability (вариант B) — утверждено

Shared POJO на все flora registries:

```text
FloraClimateSuitability
  rainfall_min / rainfall_max: int | None
  temperature_min / temperature_max: int | None
  elevation_z_min / elevation_z_max: int | None
  climate_zones: list[str] | None    # optional extra gate
```

Eligible = profile клетки (`base_rainfall`, `base_temperature`, elev) ∈ диапазонам; `None` = нет ограничения.  
`climate_zones`, если задан — gate по зоне.

### FloraSuitabilityIndex (утверждено 2026-07-17)

**Назначение:** один shared lookup для autoresolve леса и FloraGenerator — без повторного скана реестра и без дубля фильтра в landcover/forest contributor.

```text
build(world.*_registry) → FloraSuitabilityIndex
  # один раз на bake (или до смены registry / climate scalars)
  # вход: FloraClimateSuitability ranges на каждом entry

query(climate) → eligible[FloraKind]   # climate = zone profile или cell sample
  # ключ кэша ответа: обычно system_climate_zone / (rainfall, temp[, elev])
  # дискретные корзины temp/rain — optional ускорение; SoT остаётся ranges
```

| Правило | |
|---|---|
| SoT видов | только `world.*_registry` + `FloraClimateSuitability` |
| Consumers | только `index.query(...)` / FloraGenerator; **запрещён** локальный скан + свой rainfall gate по видам |
| Scope кэша | bake / world revision — не вечный process-global без инвалидации |
| Landcover порог | `terrain_masks.default_forests.forest_min_rainfall` = «мир **хочет** класс forest» — **не** замена suitability |

#### Forest birth = пересечение двух правил мира

| Слой | Вопрос | Источник |
|---|---|---|
| **A — landcover / masks** | Кандидат на `system_terrain=forest`? | `forest_min_rainfall` (+ enable / declare region) |
| **B — flora** | Есть ли eligible **trees** (и understory по policy)? | `FloraSuitabilityIndex.query` ∩ `tree_registry` |

```text
candidate_forest = landcover gate (A)
eligible_trees   = index.query(climate).trees     # (B)
paint forest     = candidate_forest ∧ eligible_trees ≠ ∅
```

| Исход | Маска | Flora |
|---|---|---|
| A∧B | `forest` + type refs | mix / dominant refs |
| A, B=∅ | **не** `forest` → fallback plains / ниже по rank | без tree refs; **warn** в generation log (master: лес разрешён, видов нет) |
| ¬A, B≠∅ | не forest (луг/редко tree на plains — по plains policy) | plains layers |
| ¬A∧¬B | plains / фон | пусто / grass-only если eligible |

**Запрещено:** лес без деревьев; подстановка builtin-вида; игнор suitability при прошедшем A.

**Stub сейчас:** light bake красит forest только по A (flora index ещё нет) — tech debt до FloraGenerator; target = A∧B.

---

## FloraGenerator (контракт)

```text
FloraGenerateContext
  climate: zone / rainfall / temp / elev
  registries: world flora roots
  layers: which registries to use   # e.g. forest → tree+bush+grass+plant; meadow → grass+plant
  occupancy_policy: caps / noise knobs
  region / cells: where to place
  seed

FloraLayout
  mixes: tree_mix, bush_mix, …      # weighted eligible entries
  cells: map → FloraCellOccupancy   # full/L2; light may omit per-cell
```

Pure: только данные. Persist / paint — caller.

---

## Occupancy — гибрид volume weight (утверждено 2026-07-17)

### Что значит «гибрид»

Не один источник формул, а **склейка двух практик** в одном SoT:

| Источник | Что берём | Чего не берём |
|---|---|---|
| **Лесная allometry** (FAO, basal area, crown) | как считать **вес** особи из ствола / кроны / объёма | полный species-specific FAO bake, рост во времени (FON sim) |
| **Game / PCG vegetation** (слои, density, ZOI, shade) | **слои** canopy→understory→ground, bulk density/noise, Zone of Influence на несколько клеток, shade | только «1 tree = 1 cell» без веса |

```text
гибрид =
  weight(entry)     ← allometry-lite (BA + canopy + V^(2/3))
  + place(chunk|cell) ← PCG layers + capacity + ZOI + noise
```

Итог: лимит на клетку(и) = **остаток capacity − сумма весов**, а не слепой счётчик «N кустов».  
Safety caps на policy — optional верхняя граница, не замена веса.

### Формулы веса (SoT draft; knobs `k_*` — DefaultOnWire на flora occupancy policy)

Единицы: клетка **1×1 м**; weight ∈ ℝ⁺ (доля capacity).

```text
# --- Tree (ствол + крона / ZOI) ---
trunk_radius_m = trunk_thickness / 2
trunk_area     = π * trunk_radius_m²                    # basal area proxy
canopy_area    = k_canopy_area * canopy_volume^(2/3)    # объём → площадь (self-similar)
# optional override: если на entry задан canopy_radius → canopy_area = π * r²

weight_tree = k_trunk * trunk_area + k_canopy * canopy_area
cells_span  = max(1, ceil(canopy_area))                 # multi-cell claim кроны
# stem volume (справочно / later biomass; не обязателен для capacity):
#   V_stem ≈ 0.42 * trunk_area * height_z               # forestry rule-of-thumb

# --- Bush / plant / crops (объём → footprint) ---
weight_bush  = k_bush  * volume^(2/3)
weight_plant = k_plant * volume^(2/3)
weight_crops = k_crops * volume^(2/3)

# --- Grass (не штучный объём) ---
weight_grass = coverage ∈ [0, 1]                        # только на soil
```

\(V^{2/3}\): стандартный переход «объём → характерная площадь» ( alike allometric scaling); стабильнее сырого volume как weight.

### Capacity клетки и слои

Слои **независимы** по budget (как PCG layers), с shade-коррекцией understory:

```text
cap_tree  = 1.0          # сумма weight_tree (вклад ствола/ZOI share) на клетке
cap_bush  = B            # policy default (напр. 1.0–2.0)
cap_plant = P
cap_grass = 1.0          # coverage

# под кроной (shade; ecology: understory ↑ в прогалинах):
canopy_cover(cell) ∈ [0,1]   # доля перекрытия кронами
cap_bush'  = cap_bush  * shade_bush(canopy_cover)    # ниже под плотной кроной
cap_grass' = cap_grass * shade_grass(canopy_cover)
# в прогалине canopy_cover→0 → caps ближе к полным (LAI compensation)

remaining(layer) -= weight;  reject / skip если remaining < weight
```

Крупное дерево: `weight_tree` / `canopy_area` распределяется по `cells_span` (ZOI); ствол якорится в одной клетке.

### Два API FloraGenerator

| API | Назначение | Типичный caller |
|---|---|---|
| **`apply_flora_chunk`** (bulk) | веса + noise/mix на **chunk** → occupancy → вклад в маску | forest / plains / wilderness full_bake |
| **`apply_flora_cell`** (per-cell) | точечно поставить/заменить flora с проверкой веса | города, парки, дворы |

```text
apply_flora_chunk(chunk|region, context) → FloraLayout
  # noise / canopy_noise решает «ставить ли»; weight — «влезает ли»

apply_flora_cell(cell|cells, placement, context) → FloraCellOccupancy
  # тот же remaining capacity; explicit entry/mix
```

Оба пути: один `weight(entry)`, одни registries ∩ climate.  
Per-cell не обходит suitability (кроме явного master override later).

### Связь с mask / bake

```text
bulk:  apply_flora_chunk → occupancy → forest/plains paint / objects
per-cell: settlement flora → apply_flora_cell (mask paint optional)
```

`canopy_noise` / `full_cell_side` — knobs **bulk** (wilderness). Город — чаще **per-cell**.

### Инварианты размещения

| # | Правило |
|---|---|
| O1 | Лимит = f(volume weight, capacity), не слепой count |
| O2 | Tree footprint может spanning несколько клеток (крона / ZOI) |
| O3 | Grass = coverage на **soil**, отдельно от volume-weights штук |
| O4 | Bulk и per-cell — один SoT веса |
| O5 | Размножение = `FloraReproduction` sum type; `FruitReproduction` → `FruitSpec.seeds`; новые способы = новый variant |
| O6 | Гибрид: allometry-lite для weight + PCG layers/ZOI/shade для place |
| O7 | Не FON growth sim и не полный FAO species table на bake path |

---

## Consumers

### Порядок в light_bake

```text
relief → climate → landcover → flora → mountain → …
```

| Правило | |
|---|---|
| Flora **после** climate | type refs только из `FloraSuitabilityIndex.query` / climate cell |
| Flora **после** landcover | знает forest/plains context (какие layers); forest paint только если A∧B |
| Запрещено | flora до climate; свой скан registry в contributor мимо index |

`FloraGenerator` на light path: `index.query` → dominant type ref на слой → писать на cell; **не** ставить инстансы.  
Forest autoresolve / landcover: тот же index для gate B (empty trees → нет `forest`).

| Режим | Terrain mask | Flora storage |
|---|---|---|
| **light_bake** | `system_terrain=forest` | **per cell:** ссылки на типы (`system_tree`, `system_bush`, `system_grass`, `system_plant`, …) — ключи `world.*_registry`, **не** инстансы, не volume/objects |
| **full_bake** | — | chunk flora layer: weight occupancy, noise tree/empty, optional promote → `location_objects` |

```text
# light cell wire (целевой; имена POJO — при sync WorldMapCellWire)
system_tree:  str | None   # → tree_registry
system_bush:  str | None   # → bush_registry
system_grass: str | None   # → grass_registry
system_plant: str | None   # → plant_registry
# crops — обычно не на wild forest light cell
```

Один dominant type ref на слой на light cell (не полный mix list на cell).  
Региональный `tree_mix` может жить на Spec для bake planning; **persist L0** = type refs per cell.

### Другие контексты (target)

| Context | Layers | Notes |
|---|---|---|
| Plains / meadow | grass, plant | без tree (или редко) |
| Settlement park | tree, bush, plant, grass | другие caps |
| Farmland | crops | agriculture |
| Mountain `FORESTED` | tree (+ understory) | после mountain SideFill |

---

## Хранение (LOD)

| Слой | Что храним | Не храним |
|---|---|---|
| **light_bake cell** | type refs: `system_tree` / `system_bush` / `system_grass` / `system_plant` (+ `system_terrain`) | инстансы, volume weight, seeds/fruit objects |
| **full / L2 chunk flora layer** | occupancy по weight, sparse trees, grass coverage | — |
| **`location_objects`** | interactive / city / promote near | весь wilderness flora |

---

## Инварианты

| # | Правило |
|---|---|
| FL1 | Flora — **отдельный** generator/domain; не зарыт только в forest contributor |
| FL2 | Виды — только `world.*_registry`, не литералы |
| FL2b | **`FloraKind` — engine StrEnum в `dataModel/flora/enums/`**; N+1 = виды; wire = `StrictEnumOnWire`; не glossary/имя/литералы в generators |
| FL3 | Eligible = registry ∩ `FloraClimateSuitability` |
| FL3b | **`FloraSuitabilityIndex`**: build из registries once/bake; autoresolve + FloraGenerator только через `query`; запрещён дубль фильтра в landcover |
| FL3c | **Forest paint = A∧B**: landcover `forest_min_rainfall` (A) ∧ eligible trees ≠ ∅ (B); B=∅ → не `forest`, fallback plains, warn log; без phantom canopy / builtin tree |
| FL4 | `crops_registry` ⊥ wild forest mix |
| FL5 | Consumers оркестрируют; generator не пишет `system_terrain` |
| FL6 | light_bake: **type refs per cell** (не инстансы); full_bake: chunk weight/occupancy |
| FL6b | light_bake порядок: **climate → landcover → flora**; suitability check обязателен |
| FL7 | Tree: weight/ZOI может multi-cell; иначе budget по remaining capacity |
| FL8 | Bulk `apply_flora_chunk` + per-cell `apply_flora_cell` — два API, один weight SoT |
| FL10 | Развитие = `FloraDevelopment` (abstract); bake + background cycle переиспользуют methods; morphologiy SoT один |

---

## Status / gate (2026-07-17)

**Flora domain architecture зафиксирована в этом ТЗ**, но **имплементация отложена**.

| Слой | Пока |
|---|---|
| `docs/tz_flora.md` | SoT решений (Kind, registries, occupancy, LOD…) — не выкидывать |
| `dataModel/flora/` | **не** делать полный каталог сейчас |
| `FloraGenerator` / Development / Reproduction | **stub** или отсутствующий call site |
| light bake forest | footprint + `system_terrain=forest` как сейчас; **без** полной flora materialize |
| Возврат | после стабилизации **map / mountain / terrain_masks** engine |

Consumers карты **не** блокируются на flora stub: сейчас forest mask → paint по gate A only.  
**Норматив target (уже в инвариантах):** A∧B + `FloraSuitabilityIndex` — см. FL3b/FL3c; stub не отменяет правило.

---

## Open

- **DEFER:** полный FloraGenerator + dataModel flora registries — после map/mountain
- Numeric defaults `k_*`, shade, occupancy sync (`canopy_area`)
- `ForestSpec` / declare forests — в light bake / masks; flora mix — later
- Optional lore keys `flora_*` (не дискриминатор kind)

---

## История

| Дата | Изменение |
|---|---|
| 2026-07-17 | Домен flora вынесен из light bake; FloraGenerator multi-context; registries + suitability B; forest = consumer |
| 2026-07-17 | Entry fields tree/bush/plant/crops/grass; occupancy = volume weight + bulk chunk + per-cell API |
| 2026-07-17 | Гибрид уточнён: allometry-lite weight + PCG place; формулы BA / V^(2/3) / canopy ZOI / shade caps |
| 2026-07-17 | light_bake: per-cell **type refs** only (не Spec-only mix, не инстансы); full = chunk layer / objects |
| 2026-07-17 | light_bake: flora после climate (+ landcover); FL6b |
| 2026-07-17 | `tree_type` N+1 declare + `TreeInstance` detailed_bake (age→trunk/height/canopy); meters SoT, cells=м |
| 2026-07-17 | `FloraReproduction` sum type; `FloraDevelopment` abstract (materialize/tick/grow/die); background growth cycle |
| 2026-07-17 | bush/plant/crops declare+instance по аналогии с tree (volume/height, без trunk/canopy) |
| 2026-07-17 | **DEFER impl:** flora stub; SoT остаётся в TZ; фокус → map/mountain generator |
| 2026-07-17 | **FL3b/FL3c:** `FloraSuitabilityIndex` + forest birth = landcover gate ∧ eligible trees; empty → no forest paint |
