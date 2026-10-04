# ТЗ: каскадный резолв параметров локаций — `LocationContext`

Отдельное доменное ТЗ. Доменный контракт: как параметры с семантикой
«null → наследует от предка» попадают к консьюмерам без ручной проводки
на каждом уровне. Связанные ТЗ: [tz_locations.md](tz_locations.md)
(поля `named_locations.*`), [tz_economic_tier.md](tz_economic_tier.md)
(§4 — каскад тира, сегодняшний частный случай),
[tz_building_generator.md](tz_building_generator.md) (§8.7.1 —
consumer resolved-контекста).

---

## 1. Зачем отдельный механизм

Каждый параметр с каскадной семантикой сегодня протаскивается по цепочке
предков **вручную, отдельным кодом на каждом уровне и в каждой точке
вызова**. Это даёт повторяющийся класс багов: звено цепочки можно забыть,
и механизм молча деградирует до дефолта.

Фактические сбои на 2026-10 (аудит call sites, факт кода):

- `system_economic_tier` никогда не записывается на district/building/room
  NL — authored-канал поля жив только на settlement;
- `structureGeneratorService` вызывает `TierResolver` 4 раза на здание
  (rooms, shafts, passages, openings) без district/city, с rng;
- дополнительно тир резолвится **per room** (`materialResolver.
  resolve_room_materials`) и **per opening** (`wallOpening.glass_tier`),
  каждый со своим rng — возможны разные тиры внутри одного здания;
- канал `template_tier` **мёртв**: `roomFactory` всегда передаёт
  `template_tier=None`, `PlotLayoutTemplate.economic_tier` нигде не
  читается — до структуры доходит только `economic_tier_band`;
- `DistrictTemplateEntry` имеет только `economic_tier_range`, district NL
  создаётся без тира; building NL пересоздаётся в `_place_building` при
  каждом assemble — без `parent_location_uid` и `system_economic_tier`;
- `parent_wall_material` / `parent_floor_material` резолвятся ad-hoc
  `or`-цепочками в точках потребления (`structureGeneratorService`,
  `foundationBuilder`, `roofBuilder`), без цепочки и без единого дефолта.

Дальнейшие каскадируемые параметры — это не единицы, а доменное
пространство: расы/виды населения, культура, язык, религия, фракция;
морфология и density поселения; доминирующие материалы и палитры;
климатические якоря, flora/livestock-профили; торговый профиль, валюта;
law/customs, magic/tech level. Порядок — 15–25 параметров, все с той же
семантикой «authored → наследует → default». Каждый будет воспроизводить
те же ошибки, если проводить руками. Поэтому каскад — **инфраструктура,
а не логика параметра**: цепочка строится механически, консьюмеру
недоступно «забыть звено».

---

## 2. Каскадная цепочка и полиморфные звенья

Каноническая цепочка (решение мастера 2026-10-03):

```
world → settlement → district → area → building → room
```

Критерий уровня — **собственные потребители параметра** (городские стены
и дороги, дороги/стены района, забор и двор участка, структура, материалы
комнаты), а не наличие authored-поля. Иерархия зафиксирована enum'ом
`ScopeLevel` (`dataModel`) — она в контракте, не в голове caller'а.

`ScopeLevel` — **локационная ось**, не «ось вообще»: каждый домен со
своей иерархией scope'ов (фракции, магия, эры) объявляет собственный
enum на базе `ScopeAxis` (StrEnum-миксин с `rank`). Каскад — механизм
поверх **любой** оси: параметр привязан к своей через `Cascade.axis`
(`ECONOMIC_TIER.axis is ScopeLevel`), канал на чужой оси — ошибка
контракта. Новый параметр на локационной оси (race_mix, культура) —
новая аннотация поля без правок enum'а; новый домен — новый enum оси.

**Уточнение мастера 2026-10-03: связь полей, а не реестр типов.**
Строковый `ScopeLevel`, независимый `cascade_value(field: str)` и
таблица «уровень → типы POJO» не обеспечивают связь объекта с контрактом:
`ScopeLevel` — **чистая ось порядка** scope'ов и не знает, какие модели
кормят уровень (источники различаются между параметрами: district может
давать `economic_tier` из одного POJO, а `race_mix` — из другого).

Контракт — **двусвязный список полей**, объявленный на самих
полях-источниках, в том же стиле, что wire-политики (`DefaultOnWire`):

- `CascadeChannel(param, level, above, below, kind)` — метаданные в
  `Annotated` поля-источника: «это поле — канал параметра `param` на
  уровне `level`»;
