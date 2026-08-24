# TZ: Terrain relief — consume (хранение + debug ASCII)

**Статус:** SoT поддомена. Генерация (C39/C41, L2, persist R43) — [`tz_terrain_relief.md`](tz_terrain_relief.md). Этот файл — **что лежит после bake** и **как это читать**. LLM и карта — uid→Instance→System. **Dump ASCII — debug для разработчика**, не мастер мира, не игрок, не DAG. Не дублирует walk. **8 слотов клетки** (SLOPE / SHEER / COUPLE) — **pack**, не свойство ASCII и не derive из z.

**Родитель:** [`tz_terrain_relief.md`](tz_terrain_relief.md). ASCII-оси/файлы пака: [`tz_pack_ascii_render.md`](tz_pack_ascii_render.md) — глиф клетки grade **здесь**, не односимвольный overlay PAR-G. Sink R44: [`tz_logging.md`](tz_logging.md) консьюмер `relief` / `gradeCellRays`.

---

## Граница

| Слой | Этот TZ | Не этот TZ |
|---|---|---|
| Discover / paint / SQL persist instances | нет | relief generate + R43 |
| Bake leftover `occ` / `seam` / `facing_bits` | не хранить | generate |
| Pack: 8 слотов клетки (SLOPE / SHEER / COUPLE) | да | не derive в рендере / валидаторе |
| Постгенерационный валидатор 8 лучей | да (контракт) | generate не abort |
| Клетка → Instance → System | да | — |
| L2 ASCII dump: **3×3 клетка**, выравнивание с `surface_z` | да (debug разработчика) | не мастер, не игрок, не DAG |
| Карта / LLM payload | контракт uid | Wave E DAG — open |

---

## Четыре слоя данных (locked)

`occ` / `seam` / `facing_bits` / трассы **не** в pack/SQL. Claimed C41 **SLOPE/SHEER** и сцепление **COUPLE** — **в pack** как слоты `(клетка, Facing)`, не колонка FineTerrain и не SQL «8 бит». Не «остаточные» лучи: в sidecar всё, что generate записал по 8 сторонам клетки во вселенной R44.

### 1. Bake (эфемерно)

`occ` / `seam` / `facing_bits` / трассы. Нужны generate. В SQL и в `FineTerrainColumnWire` **нет**.

### 2. Pack — 8 слотов клетки (онтология, не leftover)

Sidecar `grade_rays.json` — **что generate записал на 8 сторонах клетки**, не «добить остаток». Не колонка FineTerrain, не SQL «8 бит», не Instance.

Слот pack = `(клетка, Facing)` last-wins. Kind слота:

| Kind | Когда | Instance |
|---|---|---|
| **SLOPE** / **SHEER** | все лучи фронтов, которые generate выставил: `rim ∪ corridor × outward` **и** получатель `opposite` | да (claim C41 = только отправитель SLOPE/SHEER) |
| **COUPLE** | сосед в unit, та же `surface_z` — сцепление единой поверхности | нет |
| нет слота | нет соседа **или** сосед другой z без SLOPE/SHEER | — |

SLOPE/SHEER **побеждает** COUPLE на том же `(клетка, Facing)`. Оба конца сцепления пишутся (как оба конца луча). Получатель вне мира — omit только этот конец.

**Пишет generate (persist чанка), не рендер и не валидатор.** Вселенная = клетки фронта + 8-halo (как R44), не 1e6 равнин. Не тело вершины × 8 как выдуманный SLOPE/SHEER. Не `OR` трёх очередей seed.

**Запрещено:** считать получателя или `+` в рендере из `opposite` / сравнения z; второй обход тайла «добить восьмёрку»; валидатор не дописывает слоты.

**Файлы pack** (не FineTerrain `.zst`, не SQL):

- wilderness tile: `tiles/r.{gx}.{gy}.grade_rays.json`
- location: `locations/l.{uid}.grade_rays.json`

Каждый слот кладётся в файл **своей** клетки (wilderness vs location — split по XY+z).

Зерно файла: слот `(x, y, facing, kind)`, kind ∈ {SLOPE, SHEER, COUPLE}. Uniqueness **claim** фронта (C41) — только отправитель SLOPE/SHEER.

### 3. Клетка (wire / pack / SQL map cell)

| Поле | Смысл |
|---|---|
| `system_grade_uid` | FK **Instance**. Пусто = клетка не в grade (C11). |
| `system_facing` | cache SLOPE; SHEER — omit (C10, R36h). |

Одна клетка — **не больше одного** Instance. Rim-тело луча **не** stamped (C11). Shared pit — `seam` generate, **не** 9-й grade и **не** uid на клетке.

**Запрещено:** `system_grade_uid` = System; второй uid; восстановление 8 лучей **только** из колонки (у колонки максимум один facing).

### 4. SQL сущности (R43)

| Таблица | Зерно |
|---|---|
| `relief_grade_instances` | один θ, один Facing, SLOPE **или** SHEER |
| `relief_grade_systems` | ≥2 Instance: T-3c (одно тело) **или** Q3-attach (бок + ближайший по \|Δz\| склон). LLM-имя формы. Нет отдельной таблицы Q3 |

