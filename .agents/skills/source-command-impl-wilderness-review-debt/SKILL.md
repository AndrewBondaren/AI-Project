---
name: "source-command-impl-wilderness-review-debt"
description: "Имплементирует план wilderness-regions-review-debt: 7 находок ревью шагов 0–7 (кэш claim_owners, restore при пустом regions, контракт merge_rank vs declared, zero-score resolve, детерминизм _pick, BboxShape.area, DefaultWhenMissing). Шаг 3 — решение мастера. Новый чат: /impl-wilderness-review-debt."
---

# source-command-impl-wilderness-review-debt

Use this skill when the user asks to run the migrated source command `impl-wilderness-review-debt`.

## Command Template

# Имплементация: wilderness review debt — 7 находок ревью 0–7

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

**Важно — дерево движется.** План ревью написан по коммитам `38e1be37..470300d8` + дереву; с тех пор исполнялись шаги 7b/8/9/10 (в т.ч. 10b удалил `resolveForestPlains.py` — находка 5 может быть снята или переехала в `landcoverBackground.background_key_for_zone`). **Каждую находку сначала верифицируй на текущем коде**; снятую — отметь в плане, не «чинить» призрака.

## Прочитать до первой правки

1. [`.cursor/plans/wilderness-regions-review-debt.md`](../../../.cursor/plans/wilderness-regions-review-debt.md) — **единственный SoT**: 7 шагов с файлами/контрактами/проверками + «Вне scope» (не трогать: staging шага 8, `_pick`-рефакторинг, hydro дубль-проход, дубли лога, `isinstance`-guard — по желанию).
2. [`.cursor/plans/wilderness-regions-mechanic.md`](../../../.cursor/plans/wilderness-regions-mechanic.md) — §4/§5: контракты, на которые находки опираются (autoresolve детерминизм, precedence-цепочка, resolver «все отпали → WarningError»).
3. [`docs/tz_map_light_bake.md`](../../../docs/tz_map_light_bake.md) — § Регионы покрытия › Пересечения и приоритет, › Реестр и CoverageResolver; § Hybrid C (детерминизм).
4. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — **один шаг за заход**, отчёт → «ок»
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/contract-creation.mdc`](../../../.cursor/rules/contract-creation.mdc), [`.cursor/rules/type-kind-str-fields.mdc`](../../../.cursor/rules/type-kind-str-fields.mdc)
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Порядок шагов (из плана)

**1 → 2 → 4 → 5 (код, независимы); 3 — решение мастера; 6–7 — однострочные, в конец.**

| Шаг | Суть | Ключевые точки |
|---|---|---|
| 1 | `claim_owners` BFS — один раз на claim, не per-регион/тайл | `ClaimOwnersIndex` явным объектом (предпочтительно), не скрытый `@cache`; `masks/regionRasterizer.py`, `landcover/materializer.py`, `landcover/finePaint.py`; детерминизм `w` сохранить |
| 2 | `paint_regions_fine`: пустой `regions` → та же restore-ветка | убрать early return до `region_painted_parent → restore`; кейс: parent `region_uid` + collect `[]` → terrain в fallback; `landcover/finePaint.py`, `test_landcover_fine_paint` |
| 3 | **Контракт, не код:** `merge_rank` доминирует specificity — declared farmland проигрывает autoresolve | вариант (a) зафиксировать в ТЗ + warning-лог; вариант (b) declared-бонус в `_precedence_key` + ТЗ. **Решение мастера — спросить до правки** |
| 4 | `resolve()` zero-score argmax → `farmland` | `score > 0` обязателен; итог `None` → WarningError + тип не меняется (тот же путь «все отпали»); `regions/coverageResolver.py`, `test_coverage_resolver` |
| 5 | `_pick` → `next(iter(set))` недетерминирован | **проверить актуальность**: `resolveForestPlains.py` удалён 10b → логика в `landcoverBackground.background_key_for_zone`? Фикс: `min(terrain_set)`; два прогона с разным `PYTHONHASHSEED` → один ключ |
| 6 | `BboxShape.area()` `dx·dy` vs инклюзивный `contains` `(dx+1)(dy+1)` | bbox 1×1 area=0 всегда проигрывает tie-break; `dm/spatial/regionShape.py` — `(dx+1)(dy+1)` или зафиксировать «геометрическая» (решение с мастером) |
| 7 | `declared_regions` без `DefaultWhenMissing` | `dm/terrainMasks/worldTerrainMasks.py:138` — согласовать с `declared_mountains`; пустой список не сериализуется |

## Жёсткие запреты

- Один шаг за заход; не лить 7 находок одним коммитом.
- Не выходить за «Вне scope» список плана (staging шага 8, рефакторинг `_pick`, perf-дубли).
- Шаг 3 — **не кодить** до решения мастера (a/b); зафиксировать выбор в ТЗ.
- Шаг 5 — без рефакторинга legacy; минимальный фикс (или отметка «снято 10b»).
- Шаг 6 — если выбирается «геометрическая площадь» — записать в ТЗ, не менять код молча.
- Детерминизм не нарушать: кэш/restore/порядок не должны менять результат bake (проверки без изменений результата).
- Не трогать DAG-ноды, schema, не стартовать backend, не коммитить.
- Проверки из `backend/`; `compileall` + профильные unittest после каждого шага.

## Приёмка (из плана)

- Шаг 1: один `claim_owners` на claim за bake/refine; `test_region_rasterizer` + `test_landcover_materializer` + `test_landcover_fine_paint` зелёные без изменений результата.
- Шаг 2: новый кейс (parent `region_uid`, collect `[]` → terrain в fallback); регрессия 145.
- Шаг 3: контракт в ТЗ однозначен + код/лог по выбранному варианту.
- Шаг 4: `facts=None` → `resolve=None` + warning; argmax/tie-кейсы не меняются; farmland не возникает из пустых фактов.
- Шаг 5: два `PYTHONHASHSEED` → один ключ (или «снято 10b» — с отметкой).
- Шаг 6: bbox 1×1 не проигрывает по нулевой площади; precedence-кейсы не меняются.
- Шаг 7: `model_dump` канонического объекта без `declared_regions`; parse пустого → `[]`.
- Пометки «выполнен» в плане — после приёмки и «ок» мастера, по одному шагу.

## Старт

Прочитай план долга целиком, верифицируй каждую находку на текущем коде (особенно 5 — после 10b), спроси у мастера решение шага 3 (и 6, если неоднозначно), затем шаги 1→2→4→5 по одному.
