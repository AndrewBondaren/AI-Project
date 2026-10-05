# ТЗ: Переходы (`Transition`) — единый шаблон на весь движок

**Статус:** утверждено мастером; уточнения порталов и хранения сторон согласованы
2026-10-05. Оставшиеся вопросы перечислены в §10. Код — только после согласования
[плана имплементации](../.cursor/plans/location-transitions.md) и явной команды.
Домен **общий для движка**: не срез `tz_locations`, а
расширение, на которое `tz_locations` § Точки входа / § `location_passages`,
`tz_structure_connections` §4.1 (порталы) и `tz_settlement_outdoor` C17/C20/O3
должны ссылаться как на SoT.

Связанные ТЗ: [`tz_locations.md`](./tz_locations.md) (levels, entry points,
passages), [`tz_structure_connections.md`](./tz_structure_connections.md)
(граф улиц, порталы, `settlement_gate`), [`tz_settlement_outdoor.md`](./tz_settlement_outdoor.md)
(C17, C20, O3), [`tz_building_generator.md`](./tz_building_generator.md)
(двери/лестницы шаблона), [`tz_world_pack_storage.md`](./tz_world_pack_storage.md)
(WP-13 `location_entry`).

---

## 0. Зачем

Сейчас «переход из одного пространства в другое» описан **тремя** несовместимыми
формами:

| Сегодня | Форма | Направленность | Классификация | Хост стороны |
|---|---|---|---|---|
| `location_passages` | `from_level+xy → to_level+xy` | `is_bidirectional` | `system_passage_type` | через `level.location_uid` |
| `location_entry_points` | владелец + клетка + `leads_to_level_uid` | нет (одна сторона) | `entry_role` (роль, не тип) | по координатам |
| `connection_nodes` (`portal`, `building_entrance`, `settlement_gate`) | узел графа + `portal_destinations` | `portal_bidirectional` | `node_type` | `location_uid` узла |

Pathfinding, сцена (WP-13), LLM-нарратив и игровые действия («запечатать
портал», «взломать дверь») вынуждены знать все три. Требование мастера:
**один шаблон перехода на весь проект**, в который укладываются дверь дома,
ворота города, люк из подвала таверны в пещеру (чей parent — лес), портал,
провал в полу.

---

## 1. Термины

**Имена сторон согласованы 2026-10-06:** `source` / `destination` вместо
`a` / `b`. POJO хранит endpoints `source` / `destination` и состояние
`source_side` / `destination_side`; SQL side ∈ {`source`, `destination`}.
Для двунаправленных типов это порядок хранения, не запрет обратного движения.

- **Transition** — ориентированный или двунаправленный переход с двумя
  сторонами. Физические проходы имеют два конкретных endpoint'а; портал
  может задавать назначение как локацию, а не заранее выбранную клетку.
  Конкретное ребро навигации — представление перехода для перемещения,
  не требование хранить любой портал как пару статических точек.
  Единственная сущность домена.
