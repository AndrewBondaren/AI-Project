# dataModel — типизация city POJO (`str` → RegistryKey / ENUM-E)

**Тип:** инженерное ТЗ / living registry. Не алгоритм generate.  
**Scope:** POJO города в `backend/app/dataModel/settlement/` + зеркала (`CitySkeleton`, `BundleNamedLocation` overlay, `EconomicTierRange`, layout `economic_tier`).  
**Не это ТЗ:** дубли литералов SoT — [`tz_datamodel_pojo_discrepancies.md`](./tz_datamodel_pojo_discrepancies.md) (`POJO-D-*`); nested generate `list[dict]` — **POJO-D-16**.  
**Словарь wire:** [`tz_json_validation.md`](./tz_json_validation.md) §0 `RegistryKey[R]` / ENUM-E / REF-W.  
**Продукт города:** [`tz_city_generation.md`](./tz_city_generation.md).  
**Срез:** 2026-09-07.

Новый leftover → новый ID; resolved не удалять.

| Поле | Значение |
|---|---|
| **ID** | `POJO-C-*` |
| **Status** | `open` / `locked` / `resolved` / `leave` / `blocked` |

**Правила среза**

1. Identity строки реестра и refs на неё — **в одном касании**. Иначе бренд на условии/скелете фейковый.
2. Миграция N1-W — **при касании**, не массово по всему `dataModel/`.
3. Membership miss terrain/tier/material — прежний REF-W / warn+default. **Не** копировать политику size→medium.
4. Не изобретать `WorldDistrictTypeRegistry`. `district_type` / `district_subtype` — голый `str` (`leave`).
5. Скелет: size / tier / material / density / overlay `Literal` — **resolved, не reopen**.

---

## Resolved

| ID | Что | Тип |
|---|---|---|
| POJO-C-R1 | `RegistryKey[R]`, `registry_key_target`, peel `list[T]` / alias / `T \| None` | `registryKey.py` |
| POJO-C-R2 | `SettlementSizeEntry.system_size` + NL/скелет `system_city_size` + `PlacementCondition.size` | `SettlementSizeKey` |
| POJO-C-R3 | `EconomyTierEntry.system_tier` + скелет `economic_tier` + NL `system_economic_tier` + `EconomicTierRange` + layout `economic_tier` + `PlacementCondition.tier` + material row `economic_tier` | `EconomyTierKey` |
| POJO-C-R4 | `TerrainRegistryEntry.system_terrain` + `PlacementCondition.terrain_types` | `TerrainKey` |
| POJO-C-R5 | `MaterialRegistryEntry.system_material` + скелет/NL `dominant_material` | `MaterialKey` |
| POJO-C-R6 | `PlacementCondition.zone`; `WorldDistrictZonePreference.zone` уже был | `CellZone` |
| POJO-C-R7 | скелет/NL `settlement_density`; `DistrictTemplateEntry.density`; `DistrictDensity` = StrEnum | `DistrictDensity` |
| POJO-C-R8 | `NAMED_LOCATION_OVERLAY_FIELDS` / `NAMED_LOCATION_FIELD_ALIASES` | `Literal` имён полей + assert ⊆ `model_fields` |
| POJO-C-R9 | `CitySkeleton` зеркало: size / tier / material / density | те же типы, не параллельный `str` |
| POJO-C-1 | `DistrictTemplateEntry.street_layout` | `StreetLayout` (`DefaultOnWire` = `GRID`; omit/invalid → GRID + warning) |
| POJO-C-7 | чертёж участка: `BuildingLayoutTemplate.system_name` + `RequiredStructure.building_template` + ключи `plot_counts` / `plot_priority`; rename `structure_counts`/`structure_priority` | `DrawingKey` = `RegistryKey[BuildingLayoutTemplate]` |
| POJO-C-5 | `ConnectionTypeEntry.system_connection_type` + `DistrictConnection` / `DistrictTopologyEntry.connection_type` + `frontage_type_order[]` + `FrontageTypeOrder.order` | `ConnectionTypeKey` |
| POJO-C-2 | `LocationMoodEntry.system_mood` + скелет / NL / `CitySkeleton.system_location_mood` | `LocationMoodKey` |
| POJO-C-3 | `SettlementSpecializationEntry.system_specialization` + `SettlementSpecializationBind.system_specialization` | `SettlementSpecializationKey` |
| POJO-C-4 | `DistrictTemplateEntry.system_name` + `TypicalDistrictRef.system_name` + `DistrictTopologySlot.template_system_name` | `DistrictTemplateKey` |
| POJO-C-6 | `BarrierTemplateEntry.system_type` + `PerimeterBarrier.template` | `BarrierTemplateKey` |
| POJO-C-8 | `RequiredStructure.position` | `RequiredStructurePosition` (`any` / `center`; `DefaultOnWire` = `ANY`) |
| POJO-C-9 | `PerimeterBarrier.sides` | `list[Facing]` (кардиналы; omit/`[]` = все четыре) |
| POJO-C-10 | `BundleNamedLocation.parent_wall_material` / `parent_floor_material` | `MaterialKey` (как `dominant_material`; не скелет) |

