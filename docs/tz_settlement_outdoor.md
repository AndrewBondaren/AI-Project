---
name: tz-settlement-outdoor
description: "Outdoor settlement на запечённом World Pack — дерево локаций, граф участков, эталон vs дельта. Не генератор зданий и не relief mill."
---

# ТЗ: Outdoor settlement на Pack

**Статус:** целевая архитектура (согласовано 2026-08-30). **O1–O4 locked (C14–C16, C19–C20), C17–C18, C21.** Impl-план outdoor: [`.cursor/plans/settlement-outdoor-pack.md`](../.cursor/plans/settlement-outdoor-pack.md). **P13 High:** [`.cursor/plans/c21-plot-ground-z.md`](../.cursor/plans/c21-plot-ground-z.md) — код по явной просьбе.

**Зачем отдельный документ:** алгоритм застройки — [`tz_city_generation.md`](./tz_city_generation.md); участок/здание — [`tz_assembler_hierarchy.md`](./tz_assembler_hierarchy.md) и [`tz_building_generator.md`](./tz_building_generator.md); земля/grade — [`tz_world_pack_storage.md`](./tz_world_pack_storage.md) и [`tz_terrain_relief.md`](./tz_terrain_relief.md). Здесь только **склейка**: оркестрация, куда писать эталон, дерево имён, экспорт. Алгоритмы не копировать — ссылки на пункты.

Генератор зданий и relief TZ **не расширять** этим слоем.

---

## 1. Scope

Поверх **уже запечённого** pack получить:

- дерево `named_locations` для поселения (районы + здания);
- outdoor-город как **эталон** в pack (граф участков);
- граф улиц в SQL.

**Предусловие:** light/full/detailed bake земли есть. Это **не** четвёртый bake mode и не `detailed_bake`.

### Вне слоя

| Тема | Куда |
|---|---|
| Интерьеры, rooms, `location_passages` между комнатами | [`tz_city_generation.md`](./tz_city_generation.md) §5 фаза 3; [`tz_building_generator.md`](./tz_building_generator.md) |
| DAG wiring, `lazy_settlement` | [`tz_world_generation_dag.md`](./tz_world_generation_dag.md) — Gate: DAG; позже тот же orchestrator |
| Growth (`place_building`, пристройка) | city §11.5 growth; DAG player build |
| LLM-имена географии | [`tz_world_generation_dag.md`](./tz_world_generation_dag.md) U13 |
| Mill / paint / grade | [`tz_terrain_relief.md`](./tz_terrain_relief.md) § Caller |
| Процедурная расстановка **новых** городов на wilderness | нет в city TZ — не делать |
| Debug ASCII / dump | [`tz_pack_ascii_render.md`](./tz_pack_ascii_render.md) — только читает merge, не SoT |
| World Snapshot на ход | [`tz_world_snapshot.md`](./tz_world_snapshot.md) — другой модуль |
| Радиус сцены / контекст событий вокруг игрока | отдельное ТЗ (не это); контракт здесь — **C18**, чтобы не разъехалось |

---

## 2. Карта ссылок (не дублировать)

