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
| 7 | **RELIEF-TD-7** | `SurfaceSupportCapture` — membership-проверка только для `templates`; остальные registry без world_uid-привязки | **open** ⚠️ требует тщательной проверки 2026-10-29 — см. § RELIEF-TD-7 |
| 8 | **RELIEF-TD-8** | `SurfaceSupportInput` — `model_copy` не прогоняет after-валидаторы; нет защиты от неканонического copy | **open** ⚠️ требует тщательной проверки 2026-10-29 — см. § RELIEF-TD-8 |
| 9 | **RELIEF-TD-9** | `hills_authored` — load-bearing зависимость от `model_fields_set` источника; known limitation при canonical round-trip | **open** ⚠️ требует тщательной проверки 2026-10-29 — см. § RELIEF-TD-9 |
| 10 | **RELIEF-TD-10** | G9-S: повторная полная растеризация declared region для каждого fine-тайла | **open** 2026-10-29 — см. § RELIEF-TD-10 |
| 11 | **RELIEF-TD-11** | G9-S: `observe_sides` перебирает все mountain entries для каждой shore-клетки; требуется оценка масштаба | **open** (performance hypothesis) 2026-10-29 — см. § RELIEF-TD-11 |
| 12 | **RELIEF-TD-12** | G9-S: восстановление authored presence через `model_construct(_fields_set=...)` | **open** (architecture) 2026-10-29 — см. § RELIEF-TD-12 |

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
| `fineTerrainAsciiKernel.draw_*_grid` | raster; L0: `map_cell_fine_span` / `x_rulers` / `bounds` |

**Не** класть `WorldMapCellWire` в L2 kernel колонок FineTerrain.

`packBakeLog` — не этот сплит.

---

## RELIEF-TD-7 — `SurfaceSupportCapture`: membership-проверка только для `templates`

**Severity:** medium. **Status:** open. **P:** P2.
**Обнаружено:** 2026-10-29 — ревью SurfaceSupport capture/input.

**Проблема:** В `_build_capture` (`surfaceSupportCapture.py:80-98`) membership-проверка
`world_uid in registry` выполняется только для `world.terrain_templates` →
`template_by_uid`. Остальные 10 registry (hills, ravine, materials, terrain,
landcover, regions, water_bodies, rivers, mountain_policy, climate,
landcover_policy) **не** проходят проверку. Если `world_uid` ссылается на объект,
которого нет в `world.terrain_hills`, `world.materials` и т.д., `get_by_id`
вернёт `None`, и capture упадёт с неочевидным `AttributeError` на `None`.

**Влияние:** В product-пути это не воспроизводится — `world.uid` и
`world.<field>.uid` заполняются одним и тем же resolver'ом (`mapCellService.py:36-53`),
поэтому `world.terrain_hills.uid` всегда равен `world.uid` при наличии объекта.
Однако контракт `SurfaceSupportCaptureInput` не гарантирует эту инвариантность явно,
и capture-модуль уязвим для ручного/тестового построения input с несогласованными
world_uid.

**Целевое решение:** Либо (a) добавить membership-проверку для всех 11 registry
(единый паттерн: `get_by_id` + явная ошибка при `None`), либо (b) задокументировать
в контракте input, что `world_uid` — identity `world` и все registry-объекты
непременно существуют при данном world_uid (тогда проверка избыточна и можно
заменить на assert). Вариант (b) проще, но менее defensive.

**Критерии закрытия:** Единый паттерн проверки для всех registry либо явный
контракт + assert; unit-тест на несогласованный world_uid → явная ошибка.

---

## RELIEF-TD-8 — `SurfaceSupportInput`: `model_copy` не прогоняет after-валидаторы

**Severity:** medium. **Status:** open. **P:** P2.
**Обнаружено:** 2026-10-29 — ревью SurfaceSupport capture/input.

**Проблема:** `SurfaceSupportInput` использует `frozen=True`. Pydantic v2
`model_copy()` на frozen-модели **не** вызывает `model_post_init` /
`field_validator(mode="after")`. После `model_copy(update={...})`
`_validate_hills_authored` не выполнится.

**Влияние:** В текущем product-пути `model_copy` на `SurfaceSupportInput` не
используется — input строится один раз в `_build_capture` и передаётся read-only.
Однако:
1. Будущий caller, делающий `input.model_copy(update={...})`, получит объект,
   на котором invariant `hills_authored == (hills is not None)` **не проверен**.
