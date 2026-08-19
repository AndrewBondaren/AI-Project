---
name: tz-pack-ascii-render
description: "ТЗ pack ASCII / grid render — L0 mosaic и L2 location/wilderness levels; consumers pack wire, не генераторы"
metadata:
  node_type: memory
  type: project
---

> **Статус:** SoT **pack ASCII render** (файлы, L0/L2 keys, wire membership). **PAR-G\*** locked · **R36u** grade writer = detailed_bake geometry. Глиф клетки outdoor grade (3×3, выравнивание с `surface_z`) — [`tz_terrain_relief_consume.md`](./tz_terrain_relief_consume.md); код: `gradeRayDump` + sidecar `grade_rays.json`.  
> **Generate vs render:** рендер **не** materialize terrain/grade; membership читает pack wire / FineTerrain; **8-ray** дамп читает discover leftover (не колонку).  
> **Grade generate SoT:** [`tz_terrain_relief.md`](./tz_terrain_relief.md) (**R36u** / **R36t**). **Consume / 3×3:** [`tz_terrain_relief_consume.md`](./tz_terrain_relief_consume.md). **Pack storage:** [`tz_world_pack_storage.md`](./tz_world_pack_storage.md).

# Pack ASCII / grid render

## Назначение

Единый контракт **debug/master ASCII** поверх World Pack:

| Слой | Что рисует | Не делает |
|---|---|---|
| L0 world mosaic | light / height | invent height; **outdoor grade** (нет L0 grade layer) |
| L2 location | surface (+ diagnostics) / **surface_grade** + **grade_{z}** | invent uid вне detailed geometry |
| L2 wilderness tile | surface (+ mountain diagnostics) / **surface_grade** + **grade_{z}** | invent uid; L0→L2 **grade** carry |

**Scope (R36u):** L0→L2 **mask** carry (terrain / hydro / facing) — unchanged ([`tz_world_pack_storage.md`](./tz_world_pack_storage.md)). Меняется только **relief grade** writer + omit L0 grade ASCII.

Код (ориентиры): `render/worldMapPackRenderer.py`, `locationTerrainPackRenderer.py`, `wildernessTilePackRenderer.py`, `fineTerrainAsciiKernel.py`, `mapSymbols.py`, `facingArrows.py`, `renderPayloads.py`; dump — `scripts/render_maps.py` / `dump_detailed_renders`.

**Антипаттерн:** «рендер чинит мир» (gap fill, invent `system_grade_uid`, повторный ribbon apply на L0).

---

## Уровни (level keys)

Общие константы: `renderPayloads.LEVEL_*`.

### L0 (`WorldMapPackRenderer` / `render-world-grid`)

| Key | Dump (типично) | Содержимое |
|---|---|---|
| `light` / map | `world-map.txt` | terrain mosaic / tile |
| `height` | `world-height.txt` | surface_z |
| **`grade` / `world-grade`** | **omit** | outdoor grade **не** на L0 (**R36u**); не писать `world-grade.txt` как SoT |

**Locked (мастер):** L0 ASCII = map + height only. Legacy dump `world-grade.txt` / tile `levels.grade` — **не** продукт после R36u (пусто / omit).

### L2 location + wilderness (detailed dump)

| Key / файл | Статус | Содержимое |
|---|---|---|
| `surface` → `surface.txt` | ✅ | FineTerrain top / surface **symbols** |
| **`surface_z`** → **`surface_z.txt`** | ✅ | per-cell **max world-z** (FineTerrain top); L2 analog of L0 `height` |
| `column_span` / `cliff_delta` | ✅ diag | см. [`tz_mountain_architecture.md`](./tz_mountain_architecture.md) § Debug render |
| numeric z → `z/{n}.txt` | ✅ | material slice at world-z |
| **`surface_grade`** → **`surface_grade.txt`** | ✅ путь; глиф — consume TZ | **3×3** (центр всегда + до 8 исходящих лучей), поле **W** как `surface_z`, **3 строки / gy**. Источник краёв — sidecar leftover, не колонка. Omit если нет лучей и нет uid |
| **`grade_{n}`** → **`z/grade_{n}.txt`** | ✅ | **composite:** material at z + grade только где `surface_z == n`; omit если на этом z нет grade |

**Locked (мастер):**

| Bake | Grade **generate** | Grade **render** |
|---|---|---|
| light / full (L0) | ❌ (**R36u**) | нет L0 grade layer |
| detailed (`detailed_bake` geometry) | ✅ single-writer (R36 / R36t) | **location + wilderness** `surface_grade` + `z/grade_{n}` (composite) |

`surface.txt` / `z/{n}.txt` остаются **без** grade (чистый material). Grade смотреть в `surface_grade` / `grade_{n}`.

---

## Grade ASCII — клетка

**SoT раскладки клетки (outdoor L2):** [`tz_terrain_relief_consume.md`](./tz_terrain_relief_consume.md) — центр всегда, 8 краёв = исходящие лучи с rim, выравнивание X/Y с `surface_z`.

