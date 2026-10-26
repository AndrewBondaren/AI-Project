# Каскадный резолв параметров локаций (`LocationContext`) — атомарный план ✅ DONE

Статус: закрыт 2026-10-16 — S0–S3 выполнены здесь; S4–S5 замещены `cascade-migration-done.md`. Дата проекта: 2026-10-03.
Приоритет: доменный контракт — [docs/tz_cascade_context.md](<E:/AI Project/docs/tz_cascade_context.md>).
Блокирует production-подключение resolved-контекста в
`structure-wall-materials-done.md` (S5–S6): consumer политики материалов
требует resolved экономический контекст здания, которого сейчас
пайплайн дать не может.

## Основание и границы

Каскад «authored → наследует от предка → default» сегодня размазан по
точкам потребления: `TierResolver` вызывается без district/city,
`system_economic_tier` не пишется на district/building NL, resolve
дёргается на здание 4 раза в фазах + per room + per opening, с rng
(возможны разные тиры в фазах одного здания), `parent_*_material`
резолвятся `or`-цепочками в трёх местах.

Аудит call sites `TierResolver` (2026-10-03, факт кода):

| Файл | Scope | Примечание |
|---|---|---|
| `structure/structureGeneratorService.py` ×4 (rooms, shafts, passages, openings) | building | с rng, без district/city |
| `utils/materialResolver.py` `resolve_room_materials` | room | per room, `room_tier`, с rng — фактически room-звено |
| `structure/passages/wallOpening.py` `glass_tier` | room | per opening, с rng |
| `settlementAssembler._build_skeleton`, `settlementGeneratorService.plan_slots_and_city_graph`, `settlementOutdoor/settlementOutdoorPackingJob` | city | только `city=settlement` |

Дополнительные факты, от которых зависит контракт:

- Канал `template_tier` **мёртв**: `roomFactory` всегда передаёт
  `template_tier=None`; `PlotLayoutTemplate.economic_tier` нигде не
  читается, в structure доходит только `economic_tier_band` через
  `StructureContext.building_band`.
- `DistrictTemplateEntry` имеет **только** `economic_tier_range`
  (ни tier, ни band); district NL создаётся в
  `settlementOutdoorExtract._district_named_location` без
  `system_economic_tier`. Решение мастера: district — уровень цепочки
  (свои потребители: дороги, стены), range — materialize-канал (см. S0).
- Building NL создаётся в `structureAreaAssembler._place_building`
  заново при каждом assemble: без `parent_location_uid`, без
  `system_economic_tier`, `parent_*_material` = `DEFAULT_*` литералы.
- Шов до структуры: `structureAreaAssembler → StructureContext.building_band
  → buildingAssembler → generate_from_template(building_band=)`; прямые
  вызовы также из `api/routes/debug.py` и `debugStructureRotations.py`.
- rng: `materialize_band` без anchor делает `rng.choice` из структурного
  `Random(_make_seed(world_uid, building_uid))` — каждый из 4+ вызовов
  потребляет rng и сдвигает последующие draw'ы.
Пространство каскадируемых параметров — 15–25 (tier, материалы,
население/расы, культура, density, климат, профили) — ручная проводка
каждого гарантирует повторение класса багов.

Принято мастером: механизм — универсальная инфраструктура. Контракт —
typed `LocationContext` с `Cascade`-аннотациями на полях; движок — один
generic `extend()`, контекст распространяется вниз по потоку генерации,
walker'а вверх по `parent_location_uid` нет. Полиморфизм — на связном
списке полей-каналов (`CascadeChannel`/`CascadeLink`), не на параметре
и не на строковой таблице полей. v1 — архитектурно чистый
движок + **один тестовый параметр `economic_tier`** (доказывает
fold-семантику, provenance, одиночный rng-вход); остальные поля
(материалы, city_size, население, профили) — последующие строки с
`Cascade`, не scope. `TierResolver` после миграции не удаляется — на
месте его вызовов остаётся `# TODO: перенести на LocationContext`;
физическая зачистка — когда будем готовы перенести оставшиеся
call sites.

