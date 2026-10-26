---
name: "source-command-impl-wilderness-9c"
description: "Имплементирует шаг 9c плана wilderness-regions-mechanic: region state overlay на read — один фасад: клетка с region_uid и state.current_type ≠ baked → подмена ключа; tombstone → policy-fallback; применяется ниже слоя patch (terrain_delta сверху); лог overlap_rerank_deferred. Входы закрыты: 6/7 (region_uid на клетке), 9a/9b. Новый чат: /impl-wilderness-9c."
---

# source-command-impl-wilderness-9c

Use this skill when the user asks to run the migrated source command `impl-wilderness-9c`.

## Command Template

# Имплементация: wilderness-9c — region state overlay (read)

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

**Блокер-условия (все):**
1. Шаги 6/7 — `region_uid` на `WorldMapCellWire` и `FineTerrainColumnWire`.
2. Шаги 9a/9b — `iRegionStateRepository` (read) + `RegionState` POJO.
Чего-то нет → стоп, доклад мастеру.

## Прочитать до первой правки

1. [`.cursor/plans/wilderness-regions-mechanic.md`](../../../.cursor/plans/wilderness-regions-mechanic.md) — **единственный SoT этой задачи**: §4 строка **9c** (цель/ТЗ/файлы/проверка); §5 #8 (overlay-семантика, tombstone → policy-fallback), «Известный gap» — overlap re-rank deferred + лог-событие; #11 (доменные эффекты морфинга — **не** на read, при materialize/refine). Не отклоняться.
2. [`docs/tz_world_pack_storage.md`](../../../docs/tz_world_pack_storage.md) — § **Region state overlay** (точный псевдокод фасада, Layer priority ниже `patch`, `terrain_delta` сверху, gap overlap re-rank).
3. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок»
   - [`.cursor/rules/contract-creation.mdc`](../../../.cursor/rules/contract-creation.mdc)
   - [`.cursor/rules/type-kind-str-fields.mdc`](../../../.cursor/rules/type-kind-str-fields.mdc) — возвращаемый ключ = `TerrainKey`
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/layer-boundaries.mdc`](../../../.cursor/rules/layer-boundaries.mdc)
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Что уже есть — не переписывать

- `backend/app/application/worldData/pack/read/` — read-фасады: `packFineTerrainReadFacade.py`, `packRenderReadFacade.py`, `packDebugReadFacade.py`, `mapCellFromMerged.py` (слияние слоёв WP-20 с patch), `packReadContext.py`, `packReadServices.py`. Точка вызова — **одна**: в слиянии слоёв ниже `patch`.
- `WorldMapCellWire.region_uid` / `FineTerrainColumnWire.region_uid` (6/7).
- `iRegionStateRepository` read (9a), `RegionState` (9b) с `current_type: TerrainKey`, `tombstone`.
- `LandcoverRegionsCategoryPolicy` fallback-ключ (из 10b-контракта — если ещё нет, transitional `default_*` fallback-ключ как интерфейс; сверить с планом, не изобретать).
- `wildernessRegionReadService.py` (шаг 8) — прецедент тонкого read-сервиса по регионам.
- Pack = immutable snapshot: baked `system_terrain` самодостаточен для raw-читателей — overlay **не** переписывает пак.

## Скоуп шага 9c — строго по плану §4

- `backend/app/application/worldData/pack/read/regionStateOverlay.py` — чистая функция подмены по контракту ТЗ:

  ```text
  cell.region_uid is None          → system_terrain как в pack
  state(region_uid) отсутствует    → system_terrain как в pack
  state.tombstone                  → policy-fallback ключ
  state.current_type != baked key  → state.current_type
  иначе                            → system_terrain как в pack
  ```

- Один вызов-фасад в read path (слияние слоёв): применяется ко **всем слоям WP-20 ниже `patch`** — `terrain_delta`/patch-слой остаётся сверху (patch не подменяется overlay'ем).
- Подменяется **только** `system_terrain` — `system_material`, роли, z не трогаются (эффекты морфинга — refine/materialize, не read).
- L0 (`WorldMapCellWire`) и L2 (`FineTerrainColumnWire`) — одна функция, одна точка вызова в общем read path; batch-загрузка state по `region_uid`-множеству (не по одной записи на клетку — repo batch-get).
- **Известный gap реализовать как есть**: overlap re-rank не пересчитывается на read — при смене `current_type` у региона, пересекающего другие по индексу/bbox, логируется `region_state | overlap_rerank_deferred | region_uid=… neighbors=…` (warning, конвенция domain|event|key=value).
- Юнит-тесты по приёмке ниже.

- **Не в шаге 9c:** write-path (10a), re-materialize/refine-эффекты, `terrain_delta` изменения, re-bake триггеры. Overlay — read-only.

## Жёсткие запреты

- Один фасад — не размазывать подмену по пяти read-местам; raw-readers (pack dump) продолжают видеть baked ключ.
- Нет записи в пак/store — read не мутирует состояние.
- `terrain_delta` и слои `patch` — поверх overlay, не подменяются.
- Ключ подмены — `TerrainKey` typed (не `str`); fallback-ключ — из policy POJO, не литерал.
- Не трогать DAG-ноды, schema, не стартовать backend, не коммитить.
- Проверки запускать из `backend/`; не чинить окружение «заодно».

## Приёмка (из плана, строка 9c)

- `python -m compileall backend/app` — чисто.
- Юнит: `forest→steppe` в store → read отдаёт `steppe` без перепечки; `region_uid=None`/нет state → baked ключ; tombstone → policy-fallback ключ; `state.current_type == baked` → без изменений.
- `terrain_delta` patch поверх overlay — не подменяется (patch остаётся последним слоем).
- Overlap-кейс: смена типа у пересекающегося региона → `overlap_rerank_deferred` в логе; baked-победитель сохраняется до refine.
- Пометка «выполнен» в плане — только после приёмки и «ок» мастера.

## Старт

Прочитай план целиком, проверь блокеры, найди **одну** точку вызова в read path (слияние слоёв до/после patch — покажи её), покажи сигнатуру overlay и batch-get repo до первой правки.