2. `model_dump()` → `model_validate()` round-trip **проверяет** invariant.
   Но `model_copy()` — нет.
3. `hills_authored` вычисляется из `model_fields_set` источника — этот
   контекст **теряется** после copy. Если кто-то скопирует input и изменит
   `hills` через `model_copy(update={"hills": ...})`, `hills_authored`
   останется старым.

**Целевое решение:**
- (a) Заменить на `model_validator(mode="after")` с явным re-check invariant.
- (b) Запретить `model_copy` через override с `raise TypeError` — input
  создаётся только через `SurfaceSupportCapture.build()`.
- (c) Сделать `hills_authored` computed property (теряется сериализация).

**Критерии закрытия:** Unit-тест: `input.model_copy(update={"hills": None})` →
invariant проверяется (или copy запрещён). Документация: `SurfaceSupportInput` —
immutable, создаётся только через `SurfaceSupportCapture.build()`.

---

## RELIEF-TD-9 — `hills_authored`: load-bearing зависимость от `model_fields_set`

**Severity:** low. **Status:** open (known limitation). **P:** P3.
**Обнаружено:** 2026-10-29 — ревью SurfaceSupport capture/input.

**Проблема:** `hills_authored` вычисляется в `SurfaceSupportCapture._build_capture`
(line 112) как `world_uid in condition.model_fields_set`. Это работает для
in-memory объектов. Однако `model_fields_set` **теряется** при:
1. `model_dump(exclude_none=False)` → `model_validate()`: если `hills: None`
   явно сериализован, round-trip даст `hills_authored=True` — **неправильно**.
2. JSON serialization без `exclude_none`: аналогично.

**Влияние:** В product-пути `ReliefTemplateSnapshot` строится в-memory
(`_load_snapshot` в `reliefTemplateStore.py`), и `model_fields_set` корректен.
При persistence round-trip семантика `hills_authored` может деградировать.

**Целевое решение:**
- (a) Явно сериализовать `hills_authored` в snapshot JSON (отдельное поле).
- (b) Запретить `exclude_none=False` для `ReliefTerrainCondition` в
  persistence-пути.
- (c) Задокументировать как known limitation.

**Критерии закрытия:** Явное решение (a/b/c) + unit-тест round-trip
`condition → dump → validate → capture` с `hills=None` → `hills_authored`
сохраняется.

---

## RELIEF-TD-10 — G9-S: повторная полная растеризация declared region на каждом тайле

**Severity:** medium. **Status:** open. **P:** P2. **Обнаружено:** 2026-10-29, независимое статическое ревью master.

**Доказательство:** `backend/app/application/worldData/generators/terrain/relief/surfaceCoating/sources.py:102-133`: `SupportSources.terrain_at()` кэширует `_tiles[tile]`, но при промахе по кэшу для каждого `ResolvedRegion` вызывает `rasterize_fine(region.spec.shape, self.world, context)` без scope, а затем отбрасывает координаты за пределами bbox тайла. `backend/app/application/worldData/masks/regionRasterizer.py`: `rasterize_fine()` проходит `shape.bbox()` целиком; в отличие от `rasterize_claim_fine(..., scope=bbox)`, ограничения выборки нет. Для региона, пересекающего N тайлов, возможны N полных обходов bbox. Это **подтверждённый кодом избыточный обход**, но величина замедления не измерена.

**Влияние:** масштабирование G9-S support при больших регионах и множестве shore-клеток; G9-S пока изолирован до G10-A, поэтому это долг **до production-активации**, а не доказанная текущая регрессия.

**Целевое решение:** дать общему rasterizer контракт ограниченной выборки по bbox тайла с сохранением исходной семантики membership/density/topology, включая wrapped/reflected координаты. Не дублировать растеризацию в `SupportSources`. Альтернатива — существующий эквивалентный пространственный индекс, если он обеспечивает ту же семантику. Сравнить результаты с текущим полным проходом.

**Критерии закрытия:** тесты эквивалентности полной и ограниченной выборки для planar/wrapped и граничных регионов; тест на отсутствие повторного полного обхода при нескольких тайлах; замер на крупном регионе с множеством тайлов; отсутствие изменений в terrain selection.

---

## RELIEF-TD-11 — G9-S: стоимость перебора mountain layout для каждой shore-клетки

**Severity:** medium (предварительно). **Status:** open, требует профилирования. **P:** P2 candidate. **Обнаружено:** 2026-10-29, независимое статическое ревью master.

