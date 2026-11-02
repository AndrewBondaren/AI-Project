# LIGHT-HYDRO-ROUTE — статическая трасса API → light → гидрология

**Проверено:** 2026-11-02. **Статус:** AS-IS evidence для последующего проектирования пользователем DAG-нод. Новые NodeId, родство, CRUD-контракты и перенос вызовов этим документом не принимаются.

## 1. Route и результат проверки

`POST /api/worlds/{world_uid}/map/pack/bake?mode=light`.

Префикс `/api` подтверждён [app.include_router](../../backend/app/core/app.py:140). Handler: [bake_world_pack](../../backend/app/api/routes/map.py:99).

Handler получает world, locations, connection nodes/edges, materialization context и writer; напрямую вызывает `surface_materialization_orchestrator().bake_pack`. Затем отдельно читает loading progress и формирует HTTP 200/207 response. Вызова engine DAG в этом handler нет. Текст module docstring про production DAG не является evidence фактического переноса этого route.

По принятому правилу необходимо сначала реализовать/принять API → DAG замену, затем удалить старый обход. URL может сохраниться с новым engine binding; существующий прямой generator caller не должен остаться fallback/debug альтернативой после cutover. Пока замены нет, этот аудит сам по себе не разрешает удаление.

## 2. Подтверждённая цепочка

```text
bake_world_pack(mode=light)
  → WorldSurfaceMaterializationOrchestrator.bake_pack
    → materialize_pack_light
      → PackMaterializationOrchestrator.materialize_light_pack
        → _materialize_l0_pack(scope=light)
          → загрузка relief templates
          → SurfacePlanningEntry.capture_view / prepare_captured
            → SurfacePlanningAssembler.prepare
              → PlanningService.get_or_build / registry providers
          → region-state snapshot / tile planning
          → условный drain фоновых jobs
          → coarse climate
          → locations index
          → WorldMapBakeOrchestrator.bake_tiles
            → compose_light_grid / HydroContributor
            → writer.write_world_map_tile
          → relief-grade persistence
          → fine-climate policy
          → PackBakePublisher.publish (если binding имеется)
            → freshness / finalize_pack_on_world
```

Evidence: [выбор light и делегирование](../../backend/app/application/worldData/materialize/surface/worldSurfaceMaterializationOrchestrator.py:114), [light wrapper](../../backend/app/application/worldData/pack/bake/l0/packMaterializationOrchestrator.py:91), [общий L0 метод](../../backend/app/application/worldData/pack/bake/l0/packMaterializationOrchestrator.py:150), [DI с publisher](../../backend/app/core/container/worldData.py:346).

DI регистрирует baseline providers через `register_world_plan_providers`; GEO/native не считаются активными по наличию классов. Cache hit может исключать повторный provider build, но не меняет обязательную согласованность результата.

## 3. Гидрология внутри surface planning

| Порядок зависимости | Caller → callee | Получаемый результат |
|---|---|---|
| После terrain base | `WaterPlacementPlanProvider.build` → `run_prepared_water_placement` | WaterPlacementPlan: records и basin specs |
| После размещения воды | Relief provider | Pre-river ReliefPlan; это операция рельефа |
| После relief/placement | `HydrologyRoutesPlanProvider.build` → `HydrologyRoutesAssembler.assemble` | HydrologyRoutesPlan |
| Внутри assemble | `WaterBodyPlanner.plan` → `WaterBodyJob.plan` | OpenWaterPlan |
| Затем внутри _routes | `CoarseRiverPlanner.plan` → `CoarseRiverJob.plan` | CoarseRiverPlan |
| Затем | `FineRiverPlanner.plan` → `FineRiverJob.plan` | FineRiverPlan |
| Затем | `DeclaredWaterPaintProjector.project` | Declared water paint |
| После route-stage | RiverReliefPlanProvider | RiverReliefPlan; операция рельефа |
| После routes и русел | `HydrologyFinalPlanProvider.build` → `HydrologyFactsAssembler.assemble` | HydrologyPlan с итоговыми water facts и post-river surface |