Generate: unknown **size** → `medium` + WARNING (`jsonValidation` / `resolve`). Omit size → `medium` без warning.

`street_layout`: `DefaultOnWire` (не `DefaultEnumOnWire` / не 422). Generate — `StreetLayout.for_generator`; non-grid layout — **CITY-T-1f**, не этот срез. TZ §9.2 inherit-from-city не реализован (у скелета нет `street_layout`).

`system_location_mood`: omit/`null` → `None` (нет дефолтного mood). `""` → reject. Не size→medium.

`system_specialization`: identity роли, не `district_subtype`. `subjects` / `subject_kind` — не этот ID.

`DistrictTemplateKey`: чертёж района (`civic_center`), не ткань `civic` и не `DrawingKey` участка. Pin `TypicalDistrictRef.system_name`: omit/`null` → `None` (подбор по `district_type` / subtype); `""` / blank на `resolve_model` → `None` + WARNING `invalid; using field default` (не 422). Identity и `DistrictTopologySlot.template_system_name`: `""` → reject. Не size→medium.

`BarrierTemplateKey`: чертёж барьера (`wooden_fence` / `stone_fence` / `city_wall`), identity `system_type` (не `system_name`). `PerimeterBarrier.template`: omit/`null` → `None` (скип инстанса); `""` / blank на `resolve_model` → `None` + WARNING (не 422, не `wooden_fence`). Identity `system_type`: `""` → reject. Relief `structure_refs` — не этот срез.

`PerimeterBarrier.sides`: `DefaultOnWire[list[Facing] \| None] = None`. Только кардиналы. Omit/`null`/`[]` → четыре прямые. Intercardinal / unknown в списке — skip элемента + warning; не 422 на барьер. После skip пусто → как `[]`. Не `RequiredStructure.position`, не горные `sides`.

`RequiredStructure.position`: ENUM-E `RequiredStructurePosition` (`any` / `center`). `DefaultOnWire` = `ANY` (как `street_layout`, не `StrictEnumOnWire` / не 422). Omit → `any`. `""` / unknown на `resolve_model` → `any` + WARNING. `PackingToken.position` и CONN-PACK-2 — не этот срез. Не `CellZone.center`, не `Facing`.

`parent_wall_material` / `parent_floor_material`: тот же `MaterialKey`, что `dominant_material` (identity уже branded). Omit/`null` → `None` (generate позже берёт `DEFAULT_WALL_MATERIAL` / floor). `"stone"` → branded. `""` → reject. Не size→medium. Не заполнять `wood`/`stone` на import. Скелет не reopen; SQL `NamedLocation` остаётся `str | None`. `MaterialPick` на building/barrier — не этот срез.

### Контракт connection_type (POJO-C-5)

Реестр: `WorldConnectionTypeRegistry` (`worlds.connection_type_registry`, N1-W-06).  
Алгоритм фасада / нитки — [`tz_structure_connections.md`](./tz_structure_connections.md) §5.1.3; здесь только типы POJO.

Не ENUM-E. Не `ConnectionNodeType` (ворота на **узле** ≠ тип **ребра**). Wire JSON — строка (`"road"`). Пустая строка — reject (`RegistryKey` `min_length=1`). Membership в реестре **мира** — REF-W / `entry_for` / generate skip, не 422 на parse.

#### Тип

