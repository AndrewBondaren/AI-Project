# План: библиотека участков на каждый лист `BuildingPurpose` ✅ DONE

Не SoT (SoT — `docs/tz_building_generator.md` §2.1 / §3.1). Код не в этом файле.

**Замок уже в силе:** чертёж packing = **участок** (`DrawingKey` + `occupied_footprint`). Здание на участке = вложенное `building` (пример: `fixtures/templates/inn_small.json` ← `tavern_1.json`). Малые пристройки **не** в чертеже. Интерьер packing не гоняет. DAG не трогать. Ранг ≠ морфология. Generate в fine cells.

## Цель

Каждый **лист** `BuildingPurpose` имеет ≥1 чертёж участка с верным `structure_types` и заявленным конвертом. Иначе enabled-лист в мире = leftover packing (как сейчас для `house`, `plaza`, `palace`, …).

Не цель: уникальный интерьер на лист, `small_layouts`, CITY-T-2b (uid→SQL), tightening `allowed` районов, `yard_depth` (NC-2).

## Счёт

72 листа в дереве. Канон-пак `fantasy` включает **59**. Паки extras (modern/magic/steampunk/sci_fi) добавляют **13**, не заменяя fantasy.

Сейчас в builtin каталоге **11** leftover-имён (не целевой `{leaf}_default`):

| leftover | лист | Целевой fallback |
|---|---|---|
| `town_hall` | `town_hall` | `town_hall_default` (+ pin civic) |
| `inn_small` | `tavern` | `tavern_default` (тело может остаться `tavern_1.json`) |
| `mine` `mill` `smelter` `workshop` `temple` `theater` `library` `farm` `livestock` | одноимённый лист | `{leaf}_default` |

Нет чертежа с тегом **`house`**, хотя omit `structure_types` → `[house]`.

## Форма одной записи (fallback `{leaf}_default`)

```text
fixtures/templates/{plot_system_name}.json
  system_name          — DrawingKey участка (ключ plot_counts / pin)
  structure_types[]    — листья, не семья
  occupied_footprint   — bbox здания на участке (клетки)
  perimeter_barrier    — забор участка или omit
  resource_kind / crop_kind / livestock_kind / subjects — только extract/farm/livestock
  building             — тело здания (как tavern_1) или null
```

- `building: null` + нет leftover `levels` на корне → участок без NL (`plaza`).
- `building` есть → assembler ставит NL + оболочку пола из footprint; комнаты не generate.
- Тело здания живёт в `fixtures/templates/` (как `tavern_1.json`); участок его вкладывает или leftover корневые `levels` до миграции stub.
- Каталог: `canonical_defaults()` грузит JSON, как `inn_small`. Не плодить третий stub «ратуша на все» в Python.
- Позже CITY-T-2b: те же JSON под `structures_templates/engine/` — **не** этот план.
- Имена папок `engine` / zip **не** путать с `purpose_packs`.

### Имена (замок)

Fallback-библиотека движка, не нумерованные варианты мастера.

- Чертёж участка: **`{leaf}_default`** (`house_default`, `butcher_default`, `plaza_default`).
- Не `{leaf}_1`. Не `system_name` = лист (`house`, `town_hall`) — это purpose / ловушка pin.
- Тело здания (интерьер, как сейчас `tavern_1.json`) — **другой** файл; его имя не обязано совпадать с участком.
- `inn_default` = постоялый двор (dwelling). `tavern_default` = таверна (trade). Не путать.
- Комбо: `house_workshop_default`, не вместо одиночных.
- Старые 11 имён (`town_hall`, `inn_small`, `mine`, …) — leftover. В той же волне fill: переименовать в `{leaf}_default` и вместе поменять pin `civic_center` → `town_hall_default`. `inn_small` → `tavern_default` (вложенное тело может остаться `tavern_1.json`).

## Архетипы участка (топология, не комнаты)

