# План: техдолг — `*_type` / `*_kind` поля на голом `str`

## Контекст

Инвентаризация `backend/app` (113 совпадений `\w*_(type|kind): str…`)
после WR-TD-1 (`TerrainKey`/`RegionShapeKind` в wilderness). Паттерн SoT:
`RegistryKey[<Registry>]` / `*Key`-алиасы для ссылок на реестр, StrEnum /
закрытый union — для значений из фиксированного набора. Голый `str` на
поле контракта теряет принадлежность к реестру и даёт silent mismatch.

**Scope плана — только поля контрактов/POJO** (таблица ниже). Не scope:

- `db/models/*` — SQL-строки, `str` по определению слоя
  (`system_location_type`, `connection_type`, `node_type`, `library_kind`,
  `*_age_type`, `message_type` и пр.).
- Параметры функций — lookup-граница реестра (`entry_for`, `require`,
  `subtype_for`, planner/resolver-параметры) — `str` допустим как вход;
  boundary-адаптеры вида `str | LibraryKind` — существующая конвенция.
- `MaskDomainId`/contributor name-поля — StrEnum-совместимы.

Проверки каждого шага: `python -m unittest tests.<…>` из `backend/` +
`compileall app`. Новый enum/key — только если его ещё нет; alias вида
`XKey = RegistryKey[XRegistry]` по образцу `TransitionTypeKey` /
`ConnectionTypeKey` / `TerrainKey`.

## Карта полей → целевые типы (верифицировано по коду)

Домен каждого поля подтверждён по месту производства/потребления.
«100%» — enum/key-алиас уже существует в репозитории.

| # | Поле | Целевой тип | Статус домена |
|---|---|---|---|
| 1 | `library_kind` | `LibraryKind` | 100% (enum есть; границы уже `str \| LibraryKind`) |
| 2 | `connection_type` (контракт-поля) | `ConnectionTypeKey` | 100% (alias есть) |
| 3 | `shape_type` | `ShapeType` | 100% (enum есть) |
| 3 | `room_type` | `RoomTypeKey = RegistryKey[WorldRoomTypeRegistry]` | реестр есть, alias добавить |
| 3 | `staircase_type` | `StaircaseType` | 100% (StrEnum есть) |
| 3 | `default_shaft_size_type` | `StraightSize \| UShapeSize \| SpiralSize` (поле) / `str` (boundary-функция) | union-enum есть; dependent key — см. § Dependent-key |
| 4 | `foundation_type` | `FoundationType` (новый StrEnum) | литералы `none\|slab\|perimeter\|full\|hull` из комментов |
| 4 | `roof_type` | `RoofType` (новый StrEnum) + нормализация `str \| list[str]` → `list[RoofType]` | ОТЛОЖЕНО, см. шаг 9 |
| 4 | `hull_type` | `str` + валидация при producer | scaffold — контекст нигде не конструируется |
| 4 | `base_structure_type` | `str` + `in BUILDING_ASSEMBLER_REGISTRY.all()` | scaffold; engine-registry, не N+1 |
| 4 | `extraction_type` | `str` + валидация при producer | scaffold |
| 4 | `resource_type` | `ResourceTypeKey = RegistryKey[WorldResourceTypeRegistry]` | реестр есть, alias добавить |
| 5 | `pole_kind` | `PoleKind` | 100% (enum есть: `wire_value`/`from_wire`; `_pole_kind_wire` уже принимает enum) |
| 6 | `system_location_type` (wire) | `LocationTypeKey = RegistryKey[WorldLocationTypeRegistry]` | реестр есть, alias добавить |
| 7 | `node_type` (`ResolvedConnectionNode`) | `ConnectionNodeType` | 100% (enum есть — тот же набор, что в DDL-комменте) |
| 7 | `graph_level` (`ResolvedConnectionNode`) | `GraphLevel` | 100% (enum есть; call sites уже `GraphLevel.X.value`) |
| 8 | `task_type` | `TaskType` | 100% (enum есть; `chatService` уже делает `TaskType(task_type)`) |
| 8 | `grid_kind` | defer | один producer `world_map_light` — enum при появлении второго kind |
| — | `system_location_subtype` | dependent key (реестр по `system_location_type`) | см. § Dependent-key |