```python
type ConnectionTypeKey = RegistryKey[WorldConnectionTypeRegistry]
```

Паттерн как `EconomyTierKey`: alias после класса реестра + `ConnectionTypeEntry.model_rebuild()` (identity в entry через `TYPE_CHECKING`, цикл registry→entry).

`require` / `require_engine` / `keys` / `road_mask_connection_types` / `hydrology_connection_types` возвращают `ConnectionTypeKey` (или `frozenset`/`tuple` того же). Токены lookup (`ROAD_MASK_CONNECTION_TYPE_KEYS`, `SYSTEM_CONNECTION_TYPE_ROAD`) остаются `str` — аргументы `require_engine`, не параллельный словарь типов.

Wire-имена **не** сливать ([POJO-D-3](./tz_datamodel_pojo_discrepancies.md)): identity = `system_connection_type`; refs на ребре/шаблоне = `connection_type`.

#### Identity + refs — один срез

| Место | Поле | Политика |
|---|---|---|
| `ConnectionTypeEntry` | `system_connection_type` | `StrictOnWire[ConnectionTypeKey]` |
| `DistrictConnection` | `connection_type` | `StrictOnWire[ConnectionTypeKey]` |
| `DistrictTopologyEntry` | `connection_type` | `StrictOnWire[ConnectionTypeKey]` |
| `DistrictTemplateEntry` | `frontage_type_order` | `DefaultOnWire[list[ConnectionTypeKey] \| None] = None` |
| `SettlementSkeleton` | `frontage_type_order` | то же |
| `BundleNamedLocation` | `frontage_type_order` | то же (`_skeleton_default`) |
| `CitySkeleton` | `frontage_type_order` | `list[ConnectionTypeKey] \| None` |
| `FrontageTypeOrder` | `order` | `DefaultOnWire[list[ConnectionTypeKey]]` |

`DEFAULT_CONNECTION_TYPE` / `DistrictConnection.street_default()` — `require_engine(SYSTEM_CONNECTION_TYPE_ROAD)`. Литерал `"road"` в генераторе не возвращать.

#### `frontage_type_order`

Элементы списка — ключи **ребра** (`ConnectionTypeKey`), не `structure_type`, не чертёж участка, не `district_type`.

| Wire | Смысл |
|---|---|
| omit / `null` / `[]` | наследовать уровень выше |
| список строк | порядок = приоритет парадного (выше в списке — главнее) |
| ключ не из реестра мира | **skip** + warning; не валить generate; если после skip пусто — наследовать |
| `""` в массиве | type fail POJO (не skip) |

Резолв (первый непустой kept): **район** → **город** (`CitySkeleton` / NL overlay) → **дефолт движка** (`FrontageTypeOrder.canonical_defaults().order`). Мирового N+1-списка «на все города» в v1 нет.

Дефолт движка (порядок SoT `FrontageTypeOrder`, ключи — `require_engine`):

`highway` > `road` > `dirt_road` > `alley` > `trail`

Не сравнивать фасад по этому списку: `air_route`, `sea_route`, `portal`, `yard_path`. `bridge` / `settlement_gate` наследуют ранг продолжаемого ребра. `sidewalk` — ранг `parent_edge`. Авторский список **может** содержать любой ключ реестра мира (в т.ч. N+1 и `sidewalk`); generate ранжирует только касающиеся полотна. Площадь / `plaza`: список **не** выбирает парадную (connections §5.1.3).

SQL `named_locations.frontage_type_order` — JSON-массив; dataclass `NamedLocation` остаётся `list \| None`. Coerce на `SettlementSkeleton` / `CitySkeleton`. **0001 не менять.**

#### Не этот срез (тот же словарь, чужой домен / следующий touch)

Правило 2: N1-W при касании POJO, не массово.

| Поле | Почему |
|---|---|
| `RoadSettingsEntry.system_connection_type` | roads (`connection_type` alias); следующий touch `WorldRoadSettings` |
| `DeclaredRiverSegment.connection_type` | hydrology declare |
| `HydrologyConnectionType` | ENUM-E subset; values уже `require_engine` |
| `connection_edges.connection_type` / SQL dataclass ребра | persist графа; REF-W-CONN на import JV-0b; coerce как прочие NL columns |
| width helpers / `connectionWidthDefaults` lookup `str` | аргумент `require_engine`, не identity-поле |

