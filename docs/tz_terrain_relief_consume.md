# TZ: Terrain relief — consume (хранение + debug ASCII)

**Статус:** SoT поддомена **после bake**. Генерация (очереди, стрелки, шаблоны/pick, canal/obstacle, SQL catalog) — [`tz_terrain_relief.md`](tz_terrain_relief.md). Bake R36u–w / envelope подробно — архив [`tz_terrain_relief_v1_superseded.md`](tz_terrain_relief_v1_superseded.md). Этот файл — **что лежит** и **как это читать**. LLM и карта — uid→Instance→System. **Dump ASCII — debug для разработчика**, не мастер мира, не игрок, не DAG. Не дублирует walk. **8 слотов клетки** — pack-коды [`tz_terrain_relief.md`](tz_terrain_relief.md) § Pack-слот, не свойство ASCII и не derive из z.

**Родитель generate:** [`tz_terrain_relief.md`](tz_terrain_relief.md). Техдолг кода: [`tz_terrain_relief_technical_debt.md`](tz_terrain_relief_technical_debt.md). ASCII-оси/файлы пака: [`tz_pack_ascii_render.md`](tz_pack_ascii_render.md) — глиф клетки grade **здесь**, не односимвольный overlay PAR-G. Sink ERROR слотов: [`tz_logging.md`](tz_logging.md) консьюмер `relief` / `gradeCellRays`. Persist occupancy — [`gradeCellSlotValidate.py`](../backend/app/application/worldData/generators/terrain/relief/validate/gradeCellSlotValidate.py), на bake **только** при `DEBUG_GRADE_SLOT_VALIDATE=1`. Обход `leftover_plus_halo` / R44 в [`gradeCellRays.py`](../backend/app/application/worldData/generators/terrain/relief/validate/gradeCellRays.py) — **interim**, не конечный валидатор.

---

## Граница

| Слой | Этот TZ | Не этот TZ |
|---|---|---|
| Discover / paint / SQL persist instances | нет | generate [`tz_terrain_relief.md`](tz_terrain_relief.md) § SQL catalog |
| Bake leftover `occ` / `seam` / `facing_bits` | не хранить | generate |
| Pack: 8 слотов клетки (коды Octant/Seam/Sheer/Couple) | да | не derive в рендере / валидаторе; не глиф в файле |
| Постгенерационный валидатор 8 лучей | да (контракт) | generate не abort |
| Клетка → Instance → System | да | — |
| L2 ASCII dump: **3×3 клетка**, выравнивание с `surface_z` | да (debug разработчика) | не мастер, не игрок, не DAG |
| Карта / LLM payload | контракт uid | Wave E DAG — open |

---

## Четыре слоя данных (locked)

`occ` / `seam` / `facing_bits` / трассы **не** в pack/SQL. Слоты pack — [`tz_terrain_relief.md`](tz_terrain_relief.md) § Pack-слот: 8 int на клетку. Не колонка FineTerrain и не SQL «8 бит». Не mill `Facing` в sidecar.

### 1. Bake (эфемерно)

`occ` / `seam` / `facing_bits` / трассы. Нужны generate. В SQL и в `FineTerrainColumnWire` **нет**.

### 2. Pack — 8 слотов клетки (онтология, не leftover)

Sidecar — **что generate записал на 8 сторонах клетки**, не «добить остаток». Не колонка FineTerrain, не SQL «8 бит», не Instance, не Unicode.

Слот = `(клетка, позиция края 0…7)` + **один код** (четыре IntEnum, общая нумерация только wire). На клетке обхода **всегда 8 кодов**. First-wins по `(клетка, позиция)`.

| Код | Когда | Instance |
|---|---|---|
| **`GradeOctant` 0…7** | луч SLOPE; значение = **поток** (оба конца тот же член, напр. `EAST`) | да (claim C41 = отправитель mill `Facing`) |
| **`GradeSheer.SHEER` = 9** | луч SHEER оба конца | да |
| **`GradeCouple.COUPLE` = 10** | сосед в unit, та же `surface_z` | нет |
| **`GradeSeam.SEAM` = 8** | нет соседа в `z_height_map` — **писать явно** | нет |
| нет кода | **ERROR** — не шов, не «закрыто из z» | — |