Evidence: [baseline registration](../../backend/app/application/worldData/planning/composition/planProviders.py:118), [assembler planning order](../../backend/app/application/worldData/planning/composition/surfacePlanningAssembler.py:60), [provider adapters](../../backend/app/application/worldData/generators/hydrology/planning/hydrologyPlanProvider.py:32), [вложенные route-операции](../../backend/app/application/worldData/generators/hydrology/planning/assembly/hydrologyRoutesAssembler.py:64), [final facts](../../backend/app/application/worldData/generators/hydrology/planning/assembly/hydrologyFactsAssembler.py).

Water/river jobs вычисляют свои результаты. Например, CoarseRiverJob имеет algorithmic policy branches для disabled hydrology и declared/procedural routes; такие внутренние ветвления не становятся DAG-нодами автоматически. Независимость coarse/fine публичных границ подтверждается контрактным разбором, не одним числом вызовов.

## 4. Применение гидрологии к L0

`compose_light_grid` вызывает `HydroContributor.apply` в общем contributor order. Он использует frozen hydrology plan и последовательно выполняет:

1. `apply_declared_rivers`;
2. `apply_declared_basins`;
3. `apply_coarse_open_water`.

Последняя стадия читает final coarse hydro и surface heights, наносит SEA/LAKE и сохраняет declared river cells по принятому правилу. Это три внутренних шага нанесения слоя, не три автоматически предлагаемые ноды. Evidence: [HydroContributor](../../backend/app/application/worldData/pack/bake/lightGrid/contributors/hydro/hydro.py:25), [coarse open water](../../backend/app/application/worldData/pack/bake/lightGrid/contributors/hydro/coarseOpenWater.py:27).

## 5. Статические количественные данные

Подсчёты не являются runtime-статистикой или оценкой latency:

| Объект подсчёта | Количество | Метод / граница |
|---|---:|---|
| Route declarations в map.py | 19 | Python AST router decorators; 13 GET, 5 POST, 1 DELETE. Не аудит всех API приложения |
| Исходные service reads bake-handler | 4 | World, locations, connection nodes, connection edges до bake; загрузка templates/region states вложена отдельно |
| Planning slots baseline prepare | 8 | Climate base, terrain base, water placement, relief, hydro routes, river relief, final hydro, local climate |
| Вложенные операции baseline routes assembler | 4 | Water bodies, coarse rivers, fine rivers, declared paint; не runtime call frequency |
| Внутренние стадии HydroContributor | 3 | Declared rivers, declared basins, coarse open water |
| Прямые DAG dispatch в bake-handler | 0 | Проверен handler bake_world_pack и его прямой вызов stack.bake_pack |

Ноль водоёмов/рек может быть нормальным доменным результатом; количество объектов, фактические cache hits/misses, повторные вычисления, bytes, длительности и частота ошибок этим аудитом не измерены.

## 6. Соседние API-пути, требующие отдельной миграции

В map.py найдены прямые generator/refine вызовы в `refine-from-entry`, `refine-chunk`, `schedule-chunk-refine`: handler готовит surface inputs, вызывает entry/refine operations и finalizes pack. Их перенос не покрывается одним изменением bake-handler. Evidence: [entry](../../backend/app/api/routes/map.py:490), [chunk](../../backend/app/api/routes/map.py:594), [schedule](../../backend/app/api/routes/map.py:673).

Полный аудит всех 19 routes и всего API приложения не выполнен. Не объявлять остальные GET/POST/DELETE уже проверенными или мигрированными по этому inventory. Новые route-исключения из правила API → DAG не вводятся.

## 7. Основа дальнейшего проектирования — без назначения нод

Подтверждена вложенная композиция самостоятельных кандидатов: water placement, relief, water bodies, river routes, river beds, final hydrology и L0 projection. Требуется сначала принять domain CRUD/Pipeline Input/Output/Error/DoD и решить, какие стадии самостоятельны, а какие внутренние.

Отдельно согласовать границу ранее именованного ISurfacePlanningPipeline: сохранение всей вложенной orchestration за одним именем не считается декомпозицией. Изменение ранее принятой публичной границы предъявляется явно; молча менять её запрещено.

После контрактов пользователь описывает ноды и orchestration. Этот документ не меняет семейства, callers, readers или их обязанности и не предлагает новую обязательную цепочку entry checks.
