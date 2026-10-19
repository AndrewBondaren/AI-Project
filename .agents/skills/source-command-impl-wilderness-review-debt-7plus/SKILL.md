---
name: "source-command-impl-wilderness-review-debt-7plus"
description: "Имплементирует план wilderness-regions-review-debt-7plus: 4 шага ревью шагов 7+ (parity degraded identity preview/runtime, drift-таргеты consumer'а — zero-score + фильтрация кандидатов, мёртвый index_hydrology, region_states в WP-DELETE-1). Шаг 2b — решение мастера. Новый чат: /impl-wilderness-review-debt-7plus."
---

# source-command-impl-wilderness-review-debt-7plus

Use this skill when the user asks to run the migrated source command `impl-wilderness-review-debt-7plus`.

## Command Template

# Имплементация: wilderness review debt 7+ — 4 шага

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

**Важно — дерево движется.** План ревью написан по состоянию после шагов 10c. **Каждую находку сначала верифицируй на текущем коде**; снятую — отметь в плане, не «чинить» призрака.

## Прочитать до первой правки

1. [`.cursor/plans/wilderness-regions-review-debt-7plus.md`](../../../.cursor/plans/wilderness-regions-review-debt-7plus.md) — **единственный SoT**: 4 шага + решения мастера + TODO-записи T-1..T-6. Вне scope шагов: T-1..T-6 — **не кодить** (это заметки к будущим контрактам, не работа этого чата).
2. [`.cursor/plans/wilderness-regions-review-debt.md`](../../../.cursor/plans/wilderness-regions-review-debt.md) — долг 0–7; находка №4 (zero-score argmax) там **пересекается с шагом 2a** — фикс один, общий.
3. [`.cursor/plans/wilderness-regions-mechanic.md`](../../../.cursor/plans/wilderness-regions-mechanic.md) — §4/§5: контракты (5a «все отпали → WarningError», 10b «entry без eligibility не выбирается с нулевым score», приёмка 10c «одинаковое решение в обоих режимах»).
4. [`docs/tz_json_validation.md`](../../../docs/tz_json_validation.md) — ResolveContext/report; [`docs/tz_map_light_bake.md`](../../../docs/tz_map_light_bake.md) — § Реестр и CoverageResolver; [`docs/tz_generator_technical_debt.md`](../../../docs/tz_generator_technical_debt.md) — § WP-DELETE-1 (шаг 4 — док-правка).
5. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — **один шаг за заход**, отчёт → «ок»
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/contract-creation.mdc`](../../../.cursor/rules/contract-creation.mdc), [`.cursor/rules/type-kind-str-fields.mdc`](../../../.cursor/rules/type-kind-str-fields.mdc)
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить, schema = только `0001`
   - [`.cursor/rules/bulk-sql.mdc`](../../../.cursor/rules/bulk-sql.mdc) — если новых bulk-записей не будет, правило только на сверку

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Решения мастера, уже принятые (не переспрашивать)

- **child_uid = `parent_region_uid + seed_xy`** — валидный отдельный источник identity (коллизия overlapping-родителей реальна). Код 10a менять **не** надо. Остаток — T-1/T-2 (TODO-записи, не код этого чата).
- **Проекция hills/eligibility — только при инициализации** — поведение по дизайну; статус идемпотентности — T-3 мастера, не трогать.
- **`cleanup_orphans` — пока рано** (T-4); **`World.seed`** — отдельный трек (T-5).

## Порядок шагов (из плана)

**1 → 2 → 3 → 4.** 2b — после решения мастера по составу таргетов.

| Шаг | Суть | Ключевые точки |
|---|---|---|
| 1 | `validate_declared_regions` роняет `REGION_DEGRADED_IDENTITY` в validate_only | `local` → `ctx.child(index)`; issue в `ctx.report` при preview + WarningError при runtime — **одинаковое решение**; severity-классификация issue vs error и фильтрация перед `ImportValidationError` — согласовать с мастером до правки `prepare_import`; `jsonValidation/declaredRegions.py`, `resolve.py` |
| 2a | `resolve()` zero-score argmax → пишет `pending_target` в `region_states` | `score > 0` обязателен; `None` → WarningError + тип не меняется (путь «все отпали»); **общий фикс с долгом #4 из review-debt 0–7**; `regions/coverageResolver.py`, `test_coverage_resolver` |
| 2b | Consumer берёт полный реестр мира → disabled/`autoresolve=false`/не-eligibility ключи — дрейф-таргеты | **Решение мастера — спросить до правки:** `coverage_registry`-фильтр / только `enabled` / осознанный полный реестр. Внимание: `liquid_body` без eligibility — таргет morph-в-воду через `morph_hydrology_role`; фильтр «только eligibility» его отрежет — вариант решения зафиксировать в ТЗ; `regions/stateChange/consumer.py`, `coverageBackground.py` |
| 3 | `index_hydrology` — мёртвый прогон на каждый `collect` | `hydrology_entries` не вычисляется; модуль удаляется целиком либо вызов за явный запрос — по решению мастера; `landcover/materializer.py`, `landcover/hydrologyIndex.py` |
| 4 | `region_states` FK без `ON DELETE CASCADE` → delete мира = IntegrityError | **Только док-правка:** дописать `region_states` в перечень WP-DELETE-1 (`docs/tz_generator_technical_debt.md`); код/schema не менять |

## Жёсткие запреты

- Один шаг за заход; не лить 4 шага одним заходом.
- **T-1..T-6 — не кодить** (child-uid reachability, маркер идемпотентности реестра, cleanup-политика, `World.seed` — контракты будущих шагов).
- Шаг 2b — **не кодить** до решения мастера по составу таргетов; выбор зафиксировать в ТЗ.
- Шаг 4 — **только `docs/tz_generator_technical_debt.md`**; DDL/модели/код не трогать (общий фикс — WP-DELETE-1).
- Детерминизм не нарушать: фиксы не должны менять результат bake/collect при валидных входах.
- Не трогать DAG-ноды, schema (`0001` — только если явно попросит мастер), не стартовать backend, не коммитить.
- Не рефакторить consumer/resolver за пределами минимального фикса.
- Проверки из `backend/`; `compileall` + `git diff --check` + профильные unittest после каждого шага.

## Приёмка (из плана)

- Шаг 1: `POST /worlds/{uid}/regions?validate_only=true` безымянный → issue в `ImportValidationReport`; runtime → WarningError + degraded uid без reject; коллизия имён — по-прежнему reject.
- Шаг 2a: `facts=None` → `resolve=None` + warning; `evaluate` на пустых фактах не пишет `pending_target`; argmax/tie-кейсы на score>0 не меняются.
- Шаг 2b: disabled-ключ не становится таргетом (по выбранному варианту); morph-таргеты сохранены; решение записано в ТЗ.
- Шаг 3: collect/materialize/outline поведение идентично; `hydrology_entries` не вычисляется; профильные тесты зелёные.
- Шаг 4: `region_states` упомянута в WP-DELETE-1; дифф — только ТЗ.
- Пометки «выполнен» в плане — после приёмки и «ок» мастера, по одному шагу.

## Старт

Прочитай `wilderness-regions-review-debt-7plus.md` целиком, верифицируй 4 находки на текущем коде, спроси у мастера решения по шагам 1 (severity-классификация) и 2b (состав таргетов), затем шаги по одному.