Файлы: `lifecycleContracts.py:53`, `legacyWorldContracts.py:33`,
`connectionEntry.py:25`, `road/connectionPolicy.py:24`,
`hydrology/types.py:62-63,84,94`, `roomInstance.py:21,27,43`,
`staircaseType.py:11`, `structureContext.py:9-10`,
`vastHullAssembler.py:20`, `ruinsAssembler.py:19`,
`resourceExtractionAssembler.py:19,21`, `climatePole.py:19`,
`climatePolePreset.py:14`, `locationsIndexWire.py:24`,
`renderPayloads.py:109`, `sseEvents.py:26`, `sessionSnapshot.py:9`,
`api/routes/chat.py:43`, `chatService.py:21`.

## Шаги

### Шаг 0 — contract hygiene scan-тест (gate роста карты)

- **Цель:** карта дыр не растёт — скан ловит новые `*_type`/`*_kind`
  поля на голом `str`; allowlist только уменьшается.
- **ТЗ:** `tz_json_validation.md` § RegistryKey; правила
  `.cursor/rules/type-kind-str-fields.mdc` + `contract-creation.mdc`.
- **Файлы:** `backend/tests/test_contract_hygiene.py` (новый).
- **Контракт:** AST-скан `app/**` минус `app/db/models/**` — без
  runtime-import (не маскирует import-ошибку, ловит `@dataclass` и
  Pydantic одинаково); allowlist `(module, class, field) → шаг`;
  новая дыра и stale-запись allowlist — оба fail. Легитимный `str`
  допустим только с пометкой в ТЗ — и тогда заносится в allowlist
  со ссылкой на спеку, не обходится молча.
- **Проверка:** `python -m unittest tests.test_contract_hygiene` из
  `backend/`; удаление записи из allowlist → тест красный.
- **Done:** тест зелёный; allowlist = карта ниже + находки вне карты
  зафиксированы отдельно.

#### Инвентаризация шага 0 (2026-10-18)

**Шаг 0 выполнен и принят 2026-10-18:** мастер разрешил переход «Далее».
7 тестов, compileall и diff --check прошли; allowlist остался из 50 полей.

Исходный `test_contract_hygiene.py` уже находился среди untracked-файлов.
Зафиксировано 50 записей allowlist; состав не расширен. Скан читает AST,
включая список wire-обёрток из `annotationPolicy.py`, без runtime-import
`app`. Вложенные Annotated/Optional/union и строковые аннотации раскрываются;
SQL-модели и lookup-параметры исключены. Отрицательные проверки покрывают
новую дыру и stale-запись. Статус шага меняется только после «ок» мастера.

Находки существующего allowlist сверх исходных файлов шагов (суффикс
`+scan` — инвентаризация, не разрешение расширять следующий шаг молча):

- `LibraryPinEntry.library_kind`, `LibraryPackManifestMember.library_kind`.
- `DeclaredRiverSegment.connection_type`, `ConnectionEdgeImportRow.connection_type`,
  `RoadSettingsEntry.system_connection_type`.
- `RoomDef.shape_type`, `RoomDef.room_type`, `RoomDef.staircase_type`.
- `BuildingBodyTemplate.foundation_type`, `BundleNamedLocation.system_location_type`.
- `SocketEvent.type`, `Rule.type`: скан охватывает и точные имена `type`/`kind`;
  принадлежность этих полей к `TaskType` не установлена, требуется отдельная
  проверка домена до любых правок шага 8.

Отдельные находки вне карты целевых типов, **без назначения типа наугад**:

- `ConnectionEdgeImportRow.lighting_type`, `ConnectionNodeImportRow.portal_type`.
- `LocationTypeEntry.system_type`.
- `DistrictTemplateEntry.district_type`, `PlacementCondition.district_type`,
  `TypicalDistrictRef.district_type`.
- `SettlementSpecializationEntry.subject_kind`.
- `EarthenCanal.system_type`, `StructureCanal.system_type`, `CanalTemplateEntry.system_type`.

