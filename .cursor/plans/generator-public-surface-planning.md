# GEN-SURFACE-PLAN — публичный pipeline подготовки плана поверхности

**Навигационный граф разработки:** [WORLD-PLAN-GRAPH-1](./world-generation-plan-dependency-graph.md), §§1, 4, 5.1/5.2, 8 и 12. Для применимой GEN preparation-ноды сначала согласуется доменный public contract §7 (GEN-CONTRACTS), затем реализованный/проверенный метод передаётся в binding (GEN-PORTS); это не общий prerequisite всех GEN-нод. Нормативные I/O/E/ownership, статус и разрешение реализации остаются в этом owning-плане.

**Статус:** REQUIREMENTS / OPEN, 2026-11-02. По поручению пользователя фиксируются target interface/method names и отдельное требование реализации. Это не разрешение реализации или cutover, не расширение поведения существующих DAG-нод.

**Owning domain:** surface planning (`application/worldData/planning`). Интерфейс принадлежит этому домену, а не engine и не общему facade всех генераторов. Реализация использует существующие domain providers и PlanningService.

## 1. Фиксируемое имя и потребители

| Публичный интерфейс | Метод | Результат | Потребители |
|---|---|---|---|
| `ISurfacePlanningPipeline` | `prepare_surface_plan` | Согласованный immutable surface-plan bundle для captured inputs, с source/dependency evidence и diagnostics | Подготовка L0 light/full и L2 detailed, когда соответствующей операции нужен surface plan; exact DAG binding OPEN |

Target реализация — `SurfacePlanningPipeline`; публичный интерфейс `ISurfacePlanningPipeline`, метод `prepare_surface_plan`. Суффикс `Pipeline` явно обозначает доменную последовательность одной операции.

Имя интерфейса и метода — target требование. Сейчас этих символов в коде нет. Существующие `SurfacePlanningEntry`, `SurfacePlanningCapture`, `SurfacePlanningAssembler` — evidence и кандидаты внутренней реализации, а не интерфейсы для прямого импорта в engine.

Новая нода подготовки планов не назначается. Таблица не меняет I/O, callers/callees и родство `light_bake_initialization`, `full_bake_initialization`, `detailed_bake_initialization` или readers. Конкретный node → interface binding согласуется отдельно. Light readers не становятся потребителями preparation pipeline и не поставляют ему настройки.

## 2. Входная граница

Смысловой Input: world identity и immutable captured surface inputs с revision, extent/grid/topology, необходимыми climate/terrain/hydrology/relief settings, location anchors и template inputs. Execution wait/cancel policy передаётся отдельно от смысловых source inputs по существующему planning-контракту.

Reuse candidates: `SurfacePlanningView` / `ReadySurfacePlanningView`, `GeoSurfacePlanningView`, `PlanWaitControl`. Не создавать зеркальные POJO. Exact signature и способ внедрения execution control OPEN.

`SurfacePlanningCapture.capture` сейчас не выполняет I/O: преобразует уже переданные World/NamedLocation/template inputs и вычисляет revision fingerprint. Получение authoritative source данных и выбор публичной границы capture+prepare либо prepare(captured view) остаются отдельным contract-freeze вопросом. Не передавать SQL rows, repositories или concrete assembler в будущий node Input. Не объявлять capture общей нодой настроек мира.

## 3. Output и Definition of Done

Успешный результат подтверждает только подготовленный план поверхности:

1. Все обязательные планы принятого набора присутствуют; частичный bundle не выдаётся как success.
2. Планы относятся к одному world и согласованным extent/grid/topology; bundle привязан к captured revision.
3. Schema/algorithm versions и точные upstream dependency refs согласованы; изменение зависимости исключает reuse старого несовместимого результата.
4. Результат immutable и пригоден downstream; diagnostics не потеряны. Cache hit и compute дают одинаковые контрактные гарантии.
5. Операция не производит L0 tiles, climate pack artifacts, C23, L2 или C11 и не активирует публикацию мира. Запись planning cache допустима как внутренняя инфраструктура и не является world publication.

Reuse candidates: `SurfacePlanBundle`, `GeoSurfacePlanBundle`, `PlanEnvelope`, `PlanRef`, `PlanDiagnostic`. Выбор baseline/GEO target принадлежит owning GEO activation contract; pipeline не переключает их по усмотрению caller. Exact output/error types и files OPEN. `SurfaceWorkingMaps` — внутренняя вычислительная проекция; публичная выдача mutable working maps автоматически не разрешается.

## 4. Неуспех и freshness

- Invalid captured inputs, world/grid/topology/version/dependency mismatch и provider failure не выдают готовый bundle.
- `no_extent` — отдельный явный неготовый исход; текущий `None` не означает успешную подготовку. Exact typed outcome OPEN.
- Cancel, timeout и busy должны сохранять различимую семантику; не превращать их в отсутствие планов или success. Inventory reuse: `PlanContractFailure`, `PlanBuildFailure`, `PlanWaitCancelled`, `PlanWaitTimeout`, `PlanningBusy`.
- Принятие warning/degraded diagnostics требует явной доменной policy; exact mapping OPEN, существующие fallback не удаляются этим планом автоматически.
- Bundle доказывает согласованность captured inputs, а не неизменность live мира до commit. Freshness перед world publication проверяется publication owner отдельно.

## 5. Разрешённый внутренний pipeline

