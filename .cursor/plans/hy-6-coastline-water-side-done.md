# HY-6 — водная сторона declared coastline по перпендикуляру — done

**Выполнено 2026-10-20:** шаги 1–4; геометрия и диагностика приняты. По решению мастера «Отдельный долг L0; закрыть геометрию HY-6» пропуск deepening band в L0 вынесен в **HY-10**, paint-модули не изменены. Финальная приёмка HY-6 проверяет band в coarse; исходное ожидание `s` во всём западном столбце L0 относится к HY-10.

**Долг:** HY-6 в [`docs/tz_generator_technical_debt.md`](../../docs/tz_generator_technical_debt.md).
**ТЗ:** [`docs/tz_terrain_hydrology.md`](../../docs/tz_terrain_hydrology.md) § SeaBasinGenerator (U15/U21), § declare/autoresolve.
**Evidence (smoke 2026-10-19, `world_test_004`):** вертикальная coastline x=-1500 на крайнем map-столбце gx=-2 → `coastal_sea cells=5` (только shore), `autoresolve_sea cells=0`, `open_ocean cells=0`; рендер — `s` без `~`/`o`.

## Проблема

1. `flood_water_side._in_water_strip` — осевой кламп: gx внутри размаха линии **и** gy за её пределами. Для N-S берега (`coast_gx_min == coast_gx_max`) вода невозможна **при любой фикстуре**; диагональ режется.
   → `backend/.../hydrology/shore/deepeningBandCarver.py:140-148`.
2. `flood_water_side_unbounded` обтекает открытые концы полилинии на сушевую сторону (BFS без ограничителя; wall только coast + land_shore).
3. Seeds только из `heightmap.surface_z` → море за краем bounds невозможно; «берег без воды» молчит (нет warning).
4. Light-grid `apply_declared_basins` красит `SHORE` независимо от flood → видимый `s` при нулевой воде (сам по себе не баг — симптом).

## Целевой контракт водной стороны

Водная клетка = достижима от water-seed **и** лежит по водную сторону ближайшей клетки линии:

```
water(C) ⇔ (C − K)·n(K) > 0
K — ближайшая клетка coastline, принадлежащая owning-сегменту
n(K) — водный шаг сегмента K (perpendicular away from land centroid, water_step_from_segment)
```

**Уточнение из запущенного навыка `source-command-impl-hy-6` (согласовано в шаге 1):** owning-сегмент выбирается по минимальному расстоянию до отрезка, не до растровой клетки и не по L1 BFS. Нормаль `n(K)` и проекция `t` принадлежат одному owning-сегменту. Multi-source BFS используется для достижимости и расстояния от water seeds; выбор owning-сегмента — отдельная геометрическая операция.

- Открытые концы не обтекаются: клетка за торцом имеет dot ≤ 0 → суша.
- Делает `_in_water_strip`/`_water_gy_direction` ненужными: E-W берег даёт тот же результат, N-S и диагональ получают корректную сторону; «за концом по x, но на водной стороне» (test `reaches_outside_coast_gx_strip`) покрывается.
- Вода существует только внутри `heightmap.surface_z` (bounds). Море «за краем мира» — не генерируется; документируется.
- Вогнутые берега (бухта) в v1 — ограничение heuristic'и (tie/ближайшая нормаль); сложные формы → несколько `declared_coastlines` или `declared_lakes`.

**Bounded vs unbounded** (autoresolve опирается на разницу — hy5a `reaches_outside_coast_gx_strip`, `apply_adds_open_ocean_outside_declare_strip`):

| Функция | Условие | Пример (E-W `(2,2)-(8,2)`, вода север) |
|---|---|---|
| `flood_water_side_unbounded` | `dot > 0` — полуплоскость ближайшего сегмента | `(0,1)` ∈, `(10,0)` ∈, `(0,3)` ∉ |
| `flood_water_side` | `dot > 0` **и** проекция C на ближайший сегмент внутри него (`t ∈ [0,1]` вдоль касательной) | `(2,1)` ∈ (`t=0`), `(0,1)` ∉ (`t<0`) |

**Один `n(K)` на всё:** seeds (`K + n(K)`), `land_shore` (соседи K с `dot < 0`; `dot = 0` — торец, не shore), flood — на одном per-cell векторе; centroid-fallback остаётся только для вырожденного сегмента `a == b`. Стена для BFS — dot-тест, не множество `coastline_cells` (Bresenham 8-связен, 4-связный BFS иначе протекает между клетками диагонали).

**Tie-break ближайшего K** (угол ломаной, равное расстояние до отрезков): клетка берёт `n` того K, у которого `dot` **больше** (`max` по tied) → внешний угол — вода, внутренний — суша. Детерминизм: tied K обходятся в порядке `(gy, gx)`, остаточное равенство — стабильный порядок declare-сегментов.