Правила: `.cursor/rules/code-gates.mdc`, `refactor-safety.mdc`,
`dataModel-no-hardcode.mdc`, `layer-boundaries.mdc`,
`class-size-limit.mdc`. Один заход = один атомарный шаг → проверки →
отчёт → ожидание «ок» мастера. Не менять состав плана молча. Документ
не разрешает кодить. Не запускать backend, не коммитить без команды.
DAG-ноды не трогаем. Новых authored-полей и wire-ключей не вводить.

## S0: принятые решения и оставшиеся вопросы

**Уже решено; повторно не запрашивать:**

- Контекст — конкретная typed Pydantic-модель `LocationContext`
  (`dataModel/locations/context/`), поля объявлены через
  `Annotated[..., Cascade(field=…, materialize=…, default=…, fold=…)]`.
  Отдельного реестра дескрипторов нет — метаданные живут у поля.
- **Каноническая цепочка (решение мастера 2026-10-03):**
  `world → settlement → district → area → building → room`. Критерий
  уровня — **собственные потребители тира** (городские стены и дороги,
  дороги/стены района, забор и двор участка, структура, материалы
  комнаты), а не наличие authored-поля. Соответствие уровней объектам:

  | Уровень | Звено | Каналы тира (частное → общее) | NL / stamp |
  |---|---|---|---|
  | world | `World` | — (root пустой) | — |
  | settlement | city `NamedLocation` / `SettlementSkeleton` | `system_economic_tier` / `economic_tier` | да / **да** |
  | district | `DistrictSlot` + `DistrictTemplateEntry` | `economic_tier_range` (materialize) | да / **да** |
  | area | `AreaSlot` + `PlotLayoutTemplate` | `economic_tier` → `economic_tier_band` → `economic_tier_range` | нет (transient) / — |
  | building | building `NamedLocation` (+ `BuildingBodyTemplate`, своего тира нет) | `system_economic_tier` | да / **да** |
  | room | `RoomDef` / `_RoomInstance` → room `NamedLocation` | `rooms[].economic_tier` | да / **да** |

- **`economic_tier_range` — materialize-канал (Q1 → a).** Порядок
  каналов на уровне: `economic_tier` → `band` → `range`. Семантика
  range: ближайший к унаследованному тиру внутри `[min, max]`; если
  унаследованного нет — rng внутри range (тот же единственный rng-вход
  scope). Фильтрация размещения в `planner/economic.py` не меняется.
- **Иерархия — явная в контракте, не в голове caller'а (решение
  мастера).** Enum `ScopeLevel` (`world, settlement, district, area,
  building, room`) в `dataModel`; каждое звено объявляет `level`. `extend()`
  проверяет: уровень нового звена строго ниже `ctx.level`; пропуск
  уровня и повтор уровня — ошибка (повтор = второй резолв на scope).
  Provenance = `(ScopeLevel, source)`, не свободная строка.
  Расширение контракта (не v1, но форма `Cascade` его не должна
  ломать): `Cascade(levels=…)` — с каких уровней поле вообще может
  прийти (per-field иерархия для будущих полей вроде climate anchor).
- **Default — политика POJO, не callable в движке (решение мастера).**
  `Cascade.default` ссылается на `DefaultPolicy` (`REGISTRY_MEDIAN`,
  `CANONICAL_DEFAULT`, `NONE_IS_ERROR`), реализацию которой держит POJO
  домена поля (для тира — registry economic tiers: median + WARNING);
  движок знает только, как вызвать политику с `world`. Литералов и
  параллельных default-таблиц в `contextResolver` нет
  (`dataModel-no-hardcode.mdc`).
