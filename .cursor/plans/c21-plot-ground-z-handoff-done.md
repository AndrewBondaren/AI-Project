# C21 — бриф для агента с чистым окном ✅ DONE

Скопируй блок **«Промпт»** в **новый чат**. Этот файл — SoT брифа; план имплементации не дублируй сюда целиком.

Связанное: [c21-plot-ground-z-done.md](./c21-plot-ground-z-done.md) · [tz_settlement_outdoor.md](../../docs/tz_settlement_outdoor.md) **C21/P13** · [tz_generator_technical_debt.md](../../docs/tz_generator_technical_debt.md) **NC-2**.

---

## Промпт

```text
Ты имплементируешь C21 / P13 в репозитории AI Project (workspace: корень репо).

Это сообщение = явная просьба писать код (no-code-until-asked снят). Коммит не делать, пока мастер не скажет «закоммить». Backend не стартовать (python start.py / uvicorn / npm run backend). DAG-ноды (application/engine/nodes/) не менять. Schema: не трогать 0001_initial.sql и не плодить 0002. Occupancy flood в assemble() не чинить. HTTP/orchestrator persist outdoor не переписывать.

Целевая архитектура ЦЕЛИКОМ (не слайс «сначала только door / всегда здание / bbox=участок»). Порядок работ = слои плана §4, не вертикальный кусок одной улицы.

Не переоткрывать замки продукта. Если сомнение — план и ТЗ, не «упростить».

════════════════════════════════════
1. ПРОЧИТАТЬ СНАЧАЛА (в этом порядке)
════════════════════════════════════

План (контракты, слои, файлы, приёмка):
  .cursor/plans/c21-plot-ground-z-done.md
  — целиком §0–§7. Особенно §2.0 (кто что считает), §2.2b (parcel/NC-2/забор), §2.2c (helpers луча), §4 (порядок), §5 (файлы), §6 (приёмка).

Продукт:
  docs/tz_settlement_outdoor.md        — C21, P13; extract C20 front только если есть здание
  docs/tz_structure_connections.md     — §5.1.1 луч (только при Δz), §5.1.2 θ / clamp map_z ↑↓ / материалы; C10 клетки дороги в SQL не обязательны
  docs/tz_assembler_hierarchy.md       — §6.2 ground_z; §7.1 AreaSlot / AreaThreshold / StreetApproach / AreaLayout; §7.2 assemble(); §7.3 helpers vs методы
  docs/tz_generator_technical_debt.md  — NC-2 (замок: не DEFAULT_PARCEL_MARGIN_M на PerimeterBarrier)
  docs/tz_locations.md                 — perimeter_barrier = template + probability (без отступа)

Правила репо (не нарушать):
  .cursor/rules/layer-boundaries.mdc
  .cursor/rules/dataModel-no-hardcode.mdc
  .cursor/rules/architecture-first.mdc
  .cursor/rules/documentation-layout.mdc
  .cursor/rules/bulk-sql.mdc           — массовые SQL только если тронешь persist; этот pass скорее нет

Не читать целиком (только по необходимости):
  mill discover / _rim_shots / Q1 — assembler участка НЕ импортирует relief/discover
  tz_terrain_relief.md — только partition_height / geom_resolve как нарезка z на ГОТОВОМ луче
  settlement-outdoor-pack-done.md — persist/HTTP уже сделаны; не re-architect

════════════════════════════════════
2. ЗАМКИ (не спорить)
════════════════════════════════════

Z:
  Район НЕ выравнивает участки. DistrictSlot.ground_z = пин NL, не пол домов.
  AreaSlot.ground_z = двор (median колонок выбранных клеток). packing НЕ копирует z района на слот.
  building.map_z ≠ slot.ground_z допустимо. После place НЕ писать map_z = slot.ground_z.
  θ > 45°: только map_z (или threshold.z без дома). Формула clamp_near_z_to_45.
  Дом выше улицы → опустить; ниже → поднять. XY дома не двигать. Pack land не резать (C1).
  Луч порог→улица ТОЛЬКО если slot.ground_z ≠ z примыкающей улицы; иначе form=NONE, без grade/clamp на hop.
  Hop дверь↔ворота: луч только если building.map_z ≠ z порога. Один measure_street_approach, разные аргументы.
  z улицы для peek: клетка ПОЛОТНА ребра (street_xy), не узел-перекрёсток (block_size 50/80/120 — алгоритм сетки, так и задумано).

Участок / забор (NC-2):
  AreaSlot.cells и collision packing = один parcel (footprint + двор). Не bbox occupied_footprint.
  PARCEL_GAP_M = щель МЕЖДУ участками, не глубина двора.
  Забор = периметр уже готовых slot.cells. НЕ expand_bbox. Удалить DEFAULT_PARCEL_MARGIN_M (это не поле PerimeterBarrier).
  yard_depth_m в шаблон в этом pass НЕ вводить; padding — константа packing в areaSlots.
  kind порога: door | gate | parcel_edge. gate на ребре УЧАСТКА, не bbox дома.
  Здание опционально. Extract: C20 «нет front» только если building есть.

Луч:
  Свой walk_grid_ray в generators/coordinates/. Не звать mill / measure_terrain_descent из area assembler.
  Mill: обернуть measure_terrain_descent своим stop НА walk_grid_ray (тот же helper-слой).
  ≤30°: partition_height / geom_resolve на клетках луча, CITY_STRUCTURE, не ReliefGradeInstance, не location_terrain.
  30–45°: лестница (канон 45° ⇔ h=L).
  Материалы §5.1.2 (онтология порога + тир), не литерал камня.

Слои:
  DTO без методов «построить луч». assemble() только оркестрация, без atan/median/шага сетки.
  _build_paths = только граф. Клетки входа = stamp_approach_cells.
  _resolve_threshold НЕ принимает street_xy.
  StructureContext.ground_z = building.map_z после clamp, не slot.ground_z.
  translate_layout(dx, dy, dz); cache interior @ z=0 без фундамента/крыши; envelope на place.

════════════════════════════════════
3. КОД СЕЙЧАС (баги, которые чинить)
════════════════════════════════════

Копирование одной z:
  backend/app/application/worldData/generators/assemblers/settlementAssembler/planner/terrain.py
    resolve_ground_z = max(z) AABB → сузить до resolve_district_pin_z (поверхность origin)
  backend/app/application/worldData/generators/assemblers/settlementAssembler/planner/districts.py
    пишет slot.ground_z с resolve_ground_z
  backend/app/application/worldData/generators/assemblers/districtAssembler/planner/areaSlots.py
    _make_area_slot(..., slot.ground_z) — packing не должен задавать финальный z участка
    cells = только footprint bbox — NC-2

Улицы на пине:
  backend/app/application/worldData/generators/road/layouts/gridLayout.py  (z = slot.ground_z)
  Проверить peers: culDeSacLayout.py, courtyardLayout.py, organicLayout.py, radialLayout.py
  backend/app/application/worldData/generators/assemblers/settlementAssembler/planner/streets.py
  Порядок DistrictAssembler: СЕЙЧАС areas ПОТОМ streets — надо packing → streets → rasterize_street_xy → area assemble
    backend/app/application/worldData/generators/assemblers/districtAssembler/districtAssembler.py

Place / cache / translate:
  backend/app/application/worldData/generators/assemblers/areaAssembler/structureAreaAssembler.py
    derive_structure_context игнорирует terrain_cells; map_z=slot.ground_z; translate только xy
  backend/app/application/worldData/generators/structure/layoutTranslate.py  — нет dz
  backend/app/application/worldData/generators/assemblers/settlementAssembler/buildingCache.py
  backend/app/application/worldData/generators/assemblers/structureAssembler/buildingAssembler.py
    _build_terrain_surface — заменить на общий column_surface

Забор workaround:
  backend/app/dataModel/settlement/area/perimeterBarrier.py  — DEFAULT_PARCEL_MARGIN_M
  backend/app/dataModel/settlement/area/__init__.py         — export
  backend/app/application/worldData/generators/assemblers/areaAssembler/planner/areaBarriers.py
    expand_bbox(..., DEFAULT_PARCEL_MARGIN_M)

Extract (C20 на двор без дома упадёт):
  backend/app/application/worldData/settlementOutdoor/settlementOutdoorExtract.py
    «has no front entry»; AreaLayout.building_* сейчас обязательны
  backend/tests/test_settlement_outdoor_extract.py
  collect_connection_graph: settlementLayoutExtract.py — добавить GraphLevel.AREA с участка

Mill (обёртка, не перенос логики в area):
  backend/app/application/worldData/generators/terrain/relief/geom/terrainDescent.py
  backend/app/dataModel/spatial/facing.py  — GRID_OUTWARD_DELTA
  backend/app/application/worldData/generators/terrain/relief/geom/geomResolve.py  — partition_height

════════════════════════════════════
4. КОМАНДЫ РАЗВЕДКИ (сделай до/во время кода)
════════════════════════════════════

Grep (Cursor Grep или rg из корня репо):

  resolve_ground_z
  _make_area_slot
  translate_layout
  _build_terrain_surface
  DEFAULT_PARCEL_MARGIN_M
  PARCEL_GAP_M
  slot.ground_z
  map_z=slot.ground_z
  class AreaLayout
  class AreaSlot
  has no front entry
  collect_connection_graph
  measure_terrain_descent
  partition_height
  GRID_OUTWARD_DELTA

Проверить все road layouts на z узла.
Не стартовать сервер. Тесты: существующий backend/tests/test_settlement_outdoor_extract.py + новые под C21 (helpers, parcel ≠ bbox, skip луча, clamp ↑↓, gate→waypoint, extract без здания).

После правок dataModel — не оставлять мёртвый export DEFAULT_PARCEL_MARGIN_M.

════════════════════════════════════
5. ПОРЯДОК КОДА = план §4
════════════════════════════════════

1. coordinates: walk_grid_ray, column_surface, median_surface_z, classify_approach, clamp_near_z_to_45
   mill terrainDescent → walk_grid_ray + свой stop
2. translate_layout + dz (cells, rooms.map_z, levels.z, passages xy, footprint xy)
3. cache interior @ z=0, без foundation/roof
4. attach_envelope; derive_structure_context читает terrain_cells; ground_z = building.map_z после clamp
5. улицы: node.z = column_surface[(x,y)]; rasterize_street_xy (RAM, width_cells + sidewalk; НЕ SQL C10)
6. packing: parcel_cells; collision = тот же rect; не копировать DistrictSlot.ground_z в AreaSlot как пол
7. DistrictAssembler: packing → streets → street_xy → StructureAreaAssembler.assemble(..., street_xy=)
8. area planner: resolveThreshold (без street_xy), measureApproach, stampApproach, areaPaths только граф
   areaBarriers: ring(slot.cells), удалить DEFAULT_PARCEL_MARGIN_M
9. assemble() оркестрация по assembler §7.2; AreaLayout optional building + threshold + approach + graph
   extract: area graph; C20 только если дом
10. тесты; P13/NC-2 в ТЗ closed только если мастер просит править статус в docs — иначе оставь open/план

Новые файлы — как план §5 (имена не плодить вторые column_surface / areaThreshold.py в двух смыслах: DTO vs planner resolveThreshold.py).

════════════════════════════════════
6. ГОТОВО КОГДА
════════════════════════════════════

Чеклист плана §6. Плюс: grep не находит DEFAULT_PARCEL_MARGIN_M; packing cells шире footprint; mid-block peek не требует узел; равные z → нет луча; θ>45 поднимает и опускает map_z; xy дома тот же.

Если упрёшься в продукт (не в код) — спроси мастера, не изобретай слайс.

Отчёт в конце: что сделано по слоям §4, какие тесты, что сознательно не тронуто.
```