Стрелки / `┃`: `facingArrows.FACING_ARROW` и тот же sheer-глиф, **в слоте Facing луча**, не одним символом на всю клетку.

**Код L2:** `render/gradeRayDump.py` (слот из `GRID_OUTWARD_DELTA`, глиф из `ReliefSideKind` + `Facing`). L0 mosaic по-прежнему `grade_symbol` (uid overlay) — не 8-ray.

**Запрещено:** рисовать «grade» только по `system_facing` без uid (C11: клетка **в** grade ↔ uid). Это про membership occupancy, не про 8 слотов rim.

Доменные поля h/L/θ на ASCII **не** дублировать — occupancy по-прежнему uid + facing cache (C10/C11). 8 лучей — leftover discover, не колонка.

---

## Wire / data (grade) — контракты

### Locked (наследуют relief + product)

| ID | Контракт |
|---|---|
| **PAR-G1** | Single-writer **geometry** outdoor grade = **`detailed_bake` geometry** ([`tz_terrain_relief.md`](./tz_terrain_relief.md) **R36u** / **R36v**). **Не** L0 ribbon |
| **PAR-G2** | Detailed **generate** grade в chunk pool (R36v / стык **R36w**; R36 materialize + entity + refs; anchors **R36t**). **Запрещено:** трактовать detailed как «только propagate L0 uid»; **запрещено** invent uid без bake-формирования грани; **запрещён** tile-wide serial scan как SoT |
| **PAR-G3** | Membership = только `system_grade_uid` (omit если нет); h/L/angle на Grade entity (R24, R36h/j, C11) |
| **PAR-G4** | Empty omit. Outdoor 8-ray: пусто = нет claimed лучей **и** нет uid ([`tz_terrain_relief_consume.md`](./tz_terrain_relief_consume.md)); ~~omit только по uid~~ не SoT (rim без stamp). Per-z: нет файла, если на этом z нечего показать |
| **PAR-G5** | L2 grade dump under detailed location/wilderness tile. L0 `world-grade` — **не** SoT (omit) |
| **PAR-G6** | Wilderness L2 grade ASCII **in scope**: `surface_grade.txt` + `z/grade_{n}.txt` (тот же consumer, что location) |
| **PAR-G7** | **FineTerrain column wire** несёт оба кэша колонки, по relief: `system_facing` (**R16**) и `system_grade_uid` (клеточный ref **R24** / R36h на pack-колонке; omit если нет). Не дублировать entity-поля. Stairs facing — per-cell ([`tz_locations.md`](./tz_locations.md)); outdoor facing SoT — Grade entity (**C10**), колонка = cache |
| **PAR-G8** | ~~L0→L2 `system_grade_uid` categorical nearest carry~~ — **superseded (R36u)**. Grade uid **не** несут с parent light. (Carry других categorical полей terrain/mask — вне grade SoT; не использовать как membership grade.) |
| **PAR-G9** | Stamp + агрегация колонки: `system_grade_uid` **и** `system_facing` только с **surface** (`z == surface_z` / top cell). **Запрещено:** majority по z-стеку. Wire: `_column_surface_attrs` |
| **PAR-G10** | **`system_grade_uid` = ref на `ReliefGradeInstance` (SLOPE\|SHEER)**, если grade есть; иначе omit (R24, R36h/j, R36f, C9/C11). Не «ASCII-токен». Occupancy membership — consumer этого ref. Раскладка 3×3 / 8 лучей — [`tz_terrain_relief_consume.md`](./tz_terrain_relief_consume.md) (leftover, не колонка). Entity fields (kind/h/L/θ) на wire **не** копировать. Climb / LLM — Wave E later |

Разделение (уже SoT relief — не open):

| Поле | Где | Смысл |
|---|---|---|
| `system_grade_uid` | FineTerrain **column** (omit); **не** L0 SoT writer | **ref → ReliefGradeInstance** (SLOPE\|SHEER) |
| `system_facing` | FineTerrain **column** (`Facing`, R16); outdoor SoT на Grade entity | uphill cache |
| h / L / θ / kind | **Grade entity** only | не на клетке и не на column wire |

`FineTerrainColumnWire.system_grade_uid` + `system_facing` — SoT membership после detailed geometry (**PAR-G7**).  
L0 `WorldMapCellWire.system_grade_uid` — **не** writer path после R36u (legacy field / omit dump).  
Surface stamp/агрегация — **PAR-G9**.  
Legacy FineTerrain без uid → empty (**PAR-G4**): omit `surface_grade` / `grade_{n}`; re-bake detailed после имплементации writer.

**Per-z grade (locked):** `grade_{n}` = material at `n` + grade where top/`surface_z` == `n` (PAR-G9). Не копировать полный `surface_grade` в каждый z.

### Closed Q (больше не open)

