---
name: tz-terrain-relief-technical-debt
description: "Техдолг кода relief grade: god-object, жирные классы, смешение слоёв, хардкоды. Не SoT generate."
metadata:
  node_type: memory
  type: project
---

# Terrain relief — technical debt (код)

**Тип:** инженерное ТЗ / living registry. Не generate SoT, не dump-контракт.  
**SoT продукта:** [`tz_terrain_relief.md`](./tz_terrain_relief.md), [`tz_terrain_relief_consume.md`](./tz_terrain_relief_consume.md).  
**Очередь IDs generate (T-25 occupancy):** [`tz_generator_technical_debt.md`](./tz_generator_technical_debt.md) **R41-T-25**. Этот файл — **запахи кода** после посадки pack-слотов (2026-08-26), не дубль алгоритма заполнения.  
**План агента (не SoT):** [`.cursor/plans/relief-pack-slot-contract-t25.md`](../.cursor/plans/relief-pack-slot-contract-t25.md).

**Срез кода:** persist пишет `SCH-GRADE-CELL-SLOTS`; dump читает `slots[8]`. Locked-тесты `test_relief_r41_t25_locked_cases.py` не менять без просьбы мастера.

---

## Приоритет

| # | ID | Что | Status |
|---|---|---|---|
| 1 | **RELIEF-TD-1** | Dump/read на `slots[8]`; persist-путь без `rays[]` | **done** 2026-08-27 |
| 2 | **RELIEF-TD-2** | Старый валидатор R44 не звать с generate; не закрывать слот из z | **done** 2026-08-27 |
| 3 | **RELIEF-TD-3** | Порог leftover SHEER 80° и L=1 — именованные SoT-константы, не рядом с envelope 45° | **done** 2026-08-27 |
| 4 | **RELIEF-TD-4** | Срез leftover-pack / pretty `rays[]` с persist; leftover-хелперы — пока locked-тесты | **partial** 2026-08-27 — pretty `GradeRaySidecar` / Writer-Reader `rays[]` **done**; `downhill` / halo / R44 остаются для locked |
| 5 | **RELIEF-TD-5** | Pack persist vs T-3c catalog emit — не один бог | **done** 2026-08-27 (`finish` = pack files; emit = runner; SQL upsert = оркестраторы) |
| 6 | **RELIEF-TD-6** | `WorldMapPackRenderer` сплит raster/pins/omit-grade; `packBakeLog` god-модуль | **partial** — renderer **done** 2026-08-27; `packBakeLog` open |

---

## God-object

Новый слой слотов (`GradeCellSlots`, `gradeSlotSidecar`, `pack_cell_slots`) — **не** god-object.

| Где | Проблема |
|---|---|
| **`FineChunkPersist`** | Pack files: location zst + sidecar + manifest. Occupancy sidecar — `_persist_grade_cell_slots`. Mill leftover — `_mill_rim_acc`. T-3c emit — `emit_fine_grade_catalog` на runner (**RELIEF-TD-5** done). SQL upsert — `persist_relief_grades` на оркестраторах |
| `WorldMapPackRenderer` | фасад ~207 — mask+height SoT; raster/pins/macro/grade вынесены (**RELIEF-TD-6** renderer done) |
| `packBakeLog.py` | **1158** строк — не класс, god-**модуль** логов |
| `WorldPackWriter` | 325 — все виды pack-файлов в одном фасаде |
| `PackDetailedBakeOrchestrator` | 302 — оркестрация bake |

---

## Классы / файлы > 400 строк

| | Строк | Класс? |
|---|---|---|
| `WorldMapPackRenderer` | **~207** | да — фасад mask+height. Было ~458; сплит 2026-08-27 |
| `WildernessTilePackRenderer` | 353 | почти порог |
| `packBakeLog.py` | 1158 | нет, модуль функций |
| `fineTerrainAsciiKernel.py` | 412 | нет, набор dump-функций |
| `reliefTerrainEnvelope.py` | 417 | POJO + методы конверта |

`gradeSlot.py`, `gradeLeftoverPair.py`, `pack/refine/gradeCellSlots.py`, `gradeSlotSidecar.py` — под порогом. `FineChunkPersist` (~293) — не этот порог.

---

## Смешивание ответственности

### RELIEF-TD-1 — два контракта pack

