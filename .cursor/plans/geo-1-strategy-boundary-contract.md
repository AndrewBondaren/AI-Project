# GEO-1 G4 — уточнение границы стратегий

Статус: основной контракт APPROVED 2026-10-28; G4-S IMPLEMENTED/VERIFIED.
Уточнение runtime → resolved result APPROVED 2026-10-28 («Далее»).
G4-I и G4 IMPLEMENTED/VERIFIED; production binding остаётся G10-A.
Дата: 2026-10-28. Основной шаг: [G4](./geo-1-designed-water.md#g4--абстракция-стратегий).

## G5 — незамкнутый authored geometry input

Статус: G5 IMPLEMENTED/VERIFIED 2026-10-28 после APPROVED («Давай»).
ТЗ: tz_terrain_generation §Planning и доставка GEO-1;
tz_terrain_hydrology §Declare; main §5.2-E/§6.29-B/M.

Входной аудит G5 показал:
- shape_cells требует ready anchors для AnchorRadiusShape;
- open coastline_cells требует actual seas max_area/max_extent limits;
- helpers принимают snapshot и geometry в одной рабочей сетке, но G4 source
  имеет fine geometry, а pre_hydrology — coarse surface;
- lake_level определяется по уже построенной shoreline geometry. Metadata.level
  требуется до design, поэтому его нельзя вычислить внутри strategy с подменой
  готовой metadata либо повторно растеризовать ту же геометрию в G8 mapper.

Рекомендуемый шов: однократная authored geometry preparation до metadata/design.
Существующие geometry algorithms сохраняются; не строить fine-world heightmap,
не передавать WorldHydrology/raw dict, не подставлять seas defaults в strategy.

Точные новые records — dataModel/terrain/designedWater/geometry/
authoredGeometry.py (+__init__, всего2):
AuthoredWaterGeometryRequest: source (три existing authored wrappers),
pre_hydrology:PlanEnvelope[TerrainPlan], topology:WorldTopology,
grid:SurfaceGridSettings, seed_root:EntityUid,
anchors:tuple[WaterAnchorInput,...], seas:HydrologySeasPolicy, z_min:FineZ.
Все поля required, frozen/strict/extra=forbid/revalidation; legacy seas POJO
revalidate через actual fields. Seas используется только для geometry limits;
admission/cascade/priority остаются у своих владельцев.
AuthoredWaterGeometry: source_uid:EntityUid, pre_hydrology_ref:PlanRef,
coordinate_space:CoordinateSpace, footprints:tuple[frozenset[Coord],...],
rim_level:FineZ|None, z_min:FineZ, notices:tuple[FieldPathError,...].
Geometry output в WORLD_SURFACE_GRID после existing fine→coarse projection;
collapse/degenerate/cap остаются явными existing domain issues.

Existing application/worldData/placement/adapters/water.py получает
prepare_authored_water_geometry(request)->AuthoredWaterGeometry.
Это source projection + существующие shape/lake/coastline helpers; без
PreparedPlacement/P2/admission/floor write. Ready anchors явно проецируются.
Existing hydrology/placement/projectDeclaredHydrology.py предоставляет
typed single-source projection; не собирать временный WorldHydrology.
Geometry helpers получают seed_root явно: не подменять actual world_uid seed'ом.
Existing callers обновляются вместе с helper signatures, без параллельного API.
В existing waterTypes.py: WaterGeometryView — structural Protocol только
topology/surface_z/anchors; AuthoredGeometryView — frozen application working
view этих полей. Это локальный geometry buffer, не второй transport и не
source settings. Существующий WaterPlacementContext соответствует Protocol.
Комментарии на records/geometry-field и пояснения в ТЗ обязательны по просьбе мастера.

AuthoredWaterDesignInput получает обязательное geometry:AuthoredWaterGeometry;
проверяет source/ref identity и metadata.level==rim_level у lake.
AuthoredRegionStrategy.design использует этот готовый geometry, сохраняет
metadata и authored basin floor; для lake/coastline scalar floor берётся из
готовых level/default_depth. Floor проверяется по geometry.z_min; authored
floor не изменяется молча и невозможное дно не получает скрытый clamp.
Процедурный input/strategy protocol/factory не меняются.

G8 после READY admission вызывает geometry preparation один раз, затем
строит metadata (lake level из geometry.rim_level), complete design input,
design draft и общий G4-C preparer. Profile/spec/writer остаются G9.
Нет циклической зависимости metadata↔design и повторной rasterization.

До реализации синхронизировать G5/G8 и ТЗ. Composition: geometry2,
strategies3→4, adapters6→6 (WARN, новые flat files не добавляются),
hydrology/placement3→3. Новые тесты — отдельная tests/geo1/authored/.
Проверки: basin/anchor/lake/open+closed coast, typed source projection и
collapse, same snapshot/space/seed, rim metadata coherence, no hidden defaults,
no writes/resolve, exact profile/geometry transport и existing adapter regression.

G5 выполнен: GEO-1 295/295 (+22), existing placement/water/factory67/67,
positive Pyright — 0 ошибок, negative planning144/144 (+7).
Records/geometry-field пояснены в docstrings/comments и ТЗ; explicit seed,
single-source projection и geometry result переиспользуются без rerasterize.
Actual legacy seas fields revalidate strict (включая bool→float), helpers
включены в positive typing. G8/G9/G10-A не переключались.

## Обнаруженные расхождения

### G5-CP — уточнение policy sources и support snapshot

Статус: APPROVED 2026-10-28, согласовано пользователем «Ок»; G5-CP DONE.
ТЗ: tz_policy §2–5; tz_terrain_generation §Planning;
tz_terrain_hydrology §GEO-1; main §6.8-F/§6.9/§6.29-C/G.

Проверенные блокеры G5-CP:
1. PriorityValueRef(FieldRef(HydrologySeasPolicy.placement_specificity))
   отклонён existing validator: frozen/extra=forbid/revalidate_instances=always
   обязательны. Existing seas/lakes/source POJO этому не соответствуют;
   DeclaredCoastline/DeclaredLake вообще не имеют authored priority поля.
2. Domain default сейчас0, а не1. Число1 нельзя вводить в descriptor/facts
   как исправление отсутствующего binding; owning default switch остаётся G10-A.
3. HydrologyPlan не содержит source_mapping; SourceBodyMapping ещё не создан.
   declared_basin_uid/location_uid физического WaterBody не заменяют many-to-many
   mapping после merge/split. Из них нельзя выводить water support source UID.

Согласованное замыкание входит в контракт G5-CP, без второго policy engine:

**Владельцы scalar priority.** Новый
dataModel/hydrology/placement/placementFields.py (+__init__,2 файла):
WaterSourcePlacementFields — единственный owner nullable placement_specificity
(default None); WaterCategoryPlacementFields — owner category placement_specificity
(existing default0 до G10-A). Frozen/strict/forbid/revalidation.
Category priority nullable (None означает наследование terminal0), default остаётся0.
HydrologyCategoryPolicy (category.py) оставляет общие bands; прежнее поле
рек механически переносится в HydrologyRiversPolicy (rivers.py), без смены поведения.
Existing basin/coastline/lake/procedural sources наследуют source поле;
seas/lakes — category поле. Старые объявления тех же полей удаляются,
не создаются вторая default table или persisted settings blob.
Readonly scalar projections для PolicySource используют эти же owning classes,
но получают actual значения normalized source/category POJO явно. Отсутствие
или invalid значение не исправляется default'ом проекции. Изменение actual
category value обязано менять decision без изменения descriptor/engine.
Root/category enabled и resolved strategy передаются typed required inputs;
field-local cases/gates объявляются metadata, а не ручным PolicyRuleId.
Точные модели в hydrologyPlacementPolicy.py:
HydrologyPlacementGateInputs(world_enabled:StrictBool, category_enabled:StrictBool)
с EnabledFor на обоих полях; HydrologyPlacementBehaviorInputs(strategy:
DesignedWaterStrategyKind) с SelectByValue по enum. Поля required, без defaults;
это derived inputs от captured owners/resolved context, не persisted настройки.
Descriptor ссылается на priority owning classes, поэтому определяется до
gate/behavior metadata и не создаёт source-model import cycle.
Общий FieldRef validator не ослабляется ради legacy POJO.

**Support snapshot.** Новый prescribed main §6.29-G
dataModel/hydrology/planning/sourceBodyMapping.py: SourceBodyMappingEntry
(source_uid, sorted unique body_uids) и SourceBodyMapping(entries sorted unique).
Пустая entry означает authoritative dry source; отсутствующая entry accepted
source — неизвестный required input, не dry.
В hydrology/policy/hydrologyPlacementPolicy.py определить HydrologyPolicySnapshot
с world identity, typed PolicySupportFact observations, optional actual
PlanEnvelope[HydrologyPlan], source mapping и explicit binding к тому же ref.
Поля required: world_uid:EntityUid, supports:tuple[PolicySupportFact,...],
hydrology:PlanEnvelope[HydrologyPlan]|None, source_mapping:SourceBodyMapping|None,
mapping_hydrology_ref:PlanRef|None. None означает отсутствие supplied evidence,
не отсутствие воды. HydrologyPolicyFacts содержит purpose:CoastlinePurpose,
category:WaterGenerationCategory, target_has_water:FactValue[bool|None].
Для water_source последний факт Known(None), не выдуманный Known(True).
Нет live World/SQL/Pack, opaque object/callback или независимого revision lifecycle.
Actual producer mapping остаётся final fill/materialize owning стадии;
G5-CP tests используют явные typed snapshots, production activation не заявляется.

**Декларации и исполнение.** hydrologyPlacementPolicy.py владеет AdmissionPolicy,
enum case keys, compound FieldRef predicates, HydrologyPolicyFacts и typed
source/boundary observations. Water source не получает выдуманной воды/опоры.
Boundary требует explicit target support; pending/disabled/failed/missing
наблюдения передаются существующим generic support механизмам. Wet/dry факт
берётся из mapping и actual final hydrology; unknown не заменяется False.
Target UID структурно связывается с RequireSupportEffect, а не вшивается в
строковый rule ID и не выбирается поиском ближайшей воды.

Application hydrology/policy/hydrologyPolicyFacts.py реализует только collect;
новый hydrology/policy/hydrologyPlacementBinding.py связывает typed inputs и
compile_admission_policy. Он не исполняет policy. Единственный executor —
existing PolicyResolver; existing P2/session читает decision.

Перед кодом синхронизировать G5-CP source-owner изменения и ТЗ, включая
точные readonly enabled/strategy inputs. Проверки: actual domain default
mutation, authored0, terminal0, source без support, boundary wet/dry/pending/
missing/failed/disabled, reference coherence, preview/runtime parity, no raw
wiring/UID inference. G5-C2/G5-C3/G8/G10-A сохраняют своё wiring/activation.
Composition: hydrology/placement2, hydrology/policy3→4, planning2→3,
application hydrology/policy3 файла (init/facts/binding); existing roots без additions.

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
region_coverage. context после согласованного G4-I имеет тип
ResolvedWaterGenerationContext, не рабочий WaterGenerationContext.
pre_hydrology_ref — property envelope.ref.
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

G4 выполнен 2026-10-28: GEO-1 238/238 (+19), location/cascade/rasterizer
77/77, positive Pyright — 0 ошибок, negatives planning124/cascade23.
Input.validate_draft проверяет выход с actual grid/topology: complete coarse
samples, metadata/recipe identity, canonical authored footprints и сохранение floor.
Budget records только проверяют границы; calculation/threshold/wiring не включены.

G4-S и G4 — два отдельных захода по правилу «один шаг за заход».
Перед G4-S пересчитать bathymetry и затрагиваемые test folders; существующий
hydrology root не расширяется, source contracts живут в sources/.
После согласования привести §5.1/§5.2/§6.29-M, G4 и ТЗ к этому контракту,
добавить G4-S перед G4. G4-P/G4-C/G5/G6/G7 сохраняют свои обязанности.

## Уточнение G4: рабочий cascade context не является immutable input

Статус этого раздела: IMPLEMENTED/VERIFIED 2026-10-28 после согласования.

При проверке ответственности перед G4 обнаружено: существующий
WaterGenerationContext наследует CascadeRuntimeContext. Frozen запрещает
присваивание публичным полям, но не делает объект immutable:
provenance — dict, private _world хранит live world, _links/_node_results —
рабочие данные общего resolver. Через такой input strategy получает доступ
к чужой ответственности и к исходным mutable данным. Cache immutable admission
также отвергает dict provenance; простой deepcopy не устраняет эти свойства.

Прошлый G4-S не менял этот существующий runtime-контракт. Его нельзя исправить
удалением private attrs внутри водной factory или локальным water-only freeze
механизмом: lifecycle cascade должен оставаться у общего cascade домена.

### Предлагаемая граница

1. В existing dataModel/cascade/runtimeContext.py добавить общий frozen
   ResolvedCascadeState[AxisT] с required level:AxisT и
   provenance:tuple[tuple[str,tuple[AxisT,str]],...]. Entries сортируются по
   имени параметра, имена уникальны; нет dict, private attrs/world/links/cache.
   Публичный freeze_resolved_context(ctx, result_type)->result_type выполняет только
   projection/revalidation публичных полей в явно переданный frozen subtype.
   Поля результата required, без подстановки defaults; generic boundary не
   содержит списка water fields и проверяет соответствие scope axis.
   Преобразование provenance — часть общего snapshot boundary.
2. В existing hydrology/generation/generationContext.py добавить
   ResolvedWaterGenerationContext(ResolvedCascadeState[WaterGenerationScope]):
   required water_fraction:WaterFraction, autoresolve:StrictBool,
   strategy:DesignedWaterStrategyKind. Все поля non-null, extra=forbid,
   strict/frozen/revalidate_instances=always. Нет новых defaults/cascade links,
   policy metadata или алгоритмов. WaterGenerationContext остаётся рабочим
   типом existing extend/PolicyResolver без изменения своего wire/state.
3. G4 input.context меняется на ResolvedWaterGenerationContext. Caller после
   existing cascade/policy передаёт результат общего freeze_resolved_context.
   Snapshot не вызывает extend/policy, не создаёт отсутствующие значения,
   не меняет исходный runtime context и не переносит private state.
   Ошибка неполного context — validation failure, а не fallback к defaults.

Это два разных контракта: рабочее состояние resolver и immutable результат
его работы. Снимок не является вторым authored settings source; поля
наследования/defaults по-прежнему задаются единственными existing settings.
Преобразование не имеет водного варианта общего cascade executor.

### Ownership и порядок

Отдельный подготовительный шаг G4-I перед G4: common snapshot record и
projection принадлежат dataModel/cascade/runtimeContext.py; water subtype —
dataModel/hydrology/generation/generationContext.py. Existing файлов в каждой
папке 5→5; новые production modules/registry registrations не требуются.
Для повторного использования existing immutable validation pure functions
_complete_record/_immutable/validate_immutable механически переносятся из
application/cache/service/cacheService.py в dataModel/validation/immutableValue.py.
cacheService сохраняет прежние names через explicit import aliases; поведение
API cache/planning не меняется, dataModel не импортирует application.
При проверке deep immutability найден пробел existing validator: он не обходил
private values вложенных BaseModel. Общий walker теперь проверяет их тем же
правилом (opaque/mutable/cycle rejected), без второго cascade-only validator.
Добавлена регрессия nested private world/list/dict/cycle; immutable private
tuple допустим. Это намеренное усиление admission, а не изменение cache API.
validation
1→2 файла; cascade и hydrology/generation остаются 5→5. Тесты нового boundary:
tests/geo1/contracts/cascade/resolved/{__init__,test_context}.py (2 файла),
parent cascade остаётся 5 файлов. Positive generic checks — отдельный
typing/planning/valid/cascade.py (valid 4→5), water checks — terrain/water.py;
negative checks — existing cascade_fields_invalid.py.
ТЗ: tz_cascade_context — resolved result boundary;
tz_terrain_generation §Planning и доставка GEO-1 — strategy input.

Проверки G4-I: snapshot неполного context отклоняется; independent snapshots
не делят mutable state; изменение исходного provenance не меняет снимок;
private world/links отсутствуют; existing validate_immutable принимает снимок;
round-trip и scope-axis validation; общий projection работает также с
невода́ным subtype. Positive fixtures — thematic valid/policy.py и
valid/terrain/water.py, без возврата к valid.py; negatives проверяют runtime
context вместо resolved snapshot и несовпадающие scope axes.

После G4-I G4 выполняется с остальными согласованными input/draft/budget/
protocol/factory контрактами. Threshold остаётся G4-C; sampling — G6/G7;
production wiring — G10-A.

G4-I выполнен: GEO-1 219/219 (+10), location/cascade/rasterizer 70/70;
positive typing 304 файла / 0 ошибок, negatives planning 113/113,
cascade 23/23 (+4). Freeze не вызывает resolver/policy/IO; actual runtime
world/links/provenance не передаются. Nested private values проверяет тот
же shared immutable walker. API cache/planning сохранён через import aliases;
immutable admission намеренно усилен для скрытых mutable/opaque/cyclic values.
Composition: cascade/generation по5, validation2, resolved tests2, valid5.

### Сверка с ТЗ World Snapshot (2026-10-28)

Семантически это immutable derived value, а не World Snapshot:

- tz_world_snapshot §Назначение/§Обязательные границы оставляет единственному
  WorldSnapshotService lifecycle истории, snapshot identity/lineage, применение
  PatchSet и commit/read/restore/branch. Ни одного такого API/IO здесь нет.
- Domain/application caller получает coherent source view по existing G0-S
  seam, выполняет cascade один раз и передаёт immutable результат стратегии.
  Freeze не перечитывает world/SQL, не формирует самостоятельное состояние
  мира, не создаёт snapshot UID/revision и не подтверждает freshness источника.
- Existing StateViewRevision и PlanRef по-прежнему обеспечивают согласованность
  planning inputs/dependencies; freeze их не заменяет и не пересчитывает.
  Связь с captured view сохраняет owning caller G8/G10-A, не cascade helper.
- tz_cascade_context §GEO-1 G0-A явно называет CascadeRuntimeContext рабочим
  transient state, не serialized snapshot. Его состояние не сериализуется
  новым API: результат содержит только declared resolved values/provenance.
  §Инварианты «consumer не резолвит» и обязательный provenance сохраняются.

Предыдущее имя snapshot_context слишком близко к термину World Snapshot;
предложение уточнено до freeze_resolved_context. В API/ТЗ результат называть
«immutable результат каскада», без отдельного snapshot lifecycle. Добавление
такого результата — расширение tz_cascade_context и изменение G4 input.context,
поэтому требовалось отдельное согласование; оно получено 2026-10-28 («Далее»).
Соответствие WS-инвариантам само по себе не заменяет расширение cascade ТЗ.

G5-CP binding result: HydrologyPlacementBinding (frozen dataclass), application
hydrology/policy/hydrologyPlacementBinding.py: spec + PolicyInputs + PolicyFacts;
producer bind_hydrology_placement_policy, consumer existing PolicyResolver caller.
WaterPlacementPolicySource = WaterDesignSource | DeclaredCoastline, dataModel
hydrology/policy/hydrologyPlacementPolicy.py; normalized typed source input only.

G5-CP implementation clarification: field metadata сохраняет identity основного
placement descriptor. Target-bound compound support case компилируется отдельно
с explicit priority/facts models (без field metadata); его RequireSupport rule
добавляется к основному compiled spec. Оба используют compile_admission_policy;
verifier identity checks и executor не меняются, rule IDs создаёт compiler.

G5-CP выполнен: GEO-1 338/338 (+28), existing placement/water/factory80/80,
positive Pyright0, negative153/153 (+5). Captured typed binding и facts;
final-fill mapping producer/adapter activation остаются следующим owning шагам.
