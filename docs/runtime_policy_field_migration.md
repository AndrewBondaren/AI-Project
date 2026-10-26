# Миграция field policy E6

Аннотации: DefaultWhenMissing / DefaultEnumWhenMissing. Типы, Field constraints,
aliases, nullable, default/default_factory и CascadeChannel сохранены.
Перечень фиксирует затронутые поля, не заменяет schema registry.

Мигрированы 578 legacy-default полей: 556 в 88 модулях dataModel и 22 в bundle DTO. Дополнительно уточнён nullable enum контракт WallOpeningSpec.opening_type.

- `backend/app/dataModel/climate/climateZone/climateZoneEntry.py` — 5 полей.
- `backend/app/dataModel/climate/weatherType/weatherTypeEntry.py` — 8 полей.
- `backend/app/dataModel/climate/worldClimateScalars.py` — 13 полей.
- `backend/app/dataModel/flora/cropsTypeEntry.py` — 2 полей.
- `backend/app/dataModel/hydrology/category.py` — 1 полей.
- `backend/app/dataModel/hydrology/declaredCoastline.py` — 1 полей.
- `backend/app/dataModel/hydrology/declaredLake.py` — 1 полей.
- `backend/app/dataModel/hydrology/declaredRiver.py` — 13 полей.
- `backend/app/dataModel/hydrology/lakes.py` — 1 полей.
- `backend/app/dataModel/hydrology/landforms.py` — 1 полей.
- `backend/app/dataModel/hydrology/mapCellHydrology.py` — 5 полей.
- `backend/app/dataModel/hydrology/rivers.py` — 8 полей.
- `backend/app/dataModel/hydrology/seas.py` — 5 полей.
- `backend/app/dataModel/hydrology/worldHydrology.py` — 10 полей.
- `backend/app/dataModel/livestock/livestockTypeEntry.py` — 2 полей.
- `backend/app/dataModel/locations/locationType/locationTypeEntry.py` — 4 полей.
- `backend/app/dataModel/locations/locationType/locationTypeSubtypeEntry.py` — 6 полей.
- `backend/app/dataModel/locations/namedLocation/bundleNamedLocation.py` — 29 полей.
- `backend/app/dataModel/locations/settlement/area/perimeterBarrier.py` — 3 полей.
- `backend/app/dataModel/locations/settlement/district/districtConnection.py` — 3 полей.
- `backend/app/dataModel/locations/settlement/district/districtPayload.py` — 1 полей.
- `backend/app/dataModel/locations/settlement/district/districtTemplateEntry.py` — 16 полей.
- `backend/app/dataModel/locations/settlement/district/districtTopologySlot.py` — 2 полей.
- `backend/app/dataModel/locations/settlement/district/frontageTypeOrder.py` — 1 полей.
- `backend/app/dataModel/locations/settlement/district/placementCondition.py` — 6 полей.
- `backend/app/dataModel/locations/settlement/district/requiredStructure.py` — 3 полей.
- `backend/app/dataModel/locations/settlement/district/worldDistrictZonePreference.py` — 1 полей.
- `backend/app/dataModel/locations/settlement/settlement/locationMoodEntry.py` — 1 полей.
- `backend/app/dataModel/locations/settlement/settlement/settlementPayload.py` — 14 полей.
- `backend/app/dataModel/locations/settlement/settlement/settlementSizeEntry.py` — 1 полей.
- `backend/app/dataModel/locations/settlement/settlement/settlementSkeleton.py` — 2 полей.
- `backend/app/dataModel/locations/settlement/settlement/settlementSpecializationBind.py` — 2 полей.
- `backend/app/dataModel/locations/settlement/settlement/settlementSpecializationEntry.py` — 3 полей.
- `backend/app/dataModel/locations/settlement/settlement/typicalDistrictRef.py` — 2 полей.
- `backend/app/dataModel/locations/structure/barrier/barrierTemplateEntry.py` — 6 полей.
- `backend/app/dataModel/locations/structure/building/buildingBodyTemplate.py` — 7 полей.
- `backend/app/dataModel/locations/structure/building/buildingTemplateOutline.py` — 17 полей.
- `backend/app/dataModel/locations/structure/building/buildingTemplateRegistryEntry.py` — 2 полей.
- `backend/app/dataModel/locations/structure/building/buildingTemplateRoomSlot.py` — 2 полей.
- `backend/app/dataModel/locations/structure/building/levelDef.py` — 6 полей.
- `backend/app/dataModel/locations/structure/building/occupiedFootprint.py` — 2 полей.
- `backend/app/dataModel/locations/structure/building/plotLayoutTemplate.py` — 12 полей.
- `backend/app/dataModel/locations/structure/building/roomConnection.py` — 7 полей.
- `backend/app/dataModel/locations/structure/building/staircaseSpec.py` — 20 полей.
- `backend/app/dataModel/locations/structure/building/structureTemplate.py` — 9 полей.
- `backend/app/dataModel/locations/structure/enums/buildingPurpose/purposePackEntry.py` — 1 полей.
- `backend/app/dataModel/locations/structure/room/entryPoint.py` — 5 полей.
- `backend/app/dataModel/locations/structure/room/roomDef.py` — 16 полей.
- `backend/app/dataModel/locations/structure/room/roomTypeEntry.py` — 1 полей.
- `backend/app/dataModel/locations/structure/room/shapeParams.py` — 5 полей.
- `backend/app/dataModel/locations/structure/room/sizeSpec.py` — 4 полей.
- `backend/app/dataModel/locations/structure/room/wallOpeningSpec.py` — 3 полей.
- `backend/app/dataModel/locations/transitions/transition.py` — 10 полей.
- `backend/app/dataModel/locations/transitions/transitionEndpoint.py` — 7 полей.
- `backend/app/dataModel/locations/transitions/transitionParams.py` — 1 полей.
- `backend/app/dataModel/locations/transitions/transitionSide.py` — 6 полей.
- `backend/app/dataModel/locations/transitions/transitionTypeEntry.py` — 1 полей.
- `backend/app/dataModel/lore/loreRegistry/loreRegistryEntry.py` — 1 полей.
- `backend/app/dataModel/masks/maskCategoryPolicy.py` — 2 полей.
- `backend/app/dataModel/materials/materialRegistryEntry.py` — 23 полей.
- `backend/app/dataModel/perks/perkTemplateOutline.py` — 12 полей.
- `backend/app/dataModel/perks/perkTemplateRegistryEntry.py` — 2 полей.
- `backend/app/dataModel/races/raceTemplateOutline.py` — 9 полей.
- `backend/app/dataModel/races/raceTemplateRegistryEntry.py` — 2 полей.
- `backend/app/dataModel/resources/resourceTypeEntry.py` — 7 полей.
- `backend/app/dataModel/roads/roadSettingsEntry.py` — 7 полей.
- `backend/app/dataModel/shared/ranges.py` — 2 полей.
- `backend/app/dataModel/terrain/relief/canal.py` — 2 полей.
- `backend/app/dataModel/terrain/relief/canalObstaclePolicy.py` — 1 полей.
- `backend/app/dataModel/terrain/relief/canalTemplateEntry.py` — 3 полей.
- `backend/app/dataModel/terrain/relief/mountainSideRecipe.py` — 4 полей.
- `backend/app/dataModel/terrain/relief/reliefDeltaBand.py` — 1 полей.
- `backend/app/dataModel/terrain/relief/reliefGradeInstance.py` — 10 полей.
- `backend/app/dataModel/terrain/relief/reliefGradeKnobs.py` — 5 полей.
- `backend/app/dataModel/terrain/relief/reliefGradeSystem.py` — 2 полей.
- `backend/app/dataModel/terrain/relief/reliefRoleCase.py` — 9 полей.
- `backend/app/dataModel/terrain/relief/reliefTemplate.py` — 10 полей.
- `backend/app/dataModel/terrain/relief/reliefTemplateRegistryEntry.py` — 2 полей.
- `backend/app/dataModel/terrain/relief/reliefTerrainEnvelope.py` — 21 полей.
- `backend/app/dataModel/terrain/relief/specs.py` — 2 полей.
- `backend/app/dataModel/terrain/relief/worldReliefGradeObstacle.py` — 1 полей.
- `backend/app/dataModel/terrain/relief/worldReliefPickPolicy.py` — 13 полей.
- `backend/app/dataModel/terrain/terrainCategoryEntry.py` — 5 полей.
- `backend/app/dataModel/terrain/terrainRegistryEntry.py` — 7 полей.
- `backend/app/dataModel/terrain/worldTerrainScalars.py` — 9 полей.
- `backend/app/dataModel/terrainMasks/hillPolicy.py` — 4 полей.
- `backend/app/dataModel/terrainMasks/mountain/specs.py` — 18 полей.
- `backend/app/dataModel/terrainMasks/worldTerrainMasks.py` — 34 полей.