| Тема | SoT | Что брать |
|---|---|---|
| Skeleton-first, фазы 1–2, district templates, footprint v1 | city §2, §5 фазы 1–2, §6, §9 | generate |
| `CitySkeleton`, `dominant_material` | city §3, §3.1 | поля поселения / post-assemble |
| Шов pack, город на ребре тайла | city §1; pack WP-19; relief-v1 **C29** | не клипать layout по тайлу |
| Слои assembler, вход Settlement | assembler §1–§3 | не вызывать Structure вне stack в этом слое |
| Участок: `AreaSlot` / `AreaLayout` | assembler §7.1–§7.2 | **persist-контракт геометрии**; **C21:** z и порог — assembler участка, не район; участок ≠ обязательно здание |
| generate-first, cache шаблона | assembler §7.7 | RAM; не второй generate при persist |
| Координаты footprint | assembler §7.5; city §9.6 | `settlement_meter_rect` |
| Дороги city/district, `settlement_gate` | connections §5, **§5.1**; city §11.5 | SQL `connection_*` |
| Шаблон здания, `BuildingLayout`, levels, entry на комнате | building §3.6, §7, §8.9, §11 | не копировать схему шаблона |
| Что не v1 здания (мебель и т.д.) | building §12 | не тащить |
| Pack vs Patch, WP-1…7 | pack § Целевая архитектура, инварианты | эталон vs ход |
| `location_terrain` file-per-location | pack WP-19, § L2 локации | **земля volume**, не город |
| Merge read | pack WP-20, § Layer priority | patch выше эталона |
| Modification ≠ bake | pack § Слой модификации мира | взрыв → Patch Store |
| L0 pins поселения | pack § L1; [`tz_map_light_bake.md`](./tz_map_light_bake.md) settlement contributor | occupancy карты |
| Тип поселения / footprint | pack REVIEW-3; `locationFootprintPolicy` | не `== "settlement"` |
| Дерево имён, типы, SceneInit | locations § Иерархия, § Engine flow | SQL skeleton; `location_uid` = якорь, не объём сцены (**C18**) |
| Вход в здание | locations § `location_entry_points`, § `location_levels` | persist дверей/этажей, не телепорт и не смена сцены на этаж |
| JSON skeleton vs pack zip | bundle WP-24 / pack WP-24; bundle § C `map_cells` reject | экспорт |
| Grade не в этом job | relief § Caller, § Граница слоёв | не mill при generate city |

---

## 3. Эталон vs дельта

| Хранилище | Содержимое этого слоя | Мутация | Экспорт |
|---|---|---|---|
| **Pack** (земля уже есть) | слой **структуры города**: граф районов → участков | master write после generate | pack zip |
| **SQL** | `named_locations` (settlement → district → building), `connection_*`, `location_levels` + `location_entry_points` зданий | тот же generate | JSON skeleton |
| **Patch Store** | ход: взрыв, пристройка, `terrain_delta` / `climate_delta` | каждый ход | **не** world bundle |

Pack земли (`world_map`, wilderness, `l.{uid}.terrain.zst`) **не** переписывать этим job. Authored city в патчах не экспортируется — поэтому эталон города не класть в `map_cell_patches`.

Уточнение к pack **WP-3:** gameplay persist → Patch Store. **Authored outdoor city** → pack city layer (master), не патчи.

---

## 4. Экспорт

| Артефакт | Состав | Не входит |
|---|---|---|
| JSON skeleton | дерево `locations` + `connection_nodes` / `connection_edges` + шаблоны library | клетки, pack blobs |
| Pack zip | L0/L2 **земля** + **отдельный** city-structure слой | `map_cell_patches` сессии |
| Session | патчи | world bundle |

Перенос локации между мирами — subgraph + remap ([`tz_world_bundle.md`](./tz_world_bundle.md) § Location transfer), не library. Pack-геометрия участка после переноса — rebake/attach, не этот документ.

---

## 5. Оркестрация

Один application-сервис (имя цели: `SettlementOutdoorOrchestrator`). **Не** generator, **не** route, **не** DAG.

```
Route (debug HTTP)
  → orchestrator.materialize(world_uid, location_uid)
       → SQL: NamedLocation поселения
       → тип: named_location_uses_settlement_meter_footprint
       → terrain: MapCellQueryFacade по footprint (pack + патчи), не get_all мира
       → SettlementGeneratorService.generate_layout  (pure, city §5 фаза 2)
       → SettlementPersistService: SQL дерево/граф/levels + pack city structure
```

| Слой | Делает | Не делает |
|---|---|---|
| Route | HTTP → orchestrator | generate, persist, `get_all` |
| Orchestrator | порядок шагов, skip если эталон уже в pack | алгоритм улиц/зданий |
| `SettlementGeneratorService` / assembler | layout | SQL, pack I/O |
| Persist | запись SQL + pack city layer | LLM, HTTP |
| `MapCellQueryFacade` | read merge | generate |

Идемпотентность: skip, если city-structure для `location_uid` уже в pack (не зонд патчей).

Debug `POST …/generate-settlement` — тонкая оболочка над orchestrator (city §11.5 Debug API). Production позже: нода DAG → тот же метод ([`tz_world_generation_dag.md`](./tz_world_generation_dag.md) Gate).

