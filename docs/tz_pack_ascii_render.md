---
name: tz-pack-ascii-render
description: "ТЗ pack ASCII / grid render — L0 mosaic и L2 location/wilderness levels; consumers pack wire, не генераторы"
metadata:
  node_type: memory
  type: project
---

> **Статус:** SoT **pack ASCII render** (раньше отдельного ТЗ не было). **PAR-G1…G10** locked · open product Q — нет.  
> **Generate vs render:** рендер **не** materialize terrain/grade; только читает pack wire / FineTerrain.  
> **Grade domain SoT:** [`tz_terrain_relief.md`](./tz_terrain_relief.md). **Pack storage:** [`tz_world_pack_storage.md`](./tz_world_pack_storage.md).  
> **Agent plan (L2 location grade):** [`.cursor/plans/grade-detailed-location-render.md`](../.cursor/plans/grade-detailed-location-render.md)

# Pack ASCII / grid render

## Назначение

Единый контракт **debug/master ASCII** поверх World Pack:

| Слой | Что рисует | Не делает |
|---|---|---|
| L0 world mosaic | light / height / **grade** | ribbon generate, height invent |
| L2 location | surface (+ diagnostics) / **grade** | detailed ribbon grade |
| L2 wilderness tile | surface (+ mountain diagnostics) | grade v1 (out of scope) |

Код (ориентиры): `render/worldMapPackRenderer.py`, `locationTerrainPackRenderer.py`, `wildernessTilePackRenderer.py`, `fineTerrainAsciiKernel.py`, `mapSymbols.py`, `facingArrows.py`, `renderPayloads.py`; dump — `scripts/render_maps.py` / `dump_detailed_renders`.

**Антипаттерн:** «рендер чинит мир» (gap fill, invent `system_grade_uid`, повторный ribbon apply).

---

## Уровни (level keys)

Общие константы: `renderPayloads.LEVEL_*`.

### L0 (`WorldMapPackRenderer` / `render-world-grid`)

| Key | Dump (типично) | Содержимое |
|---|---|---|
| `light` / map | `world-map.txt` | terrain mosaic 32×32 / tile |
| `height` | `world-height.txt` | surface_z |
| **`grade`** | **`world-grade.txt`** | overlay `grade_symbol` по `system_grade_uid` + facing |

**Locked (мастер):** grade на L0 — **отдельный** layer/файл; **не** смешивать со map/height.

**Empty grade:** нет ни одной клетки с `system_grade_uid` → **omit** layer / **не** писать файл (не псевдопустая полная сетка). Non-empty → crop bbox + X/Y rulers.

### L2 location (`LocationTerrainPackRenderer` / `render-location-grids`)

| Key | Статус | Содержимое |
|---|---|---|
| `surface` | ✅ | FineTerrain top / surface symbols |
| `column_span` / `cliff_delta` / z-slices | ✅ diag | см. [`tz_mountain_architecture.md`](./tz_mountain_architecture.md) § Debug render |
| **`grade`** | ✅ | overlay как L0 `grade_symbol`; dump `…/locations/{uid}/grade.txt` |

**Locked (мастер):**

| Bake | Grade **generate** | Grade **render** |
|---|---|---|
| light / full (L0) | ✅ ribbon consumers | L0 `world-grade` |
| detailed (L2) | ❌ не ribbon / не invent uid | **location** `levels.grade` |

Detailed dump **не** подменяет L0 world-grade «вместо» локации.

### L2 wilderness

| Key | Статус |
|---|---|
| surface + mountain diagnostics | ✅ |
| `grade` | **v1 out of scope** (расширение — отдельный lock) |

---

## Grade ASCII — символы

SoT символа: `mapSymbols.grade_symbol(system_grade_uid, system_facing)` + `facingArrows.FACING_ARROW`.

| Условие | Символ |
|---|---|
| нет `system_grade_uid` | не клетка grade (space / omit из crop) |
| uid + facing ∈ Facing | стрелка uphill |
| uid + SHEER / facing omit | `┃` (sheer) |

**Запрещено:** рисовать «grade» только по `system_facing` без uid (ломает R36h/C11: клетка в grade ↔ uid).

Доменные поля h/L/θ на ASCII **не** дублировать — только ref + facing cache (см. relief C10/C11).

---

## Wire / data (grade на L2) — контракты

### Locked (наследуют relief + product)

| ID | Контракт |
|---|---|
| **PAR-G1** | Single-writer **geometry** grade = L0 ribbon only ([`tz_terrain_relief.md`](./tz_terrain_relief.md)) |
| **PAR-G2** | Detailed = **propagate** L0 refs на fine grid; **не** новый `geom_resolve` / ribbon apply |
| **PAR-G3** | Membership = только `system_grade_uid` (omit если нет); h/L/angle на Grade entity (R24, R36h/j, C11) |
| **PAR-G4** | Empty → нет ключа `levels.grade` / нет `grade.txt` |
| **PAR-G5** | Location grade dump path: under detailed location uid; не путать с L0 `world-grade.txt` |
| **PAR-G6** | Wilderness `levels.grade` — не v1 |
| **PAR-G7** | **FineTerrain column wire** несёт оба кэша колонки, по relief: `system_facing` (**R16**) и `system_grade_uid` (клеточный ref **R24** / R36h на pack-колонке; omit если нет). Не дублировать entity-поля. Stairs facing — per-cell ([`tz_locations.md`](./tz_locations.md)); outdoor facing SoT — Grade entity (**C10**), колонка = cache |
| **PAR-G8** | L0→L2 **`system_grade_uid` carry** = categorical **nearest** parent light (`ParentLightTile.meters_to_tx_ty`), зеркало terrain mask carry / facing. **Запрещено:** bilinear, majority resample, invent uid без L0. Knobs: `ParentLightRefinePolicy.categorical_resample=nearest` (legacy alias `terrain_resample`) ([`tz_world_pack_storage.md`](./tz_world_pack_storage.md) § Terrain mask carry) |
| **PAR-G9** | Stamp + агрегация колонки: `system_grade_uid` **и** `system_facing` только с **surface** (`z == surface_z` / top cell). **Запрещено:** majority по z-стеку. Wire: `_column_surface_attrs` |
| **PAR-G10** | **`system_grade_uid` = ref на `ReliefGradeInstance` (SLOPE\|SHEER)**, если grade есть; иначе omit (R24, R36h/j, R36f, C9/C11). Не «ASCII-токен». Pack ASCII — **consumer** того же ref (символ по uid+facing cache). Entity fields (kind/h/L/θ) на wire **не** копировать. Climb / LLM resolve entity — Wave E later ([`tz_terrain_relief.md`](./tz_terrain_relief.md)); **не** открытый вопрос «ссылается ли uid на relief» |

