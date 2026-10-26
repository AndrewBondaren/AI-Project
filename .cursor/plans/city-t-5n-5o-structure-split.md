# CITY-T-5n + CITY-T-5o — сплит BuildingLayoutTemplate и generate геометрии в C11

**Источник:** [`docs/tz_city_generation_technical_debt.md`](../../docs/tz_city_generation_technical_debt.md) — **5n** (P1 blocker), **5o** (P1, root cause слоёв). Один срез: сплит модели enforce-ит границу, которую лечит 5n.

**Ревизия 2026-09-28** (анализ плана против кода): очередь исполнения — §3 «Порядок исполнения» (4a перед 3c — блокер 5n не ждёт ориентацию); новые шаги 3b' (остаток band), 4c (packing через `StructureCatalog`); 4b — fallback `facing=None` вместо SOUTH (противоречие с контрактом 3c).

**Ревизия 2026-09-28 (§4.3 решено):** мастер выбрал **вариант B** — весь пайплайн в авторском фрейме, один поворот перед `_assemble_result`. 3c.1–3c.6 схлопнуты в один шаг 3c; план лестниц сокращён до S0–S2 + характеризационная защита (S3 покрыт шагом 3c-RNG). Добавлено в поля поворота: `MapCell.railing_sides` (направленное поле, упущено в первой редакции таблицы B).

**Статус решений мастера (зафиксировано):**
- `StructureAssembler`-слой = **только геометрия** (interior box + envelope). Ни участка, ни наполнения (`StructureInteriorAssembler`), ни persist.
- `StructureAreaAssembler` владеет **чертежом участка** — здания объявлены на участке.
- `PlotLayoutTemplate` владеет зданиями: `main_building` (единственный) + `secondary_buildings` (stub).
- `BuildingBodyTemplate` = envelope (тип основания/крыши/материалы/porch) + `structure`.
- **`structure` — всегда ссылка** на `StructureTemplate` в библиотеке, не inline.
- Библиотеки две: engine stdlib (`structures_templates/` паки) + world overlay (`building_templates` + `worlds.building_template_registry`).

---

## 1. Целевая модель данных

```python
# dataModel/locations/structure/building/structureTemplate.py — НОВЫЙ
class StructureTemplate(BaseModel):
    """Библиотечный объект геометрии. То, что ест StructureGeneratorService."""
    system_name:      StrictOnWire[RegistryKey[StructureTemplate]]   # uid шаблона (uuid-строка, формат проверяет POJO), глобально уникален = SQL template_uid; stem файла — §4.1 модель А
    display_name:     StrictOnWire[str]                              # человеческое имя ("Таверна малая"), НЕ уникально
    description:      DefaultOnWire[str | None] = None
    version:          DefaultOnWire[str] = "1.0"
    levels:           DefaultOnWire[list[dict]] = []                 # POJO-D-16
    staircases:       DefaultOnWire[list[dict]] = []
    connections:      DefaultOnWire[list[dict]] = []
    default_z_height: DefaultOnWire[int] = DEFAULT_Z_HEIGHT          # перенести константу из buildingLayoutTemplate.py, не второй литерал
    structure_types:  DefaultOnWire[list[BuildingPurpose]]           # назначение ЗДАНИЯ (листья); omit/[] → derived из комнат, иначе [house]; см. §4.2 и ТЗ §3.4b
    # levels[].purpose / levels[].rooms[].purpose — лист BuildingPurpose (ТЗ §3.4b); dict-поля (POJO-D-16),
    # читаются model_validator(after): derived ⊆ structure_types иначе ValidationError; семья/неизвестный ключ → ValidationError.
    # room_purposes() -> dict[room_id, BuildingPurpose]  — эффективное назначение по каскаду
    #   room ?? level ?? structure_types (комната переписывает этаж/дом), служебные комнаты не входят

# dataModel/locations/structure/building/buildingBodyTemplate.py — НОВЫЙ
class BuildingBodyTemplate(BaseModel):
    """Здание на участке: envelope + ссылка на геометрию. Участка не знает."""
    foundation_type:     DefaultOnWire[str] = "slab"    # бывший default_structure_context
    roof_type:           DefaultOnWire[str] = "gable"
    foundation_depth:    DefaultOnWire[int] = 1
    foundation_material: DefaultOnWire[str | None] = None
    roof_material:       DefaultOnWire[str | None] = None
    porch_material:      DefaultOnWire[str | None] = None
    porch_has_roof:      DefaultOnWire[bool] = False
    structure:           StrictOnWire[RegistryKey[StructureTemplate]]  # ВСЕГДА ref по uid структуры (system_name = uuid); резолв в глобальном StructureCatalog

# dataModel/locations/structure/building/plotLayoutTemplate.py — переименование + чистка
class PlotLayoutTemplate(BaseModel):
    """Чертёж участка: что на нём и где. Ничего про строительство."""
    system_name:     StrictOnWire[DrawingKey]            # RegistryKey[PlotLayoutTemplate]
    display_name:    StrictOnWire[str]
    plot_type:       DefaultOnWire[BuildingPurposeFamily] = BuildingPurposeFamily.DWELLING  # семья УЧАСТКА; omit → жилой + warning (см. §4.2)
    economic_tier / _band / _range, resource_kind / crop_kind / livestock_kind, subjects
    perimeter_barrier:   DefaultOnWire[PerimeterBarrier]
    occupied_footprint:  DefaultOnWire[OccupiedFootprintSpec | None]
    main_building:       DefaultOnWire[BuildingBodyTemplate | None] = None
    secondary_buildings: DefaultOnWire[list[BuildingBodyTemplate]] = []  # STUB
    # УДАЛЕНО: levels / staircases / connections / default_z_height / default_structure_context
```

**Маппинг миграции** (старое поле → новое место):

| Было (`BuildingLayoutTemplate`) | Стало |
|---|---|
| `levels`/`staircases`/`connections`/`default_z_height` | `StructureTemplate` (библиотека) |
| `default_structure_context` | поля `BuildingBodyTemplate` |
| `main_building: BuildingLayoutTemplate` (inline тело) | `main_building: BuildingBodyTemplate` с `structure: "<key>"` ref |
| `interior_of` ветка «root levels = body» | удалить — bare body-файл валидируется `StructureTemplate` |
| `_looks_like_plot_or_interior` / `try_building_layout` | удалить эвристику |
| `DrawingKey = RegistryKey[BuildingLayoutTemplate]` | `RegistryKey[PlotLayoutTemplate]` |
| `structure_types` на участке (листья) | `StructureTemplate.structure_types` (листья здания) + `PlotLayoutTemplate.plot_type` (семья участка). Fixtures: `plot_type` = семья primary-листа старого участка (`inn_small` → `dwelling`, `mine` → `extract`, …) |

## 2. Границы слоёв (target)

```
StructureAreaAssembler   владеет PlotLayoutTemplate: plot_has_building, порог, StructureContext(runtime)
      │  body = plot.main_building; structure = catalog.resolve(body.structure)
      ▼
BuildingAssembler        владеет BuildingBodyTemplate: envelope из полей body
      │  layout = service.generate(structure); attach_envelope(layout, body-поля + runtime context)
      ▼
StructureGeneratorService  только геометрия: generate_from_template(world, building, structure: StructureTemplate, ground_z, foundation_depth)
      ▼
StructureInteriorAssembler  отдельный epic — не этот срез
```

`coerce_building_layout` + `interior_of` в `generate_from_template` (строки 234–237) — **удалить**: сервис принимает `StructureTemplate`, участок не видит.

## 3. Шаги по слоям (не по фичам)

### Шаг 1 — dataModel
1. `structureTemplate.py`: новый POJO (см. §1).
2. `buildingBodyTemplate.py`: новый POJO.
3. `buildingLayoutTemplate.py` → `plotLayoutTemplate.py`: переименование класса, удалить body-поля и `default_structure_context`; `main_building`/`secondary_buildings` типизированы `BuildingBodyTemplate`. Оставить файл-alias или обновить все импорты (~174 usages).
4. Helpers: `interior_of(plot) → plot.main_building.structure` (ref); `plot_has_building` → `main_building is not None`; удалить `coerce_building_layout` tolerant-ветку, `try_building_layout`, `_looks_like_plot_or_interior`.
5. `DrawingKey` → `RegistryKey[PlotLayoutTemplate]`; `BuildingTemplateOutline.system_name` — DrawingKey участка (не менять смысл).
5a. **Назначение этажа/комнаты (ТЗ §3.4b, введено в срез 2026-09-26):** `StructureTemplate` — `model_validator(mode="after")`: парсить `levels[].purpose` и `levels[].rooms[].purpose` через `BuildingPurpose.from_wire` (None/omit → нет; строка-семья или неизвестный → `ValueError`); `derived` = упорядоченные уникальные эффективные purpose — каскад `room ?? level ?? structure_types` (уточнение мастера 2026-09-27: `structure_types` — дефолт дома, `level.purpose` переписывает его на этаже, `room.purpose` переписывает этаж/дом на комнате); `structure_types` задан явно и `derived ⊄ structure_types` → `ValueError` с `room_id`; `structure_types` omit/`[]` → `derived` или `[house]`. Метод `room_purposes()`. **Multi-type разводка по этажам (уточнение мастера 2026-09-27):** `len(structure_types) > 1` требует назначения по этажам; если ни один `levels[].purpose` не задан — авто-разводка `level[i].purpose = structure_types[min(i, len-1)]` (первый этаж → первый тип, последний этаж → последний) + `packing_warning` (новый `PackingReason`, uid структуры) в точке загрузки каталога — модель не логирует. Геометрия/packing `purpose` не читают. Тесты: derived-агрегация, explicit ⊇ derived ок, derived ⊄ explicit → ошибка, семья в `purpose` → ошибка, явный `null` на комнате при `purpose` этажа → служебная. Fixture: структура таверны (`inn_small` → `tavern_1`) получает `purpose: "tavern"` на уровнях 0 и 1, `cellar` — без.