---

## 6. Геометрия: граф участков, не dump клеток

SoT объекта — assembler §7.1: район ссылается на **участки**; участок (`AreaLayout`) хранит **себя** (слот, facing, забор/двор) и **опционально** здания. Участок не синоним здания.

**Z — участок, не район (C21).** Район не выравнивает слоты и не копирует z улицы. Порог к улице (дверь / ворота / край) выбирает assembler участка (§5.1.1). Pack-земля не террасируется (C1). Код копирует одну z района на все слоты — **P13**.

```
pack city structure
  settlement_uid
  districts[]          → uid + ref
    areas[]            → uid + AreaSlot + shell участка
      buildings[]      → named_location uid + outdoor shell (поле объекта)
```

- Клетки — **поле** участка/здания, не SoT всего города.
- Не flatten в `collect_geometry_meter_cells` на весь settlement.
- Не FineTerrain column-runs и не смесь с `l.{uid}.terrain.zst` (pack § L2 location = земля).
- Occupancy метровой матрицы **не persist**. Резерв на карте — L0 pin + `city_size` / footprint (pack § L1, light bake settlement contributor). `plan_footprint_occupancy_cells` как flood в патчи — запрещён.

**SQL vs pack:** участок **не** `location_type` и не узел SceneInit. Дерево имён: settlement → district → building (locations § Иерархия). Пространственная группировка — pack (district → area → building uid).

Дороги — `connection_*` в SQL (connections §5.1), не дети участка. Уровни улиц как сцены — отложить (locations § `location_levels` только для зданий в этом слое).

Outdoor shell на объекте здания: envelope, видимый с улицы (`wall` / `roof` / `door` / `window` / `archway` / foundation + barriers участка). Interior cells в RAM для bin-pack (assembler §7.7) — не persist. Комнаты — фаза 3 city.

City-level / district barriers — на соответствующих узлах **того же** графа, не в `location_terrain`.

Read: query bbox пересекает участки → вклад клеток в merge. Новый слой **выше** `location` (земля), **ниже** patch (ход). Точная врезка в enum — impl; приоритет pack WP-20 не ломать для patch/scene/path.

---

## 7. Тип поселения

Не `system_location_type == "settlement"`.

SoT: `uses_settlement_meter_footprint` / `named_location_uses_settlement_meter_footprint` — type `settlement` | `district` | legacy `city`, subtype из реестра, либо `system_city_size` из `city_size_registry` (locations § Размер поселения; pack REVIEW-3).

Orchestrator и route используют policy. Нода `lazy_settlement` с литералами size — вне слоя; правится при DAG.

---

## 8. Дерево локаций (контракт persist)

Районы **писать сразу** в `named_locations` (`system_location_type=district`, parent=settlement). Здание: `parent_location_uid` = район.

Это контракт extract/persist, не отдельный инвариант мира и не «исключение для локаций». Нет района в выходе assembler — сломан extract.

Имена районов — `display_name` шаблона ([city §9](./tz_city_generation.md)), без LLM.

`location_levels` + `location_entry_points` — **для зданий**, сейчас (locations § Точки входа, § `location_levels`; building §8.9 / §3.6 как источник в layout). Levels/entry — этаж и клетка входа, не «сцена = этаж». Объём сцены и соседство — **C18**. Улицы как уровни — отложить. Rooms / interior passages — не этот слой.

---

## 9. Запрещено

| Не делать | Почему |
|---|---|
| Стены / застройка в `l.{uid}.terrain.zst` | это земля WP-19 |
| Occupancy-flood в `map_cell_patches` | эталон ≠ ход; масштаб метров |
| Плоский city-wide voxel как SoT | участок — единица, assembler §7 |
| Одна плоскость `ground_z` на район / `max(z)` AABB → все здания | выравнивание зданий — участок (**C21**, **P13**) |
| Оркестрация в route | layer-boundaries |
| `get_all` клеток мира как terrain для assembler | facade по footprint |
| Mill/paint/grade в этом job | relief § Caller |
| Процедурные новые города на wilderness | нет в city TZ |
| Интерьеры / DAG / growth / LLM-имена | §1 вне слоя |

