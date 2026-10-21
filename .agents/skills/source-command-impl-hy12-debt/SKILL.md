---
name: "source-command-impl-hy12-debt"
description: "Имплементирует остаток плана hy-12-step5-review-debt: шаги 4–6 (fine carve aliasing/R-2, POJO with_*, фиксация семантик) и согласованный шаг 7 — находки ревью раунда 2 коммита 49e78d41 (uid-конвенция mouth, диагностика, crash-граница kind). Шаги 1–3 закрыты. Новый чат: /impl-hy12-debt."
---

# source-command-impl-hy12-debt

Use this skill when the user asks to run the migrated source command `impl-hy12-debt`.

## Command Template

# Имплементация: HY-12 review-debt — шаги 4–6 и раунд 2

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/hy-12-step5-review-debt.md`](../../../.cursor/plans/hy-12-step5-review-debt.md) — **единственный SoT этой задачи**. Обязательные разделы:
   - «Согласованные решения мастера» — R-1…R-6 (topology обязательна; вода видна до planning; явный отказ + runtime-fallback + полный WarningError; `channel_depth_cells` default 3; `bed_specs` удалён; `mouth_search_radius_fine` default 200 world-fine cells).
   - «Карта находок → шаги» — находки 1–21 с указанием шага.
   - Отчёты шагов 1–3 — что уже сделано в `49e78d41`: не переделывать.
   - **«Ревью раунда 2»** — находки R2-1…R2-13 коммита `49e78d41` и открытые вопросы Q-1…Q-5. Шаг 7 — только после решений мастера.
   - Шаги 4–6 — контракты, файлы, проверки, критерии Done.
2. [`.cursor/plans/hy-12-sea-elevation-contract-done.md`](../../../.cursor/plans/hy-12-sea-elevation-contract-done.md) — § шаг 5 (реки) и приёмка трека.
3. [`docs/tz_terrain_hydrology.md`](../../../docs/tz_terrain_hydrology.md) — § реки (устье/профиль/routing), level-fill.
4. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок» мастера → следующий
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc) — без литералов, дублирующих POJO
   - [`.cursor/rules/layer-boundaries.mdc`](../../../.cursor/rules/layer-boundaries.mdc) — генераторы не writer z; persist не в генераторе
   - [`.cursor/rules/contract-creation.mdc`](../../../.cursor/rules/contract-creation.mdc) — инвентаризация до нового поля; `str` только как исключение, отмеченное в ТЗ
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG-ноды, не стартовать backend, не коммитить

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Что уже есть — не переписывать

- Шаги 1–3 выполнены (commit `49e78d41`): явный `WorldTopology` во всех river-точках с TypeError-гейтом; `river_topology` удалён; `HydrologyRiversPolicy.channel_depth_cells`/`mouth_search_radius_fine`/`max_path_cells` в POJO; `channel_depth_for` на policy; `riverBedProfile.py` (spec+roles, без carver-семантики); `riverNetworkAssembler` — один API `assemble_rivers` → `AssembledRivers` (by_cell/segments/dirty_bbox/drops/diagnostics); atomic requests → `prepare_river` → один `apply_river_bed_z` → роли/drops; `riverRouting` (validate/fallback), `riverRouteRequests`, `riverRouteDiagnostics` через `ResolveContext`; `min(z, lowered_z)` сохранён намеренно (не поднимать пол ниже z_min).
- `RiverBedSpec`/`apply_river_bed_z` в `terrain/reliefObjects/riverBed/` — единственный z-writer.
- `is_river_mouth` — единый предикат «принимающее тело»; `canonical_neighbors8`/`dist2`/`unrolled_images` — topology-домен.

## Скоуп — строго по плану

- **Шаг 4:** `shore/fineHydrologyIndex.py` + caller `surfaceTerrainContext.py` — возврат z без алиасинга `hm.surface_z is surface_z`; выделить `WORLD_SURFACE_GRID`-зону (sampling, occupied-проекция, re-classify); локальные импорты наверх; по R-2 resolved вода доступна intent-planning заранее (усечение в spec — только защита дна).
- **Шаг 5:** `with_*` в `physicalWaterUnion`/`waterBody`/`mapCellHydrology` — без ручного перечисления полей, **с сохранением валидации** (голый `model_copy(update=...)` её не выполняет — см. уточнение находки 7); `apply_test_river` без `z_min=0`.
- **Шаг 6:** фиксация принятых семантик в `docs/tz_terrain_hydrology.md` + docstring'и; код не меняется.
- **Шаг 7 (находки раунда 2):** только после решений мастера Q-1…Q-5 — не начинать без них. До решений можно готовить инвентаризацию callers `plan_path_to_target`, `RECEIVER_METADATA`, `requested_mouth`.

## Жёсткие запреты

- Не расширять состав шагов молча; новый факт — явная правка плана + сообщение.
- Шаг 7 без решений Q-1…Q-5 не кодить.
- `str`/`None`-fallbacks в контрактах без пометки в ТЗ — нет; `topology=None`/`policy=None` в геометрических helpers — нет.
- Не удалять `min(z, lowered_z)` в `river_bed_spec` — осознанная защита (находка 13, уточнена).
- Реки не writer z — только `RiverBedSpec` → `apply_river_bed_z`.
- Не трогать DAG-ноды, не стартовать backend (smoke поднимает мастер), не коммитить.
- Bulk-записи — только `app.db.bulkSql`; SQL только `0001_initial.sql` + sync `db/models/`.

## Приёмка

- По критериям Done каждого шага + регрессия: `backend/tests/test_hydrology_*` (routing/depth/topology/rivers/HY-5/HY-12 suites), `compileall app`, `git diff --check`.
- Отчёт за шаг в плане — после «ок» мастера.

## Старт

Прочитай план целиком (карта находок → отчёты 1–3 → раунд 2 → шаги 4–7), сверь с кодом: `shore/fineHydrologyIndex.py`, `rivers/{riverPrepare,riverRouteRequests,riverRouting,riverRouteDiagnostics,resolveDeclaredRiverPath,riverBedProfile,riverGeometry,riverNetworkPlanner,riverMouth,classifyRiverSegments}.py`, `riverNetworkAssembler.py`, `dataModel/hydrology/{rivers,riverRouting,mapCellHydrology,waterBody,physicalWaterUnion,waterfallDrop}.py`, `terrain/passes/surfaceTerrainContext.py`. Покажи карту изменений шага 4 до первой правки и жди «ок».
