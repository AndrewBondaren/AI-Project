# HY-12 — declare морей = бассейн в elevation; autoresolve по уровню — DONE

**Долг:** HY-12 (high) в [`docs/tz_generator_technical_debt.md`](../../docs/tz_generator_technical_debt.md).
**ТЗ:** [`tz_terrain_hydrology.md`](../../docs/tz_terrain_hydrology.md) § SeaBasinGenerator, § Ocean bathymetry, § U15, § Pass 1.4/1.5; [`tz_terrain_generation.md`](../../docs/tz_terrain_generation.md) § Топология поверхности.
**Зависимости:** HY-6 ✅ (water-side геометрия для rim у declared coastline); HY-11/TOPO-1 (домен топологии — соседи/метрика/канонизация через шов); HY-BATH-1 (DepressionForm — vehicle форм впадин). HY-8 — семантический предшественник: **порядок carve → fill → derived shore**; HY-12 реализует declare-слой и autoresolve поверх этой семантики (слои разделены — решение мастера).
**Не входит:** HY-9 формы береговых линий (отдельный трек поверх), HY-10 band→L0, HY-7 precedence горы (следствие carve-лимита), COV-1, батиметрия неоднородного дна (DepressionSpec внутри воды — после базового бассейна).

## Межплановые зависимости — актуализация 2026-10-20

Планы выделены явно: [общий placement](generator-placement.md), [общий lifecycle](entity-lifecycle.md), [динамические водные системы](hydrology-water-systems.md). Карта: [plan-dependency-graph.md](plan-dependency-graph.md).

- Шаг 1 HY-12 совместно с P1 закрывает контракт coastline → basin. Шаг 2 использует общий placement-контракт P1; шаг 3 ждёт общего resolver P2 и водного adapter P3 — **жёсткая зависимость, решение мастера 2026-10-20 (вариант A)**: carve не работает с сырыми declare в обход resolver даже для authored absolute footprint; обходного пути «прямой carve + долг на миграцию» нет. Шаги 1–2 идут параллельно с P0/P1 (контракты согласуются совместно). Миграция остальных placement consumers не является искусственным блокером HY-12, но общий placement-трек без них не закрывается.
- **Placement P2 + P3 W1–W2 adapter выполнены 2026-10-20:** общий resolver и `placement/adapters/water.py` готовы, приёмка 184 tests OK (21 adapter-проверка). Prerequisite adapter для разработки HY-12/3 закрыт. В шаге 3 caller собирает полный world-fine pre-carve snapshot и intents готовых доменов → один общий P2 → `resolved_water_placements` → factory/spec-apply. Старый coarse heightmap нельзя выдавать за fine; water-only pass запрещён. Production wiring и materialize ещё не выполнены и не объявляются миграцией W1–W2.
- **Уточнение B1 в P1 (принято мастером):** совместный проход подготовленных мировых intent выполняется на base heightmap + anchors до 1.4. Поздние зависимости (в том числе river mouth на готовой воде) используют тот же общий resolver по мере готовности опор, с ранее принятыми решениями без их пересмотра. Это не локальный placement внутри hydrology. Missing/null specificity → auto по утверждённой adapter policy, без неявного 0; coastline без воды сохраняет отдельное утверждённое правило effective 0. Typed record и missing-default/validate_only политика — § Placement P1 `tz_map_light_bake.md`.
- Lifecycle L0–L2 готовится независимо от placement и HY-12. Его отсутствие не блокирует чистые carve/fill и river tests HY-12.
- Шаги 4–5 HY-12 поставляют физические водные объекты и соединения для W3. W0/W1 могут готовиться заранее после согласования входных контрактов, W2 тестируется на fixtures. L3 и W3 вместе принимают atomic writer и историю.
- В HY-12 `waterBodyResolver` разрешает физические уровни непосредственно сливающейся воды. Он не выбирает доменную систему вместо W-consumer и не реализует общий lifecycle. Соединение объектов рекой не делает все уровни системы одинаковыми.
- Шесть шагов HY-12 сохраняются. Динамические системы, общий lifecycle и миграция placement вынесены в отдельные планы; их реализация не приписывается шагу 4 HY-12 и не включается молча в его Done.
- HY-9 адаптируется к HY-12/GEO-1: старый procedural bbox-edge flood не используется как target. HY-10 следует после физических ролей/индексов и отвечает за L0 wire/bands. GEO-1 использует placement и relief, не подменяется natural-only autoresolve HY-12.

## Проблема

Declare-контракт морей — «линия → флуд в сторону» (`declared_coastlines` + полуплоскость `(C−K)·n>0`):

- форма водоёма не выразима — океан всегда полуплоскость/прямоугольник;
- на wrapped/sphere одиночная линия = неразделяющая петля → flood заливает весь мир минус линия;
- declare = paint роли + безусловный `surface_z = z_sea` (HY-8): мастер объявляет воду, а не рельеф под ней;
- типы водоёмов (`sea`/`ocean`/`inland_sea`) не объявляемы — `basinKindResolver` читает только subtype локации;
- autoresolve = bbox-edge flood — на торе «края» не существует.

## Целевой контракт

**Declare моря = изменение elevation, не paint. У каждого водоёма свой уровень.**