- `param` — **сам объект `Cascade`** (объявлен единожды в
  `cascadeParams`), связь по identity, не по строке; переименование
  константы ломает импорт, а не деградирует в наследование;
- `above` / `below` — `CascadeLink(model, field, level)`: типизированные
  указатели на соседние узлы (`prev`/`next` связного списка); порядок
  внутри уровня и между уровнями задаётся рёбрами, а не скрытым
  порядком таблицы;
- **каждое ребро объявляется ровно один раз** — на той стороне, чей
  модуль может импортировать соседа без циклического импорта
  (POJO-граф уже переплетён: NL↔Skeleton↔Plot); проверка контракта
  достраивает обратное направление — как ORM `backref`, в проверенном
  графе у каждого узла известны оба соседа. Дублированная декларация
  одного ребра с двух сторон допустима только если согласована —
  рассогласование есть ошибка контракта;
- `model=None` в `CascadeLink` — ссылка на собственную модель (класс
  не может сослаться на себя внутри своего тела);
- проверка контракта проходит по рёбрам: имя поля резолвится в
  `model_fields` указанной модели, типы концов совместимы (kind-aware:
  `VALUE`↔`VALUE` один базовый тип; `BAND`/`RANGE` — входы materialize),
  ребро соединяет только узлы одного уровня или соседних рангов,
  цепочка непрерывна от верха до world (один top, один bottom,
  без ветвлений и сирот).

Изменение/удаление поля или несовместимое изменение его типа должно
обнаруживаться проверкой контракта, а не превращаться в `None`,
наследование или median. «У модели нет канала» и «объявленное поле имеет
значение null» — разные состояния. Звено проверяется по своим
метаданным («объявляет ли тип канал для этого уровня»), не по
isinstance-таблице: новый POJO-тип становится валидным звеном просто
аннотировав поле.

Wire-политика (`StrictOnWire`/`DefaultOnWire`/`IgnoreOnWire`)
ортогональна каскаду: она — политика импорта, к моменту резолва уже
отработала; движок читает готовое значение поля POJO.

Runtime `DistrictSlot` остаётся объектом application: связь с данными
района проходит через его typed `DistrictTemplateEntry`. Ссылки из
dataModel на application/db не вводятся; преобразование
persistence/runtime объектов к исходным POJO — обязанность границы
caller, а не движка каскада.

Соответствие уровней объектам и каналам тира (частное → общее):

| Уровень | Звено | Каналы тира | NL / stamp |
|---|---|---|---|
| world | `World` | — (root пустой, без materialize/default) | — |
| settlement | city `NamedLocation` / `SettlementSkeleton` | `system_economic_tier` / `economic_tier` | да / **да** |
| district | `DistrictSlot` + `DistrictTemplateEntry` | `economic_tier_range` (materialize) | да / **да** |
| area | `AreaSlot` + `PlotLayoutTemplate` | `economic_tier` → `economic_tier_band` → `economic_tier_range` | нет (transient) / — |
| building | building `NamedLocation` (+ `BuildingBodyTemplate`, своего тира нет) | `system_economic_tier` | да / **да** |
| room | `RoomDef` / `_RoomInstance` → room `NamedLocation` | `rooms[].economic_tier` | да / **да** |

**Звено цепочки — `{level, obj}`** без собственной логики чтения:
движок сам проходит каналы типа объекта по `CascadeChannel`-метаданным.
`EmptyLink(level)` (`obj=None`) — явное пустое звено для caller'ов без
объекта уровня (debug-роут) — уровень не пропускается молча.

Граница scope — точка, где появляется новое звено: world import/skeleton →
settlement assemble → district → area/building → structure generate
(room). Caller знает только свои звенья, не чужие.

---

## 3. `LocationContext` и аннотация `Cascade`

Механизм — домен-нейтральный пакет `dataModel/cascade/`
(`cascadeSpec` — словарь объявлений, `cascadeGraph` — интроспекция и
упорядочение графа, `cascadeVerify` — целостная проверка). Домен
объявляет только своё: ось (`ScopeLevel`), параметры (`cascadeParams`),
контекст и каналы на полях — `dataModel/locations/context/` рядом с
`namedLocation/`.

Контракт — конкретная typed Pydantic-модель `LocationContext`. Каждый
каскадируемый параметр — **поле модели с `Cascade`-метаданными в
`Annotated`**, объявленное один раз, рядом с типом:

Параметр объявляется **один раз** — объектом `Cascade` в
`cascadeParams` (dataModel домена). Поле контекста и все каналы-источники
ссылаются на **тот же объект**: связь по identity (`is`), не по строке.