- `extend(*links)` — единственная точка резолва; вызывается на границе
  scope (settlement → district → area → building → room). Повторный
  резолв параметра внутри scope запрещён.
- Звено — `Link(level, obj)`: caller конвертирует runtime-объект в
  source-POJO (city NL / `SettlementSkeleton` / `DistrictTemplateEntry`
  из `DistrictSlot` / `PlotLayoutTemplate` из `AreaSlot` / NL /
  `RoomDef`); `check_link` подтверждает, что тип объявляет канал для
  уровня. Движок читает узлы цепочки рёбер, не строковые имена.
- Каскад тира = полный каскад по канонической цепочке: room → building
  NL → area (plot `economic_tier` → band → range) → district (range) →
  settlement → `DefaultPolicy.REGISTRY_MEDIAN` + WARNING. Текущий
  усечённый вызов `TierResolver` в structureGeneratorService, мёртвый
  канал `plot.economic_tier` и непереданный district — баги, которые
  этот план чинит проводкой, а не маскирует. `TierResolver` не трогаем.
- Отсутствие значения после полного каскада + default — баг caller'а →
  ошибка; молчаливый дефолт у консьюмера запрещён.
- Provenance обязателен: `ctx.provenance[param] = (level, source)`;
  WARNING при domain default вместо silent median.
- Движок — новый слой `application/worldData/context/`; не
  `generators/utils/` и не экономика.
- Persist resolved-значений на NL (писать `system_economic_tier` на
  каждой NL цепочки при создании) — решение §6 ТЗ, см. ниже.
- Режим v1 — first-non-null + materialize; сложная семантика только
  через `fold` конкретного параметра; merge-режимов нет.

- v1 = движок + один параметр `economic_tier`; ширина покрытия не цель —
  чистота механизма (решение мастера).
- `TierResolver` сохраняется с TODO-комментарием `перенести на
  LocationContext` у вызовов; зачистка отдельным заходом, когда будем
  готовы переносить (решение мастера).
- **Persist — каждая NL цепочки получает stamped resolved тир**
  (решение мастера): settlement, district, building, room NL — при
  создании `system_economic_tier` = `ctx.economic_tier` (authored
  остаётся как есть; null → materialized/median → записывается). Area
  NL нет — transient. Поле на settlement становится
  authored-или-materialized: такие поля проще и правильнее хранить,
  общий тир города может меняться в обе стороны. Остальные параметры
  transient, persist им запрещён.
  Перегенерация: stamped-тир — первое звено каскада → стабильность
  между генерациями; ретро-пропагация правок предков отсутствует —
  доменное правило tz_cascade_context §6.
- **Потребители district/settlement-уровня в v1 не переводятся на ctx**
  (решение мастера): барьеры, дороги, стены читают тир как сейчас (из
  `CitySkeleton`); v1 только строит ctx и stamp'ит. Перевод этих
  потребителей — follow-up отдельным планом.

**Остаётся уточнить:** нет — все вопросы S0 закрыты решениями мастера
(2026-10-03).

**Закрыто аудитом (решения мастера 2026-10-03):**

- **Q1 → (a).** `economic_tier_range` — materialize-канал на district и
  area (семантика — «Уже решено»). Требует sync tz_cascade §5 и
  tz_economic_tier §4.
- **Q2 → (b).** `Cascade` в `dataModel` хранит `field`, `DefaultPolicy`,
  `fold`, (`levels`); materialize (band → tier через rng) подключает
  движок `contextResolver` по имени поля — локальная привязка, не
  публичный реестр; `materialize_band` остаётся в application.
- **Q3 → да.** Отдельный `Random(_make_seed(world_uid, <scope_uid>,
  "tier"))` в caller'е каждого scope с materialize (district, building);
  diff геометрии band-шаблонов фиксируется в S1 как ожидаемый.