---

## 10. Слои имплементации (после замка §13)

Порядок **архитектуры**, не vertical slice продукта. План: [`.cursor/plans/settlement-outdoor-pack.md`](../.cursor/plans/settlement-outdoor-pack.md). Код — когда мастер скажет «делай».

1. POJO/wire city-structure (district → area refs, Area persist).
2. Pack I/O слоя + merge + `get_volume(footprint)` на facade.
3. Extract: `NamedLocation` района на layout; persist Area; убрать occupancy flood из persist path.
4. Persist: SQL дерево/граф/levels/entry + pack graph. Не патчи для эталона.
5. Orchestrator — один метод.
6. Route — thin.

---

## 11. Расхождение с более старыми пунктами

| Было | Теперь |
|---|---|
| city §11.5 persist → `map_cells` / occupancy scopes как эталон | эталон = pack city structure + SQL имена; §11.5 **generate scopes** и growth — как были |
| pack WP-3 «settlement layout → patches» | authored city → pack; патч только ход |
| pack § L1 «не дублировать SettlementLayout в SQLite» | верно; граф участков в **pack**, не OLTP-клетки |
| `collect_building_locations` parent=settlement | parent=district (§8) |
| SceneInit ground = `min(z) ≥ terrain` | **C17:** вход = `z_offset=0` / entry; подземный город |
| Scene = leaf-building / этаж; телепорт на участок | **C18:** якорь ≠ объём; карта = здание + рядом; события = радиус (другое ТЗ) |
| `DistrictSlot.ground_z` → все здания района | **C21 / P13:** выравнивание участков — assembler участка; порог ≠ всегда дверь |

city §11.4 snapshot / regen — по-прежнему [`tz_world_snapshot.md`](./tz_world_snapshot.md), не этот слой.

---

## 12. Зафиксированные контракты

Не переоткрывать без явной отмены.

