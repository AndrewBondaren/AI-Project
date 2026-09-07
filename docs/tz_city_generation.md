# ТЗ: Генератор города

**Обновлено:** 2026-09-07 **§9.3** `min_adjacent_cells`; **LOC-T-2** ранг размера (`small`…) ≠ морфология, footprint из контекста; 2026-09-06 **detailed_bake** консьюмер C11 (`generate-settlement`); **§8** topology на `full_bake`; **§1.2.1** subject packing; 2026-09-05 **§1.1 / §1.2** морфология vs специализация; районы `district_type` + `district_subtype`; приоритет списка на городе → специализация; seed чертежа здания = мир+город+клетка footprint (§9.6); 2026-09-04 **CITY-T-2**; 2026-09-03 **CITY-T-1**; **C29** город на шве pack.

**Связанные документы:**

| Документ | Роль |
|---|---|
| [tz_assembler_hierarchy.md](./tz_assembler_hierarchy.md) | Stack Settlement → District → Area → Structure |
| [.cursor/plans/settlement-assembler.md](../.cursor/plans/settlement-assembler.md) | Фазы A–H impl, acceptance |
| [.cursor/plans/city-three-axes-transition.md](../.cursor/plans/city-three-axes-transition.md) | Три оси §1.1 слои A–F (сделано в коде) |
| [.cursor/plans/settlement-specialization-districts.md](../.cursor/plans/settlement-specialization-districts.md) | §1.2 CITY-T-2d: специализация, `district_subtype`, приоритет районов |
| [.cursor/plans/city-t-4-planner-debt.md](../.cursor/plans/city-t-4-planner-debt.md) | CITY-T-4 планировщик после 2d — **сделано** (`/impl-city-t-4`) |
| [tz_structure_connections.md](./tz_structure_connections.md) | Дороги settlement/district (§5) |
| [tz_terrain_relief.md](./tz_terrain_relief.md) | **C29:** город на техническом шве pack — норма; layout не клип по тайлу |
| [tz_world_pack_storage.md](./tz_world_pack_storage.md) | WP-19; topology после `full_bake`; **detailed_bake** = pack локации (консьюмер L2 + C11; не алгоритм C22) |
| [tz_settlement_outdoor.md](./tz_settlement_outdoor.md) | **SoT** persist/оркестрация outdoor на pack. **C23** topology. Не дублировать сюда |
| [tz_locations.md](./tz_locations.md) | Дерево NL; морфология `city`/`village` ≠ ранг размера **LOC-T-2** ≠ специализация; subtype района; SoT осей — **§1.1–§1.2 здесь** |
| [tz_building_generator.md](./tz_building_generator.md) | Library: `structure_type` vs `system_name` чертежа |
| [tz_generator_technical_debt.md](./tz_generator_technical_debt.md) | NC/MR smells; **CITY-T-1** контур; **CITY-T-2** пул/uid (**2d** `partial`, **2b** open); **CITY-T-4** планировщик **resolved** |
| [tz_city_generation_technical_debt.md](./tz_city_generation_technical_debt.md) | **CITY-T-5** после C23: dual persist, хардкоды, смешение слоёв. Не SoT §8 |

### Статус реализации (код vs это ТЗ)

| Блок TZ | Код | Статус |
|---|---|---|
| Фаза 2 lazy layout | `SettlementGeneratorService` → `SettlementAssembler` | ✅ фазы A–F plan |
| Фаза 3 lazy interior | `StructureGeneratorService` (+ area cache) | ✅ |
| Engine hook | `lazy_settlement` node | ✅ |
| §1.1–§1.2 оси + специализация + приоритет районов | 3 прохода, registry ролей, subjects N+1 | ✅ path 3; path 2 recreate DB |
| §9 district templates | `planner/placement.py`, `DistrictAssembler` | ✅ core |
| §8 Topology на `full_bake` | районы + city gates после L0 | ✅ spec locked; код C23 |
| Фаза 1 skeleton validate | import / world create | ⬜ partial |
| `dominant_material` post-assemble + DAG → LLM | layout / DAG | ✅ resolver; ⬜ DAG wire |
| Phase G organic footprint | `planner/footprint.py` v1 square | ⬜ v2 |
| Persist layout → connections + building `NamedLocation` в БД | `layoutCells` → map_cells only | ⬜ SoT: [tz_settlement_outdoor.md](./tz_settlement_outdoor.md); §11.5 generate scopes |
| `world_generation.init_mode` (`config.toml` + API) | — | ⬜ spec ✅ §11 |