- **Q5 (решение, не вопрос).** Debug-роут строит
  `LocationContext.root(world).extend(EmptyLink(settlement))
  .extend(EmptyLink(district)).extend(area_link)` из шаблона — тир/band
  только из `PlotLayoutTemplate`, без stamping; пустые звенья явные,
  валидация уровней не обходится.
- **District — уровень цепочки** (разворот промежуточного решения
  «district вне цепочки»: критерий уровня — свои потребители тира);
  stamp на всех NL включая settlement и room; см. «Уже решено».
- **Иерархия явная (`ScopeLevel`), default — политика POJO**; см.
  «Уже решено».
- **Q4 → (a).** Caller с репозиторием (packing job / persist service)
  читает существующий building NL по `location_uid` и подаёт в
  `structureAreaAssembler` — он становится первым звеном building ctx
  вместо свежего `_place_building`; stamped-тир из БД участвует в
  каскаде → §8.4 выполним. Побочно: `_place_building` не ставит
  `parent_location_uid` — баг родословной, фикс отдельно, не scope.

## Итоговая архитектура

- `dataModel/cascade/` — домен-нейтральный механизм (ни один домен не
  хозяин): `cascadeSpec.py` — словарь объявлений (`ScopeAxis`,
  `Cascade`, `CascadeLink`, `CascadeChannel`, `DefaultPolicy`,
  `ChannelKind`); `cascadeGraph.py` — интроспекция и `ordered_chain`;
  `cascadeVerify.py` — `verify_cascade_contract`. Callables из
  application здесь не живут (Q2=b).
- `dataModel/locations/context/scopeLevel.py` — enum `ScopeLevel`
  (`world, settlement, district, area, building, room`), порядок =
  иерархия; локационная ось `ScopeAxis`.
- `dataModel/locations/context/locationContext.py` — `LocationContext`
  (frozen): `level: ScopeLevel`, единственное v1-поле `economic_tier`
  с `Cascade(field="system_economic_tier", default=REGISTRY_MEDIAN)`,
  `provenance: dict[str, tuple[ScopeLevel, str]]`; новые параметры —
  новые аннотированные поля, движок не правится.
- `application/worldData/context/cascadeLink.py` — звено
  `Link(level, obj)` + `EmptyLink(level)` — явное пустое звено для
  caller'ов без объекта уровня (debug-роут), чтобы уровень не
  пропускался молча. Адаптеров «тип звена → поле» нет: caller
  конвертирует runtime-объект в source-POJO (settlement — city NL /
  `SettlementSkeleton`; district — `DistrictTemplateEntry` из
  `DistrictSlot`; area — `PlotLayoutTemplate` из `AreaSlot`;
  building — NL; room — `RoomDef`), `check_link` подтверждает канал.
- `application/worldData/context/contextResolver.py` — `extend(ctx,
  *links, rng)`: валидирует уровень (один level, строго ниже, без
  пропуска/повтора, ось = оси ctx), читает `Cascade`-метаданные полей
  и идёт по `ordered_chain(param)` **только по узлам нового уровня** —
  per-scope резолв делает materialize однократным (band на area не
  перебрасывается глубже). `VALUE` first-non-null → `BAND`/`RANGE`
  materialize на месте узла (anchor = унаследованное значение;
  provisional default якорем не является) → inherit → `DefaultPolicy`
  через POJO домена (default не предупреждает повторно на пустых
  scope); provenance `(axis member, "Model.field" | "default:<policy>")`;
  единственный rng-вход — materialize тира, rng подаёт caller, seeded
  по uid scope (`_make_seed(world_uid, <scope_uid>, "tier")`); rng
  нужный, но не поданный — ошибка caller'а.
