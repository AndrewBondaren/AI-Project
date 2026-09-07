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
| **Status** | `open` / `resolved` / `leave` / `blocked` |

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

Generate: unknown **size** → `medium` + WARNING (`jsonValidation` / `resolve`). Omit size → `medium` без warning.

---

## Open — реестр или enum уже есть

Дешёвый первый: **POJO-C-1** (`StreetLayout` уже StrEnum, как density). Дальше — identity+refs одним срезом.

### POJO-C-1 — `street_layout` → `StreetLayout`

**Status:** open

`DistrictTemplateEntry.street_layout`: сейчас `DefaultOnWire[str] = StreetLayout.GRID.value`. Enum: `dataModel/roads/enums/streetLayout.py`.

### POJO-C-2 — mood

**Status:** open

| Поле | Сейчас |
|---|---|
| `LocationMoodEntry.system_mood` | `StrictOnWire[str]` |
| скелет / NL `system_location_mood` | `str` |

Реестр: `WorldLocationMoodRegistry`.

### POJO-C-3 — specialization identity

**Status:** open

| Поле | Сейчас |
|---|---|
| `SettlementSpecializationEntry.system_specialization` | `StrictOnWire[str]` |
| `SettlementSpecializationBind.system_specialization` | `StrictOnWire[str]` |

Реестр: `WorldSettlementSpecializationRegistry`. `subjects` / `subject_kind` — не этот ID (`leave` / TODO extract).

### POJO-C-4 — чертёж района `system_name`

**Status:** open

Identity `DistrictTemplateEntry.system_name` + refs:

- `TypicalDistrictRef.system_name` (pin чертежа, не `district_type`)
- `DistrictTopologySlot.template_system_name`

`RegistryKey[WorldDistrictTemplateRegistry]`. Не брендировать как ткань `civic`.

### POJO-C-5 — `connection_type`

**Status:** open

Identity `ConnectionTypeEntry.system_connection_type` ещё `str`. Refs:

- `DistrictConnection.connection_type`
- `DistrictTopologyEntry.connection_type`
- `frontage_type_order[]` (скелет, район, `FrontageTypeOrder.order`)

Реестр: `WorldConnectionTypeRegistry`. Один срез на identity + все refs.

### POJO-C-6 — `PerimeterBarrier.template`

**Status:** open

Ref → `barrier_template_registry` (`WorldBarrierTemplateRegistry`).

### POJO-C-7 — `RequiredStructure.building_template`

**Status:** open

Pin `system_name` чертежа здания (CITY-T-2d), не `structure_type`.

### POJO-C-8 — `RequiredStructure.position`

**Status:** open

Закрытые литералы `any` / `center` в модуле. ENUM-E, не RegistryKey.

### POJO-C-9 — `PerimeterBarrier.sides`

**Status:** open

Сейчас `list[str]`; разбор в `resolved_host_sides` → `Facing`. Цель: `list[Facing]` (кардиналы).

### POJO-C-10 — NL parent materials

**Status:** open

`BundleNamedLocation.parent_wall_material` / `parent_floor_material` — тот же `MaterialKey`, что `dominant_material`. Не скелет (скелет не reopen).

---

## Leave — намеренно `str`

| Поле | Почему |
|---|---|
| `display_*` | не ключ реестра |
| `district_type` / `district_subtype` (шаблон, typical, zone preference, `PlacementCondition.district_type`) | нет реестра ткани; subtype ≠ identity specialization-строки |
| `LocationTypeSubtypeEntry.typical_district_types` | та же ткань |
| `allowed_structure_types`, `required_structure_types`, ключи `structure_counts` / `structure_priority` | kind библиотеки зданий, не N1-W identity |
| `subjects`, `subject_kind`, ключи `subjects_to_structure_types` | N+1 в несколько реестров; TODO в POJO bind/entry |
| uid (`location_uid`, `node_uid`, `paired_exit_uid`, …) | экземпляр |
| `LocationTypeSubtypeEntry.footprint_by_size` ключи | не SoT метров; не этот обход |

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
