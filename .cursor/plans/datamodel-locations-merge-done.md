# Мердж домена в `dataModel/locations/` — атомарный план ✅ done

Статус: выполнен полностью (M0–M3, 2026-10-04). Дата: 2026-10-04.
Основание: решение мастера 2026-10-04 — «settlement отдельно, structure
отдельно, locations отдельно, хотя это один домен». `dataModel/cascade/`
уже вынесен мастером как домен-нейтральный механизм — не входит в scope.

**Правило мастера:** старое не удаляется, пока новое не перенесено.
Механика — `git mv` (новый путь и содержимое появляются до удаления
старого, история файлов сохраняется); пустые каталоги уходят в том же
шаге, после rewrite импортов и проверок. Ни один коммит/состояние не
оставляет висячих ссылок на `app.dataModel.settlement` /
`app.dataModel.structure`.

## Границы

- Только module path'ы. Wire-ключи, SQL schema, FS-layout
  `structures_templates/` / `relief_templates/`, содержимое файлов —
  без изменений.
- `dataModel/cascade/` — не трогаем (домен-нейтральный).
- `dataModel/connections/` — не трогаем (дороги/граф — отдельный домен;
  если мастер захочет под зонтик — отдельное решение).
- Три `enums/` поддомена (locations, settlement, structure) НЕ
  смешиваются — разные наборы, остаются при своих пакетах.
- `locations/__init__.py` — только docstring; re-export'ы поддоменов
  вверх не дублируются (двойная публичная поверхность не нужна).
- Один шаг за заход; после каждого — отчёт и ожидание «ок».

## Старая структура (факт 2026-10-04)

```text
backend/app/dataModel/
  locations/                          # домен: идентичность + типы + ctx
    __init__.py
    context/__init__.py
    context/cascadeParams.py          # ECONOMIC_TIER + input_types
    context/locationContext.py        # LocationContext
    context/scopeLevel.py             # ScopeLevel — локационная ось
    enums/__init__.py
    enums/borderCategory.py
    enums/entryRole.py
    enums/geographicSubtype.py
    locationFootprintPolicy.py
    locationType/__init__.py
    locationType/locationTypeEntry.py
    locationType/locationTypeSubtypeEntry.py
    locationType/worldLocationTypeRegistry.py
    namedLocation/__init__.py
    namedLocation/bundleNamedLocation.py
  settlement/                         # 31 файл — ТО ЖЕ ДОМЕН
    __init__.py                       # re-export всего поддомена
    area/__init__.py
    area/perimeterBarrier.py
    district/__init__.py
    district/allowedStructureTypes.py
    district/cellZone.py
    district/districtConnection.py
    district/districtTemplateEntry.py
    district/districtTopologySlot.py
    district/frontageTypeOrder.py
    district/placementCondition.py
    district/requiredStructure.py
    district/requiredStructureResolve.py
    district/structurePlacement.py
    district/worldDistrictTemplateRegistry.py
    district/worldDistrictZonePreference.py
    enums/__init__.py
    enums/districtDensity.py
    enums/districtEntryRole.py
    enums/districtStreetRole.py
    enums/requiredStructurePosition.py
    settlement/__init__.py
    settlement/locationMoodEntry.py
    settlement/settlementFootprint.py
    settlement/settlementSizeEntry.py
    settlement/settlementSkeleton.py
    settlement/settlementSpecializationBind.py
    settlement/settlementSpecializationEntry.py
    settlement/typicalDistrictRef.py
    settlement/worldLocationMoodRegistry.py
    settlement/worldSettlementSizeRegistry.py
    settlement/worldSettlementSpecializationRegistry.py
  structure/                          # 50 файлов — ТО ЖЕ ДОМЕН
    __init__.py                       # re-export всего поддомена
    barrier/__init__.py
    barrier/barrierTemplateEntry.py
    barrier/worldBarrierTemplateRegistry.py
    building/__init__.py
    building/buildingBodyTemplate.py
    building/buildingCatalog.py
    building/buildingTemplateOutline.py
    building/buildingTemplateRegistryEntry.py
    building/buildingTemplateRoomSlot.py
    building/levelDef.py
    building/occupiedFootprint.py
    building/plotLayoutTemplate.py
    building/roomConnection.py
    building/staircaseSpec.py
    building/structureCatalog.py
    building/structureTemplate.py
    building/worldBuildingLayoutDefaults.py
    building/worldBuildingTemplateRegistry.py
    enums/__init__.py
    enums/attachWall.py
    enums/buildingContext.py
    enums/buildingElement.py
    enums/buildingPurpose/__init__.py
    enums/buildingPurpose/catalog.py
    enums/buildingPurpose/craft.py
    enums/buildingPurpose/cultivation.py
    enums/buildingPurpose/culture.py
    enums/buildingPurpose/defense.py
    enums/buildingPurpose/diplomatic.py
    enums/buildingPurpose/dwelling.py
    enums/buildingPurpose/extract.py
    enums/buildingPurpose/factory.py
    enums/buildingPurpose/family.py
    enums/buildingPurpose/government.py
    enums/buildingPurpose/harbor.py
    enums/buildingPurpose/husbandry.py
    enums/buildingPurpose/knowledge.py
    enums/buildingPurpose/logistics.py
    enums/buildingPurpose/packs.py
    enums/buildingPurpose/process.py
    enums/buildingPurpose/public.py
    enums/buildingPurpose/purposePackEntry.py
    enums/buildingPurpose/trade.py
    enums/buildingPurpose/transit.py
    enums/buildingPurpose/utility.py
    enums/buildingPurpose/worldPurposePackRegistry.py
    enums/buildingPurpose/worldPurposePacks.py
    enums/entryAccessType.py
    enums/passageType.py
    enums/roomSize.py
    enums/staircaseSize.py
    enums/staircaseType.py
    materialPick.py
    room/__init__.py
    room/entryPoint.py
    room/roomDef.py
    room/roomTypeEntry.py
    room/shapeParams.py
    room/sizeSpec.py
    room/wallOpeningSpec.py
    room/worldRoomTypeRegistry.py
```

