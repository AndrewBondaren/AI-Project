# City generate — оставшиеся дыры (сессия)

Живой чеклист для агента. Не SoT, не `docs/`. §9.3 (`PlacementCondition`) **закрыт** — не reopen.

Продуктовые якоря (не путать оси):

- ранг поселения = `system_city_size` / wire `system_settlement_size` (`small`/`medium`/`large`)
- морфология = `system_location_subtype` (`city`/`village`/…)
- generate в **fine cells**, не метры; `footprint_m` в старых фразах ТЗ — leftover, не поле движка
- DAG / `engine/nodes/` — не трогать

## Очередь

### 1. §9.5 улицы района

Три слоя, не смешивать:

| Слой | Статус |
|---|---|
| `street_layout` кроме `grid` | не дыра v1 — **CITY-T-1f** / **CONN-PACK-1**; канон `grid`; overlay non-grid → `NotImplementedError` |
| `connections[].role` | **сделано:** `DistrictStreetRole` → spine / fill / alley; фасад при равном типе |
| inherit `street_layout` от города | leftover TZ §9.2; **POJO-C-1** omit → `GRID`; поля на скелете нет |

Дальше по §9.5: только inherit-фраза в таблице §9.2, если мастер захочет вычеркнуть.

### 2. §9.4 `required_structures`

Pass 1, `count`, `any` / один `center` работают. **Pin и purpose закрыты:** `building_template` = чертёж (`by_system_name`); назначение = `structure_types[]` движка (`BuildingPurpose`); leftover scalar `structure_type`. Район `allowed_match` like/strict. Settlement-required садится только в районы-хосты `allowed_structure_types`.

**CONN-PACK-2 closed:** несколько `position: center` — один кластер вокруг home-модуля inner bbox района (4-соседство модулей, первый ближе к home). Рамка обходит AABB hull. Не влезло — leftover, не проход 2. Канон civic — один `town_hall`. Дальше по §9.4 не осталось.

### 3. §9.2 / §6.3 барьеры поселения (**CITY-T-1c**)

Shrink слота района от барьера поселения есть. Клетки стен: `planner/barriers.py` эвристика `_WALLED_SIZES` / `_NO_WALL_SIZES` (старые morph-ключи), **не** читает `PerimeterBarrier` на скелете. Канонические ранги `small`/`medium`/`large` → **нет стен**. `DistrictAssembler.assemble` не заполняет `DistrictLayout.barrier_cells`.

### 4. §9.6 / LOC-T-2 footprint generate

POJO: `resolve_settlement_footprint_multiplier(subtype, size)`. Generate: `planner/footprint.py` → `_size_only_morphology()` — **не** subtype этого поселения. Village и city одного ранга получают одну сторону footprint.

### 5. Persist / library (не §9)

Канон C11 extract: parent здания = район. Legacy `settlementLayoutExtract.collect_building_locations` parent = **поселение** → ложный authored-skip (**CITY-T-5a** / **5g**). **CITY-T-2b**: packing ест layout-тела; world registry uid → SQL library не SoT.

### 6. Deferred / не v1

Organic city footprint, world-routes в `settlement_gate`, `init_mode`, interiors, C21 leftovers. **CITY-T-5i**: topology planner с оркестратора **и** assembler если нет freeze.

## Закрыто в этой нитке (не трогать)

- §9.3: `PlacementCondition.size` = порог ранга на чертеже; host rank на скелете; generate сравнивает host vs порог.
- §9.5.1 `role` на `grid`: spine / fill / alley + фасад при равном `connection_type`.
- §9.4 pin: `required_structures[].plot_template` = чертёж участка; leftover `building_template`; `structure_types[]` = engine `BuildingPurpose` на чертеже (не ключ строки района; pin не purpose-pool).
- CONN-PACK-2: кластер `center` вокруг home inner bbox; рамка по hull; leftover не проход 2.
- Назначения зданий: дерево семей → листьев ([tz_building_generator.md](../../docs/tz_building_generator.md) §2.1); рецепты паков `WorldPurposePackRegistry`; включённые id `purpose_packs` (omit → `[base, fantasy]`); церковь `culture.church`; телепорт `transit.portal`. **Код:** дерево + реестр рецептов + `purpose_packs`; `allowed` expand семьи; packing ∩ enabled. Overlay `base` заморожен. `allowed_match` like/strict; omit чертежа → `[house]`; хост settlement-required = membership expanded `allowed` ∩ enabled.
- Специализация → семья, мир → листья: `SettlementSpecializationEntry.allowed_family`; штамп `DistrictSlot.allowed_structure_types`; `agrarian` удалён. `required_structure_types` / `subjects_to_structure_types` на записи — ValidationError.
- Канон `size="town"` → `WorldSettlementSizeRegistry.default_system_size()` (`medium`).
- Wire `min_settlement_size`; leftover JSON `min_city_size` → тот же enum.
- Невалидный ранг на generate → `medium` + warning, generate идёт (`resolve_settlement_size_key`) — **намеренно**.
- Alias `min_city_size` — leftover JSON, не продуктовая дыра.
- Water connectivity для `adjacent_terrain` — ТЗ-open, не дыра кода §9.3.
