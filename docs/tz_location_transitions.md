# ТЗ: Переходы (`Transition`) — единый шаблон на весь движок

**Статус:** черновик, до согласования с мастером. Код не трогать до плана
(`.cursor/plans/`). Домен **общий для движка**: не срез `tz_locations`, а
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

- **Transition** — ориентированное или двунаправленное ребро между двумя
  **endpoint'ами**. Единственная сущность домена.
- **Endpoint** — «где стоишь, когда проходишь»: клетка `(x, y, z)` в
  глобальных координатах `map_cells` + опциональный `level_uid`
  (`NULL` = открытое пространство / terrain, не уровень локации).
  **Хост endpoint'а** (локация, в чьём пространстве клетка) — `level.location_uid`
  при `level_uid`, иначе `host_location_uid` endpoint'а (NL territory /
  settlement / district; `NULL` = дикая местность без NL). Хост **явный**, по
  координатам не выводится (тот же принцип, что `parent_location_uid`,
  `tz_locations` § Scope = позиция в parent-цепочке).
- **Side (сторона)** — проекция перехода на один endpoint: видимость,
  доступность, overrides сложности. У перехода **ровно две** стороны `a` / `b`.
- **Тип перехода** — единственная ось классификации: форма **и** семантика
  входа (`main_entrance` — парадный вход в локацию, `service_entrance` —
  чёрный, `door` — дверь без семантики входа, `staircase`, `hatch`, `portal`,
  `fall`…). N+1 реестр `worlds.transition_type_registry` поверх builtin enum
  (решено: словарь `tz_building_generator` §3.6 — часть реестра, отдельной
  оси «роль» нет).
- **Направление** — для типов `main_entrance`/`service_entrance` endpoint `b`
  = **входимая** локация (owner стороны `b`), `a` = откуда входят. Для
  симметричных типов (`door`, `staircase`, `tunnel`) порядок `a`/`b` не
  несёт смысла.

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
  type_params           JSON   -- параметры builtin-типа, pydantic per type (§7); portal: portal_type graph|coordinate, blocked_behavior_override
  display_name, glossary_ref, tag_refs
  -- endpoint a
  a_level_uid           FK location_levels, nullable
  a_host_location_uid   FK named_locations, nullable   -- хост при a_level_uid IS NULL
  a_x, a_y, a_z         int (глобальные map_cells)
  a_node_uid            FK connection_nodes, nullable   -- endpoint лежит на узле графа (portal graph-типа, ворота, порог) — К7
  -- endpoint b
  b_level_uid, b_host_location_uid, b_x, b_y, b_z, b_node_uid   -- симметрично
  -- вертикаль implicit: a_z ≠ b_z

