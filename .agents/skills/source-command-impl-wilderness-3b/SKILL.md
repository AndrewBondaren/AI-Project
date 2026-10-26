---
name: "source-command-impl-wilderness-3b"
description: "Имплементирует шаг 3b плана wilderness-regions-mechanic: merge rank cutover — terrain_merge_rank/may_paint_terrain на TerrainRegistryEntry.merge_rank, удаление TERRAIN_MERGE_RANK_HIGH_TO_LOW/merge_rank_order/system_terrain_for_domain. Домен — writer, не приоритет. Входы закрыты: 0, 2, 3 (merge_rank должен существовать на записи реестра). Новый чат: /impl-wilderness-3b."
---

# source-command-impl-wilderness-3b

Use this skill when the user asks to run the migrated source command `impl-wilderness-3b`.

## Command Template

# Имплементация: wilderness-3b — merge rank cutover

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

**Блокер-условие:** шаг 3 закрыт — `TerrainRegistryEntry.merge_rank` существует и несёт builtin-значения из `canonical_defaults()`. Нет — стоп, доклад мастеру, этот шаг не исполняется.

## Прочитать до первой правки

1. [`.cursor/plans/wilderness-regions-mechanic.md`](../../../.cursor/plans/wilderness-regions-mechanic.md) — **единственный SoT этой задачи**: §4 строка **3b** (цель/ТЗ/файлы/проверка); §5 #7 «Пересечения» — домен = writer, приоритет = у ключа. Не отклоняться.
2. [`docs/tz_map_light_bake.md`](../../../docs/tz_map_light_bake.md) — § **Merge `system_terrain`** (источник ранга — `TerrainRegistryEntry.merge_rank`, N+1-ключи получают ранг в своей записи), § Hybrid C; § Регионы покрытия › Реестр и CoverageResolver.
3. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок»
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc) — ранги только из реестра
   - [`.cursor/rules/layer-boundaries.mdc`](../../../.cursor/rules/layer-boundaries.mdc)
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Что уже есть — не переписывать

- `backend/app/application/worldData/masks/terrainMerge.py` — `TERRAIN_MERGE_RANK_HIGH_TO_LOW`, `terrain_merge_rank`, `may_paint_terrain`, `system_terrain_for_domain` — **удаляемая** transitional-механика.
- `backend/app/dataModel/terrainMasks/worldTerrainMasks.py` — `merge_rank_order()` — **удаляется** после перепайки потребителей.
- `backend/app/dataModel/masks/enums/maskDomainId.py` — домен-ранкинг, привязанный к enum — **удаляется** (сами члены `FORESTS`/`PLAINS` **не трогать** — их cutover шаг 10b).
- `backend/app/application/worldData/masks/applyFootprint.py` — `apply_terrain_footprint` — точка merge на клетке; перепайка на ранг записи реестра.
- `backend/app/application/worldData/pack/bake/lightGrid/paintTerrain.py` — caller paint, потребитель ранга.
- `TerrainRegistryEntry.merge_rank` + `canonical_defaults()` (`road > ravine > mountain > forest > plains`) — вход из шага 3; `may_paint_terrain` получает запись реестра мира.
- `regionPrecedence.py` (шаг 2b) — источник ранга переходит на ту же точку (`entry.merge_rank`), если уже есть.

## Скоуп шага 3b — строго по плану §4

- Перепайка `terrain_merge_rank` / `may_paint_terrain`: ранг ключа — `world.terrain_registry.entry_for(key).merge_rank`, не таблица доменов; домен-писатель приоритет не задаёт (domain = writer, rank = у ключа).
- Удаление `TERRAIN_MERGE_RANK_HIGH_TO_LOW`, `WorldTerrainMasks.merge_rank_order()`, `system_terrain_for_domain` и связанного домен-ранкинга в `maskDomainId` — после перепайки всех потребителей (grep до нуля).
- Хранимая семантика ключа не меняется: клетка пишет `system_terrain`, ранг живёт в реестре мира; N+1-ключ получает ранг из своей записи без правок engine.
- Поведение неизменно для текущих ключей: builtin-значения в `canonical_defaults()` (шаг 3) дают тот же итоговый порядок, что таблица до cutover — это и есть приёмка.
- `PRESERVE_HYDROLOGY_ROLES` / hydro-preserve логика `apply_terrain_footprint` — без изменений (вода старше landcover — не рангом, а явным preserve).

- **Не в шаге 3b:** удаление `MaskDomainId.FORESTS`/`PLAINS` и policy-категорий (шаг 10b), `regionPrecedence` врезка (уже есть либо шаг 6), landcover materializer (5b), любые новые ключи террейна.

## Жёсткие запреты

- Никаких rank-литералов в application после удаления — чтение только через запись реестра; ключ без записи = контрактная ошибка, не silent default (fallback — только canonical `entry_for`/fallback POJO реестра, если он есть в dataModel).
- Поведение merge для существующих ключей — побитово то же: проверка — тесты порядка и smoke, не «на глаз».
- Не трогать членов `MaskDomainId` (только домен-ранкинг), DAG-ноды, schema; не стартовать backend, не коммитить.
- Не переносить equal-rank WarningError из 2b — логирование привязки идёт вместе с потребителями (шаги 6/7), здесь — только источник ранга.
- Проверки запускать из `backend/`; не чинить окружение «заодно».

## Приёмка (из плана, строка 3b)

- `python -m compileall backend/app` — чисто; `grep` по `TERRAIN_MERGE_RANK_HIGH_TO_LOW` / `merge_rank_order` / `system_terrain_for_domain` — ноль совпадений в дереве.
- Существующие тесты merge rank (дороги/ravine/горы/landcover) — тот же порядок, зелёные без правок тестов.
- Light bake smoke на тест-мире — идентичен до/после (клетки, роли, ключи).
- Ключ с кастомным `merge_rank` в записи реестра (юнит) — применяется без правок engine.
- Пометка «выполнен» в плане — только после приёмки и «ок» мастера.

## Старт

Прочитай план целиком, сверь строку 3b и статус шага 3 с кодом (`merge_rank` на `TerrainRegistryEntry` должен существовать), покажи карту потребителей старого ранга (grep-лист → куда перепаивается каждый) до первой правки.