- Caller'ы: `settlementAssembler` (settlement ctx → district ctx на
  каждый `DistrictSlot`; district ctx передаётся в
  `structureAreaAssembler` вместе со slot'ом),
  `structureAreaAssembler` (`district_ctx.extend(area_link)
  .extend(building_link)` — сейчас отсутствует; building-звено —
  существующий NL из БД (Q4) или новый из `_place_building`), building
  ctx едет в структуру через `StructureContext` (поле `context:
  LocationContext` вместо `building_band`) → `buildingAssembler` →
  `generate_from_template`; room ctx строится в `roomFactory`
  (`building_ctx.extend(room_link)`) — там, где сегодня
  `resolve_room_materials` резолвит сам. Stamp: settlement NL
  (`settlementAssembler`/persist), district NL
  (`settlementOutdoorExtract._district_named_location`), building NL
  (`_place_building`), room NL (`_room_to_named_location`).
- Консьюмеры читают `ctx.economic_tier`: structureGeneratorService
  (4 фазы), `materialResolver.resolve_room_materials` (room ctx),
  `wallOpening` (room ctx, без собственного резолва),
  `_RoomInstance.economic_tier` = **effective** тир комнаты (сейчас —
  authored `room_def.economic_tier`, часто `None`); будущий
  MaterialPolicyConsumer. `TierResolver` сохраняется как facade с
  `# TODO: перенести на LocationContext` у city-вызовов — зачистка
  отдельным заходом. Ad-hoc `or`-цепочки материалов (foundation/roof) в
  v1 не трогаются — их параметры не в scope.
- `LocationContext.root(world)` — пустой ctx уровня `world` без
  materialize/default (у world нет authored тира; WARNING на root
  недопустим).

Поток данных: `LocationContext.root(world)` → extend на каждой границе
scope → замороженный ctx передаётся сервисам уровня → консьюмеры читают
поля. Никакого обхода предков и повторных resolve.

## Проверки

- Детерминизм ×2 на одном seed; effective tier здания идентичен во всех
  фазах (rooms, shafts, passages, openings) — один резолв.
- WARNING при отсутствии authored tier по всей цепочке (median path);
  отсутствие WARNING при явном authored tier.
- Иерархия: `extend` звеном того же уровня / с пропуском уровня / выше
  текущего → ошибка (unit S3).
- U-гейт structure: `./.venv/Scripts/python.exe -m unittest
  tests.test_u_shape_orientation_baseline tests.test_u_shape_facing
  tests.test_structure_orientation tests.test_debug_structure_rotations
  tests.test_embedded_shaft tests.test_embedded_upper_layout
  tests.test_shaft_walls` — геометрия/диагностики неизменны.
- compileall изменённых модулей, `git diff --check` после каждого шага.
- Поведение генерации не меняется, кроме целевого: тир теперь доходит от
  settlement/area до structure-консьюмеров; допустимые diff — значения
  effective tier и материалов там, где раньше каскад обрывался, плюс
  (по решению Q3) геометрия band-шаблонов из-за сдвига rng.

## Атомарные шаги

**Поправки мастера после ревью S2 (2026-10-03), итоговая форма.**
Строковый `ScopeLevel`, независимый `cascade_value(field: str)`, таблица
«уровень → типы POJO» на enum'е и `param` строкой не обеспечивают связь
объекта с контрактом. До S3 — корректирующий шаг S2a: контракт как
**двусвязный список полей** — `CascadeChannel(param=объект, level, above,
below, kind)` на самих полях-источниках (стиль wire-политик),
`CascadeLink(model, field, level)` — указатели prev/next; каждое ребро
объявляется **один раз** на стороне, чей модуль может импортировать
соседа без цикла (ORM-`backref` конвенция; `back_populates`-стиль
требовал бы ленивых строк — отклонено); обратное направление
материализует verify. Параметр — объект `Cascade` из `cascadeParams`
(identity-связь), `ScopeLevel` — чистая ось порядка
(tz_cascade_context §2, уточнение мастера). S3 в старой форме не начинать.

### S2a — Связный список полей: каналы, рёбра, identity параметра
- **Цель:** исключить строковые контракты и реестры типов, способные
  разойтись с исходными моделями или забыть звено.