Не трогать: `ConnectionNodeType`, `graph_level`, `role` на `DistrictConnection`, numeric width/road_settings.

---

## Open — реестр или enum уже есть

Очередь POJO-C закрыта. Осталось blocked `architectural_style` (реестр в ТЗ, POJO нет).

### Контракт участка (locked)

Три слоя. Не смешивать.

| Слой | Что это | Где живёт | Пример |
|---|---|---|---|
| Назначение | лист `BuildingPurpose` (+ семья в каталоге, не на чертеже) | `structure_types[]`; фильтр района — лист или `BuildingPurposeFamily`; паки мира режут каталог | `cafe`, `temple`, `portal`; комбо `[house, workshop]` |
| Чертёж участка | **тип участка** = identity шаблона | `BuildingLayoutTemplate.system_name` | `tavern_1`, `inn_small` |
| Здание на участке | тело generate (§3) или leftover корневые `levels` | `building` / leftover `levels` | `fixtures/templates/tavern_1.json` внутри `inn_small` |
| Участок | инстанс после packing | `AreaSlot` / `AreaLayout` | клетка в районе |

`structure_types` **не** владеет участком и **не** ключ counts. Режет пул («в квартале можно мастерские»). Generate среди чертежей с подходящими тегами — rng + тир + subjects + `like`/`strict`. Pin конкретного чертежа — `required_structures[].building_template` = `system_name`, не purpose.

**Поля**

| Поле | Тип | Смысл |
|---|---|---|
| `plot_counts` | `DefaultOnWire[dict[DrawingKey, int] \| None] = None` | N **участков** = N копий этого чертежа. Район перекрывает город **по ключу**. Нет поля / нет ключа — не ноль, смотреть ниже. Явный `0` — не сажать |
| `plot_priority` | `DefaultOnWire[dict[DrawingKey, int] \| None] = None` | очередь посадки, **не** N. Нет ключа → `0` (проход 2) |
| `allowed_structure_types` | `list[BuildingPurpose \| BuildingPurposeFamily] \| None` | фильтр: лист или семья; omit = легальный каталог мира; `[]` = pins only |
| `allowed_match` | `BuildingPurposeMatch` | default `like`; `strict` = участок ⊆ фильтра |
| `required_structures[].building_template` | тот же `DrawingKey` | pin чертежа (`by_system_name`); `count` на строке **главнее** `plot_counts` |
| `required_structures[].structure_type` | leftover optional purpose | дубль ключа рецепта поселения, не pin, не ключ map |

`DrawingKey` — `RegistryKey[BuildingLayoutTemplate]` (identity чертежа generate, не uid `WorldBuildingTemplateRegistry`). Не ткань района. Не `PlotType` / `StructureType`.

Резолв N ([`tz_structure_connections.md`](./tz_structure_connections.md) §5.1.3): `required.count` → `plot_counts` района → `plot_counts` города → **1**.

Зеркала тех же map: `DistrictTemplateEntry`, скелет, NL overlay / SQL. Import: alias `structure_counts` / `structure_priority`.

Не трогать (чужой контракт):

| Имя | Почему |
|---|---|
| `structure_type` / `structure_types` | назначение чертежа (engine enum + leftover scalar) |
| `allowed_structure_types` / `required_structure_types` / `subjects_to_structure_types` | фильтр purpose |
| `required_structures` | массив pin, не map N |
| `RequiredStructure.structure_type` | leftover optional purpose на строке рецепта |
| `structure_context` / `default_structure_context` / `StructureAreaAssembler` / `ASSEMBLER_REGISTRY` | generate здания |
| `structure_canal` / `structure_refs` | relief/канал |
| pack `structure_path` / `structure_hash` | world pack |

---

## Leave — намеренно `str`