| Слой | Старый `GradeRimRay` / `rays[]` | Новый `slots[8]` |
|---|---|---|
| Persist | не пишет | пишет |
| Dump / `PackRenderReadFacade` | unit dump: `GradeRayIndex` (`test_grade_ray_dump`) | `read_grade_cell_slots_*` |
| Mill discover | копит `rim_rays` (`rim_rays_from_front`; модуль без `leftover_plus_halo`) | не источник sidecar |
| Валидатор | `validate_grade_cell_empty_rays` + `leftover_plus_halo` (`gradeCellRays`, locked/тесты) | `validate_grade_cell_slots` (`gradeCellSlotValidate`; persist только `DEBUG_GRADE_SLOT_VALIDATE=1`) |
| I/O | **срезан** (`gradeRaySidecar` / `merge_grade_rays_*` удалены) | `gradeSlotSidecar` + `merge_grade_cell_slots_*` |

Bake и dump — `slots[8]`. Старый sidecar без `SCH-GRADE-CELL-SLOTS` dump не рисует края (не dual-read). Leftover-pack-хелперы в `gradeRimRay` / `gradeRimPackLegacy` — locked-тесты (**RELIEF-TD-4** residual).

### Прочее

| Где | Status |
|---|---|
| R44 и occupancy-validator в одном файле | **done** — `gradeCellRays` vs `gradeCellSlotValidate`; диаграмма 3×3 — `emptySlotDiagram` |
| `FineChunkPersist.finish` pack + T-3c emit | **done** **RELIEF-TD-5** — emit в `fineGradeCatalog` / runner; SQL не был в `finish` |
| `FineRefineResult.rim_rays` врало | **done** — `mill_rim_rays` |
| `gradeSlot.py` merge + decode + assert дельт | **done** дельты из `GRID_OUTWARD_DELTA`; decode по членам enum; merge остаётся как у `GradeRimRay` |
| правила пары в `pack/refine` | **done** — `dataModel` `gradeLeftoverPair`; pack только обход occupancy |

---

## Хардкоды

### Writer / угол leftover (RELIEF-TD-3) — done

`LEFTOVER_SHEER_MIN_DEG` / `LEFTOVER_PAIR_LENGTH_CELLS` в [`gradeLeftoverPair.py`](../backend/app/dataModel/terrain/relief/gradeLeftoverPair.py). `GradeOctant.opposite` через `Facing.OPPOSITE`.

### POJO `gradeSlot.py` — done

Decode по enum; дельты = `GRID_OUTWARD_DELTA`; `schema_id` валидируется против `GRADE_SLOT_SCHEMA_ID` (без второго `Literal` строки).

`GRADE_SLOT_COUNT=8` / `GRADE_SLOT_CODE_MAX=10` и члены enum 0…10 — **wire-контракт**, не долг.

### Persist / логи — done

Sidecar heartbeat: `n_cells`. Location flush: `LOCATION_TERRAIN_CHUNK_CX/CY`.

`EXECUTEMANY_BATCH_SIZE` на heartbeat валидатора — общий размер пачки, не второй литерал 5000.

### Старый стек (RELIEF-TD-4 partial)

| | |
|---|---|
| `gradeRimRay._downhill_leftover_kind` → `slope_outcome` / plains envelope | запрещён для leftover L=1 (нужен `leftover_pair_is_sheer`) |
| `gradeRaySidecar` `indent=2` | **done** — файл и Writer/Reader `rays[]` удалены |
| R44 `_slot_closed`: нет соседа в z → слот закрыт | invent шва — **не** generate/persist; живёт для locked (**TD-4**) |

---

## RELIEF-TD-2 — R44 не на generate (done 2026-08-27)

Bake **не** вызывает `validate_grade_cell_empty_rays`. Persist пишет `pack_cell_slots`; occupancy-validator (`validate_grade_cell_slots`) не закрывает слот из z.

Mill [`gradeRimRays.py`](../backend/app/application/worldData/pack/refine/gradeRimRays.py) — generate API `rim_rays_from_front`. `leftover_plus_halo` / downhill / COUPLE-на-halo **не** импортируются при этом импорте (discover).

`pack_slots_for_persist` — leftover-pack для locked-тестов: тело в [`gradeRimPackLegacy.py`](../backend/app/application/worldData/generators/terrain/relief/validate/gradeRimPackLegacy.py); lazy re-export с `gradeRimRays`, чтобы не править импорты тестов.

R44 invent-from-z (`_slot_closed`) остаётся в `gradeCellRays` до полной срезки leftover-стека (**RELIEF-TD-4** residual).

## RELIEF-TD-4 — leftover-pack / pretty `rays[]` (partial 2026-08-27)

