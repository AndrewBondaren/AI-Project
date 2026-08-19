# TZ: Terrain relief — consume (хранение + debug ASCII)

**Статус:** SoT поддомена. Генерация (C39/C41, L2, persist R43) — [`tz_terrain_relief.md`](tz_terrain_relief.md). Этот файл — **что лежит после bake** и **как это читать** (LLM, карта, дамп). Не дублирует walk.

**Родитель:** [`tz_terrain_relief.md`](tz_terrain_relief.md). ASCII-оси/файлы пака: [`tz_pack_ascii_render.md`](tz_pack_ascii_render.md) — глиф клетки grade **здесь**, не односимвольный overlay PAR-G.

---

## Граница

| Слой | Этот TZ | Не этот TZ |
|---|---|---|
| Discover / paint / SQL persist instances | нет | relief generate + R43 |
| Bake leftover `occ` / `seam` / `facing_bits` | не хранить | generate |
| Клетка → Instance → System | да | — |
| L2 ASCII: **3×3 клетка**, выравнивание с `surface_z` | да | — |
| Карта / LLM payload | контракт uid | Wave E DAG — open |

---

## Три слоя данных (locked)

Bake leftover **не** пишется в pack/SQL. Consume видит только то, что ниже.

### 1. Bake (эфемерно)

`occ` / `seam` / `facing_bits` / трассы лучей. Нужны generate и **debug 8-ray dump**. В SQL и в `FineTerrainColumnWire` **нет**.

### 2. Клетка (wire / pack / SQL map cell)

| Поле | Смысл |
|---|---|
| `system_grade_uid` | FK **Instance**. Пусто = клетка не в grade (C11). |
| `system_facing` | cache SLOPE; SHEER — omit (C10, R36h). |

Одна клетка — **не больше одного** Instance. Rim-тело луча **не** stamped (C11). Shared pit — seam в leftover, **не** 9-й grade и **не** uid на клетке.

**Запрещено:** `system_grade_uid` = System; второй uid; восстановление 8 лучей **только** из колонки (у колонки максимум один facing).

### 3. SQL сущности (R43)

| Таблица | Зерно |
|---|---|
| `relief_grade_instances` | один θ, один Facing, SLOPE **или** SHEER |
| `relief_grade_systems` | ≥2 Instance **одного** vertex (T-3c); LLM-имя формы |

Карта: Instance. System — только через `system_id` у Instance.

---

## LLM / карта (locked)

Цепочка: клетка.`system_grade_uid` → Instance → (если T-3c) System.

C13: LLM читает **сущность**, не скан сетки. Две Instance в одну низину (разные Facing / вершины) — **две** сущности; низина их не склеивает.

Wave E (какие поля в payload) — **open**.

---

## Debug ASCII — клетка 3×3 (locked)

Односимвольный overlay (`↑` / `┃` на stamped) **не** SoT. Он не показывает 8-way с rim (тело пустое) и общую низину (pit без uid).

### Слот клетки

Одна карта-клетка `(gx, gy)` = **всегда центр** + **до 8 символов по краям** (нет луча → пусто).

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

| Слот | Когда заполнен |
|---|---|
| **C** | **всегда** (клетка существует в гриде дампа) |
| 8 краёв | исходящий луч **с этой клетки как rim**: пара `(клетка, Facing)` claimed в C41 |

Центр **не** occupancy и **не** uid. Центр = глиф поверхности той же колонки (`surface.txt` / terrain), как якорь «здесь клетка». Края — только **исходящие** лучи с rim. Коридор downhill и shared pit: края **пустые** (лучи видны на соседе-rim). Изолированная низина без исходящих = один центр.

| Луч | Глиф в слоте этого Facing |
|---|---|
| нет | пусто (пробел в слоте) |
| SLOPE | `FACING_ARROW` (`↑→↓←↗↘↖↙`) |
| SHEER | `┃` (слот всё равно выбирает Facing луча) |

**Запрещено:** заполнять 8 краёв из `system_facing` колонки; рисовать входящие лучи на pit/corridor как «8-way этой клетки»; один overlay-символ как SoT.

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

Те же три клетки в `surface_grade.txt`, если только средняя (`6`) бьёт SOUTH (`┃`). В примере `.` = пустой слот (в файле — пробел), `#` = поверхность:

```
     | ... ... ...
 904 | ... .#. ...
     | ... .┃. ...
```

Низина под ней (нет исходящих) — три строки, края пустые, центр есть. Восемь лучей с вершины видны **на клетке rim**, не на дне.

### Когда писать файл

PAR-G4 «omit если нет uid» **не** годится для 8-ray: rim без stamp. Писать `surface_grade.txt`, если есть **хотя бы один claimed луч** или хотя бы один `system_grade_uid`. Пусто только если нет обоих.

### Источник 8 лучей

Не pack-колонка. Dump читает **discover leftover** (claimed `(rim cell, Facing)` + kind painted front), sidecar bake / debug-only:

- tile: `tiles/r.{gx}.{gy}.grade_rays.json`
- location: `locations/l.{uid}.grade_rays.json`

**Не** новая колонка SQL «8 бит на клетку» для продукта.

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
| Occupancy на краях pit | путает исходящий rim и дно |

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