```python
# cascadeParams.py
ECONOMIC_TIER = Cascade(
    field="system_economic_tier",         # каноническое authored/stamp-поле
    default=DefaultPolicy.REGISTRY_MEDIAN,  # median + WARNING
    axis=ScopeLevel,
    input_types=((ChannelKind.RANGE, EconomicTierRange),),
)

class LocationContext(ContextModel):
    level: ScopeLevel
    economic_tier: Annotated[EconomyTierKey | None, ECONOMIC_TIER] = None
    # будущие поля — та же форма:
    # wall_material: Annotated[MaterialKey | None, WALL_MATERIAL] = None
```

| Элемент `Cascade` | Назначение |
|---|---|
| `field` | Имя канонического authored/stamp-поля параметра (`system_economic_tier`, `parent_wall_material`, …) — объявлено один раз, проверяется верификатором против `model_fields` источников |
| `default` | `DefaultPolicy` — ссылка на **политику POJO** (`REGISTRY_MEDIAN`, `CANONICAL_DEFAULT`, `NONE_IS_ERROR`); реализацию держит POJO домена поля (для тира — `WorldEconomyTierRegistry`: median + WARNING). Callables и литералы в dataModel не живут — движок знает только, как вызвать политику с `world` (`dataModel-no-hardcode.mdc`) |
| `fold` | Опциональный полный per-param resolver — для параметров, которым first-non-null недостаточно (точечно, не режим движка) |
| `levels` | Опционально (v1 не использует): ограничение подмножества уровней для будущих полей (climate anchor и пр.); покрытие уровней каналами проверяется непрерывностью цепочки рёбер |
| `axis` | Ось scope'ов параметра (`type[ScopeAxis]` — для locations `ScopeLevel`); канал на чужой оси — ошибка контракта |
| `input_types` | Ожидаемый тип поля для materialize-kinds (`RANGE` → `EconomicTierRange`); kinds без записи — str-совместимые wire-ключи (`VALUE`, `BAND`) |

Materialize (band → tier, range → tier через rng) объявляется **не
callable в модели**, а привязкой по имени поля внутри `contextResolver`
— локальная привязка движка, не публичный реестр; `materialize_band`
остаётся в application.

`ScopeLevel` — enum (`world, settlement, district, area, building,
room`), порядок значений = иерархия; `ctx.level` — уровень текущего
контекста.

Новый каскадируемый параметр — **новая аннотированная строка в модели**,
не resolver-класс, не запись в стороннем реестре и не копия каскада в
сервисе. Метаданные живут у поля: тип, источник, дефолт видны в одном
месте.

**Режим v1:** `first-non-null` по цепочке + опциональный `materialize`.
Сложная семантика — только через `fold` конкретного параметра; режимов
движка «merge/accumulate» нет и не вводить.

---

## 4. Движок — `extend()`

Движок — один generic-walker в новом cross-domain слое
`application/worldData/context/` (сосед `generators/`, `pack/`,
`render/`). Не `generators/utils/`: цепочка включает settlement/district
уровни, это инфраструктура резолва world data, а не утилита одного
генератора.

Контекст распространяется **вниз по существующему потоку генерации** —
walker'а вверх по `parent_location_uid` нет: каждый assembler уже знает
своего родителя, он его сам создал:

```
settlement_ctx = extend(LocationContext.root(world), settlement_link)
district_ctx   = extend(settlement_ctx, district_link)
area_ctx       = extend(district_ctx, area_link)
building_ctx   = extend(area_ctx, building_link)
room_ctx       = extend(building_ctx, room_link)   # rooms[].economic_tier и т.п.
```

`extend(ctx, *links, rng)`:

0. **Валидация уровня:** все звенья одного `link.level`, строго ниже
   `ctx.level`; пропуск уровня и повтор уровня — **ошибка** (повтор =
   второй резолв на scope). Ось звена обязана совпадать с осью ctx.
   Caller без объекта уровня передаёт `EmptyLink(level)` явно.
   `check_link` подтверждает, что тип объекта объявляет канал для этого
   уровня — таблицы типов нет.
1. Проходит по полям `LocationContext`, читает `Cascade`-метаданные.
2. Для каждого параметра движок идёт по **связному списку полей**
   (`ordered_chain(param)`) — но только по узлам нового уровня:
   first non-null `VALUE` побеждает; `BAND`/`RANGE` materialize
   **на месте узла** с якорем = унаследованное значение родительского
   ctx; `None`-канал — пропуск, не отсутствие.
3. Ни один узел уровня не дал значения → наследуется значение
   родительского ctx (оно уже свёрнуто с узлами пройденных уровней).