transition_sides
  (transition_uid, side) PK, side ∈ {'a','b'}
  owner_location_uid    FK named_locations   -- чей это «вход» с этой стороны (=host endpoint'а, но может быть глубже: комната)
  is_discovered         bool
  is_accessible         bool
  entry_difficulty_override  int nullable 0–100
  guard_level_override       int nullable 0–100
  display_name          nullable   -- «Северные ворота» / «Лаз за бочками»
```

**Инварианты:**

1. Две стороны всегда есть (даже у `fall` — у стороны `b` `is_accessible`
   может быть `false`).
2. `is_bidirectional` читается **только** для builtin-типов с
   `directional=true` (`portal`, `fall`); `false` ⇒ проход только `a → b`,
   обратный — **не** вторая строка, а флип флага игровым действием
   (`tz_structure_connections` §4.1). Для остальных типов флаг игнорируется
   и писаться должен `true` (дефолт), не как маркер «это вход» (К2).
3. `a_level_uid IS NULL AND a_host_location_uid IS NULL` ⇒ дикая местность;
   допустимо только для `origin='runtime'` (пролом, ad-hoc) и для
   endpoint'ов на terrain вне любого NL.
4. Тип из реестра поверх закрытого enum движка. Генератор сравнивает тип
   через engine-enum (как HY-5), реестр расширяет display.
7. Здание: **≥1** `main_entrance` со стороной `b.owner = building`, **≥0**
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
9. **Портал** (`type_params.portal_type`, `tz_structure_connections` §4.1):
   `coordinate` — endpoint `b` = клетка, граф игнорируется; `graph` —
   `b_node_uid` обязателен, endpoint `b` = клетка узла, дальнейшее
   движение — по рёбрам графа от узла; `blocked_behavior_override` — только
   для `graph`. Несколько назначений = несколько `Transition` с общим `a`.
   Портал — **всегда SQL-ярус** (§4), даже внутри одного здания: он
   рантайм-изменяем (К3).
10. **Детерминизм uid** (К10): `transition_uid` для `origin ∈ {authored,
    generated}` — детерминированный uuid5 от `world_uid` + тип + endpoint'ы
    (`(a_x,a_y,a_z) → (b_x,b_y,b_z)`), тот же приём, что `_det_uuid` для
    passages и `entry_uid(b_uid, role, passage_uid)` сейчас. Повторная
    генерация мира с тем же seed даёт те же `transition_uid` в pack и в SQL —
    ссылки (`a_node_uid`, `connection_nodes.transition_uid`, scene anchors)
    переживают regenerate. `origin='runtime'` — uuid4 (создан действием, не
    воспроизводится генерацией). Формула — **только** через общий helper
    `app/utils/deterministicIds` (решено): два корня — `world_uid`
    (идентичность сущностей: NL, levels, transitions, nodes) и `world_seed`
    (pack/relief job-uid и rng) — это **разные функции одного helper'а**, не
    две конвенции; ad-hoc `uuid5(...)` / `Random(f"...")` вне helper'а
    запрещены. Cross-cutting ТЗ — `project_data_storage_tz.md`
    § Детерминированные uid (написать).

---

## 3. Классификация явных переходов

### 3.1 Тип (реестр `transition_type_registry`, N+1)

Объединение сегодняшних словарей: `tz_locations` § `passage_type_registry`
(`door/doorway/archway/corridor/staircase/ladder/rope/bridge/portal/fall`) +
`tz_building_generator` §3.6 (`main_entrance/service_entrance`) + новые для
cross-location (`hatch/tunnel/gate/breach`).

| `system_type` | Семантика | `entry` | `directional` | Вертикаль | Создаёт |
|---|---|---|---|---|---|
| `main_entrance` | парадный вход в локацию (`b` = входимая) | да | нет | нет | structure generator (шаблон `entry_point`), C23 ворота поселения |
| `service_entrance` | чёрный вход в локацию | да | нет | нет | structure generator (`back_entry_point`) |
| `hidden_entrance` | тайный вход; `b.is_discovered=false` по умолчанию | да | нет | любая | generator (`location_complex`), runtime |
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

- `entry=true` — тип несёт семантику «вход в локацию `b.owner`»: участвует
  в C20-инварианте, WP-13 выборе якоря, LLM «входы локации». Сегодняшний
  `entry_role` (`front`/`service`) → **тип** `main_entrance`/`service_entrance`;
  `tz_settlement_outdoor` C20 переписать в терминах типов.
- `directional=true` — только эти типы читают `is_bidirectional` (К2).
- Ворота поселения на периметре footprint (C23 `settlement_gate`) — тип
  `main_entrance`/`service_entrance` с `b.owner = settlement`; `gate` — для
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

Класс **вычисляется** из endpoint'ов, не хранится. Cross-branch — именно тот
случай, ради которого parent и переход разведены.

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
| **Структурный генератор** — наружная дверь | `LocationPassage(from=NULL, to=level, is_bidirectional=False, type=main_entrance)` → extract → `LocationEntryPoint(entry_role)` | `Transition(type=main_entrance|service_entrance, a=(street cell, host=district/settlement NL), b=(level, cell))`; `b.owner=building`; тип — из `EntryPoint.passage_type` шаблона как сейчас; `is_bidirectional` не пишется (дефолт) |
| Структурный генератор — внутренние | `LocationPassage` в pack | `Transition` в pack, класс intra-location, обе стороны `owner=building` (или room), типы `door/doorway/archway/staircase` |
| **Settlement topology (C23)** — `settlement_gate` | `connection_nodes.node_type=settlement_gate` | узел графа остаётся (`graph_level=city`), получает `transition_uid` → `Transition(type=main_entrance|service_entrance, a=outside (host=territory), b=inside (host=settlement))`; `b.owner=settlement` |
| Барьер участка (`perimeter_barrier`) — калитка | нет | `AreaAssembler`: `Transition(type=gate)` sibling district↔area **только при наличии барьера** (К7); без барьера переход не создаётся. Граф улиц (`building_entrance`/`yard_path`) — независимо |
| **Порталы** (`tz_structure_connections` §4.1) | `portal_*` колонки на `connection_nodes` | `Transition(type=portal, is_bidirectional, is_active, type_params.portal_type)`; `a_node_uid` = узел-портал; `coordinate` ⇒ `b` = клетка, граф игнорируется; `graph` ⇒ `b_node_uid` обязателен, движение дальше по рёбрам, `blocked_behavior_override` в `type_params`; **несколько** `portal_destinations` ⇒ несколько `Transition` с общим `a`. Всегда SQL (инвариант 9) |
| **`location_complex`** (крипта, шахта) | — | уровни комплекса = `location_levels`; вход — `Transition(type=main_entrance|hidden_entrance, b.owner=complex)` cross-branch из подвала здания / с поверхности леса; parent комплекса — по смыслу (лес/гора), не по входу |
| **Ad-hoc** (O3) | «можно добавить entry после успеха» | `Transition(type=breach, origin=runtime)` создаётся движком после успешного действия; обе стороны `is_discovered=true` для совершившего |
| **`fall`** | в реестре passage | `Transition(type=fall, is_bidirectional=false, origin=runtime)` |
| **WP-13 `location_entry`** | «ближайший discovered entry» | якорь = ближайший переход `entry=true` с `b.owner=location`, `b.is_discovered AND b.is_accessible`, предпочтение `main_entrance` |
| **Pathfinding** | три таблицы | один граф: terrain A* + `transitions` (SQL) + pack-переходы внутри здания |

---

## 6. Конфликты, найденные при сверке (требуют решения мастера)

| # | Конфликт | Где | Предложение |
|---|---|---|---|
| **К1** ✅ решено | Два словаря типов в **разных ТЗ**: `tz_building_generator` §3.6 (`main_entrance/service_entrance` — шаблон здания, enum `PassageType`) и `tz_locations` § `passage_type_registry` (`door/…/portal/fall`) — ни один не содержит другой; `entry_role` на `location_entry_points` дублирует `main/service` третьим словарём. | `passageType.py`, `tz_locations` § passage_type_registry, `tz_settlement_outdoor` C20, `settlementOutdoorExtract._role_for_passage` | **Один** реестр = объединение (§3.1); `main_entrance`/`service_entrance` — **типы** с `entry=true`, отдельной оси «роль» нет. `entry_role` удаляется, `_role_for_passage` не нужен. `tz_locations` реестр дополнить, C20 переписать в типах. |
| **К2** ✅ решено | Наружная дверь здания записывается `is_bidirectional=False` как маркер «вход». | `generators/structure/passages/entry.py:83` | Флаг читают **только** `directional`-типы (`portal`, `fall`); остальные игнорируют и пишут дефолт `true`. `entry.py` — убрать явный `False`. |
| **К3** ✅ решено | C20 вариант 1: «interior `location_passages` не писать в SQL» vs требование единого графа переходов для движка. | `tz_settlement_outdoor` C20, `settlementOutdoorSqlPersist` | §4: одна модель, два яруса; **исключение — порталы** обоих видов (`graph` / `coordinate`, инвариант 9) и всё рантайм-изменяемое: всегда SQL. C20 переписать. |
| **К4** ✅ решено | Портал живёт на `connection_nodes` (`portal_type`, `portal_destinations`, `portal_bidirectional`, `portal_is_active`) — вторая реализация направленности/активности рядом с passage. | `tz_structure_connections` §4.1, DDL `connection_nodes` | Портал = `Transition(type=portal)`; `connection_nodes` хранит только `node_type=portal` + `transition_uid`(s). `portal_*` колонки удалить. Несколько назначений = несколько переходов с общим endpoint `a`. **Отдельный шаг плана, первый** (§11 T1). |
| **К5** | `location_entry_points` знает, **чья** это дверь (`location_uid`) и **куда** ведёт (`leads_to_level_uid`), но **не знает, в чьём пространстве стоит клетка снаружи**: для люка в подвале таверны строка пещеры хранит `(x,y,z)` подвала, а «это подвал таверны» можно узнать только поиском `map_cells` по координатам — при z-стекинге на одной клетке могут быть и подвал, и пещера (тот же запрет, что для `parent_location_uid`: overlap ≠ containment). | DDL, `LocationEntryPoint`, extract | В `Transition` хост **обоих** endpoint'ов явный (`a_level_uid`/`a_host_location_uid`, `b_*`). Отдельная таблица входов не нужна: «входы локации X» = `transitions WHERE entry=true AND b.owner = X`. Таблицу удалить, repo переписать на этот запрос. |
| **К6** ✅ решено | Координаты: `location_passages.from_x/from_y` — **локальные** для уровня (offset = `MIN(map_cells.x/y)`, нигде не хранится — `tz_locations` отложенное «Coordinate bridging»); `location_entry_points.x/y/z` — **глобальные**. Один endpoint не может быть в двух системах. | `tz_locations` §1623, DDL | Endpoint — только **глобальные** `map_cells` координаты (z у уровней уже абсолютный). Локальные координаты — закрыть tech debt, не тащить в новую модель. |
| **К7** ✅ решено | На пути улица → дом три разных объекта трёх доменов, которые нельзя склеивать: (1) **дверь здания** `main_entrance` — structure generator, есть всегда (C20); (2) **калитка участка** `gate` — `AreaAssembler`/территория, существует **только если** по периметру участка есть `perimeter_barrier` (wall / fence); нет барьера — нет перехода, двор открыт; (3) **граф улиц** `building_entrance` + `yard_path` — connections, существует **независимо** от (1) и (2): это маршрутизация, не проход. | `tz_structure_connections` §5.1.3, `tz_assembler_hierarchy` §69, §442, `tz_city_generation` §perimeter_barrier | Граф не обязан иметь узел на каждую дверь и переход не обязан иметь узел. `a_node_uid`/`b_node_uid` — опциональная ссылка, когда endpoint фактически лежит на узле (координаты сверяются на persist). Обязателен узел только там, где переход **и есть** элемент графа: `settlement_gate` (`main|service_entrance` поселения) и `portal(graph)` (инвариант 9). `yard_path` при наличии барьера проходит через клетку `gate`. |
| **К8** ✅ решено | `transition_type_registry` (N+1, мастер) vs builtin-поведение (`entry`, `directional`, вертикаль, portal-механика). Открытый реестр не может нести поведение. | `tz_locations` § passage_type_registry | N+1 запись **обязана** ссылаться на закрытый тип движка (`behaves_as: TransitionType`); поведение, флаги и `type_params`-модель — только от builtin; запись без `behaves_as` — ошибка импорта. |
| **К9** ✅ решено (частично дубль) | `location_levels.access_mechanic` и переходы оба отвечают на «как попасть», но на разные вопросы. | DDL `location_levels`, `LocationLevel`, `tz_building_generator` §214 | **Механика доступа отвечает: закрыт ли данный проход и чем открывается** → поле `access_mechanic` на `Transition` (инвариант 8), общий закрытый enum механик. `location_levels.access_mechanic` остаётся только для `isolated` уровней без переходов — «ребра нет; по этой механике движок его создаст». `tz_building_generator` §214 и `tz_locations` § location_levels — зафиксировать границу. |
| **К10** (мелочь) | Расхождение имени колонки между ТЗ и схемой: в `tz_locations` § `location_passages` схема записана как `passage_uid, world_id, …`, а в `0001_initial.sql` и dataclass `LocationPassage` колонка называется `world_uid` — как и во всех остальных таблицах (`named_locations.world_uid`, `connection_nodes.world_uid`). Поведения не меняет; это опечатка в ТЗ, которая при копировании в новую DDL `transitions` дала бы вторую конвенцию имён. | `tz_locations` §940, DDL `location_passages`, `db/models/locationPassage.py` | **Одна конвенция — `world_uid`**, везде: колонка, POJO, формула детерминированного uid. Причина не косметическая: все uid и rng генерации выводятся из `world_uid` (`settlement_cell_rng(world.world_uid, …)`, `_det_uuid(building_uid, …)`, `Random(f"{world.world_uid}_{scope_uid}_…")`); второе имя в одном из слоёв = второй источник seed, и повторная генерация мира по тому же seed даст другие `transition_uid` — pack и SQL разойдутся. Инвариант 10. При T0 исправить `tz_locations` § `location_passages`. |

---

## 7. Расширяемость

- `type_params TEXT` (JSON) на `transitions` — параметры конкретного builtin
  типа (`portal`: `blocked_behavior_override`, `portal_type`; `gate`:
  `width_cells`; `staircase`: `staircase_type`). Валидируется pydantic-моделью
  **per builtin type** (тот же приём, что `location_payload` по `payload_kind`
  в `nl-typed-host-payload`). Не колонки per type.
- Новый вид перехода = новый builtin в enum + модель `type_params` + запись
  в реестре. Таблиц не прибавляется.

---

## 8. Потребители (кто читает, что гарантируем)

| Потребитель | Читает | Гарантия |
|---|---|---|
| Pathfinding (карта) | `transitions` SQL, `is_active`, `side.is_accessible`, `is_bidirectional` | ребро проходимо только в разрешённом направлении и при обеих `is_accessible` сторонах |
| Pathfinding (интерьер) | pack-переходы здания | те же поля, тот же POJO |
| SceneInit / WP-13 | ближайший `entry=true` переход владельца с discovered стороной `b` | `main_entrance` предпочтительнее; `hidden_entrance` — только если discovered |
| LLM scene context | `display_name` стороны, тип, хост обоих endpoint'ов | «люк в погребе Ржавого Якоря ведёт в Сырую пещеру» без вывода по координатам |
| Game actions | `is_active`, `is_bidirectional`, `side.is_accessible`, `origin=runtime` create | запечатать/открыть/взломать/проломить — патчи полей, не новые таблицы |

---

## 9. Вне scope этого ТЗ

- Алгоритм pathfinding и стоимость переходов (`travel_ticks` interior — нет,
  как сейчас).
- DAG-ноды (scene context, навигация) — gate DAG, по общему правилу.
- Магма-телепорт, climate/terrain переходы по terrain-категориям.
- Генерация самого `location_complex` (отдельное ТЗ после
  `nl-typed-host-payload`).

## 10. Открытые вопросы

1. `transition_sides` как отдельная таблица vs 2×набор колонок на `transitions`
   (`a_is_discovered`, `b_is_discovered`, …). Таблица чище для
   `get_by_location`; колонки — проще bulk persist. Склоняюсь к **колонкам**
   (ровно две стороны, join не нужен); оставлено на решение.
2. Pack-ярус: нужен ли индекс «какие pack-переходы касаются уровня X» в
   manifest, или достаточно читать layout здания целиком.
3. Переходы между **уровнями комплекса** (крипта L1 ↔ L2): pack или SQL?
   По §4 — intra-location → pack; но комплекс может генерироваться поуровнево
   (lazy). Решить вместе с ТЗ `location_complex`.

## 11. Порядок имплементации (каркас плана, детали — `.cursor/plans/`)

По слоям: контракт → схема → writers → readers → зачистка. Порталы — первым
шагом (решение мастера, К4): это единственный сегодня **рантайм-изменяемый**
переход, на нём проверяется, что модель несёт направленность/активность.

| # | Шаг | Слои | Done |
|---|---|---|---|
| T0 | ТЗ-sync: `tz_locations` (реестр §3.1, удалить § `location_entry_points`, К10), `tz_structure_connections` §4.1 → ссылка сюда, `tz_settlement_outdoor` C20 в типах | docs | ссылки сходятся |
| **T1** | **Порталы → `Transition`** (К4): `TransitionType` enum + `type_params` модель `portal`; DDL `transitions` (+ стороны по §10.1) **без** удаления старых таблиц; `connection_nodes.portal_*` → `transition_uid`; writer `StructureAreaAssembler(portal)`; game actions портала — патчи `transitions` | dataModel, `0001`, db/models, persist, actions | портал живёт только в `transitions` |
| T2 | Наружные входы: structure generator пишет `Transition(main|service_entrance)` с явными хостами `a`; extract/persist → `transitions`; `location_entry_points` удалить; C20 инвариант на типах; `entry.py` без `is_bidirectional=False` (К2) | generator passages, `settlementOutdoorExtract/SqlPersist`, repo | C6/C20 smoke = baseline, таблица входов удалена |
| T3 | `location_passages` → `transitions` (rename + глобальные координаты, К6); pack-ярус пишет тот же POJO | `0001`, db/models, structure passages builder, pack writer | один POJO в SQL и pack |
| T4 | C23 `settlement_gate` → `Transition(main|service_entrance, b.owner=settlement)` + `transition_uid` на узле; `building_entrance` узел — опциональная ссылка (К7) | topology planner, connections persist | ворота = переход |
| T5 | Readers: WP-13 якорь, repo `entries_of(location)`, pathfinding-слой читают `transitions` | pack/refine, repos | старые чтения удалены |
| T6 | Runtime-типы `breach`/`fall`/`hidden_entrance` создание из game actions (`origin=runtime`) | actions / engine — **DAG gate** | по общему правилу DAG |