- **ТЗ:** tz_cascade_context §2 (уточнение мастера), §3, §5.
- **Файлы:** dataModel/locations/context/{cascadeLevel,cascadeSpec,
  cascadeParams,locationContext}.py; `CascadeChannel` на полях
  `BundleNamedLocation` (×4 уровня), `SettlementSkeleton`,
  `DistrictTemplateEntry`, `PlotLayoutTemplate` (×3), `RoomDef`;
  backend/tests/test_location_context_contract.py.
- **Контракт:** `ScopeAxis` — StrEnum-миксин с `rank` (ось scope'ов
  любого домена); `ScopeLevel` — локационная ось на его базе;
  `Cascade.axis` привязывает параметр к своей оси (канал на чужой оси
  = ошибка); `CascadeChannel(param: Cascade, level, above: CascadeLink|None,
  below: CascadeLink|None, kind)` в `Annotated` полей-источников;
  `CascadeLink(model|None=self, field, level)`; `ECONOMIC_TIER =
  Cascade(...)` в `cascadeParams` — поле контекста и каналы ссылаются
  на один объект; ребро декларируется один раз (сторона без цикла
  импорта), verify материализует обратное; `check_link` через
  метаданные типа объекта (нет isinstance-таблицы); порядок цепочки —
  из рёбер; verify — скан `BaseModel.__subclasses__()`: резолв имён
  полей, kind-aware типы, один top/bottom, рёбра только внутри уровня
  или соседних рангов, непрерывность до world. «Нет канала» ≠
  «канал = null». Runtime/persistence — граница application; обратных
  импортов из dataModel нет; wire-поля не добавляются.
- **Проверка:** unit: identity параметра; ссылка на несуществующее
  поле → ошибка; ссылка на уровень без канала → ошибка; несовместимый
  тип → ошибка; разрыв/ветвление/пропуск ранга цепочки → ошибка;
  `check_link` на чужом типе → ошибка; nullable поле продолжает
  наследование. S1 baseline, compileall, diff --check.
- **Done:** изменение исходного POJO не может молча деградировать в
  наследование/default; новый источник подключается аннотацией поля
  без правок центральных таблиц; S3 использует связный список полей.

### S0 — Согласовать доменный контракт (только документация) — **закрыт 2026-10-03**
- **Цель:** закрепить форму механизма и состав v1-полей.
- **ТЗ:** [tz_cascade_context.md](<E:/AI Project/docs/tz_cascade_context.md>)
  целиком; [tz_economic_tier.md](<E:/AI Project/docs/tz_economic_tier.md>)
  §4 (каскад), §9 (поля); [tz_locations.md](<E:/AI Project/docs/tz_locations.md>)
  (семантика `system_economic_tier`, «null → наследует»).
- **Файлы:** tz_cascade_context.md — §2 цепочка
  `world → settlement → district → area → building → room` + критерий
  уровня (свои потребители тира); §3 форма `Cascade` (`DefaultPolicy`,
  `levels`) и `ScopeLevel`; §4 валидация уровней в `extend`,
  `EmptyLink`, rng per scope; §5 таблица источников (district = range,
  area = plot `economic_tier` → band → range; семантика range); §6 stamp
  на каждой NL цепочки (settlement, district, building, room), area
  transient; §8.1–8.3 уровни `city → district → area → building`
  (кейсы уже в этой форме — проверить). tz_economic_tier.md §4 —
  добавить area/template и range в каскад. Этот план.
- **Контракт:** ответ мастера на Q4; ТЗ синхронизированы с решениями
  S0.
- **Проверка:** сверить поля v1 с реальными полями NL/skeleton/template
  (аудит в «Основании» — исходная точка); код не менять.
- **Done:** мастер согласовал Q4 и правки ТЗ; S2–S5 до этого не готовы.

