# TZ: Terrain relief — consume (хранение + debug ASCII)

**Статус:** SoT поддомена. Генерация (C39/C41, L2, persist R43) — [`tz_terrain_relief.md`](tz_terrain_relief.md). Этот файл — **что лежит после bake** и **как это читать** (LLM, карта, дамп). Не дублирует walk. Ребро луча (отправитель + получатель) — **pack**, не свойство ASCII.

**Родитель:** [`tz_terrain_relief.md`](tz_terrain_relief.md). ASCII-оси/файлы пака: [`tz_pack_ascii_render.md`](tz_pack_ascii_render.md) — глиф клетки grade **здесь**, не односимвольный overlay PAR-G. Sink R44: [`tz_logging.md`](tz_logging.md) консьюмер `relief` / `gradeCellRays`.

---

## Граница

| Слой | Этот TZ | Не этот TZ |
|---|---|---|
| Discover / paint / SQL persist instances | нет | relief generate + R43 |
| Bake leftover `occ` / `seam` / `facing_bits` | не хранить | generate |
| Pack: ребро луча **отправитель + получатель** | да | не derive в рендере |
| Постгенерационный валидатор 8 лучей | да (контракт) | generate не abort |
| Клетка → Instance → System | да | — |
| L2 ASCII: **3×3 клетка**, выравнивание с `surface_z` | да | — |
| Карта / LLM payload | контракт uid | Wave E DAG — open |

---

## Четыре слоя данных (locked)

`occ` / `seam` / `facing_bits` / трассы **не** в pack/SQL. Claimed C41 leftover **в pack** — как ребро (отправитель + получатель), не колонка FineTerrain и не SQL «8 бит».

### 1. Bake (эфемерно)

`occ` / `seam` / `facing_bits` / трассы. Нужны generate. В SQL и в `FineTerrainColumnWire` **нет**.

### 2. Pack — ребро луча (отправитель + получатель)

Один claimed leftover C41 = **одно ребро Grade** (Instance). Слоты pack **шире**: то же построение (список вершин + спуск), без второго обхода тайла.

**Отправитель pack** (не рендер):

| Откуда | Клетка | Facing | kind |
|---|---|---|---|
| 8-взгляд тела (`_rim_shots` / `body × 8`) | клетка `body` вершины | каждый из 8, где сосед в bake **ниже** (`zn < z_src`). Равная z — **не** pack-луч (сцепление). **Не** вверх | покрашенный фронт этой стороны, иначе default ``GradeRimRay.kind`` (глиф, не Instance) |
| шаг фронта (`_walk_trace`) | `rim ∪ corridor` | `outward` только. Равная z вдоль ширины `W` — **не** pack-луч (сцепление) | kind покрашенного фронта |
| **Получатель** | `(x, y) + GRID_OUTWARD_DELTA[F]` | `opposite(F)` | **тот же** kind |

C41-uniqueness **claim** (Instance / leftover) — по-прежнему отправитель leftover `(клетка, Facing)`. Слот pack: last-wins `(x, y, Facing)`.

**Сцепление единой поверхности** (не pack-луч, не Instance): сосед есть в unit **и** `surface_z` совпадает. Клетки уже вместе — ребра leftover между ними нет. Не писать `+` в `grade_rays.json`. Считать в валидаторе и в дампе `surface_grade` из `surface_z`.

**Запрещено:** вычислять получателя leftover в рендере (`opposite`, «дорисовать входящие»). Рендер читает слоты pack и глиф leftover; шаг к соседу — **только** сравнить `surface_z` для сцепления. Второй проход по всей сетке «добить восьмёрку leftover» — нет: только тело вершин (downhill) и трасса луча (`outward`).

**Файлы pack** (не FineTerrain `.zst`, не SQL):

- wilderness tile: `tiles/r.{gx}.{gy}.grade_rays.json`
- location: `locations/l.{uid}.grade_rays.json`

Каждый конец кладётся в файл **своей** клетки (wilderness vs location — как сейчас split по XY+z). Получатель вне мира / без клетки — omit только этот конец; отправитель остаётся.

Зерно файла: ребро (sender + receiver + kind), не «debug leftover». Слот клетки для ASCII/карты = `(cell, Facing)` **любого** конца. Uniqueness слота pack: last-wins на `(x, y, Facing)` (как merge C41). Uniqueness **claim** generate по-прежнему только отправитель (C41).