Octant/SHEER **побеждает** COUPLE на той же позиции. Оба конца сцепления и луча пишутся. Шов — один конец (соседа нет).

**Пишет generate (persist чанка), не рендер и не валидатор.** Правила пары — generate § Правила стрелок. Обход кода `leftover_plus_halo` / R44 — **interim**. Не тело вершины × 8. Не `OR` Q1 leftover и Q2 в одном drain.

Dump читает код → глиф. Сравнивать `surface_z` в рендере **запрещено**. Нет кода на краю = ERROR generate, не баг дампа.

Generate пишет 8 кодов по правилам пары. **Полный occupancy — R41-T-25**. Dump/валидатор только читают pack. Mill: downhill = Instance leftover, same-z не leftover. Seed: Q1/Q2, mill Q3 нет.

**Запрещено:** invent код из `opposite` / z; глифы в sidecar; один enum на 0…10; валидатор дописывает слоты; закрывать край «нет соседа» без `SEAM`.

**Файлы pack** (не FineTerrain `.zst`, не SQL):

- wilderness tile: `tiles/r.{gx}.{gy}.grade_rays.json`
- location: `locations/l.{uid}.grade_rays.json`

Каждая **клетка** — в файл своей клетки (wilderness vs location — split по XY+z). Имя `grade_rays` историческое; тело — § Тело sidecar.

### Тело sidecar (locked)

Не массив лучей `{x, y, facing, kind}`. Не Unicode. Не mill `Facing`. Не колонка `terrain.zst`.

Корень файла:

```json
{
  "schema_id": "SCH-GRADE-CELL-SLOTS",
  "cells": [
    { "x": 0, "y": 1, "slots": [8, 10, 10, 8, 4, 8, 10, 10] }
  ]
}
```

| Поле | Контракт |
|---|---|
| `schema_id` | `"SCH-GRADE-CELL-SLOTS"` |
| `cells` | список клеток обхода этого файла |
| `x`, `y` | world XY; **уникальны** в файле |
| `slots` | ровно **8** int, порядок NW N NE W E SW S SE (§ Pack-слот) |
| код | ∈ {0…10}; иначе **reject** файла |

Пример `slots` — яма `(0,1)=4` (generate § Pack-слот). Dump этот массив не хранит глифами.

JSON **compact** (без pretty `indent=2`). Растр тайла / zstd-обёртка sidecar — **не** этот контракт (не смешивать с FineTerrain).

Нет записи клетки, которая должна быть в обходе — ERROR generate (валидатор), не «шов из omit». `slots.length ≠ 8` — reject.

Merge bake: first-wins на `(x, y, позиция 0…7)`; generate обычно пишет клетку целиком.

Loader dump/валидатора: клетка → 8 кодов. Старый `{"rays":[…]}` (`SCH-GRADE-RAY-SIDECAR`) — **не** SoT.

Зерно чтения: `(x, y, позиция) → код`. Claim C41 — отправитель mill, не запись sidecar.

### 3. Клетка (wire / pack / SQL map cell)

| Поле | Смысл |
|---|---|
| `system_grade_uid` | FK **Instance**. Пусто = клетка не в grade (C11). |
| `system_facing` | cache SLOPE; SHEER — omit (C10, R36h). |

Одна клетка — **не больше одного** Instance. Rim-тело луча **не** stamped (C11). Shared pit — `seam` generate, **не** 9-й grade и **не** uid на клетке.

**Запрещено:** `system_grade_uid` = System; второй uid; восстановление 8 лучей **только** из колонки (у колонки максимум один facing).

### 4. SQL сущности