Подготовка climate/terrain/water/relief/hydrology/local-climate plans остаётся внутри одной публичной операции с единым результатом. Providers, их внутренняя последовательность, fingerprinting, cache и single-flight не переносятся в отдельные DAG-ноды только из-за числа стадий. GEO extension применяется только по принятому owning контракту.

Pipeline не принимает решений о выборе старта, missing light → full, запуске L0/L2/C23/C11, подготовке соседних публичных операций или world publication. Этим межоперационным flow управляет DAG по отдельно принятой карте.

## 6. AS-IS evidence

- [SurfacePlanningEntry](../../backend/app/application/worldData/planning/composition/surfacePlanningEntry.py) — capture/prepare entry и projection рабочих полей.
- [SurfacePlanningCapture](../../backend/app/application/worldData/planning/composition/surfacePlanningCapture.py) — исходная immutable проекция без I/O.
- [SurfacePlanningAssembler](../../backend/app/application/worldData/planning/composition/surfacePlanningAssembler.py) — baseline/GEO внутренняя композиция.
- [SurfacePlanBundle](../../backend/app/application/worldData/planning/contracts/surfacePlanBundle.py) — результат и coherence validation.
- [PlanningService](../../backend/app/application/planning/service/planningService.py) — versioned get-or-build, validation, cache и execution control.

## 7. Реализация в owning domain — отдельный срез GEN-PLAN-1

- [ ] Принять публичную capture/preparation границу и authoritative source acquisition contract.
- [ ] Выбрать baseline/GEO variant по owning activation contract; согласовать полный Input/Output/Error и diagnostics/no-extent/cancel semantics с reuse inventory.
- [ ] Предъявить domain-owned interface/implementation/adapters/DI file и import map, folder counts. Не создавать engine-owned дубли.
- [ ] После отдельного разрешения реализовать `ISurfacePlanningPipeline.prepare_surface_plan` поверх принятого domain pipeline.
- [ ] Проверить coherent output, exact dependency refs, cache-hit equivalence, source-change invalidation, wrong world/grid/version, no extent, provider failure, cancel/timeout; отсутствие world writes и запуска соседних операций.
- [ ] Принять domain implementation; отдельно согласовать concrete consumer bindings. Не переводить автоматически debug/production callers и не менять родство.

Долг: [GEN-PLAN-1](../../docs/tz_generator_technical_debt.md#gen-plan-1). Реестр: [generator_public_method](./generator_public_method.md). Owning DAG-план: [GEN-DAG-1](./gen-dag-1-post-geo-ws.md).

## 8. Декомпозиция существующих оркестраторов — граница DAG / Pipeline

**Точная формулировка пользователя:** упрощение — декомпозиция оркестратора в линейные pipeline, где оркестратор находится в DAG. Не сохранять генераторную оркестрацию под новым именем. Публичные domain interfaces/implementations имеют суффикс Pipeline.

| Существующий компонент | Что требуется разобрать / выделить | Судьба оркестрации |
|---|---|---|
| `WorldSurfaceMaterializationOrchestrator` | Разделить управление light/full/detailed и последовательностями L0/C23, L2/C11 от domain compute pipelines | Межоперационное управление переносится в DAG; прежняя orchestration-обёртка под удаление после принятой замены/cutover |
| `PackMaterializationOrchestrator` | Разделить surface planning, climate, L0, фоновые jobs и publication; линейные domain pipeline должны иметь отдельные принятые результаты | Управление самостоятельными операциями переносится в DAG; старый composite pipeline не оборачивается целиком новым интерфейсом |
| `PackDetailedBakeOrchestrator` | Выделить линейные вычислительные pipeline для принятых detail-операций; отделить самостоятельные climate/grade effects. Exact decomposition OPEN | Оркестрация отдельных операций принадлежит DAG; кандидат внутреннего refine pipeline не считается принятым без I/O/Error/DoD |
| `WorldMapBakeOrchestrator` | Кандидат декомпозиции в линейный L0 compose/preparation Pipeline; отделить effects и получить staged result. Exact interface/method name OPEN | Внутренние contributors/растеризация могут остаться стадиями одной операции; межоперационные решения не остаются в генераторе |
| `SurfacePlanningAssembler` / `SurfacePlanningEntry` | Согласованная внутренняя подготовка единого bundle оформляется как `SurfacePlanningPipeline` за `ISurfacePlanningPipeline.prepare_surface_plan`; capture boundary остаётся OPEN | Providers/cache/внутренние зависимости обслуживают одну операцию; управление этим pipeline вместе с соседними публичными операциями находится в DAG |

Карта отмечает направление декомпозиции, а не принимает exact срезы всех перечисленных классов. Для ещё не разобранных pipeline имена/методы/I/O/Error/DoD фиксируются отдельно. «Сохранить оркестратор» не является исходом; сохраняться могут вычисления внутри принятого линейного pipeline. Никакие DAG-ноды, родство или production callers этой картой не меняются.

## Подоменные разборы

- [LIGHT-RELIEF — классы рельефа, подтверждённые вызовы и границы pipeline](./generator-light-relief-classes.md). Статический аудит; runtime execution не подтверждается этим документом.

- [LIGHT-RELIEF-REVIEW — отдельная ревизия рельефа light_bake](./generator-light-relief-review.md). Подтверждённые расхождения AS-IS/target и незакрытые вопросы.