### Шаг 2 — библиотека / резолв refs
6. `StructureCatalog` (рядом с `BuildingCatalog`): sync snapshot `StructureTemplate` на сборку — merge engine stdlib + world overlay. Pattern как `BuildingCatalog` — caller гидрирует, не live SQL. Состав источников — по решению §4 «Хранение».
7. **Schema-решение мастера** (варианты и рекомендация — §4 «Хранение»). По policy — правка `0001_initial.sql` + sync `db/models`, recreate БД.
8. Engine stdlib структур: **новый** domain root `structures_templates/{pack}/{system_name}.json`, stem == system_name (правило `template-pack-layout`). Сейчас корня нет — stdlib живёт в `fixtures/templates/*.json` через хардкод-список `_PACKING_STEMS` в `worldBuildingLayoutDefaults.py`. Загрузчик — копия паттерна `reliefTemplateFsImport.py` (`resolve_*_domain_root` + env override), не второй хардкод-список stems.

### Статус шагов 1–2 (2026-09-27)

Шаги 1, 2, 5a — **сделаны** одним заходом (нарушение `plan-before-code.mdc` п.2 — не повторять). Ревью диффа дало 5 замечаний → шаг 2b. Дальше — **один шаг за заход**: отчёт → «ок» → следующий. Пп. 9–18 ниже — исходная формулировка (история); действующая разбивка — таблицы 2b … 6.

### Порядок исполнения (ревизия 2026-09-28)

Сделано: 1, 2, 2b, 3a, 3b, 3b', 4a, 4c, 3c-RNG, 5a. Осталось — в этом порядке, номера шагов сохранены как имена, **не** как очередь:

| # | Шаг | Почему здесь |
|---|---|---|
| 1 | **3c** — `StructureOrientation` + один поворот перед `_assemble_result` (§4.3 = **вариант B**, решено 2026-09-28) | на уже работающем пайплайне; лестницы — только S0–S2 (S3 = 3c-RNG, сделан) |
| 2 | **4b** — fit-check + fallback `facing=None` + wiring `context.facing` | требует 3c |
| 3 | **5**, **6** | приёмка |

**2026-09-29:** 3b' — коммит `eda606e`; 4a + 4c + 3c-RNG — одним коммитом `edb16a7` (нарушение «один шаг за заход», как для 1+2+5a — зафиксировано, не повторять). Прогон `StaircaseValidator`/door/archway по всем 13 stdlib-структурам (`structures_templates/base/`): generate без exception, но **36 ERROR-строк** — разбор и детали в §7 п.11. Попутно найден и закрыт латентный баг — §7 п.10.

Критерий «`main_entrance` на стороне `slot.facing`» (шаг 5) проверяется только после 3c/4b; smoke §6 (`200`, `districts=1`, `buildings>0`) — после 4a.

### Шаг 3b' — остаток регресса band

| | |
|---|---|
| Цель | Материалы стен/пола комнат и шахт видят `building_band`: `utils/materialResolver.resolve_room_materials` хардкодит `building_band=None`, хотя сервис band уже проводит |
| ТЗ | `tz_building_generator.md` §8.5b (band → материалы) |
| Файлы | `generators/utils/materialResolver.py` (параметр `building_band: str \| None = None`, литерал убрать); call sites `room/roomFactory.py:146`, `staircase/shaftFactory.py:112` — передать band, который сервис уже держит в `_instantiate_rooms` |
| Контракт | `resolve_room_materials(world, room_tier, template_tier, rng, room_id="", building_tier=None, template=None, *, building_band=None)`; `TierResolver.resolve(..., building_band=building_band)` |
| Проверка | `python -m unittest tests.test_building_assembler tests.test_city_three_axes`; grep `building_band=None` по `generators/` — только сигнатуры-дефолты |
| Done | **Сделано 2026-09-29** (eda606e): band проведён в `resolve_room_materials` → `roomFactory`/`shaftFactory` из `_instantiate_rooms`; `test_building_assembler` расширен (rich→`high_stone`, poor→`low_stone`, None→`median_stone`, явный tier перекрывает band, band доходит до комнат и шахт); grep `building_band=None` в `generators/` чист |

### Шаг 2b — правки по ревью слоёв 1–2

| | |
|---|---|
| Цель | Закрыть замечания ревью до генераторов: дубль uid не затирается тихо; dataModel не импортирует application; мёртвые модули и fixtures-тела убраны |
| ТЗ | `tz_building_generator.md` §5.1 (дубль `system_name` = ошибка; тот же uid повторно = update in-place); правила `layer-boundaries.mdc`, `template-pack-layout.mdc` |
| Файлы | `dataModel/locations/structure/building/structureCatalog.py`; `dataModel/locations/structure/building/worldBuildingLayoutDefaults.py` + `assemblers/settlementAssembler/planner/buildingDefaults.py`; удалить `dataModel/locations/structure/building/buildingLayoutTemplate.py`, `defaultStructureContext.py`; удалить `fixtures/templates/tavern_1.json`, `tavern_2.json`, `manor_1.json` (тела уже в `structures_templates/base/`) |
| Контракт | `StructureCatalog.__init__`: дубль `system_name` → `ValueError` (uid + оба `display_name`); docstring «later wins» убрать. Warning о `_PACKING_STEMS`/canonical эмитит `assemble_building_catalog` (application); loader в dataModel только грузит |
| Проверка | `python -m unittest tests.test_structure_template tests.test_plot_layout tests.test_city_three_axes tests.test_c24_district_packing`; `compileall app`; grep: нет импортов удалённых модулей; нет `app.application` внутри `dataModel/` |
| Done | новый тест «дубль uid → ValueError» зелёный; 4 набора зелёные; grep пустой |

Post-fix (2026-09-27): grep-проверка 2b покрыла `app/`, но не `scripts/` — `scripts/debug_settlement.py` держал импорт `BuildingLayoutTemplate` в `test_phase_area_barriers`. Исправлено: `PlotLayoutTemplate` без legacy-поля `structure_type` (валидатор `_reject_legacy_body_wire` рейзит); кейс прогнан, зелёный.

### Шаг 3a — ТЗ sync под контракт генератора (только текст)

| | |
|---|---|
| Цель | Зафиксировать в ТЗ контракт §2 плана до кода: сервис получает `StructureTemplate` + `facing` + `building_band`; `StructureAssembler.assemble` — body + structure; контекст из body + runtime; generate на посадке |
| ТЗ | `tz_building_generator.md` §9 (сигнатура), §11 вводка, §11.1 (`StructureContext` + `facing`/`ground_z`/`building_band`), §11.4 (интерфейс), §11.6 (`default_structure_context` → поля `BuildingBodyTemplate`); `tz_assembler_hierarchy.md` §2 (три слоя), §6.1, §6.5, §6.8, §7.2, **§7.7** («generate-first, place-second» → «envelope для packing, generate на посадке», решение §4.0; fit-check) |
| Файлы | только `docs/` |
| Контракт | сигнатуры — как в 3b/3c/4a ниже; **band идёт через `StructureContext.building_band`**, не отдельным параметром `assemble` |
| Проверка | §2 плана против правленых разделов — расхождений нет |
| Done | **сделано 2026-09-27**: 11 разделов ссылаются на `StructureTemplate`/`BuildingBodyTemplate`, `facing`, `building_band`; §7.7 не противоречит §4.0 |

### Шаг 3b — `generate_from_template(structure, building_band)` + `BuildingAssembler.assemble(body, structure)`

| | |
|---|---|
| Цель | Закрыть регресс `economic_tier_band` (сейчас `building_band=None` захардкожен в 4 местах сервиса) и провести body через ассемблер |
| ТЗ | `tz_building_generator.md` §9, §11.4 (после 3a); §8.5b (band → материалы) |
| Файлы | `generators/structure/structureGeneratorService.py`; **rename слоя здания** (решение 2026-09-27, ТЗ hierarchy §2): пакет `assemblers/structureAssembler/` → `assemblers/buildingAssembler/`, `BaseStructureAssembler` → `BaseBuildingAssembler`, `ASSEMBLER_REGISTRY` → `BUILDING_ASSEMBLER_REGISTRY`; ABC — сигнатура контракта, `context: StructureContext` вместо `object`; все kind реестра: `buildingAssembler.py`, `ruinsAssembler.py`, `vastHullAssembler.py`, `resourceExtractionAssembler.py`; `assemblers/structureAssembler/structureContext.py` (+`building_band`); `generators/utils/tierResolver.py` (`band_from_template(PlotLayoutTemplate)` удалить — band приходит параметром); call sites `assemble`/`attach_envelope` (area `structureAreaAssembler.py:333`, `routes/debug.py`, тесты) |
| Контракт | `generate_from_template(world, building, structure: StructureTemplate, *, ground_z, foundation_depth, building_band: str \| None = None)`; `StructureContext.building_band: str \| None = None` (новое поле, ТЗ §11.1); `BuildingAssembler.assemble(world, building, body: BuildingBodyTemplate, structure: StructureTemplate, context: StructureContext, terrain_cells)` передаёт `context.building_band`; area заполняет `building_band=plot.economic_tier_band` в `derive_structure_context`; `attach_envelope` без изменений; `facing` в этом шаге **не** добавляется |
| Проверка | `python -m unittest tests.test_city_three_axes` + тесты по grep `generate_from_template` в `tests/`; `compileall` |
| Done | **Сделано 2026-09-27**: пакет `buildingAssembler`, ABC и четыре kind переведены на body + structure + `StructureContext`; envelope в `BuildingAssembler` берётся из body без мутации runtime-контекста. Band проходит из plot через context во все четыре resolve сервиса; debug route принимает опциональный `building_band`; `band_from_template` удалён. `tests.test_building_assembler` (5 тестов: реальные материалы для rich/poor/None, приоритет явного tier, body/runtime, реестр, прямой generator) + `tests.test_city_three_axes` — 48 тестов; `tests.test_plot_layout`, `tests.test_c24_district_packing`, `tests.test_structure_template` — 41 тест; всё зелёное. `compileall app tests`, import smoke debug/foundation/roof, `git diff --check` — OK; grep старых импортов и `building_band=None` в сервисе пустой. Facing и generate на посадке не менялись. **Остаток (найдено 2026-09-28):** `utils/materialResolver.resolve_room_materials` хардкодит `building_band=None` (вызовы `roomFactory.py:146`, `shaftFactory.py:112`) — материалы комнат/шахт band не видят → шаг 3b' |

