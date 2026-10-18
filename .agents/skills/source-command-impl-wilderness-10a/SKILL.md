---
name: "source-command-impl-wilderness-10a"
description: "Имплементирует шаг 10a плана wilderness-regions-mechanic: StateChangeConsumer — единый writer RegionState (facts → CoverageResolver → прогресс/гистерезис strength·elapsed/inertia → history[] → overrides); частичный переход → child-регион (sublocation, specificity родителя+1); morphEffects на materialize, не на read; elapsed_ticks — заглушка-параметр. Входы закрыты: 5a, 9a, 9b. Новый чат: /impl-wilderness-10a."
---

# source-command-impl-wilderness-10a

Use this skill when the user asks to run the migrated source command `impl-wilderness-10a`.

## Command Template

# Имплементация: wilderness-10a — `StateChangeConsumer`

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

**Блокер-условия (все):**
1. Шаг 5a — `CoverageResolver` (`resolve → TargetCoverage{target_key, strength}`), `RegionFacts`, fact consumers.
2. Шаги 9a/9b — `iRegionStateRepository` (writer) + `RegionState` POJO.
3. Шаг 3 — `inertia` на `TerrainRegistryEntry`, uid-формула.
Чего-то нет → стоп, доклад мастеру.

## Прочитать до первой правки

1. [`.cursor/plans/wilderness-regions-mechanic.md`](../../../.cursor/plans/wilderness-regions-mechanic.md) — **единственный SoT этой задачи**: §4 строка **10a** (цель/ТЗ/файлы/проверка); §5 **#11** — весь контракт состояния (typed facts, scorer, две гранулярности, морфинг не tombstone, прогресс с гистерезисом, child-регион частичного перехода, declaration как факт с весом, `elapsed_ticks`-заглушка с обязательным комментарием, история с привязкой к событию/времени позже), #8 (single-writer, tombstone/orphan, declared-edit правила). Не отклоняться.
2. [`docs/tz_map_light_bake.md`](../../../docs/tz_map_light_bake.md) — § Регионы покрытия › **Состояние и переходы** (consumer контракт, гибрид порогов: `inertia` на записи + `transition_threshold` в policy + `DeclarationFacts.strength` в effective inertia).
3. [`docs/tz_world_pack_storage.md`](../../../docs/tz_world_pack_storage.md) — § Region state store (single-writer — этот consumer), § Region state overlay (граница: эффекты домена — на materialize/refine, не read).
4. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок»
   - [`.cursor/rules/contract-creation.mdc`](../../../.cursor/rules/contract-creation.mdc) — `TerrainKey`/enum-типы (WR-TD-1)
   - [`.cursor/rules/type-kind-str-fields.mdc`](../../../.cursor/rules/type-kind-str-fields.mdc)
   - [`.cursor/rules/bulk-sql.mdc`](../../../.cursor/rules/bulk-sql.mdc) — массовая запись state только через `bulkSql`
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc) — `transition_threshold` в policy-POJO
   - [`.cursor/rules/layer-boundaries.mdc`](../../../.cursor/rules/layer-boundaries.mdc) — сервис состояния, не генератор и не persist-оркестратор
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc) — приёмка включает «ни один класс > 300 строк»

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Что уже есть — не переписывать

- `backend/app/application/worldData/regions/` — `CoverageResolver`, `RegionFacts`, `factConsumers` (5a); сюда `stateChange/` подпакет.
- `backend/app/dataModel/regions/regionState.py` (9b) — POJO с `history[]`, `tombstone`, `overrides`.
- `iRegionStateRepository` (9a) — единственный write-канал; bulk через `bulkSql`.
- `TerrainRegistryEntry.inertia` + `eligibility` (3); `transition_threshold` — новый policy-knob в `LandcoverRegionsCategoryPolicy`/world policy (transitional `default_*` — где живёт политика landcover; canonical default, не литерал).
- `CoverageResolver.resolve` — тот же интерфейс, что у autoresolve (контекст → покрытие); здесь на `RegionFacts` существующего региона.
- Merge/paint (`apply_terrain_footprint`, precedence) — эффекты перехода исполняются на bake/refine, consumer их не красит сам.
- Логирование `domain | event | key=value` — `region_state | transition | …`, `region_state | overlap_rerank_deferred | …`.