Каталог и persist — [`tz_terrain_relief.md`](tz_terrain_relief.md) § SQL catalog. Здесь — как **читать**.

| Таблица | Зерно |
|---|---|
| `relief_grade_instances` | один θ, один Facing, SLOPE **или** SHEER |
| `relief_grade_systems` | ≥2 Instance: T-3c (одно тело) **или** бок-attach Q2 (бок + ближайший по \|Δz\| склон). LLM-имя формы. Нет таблицы «очередь Q3» |

Карта: Instance. System — только через `grade_system_uid` у Instance (не uid на клетке). Бок Q2 не orphan: тот же System, что у склона соседнего коридора — [`tz_terrain_relief.md`](tz_terrain_relief.md) § очереди.

---

## Постгенерационный валидатор (код — interim)

Контракт «ERROR в лог, не abort» остаётся. **Кого обходить** — открыто: код `leftover_plus_halo` / R44 **не** конечный SoT. Правила слота (закрыт = pack или нет соседа) — как ниже, пока не сменим валидатор. Generate SoT слотов — [`tz_terrain_relief.md`](tz_terrain_relief.md).

Аналог валидаторов генератора структуры здания ([`tz_building_generator.md`](tz_building_generator.md) § headroom / staircase: после построения — **log ERROR**, **не** бросать, результат **сохраняется**).

**Когда:** после того как pack-файл ребра записан (отправитель + получатель) для unit (`detailed_bake` / persist чанка). Не в рендере ASCII. Occupancy-обход на persist — **только** при `DEBUG_GRADE_SLOT_VALIDATE=1` (dev); product bake пишет sidecar без этого прохода.

**Кого:** surface-клетки refined rect — тот же грид, что `surface_grade` / pack-файл этого unit.

### Проверка 1 (основная) — незакрытый слот Facing

У клетки **8** сторон (позиции dump). На каждом крае — **код** generate § Pack-слот. Пустота (нет кода / нет глифа) — **ERROR**.

Слот **закрыт**, только если в sidecar есть код на `(клетка, позиция)`. `SEAM` — валидное закрытие (шов записан). Нет кода — ERROR, даже если соседа нет в `z_height_map` (generate не написал шов).

Дальше (не invent): Octant/SHEER при разной z оба конца; `COUPLE` при той же z оба конца; `SEAM` только если ключа соседа нет. Несовпадение кода и пары — ERROR. Сцепление/шов не дорисовывать из z.

| | |
|---|---|
| Уровень | **ERROR** |
| Generate | **не останавливать**: pack/SQL/fill как были; валидатор **не** чинит лучи, **не** invent uid и **не** дописывает слоты |
| Запись | **одна** ERROR на клетку: `x`, `y`, пустые Facing; **3×3 ячейки клетки** — `slots` (`.` = не закрыта, `#` = закрыта / центр) и `open` (компакт NW,N,NE,W,E,SW,S,SE). Код обходит leftover SLOPE/SHEER + 8-halo (`leftover_plus_halo`) — **interim**, не SoT нового валидатора |
| Лог | только хелпер [`relief/log/log.py`](../backend/app/application/worldData/generators/terrain/relief/log/log.py) — `relief_error` (тот же модуль, что `relief_info` / `relief_warning` / `relief_debug`). Event: `EVENT_GRADE_CELL_EMPTY_RAY` = `"grade_cell_empty_ray"` в [`events.py`](../backend/app/application/worldData/generators/terrain/relief/log/events.py). Файл: [`tz_logging.md`](tz_logging.md) `logs/relief/gradeCellRays.log`. **Не** консоль (L8). Ритм на stdout — `packBakeLog` `grade_ray validate` (`empty=`), не замена этой ERROR |

**Запрещено:** `logging.getLogger` в обход хелпера; `print` / script-tee dump-скриптов (тики dump — `dumpLog`, не замена этой ERROR); `packBakeLog` heartbeat как замена этой ERROR; abort bake; repair/DAG; заполнять слоты в валидаторе; считать COUPLE из z в рендере.