### Шаг 3c-RNG — детерминированный угол лестницы + один helper `det_uuid`

**Решение мастера (2026-09-28):** рандом лестницы — от seed мира + uid конкретного здания (+ id лестницы): уникален для объекта, повторяем между прогонами. Реализация — вариант 2 (sub-RNG на лестницу, не общий `rng` сервиса: угол не должен зависеть от порядка потребления RNG другими builders). Helper — **общий для всех сущностей с детерминированными uid**, вне домена `generators/` целиком: `app/utils/` (там уже живёт `graph.py`).

| | |
|---|---|
| Цель | Убрать единственный глобальный `random.choice` в `generators/structure/` (`uShapeHelper._compute_fr_anchor:89`); консолидировать 6 копий формулы `uuid5(NAMESPACE_DNS, "\|".join(parts))` в один helper уровня `app/utils` |
| ТЗ | `tz_staircase_generation.md` §6 «Якоря (только u_shape)» (выбор угла — при уже известном facing; состав кандидатов, предпочтение свободного угла, fallback на второй, `prev_fr_anchor` — **не меняются**); `tz_building_generator.md` §9 (детерминизм: same world + building → same layout) |
| Файлы | **новый** `app/utils/deterministicIds.py`; `staircase/uShape/uShapeHelper.py` (`_compute_fr_anchor`, `_compute_u_params` — параметр `rng: Random`), `staircase/uShape/uShape.py` (создание sub-RNG, вызов `_compute_u_params`); замена локальных копий на импорт: `generators/structure/structureGeneratorService.py:90` (`_det_uuid(namespace, *parts)`), `generators/structure/passages/shared.py:17`, `generators/structure/passages/staircaseTunnelOrchestrator.py:27`, `generators/structure/staircase/builder.py:33`, `generators/structure/staircase/surfaceCorridor.py:26`, `settlementOutdoor/settlementOutdoorUids.py:11` (`_uuid5`). **Не трогать:** `_make_seed` (`structureGeneratorService.py:94`, md5 — смена формулы поменяет всю существующую геометрию); `building_template_uid`/`relief_template_uid` (`NAMESPACE_URL`, другая формула — уходят в §7 п.8) |
| Контракт | `det_uuid(*parts: str) -> str` = `str(uuid5(NAMESPACE_DNS, "\|".join(parts)))` — побайтово совпадает со всеми шестью копиями (вариант с `namespace` в сервисе — тот же результат при передаче namespace первым part), **значения uid не меняются**; `scoped_rng(*parts: str) -> random.Random` = `Random(det_uuid(*parts))`. В u_shape: `rng = scoped_rng(building_uid, staircase_id, "fr_anchor")`, `rng.choice(choices)` вместо `random.choice`. Модуль `app/utils/deterministicIds.py` — только stdlib, без импортов из `app.application`/`app.dataModel` |
| Проверка | `python -m unittest tests.test_city_three_axes tests.test_building_assembler tests.test_c24_district_packing` (outdoor uids не изменились); новый `tests/test_deterministic_ids.py`: `det_uuid("a","b") == str(uuid5(NAMESPACE_DNS, "a\|b"))`; `scoped_rng(*p).random() == scoped_rng(*p).random()`; два generate одного `(world, building)` → одинаковый `fr_anchor` и одинаковые клетки лестницы; другой `location_uid` → допускается другой угол; grep `random\.` в `generators/structure/` пустой, `def _det_uuid` / `def _uuid5` в `app/` — пустой |
| Done | **Сделано 2026-09-29** (edb16a7): новый `app/utils/deterministicIds.py` (`det_uuid`, `scoped_rng` — только stdlib); 6 копий формулы `uuid5` заменены импортом; `random.choice` → `rng.choice` в `_compute_fr_anchor` через `scoped_rng(building_uid, staircase_id, "fr_anchor")`; `_make_seed` (md5) и `NAMESPACE_URL`-uids не тронуты; `tests/test_deterministic_ids.py` — побайтовая совместимость формулы, replay, независимость потоков, generate×2 идентичен, глобальный `random` запрещён патчем; grep `random.` в `generators/structure/` и `def _det_uuid`/`def _uuid5` в `app/` чист |

### Шаг 3c — `StructureOrientation` + один поворот перед `_assemble_result` (вариант B)

**Ревизия 2026-09-28 (решение мастера):** §4.3 → **вариант B**. Весь пайплайн работает в авторском фрейме шаблона; общий поворот — один проход над runtime-продуктами до сборки `StructureLayout` в `_assemble_result` (`structureGeneratorService.py:647`, вызов :273). Подразделы 3c.1–3c.6 первой редакции **отменены**: orientation-aware builders, `inverse_point`-tie-breaks, `oriented_footprint` не нужны — весь выбор и маршруты остаются в исходном фрейме бесплатно. Публичный контракт `facing` (кардиналы, pivot, требование входа) сохранён без изменений — он относится к входу generate, а не к точке поворота.

| | |
|---|---|
| Цель | `generate_from_template(..., facing: Facing \| None = None)`; явный cardinal — главный вход смотрит на `facing`; `None` — авторский фрейм (поведение V1 из 4a) |
| ТЗ | `tz_building_generator.md` §9 (facing-контракт: убрать временное равенство `None`/SOUTH, описать pivot, cardinal-only, требование одного входа), §8.6–§8.7 (фаза поворота перед сборкой результата; footprint по финальным cells), §8.8 (passages); `tz_city_generation.md` §6.3 (facing участка) |
| Файлы | **новый** `generators/structure/structureOrientation.py`; `structureGeneratorService.py` (вычисление `quarter_turns` + вызов поворота перед `_assemble_result`); `api/routes/debug.py` (эндпоинт эмуляции поворотов, ниже); `tests/test_structure_orientation.py` |
| Контракт | `StructureOrientation(pivot: tuple[int, int], quarter_turns: int)` — immutable runtime, не POJO и не SQL-поле; `point`/`inverse_point`/`vector`/`facing`, четверть-обороты 0…3, `(dx,dy) → (−dy,dx)` (east=+X, north=+Y). Один проход: `cells_dict` — ключи `(x,y)` и `MapCell.x/y` + `system_facing` + **`railing_sides`** (список граней — поворачивать каждый; `display_facing` генерацией структур не заполняется — проверено, при появлении маппить через `Facing`); `passages` — `to_x/to_y`, `from_x/from_y` (поля facing у `LocationPassage` нет — проверено); `all_rooms` — `origin`, `width`↔`depth` при нечётных оборотах, `extra_cells`. `NamedLocation` комнат создаются внутри `_assemble_result` уже повёрнутыми. uid, room_id, stops, материалы, `is_bidirectional`, `display_name` не преобразовывать. `occupied_footprint` — из повёрнутых cells |
| Условия входа | только кардиналы через `CARDINAL_FACINGS`, диагональ → `GenerationError` до генерации (voxel-мир); явный `facing` требует ровно один размещённый `main_entrance` (нет/несколько → `GenerationError` с uid структуры и room_id кандидатов); `quarter_turns` = разница `entry_point.wall` главного входа → `facing`, не безусловный поворот от SOUTH; pivot — исходный `origin` комнаты главного входа, вычислен один раз; `StructureTemplate` не мутируется |
| Проверка | `python -m unittest tests.test_structure_orientation tests.test_u_shape_orientation_baseline tests.test_vertical_ladder_orientation_baseline tests.test_building_assembler tests.test_city_three_axes tests.test_c24_district_packing`; `python -m compileall -q app tests` |
| Done | четыре стороны; `generate(facing=F)` ≡ поворот `generate(facing=None)` — по cells (координаты, `system_facing`, `railing_sides`), passages (обе точки), rooms (`map_x/y` + размеры) и `occupied_footprint`; 4×90° = identity; дверь на стороне `facing`; детерминизм seed сохранён; `layoutTranslate.py`, packing, `BuildingLayoutCache` не тронуты |

**Инструмент эмуляции поворота (debug API, требование мастера 2026-09-28).** **Отдельный** эндпоинт в `routes/debug.py` — не расширение и не замена существующего `generate-structure` (:44): тот остаётся инструментом для **одной структуры** (`StructureTemplate` на вход, один layout на выход), этот — отдельный инструмент для **участка** (`PlotLayoutTemplate` → 4 поворота). Паттерн (JsonResolver, синтетический `NamedLocation`, log-capture, `render_all_levels`) переиспользуется, route-дублирование допустимо по объёму — два инструмента, два входа.