### S1 — Аудит и baseline точек потребления (только проверки)
- **Цель:** полный список мест, где каскад размазан, + снимок поведения.
- **ТЗ:** tz_cascade_context §1, §5; tz_economic_tier §4, §8.
- **Файлы:** backend/tests/test_cascade_context_baseline.py (или
  расширение существующего baseline); .local/-артефакты.
- **Контракт:** production не меняется; зафиксировать текущие значения
  effective tier во всех 4 фазах structureGeneratorService, per-room
  тир/материалы из `resolve_room_materials`, `glass_tier` в
  `wallOpening`, + foundation/roof/barriers; отдельно — мёртвый канал
  `template_tier` (plot.economic_tier не влияет) и геометрия
  band-шаблонов (Q3).
- **Проверка:** unit + U-гейт; список diff-ожиданий для S4–S5.
- **Done:** baseline воспроизводим; известно, где значения изменятся
  после проводки settlement/district/area(plot) и смены rng-источника.

### S2 — Контракты: `Cascade` + `LocationContext` (только dataModel)
- **Цель:** typed модель контекста и метаданные полей.
- **ТЗ:** tz_cascade_context §3, §5.
- **Файлы:** dataModel/locations/context/{cascadeLevel,cascadeSpec,locationContext}.py;
  backend/tests/test_location_context_contract.py.
- **Контракт:** `ScopeLevel` enum (порядок = иерархия);
  `DefaultPolicy` enum; `Cascade(field, default: DefaultPolicy, fold=None,
  levels=None)`; frozen `LocationContext` с `level`, единственным
  v1-полем `economic_tier` (`Cascade(field="system_economic_tier",
  default=REGISTRY_MEDIAN)`) и `provenance`; `root(world)` → уровень
  `world`, пустые поля. Реализация `REGISTRY_MEDIAN` — на POJO
  экономического registry (`dataModel/economy`), не в движке. Без
  импортов из application/ и без wire-полей.
- **Проверка:** unit-контракт объявлений, compileall.
- **Done:** модель объявляет тестовый параметр; production не подключён.

### S3 — Движок `extend()` + адаптеры звеньев (только механизм) ✅ done
- **Цель:** generic fold по `Cascade`-метаданным.
- **ТЗ:** tz_cascade_context §2, §4.
- **Файлы:** application/worldData/context/{cascadeLink,contextResolver}.py;
  backend/tests/test_context_extend.py.