Дальнейшие проверки — later (этот пункт = первая и основная).

---

## LLM / карта (locked)

Цепочка: клетка.`system_grade_uid` → Instance → System, если есть (`grade_system_uid`): T-3c **или** бок-attach Q2 к ближайшему по высоте Grade ([`tz_terrain_relief.md`](tz_terrain_relief.md) R41 очереди).

C13: LLM читает **сущность**, не скан сетки. Две Instance в одну низину (разные Facing / независимые вершины) — **две** сущности; низина их не склеивает. **Исключение:** Instance бока Q2 и Instance склона, чей коридор этот бок, — один System; в бою/описании не зазор «второй холм».

Wave E (какие поля в payload) — **open**.

---

## Debug ASCII — клетка 3×3 (locked)

Аудитория: **разработчик**. Не мастер мира, не игрок, не DAG.

**Ответственность слоёв (locked) — `+` на теле той же z:**

| Слой | Делает | Не делает |
|---|---|---|
| Generate / persist | пишет 8 кодов; `COUPLE` оба конца same-z | глиф ASCII |
| Dump `surface_grade.txt` | глиф по коду (`COUPLE` → `+`) | invent из `surface_z`; чинить generate |
| Валидатор | ERROR, если на позиции нет кода (в т.ч. нет `COUPLE` при same-z) | закрывать из z; дописывать слоты |

Сцепление пишет generate в pack; dump только читает код. Нет `COUPLE` на краю при соседе той же z — ERROR generate.

Односимвольный overlay (`↑` / `┃` на stamped) **не** SoT. Он не показывает 8-way с rim (тело пустое) и общую низину (pit без uid).

### Слот клетки

Одна карта-клетка `(gx, gy)` = **всегда центр** + **8 глифов по краям** (из кодов).

Внутри клетки три глифа **подряд, без пробелов** (клетка = 3 колонки символов × 3 строки):

```
NW N NE
 W C  E
SW S SE
```

Пример заполнения (пик бьёт SOUTH `SHEER` → `┃`; `#` = поверхность):

```
...
.#.
.┃.
```

Плато той же `surface_z`: `+` только если код `COUPLE`. Dump не считает высоты.

| Слот | Когда заполнен |
|---|---|
| **C** | **всегда** (клетка существует в гриде дампа) |
| 8 краёв | код на этой клетке. Octant/SHEER **побеждает** COUPLE |

Центр **не** occupancy и **не** uid. Центр = глиф поверхности (`surface.txt` / terrain). Края = dump кодов. Стык разной z: оба конца тот же `GradeOctant` (поток) или оба `SHEER`. Стык той же z — `COUPLE` с обеих сторон.

| Код | Глиф |
|---|---|
| `GradeOctant.NORTHWEST` … `SOUTHEAST` | `↖ ↑ ↗ ← → ↙ ↓ ↘` |
| `GradeSheer.SHEER` | `┃` |
| `GradeSeam.SEAM` | `.` |
| `GradeCouple.COUPLE` | `+` |
| нет кода | **ERROR генерации** |

Срезы `grade_{n}` — только Octant/SHEER (без COUPLE, иначе стена = сплошной `+`).

**Запрещено:** заполнять 8 краёв из `system_facing` колонки; `opposite` / сравнение z **чтобы invent слот**; один overlay-символ как SoT; выдавать получателя за второй C41-claim. Рендер **только** читает sidecar.

### Выравнивание с `surface_z` (locked)

`surface_z`: `height_cell_width` → поле ширины **W**, `format_height_cell` (right-align), `join_height_row` (клетки через один пробел), gy `yyyy |` (`y:4d`).

Дампа лучей и высоты — **одна и та же сетка клеток**:

**Ось X.** Каждая карта-клетка занимает **то же поле W + один пробел-разделитель**, что и соответствующая клетка `surface_z`. Строка 3×3 — ровно 3 глифа; они кладутся **внутрь** поля W с **тем же right-align**, что z (`format_height_cell`). Если W < 3 — для **парного** снимка (`surface_z` + лучи) W := max(W_высот, 3).