**Не** колонка `FineTerrainColumnWire` и **не** новая SQL-карта «8 бит на клетку».

### 3. Клетка (wire / pack / SQL map cell)

| Поле | Смысл |
|---|---|
| `system_grade_uid` | FK **Instance**. Пусто = клетка не в grade (C11). |
| `system_facing` | cache SLOPE; SHEER — omit (C10, R36h). |

Одна клетка — **не больше одного** Instance. Rim-тело луча **не** stamped (C11). Shared pit — seam в leftover, **не** 9-й grade и **не** uid на клетке.

**Запрещено:** `system_grade_uid` = System; второй uid; восстановление 8 лучей **только** из колонки (у колонки максимум один facing).

### 4. SQL сущности (R43)

| Таблица | Зерно |
|---|---|
| `relief_grade_instances` | один θ, один Facing, SLOPE **или** SHEER |
| `relief_grade_systems` | ≥2 Instance **одного** vertex (T-3c); LLM-имя формы |

Карта: Instance. System — только через `system_id` у Instance.

---

## Постгенерационный валидатор (locked)

Аналог валидаторов генератора структуры здания ([`tz_building_generator.md`](tz_building_generator.md) § headroom / staircase: после построения — **log ERROR**, **не** бросать, результат **сохраняется**).

**Когда:** после того как pack-файл ребра записан (отправитель + получатель) для unit (`detailed_bake` / persist чанка). Не в рендере ASCII.

**Кого:** surface-клетки refined rect — тот же грид, что `surface_grade` / pack-файл этого unit.

### Проверка 1 (основная) — незакрытый слот Facing

У клетки **8** сторон = 8 `Facing` (как 3×3). Слот **закрыт**, если выполняется **любое**:

| | |
|---|---|
| Pack-луч | в sidecar есть конец ребра (отправитель **или** получатель) на `(клетка, Facing)` — leftover SLOPE/SHEER |
| Сцепление | сосед есть в `z_at` unit **и** `surface_z` тот же — единая поверхность, луч не нужен |
| Край | соседа нет в `z_at` (край тайла / мира) — omit, не ERROR |

Если сосед есть, **z другая**, и pack-луча на этом Facing нет → слот **пуст**, клетка **некорректна**.

| | |
|---|---|
| Уровень | **ERROR** |
| Generate | **не останавливать**: pack/SQL/fill как были; валидатор **не** чинит лучи, **не** invent uid и **не** пишет сцепление в pack |
| Запись | **одна** ERROR на клетку: `x`, `y`, пустые Facing; **3×3 ячейки клетки** — `slots` (`.` = не закрыта, `#` = закрыта / центр) и `open` (компакт NW,N,NE,W,E,SW,S,SE). Вселенная = все ячейки домена terrain, не здания |
| Лог | только хелпер [`relief/log/log.py`](../backend/app/application/worldData/generators/terrain/relief/log/log.py) — `relief_error` (тот же модуль, что `relief_info` / `relief_warning` / `relief_debug`). Event: `EVENT_GRADE_CELL_EMPTY_RAY` = `"grade_cell_empty_ray"` в [`events.py`](../backend/app/application/worldData/generators/terrain/relief/log/events.py). Файл: [`tz_logging.md`](tz_logging.md) `logs/relief/gradeCellRays.log`. **Не** консоль (L8). Ритм на stdout — `packBakeLog` `grade_ray validate` (`empty=`), не замена этой ERROR |

**Запрещено:** `logging.getLogger` в обход хелпера; `print` / script-tee dump-скриптов (тики dump — `dumpLog`, не замена этой ERROR); `packBakeLog` heartbeat как замена этой ERROR; abort bake; repair/DAG; заполнять leftover-слоты в валидаторе; persist сцепления как `GradeRimRay`.

Дальнейшие проверки — later (этот пункт = первая и основная).

---

## LLM / карта (locked)

Цепочка: клетка.`system_grade_uid` → Instance → (если T-3c) System.

C13: LLM читает **сущность**, не скан сетки. Две Instance в одну низину (разные Facing / вершины) — **две** сущности; низина их не склеивает.

Wave E (какие поля в payload) — **open**.

---

## Debug ASCII — клетка 3×3 (locked)

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

Плато той же `surface_z` (сцепление, не leftover): слот = `+`.

