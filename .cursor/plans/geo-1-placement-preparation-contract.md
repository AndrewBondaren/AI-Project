# GEO-1 G4-C — уточнение входа и ownership preparer

Статус: G4-C IMPLEMENTED/VERIFIED 2026-10-28, после APPROVED («Ок»).
Указание мастера: старые контракты не сохранять ради совместимости;
параллельный water V2 transport не вводить.
Основной шаг: geo-1-designed-water.md, G4-C; threshold — §6.29-F.
ТЗ: tz_terrain_generation §Planning и доставка GEO-1;
tz_map_light_bake §Placement P1/P2.

## Обнаруженные незамкнутые стыки

1. prepare(WaterDesignInput, draft) не получает PlacementHeader и готовый
   object-admission decision. Generation context не содержит effective_priority,
   relations или per-object placement identity. Generation region не заменяет
   эту identity. Получать их внутри preparer — обход владельцев cascade/policy/P2.
2. score_bits есть только в ContinentalNoisePolicy. PlateRecipe содержит только
   PlateGenerationPolicy. Единый threshold для plate потребует скрытый noise
   default либо новый обязательный вход, которого нет в согласованной сигнатуре.
3. WaterPlacementPreparation/PreparedWaterEntry обслуживают активный baseline:
   legacy PreparedPlacement, declared source, scalar floor. G0-P/session работают
   с PreparedPlacementV2 и готовым decision. Union с baseline размоет typed wiring;
   замена этих полей требует обновить непосредственных producers/consumers.
   Это граница миграции, а не основание сохранять старые contracts или вводить
   вторые WaterPlacementPreparationV2/PreparedWaterEntryV2.

## Согласованный контракт

Strategy input G4 не расширять admission/session настройками.
G4-C готовит geometry/candidates, G8 владеет их связыванием с admission.
Уточнённая сигнатура:
prepare(input:WaterDesignInput, draft:WaterDesignDraft,
        *, selection_policy:WaterFieldSelectionPolicy) -> WaterDesignPreparation.

DataModel/terrain/designedWater/preparation/{__init__,result}.py:
WaterDesignPreparation — strict/frozen/revalidate record результата design:
metadata:WaterSourceMetadata, pre_hydrology_ref:PlanRef,
coordinate_space:CoordinateSpace, grid:SurfaceGridSettings,
candidates:tuple[PlacementCandidate,...], original_area:OriginalArea,
floor_z:FineZ, floor_profile:BasinFloorProfile|None,
notices:tuple[FieldPathError,...].
Original area фиксируется до P2; единицы соответствуют coordinate_space
кандидатов. Quantization weights/budget по-прежнему считаются в fine².
Это результат предшествующей стадии, не второй water placement transport:
нет PreparedPlacement, admission, snapshot UID или outcome.
Preparer не создаёт header/priority/decision. Caller G8 вызывает его только
для READY admission и строит generic prepared из результата и готового decision.

DataModel/terrain/designedWater/settings/fieldSelectionPolicy.py:
WaterFieldSelectionPolicy — frozen strict record, score_bits=24 (8..30).
Перенести score_bits из ContinentalNoisePolicy, не хранить две копии.
Noise/plate/composer вычисляют signed field; selection_policy использует
только общий preparer. G8/G10-A передают record явно из captured settings;
planned GeoWaterPlacementInput дополняется selection_policy.
Defaults/ranges сохраняются, noise recipe перестаёт хранить threshold knob.

WaterDesignDecision и header/relations принадлежат подготовке admission G8,
не G4-C. Использовать object specialization с enum стратегии по §6.29-C;
готовый decision передаётся через existing PlacementAdmissionInput/session.
Early disabled/waiting/unresolved не требуют design или geometry.

## Сверка перехода water adapter с G8/G9

Фактическая цепочка:
WaterPlacementPlanProvider → run_prepared_water_placement →
prepare_water_placements → PlacementBatch/resolve_placements →
resolved_water_placements → basin_specs → WaterPlacementPlan.

G8 (J06/J07/J08) заменяет существующие PreparedWaterEntry и
WaterPlacementPreparation на целевые типы в waterTypes.py. Source —
WaterSourceMetadata, prepared — целевой generic prepared с admission decision;
floor/profile переносятся из WaterDesignPreparation. Вторые water records
с суффиксом V2 и union old/new не создаются.
Обновляются water.py, waterPlacementPass, provider/result DTO, ResolvedWaterPlacement
и непосредственные consumers одним согласованным шагом; старые constructors,
прямой baseline resolver path и imports убираются из переведённой цепочки.
Экспорт generic placement lifecycle синхронизируется с фактическим generic
cutover; несовместимость не обходить cast или восстановлением decision по priority.

В том же G8 существующий basinSpecFactory переводится механически на metadata:
source_uid/kind/liquid/level/bands читаются из неё, scalar floor — из entry.
Доступ source.location_uid/isinstance(DeclaredBasin)/повторный выбор bands из
WorldHydrology удаляется. Это обязательный consumer update нового контракта,
а не перенос field writer в G8.

G9 (J09) добавляет floor_profile в единственный BasinSpec, переносит принятый
profile из entry и обновляет единственный terrain writer. До G9 field profile
не выдаётся за поддержанный scalar floor и не отбрасывается молча; production
activation procedural поля остаётся gated полным producer→writer контрактом.
G10-A включает согласованное поведение GEO-1; не является причиной сохранять
совместимые копии старого water API. Если generic cutover требует producers
раньше G8, их перенос отдельно фиксируется в плане, без скрытого второго пути.

## Выполнение после согласования

Application terrain/designedWater/preparation/placementPreparation.py:
validation → общий quantization/prefix selection → typed candidates.
Threshold — существующий §6.29-F. Region membership/weights — через
terrain-owned coverage operations; world-space projection — water adapter.
Authored footprints не растеризуются заново и сохраняют исходный world space;
fine→coarse projection/collapse diagnostics выполняет adapter G8.
Profile переносится явно,
spec/writer остаются G9. Shortfall/collapse — явные domain issues.

G4-C/G8/G9, J06/J08/J09, §5.2/§6.29-L/M и раздел ТЗ синхронизируются до кода.
Проверки G4-C: typed/raw boundary, source/ref identity, plate без
noise dependency, quantization/prefix ties/zero/shortfall, partial region
cells, authored/profile preservation, legacy regression. Нет повторного
cascade/policy/budget, spatial resolve, z-write или World IO.

Composition G4-C: dataModel preparation2; settings4→5;
application preparation2. Adapter contracts не меняются этим шагом;
если нужны geometry projection helpers, adapter6→6 (WARN), без новых flat files.
Тесты — отдельная tests/geo1/preparation/, не расширять strategies5→6.
Exact coarse intersection areas добавляются методом RegionCoverageMeasure
в existing application/worldData/generators/terrain/regions/coverageMeasure.py
(regions4→4), без собственного measure в water preparer.
Нулевой выбранный prefix не создаёт фиктивный positive OriginalArea:
PlanBuildFailure с domain issue; early disabled quota остаётся обязанностью G8.

G4-C выполнен: GEO-1 273/273 (+22), existing placement/water/factory67/67,
positive Pyright — 0 ошибок, negative planning137/137 (+8).
Ни raw wiring, ни второй water transport не добавлены; G8/G9 сохраняют
согласованные выше обязанности по единому adapter и profile writer.