| | |
|---|---|
| Endpoint | `POST /debug/worlds/{world_uid}/generate-structure-rotations` — вход **участок**: `PlotLayoutTemplate` JSON (file/path, как существующий route) **или** `plot_uid` из `building_templates`. `main_building is None` → 422 (площадь — не здание). Существующий `generate-structure` **не менять** — он остаётся для голой структуры |
| Резолв | `body = plot.main_building`; `structure = StructureCatalog(world).resolve(body.structure)` → None → 422; синтетический `NamedLocation` как в существующем route (`map_x/y/z` из query) |
| Эмуляция | 4 вызова `generate_from_template(world, building, structure, facing=N/E/S/W)` — структурный уровень, envelope не применяется (он строится в мировом фрейме после поворота и на ориентацию не влияет); лог-capture на вызов, как сейчас |
| Ответ | по каждой стороне: `summary`, `rooms`, `passages`, `cells`, `occupied_footprint`, `grids` (ASCII `render_all_levels`, маркеры входа — как существующий route), `warnings`; плюс `equivalence` — автосверка «вариант ≡ R(None-варианта)» по правилам `test_structure_orientation` (cells/passages/rooms/footprint), чтобы инструмент сразу показывал расхождения, а не только картинки |
| Ошибки | `GenerationError` на одной стороне (нет `main_entrance`, диагональ не подаётся) → статус `error` внутри варианта, остальные стороны возвращаются |

**Синхронизация ТЗ до кода, в начале шага:** `tz_building_generator.md` §9, §8.6–§8.7 — как в строке «ТЗ». Расхождения docs/code, найденные при разборе 3c (порядок `connect_corridors` vs passages в `tz_corridor_connect.md`; §3.10 vs §3.11 про окна шахт; подземность `level.z < ground_z` вместо `< 0`), к ориентации при варианте B отношения не имеют — перенесены в шаг 5.

**Лестницы при варианте B:** builders работают в исходном фрейме, адаптации не требуется — их геометрия поворачивается общим проходом вместе с cells/passages/shaft-инстансами. Отдельный план [city-t-5n-5o-staircase-orientation.md](city-t-5n-5o-staircase-orientation.md) сокращён до S0 (семантика facing в ТЗ), S1–S2 (характеризационные baseline-тесты — защита от регресса, проверяются внутри `test_structure_orientation`); S3 покрывается шагом 3c-RNG (sub-RNG `scoped_rng`, решение мастера), S4–S10 отменены.

**Граница 3c:** механика поворота и её доказательство тестом. Публичный `facing` из `StructureContext` и fit-check — 4b; generate на посадке — 4a.

### Шаг 4a — area: generate на посадке (фикс 5n)

| | |
|---|---|
| Цель | `StructureAreaAssembler.assemble`: place → resolve structure → generate → порог по реальному `main_entrance`. Убрать `_cache_has_rooms`-ветку; `_shell_layout` **удалить** — после generate-on-place потребителей нет (площадь = участок без `main_building`, клеток здания не имеет — см. решение мастера ниже). **V1 ориентации:** `facing` в генератор не передаётся (авторский фрейм шаблона); дверь может смотреть не на улицу — принято до 3c/4b, тот же компромисс, что fallback 4b |
| ТЗ | `tz_assembler_hierarchy.md` §7.2, §7.7 (после 3a); `tz_structure_connections.md` §5.1 (порог, `_build_paths`); `tz_city_generation.md` Фаза 2 C11, §11.5 |
| Файлы | `assemblers/areaAssembler/structureAreaAssembler.py` (`assemble`, `derive_structure_context` → shim над body, `_runtime_footprint`); `planner/resolveThreshold.py` не меняется; call site передаёт `StructureCatalog` |
| Контракт | порядок: `bx/by, fp = plot.occupied_footprint` → `building = _place_building(...)` → `body = plot.main_building; structure = structure_catalog.resolve(body.structure)` → `context = StructureContext(из полей body, ground_z=building.map_z, building_band=plot.economic_tier_band, facing=None)` → `layout = BuildingAssembler.assemble(world, building, body, structure, context, terrain_cells)` → `entry_xy = _entry_xy_world(layout)` → `resolve_threshold(slot, entry_xy=…, house_cells=fp_cells)` → approach/clamp (блок п.12 истории **без** `rotate_structure`/fit-check — это 3c/4b); `structure_catalog.resolve(body.structure) is None` → `GenerationError` → 422 с `plot`/`structure`; при `clamp` — `translate_layout(layout, 0, 0, dz)`; `BuildingLayoutCache` не трогать; `cached_layout`-параметр `assemble` удалить (для зданий смысла нет, площадь клеток не имеет — два пути не плодить). **Маппинг ошибок (решение мастера 2026-09-27, вариант A):** `GenerationError` — `RuntimeError`, route ловит только `SettlementOutdoor*`; на границе area/orchestrator (`PackingJob.run_queue` при вызове assemble) `except GenerationError → SettlementOutdoorError` → существующий `_http_from_outdoor` → 422. Без этого будет 500 |
| Проверка | `python -m unittest tests.test_city_three_axes tests.test_c24_district_packing` + C11-тесты (grep `StructureAreaAssembler` в `tests/`) |
| Done | **Сделано 2026-09-29** (edb16a7): `_cache_has_rooms`, `_shell_layout`, `cached_layout` удалены; `structure_catalog` — обязательный параметр `assemble`; нерезолв `body.structure` → `GenerationError` → `SettlementOutdoorError` на границе `PackingJob` → 422; порог резолвится в реальный `main_entrance` (`_entry_xy_world` читает layout в world-координатах); clamp — `translate_layout(0,0,dz)` + `replace(context, ground_z=clamped)`; `facing` в генератор не передаётся (V1, тест фиксирует `NotIn("facing")`); `tests/test_structure_area_assembler.py` — 5 тестов (порог=дверь, uid комнат разные на двух посадках, площадь без геометрии, нерезолв → GenerationError, clamp z-only). Smoke §6 — ещё не прогнан (шаг 6) |

### Шаг 4b — fit-check + fallback в авторский фрейм + wiring facing

| | |
|---|---|
| Цель | `BuildingAssembler` передаёт `context.facing = slot.facing` в генератор (wiring из бывшего 3c.6); `layout.occupied_footprint ⊆ slot.cells`; не влезло → `packing_warning` + повторный generate с `facing=None`; и так не влез → `GenerationError` → 422 |
| ТЗ | `tz_city_generation.md` §6.3 (резервация footprint в фрейме шаблона); `tz_assembler_hierarchy.md` §7.7 warning-политика; `tz_building_generator.md` §9 (контракт `facing=None`) |
| Файлы | `structureAreaAssembler.py` (или helper `areaAssembler/fitCheck.py`, если `assemble` > 60 строк); `assemblers/buildingAssembler/buildingAssembler.py`, `api/routes/debug.py` (cardinal `facing`); `tests/test_building_assembler.py` + новый тест |
| Контракт | `fit_or_fallback(generate: Callable[[Facing \| None], StructureLayout], slot) -> StructureLayout`; fallback-ориентация — **`facing=None`** (авторский фрейм шаблона = фрейм `plot.occupied_footprint`, dims совпадают по построению); warning через `packingLog.packing_warning` с `plot`, `structure`, `facing` |
| Проверка | `python -m unittest tests.test_city_three_axes tests.test_building_assembler` + новый тест |
| Done | тест: неквадратный чертёж, EAST не влезает → `None` + warning; `None` не влезает → 422 с именами; `main_entrance` на стороне `slot.facing`, когда влезло |

**Решение мастера (2026-09-27):** fallback — не 180°/NORTH. После fallback дверь может смотреть не на улицу района — принято, покрывается `packing_warning`; правильное решение — резервация в фрейме facing (§7 п.1).

**Правка 2026-09-28:** первоначальный fallback «всегда SOUTH» противоречил контракту 3c (явный SOUTH = направление входа, угол = разница с `entry_point.wall`): для шаблона с входом на EAST явный SOUTH — поворот на 90°, footprint с резервацией **не** совпадёт. Фрейм резервации (`parcel.py:68`, `areaSlots.py:118`) — фрейм шаблона, т.е. `facing=None`. Если авторский вход шаблона — SOUTH, оба варианта совпадают.

**Caveat (проверено 2026-09-28):** слот всегда строится в фрейме шаблона (`make_area_slot` → `parcel_cells(fp, bx, by, …)`, `areaSlots.py:72`, :110–118 — `fp.width × fp.depth`, `facing=SOUTH` захардкожен). Поэтому **неквадратный** footprint при 90°-facing (EAST/WEST) гарантированно не влезает → всегда fallback `None`. До §7 п.1 facing=EAST/WEST реально работает только на квадратных чертежах — критерий шага 5 «`main_entrance` на стороне `slot.facing`» проверять с этой оговоркой. Смежный pre-existing дефект: `Reservation.rotated_90` (`types.py:94`, `pass2.py:89`) **теряется** в `placements_from_reservations` — слот собирается без учёта поворота резервации → `slot.cells` может не совпадать с фактическим reserved-rect. В срезе не чинить (fit-check читает slot.cells, они самосогласованы с фреймом шаблона), записано в §7 п.1.

### Шаг 4c — packing: листья здания через `StructureCatalog` (§4.2)

