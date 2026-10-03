# ТЗ: каскадный резолв параметров локаций — `ResolvedLocationContext`

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

Фактические сбои на 2026-10:

- `system_economic_tier` никогда не записывается на district/building NL —
  authored-канал поля жив только на settlement;
- `structureGeneratorService` вызывает `TierResolver` без district/city —
  каскад §4 внутри структуры усечён до `building + band`;
- `TierResolver.resolve` вызывается 4 раза на здание с rng —
  `materialize_band` может дать разные тиры в разных фазах одного здания;
- `parent_wall_material` / `parent_floor_material` резолвятся ad-hoc
  `or`-цепочками в точках потребления (`structureGeneratorService`,
  `foundationBuilder`, `roofBuilder`), без цепочки предков и без единого
  дефолта.

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

Канонический порядок уровней:

```
world → settlement(city) → district → building → room → (cell)
```

Но «звено» — **не только `NamedLocation`**. В коде три параллельные
иерархии, все с семантикой наследования:

| Иерархия | Звенья | Примеры |
|---|---|---|
| **NL-родословная** (persist) | `parent_location_uid` вверх | `system_economic_tier`, `parent_wall_material`, `parent_floor_material` |
| **Модели генерации** (transient) | `SettlementSkeleton → DistrictSlot/DistrictLayout → AreaSlot/AreaLayout → building probe → RoomInstance` | `skeleton.system_city_size or settlement.system_city_size or "hamlet"` — ad-hoc каскад уже сегодня |
| **Шаблонные каналы** | `world registry → level template → instance` | `plot.economic_tier` / `_band` / `_range`, `district_template.economic_tier_range`, `rooms[].economic_tier`, `outline.default_*_material` |

**Звено цепочки — полиморфный источник полей**, а не NL. Движок принимает
упорядоченный список звеньев (частное → общее); каждое звено — адаптер
над конкретным объектом (`NamedLocation`, `SettlementSkeleton`,
`DistrictSlot`, `RoomInstance`, `PlotLayoutTemplate`, …). Дескриптор
параметра объявляет, **из каких типов звеньев и как** читать authored-поле
и шаблонные каналы; движок не знает, где звено было NL, а где —
объектом генерации или шаблоном.

Граница scope — точка, где появляется новое звено: world import/skeleton →
settlement assemble → district assemble → area/building → structure
generate (room). Caller знает только свои звенья, не чужие.

---

## 3. `LocationContext` и аннотация `Cascade`

Контракт — конкретная typed Pydantic-модель `LocationContext`
(`dataModel/locations/context/` рядом с `namedLocation/`). Каждый
каскадируемый параметр — **поле модели с `Cascade`-метаданными в
`Annotated`**, объявленное один раз, рядом с типом:

```python
class LocationContext(ContextModel):
    economic_tier: Annotated[EconomyTierKey | None, Cascade(
        field="system_economic_tier",      # authored-поле на звене
        materialize=band_to_tier,          # band → tier (rng), опционально
        default=median_tier,               # конец цепочки + WARNING
    )] = None
    race_mix: Annotated[RaceMix | None, Cascade(
        field="population_composition",
        default=world_race_profile,
    )] = None
    wall_material: Annotated[MaterialKey | None, Cascade(
        field="parent_wall_material",
        default=canonical_wall_default,
    )] = None
```

| Элемент `Cascade` | Назначение |
|---|---|
| `field` | Имя authored-поля, которое адаптер звена читает (`system_economic_tier`, `parent_wall_material`, …) |
| `materialize` | Опциональный пост-процессор при пустом authored-поле (band → tier через rng); может быть `None` |
| `default` | Доменный дефолт конца цепочки (функция от `world`; median + WARNING для тира, canonical default для материалов) |
| `fold` | Опциональный полный per-param resolver — для параметров, которым first-non-null недостаточно (точечно, не режим движка) |

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
settlement_ctx = LocationContext.root(world).extend(settlement_link)
district_ctx   = settlement_ctx.extend(district_link)
building_ctx   = district_ctx.extend(building_link)
room_ctx       = building_ctx.extend(room_link)   # rooms[].economic_tier и т.п.
```

`extend()`:

1. Проходит по полям `LocationContext`, читает `Cascade`-метаданные.
2. Для каждого поля — first non-null по новым звеньям (через
   `link.cascade_value(field)`), иначе наследует текущее значение родителя.
3. Пусто после всех звеньев → `materialize` (если объявлен), затем
   `default`.
4. Возвращает **новый замороженный** `LocationContext` + provenance:
   `ctx.provenance[param] = (level, source)` — какой уровень/канал дал
   значение.

Адаптер звена — `link.cascade_value(field) -> value | None`:
полиморфизм живёт на звене (NL читает `system_economic_tier`, шаблон —
`economic_tier`/`_band`, skeleton — alias-поле), матрицы
«параметр × тип звена» нет.

**Инварианты:**

- **Один резолв на scope.** Контекст строится один раз на границе входа в
  генерацию уровня (settlement → district → building) и передаётся вниз.
  Повторный резолв того же параметра внутри scope запрещён — именно он
  сегодня даёт rng-дрейф тира между фазами.
- **Консьюмер не резолвит.** Consumer получает `ctx.effective_*` и не
  имеет доступа к цепочке, rng и реестру в обход контекста.
- **Отсутствие значения после полного каскада + domain default — баг
  caller'а**, ошибка/exception, не молчаливый дефолт у консьюмера
  (то же правило, что для экономического контекста в §11.2
  tz_economic_tier).
- **Provenance обязателен** в контексте: WARNING «взято с уровня X /
  domain default» вместо silent median.

---

## 5. Параметры v1 и кандидаты на расширение

**v1 — архитектурно чистый движок + один тестовый параметр:**

| Параметр | Authored-поле | Шаблонные источники | Materialize | Domain default |
|---|---|---|---|---|
| `economic_tier` | `NL.system_economic_tier` | `plot.economic_tier`, `plot.economic_tier_band`, `plot.economic_tier_range`; `rooms[].economic_tier` (уровень комнаты) | `materialize_band` (§5 tz_economic_tier) | `median_system_tier` + WARNING (§4 tz_economic_tier) |

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

Каскад тира при миграции должен покрывать **все** звенья §4
(room → template → building → district → city → bands → median), включая
сейчас отсутствующую передачу district/city в structure-вызовы.

---

## 6. Границы и не-scope

- **Persist resolved-значений на NL — принято (гибрид).** Механизм
  резолва transient; но `system_economic_tier` **записывается** на
  district/building NL в момент создания (там, где происходит резолв).
  Поле проектировалось как хранимый ref — это материализация
  наследования, а не подмена authored. Остальные параметры persist'ить
  запрещено: отдельных колонок у них нет, и вводить их — расширение
  schema, отдельное решение.
  **Перегенерация:** stamped-тир — первое authored-звено каскада →
  здание сохраняет тир между генерациями (тир — часть идентичности
  артефакта, детерминизм, повторного rng-materialize нет). Правки
  тира предков **не распространяются** на уже сгенерированные NL:
  перенаследование требует явного обнуления поля / отдельной политики
  re-materialize — вне scope v1, зафиксировано как доменное правило.
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

- `structure-wall-materials.md`: consumer политики материалов требует
  resolved экономический контекст (§11.2 tz_economic_tier) — этот
  механизм является его источником. Шаги S5–S6 того плана могут идти по
  transient-контракту, но production-подключение resolved-контекста
  корректно только после каскадного резолва building scope.
- Фикс «запись `system_economic_tier` на district/building NL при
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