**Под HY-8 («вода — уровень», см. tech debt):** helper водной стороны отвечает только за **footprint борта** — *где* резать. Предикат проходимости BFS (сейчас `cell in heightmap.surface_z`) — отдельный параметр helper'а, чтобы HY-8 подменил его на `z ≤ z_sea` без правки геометрии. `carve_deepening_bands` уже в шаге 2 разносится на два вызова: `footprint = water_side_footprint(...)` → `apply_carve(footprint, ...)`; fill как отдельный шаг пока вырожден (= footprint), но шов есть. Безусловный `surface_z = level` внутри carve в HY-6 **не** чинится — это HY-8.

**Что HY-6 не решает (осознанно):** узкая вода (`water extent < bands.min`) целиком уходит в deepening band (`s`, open water нет) — это семантика `bands` как счётчика; целевой rim-профиль впадины — HY-BATH-1. Shoreline сквозь `mountain`-маску — HY-7 (механизм — HY-8). В HY-6 оба только получают warning / документированное ожидание в smoke.

## Шаги

### Шаг 1 — ТЗ: контракт водной стороны

| Поле | Содержание |
|---|---|
| Цель | зафиксировать семантику water-side для произвольной ориентации coastline до кода |
| ТЗ | `tz_terrain_hydrology.md` § SeaBasinGenerator — дописать пункт «Водная сторона»: перпендикуляр от ближайшей клетки линии, bounded (проекция внутри сегмента) vs unbounded (полуплоскость), tie-break `max dot`, открытые концы не обтекаются, вода только внутри bounds, warning при flood=0 и при `water extent < bands.min`; ссылка на HY-BATH-1 (rim-профиль) и HY-7 (shoreline × mountain) как известные ограничения |
| Файлы | `docs/tz_terrain_hydrology.md` |
| Проверка | текст согласован с мастером |
| Done | раздел обновлён |

### Шаг 2 — flood по перпендикуляру