| | |
|---|---|
| Цель | Источник листьев для разметки района — структура, не участок: `resolve_leaves(plot) = structure_catalog.resolve(plot.main_building.structure).structure_types`; без `allowed` на районе — дефолт `plot.plot_type ∈ expand(штамп семьи)`. Участок без здания → листьев нет (площадь — по `plot_type`) |
| ТЗ | `tz_city_generation.md` §9.2 (`allowed_structure_types` матчит через участок), §6.3; `tz_building_generator.md` §2.1 (семья ≠ пак) |
| Файлы | `districtAssembler/planner/tokens.py` (pool/required/fill — сейчас `catalog.structure_types()` из `BuildingCatalog`), `settlementAssembler/planner/districts.py`, `frontage.py` (`is_plaza` — по `plot_type == PUBLIC`, решение мастера §4.2), `BuildingCatalog.of_structure_type/matching_allowed/structure_types()`, `buildingCache.py:184` лог; call site сборки каталогов — `StructureCatalog` гидрируется вместе с `BuildingCatalog` и передаётся в district-planner |
| Контракт | `BuildingCatalog` не хранит листья участка; листья приходят через `StructureCatalog`, переданный в конструктор `BuildingCatalog` (один способ; альтернативу с `Callable` не делать). Нерезолвимый `structure`-ref в разметке → `GenerationError` (тот же путь → 422, что 4a) |
| Проверка | `python -m unittest tests.test_c24_district_packing tests.test_city_three_axes` |
| Done | **Сделано 2026-09-29** (edb16a7): `BuildingCatalog(layouts, structures)` — листья через `structures.leaves_of(plot)`; explicit `allowed` приоритетнее specialization-штампа (`districts.slot_allowed_for_template`); без `allowed` на районе — фильтр `plot.plot_type ∈ families(expand(штамп))`; `is_plaza` = `plot_type==PUBLIC` включая участки со зданием; upfront-`GenerationError` на нерезолвимый `structure`-ref в `tokens.py`; `StructureCatalogPackingTest` — 6 тестов (structure-despite-family, stamp-фильтр, приоритет explicit, нерезолв → ошибка, strict/world-pack, plaza) |

### Шаг 5 — docs sync + тесты приёмки

| | |
|---|---|
| Цель | Документы и тесты соответствуют коду после 2b–4b |
| ТЗ | `tz_building_generator.md` §1–2 (термины `plot_type`/`structure_types`; «Участок: главное здание» — ref-модель), §5.1–5.2 (модель А, uuid `system_name`), §3.10 vs §3.11 (окна шахт — код обрабатывает, §3.11 говорит пропускать), §3.11 (подземность = `level.z < ground_z`, не `< 0`); `tz_pojo_city_typing.md`; `tz_city_generation.md` §9.2 (`allowed_structure_types` матчит через участок); `tz_corridor_connect.md` «Порядок выполнения в пайплайне» (ТЗ ставит connector до passages, код — после; зафиксировать порядок кода, не переделывать связность) + «Алгоритм / Шаг 3» (connector добавляет cells, не `_RoomInstance`); `tz_staircase_generation.md` §8.1 (условие тоннеля — ground-relative); `template-pack-layout.mdc` — **таблица доменов сейчас отдаёт корень `structures_templates/` участкам (`building_templates`)**, а по факту в нём лежат тела `StructureTemplate` (SQL `structure_templates`): добавить строку «structures → `structures_templates/` → `structure_templates`», для участков корня на FS нет (`fixtures/templates/`) — записать как «не задан». Разнобой имён корень/таблица (`structures_` vs `structure_`) — выровнять на `structure_templates/` пока stdlib 13 файлов, или зафиксировать текущее осознанно |
| Файлы | `docs/`, `.cursor/rules/template-pack-layout.mdc`, `tests/` |
| Контракт | — |
| Проверка | тесты п.18: C11 smoke-тест → buildings>0, `main_entrance` на стороне `slot.facing`, uid комнат уникальны между двумя участками одного чертежа |
| Done | ссылки на `BuildingLayoutTemplate`/`default_structure_context`/`interior_of` в `docs/` заменены или помечены историей |

### Шаг 6 — smoke на backend пользователя + замер (п.15)

| | |
|---|---|
| Цель | Реальный `generate-settlement?district_uid=` (§6) → 200, `districts=1`, `buildings>0`; тайминг `generate_from_template(tavern, facing=WEST)` и полного generate до/после |
| ТЗ | `tz_city_generation.md` §11.5 DoD |
| Файлы | нет правок кода; лог приёмки — §6 этого плана |
| Контракт | recreate локальной БД после DDL и запуск backend — пользователь |
| Проверка | HTTP-smoke; render-grid показывает `city_z` |
| Done | результат и тайминги записаны в §6; N generate неприемлемо → план B §7 п.7 |

---

### История формулировок (пп. 9–18 — заменены таблицами выше)

**Не исполнять по этому разделу.** Известные расхождения с действующими таблицами: п.12 включает `rotate_structure`/fit-check в `assemble` (сейчас — 3c/4b, не 4a); п.13 — `facing: Facing = Facing.SOUTH` default (3c решил `None`); п.14 — fallback SOUTH (4b: `facing=None`). Оставлено как история решений §4.0.

### Шаг 3 — генераторы
9. `StructureGeneratorService.generate_from_template(..., structure: StructureTemplate, ground_z, foundation_depth)` — убрать unwrap участка.
10. `BuildingAssembler.assemble(world, building, body: BuildingBodyTemplate, context, terrain)`: `structure = <resolved>`; generate → `attach_envelope` из полей body. Сигнатуру `attach_envelope` синкнуть (context из body+runtime).

### Шаг 4 — area: generate на посадке (фикс 5n; решение §4.0)
11. **Кэш не трогать.** `BuildingLayoutCache` остаётся envelope-only (`occupied_footprint` из объявленного участка) — это всё, что нужно разметке района. `_envelope_layout`, `from_south_map`, ключ `(template, facing)` — без изменений. `_cache_has_rooms` / `translate_layout`-ветка в area становится мёртвой → удалить (`layoutTranslate.py` оставить: используется debug/тестами — проверить grep перед удалением модуля).
12. **`StructureAreaAssembler.assemble` — переупорядочить:**
    ```
    bx/by, fp = plot.occupied_footprint (объявленный)          # как сейчас
    building = _place_building(...)                             # map_z = медиана поверхности под fp
    body = plot.main_building; structure = structure_catalog.resolve(body.structure)   # None → 422, не shell
    context = StructureContext(из полей body + facing=slot.facing + ground_z=building.map_z)
    layout = BuildingAssembler.assemble(world, building, body, structure, context, terrain_cells)
        # внутри: generate (SOUTH-фрейм шаблона) → rotate_structure(slot.facing) → fit-check → attach_envelope
    entry_xy = _entry_xy_world(layout)                          # реальный main_entrance; bx/by уже в layout — без сдвига
    threshold = resolve_threshold(slot, entry_xy=entry_xy, house_cells=fp_cells)
    approach / clamp_near_z_to_45 → если building.map_z изменился: layout = translate_layout(layout, 0, 0, dz)
    ```
    `_shell_layout` — **удалить** (см. решение мастера: площадь — назначение участка, не shell-кейс). `derive_structure_context` → тонкий shim над полями body (или удалить, если `StructureContext` собирается напрямую). `rebind_layout_to_building` остаётся как есть (uid уже реальный; вызов в `collect_geometry_fine_cells` становится no-op — оставить, не расширять).
13. **Ориентация структуры по посадке района — внутри генератора.** `AreaSlot.facing` задаёт район (`DistrictAssembler` → `frontage.py:179` `facing_from_street`), здание обязано сесть по нему автоматически. Поворот готового `StructureLayout` **невозможен корректно**: `rooms[]` — `NamedLocation` с `map_x/map_y` = левый-нижний угол, размеров комнаты в layout нет (`width/depth` только в `_RoomInstance`), клетки несут uid здания. Поэтому: `generate_from_template(..., facing: Facing = Facing.SOUTH)`; после раскладки (`layoutEngine`) и до эмиссии `NamedLocation`/клеток/passages — **rigid-body поворот** `_RoomInstance` (origin + width↔depth), шахт лестниц (facing), проёмов (`entry_point.wall`, стены дверей) вокруг origin входной комнаты так, что стена главного входа → `facing`. Внутренний helper `structure/rotateInstances.py` (или в `structurePostProcess.py`), тест: 4 стороны, 4×90° = identity, дверь на стене `facing`, `compute_occupied_footprint` после поворота. Калитка (`gate_on_facing_edge`, `slot.facing`) и дверь оказываются на одной стороне. `layoutTranslate.py` не трогать.
14. **Fit-check после generate:** `layout.occupied_footprint ⊆ slot.cells`. Packing резервирует footprint **всегда в SOUTH-фрейме** (`parcel.py:68`, `areaSlots.py:118`), facing назначается **после** — при 90° (EAST/WEST) width↔depth, неквадратный чертёж может не влезть. Не влезло → **`packing_warning` + повторный generate с fallback на SOUTH-ориентацию** (canonical-фрейм, footprint совпадает с резервацией по построению); не влезло и в SOUTH → `GenerationError` → 422 с именами plot/structure (кривой чертёж). Резервация в правильном фрейме — §7 п.1.
15. **Замер:** время одного `generate_from_template(tavern_1, facing=WEST)` и полного `generate-settlement` до/после — записать в лог приёмки; если N generate неприемлемо — план B §7 п.7.

### Шаг 5 — fixtures + docs
16. `fixtures/templates/*.json`: `main_building` inline → `{envelope-поля, structure: "<key>"}`; тела выделить в `structures_templates/base/` (с `structure_types` листьями); участок получает `plot_type` (семья); `default_structure_context` → на body.
17. ТЗ sync: `tz_building_generator.md` («Участок: главное здание», §1 таблица терминов — `plot_type`/`structure_types`, §9, §11 — имя класса, ref-модель), `tz_pojo_city_typing.md`, `tz_assembler_hierarchy.md` §6.5, `tz_city_generation.md` §9.2 (`allowed_structure_types` матчит структуру через участок).
18. Тесты: `test_city_three_axes.py`, `test_plot_layout.py` (`from_south_map` — контракт не меняется, входы остаются envelope), тест `rotate_structure` (4 стороны, 4×90° = identity, дверь на стороне `to_facing`), тест шага 14 (90° не влезает → fallback SOUTH + warning; SOUTH не влезает → 422), новый C11 smoke: `generate-settlement?district_uid=` → buildings>0, у каждого здания `main_entrance` на стороне `slot.facing`, uid комнат уникальны между двумя участками одного чертежа.

## 4. Открытые вопросы (решить до/в начале — не блокируют каркас)

- `secondary_buildings` — формат элемента отложен (stub).

