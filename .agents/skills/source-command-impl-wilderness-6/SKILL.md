---
name: "source-command-impl-wilderness-6"
description: "Имплементирует шаг 6 плана wilderness-regions-mechanic: thin LandcoverContributor через run_mask_domain(LANDCOVER) — apply пишет system_terrain (paint_key: state → spec → fallback) + region_uid победителя по regionPrecedence; density/edge каналы; per-cell fallback default_*; WorldMapCellWire.region_uid. Входы закрыты: 0–5b. Новый чат: /impl-wilderness-6."
---

# source-command-impl-wilderness-6

Use this skill when the user asks to run the migrated source command `impl-wilderness-6`.

## Command Template

# Имплементация: wilderness-6 — thin `LandcoverContributor` + `region_uid`

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

**Блокер-условия (все):** шаги 0, 2, 2b, 3, 3b, 4, 5a, 5b сданы — `LandcoverMaterializer` существует и готов к подключению; `regionPrecedence` и `merge_rank` на реестре работают. Чего-то нет → стоп, доклад мастеру.

## Прочитать до первой правки

1. [`.cursor/plans/wilderness-regions-mechanic.md`](../../../.cursor/plans/wilderness-regions-mechanic.md) — **единственный SoT этой задачи**: §4 строка **6** (цель/ТЗ/файлы/проверка); §5 #5 L0-путь (`run_mask_domain` → `MaskFootprint` → `apply_terrain_footprint`), #7 (пересечения + цепочка 2b на клетке, WarningError equal-rank), #8 (`state_fingerprint` — чтение state для paint_key), #9 (`density`-маска). Логирование paint-источника — точки из раздела архитектуры. Не отклоняться.
2. [`docs/tz_map_light_bake.md`](../../../docs/tz_map_light_bake.md) — § Регионы покрытия › **Пересечения и приоритет** (победитель на клетке), › **L0/L2** (L0 — MaskFootprint + apply), › Состояние и переходы (paint_key: state → spec → fallback).
3. [`docs/tz_world_pack_storage.md`](../../../docs/tz_world_pack_storage.md) — § `WorldMapCellWire.region_uid` (wire-поле), § Region state overlay (read-фасад — контекст, сам overlay — шаг 9c).
4. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок»
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/layer-boundaries.mdc`](../../../.cursor/rules/layer-boundaries.mdc)
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить, schema только `0001_initial.sql` (wire-поле — dataModel, не SQL)
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Что уже есть — не переписывать

- `backend/app/application/worldData/pack/bake/lightGrid/contributors/landcover.py` — текущий contributor (климатический per-cell через `resolveForestPlains`/`default_*`); становится thin-обёрткой `run_mask_domain(LANDCOVER)`.
- `backend/app/application/worldData/pack/bake/lightGrid/maskDomainRegistry.py` + `masks/runMaskDomain.py` — реестр доменов и раннер; `MASK_DOMAIN_CONTRIBUTOR` → `LANDCOVER`.
- `backend/app/application/worldData/masks/applyFootprint.py` — `apply_terrain_footprint` (hydro-preserve, merge); точка записи клетки — расширяется `region_uid` победителя (не второй writer).
- `backend/app/application/worldData/masks/regionPrecedence.py` — tie-break (шаг 2b); `terrainMerge` на `entry.merge_rank` (3b).
- `backend/app/dataModel/worldPack/wire/worldMapCellWire.py` — `system_terrain` уже есть; += `region_uid: str | None`.
- `generators/terrain/landcover/` — materializer/autoresolve/collect (5b).
- `default_forests`/`default_plains` — transitional per-cell fallback для клеток **вне** регионов (политика, не регион).
- `seeded_u01`/`seed_rng` каналы `channel="density"`/`"edge"` — уже в растеризаторе; здесь только потребление результата.

## Скоуп шага 6 — строго по плану §4

- `contributors/landcover.py` — thin: регистрация в `maskDomainRegistry` под `MaskDomainId.LANDCOVER`, делегация `run_mask_domain`; своя логика покрытия удаляется в пользу materializer (per-cell fallback `default_*` остаётся только для клеток вне любого региона).
- `apply` пишет на клетку:
  - `system_terrain` = paint_key региона-победителя: **`state.current_type` → `entry_type` → policy fallback** (state — чтение `region_states` если стор сдан (9a); до 9a — spec→fallback, чтение стора изолировано за интерфейсом, чтобы 9b/c не переписывали apply);
  - `region_uid` победителя по `regionPrecedence` (шаг 2b) — клетка хранит победителя, overlay/read по нему;
  - `PRESERVE_HYDROLOGY_ROLES` без изменений — вода старше landcover.
- `density`/`edge`-маски — применены на растеризации (4); здесь только footprint-результат.
- Логирование по конвенции `domain | event | key=value`: `landcover | paint_key_source | region_uid=… source=state|spec|fallback`, `landcover | equal_rank_resolved | …` (warning при equal-rank по 2b — см. 2b).
- Юнит/smoke по приёмке ниже.

- **Не в шаге 6:** L2 paint (7), hills-по-ключу (7b), manifest entries (8), `region_states` стор и overlay (9a–c), `StateChangeConsumer` (10a), удаление `FORESTS`/`PLAINS`/`resolve_forest_plains`/`default_*` (10b). Transitional-пути продолжают работать.

## Жёсткие запреты

- Один writer клетки — `apply_terrain_footprint` + precedence; contributor не красит сам.
- Клетка вне региона — только `default_*` per-cell fallback, не «ближайший регион».
- Чтение `region_states` — за интерфейсом-заглушкой (до 9a возвращает `None` → spec→fallback); прямого SQL в contributor нет.
- Не вводить `MaskFootprint`-файлы persist — footprint живёт в bake-пайплайне.
- Не трогать DAG-ноды, schema, не стартовать backend, не коммитить.
- Проверки запускать из `backend/`; не чинить окружение «заодно».

## Приёмка (из плана, строка 6)

- `python -m compileall backend/app` — чисто.
- Light bake smoke на тест-мире: леса/равнины/пашни = регионы с органическими границами (не прямые линии); клетки регионов несут `region_uid`; клетки вне регионов — `default_*` фон.
- Лог содержит `paint_key_source` события; equal-rank конфликт → warning.
- Hydro-роли (sea/lake/river) не перекрашиваются landcover.
- Пометка «выполнен» в плане — только после приёмки и «ок» мастера.

## Старт

Прочитай план целиком, проверь все блокеры, сверь протокол contributor↔`run_mask_domain` и точку расширения `apply_terrain_footprint` под `region_uid`, покажи карту изменений (`landcover.py`, `maskDomainRegistry.py`, `worldMapCellWire.py`, `applyFootprint.py`) до первой правки.