Это зафиксированный долг, не новые шаги имплементации. `LocationTypeEntry.display_type`
— текстовое исключение, а не ключ. Причины для display/scaffold/dependent-key/grid
закреплены в `docs/tz_json_validation.md` § Contract hygiene — отложенные строковые
поля и указаны в allowlist. `ResourceExtractionContext.resource_type` относится
к шагу 4, хотя контекст пока scaffold. Поля `orientation`/`ruin_style` и
`system_location_subtype` не соответствуют шаблону имён сканера; их обязательства
сохраняются в разделах Scaffold/Dependent-key этого плана.

### Шаг 1 — `library_kind` → `LibraryKind` в pack-контрактах

- **Цель:** enum `LibraryKind` уже существует в `app/ids`; контракты
  packs держат его как `str`.
- **ТЗ:** `tz_template_library_packs.md` (pack contracts);
  `tz_json_validation.md` § RegistryKey.
- **Файлы:** `backend/app/application/templateLibrary/packs/lifecycleContracts.py`,
  `backend/app/application/templateLibrary/packs/legacy/legacyWorldContracts.py`;
  потребители поля (packService/packScope) — только если подпись требует
  str на выходе.
- **Контракт:** поле `library_kind: LibraryKind`; на SQL/wire-границе
  остаётся `.value` / coerce через существующий `_coerce_kind`.
- **Проверка:** `test_*pack*` unittest; round-trip контракта.
- **Done:** поле typed, адаптеры не дублируют coerce.

### Шаг 2 — `connection_type` → `ConnectionTypeKey` в контрактах

- **Цель:** `ConnectionTypeKey = RegistryKey[WorldConnectionTypeRegistry]`
  существует — перенести stored-поля с `str`.
- **ТЗ:** `tz_map_light_bake.md` § connections; `tz_json_validation.md`
  § RegistryKey.
- **Файлы:** `backend/app/application/worldData/generators/assemblers/districtAssembler/connectionEntry.py`,
  `backend/app/application/worldData/generators/road/connectionPolicy.py:24`
  (dataclass-поле), `backend/app/application/worldData/generators/hydrology/types.py`
  (`connection_type` строки 84, 94).
- **Контракт:** поля `connection_type: ConnectionTypeKey`;
  membership — через существующий `validate_reference_value`/реестр
  на границе, не в поле.
- **Проверка:** профильные тесты road/hydrology/district; N+1 ключ
  мира проходит.
- **Done:** ключи соединений типизированы на контрактах.

### Шаг 3 — structure-контракты: shape/room/staircase type

- **Цель:** `roomInstance.py` поля и `default_shaft_size_type` получают
  typed-типы; рядом уже есть `ShapeType`/`StaircaseType`/`StaircaseSize`.
- **ТЗ:** `tz_locations.md` § structure generator; если раздела для
  контрактов нет — сначала строка в ТЗ.
- **Файлы:** `backend/app/application/worldData/generators/structure/room/roomInstance.py`,
  `backend/app/dataModel/locations/structure/enums/staircaseType.py`.
- **Контракт:** `shape_type: ShapeType` (enum есть),
  `room_type: RoomTypeKey` (новый alias
  `RegistryKey[WorldRoomTypeRegistry]`),
  `staircase_type: StaircaseType | None` (StrEnum есть),
  `default_shaft_size_type: StraightSize | UShapeSize | SpiralSize`
  — union: `VERTICAL_LADDER` занимает `sq_small` из чужого
  `UShapeSize`, поэтому не один enum. Публичная
  `default_shaft_size_type()` остаётся `str` — потребители ищут в
  merged `all_staircase_size_presets()`. Wire-совместимость POJO
  staircases/rooms — проверить на `test_*staircase*`/`test_*rooms*`.
- **Проверка:** unittest structure-слоя; unknown key/enum → reject.
- **Done:** поля typed, wire-значения не изменились.

### Шаг 4 — assembler поля: foundation enum + ResourceTypeKey + scaffold-валидация

- **Цель:** `foundation_type` → новый `FoundationType` StrEnum
  (`none|slab|perimeter|full|hull` — верифицировано по комменту
  `structureContext.py:9` и веткам `foundationBuilder.py`);
  `resource_type` → `ResourceTypeKey` (alias
  `RegistryKey[WorldResourceTypeRegistry]`, реестр существует).
  `roof_type` НЕ входит — отдельный шаг 9 (нормализация union).