## Скоуп шага 10a — строго по плану §4

- `backend/app/application/worldData/regions/stateChange/`:
  - `consumer.py` — оркестрация: собрать `RegionFacts` через fact consumers → `CoverageResolver.resolve` → `progress`/`history`/`overrides` → запись через repo (single-writer). Не генератор, не bake, не persist-оркестратор — сервис состояния.
  - `progress.py` — накопление с гистерезисом: `target == current` → затухание; `target != current` → `pending_target = target`, `progress += strength·elapsed / inertia(current)`; смена `pending_target` → reset; `progress ≥ transition_threshold` → `current_type = target`, reset, history-запись + `region_state | transition` лог.
  - `history.py` — append-only `{from_type, to_type, cause, at}`; `at` — привязка ко времени позже (заглушка, комментарий); `cause` — typed enum (`RegionTransitionCause`: `drift` / `declared_edit` / `event` — по канонам, иначе предложить enum и записать в план).
  - `morphEffects.py` — морфинг (лес→озеро): `current_type` меняется, uid тот же; эффекты домена по роду ключа (вода → hydro role/bed carve по shape) — **очередь/сигнал на refine/materialize**, не здесь-красим; регион-эффект владеет доменом эффекта, не сущностью.
  - `elapsed_ticks: int` — **рабочий параметр-заглушка** (домен времени/LOD не реализован; явный комментарий «переработать при появлении домена времени/LOD» — требование из #11).
  - **Частичный переход** — child-регион (саблокация): пространственное распределение внутри региона (низины → болото) создаёт child со своим uid (seed/scope-подобный ключ), `parent_region_uid`, specificity родителя + 1 при равном ранге; родитель держит тип снаружи.
  - `DeclarationFacts.strength` → effective inertia (declared инертнее); declared-edit — по правилам #8 (shape-edit → reset progress, type-edit → reset к entry_type + history).
- Юнит-тесты по приёмке ниже.

- **Не в шаге 10a:** worldEdit вызовы (10c), overlay read (9c — уже есть), sweep/tick-триггер (eval — pure, триггер извне/на read; LOD-трек позже), полный `flora.*` канал.

## Жёсткие запреты

- Единый writer `region_states` — никаких записей состояния из bake/генераторов/routes (чтение свободно).
- Нет таблицы переходов A→B — только scorer `CoverageResolver`; промежуточных «dead_forest»-ключей нет.
- Нет `random`/своего рандома — детерминизм от фактов + seeded-инфраструктуры.
- `elapsed_ticks` — параметр с комментарием-заглушкой; мокать время в коде запрещено, тесты используют параметр.
- Не трогать DAG-ноды, schema (9a), не стартовать backend, не коммитить.
- Проверки запускать из `backend/`; не чинить окружение «заодно».

## Приёмка (из плана, строка 10a)

- `python -m compileall backend/app` — чисто; ни один класс > 300 строк.
- Юнит: дрейф лес→степь по `elapsed_ticks`-параметру (прогресс накапливается → порог → `current_type` меняется + history-запись); гистерезис — смена target до порога → reset, не «половина перехода»; сила `strength` влияет на темп.
- Частичный переход → child-регион с `parent_region_uid`, своим uid, specificity+1; родитель сохраняет тип.
- Declared-регион инертнее autoresolve при одинаковых фактах (`DeclarationFacts.strength`).
- `region_states` запись только через repo; bulk — `bulkSql`.
- Пометка «выполнен» в плане — только после приёмки и «ок» мастера.

## Старт

Прочитай план целиком, проверь блокеры, сверь поля `RegionState`/`RegionFacts` с реализованными моделями (могли уехать), покажи карту `stateChange/` (consumer/progress/history/morphEffects сигнатуры + точка вызова consumer'а — кто триггерит eval) до первой правки.