**Ось Y.** Каждая карта-`gy` занимает **ровно 3 подряд идущие строки дампа** (север сверху: `NWNNE`, затем `WCE`, затем `SWSSE`). Метка `gy` в формате `yyyy |` — **только на средней** строке (ряд центра). Верхняя и нижняя подстроки: те же 4 символа поля номера, пробелы, тот же `|` — колонка `|` совпадает с `surface_z`.

Итог: колонки клеток совпадают с `surface_z` по X; по Y клетка — квадрат 3 строк, не одна. `surface_z` остаётся **1 строка / gy** (числа). Сверять по `gx`/`gy` и по началу поля W, не наложением файл-в-файл по номеру строки.

Пример одной строки мира `4 6 3` (W=3). `surface_z`:

```
 904 |  4   6   3
```

Те же три клетки в `surface_grade.txt`, если средняя (`6`) — **отправитель** SOUTH SHEER (`┃` = `GradeSheer.SHEER`). Получатель южнее: слот NORTH, тот же код `SHEER`. `#` = поверхность. Края без удара — коды пары (`SEAM` / `COUPLE` / Octant), не пробел:

```
     | ... ... ...
 904 | ... .#. ...
     | ... .┃. ...
     | ... .┃. ...
 903 | ... .#. ...
     | ... ... ...
```

Низина без Instance на клетке — края всё равно 8 кодов (яма-эталон). Получатель SHEER **не** звезда 8 лучей: только слот удара несёт `SHEER`. Сосед той же z — `COUPLE`, не invent из z.

### Когда писать файл

PAR-G4 «omit если нет uid» **не** годится для 8-ray: rim без stamp. Писать `surface_grade.txt`, если в pack есть **хотя бы один слот** или хотя бы один `system_grade_uid`. Пусто только если нет обоих.

### Источник 8 слотов

Только sidecar § Тело sidecar (`slots[8]`). Dump и валидатор **читают** коды, не `rays[]`, не `opposite`, не глиф из z.

**Не** новая колонка SQL «8 бит на клетку». **Не** FineTerrain `.zst`.

Файл L2: `surface_grade.txt` (тот же путь, что PAR-G) — **этот** 3×3 формат, не 1-char overlay.

L0: grade omit (PAR-G5) — без изменений.

---

## Анти-паттерны

| | |
|---|---|
| System uid на клетке | карта/LLM теряют θ/Facing |
| Выдумать uid в рендере | C11 |
| 1-char overlay как SoT 8-way | rim и pit невидимы |
| 8 краёв из одного `system_facing` | у колонки один луч, не звезда с вершины |
| Occupancy на краях pit | путает C41-claim и дно |
| `opposite` в рендере invent слот | оба конца луча — persist, тот же `GradeOctant`/`SHEER` |
| Считать `+` / `.` из z | `COUPLE` / `SEAM` пишет generate; dump только глиф |
| Только leftover mill в pack | 8 кодов по правилам пары, в т.ч. яма без Instance |
| Массив `rays[]` / `{facing, kind}` | SoT = `{x,y,slots[8]}` (`SCH-GRADE-CELL-SLOTS`) |
| Один enum 0…10 | LLM путает сторону и шов; имена членов = смысл |
| Только отправитель SLOPE/SHEER в pack | стык двух gy разной z — разрыв (южная полоса vs северная) |
| Abort generate из валидатора 8 слотов | как структура: ERROR в лог, геометрия остаётся |
| Второй logger / `print` для этой ERROR | только `relief_error` |
| Второй обход тайла / тело × 8 как Octant/SHEER | не invent лучей; `COUPLE` — same-z оба конца |
| Один generate `is_seed` = C39∨посадка∨бок | две очереди (Q1 leftover / Q2), один станок — [`tz_terrain_relief.md`](tz_terrain_relief.md) R41; **R41-T-18** |