## Новая структура

```text
backend/app/dataModel/
  cascade/                            # вне scope (мастер вынес)
  locations/                          # КОРЕНЬ ДОМЕНА «локации»
    __init__.py                       # docstring обновлён: umbrella-домен
    context/                          # без изменений
      __init__.py
      cascadeParams.py
      locationContext.py
      scopeLevel.py
    enums/                            # без изменений
      __init__.py
      borderCategory.py
      entryRole.py
      geographicSubtype.py
    locationFootprintPolicy.py        # без изменений
    locationType/                     # без изменений
      __init__.py
      locationTypeEntry.py
      locationTypeSubtypeEntry.py
      worldLocationTypeRegistry.py
    namedLocation/                    # без изменений
      __init__.py
      bundleNamedLocation.py
    settlement/                       # ← git mv dataModel/settlement
      __init__.py  area/  district/  enums/  settlement/
      # все 31 файл, внутренняя раскладка без изменений
    structure/                        # ← git mv dataModel/structure
      __init__.py  barrier/  building/  enums/  room/  materialPick.py
      # все 50 файлов, внутренняя раскладка без изменений
```

## Rewrite-правила

| Было | Стало |
|---|---|
| `app.dataModel.settlement.` | `app.dataModel.locations.settlement.` |
| `app.dataModel.settlement` (bare, без точки) | `app.dataModel.locations.settlement` |
| `app.dataModel.structure.` | `app.dataModel.locations.structure.` |
| `app.dataModel.structure` (bare) | `app.dataModel.locations.structure` |

Правила применяются к **любому** текстовому вхождению в
`backend/**` (import-строки, строковые литералы module-path в
patch/assertLogs/docstring-путях) — префикс уникален, ложных срабатываний
нет. Relative imports (`from .x import`) не затрагиваются.

Затрагиваемые файлы (факт по grep `app\.dataModel\.(settlement|structure)\b`):
**195 файлов** — `app/dataModel/**` (внутренние `__init__.py` и
кросс-ссылки), `app/application/**`, `app/api/**`, `app/db/**`,
`app/dataModel/worldPack/locationsIndexWire.py`, `tests/**`,
`scripts/debug_settlement.py`.

Пути вне кода (входят в зачистку шага M3, не блокируют импорты):
`docs/tz_building_generator.md`, `tz_generator_technical_debt.md`,
`tz_city_generation_technical_debt.md`, `tz_pojo_city_typing.md`;
активные `.cursor/plans/` (`cascade-context-resolution-done.md`,
`structure-wall-materials.md`, `unified-staircase-placement.md`,
`race-height-clearance.md`, `city-t-5n-5o-structure-split.md` и др.
НЕ-done). Файлы `*-done.md` — история, не переписываются.

## Атомарные шаги

### M0 — Документация доменного layout (только docs)
- **Цель:** зафиксировать SoT раскладки до кода (gate-2: шаг без
  раздела ТЗ не готов).
- **ТЗ:** [docs/tz_locations.md](<E:/AI Project/docs/tz_locations.md>) —
  добавить раздел «Package layout»: `dataModel/locations/` — корень
  домена (`context`, `namedLocation`, `locationType`, `enums`,
  `settlement`, `structure`); `dataModel/cascade/` — домен-нейтральный
  механизм, не часть домена.