- `backend/app/application/jsonValidation/bundle/connectionGraph.py` — 22 поля.

Resolver не конструирует unchecked POJO и не пропускает ошибочные строки.
Deprecated alias names экспортируются с новой policy только для совместимости
импортов; старого fallback поведения нет. Типовые numeric nullable constraints
помещены внутри non-null ветки union, чтобы null не вызывал TypeError.

Сохранены индивидуальные domain contracts: optional null наследуется, blank
pin/template означает отсутствие по явному before-validator, known purpose
family normalization и штатные empty-library defaults сохранены. Неизвестные
purpose tokens больше не теряются. Room/opening/height/stem invalid repairs
удалены, horizontal passage должен быть doorway/archway. Identity race/perk
заполняется для None-auto; пустая строка отвергается.

На этапе миграции полей оставались cascade source refs, standalone library/CRUD
и domain-specific sides/placement/material repair. Последующий consumer-срез
и точные границы завершённого аудита указаны в плане runtime-world-edit-policy.
Смена annotation сама по себе не подтверждает соответствие consumer политике.

Приёмка: 140 целевых tests OK; исходные 196 контрактных tests OK (наборы
пересекаются). Итоговый широкий прогон: 1631 tests, 32 errors,
1 expected failure. Все 32 идентификатора ошибок встречались в baseline;
совпадение имён само по себе не доказывает отсутствие регрессий поведения.
Typecheck cascade: 0 errors/warnings, 4 negative contracts подтверждены.