| ID | Контракт |
|---|---|
| **C1** | Эталон = pack city-structure + SQL имена/граф. Ход = Patch Store. Земля (`location_terrain` / wilderness / L0) этим job не переписывается. |
| **C2** | Геометрия города = граф **участков** (assembler §7 `AreaSlot`/`AreaLayout`), не city-wide voxel и не occupancy-flood. Клетки — поле объекта. |
| **C21** | **Онтология z участка.** Район **не** выравнивает участки: не одна плоскость, не `max(z)` AABB, не копия z улицы / `DistrictSlot.ground_z`. Участок ≠ обязательно здание (двор+забор, дом у улицы, дом в глубине). `ground_z` слота и **порог к улице** считает `StructureAreaAssembler` по топологии (`door` / `gate` / `parcel_edge` — connections §5.1.1). Не формула «всегда фасад здания». `building.map_z` (если дом есть) может отличаться от `AreaSlot.ground_z`. Луч порог→улица — **только если** `ground_z ≠ z` примыкающей улицы; иначе стык без профиля. Если луч даёт **θ > 45°** — assembler правит `map_z` **этого** дома (вверх или вниз), пока θ = 45° (§5.1.2). **Не** двигать здание в xy к улице. Соседние участки не трогать. Подъезд xy — `yard_path` к **порогу**. Pack-земля не терраса (C1). Пин района — не пол участка. |
| **C3** | Участок **не** `location_type` и не SceneInit. SQL-дерево: settlement → district → building. Area uid только в pack-графе. |
| **C4** | Районы писать сразу (`named_locations`). `parent` здания = район. Это extract/persist, не отдельный инвариант мира. |
| **C5** | District `NamedLocation` и Area uid **синтезируются на extract** из `DistrictSlot` / слота (детерминированный uid). Assembler не ходит в SQL. `collect_building_locations` больше не ставит parent=settlement. |
| **C6** | Тип поселения = `named_location_uses_settlement_meter_footprint`, не `== "settlement"`. |
| **C7** | Occupancy на карте = L0 pin + footprint rect. Не persist метровой матрицы, не `plan_footprint_occupancy_cells` → патчи. |
| **C8** | Outdoor shell здания: `wall` / `roof` / `door` / `window` / `archway` / foundation + barriers участка. Interior cells / rooms / `location_passages` между комнатами — не persist. |
| **C9** | Persist `location_levels` зданий (из `StructureLayout.levels`): абсолютный `z` / `z_height` / `display_name`. Улицы как уровни — отложить. Yard / small_layouts / пустые barriers — как есть. |
| **C17** | «Первый этаж» / вход = шаблонный **`z_offset == 0`** (и/или `entry_point.leads_to_level_uid`), **не** `min(z) ≥ surface terrain`. Подземный город: улица и `building.map_z` уже под землёй; offset 0 всё равно входной этаж. Эвристика locations SceneInit (`z ≥ terrain_z`) — **неверна**, не использовать. |
| **C18** | **Сцена движка ≠ этаж и ≠ одно здание как весь мир.** Персонажа не телепортируют «на участок». `SessionScene.location_uid` — **якорь** в дереве (где персонаж числится), не bounding box симуляции. **Карта:** при входе в здание **добавляем** его оболочку и **оставляем** уже загруженное рядом (улица, соседние участки, окно/дверь наружу). **Контекст событий:** пространство в **радиусе от игрока** (жизнь за окном идёт независимо); величина радиуса — **наружу** (world/engine scalar). Спека радиуса и тиков событий — **другое ТЗ**; этот слой не кодирует «сцена = leaf» и не invent число. Generate поселения по-прежнему пишет полный граф в pack (это эталон, не play-load). |
| **C10** | Дороги = SQL `connection_*` (city/district). Road bed cells в этом слое не обязательны (`collect_edge_cells` сейчас пуст — так и оставить). |
| **C11** | Ядро: `materialize(world_uid, location_uid)` — одно поселение. SQL → bbox terrain → generate_layout → persist. Route на один uid тонкий. Не `get_all` клеток мира. |
| **C12** | Read карты/bbox **включает** rasterize участков в merge: слой города выше `location_terrain`, ниже patch. Play-bbox — окрестность игрока (**C18**), не «только footprint одного здания». Не отдельный debug-render формат. FineTerrain column-runs для города не использовать. |
| **C13** | Вне слоя: интерьеры, DAG, growth, LLM-имена, mill/grade, новые города на wilderness, **радиус сцены / event context** (другое ТЗ; здесь только C18). |
| **C14** | Skip materialize iff **и** файл `l.{uid}.settlement.zst` на диске, **и** запись в manifest, **и** в SQL есть дети (районы/здания). Blob без SQL / SQL без blob — не skip. |
| **C19** | **O4 locked.** Канон = один layout в RAM → encode `.tmp` (вне SQL write-lock) → одна SQL-транзакция (идемпотентный upsert) → `COMMIT` → `os.replace` + manifest + invalidate reader. Encode/publish не внутри открытой SQL write-tx. После COMMIT pack-retry **без** второго generate (tmp или тот же layout). Crash до COMMIT: стереть tmp, полный повтор. Процесс умер после COMMIT, tmp потерян: не skip; журнал pending **или** детерминированный generate с тем же seed — иначе SQL-имена и геометрия разъедутся. Скорость (parallel C16, batch) — после этого протокола, не вместо. |
| **C20** | **O3 locked, вариант 1.** Persist `location_levels` + наружные двери → `location_entry_points` (не interior passages). Роли: **`front`** (парадный) и **`service`** (чёрный). Здание: **≥1 `front`**, **≥0 `service`**. Default NPC/игрок идут объявленными входами (предпочтение `front`, если действие не говорит иное — доставка, «чёрный ход»). Ad-hoc (стена, окно, пролом) не запрещён и не нумеруется при generate. Шаблон здания сейчас даёт ≤1+1; N дверей той же роли — без смены контракта. Колонка роли в SQL сейчас нет — добавить при impl (`0001`). |
| **C15** | **O1 locked:** один pack-файл на поселение `locations/l.{settlement_uid}.settlement.zst` (граф районов/участков внутри). Не файл на участок. Шов тайлов — тот же uid (как WP-19). |
| **C16** | **O2 locked:** ядра достаточно. Отдельные **селекторы uid** (не второй generate): (1) все settlement-like мира; (2) потомки узла дерева локаций (`region` / `territory` — «континент/регион», не новый type); (3) по государству `state_uid` ([tz_states.md](./tz_states.md), опционально вниз по `parent_state_uid`). Каждый uid → тот же `materialize`. |