Карта: Instance. System — только через `grade_system_uid` у Instance (не uid на клетке). Q3 не orphan: тот же System, что у склона соседнего коридора — [`tz_terrain_relief.md`](tz_terrain_relief.md) R41 persist.

---

## Постгенерационный валидатор (locked)

Аналог валидаторов генератора структуры здания ([`tz_building_generator.md`](tz_building_generator.md) § headroom / staircase: после построения — **log ERROR**, **не** бросать, результат **сохраняется**).

**Когда:** после того как pack-файл ребра записан (отправитель + получатель) для unit (`detailed_bake` / persist чанка). Не в рендере ASCII.

**Кого:** surface-клетки refined rect — тот же грид, что `surface_grade` / pack-файл этого unit.

### Проверка 1 (основная) — незакрытый слот Facing

У клетки **8** сторон = 8 `Facing` (как 3×3). Слот **закрыт**, если выполняется **любое**:

| | |
|---|---|
| Pack-слот | в sidecar есть `(клетка, Facing)` kind SLOPE, SHEER **или** COUPLE |
| Край | соседа нет в `z_at` (край тайла / мира) — omit, не ERROR |

Если сосед есть, **z другая**, и нет SLOPE/SHEER на этом Facing → слот **пуст**, клетка **некорректна**. Та же z без COUPLE в pack — тоже пустой слот (сцепление не дорисовывать из z).

| | |
|---|---|
| Уровень | **ERROR** |
| Generate | **не останавливать**: pack/SQL/fill как были; валидатор **не** чинит лучи, **не** invent uid и **не** дописывает слоты |
| Запись | **одна** ERROR на клетку: `x`, `y`, пустые Facing; **3×3 ячейки клетки** — `slots` (`.` = не закрыта, `#` = закрыта / центр) и `open` (компакт NW,N,NE,W,E,SW,S,SE). Вселенная = клетки pack-луча фронта + 8-halo (зона вершин/коридоров/обрывов), **не** все равнины тайла и не здания |
| Лог | только хелпер [`relief/log/log.py`](../backend/app/application/worldData/generators/terrain/relief/log/log.py) — `relief_error` (тот же модуль, что `relief_info` / `relief_warning` / `relief_debug`). Event: `EVENT_GRADE_CELL_EMPTY_RAY` = `"grade_cell_empty_ray"` в [`events.py`](../backend/app/application/worldData/generators/terrain/relief/log/events.py). Файл: [`tz_logging.md`](tz_logging.md) `logs/relief/gradeCellRays.log`. **Не** консоль (L8). Ритм на stdout — `packBakeLog` `grade_ray validate` (`empty=`), не замена этой ERROR |

**Запрещено:** `logging.getLogger` в обход хелпера; `print` / script-tee dump-скриптов (тики dump — `dumpLog`, не замена этой ERROR); `packBakeLog` heartbeat как замена этой ERROR; abort bake; repair/DAG; заполнять слоты в валидаторе; считать COUPLE из z в рендере.

Дальнейшие проверки — later (этот пункт = первая и основная).

---

## LLM / карта (locked)

Цепочка: клетка.`system_grade_uid` → Instance → System, если есть (`grade_system_uid`): T-3c **или** Q3-attach к ближайшему по высоте Grade ([`tz_terrain_relief.md`](tz_terrain_relief.md) R41 очереди).

C13: LLM читает **сущность**, не скан сетки. Две Instance в одну низину (разные Facing / независимые вершины) — **две** сущности; низина их не склеивает. **Исключение:** Instance бока Q3 и Instance склона, чей коридор этот бок, — один System; в бою/описании не зазор «второй холм».

Wave E (какие поля в payload) — **open**.

---

## Debug ASCII — клетка 3×3 (locked)

Аудитория: **разработчик**. Не мастер мира, не игрок, не DAG. Сцепление (COUPLE) пишет generate в pack; dump только читает.

Односимвольный overlay (`↑` / `┃` на stamped) **не** SoT. Он не показывает 8-way с rim (тело пустое) и общую низину (pit без uid).

### Слот клетки

Одна карта-клетка `(gx, gy)` = **всегда центр** + **до 8 символов по краям**.

Внутри клетки три глифа **подряд, без пробелов** (клетка = 3 колонки символов × 3 строки):

```
NW N NE
 W C  E
SW S SE
```

Пример заполнения (пик бьёт SOUTH SHEER; в примере `.` = пустой слот, в файле — пробел; `#` = поверхность):

```
...
.#.
.┃.
```

Плато той же `surface_z` (kind COUPLE в pack): слот = `+`.

| Слот | Когда заполнен |
|---|---|
| **C** | **всегда** (клетка существует в гриде дампа) |
| 8 краёв | pack-слот **на этой клетке** (SLOPE / SHEER / COUPLE). SLOPE/SHEER **побеждает** COUPLE |