| Поле | Содержание |
|---|---|
| Цель | водная сторона по `(C−K)·n > 0` вместо осевого `_in_water_strip` |
| ТЗ | § SeaBasinGenerator (шаг 1) |
| Файлы | `deepeningBandCarver.py` + `shore/waterSideFootprint.py` (helper водной стороны: ближайший отрезок → owning `K`, per-cell `n(K)`, `dot`, проекция `t`; multi-source BFS от water seeds; `flood_water_side` + `flood_water_side_unbounded` на нём; `water_side_seeds` и `_land_shore_cells` на том же `n(K)`; `_in_water_strip`/`_water_gy_direction` удалить). `land_shore_from_water_dist` (bbox-flood без declare) — не трогать |
| Контракт | публичные сигнатуры `flood_water_side` / `flood_water_side_unbounded` без изменений (тонкие обёртки над helper'ом с default-предикатом `cell in surface_z`); helper принимает `passable: Callable[[Cell], bool]`; внутри `carve_deepening_bands` — два вызова footprint → apply, внешняя сигнатура прежняя; `proceduralSeaAutoresolve` — без правок вызовов |
| Проверка | `python -m unittest backend.tests.test_hydrology_hy2 backend.tests.test_hydrology_hy5a`; новый `TestWaterSidePerpendicular` на `flat_heightmap(0,10,0,6)`: A1 E-W регрессия (`(5,1)` ∈, `(5,3)` ∉); A2/A3 N-S `(2,1)-(2,5)` (`(1,3)` ∈, `(3,3)` ∉; торцы `(2,0)`,`(3,0)` ∉, `(1,0)` ∈ unbounded / ∉ bounded); A4 диагональ `(1,1)-(5,5)` (`(3,2)` ∈, `(2,3)` ∉); A5 угол `(2,1)-(2,4)-(6,4)` с зафиксированным tie-break; A6 берег на `x_min` → `{}`; B bounded ∌ `(0,1)`, unbounded ∋ `(0,1)`, оба ∌ `(0,3)`; C `land_shore` N-S: `(3,3)` ∈, `(2,0)` ∉ |
| Done | вода на water-side для N-S/диагонали; нет обтекания концов; land_shore/seeds согласованы с flood; тесты зелёные |

### Шаг 3 — warning при пустом flood

| Поле | Содержание |
|---|---|
| Цель | «берег без воды» не должен быть молчаливым |
| ТЗ | § SeaBasinGenerator (шаг 1) |
| Файлы | `seaBasinGenerator.py` / `hydrologyGeneratorService.py`: (1) `declared coastline → water_dist=0 (water side outside bounds?)` при ненулевых сегментах; (2) `declared coastline → water extent N < bands.min M: no open water` когда `max(water_dist) ≤ bands.min` |
| Проверка | rebake `world_test_004` **до** правки фикстуры → warning (1) в `bake-*.log`; после шага 4 → warning (2) |
| Done | оба warning видны в generation log |

### Шаг 4 — фикстура + smoke

| Поле | Содержание |
|---|---|
| Цель | проверить всю цепочку declare → coarse water → light `~` на реальном мире |
| ТЗ | § SeaBasinGenerator; smoke-процедура из HY-5/HY-BATH-1 |
| Файлы | `fixtures/world_test_004.json`: coastline x=−1500 → **−500** (gx=−1; западнее остаётся столбец gx=−2 heightmap); coast-pin `map_x` → −500; ocean-pin остаётся западнее линии. Сдвиг только ради воды внутри bounds; по z линию **не** двигать — западный столбец `m` остаётся: гора на берегу = скалистый берег по семантике, shoreline поверх неё не рисуется (HY-7); `world_test_004` — фикстура и для HY-7 |
| Контракт | без правок wire/POJO |
| Проверка | два прохода. **State 1** (фикстура как есть): warning (1), на L0 только `s`. **State 2** (−500): wipe `db/worlds/{uid}/pack` → `POST …/map/pack/bake?mode=light` (+full) → `GET render-world-grid`; `python backend/scripts/render_maps.py {uid}` → дамп. Ожидание interim: столбец gx=−2 = deepening band (`s`, `deepening_index=1`), warning (2); `coastal_sea cells` > 5 (land_shore + столбец воды); `o`/`≈` **отсутствуют по дизайну** (весь запад внутри `declare_coastline_bbox_padded`, autoresolve пуст). `~` появится только после HY-BATH-1 rim-профиля. `s` на `m`-клетках линии/land_shore — видимый симптом HY-7, в HY-6 не чинится и не маскируется |
| Done | flood непустой на реальном мире (`water_dist` = столбец gx=−2); оба warning по состояниям; ocean-pin на водной (band) клетке, coast-pin на линии |

**Согласованное уточнение приёмки (2026-10-20):** `water_dist` и `deepening_index=1` проверяются в coarse planning; перенос band в L0 и соответствующий `s` на западном столбце — отдельный долг **HY-10**. Саму declare-линию L0 отображает; отсутствие `~`/`≈`/`o` соответствует interim bands. Остальные проверки шага сохранены.

## Не входит

- Bathymetry полноценная (HY-BATH-1, DepressionForm pipeline) **и** rim-профиль борта вместо `bands.min`-счётчика (узкая вода → `~`); clamp в `_shelf_depth` не делать.
- HY-7: shoreline не рисуется на `mountain`-маске (role `SHORE` / `shore_sea` / bands), precedence role в `tz_map_light_bake`, carve сквозь гору.
- HY-8: вода как уровень — basin carve до fill, строгий `z ≤ z_sea`, DepressionSpec как источник autoresolve-океана, переписывание hy2/hy5a на carve → fill. HY-6 оставляет только шов (предикат + footprint/apply).
- `materialize_named_locations` (LLM naming, HY-3 — после DAG).
- Изменение `world_bounds`/`world_topology_mode` семантики.
- Concave-coast полная поддержка (документированное ограничение v1).

## Проверка реализации — 2026-10-20

- Шаги 1–3 реализованы. `test_hydrology_hy6` + существующие hy2/hy5a: **35 тестов OK**; `compileall` изменённых модулей и `git diff --check` с учётом CRLF — OK. В A4 суша задана южнее диагонали повышенным весом южного ряда: на исходной плоской карте centroid `(5,3)` выбирает противоположную нормаль.
- Smoke использует существующий импорт `world_test_004`, runtime UID `1ff7d3a4-a832-4951-ad33-fe9cb314336c`; coast/ocean location UID импортом заменены на UUID. Фикстура и runtime coastline/coast-пин синхронно сдвинуты на `x=-500`, ocean-пин остаётся `x=-1900`; y/z не изменены.
- **State 1**, `x=-1500`: [bake-light-20261019T222116Z.log](../../backend/logs/generation/1ff7d3a4-a832-4951-ad33-fe9cb314336c/bake-light-20261019T222116Z.log) содержит `water_dist=0 (water side outside bounds?)`, `coastal_sea cells=5`, `autoresolve_sea cells=0`.
- **State 2**, `x=-500`: light/full bake завершены HTTP 200; light — 10 тайлов / 10240 клеток, full — 25 тайлов / 25600 клеток. [bake-full-20261019T222552Z.log](../../backend/logs/generation/1ff7d3a4-a832-4951-ad33-fe9cb314336c/bake-full-20261019T222552Z.log) содержит `water extent 1 <= bands.min 5: no open water`, `coastal_sea cells=9`, `autoresolve_sea cells=0`.
- [Проверка coarse-данных](../../.local/map-render/1ff7d3a4-a832-4951-ad33-fe9cb314336c/hy6-coarse-acceptance.json): `water_dist` = `{(-2, gy): 1 | gy=-2..2}`, все пять клеток имеют `deepening_index=1`; ocean-пин `(-2,0)` на band, coast-пин `(-1,0)` на declare-линии.
- `render_maps.py` выполнен; [итоговый L0-дамп](../../.local/map-render/1ff7d3a4-a832-4951-ad33-fe9cb314336c/20261019T222833Z/world-map.txt) содержит 160 `s` declare-линии, `~`/`≈`/`o` отсутствуют. В gx=-2 ноль `s`, несмотря на coarse band: `coarseOpenWater._OPEN_WATER` пропускает `SHORE`, `declaredBasins` красит только declare-линию. По решению мастера это отдельный долг **HY-10**; геометрия HY-6 закрыта, paint-модули не менялись.
