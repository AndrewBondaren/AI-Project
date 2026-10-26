---
name: "source-command-impl-cascade-materials"
description: "Имплементирует M9–M10 плана cascade-migration: wall_material/floor_material (NL parent_* каналы, or-цепочки структуры) и dominant_material (первая проверка Cascade.fold). M1–M8 закрыты. Новый чат: /impl-cascade-materials."
---

# source-command-impl-cascade-materials

Use this skill when the user asks to run the migrated source command `impl-cascade-materials`.

## Command Template

# Имплементация: каскад M9–M10 — материалы

Это **явная просьба писать код** (шаги плана). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/cascade-migration-done.md`](../plans/cascade-migration-done.md) — **единственный SoT по шагам**: форма шага параметра, M9, M10, проверки. Не отклоняться.
2. [`.cursor/plans/cascade-params-matrix.md`](../plans/cascade-params-matrix.md) — сверочная матрица параметров.
3. [`docs/tz_cascade_context.md`](../../docs/tz_cascade_context.md) — §4 (движок/`extend`), §6 (stamp на NL), §7 (потребители; **решает grouped vs два Cascade в M9**), §8 (кейсы).
4. [`docs/tz_economic_tier.md`](../../docs/tz_economic_tier.md) §4 (каскад), §9 (поля).
5. [`structure-wall-materials-done`](../plans/structure-wall-materials-done.md) — классификация/политика материалов (закрыт; здесь только проводка через каскад).
6. Кодовое состояние после M1–M8 (не писать заново):
   - `backend/app/dataModel/cascade/` — `cascadeSpec`, `cascadeGraph`, `cascadeVerify` (generic; `Cascade.levels` поддержан — subset-параметры работают);
   - `backend/app/dataModel/locations/context/` — `scopeLevel`, `cascadeParams` (`ECONOMIC_TIER`, `CITY_SIZE`, `SETTLEMENT_DENSITY`), `locationContext` (поля: `economic_tier`, `system_city_size`, `settlement_density`);
   - `backend/app/application/worldData/context/` — `cascadeLink`, `contextResolver` (`extend`, `_resolve_default` per-param), `locationScope` (scope factories + `empty_location_chain`/`debug_building_context`);
   - тесты: `test_context_extend.py`, `test_location_context_contract.py`, `test_cascade_migration_m2.py`, `test_cascade_context_baseline.py`.
7. Правила (нарушение = стоп):
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../rules/dataModel-no-hardcode.mdc) — default через политику реестра/POJO, не литерал в консьюмере;
   - [`.cursor/rules/layer-boundaries.mdc`](../rules/layer-boundaries.mdc)
   - [`.cursor/rules/code-gates.mdc`](../rules/code-gates.mdc) — один шаг за заход;
   - [`.cursor/rules/project-context.mdc`](../rules/project-context.mdc) — не DAG, не коммитить, schema = только `0001`;
   - [`.cursor/rules/class-size-limit.mdc`](../rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Состояние после M1–M8 (сверить с кодом, не с памятью)

- `LocationContext.extend()` — единственный путь параметра к консьюмерам; `TierResolver`/`building_band` удалены (acceptance grep пуст).
- Паттерн каналов: `CascadeChannel(param, level, above/below=CascadeLink(model, field, level))` в `Annotated`; каждое ребро объявлено **один раз** на стороне без import-цикла; verifier материализует обратную сторону. Глубокий scope = top цепи = резолвится первым.
- Паттерн resolved-stamp: `city_skeleton_from_settlement(settlement, *, economic_tier, settlement_density)` — runtime skeleton несёт effective значения; `settlement_skeleton_pojo` — authored-каналы.
- Default-политики: `REGISTRY_MEDIAN` (tier, warning), `CANONICAL_DEFAULT` (size→`WorldSettlementSizeRegistry.default_system_size()`, density→`DistrictDensity.default()`; silent).
- Pre-existing падения backend-сьюта (не чинить, не путать с регрессиями): `Plot 'farm'` ×2 в `test_settlement_topology`, hydrology ×4, building_purpose/plot_layout, bootstrap map-cell writers, schema drift `system_grade_uid`. Baseline ~1314 тестов, 5F/23E.

## Цель

### M9 — `wall_material` / `floor_material`

- `NL.parent_wall_material`/`parent_floor_material` (надёжные каналы — parent = верхний scope) и or-цепочки структуры → `ctx.wall_material`/`ctx.floor_material`.
- Точки: `foundationBuilder.py:65`, `roofBuilder.py:41`, `connect_corridors` (`parent_wall_material or DEFAULT`), room-resolved материалы.
- Решить по tz §7: два `Cascade` или один grouped.
- `default` — политика материального реестра, не литерал.

### M10 — `dominant_material`

- `resolve_dominant_material` (`planner/dominantMaterial.py`) → каскад.
- Fallback «из районов»/«по tier» — derived/fold-логика: **первая проверка `Cascade.fold`**; если fold не нужен — authored-цепочка + domain-default. Решение зафиксировать в отчёте.

## Жёсткие запреты

- Обход движка запрещён: локальные `or`-цепочки, ручное наследование, свой fallback в консьюмере — баг. Новая точка наследования — новый канал/звено.
- Не новые authored-поля, wire-ключи, schema-изменения. Не `0002_*.sql`.
- Не DAG `application/engine/nodes/`. Не стартовать backend. Не коммитить.
- Материальная классификация/политика — план `structure-wall-materials-done` (закрыт); здесь только каскад-проводка.
- Не менять фильтрацию `planner/economic.py`.

## Порядок

M9 → M10, каждый по общей форме шага параметра (`Cascade` + каналы + поле контекста + привязки + потребители + тесты). Один шаг за заход — без исключений.

**Правило мастера:** каждое сообщение мастера после отчёта = приступать к следующему шагу, **если** в нём нет фидбека по ревью кода. Фидбек — сначала обработать, шаг не начинать.

После каждого шага: что сделано / файлы / проверки (чем прогнал) / что осталось / что сознательно не тронуто.

## Приёмка

- Focused-тесты затронутых сьютов + `test_context_extend`/`test_location_context_contract` зелёные.
- Полный backend-съют: падений ровно столько же, сколько pre-existing baseline (список выше) — новых нет.
- `compileall` изменённых модулей, `git diff --check` после каждого шага.
- M9 Done: `or parent_*` цепочки удалены; материалы стены/пола — ctx.
- M10 Done: решение по `Cascade.fold` зафиксировано; or-resolution удалён.

## Старт

Прочитай `cascade-migration-done.md` целиком + точки M9 из инвентаря. Затем шаг M9.