---

## 13. Вопросы — закрыты

Блокеров нет. **O1** → C15, **O2** → C16, **O3** → C20, **O4** → C14/C19. План: [`.cursor/plans/settlement-outdoor-pack.md`](../.cursor/plans/settlement-outdoor-pack.md).

### O2 — locked (C16)

Метод генерации **одного** поселения обязателен и достаточен как ядро.

Отдельно — тонкие проходы по уже существующим скелетам в SQL (не новый генератор, не placement на wilderness):

1. Все поселения мира (`named_location_uses_settlement_meter_footprint`).
2. По иерархии **локаций:** задан uid предка (`region` / `territory`) → CTE потомки → из них только settlement-like. «Континент» в продукте = узел дерева, не отдельный `location_type`.
3. По иерархии **государств:** задан `state_uid` → поселения с этим `state_uid`; при необходимости включить дочерние государства (`states.parent_state_uid`). Settlement может иметь иной `state_uid`, чем territory ([tz_states.md](./tz_states.md)).

Порядок uid в batch — стабильный (например `location_uid` ASC). Ошибка на одном городе: залог для плана (не глотать молча); по умолчанию continue + отчёт failed uids.

### O3 — locked (C20)

Вариант **1:** `location_levels` + наружные двери → `location_entry_points`. Interior `location_passages` не писать.

| Роль (system) | Смысл | Кардинальность |
|---|---|---|
| `front` | парадный | ≥1 на здание |
| `service` | чёрный ход | ≥0 |

Источник: шаблон `entry_point` → `front`, `back_entry_point` → `service` (building §3.6 `passage_type` `main_entrance` / `service_entrance`).

Default: NPC/игрок пользуются объявленными входами; среди них предпочтение `front`, пока действие не требует иного (`service`, ad-hoc). Ad-hoc (стена, окно, пролом) не запрещён, при generate не нумеруется. После успеха событие может **добавить** entry.

Persist без ≥1 `front` — ошибка, не писать здание. Колонка `entry_role` в SQL — при impl в `0001`.

### O4 — locked (C14 / C19)

SQL и файлы pack — не один COMMIT. Надёжность = протокол (как WP-12 chunk: `.tmp` → rename → manifest).

**Канон:** один `SettlementLayout` в RAM. Из него и SQL, и blob. Pack-retry после SQL **без** второго generate.

**Порядок:**

1. Encode `.tmp` (не в manifest). Долгое — вне SQL write-lock.
2. Одна SQL-транзакция: идемпотентный upsert дерева / графа / levels / entry_points → `COMMIT`.
3. `os.replace` → `l.{uid}.settlement.zst`, атомарно manifest, invalidate reader.

**Recovery:** crash до COMMIT → стереть tmp, полный materialize. После COMMIT, файла нет → дописать pack из tmp/layout, не skip. Процесс умер, tmp потерян → не skip; журнал pending или тот же seed. Skip (**C14**) iff файл + manifest + SQL-дети.

Скорость (parallel C16, batch) — после этого, не вместо.

Не вопросы этого слоя (уже C*): merge да/нет, area в `named_locations`, occupancy flood, parent=settlement, walls в `location_terrain`, один файл vs много (C15).

---

## 14. Проблемы (код vs цель)

Разрывы, которые план должен закрыть слоями §10 — не обходами в route.

### P13 — High: район не должен выравнивать здания

**Приоритет: высокий.** Нарушает **C21**. Не закрыто outdoor-impl (A–F). План: [`.cursor/plans/c21-plot-ground-z.md`](../.cursor/plans/c21-plot-ground-z.md).

Код сажает **все** участки и здания района на **одну** z: `resolve_ground_z` берёт `max(z)` terrain в AABB района; `_make_area_slot(..., slot.ground_z, ...)` копирует её в каждый `AreaSlot`. Pack-heightmap не режется (C1), но полы/фундамент/заборы — плато на пике района. На склоне дома парят или врезаются в холм; «идеально плоский район» — баг, не цель.