---

## Карта чтения (шпаргалка)

| Зачем | Файл | Что смотреть |
|---|---|---|
| Контракт impl | `.cursor/plans/c21-plot-ground-z-done.md` | §2, §4, §5, §6 |
| Онтология z / порог | `docs/tz_settlement_outdoor.md` | **C21**, **P13** |
| Луч, θ, clamp, материал | `docs/tz_structure_connections.md` | **§5.1.1–§5.1.2** |
| DTO / assemble | `docs/tz_assembler_hierarchy.md` | **§6.2, §7.1–§7.3** |
| Parcel / забор | `docs/tz_generator_technical_debt.md` | **NC-2** |
| Barrier wire | `docs/tz_locations.md` | `perimeter_barrier` |
| Живой баг z района | `…/settlementAssembler/planner/terrain.py` | `resolve_ground_z` |
| Живой баг packing | `…/districtAssembler/planner/areaSlots.py` | `_make_area_slot` |
| Порядок района | `…/districtAssembler/districtAssembler.py` | areas до streets |
| Translate | `…/structure/layoutTranslate.py` | нет `dz` |
| Extract C20 | `…/settlementOutdoor/settlementOutdoorExtract.py` | front обязателен |
| Mill stop | `…/relief/geom/terrainDescent.py` | обёртка на луч |
| Grade нарезка | `…/relief/geom/geomResolve.py` | `partition_height` |
| Шаг сетки | `…/dataModel/spatial/facing.py` | `GRID_OUTWARD_DELTA` |

## Не делать

- Слайс door-only / «пока всегда здание» / cells=bbox «потом NC-2»
- Импорт `relief/discover` из area assembler
- Новая колонка SQL / `0002_*.sql`
- `yard_depth_m` на `PerimeterBarrier`
- Сдвиг дома в xy «к улице»
- Старт backend, коммит без просьбы, правки DAG-нод