Центр **не** occupancy и **не** uid. Центр = глиф поверхности той же колонки (`surface.txt` / terrain). Края = слоты pack. Коридор фронта — отправитель шага + получатель. Стык разной z: SOUTH на `(x, y)` и NORTH на `(x, y−1)` — оба SLOPE/SHEER. Стык той же z — COUPLE `+` с обеих сторон **в sidecar**.

| Луч / связь | Глиф в слоте этого Facing |
|---|---|
| нет слота (другая z без луча, или нет соседа) | пусто (пробел) |
| COUPLE | `+` |
| SLOPE | `FACING_ARROW` (`↑→↓←↗↘↖↙`) |
| SHEER | `┃` |

`+` на **`surface_grade.txt`** читается из pack (kind COUPLE), не из сравнения z. Срезы `grade_{n}` — только SLOPE/SHEER (без COUPLE, иначе стена = сплошной `+`).

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

Те же три клетки в `surface_grade.txt`, если средняя (`6`) — **отправитель** SOUTH SHEER (`┃`). Получатель — клетка южнее: слот NORTH, тот же kind. В примере `.` = пустой слот (в файле — пробел), `#` = поверхность:

```
     | ... ... ...
 904 | ... .#. ...
     | ... .┃. ...
     | ... .┃. ...
 903 | ... .#. ...
     | ... ... ...
```

Низина без слота на этой клетке — три строки; края пустые, если соседи другой z без луча или отсутствуют. Получатель SHEER **не** звезда 8 лучей: только facing удара. Сосед той же z — COUPLE в pack (`+`), не invent из z.

### Когда писать файл

PAR-G4 «omit если нет uid» **не** годится для 8-ray: rim без stamp. Писать `surface_grade.txt`, если в pack есть **хотя бы один слот** или хотя бы один `system_grade_uid`. Пусто только если нет обоих.

### Источник 8 слотов

Только sidecar `grade_rays.json` (SLOPE / SHEER / COUPLE). Dump и валидатор **читают** слоты, не считают `opposite` и не рисуют `+` из `surface_z`.

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
| `opposite` в рендере invent слот | получатель SLOPE/SHEER и оба конца COUPLE — persist pack, не ASCII |
| Считать `+` из сравнения `surface_z` | COUPLE пишет generate в sidecar; dump/валидатор только читают |
| Только «остаточные» SLOPE/SHEER в pack | sidecar = все лучи фронтов по 8 сторонам + COUPLE во вселенной R44 |
| Только отправитель SLOPE/SHEER в pack | стык двух gy разной z — разрыв (южная полоса vs северная) |
| Abort generate из валидатора 8 слотов | как структура: ERROR в лог, геометрия остаётся |
| Второй logger / `print` для этой ERROR | только `relief_error` |
| Второй обход тайла / тело × 8 как SLOPE/SHEER | не invent лучей; COUPLE — только same-z сосед во вселенной R44 |
| Один generate `is_seed` = C39∨посадка∨бок | три очереди, один станок фронтов — [`tz_terrain_relief.md`](tz_terrain_relief.md) R41 |

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
| 2026-08-23 | **Dump ASCII = debug разработчика:** не мастер мира, не игрок, не DAG. |
| 2026-08-23 | **Pack = 8 слотов клетки:** sidecar хранит все SLOPE/SHEER фронтов (не «остаток») и COUPLE same-z; dump/валидатор не invent `+` из z. |
| 2026-08-23 | **Q3 persist:** SQL тот же каталог; клетка → Instance; System после emit (T-3c + attach). Нет колонки parent_slot. |
| 2026-08-23 | **Q3-attach:** бок не orphan; LLM Instance→System вместе со склоном соседнего коридора. Низина по-прежнему не клеит чужие вершины. |
| 2026-08-23 | **Три очереди seed:** отправитель pack только фронт (не тело×8); generate Q1/Q2/Q3 не OR; R44 вселенная = луч+halo, не вся равнина. |
| 2026-08-23 | **Консоль:** R44 ERROR не stdout; heartbeat validate на `packBakeLog` — [`tz_logging.md`](tz_logging.md) L7/L8. |
| 2026-08-23 | **Сцепление единой поверхности (superseded same-day):** сначала equal-z не писали в pack; затем COUPLE стал kind sidecar — строка выше. |
| 2026-08-22 | **R44 вселенная + лог 3×3:** клетка = все ячейки домена terrain (не здания). ERROR: `slots` / `open`. Sink: [`tz_logging.md`](tz_logging.md) `relief/gradeCellRays`. |
| 2026-08-22 | **Валидатор 8 лучей + pack receiver:** persist пишет оба конца; `relief_error` / `grade_cell_empty_ray`; generate не abort. |
| 2026-08-22 | **Ребро pack:** отправитель (C41 `(клетка, Facing)`) + получатель (`+Δ(F)`, `opposite(F)`, тот же kind). Persist пишет оба конца; рендер только читает слоты. Не колонка, не SQL 8 бит. |