**Целевое:** порог и `ground_z` считает **`StructureAreaAssembler`** (дверь / ворота / край участка). Район не проставляет этаж. Подъезд — `yard_path` к порогу (§5.1.1). `DistrictSlot.ground_z` не онтология выравнивания.

Смежный симптом (тот же fix-pass): cache здания собирается при `ground_z=0`, `translate_layout` двигает xy; даже правильный `AreaSlot.ground_z` может не попасть в клетки этажей.

| ID | Где | Проблема |
|---|---|---|
| **P13** | `planner/terrain.resolve_ground_z` + `areaSlots._make_area_slot` | **High.** Одна z на район → все здания; C21. Fix: z на участке |
| **P1** | `api/routes/locations.py` `generate-settlement` | Оркестрация в HTTP: type `== "settlement"`, `get_all` мира, generate+persist |
| **P2** | `SettlementPersistService` | Эталон в `map_cell_patches` (`save_settlement_surface` / `save_generated`); occupancy+полный interior layout |
| **P3** | `plan_footprint_occupancy_cells` + assembler | Метровый flood на весь footprint (порядок 10^6 cells у town) |
| **P4** | `layoutCells.collect_geometry_meter_cells` | Flatten всего города, включая interior `StructureLayout.cells` |
| **P5** | `collect_building_locations` | `parent_location_uid=settlement`; районов в SQL нет |
| **P6** | `DistrictLayout` / `AreaLayout` | Нет district `NamedLocation`, нет area uid — extract не из чего взять без синтеза |
| **P7** | `StructureAreaAssembler._place_building` | Building NL без parent; uid/created_at/материалы — черновые литералы |
| **P8** | Facade | Нет `get_volume(footprint bbox)` для terrain assembler; route обходит через `get_all` |
| **P9** | `location_entry_points` | Таблица есть; нет dataclass/repo/persist; нет `entry_role` (`front`/`service`, C20) — колонка в `0001` при impl |
| **P10** | `MapLayerKind` | Нет слоя города; `FineTerrainZRun` без `system_building_element` — walls в location_terrain некуда и нельзя |
| **P11** | pack WP-3 / city §11.5 текст | Ещё описывают settlement → patches / map_cells; указатели на это ТЗ есть, инвариант WP-3 не переписан |
| **P12** | `lazy_settlement` | Литералы size как type; `get_by_world` клеток. Вне слоя (DAG gate), но сломает production path пока не вызовут C11 |

§10 (слои кода) остаётся порядком **после** замка §13, не заменой §12–§14.

---

## Changelog

| Дата | Изменение |
|---|---|
| 2026-08-30 | **C21:** участок ≠ здание; порог = assembler (`door`/`gate`/`parcel_edge`). План: `.cursor/plans/c21-plot-ground-z.md`. |
| 2026-08-30 | **O3 → C20:** variant 1; `front`≥1, `service`≥0; default объявленные двери; ad-hoc не запрещён. |
| 2026-08-30 | **O4 → C14/C19:** SQL+pack протокол; skip только согласованная пара. |
| 2026-08-30 | **C18:** сцена = радиус вокруг игрока; карта = здание + рядом; не телепорт. |
| 2026-08-30 | **C17:** входной этаж = `z_offset=0` / entry ≠ surface terrain. |
| 2026-08-30 | **O2 → C16:** ядро = один uid; селекторы all / дерево локаций / `state_uid`. |
| 2026-08-30 | **O1 → C15:** один pack-файл на поселение. |
| 2026-08-30 | v1: склейка outdoor на pack; граф участков; эталон vs дельта |

---

## Связанные документы

Полный список пунктов — §2. Кратко: [city](./tz_city_generation.md), [assembler](./tz_assembler_hierarchy.md), [pack](./tz_world_pack_storage.md), [locations](./tz_locations.md), [building](./tz_building_generator.md), [connections](./tz_structure_connections.md), [bundle](./tz_world_bundle.md), [relief](./tz_terrain_relief.md) (только границы), [DAG](./tz_world_generation_dag.md) (не impl).