- **ТЗ:** `tz_locations.md` § building assembler; при отсутствии
  раздела — строка ТЗ до кода.
- **Файлы:** `buildingAssembler/structureContext.py`,
  `buildingBodyTemplate.py` (`DEFAULT_FOUNDATION_TYPE` →
  `FoundationType.SLAB`), `foundationBuilder.py`, `buildingAssembler.py`,
  `resourceExtractionAssembler.py`.
- **Контракт:** `foundation_type: FoundationType`;
  `resource_type: ResourceTypeKey | None`. Литералы scaffold-контекстов
  (`hull_type`, `extraction_type`, `base_structure_type`, `ruin_style`)
  остаются `str` — см. § Scaffold ниже.
- **Проверка:** unittest assembler-слоя; smoke materialize одного
  building template.
- **Done:** foundation/resource typed; scaffold-поля — только с
  зафиксированным требованием валидации.

### Шаг 5 — `pole_kind` → enum

- **Цель:** `climatePolePreset.pole_kind` и `climatePole.pole_kind` —
  существующий `PoleKind` вместо str.
- **ТЗ:** `tz_terrain_generation.md` § climate poles (если нет —
  строка в ТЗ).
- **Файлы:** `dataModel/climate/enums/climatePolePreset.py`,
  `generators/climate/climatePole.py`, `poleResolve.py`
  (`infer_pole_kind` → возвращать `PoleKind`).
- **Контракт:** `pole_kind: PoleKind`; wire = `.wire_value`.
  `climatePoleTemperature._pole_kind_wire` уже принимает
  `.wire_value` — потребитель готов.
- **Проверка:** climate unittest; round-trip preset.
- **Done:** один enum — один источник значений.

### Шаг 6 — семейство `system_location_type`/`system_type` → `LocationTypeKey`

- **Цель:** все поля-ключи `location_type_registry` получают
  `RegistryKey[WorldLocationTypeRegistry]` (alias
  `type LocationTypeKey = RegistryKey[WorldLocationTypeRegistry]` ввести
  в `worldLocationTypeRegistry.py` при отсутствии — по образцу
  `TerrainKey`/`MaterialKey`/`DistrictTemplateKey`). Семья:
  - `LocationsIndexPin.system_location_type` (wire pin);
  - `BundleNamedLocation.system_location_type` — `StrictOnWire[LocationTypeKey]`;
    boundary `bind_payload` → `entry_for(system_type)` остаётся
    str-параметром, persist `to_db_fields()` → `model_dump(mode="json")`
    не меняется;
  - `LocationTypeEntry.system_type` — self-key записи реестра,
    `TYPE_CHECKING`-импорт реестра против цикла
    (эталон `TerrainRegistryEntry.system_terrain`);
  - `LocationTypeEntry.parent_types: list[str | None]` →
    `list[LocationTypeKey | None]` — имя во множественном числе,
    сканер-суффикс не ловит, та же семья (см. правило
    `type-kind-str-fields` § «Паттерн имени — эвристика»).
  `display_type` остаётся `str` — display-пара, не ключ.
- **ТЗ:** `tz_world_pack_storage.md` § locations index;
  `tz_locations.md` § location_type_registry;
  `tz_json_validation.md` § RegistryKey.
- **Файлы:** `backend/app/dataModel/worldPack/wire/locationsIndexWire.py`
  (+ точки записи/чтения: `locationsIndexBake.py`, потребители pins),
  `backend/app/dataModel/locations/namedLocation/bundleNamedLocation.py`,
  `backend/app/dataModel/locations/locationType/locationTypeEntry.py`,
  `backend/app/dataModel/locations/locationType/worldLocationTypeRegistry.py`
  (alias). Заодно: `structureGeneratorService.py:230` пишет
  `system_location_type="room"` литералом — call-site хардкод
  registry-ключа; перевести на `LocationTypeKey`/константу
  из реестра (принцип «ключ из реестра, не литерал»).