Разделение (уже SoT relief — не open):

| Поле | Где | Смысл |
|---|---|---|
| `system_grade_uid` | клетка / FineTerrain **column** (omit) | **ref → ReliefGradeInstance** (SLOPE\|SHEER) |
| `system_facing` | FineTerrain **column** (`Facing`, R16); опц. кэш на клетке (SQL `str`) | uphill cache; entity = SoT outdoor |
| h / L / θ / kind | **Grade entity** only | не на клетке и не на column wire |

`MapCell.system_grade_uid` и L0 `WorldMapCellWire.system_grade_uid` — уже SoT.  
`FineTerrainColumnWire.system_facing` — уже; **`system_grade_uid` на том же POJO** (G7).  
Upsample uid — **PAR-G8**; surface stamp/агрегация — **PAR-G9**.  
Legacy FineTerrain без поля uid → как empty (**PAR-G4**): omit `levels.grade`; re-bake detailed после имплементации. Forced pack invalidate — не требуется контрактом.

### Closed Q (больше не open)

| Было | Стало | Почему |
|---|---|---|
| ~~PAR-Q1~~ | **PAR-G7** | R16+R24 |
| ~~PAR-Q2~~ | **PAR-G8** | pack categorical carry + PAR-G2 |
| ~~PAR-Q3~~ | **PAR-G9** | R36f surface + stamp как facing |
| ~~PAR-Q4~~ | **PAR-G10** | uid→entity уже relief SoT; ASCII = consumer; climb later ≠ «нужна ли сущность» |
| ~~PAR-Q5~~ | **PAR-G4** | omit пустого / legacy без uid |

Open product XOR по L2 grade ASCII — **нет**. Impl backlog — план [`grade-detailed-location-render`](../.cursor/plans/grade-detailed-location-render.md).

---

## HTTP / dump (ориентиры)

| Путь | Grade |
|---|---|
| `GET …/render-world-grid` (+ dump L0) | `levels.grade` / `world-grade.txt` при non-empty |
| `GET …/render-location-grids` | target: `levels.grade` |
| `dump_detailed_renders` | target: `locations/{uid}/grade.txt` only; wilderness — нет |
| `GET …/render-wilderness-tile-grid` | grade v1 — нет |

Отдельный query `?layer=grade` **не** обязателен, если payload уже несёт `levels` dict.

---

## Границы с другими ТЗ

| Документ | Что остаётся там |
|---|---|
| [`tz_terrain_relief.md`](./tz_terrain_relief.md) | generate, Grade entity, templates, R36 |
| [`tz_world_pack_storage.md`](./tz_world_pack_storage.md) | blob layout, LOD, WP-* |
| [`tz_map_light_bake.md`](./tz_map_light_bake.md) | L0 paint/bake frame (MLB) |
| [`tz_mountain_architecture.md`](./tz_mountain_architecture.md) | L2 column_span / cliff_delta diagnostics |
| [`tz_locations.md`](./tz_locations.md) | stairs `system_facing` per-cell |

---

## История

| Дата | Изменение |
|---|---|
| 2026-08-12 | **PAR-T-4:** pack/FineTerrain/LightGrid `system_facing: Facing`; coerce on wire; MapCell SQL str |
| 2026-08-12 | **PAR-T fix wave:** T-1/2/3/5/6/7/8 resolved; T-4 Facing-as-str deferred — [`tz_generator_technical_debt.md`](./tz_generator_technical_debt.md) |
| 2026-08-12 | **Pack ASCII debt:** post-impl L2 grade → [`tz_generator_technical_debt.md`](./tz_generator_technical_debt.md) **PAR-T-1…T-8** |
| 2026-08-12 | **L2 location grade ASCII shipped:** FineTerrain `system_grade_uid`; nearest upsample; surface stamp; `levels.grade` / dump |
| 2026-08-11 | **PAR-G9/G10:** surface-only uid; uid→ReliefGradeInstance SoT (R24/R36f); ~~Q3–Q5~~ closed; open product Q = none |
| 2026-08-11 | **PAR-G8:** L0→L2 `system_grade_uid` = categorical nearest carry (pack terrain mask / facing); ~~PAR-Q2~~ closed |
| 2026-08-11 | **PAR-G7:** `FineTerrainColumnWire.system_grade_uid` locked по relief R16+R24/C10/C11; ~~PAR-Q1~~ closed |
| 2026-08-11 | **Создан** SoT pack ASCII: L0 grade; L2 location grade target; PAR-G1…G10; pointer plan `grade-detailed-location-render` |
