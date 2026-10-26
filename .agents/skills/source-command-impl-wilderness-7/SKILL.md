---
name: "source-command-impl-wilderness-7"
description: "Имплементирует шаг 7 плана wilderness-regions-mechanic: L2 интеграция — region paint поточечно в build_tile_surface_state между upsample и place_hills; upsample → fallback-роль фона; FineTerrainColumnWire.region_uid. Входы закрыты: 0–6. Новый чат: /impl-wilderness-7."
---

# source-command-impl-wilderness-7

Use this skill when the user asks to run the migrated source command `impl-wilderness-7`.

## Command Template

# Имплементация: wilderness-7 — L2 интеграция (region paint на fine-сетке)

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

**Блокер-условия (все):** шаги 0–6 сданы — `RegionRasterizer.rasterize_fine`, `regionPrecedence`, `LandcoverMaterializer`, L0-paint с `region_uid` работают. Чего-то нет → стоп, доклад мастеру.

## Прочитать до первой правки

1. [`.cursor/plans/wilderness-regions-mechanic.md`](../../../.cursor/plans/wilderness-regions-mechanic.md) — **единственный SoT этой задачи**: §4 строка **7** (цель/ТЗ/файлы/проверка); §5 **#5** (текущий путь `build_tile_surface_state:150` — `upsample` → `place_hills` → `merge_hydro_hard_corridor`; upsample деградирует до fallback; поточечное членство в fine-координатах; порядок upsample → region paint → hills → hydro merge; **одна точка правки**). Не отклоняться.
2. [`docs/tz_map_light_bake.md`](../../../docs/tz_map_light_bake.md) — § Регионы покрытия › **L0/L2** (одна shape → два rasterize; L2 поточечно, край чёткий в метрах).
3. [`docs/tz_world_pack_storage.md`](../../../docs/tz_world_pack_storage.md) — § **Fine terrain column** (`region_uid?` на колонке), § Region state overlay (контекст — overlay сам в 9c).
4. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок»
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/layer-boundaries.mdc`](../../../.cursor/rules/layer-boundaries.mdc)
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Что уже есть — не переписывать

- `backend/app/application/worldData/materialize/terrainBatchOrchestrator.py` — `build_tile_surface_state` (~109): `upsample_terrain_from_parent_light` (~150) → `place_hills` (~162) → hydro merge. **Одна точка врезки** — между upsample и place_hills.
- `backend/app/application/worldData/masks/regionRasterizer.py` — `rasterize_fine` (шаг 4): членство в метровых координатах, та же формула что L0.
- `backend/app/application/worldData/masks/regionPrecedence.py` — tie-break победителя клетки (2b).
- `backend/app/dataModel/worldPack/wire/fineTerrainChunkWire.py` — колонка с `system_terrain`/`system_material`; += `region_uid: str | None`.
- `parentLightTerrain.py` / `upsample_terrain_from_parent_light` — текущий nearest-carry из L0: становится **policy-fallback фона** (неполотно не исчезает — клетки вне регионов получают фон как раньше через `default_*`-политику).
- `place_hills` — должен видеть корректное покрытие: region paint до hills (порядок зафиксирован); hills-политика по ключу — **шаг 7b, здесь не трогать**.
- `merge_hydro_hard_corridor` — после region paint; вода старше.

## Скоуп шага 7 — строго по плану §4

- В `build_tile_surface_state` между upsample и `place_hills`:
  - region paint **поточечно**: для каждой fine-колонки — членство в регионах (`rasterize_fine`/claim-функция на метровых координатах, заданные Specs из collect/materializer-пути домена), победитель по `regionPrecedence`;
  - `surface_terrain` колонки = paint_key победителя (state → spec → fallback, тот же источник что шаг 6 — общий paint-резолвер, не копия);
  - `FineTerrainColumnWire.region_uid` = uid победителя.
- `upsample_terrain_from_parent_light` → **fallback-роль**: фон непокрытых клеток («state → spec → fallback» — upsample покрывает именно fallback-ветку, не основной paint); L0-контур больше не задаёт L2-геометрию.
- Seam: членство через `topology.canonicalize` (из 4) — seam-регион красит оба края fine-сетки.
- Hydro merge — **после** region paint, поведение без изменений.
- Логирование `landcover | paint_key_source | …` на L2 той же конвенции.
- Юнит/smoke по приёмке ниже.

- **Не в шаге 7:** `place_hills` по ключу реестра / `openLandTerrains` предикат (7b), manifest (8), `region_states`/overlay (9), consumer (10a). Hills получают корректное покрытие автоматически — политика пока `plains_key`/`forest_key` как есть.

## Жёсткие запреты

- Одна точка правки — между upsample и `place_hills`; upsample не удаляется и не переписывается (fallback-роль).
- Та же формула членства, что L0 — никакой отдельной L2-геометрии (иначе контур L2 ≠ L0 — баг, который лечит весь план).
- Победитель — только `regionPrecedence`; свои сравнения в оркестраторе запрещены.
- Hydro merge и preserve-семантика без изменений.
- Не трогать DAG-ноды, schema (wire-поле — dataModel), не стартовать backend, не коммитить.
- Проверки запускать из `backend/`; не чинить окружение «заодно».

## Приёмка (из плана, строка 7)

- `python -m compileall backend/app` — чисто.
- Refine чанка на границе региона: край покрытия **чёткий в fine-координатах**, не лесенка L0-сетки; колонки региона несут `region_uid`.
- Клетки вне регионов — тот же фон, что до шага (upsample-fallback).
- `place_hills` видит region-покрытие (холмы не ставятся на клетки леса там, где раньше стояли).
- Hydro-мерж поверх: вода старше покрытия.
- Пометка «выполнен» в плане — только после приёмки и «ок» мастера.

## Старт

Прочитай план целиком, проверь все блокеры, покажи точный diff-план `build_tile_surface_state` (где paint-вызов, откуда Specs/claim-контекст приходит в оркестратор — collect-путь или параметр) до первой правки.