- **Контракт:** `extend(*links)`: звено — `{level, obj}` (или
  `EmptyLink(level)`); валидация `level` (строго ниже `ctx.level`, без
  пропуска и повтора → ошибка) → чтение каналов типа по
  `CascadeChannel`-метаданным → first-non-null по цепочке рёбер
  `above`/`below` → inherit → materialize (`BAND`/`RANGE` kind через
  rng caller'а, привязка внутри resolver, Q3) → `DefaultPolicy` через
  POJO; provenance `(ScopeLevel, source)`; `root()` не materialize'ит;
  caller конвертирует runtime-объекты в исходные POJO: settlement
  (city NL / `SettlementSkeleton`), district (`DistrictTemplateEntry`
  из `DistrictSlot`), area (`PlotLayoutTemplate` из `AreaSlot`),
  building (NL), room (`RoomDef`); materialize range = ближайший к
  anchor внутри `[min, max]`, без anchor — rng; объявленный канал со
  значением `None` → продолжить каскад, не ошибка.
- **Проверка:** unit: порядок звеньев, валидация уровней (повтор /
  пропуск / выше), inherit, materialize-once (rng-мок), default+WARNING
  через политику POJO, provenance, неизвестный тип звена;
  приёмочные кейсы tz_cascade_context §8.1–8.3 — фикстуры собираются
  из объектов dataModel (`NamedLocation`, `WorldEconomyTierRegistry`),
  не из raw dict.
- **Done:** движок резолвит тестовый параметр по контракту §8;
  production не подключён.

### S4 — Проводка caller'ов (замена точек потребления) — ⛔ замещён `cascade-migration-done.md` (M1–M5 + зачистка M6)
- **Цель:** контекст строится на границах scope и доходит до структуры.
- **ТЗ:** tz_cascade_context §4, §7; tz_economic_tier §4.
- **Файлы:** settlementAssembler.py (settlement ctx + stamp settlement
  NL; district ctx на каждый `DistrictSlot`, передача в area assembler),
  settlementOutdoorExtract.py (`_district_named_location` — stamp
  district NL), structureAreaAssembler.py (district→area→building ctx,
  `_place_building` — stamp, существующий NL первым звеном по Q4),
  structureGeneratorService.py `_room_to_named_location` (stamp room NL
  effective тиром),
  buildingAssembler/structureContext.py (`building_band` →
  `context: LocationContext`), buildingAssembler.py,
  structureGeneratorService.py (входной ctx, 4× TierResolver → ctx),
  structure/room/roomFactory.py (room ctx = `extend(room_link)`),
  utils/materialResolver.py (`resolve_room_materials` принимает
  effective tier, не резолвит), structure/passages/wallOpening.py
  (glass_tier из room ctx), api/routes/debug.py и
  debugStructureRotations.py (Q5); тесты сервисов.
  foundationBuilder/roofBuilder не трогаем — материалы вне scope v1.
  Разбить на под-шаги по слоям, если дифф не ревьюится за один
  просмотр: S4a caller'ы+StructureContext, S4b структура/room.
- **Контракт:** `generate_from_template` получает `LocationContext`
  (вместо `building_band`); room-override через `ctx.extend(room_link)`
  в roomFactory; `_RoomInstance.economic_tier` = effective; при создании
  **каждой** NL цепочки (settlement, district, building, room) resolved
  `ctx.economic_tier` пишется в `system_economic_tier` (persist-решение
  S0; tz_cascade_context §6); потребители district/settlement-уровня
  (барьеры, дороги, стены) в v1 на ctx **не** переводятся — читают как
  сейчас; `TierResolver` не удаляется — у оставшихся city-вызовов
  (settlementAssembler, settlementGeneratorService,
  settlementOutdoorPackingJob) комментарий `# TODO: перенести на
  LocationContext` (зачистка отдельным заходом).
- **Проверка:** U-гейт, детерминизм ×2, WARNING-тесты, unit caller'ов;
  materialize тира дёргается один раз на здание (rng-мок/счётчик);
  `grep TierResolver` в `generators/structure/` и `utils/materialResolver`
  пуст; кейс §8.4 (persist + перегенерация сохраняет stamped-тир — по
  Q4).
- **Done:** effective tier с settlement/district/area(plot) доходит до
  всех фаз структуры и до комнат/проёмов; все NL цепочки stamped; в
  структурном scope (service, roomFactory, materialResolver,
  wallOpening) нет `TierResolver`; оставшиеся city-вызовы помечены TODO.
- **Follow-up (вне v1, отдельный план):** перевод потребителей
  district/settlement-уровня (барьеры, дороги, стены) на
  `LocationContext`.

### S5 — Приёмка и handoff — ⛔ замещён `cascade-migration-done.md` (M6 acceptance)
- **Цель:** подтвердить класс бага закрытым; разблокировать
  wall-materials S5–S6.
- **ТЗ:** tz_cascade_context §6–§7; structure-wall-materials-done §S0.
- **Файлы:** этот план (пометки), при необходимости tz_economic_tier §8
  (обновить таблицу «Где что используется»).
- **Контракт:** решение по persist `system_economic_tier` на NL
  зафиксировано (сделано/отложено — явно).
- **Проверка:** полный sweep генерации, sweep-гейт из wall-materials
  плана, финальный отчёт.
- **Done:** контекст — единственный путь параметров к консьюмерам;
  wall-materials S5 может подключать resolved-контекст без костылей.