- **Endpoint** — «где стоишь, когда проходишь»: клетка `(x, y, z)` в
  глобальных координатах `map_cells` с явным пространством: `surface`
  (поверхность/terrain, значение по умолчанию) либо `level`
  (уровень локации, требует `level_uid`). `surface` не означает z=0:
  координата z по-прежнему задаётся явно.
  **Хост endpoint'а** (локация, в чьём пространстве клетка) — `level.location_uid`
  при пространстве level; для surface ссылка `host_location_uid` может
  указывать существующую NL (territory / settlement / district), но не
  обязательна. Surface без NL — полноценная сторона перехода, не ошибка
  и не повод создавать фиктивную локацию. `surface` — значение вида
  пространства, не строка вместо UID в FK. Если ссылка на host задана,
  она явная, по координатам не выводится. Host не является parent.
  **Решение мастера 2026-10-05:** `surface` — семантическое назначение;
  объявление выхода в surface не требует от автора указания фиксированной
  точки. Алгоритм сам должен искать ближайший допустимый выход среди
  возможных комбинаций генератора (лестница, тоннель и т.д.). У wilderness
  мало семантических привязок, поэтому конкретное решение не задаётся
  обязательным host/parent. Алгоритм поиска, критерий близости и сборка
  выбранного выхода — TODO, сейчас не приоритет
  ([SURFACE-T-1](./tz_generator_technical_debt.md#surface-t-1--поиск-выхода-в-surface-среди-комбинаций-генератора)).
- **Side (сторона)** — состояние одной стороны перехода: видимость,
  доступность, overrides сложности. У перехода **ровно две** стороны `source` / `destination`.
- **Тип перехода** — единственная ось классификации: форма **и** семантика
  входа (`main_entrance` — парадный вход в локацию, `service_entrance` —
  чёрный, `door` — дверь без семантики входа, `staircase`, `hatch`, `portal`,
  `fall`…). N+1 реестр `worlds.transition_type_registry` поверх builtin enum
  (решено: словарь `tz_building_generator` §3.6 — часть реестра, отдельной
  оси «роль» нет).
- **Направление** — для типов `main_entrance`/`service_entrance` endpoint `destination`
  = **входимая** локация (owner стороны `destination`), `source` = откуда входят. Для
  симметричных типов (`door`, `staircase`, `tunnel`) порядок `source`/`destination` не
  несёт смысла.
- **Портал** — общая абстракция (`TransitionType.PORTAL`) с двумя
  реализациями: `graph` (перемещение с учётом графа и блокирующих его
  специальных барьеров) и `coordinate` (буквальный телепорт между
  конкретными точками, без обращения к графу). Это реализации одного
  builtin-типа, не два новых типа в реестре.
- **Назначение портала** — куда ведёт портал: конкретная точка, узел
  графа или локация как место назначения. Вид назначения и реализация
  портала — разные понятия (§3.4); наличие UID локации не означает, что
  портал обязательно ведёт в заранее выбранную клетку этой локации.

**Не путать:**
- `parent_location_uid` — семантическое дерево для каскада; переход **не**
  меняет parent и не выводится из него (`tz_locations` «Semantic parent ≠
  physical entry»).
- WP-13 `refine_from_entry(kind=location_entry)` — вход **сессии** в мир
  (якорь сцены), не переход. Он *читает* переходы для выбора якоря.
- `magma_antipode_teleport` — правило движка на `z_magma_bottom`, не строка
  перехода (`tz_locations` § Магма); остаётся как есть.
- `access_mechanic` / `isolated` на `location_levels` — свойства **уровня**
  (как на него вообще попадают), не ребра.

---

## 2. Модель

```text
transitions
  transition_uid        PK
  world_uid             FK worlds
  system_transition_type  ref → worlds.transition_type_registry (N+1)
  is_bidirectional      bool   -- одна строка на переход; смысл ТОЛЬКО у типов с directional=true (portal, fall); остальные игнорируют (решено)
  origin                'authored' | 'generated' | 'runtime'   -- кто создал (import / generator / game action)
  is_active             bool   -- переход работает (портал выключен, дверь замурована)
  access_mechanic       JSON list[str]  -- проход ЗАКРЫТ; перечисленные механики его открывают (lockpick, key, excavation, teleport, …); [] = открыт (К9)
  type_params           JSON   -- параметры builtin-типа; portal: реализация graph|coordinate, typed назначение(я), blocked_behavior_override (§3.4)
  display_name, glossary_ref, tag_refs
  -- endpoint source
  source_space               'surface' | 'level', default 'surface'
  source_level_uid           FK location_levels, nullable
  source_host_location_uid   FK named_locations, nullable   -- optional существующая NL для surface
  source_x, source_y, source_z         int (глобальные map_cells материализованного прохода, не обязательные координаты объявления surface)
  source_node_uid            FK connection_nodes, nullable   -- endpoint лежит на узле графа (portal graph-типа, ворота, порог) — К7
  -- endpoint destination
  destination_space, destination_level_uid, destination_host_location_uid, destination_x, destination_y, destination_z, destination_node_uid
  -- конкретный endpoint destination у физических проходов и coordinate-портала;
  -- у портала с назначением-локацией статическая клетка destination не обязательна:
  -- источник назначения — typed portal params, не фиктивные destination_x/destination_y/destination_z
  -- nullable/проекция destination для такого назначения уточняются по §10
  -- вертикаль implicit: source_z ≠ destination_z, когда оба endpoint'а конкретны

transition_sides
  (transition_uid, side) PK, side ∈ {'source','destination'}
  owner_location_uid    FK named_locations, nullable   -- чей это «вход»; NULL для wilderness без NL, не для корневой NL
  is_discovered         bool
  is_accessible         bool
  entry_difficulty_override  int nullable 0–100
  guard_level_override       int nullable 0–100
  display_name          nullable   -- «Северные ворота» / «Лаз за бочками»
```

Это схема конкретных endpoint'ов и общих сторон, а не разрешение
превратить назначение-локацию в пустой wilderness endpoint. Если портал
объявляет локацию назначения, эта ссылка сохраняется явно в typed
параметрах; отсутствие ещё определённой клетки прибытия не означает
«дикая местность». Полная SQL/POJO-проекция такого назначения и стороны destination
закрывается по §10 до реализации схемы.

Аналогично `surface` само по себе не определяет конкретную точку выхода.
Геометрия фактически выбранного прохода и семантическое объявление выхода
в surface — разные данные; последнее не заполняется фиктивными xyz.
Поиск и материализация решения относятся к отложенному SURFACE-T-1.

**Инварианты:**

1. Две стороны всегда есть (даже у `fall` — у стороны `destination` `is_accessible`
   может быть `false`).
2. `is_bidirectional` читается **только** для builtin-типов с
   `directional=true` (`portal`, `fall`); `false` ⇒ проход только `source → destination`,
   обратный — **не** вторая строка, а флип флага игровым действием
   (`tz_structure_connections` §4.1). Для остальных типов флаг игнорируется
   и писаться должен `true` (дефолт), не как маркер «это вход» (К2).
3. Пространство endpoint'а явно: `surface` по умолчанию либо `level` с
   обязательным `level_uid`. Для surface без NL host/owner FK могут быть
   NULL; семантика этой стороны — **surface**, а не неопределённое
   отсутствие пространства (решение мастера 2026-10-05).
   Отсутствие parent у существующей локации — другой случай: корневая NL
   сохраняет свой UID и может быть host/owner перехода.
   Сам проход не требует отношений parent/child между сторонами,
   не создаёт их и не проверяет иерархию для разрешения движения.
4. Тип из реестра поверх закрытого enum движка. Генератор сравнивает тип
   через engine-enum (как HY-5), реестр расширяет display.
7. Здание: **≥1** `main_entrance` со стороной `destination_side.owner_location_uid = building`, **≥0**
   `service_entrance` (C20). Проверка на persist, как сейчас
   `fronts < 1 → SettlementOutdoorExtractError`.
5. Переход не создаёт и не меняет `parent_location_uid` ни одной стороны.
6. Effective значения стороны (как сейчас у entry points):
   `difficulty = side.override ?? owner_location.entry_difficulty ?? 0`,
   `guard = side.override ?? owner_location.guard_level ?? 0`.
8. **Закрытость** (К9): `access_mechanic` на переходе отвечает «закрыт ли
   этот проход и чем открывается». `[]` — открыт. Непустой — проход
   существует, но закрыт: pathfinding не строит ребро без механики,
   action-путь — по механике (`lockpick` → `entry_difficulty`, `guard` →
   `guard_level`; словарь механик — закрытый enum движка, общий с
   `location_levels.access_mechanic`). `side.is_accessible` — текущее
   **состояние** (временно завалено / закрыто движком), не способ открыть.
   Уровень: `location_levels.access_mechanic` остаётся для `isolated`
   уровней **без единого перехода** — «прохода нет; вот механика, по
   которой движок его создаст» (успех `excavation` ⇒ `Transition(breach,
   origin=runtime)`; `teleport` ⇒ `Transition(portal)`). Граница: уровень —
   нет ребра; переход — ребро есть, закрыто.
9. **Портал** — одна абстракция, две обязательные реализации (§3.4).
   `coordinate` буквально телепортирует между точками и игнорирует граф;
   `graph` учитывает граф перемещения, специальный барьер на маршруте
   может блокировать сам переход. Графовый портал не определяется как
   «сначала телепорт на узел, потом обычная прогулка».
   Назначение может быть локацией; обязательный `destination_node_uid` для любого
   graph-портала и обязательная статическая клетка destination отменяются.
   Конкретная node-ref обязательна только у назначения вида node.
   `blocked_behavior_override` — только для `graph`.
   Несколько назначений не сводятся принудительно к набору статических
   пар endpoint'ов; точный контракт множественности — §10.
   Портал — **всегда SQL-ярус**, даже внутри одного здания (К3).
10. **Детерминизм uid** (К10): `transition_uid` для `origin ∈ {authored,
    generated}` — детерминированный uuid5 от `world_uid` + тип + endpoint'ы
    (`(source_x,source_y,source_z) → (destination_x,destination_y,destination_z)`) для переходов с фиксированными
    endpoint'ами; формула идентичности портала с назначением-локацией
    и изменяемыми назначениями уточняется в §10. Не выводить UID из
    выдуманной точки прибытия. Тот же приём, что `_det_uuid` для
    passages и `entry_uid(destination_uid, role, passage_uid)` сейчас. Повторная
    генерация мира с тем же seed даёт те же `transition_uid` в pack и в SQL —
    ссылки (`source_node_uid`, `connection_nodes.transition_uid`, scene anchors)
    переживают regenerate. `origin='runtime'` — uuid4 (создан действием, не
    воспроизводится генерацией). Формула — **только** через общий helper
    `app/application/worldData/ids/` (SoT: storage DET-1): два корня — `world_uid`
    (идентичность сущностей: NL, levels, transitions, nodes) и `world_seed`
    (pack/relief job-uid и rng) — это **разные функции одного helper'а**, не
    две конвенции; ad-hoc `uuid5(...)` / `Random(f"...")` вне helper'а
    запрещены. Cross-cutting ТЗ — `project_data_storage_tz.md`
    § «Детерминированные uid и rng (DET-1)».

---

## 3. Классификация явных переходов

### 3.1 Тип (реестр `transition_type_registry`, N+1)

Объединение сегодняшних словарей: `tz_locations` § `passage_type_registry`
(`door/doorway/archway/corridor/staircase/ladder/rope/bridge/portal/fall`) +
`tz_building_generator` §3.6 (`main_entrance/service_entrance`) + новые для
cross-location (`hatch/tunnel/gate/breach`).

| `system_type` | Семантика | `entry` | `directional` | Вертикаль | Создаёт |
|---|---|---|---|---|---|
| `main_entrance` | парадный вход в локацию (`destination` = входимая) | да | нет | нет | structure generator (шаблон `entry_point`), C23 ворота поселения |
| `service_entrance` | чёрный вход в локацию | да | нет | нет | structure generator (`back_entry_point`) |
| `hidden_entrance` | тайный вход; `destination_side.is_discovered=false` по умолчанию | да | нет | любая | generator (`location_complex`), runtime |
| `door` | дверь без семантики входа (между комнатами) | нет | нет | нет | structure generator |
| `doorway` | проём без створки | нет | нет | нет | structure generator |
| `archway` | арка | нет | нет | нет | structure generator |
| `corridor` | коридор-связка | нет | нет | нет | structure generator |
| `staircase` | лестница | нет | нет | да | structure generator |
| `ladder` | стремянка / скобы | нет | нет | да | structure generator |
| `rope` | верёвка | нет | нет | да | runtime / generator |
| `hatch` | люк / лаз в полу-потолке между локациями | нет | нет | да | generator (подвал↔пещера), runtime |
| `tunnel` | тоннель между локациями | нет | нет | любая | generator (`location_complex`), runtime |
| `gate` | ворота периметра (район / участок) без семантики входа в NL; создаётся **только при наличии барьера** на периметре (К7) | нет | нет | нет | `AreaAssembler` (`perimeter_barrier`), межрайонные проходы |
| `breach` | пролом / окно — ad-hoc | нет | нет | любая | runtime (O3, после успеха действия) |
| `bridge` | мост / переход | нет | нет | нет | BridgeAssembler |
| `portal` | магический переход | нет | **да** | любая | StructureAreaAssembler (`structure_type=portal`) |
| `fall` | провал | нет | **да** (всегда `false`) | вниз | runtime (разрушение пола) |

- `entry=true` — тип несёт семантику «вход в локацию `destination_side.owner_location_uid`»: участвует
  в C20-инварианте, WP-13 выборе якоря, LLM «входы локации». Сегодняшний
  `entry_role` (`front`/`service`) → **тип** `main_entrance`/`service_entrance`;
  `tz_settlement_outdoor` C20 переписать в терминах типов.
- `directional=true` — только эти типы читают `is_bidirectional` (К2).
- Ворота поселения на периметре footprint (C23 `settlement_gate`) — тип
  `main_entrance`/`service_entrance` с `destination_side.owner_location_uid = settlement`; `gate` — для
  внутренних периметров без семантики входа в NL.

Builtin = закрытый enum движка (`TransitionType`) с флагами `entry`,
`directional`, `vertical`; мастер добавляет только `display`-типы с
привязкой `behaves_as` к builtin (как `like` у purpose) — поведение от builtin.

### 3.2 Сторона (без роли)

Сторона несёт только состояние: `is_discovered`, `is_accessible`, overrides
`entry_difficulty`/`guard_level`, `display_name`. Отдельной оси «роль» нет
(решено, К1): семантика входа — у типа.

### 3.3 По отношению к иерархии

| Класс | Стороны | Пример |
|---|---|---|
| **intra-location** | один `owner_location_uid` (или parent/child: здание↔комната) | дверь между комнатами, лестница на этаж |
| **sibling** | оба хоста под одним parent | дверь из дома во двор участка, ворота района |
| **cross-branch** | хосты в разных ветках дерева | люк: подвал таверны (parent — район города) ↔ пещера (parent — лес) |
| **to-wild** | одна сторона без NL | дверь дома на улицу без NL, пролом в стене наружу |

Класс **вычисляется** при необходимости для анализа, не хранится и не
является условием работоспособности двери/прохода. Переходу нужны стороны,
геометрия и состояние; отношения parent/child для движения не требуются.
Cross-branch — именно тот случай, ради которого parent и переход разведены.
Принадлежность интерьера одному зданию для выбора pack берётся из
материализованного building layout/ссылок levels, не означает обязательное
родство всех соединённых локаций.

Для портала с назначением-локацией отсутствие конкретного endpoint destination
не требует выдумывать клетку ради классификации: host/назначение читаются
из явных ссылок. Выбор SQL-яруса для любого портала уже определён типом.

### 3.4 Портал: общая абстракция и две реализации

Общая сущность — `Transition(type=portal)`. Она несёт направленность,
активность, состояние сторон и назначение; эти свойства не дублируются
на `connection_nodes`. Реализация выбирается закрытым `portal_type`:

- **`graph` — графовое перемещение.** Проход учитывает граф движения.
  Специальный барьер, на который наталкивается маршрут графа портала,
  может заблокировать переход. Это блокировка портального перемещения,
  а не только обычной дороги после уже успешного телепорта.
- **`coordinate` — прямой телепорт.** Персонаж переносится из конкретной
  точки A в конкретную точку B. Граф не проверяется; барьер, действующий
  через граф портала, не блокирует этот перенос. `is_active`, направление,
  состояние доступа и механики перехода по-прежнему действуют.

**Назначение — отдельный контракт.** Портал может вести в локацию как
место назначения, не только на node UID или фиксированные xyz.
Хранится объявленное назначение; фактическое положение персонажа после
прохода не подменяет его. В частности, локацию нельзя автоматически
заменить её центром, ближайшим входом или выбранной клеткой.
Задание назначения портала в генераторе и точное правило прибытия в
локацию отложены мастером 2026-10-05 как неприоритетный техдолг
[`PORTAL-T-1`](./tz_generator_technical_debt.md#portal-t-1--задание-назначения-портала-в-генераторе-и-прибытие-в-локацию).
Обязательные «места прибытия» на целевых локациях не согласованы и не
вводятся этим ТЗ. Возврат к вопросу — отдельно; не реализовывать fallback
под видом временного решения.

Итак, две реализации — **graph/coordinate**, а не **location/point**.
Вид ссылки на назначение сам по себе не определяет механизм перемещения.
Для coordinate-прохода конкретная точка B должна быть определена;
связь объявления назначения-локации с такой точкой требует отдельного
правила и не разрешается произвольным resolver'ом.

**Блокировка graph-портала:** применяется
`type_params.blocked_behavior_override`, если задан, иначе
`world.mechanics_settings["portal_blocked_behavior"]`:

- `random_portal` — выброс в случайный портал сети;
- `before_portal` — возвращение перед порталом входа;
- `random_effect` — случайный выбор одного из этих вариантов.

`is_accessible` — состояние, управляемое движком, а не обозначение
реализации портала или специального барьера. Наличие graph-барьера
проверяется по графу; как его результат отражается в состоянии сторон,
определяется контрактом действий/событий, не автоматической сменой
флага при генерации. Общая ошибка доступности и блокировка graph-маршрута
не должны смешиваться.

Узел графа может обозначать физическую точку портала, но не является
самим порталом и не ограничивает множество его назначений. Перенаправление,
включение/выключение, изменение обратного прохода и blocked behavior —
изменения данных портала через игровые действия. SQL — единый ярус
обеих реализаций. Алгоритм маршрута, правило выбора назначения из нескольких
и точная проекция сторон определяются до реализации (§10).

---

## 4. Хранение — два яруса, одна модель

| Ярус | Что | Где | Почему |
|---|---|---|---|
| **SQL `transitions` + `transition_sides`** | все переходы, у которых хотя бы одна сторона **вне** одного здания: наружные двери, ворота, люки/тоннели между локациями, порталы, мосты, runtime-переходы | `0001_initial.sql` | нужны pathfinding'у по карте, сцене, LLM, игровым действиям; редактируемы в рантайме |
| **Pack (`l.{uid}.settlement.zst` / building layout)** | intra-location переходы внутри одного здания (двери комнат, лестницы) | как сейчас (C20 вариант 1: interior не в SQL) | объём; меняются только при перегенерации дома |

Правило: **модель одна** (`Transition` POJO), writer выбирает ярус по классу
§3.3 (`intra-location` → pack, остальное → SQL) **и по типу**: builtin с
`directional=true` или рантайм-изменяемые (`portal` обоих видов, `fall`,
всё с `origin=runtime`) — всегда SQL, независимо от класса (К3). Pathfinding внутри здания
читает pack, между локациями — SQL; движок видит один тип `Transition`.
Runtime-переход внутри здания (пролом в стене комнаты) — **SQL** (`origin=
'runtime'`), поверх pack: pack read-only.

`location_entry_points` → **удаляется**: это `transition_sides` с
`owner_location_uid = building`. `location_passages` → **переименовывается**
в `transitions` (DDL §2). Миграции — только `0001` + recreate (schema-policy).

---

## 5. Маппинг доменов на шаблон

| Домен | Сегодня | Целевое |
|---|---|---|
| **Структурный генератор** — наружная дверь | `LocationPassage(from=NULL, to=level, is_bidirectional=False, type=main_entrance)` → extract → `LocationEntryPoint(entry_role)` | `Transition(type=main_entrance|service_entrance, source=(street cell, host=district/settlement NL), destination=(level, cell))`; `destination_side.owner_location_uid=building`; тип — из `EntryPoint.passage_type` шаблона как сейчас; `is_bidirectional` не пишется (дефолт) |
| Структурный генератор — внутренние | `LocationPassage` в pack | `Transition` в pack, класс intra-location, обе стороны `owner=building` (или room), типы `door/doorway/archway/staircase` |
| **Settlement topology (C23)** — `settlement_gate` | `connection_nodes.node_type=settlement_gate` | узел графа остаётся (`graph_level=city`), получает `transition_uid` → `Transition(type=main_entrance|service_entrance, source=outside (host=territory), destination=inside (host=settlement))`; `destination_side.owner_location_uid=settlement` |
| Барьер участка (`perimeter_barrier`) — калитка | нет | `AreaAssembler`: `Transition(type=gate)` между конкретными сторонами барьера **только при наличии барьера** (К7); без барьера переход не создаётся. Outdoor endpoint'ы могут иметь пространство surface без area NL. Существующие host refs optional; создание area NL и отношения district↔area не являются prerequisite прохода. Граф улиц (`building_entrance`/`yard_path`) — независимо |
| **Порталы** (`tz_structure_connections` §4.1) | `portal_*` колонки на `connection_nodes` | Одна абстракция `Transition(type=portal)`, реализации `graph` / `coordinate` (§3.4); объявленное назначение может быть локацией. Graph-маршрут блокируется специальным барьером; coordinate переносит между точками без графа. Node refs — конкретные привязки, не универсальная модель назначения. Множественность назначений — §10. Всегда SQL |
| **`location_complex`** (крипта, шахта) | — | уровни комплекса = `location_levels`; вход — `Transition(type=main_entrance|hidden_entrance, destination_side.owner_location_uid=complex)` cross-branch из подвала здания / с поверхности леса; parent комплекса — по смыслу (лес/гора), не по входу |
| **Ad-hoc** (O3) | «можно добавить entry после успеха» | `Transition(type=breach, origin=runtime)` создаётся движком после успешного действия; персональное discovery — отдельная тема вне scope генератора, не интерпретировать глобальный bool как состояние конкретного персонажа |
| **`fall`** | в реестре passage | `Transition(type=fall, is_bidirectional=false, origin=runtime)` |
| **WP-13 `location_entry`** | «ближайший discovered entry» | якорь = ближайший переход `entry=true` с `destination_side.owner_location_uid=location`, `destination_side.is_discovered AND destination_side.is_accessible`, предпочтение `main_entrance` |
| **Pathfinding** | три таблицы | один граф: terrain A* + `transitions` (SQL) + pack-переходы внутри здания |

---

## 6. Конфликты, найденные при сверке (требуют решения мастера)

| # | Конфликт | Где | Предложение |
|---|---|---|---|
| **К1** ✅ решено | Два словаря типов в **разных ТЗ**: `tz_building_generator` §3.6 (`main_entrance/service_entrance` — шаблон здания, enum `PassageType`) и `tz_locations` § `passage_type_registry` (`door/…/portal/fall`) — ни один не содержит другой; `entry_role` на `location_entry_points` дублирует `main/service` третьим словарём. | `passageType.py`, `tz_locations` § passage_type_registry, `tz_settlement_outdoor` C20, `settlementOutdoorExtract._role_for_passage` | **Один** реестр = объединение (§3.1); `main_entrance`/`service_entrance` — **типы** с `entry=true`, отдельной оси «роль» нет. `entry_role` удаляется, `_role_for_passage` не нужен. `tz_locations` реестр дополнить, C20 переписать в типах. |
| **К2** ✅ решено | Наружная дверь здания записывается `is_bidirectional=False` как маркер «вход». | `generators/structure/passages/entry.py:83` | Флаг читают **только** `directional`-типы (`portal`, `fall`); остальные игнорируют и пишут дефолт `true`. `entry.py` — убрать явный `False`. |
| **К3** ✅ решено | C20 вариант 1: «interior `location_passages` не писать в SQL» vs требование единого графа переходов для движка. | `tz_settlement_outdoor` C20, `settlementOutdoorSqlPersist` | §4: одна модель, два яруса; **исключение — порталы** обоих видов (`graph` / `coordinate`, инвариант 9) и всё рантайм-изменяемое: всегда SQL. C20 переписать. |
| **К4** ✅ решено; уточнено 2026-10-05 | Портал живёт на `connection_nodes` (`portal_type`, `portal_destinations`, `portal_bidirectional`, `portal_is_active`) — дублирование домена переходов. | `tz_structure_connections` §4.1, DDL `connection_nodes` | Портал = `Transition(type=portal)`, две реализации graph/coordinate (§3.4); назначения не ограничены статическими точками, локация допустима. `portal_*` колонки удалить; node остаётся графовой привязкой. Форма связи node↔portal и нескольких назначений уточняется в §10. Operational перенос отложен вместе с контрактами §10; существующие node/import поля сохраняются до отдельной миграции (§11). |
| **К5** | `location_entry_points` знает, **чья** это дверь (`location_uid`) и **куда** ведёт (`leads_to_level_uid`), но **не знает, в чьём пространстве стоит клетка снаружи**: для люка в подвале таверны строка пещеры хранит `(x,y,z)` подвала, а «это подвал таверны» можно узнать только поиском `map_cells` по координатам — при z-стекинге на одной клетке могут быть и подвал, и пещера (тот же запрет, что для `parent_location_uid`: overlap ≠ containment). | DDL, `LocationEntryPoint`, extract | В `Transition` хост **обоих** endpoint'ов явный (`source_level_uid`/`source_host_location_uid`, `destination_*`). Отдельная таблица входов не нужна: «входы локации X» = `transitions WHERE entry=true AND destination_side.owner_location_uid = X`. Таблицу удалить, repo переписать на этот запрос. |
| **К6** ✅ решено | Координаты: `location_passages.from_x/from_y` — **локальные** для уровня (offset = `MIN(map_cells.x/y)`, нигде не хранится — `tz_locations` отложенное «Coordinate bridging»); `location_entry_points.x/y/z` — **глобальные**. Один endpoint не может быть в двух системах. | `tz_locations` §1623, DDL | Endpoint — только **глобальные** `map_cells` координаты (z у уровней уже абсолютный). Локальные координаты — закрыть tech debt, не тащить в новую модель. |
| **К7** ✅ решено | На пути улица → дом три разных объекта трёх доменов, которые нельзя склеивать: (1) **дверь здания** `main_entrance` — structure generator, есть всегда (C20); (2) **калитка участка** `gate` — `AreaAssembler`/территория, существует **только если** по периметру участка есть `perimeter_barrier` (wall / fence); нет барьера — нет перехода, двор открыт; (3) **граф улиц** `building_entrance` + `yard_path` — connections, существует **независимо** от (1) и (2): это маршрутизация, не проход. | `tz_structure_connections` §5.1.3, `tz_assembler_hierarchy` §69, §442, `tz_city_generation` §perimeter_barrier | Граф не обязан иметь узел на каждую дверь и переход не обязан иметь узел. `source_node_uid`/`destination_node_uid` — конкретные optional ссылки (координаты сверяются на persist). Node обязателен у settlement_gate и назначения портала вида node; назначение-локация не подменяется node (§3.4). `yard_path` при наличии барьера проходит через клетку `gate`. |
| **К8** ✅ решено | `transition_type_registry` (N+1, мастер) vs builtin-поведение (`entry`, `directional`, вертикаль, portal-механика). Открытый реестр не может нести поведение. | `tz_locations` § passage_type_registry | N+1 запись **обязана** ссылаться на закрытый тип движка (`behaves_as: TransitionType`); поведение, флаги и `type_params`-модель — только от builtin; запись без `behaves_as` — ошибка импорта. |
| **К9** ✅ решено (частично дубль) | `location_levels.access_mechanic` и переходы оба отвечают на «как попасть», но на разные вопросы. | DDL `location_levels`, `LocationLevel`, `tz_building_generator` §214 | **Механика доступа отвечает: закрыт ли данный проход и чем открывается** → поле `access_mechanic` на `Transition` (инвариант 8), общий закрытый enum механик. `location_levels.access_mechanic` остаётся только для `isolated` уровней без переходов — «ребра нет; по этой механике движок его создаст». `tz_building_generator` §214 и `tz_locations` § location_levels — зафиксировать границу. |
| **К10** (мелочь) | Расхождение имени колонки между ТЗ и схемой: в `tz_locations` § `location_passages` схема записана как `passage_uid, world_id, …`, а в `0001_initial.sql` и dataclass `LocationPassage` колонка называется `world_uid` — как и во всех остальных таблицах (`named_locations.world_uid`, `connection_nodes.world_uid`). Поведения не меняет; это опечатка в ТЗ, которая при копировании в новую DDL `transitions` дала бы вторую конвенцию имён. | `tz_locations` §940, DDL `location_passages`, `db/models/locationPassage.py` | **Одна конвенция — `world_uid`**, везде: колонка, POJO, формула детерминированного uid. Причина не косметическая: все uid и rng генерации выводятся из `world_uid` (`settlement_cell_rng(world.world_uid, …)`, `_det_uuid(building_uid, …)`, `Random(f"{world.world_uid}_{scope_uid}_…")`); второе имя в одном из слоёв = второй источник seed, и повторная генерация мира по тому же seed даст другие `transition_uid` — pack и SQL разойдутся. Инвариант 10. При документационной синхронизации исправить `tz_locations` § `location_passages`. |

---

## 7. Расширяемость

- `type_params TEXT` (JSON) на `transitions` — параметры конкретного builtin
  типа (`portal`: `portal_type=graph|coordinate`, typed объявленные назначения,
  `blocked_behavior_override` для graph, см. §3.4; `gate`:
  `width_cells`; `staircase`: `staircase_type`). Валидируется pydantic-моделью
  **per builtin type** (тот же приём, что `location_payload` по `payload_kind`
  в `nl-typed-host-payload`). Не колонки per type.
- Новый вид перехода = новый builtin в enum + модель `type_params` + запись
  в реестре. Таблиц не прибавляется.

---

## 8. Потребители (кто читает, что гарантируем)

| Потребитель | Читает | Гарантия |
|---|---|---|
| Pathfinding (карта) | `transitions` SQL, реализация и назначение портала, `is_active`, `side.is_accessible`, `is_bidirectional` | разрешённое направление и актуальное состояние доступа; graph-портал проверяет блокирующие маршрут барьеры, coordinate игнорирует граф. Правило проверки сторон, включая fall, уточняется в §10 |
| Pathfinding (интерьер) | pack-переходы здания | те же поля, тот же POJO |
| SceneInit / WP-13 | ближайший `entry=true` переход владельца с discovered стороной `destination` | `main_entrance` предпочтительнее; `hidden_entrance` — только если discovered |
| LLM scene context | `display_name` стороны, тип, хост обоих endpoint'ов | «люк в погребе Ржавого Якоря ведёт в Сырую пещеру» без вывода по координатам |
| Game actions | `is_active`, `is_bidirectional`, `side.is_accessible`, `origin=runtime` create | запечатать/открыть/взломать/проломить — патчи полей, не новые таблицы |

### 8.1 CRUD переходов — application/persist, не генератор

**Решение мастера 2026-10-05:** для создания и изменения существующих
переходов нужны CRUD-операции. Генератор материализует данные; управление
сохранённым состоянием выполняет application-сервис через repository:

- **Create:** сохранить переход и обе стороны атомарно, проверить ссылки,
  тип и параметры до записи.
- **Read:** получить переход по UID и выборки по локации/уровню/узлу
  согласно поддержанным видам назначения.
- **Update:** явно изменить поля перехода/сторон через один контракт
  валидации; изменение рабочего состояния не подменять перегенерацией.
- **Delete:** удалить SQL-переход и связанные стороны атомарно, обработать
  зависимые ссылки согласно FK/доменному контракту.

Операции применяются к SQL-ярусу; read-only pack генератором или CRUD
«на месте» не редактируется. CRUD не означает автоматический reset
пользовательских изменений при regenerate. Политика согласования
повторной генерации и существующего состояния определяется отдельно,
а не скрытыми side effects generator/persist.

---

## 9. Вне scope этого ТЗ

- Алгоритм pathfinding и стоимость переходов (`travel_ticks` interior — нет,
  как сейчас).
- DAG-ноды (scene context, навигация) — gate DAG, по общему правилу.
- Магма-телепорт, climate/terrain переходы по terrain-категориям.
- Генерация самого `location_complex` (отдельное ТЗ после
  `nl-typed-host-payload`).
- Персональное discovery персонажей — отдельная большая тема, не scope
  данного генератора (решение мастера 2026-10-05). Генератор не определяет
  общую/персональную видимость и не создаёт систему player-state.
- Выбор session/scene якоря WP-13 — обязанность потребителя (§8), не
  генератора. Правила ранжирования входов не являются его входным gate.
- Обратная совместимость старого JSON bundle импорта — задача import-слоя,
  не генератора; конвертация старого формата не согласована.

## 10. Открытые вопросы

1. **Закрыто 2026-10-05:** стороны хранятся в отдельной `transition_sides`,
   как в §2. Вариант 2×колонок на transitions не используется.
2. Pack-ярус: нужен ли индекс «какие pack-переходы касаются уровня X» в
   manifest, или достаточно читать layout здания целиком.
3. Переходы между **уровнями комплекса** (крипта L1 ↔ L2): pack или SQL?
   По §4 — intra-location → pack; но комплекс может генерироваться поуровнево
   (lazy). Решить вместе с ТЗ `location_complex`.
4. **Назначение портала:** точная typed форма ссылки на локацию/узел/точку,
   допустимые сочетания с graph/coordinate. **Задание назначения в
   генераторе портала и правило прибытия в локацию — отложенный техдолг
   PORTAL-T-1, P3**, решение мастера 2026-10-05. Не приоритет текущей работы.
   Общая абстракция и две реализации утверждены (§3.4); обязательные места
   прибытия/«ближайший вход»/«центр»/автоматический resolver не утверждены.
5. **Множественность и стороны:** хранение нескольких объявленных назначений,
   их выбор, связь node↔portal и состояние стороны destination при назначении-локации.
   Это не обязательный набор статических Transition на каждую клетку назначения.
   **Отложено, не приоритет** (решение мастера 2026-10-05).
6. **Идентичность портала:** stable UID при изменении назначения; проекция
   endpoint destination в SQL/POJO без обязательных фиктивных xyz; поведение обратного
   прохода для назначения-локации. **Идентичность изменяемого портала и
   обратный проход отложены, не приоритет** (решение мастера 2026-10-05).
   Зависимые реализации не начинать в текущем заходе; независимые
   контракты переходов не блокируются этим обсуждением.
7. **Доступность стороны:** `is_accessible` — управляемое движком состояние
   (§2 инв. 8), не направленность. Требуется определить проверку исходной/
   целевой стороны при проходе; пример fall с недоступной destination не является
   основанием автоматически менять обе стороны на true.
   **Уточнение правила отложено, не приоритет** (решение мастера 2026-10-05).
8. **Закрыто:** nullable owner wilderness допустим (§2 инв. 3).
   Явное значение пространства без NL — `surface` по умолчанию.
   Отсутствие parent корневой локации не означает отсутствие её UID/host.
9. **Закрыто:** дверь/калитка — проход, ей не нужны отношения parent/child.
   Area NL не создаётся только ради host FK перехода; outdoor стороны
   могут использовать surface (§1, §5). Parent здания не меняется.
10. **Изменения существующих переходов:** нужны CRUD в application/persist
    (§8.1), не логика изменения состояния внутри генератора.
11. **Surface — принято; алгоритм отложен:** генератор должен самостоятельно
    искать ближайший допустимый выход из возможных комбинаций (лестница,
    тоннель и т.д.). Критерий близости, допустимость комбинаций и их сборка
    — TODO SURFACE-T-1, P3; не приоритет текущей работы. Surface не требует
    ручного объявления фиксированных xyz или наличия NL в wilderness.

## 11. Границы и порядок текущей имплементации

Детальная последовательность и зависимости — в согласованном
[плане location-transitions](../.cursor/plans/location-transitions.md).
Текущая поставка: контракт физических переходов и реестр, SQL со сторонами,
application CRUD, structural/outdoor producers, interior pack и чтение данных.
Порядок: контракт → аддитивная схема/реестр → validation/repository/CRUD →
подготовка pack/extract → structural API → проверка write/read →
переключение production → gates → объединённое чтение → зачистка legacy.

Портал остаётся общей абстракцией с обеими реализациями (§3.4).
Прежний каркас «порталы первым функциональным шагом» заменён решениями
мастера 2026-10-05: operational portal producer, destination projection,
перенос `portal_*` и исполнение возвращаются отдельно после отложенных
контрактов §10. До этого существующие node/import поля сохраняются.

Surface — явное пространство по умолчанию, без обязательной NL или ручных xyz.
Поиск ближайшего допустимого выхода и сборка комбинаций генератора —
SURFACE-T-1, не приоритет. Parent/child не prerequisite прохода.

WP-13 выбор якоря, navigation/traversal, discovery, DAG/game actions,
новый bundle import/conversion и lazy-комплексы — отдельные темы,
не блокирующие приёмку текущего generator/storage/CRUD scope.
Legacy passage/entry таблицы удаляются после переключения действующих
callers и готовности чтения SQL/pack.
