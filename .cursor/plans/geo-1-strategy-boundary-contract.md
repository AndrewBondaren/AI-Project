# GEO-1 G4 — уточнение границы стратегий

Статус: APPROVED 2026-10-28; G4-S IMPLEMENTED/VERIFIED, G4 следует отдельным заходом.
Дата: 2026-10-28. Основной шаг: [G4](./geo-1-designed-water.md#g4--абстракция-стратегий).

## Обнаруженные расхождения

1. §5.2-E/H, J06 и G6/G7 требуют field draft и единственный threshold в
   G4-C. §6.29-M требует от strategy draft уже готовые footprints. Для
   procedural strategy это переносит threshold до общего preparer либо
   вынуждает повторно выбирать геометрию. Эти сигнатуры несовместимы.
2. G4 перечисляет input/draft/field/budget/protocol/factory, но обязательные
   поля §6.29-B/F/L/M ссылаются на ещё отсутствующие WaterDesignSource,
   WaterSourceMetadata, WaterFieldRecipe policies и BasinFloorProfile.
   Нельзя заменить их object/Any/строковыми forward refs на несуществующие
   модели или импортом application DTO в dataModel.
3. Factory должна возвращать implementation, но четыре implementation
   реализуются только в G5/G6/G7. Внутренние NotImplementedError-заглушки
   противоречат code-gates; импорт будущих модулей делает G4 неисполняемым.
4. В §5.1 поле названо normalized wetness [0,1], а §6.29-F задаёт signed
   continental field [-1,1] с последующей quantization. Носитель и момент
   преобразования должны быть одни для noise/plate/composer/preparer.

Ни одно расхождение не требует менять алгоритмы, defaults, policy engine,
budget formula, production gate G10-A или добавлять новый placement resolver.

## Согласованный единый контракт

### Стратегия возвращает поле либо authored геометрию

WaterDesignDraft — discriminated union с двумя вариантами:

- AuthoredWaterDesignDraft: footprints:tuple[frozenset[Coord],...],
  coordinate_space:CoordinateSpace, metadata:WaterSourceMetadata,
  floor_z:FineZ, floor_profile:BasinFloorProfile|None.
- ProceduralWaterDesignDraft: field:ContinentalField,
  metadata:WaterSourceMetadata, floor_z:FineZ,
  floor_profile:FieldFloorProfile. Footprints отсутствуют.

Discriminator — отдельный enum формы результата AUTHORED/PROCEDURAL,
а не новый enum выбора алгоритма. Existing DesignedWaterStrategyKind
остаётся единственной осью выбора алгоритма.

ContinentalField содержит recipe:WaterFieldRecipe и immutable row-major
samples:tuple[tuple[SurfaceGridCoord, finite strict float[-1,1]],...].
Один sample на canonical coarse working cell; duplicate coordinates и неверный
порядок отклоняет field record, canonical coordinates — G4 input boundary с
actual topology/grid (recipe topology описывает world-fine field).
Field record не угадывает coordinate scale. Поле не является fine-world
array, floor map или уже выбранным набором воды.

Noise/plate/composer возвращают signed field по §6.29-F. G4-C единожды
переводит значения в quantized wet score, отсекает partial region cells,
применяет allocated_fine2 и deterministic prefix. Только после этого
возникают procedural footprints и existing PlacementCandidate. У authored
ветки готовая геометрия сохраняется без threshold; G5 переиспользует
existing geometry helpers, G4-C не растеризует её повторно.

Таким образом требование §6.29-M о footprints применяется к authored draft
и результату procedural preparation, а не к procedural strategy draft.
ТЗ «preparer создаёт typed draft» уточняется до «preparer принимает draft
и создаёт prepared entries/candidates».

### Вход использует реальные immutable данные

Сохраняются поля §6.29-L/M: source, metadata, context, region, budget,
seed_root, topology, grid, pre_hydrology:PlanEnvelope[TerrainPlan],
region_coverage. pre_hydrology_ref — property envelope.ref.
Procedural вариант дополнительно содержит field_policy:WaterFieldRecipe;
authored вариант его не имеет. Discriminator — effective strategy enum.
Для трёх procedural enum нужны отдельные literal variants с подходящим
recipe, чтобы noise input нельзя было соединить с plate recipe.

Boundary validation проверяет source/metadata/budget identity, region UID
и area/coverage, resolved non-null context и strategy/recipe согласованность,
coherence world/ref/topology/grid. Это проверки входных данных, не повторный
PolicyResolver/cascade и не spatial resolve. Immutable envelope нужен для
sampling, opaque ref его не заменяет. Активный source capture не меняется.

### Dispatch собирается из готовых реализаций

DesignedWaterStrategy остаётся protocol design(input)->WaterDesignDraft.
DesignedWaterStrategyFactory получает четыре обязательных implementation
через именованные constructor arguments: authored_region,
continental_noise, plate, plate_noise. Все имеют общий protocol.
get(kind:DesignedWaterStrategyKind)->DesignedWaterStrategy использует одну
полную enum→implementation таблицу; нет defaults, registry mutation,
скрытого импорта будущих классов и fallback на noise.

G4 тестирует dispatch на test implementations; G5/G6/G7 поставляют реальные
классы. Production composition связывает их в G10-A. Это конечная DI
граница, не временные внутренние алгоритмические заглушки.
Failures на strategy boundary используют существующие PlanBuildFailure и
FieldPathError с доменными enum codes; отдельный parallel result/failure
framework не вводится. Неизвестный kind не превращается в успешный draft.

## Порядок реализации после согласования

### G4-S — недостающие dataModel prerequisites

Цель: предоставить обязательные типы G4 до интерфейса стратегий.
ТЗ: tz_terrain_generation §Planning и доставка GEO-1;
tz_terrain_hydrology §Declare; main §6.29-B/F/L/M.

Файлы, уже предусмотренные целевой архитектурой основного плана:

- dataModel/hydrology/sources/{proceduralWaterSource,waterDesignSource,
  waterSourceMetadata}.py и __init__.py — 4 файла.
- existing hydrology/generation/waterGenerationSettings.py — добавить
  body-only generation_region_uid по B, без нового cascade channel.
- dataModel/terrain/designedWater/settings/{continentalNoisePolicy,
  plateGenerationPolicy,fieldCompositionPolicy}.py и __init__.py — 4 файла.
- dataModel/terrain/designedWater/fields/field.py и __init__.py — 2 файла:
  recipes, field samples и общие enum channels/composition operation.
- dataModel/terrain/relief/bathymetry/floorProfile.py — isolated profile
  union; existing BasinSpec floor_profile/writer расширяются только в G9.

Settings здесь — resolved frozen policies с точными defaults/ranges F;
authored nullable leaf settings/cascade bindings не подменяются этими
records и подключаются owning generation шагом до G8/G10-A.
Source union — derived wrappers existing declared sources, не новый
persisted список. До G5-C1 existing coastline имеет нынешнюю water_source
семантику; G5-C1 обязателен для исключения нового BODY_BOUNDARY из wrapper.
WorldHydrology.procedural_bodies и активные Declared* поля здесь не меняются.

Проверка: strict/frozen/revalidation tests sources/metadata/recipes/profiles;
wrong source kind, duplicate region binding, nonfinite/range errors,
wrong recipe discriminator; positive/negative planning typing. Нет новых
imports из dataModel в application и нет production registration.
Done: обязательные G4 dependency types существуют без algorithm/writer switch.

G4-S выполнен 2026-10-28: GEO-1 209/209 (+17), location/cascade/rasterizer
70/70; positive typing 291 файл, 0 ошибок; negative planning 113/113,
cascade 19/19. Composition подтверждена, dataModel→application imports нет.
Canonical coarse membership поля проверяется в G4 с actual grid; sampled
profile completeness/z<level — в draft/spec, а не isolated profile record.

### G4 — input/output/protocol/dispatch

Цель/ТЗ прежние. Файлы исходного G4 сохраняются; prerequisite modules
поступают из G4-S. Budget records реализуются здесь, calculator — G4-P.
Точные варианты draft/input и DI boundary — выше.
Проверка: identity/recipe/coordinate invariants; dispatch всех enum values
на предоставленные test implementations, missing constructor bindings и
invalid kind явно отклоняются; no spatial resolve/z-write/default choice.
Done: executable typed boundary; algorithms остаются G5/G6/G7.

G4-S и G4 — два отдельных захода по правилу «один шаг за заход».
Перед G4-S пересчитать bathymetry и затрагиваемые test folders; существующий
hydrology root не расширяется, source contracts живут в sources/.
После согласования привести §5.1/§5.2/§6.29-M, G4 и ТЗ к этому контракту,
добавить G4-S перед G4. G4-P/G4-C/G5/G6/G7 сохраняют свои обязанности.