Двор в packing пока константа `YARD_PADDING_FINE=1` (NC-2). Поле двора на чертеже в этом плане **не** открываем. Порог `door` (лот=дом) почти не живой, пока pad=1.

| id | Когда | `occupied_footprint` (ориентир) | `building` | забор |
|---|---|---|---|---|
| `street_house` | жилой / лавка вплотную | 6×8 … 8×10 | да | нет |
| `yard_house` | дом во дворе, казарма | 8×10 … 12×12 | да | опц. |
| `civic_hall` | ратуша, суд, гильдия, академия | 12×12 … 16×16 | да | как ратуша / нет |
| `open` | площадь | = лот 12×16 … 16×16 | **null** | нет |
| `yard_work` | ферма, шахта, склад, верфь | 16×20 … 24×24; дом меньше лота | да (коробка) | часто да |
| `dock` | причал | 8×16 … 12×20 | да или навес | нет |
| `gate` | надвратная / сторожка | 6×8 … 8×8 | да | нет (стены города — CITY-T-1c, не этот чертёж) |

Один архетип на много листьев. Различает `system_name` + `structure_types` + kind/subjects.

## Волны

### Волна 0 — контракт (сделано)

`occupied_footprint`, `building`, пример таверны, cache из footprint, assembler без малых пристроек и без generate комнат.

### Волна 1 — канон играбелен (~22 новых + миграция 10 stub)

Без этого city/village generate сажает чужие теги в жилой fill и бумажные семьи.

**Миграция stub → JSON `{leaf}_default`** (явный footprint ≠ 4×4 где архетип больше) + смена pin:

| leftover | цель |
|---|---|
| `town_hall` | `town_hall_default` + pin `civic_center` |
| `inn_small` | `tavern_default` |
| `mine` `mill` `smelter` `workshop` `temple` `theater` `library` `farm` `livestock` | `{leaf}_default` |

**Новые обязательные:**

| лист | `system_name` | архетип | зачем |
|---|---|---|---|
| `house` | `house_default` | `street_house` | omit тега и жилой fill |
| `plaza` | `plaza_default` | `open` | участок без NL; frontage skip |
| `inn` | `inn_default` | `yard_house` | dwelling, не таверна |
| `barracks` | `barracks_default` | `yard_house` | dwelling |
| `shop` | `shop_default` | `street_house` | коммерческий fill не одной таверной |
| `warehouse` | `warehouse_default` | `yard_work` | extract/process рядом |
| `market` | `market_default` | `open` или `civic_hall` | торг; здание опц. навес — **решить:** NL да/нет |
| `shrine` | `shrine_default` | `street_house` | fantasy public |
| `bathhouse` | `bathhouse_default` | `yard_house` | fantasy public |
| `courthouse` | `courthouse_default` | `civic_hall` | не тюрьма |
| `palace` | `palace_default` | `civic_hall` крупнее | government |
| `legislature` | `legislature_default` | `civic_hall` | government |
| `chancery` | `chancery_default` | `civic_hall` | government; MoD = чертёж этого листа, не `gatehouse` |
| `academy` | `academy_default` | `civic_hall` | knowledge в fantasy |
| `dock` | `dock_default` | `dock` | harbor |
| `gatehouse` | `gatehouse_default` | `gate` | defense |
| `watchtower` | `watchtower_default` | `gate` | defense |
| `prison` | `prison_default` | `yard_house` | defense, не public |
| `smithy` | `smithy_default` | `yard_house` | craft ≠ generic `workshop` |

**Решить до кода волны 1:** `market` — площадь без NL или крытый рынок с зданием. Рекомендация: **с NL** (навес = здание), `plaza` остаётся единственным канон-open без дома.

### Волна 2 — остальной fantasy (одиночный лист = один участок)

Все остальные листья **в** `PACK_PURPOSES[fantasy]`, которых нет после волны 1.

**public** (уже есть после 1, кроме): —

**trade:** `guild`, `granary`, `bakery`, `butcher`, `fishmonger`, `greengrocer`, `apothecary`, `tailor`, `cobbler`, `jeweler`, `bookseller`  
(таверна/`shop`/`warehouse`/`market` — волна 1)