- **Контракт:** `StrictOnWire[LocationTypeKey]` или `DefaultWhenMissing`
  — по политике поля; historical pins при чтении — snapshot-семантика
  (без live-membership), как в WR-TD-1.
- **Проверка:** bake/read pack unittest; старый pack читается;
  `test_contract_hygiene` — записи `6*` выпадают из allowlist.
- **Done:** семейство typed; unknown type на write → reject.

**Шаг 6 реализован, готов к приёмке (2026-10-18):** `LocationTypeKey`
добавлен рядом с `WorldLocationTypeRegistry`; типизировано всё расширенное
семейство: pin, `BundleNamedLocation.system_location_type`, self-key
`LocationTypeEntry.system_type` и `parent_types`. Entry использует
`RegistryKey[WorldLocationTypeRegistry]` напрямую (тот же тип, что alias);
цикл разорван через TYPE_CHECKING/model_rebuild до canonical-записей.
`display_type`, boundary lookup-параметры и SQL-модели сохранены.
`build_locations_index` проверяет новые ключи через REF-W по resolved
registry мира (без мира — engine); historical pack/read и SQL identity
overlay сохраняют snapshot-семантику. Комната использует SYSTEM_TYPE_ROOM.
Типизация parent refs потребовала двух поправок общей границы REF-W:
`sourceValidation.registry_vocabulary` не превращает list refs в строковые
identity-ключи; `_reference_issues`/`validate_reference_value` пропускают
разрешённый None в списке ключей. Новые тесты проверяют оба случая.
Allowlist уменьшен 50→47, записей `6*` не осталось. 128 профильных и
регрессионных тестов (15 тестов семейства) + 5 integration-тестов импорта
fixture bundles прошли. Wire JSON сохранён. Этот отчёт заменяет прежний
отчёт о pin-only реализации после расширения шага мастером.
Пометка «выполнен» — после «ок» мастера.

**Дополнительная N+1-приёмка шага 6 (2026-10-18, по запросу мастера):**
`backend/tests/test_location_type_n_plus_one.py` — 4 integration-теста
через production validate_only/import/export, временную SQLite и pack IO.
Покрыты новый self-key + новый parent key (включая корневой None),
N+1-расширение parent/subtype существующего building-типа, новый тип с
существующим settlement payload-контрактом, world-scoped membership и
чтение исторического pack после удаления ключа из текущего реестра.
Проверены сохранность строк в JSON/SQL и typed-ключи в POJO/overlay.
Все 4 теста прошли; production-код этой проверкой не менялся.

### Шаг 7 — `hydrology/types.py`: `node_type` + `graph_level`

- **Цель:** `ResolvedConnectionNode.node_type` → `ConnectionNodeType`
  (enum есть: `intersection|settlement_gate|portal|building_entrance|
  location_hub|waypoint` — совпадает с DDL-комментом);
  `graph_level` → `GraphLevel` (enum есть; call sites уже пишут
  `GraphLevel.CITY.value`).
- **ТЗ:** `tz_map_light_bake.md` § hydrology; `tz_structure_connections.md`
  § graph levels.
- **Файлы:** `backend/app/application/worldData/generators/hydrology/types.py`,
  `hydrology/load/loadConnectionGraph.py` (boundary-parse из DB-str).
- **Контракт:** `node_type: ConnectionNodeType`,
  `graph_level: GraphLevel`; parse — на границе загрузки графа,
  DB-строки не трогаем.
- **Проверка:** hydro unittest; unknown literal → ошибка валидации.
- **Done:** оба поля typed.

### Шаг 8 — `task_type` → `TaskType`

- **Цель:** `task_type` (SSE-события, session snapshot, chat DTO) —
  существующий `TaskType` (`engine/taskType.py`) вместо str.
- **ТЗ:** `tz_engine_flow.md` (task_type — канал отмены/типа задачи).
- **Файлы:** `events/sseEvents.py`, `cancellation/sessionSnapshot.py`,
  `api/routes/chat.py`, `chat/chatService.py`
  (там уже `TaskType(task_type)` — убрать дубль-coerce после типизации).
- **Контракт:** `task_type: TaskType`; wire/JSON = `.value`.
  `grid_kind` — **defer**: единственный producer
  `packMapGridRender.py:214` (`"world_map_light"`); зафиксирован как
  известный дискриминатор, enum/Literal — при появлении второго kind.