**Уточнение мастера 2026-10-20 — общий resolve размещения.** Все объекты генератора, включая водоёмы и coastline, используют единый контракт и общий resolver размещения ([Placement priority](../../docs/tz_map_light_bake.md#placement-priority)). Добавить только локальное поле приоритета в `DeclaredBasin` или собственный resolve гидрологии недостаточно. Доменные carve/fill и физическое разрешение уровней остаются ответственностью гидрологии; конкуренция размещения и порядок зависимостей разрешаются общим механизмом.

**Целевые пути общего placement (утверждено мастером 2026-10-20):** `backend/app/application/worldData/placement/` — общий resolver всех объектов генератора; `backend/app/dataModel/placement/` — общие POJO-контракты. Папки и реализация пока не созданы. Гидрология подключается к этому общему механизму; собственный placement resolver в `generators/hydrology/` не создаётся.

Coastline — контракт создания воды; если воды нет, эффективный приоритет coastline = **0**, независимо от авторского `placement_specificity`, с **`WarningError` в лог** (уточнение мастера 2026-10-20). Исходное авторское значение сохраняется в намерении; диагностика — один раз на coastline за проход, с UID и причиной. Это решение заменяет трактовку «coastline без бассейна только warning и воду не создаёт». Шаг 1 фиксирует отсутствие воды на pre-carve входе, без проверки будущего fill; P1 описывает общий typed-вход факта и зависимостей. Архитектуру общего контракта, инвентарь потребителей и порядок миграции следует согласовать отдельным планом до реализации общего resolver; текущие шаги HY-12 не расширяются молча на миграцию всех генераторов.

Naming (решение мастера): `z_sea` некорректно — уровень воды **на водоём**, не на мир:
`z_water_level`. Глобальный скаляр становится `default_water_level` (уровень
океана); `declared_basins[].z_water_level` может отличаться — два несоединённых
моря могут иметь разные уровни (физика). Соединённые тела уровень общий —
иначе вода перетекает.

**Единый механизм для всей гидрологии (решение мастера 2026-10-20):** любой водоём — declared basin, `DeclaredLake`, coastline-derived, procedural — идёт одним путём: `declare → placement resolve → BasinSpec → relief carve → fill → classify → shore`. Параллельных механизмов (свой carve у озёр, свой flood у морей) нет. **Меняется только контекст carve**: `kind` задаёт профиль дна (`ocean` — shelf/abyss, `lake` — bowl), источник spec — authored (`DeclaredLake` нормализуется в `DeclaredBasin`-путь) или policy/autoresolve. `deepeningBandCarver`/`lakeBasinGenerator` не отдельные carvers — их функцию несёт `floorProfile` по `kind`.

По каждому домену гидрологии явно:

| Домен | Роль в едином механизме | z-запись |
|---|---|---|
| `load/` | нормализация всех declare (`DeclaredBasin`/`DeclaredLake`/`DeclaredCoastline`/реки) в единые входы + spec-контексты | нет |
| `bathymetry/` (relief) | `BasinSpec` → `surface_z` — единственный carver тел | **да** |
| `reliefObjects/riverBed/` | `RiverBedSpec` → `surface_z` русла | **да** |
| `water/` | fill `z < z_water_level`, компоненты, merge → система, classify, `shoreDerive` — читает post-carve | нет |
| `rivers/` | planner → эмиссия `RiverBedSpec` → потребляет вырезанную поверхность → роли/устье | нет |
| `waterfalls/` | **отдельная механика перелива через отвесный перепад z** (решение мастера 2026-10-20): подключается везде, где жидкость переходит между z-уровнями вертикально — ступень русла реки, pour-point/sill бассейна (перелив через борт), authored drop. Вход: факты перепада от producer'ов (river segments, rim spillway-клетки fill'а, declared drop); выход: `waterfall`-признак/фича (клетка, высота падения, жидкость, уровень низа) для NL/render/локаций. Ступень материализует relief (bed/basin профиль), профиль обязан сохранять отмеченный перепад — сглаживание не стирает. Не часть рек | нет |
| `shore/` | rim-позиция declared coastline (`waterSideFootprint`) — вход спецификации, не генератор воды | нет |
| `autoresolve/` | classify-only: компоненты впадин → spec-контексты procedural (`kind=lake` и т.д.); carve не выполняет | нет |

**Поведение водоёма = поведение локации (решение мастера 2026-10-20).** Водоём —
объект `geographic.*` (`GeographicSubtype`: sea/ocean/inland_sea/lake — уже в
реестре подтипов): `location_uid`, pin/anchor, footprint, участие в **общем
Placement resolver** (`tz_map_light_bake` § Placement priority:
`placement_specificity` → площадь → `region_uid`, опора→зависимый) наравне с
горами/лесами/поселениями. Гидрологии принадлежат только доменные carve/fill/
уровни — конкуренция за пространство решается resolver'ом, не водой.
Coastline — контракт создания воды (приоритет 0 без воды).

```
# dataModel/hydrology/ — новые POJO (strict typing, contract-creation rule)

class BasinKind(StrEnum):            # enums/basinKind.py
    SEA = "sea"; OCEAN = "ocean"; INLAND_SEA = "inland_sea"; LAKE = "lake"

class DeclaredBasin(BaseModel):      # declaredBasin.py — frozen, extra=ignore
    location_uid: StrictOnWire[str]                     # geographic-локация водоёма (пин/анкор — как у DeclaredCoastline/Lake)
    footprint: StrictOnWire[RegionShape]                # dataModel/spatial — bbox/ellipse/polygon/corridor/anchor_radius + edge_noise, без нового shape-DSL
    kind: StrictOnWire[BasinKind]
    liquid: DefaultWhenMissing[StrictOnWire[MaterialKey]] = "water"  # тип поля — system_material (ключ WorldMaterialRegistry, liquid_keys)
    floor_z: StrictOnWire[int]                          # дно строго < z_water_level — валидация
    z_water_level: DefaultWhenMissing[int | None] = None  # None → default_water_level мира
    rim: DefaultWhenMissing[HydrologyBands | None] = None  # None → policy категории
    placement_specificity: DefaultWhenMissing[int | None] = None  # единый resolver (None у autoresolve — правило § Placement priority)

# WorldHydrology (scalars):             # глобальный дефолт — бывший z_sea
    default_water_level: DefaultWhenMissing[int] = 0    # replace resolve_z_sea()=0

# Расширение существующего DeclaredCoastline (declaredCoastline.py) —
# declare объявляет водоём целиком:
class WaterSide(StrEnum):              # enums/waterSide.py — сторона воды у петли
    INTERIOR = "interior"; EXTERIOR = "exterior"

DeclaredCoastline +=
    kind: StrictOnWire[BasinKind]                        # тип водоёма (не реки)
    liquid: DefaultWhenMissing[StrictOnWire[MaterialKey]] = "water"  # system_material
    closed: DefaultWhenMissing[bool] = False             # тип линии: открытая | петля
    water_side: DefaultWhenMissing[WaterSide | None] = None  # обязательно при closed=True (валидация)
    # форма: form/form_knobs — отдельный трек HY-9 (CoastlineForm), не этого контракта

# MapCellHydrology +=                   # рантайм-факт на клетке (для устьев/берегов/render)
    z_water_level: DefaultWhenMissing[int | None] = None  # уровень своего водоёма (per-body)

**Дефолтные формы гидрологии (зафиксировано 2026-10-20):**

```
Площадь (footprint бассейна):  RegionShape = bbox | ellipse | polygon | corridor | anchor_radius (+edge_noise)
Линия (coastline/river/lake-shore): open polyline | closed ring + CoastlineForm
                                 (straight | sine_noise | sine_lagoons — HY-9, до rasterize)
Точка:                          anchor_radius (круглый водоём у якоря)
```

**`corridor` — решено добавить (2026-10-20):** `RegionShapeKind += CORRIDOR` — общий spatial-примитив (не hydrology-owned): `path: list[Point]`, `width: int > 0`, caps. Растеризация — `topology.dist` до сегментов ≤ `width/2` (unrolled-метрика, через шов). Проливы/каналы/дельты — declare без обхода полигоном.

# Записи водоёмов (компоненты/declare) — новый POJO waterBody.py:
class WaterBody(BaseModel):
    water_body_uid: StrictOnWire[str]
    location_uid: DefaultWhenMissing[str | None]        # пин/анкор локации
    kind: StrictOnWire[BasinKind]
    liquid: DefaultWhenMissing[StrictOnWire[MaterialKey]] = "water"  # resolved: system_material
    declared_level: StrictOnWire[int]                   # свой уровень: declared_i ∩ pour_point (без cascade)
    z_water_level: StrictOnWire[int]                    # effective: каскад по PHYSICAL_MERGE-предкам; нет предка → = declared_level
    declared_basin_uid: DefaultWhenMissing[str | None]  # None → autoresolve-компонента
    parent_system_uid: DefaultWhenMissing[str | None]   # ближайший union-предок; цепочка вверх = каскад уровня
```

**Инвариант согласования: метаданные ↔ материализация (решение мастера 2026-10-20).** Каждый шаг трека описывается и проверяется по двум сторонам: **метаданные** — что меняется в записях; **материализация** — что меняется в мире. Шаг, меняющий метаданные без материализации или наоборот — незавершённый контракт. Явная раскладка по слоям:

| Слой | Метаданные | Материализация |
|---|---|---|
| Placement (P) | resolved intent: footprint, specificity, опоры | — (решение «где», не мир) |
| Basin carve | `ResolvedWaterPlacement` → `basinSpecFactory` → `BasinSpec` | `surface_z` профиля дна (relief, Pass 1.4) |
| Fill + merge | `WaterBody` (level/kind/uid), union-система, warnings | роли воды на клетках (hydrology, Pass 1.5) |
| Shore derive | `deepening_index` | роль `SHORE` |
| Реки | `RiverBedSpec`, факт устья (connection) | bed carve (relief) + river-роли |
| Системы (W) | membership/primary/уровень системы, lifecycle | — выведена из фактов тел; последствия уровня — событие producer'ам |
| Lifecycle (L) | uid, предшественники, `is_active` | — |
| Persist | — | атомарная запись состояния (одна транзакция L3/W3) |

Pipeline (порядок HY-8, зафиксирован):

1. **basin carve = relief object (Pass 1.4, не гидрология).** `DeclaredBasin` → (P3 adapter → placement-pass → `ResolvedWaterPlacement` → `basinSpecFactory`, решение A2+B1) → spec бассейна → `reliefObjects/basinZ` пишет `surface_z` по piecewise-профилю (§ Алгоритм дна) в той же очереди что `mountainZ`/`ravineZ` — **дно океана принадлежит домену рельефа** (решение мастера 2026-10-20). Гидрология не пишет elevation вообще; вопрос «carve vs горы» снимается — один spec-механизм Pass 1.4;
2. **компоненты впадин** — depression labeling на heightmap **до** воды: каждой компоненте свой `z_water_level` = `min(declared_level, pour_point(component))`; declared выше pour-point → spill + warning «level exceeds pour point» (вода переливается через борт — так физически и есть);
3. **level fill** — вода там, где `z < z_water_level(component)` (строго); `z = z_water_level` — суша (waterline принадлежит суше). Заливки соседних бассейнов, соединившиеся на своих уровнях, **объединяются в систему**: слитое тело = родительская система (решение мастера 2026-10-20), дети-тела сохраняют свои uid/kind и наследуют общий `z_water_level` от родителя; конфликт уровней — § «Алгоритм разрешения уровней» (общий уровень = pour-point объединения);
4. **классификация** — тело с океанным дефолтным уровнем и массой = `ocean`; замкнутое тело на `z_water_level` ≠ океанского = `inland_sea`/`lake` по размеру и уровню (горное озеро — тело выше океанского уровня по определению); локальный минимум — `lake` (`depressionDetect`-семантика). На wrapped/sphere «достижимость от края» не применяется — признак по уровню/массе/declare, не по границе;
5. **берег derived** — land-клетка (в т.ч. `z = z_water_level` тела), 4-соседняя воде = `SHORE`; не задекларирован, не краска;
6. **реки** — река = **потребитель рельефа, не writer z** (решение мастера 2026-10-20): planner работает на post-1.4 heightmap → эмитит `RiverBedSpec` (маршрут, ширина/глубина, уклон) → **рельеф применяет bed carve** (та же spec-механика что `basinZ`) → роли/устье на вырезанной поверхности. Логика русла та же, владелец записи z — relief-домен. Устье = waterline: завершение на первой клетке `z < z_water_level` **или** open-water роли. Река может впадать в озеро **выше** океанского уровня — устье на уровне того водоёма. Порядок внутри шага рек: planner → bed spec → relief apply → роли (fill тел уже завершён — bed carve не переоткрывает fill, клетки русла получают river-семантику).

`declared_coastlines` остаётся authored-интентом береговой линии (позиция rim + HY-9 формы). Как контракт создания воды (решение мастера 2026-10-20) coastline объявляет водоём целиком:

- `kind: BasinKind` — какое море (не реки — `BasinKind` рек не содержит); с `location_uid` — какая именно локация;
- `liquid: system_material` — тип жидкости, ключ из `WorldMaterialRegistry` (`liquid_keys` — water/lava/…), default `water` (прецедент `precipitation_liquid`);
- **оси линии ортогональны** (решение мастера 2026-10-20): **топология** `closed` управляет алгоритмом footprint — `False` (открытая): bounded downhill-расширение в водную сторону с бюджетом `default_seas` (area/extent cap + edge_noise); `True` (петля): footprint = область петли, сторона воды — явное `water_side: interior | exterior` (interior → озеро/лагуна; exterior → берег острова). **Форма** `CoastlineForm`/`form_knobs` (HY-9: `sine_noise`, `sine_lagoons`…) деформирует путь **до** rasterize — на семантику footprint не влияет: синусоида открытой линии работает как открытая, волнистая петля — как петля. На торе interior/exterior — topology-aware rasterize, не bbox. Размер/глубина/уровень — явные поля declare или `default_seas` политика (детали — шаг 1 + P1).

Разрешение `liquid` при merge тел с разными жидкостями — **отдельный домен resolve типов материалов** (решение мастера 2026-10-20): гидрология и системы фиксируют факт разножидкостного union, итоговый `liquid` определяет домен материалов (смешение/доминант/запрет) — вне этого плана и вне W-трека.

## Архитектура и расположение (класс = одна ответственность)

| Слой | Путь | Ответственность |
|---|---|---|
| **dataModel** | `dataModel/hydrology/declaredBasin.py` | `DeclaredBasin` — declare-контракт водоёма |
| | `dataModel/hydrology/enums/basinKind.py` | `BasinKind` StrEnum |
| | `dataModel/hydrology/waterBody.py` | `WaterBody` — resolved-запись тела воды (level/kind/merged) |
| | `dataModel/hydrology/worldHydrology.py` | `+declared_basins`, `+default_water_level` |
| | `dataModel/hydrology/mapCellHydrology.py` | `+z_water_level` на клетке |
| **relief — морское дно** | `terrain/reliefObjects/bathymetry/basinSpec.py` | `BasinSpec` — что Pass 1.4 надо (footprint, kind, floor_z, rim, level) |
| | `terrain/reliefObjects/bathymetry/floorProfile.py` | piecewise-профиль дна: зоны shelf/slope/abyss по `d`, параметры по `kind` |
| | `terrain/reliefObjects/bathymetry/distanceField.py` | multi-source BFS `d` от waterline/rim через `topology.neighbor` |
| | `terrain/reliefObjects/bathymetry/basinZ.py` | relief object: footprint → distance field → профиль → **абсолютная** запись `surface_z` |
| | `terrain/reliefObjects/riverBed/riverBedSpec.py` + `riverBedZ.py` | spec русла (маршрут/ширина/глубина/уклон) + relief object: carve по маршруту |
| | `terrain/reliefObjects/applyReliefObjectsZ.py` | dispatch spec → `basinZ`/`riverBedZ` рядом с `mountainZ`/`ravineZ` |
| **hydrology — только вода** | `hydrology/water/levelFill.py` | fill `z < z_water_level`, водные клетки (пишет роли, НЕ z) |
| | `hydrology/water/componentLabel.py` | connected components через `topology.neighbor` |
| | `hydrology/water/waterBodyResolver.py` | merge/spill уровней → `WaterBody` (priority fill + union) |
| | `hydrology/water/waterClassifier.py` | kind компоненты: ocean/inland_sea/lake (уровень/масса/declare, не «край») |
| | `hydrology/water/shoreDerive.py` | `SHORE` = land-сосед воды; `deepening_index` из профиля |
| | `hydrology/basinSpecFactory.py` | `ResolvedWaterPlacement` → `BasinSpec` (kind→floorProfile, `default_seas`, rim) → очередь Pass 1.4 (решение A2) |
| | `hydrology/load/loadDeclaredHydrology.py` | `+declared_basins` → нормализация к placement intent (не spec — spec делает factory по resolved) |
| | `hydrology/rivers/riverNetworkPlanner.py` | устье на `z_water_level` ИЛИ роль; `_neighbors8` → домен |
| | `hydrology/basins/seaLevelPolicy.py` | `resolve → default_water_level` (был хардкод `0`) |
| **legacy** | см. § «Legacy-код» ниже — судьба каждого файла явно | |

Принципы: рельеф владеет `surface_z` (в т.ч. дно); гидрология — роли/уровни/компоненты, не z; `bathymetry/` — отдельная подпапка внутри `reliefObjects/` — семантика «морское дно», не смешивать с горами; spec объекты — в своём файле, не в applier'е.

## Legacy-код — судьба по классам / методам / контрактам

Инвентарь `generators/hydrology/` по факту кода. Каждый символ — одна категория.

**Удаляется / заменяется (flood-модель, paint, z-запись в гидрологии):**

| Файл | Символы | Замена |
|---|---|---|
| `basins/seaBasinGenerator.py` | `generate_coastal_sea` — flood declare-моря | `waterBodyAssembler` + `bathymetry/basinZ` + `water/levelFill` |
| `basins/oceanBasinGenerator.py` | `generate_open_ocean`, `expand_open_ocean` — flood океана | то же (`kind=ocean` — параметр, не класс) |
| `basins/lakeBasinGenerator.py` | `generate_lakes`, `carve_lake_basin`, `carve_lake_interior` (+`_interior_*`, `_shoreline_ring`) — собственный carve | `BasinSpec(kind=lake)` + `floorProfile` bowl — единый pipeline |
| `basins/basinKindResolver.py` | `resolve_lake_basin_role` — kind из subtype | `waterClassifier` (уровень/масса/declare) |
| `bathymetry/stubElevation.py` | `resolve_open_water_surface_z`, `ocean_stub_drop_amount` — interim z-stub | `reliefObjects/bathymetry/basinZ` |
| `autoresolve/proceduralSeaAutoresolve.py` | `autoresolve_sea_basins` (+`_carve_water_candidates`, `_autoresolve_beyond_declare_bbox`, `_autoresolve_from_map_boundary`) — bbox-edge flood | classify-only autoresolve (`water/`); синтез бассейна отклонён → GEO-1 |
| `autoresolve/proceduralLakeAutoresolve.py` | `autoresolve_lakes`, `flood_basin_interior` | spec-контексты classify-only → единый pipeline |
| `shore/deepeningBandCarver.py` | `carve_deepening_bands`/`_apply_carve` (z-запись), `DeepeningCarveResult`, `flood_water_side*`, `flood_from_bbox_ocean_edge`, `declare_coastline_bbox_padded`, `land_shore_from_water_dist`, `water_side_seeds`, `_land_shore_cells` | carve → `floorProfile`/`basinZ`; bbox-edge flood — удаляется; rim-helpers — функция `waterSideFootprint` (HY-6) |
| `rivers/riverBedCarver.py` | `carve_river_segment` (z-запись), `generate_rivers` (оркестрация) | `RiverBedSpec` + `reliefObjects/riverBed/riverBedZ`; оркестрация → `riverNetworkAssembler` |

**Пересматривается (семантика меняется, часть кода живёт):**

| Файл | Символы | Что меняется |
|---|---|---|
| `basins/lakeSpecs.py` | `extract_lake_specs`, `_group_segments`, `_location_uid_for_group` | `LakeSpec`-эмиссия → нормализация в `DeclaredBasin`-путь (declare → placement intent), не самостоятельный carve |
| `autoresolve/proceduralRiverAutoresolve.py` | `autoresolve_river_segments` | источник процедурных рек под новым контрактом — **открытый вопрос** (declare-only / policy на post-carve / GEO-1) |
| `basins/seaLevelPolicy.py` | `resolve_z_sea`, `is_land` | `resolve_z_sea()=0` → resolve `default_water_level`; `is_land(z, level)` — level становится per-body `z_water_level` (сигнатура меняется) |
| `geom/*` (`polygonInterior`, `polylineRasterize`, `smoothRiverPolyline`) | helpers | остаются; planar-геометрия → `topology`-сервисы где применимо |
| `rivers/riverNetworkPlanner.py` | planner, `_neighbors8` | post-1.4 heightmap; `_neighbors8` → домен; устье на waterline; факты перепадов → `waterfalls/` |
| `waterBodyIdentity.py` | `AutoWaterBodyRole`, `auto_water_body_uid`, `water_body_uid_for` | сохраняются для auto-тел; `water_body_uid` из компоненты/declare |
| `shore/parentLightHydroCorridor.py` | `hydro_mask_from_parent` | L0 parent-light corridor merge — домен L0 wire; пересмотр с **HY-10**, не в этом треке |

**Контракты `types.py` — судьба по классам:**

| Класс | Судьба |
|---|---|
| `LakeSpec` | superseded — lake declare идёт `DeclaredBasin`-путём (intent → `ResolvedWaterPlacement` → `BasinSpec(kind=lake)`); тип снимается после миграции callers |
| `CoastlineSpec` | расширяется rim-ролью; declare-поля (`kind`/`liquid`/`closed`/`water_side`) живут на `DeclaredCoastline`, spec-контекст — placement intent |
| `HydrologyMasterInput` | += `declared_basins` (нормализованные входы) |
| `HydrologyCellIndex`, `HydrologyResult` | += факты тел/уровней (`z_water_level`, water bodies); `RiverSegment`, `DeclaredRiverEdge`, `LoadedConnectionGraph`, `ResolvedConnectionNode`, `RiverTypeClassify` — без изменения семантики |
| `HydrologyScope`, `resolve_scopes`, `HydrologyBands` | без изменений; `HydrologyBands` переиспользуется как `rim` у `DeclaredBasin` |
| `RiverSystemIndex` | declare-time индекс U27 — **не** динамическая система (W-трек); согласование — W0 |

**Точки входа оркестрации (service — заменяемые call-sites):** `generate_coastal_sea`, `autoresolve_sea_basins`, `generate_open_ocean`, `generate_lakes`, `generate_rivers` — всё заменяется вызовами `waterBodyAssembler`/`riverNetworkAssembler`; facade сохраняет порядок/scope/dirty-bbox.

**Остаётся без изменений семантики:** `shore/waterSideFootprint.py` (`CoastlineWaterSide`, `water_side_footprint`, `water_step_from_segment`, `compute_land_centroid`, `canonical_passable` — rim declared coastline); `basins/coastalLandformClassifier.py` (read-only landform tags); `load/*` (расширяется); `shore/shoreProfile.py`, `fineHydrologyIndex.py`, `heightmapSurfaceCells.py`; `hydrologyGeneratorService.py` (facade); `dataModel/hydrology/declaredLake.py` (wire-контракт — нормализуется при load, не удаляется).

Проверка миграции в приёмке: grep `surface_z`/z-записи по `generators/hydrology/` → 0; grep вызовов `generate_coastal_sea|generate_open_ocean|generate_lakes|carve_deepening_bands|carve_river_segment|autoresolve_sea_basins|resolve_open_water_surface_z` → 0 вне их файлов.

## Оркестрация — свой слой, не city-assemblers (решение мастера 2026-10-20)

Оркестрация гидрологии живёт **внутри домена** `generators/hydrology/`, не в `generators/assemblers/` (там settlement-иерархия). Гидрология — raster-pipeline (passes над heightmap), не containment-tree: водоёмы — siblings, реки — соединители, не дети.

| Слой | Путь | Ответственность |
|---|---|---|
| facade | `hydrology/hydrologyGeneratorService.py` | только порядок passes/scopes/dirty-bbox/лог; без доменной логики |
| body | `hydrology/waterBodyAssembler.py` | сборка одного водоёма: `ResolvedWaterPlacement` → `basinSpecFactory` → `BasinSpec` → enqueue Pass 1.4 → fill → classify → shore. Параметризован `BasinKind` — **per-kind классы (`OceanAssembler`/`SeaAssembler`) запрещены**, физика одна |
| rivers | `hydrology/riverNetworkAssembler.py` | сеть: истоки → маршрут (`riverNetworkPlanner`) → bed → устье на waterline |

Границы: чистая физика остаётся в `water/`/`rivers/`/`bathymetry/` модулях — assembler вызывает, не содержит алгоритмы; уровень **систем** — не assembler, а runtime consumer (`application/worldData/hydrology/systems/`, W-трек) вне pure-генераторов; `semantic-first` применим — мастер декларирует `kind/level/footprint`, assembler разворачивает в spec и passes.

## Алгоритмы (исследование, внешние источники)

Все этапы — стандартные алгоритмы DEM/procgen, нижние границы сложности для materialize:

| Этап | Алгоритм | Источник | Сложность |
|---|---|---|---|
| Fill + компоненты | scan + flood-fill connected-component labeling | Island/ACE pipeline (`IdentifyWaterArea → IdentifyLakesAndOcean → IdentifyCoastLine`); Azgaar FMG `markupPack`; OpenFrontIO `ConnectedComponents` | O(n) |
| Fill через шов | wrap-aware flood fill (`wrapLongitude`) | DrainTheOcean `FloodFill.scala` — wrap на левой/правой границе; у нас — `topology.neighbor`/`neighbors4_unrolled` | O(W) |
| Rim-профиль / `deepening_index` | multi-source BFS distance field от rim/waterline → `z = profile(d)` | redblobgames elevation-control (distance fields `B/(A+B)`); LeatherBee modified-BFS continental shelf; Meijster et al. exact EDT | O(footprint) |
| Классификация ocean/lake | «connected to border = ocean, иначе lake» (planar); largest-component (компактная) | Random Genesis; ACE `IdentifyLakesAndOcean`; Azgaar feature `type`/`group` | O(#компонент) |
| Дренаж рек | Priority-Flood (Barnes et al. 2014) — каждая клетка имеет downhill-путь до океана; depression `closed`-флаг для endorheic | DOI 10.1016/j.cageo.2013.04.024; RichDEM `filldepressions`/`resolveflats` (ε-градиент на flat) | O(n·log n) float |
| Векторная береговая (render) | marching squares — контур на `z_water_level` компоненты | Lorensen-Cline; Frozen Fractal part 18 | O(n) |
| Speckle-cleanup | binary opening/closing; мин. размер компоненты (одиночная `z < z_water_level` = puddle, не водоём) | spatialworkflow coastline guide; Dayside — warning all-land/all-sea на краях слайдера | O(n) |

Классификатор на compact-топологии использует уровень и массу: largest-component ocean-кандидат имеет океанский default-уровень; крупнейшее горное озеро не становится океаном по одному размеру. На planar учитывается мировая граница, не край bake-bbox. Остальные тела — inland_sea/lake по ТЗ; < min_water_cells — puddle-warning.

**Домен динамических водных систем (решение мастера 2026-10-20).** Водные системы — отдельный домен внутри гидрологии, в отдельной папке. Общие POJO системы и её состояния: `backend/app/dataModel/hydrology/systems/`. Доменный consumer и обновление системы: `backend/app/application/worldData/hydrology/systems/`. Это целевые пути; реализация ещё не создана. Consumer получает изменения водных объектов и их соединений и актуализирует состав, связность и основной объект системы. Система динамическая: появление, исчезновение и изменение соединений могут объединять и разделять системы; результат не фиксируется навсегда при bake. При равном типе и объёме основной объект не выбирается. Pure-генераторы в `backend/app/application/worldData/generators/hydrology/` производят доменные данные для системы; runtime consumer не помещается внутрь pure-генераторов. Общий placement resolver в `backend/app/application/worldData/placement/` продолжает разрешать размещение всех объектов; домен систем потребляет его результат и гидрологические факты, не создавая собственного resolver размещения. Persist остаётся на границе application-сервисов/repositories. Контракты входных изменений, состояния, identity при merge/split и подключения U27 нужно описать в отдельном плане домена до реализации.

**Слитое тело = система с наследованием уровня (решение мастера 2026-10-20):** следствие свойства «водоём = локация». Локации несут собственный `location_uid` — merge не может уничтожать идентичности; система — контейнер над существующими локациями (U27-прецедент: `system` отделён от геометрии участников). Физический merge заливок — не поглощение объекта, а образование родительской системы. Дети-тела сохраняют собственные uid/kind; каждый ребёнок технически — своя система, **наследующая параметр `z_water_level` от родителя**. Это снимает проблему identity union при равенстве: победитель не нужен — uid родителя новый (lifecycle-контракт), у детей прежние.

**Единая водная система по связности (решение мастера 2026-10-20):** все водные объекты, соединённые друг с другом непосредственно или через другие водные объекты, входят в одну систему — океаны, моря, озёра и реки. Тип и объём не ограничивают членство: связь транзитивна, отдельная несвязанная группа образует другую систему. Система объединяет участников с их собственными UID; она не заменяет их одним объектом. Иерархия `ocean > sea > lake` и сравнение объёмов определяют основной объект внутри системы; при одинаковом типе и объёме победителя нет. Объединение в систему не требует одинакового уровня воды у всех участников: река может соединять водоёмы на разных высотах; физическое слияние зеркал и разрешение уровней остаются отдельным доменным правилом. Существующая U27-топология рек должна быть согласована с общей системой, а не образовывать параллельную независимую систему всей воды. Общий контракт системы, её identity, критерий соединения и адаптация U27 требуют фиксации до реализации; текущий `RiverSystemIndex` не считается готовой общей системой.

**Иерархия водоёмов при объединении (решение мастера 2026-10-20):** `ocean > sea > lake`. Если типы одинаковые (например, два `sea`), выигрывает водоём с большим **объёмом**, а не площадью footprint. Это правило выбора основного водоёма внутри системы; его применяет consumer домена водных систем к результату общего placement и гидрологическим фактам. Идентичность системы и идентичности её участников различаются. Выбор основного объекта не подменяет физическое разрешение общего уровня воды. **При одинаковом типе и равном объёме победителя нет: соединяющиеся водоёмы составляют одну систему**, без выбора победителя по UID или порядку обхода (решение мастера 2026-10-20). Члены системы сохраняют собственную идентичность; равенство не является поглощением одного другим. Прецедент — § «Топология речных систем A / B (U27)» в `tz_terrain_hydrology.md`: контейнер `system` отделён от геометрии участников. Существующий `RiverSystemIndex` описывает только реки; общий контракт системы водоёмов и его identity ещё требуется определить. Положение `inland_sea` в иерархии требует формализации до реализации.

**Объём водоёма — приближение простым телом (решение мастера 2026-10-20):** без отдельного скана клеток и без точного интеграла. Для сравнения в иерархии достаточно `V ≈ A_water × Δz`: `A_water` — число водных клеток (бесплатный счётчик в том же BFS fill), `Δz = z_water_level − z_floor` (`floor_z` из spec либо min-аккумулятор компоненты при fill). Опционально — форм-коэффициент по `kind`/профилю дна (чаша vs цилиндр), фиксируется в ТЗ шага 1 / W0. Выделенный проход по клеткам для объёма запрещён. **Точные формулы по интегралам — только для локальной физики игрока, отдельный домен (решение мастера 2026-10-20):** генератор мира интегральные вычисления не выполняет; точный объём/гидростатика для игрового масштаба — будущий домен локальной физики, не HY-12/W-трек.

**Общий домен устаревания (решение разработчика 2026-10-20):** актуальность, замещение и ссылки на предшественников вынесены в [единый lifecycle](../../docs/tz_entity_lifecycle.md). Целевые папки: `backend/app/dataModel/lifecycle/` и `backend/app/application/lifecycle/`. Гидрологический consumer рассчитывает новые системы и использует общий lifecycle; собственного механизма устаревания не создаёт. Проекты общих POJO `EntityLifecycle` и `LifecycleReplacement` описаны в профильном ТЗ.

**Жизненный цикл систем при merge/split (решено мастером 2026-10-20):** результат — новые системы с новыми UID и параметрами, со ссылками на предшественников; старые системы сохраняются в историческом неактивном статусе. Это применение общего принципа жизненного цикла сущностей, не очистка истории. Прецеденты: `tz_states.md` § states (`is_active=false`, сохранение для нарратива), `tz_locations.md` § cell_states (`ended_at`, история сохраняется), `tz_structural_mutations.md` §7 (typed mutation, before-image, ссылка на `world_history`). Эти прецеденты подтверждают принцип хранения истории; готовый универсальный POJO merge/split систем при инвентаризации не найден. Предлагаемый `is_active` переиспользует существующую семантику активности; новый локальный enum жизненного цикла не вводится.

**POJO динамических систем — проект для ревью:** конкретные поля `WaterSystemMember`, `WaterSystemConnection`, `WaterSystem`, `WaterSystemsSnapshot`, `WaterSystemsChange`, `WaterSystemsUpdate`, типы, инварианты, вход/выход consumer и границы U27 описаны в [ТЗ § Контракты домена динамических водных систем — проект](../../docs/tz_terrain_hydrology.md#контракты-домена-динамических-водных-систем--проект). Это документационный контракт до кода; техническая формула UID/identity операции, измерение объёма и незаданные ранги остаются открытыми. Состав шагов HY-12 не расширяется молча на реализацию этого домена.

## Алгоритм разрешения уровней (переливы)

Мир пересчитывается → алгоритм обязан быть **идемпотентной чистой функцией** `(surface_z, declares, topology)` и недорогим. Физическое правило: соединённые тела имеют общий уровень; перелив идёт от высокого уровня к низкому через борт.

**Pour-point — точное определение.** Rim-клетка `R` (сухой сосед заливки, `z_R ≥ L`) делится на два типа: **dead-end** — все её соседи вне воды `≥ z_R` (выемка/ступень борта — при росте L поглощается, уровень не ограничивает); **pour point** — имеет соседа вне компоненты с `z_out < z_R` (седловина сброса — за ней террейн уходит ниже). Операционно: при первом контакте frontier'а с `R` проверка `∃ сосед вне fill: z_out < z_R` — O(1) на rim-клетку. Pour-point компоненты = **первая** rim-клетка с таким соседом при росте L — заливка капится на `z_R` (вода стоит вровень со spillway, сам `R` = waterline-суша). `min_rim_z` в формуле union — минимум только по pour-point-клеткам; dead-end rim в `min_rim_z` не входит.

```
1. seeds: каждый declared basin / автовпадина → fill на L_i = min(declared_i, pour_point_i)
2. fill: multi-source PQ (priority-flood, Barnes): frontier несёт (body, L),
   расширение в соседи z < L через topology.neighbor
3. контакт фронтов тел A (L_a) и B (L_b):
     слитое тело = система S = {A, B} (решение мастера): дети сохраняют свои
       uid/kind — каждый технически своя система, наследующая уровень
       от родителя; identity union не требует победителя
     S.level = min(max(L_a, L_b), min_rim_z(union))   # борт union трекается при fill
     A и B: effective z_water_level = S.level (наследование);
       declared_i ≠ S.level → warning «level superseded» (1× на тело)
     выбор основного объекта внутри S (kind → объём) — W-домен,
       не physical merge
4. union обрабатывает только затронутые фронты/компоненты, без глобального пересчёта мира;
   при росте effective уровня fill расширяется, при понижении итоговые роли/extent сужаются
```

Пример: океан `L=20` + море `L=5`, пролив `≤20` → соединились → система `{океан, море}`, уровень `min(20, pour_point(union))`; pour-point 8 → вся система на 8 (океан дренируется через пролив — spillway); оба тела наследуют 8, declared-уровень моря superseded + warning.

**Инварианты пересчёта:** carve пишет **абсолютный** `z = profile(d)` (не дельта — re-carve стабилен); детерминизм — PQ tie-break `(z, y, x)`; сложность O(W·log W) по воде+борту; dirty-region инкрементальный пересчёт затронутых union.

## Алгоритм дна (bathymetry)

Дно — не плоское `floor_z` и не счётчик bands от линии: **piecewise distance-field профиль** реального шельфа, параметризованный `kind`.

```
d(cell) = multi-source BFS distance от waterline вглубь footprint
          (topology-aware; источник — land-соседи воды)

зоны профиля (ширины из rim/HydrologyBands + политика kind):
  shelf  0 .. w_shelf        z = lerp(z_land(rim) → z_shelf,  f_shelf(d))   # полого
  slope  w_shelf .. w_slope  z = lerp(z_shelf → floor_z,      f_slope(d))   # борт впадины
  abyss  > w_slope           z = floor_z + DepressionSpec-объекты           # дно
```

| kind | Профиль |
|---|---|
| `ocean` | глубокий abyss floor + широкий shelf, крутой slope |
| `sea` | shelf уже; глубина из spec/политики, не обязательный ранг глубины по kind |
| `inland_sea` | чаша — профиль к центру/борту |
| `lake` | bowl: `z = lerp(waterline → floor_z, f(d к борту))` |

Контракты:

- `deepening_index` — **квантование** `d`/глубины по band-классам (производная профиля, не самостоятельный счётчик) — то, что уйдёт в L0 по HY-10;
- **неоднородное дно**: DepressionSpec-объекты (котловина/желоб, width×length×depth) размещаются **внутри abyss** как geographic-локации через тот же resolver — дно не плоское;
- `bands.min` не «съедает» узкую воду: зоны — доли профиля по `d`, при узком footprint профиль ужимается (вода остаётся, shelf капнут — правило ТЗ шага 1);
- гора внутри footprint: carve cap `bands.max` не прорезает z ≫ floor → выступ суши в воде = остров naturally (HY-7 следствие).

## Дегенераты (обязаны быть в ТЗ)

- весь мир `z ≥ z_water_level` без carve → воды нет, море не объявлено → это норма, не warning;
- declare-бассейн обязан опускать floor строго `< z_water_level` — footprint целиком ≥ уровня после carve = ошибка declare (warning);
- `z = z_water_level` повсюду → воды нет (waterline = суша);
- два несоединённых моря с разными `z_water_level` — валидны; соединённые тела с разными уровнями — level conflict → общий уровень = pour-point объединения (физика: вода перетекает), warning мастеру;
- `floor_z ≥ pour_point` — declare валиден, но бассейн физически не удерживает воду (выход ниже дна): водоём не создаётся → warning «basin cannot hold water»;
- footprint > мира / на торе ≥ 50% клеток → warning «мир — океан» (Dayside-прецедент);
- компонента < min_size → puddle, не водоём (min из `default_seas`/`default_lakes` политики).

## Решения шага 1 и входные gates (2026-10-20)

Шаг 1 подготовлен к ревью: нормативный контракт теперь находится в [ТЗ](../../docs/tz_terrain_hydrology.md#level-fill--компоненты-hy-12), schema/defaults — в [declare-разделе](../../docs/tz_terrain_hydrology.md#declare-бассейн-озеро-и-coastline-u20u21-hy-12).

- Уровень на тело: `z_water_level`, мировой default — `default_water_level=0`; strict fill `z < level`, равенство — суша.
- Coastline создаёт воду через общий placement. Если воды нет на pre-carve входе, effective specificity `0` даже при authored значении, `WarningError` один раз на coastline за проход; будущий fill не является входной опорой. Общий typed факт принадлежит P1.
- Hydrology читает готовые `topology.bounds.width/height` рабочего пространства. В существующем `HydrologySeasPolicy` целевые `max_area_fraction=0.25`, `max_extent_x_fraction=0.5`, `max_extent_y_fraction=0.5`; полный world extent, не bake-bbox. Это настраиваемые стартовые defaults реализации, не географические константы.
- Глубина coastline: существующий `HydrologySeasPolicy.basin_depth: DefaultWhenMissing[int] = 20`, `>0`, Z; wire `world.hydrology.default_seas.basin_depth`. Явный `DeclaredBasin.floor_z` имеет приоритет; отсутствующее значение политики берётся из POJO. Для сохранённого lake-wire целевой `HydrologyLakesPolicy.basin_depth=5`. Kind выбирает профиль.
- Natural-only autoresolve классифицирует существующие впадины; designed ocean — GEO-1. Целевой `min_water_cells=2` в seas/lakes policy, `inland_sea_min_area_fraction=0.01` в seas policy; defaults и единицы описаны в ТЗ.
- Basin/river z пишет relief. Union уровня: `min(max(L_a,L_b), pour_point(union))`; дети сохраняют UID/kind, каскад только PHYSICAL_MERGE. Итоговый fill согласован с effective уровнем при его повышении и понижении.
- Identity источники сохраняются: declared location_uid / morph region_uid / positional auto helper; общий lifecycle identity системы — L/W, не HY-12. Объём — `A_water * depth`, без интегралов и отдельного скана.
- Sphere-fold и strict waterline проверяются в шагах 3–6; L0 bands — HY-10. Domain log diagnostics: 1× на условие на тело, без `warnings: list[str]` на POJO.
- A2+B1: P3 resolved record → hydrology basinSpecFactory → relief spec queue; placement после terrain base+anchors до 1.4. Шаг 3 ждёт P2+водный P3, шаг 2 согласует placement-поля с P1. Реализация соседних треков в HY-12 не включена.

## Шаги


### Шаг 1 — ТЗ: § Sea/level-fill contract (согласован 2026-10-20)

| Поле | Содержание |
|---|---|
| Цель | формализовать elevation-контракт морей до кода |
| ТЗ | `tz_terrain_hydrology.md` § SeaBasinGenerator, § Ocean bathymetry, § U15, § Pass 1.4/1.5 R3 — пересмотр; новый подраздел «Level-fill + компоненты» |
| Файлы | `docs/tz_terrain_hydrology.md` (+ строка в `tz_generator_technical_debt.md`) |
| Контракт | предикаты (`z < z_water_level` строго, `z = z_water_level` = суша; уровень на водоём), порядок carve→компоненты→fill/merge→берег→реки, классификатор planar/compact, rim-профиль, `declared_basins` схема полей, дегенераты, детерминизм (канонический scan-order `(y,x)`, seed-каналы форм) |
| Проверка | ревью мастером; ссылки из планов разрешаются в раздел |
| Done | контракт читается без обращения к этому плану |

### Шаг 2 — `declared_basins[]` контракт данных (реализован 2026-10-20)

| Поле | Содержание |
|---|---|
| Цель | POJO + wire для declare водоёма по форме и типу |
| ТЗ | раздел из шага 1 |
| Файлы | `dataModel/hydrology/` (`seas.py`/`lakes.py`: поля глубины/лимитов/порогов по ТЗ; `declaredBasin.py`, `enums/basinKind.py`, `enums/waterSide.py`, `waterBody.py`), `declaredCoastline.py` (+`kind`/`liquid`/`closed`/`water_side`), `dataModel/spatial/regionShape.py` (+`CORRIDOR`: path+width, rasterize через `topology.dist`), `worldHydrology.py` (+`declared_basins`, +`default_water_level`), `mapCellHydrology.py` (+`z_water_level`), `seaLevelPolicy.py` (resolve из скаляра), `loadDeclaredHydrology.py` (**только parse** `declared_basins[]` → POJO; intent-нормализация — шаг 3, зависит от P1), fixture `world_test_004` (+ один declared basin) |
| Контракт | POJO по блоку «Целевой контракт» выше — `DeclaredBasin`/`BasinKind`/`WaterBody`; footprint переиспользует `RegionShape` — **без** нового shape-DSL; `floor_z < z_water_level` — валидация при load |
| Проверка | `python -m unittest backend.tests.test_load_hydrology` (какой есть), импорт fixture; `CORRIDOR` — новый член shared `RegionShapeKind`: grep потребителей на исчерпывающую обработку kind (masks/regions/pack) — без регрессий |
| Done | мастер может объявить бассейн; валидация `floor_z < z_water_level` |

**Отчёт шага 2 (2026-10-20):** добавлены DeclaredBasin/WaterBody/BasinKind/WaterSide, поля существующих seas/lakes policies, WorldHydrology и MapCellHydrology. SeaLevelPolicy читает мировой scalar из POJO, waterline equality — суша. Loader/master передают бассейны без placement-нормализации и без carve. Материал проверяется как liquid на import (существующий REF-W в `jsonValidation/index/validate.py`) и load. Shared CORRIDOR: `topology/corridorGeometry.py` предоставляет unrolled-distance и геометрическую union-area с круглыми caps, `regionRasterNoise` поддерживает edge_noise; masks/regions/pack используют существующие shape API. Новый enum не требует их локальных shape-switches. Обязательный coastline.kind потребовал миграции четырёх fixtures и общего тестового builder; world_test_004 дополнен бассейном через x-шов. Эти изменения — техническая проводка контрактов шага 2, состав следующих шагов не расширен. Проверки: hydrology + corridor/region/RegistryKey/defaults, импорт четырёх fixtures, compileall и diff-check. Placement contracts P1/P2/P3 не реализуются здесь; следующий шаг 3 требует P2+водный P3.


### Шаг 3 — basin carve = relief object (Pass 1.4)

| Поле | Содержание |
|---|---|
| Цель | footprint → `surface_z` через piecewise-профиль дна; в очереди relief objects до hydrology |
| ТЗ | раздел из шага 1; `tz_terrain_relief` — relief objects z (Pass 1.4), spec-механизм |
| Файлы | `terrain/reliefObjects/bathymetry/` — `basinSpec.py`, `floorProfile.py`, `distanceField.py`, `basinZ.py` (новая подпапка, § Архитектура); `applyReliefObjectsZ.py` (dispatch); `hydrology/basinSpecFactory.py` + wiring `ResolvedWaterPlacement` → `BasinSpec` → очередь; `loadDeclaredHydrology.py` (intent-нормализация declare → P1-контракт); `dataModel/topology/topologyGeometry.py` (только если не хватает сервиса) |
| Контракт | rasterize footprint unrolled→canonical; multi-source BFS distance field от rim/waterline; **piecewise профиль дна** (§ Алгоритм дна: shelf → slope → abyss по `d`, параметры по `kind`, ширины из `rim`); cap `bands.max`. **Carve — абсолютная запись `z`**, не дельта: re-carve того же footprint на пересчёте идемпотентен |
| Проверка | unit: carve на planar + wrapped (footprint через x-шов); `compileall` |
| Done | heightmap содержит впадину `< z_water_level` заданной формы, шов пересекается |

#### Шаг 3 — контракт перед кодом (2026-10-21; решения мастера 1–3 приняты)

**Решения мастера:**

1. **Рабочая сетка pre-1.4 прохода = coarse surface grid** (`(gx, gy)`, `resolve_hydrology_topology`). Полный world-fine snapshot при `fine_cells_per_map_cell=1000` невозможен; placement-контракт P1/P2 единиц не требует — «world fine» в ТЗ заменяется на «рабочая сетка snapshot» (coarse для мирового pre-1.4 прохода, fine для L2/локальных вызовов). Declared геометрия проецируется fine→coarse на границе caller: segments/waypoints — `fine_to_grid_xy` (прецедент `_grid_segments`), `RegionShape` — новый метод `RegionShape.projected(divisor)` в `dataModel/spatial/regionShape.py` (координаты `//`, радиусы/width/`edge_noise.amplitude|scale` — `max(1, round(v / divisor))`). Правки ТЗ: `tz_map_light_bake` § P1 (`PlacementBatch.topology`, `PlacementFootprint.cells`, `original_area` — единицы рабочей сетки), § P3 water; `generator-placement.md` приёмка W1–W2 («не выдавать coarse за fine» → coarse является рабочей сеткой pre-1.4).
2. **Auto-specificity воды** — поле политики `placement_specificity: DefaultWhenMissing[int] = constrained_field(default=0, greater_equals=0)` на `HydrologyCategoryPolicy` (→ `default_lakes`, `default_rivers`) и `HydrologySeasPolicy` (`default_seas`). Caller кладёт его в `WaterPlacementContext.auto_specificity` по kind источника: `lake` → `default_lakes`, остальные — `default_seas`. Literal 0 в коде запрещён.
3. **Один carve.** После подключения basinZ legacy z-запись для declared источников снимается в том же заходе, interim с двойным carve не допускается. Шаг разбит на два атомарных захода: **3a** — чистые модули без pipeline (двойного carve нет, т.к. ничего не подключено); **3b** — wiring + cutover legacy z-записи.
4. **Гора иммутабельна относительно моря; море подстраивается под клетки горы (решение мастера 2026-10-21).** Вместо «cap bands.max»: порядок `mountainZ → ravineZ → basinZ(reserved)`. `mountainZ` возвращает множество поднятых клеток; `basinZ` идёт последним, пишет дно абсолютно `z = profile(d)`, **пропуская reserved-клетки** (остаются сушей своей высоты → остров), и считает distance field по footprint без reserved (reserved — «вне footprint», вокруг острова обычный шельф). Cap в z нет; `bands` — только ширины зон профиля по `d`. Идемпотентно: basinZ читает reserved-множество, не прежний z. После миграции гор в общий resolver (W7) reserved-механика снимается — спорные клетки не попадают в footprint уже на placement.

**3a — чистые модули (без pipeline, без изменения поведения мира):**

| Модуль | Контракт |
|---|---|
| `dataModel/hydrology/enums/basinKind.py` | `+ BasinKindProfile(BaseModel, frozen): shelf_depth_fraction: float \| None` (`None` = bowl) и `basin_kind_profile(kind)` — прецедент `mountain_kind_profile`. Стартовые значения: `ocean=0.15`, `sea=0.30`, `inland_sea=None`, `lake=None` |
| `terrain/reliefObjects/bathymetry/basinSpec.py` | `@dataclass(frozen=True) BasinSpec(source_uid: str, kind: BasinKind, liquid: MaterialKey, footprint: frozenset[Coord], z_water_level: int, floor_z: int, bands: HydrologyBands)`; инвариант `floor_z < z_water_level`, footprint непустой canonical |
| `terrain/reliefObjects/bathymetry/distanceField.py` | `distance_from_boundary(cells: frozenset[Coord], topology) -> dict[Coord, int]`: multi-source BFS; источник `d=1` — клетка footprint с 4-соседом (через `topology.neighbor`) вне footprint; footprint без границы (весь мир) → все `d = bands.max + 1` у вызывающего (abyss) |
| `terrain/reliefObjects/bathymetry/floorProfile.py` | `floor_profile_z(d, *, level, floor_z, bands, profile) -> int`. `top = level − 1` (strict fill: при `d ≥ 1` вода обязана существовать), `depth = top − floor_z ≥ 0`, `D_shelf = bands.min`, `D_slope = bands.max`. Bowl (`profile.shelf_depth_fraction is None`): `z = floor_z + round(depth · (1 − min(d, D_slope)/D_slope))`. Shelf-профиль: `z_shelf = top − round(depth · fraction)`; `d ≤ D_shelf`: lerp(top → z_shelf, d/D_shelf); `D_shelf < d ≤ D_slope`: lerp(z_shelf → floor_z, (d−D_shelf)/(D_slope−D_shelf)) (`D_slope == D_shelf` → floor_z); `d > D_slope`: floor_z. Целочисленно, монотонно по `d`, всегда `floor_z ≤ z ≤ top` |
| `terrain/reliefObjects/bathymetry/basinZ.py` | `apply_basin_z(heightmap, specs, topology, *, reserved: frozenset[Coord]) -> int` (число записанных клеток). Для каждого spec эффективный footprint = `footprint − reserved`; пустой → spec пропускается с debug-логом. Specs обрабатываются в порядке `source_uid`; запись абсолютная; при перекрытии footprint (permitted overlap) клетка получает `min` из профилей; клетки footprint вне `heightmap.surface_z` — ошибка входа (footprint уже canonical на рабочей сетке). Идемпотентно: повторный вызов на том же входе не меняет z |
| `terrain/reliefObjects/mountainZ.py` | `apply_mountain_z` возвращает `frozenset[Coord]` поднятых клеток вместо счётчика (единственный caller — `applyReliefObjectsZ`; лог использует `len`) |
| `terrain/reliefObjects/applyReliefObjectsZ.py` | `+ basin_specs: Sequence[BasinSpec] = ()` и `topology: WorldTopology \| None`; порядок `mountainZ → ravineZ → basinZ(reserved=raised)`; без specs поведение прежнее |
| `dataModel/topology/topologyGeometry.py` | `+ canonical_neighbors4(topology, cell) -> tuple[Coord, ...]` (4 соседа через `topology.neighbor`, `None` отброшен); `placement/adapters/coastlineShape.cell_neighbors` переводится на него (один helper, не два) |
| `application/worldData/placement/adapters/waterTypes.py` | `PreparedWaterEntry += floor_z: int` (правило floor остаётся в adapter, factory не дублирует) |
| `generators/hydrology/basinSpecFactory.py` | `basin_specs(preparation: WaterPlacementPreparation, records: Sequence[ResolvedWaterPlacement], hydrology: WorldHydrology) -> list[BasinSpec]`: entry по `source_uid`; `floor_z` с entry; `bands` = `source.rim` у `DeclaredBasin` при наличии, иначе `default_lakes.bands` для `lake` и `default_seas.bands` для остальных; footprint = `record.footprint_cells`. Без физики, без z |

Тесты 3a (`tests/test_bathymetry_basin_z.py`, `tests/test_basin_spec_factory.py`): профиль — монотонность, `z < level` при `d ≥ 1`, `floor_z` при `d > D_slope`, bowl vs shelf, `D_slope == D_shelf`, `depth = 0`; distance field — planar и wrapped (footprint через x-шов: `d` одинаков по обе стороны шва), footprint без границы; basinZ — абсолютная запись/идемпотентность (двойной вызов), перекрытие двух specs → min, reserved-клетки горы внутри footprint не трогаются (остров сохраняет свою высоту, соседние клетки получают `d=1`); factory — floor/bands по kind и `DeclaredBasin.rim`. Регрессии: `test_water_placement_adapter`, `test_terrain_*` на `apply_relief_objects_z` без specs.

**Отчёт 3a (2026-10-21):** реализованы `reliefObjects/bathymetry/{basinSpec,distanceField,floorProfile,basinZ}.py`, `hydrology/basinSpecFactory.py`, `BasinKindProfile`/`basin_kind_profile`, `topologyGeometry.canonical_neighbors4` (coastline adapter переведён на него), `apply_mountain_z → frozenset` поднятых клеток, `apply_relief_objects_z(+basin_specs, +topology)` с порядком mountain → ravine → basin(reserved); `PreparedWaterEntry += floor_z`. Pipeline не подключён, поведение мира без specs неизменно. Тесты: `test_bathymetry_basin_z` (13), `test_basin_spec_factory` (5); regression-набор placement/hydrology/topology/relief — 127 OK; compileall, diff-check. Границы distance field: planar — граница footprint только от суши (за краем мира соседа нет — логично); wrapped/sphere — непрерывно через шов/полюс через `topology.neighbor`, отдельного кода нет (подтверждено мастером).

**3b — wiring + cutover (отдельный заход после приёмки 3a):**

- `terrain/passes/surfaceTerrainContext.prepare_surface_terrain_context`: после `run_surface_pass_coarse`, до `apply_relief_objects_z` — новый pure-helper `hydrology/placement/prepareWaterPlacementPass.py` (имя уточнить при 3b): `hydrology(world)` → проекция declare на coarse (`project_hydrology_to_grid(hydrology, map_cell, topology)` — waypoints, `RegionShape.projected`), `WaterPlacementContext(world_uid, snapshot_uid, topology=resolve_hydrology_topology(world, coarse_hm, locations), surface_z=dict(coarse_hm.surface_z), z_min=world_z_min, anchors=пины geographic-локаций fine→grid, location_subtypes=по geographic-локациям, auto_specificity=по решению 2, dependencies/overlaps/separations={})` → `prepare_water_placements` → `resolve_placements(PlacementBatch(phase=pre_relief, accepted=()))` → `resolved_water_placements` → `basin_specs` → `apply_relief_objects_z(..., basin_specs=…, topology=…)`. Unresolved/failures — существующие sinks (runtime `WarningError`, validate_only report), без reject прохода.
- `snapshot_uid = entity_uid(world_uid, UidKind.TERRAIN_SNAPSHOT, phase="pre_relief")` — новый member `UidKind` (DET-1), не строковая формула.
- Cutover legacy z-записи для declared источников: `generate_lakes` больше не carve'ит `declared_lake_specs` (цикл удаляется; `LakeSpec` остаётся до снятия типа в шаге 4); `carve_deepening_bands` для declared coastline — role-only (z не пишет; роли/deepening до шага 4 остаются legacy). Autoresolve-ветки (`proceduralSeaAutoresolve`, `oceanBasinGenerator`, lake autoresolve) и `riverBedCarver` не меняются до шагов 4–5. Проверка: grep z-записей в `generators/hydrology/` — остаются только autoresolve/river; `world_test_004` smoke: бассейн `loc-geo-ocean-west-004` вырезан basinZ через x-шов, legacy его не перерезает.
- ТЗ-правки по решению 1 и 2 выполняются в 3b вместе с wiring.

**Отчёт 3b (2026-10-21):** реализовано — `HydrologyCategoryPolicy`/`HydrologySeasPolicy += placement_specificity` (`DefaultWhenMissing[int]`, ≥0, default 0); `RegionShape.projected(divisor)` на всех конкретных формах (координаты `v // divisor`, размеры `max(1, round(v/divisor))`, `edge_noise` масштабируется, `divisor <= 0` → ValueError, коллапс → `ValidationError`); `hydrology/placement/{__init__,projectDeclaredHydrology,waterPlacementPass}.py` — проекция declare fine→coarse на границе caller с drop+issue на коллапс (path `hydrology.<collection>.<index>`, code `WATER_PLACEMENT_GEOMETRY`), `run_water_placement_pass` (topology → anchors/subtypes/auto_specificity из `default_seas|default_lakes.placement_specificity` → prepare → `PlacementBatch(phase="pre_relief")` → resolve → `basin_specs`); `UidKind.TERRAIN_SNAPSHOT`; wiring в `prepare_surface_terrain_context` (после `run_surface_pass_coarse`, до `apply_relief_objects_z`, `basin_specs`+`topology` из `WaterPlacementPassResult.topology`). Cutover: `generate_lakes` не carve'ит declared (`declared_lake_specs`-цикл снят), `carve_deepening_bands` → role-only (`_apply_carve` z-запись снята; единственный caller). grep `surface_z[` в `generators/hydrology/`: остались `proceduralSeaAutoresolve`, `oceanBasinGenerator`, `riverBedCarver`, `fineHydrologyIndex`, `lakeBasinGenerator.carve_lake_interior` (autoresolve только). Изменённые legacy-asserts: `test_hydrology_hy2` (deepening-carver role-only — z не меняется), `test_hydrology_hy6` (coastline carver — z не меняется), `test_hydrology_hy11` (declared carver — z не меняется), `test_hydrology_coarse_space` (declared lake — legacy apply путь больше не выдаёт LAKE-клетки, carve/роль в pre-1.4 pass). Тесты: `test_water_placement_pass` (5, включая world_test_004 через x-шов и детерминизм), regression-набор 319 OK; compileall чистый.

**3b follow-up — дубль `location_uid` (решение мастера 2026-10-21, A+B):** fixture `world_test_004` возвращён к намеренному дублю basin+coastline `loc-geo-ocean-west-004` как edge case и не чинится. Import-валидация отклоняет дубль через REF-W (code `WATER_IDENTITY_DUPLICATE`, `FieldPathError` на обе записи); runtime `prepare_water_placements` сливает группу одинаковых UID в один entry (footprint = union клеток, primary `basin > coastline > lake` с tie по порядку объявления, `kind`/`liquid`/`level`/`floor`/`specificity` от primary) с одним `WarningError` `WATER_PLACEMENT_MERGED_SOURCES` через `log_issues` (validate_only ctx — `report_issues`). Полный контракт — `generator-placement.md` § «Дубль `location_uid` declared water».

### Шаг 4 — level fill + компоненты + derived shore (реализован 2026-10-21)

**Начальный срез до согласования identity (исторический отчёт 2026-10-21).** Добавлены независимые read-only модули
`water/{levelFill,componentLabel,waterClassifier,shoreDerive}.py` и unit-проверки
`tests/test_hydrology_level_fill.py` (8 tests). Проверены strict waterline,
неизменность z, 4-связность, wrapped x-шов, sphere-fold, отказ на неполных
данных борта, сохранение authored kind и ocean-классификация по уровню/массе.
Вместе с `test_bathymetry_basin_z` и `test_basin_spec_factory`: 23 tests OK.
На момент начального среза pipeline ещё не переключался; финальный отчёт шага 4 ниже.

Решения мастера 2026-10-21 и оставшийся контракт перед resolver:

1. Мастер выбрал **сначала согласовать UID родителя**. Вариант physical-факта
   с `parent_system_uid=None` до W/L не принят; согласованный identity-контракт реализован ниже. Основа согласована после уточнения lifecycle участников: общий DET-1
   `entity_uid(world_uid, UidKind.WATER_SYSTEM, change_uid=change_uid,
   members=state_fingerprint(tuple(sorted(member_uids))), system_kind=kind)`, где member_uids —
   уникальные UID конечных участников физического union; change_uid — обязательная
   identity операции от общего lifecycle/application caller. Новый WATER_SYSTEM
   tag и формула общие для W/HY, не локальная identity внутри генератора.
   Одинаковая операция/состав даёт тот же UID; новый merge после split получает
   новый change_uid и новый UID даже при прежнем составе. Уровень, объём и порядок
   обхода не входят в identity. UID ребёнка/предшественника не заменяется UID
   родителя. Различение PHYSICAL_MERGE/CONNECTED и bootstrap operation зафиксированы в ТЗ и общем app/ids adapter; stateful change caller остаётся W/L.
   Согласованная основа identity, bootstrap и различение видов реализованы; durable runtime-operation journal остаётся L/W. Это не разрешение реализовать весь W/L. Члены сохраняют собственные UID и lifecycle; вступление в union не завершает их lifecycle. При merge/split историзируются замещаемые родители, а lifecycle сохранившихся участников продолжается.
2. **Принято:** мировой planar-край открытого океана держит `default_water_level`;
   остальные бассейны сохраняют void-слив. Уточнение внесено в
   `tz_terrain_hydrology` § Компоненты и уровни. Подводный океанский край
   `z=-10`, default=0 остаётся водой; `z=0` остаётся сушей. Для natural-only
   ocean-кандидата это входное граничное условие default-level resolve, не
   восстановление воды после ошибочного void-слива. Край частичного bake не
   получает океанского/void условия. Wrapped/sphere швы не меняются.

| Поле | Содержание |
|---|---|
| Цель | вода/берег/класс — следствия elevation, не paint |
| ТЗ | раздел из шага 1 |
| Файлы | `hydrology/water/` — `levelFill.py`, `componentLabel.py`, `waterBodyResolver.py`, `waterClassifier.py`, `shoreDerive.py` (новая подпапка); `basins/seaBasinGenerator.py`/`oceanBasinGenerator.py` (замена flood → делегация в water/), `basinKindResolver.py` → `waterClassifier`, `waterSideFootprint.py` (уходит в rim declared coastline) |
| Контракт | BFS `z < z_water_level(component)` через `topology.neighbor`; components labeling; merge/spill — по § «Алгоритм разрешения уровней»; классификация по шагу 1; `SHORE` = land-сосед воды; `water_body_uid` из компоненты/declare |
| Проверка | unit: planar/ wrapped-классификация, `z = z_water_level` суша, компонента < min_size = puddle; регрессия `test_hydrology_hy2/hy5a` (переписать на carve→fill — отмечено в HY-8) |
| Done | `neighbors4`-flood морей заменён level-fill; классы водоёмов корректны на wrapped |

**Финальный отчёт шага 4 (2026-10-21).** Реализованы `water/{depressionTree,componentLabel,levelFill,waterSources,waterBodyResolver,waterMaterialize,waterClassifier,shoreDerive,waterDiagnostics}.py`, `waterBodyAssembler`, общий DET-1 adapter систем и `PhysicalWaterUnion`. Production facade переведён на один post-carve проход, `surfaceTerrainContext` передаёт исходные specs/topology из pre-1.4 placement. Body-проход z не пишет; реки пока legacy (шаг 5). Natural-only sources — существующие впадины, без синтеза океанского дна. Priority elevation hierarchy с атомарными plateaus, frontier bags small-to-large, physical nested merge/effective cascade и final strict fill; puddle без WaterBody/ролей, сухой shore с уровнем/UID; неполный snapshot — общий unresolved sink. Старые standalone body/geometry helpers не подключены к production и сохранены для historical regression; их полное удаление/остаточные z-writes учитываются в финальной cleanup-приёмке трека, не маскируются как новый путь.

Финальная проверка: 344 tests OK (hydrology, placement, bathymetry, relief, pack bake, topology, DET-1 и terrain); compileall и git diff --check чистые. Дополнительно проверены постоянство planar ocean reservoir после позднего merge, повторное вычисление общего UID при нормализации auto-anchor и сохранение раздельных низких карманов одного declared footprint после spill. `world_test_004` offline: общие placement→relief→fill, водные клетки по обе стороны wrapped x-шва, на них z<effective level и UID тела, re-bake даёт одинаковые z и гидроиндекс. Проверены вложенный каскад, spill union, dead-end/плоский sill, сужение extent при понижении уровня, отсутствие merge через сухой sill, puddle, mountain island, совпадающие declared identities, dry/refill operation identity и различение system kind. Шаги 5–6, backend/HTTP smoke, W/L runtime/history/persist и HY-10 этим не закрыты.

**Уточнение границы HY-12 ↔ W/L (принято 2026-10-21).** Пересыхание — состояние сохраняющегося водоёма, не завершение его lifecycle: UID, котловина и authored-данные сохраняются, мокрый footprint пуст. Отсутствие WaterBody/open-water ролей в результате fill не означает уничтожение durable-объекта. Текущие водные связи подтверждаются producer заново; старое русло не доказывает связь. Изменение состава/merge/split перевыпускает родительские системы с историческими ссылками, сохраняя lifecycle участников. Повторное наполнение возвращает тот же объект; восстановленная система имеет новый UID и не реактивирует историческую исходную. Подробный контракт и сценарий «три озера + речка → засуха → восстановление» закреплены в `tz_terrain_hydrology` § «Пересыхание и восстановление водоёма» и W0/W1/W2/W3; runtime-состояние/история не объявляются реализованными шагом 4 HY-12.

### Шаг 5 — реки: устье на waterline + topology leftover (реализован 2026-10-21)

| Поле | Содержание |
|---|---|
| Цель | устье = `z < z_water_level` ИЛИ open-water роль; `_neighbors8` → домен (TOPO-1 leftover); bed carve — через relief spec (река = потребитель); факты перепадов z для `waterfalls/` |
| ТЗ | раздел из шага 1; TOPO-1 строка «↳ реки» |
| Файлы | `rivers/riverNetworkPlanner.py`, `rivers/riverBedCarver.py` → эмиссия `RiverBedSpec`; `terrain/reliefObjects/riverBed/` (`riverBedSpec.py`, `riverBedZ.py`); `dataModel/topology/topologyGeometry.py` (`neighbors8_unrolled` при отсутствии) |
| Проверка | unit: река доходит до carved-бассейна и кончается на waterline; река через x-шов на wrapped |
| Done | `_neighbors8` в гидрологии — 0; устье не зависит от порядка записи ролей |

**Отчёт шага 5 (2026-10-21).** Добавлены shared `neighbors8_unrolled`/`canonical_neighbors8`, локальная развёртка поворотов (wrapped/sphere), multi-source D8 distance-to-mouth; локальные истоки читают topology-соседей post-carve snapshot. Устье = open-water роль либо strict `z < z_water_level` только при body UID в resolved индексе; dry shore путь не блокирует. Сеть/declared paths обрезаются по первому принимающему телу, его дно сохраняется. `riverNetworkAssembler` собирает все профили на одном pre-bed snapshot, `RiverBedSpec` переносит абсолютные z в единственный relief writer `riverBedZ`, затем выдаются роли/факты перепадов. Классификатор больше не выбрасывает вершины; `waterfalls/riverDrops` отдаёт typed `WaterfallDrop` в `HydrologyResult.waterfall_drops`, на устье нижний уровень — waterline, не дно. Это физические факты для waterfall-потребителя; игровой render/persist и sill/authored-drop producers этим не закрыты.

Fine caller мигрирован на тот же relief writer. Обнаруженный coarse-вход в fine helper теперь явно обозначен `base_space`; z выбирается только для declared fine-клеток из pre-river coarse snapshot, без выдуманного нуля и повторного углубления. Принимающая вода защищена coarse индексом. Standalone APIs сохранены тонкими совместимыми обёртками. ТЗ содержит контракты новых полей и opaque edge UID; строка «↳ реки» TOPO-1 закрыта.

Проверки: расширенная регрессия **449 tests OK**, включая hydrology/placement/bathymetry/topology/terrain/relief objects/pack bake/DET-1 и SQLite schema. После финальной защиты pre-river snapshot — **43 tests OK** затронутого пути. Новый `test_hydrology_hy12_rivers`: **10 tests** (role-independent waterline, strict equality/низина без body, wrapped turn, sphere fold, tiny-world D8, абсолютный negative-z профиль/replay, сохранение дна и drop, carve→fill→dry shore→river, fine sampling, отсутствие двойного carve). Sandbox temp/SQLite ограничения обойдены разрешённым прогоном вне sandbox, не изменением тестов. compileall и diff-check выполнены; backend не запускался, коммит не создавался. Шаг 6/coarse-приёмка всего трека, legacy cleanup, W/L и HY-10 открыты.

### Шаг 6 — coarse smoke + приёмка физической гидрологии (выполнен 2026-10-21)

| Поле | Содержание |
|---|---|
| Цель | подтвердить физические footprint, дно, уровень, воду и derived shore, включая шов |
| Файлы | `fixtures/world_test_004.json` (+ declared basin), `light_and_full_bake.py --render` |
| Проверка | coarse heightmap + hydro index: footprint, z дна/уровня, water_body_uid, роли, derived shore, wrapped/sphere seams; re-bake детерминирован. HTTP smoke — только на backend, поднятом пользователем. L0 render — дополнительная диагностика до HY-10 |
| Done | coarse данные подтверждают carve → fill → shore → river mouth; warnings соответствуют дегенератам. Полнота L0 bands и динамический lifecycle не объявляются выполненными |

**Отчёт шага 6 (2026-10-21).** Добавлен offline `backend/scripts/smoke_hydrology_hy12.py --render`: без БД/HTTP запускает production `prepare_surface_terrain_context` на fixture и проверяет replay физических фактов. `world_test_004`: 11 water + 10 dry shore, `loc-geo-ocean-west-004` и effective level сохранены на wrapped-шве; reserved-горы остаются сухими. Expected warnings: `WATER_PLACEMENT_CAP_REACHED` и `WATER_PLACEMENT_MERGED_SOURCES` (намеренный дубль basin+coastline). JSON/SVG: `.local/map-render/hy12-coarse/{acceptance.json,coarse.svg}`.

Удалены standalone sea/ocean/lake generators, procedural bbox-edge sea/lake carvers, `deepeningBandCarver`, `basinKindResolver`, `lakeSpecs` и interim bathymetry stub/knob. L0 `coarseOpenWater` только копирует готовую coarse-высоту, без собственной батиметрии и без clamp высокого озера к ocean-default. `riverBedCarver` оставляет spec/role эмиссию; fine caller сначала собирает все profiles на общем snapshot, затем применяет relief writer, сохраняя пересечения без двойного углубления. `proceduralRiverAutoresolve` сохранён по HY-RIV-1; waterfall product — HY-WF-1.

`LakeSpec`/`declared_lake_specs` сохраняются только как geometry-only compatibility для pack tile collection/L0 до HY-10: без `open_water_role`, kind resolver или carve. Это следует условию снятия типа «после миграции callers», не объявляет HY-10 выполненным. `DeclaredLake` wire и его P3 adapter остаются. Геометрические HY-6/HY-11 проверки переведены на retained `waterSideFootprint`, paint/bbox-edge assertions заменены актуальными placement/strict fill/natural-only/identity проверками; legacy river tests явно применяют spec → relief → roles.

Проверки: **523 tests OK** (hydrology/landcover/topology/placement/bathymetry/terrain/pack bake+wire/DET-1/SQLite schema). Новая coarse acceptance покрывает basin/lake/coastline, wrapped/sphere, planar reject без clipping, сухой shore, river waterline с сохранённым дном, duplicate fine river intersection; hash-seed `0/1/42` сравнивает полный fixture snapshot. Для существующих SQLite/tempfile тестов использован разрешённый прогон вне sandbox; для межтестовых импортов — `PYTHONPATH=backend;backend/tests`. Compileall/diff-check и статический аудит writer/legacy-call/raw-neighbor выполнены. HTTP/full L0 bake не выполнялись; backend не запускался, коммит не создавался.

**Приёмка HY-12 завершена.** HY-8 семантически resolved; HY-BATH-1 partial: базовый basin profile готов, дополнительные DepressionSpec/Form/Kind ещё нет. HY-7/9/10, GEO-1, HY-RIV-1, HY-WF-1, W/L остаются открытыми. Упоминания cap `bands.max` в раннем проекте этого плана исторические и заменены решением мастера шага 3: reserved mountains + widths-only bands.

## Приёмка трека

- `python -m unittest` — hydrology + landcover + topology наборы, без новых падений относительно baseline;
- `python -m compileall` changed modules; `git diff --check`;
- grep: `neighbors4`/`_neighbors8`/`dist_euclidean` в `generators/hydrology/` → 0;
- долг HY-12 → resolved, план → `-done`; статусы HY-8 (семантика реализована), HY-BATH-1 (форма переиспользована) обновлены;
- шаг за заход, отчёт после каждого; backend не стартовать агентом; не коммитить.

## Связанные планы и долги

| Артефакт | Связь |
|---|---|
| [hy-11-topology-domain-geometry-done.md](hy-11-topology-domain-geometry-done.md) | prerequisite — домен даёт neighbor/metric/canonicalize для footprint и fill через шов |
| [topo-1-domain-consumers.md](topo-1-domain-consumers.md) | родительский трек; строка «↳ реки» закрывается шагом 5 |
| [hy-6-coastline-water-side-done.md](hy-6-coastline-water-side-done.md) | prerequisite ✅ — water-side для rim у declared coastline |
| [coastline-forms.md](coastline-forms.md) | HY-9 — формы береговой линии поверх; footprint edge_noise переиспользует RegionShape |
| HY-8 | семантика carve→fill→shore — реализуется внутри шагов 3–4 |
| HY-BATH-1 | DepressionForm — vehicle формы footprint; Scope A снят (решение в долге) |
| HY-7 | гора × борт — следствие cap `bands.max` (карв не прорезает) + warning; precedence — после HY-12 |
| GEO-1 | designed water — процедурный океан через общий Placement resolver + continental-поле; **вне** этого плана (autoresolve здесь = classify-only) |
| HY-10 | band→L0 — после того как роли/индексы появятся из fill (не раньше) |
