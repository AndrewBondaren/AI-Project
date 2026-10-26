---
name: "source-command-impl-wilderness-review-debt-7plus"
description: "Имплементирует план wilderness-regions-review-debt-7plus: 5 шагов ревью шагов 7+ (degraded identity по validate_only, фильтр кандидатов state-change через coverage_registry, water_body_uid на гидро-клетках с иерархией declared>region>auto, удаление index_hydrology, region_states в WP-DELETE-1). Все решения мастера приняты. Новый чат: /impl-wilderness-review-debt-7plus."
---

# source-command-impl-wilderness-review-debt-7plus

Use this skill when the user asks to run the migrated source command `impl-wilderness-review-debt-7plus`.

## Command Template

# Имплементация: wilderness review debt 7+ — 5 шагов

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

**Важно — дерево движется.** План ревью писался после шагов 10c; долг 0–7 с тех пор полностью закрыт, zero-score (2a) уже в коде. **Каждую находку сначала верифицируй на текущем коде**; снятую — отметь в плане, не «чинить» призрака.

## Прочитать до первой правки

1. [`.cursor/plans/wilderness-regions-review-debt-7plus.md`](../../../.cursor/plans/wilderness-regions-review-debt-7plus.md) — **единственный SoT**: 5 шагов с файлами/контрактами/проверками + решения мастера + TODO-записи T-1..T-6. T-1..T-5 — **не кодить** (контракты будущих треков); T-6 — маркер «долг 0–7 закрыт».
2. [`.cursor/plans/wilderness-regions-mechanic.md`](../../../.cursor/plans/wilderness-regions-mechanic.md) — §4/§5: контракты (5a «все отпали → WarningError», 10b «entry без eligibility не выбирается с нулевым score», приёмка 10c «одинаковое решение в обоих режимах», morph `parent+seed_xy`).
3. [`docs/tz_json_validation.md`](../../../docs/tz_json_validation.md) — ResolveContext/report (шаг 1); [`docs/tz_map_light_bake.md`](../../../docs/tz_map_light_bake.md) — § Реестр и CoverageResolver (шаг 2); [`docs/tz_terrain_hydrology.md`](../../../docs/tz_terrain_hydrology.md) — § C2 wire-форма `map_cells.hydrology` (шаг 3 — дописать поле); [`docs/tz_generator_technical_debt.md`](../../../docs/tz_generator_technical_debt.md) — § WP-DELETE-1 (шаг 5 — док-правка).
4. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — **один шаг за заход**, отчёт → «ок»
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/contract-creation.mdc`](../../../.cursor/rules/contract-creation.mdc), [`.cursor/rules/type-kind-str-fields.mdc`](../../../.cursor/rules/type-kind-str-fields.mdc)
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить, schema = только `0001`
   - [`.cursor/rules/bulk-sql.mdc`](../../../.cursor/rules/bulk-sql.mdc) — если новых bulk-записей не будет, правило только на сверку
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Решения мастера, уже принятые (не переспрашивать)

- **`REGION_DEGRADED_IDENTITY` — severity по режиму:** validate_only → ошибка в отчёте (`ctx.errors` → `ImportValidationError` → preview `valid=false`); runtime/apply → WarningError в логе, degraded uid без reject. Ветка по `ctx.validate_only` в producer'е; severity-флаг и канал warnings **не нужны**, `prepare_import` и wire-форма не меняются.
- **Состав кандидатов state-change = autoresolve-фильтр:** consumer передаёт в `resolve` `coverage_registry(..., autoresolve=True)` — тот же фильтр, что L0 autoresolve. Morph-таргеты проходят тот же eligibility-scoring; ключ без `eligibility` не выбирается автоматикой.
- **Hydro identity = `water_body_uid`, иерархия:** declared → `location_uid` (durable); event/morph → `region_uid` (durable); procedural autoresolve → `auto-{role}-{anchor}` (позиционная, **не durable** — persist/`region_states` на неё не опираются). `auto-*` только внутри policy-enabled autoresolve-веток. События (morph→lake) и климат — разные треки; ни один не минтует `auto-*`.
- **child_uid = `parent_region_uid + seed_xy`** — принято (T-1/T-2, не код этого чата). **Проекция hills/eligibility — только при инициализации** (T-3). **`cleanup_orphans` — пока рано** (T-4). **`World.seed`** — отдельный трек (T-5).

## Порядок шагов (из плана)

**1 → 2 → 3 → 4 → 5.** 1 и 2 major независимы; 4 независим от 3.

| Шаг | Суть | Ключевые точки |
|---|---|---|
| 1 | `REGION_DEGRADED_IDENTITY` теряется в validate_only (local ctx со свежим report) | `local` → `regions_ctx.child(index)` (шарит report/mode/schema_id; чинит drift `mode=runtime`); в `declared_region_identity` при `spec.name is None`: `validate_only=True` → `report_issues`, `False` → `log_issues`; `REGION_UID_CONFLICT` — reject в обоих режимах; `jsonValidation/declaredRegions.py`, `masks/regionIdentity.py`, JV/region тесты |
| 2 | Consumer берёт полный реестр → disabled/`autoresolve=false` ключи — дрейф-таргеты | 2a уже в коде (`coverageResolver.py:70-76` — верифицировать, не дублировать); 2b: в `_advance` передать `coverage_registry(self._registry, self._policy, autoresolve=True)`, сырой реестр для `_require_key`/inertia; фикстуры morph-кейсов получают `eligibility`; строка в ТЗ «morph-таргеты проходят тот же scoring»; `regions/stateChange/consumer.py`, `coverageBackground.py`, `test_coverage_resolver.py`, `test_region_state_change.py` |
| 3 | `water_body_uid` на гидро-клетках — identity L0→L2 | `MapCellHydrology.water_body_uid: str | None` (`DefaultWhenMissing`, `exclude_none`, в т.ч. `.shore()`); стамп при carve во **всех** точках: `lakeBasinGenerator.carve_lake_interior` (declared `spec.location_uid` / autoresolve `auto-lake-{gx}x{gy}` из feature center), `deepeningBandCarver` + `seaBasinGenerator` (uid coastline), `oceanBasinGenerator` (**наследует** uid relabeled-моря, не минтует новый), `proceduralSeaAutoresolve` (`auto-sea-{min_cell}`, один flood = одно тело), `riverBedCarver` (declared `segment.location_uid` / auto-river по source), `fineHydrologyIndex` (fine-carve — то же); coastline: `declared_coastline_segments` flat → per-coastline spec с `location_uid` (паттерн `LakeSpec`); declared без `location_uid` → fallback `auto-*` (поле не-None на любой carve-клетке); shore/deepening-клетки несут uid тела; `connection_edge_uid` сохраняется; **light wire не трогать**; `tz_terrain_hydrology.md` § C2 дописать поле |
| 4 | Удалить `index_hydrology`/`hydrology_entries` | `materializer.py` поле + reset + вызов; удалить `landcover/hydrologyIndex.py`; секция в `test_landcover_materializer.py` (прямой вызов) |
| 5 | `region_states` FK без CASCADE → delete мира = IntegrityError | **Только док-правка:** дописать `region_states` в перечень WP-DELETE-1 (`docs/tz_generator_technical_debt.md`); код/schema не менять |

## Жёсткие запреты

- Один шаг за заход; не лить 5 шагов одним заходом.
- **T-1..T-5 — не кодить** (morph-materialize reachability, маркер идемпотентности реестра, cleanup-политика, `World.seed`).
- `auto-*` — только внутри policy-enabled autoresolve-веток; не придумывать uid вне carve-точек; не persist'ить auto-uid как durable-ссылку.
- Light wire (`WorldMapCellWire.hydrology_role`/`width`) — без uid; corridor-путь — отдельный шаг, если понадобится.
- Шаг 5 — **только `docs/tz_generator_technical_debt.md`**; DDL/модели/код не трогать.
- Детерминизм не нарушать: uid — чистая функция детерминированных якорей (feature center / source / min-cell), не порядок итерации и не loop index.
- Не трогать DAG-ноды, schema (`0001` — только если явно попросит мастер), не стартовать backend, не коммитить.
- Не рефакторить consumer/resolver/hydrology за пределами контракта шага.
- Проверки из `backend/`; `compileall app` + `git diff --check` + профильные unittest после каждого шага.

## Приёмка (из плана)

- Шаг 1: `POST /worlds/{uid}/regions?validate_only=true` безымянный → `REGION_DEGRADED_IDENTITY` в `ImportValidationReport`, `valid=false`; apply → WarningError + degraded uid без reject; коллизия имён — reject в обоих режимах.
- Шаг 2: disabled-ключ не становится таргетом; `zero_score`-warning содержит только eligibility-кандидатов; morph-фикстуры с `eligibility` проходят; hysteresis/transition кейсы без изменений.
- Шаг 3: юнит — declared lake → клетки `location_uid`; autoresolve lake → `auto-lake-*`; река → `location_uid` + `connection_edge_uid`; ocean relabel → uid моря; persist wire содержит поле; **два прогона → те же uid**.
- Шаг 4: collect/materialize/outline идентично; `hydrology_entries` не вычисляется; профильные тесты зелёные.
- Шаг 5: `region_states` в WP-DELETE-1; дифф — только ТЗ.
- Пометки «выполнен» в плане — после приёмки и «ок» мастера, по одному шагу.

## Старт

Прочитай `wilderness-regions-review-debt-7plus.md` целиком, верифицируй находки на текущем коде (2a — подтверди `coverageResolver.py:70-76` и отметь «уже в коде»), затем шаги 1→2→3→4→5 по одному с отчётом после каждого.
