# LIGHT-RELIEF — классы, вызовы и границы pipeline

Поддокумент [GEN-SURFACE-PLAN](./generator-public-surface-planning.md). Срез: рельеф в light_bake. Проверено 2026-11-02.

**Статус:** статический аудит AS-IS и предложения для совместного разбора. Прямые вызовы, DI и registry dispatch проверены по коду. Runtime trace, запуск bake и функциональные проверки не выполнялись. Target interfaces, новые ноды и изменение родства этим документом не принимаются.

## 1. Подтверждённый вход и управление

| Caller | Проверенная связь | Evidence |
|---|---|---|
| HTTP pack bake | `container.surface_materialization_orchestrator()` → `stack.bake_pack(...)` | [map.py](../../backend/app/api/routes/map.py:147) |
| DI | Создаёт `WorldSurfaceMaterializationOrchestrator` с pack/detailed/planning/capture bindings | [worldData.py](../../backend/app/core/container/worldData.py:247) |
| `WorldSurfaceMaterializationOrchestrator.bake_pack(mode=light)` | `materialize_pack_light()` → `PackMaterializationOrchestrator.materialize_light_pack()` | [выбор light](../../backend/app/application/worldData/materialize/surface/worldSurfaceMaterializationOrchestrator.py:114), [делегирование](../../backend/app/application/worldData/materialize/surface/worldSurfaceMaterializationOrchestrator.py:210) |
| `PackMaterializationOrchestrator.materialize_light_pack()` | `_materialize_l0_pack(scope=light)` | [packMaterializationOrchestrator.py](../../backend/app/application/worldData/pack/bake/l0/packMaterializationOrchestrator.py:91) |
| `_materialize_l0_pack()` | Capture/prepare surface plans → L0 `bake_tiles()` → сопутствующие effects → publisher | [подготовка](../../backend/app/application/worldData/pack/bake/l0/packMaterializationOrchestrator.py:174), [L0](../../backend/app/application/worldData/pack/bake/l0/packMaterializationOrchestrator.py:221), [publication](../../backend/app/application/worldData/pack/bake/l0/packMaterializationOrchestrator.py:254) |

Это сокращённая цепочка рельефа: климат, region state, background jobs и другие операции pack отдельно не аудируются этим документом.

## 2. Подтверждённая planning-цепочка

```text
SurfacePlanningEntry.prepare_captured
  → prepare_captured_bundle
    → SurfacePlanningAssembler.prepare
      → _build(contract, inputs, exact upstream refs)
        → PlanningService.get_or_build
          → cache hit: проверенный PlanEnvelope
          → cache miss: PlanningService._build
            → PlanRegistry.build → зарегистрированный provider.build
```

Evidence: [entry](../../backend/app/application/worldData/planning/composition/surfacePlanningEntry.py:61), [bundle preparation](../../backend/app/application/worldData/planning/composition/surfacePlanningAssembler.py:145), [service dispatch](../../backend/app/application/planning/service/planningService.py:141), [registry adapter](../../backend/app/application/planning/providers/planRegistry.py:55).

**Проверенный DI использует baseline:** `surface_planning()` вызывает `register_world_plan_providers`, а тот регистрирует `TerrainPlanProvider`, `ReliefPlanProvider`, `RiverReliefPlanProvider`. Evidence: [DI](../../backend/app/core/container/worldData.py:131), [регистрация](../../backend/app/application/worldData/planning/composition/planProviders.py:118). На cache hit provider не обязан вычисляться повторно; наличие пути dispatch не является доказательством runtime-вызова каждого provider на каждом bake.

| Класс | Получает | Возвращает / вычисляет | Проверенный вызов |
|---|---|---|---|
| `TerrainPlanProvider` | `TerrainBaseInput`, climate-base envelope | `TerrainPlan`: coarse базовые высоты | [build](../../backend/app/application/worldData/generators/terrain/planning/terrainPlanProvider.py:23) |
| `ReliefPlanProvider` | Relief inputs и exact climate/terrain/water envelopes | `ReliefPlan`: coarse surface, mountain layout, light effects | [build → _plan_relief](../../backend/app/application/worldData/generators/terrain/relief/planning/reliefPlanProvider.py:104) |
| `RiverReliefPlanProvider` | River-relief inputs, pre-river relief и routes | `RiverReliefPlan`: coarse/fine русла и поверхности | [build → _plan_river_relief](../../backend/app/application/worldData/generators/terrain/relief/planning/reliefPlanProvider.py:163) |

Внутри assembler проверена зависимость: climate base → terrain base → water placement → relief → hydrology routes → river relief → final hydrology. Это AS-IS dependency flow планов, не дерево родства DAG-нод.

## 3. Внутренние вычислительные pipeline — преимущественно функции

| Функция / модуль | Подтверждённая работа | Роль |
|---|---|---|
| `_plan_relief()` | Последовательно вызывает mountain layout, coarse relief и light relief | Внутренняя сборка одного ReliefPlan |
| `naturalRelief.mountain_layout()` | Collect подготовленных mountain entries, выбор/stamp параметров | Алгоритмическая стадия |
| `naturalRelief.light_relief()` | Базовые light-высоты → mountain footprint effects → ravine effects | Линейная вычислительная последовательность |
| `formPipeline.materialize_mountain_entry()` | Выбирает вычисление горы или хребта; form/raster/side-fill и merge peaks | Внутренний pipeline геометрии, а не класс Orchestrator |
| `_plan_river_relief()` → `river_beds()` | Вычисляет coarse и fine изменения поверхности под руслами | Вычислительная стадия после routes |