| Поле | Почему |
|---|---|
| `display_*` | не ключ реестра |
| `district_type` / `district_subtype` (шаблон, typical, zone preference, `PlacementCondition.district_type`) | нет реестра ткани; subtype ≠ identity specialization-строки |
| `LocationTypeSubtypeEntry.typical_district_types` | та же ткань |
| `allowed_structure_types`, `required_structure_types`, `RequiredStructure.structure_type` | назначение чертежа (`BuildingPurpose` / leftover scalar), не identity участка; не ключи counts |
| `subjects`, `subject_kind`, ключи `subjects_to_structure_types` | N+1 в несколько реестров; TODO в POJO bind/entry |
| uid (`location_uid`, `node_uid`, `paired_exit_uid`, …) | экземпляр |
| `LocationTypeSubtypeEntry.footprint_by_size` ключи | не SoT метров; не этот обход |
| `CanalStructureSpec.structure_refs` / relief knobs `structure_refs` | relief/канал; не city PerimeterBarrier |

---

## Blocked

| Поле | Почему |
|---|---|
| скелет / NL `architectural_style` | в [`tz_architectural_style.md`](./tz_architectural_style.md) есть реестр, **POJO нет** (черновик, только LLM) |

---

## Вне города (не очередь POJO-C)

`BundleNamedLocation.system_location_type` / `system_location_subtype`, `LocationTypeEntry.system_type` — локации, не этот документ. Subtype≠size уже разведены (LOC-T-2).

`rooms[].economic_tier` — пока `list[dict]` (**POJO-D-16**).

SQL dataclass `NamedLocation` остаётся `str \| None`; coerce на POJO / `CitySkeleton`.

---

## Changelog

| Дата | Изменение |
|---|---|
| 2026-09-07 | Документ: очередь city `str`→RegistryKey/ENUM-E; resolved C-R1…C-R9; open C-1…C-10; leave ткань/`structure_type`/subjects; blocked style |
| 2026-09-07 | POJO-C-1 resolved: `street_layout` → `DefaultOnWire[StreetLayout] = GRID` |
| 2026-09-07 | Контракт участка locked: чертёж = тип участка; `plot_counts` ключи = DrawingKey (C-7); `structure_type` только фильтр |
| 2026-09-07 | POJO-C-7 resolved: `DrawingKey`; `plot_counts` / `plot_priority`; alias старых имён map |
| 2026-09-07 | POJO-C-5 **locked**: `ConnectionTypeKey`; identity + city refs включая `frontage_type_order`; roads/hydrology/SQL edges — не срез |
| 2026-09-07 | POJO-C-5 **resolved**: `ConnectionTypeKey` на identity + city refs; `FrontageTypeOrder.order` через `require_engine` |
| 2026-09-07 | POJO-C-2 **resolved**: `LocationMoodKey`; omit/`null` → `None`; не size→medium |
| 2026-09-07 | POJO-C-3 **resolved**: `SettlementSpecializationKey` на entry + bind; subjects/`district_subtype` не трогать |
| 2026-09-07 | POJO-C-4 **resolved**: `DistrictTemplateKey` на identity + pin `TypicalDistrictRef.system_name` + `template_system_name`; pin `""` → `None` + warning; ткань `district_type` leave |
| 2026-09-07 | POJO-C-6 **resolved**: `BarrierTemplateKey` на identity `system_type` + `PerimeterBarrier.template`; `""` → `None` + warning; `sides`/relief `structure_refs` не срез |
| 2026-09-08 | POJO-C-8 **resolved**: `RequiredStructurePosition` (`any`/`center`); omit/invalid → `any` + warning; CONN-PACK-2 не срез |
| 2026-09-08 | POJO-C-9 **resolved**: `PerimeterBarrier.sides` → `list[Facing]` (кардиналы); skip unknown/intercardinal + warning |
| 2026-09-12 | Чертёж участка: `occupied_footprint` + вложенное `building` (пример `inn_small` ← `tavern_1`). Малые пристройки не в чертеже. |
| 2026-09-12 | Дерево назначений: семья → лист; `allowed` может быть семьёй; паки мира. SoT [tz_building_generator.md](./tz_building_generator.md) §2.1 |
| 2026-09-12 | Назначение участка: `structure_types[]` + `BuildingPurpose` (не N+1); `allowed_match` like/strict; pin только `system_name` |
| 2026-09-08 | POJO-C-10 **resolved**: NL `parent_wall_material` / `parent_floor_material` → `MaterialKey`; omit/`null` → `None`; `""` → reject. Не скелет, не `MaterialPick` |