### 4.0 Момент generate — **решено: на посадке** (шаг 4 переписан)

**Факты (проверено):**
- Здание инициализируется **на посадке**: `NamedLocation` в `StructureAreaAssembler._place_building` (uid `{world}-{template}-{x}-{y}`, `map_z` = медиана поверхности), envelope — `attach_envelope` там же с реальным `slot.facing` / `terrain_cells`. Envelope в кэше никогда не был.
- Кэш для разметки района нужен только как `occupied_footprint` (из объявленного `plot.occupied_footprint`).
- Опорная точка геометрии: `layoutEngine._find_start` → комната с `entry_point`, её `origin = (bx, by) = building.map_x/map_y`; BFS раскладывает остальные вокруг (bbox может уйти в минус, фактический — `compute_occupied_footprint`). Стена входа — `entry_point.wall`, default SOUTH (`passages/entry.py:31`). `generate_from_template` **facing не принимает**.
- Поворот структуры (геометрии) = rigid-body вокруг origin входной комнаты (cells xy + `system_facing`, passages xy, rooms xy, facing шахт) **до** `attach_envelope`; после — `compute_occupied_footprint` заново. Ловушка: при 90° width/depth меняются местами — резервация участка может не вместить (шаг 14).
- **Терминология:** «структура» = геометрия здания (комнаты, уровни, лестницы, проёмы). «Интерьер» (мебель, наполнение, `StructureInteriorAssembler`) — отсутствующий слой, в этом плане не фигурирует.

| | Generate в кэше (отвергнуто → §7 п.7) | Generate на посадке (шаг 4) |
|---|---|---|
| Вызовов generate | K чертежей | N зданий (**замерить** `tavern_1`) |
| Синтетический `NamedLocation` | нужен | нет |
| Rebind всех uid | нужен | **нет** — uid комнат сразу от реального `building.location_uid` |
| Terrain/facing контекст | недоступен | естественно на месте |
| Контракт кэша / `from_south_map` | меняется | не меняется, кэш остаётся envelope-only |
| Порядок в area | как сейчас | place → generate → `_entry_xy` из реальных passages → threshold (bx/by известны до place) |
| Поворот структуры под `slot.facing` | нужен | нужен — шаг 13 (генератор без facing) |

**Решение мастера — на посадке.** 5n фиксится вызовом `BuildingAssembler.assemble` в area вместо `_shell_layout`/`translate_layout`; rebind-расширение и синтетический `NamedLocation` не нужны; кэш и его тесты не меняются. Цена — N generate; замер — шаг 15, план B (кэш полных layout) — только если замер неприемлем.

### 4.3 Точка поворота структуры — **решено: вариант B (2026-09-28)**

> Решение мастера — **B**: один поворот перед `_assemble_result`. Раздел 3c переписан под B; таблица ниже оставлена как обоснование.

**Факт (проверено 2026-09-28):** §4.0 отверг «поворот готового layout» потому, что у `NamedLocation` нет width/depth, а клетки несут uid. Это верно для **`StructureLayout` (DTO)**. Но в сервисе есть точка **до** сборки DTO — `_assemble_result(building, levels, all_rooms, room_uids, cells_dict, passages)` (`structureGeneratorService.py:647`), где ещё живы `_RoomInstance` (origin/width/depth/extra_cells), `cells_dict` и `passages`. Uid клеток/комнат от координат не зависят (`_det_uuid(location_uid, room.uid_key)`). Ни один builder (doors, corridors, tunnels, stairs, windows) не читает мировой контекст во время генерации: `ground_z` — скаляр, `building_band` — не пространственный.

| | A. Поворот после layout, builders в повёрнутом фрейме (текущие 3c.1–3c.6) | B. Весь пайплайн в фрейме шаблона, один поворот перед `_assemble_result` |
|---|---|---|
| Что поворачивается | `_RoomInstance` после `_layout_rooms`; далее каждый builder обязан быть orientation-aware (tie-break через `inverse_point`) | один проход: `MapCell.x/y/system_facing/display_facing`, `LocationPassage.to_x/to_y/from_x/from_y` + facing, `_RoomInstance.origin/width/depth/extra_cells` |
| Файлы | `rotateInstances.py`, `structureOrientation.py`, `passages/{shared,doorPlacer,entry,doorway,archway,builder,corridorConnector,tunnelPathFinder,staircaseTunnelOrchestrator,wallOpening,wallOpeningResolver}.py`, `staircase/*` (план S0–S10), `roomInstance.py` (`oriented_footprint`) | `structureOrientation.py` (новый), `structureGeneratorService.py` (один вызов), `roomFactory.py` (копии `entry_point` — уже в плане) |
| «Повёрнутая копия = исходная» | доказывается тестами на каждый модуль | по построению |
| Тесты | `test_rotate_{instances,doors,corridors,tunnels,stair_anchors,staircases,windows}`, `test_structure_orientation` | `test_structure_orientation` (полная генерация ×4 стороны, cells/passages/rooms = R(исходных)); характеризационные тесты лестниц S1–S3 остаются как защита, но поворота не видят |
| Что теряется | — | builders не могут читать мировые координаты при генерации. Сегодня не читают; terrain-адаптация — §7 п.2 и потребует отдельного дизайна в любом варианте |
| Риск | объём; расползание orientation по всем passages-модулям; хрупкие лестницы | `compute_occupied_footprint` после поворота (по cells — ок); `display_facing` — локализованная строка, маппить через тот же `Facing` |

**Рекомендация разработчика — B.** Текущий объём 3c вырос из «параметр + один вызов» до эпика именно из-за выбора A. Пивот, cardinal-only, требование ровно одного `main_entrance`, контракт `facing=None` — сохраняются как есть (это контракт публичного generate, не точка поворота). При выборе B: 3c.1–3c.6 переписать в один шаг «3c — `StructureOrientation` + поворот перед `_assemble_result`», план лестниц сократить до S0–S3 (семантика facing лестниц + характеризационные тесты). При выборе A — исполнять 3c.1–3c.6 как записано.

### 4.1 Хранение `StructureTemplate` — факты и варианты (schema-решение мастера)

**Что есть сейчас (проверено):**

| Источник | Где | Состояние |
|---|---|---|
| Engine stdlib участков | `fixtures/templates/*.json`, `_PACKING_STEMS` в `worldBuildingLayoutDefaults.py` | работает; тело inline в `main_building` |
| SQL library | `building_templates.data` | пишется **только** `BuildingTemplateOutline.model_dump()` (`upsert_outline`). Outline: `levels: IntMinMax`, `extra="ignore"` → полный чертёж через bundle **теряет generate-`levels`**. `layouts_for_world` потом `try_building_layout(data)` → «outline-only skip». World overlay для generate **мёртв по конструкции** |
| World inline | `worlds.building_template_registry` layout-shaped строки → `world_building_layout_overrides` | работает, но это третий путь мимо SQL library |
| Relief-прецедент | `relief_templates` + `worlds.relief_template_registry` + `relief_templates/` FS root + `reliefTemplateFsImport` + `load_relief_templates_for_world` | полный образец «domain root → SQL → pointer → body» |

**Варианты для тела геометрии:**

| | A. `building_templates` + колонка `kind` (`plot`/`structure`) | B. `structure_templates` + `worlds.structure_template_registry` (зеркало relief) | C. `structure_templates` **без** world-pointer |
|---|---|---|---|
| Таблиц / колонок worlds | 0 новых таблиц, +1 колонка `kind` | +1 таблица, +1 колонка worlds, +dataclass, repo, route, bundle-section, registry POJO | +1 таблица, +dataclass, repo, FS-import; worlds не трогаем |
| uid namespace | общий `building_templates\|name` → участок и структура с одним `system_name` коллидируют; `system_name UNIQUE` через оба kind; `structure_type NOT NULL` бессмыслен для структуры | чистый `structure_templates\|name` | чистый |
| Per-world изоляция структур | pointer list смешивает kinds | явная, как relief | **неявная**: структура доступна миру iff на неё ссылается участок из реестра мира |
| Соответствие `template-pack-layout` (домен = свой корень + своя таблица) | нарушает | да | да |
| Blast radius | малый, но закрепляет смешение plot/structure в одной таблице — то, что 5o лечит | большой | средний |

**Рекомендация — C.** Структура — не самостоятельный объект мира, она достижима только через `PlotLayoutTemplate.main_building.structure`; отдельный pointer-реестр дублирует связь, которая уже есть в участке. Резолв в `StructureCatalog`: FS stdlib (`structures_templates/`) ⊕ все строки `structure_templates`, ключ — uid (`system_name` = uuid, см. «ключ структуры» ниже); later-wins по имени отменён — коллизий нет по построению. Импорт участка в мир (bundle / registry) валидирует, что `structure`-ref резолвится, иначе `ImportError` — тот же паттерн, что проверка материалов в ТЗ §6.2. Если позже понадобится per-world изоляция библиотеки структур — колонка worlds добавляется поверх C без переделки таблицы (C → B монотонно).

**Артефакты по вариантам** (образец — relief: `db/models/reliefTemplate.py`, `i/ReliefTemplateRepository`, `reliefTemplateLibraryService`, `reliefTemplateFsImport`, `reliefWorldImportService`, `loadReliefTemplatesForWorld`, `routes/reliefTemplates.py` (6 endpoints), `bundle/reliefSection.py`, `worldReliefTemplateRegistry` + entry POJO, колонка `worlds.relief_template_registry`, `worldRow.relief_template_registry`, container wiring):