4. Совсем пусто (нет authored и нет наследия) → `default` через
   `DefaultPolicy` POJO. Default-source **не является якорем** для
   materialize ниже и не предупреждает повторно — он provisional.
5. Возвращает **новый замороженный** `LocationContext` с новым `level` +
   provenance: `ctx.provenance[param] = (axis member, "Model.field"
   | "default:<policy>")` — какой уровень/канал дал значение.

Звено — `Link(level, obj)`: caller сам конвертирует runtime/persist
объект в source-POJO до вызова; движок не знает имён полей — только
граф каналов. Именно per-scope резолв (узлы уровня ходятся ровно на
его границе) делает materialize **однократным**: band на area
materialize-ится на границе area и никогда не перебрасывается
более глубокими scope.

**Семантика materialize тира:** порядок каналов на уровне
`economic_tier` → `band` → `range`. Range разворачивается как
**ближайший к унаследованному тиру (anchor)** внутри `[min, max]`; если
унаследованного нет (включая provisional default) — rng внутри range.
`materialize_band` — anchor-предпочтение ближайшего тира в band,
иначе rng.choice по tiers_for_band. Materialize без rng там, где он
нужен (нет anchor), — ошибка caller'а, не silent skip.

**rng:** единственный rng-вход контекста — materialize тира, **один раз
на scope**. rng подаёт caller, отдельный
`Random(_make_seed(world_uid, <scope_uid>, "tier"))` для каждого scope
с materialize (district, area, building) — rng не разделяется с
геометрией/размещением.

**Инварианты:**

- **Один резолв на scope.** Контекст строится один раз на границе входа в
  генерацию уровня (settlement → district → building) и передаётся вниз.
  Повторный резолв того же параметра внутри scope запрещён — именно он
  сегодня даёт rng-дрейф тира между фазами.
- **Консьюмер не резолвит.** Consumer читает `ctx.<param>` и не имеет
  доступа к цепочке, rng и реестру в обход контекста.
- **`root(world)` — пустой ctx уровня `world`**: у world нет authored
  тира, materialize/default на root не выполняется (WARNING на root
  недопустим).
- **Отсутствие значения после полного каскада + domain default — баг
  caller'а**, ошибка/exception, не молчаливый дефолт у консьюмера
  (то же правило, что для экономического контекста в §11.2
  tz_economic_tier).
- **Provenance обязателен** в контексте: WARNING «взято с уровня X /
  domain default» вместо silent median.

---

## 5. Параметры v1 и кандидаты на расширение

**v1 — архитектурно чистый движок + один тестовый параметр:**

| Параметр | `Cascade` | Источники по уровням | Domain default |
|---|---|---|---|
| `economic_tier` | `field="system_economic_tier"`, `default=REGISTRY_MEDIAN` | room: `rooms[].economic_tier`; building: NL поле; area: `plot.economic_tier` → `_band` → `_range`; district: `district_template.economic_tier_range` (materialize); settlement: NL поле / skeleton `economic_tier` | `median_system_tier` + WARNING (`DefaultPolicy.REGISTRY_MEDIAN`, POJO `WorldEconomyTierRegistry`) |

Каскад тира — полный: room → building NL → area (plot) → district
(range) → settlement → `REGISTRY_MEDIAN`. Мёртвый сегодня канал
`plot.economic_tier` оживает через area-звено — это целевой фикс, не
расширение.

Ширина покрытия не является целью v1 — важна чистота движка: один
параметр доказывает fold-семантику, provenance и одиночный rng-вход.
Остальные поля добавляются строками с `Cascade` без правок движка.

**Кандидаты на последующие поля (не scope v1):** `wall_material` /
`floor_material` (`NL.parent_*_material`, ad-hoc `or`-цепочки в
foundation/roof/structure), `city_size` (`skeleton.system_city_size or
settlement.system_city_size`), `dominant_material` (settlement →
building barriers fallback, tz_city §«Fallback»), `race_mix` /
`population_composition`, культура/язык/фракция, `settlement_density`,
climate anchor, торговый профиль/валюта, law/magic/tech level.

Каскад тира при миграции покрывает **всю** каноническую цепочку §2
(room → building → area(plot) → district(range) → settlement →
`REGISTRY_MEDIAN`), включая сейчас отсутствующие звенья area и district
в structure-вызовах.

---

## 6. Границы и не-scope

