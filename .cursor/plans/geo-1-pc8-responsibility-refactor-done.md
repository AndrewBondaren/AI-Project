# PC-8 — согласованный план разделения ответственностей [done]

Статус: **DONE (2026-10-23)** — целевые ответственности и контракты
зафиксированы по указанию мастера; R1–R5 исполнены, реализация принята
мастером.
Основной SoT: geo-1-designed-water.md §6.31-D/E/F и §7 PC-8.
ТЗ: docs/tz_terrain_generation.md §PC-D/PC-E/PC-F;
docs/tz_map_light_bake.md §PC-0 frozen surface plans.
PC-8: DONE. PC-8C открыт. R1–R5 выполнены и приняты.
Согласованные cached phase/payload contracts остаются прежними.
Нормативная карта реализации синхронизирована с
[tz_terrain_generation.md §PC-D1](../../docs/tz_terrain_generation.md#pc8-responsibility-boundaries).
Данная карта заменяет прежнее размещение всей domain logic в provider
module только для PC-8; описание старой реализации не является target.

## 1. Архитектурная граница

Provider владеет только адаптацией общего planning lifecycle к доменному
API: require dependency envelopes, проверка exact upstream refs, вызов
одного доменного assembly API. Cache/keys/refs остаются общему engine и
provider boundary; тело доменного алгоритма не получает PlanRequest,
PlanDependencyReader, RegisteredPlanContract, PlanEnvelope или PlanRef.

Доменная assembly знает порядок публичных операций, но не их реализацию.
Она не получает PreparedRiver, FineRiverSampling, SurfaceHeightmap,
AssembledWater или MaterializedWater, не назначает UID, не фильтрует
BasinSpec по policy, не выбирает retained samples/receiver/roles.
Владельцы операций возвращают immutable typed results.

PlanBuildResult[T] переиспользуется как существующий immutable result
(payload, diagnostics). Это осознанный общий return contract application
сборки, не cache envelope. Новый одинаковый Result[T] не создаётся.
Использование PlanBuildResult не даёт доменному компоненту доступа к
registry/cache/key/ref. Промежуточные results не регистрируются в cache.
PlanBuildControl используется только как публичный cancellation contract.

## 2. Точная карта исполняемых классов

Все application пути ниже относительно
backend/app/application/worldData/generators/.
Конструкторы получают перечисленные collaborators через DI. World/SQL/
pack чтение запрещено. Существующие алгоритмы переиспользуются.

### 2.1 HydrologyRoutesPlanProvider — существующий, изменить

Файл: hydrology/planning/hydrologyPlanProvider.py.
Слой application, владелец hydrology planning integration.
Ответственность: подключение routes-stage к общему planning protocol.

Методы:
- __init__(relief: RegisteredPlanContract[ReliefPlanInput, ReliefPlan],
  water_placement: RegisteredPlanContract[WaterPlacementInput, WaterPlacementPlan],
  assembler: HydrologyRoutesAssembler).
- build(request: PlanRequest[HydrologyPlanInput],
  dependencies: PlanDependencyReader, control: PlanBuildControl)
  -> PlanBuildResult[HydrologyRoutesPlan].
- _require_refs(relief: PlanEnvelope[ReliefPlan],
  water: PlanEnvelope[WaterPlacementPlan]) -> None: exact upstream ref check.

build вызывает require(RELIEF), require(WATER_PLACEMENT), _require_refs,
assembler.assemble(world_uid=request.key.world_uid, inputs=request.inputs,
relief=relief.payload, placement=water.payload, control=control).
Возвращает готовый PlanBuildResult без domain postprocessing.

### 2.2 HydrologyFinalPlanProvider — существующий, изменить

Тот же файл и слой; ответственность: final-stage integration.
Методы:
- __init__(relief: RegisteredPlanContract[ReliefPlanInput, ReliefPlan],
  hydrology_routes: RegisteredPlanContract[HydrologyPlanInput, HydrologyRoutesPlan],
  river_relief: RegisteredPlanContract[RiverReliefInput, RiverReliefPlan],
  assembler: HydrologyFactsAssembler).
- build(request: PlanRequest[HydrologyFinalInput],
  dependencies: PlanDependencyReader, control: PlanBuildControl)
  -> PlanBuildResult[HydrologyPlan].
- _require_refs(relief: PlanEnvelope[ReliefPlan],
  routes: PlanEnvelope[HydrologyRoutesPlan],
  river: PlanEnvelope[RiverReliefPlan]) -> None:
  exact relief/routes refs, без cell/geometry проверок.

build вызывает require трёх slots, _require_refs, затем
assembler.assemble(inputs=request.inputs, relief=relief.payload,
routes=routes.payload, river=river.payload, control=control).

### 2.3 HydrologyRoutesAssembler — новый

Файл: hydrology/planning/assembly/hydrologyRoutesAssembler.py.
Слой application; владелец: гидрология, последовательность routes-stage.
Ответственность: согласовать результаты публичных hydrology operations.

Методы:
- __init__(water: WaterBodyPlanner, coarse: CoarseRiverPlanner,
  fine: FineRiverPlanner, paint: DeclaredWaterPaintProjector).
- assemble(*, world_uid: EntityUid, inputs: HydrologyPlanInput,
  relief: ReliefPlan, placement: WaterPlacementPlan,
  control: PlanBuildControl) -> PlanBuildResult[HydrologyRoutesPlan].

Последовательность: water.plan -> coarse.plan -> fine.plan -> paint.project.
Параллелизм не вводится. На границах фаз — control.raise_if_shutdown().
Собирает HydrologyRoutesPlan из готовых полей intermediate payloads,
объединяет их уже классифицированные diagnostics в этом порядке,
дедупликация existing issue semantics. Диагностика не читает наружный ctx.
Чтение именованных публичных DTO fields — часть контракта; раскрытие
внутренних buffers/jobs/samplers запрещено.

### 2.4 WaterBodyPlanner — новый

Файл: hydrology/water/planning/waterBodyPlanner.py.
Слой application; владелец hydrology water bodies.
Ответственность: получить принятый open-water plan на pre-river surface.

Методы:
- plan(*, world_uid: EntityUid, inputs: HydrologyPlanInput,
  surface_z: tuple[tuple[SurfaceGridCoord, FineZ], ...],
  placement: WaterPlacementPlan, control: PlanBuildControl)
  -> PlanBuildResult[OpenWaterPlan].
- _select_specs(inputs, specs: tuple[BasinSpec, ...]) -> tuple[BasinSpec, ...]:
  единственный владелец existing scopes/enabled/category admission этого path.
- _require_surface(surface_z, topology, z_min, z_max) -> None:
  canonical/full extent и world z validation.

plan строит собственный local SurfaceHeightmap, вызывает existing
assemble_water_bodies с existing policy projection. Только этот класс
разворачивает AssembledWater/MaterializedWater в OpenWaterPlan. Disabled/
исключённые scopes дают корректный пустой OpenWaterPlan, а не fake terrain.
UID/levels/unions algorithms остаются existing water kernels, не копируются.

### 2.5 CoarseRiverPlanner — новый

Файл: hydrology/rivers/planning/coarseRiverPlanner.py.
Слой application; владелец coarse river route planning.
Ответственность: принятые coarse routes и их occupancy/drainage claims.

Методы:
- plan(*, world_uid: EntityUid, inputs: HydrologyPlanInput,
  surface_z: tuple[tuple[SurfaceGridCoord, FineZ], ...],
  water: OpenWaterPlan, control: PlanBuildControl)
  -> PlanBuildResult[CoarseRiverPlan].

plan вызывает public prepared declare/request/route kernels, затем
baseline procedural producer и route kernel для auto candidates.
Владение policy последовательностью declare-before-auto — здесь.
Procedural UID/classification принадлежат existing
hydrology/autoresolve/proceduralRiverAutoresolve.py: новый pure public
prepare_procedural_river_requests(world_uid, seed, policy, surface,
occupied, topology, span) -> tuple[RiverRouteRequest, ...].
Он объединяет existing plan_prepared_river_network, classification,
UID formula и request conversion. Формула UID не находится в planner.

Existing riverPrepare.py получает public route-only API
plan_prepared_routes[S](..., to_coordinate: Callable[[Coord], S],
control) -> PlanBuildResult[RiverRouteBatch[S]].
Его typed inputs перечисляются ниже; PreparedRiver и build_profiles=False
становятся внутренними деталями route owner. Вызвавший planner не читает
job.segments/specs и не формирует claims вручную.

### 2.6 FineRiverPlanner — новый

Файл: hydrology/rivers/planning/fineRiverPlanner.py.
Слой application; владелец fine river route planning.
Ответственность: fine routes и retained pre-river samples на заданном extent.

Методы:
- plan(*, world_uid: EntityUid, inputs: HydrologyPlanInput,
  surface_z: tuple[tuple[SurfaceGridCoord, FineZ], ...],
  water: OpenWaterPlan, coarse: CoarseRiverPlan,
  control: PlanBuildControl) -> PlanBuildResult[FineRiverPlan].

Последовательность принадлежащих fine planning действий: fine_topology,
sample_prepared_fine_river_input -> prepared_declared_river_requests ->
FineRiverSampling.sample_requests -> plan_prepared_routes[FineXY] ->
FineRiverSampling.output_heightmap. Working sampler известен только этому
владельцу. Retained set сохраняет existing accepted + rejected authored
route samples и unchanged cells; не только изменённые river beds.
Coarse claims читаются через CoarseRiverPlan, без post-carve высот.
Fine процедурный source search/HY-RIV-1 не включаются.

### 2.7 DeclaredWaterPaintProjector — новый

Файл: hydrology/load/paint/declaredWaterPaintProjector.py.
Слой application; владелец authored hydrology geometry projection.
Ответственность: authored declarations -> immutable declared paint.

Методы:
- project(*, rivers: tuple[DeclaredRiver, ...],
  coastlines: tuple[DeclaredCoastline, ...], lakes: tuple[DeclaredLake, ...],
  anchors: tuple[HydrologyAnchorInput, ...])
  -> PlanBuildResult[DeclaredWaterPaint].
- _intent_path(river, anchors: Mapping[EntityUid, FineXY])
  -> tuple[FineXY, ...] | None: полный authored anchor path, без reroute.
- _segments(loaded: LoadedDeclaredHydrology, ctx: ResolveContext)
  -> tuple[SegmentRiverPaint, ...]: width/segment projection;
  ctx принадлежит вызову project и собирает issues локально.

Existing load_prepared_declared_hydrology используется только за public
project/plan boundary; assembler/provider не получает LoadedDeclaredHydrology.
Именно сюда переезжает _paint; public result содержит typed diagnostics.
Geometry order/closure/fine-width/wire clamp остаются прежними.

### 2.8 HydrologyFactsAssembler — новый

Файл: hydrology/planning/assembly/hydrologyFactsAssembler.py.
Слой application; владелец final hydrology facts.
Ответственность: сформировать согласованные final water facts из принятых
routes и actual river relief. Не выбирать routes/bodies/levels заново.

Методы:
- assemble(*, inputs: HydrologyFinalInput, relief: ReliefPlan,
  routes: HydrologyRoutesPlan, river: RiverReliefPlan,
  control: PlanBuildControl) -> PlanBuildResult[HydrologyPlan].
- _require_coverage(inputs, relief, routes, river) -> None:
  full coarse/sampled fine coverage, canonical coordinates.
- _river_roles[S](routes: tuple[RiverRoute[S], ...],
  beds: tuple[RiverBedRecord[S], ...], surface: tuple[tuple[S, FineZ], ...],
  to_xy: Callable[[S], Coord], control: PlanBuildControl)
  -> dict[Coord, MapCellHydrology]: UID join, actual bed validation и роли.
- _require_receivers[S](routes: tuple[RiverRoute[S], ...],
  occupied: Mapping[Coord, MapCellHydrology],
  to_xy: Callable[[S], Coord]) -> None:
  actual receiver identity, включая coarse->fine projection внутри assemble.

Сюда переходят _final_roles, _receivers и domain часть final build.
Внутри _river_roles existing river_bed_roles остаётся единственным kernel
ролей; RiverSegment/RiverBedSpec — local adapters, не публичный результат.
Класс остаётся единым: coverage/UID join/receiver validation/roles/output —
операции одной ответственности, получения согласованного final state.
_require_* проверяют соответствие уже принятым данным, не выбирают новые
receiver/kind/level/flow/fallback. _river_roles только адаптирует accepted
path + actual bed к existing river_bed_roles; собственная формула ролей,
ручное создание альтернативных role rules, reroute и carve запрещены.
Если existing kernel не покрывает требуемое правило, сначала меняется
контракт/kernel его владельца, assembler не достраивает правило локально.
Structural test: patched river_bed_roles выдаёт контрольный результат,
assembler переносит его без пересчёта; contract mismatch fail-fast, без
repair/reroute. Нет автоматического дробления класса по числу методов.
Consistency failure -> PlanBuildFailure с existing FieldPathError, без
нового error taxonomy. Final не копирует upstream diagnostics.

### 2.9 Серьёзность диагностики принадлежит producer доменного решения

HydrologyDiagnosticsAdapter исключён из целевой карты. Домен возвращает
готовый PlanDiagnostic с явным disposition в момент принятия решения.
Ни один внешний компонент не восстанавливает policy по строке code.
PlanDiagnostic переиспользуется как существующий neutral immutable DTO;
параллельный DiagnosticFact(issue, disposition) не создаётся.

Точные владельцы решений:
- water/waterMaterialize.py: materialize_water решает retain/reject и
  выпускает соответствующий disposition в той же ветке решения.
- waterBodyAssembler.py: assemble_water_bodies выпускает собственные
  world/terrain-resolution diagnostics с явным disposition.
- rivers/riverPrepare.py: prepare_river_from_inputs/его diagnostic helper
  выпускают ERROR при отказе или FALLBACK при реально принятом redirect.
- load/paint/declaredWaterPaintProjector.py: projector выпускает ERROR
  одновременно с исключением некорректной authored-геометрии.

Разрешён общий formatting helper: принимает FieldPathError и уже выбранный
PlanDiagnosticDisposition, создаёт PlanDiagnostic, не читает code для
выбора disposition. Класса ради этой упаковки нет.
Existing water_issue получает keyword-only required
`disposition: PlanDiagnosticDisposition` и optional
`emit: Callable[[PlanDiagnostic], None] | None = None`.
Call sites явно передают disposition из ветки доменного решения. Existing
assemble_water_bodies/materialize_water получают тот же optional emit и
передают без интерпретации. Route preparation получает collector аналогично;
legacy RiverRouteDiagnostic сохраняется, его severity наружный adapter не
угадывает. Новые prepared paths используют collect-only и callback; existing
legacy reporting сохраняет свой sink и не получает двойного emission.
Запрещён hidden shared collector singleton или расширение ResolveContext
ради локального severity storage. Каждый вызов владеет собственным collector.

Providers и HydrologyRoutesAssembler только передают/объединяют готовые
PlanDiagnostic. Request reporter интерпретирует explicit disposition для
показа/лога, не переопределяет domain outcome. Code остаётся идентификатором
ситуации, не источником серьёзности. Новые call-site параметры и emission
проверяются на всех existing water_issue usages до изменения сигнатуры.

## 3. Новые промежуточные POJO — точные поля и владельцы

Все strict/frozen, без injected defaults; только dataModel и validators.
Не public cache schemas; версии/ids frozen PC bindings не меняются.

backend/app/dataModel/hydrology/planning/stages/openWaterPlan.py:
OpenWaterPlan(coarse_open_water: tuple[tuple[SurfaceGridCoord, MapCellHydrology], ...],
water_bodies: tuple[WaterBody, ...], physical_unions: tuple[PhysicalWaterUnion, ...]).
Producer WaterBodyPlanner; consumers CoarseRiverPlanner/FineRiverPlanner/
HydrologyRoutesAssembler.

backend/app/dataModel/hydrology/planning/stages/riverRoutePlans.py:
- RiverRouteBatch[S](routes: tuple[RiverRoute[S], ...],
  claims: tuple[tuple[S, MapCellHydrology], ...]).
- CoarseRiverPlan — type alias RiverRouteBatch[SurfaceGridCoord], не второй POJO.
- FineRiverPlan(routes: tuple[RiverRoute[FineXY], ...],
  base_surface_z: tuple[tuple[FineXY, FineZ], ...]).
Producer route kernel/CoarseRiverPlanner/FineRiverPlanner; consumers fine
planner/routes assembler. Claims содержат river occupancy/drainage, не z.

Существующие конечные HydrologyRoutesPlan, HydrologyPlan, RiverReliefPlan,
RiverRoute/RiverPathSegment/RiverBedRecord и generic planning contracts
не меняют полей/семантики. Validators intermediate POJO: unique canonical
coordinate maps, space parameter invariant, unique routes per river UID,
claims согласованы с принятыми routes, fine paths/receiver имеют samples.

Pure plan_prepared_routes[S] принимает world_uid: EntityUid, span: int,
heightmap: SurfaceHeightmap (local caller-owned), requests:
Sequence[RiverRouteRequest], claims: dict[Coord, MapCellHydrology],
topology: WorldTopology, policy: HydrologyRiversPolicy,
water_bodies: Sequence[WaterBody], resolution_mode: ResolutionMode,
z_min: FineZ, space: CoordinateSpace, to_coordinate: Callable[[Coord], S],
control: PlanBuildControl; результат PlanBuildResult[RiverRouteBatch[S]].
Kernel создаёт local diagnostic collector; classification уже принадлежит
веткам domain decisions, возвращаемый result содержит готовые diagnostics.
Private bridge сохраняет existing prepare_river_requests_from_inputs и
ResolveContext collect-only; explicit diagnostic emission собирается внутри
boundary без code-to-severity mapping. Legacy prepare_river_requests profile path делегирует прежнему
kernel и не переводится на route-only result.

## 4. Целевой граф вызовов

PlanningService -> PlanRegistry -> HydrologyRoutesPlanProvider.build
 -> HydrologyRoutesAssembler.assemble
    -> WaterBodyPlanner.plan -> existing assemble_water_bodies
    -> CoarseRiverPlanner.plan -> prepared declare/procedural/route APIs
    -> FineRiverPlanner.plan -> sampling + prepared route APIs
    -> DeclaredWaterPaintProjector.project -> prepared declaration loader
 -> PlanBuildResult[HydrologyRoutesPlan] -> общий envelope/cache.

Отдельная внешняя terrain стадия RiverReliefPlanProvider создаёт
RiverReliefPlan. Hydrology assembler/provider её не вызывает.

PlanningService -> PlanRegistry -> HydrologyFinalPlanProvider.build
 -> HydrologyFactsAssembler.assemble -> existing river_bed_roles
 -> PlanBuildResult[HydrologyPlan] -> общий envelope/cache.

Providers получают assembly collaborators в конструкторах. В PC-8
фактические вызовы собираются fixture composition; production factory
injection новых collaborators относится к PC-9A. Запрещено создавать
новые planners/samplers/cache внутри Provider.build.

## 5. Полная судьба текущих helpers hydrologyPlanProvider.py

_failure -> локальный planning failure helper у provider; domain cell
failures создаёт owning domain module, без импорта provider helper.
_coarse/_fine -> conversion helpers внутри owning domain modules;
общеиспользуемые aliases/convert уже существуют, новые классы ради них нет.
_heightmap -> private WaterBodyPlanner surface adapter для water kernel;
river planners используют собственные caller-owned heightmap adapters
с existing SurfaceHeightmap (не получают mutable water planner buffer).
_routes/_claims -> existing rivers/riverPrepare.py route-only public boundary.
_paint -> DeclaredWaterPaintProjector.project/_intent_path/_segments.
_final_roles -> HydrologyFactsAssembler._river_roles.
_receivers -> HydrologyFactsAssembler._require_receivers.
Provider.build scopes/spec filtering -> WaterBodyPlanner._select_specs.
Provider.build coarse declare/auto -> CoarseRiverPlanner.plan.
Provider.build UID formula/classification -> existing procedural owner API.
Provider.build fine sampling/retained-set -> FineRiverPlanner.plan.
Provider.build severity/code mapping -> удаляется; severity принадлежит
producer ветке domain decision по §2.9, наружу идёт готовый PlanDiagnostic.
Provider.build immutable output assembly -> HydrologyRoutesAssembler /
HydrologyFactsAssembler. Planning refs остаются только providers.

## 6. Композиция и scope

Application hydrology/planning: 2->2 flat files, добавляются подпапки
assembly (init + 2 = 3). Отдельной diagnostics подпапки/adapter нет.
water10->10, rivers15->15, load9->9 flat files; новые подпапки
water/planning2, rivers/planning3, load/paint2. Existing autoresolve2->2.
DataModel hydrology/planning2->2; новая stages3 (init + 2).
WARN existing water10/rivers15/load9 обязателен перед implementation;
переполненные roots не расширяются. Каждый executable class <=250 строк
по требованию мастера; разделение по responsibility, не по половинам файла.
Метод не превышает границу своей ответственности за счёт свободных
функций в том же module; helpers также принадлежат указанному owner.
PC-7 RiverReliefPlanProvider остаётся external typed boundary; его
внутренняя архитектура не объявляется проверенной или автоматически
исправленной этим PC-8 планом. GEO strategies/HY-RIV-1/caller activation,
SQL/DAG/backend start/commits вне scope.

## 7. Предлагаемый порядок исполнения внутри незакрытого PC-8

R1–R5 детализируют оставшуюся работу внутри PC-8, не меняя порядка
внешних фаз основного плана. Каждый срез — отдельный заход и отчёт.
Принятие архитектуры не означает выполнение этих срезов или приёмку PC-8.

R1 — промежуточные contracts.
Статус: **DONE (2026-10-23, срез R1)**. PC-8 в целом не завершён и не принят.
Созданы stages/{__init__,openWaterPlan,riverRoutePlans}.py (3 файла).
OpenWaterPlan переиспользует existing water uniqueness/map invariants.
RiverRouteBatch[S] invariant, S constrained SurfaceGridCoord/FineXY;
CoarseRiverPlan — alias того же specialization, не новый класс.
Claims имеют exact land-bed coverage и matching role/river UID/edge/drainage;
receiver исключён только из claims своей реки, parent bed при confluence
сохраняется. Shared segment boundary сохраняет existing last-published
edge metadata. FineRiverPlan проверяет все path/receiver samples и допускает
unchanged/rejected-route retained samples без принятых routes.
Все поля required strict/frozen, duplicate coordinate/UID и wrong-space
inputs rejected; new models не импортируют application/db.
Проверки: contracts69 OK (10 новых cases), pyright valid0;
negative34 exact code/location (24 argument,1 index,9 return).
Existing PlanBuildResult/PlanDiagnostic используются без нового wrapper
или severity mapping. Codec manifests/cache ids/versions/providers/algorithms
не изменены; stages не регистрируются в cache. Следующий срез — R2.
Цель: зафиксировать domain return API без mutable implementation structs.
ТЗ: tz_terrain_generation §PC-D/PC-D1 и карта классов этого документа.
Файлы: stages/{openWaterPlan,riverRoutePlans}.py и init;
существующие tests/planning/contracts/test_domain_payloads.py, typing files.
Контракт: раздел 3; existing final payloads неизменны.
Проверка: contracts suite и pyright valid/negative.
Done: strict POJO/space/UID/sample invariants; существующий PlanDiagnostic переиспользуется.

R2 — water и paint owners.
Статус: **DONE (2026-10-23, срез R2)**. PC-8 в целом не завершён.
WaterBodyPlanner.plan/_select_specs/_require_surface реализованы в
hydrology/water/planning/waterBodyPlanner.py; DeclaredWaterPaintProjector
project/_intent_path/_segments — в hydrology/load/paint/declaredWaterPaintProjector.py.
Оба класса имеют одну указанную ответственность (58/60 строк тела),
новые leaf folders по 2 файла с init; mutable kernel structs остаются внутри.
Water planner валидирует topology/full canonical surface/world z, применяет
existing scope/category admission и вызывает existing assemble_water_bodies
один раз. Возвращает frozen OpenWaterPlan без carve/live World/SQL/pack.
Paint projector сохраняет loader geometry order/closure/fine width/wire
clamp; incomplete anchors/invalid width исключают только свой объект.
Все 9 water_issue callers проинвентаризированы и передают required
explicit disposition. Кроме planned water modules, единственный caller
hydrologyGeneratorService.py получил только import/keyword ERROR (не новый
алгоритм или wiring). Emit callback в assemble_water_bodies/materialize_water
передаёт готовый PlanDiagnostic; при callback нет второго report/log,
без callback legacy collect/preview/runtime sinks сохранены.
Severity выбирается в producer ветке retain/reject/notice, не по code.
Изменение code/message при сохранённом domain outcome не меняет disposition.
Новых adapters/diagnostic DTO/registry/cache registrations нет.
Проверки: 12 новых owner cases; providers96 OK; пять обязательных
regression suites59 OK (async вне sandbox по known Windows socketpair);
hydrology extended241/242 — прежний list/tuple тест воспроизводит старый
failure, без новых failures. Pyright valid0; negative37 exact code/location
(26 argument,1 index,10 return). New paths и waterDiagnostics включены
в existing valid config; wrong inputs/results/paint declarations rejected.
Providers пока НЕ переключены: прежняя _paint/domain/diagnostic mapping
в provider module остаётся только до атомарного R4; helper не объявляется
исправленным этим срезом. New owner baseline/equality/emission проверены;
end-to-end HIT/MISS через новую assembly подтверждается в R4/R5 после
wiring. Следующий срез — R3 coarse/fine river owners.
Цель: изолировать open-water decisions и authored projection.
ТЗ: тот же §PC-D, карта 2.4/2.7.
Файлы: water/planning/waterBodyPlanner.py, load/paint/projector и init;
existing owner helpers/tests, waterBodyAssembler.py и
water/{waterDiagnostics,waterMaterialize}.py для explicit domain emission.
Название projector файла строго 2.7; water_issue call-site inventory обязателен.
Контракт: plan->PlanBuildResult[OpenWaterPlan], project->paint result.
Проверка: domain providers tests, water baseline, declarations/width/anchors;
severity устанавливается в producer, передаётся без изменений при HIT/MISS;
изменение текста/code не меняет явно заданный disposition.
Done: готовы публичные owners; provider пока не переключается частично.

R3 — coarse/fine route owners и public prepared boundaries.
Статус: **DONE (2026-10-23, срез R3)**. Общая реализация PC-8 не завершена.
Созданы rivers/planning/{__init__,coarseRiverPlanner,fineRiverPlanner}.py,
3 файла; CoarseRiverPlanner/FineRiverPlanner имеют 43/42 строки тела.
Coarse owner сохраняет declare-before-auto, читает frozen OpenWaterPlan,
получает готовые маршруты/claims через plan_prepared_routes; не импортирует
PreparedRiver/profile kernel/build_profiles switch. Public coarse result
нормализован в конкретный CoarseRiverPlan specialization.
Procedural UID/classification/request conversion находится в existing
autoresolve/proceduralRiverAutoresolve.py::prepare_procedural_river_requests;
legacy autoresolve_river_segments и frozen producer используют одну
_segments_from_paths реализацию UID/classification, без live reads в новой API.
Fine owner единолично владеет sampler, resampling/classification, fine route
preparation и retained accepted+rejected authored path samples. Coarse
claims передаются как occupancy/drainage, heights — только pre-river.
Fine procedural source discovery/HY-RIV-1 не включены.
Existing riverPrepare.py::plan_prepared_routes возвращает только frozen
RiverRouteBatch[S] + ready diagnostics, работает на копии claims, не пишет
heightmap и не строит profiles. Space/converter mismatch rejected.
Producer preparation выпускает ERROR при фактическом отказе и FALLBACK
только после принятого redirected land route; несостоявшийся redirect
не оставляет ложный FALLBACK. Callback не вызывает log/report. Legacy
PreparedRiver/profile path и diagnostic fact format сохранены.
Typed checks existing nullable request/receiver proof стали explicit
contract guards (без cast/defaults); valid baseline geometry не меняется.
Проверки: 14 новых owner cases, providers110 OK; обязательные regressions59
OK (async вне sandbox по known Windows socketpair); extended hydrology241/242,
только прежний list/tuple failure. Pyright valid0 (включая riverPrepare и
procedural owner), negative40 exact code/location (28 argument,1 index,
11 return). Проверены baseline coarse/fine/sample equality, procedural
seed/UID/path, preview/runtime, rooted tributary, wrong types/space,
unchanged caller claims/heights, no profiles/carve/live World, shutdown,
rebuild equality и независимость disposition от diagnostic code.
На момент сдачи R3 providers ещё не переключены; переключение и удаление
old domain helpers выполнены следующим срезом R4 (см. ниже).
Цель: скрыть PreparedRiver/profile switch/sampling от assembly.
ТЗ: §PC-D, карта 2.5/2.6 и раздел 3.
Файлы: rivers/planning/{coarseRiverPlanner,fineRiverPlanner}.py и init;
existing rivers/riverPrepare.py, autoresolve/proceduralRiverAutoresolve.py,
shore/fineRiverSampling.py при необходимости boundary reuse; planned tests.
Контракт: typed coarse/fine plans, существующий legacy profile path сохранён.
Проверка: river/fine/tributary/procedural baseline, determinism и no profile.
Done: route owners возвращают frozen outcomes; прежние kernels не копируются.

R4 — assembly owners и атомарное переключение обоих providers. **DONE (2026-10-23)**

**Implementation R4 (2026-10-23):** оба provider переключены атомарно.
HydrologyRoutesAssembler получает WaterBodyPlanner, CoarseRiverPlanner,
FineRiverPlanner и DeclaredWaterPaintProjector через constructor DI; вызывает
их public API в порядке water → coarse → fine → paint, проверяет shutdown
между фазами и объединяет готовую диагностику без чтения code/disposition.
HydrologyFactsAssembler проверяет coverage, actual beds и receiver identity;
единственный расчёт ролей — existing river_bed_roles. Сборщик не маршрутизирует,
не ищет воду и не изменяет высоты. Providers содержат только dependency
require, exact-ref checks и делегирование assemble с immutable payloads.
Все прежние domain helpers удалены из hydrologyPlanProvider.py; новые
assembly owners находятся в planning/assembly/ (3 файла с init).
Providers116/contracts69/regression59 OK; pyright valid0/negative42 exact
(30 argument, 1 index, 11 return). Шесть новых boundary tests проверяют
порядок/передачу public DTO, producer severity/dedup, остановку фаз,
provider delegation/ref rejection, kernel roles и структурные ограничения.
Extended hydrology241/242: прежний list/tuple failure в
BasinContractTests.test_loader_and_master_preserve_fine_geometry_and_explicit_floor.
R4 выполнен; R5 и общая приёмка PC-8 остаются, PC-8C не открыт.


Цель: оставить providers только planning boundary.
ТЗ: §PC-D/E/F, карта 2.1-2.3/2.8.
Файлы: assembly2 и init, existing hydrologyPlanProvider.py, provider fixtures.
Контракт: constructor DI + existing Provider.build; конечные payloads прежние.
Проверка: providers suite84+, baseline equality, shutdown/error/cache checks;
structural tests: provider не импортирует river/water/load/sampling kernels,
assembler не использует PreparedRiver/FineRiverSampling/AssembledWater.
Done: полный mapping раздела 5 выполнен, helpers удалены из provider module.

R5 — приёмка PC-8 и sync статуса.

**R5 — DONE (2026-10-23): техническая проверка пройдена, реализация принята мастером.**
Карта всех восьми owning classes/methods/contracts подтверждена; размеры
классов: routes provider20, final provider26, routes assembler27, facts
assembler70, water planner58, coarse planner43, fine planner42, paint
projector60 строк. Providers не содержат domain helpers; domain owners
не получают planning envelopes/requests/refs/cache. Facts используют
river_bed_roles без собственного расчёта ролей, assembler объединяет
producer diagnostics без классификации по code.
Providers118/contracts69/cache20/regression59 OK. Два новых acceptance
cases проверяют полную карту восьми owners и nonempty ERROR/FALLBACK
outcomes в runtime/preview: HIT без build, clear с rebuild, codec roundtrip,
новая composition с новыми owners и max_workers=1 вместо 2 сохраняют
весь envelope (geometry/UID/ref/diagnostics). Final не копирует upstream
issues. TTL остаётся отключённым по CachePolicy.ttl_seconds: None.
Pyright valid0; negative42 exact code/location: 30 reportArgumentType,
1 reportIndexIssue, 11 reportReturnType. Пять обязательных baseline suites
прошли; extended hydrology241/242, единственный прежний list/tuple failure
в BasinContractTests.test_loader_and_master_preserve_fine_geometry_and_explicit_floor
(test_hydrology_hy12_contract.py:103). Тест и контракт не менялись.
Cache20 повторён вне sandbox после PermissionError временного config.toml;
detailed-bake regression также вне sandbox по известному socketpair boundary.
Новые cache ids/versions, GEO algorithms, production wiring/activation,
SQL/DAG и commits не добавлены. PC-8 принят мастером (DONE 2026-10-23);
PC-8C открыт. Файл переименован с суффиксом -done при закрытии.


Цель: подтвердить границы + отсутствие baseline/cache изменений.
ТЗ: §PC-G и tz_map_light_bake §PC-0.
Файлы: existing tests/typing configs, план и normative docs.
Контракт: прежние PC handles/versions/output semantics, новая class map.
Проверка: команды основного плана §6.27; providers/contracts/5 regression
suites; positive0/negative exact code+location; cache HIT/clear/restart и
same geometry/UID/diagnostics. Известный list/tuple старого hydrology теста
остаётся явно учтённым, не скрывается успешными suites.
Done: реализация соответствует принятой карте классов и границам,
требуемые проверки пройдены, реализация принята мастером; только затем PC-8 может получить DONE и открыть PC-8C.