Evidence: [вызовы _plan_relief](../../backend/app/application/worldData/generators/terrain/relief/planning/reliefPlanProvider.py:94), [naturalRelief](../../backend/app/application/worldData/generators/terrain/relief/planning/naturalRelief.py:27), [вызов mountain materialization](../../backend/app/application/worldData/generators/terrain/relief/planning/naturalRelief.py:74), [formPipeline](../../backend/app/application/worldData/generators/terrain/mountains/formPipeline.py:121), [русла](../../backend/app/application/worldData/generators/terrain/relief/planning/reliefPlanProvider.py:143).

## 4. Подтверждённое применение к L0

```text
WorldMapBakeOrchestrator.bake_tiles
  → compose_light_grid
    → DEFAULT_CONTRIBUTORS из maskDomainRegistry / COMPOSE_CONTRIBUTOR_ORDER
      → ReliefContributor.apply
      → MountainContributor.apply → MountainMaskMaterializer.apply_plan
      → RavineContributor.apply
  → compose.to_wire_tile → writer.write_world_map_tile
```

Relief contributors показаны как выбранные участки общего compose; между ними работают и другие contributors. Evidence: [bake_tiles → compose](../../backend/app/application/worldData/pack/bake/l0/worldMapBakeOrchestrator.py:143), [цикл contributor.apply](../../backend/app/application/worldData/pack/bake/lightGrid/bake.py:46), [factory registry](../../backend/app/application/worldData/pack/bake/lightGrid/maskDomainRegistry.py:29), [порядок](../../backend/app/dataModel/masks/enums/maskDomainId.py).

| Класс | Подтверждённая работа |
|---|---|
| `ReliefContributor` | Берёт `bundle.relief.payload.light.base_surface_z`, наносит высоты только на requested tiles |
| `MountainContributor` | Вызывает `MountainMaskMaterializer.apply_plan()` |
| `MountainMaskMaterializer.apply_plan()` | Наносит frozen mountain cells: terrain, surface_z, facing; не вызывает materialize() для повторного построения формы |
| `RavineContributor` | Наносит frozen ravine cells: terrain и surface_z |

Evidence: [relief](../../backend/app/application/worldData/pack/bake/lightGrid/contributors/relief.py), [mountain delegate](../../backend/app/application/worldData/pack/bake/lightGrid/contributors/mountain.py), [materializer](../../backend/app/application/worldData/generators/terrain/mountains/materializer.py), [ravine](../../backend/app/application/worldData/pack/bake/lightGrid/contributors/ravine.py).

`MountainMaskMaterializer` также имеет `collect()` и `materialize()`. Их наличие не означает, что они вызываются из текущего `MountainContributor.apply`: проверенная ветка использует apply_plan. Растеризация mountain form подтверждена раньше, внутри naturalRelief.light_relief.

## 5. Соседние пути: не смешивать с подтверждённым baseline light

- `GeoReliefPlanProvider` и `GeoRiverReliefPlanProvider` существуют, делегируют общим вычислениям с другими типами зависимостей. Их автоматическая activation в проверенном baseline DI не подтверждена. Само наличие классов не доказывает production wiring.
- `RiverReliefPlanner.plan_fine()` → `NativeRiverReliefPublicationJob.publish()` → `NativeRiverReliefJob.plan()` — подтверждённые прямые связи отдельной native fine-операции. Поиск по `backend/app` не выявил вызов `RiverReliefPlanner()` в проверенной baseline цепочке; это не доказательство недостижимости во всех scripts/tests.
- Native publication job валидирует source proofs и возвращает PlanEnvelope. В просмотренной реализации он не сохраняет manifest, не активирует pack и не выполняет world commit. Слово Publication здесь нельзя трактовать как publication результата light.
- `TerrainBatchOrchestrator` и grade mill/paint не добавляются в light-путь по соседству файлов: их отдельные materialization/refine сценарии не являются доказанной частью этой цепочки.

Evidence: [RiverReliefPlanner](../../backend/app/application/worldData/generators/terrain/relief/planning/riverReliefPlanner.py:14), [envelope publication](../../backend/app/application/worldData/generators/terrain/relief/planning/river/publication.py:28), [native execution](../../backend/app/application/worldData/generators/terrain/relief/planning/river/execution.py:16).

## 6. Предложения по декомпозиции — не принятые новые контракты

- `WorldSurfaceMaterializationOrchestrator` и `PackMaterializationOrchestrator`: самостоятельные операции выделяются в линейные domain Pipeline; их оркестрация переносится в DAG. Старые обёртки удаляются после принятой замены/cutover, не сейчас.
- `SurfacePlanningAssembler`/Entry/providers могут быть внутренними частями уже именованного `ISurfacePlanningPipeline.prepare_surface_plan`; конкретная реализация требует GEN-SURFACE-PLAN freeze. Суффикс Pipeline относится к публичной границе, а не требует переименовать все helpers/providers.
- `WorldMapBakeOrchestrator`: отделить L0 preparation от effects/publication; точный публичный Pipeline/метод и контракт ещё OPEN. Contributors и геометрические вычисления не превращаются автоматически в DAG-ноды.
- Выделять ли дополнительный публичный Relief Pipeline внутри/вместо части surface planning — OPEN. Имя, Input/Output/Error и место в composition не назначены.

Никаких новых NodeId, переноса children, изменения обязанностей readers, production cutover или выполнения кода этот поддокумент не разрешает.

## Отдельная ревизия

Находки, открытые вопросы и пределы подтверждения вынесены в [LIGHT-RELIEF-REVIEW](./generator-light-relief-review.md).