- **Проверка:** chat/sse unittest; round-trip snapshot.
- **Done:** task_type typed, wire не изменился.

### Шаг 9 — `roof_type` контракт-нормализация (отложено, blocker закрытия плана)

- **Цель:** `roof_type: str | list[str]` (`structureContext.py:10`,
  `buildingBodyTemplate.py:29`, priority list) — нормализовать форму
  контракта, потом типизировать. Скаляр+список в одном поле ломает
  чистый `RoofType` enum — сначала дизайн.
- **ТЗ:** `tz_locations.md` § building assembler — дописать раздел
  контракта roof (приоритет-список vs одиночный), потом код.
- **Варианты:** (a) всегда `list[RoofType]` — скаляр → `[x]`;
  (b) `RoofType | list[RoofType]` — union как есть;
  (c) разделить: `roof_type: RoofType` + `roof_fallbacks: list[RoofType]`.
  Решение — с мастером при подходе к шагу.
- **Файлы:** `structureContext.py`, `buildingBodyTemplate.py`
  (`DEFAULT_ROOF_TYPE`), `roofBuilder.py`, `structureAreaAssembler.py`,
  `buildingAssembler.py`.
- **Done:** выбранная форма задокументирована в ТЗ, поле typed;
  план не закрывается до выполнения этого шага.

## Scaffold-контексты (валидация без enum)

`VastHullContext`, `ResourceExtractionContext`, `RuinsContext`
**нигде не конструируются** — dispatch в assembler-ы ещё не написан.
Решение: enum не вводить до producer; типы остаются `str`, но
требования к валидации фиксируются сейчас:

- `hull_type` — `ship|spaceship|airship|submarine` → `HullType` StrEnum
  (или Literal) при появлении producer.
- `orientation` (`vastHullAssembler.py:21`) → `Facing` — enum есть;
  сейчас `str` с default `Facing.NORTH.value`.
- `extraction_type` — `mine|quarry|well`.
- `ruin_style` — `collapsed|burned|overgrown`.
- `base_structure_type` — **ключ engine-реестра** (НЕ N+1, не
  произвольный str): допустимые значения = только `@register`-кинды
  `BUILDING_ASSEMBLER_REGISTRY`. Граница разбора template/JSON
  обязана проверять membership — `registry.get(kind)` /
  `in registry.all()`, helper (`require`/`kind_for`) живёт рядом с
  `AssemblerRegistry`. Запрещено: принимать str без проверки и
  дублировать список ключей литералами.
- `resource_type` — см. шаг 4 (покрывается `ResourceTypeKey`).

## Dependent-key поля (отдельный дизайн-пункт)

Поля, чей допустимый набор ключей выбирается **другим полем-родителем** —
ни один `RegistryKey` не покрывает:

- `system_location_subtype`: namespace по `system_location_type` —
  большинство типов → `LocationTypeEntry.subtypes` (встроено в реестр);
  `room` → `WorldRoomTypeRegistry`; `geographic` → `GeographicSubtype`;
  `climate_pole` → `PoleKind` (`poleResolve.py:33` уже делает
  `PoleKind.from_wire(subtype)`).
- `default_shaft_size_type`: `staircase_type` → свой size-enum
  (`StraightSize`/`UShapeSize`/`SpiralSize`); решено union для поля —
  см. шаг 3.

Дизайн-пункт: resolver parent→namespace + typed-валидация на границе.
До него поля остаются `str`.

## Порядок

Шаги независимы; рекомендуемый: **0 сначала** — gate роста карты, без
него новые `str` просачиваются параллельно с закрытием старых → 6, 1, 2
(реестровые ключи — механика уже отлажена WR-TD-1) → 3, 5, 7, 8
(существующие enum — механические) → 4 (новый FoundationType +
ResourceTypeKey) → 9 (roof — нужен дизайн-диалог) → dependent-key
секция (нужен дизайн).
Общий инвариант: ни одна правка не меняет wire/DB-представление —
только runtime-тип. План **не закрывается**, пока не выполнен шаг 9.