Шапка таблицы **отстаёт от кода packing/outdoor** (C22 pass1→рамка→pass2; debug orchestrator ≠ только map_cells). Контур import/SQL скелета, dual persist, эвристика стен, DAG→LLM: **[CITY-T-1](./tz_generator_technical_debt.md#city-t-1--контур-вокруг-city-generate)**. Три оси (§1.1) vs packing fill: **[CITY-T-2](./tz_generator_technical_debt.md#city-t-2--пул-шаблонов-мира--packing)**. Швы после C23 (legacy persist, reuse в DAG, хардкоды): **[CITY-T-5](./tz_city_generation_technical_debt.md)**. Не путать с open §10 (footprint v2, cells барьера района).

**Имена в коде (не путать с legacy в других TZ):**

| Legacy в старых черновиках | Фактический класс |
|---|---|
| `CityGeneratorService` | `SettlementGeneratorService` / `SettlementAssembler` |
| `BuildingGeneratorService` | `StructureGeneratorService` (см. [tz_building_generator.md](./tz_building_generator.md)) |

---

## 1. Scope

Генератор города строит наполнение поселения — здания, улицы, районы — из скелета города.  
Скелет — **JSON import** на `NamedLocation`. На **`full_bake`** — топология районов и ворот (§8), без зданий. Застройка — шаг 2 **`detailed_bake`** (C11 поверх L2). Интерьеры — фаза 3.

`SettlementLayout` — мировые `(x,y)` / meter geometry, **не** клип по макро-тайлу. Поселение на техническом шве pack (ребро двух тайлов / грань чанка) — **валидный** кейс: один settlement, улицы и районы пересекают ребро. Не сдвигать город с шва и не плодить второй скелет «на соседнем тайле». Pack/grade: [`tz_terrain_relief.md`](./tz_terrain_relief.md) **C29**, [`tz_world_pack_storage.md`](./tz_world_pack_storage.md) WP-19.

### 1.1 Три оси: тип поселения, тип района, тип здания

Тип ≠ чертёж. Generate идёт сверху вниз. Не класть список `tavern_1` на город. Не выбирать район как случайный JSON из всей библиотеки зданий.

| Ось | Тип (семантика, N+1) | Чертёж (экземпляр в реестре/библиотеке мира) | Что задаёт тип | Что задаёт чертёж |
|---|---|---|---|---|
| **1. Поселение** | **морфология** `system_location_subtype`: `city`, `village`, `dungeon`, `underground_city`, … **плюс** **специализация** на шаблоне этого поселения (§1.2) | этот Ironhold (`location_uid`) | морфология — каркас районов (civic/жильё/…); специализация — районы и обязательные `structure_type` под функцию (шахта, мельница, театр) | не рандомится |
| **2. Район** | `district_type` (ткань квартала): канон `civic`, `commercial`, `residential`, `industrial`, `port`, `agricultural` (+ N+1, напр. `military`) **и** `district_subtype` (функция квартала, те же ключи, что специализация поселения) | строка `district_template_registry` (`civic_center`, `mining_quarter`) | какие `structure_type` можно в квартале; зона в сетке; улицы/плотность | ничья среди чертежей **того же** `district_type` **и** `district_subtype` (omit subtype на чертеже = только неспециализированный слот того же `district_type`) |
| **3. Здание** | `structure_type` библиотеки: `tavern`, `house`, `warehouse`, `town_hall`, `mine`, `plaza`, … ([tz_building_generator.md](./tz_building_generator.md) §2) | `system_name` / uid в `building_templates` (`tavern_1`, `iron_mine_1`) | назначение участка | rng среди чертежей **этого** типа, допущенных районом и тиром. Материал/культура (железо vs пшеница) режет чертёж, не плодит новый subtype поселения |

`system_settlement_size` (`small` / `medium` / `large`) — **относительный ранг в контексте морфологии**, не вид поселения и не специализация. Пара `village` + `small` корректна. Пара `village` + `village` (один токен на subtype и size) — ошибка дублирования, 422. Абсолютный footprint = `footprint_by_size[subtype][size]` ([`tz_locations.md`](./tz_locations.md) **LOC-T-2**). Инвариант: малый город > большая деревня. Код до impl: `system_city_size` и токены `hamlet`…`megalopolis`.

Import: `system_location_type` можно **не** писать, если `system_location_subtype` уникален в `location_type_registry` (канон: `city` → `settlement`). Неуникальные (`mountain`, `island`) без явного type — 422. SoT: [`tz_locations.md`](./tz_locations.md) **LOC-T-1**. Не выводить type из ранга размера.

Subtype локации `building` в дереве NL (`residential` / `commercial` / …) — иерархия SQL, **не** `district_type`, **не** `district_subtype` и **не** `structure_type` библиотеки.

**Клетка generate** — глобальная ячейка **footprint города** (§9.6): индекс `(cell_x, cell_y)` от пина поселения, сторона `map_cell_size_m`. То же число метров, что у pack макротайла, **другой индекс**. Не `tile_gx/gy`. Город на шве двух тайлов — один settlement (C29).

### 1.2 Шаблон поселения: морфология, специализация, приоритет районов

Два разных ключа. Не класть «шахтёрский город» в `system_location_subtype` вместо `city`.

| Ключ | Где | Что это | Канон |
|---|---|---|---|
| Морфология | `named_locations.system_location_subtype` → `location_type_registry` тип `settlement` | город / село / данж / подземный город: глиф L0, каркас `district_type` | `city`, `village`, `dungeon`, `underground_city` |
| Специализация | шаблон **этого** поселения (`CitySkeleton` / import JSON), список | чем живёт место; несколько сразу («добыча + обработка + производство») | `extract`, `process`, `manufacture`, `culture`, `farm`, `livestock` (+ N+1) |
| Районы на городе | тот же шаблон, список **типов** кварталов (§ ниже) | что мастер явно хочет в **этом** Ironhold | объекты `district_type` + optional `district_subtype` + optional pin `system_name` чертежа |

Реестр специализаций — `worlds.settlement_specialization_registry` (§4.1): ключ → какие районы (`district_type` + `district_subtype`) и какие обязательные `structure_type` тянуть. Geographic subtypes поля рецепта игнорируют.

**Первичны районы, указанные на самом поселении. Вторичны районы специализации.** Морфология — только добивка пустых слотов, не вытесняет список города.

Два прохода по сетке footprint, потом морфология:

1. Рассадить **все** записи `typical_districts` города: каждая берёт свободную клетку, чья зона лучше совпадает с её `district_type`. Нет клетки — warning, не подменять тип.
2. Оставшиеся клетки — union районов специализаций ∩ предпочтение зоны.
3. Ещё оставшиеся — typical морфологии `city`/`village`/… ∩ зона.

Пересечения зоны нет — клетка **скип**, не подставлять чужой `district_type` «с пола». Несколько ролей = объединение районов и `required_structure_types`, не «одна роль победила». C14: authored-дети города — скип generate, не этот рецепт.

Список на городе — **типы** (и optional subtype), не каталог `tavern_1`. Optional `system_name` — pin **чертежа района** из `district_template_registry`, не здания. Нет pin — чертёж того же `district_type`+`district_subtype` из реестра мира (seed §9.6).

На роли — **subjects** (N+1): какие руды, культуры, скот, изделия, домены. Строка `"extract"` = роль без subjects. `subjects` на инстансе — плоский список (`["iron_ore", "copper_ore"]`) **или** карта вид → токены (`{ "resource": ["iron_ore", "copper_ore"] }`). Для **extract** токены — ключи `worlds.resource_type_registry` (`system_resource`); вид добычи — ENUM-E `resource_kind` (`ore` / `stone` / `timber` / `liquid`). Для **farm** токены — ключи `worlds.crops_registry` (`system_crop`); вид культуры — ENUM-E `crop_kind` (`grain` / `vegetable` / `fruit` / `fiber` / `fodder`). Для **livestock** токены — ключи `worlds.livestock_registry` (`system_livestock`); предназначение — ENUM-E `livestock_kind` (`meat` / `dairy` / `fiber` / `draft` / `mount`). Яйца — yield вида, не kind. Постройка (птичник, хлев, конюшня) — N+1 `structure_type` / чертёж, не значение kind. Реестр ролей задаёт `subject_kind` (каталог: `resource` / `crop` / `livestock` / `product` / `domain` / …) и optional `subjects_to_structure_types`. Пустой subjects → `required_structure_types` роли (какие типы зданий). Известные subjects заменяют этот список. Неизвестный subject без mapping — как пустой для **типов зданий** (дефолт роли); сам токен не подменять (§1.2.1). Product / domain — каталоги ещё не wired.

#### 1.2.1 Subjects ↔ чертёж ↔ fallback

Матч **не** отдельная таблица «тип здания × ресурс». Мастер вешает его на **чертёж** библиотеки (`structure_type` + optional kind + optional `subjects`). Packing фильтрует пул того же `structure_type`.

**Именованный subject святой.** `subjects: ["mithril_ore"]` остаётся `mithril_ore`. Нет tagged-чертежа под этот ключ → чертёж того же kind (`resource_kind=ore`), иначе untagged. **Запрещено** подставлять канонический `iron_ore` или другой ключ мира. Токен не из реестра мира — warning, не RNG-замена.

**Пустой subject** (роль `"extract"` / `"farm"` / `"livestock"` без списка) — не дефолт `iron_ore` / `wheat` / `cow`:

1. Kind с роли и чертежа: extract+`mine` → `ore` (или `timber` у лесозаготовки и т.д.); farm → `crop_kind` чертежа / роли; livestock → `livestock_kind` если есть, иначе любой kind в реестре скота.
2. Пул = **только** каталог **этого мира** того же kind (`resource_type_registry` / `crops_registry` / `livestock_registry`). Не `material_registry` (`iron` — слиток).
3. Один ключ: rng той же базы, что чертёж здания (§9.6: `world_uid` + `location_uid` + клетка footprint), суффикс `_subjects` — не сдвигать поток `_buildings`.
4. Packing log (warning/info): какой ключ взяли и что это fallback, не tagged-чертёж мастера.
5. Пул kind пуст — warning, subject не выдумывать; сажать generic `structure_type`.

**Каталог мира vs dataModel** (только эти instance-каталоги: resource / crops / livestock):

| Колонка мира | Runtime |
|---|---|
| null / `[]` / ключ отсутствует | канон POJO (`iron_ore`, `wheat`, `cow`, …) — это и есть каталог |
| непустой список | **только** строки мира; канонические ключи, которых нет у мастера, **не** дописывать |

Не путать с overlay чертежей района / барьеров (T-29 canonical⊕world по id — другой класс реестра).

**Код:** packing tagged → kind → untagged; пустой subject — RNG из реестра мира + packing log (`SUBJECT_FALLBACK` / `SUBJECT_POOL_EMPTY`); named неизвестный — `SUBJECT_UNKNOWN`, токен не свопается. Instance-каталоги resource/crops/livestock без T-29 union.

Пример шаблона поселения:

```json
{
  "system_location_type": "settlement",
  "system_location_subtype": "city",
  "system_settlement_size": "medium",
  "system_settlement_specializations": [
    { "system_specialization": "extract", "subjects": { "resource": ["iron_ore", "copper_ore"] } },
    { "system_specialization": "process" }
  ],
  "typical_districts": [
    { "district_type": "port" },
    { "district_type": "civic" }
  ]
}
```

Слоты: сначала port/civic (как зона позволит), затем industrial+`extract` и industrial+`process` из реестра ролей, затем каркас `city` (commercial/residential/…). Обязательные здания: ратуша с морфологии `city` ∪ шахта/обогатительная с ролей.

**Код сейчас:** три прохода + specialization registry + subjects на слоте (`DistrictSlot.subject_tags`). Rank размера и zone→types — POJO (`WorldCitySizeRegistry.rank`, `WorldDistrictZonePreference`). Cache и packing — один `pick_layout_names`. Subject fallback — §1.2.1. Path 2: recreate DB после колонки `district_zone_preference` в `0001`. Leftover — [CITY-T-2b](./tz_generator_technical_debt.md#city-t-2--пул-шаблонов-мира--packing) (SQL library uid). Планировщик **CITY-T-4** resolved.

Поток:

```
морфология + список районов на городе + специализации
  → приоритет 1→2→3: набор (district_type, district_subtype) + union required structure_type
     → клетка footprint: тип/подтип района по зоне ∩ текущий приоритет
        → чертёж района (pin города или registry того же type+subtype)
           → required: тип здания → чертёж из библиотеки (seed §9.6; материал режет чертёж)
           → fill: allowed structure_type → чертёж того же типа (seed)
```

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
| `system_settlement_size` | string | `NamedLocation` | ранг → `settlement_size_registry`; footprint — subtype × ранг (**LOC-T-2**). Код: `system_city_size` | ⬜ LOC-T-2 |
| `system_settlement_specializations` | string[] | JSON import, optional | Ключи §4.1. Пусто / omit — нет вторичного рецепта районов. Несколько = union. Не `system_location_subtype` | ⬜ §1.2 |
| `typical_districts` | object[] | JSON import, optional | Приоритет 1: `{ "district_type", "district_subtype"?, "system_name"? }`. Пусто — сразу приоритет 2–3 | ⬜ §1.2 |
| `dominant_material` | string | post-assemble | ref → `material_registry`; **не** import | ✅ `resolve_dominant_material` |
| `architectural_style` | string | JSON import | ref → `architectural_style_registry`; для LLM | ✅ read |
| `settlement_density` | string | JSON import | `sparse` / `medium` / `dense` | ✅ read (NC-9) |
| `frontage_type_order` | string[] | JSON import, optional | Иерархия `connection_type` для парадного (C22). Как `settlement_density`: import → `CitySkeleton`; SQL колонка — при persist скелета (`0001`). `null` = дефолт движка. Район может переопределить | ⬜ connections §5.1.3 |
| `structure_counts` | object | JSON import, optional | Городской дефолт копий: `{ "<system_name>": int }`. Резолв N — [connections](./tz_structure_connections.md) §5.1.3 «Число токенов» | ⬜ |
| `structure_priority` | object | JSON import, optional | Городской дефолт очереди fill: `{ "<system_name>": int }`. Резолв — [connections](./tz_structure_connections.md) §5.1.3 «Приоритет посадки» | ⬜ |
| `perimeter_barrier` | nullable `PerimeterBarrier` | optional | Инстанс барьера **поселения** (прямые footprint). Как `settlement_density`: import → `CitySkeleton`. Нет поля / `template` null — скип. Не барьер района. **`SettlementAssembler`** до generate района вычитает эти прямые (`footprint ∩ DistrictSlot`) из площади района | ⬜ |
| `state_uid` | string | `NamedLocation` | Политический контекст LLM | ✅ location; ⬜ в `CitySkeleton` |

**Что LLM получает из скелета:**
- `display_location_mood` → тон описания
- `economic_tier` → богатство ("ухоженные фасады" vs "облупившаяся штукатурка")
- `architectural_style` → визуальный язык для LLM; генератором не используется (см. [tz_architectural_style.md](tz_architectural_style.md))
- `system_settlement_size` → относительный масштаб (контекст = морфология; LOC-T-2)
- `system_settlement_specializations` / `typical_districts` → чем живёт город и какие кварталы мастер зафиксировал (когда поля появятся на скелете)

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

### 4.1 `worlds.settlement_specialization_registry`

Рецепт **роли**, не морфологии и не списка `tavern_1`. Мастер вешает ключи на шаблон поселения; generate тянет районы приоритетом 2 (§1.2).

```json
[
  {
    "system_specialization": "extract",
    "display_specialization": "Добыча",
    "subject_kind": "resource",
    "typical_districts": [
      { "district_type": "industrial", "district_subtype": "extract" }
    ],
    "required_structure_types": ["mine"]
  },
  {
    "system_specialization": "process",
    "display_specialization": "Обработка",
    "subject_kind": "product",
    "typical_districts": [
      { "district_type": "industrial", "district_subtype": "process" }
    ],
    "required_structure_types": ["mill", "smelter"]
  },
  {
    "system_specialization": "manufacture",
    "display_specialization": "Производство",
    "subject_kind": "product",
    "typical_districts": [
      { "district_type": "industrial", "district_subtype": "manufacture" }
    ],
    "required_structure_types": ["workshop"]
  },
  {
    "system_specialization": "culture",
    "display_specialization": "Культура",
    "subject_kind": "domain",
    "typical_districts": [
      { "district_type": "civic", "district_subtype": "culture" }
    ],
    "required_structure_types": ["temple", "theater"],
    "subjects_to_structure_types": {
      "religion": ["temple"],
      "knowledge": ["library"]
    }
  },
  {
    "system_specialization": "farm",
    "display_specialization": "Выращивание",
    "subject_kind": "crop",
    "typical_districts": [
      { "district_type": "agricultural", "district_subtype": "farm" }
    ],
    "required_structure_types": ["farm"]
  },
  {
    "system_specialization": "livestock",
    "display_specialization": "Скотоводство",
    "subject_kind": "livestock",
    "typical_districts": [
      { "district_type": "agricultural", "district_subtype": "livestock" }
    ],
    "required_structure_types": ["livestock"]
  }
]
```

`display_*` — из lore / это поле. Пустой typical на роли — роль не тянет районы (только `required_structure_types`, если заданы). `subject_kind` (строка или список) и `subjects` на инстансе — N+1; канон не закрывает список руд/культур/скота/изделий/доменов/материалов. Канон в таблице — builtin движка; мир overlay по `system_specialization`.

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

Occupancy-flood метровой матрицы в патчи **не** делать (outdoor **C7**).

Результат: все поселения имеют скелет. LLM может назвать город по import `display_name`.

### Фаза 1b — Topology на `full_bake` (§8)

После L0 pack: число и типы районов, входы между ними, `settlement_gate`. Не C22. **Код ✅** C23.

### Фаза 2 — Outdoor layout на `detailed_bake` (C11)

Порядок **`detailed_bake` `scope=location`:** (1) L2 terrain (2) поселение **поверх** земли — `materialize`. Debug `generate-settlement` / lazy (позже) — те же вызовы, не второй алгоритм.

- Если топология уже в SQL — **reuse** слотов и uid районов (§8), не второй rng типов
- `SettlementGeneratorService.generate_layout` → packing участков + внутренняя сетка (C22)
- После assemble: `SettlementLayout.dominant_material` — authoritative для LLM
- Эталон: pack city-structure + SQL здания — [tz_settlement_outdoor.md](./tz_settlement_outdoor.md) C11

**Точка входа packing:** `backend/app/application/worldData/generators/assemblers/settlementAssembler/`

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
- `footprint_by_size[subtype][system_settlement_size]` — множитель на `world.map_cell_size_m`; сторона footprint в метрах = множитель × `map_cell_size_m`. SoT таблица и инвариант village≺city: [`tz_locations.md`](./tz_locations.md) **LOC-T-2**. Код до impl: `city_size_registry[system_city_size].footprint_multiplier` (токены `hamlet`… смешаны с морфологией — **не** целевой контракт)
- `settlement_density` → плотность застройки
- `building_template_registry` — доступные шаблоны

**Канон множителей** — на subtype, не на ранге. Не копировать полную таблицу сюда (SoT — locations **LOC-T-2**). Omit ранга → `medium`.

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
вторичные улицы = перпендикулярные ответвления; количество зависит от ранга размера (в контексте морфологии)
кварталы = прямоугольные блоки между улицами
```

### 6.3 Заполнение кварталов

Единица посадки внутри района — **квартал рамки района** (модуль `block_size`: **50 / 80 / 120 клеток**), не квартал city-сетки §6.2. Не bin-pack по AABB всего района. Метры/имперские — display, не generate.

Порядок (`DistrictAssembler`, C22). Fill — [connections](./tz_structure_connections.md) §5.1.3 «Пайплайн посадки». `DistrictSlot` — `size_pct` ячейки (§9.6); packing слот не растит.

1. Площадь района и якоря — **`SettlementAssembler`** (не packing района). Сначала слот по `size_pct`. Если инстанс барьера **поселения** валиден — вычесть прямые footprint (`sides` + `width_cells` чертежа поселения) ∩ слот из площади района, чтобы слот не заходил на клетки поселения (клетки поселения — `SettlementLayout.barrier_cells`). Затем якоря: шаблон **этого** района (`density`; барьер **района** → прямые уже урезанного слота). Packing района прямые поселения не вычитает. Инстанс района: нет поля / `template` null — скип прямых района. Иначе **v1 packing** inner bbox = урезанный слот минус прямые района минус коридор. Клетки района TODO. Зоны трёх инстансов не пересекаются. Не забор участка, не стены здания.
2. **Коллекция оболочек** — cache кандидатов (`allowed_structure_types` ∩ тир, `required_structures`). Интерьер комнат — не этот скоуп.
3. **Проход 1 — бронь приоритетных** в решётке `block_size` внутреннего bbox (не через коридор якорей). Не пустая сетка кварталов до этого шага. SoT: [connections](./tz_structure_connections.md) §5.1.3 «Два прохода посадки».
4. **Рамка вокруг броней** — полосы той же решётки + пустые кварталы на земле без брони. Ещё не полотно сквозь дома.
5. **Проход 2 — остальная коллекция** в оставшиеся кварталы. Спан только пустые слоты. Влезло — вынуть, не вытеснять.
6. **Граф улиц** — главные по рамке, аллеи внутри модуля, не через клетки участков.
7. `StructureAreaAssembler` — слот уже стоит; только касающиеся отрезки.

Тип квартала на уровне **города** (`district_type` / `allowed_structure_types`) — какие назначения в районе. Куда складу vs дому внутри района при fill — не карта зон v1.

SoT деталей: [tz_structure_connections.md](./tz_structure_connections.md) §5.1.3–§5.1.4. Debug каждого шага — §5.1.3 «Debug packing»; политика sinks — [tz_logging.md](./tz_logging.md).

**TODO — переход кода (отдельный план, не эта сессия):**

- Рамка модулей `block_size` **после** брони прохода 1 (не пустая сетка до cache; не overlay сетки после всего packing).
- Packing: пайплайн §5.1.3; два прохода — «Два прохода посадки»; число копий; оболочка 90°; аллея из `connections`.
- Аллея между мелкими из `connections`, если сумма bbox + ширина влезает в шаг; иначе не выдумывать.
- Граф/rasterize после посадки; маска занятых клеток; слоту только касающиеся рёбра.
- Якоря `entry_nodes` — город, шаг `density` района, на **уже урезанном** слоте. Барьер **поселения**: `SettlementAssembler` вычитает прямые footprint ∩ слот из площади района **до** packing. Барьер **района** (§9.2): packing вычитает прямые района из этого слота; generate клеток TODO. Нет поля района / `template` null — скип прямых района. Зоны не пересекаются.
- Нитка `frontage` (склейка кусков одной линии); `plaza` — улицы равны.
- Debug packing на каждом шаге — connections §5.1.3 «Debug packing»; sink — [tz_logging.md](./tz_logging.md) `settlement` / `settlementAssembler`.
- Не в этом TODO: интерьер, DAG, schema `0002`.

Код сейчас: `buildingCache` → `areaSlots` AABB → `_plan_streets` на весь bbox.

### 6.4 Особые объекты

Civic-здания (ратуша, храм, рынок) — `required_structures` в district template; impl ✅ (`areaSlots`, Phase C/E). Размер места — footprint **этого** шаблона, не абстрактный лот. Число копий — [connections](./tz_structure_connections.md) §5.1.3 «Число токенов».

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

## 8. Topology на `full_bake` (locked)

**Не** четвёртый bake mode. **Не** L2 / mill. **Не** packing зданий. **Не** `SettlementContributor` (тот — pin-диск L0).

После успешного [`full_bake`](./tz_world_pack_storage.md) L0 (pack есть, surface footprint читается) — pass **`settlement_topology`** на все settlement-like NL (C6). `light_bake` этот pass **не** делает: соседние тайлы большого footprint могут отсутствовать. Если `full_bake` не было — **тот же** pass при первом packing / входе (§11.3), не второй алгоритм.

Склейка: [tz_settlement_outdoor.md](./tz_settlement_outdoor.md) **C23**. World-трассы: [tz_structure_connections.md](./tz_structure_connections.md) §5.1 `_plan_world_routes` — **после** ворот, не внутри packing.

Тот же planner, что assembler: `plan_district_slots` → `plan_settlement_entries` → `plan_city_street_grid`. Bake не дублирует алгоритм.

### Что фиксирует

| | |
|---|---|
| **Имена районов** | `display_name` чертежа района. Город — import `display_name`. Генератор **не** зовёт LLM. Overlay имён — DAG U13 **без** сдвига xy |
| **Размеры** | морфология × `system_settlement_size` → сторона footprint (**LOC-T-2**). N районов = клетки сетки ∩ рецепт §1.2. Второго счётчика «сколько кварталов» нет |
| **Типы** | `district_type` + `district_subtype` + чертёж района |
| **Входы** | пары `through_road` / `paired_exit` на гранях районов; `settlement_gate` на периметре footprint; коридоры **между** районами (`graph_level=city`) |

### Что не фиксирует

Packing участков, внутренняя сетка квартала (C22: бронь → рамка → pass2), здания, `l.{uid}.settlement.zst`, интерьеры, `graph_level=district` внутри квартала.

### Persist

SQL: NL районов (`system_location_type=district`, parent=settlement, C4/C5 uid из слота) + `connection_nodes` / `connection_edges` уровня city (ворота + стыки районов). Не occupancy-flood. Не pack city-structure.

### Skip / reuse

| Уже есть | Topology | Packing (C11) |
|---|---|---|
| Authored-дети не-район (таверна / square / gate у города) | **скип** (не этот рецепт) | скип generate |
| Районы + city gates с этого pass | идемпотентный skip | **reuse** слотов/uid, не второй rng типов |
| `l.{uid}.settlement.zst` + manifest + дети | skip | skip (C14) |

### Зачем

Мировые дороги садятся в `settlement_gate`, не в центр пина. `detailed_bake` / grade видят meter-rect района, не только диск footprint.

L0 restamp полотна новых world-рёбер на уже записанный `world_map` — leftover, не блокер этого pass.

**Код:** ✅ C23. CITY-T-1a: поля скелета на NL.

Отдельная UI-кнопка «Инициализировать мир» — не нужна: `full_bake` уже процесс. `init_mode` (§11) не подменяет этот контракт packing’ом всех городов.

**Не входит сюда и в `init_mode=full`:** интерьеры (фаза 3).

---

## 9. Шаблоны районов (`district_template_registry`)

> **Impl:** ✅ core — `planner/placement.py`, `planner/districts.py`, `DistrictAssembler`. См. settlement-assembler Phase A–C.

Район — **тип** (`district_type`) + **подтип** (`district_subtype`) плюс **чертёж** в `district_template_registry`. Сначала пара type/subtype по приоритету §1.2 и зоне клетки footprint (§9.6); `DistrictAssembler` получает уже выбранный чертёж. Не путать с `structure_type` библиотеки зданий.

Канон `district_subtype` = ключи специализации поселения (`extract`, `process`, `manufacture`, `culture`, `farm`, `livestock`, … N+1). То же значение — `named_locations.system_location_subtype` у NL района ([tz_locations.md](./tz_locations.md)). Omit/`null` на чертеже — неспециализированный квартал этой ткани (`industrial_quarter` без добычи).

### 9.1 Хранение

Аналогично `building_templates` — глобальная таблица шаблонов, не привязанная к конкретному миру.
Per-world реестр: `worlds.district_template_registry` (JSON-массив, как `building_template_registry`).

### 9.2 Схема шаблона района

| Поле | Тип | Обязательность | Описание |
|---|---|---|---|
| `system_name` | string | required | Уникальный ключ: `"port_district"`, `"merchant_quarter"` |
| `display_name` | string | required | Отображаемое название |
| `district_type` | string | required | Ткань квартала (§1.1): `"civic"`, `"commercial"`, `"residential"`, `"industrial"`, `"port"`, `"agricultural"`, … N+1 |
| `district_subtype` | string | optional | Функция квартала (§1.2): `"extract"`, `"process"`, `"manufacture"`, `"culture"`, `"farm"`, `"livestock"`, … N+1. Должен быть в `location_type_registry` тип `district`. `null` = без специализации |
| `placement_conditions` | array | optional | Условия появления района (см. 9.3). Пустой массив = всегда доступен |
| `max_per_city` | int | optional | Максимальное количество районов этого типа в одном городе. `null` = без ограничений |
| `size_pct` | object | optional | Диапазон размера района как доля глобальной ячейки: `{ "width": [0.3, 1.0], "depth": [0.3, 1.0] }`. `1.0` = вся ячейка |
| `allowed_structure_types` | string[] | optional | Допустимые **типы зданий** (`structure_type` библиотеки), не имена чертежей. `null` = без ограничений типа. **Код:** omit/`null` = каталог не берётся — **CITY-T-2a** |
| `economic_tier_range` | object | optional | `{ "min": "poor", "max": "exceptional" }` — диапазон тиров зданий в районе |
| `density` | string | optional | `"sparse"`, `"medium"`, `"dense"`. Переопределяет `city_skeleton.settlement_density` для этого района. **`SettlementAssembler`** ставит `entry_nodes` с `block_size` **этого** поля (нет → плотность города) |
| `frontage_type_order` | string[] | optional | Иерархия типов дорог для фасада (C22). `null` = список города, иначе дефолт движка. Пример: `["road","highway","alley"]` — входы со стороны `road` |
| `street_layout` | string | optional | Алгоритм раскладки улиц района (см. 9.5). `null` = наследует от города |
| `connections` | array | optional | Объявления дорог внутри района: тип, sidewalk, роль. Не объявленные — генератор определяет сам. Формат — см. 9.5 |
| `required_structures` | array | optional | Особые обязательные постройки (ратуша, храм, рынок) — см. 9.4. `count` — §5.1.3 «Число токенов»; очередь — §5.1.3 «Приоритет посадки» |
| `structure_counts` | object | optional | `{ "<system_name>": int }` — районный override копий. Резолв N — [connections](./tz_structure_connections.md) §5.1.3 «Число токенов» |
| `structure_priority` | object | optional | `{ "<system_name>": int }` — районный override очереди fill. Резолв — [connections](./tz_structure_connections.md) §5.1.3 «Приоритет посадки» |
| `perimeter_barrier` | nullable `PerimeterBarrier` | optional | Барьер **района** (прямые **уже урезанного** `DistrictSlot`). Тот же класс, другой инстанс, чем у поселения ([tz_locations.md](./tz_locations.md)). Omit/null / `template` null — скип. Поле + `template` — всегда, без roll. `sides` — прямые **слота**; нет ключа / `null` / `[]` → четыре прямые слота. **v1 packing:** inner bbox минус эти прямые внутрь. Клетки — `DistrictAssembler` (TODO). Список поселения не пишет; общая xy запрещена (вычет поселения раньше). |

Канон **специализированных** чертежей (builtin, overlay мира по `system_name`). Существующие `civic_center` / `industrial_quarter` / … без `district_subtype` — неспециализированная ткань (проход 3 морфологии). **Код:** этих строк в registry нет.

| `system_name` | `district_type` | `district_subtype` | Типичные `allowed_structure_types` |
|---|---|---|---|
| `mining_quarter` | `industrial` | `extract` | `mine`, `warehouse` |
| `processing_quarter` | `industrial` | `process` | `mill`, `smelter`, `warehouse` |
| `manufacture_quarter` | `industrial` | `manufacture` | `workshop`, `warehouse` |
| `cultural_quarter` | `civic` | `culture` | `temple`, `theater`, `plaza` |
| `farm_quarter` | `agricultural` | `farm` | `farm`, `mill` |
| `livestock_quarter` | `agricultural` | `livestock` | `livestock` |

### 9.3 Условия появления (`placement_conditions`)

Каждое условие — объект с полем `type`. `SettlementAssembler` проверяет все условия до размещения.
Все условия должны быть выполнены (AND-логика).

| `type` | Параметры | Описание |
|---|---|---|
| `adjacent_terrain` | `terrain_types: string[]`, `min_adjacent_cells: int` | На внешнем кольце **слота района** ≥ N соседних terrain-клеток с `system_terrain ∈ terrain_types`. Omit → 1. Порт: `["liquid_body"]` + `1`. Не длина берега, не связность водоёма (open ниже). |
| `min_settlement_size` | `size: string` | ранг → `settlement_size_registry`; поселение **этой морфологии** не меньше ранга. Не сравнивать `small` города с `large` деревни. «Только города» = subtype `city`, не size. Код/wire до impl: `min_city_size` + токены `town`/… |
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
    { "type": "adjacent_terrain", "terrain_types": ["liquid_body"], "min_adjacent_cells": 1 },
    { "type": "min_settlement_size", "size": "medium" }
  ],
  "allowed_structure_types": ["warehouse", "tavern", "shop", "guild", "plaza"],
  "density": "dense"
}
```

### 9.4 Обязательные особые постройки (`required_structures`)

**SoT (§1.2):** обязательные **типы зданий** = union морфологии, всех специализаций поселения и extras районного чертежа. Резолв: тип → чертёж из библиотеки мира того же `structure_type` (seed §9.6; материал/ресурс режет чертёж). Не список `tavern_1` на городе.

**Код / wire сейчас:** ключ `building_template` = `system_name` чертежа (`town_hall`), висит на шаблоне района — **CITY-T-2d**, пока нет рецепта на subtype.

```json
"required_structures": [
  { "building_template": "town_hall",  "count": 1, "position": "center" },
  { "building_template": "market",     "count": 1, "position": "any"    }
]
```

`count` — число токенов; default 1. Приоритет над `structure_counts` — [connections](./tz_structure_connections.md) §5.1.3 «Число токенов». Массив — проход 1 **до** рамки пустых кварталов; порядок массива = очередь среди required — §5.1.3 «Приоритет посадки». Не путать с `structure_priority` (желательный fill, не обязательность).

`position`:
- `"center"` — размещается ближе к геометрическому центру района. Два+ с `center` — **CONN-PACK-2** ([connections](./tz_structure_connections.md) §8)
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
`DistrictAssembler` получает `street_layout` из шаблона и вызывает соответствующий генератор улиц. Рамка layout — после брони прохода 1, вокруг неё; полотно — после всей посадки (§6.3). Улицы не через занятый участок.

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

Клетка цикла — **ячейка footprint города**, не pack макротайл (§1.1). Сначала **пара** `district_type` + `district_subtype` (приоритет §1.2 ∩ зона center/edge/inner), затем чертёж: pin `system_name` с города, иначе registry с той же парой.

Предпочтение зоны смотрит на **`district_type`** (ткань), не на subtype:

```
центр: civic → commercial → residential
край:  port → agricultural → commercial → residential → industrial
внутри: residential → commercial → industrial → agricultural
```

```
проход 1 — typical_districts города (каждая запись → свободная клетка с лучшей зоной под district_type)
проход 2 — оставшиеся клетки: union specialization ∩ предпочтение зоны
проход 3 — ещё оставшиеся: typical морфологии ∩ зона
клетка без пересечения → skip
на выбранной записи: pin system_name (только проход 1) → этот чертёж, если type+subtype совпали
иначе кандидаты = чертежи registry с тем же district_type и district_subtype
                  и прошедшие placement_conditions
выбрать чертёж: среди равных rng (seed §9.6)
DistrictSlot(…, district_template = чертёж)
```

#### Воспроизводимость (чертёж из пула мира)

Rng **не** выбирает тип поселения и не подменяет N копий ([connections](./tz_structure_connections.md) §5.1.3).

**Главный пул — чертежи зданий** одного `structure_type` из библиотеки мира (§1.1 ось 3): среди `tavern_1` / `tavern_2`, не «любой JSON библиотеки».

**База seed:** `world.world_uid` + `location_uid` поселения. Для независимости клеток и роста footprint — те же два uid + **`(cell_x, cell_y)` ячейки footprint** (не `tile_gx/gy`). Та же клетка + тот же пул типа → тот же чертёж. Смена размера города не должна перетасовывать уже существующие индексы клеток.

Ничья чертежей района одного `district_type` — тот же ключ (пара uid + клетка footprint), суффикс роли `_districts` чтобы не сдвигать поток зданий. Пустой subject роли (§1.2.1) — тот же ключ, суффикс `_subjects`.

| В seed | Не в seed |
|---|---|
| `world_uid`, `location_uid` города | ранг размера, JSON реестра как строка, время, pid |
| `(cell_x, cell_y)` footprint; опц. суффикс `_districts` / `_buildings` / `_subjects` | pack макротайл; третий uid сущности |
| внутри слота (frontage, size_pct): + origin слота в метрах | |

Смена состава библиотеки (добавили `tavern_3`) меняет eligible — при том же seed выбор **может** смениться. Копия `location_uid` в другой мир — другой город.

**Код:** `plan_district_slots` — `location_uid` + размер на скелете, без мира и без клетки footprint — **CITY-T-2c**. Pick здания по `structure_type` из SQL library — **2b**; рецепт обязательных типов на поселении — **2d**. Целевой размер — ранг **LOC-T-2**, не токен морфологии.

`DistrictSlot.ground_z` — sample coarse-клетки (якорь района / `NamedLocation.map_z`). **Не** плоскость пола застройки и не значение для копирования на все `AreaSlot`. Выравнивание зданий — участок: [tz_settlement_outdoor.md](./tz_settlement_outdoor.md) **C21**, [tz_assembler_hierarchy.md](./tz_assembler_hierarchy.md) §7.1.

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
| Механика дорог внутри района и между районами | **closed** — [tz_structure_connections.md](./tz_structure_connections.md) §5; `DistrictAssembler` + `connectionPolicy`. Рамка после брони — §6.3 |
| **TODO** generate барьера **района** | **открыт** — `DistrictLayout.barrier_cells`. Зоны: не список поселения |
| **TODO** поле барьера **поселения** на скелете (`CitySkeleton.perimeter_barrier`) | **открыт** — generate shrink есть; клетки стен всё ещё эвристика — **CITY-T-1c**; import поля нет — **CITY-T-1a** |
| Зоны трёх инстансов `PerimeterBarrier` (нет общей xy) | **закрыт** — поселение вычитает `footprint ∩ слот` из площади района; packing района — только прямые района; [tz_locations.md](./tz_locations.md) |
| **CONN-PACK-1** — рамка `radial` / `organic` вокруг брони; snap якорей вне `grid` | **открыт** — [connections](./tz_structure_connections.md) §8 |
| **CONN-PACK-2** — два+ `required_structures` с `position: center` | **открыт** — connections §8; поле — §9.4 |
| **CONN-PACK-3** — envelope `(template, facing)` на проходе 1 до полосы рамки | **открыт** — connections §8 |
| `adjacent_terrain` — связанность воды | **open** — condition есть, connectivity не описана |
| **Footprint города — форма** | **v1 closed:** квадрат `footprint_multiplier × map_cell_size_m`. **v2:** §10 TODO organic |
| **CITY-T-1** — скелет C22 не roundtrip import/SQL; debug persist ≠ `lazy_settlement`; стены эвристика vs поле; шапка этого ТЗ stale | **open** — [tech debt CITY-T-1](./tz_generator_technical_debt.md#city-t-1--контур-вокруг-city-generate); не алгоритм §6.3 в коде |
| **CITY-T-2** — пул мира vs packing: uid library (**2b**); 2a/2c/2d `partial` | **partial** — [tech debt CITY-T-2](./tz_generator_technical_debt.md#city-t-2--пул-шаблонов-мира--packing) |
| **CITY-T-4** — смешение/хардкоды планировщика после 2d | **resolved** — [tech debt CITY-T-4](./tz_generator_technical_debt.md#city-t-4--планировщик-после-2d-смешение-и-хардкоды); leftover interiors/uid — **CITY-T-2b** |

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
| **`full`** | L0 **`full_bake`** + **§8 topology** (районы + city gates). Packing — не этот gate. |
| **`partial`** | Lazy: L0 по необходимости; topology/packing при входе, если ещё нет. Regen уже созданных — **после snapshot** (§11.4). |

Ключ `init_mode` в settings — ⬜; процесс мастера = `POST pack/bake?mode=full` (+ topology) → `mode=detailed&scope=location` (L2 + C11 на settlement-like).

### 11.3 Scope materialization (без интерьеров)

| Слой | `full` / `full_bake` | `partial` / lazy | Persist |
|---|---|---|---|
| Terrain S→O→C→CL (L0 pack) | ✅ | по необходимости | pack world_map |
| **Settlement topology** (§8) | ✅ после L0 | если ещё нет — при входе или C11 | SQL районы + city gates |
| Settlement outdoor packing | нет | если ещё нет — при входе | pack `settlement.zst` + SQL здания |
| `connection_*` city (ворота, стыки районов) | с topology | с topology или packing | SQL |
| `connection_*` district (внутренняя сетка) | нет | с packing | SQL |
| Building `NamedLocation` | нет | с packing, **если ещё не init** | SQL |
| **Интерьеры** (фаза 3) | **⬜ STUB** | lazy отдельно | отдельный epic |

**Мастер `detailed_bake` `scope=location`** — не строка `init_mode`. Консьюмер L2 + **C11** на settlement-like (тот же `materialize`, что debug generate-settlement). Без C11 город неиграбелен. Интерьеры не входят.

### 11.4 World Snapshot — unified module

Runtime **нет**; target — [`tz_world_snapshot.md`](./tz_world_snapshot.md).

| Принцип | Смысл |
|---|---|
| **Единый модуль** | `WorldSnapshotService` — capture / restore / branch; **не** per-domain ad-hoc snapshots |
| **Каждый ход** | После commit — **полное** сохранение мира в `world_snapshots` ([`project_data_storage_tz.md`](./project_data_storage_tz.md)) |
| **Потребители** | Regen diff, time travel, TR-2 debug replay, climate far LOD — читают **restore**, не свой формат |

**Отложено до WS-1:** change detection (`partial` init), regen matrix, time travel UI, TR-2 unblocked.

### 11.5 DoD — persist cycle (без snapshot gate)

**Куда писать эталон (pack city structure, SQL-дерево, не map_cells / не патчи):** [tz_settlement_outdoor.md](./tz_settlement_outdoor.md). Ниже — generate scopes и рост; target persist клеток как OLTP **superseded**. Occupancy-flood в `map_cell_patches` **не** HTTP default.

**Контракт outdoor etalon:** `SettlementOutdoorOrchestrator.materialize` (+ `ConnectionPersistService` для графа) — **не** генератор, **не** DAG, **не** LLM.  
`SettlementPersistService` (scopes occupancy / map_cells_*) — leftover до Gate: DAG; debug HTTP outdoor **не** зовёт его.  
DAG подключается **в обход HTTP** — напрямую к orchestrator через `context` / `Container` (P12, не этот цикл).

> **Не новый продуктовый scope.** Создание зданий и дорог уже в ТЗ — здесь только **persist + сервисный контракт** для подключения DAG и debug harness.

#### Связь с доменными ТЗ

| Тема | Где описано | Что делает §11.5 |
|---|---|---|
| Процедурная застройка города | [tz_assembler_hierarchy.md](./tz_assembler_hierarchy.md), §6 здесь | bootstrap persist outdoor layout |
| Граф дорог, `graph_level`, `settlement_gate` | [tz_structure_connections.md](./tz_structure_connections.md) §1–5, **§5.1** поток сборки | persist `connection_nodes` / `connection_edges` |
| Межгородские маршруты (`_plan_world_routes`, highway, sea_route) | [tz_structure_connections.md](./tz_structure_connections.md) §5.1, §8 | persist `graph_level=world`; **после** §8 `settlement_gate`; не packing |
| Игрок / мастер: новое здание, участок дороги | [tz_world_generation_dag.md](./tz_world_generation_dag.md) — `place_building`, `construct_building`, `connect_road`; правило v2 (узкие вызовы) | patch persist `add_building` / `add_road_*` |
| `under_construction` / `under_repair` | [tz_building_generator.md](./tz_building_generator.md) §14, [tz_structure_connections.md](./tz_structure_connections.md) §3.2 | поля на persist; gameplay gate — DAG |
| Строительство (ресурсы, время, мастерство) | [tz_construction.md](./tz_construction.md) | placeholder; не блокирует persist cycle |
| Новое ребро при отсутствии торгового пути | [tz_economy.md](./tz_economy.md) | вызывает тот же `connect_road` / world-route generate + persist |
| Границы слоёв (generate ≠ persist ≠ LLM) | `.cursor/rules/layer-boundaries.mdc` | генераторы materialize; service пишет в БД |
| **Модификация terrain** | [tz_terrain_generation.md](./tz_terrain_generation.md) § Persist cycle — **локальный patch** (cataclysm, combat, excavate); bootstrap S→O→C→CL отдельно | `MapCellService.persist_terrain_patch` + scopes |

DAG может materialize **разные уровни** в разных нодах/фазах — persist зеркалит granularity, а не один монолитный «save everything».

#### Уровни bootstrap (generate ↔ persist)

| Scope | Generate (сейчас) | Persist (target) | Когда |
|---|---|---|---|
| `settlement_topology` | `plan_district_slots` + entries + city street grid (**без** packing) | SQL NL районов + `connection_*` `graph_level=city` (ворота, стыки) | **`full_bake` после L0** (§8). DAG: [`generate_settlement_skeleton`](./tz_world_generation_dag.md) — target этот scope, не occupancy-flood |
| `occupancy` | `plan_occupancy_only` | **не** эталон (C7: L0 pin / union слотов later) | не HTTP outdoor |
| `map_cells_surface` | `collect_surface_grid_cells` | INSERT OR IGNORE leftover | не эталон |
| `map_cells_geometry` | `collect_geometry_meter_cells` | не эталон (C2) | packing / C11 |
| `connections_city` | topology pass (ворота + межрайонные); packing не переигрывает типы | upsert by uid | §8; [connections](./tz_structure_connections.md) §5.1 |
| `connections_district` | `DistrictLayout.connection_*` | nodes/edges `graph_level=district` | packing C11 — не topology |
| `buildings` | `AreaLayout.building_location` | upsert `NamedLocation`, **skip if initialized** | packing C11 |
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

Стык urban ↔ world: `settlement_gate` с topology (§8) на границе footprint — [tz_structure_connections.md](./tz_structure_connections.md) §2.2, §5.1. Без ворот трасса не в центр пина.

#### Idempotency

- Buildings: skip if location уже есть / помечен initialized (geometry probe — `needs_settlement_geometry`).
- Map cells: `INSERT OR IGNORE` (как сейчас `lazy_settlement`).
- Connections: upsert by `node_uid` / `edge_uid`; не дублировать при повторном вызове того же scope.

#### Debug API (harness)

Тонкая оболочка над orchestrator — **те же методы**, что позже DAG (обход HTTP в production):

- `POST …/locations/{uid}/generate-settlement` — debug caller **того же** C11, что `detailed_bake`; не occupancy, не `get_all`
- `POST …/generate-settlements?all=1|under=|state_uid=` — селекторы C16
- `POST …/settlements/{uid}/extend-road`, `POST …/connections/plan-world-route` — growth (TBD)
- Smoke: `GET …/locations` + `GET …/connections`

#### Checklist

- [x] `SettlementOutdoorOrchestrator` — pack city + SQL tree (C19); debug HTTP
- [x] `SettlementPersistService` — scope-based bootstrap API (DAG leftover; не HTTP outdoor)
- [x] `ConnectionPersistService` — patch persist nodes/edges (urban + world)
- [x] repos + migration: `connection_nodes`, `connection_edges`, `connection_edge_cells`
- [x] building `NamedLocation` upsert (skip if initialized)
- [ ] `SettlementStateLoader` / `WorldGraphStateLoader` — для growth (можно следом)
- [ ] `SettlementGrowthService` / `WorldRouteGeneratorService` — по контрактам DAG ТЗ (можно следом)
- [x] debug route(s) — `generate-settlement` → orchestrator; batch C16
- [x] **`detailed_bake` scope=location** → тот же C11 `materialize` после L2 (консьюмер; не копипаст packing в pack bake)
- [x] §8 `settlement_topology` после `full_bake` L0 (C23); reuse на C11
- [ ] `_plan_world_routes` на `settlement_gate` (после topology)
- [ ] `init_mode` в `AppSettings` + API (можно параллельно; packing всех городов **не** входит)
- [ ] DAG wire — **не в этом цикле** (мастер); см. [tz_world_generation_dag.md](./tz_world_generation_dag.md)

---

## Changelog

| Дата | Изменение |
|---|---|
| 2026-09-07 | **§9.3** `min_count` → `min_adjacent_cells` (порог соседних terrain-клеток слота). Breaking wire. |
| 2026-09-06 | **Контракт bake:** full = L0→C23; detailed = L2→C11 поверх. Хук C11 ✅. |
| 2026-09-06 | **§8 код:** `plan_topology` после `full_bake` L0; CITY-T-1a skeleton на NL; C11 reuse слотов. |
| 2026-09-06 | **§8 locked:** после `full_bake` L0 — topology (имена районов с чертежа, N/типы по §1.2, входы + `settlement_gate`). Не packing, не LLM, не light_bake. C11 reuse слотов. SoT склейки — outdoor **C23**. |
| 2026-09-06 | **§1.2.1** subject packing: named токен святой; пустой → RNG из реестра **мира** того же kind + packing log; канон dataModel только если колонка пустая (не union `iron_ore` в чужой каталог). |
| 2026-09-06 | **Livestock:** ENUM-E `livestock_kind` (`meat`/`dairy`/`fiber`/`draft`/`mount`) + N+1 `livestock_registry`. Роль `livestock` ≠ `farm`. Kind ≠ постройка. Recreate DB (`livestock_registry`). |
| 2026-09-06 | **Farm crops:** ENUM-E `crop_kind` (`grain`/`vegetable`/`fruit`/`fiber`/`fodder`) + N+1 `crops_registry`. Шаблон фермы: `crop_kind`. Recreate DB (`crops_registry`). |
| 2026-09-06 | **Extract resources:** ENUM-E `resource_kind` (`ore`/`stone`/`timber`/`liquid`) + N+1 `resource_type_registry`. Шаблон здания: `resource_kind`; layout-shaped `subjects` — REF-W + kind match. |
| 2026-09-06 | **§1.2 subjects:** несколько видов на роли (`subject_kind` строка\|список) и на bind (`subjects` список или карта kind→токены). |
| 2026-09-05 | **CITY-T-4** resolved (`/impl-city-t-4` A–G): POJO zone/rank/conditions; один resolve; cache=tokens; Bind-only coerce; skip unknown assembler. Не reopen §1.2. Recreate DB (`district_zone_preference`). |
| 2026-09-05 | **CITY-T-4** команда `/impl-city-t-4` + план `city-t-4-planner-debt.md` (слои A–G). Не reopen §1.2. |
| 2026-09-05 | **§1.2 subjects:** N+1 руды/культуры/изделия/домены на роли (`subjects`, `subject_kind`, `subjects_to_structure_types`); чертёж здания `subjects`. |
| 2026-09-05 | **§1.2:** морфология (`city`/`village`) ≠ специализация на шаблоне поселения (`extract`/`process`/…). Районы: `district_type` + `district_subtype`. Приоритет: список на городе → специализация → морфология. Реестр §4.1. |
| 2026-09-05 | **§1.1** три оси: тип поселения (рецепт районов + обязательные типы зданий) ≠ тип района ≠ `structure_type` / чертёж библиотеки. Клетка = footprint, не макротайл. §9.4/§9.6/seed под оси. **CITY-T-2d**. |
| 2026-09-05 | §9.6 seed: было «пул районов одним потоком»; уточнено — чертёж здания по типу, ключ мир+город+клетка footprint. |
| 2026-09-04 | **CITY-T-2:** пул шаблонов мира (не список на городе) vs packing fill — SoT [tz_generator_technical_debt.md](./tz_generator_technical_debt.md) CITY-T-2. §9.2 `allowed` null — указатель на 2a. |
| 2026-09-03 | **CITY-T-1:** контур import/SQL скелета, dual persist, стены vs C22, stale шапка — SoT [tz_generator_technical_debt.md](./tz_generator_technical_debt.md). Не packing §6.3 в коде. |
| 2026-09-03 | C22: три зоны `PerimeterBarrier` без общей xy; поселение вычитает прямые footprint из площади района до packing; `sides` = прямые bbox инстанса (`[]` = все четыре). |
| 2026-09-02 | Барьер поселения (периметр footprint) vs барьер района (`DistrictSlot`): один класс, разные инстансы. |
| 2026-08-30 | §9.6: `DistrictSlot.ground_z` = пин района, не пол застройки; SoT — outdoor **C21** |
| 2026-08-30 | Persist/оркестрация outdoor на pack → [tz_settlement_outdoor.md](./tz_settlement_outdoor.md); HTTP `generate-settlement` = `SettlementOutdoorOrchestrator`; §11.5 map_cells как эталон superseded |
| 2026-06 | §11.5 — persist cycle: ссылки на tz_world_generation_dag, tz_structure_connections §5.1, tz_construction, growth/world routes, terrain modification |
| 2026-06 | Sync TZ ↔ код: `SettlementGeneratorService`, `StructureGeneratorService`, `map_cell_size_m`, статус фаз A–F, §10 |
| 2026-06 | `tz_assembler_hierarchy.md` §7.5 — `map_cell_size_m` вместо `map_settings.global_cell_size_m` |