- **Persist — каждая NL цепочки получает stamped resolved тир**
  (решение мастера): settlement, district, building, room — при
  создании NL `system_economic_tier` = `ctx.economic_tier` (authored
  остаётся как есть; null → materialized/median → записывается).
  Area NL нет — transient. Поле на settlement становится
  authored-или-materialized: такие поля проще и правильнее хранить,
  общий тир города может меняться в обе стороны. Остальные параметры
  persist'ить запрещено: отдельных колонок у них нет, и вводить их —
  расширение schema, отдельное решение.
  **Перегенерация:** stamped-тир — первое authored-звено каскада →
  здание сохраняет тир между генерациями (тир — часть идентичности
  артефакта, детерминизм, повторного rng-materialize нет). Правки
  тира предков **не распространяются** на уже сгенерированные NL:
  перенаследование требует явного обнуления поля / отдельной политики
  re-materialize — вне scope v1, зафиксировано как доменное правило.
  **Поток чтения stamped (принято):** `_place_building` пересоздаёт
  building NL при каждом assemble — поэтому caller с репозиторием
  (packing job / persist service) читает существующий NL по
  `location_uid` и подаёт его в `structureAreaAssembler` первым звеном
  building ctx; stamped-значение из БД участвует в каскаде.
  Побочный баг (не scope): `_place_building` не ставит
  `parent_location_uid`.
- **Потребители district/settlement-уровня в v1 не переводятся на ctx**
  (решение мастера): барьеры, дороги, стены читают тир как сейчас (из
  `CitySkeleton`); v1 строит ctx и stamp'ит. Перевод — follow-up
  отдельным планом.
- **Судьба `TierResolver`:** после миграции его каскад становится fold'ом
  `economic_tier` внутри `extend`. Класс не удаляется в этом scope — на
  месте вызовов оставляется `# TODO: перенести на LocationContext` для
  последующей зачистки, когда будем готовы вычистить остальные
  call sites (settlementAssembler._build_skeleton и пр.).
- **Не трогает** резолвы внутри одного домена без родословной
  (materialResolver tier-fallback по `base_value` — это выбор из реестра,
  не наследование по цепочке).
- **Не вводит** новые authored-поля, override-флаги, wire-ключи.
- **Не переносит** orchestration в DAG — caller'ы остаются сервисами
  генерации; перенос точки сборки контекста в DAG — последующая задача.
- DAG-ноды не меняются (gate из project-context).

---

## 7. Связь с существующими планами

- `structure-wall-materials-done.md`: consumer политики материалов требует
  resolved экономический контекст (§11.2 tz_economic_tier) — этот
  механизм является его источником. Шаги S5–S6 того плана могут идти по
  transient-контракту, но production-подключение resolved-контекста
  корректно только после каскадного резолва building scope.
- Фикс «запись `system_economic_tier` на каждой NL цепочки при
  создании» — частный случай materialize-решения §6, решается в рамках
  этого механизма, а не отдельным ad-hoc присвоением.

---

## 8. Приёмочные кейсы (тестовый контракт)

Тесты строятся на **объектах dataModel** (`NamedLocation`,
`WorldEconomyTierRegistry`, skeleton/slot-модели), не на сырых dict —
поля, defaults и типы идут из POJO, иначе тест проверяет не контракт,
а литерал.

### 8.1 Null-звенья не блокируют; authored перебивает наследование

Цепочка каноническая — `city → district → area → building`
(для движка имена уровней безразличны — важен порядок частное → общее):

| Уровень | Значение |
|---|---|
| city | `medium` (средний) |
| district | `max` (максимальный) |
| area | отсутствует |
| building 1 | отсутствует → **ожидание: `max`** (ближайший non-null предок; null на area не блокирует) |
| building 2 | `medium` (средний) → **ожидание: `medium`** (authored сильнее наследования) |

Проверяет: пропуск null-звеньев, first-non-null по цепочке, explicit
сильнее наследования на любом уровне.

### 8.2 Полностью пустая цепочка → domain default

| Уровень | Значение |
|---|---|
| city | отсутствует |
| district | отсутствует |
| area | отсутствует |
| building | отсутствует → **ожидание: `median_system_tier` + WARNING** |

### 8.3 Единственный якорь на верхнем уровне

| Уровень | Значение |
|---|---|
| city | `low` (низкий) |
| district | отсутствует |
| area | отсутствует |
| building | отсутствует → **ожидание: `low`** (наследование с городского уровня) |

### 8.4 Persist и перегенерация

- При создании NL: building 1 из §8.1 получает
  `system_economic_tier = max` (stamped).
- Перегенерация того же NL: stamped `max` — первое звено → тот же тир
  без повторного materialize/rng; изменение тира district/city между
  генерациями **не меняет** stamped-значение.
- Поток чтения stamped NL принят: caller читает существующий building
  NL по `location_uid` и подаёт его первым звеном building ctx — без
  этого `_place_building` пересоздаёт NL и stamped-значение не
  доходило бы (§6).
