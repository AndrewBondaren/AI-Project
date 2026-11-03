# GEO-I9.3 — ревью исправления 01–89

**2026-11-04 · FAIL по полноте реестра.** Проверены строки 70–89 [плана](geo-1-designed-water.md#i93-реестр-удаления-старого-пути-гидрологии) и фактические callers. В коде присутствуют все 89 номеров. По отношению к [ревью 01–69](geo-i9-3-legacy-registry-rereview.md) для canonical source, XY query и standalone native routes появились владельцы и проверки. Для рабочих карт и coating указана производная проекция. Открыты три замечания. Пути ниже отсчитываются от корня репозитория.

### 1. GEO-LEGACY-76 не определяет, кто публикует точный river ref

В `backend/app/dataModel/surfacePlanning/surfacePlanBindings.py:81–82` routes и river объявлены через surface.geo bindings. Регистрация провайдера в `backend/tests/geo1/integration/support/pipeline.py:174` использует эти handles. Предлагаемый по 76 NativeRiverReliefPublicationJob требует routing_inputs, fine water и routes с точным NATIVE_ROUTES_CONTRACT, затем сам возвращает PlanEnvelope с NATIVE_RIVER_RELIEF (`backend/app/application/worldData/generators/terrain/relief/planning/river/publication.py:29–52,64–73`). В протоколе registered provider результатом служит PlanBuildResult (`backend/app/application/planning/providers/planProvider.py:51–53`). PlanningService составляет внешний ref из request.key и request.dependencies (`backend/app/application/planning/service/planningService.py:134–146`). Даже если извлечь payload из native envelope, зарегистрированная сборка с прежним binding получит другой ref. Native final проверяет NATIVE_RIVER_RELIEF (`backend/app/application/worldData/generators/hydrology/planning/assembly/final/publication.py:60–62`).

**Действие.** Дополнить 59/75/76 владельцем ключа и публикации, подходящими bindings и источником routing_inputs. Зафиксировать, как вызывающий код получает именно тот routes и river ref, который допускает native final. **Приёмка.** Запустить зарегистрированный GEO graph через PlanningService. Сравнить полные refs выданных envelopes с refs зависимостей принятого native final. Дойти до canonical source и проверить отказ для envelope с тем же payload под прежним surface.geo key.

### 2. GEO-LEGACY-77–84 пропускают вызываемый boundary-адаптер

В `backend/app/application/worldData/generators/hydrology/boundaries/boundaryPreparation.py:39` BoundaryPreparationJob передаёт snapshot в AttachedCoastlinePreparer.prepare_boundary. У метода остаются импорт HydrologyPlan и bound H: HydrologyPlan (`backend/app/application/worldData/placement/adapters/coastline/attachedCoastline.py:9,28`). Метод повторно валидирует snapshot и передаёт его в BoundaryGeometry. На него также есть прямой typed caller в `backend/tests/typing/planning/valid/terrain/geoPipeline.py:76`.

**Действие.** Привязать адаптер к 77/82/83, перевести публичную сигнатуру и импорт на новый snapshot. **Приёмка.** Проверить типизацию прямого вызова с canonical source snapshot и пройти реальный путь BoundaryPreparationJob → adapter → BoundaryGeometry с accepted target, CONNECTED_TO и SHARED_BOUNDARY.

### 3. GEO-LEGACY-89 пропускает registered climate provider

В `backend/app/application/worldData/generators/climate/planning/climatePlanProvider.py:70–84` ClimateLocalPlanProvider ограничивает H типом HydrologyPlan и передаёт в build_local_plan_from_coarse весь hydrology.payload. Production регистрирует его в `backend/app/application/worldData/planning/composition/planProviders.py:127`, GEO fixture в `backend/tests/geo1/integration/support/fixtures.py:76`. После снятия наследования по 62 standalone GeoHydrologyPlan не удовлетворит этому bound. Правка одной функции в 89 оставляет тип и передачу проекции у caller неопределёнными.

**Действие.** Включить provider и его binding в 89, определить передачу coarse height projection той же revision. **Приёмка.** Проверить типизацию зарегистрированного provider и получить climate_local через registry с новым final. Сверить высоты resolved local anchors с проекцией и отклонить чужую revision.

Проверка статическая. Сценарии для будущего удаления не запускались. Версионирование профиля Pack явно вынесено на решение владельца Spatial и не включено в три замечания.
