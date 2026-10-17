---
name: "source-command-impl-wilderness-5a"
description: "Имплементирует шаг 5a плана wilderness-regions-mechanic: CoverageResolver (scorer по EligibilityRule: required-отсев, score=Σw·satisfaction, argmax, все отпали → WarningError) + typed RegionFacts + реестр factConsumers (climate/hydrology/relief; flora→None); interim eligibility в canonical registry. Входы закрыты: 2, 3 (EligibilityRule). Новый чат: /impl-wilderness-5a."
---

# source-command-impl-wilderness-5a

Use this skill when the user asks to run the migrated source command `impl-wilderness-5a`.

## Command Template

# Имплементация: wilderness-5a — `CoverageResolver` + fact consumers

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

**Блокер-условие:** шаг 3 закрыт — `TerrainRegistryEntry.eligibility: list[EligibilityRule]` существует (тип правила, builtin-правила в `canonical_defaults()`). Нет → стоп, доклад мастеру.

## Прочитать до первой правки

1. [`.cursor/plans/wilderness-regions-mechanic.md`](../../../.cursor/plans/wilderness-regions-mechanic.md) — **единственный SoT этой задачи**: §4 строка **5a** (цель/ТЗ/файлы/проверка); §5 **#11** — механика scorer'а в деталях (typed facts, две гранулярности, `strength`, «все отпали → WarningError, тип не меняется»), #9 (interim climate, flora → `None` как канал), #4 (вид seed'а = `CoverageResolver` на контексте seed — тот же интерфейс). Не отклоняться.
2. [`docs/tz_map_light_bake.md`](../../../docs/tz_map_light_bake.md) — § Регионы покрытия › **Реестр и CoverageResolver** (`EligibilityRule` контракт, scorer, interim-комментарий), › Declaration и suitability (A∧B только autoresolve — канал `flora.*` в eligibility).
3. [`docs/tz_flora.md`](../../../docs/tz_flora.md) — FL3b/FL3c (suitability index, veto для autoresolve): почему `flora` consumer сейчас `None`, и что станет факт-каналом позже.
4. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок»
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc) — interim-правила в `canonical_defaults()` реестра, не в коде resolver'а
   - [`.cursor/rules/layer-boundaries.mdc`](../../../.cursor/rules/layer-boundaries.mdc)
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Что уже есть — не переписывать

- `backend/app/application/worldData/` — `surfaceTerrainContext.py` / `SurfaceTerrainContext`: climate/relief/hydrology факты собираются до terrain materialization — fact consumers читают его, не ходят в домены напрямую.
- `backend/app/dataModel/terrain/terrainRegistryEntry.py` — `EligibilityRule{fact, op: gte|lte|in_range|flag, lo/hi, weight, required}` + `inertia` (шаг 3, вход).
- `wd/masks/resolveForestPlains.py` — текущая per-cell climate-логика (`forest_min_rainfall` и т.п.) — **источник interim-правил**: переносятся в `canonical_defaults()` `eligibility` builtin-ключей, сама функция живёт до шага 10b.
- Реестр-паттерн: `factConsumers/` по образцу domain contributors/`MaskDomainMaterializer`-реестра — домен регистрирует `contribute(region/scope) -> XxxFacts`.
- Диагностика: `FieldPathError`/`log_issues`, `logger.warning` `domain | event | key=value`.

## Скоуп шага 5a — строго по плану §4

- `backend/app/application/worldData/regions/` — новый пакет:
  - `regionFacts.py` — typed POJO: `RegionFacts{climate: ClimateFacts|None, hydrology: HydroFacts|None, relief: ReliefFacts|None, flora: FloraFacts|None (=None — комментарий «канал flora.* ожидает flora-трек, tz_flora FL3b»), declaration: DeclarationFacts|None, elapsed_ticks: int}`. Per-domain facts — typed поля (rainfall_mean, drought_trend, water_table, flooding, elevation_plain, lowland_fraction…) — каноны фактов, на которые ссылаются `EligibilityRule.fact` (`"climate.rainfall"` и т.п.).
  - `factConsumers/{climate,hydrology,relief}.py` + реестр: каждый — `contribute(context) -> XxxFacts | None`; отсутствующий домен → `None`, resolver переживает.
  - `coverageResolver.py` — `resolve(region_facts, registry) -> TargetCoverage{target_key, strength}`:
    - `required` правило провалено → кандидат отпадает;
    - `score = Σ weightᵢ·satisfactionᵢ`, satisfaction 0..1 (`in_range` — доля/плавный falloff от границ, `gte`/`lte` — нормированное превышение порога, `flag` — 0/1);
    - `target = argmax(score)`; `strength = score / score_max`;
    - **все отпали → WarningError (`landcover | resolve_unresolved | …`), тип не меняется — без default;**
    - фактов нет по каналу, на который ссылается правило → правило satisfaction=0 (не ошибка; `required` по отсутствующему каналу = отсев).
  - **Две гранулярности**: тот же `resolve` вызывается на агрегате региона (region-level) и на клеточном/подконтексте (cell-level) — сигнатура не различает; агрегация фактов — работа collect/consumers, не resolver.
- **Interim eligibility**: climate-правила (`forest_min_rainfall` и др.) переносятся из `resolveForestPlains` в `canonical_defaults()` `eligibility` builtin-ключей с **обязательным комментарием** «interim; цель — rules мира + flora suitability (`flora.*` канал)». `resolveForestPlains` сам не удаляется (10b).
- Юнит-тесты по приёмке ниже.

- **Не в шаге 5a:** вызов resolver'а из autoresolve/materializer (5b), применение к `RegionState`/прогресс/гистерезис (10a), `DeclarationFacts.strength` в effective inertia (10a), удаление `resolveForestPlains` (10b). Только resolver + facts + реестр consumers.

## Жёсткие запреты

- Resolver чистый: факты + реестр на входе, результат на выходе; нет I/O, нет чтения мира напрямую (это делает fact consumer), нет рандома.
- Нет таблицы переходов A→B ни в коде, ни в данных — выбор только скорингом.
- `flora` consumer не реализуется — регистрация отсутствует, поле `flora: None` с комментарием-заглушкой.
- Домены не назначают тип: fact consumer отдаёт факты, resolver решает.
- Не трогать DAG-ноды, schema, не стартовать backend, не коммитить.
- Проверки запускать из `backend/`; не чинить окружение «заодно».

## Приёмка (из плана, строка 5a)

- `python -m compileall backend/app` — чисто.
- Юнит: `required`-отсев убирает кандидата; `argmax` при равных весах; все кандидаты отпали → WarningError в логе + тип без изменений (нет silent default); одинаковые факты → одинаковый `target` при любой перестановке кандидатов реестра.
- Interim: builtin `forest` требует `climate.rainfall` порога (как `forest_min_rainfall` до переноса) — autoresolve-контекст arid → forest отсекается.
- Канал `flora.*` в правиле при `flora=None` → satisfaction 0, не падение.
- Пометка «выполнен» в плане — только после приёмки и «ок» мастера.

## Старт

Прочитай план целиком, проверь блокер (`EligibilityRule` на записи реестра), сверь факт-каноны с `SurfaceTerrainContext` (какие поля реально доступны — rainfall/water_table/elevation_plain), покажи сигнатуры `RegionFacts`, `contribute`, `resolve` и список interim-правил до первой правки.
