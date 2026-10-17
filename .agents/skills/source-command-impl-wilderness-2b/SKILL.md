---
name: "source-command-impl-wilderness-2b"
description: "Имплементирует шаг 2b плана wilderness-regions-mechanic: единая функция сравнения кандидатов клетки (merge_rank → placement_specificity → area → region_uid) в masks/regionPrecedence.py — общий tie-break для L0 apply и L2 paint. Входы закрыты: 0 и 2. Новый чат: /impl-wilderness-2b."
---

# source-command-impl-wilderness-2b

Use this skill when the user asks to run the migrated source command `impl-wilderness-2b`.

## Command Template

# Имплементация: wilderness-2b — placement tie-break клетки

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/wilderness-regions-mechanic.md`](../../../.cursor/plans/wilderness-regions-mechanic.md) — **единственный SoT этой задачи**: §4 строка **2b** (цель/ТЗ/файлы/проверка); §5 #7 «Пересечения» — цепочка сравнения и её место в § Placement priority (landcover не сдвигается и не обрезается; specificity решает только цвет клетки; саблокации наследуют specificity, child-регион = specificity родителя + 1 при равном ранге); WarningError при равном ранге + разных ключах. Не отклоняться.
2. [`docs/tz_map_light_bake.md`](../../../docs/tz_map_light_bake.md) — § Регионы покрытия › **Пересечения и приоритет** (итоговая цепочка), › Declaration и suitability (None-семантика у autoresolve); § **Placement priority** (общий доменный контракт, с которым сводится цепочка).
3. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок»
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/layer-boundaries.mdc`](../../../.cursor/rules/layer-boundaries.mdc)
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Что уже есть — не переписывать

- `backend/app/application/worldData/masks/` — дом модуля: `terrainMerge.py` (`terrain_merge_rank`, `may_paint_terrain`), `applyFootprint.py`, `runMaskDomain.py`, `mergeDeclare.py`.
- `WorldTerrainMasks.merge_rank_order()` (`dataModel/terrainMasks/worldTerrainMasks.py`) — **transitional** источник ранга до cutover (шаг 3b): сейчас ранг берётся отсюда, после 3b — из `TerrainRegistryEntry.merge_rank`. Функцию строить так, чтобы источник ранга был входом/сменяем без переписывания сравнения.
- `RegionShape.area()` / `RegionSpecBase.placement_specificity` / `identity_key()` — из шага 2 (вход этого шага).
- Equal-rank `>=` в `may_paint_terrain` сегодня даёт «поздний писатель выигрывает» — сравнение 2b заменяет это поведение **для landcover-кандидатов**, общий merge остальных доменов не меняется.

## Скоуп шага 2b — строго по плану §4

- Новый `backend/app/application/worldData/masks/regionPrecedence.py` — **одна** функция сравнения кандидатов клетки (pure, детерминистичная, без I/O):

  ```text
  1. merge_rank(current_type)   ↓   # источник ранга — параметр/lookup (transitional merge_rank_order → entry.merge_rank после 3b)
  2. placement_specificity      ↓   # равный rank; None — ниже любого явного значения (в т.ч. 0)
  3. RegionShape.area()         ↓   # без edge_noise
  4. region_uid                 ↑   # каноническая строка, стабильный tie-break
  ```

- Вход — typed кандидат (POJO/namedtuple: ключ типа, spec/region-дескриптор с `placement_specificity`, `area`, `region_uid`); выход — победитель или comparator. Форму минимальную: одна публичная функция, остальное — не для этого шага.
- `None` ниже любого явного `int`, включая `0` — реализовать через ключ сортировки, не if-лес.
- Лог WarningError при исходе, где ранг равный, а ключи разные и решил п.2–4 («выбор непрозрачен → видим») — структурный `logger.warning` по конвенции `domain | event | key=value` (`landcover | equal_rank_resolved | …`).
- Юнит-тесты по приёмке ниже.

- **Не в шаге 2b:** врезка в `apply_terrain_footprint`/`may_paint_terrain` (это шаг 6 L0 и шаг 7 L2 — сейчас функция не подключается), `UidKind.REGION` и uid реальных регионов (шаг 3), rasterizer (4), resolver (5). Только функция + тесты.

## Жёсткие запреты

- Функция чистая: никаких чтений мира, рандома, I/O; одинаковый вход → одинаковый исход при любой перестановке кандидатов.
- Не менять `terrain_merge_rank`/`may_paint_terrain`/`apply_terrain_footprint` — точки вызова появятся в шагах 6/7, здесь только каркас.
- Не дублировать rank-литералы: источник ранга — существующий `merge_rank_order()` (transitional), не свой словарь.
- Не трогать DAG-ноды, schema, не стартовать backend, не коммитить.
- Проверки запускать из `backend/`; не чинить окружение «заодно».

## Приёмка (из плана, строка 2b)

- `python -m compileall backend/app` — чисто.
- Юнит: равная specificity при разных площадях → больше `area()` выигрывает; разная specificity → большее значение выигрывает независимо от площади; полный ничей → `region_uid` по возрастанию; перестановка входного списка не меняет исход (сортировать и вызывать на shuffled копиях).
- `placement_specificity=None` проигрывает явному `0` — отдельный кейс.
- Равный rank + разные ключи → WarningError в логе по конвенции.
- Пометка «выполнен» в плане — только после приёмки и «ок» мастера.

## Старт

Прочитай план целиком, сверь строку 2b и статусы 0/2 с кодом (модели `RegionSpecBase`/`RegionShape` должны существовать — иначе стоп и доклад мастеру), покажи сигнатуру функции и карту кейсов до первой правки.