| Артефакт | A (`kind` в `building_templates`) | B (зеркало relief) | C (таблица без pointer) |
|---|---|---|---|
| `0001_initial.sql` | +колонка `kind`; `structure_type` → NULLable | +`structure_templates` (`template_uid` PK, `system_name` UNIQUE, `display_name`, `version`, `data`, `source_file`) + `worlds.structure_template_registry` | +`structure_templates` (`template_uid` TEXT PK **== `StructureTemplate.system_name`** (uuid из JSON, не uuid5), `display_name` NOT NULL без UNIQUE, `version`, `data`, `source_file`; **без** `system_name`-колонки, `structure_type`, `owner_world_uid`) |
| `db/models` | правка `BuildingTemplateRow` | +`StructureTemplateRow`, +поле `World` | +`StructureTemplateRow` |
| repo | правка фильтров по `kind` | +`IStructureTemplateRepository` + sqlite | то же |
| library service | ветвление по `kind` в `BuildingTemplateLibraryService` (растёт >300 строк) | +`StructureTemplateLibraryService` (uid = `system_name` из JSON, **не** `uuid5(name)`; upsert = update in-place по тому же uid + WARNING при смене тела; list, domain root + env override) | то же |
| FS import | загрузчик с определением kind по содержимому (эвристика — то, что 5o убирает) | +`structureTemplateFsImport` (копия relief: pack dir = прямой ребёнок root, stem == system_name) | то же |
| world bind | pointer list смешивает kinds | +`structureWorldImportService` + `load_structure_templates_for_world` | **нет**; резолв ref при импорте участка в мир |
| routes | правка `building-templates` | +`/structure-templates` list/get/upsert/import/delete + `/worlds/{uid}/structure-templates/import` | +`/structure-templates` list (uid+display_name+structure_types)/get/{uid}/upsert (глобальная загрузка мастером)/import (FS)/delete (без world-route) |
| bundle | правка секции | +секция `structure_templates` по registry | +секция `structure_templates` = **замыкание refs** из участков мира (export), import = upsert global |
| `jsonValidation/worldRow` | — | +`structure_template_registry(world)` | — |
| `StructureCatalog` | фильтр `kind=structure` | stdlib ⊕ pointer-bodies мира | FS stdlib ⊕ все SQL rows, ключ uid; тот же uid → SQL wins (та же сущность); scope мира не нужен |

**Решение разработчика — C + модель А ключа** (2026-09-26; анализ [`template-key-identity-analysis-done.md`](template-key-identity-analysis-done.md) §7; блокер шагов 1/8/DDL **снят**). Требование продукта: мастер загружает шаблон **один раз** и подключает в несколько миров → библиотека — одно глобальное множество, мир — подмножество через pointers; коллизии исключаются ключом, не scope'ом. `system_name` = **uuid шаблона** (формат проверяет `field_validator` POJO, `RegistryKey` не меняется), `display_name` — человеческое имя, не уникально. Промежуточная рекомендация V2 (`owner_world_uid`) отозвана — не позволяет шарить контент мастера между мирами. Таблица ниже — **принятая** форма ключа.

**Ключ структуры (ПРИНЯТО — uid в `system_name`).** Минус C в первоначальной форме: `system_name UNIQUE` + `template_uid = uuid5("structure_templates|name")` означают, что два мира не могут иметь **разные** структуры с одним именем `tavern_1` — вторая затирает первую (later wins). Поэтому:

| | Было (образец `building_templates`/relief) | Для `structure_templates` |
|---|---|---|
| `system_name` | слаг, `UNIQUE`, uid производный от него | **независимый uid** (uuid, записан в JSON автором; omit → 422 — файл должен знать свой stem), `PRIMARY KEY`; **не** производный от имени |
| `display_name` | человеческое | человеческое имя (`tavern_1`), **не уникально** — два мира могут иметь по своей `tavern_1` |
| ref из участка | `main_building.structure: "tavern_1"` | `main_building.structure: "<uid>"` — по uid |
| FS stem | `stem == system_name` (слаг) | `stem == system_name` (uid) — правило `template-pack-layout` не нарушается; читаемость даёт `display_name` внутри файла и имя пакета-папки |
| `StructureCatalog` | резолв по слагу, later wins | резолв **только по uid**; тот же uid в FS stdlib и SQL — одна сущность (FS-import пишет в SQL), SQL wins; два файла с одним uid в stdlib-паках — ошибка FS-импорта |
| Routes list/get | по слагу | `get/{uid}`; `list` возвращает `uid + display_name + structure_types` для выбора; поиск по `display_name` — фильтр списка, не ключ |
| Debug API | `system_name` слаг | uid из каталога или JSON структуры |

Отдельного поля uid в POJO нет — `system_name` **и есть** uid (`RegistryKey[StructureTemplate]` остаётся типом ключа); в SQL колонка называется `template_uid` (единообразие с FK-холдерами) и хранит то же значение. `StructureTemplateLibraryService.upsert` **не** вычисляет uid из имени.

Тот же дефект у **участков** (`building_templates.system_name UNIQUE`, `uuid5(name)`) и relief — в срезе не трогать; миграция на uid-ключ — §7 п.8.

**Scope среза (при C):** обязательны — DDL + `StructureTemplateRow` + repo + library service + FS import + `StructureCatalog` (smoke зависит от FS stdlib, но `StructureCatalog` должен резолвить через один API, а не два пути). Routes list/get/upsert/import — тонкие, в срез. Ключ в URL — uid (`system_name`). Глобальный `POST /structure-templates` (загрузка мастером в общую библиотеку) — **в срез**: это и есть «загрузил один раз»; FS-import — для stdlib разработчика. **Bundle-секция и delete-RESTRICT** (структура, на которую ссылается участок) — §7 п.6, если мастер не потребует переносимости сейчас.

**Смежный дефект, не закрывать этим срезом, но записать в 5o:** `building_templates.data` = Outline vs полный `PlotLayoutTemplate`. После сплита участок компактный (footprint + barrier + body-ref + envelope), разрыв с Outline сводится к catalog-полям (`levels: IntMinMax`, `footprint`, `rooms: slots`, материалы). Решение «data = полный PlotLayoutTemplate, Outline — read-projection» — отдельный пункт tech debt; в этом срезе достаточно, чтобы stdlib с диска давал generate-able участки для smoke.

### 4.2 Тип участка vs назначение здания — решение мастера

**Принцип:** не смешивать тип **участка** и назначение **здания** на участке. Здание хранит своё назначение само; участок хранит свой тип сам.

**Почему не `district_type`:** по ТЗ это N+1 (`tz_city_generation.md` §1.1 стр. 65 «+ N+1, напр. `military`»; §9.3 стр. 558 «голый `str` — нет реестра типов ткани»). Участок движка на открытый ключ мира не завязать. **`BuildingPurposeFamily`** — строгий StrEnum движка, и район уже оперирует семьями: `allowed_structure_types` принимает лист **или** семью (`tz_building_generator.md` стр. 72), специализация штампует `allowed_family` на слот (`tz_city_generation.md` стр. 86).

| Поле | Где | Тип | Роль |
|---|---|---|---|
| `plot_type` | `PlotLayoutTemplate` | `BuildingPurposeFamily` | Семья участка — **дефолт движка** для автопостроения: участок ложится в район, чей штамп семьи / `allowed` его включает. **Omit на wire → `dwelling` + warning** (решение мастера): warning не в Pydantic-валидаторе (модель не логирует), а в точке загрузки каталога (`worldBuildingLayoutDefaults` / FS-import / `world_building_layout_overrides`) через единый `packingLog.packing_warning(step=CACHE, reason=PackingReason.PLOT_TYPE_DEFAULTED, system_name=…)` — новый `PackingReason`, не голый `logger.warning`. Детект omit — `"plot_type" not in plot.model_fields_set` (Pydantic), не сравнение с дефолтом |
| `structure_types` | `StructureTemplate` | `list[BuildingPurpose]` | Назначение здания (листья) — дефолт дома. `level.purpose` переписывает его на этаже, `room.purpose` — на комнате (каскад `room ?? level ?? structure_types`). `len > 1` без `level.purpose` → авто-разводка `level[i] → types[min(i, len-1)]` + `packing_warning`. Omit/`[]` → `derived` из этажей/комнат, иначе `[house]` |
| `allowed_structure_types` | `DistrictTemplateEntry` | лист или семья (без изменений) | **Высший authority.** Если задан — матч по листьям структуры через `plot.main_building.structure`; расхождение с `plot_type` роли не играет |

Packing (`tokens.py`, `BuildingCatalog.matching_allowed`, `districts.py`): вместо `plot.structure_types` читать `resolve_leaves(plot) = structure.structure_types` через `StructureCatalog`; при отсутствии `allowed` на районе — дефолт `plot.plot_type ∈ expand(штамп семьи)`. Паки мира (`purpose_packs`) по-прежнему режут листья структуры. Расхождение «участок `trade`, здание `house`» — не ошибка, мастер так задумал, район решает.

**Текущие потребители `plot.structure_types` (перевести — шаг 4c):** `tokens.py` (стр. 245, 260, 388 — pool/required/fill), `frontage.py:48` (`PLAZA`), `districts.py` (`allowed_structure_types`), `BuildingCatalog.of_structure_type/matching_allowed/structure_types()`, лог в `buildingCache:184`. `BuildingTemplateOutline.structure_types` + колонка `building_templates.structure_type` — leftover участка, в этом срезе не трогать (§7 п.3 Outline).

**Площадь (`plaza`) — tech debt, не этот срез (§7 п.5).** Сейчас `plaza` — лист `BuildingPurpose` семьи `public`, `frontage.py:48` смотрит его на участке, `base`-пак включает, `required_structures` могут требовать. У площади структуры нет — листа взять негде. В срезе: `frontage`/`required_structures` матчат площадь как `plot_type == PUBLIC and main_building is None`; лист `plaza` в дереве остаётся «виртуальным».