**Доказательство:** `backend/app/application/worldData/generators/terrain/relief/surfaceCoatingSupport.py:132-139` вызывает `observe_sides(layout, cell, ...)` для каждой shore-клетки в surface extent. `backend/app/application/worldData/generators/terrain/relief/surfaceCoating/geometry.py`: `observe_sides()` перебирает все `layout.entries` и топологические образы, затем вызывает геометрические kernels. Прямой пространственный prefilter в просмотренном пути не найден. Это **гипотеза о существенном runtime cost**, не измеренный дефект.

**Влияние:** рост затрат на G9-S при большом mountain layout и числе shore-клеток; до G10-A не считать production-регрессией.

**Целевое решение:** сначала профиль на репрезентативных размерах; при подтверждении — spatial candidate selection/footprint в общем владельце геометрии с сохранением топологии и правил winner/fraction. Не создавать новый слой кэша, пока не проверен существующий planning/cache.

**Критерии закрытия:** измерение количества проверок и времени на сетках с разным числом гор и shore-клеток; эквивалентность выбранного `SideObservation` до/после оптимизации; решение о необходимости оптимизации по результатам профиля.

---

## RELIEF-TD-12 — G9-S: реконструкция Pydantic authored presence в application-layer

**Severity:** low. **Status:** open (architecture). **P:** P3. **Обнаружено:** 2026-10-29, независимое статическое ревью master.

**Доказательство:** `backend/app/application/worldData/generators/terrain/relief/surfaceCoating/sources.py:51-64` создаёт `LandcoverTerrainPolicy` через `model_construct(_fields_set=fields, ...)`, добавляя `hills` по `landcover.terrain_policy_hills_authored`, затем вызывает `apply_to()`. `LandcoverTerrainPolicy.apply_to()` использует `self.has_authored_hills` (`model_fields_set`) при том, что `registry_hills_authored` передаётся явно. Слой реализации вынужден восстанавливать внутреннее состояние POJO ради применения политики. **Функциональный дефект не доказан**.

**Влияние:** неочевидный контракт и риск расхождения семантики authored presence при эволюции модели/codec; смежно с RELIEF-TD-9, но относится к потреблению уже captured facts.

**Целевое решение:** передавать явно оба authored-факта в операцию применения политики (или использовать типизированный captured contract), без `model_construct(_fields_set=...)`. Не создавать отдельный адаптер/домен без необходимости; сохранить существующий приоритет registry hills vs landcover override.

**Критерии закрытия:** отсутствие ручного восстановления `model_fields_set` в `SupportSources`; тесты случаев hills absent / explicit null / concrete policy и приоритета registry; неизменность результатов после canonical encode/decode.

---

## Не этот документ

- Алгоритм полного occupancy / кто в обходе на тайле 1e6 — **R41-T-25**.
- Locked-карты `test_relief_r41_t25_locked_cases.py` — без правки до просьбы мастера.
- DAG, Occupancy v1, `0002_*.sql`.

---

## История

| Дата | Изменение |
|---|---|
| 2026-10-29 | **TD-10–TD-12:** независимый аудит G9-S: повторная растеризация (подтверждена), стоимость mountain geometry (гипотеза), authored presence (архитектура). |
| 2026-10-29 | **TD-7, TD-8, TD-9:** ревью SurfaceSupport capture/input — membership-проверка, model_copy, model_fields_set. |
| 2026-08-27 | **TD-4:** срез pretty `rays[]` I/O (`GradeRaySidecar`, Writer/Reader). Leftover-pack остаётся для locked. |
| 2026-08-27 | **TD-2:** mill `gradeRimRays` без halo; leftover-pack → `gradeRimPackLegacy` (lazy re-export для locked). |
| 2026-08-27 | **TD-5:** `finish` = pack files; T-3c emit = `emit_fine_grade_catalog` на runner. |
| 2026-08-27 | **TD-1:** dump/read `slots[8]` (`GradeSlotIndex`); persist уже писал sidecar. |
| 2026-08-27 | **TD-3 + смешение:** константы leftover в `gradeLeftoverPair`; occupancy-validator отделён от R44; `mill_rim_rays`; `n_cells`. |
| 2026-08-26 | Первый срез: dual `rays[]`/`slots[8]`, `FineChunkPersist`, классы >400, хардкоды 80°/L=1/45°. |