**craft:** `carpenter`, `tannery`, `weaver`, `potter`, `glassblower`, `brewery`, `winery`, `chandler`  
(`workshop`, `smithy` — раньше)

**extract:** `quarry`, `lumber_camp`

**process:** `sawmill`, `shipyard`, `kiln`

**agrarian:** `orchard`, `vineyard`, `stable`, `apiary`, `fishery`

Итого волна 2 ≈ **28** участков. Архетип почти везде `street_house` / `yard_work`. Kind: orchard/vineyard → `crop_kind`; fishery/stable по смыслу agrarian без нового purpose.

### Волна 3 — листья вне канон-`fantasy` (13)

В каталог **можно** класть: packing режет `purpose_packs`. В мире omit packs → `fantasy` → эти чертежи не в пуле.

| лист | паки | `system_name` |
|---|---|---|
| `church` `hospital` `school` | modern, sci_fi | `{leaf}_default` |
| `cafe` `restaurant` `hypermarket` | modern, sci_fi | `{leaf}_default` |
| `embassy` | modern, sci_fi | `embassy_default` |
| `water_treatment` | steampunk, modern, sci_fi | `water_treatment_default` |
| `laboratory` | steampunk, modern, sci_fi | `laboratory_default` |
| `assembly_plant` | steampunk, sci_fi | `assembly_plant_default` |
| `arcane_lab` | magic | `arcane_lab_default` |
| `portal` | magic, sci_fi | `portal_default` |
| `air_dock` | sci_fi | `air_dock_default` |

Не сажать magician tower вместо `arcane_lab_default`. Башня жилая = комбо волна 4.

### Волна 4 — комбо (не «закрыть лист»)

После одиночных. Не заменяют `house_default` / `workshop_default`.

| чертёж | теги | зачем |
|---|---|---|
| `house_workshop_default` | `house`, `workshop` | like на мастерскую в жилом |
| `house_arcane_lab_default` | `house`, `arcane_lab` | башня мага; только если в каталоге есть `arcane_lab_default` |
| не делать канон `town_hall`+`palace` | — | civic pin like утащит дворец |

`[courthouse, prison]` — **не** обязательный канон-чертёж (мир может).

## Порядок имплементации (когда скажешь «делай»)

1. Волна 1 JSON + `canonical_defaults()` грузит файлы; stub `_TOWN_HALL_LEVELS` убрать у мигрированных.
2. Тест: каждый fantasy-лист после волны 2 имеет `catalog.of_structure_type(leaf)` nonempty; pin `civic_center` = `town_hall_default`.
3. Волна 3 теми же файлами.
4. Волна 4 по списку.
5. Не в этом плане: `allowed: ["dwelling"]` на residential (иначе после `palace_default` like пустит дворец в жилой, если район omit allowed).

## Явно не делаем

- Лист на чертёж «чтобы packing не молчал» **без** `occupied_footprint` — снова stub_no_shell.
- Авто-тег семьи на JSON.
- N+1 purpose (`blacksmith`).
- Уникальные комнаты на 72 листа; `debug_structure.py tavern_1` остаётся эталоном тела здания.
- Малые пристройки.
- Оставить pin на leftover `town_hall` / `inn_small` без переименования в `{leaf}_default`.

## Развилки

3. **Все листья = все чертежи `{leaf}_default`.** Закрыто (в т.ч. `butcher_default`, не одна `shop_default` на `trade`).

Ещё открыты (переформулировка):

1. **Рынок `market_default`:** на участке есть здание (крытый гостиный двор) или это площадь без дома, как `plaza_default`?
2. **Чертежи вне fantasy** (`church_default`, `cafe_default`, …): лежат в том же каталоге движка (паки только не дают их сажать в канон-мире) или в отдельной папке, которую канон не грузит?

После согласования волн/развилок — код только на согласованную волну.