| Слот | Когда заполнен |
|---|---|
| **C** | **всегда** (клетка существует в гриде дампа) |
| 8 краёв | leftover pack **на этой клетке** (отправитель **или** получатель) **или** сцепление (сосед в дампе, та же `surface_z`). Pack-луч **побеждает** `+` |

Центр **не** occupancy и **не** uid. Центр = глиф поверхности той же колонки (`surface.txt` / terrain), как якорь «здесь клетка». Края leftover = слоты pack. Клетка коридора на трассе луча — отправитель шага. Стык двух клеток разной z: отправитель SOUTH на `(x, y)` **и** получатель NORTH на `(x, y−1)` — оба в pack. Стык той же z — `+` с обеих сторон, без sidecar.

| Луч / связь | Глиф в слоте этого Facing |
|---|---|
| нет (другая z без leftover, или нет соседа) | пусто (пробел в слоте) |
| сцепление единой поверхности | `+` |
| SLOPE leftover | `FACING_ARROW` (`↑→↓←↗↘↖↙`) |
| SHEER leftover | `┃` (слот всё равно выбирает Facing луча) |

`+` только в **`surface_grade.txt`** (сравнение top `surface_z`). Срезы `grade_{n}` — только pack leftover, без сцепления (иначе стена = сплошной `+`).

**Запрещено:** заполнять 8 краёв из `system_facing` колонки; `opposite` / шаг к соседу **чтобы invent leftover**; persist `+` как `GradeRimRay`; один overlay-символ как SoT; выдавать получателя за второй C41-claim. Шаг к соседу в рендере — **только** сравнить `surface_z` для `+`.

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

Низина без конца ребра на этой клетке — три строки; края пустые, если соседи другой z или отсутствуют. Получатель leftover **не** звезда 8 лучей: только facing удара. Сосед той же z — `+`, не leftover.

### Когда писать файл

PAR-G4 «omit если нет uid» **не** годится для 8-ray: rim без stamp. Писать `surface_grade.txt`, если в pack есть **хотя бы один конец ребра** или хотя бы один `system_grade_uid`. Пусто только если нет обоих.

### Источник 8 лучей

Pack-файл ребра leftover (слой 2) плюс сцепление из `surface_z` на `surface_grade`. Dump leftover читает **уже записанные** концы (отправитель и получатель). Сцепление **не** sidecar.

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
| `opposite` в рендере для leftover | получатель leftover — persist pack, не ASCII |
| Шаг к соседу invent leftover | шаг разрешён **только** сравнить `surface_z` → `+` |
| Persist сцепления в `grade_rays.json` | `+` считают валидатор и `surface_grade` из z |
| Только отправитель leftover в pack | стык двух gy разной z — разрыв (южная полоса vs северная) |
| Abort generate из валидатора 8 слотов | как структура: ERROR в лог, геометрия остаётся |
| Второй logger / `print` для этой ERROR | только `relief_error` |
| Второй обход тайла ради слотов pack | тело вершины × 8 (downhill) и lockstep уже есть; равная z не pack |

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
- Pack files: [`tz_world_pack_storage.md`](tz_world_pack_storage.md) § Grade rim edges
- Sinks / консьюмер `relief/gradeCellRays`: [`tz_logging.md`](tz_logging.md)

---

## История

| Дата | Изменение |
|---|---|
| 2026-08-23 | **Консоль:** R44 ERROR не stdout; heartbeat validate на `packBakeLog` — [`tz_logging.md`](tz_logging.md) L7/L8. |
| 2026-08-23 | **Сцепление единой поверхности:** равная z не pack-луч; валидатор закрывает слот; dump `surface_grade` глиф `+`; leftover только downhill / outward. |
| 2026-08-22 | **R44 вселенная + лог 3×3:** клетка = все ячейки домена terrain (не здания). ERROR: `slots` / `open`. Sink: [`tz_logging.md`](tz_logging.md) `relief/gradeCellRays`. |
| 2026-08-22 | **Валидатор 8 лучей + pack receiver:** persist пишет оба конца; `relief_error` / `grade_cell_empty_ray`; generate не abort. |
| 2026-08-22 | **Ребро pack:** отправитель (C41 `(клетка, Facing)`) + получатель (`+Δ(F)`, `opposite(F)`, тот же kind). Persist пишет оба конца; рендер только читает слоты. Не колонка, не SQL 8 бит. |