**Persist I/O (done):** нет `gradeRaySidecar.py`, нет `GradeRaySidecar`, нет `merge_grade_rays_*` / `read_grade_rays_*`. Bake пишет только `SCH-GRADE-CELL-SLOTS`. Loader без этого `schema_id` → пустой dump (не dual-read `rays[]`).

**В дереве для locked (open):** `downhill_leftover_rim_rays` / `_downhill_leftover_kind` (plains envelope, не `leftover_pair_is_sheer`), `leftover_plus_halo`, `pack_slots_for_persist` (`gradeRimPackLegacy` + lazy re-export), `couple_rim_rays` / `pack_rim_slot_rays`, R44 `validate_grade_cell_empty_rays`. Unit dump ещё рисует `GradeRimRay` через `GradeRayIndex`.

Полный срез этих символов — **после** явной правки `test_relief_r41_t25_locked_cases.py` (и `test_grade_rim_pack_and_validate` / `test_grade_ray_dump`).

## RELIEF-TD-5 — pack persist vs catalog emit (done 2026-08-27)

`FineChunkPersist.finish` — pack files only: location `terrain.zst`, sidecar слотов, manifest. Возвращает unmerged `grade_instances` и `vertex_seams` (следы T-3c).

T-3c in-memory emit — [`emit_fine_grade_catalog`](../backend/app/application/worldData/pack/refine/fineGradeCatalog.py) после `finish` в `FineChunkRunner.refine_rects` (`merge_grade_instances` + `emit_relief_grade_systems` + bake log). Контракт оркестраторов `result.grade_systems` тот же.

SQL upsert **не** был в `finish`: `persist_relief_grades` на `PackDetailedBakeOrchestrator` / `FineTerrainRefineOrchestrator` / light pack.

## RELIEF-TD-6 — `WorldMapPackRenderer` (>400)

**Не** generate / pack-слоты. SoT dump L0: [`tz_pack_ascii_render.md`](./tz_pack_ascii_render.md) — **map + height**; L0 `world-grade` omit (**PAR-G5**, residual [`tz_generator_technical_debt.md`](./tz_generator_technical_debt.md) **R36i-T-3a**).

`WildernessTilePackRenderer` (~353) уже на `fineTerrainAsciiKernel` — не обязательный сплит. `packBakeLog.py` (1158) — god-**модуль**, **ещё open**.

### Сплит (done 2026-08-27)

Фасад [`worldMapPackRenderer.py`](../backend/app/application/worldData/render/worldMapPackRenderer.py) (~207): индекс тайлов + pins; SoT **mask + height**. Публичные `render_*` сохранены (thin delegate).

| Модуль | Роль |
|---|---|
| `lightMapCells` | `wire_symbol` / `wire_grade_symbol` |
| `lightMapPins` | проекция `locations_index` |
| `lightMosaicFrame` | MLB-12 рамка + `cell_at_world` |
| `lightMosaic` | collect mask/height; `render_all_tiles` |
| `worldMapMacroRender` | обзор 1 глиф / макротайл, не mask SoT |
| `worldMapGradeOverlay` | L0 grade leftover (**PAR-G5** omit) |
| `fineTerrainAsciiKernel.draw_*_grid` | raster; L0: `cell_size_m` / `x_rulers` / `bounds` |

**Не** класть `WorldMapCellWire` в L2 kernel колонок FineTerrain.

`packBakeLog` — не этот сплит.

---

## Не этот документ

- Алгоритм полного occupancy / кто в обходе на тайле 1e6 — **R41-T-25**.
- Locked-карты `test_relief_r41_t25_locked_cases.py` — без правки до просьбы мастера.
- DAG, Occupancy v1, `0002_*.sql`.

---

## История

| Дата | Изменение |
|---|---|
| 2026-08-27 | **TD-4:** срез pretty `rays[]` I/O (`GradeRaySidecar`, Writer/Reader). Leftover-pack остаётся для locked. |
| 2026-08-27 | **TD-2:** mill `gradeRimRays` без halo; leftover-pack → `gradeRimPackLegacy` (lazy re-export для locked). |
| 2026-08-27 | **TD-5:** `finish` = pack files; T-3c emit = `emit_fine_grade_catalog` на runner. |
| 2026-08-27 | **TD-1:** dump/read `slots[8]` (`GradeSlotIndex`); persist уже писал sidecar. |
| 2026-08-27 | **TD-3 + смешение:** константы leftover в `gradeLeftoverPair`; occupancy-validator отделён от R44; `mill_rim_rays`; `n_cells`. |
| 2026-08-26 | Первый срез: dual `rays[]`/`slots[8]`, `FineChunkPersist`, классы >400, хардкоды 80°/L=1/45°. |