**Решение мастера (2026-09-27):** plaza — назначение участка (домен `areaAssembler`), не структурное ограничение: public-участок может иметь `main_building`/пристройки — тогда обычный generate через `BuildingAssembler`; без здания — `building_layout=None`, клеток нет. `_shell_layout` удаляется, роли «пол для площади» не существует. Следствие для §7 п.5: детектор `is_plaza` (`frontage.py`) — по семье `plot_type == PUBLIC` без условия `main_building is None`, иначе public-участок с пристройкой теряет plaza-пропуск frontage.

## 5. Blast radius

- ~174 usages `BuildingLayoutTemplate` в backend.
- `fixtures/templates/*.json` — wire-миграция (ref + envelope на body).
- **Debug API** `POST /worlds/{uid}/generate-structure` (`routes/debug.py:41`): сейчас принимает JSON участка/тела через `coerce_building_layout` (эвристика — удаляется). После: принимает **`StructureTemplate`** JSON (file/path) **или** uid структуры (`system_name`) из `StructureCatalog`; опц. `facing`. Читает без мутации (generate in-memory, без persist — как сейчас), возвращает **всё**: cells, levels, passages, rooms, `occupied_footprint`, element counts, лог-capture. Envelope не применяется (это геометрия структуры, не здание) — `ASSEMBLER_REGISTRY`/`BuildingAssembler` из этого route не вызывать.
- `StructureAreaAssembler.assemble` — переупорядочивание (шаг 12): place → generate → threshold; `cached_layout`-параметр теряет смысл для зданий (остаётся для envelope площади или удаляется — решить при имплементации, не плодить два пути).
- Packing (`tokens.py`, `BuildingCatalog`, `districts.py`) — источник листьев меняется с участка на структуру через `StructureCatalog` (§4.2); `StructureCatalog` нужен уже на этапе разметки района, не только в area.
- Время `generate-settlement`: N generate вместо 0 сегодня — замер шаг 15.
- Кэш и `from_south_map` — **не меняются**.

## 6. Верификация

```bash
# C11/C24 smoke — раньше падало 422 "has no front entry"
curl.exe -X POST "http://localhost:8000/api/worlds/{uid}/locations/{city}/generate-settlement?district_uid={district}" --max-time 600
# ожидание: 200, districts=1, buildings>0; render-grid показывает city_z
cd backend && python -m unittest tests.test_city_three_axes tests.test_plot_layout tests.test_c24_district_packing tests.test_building_assembler tests.test_structure_template
```

**Не делать:** DAG-ноды не трогать; persist-архитектуру не менять; `detailed_bake` scope не расширять; `secondary_buildings` не генерить (stub); кэш не переводить на полные layout; резервацию в district-planner не поворачивать и terrain-адаптацию структуры не делать — §7.

## 7. Итерация 2 (после приёмки среза — не забыть)

| # | Что | Почему отложено | Куда |
|---|---|---|---|
| 1 | **Резервация в правильном фрейме.** Район знает улицы **до** packing → определять facing по примыканию резервации и сажать footprint уже повёрнутым (`parcel.py`, `tokens.py`, `areaSlots.py` — сейчас слот всегда в фрейме шаблона, `frontage` назначает facing после). Механизм поворота резервации **уже есть** — `Reservation.rotated_90` (`types.py:94`, `pass2.py:89`, `parcel.py:61`): задача — провести его до слота и сделать facing-driven, а не изобретать заново. Заодно закрыть pre-existing дефект: `rotated_90` теряется в `placements_from_reservations` (`areaSlots.py:109–118`) — слот собирается из `fp` шаблона без учёта поворота резерва. Тогда fallback 4b становится мёртвым путём | Правка district-planner, не area; в срезе — `facing` в генератор + fallback (4b) | `districtAssembler/planner/*` |
| 2 | **Terrain-адаптация структуры.** Generate на посадке уже видит slot/terrain/`ground_z` — контекст доступен, но геометрия структуры его не использует (только envelope: `FoundationBuilder`/`RoofBuilder`). Решить, что из контекста меняет структуру (foundation depth по уклону, pier/stilts, подрезка уровней) | Отдельный дизайн; в срезе `attach_envelope` как сегодня | `BuildingAssembler`, `StructureContext` |
| 3 | `building_templates.data`: Outline → полный `PlotLayoutTemplate` (см. §4.1 «смежный дефект») | Отдельное schema-решение; срез не зависит | tech debt 5o |
| 4 | ~~`_det_uuid` скопирован в 8 модулях — один helper~~ **→ шаг 3c-RNG** (по grep 2026-09-28 определений 5: `structureGeneratorService`, `passages/shared`, `passages/staircaseTunnelOrchestrator`, `staircase/builder`, `staircase/surfaceCorridor`; `archway/doorway/entry` импортируют из `shared`) | перенесено в срез вместе с seeded RNG лестницы | `app/utils/deterministicIds.py` |
| 5 | **Площадь (`plaza`)**: убрать лист из дерева `BuildingPurpose`; площадь = `plot_type: public` + `main_building: None`. Трогает `base`-пак (`allowed`), `required_structures: plaza` → требование безздательного участка семьи `public`, `frontage.py`, `tokens.py` | В срезе лист остаётся «виртуальным» (§4.2) — иначе срез расползается на дерево purpose и паки | `buildingPurpose/public.py`, `packs.py`, `tokens.py`, `frontage.py` |
| 6 | Библиотека структур: bundle-секция `structure_templates` (замыкание refs участков мира на export, upsert global на import) + delete-RESTRICT, если структура referenced участком | §4.1 scope среза — без переносимости; ТЗ §5.1 RESTRICT-паттерн | `bundle/`, `StructureTemplateLibraryService.delete` |
| 7 | **Кэш полных layout (план B)** — только если замер шага 15 покажет, что N generate неприемлемо: синтетический `NamedLocation` на cache-fill, rebind всех uid через `uuid5(f"{world_uid}\|{building_uid}\|{old_uid}")`, `translate_layout` как продакшн-путь | Отвергнуто мастером в пользу generate на посадке (§4.0); хранится как fallback | история этого файла до 2026-09-25 |
| 8 | **Uid-ключи для участков и relief (модель А).** `building_templates` / `relief_templates`: убрать колонку `system_name` и `uuid5(name)` — `template_uid` = `system_name` (uuid) из JSON; валидатор формата на `BuildingTemplateOutline`/`PlotLayoutTemplate`/`ReliefTemplate`; удалить `building_template_uid()`/`relief_template_uid()`. Pointer-реестры и `relief_pick_policy.default_template_uid` по форме не меняются (уже uuid) — меняется источник значения. Fixtures: `fixtures/templates/*.json` и `relief_templates/smoke_003/*.json` получают uuid-stems; `world_test_gen_003.json` — uid из файлов; refs `plot_template`/`plot_counts`/`plot_priority` и `WorldDistrictTemplateRegistry.canonical_defaults()` (`town_hall`) → uuid. F11 (`named_locations.system_template_uid` = имя) закрывается автоматически. Docs: `tz_building_generator.md` §5.1/§6.1, `tz_terrain_relief.md` R11, `tz_json_validation.md` §0. Детали — [`template-key-identity-analysis-done.md`](template-key-identity-analysis-done.md) §7.6 | Схема двух работающих библиотек + fixtures + bundle; срез не зависит | `0001_initial.sql`, `*TemplateLibraryService`, `*FsImport`, fixtures, `worldDistrictTemplateRegistry`, docs |
| 9 | **Персист назначения комнаты.** Контракт `purpose` этажа/комнаты — ТЗ §3.4b (введён в срез шагом 5a: POJO + валидация + fixture). **Отложено:** поле назначения на `NamedLocation` комнаты (колонка/`0001_initial.sql`), чтение в `StructureInteriorAssembler` и LLM scene context (DAG) | Персист — домен интерьера, требует ТЗ интерьера; DAG — gate | `named_locations`, `StructureInteriorAssembler`, `engine/nodes` (с мастером) |
| 10 | ~~**Латентный `NameError` в `passages/builder.py`**~~ — `StaircaseType` использовался в pass-2 (`:126`, `:205`) **без импорта**: любой шаблон с `staircases` падал бы `NameError` на `parse_template`. **Закрыто инцидентально в `edb16a7`** (импорт добавлен с этим коммитом; отдельного шага/теста не было) | Найдено при ревизии 2026-09-29; fix уже в коде — остаётся покрыть путь регрессионным тестом (passages pass-2 на шаблоне со staircases) | `structure/passages/builder.py`, `tests/` |
| 11 | **Ошибки валидаторов на stdlib-структурах.** Прогон generate по всем 13 файлам `structures_templates/base/` с capture `logger.error` (2026-09-29): generate без exception, но **36 ERROR-строк на 3 структурах**: `5a1f2b3c-…` (7) — `vertical_ladder cellar_ladder [to_anchor footprint]: (17,-1) вне footprint верхней комнаты`; `door cellar_exit_ladder (2,14,z=10) facing=east: через (3,14)=door — нет floor, не ставим`; 4× `archway scan`: frame `elem=door`/`ladder`/`None` вместо `wall` (z=5, z=11); `6b2f3c4d-…` (1) — `vertical_ladder cellar_staircase [to_anchor footprint]: (25,-1) вне footprint`; `7c3a4d5e-…` (28) — `archway scan H` `frame_e=(15,y) elem=None` на z=23..36 (кластер на высоких этажах, ×2 строки на z). По составу (archway/door/ladder — код не трогался в срезе) — **pre-existing дефекты геометрии шаблонов**, не регресс; подтвердить при разборе прогоном на `edb16a7^`. Важно: валидаторы только `logger.error` — ошибки не фейлят generate/тесты, видны только в логе | Дефекты шаблонов/строителей вне scope среза; до приёмки шага 6 — разобрать (шаблон кривой или builder/validator неверный) | `structures_templates/base/`, `archwayValidator`, `doorValidator`, `verticalLadder` |