---

## Open

| | |
|---|---|
| Wave E | какие поля Instance/System в LLM |
| Карта UI | тот же uid, не ASCII |

---

## Ссылки

- Generate / C41 / C11: [`tz_terrain_relief.md`](tz_terrain_relief.md)
- Файлы пака, L0/L2, `surface.txt`: [`tz_pack_ascii_render.md`](tz_pack_ascii_render.md)
- Wire колонки: [`tz_fine_terrain.md`](tz_fine_terrain.md) `FineTerrainColumnWire`
- Шаблон grade: [`tz_relief_templates.md`](tz_relief_templates.md)
- Pack files: [`tz_world_pack_storage.md`](tz_world_pack_storage.md) § Grade 8-slots
- Sinks / консьюмер `relief/gradeCellRays`: [`tz_logging.md`](tz_logging.md)

---

## История

| Дата | Изменение |
|---|---|
| 2026-08-25 | **Q3 не очередь seed:** mill SoT = Q1/Q2 — **R41-T-18**. Снос кода `is_q3_seed` — **R41-T-19**. Бок-attach persist остаётся. |
| 2026-08-25 | **`+` same-z — не dump:** COUPLE пишет generate в sidecar; ASCII только глиф по kind. Пустой край плато = нет слота в JSON. T-17 = persist + валидатор не закрывает из z; dump `+` = smoke. |
| 2026-08-27 | Persist occupancy-validator на bake только `DEBUG_GRADE_SLOT_VALIDATE=1`. |
| 2026-08-26 | **Generate SoT** сжат в [`tz_terrain_relief.md`](tz_terrain_relief.md); bake R36/R43 — архив v1. `leftover_plus_halo` / R44 — interim кода, не конечный валидатор. |
| 2026-08-26 | **R41-T-25 open:** алгоритм полного fill 8 слотов; не игнор восьмёрки. T-17 = COUPLE + валидатор не из z, не occupancy. |
| 2026-08-23 | **Dump ASCII = debug разработчика:** не мастер мира, не игрок, не DAG. |
| 2026-08-23 | **Pack = 8 слотов клетки:** sidecar хранит все SLOPE/SHEER фронтов (не «остаток») и COUPLE same-z; dump/валидатор не invent `+` из z. |
| 2026-08-23 | **Q3 persist:** SQL тот же каталог; клетка → Instance; System после emit (T-3c + attach). Нет колонки parent_slot. |
| 2026-08-23 | **Q3-attach:** бок не orphan; LLM Instance→System вместе со склоном соседнего коридора. Низина по-прежнему не клеит чужие вершины. |
| 2026-08-23 | **Три очереди seed:** отправитель pack только фронт (не тело×8); generate Q1/Q2/Q3 не OR; R44 leftover + 8-halo, не вся равнина. |
| 2026-08-23 | **Консоль:** R44 ERROR не stdout; heartbeat validate на `packBakeLog` — [`tz_logging.md`](tz_logging.md) L7/L8. |
| 2026-08-23 | **Сцепление единой поверхности (superseded same-day):** сначала equal-z не писали в pack; затем COUPLE стал kind sidecar — строка выше. |
| 2026-08-22 | **R44 leftover + 8-halo + лог 3×3:** клетка = все ячейки домена terrain (не здания). ERROR: `slots` / `open`. Sink: [`tz_logging.md`](tz_logging.md) `relief/gradeCellRays`. |
| 2026-08-22 | **Валидатор 8 лучей + pack receiver:** persist пишет оба конца; `relief_error` / `grade_cell_empty_ray`; generate не abort. |
| 2026-08-22 | **Ребро pack:** отправитель (C41 `(клетка, Facing)`) + получатель (`+Δ(F)`, `opposite(F)`, тот же kind). Persist пишет оба конца; рендер только читает слоты. Не колонка, не SQL 8 бит. |