- **Файлы:** `docs/tz_locations.md`.
- **Проверка:** ревью мастера.
- **Done:** раздел существует; M1/M2 ссылаются на него.

### M1 — `settlement/` → `locations/settlement/`
- **Цель:** перенести поддомен settlement под корень домена.
- **ТЗ:** tz_locations.md §Package layout (M0).
- **Файлы:** `git mv backend/app/dataModel/settlement
  backend/app/dataModel/locations/settlement`; rewrite
  `app.dataModel.settlement` → `app.dataModel.locations.settlement`
  во всех файлах (77 файлов, включая внутренние `__init__.py` и
  `dataModel/__init__.py` строки 78–109).
- **Контракт:** имён/экспортов/полей не меняется; публичная поверхность
  `from app.dataModel import X` сохраняется.
- **Проверка:** `compileall backend/app`; grep `app.dataModel.settlement`
  (без `locations.`) → пусто; unit-набор settlement/district
  (`test_settlement_*`, `test_district_*`, `test_city_three_axes`,
  `test_loc_t2_*`, `test_placement_condition`,
  `test_perimeter_barrier_sides`, `test_street_layout`,
  `test_registry_key`); `git diff --check`.
- **Done:** старый путь недостижим, тесты зелёные.
- **Выполнен 2026-10-04:** `git mv` + rewrite 77 файлов; residual grep
  пуст; compileall чист. 2 pre-existing ошибки
  `test_settlement_topology` (`structure … not found`) воспроизведены
  на чистом HEAD — с переносом не связаны.

### M2 — `structure/` → `locations/structure/`
- **Цель:** перенести поддомен structure под корень домена.
- **ТЗ:** tz_locations.md §Package layout (M0).
- **Файлы:** `git mv backend/app/dataModel/structure
  backend/app/dataModel/locations/structure`; rewrite
  `app.dataModel.structure` → `app.dataModel.locations.structure`
  (~152 файла, включая `dataModel/__init__.py` строки 110–131).
- **Контракт:** как M1.
- **Проверка:** `compileall backend/app`; grep → пусто; U-гейт
  structure (`test_u_shape_orientation_baseline`, `test_u_shape_facing`,
  `test_structure_orientation`, `test_debug_structure_rotations`,
  `test_embedded_shaft`, `test_embedded_upper_layout`, `test_shaft_walls`)
  + `test_building_purpose`, `test_room_def`, `test_room_connection`,
  `test_structure_template`, `test_plot_layout`,
  `test_location_context_contract`, `test_context_extend`,
  `test_cascade_context_baseline`; `git diff --check`.
- **Done:** старый путь недостижим, тесты зелёные.
- **Выполнен 2026-10-04:** `git mv` + rewrite 153 файлов; residual grep
  пуст; compileall чист. Найденная и исправленная регрессия:
  `worldBuildingLayoutDefaults.py` использует
  `Path(__file__).parents[N]` до `fixtures/templates` в корне репо —
  глубина выросла на 1, `parents[5]` → `parents[6]` (rewrite импортов
  такие пути не покрывает; единственный `parents[` в перенесённом
  дереве). Полный sweep 1243 теста: 5 failures + 23 errors — **дословно
  тот же набор**, что на чистом HEAD (pre-existing: LevelDef-фикстуры
  building_purpose/plot_layout, settlement_topology, hydrology,
  map_cell_persist и др.) — регрессий от переноса нет.

### M3 — Зачистка и приёмка
- **Цель:** финальная консистентность ссылок и полный прогон.
- **ТЗ:** tz_locations.md §Package layout.
- **Файлы:** `locations/__init__.py` docstring; пути в
  `docs/tz_*.md` и активных `.cursor/plans/*.md` (список выше);
  `*-done.md` не трогаем.
- **Проверка:** полный `python -m unittest discover tests`;
  `compileall backend/app`; финальный grep по всему репо
  `dataModel[./](settlement|structure)` — только done-планы и
  комментарии-история; `git diff --check`.
- **Done:** домен собран под `locations/`; план получает суффикс `-done`.
- **Выполнен 2026-10-04:** docstring `locations/__init__.py` →
  umbrella-домен; rewrite путей в 4 `docs/tz_*`, 4 активных планах и
  8 `.agents/skills/*/SKILL.md` (живые `/impl-*` инструкции). Полный
  sweep 1243 теста — набор падений дословно совпадает с чистым HEAD
  (все pre-existing). Residual grep по репо: только `*-done.md`,
  `.local/` scratch и исторические разделы этого плана.