| Было | Стало | Почему |
|---|---|---|
| ~~PAR-Q1~~ | **PAR-G7** | R16+R24 |
| ~~PAR-Q2~~ / ~~PAR-G8 carry~~ | **R36u** | grade не L0→L2 propagate |
| ~~PAR-Q3~~ | **PAR-G9** | R36f surface + stamp как facing |
| ~~PAR-Q4~~ | **PAR-G10** | uid→entity уже relief SoT; ASCII = consumer |
| ~~PAR-Q5~~ | **PAR-G4** | omit пустого / legacy без uid |

Open product XOR по L2 grade ASCII — **нет**.

---

## HTTP / dump (ориентиры)

| Путь | Grade |
|---|---|
| `GET …/render-world-grid` (+ dump L0) | **нет** `ascii_grade` / `world-grade.txt` (R36u) |
| `GET …/render-location-grids` | `levels.surface_grade` (+ optional `grade_{n}` в dense) |
| `GET …/render-wilderness-tile-grid` | `levels.surface_grade`; per-z grade в dump (`z/grade_{n}.txt`) |
| `dump_detailed_renders` | `surface_grade.txt` + `z/{n}.txt` + `z/grade_{n}.txt` (location и wilderness) |

Отдельный query `?layer=grade` **не** обязателен, если payload уже несёт `levels` dict.

---

## Границы с другими ТЗ

| Документ | Что остаётся там |
|---|---|
| [`tz_terrain_relief.md`](./tz_terrain_relief.md) | generate (**R36u** detailed geometry), Grade entity, templates, R36 / **R36t** |
| [`tz_terrain_relief_consume.md`](./tz_terrain_relief_consume.md) | клетка 3×3, слои leftover/wire/SQL, LLM uid→Instance→System |
| [`tz_world_pack_storage.md`](./tz_world_pack_storage.md) | FineTerrain blob layout; categorical carry **не** для grade uid |
| [`tz_map_light_bake.md`](./tz_map_light_bake.md) | L0 paint/bake frame (MLB); **без** outdoor grade writer |
| [`tz_mountain_architecture.md`](./tz_mountain_architecture.md) | L2 column_span / cliff_delta diagnostics |
| [`tz_locations.md`](./tz_locations.md) | stairs `system_facing` per-cell |

---

## История

| Дата | Изменение |
|---|---|
| 2026-08-19 | **L2 3×3 dump:** leftover rim rays (`GradeRimRay` sidecar) + `gradeRayDump` — центр поверхность, края Facing×kind; W как `surface_z` |
| 2026-08-14 | **R36w pointer:** PAR-G2 — стык на воркере; generate всё ещё chunk pool — [`tz_terrain_relief.md`](./tz_terrain_relief.md) |
| 2026-08-16 | L2 `surface_z` dump: per-cell max world-z (`surface_z.txt`) |
| 2026-08-13 | **R36v:** PAR-G1/G2 — generate в chunk pool; tile-wide serial не SoT — [`tz_terrain_relief.md`](./tz_terrain_relief.md) |
| 2026-08-13 | **R36u sync:** PAR-G1/G2/G5/G8 — grade writer = detailed_bake geometry; L0 grade ASCII omit; ~~nearest grade carry~~ superseded |
| 2026-08-13 | **L2 grade composite:** `surface_grade` / `grade_{n}` = material + grade overlay (не sparse-only) |
| 2026-08-12 | **PAR-G6 lift:** L2 dump `surface_grade.txt` + `z/grade_{n}.txt` (location+wilderness); per-z = surface_z==n |
| 2026-08-12 | **PAR-T-4:** pack/FineTerrain/LightGrid `system_facing: Facing`; coerce on wire; MapCell SQL str |
| 2026-08-12 | **PAR-T fix wave:** T-1/2/3/5/6/7/8 resolved; T-4 Facing-as-str deferred — [`tz_generator_technical_debt.md`](./tz_generator_technical_debt.md) |
| 2026-08-12 | **Pack ASCII debt:** post-impl L2 grade → [`tz_generator_technical_debt.md`](./tz_generator_technical_debt.md) **PAR-T-1…T-8** |
| 2026-08-12 | **L2 location grade ASCII shipped:** FineTerrain `system_grade_uid`; nearest upsample; surface stamp; `levels.grade` / dump |
| 2026-08-11 | **PAR-G9/G10:** surface-only uid; uid→ReliefGradeInstance SoT (R24/R36f); ~~Q3–Q5~~ closed; open product Q = none |
| 2026-08-11 | **PAR-G8:** L0→L2 `system_grade_uid` = categorical nearest carry (pack terrain mask / facing); ~~PAR-Q2~~ closed |
| 2026-08-11 | **PAR-G7:** `FineTerrainColumnWire.system_grade_uid` locked по relief R16+R24/C10/C11; ~~PAR-Q1~~ closed |
| 2026-08-11 | **Создан** SoT pack ASCII: L0 grade; L2 location grade target; PAR-G1…G10; pointer plan `grade-detailed-location-render` |
