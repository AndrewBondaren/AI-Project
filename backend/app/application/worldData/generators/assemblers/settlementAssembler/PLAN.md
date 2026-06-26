# План реализации SettlementAssembler

Оркестратор полной генерации поселения. ТЗ: `docs/tz_assembler_hierarchy.md` §2, `docs/tz_city_generation.md`, `docs/tz_structure_connections.md` §5, `docs/tz_economic_tier.md`.

**Точка входа:** `SettlementAssembler.assemble(world, settlement, terrain_cells?) → SettlementLayout`

**Поток (текущий):**

```
_build_skeleton
  → plan_district_slots (+ plan_settlement_entries)
  → DistrictAssembler × N
  → plan_city_street_grid
  → _plan_barriers
```

**Planner-модули:** `planner/footprint.py`, `placement.py`, `districts.py`, `streets.py`, `defaults.py`

**Smoke test:** `backend/scripts/debug_settlement.py` (town 1×1, city 2×2, shared node_uid)

---

## Фаза A — Connections graph (city + district) ✅

| Задача | Статус | Где |
|---|---|---|
| `CitySkeleton` из `NamedLocation` + `TierResolver` | ✅ | `_build_skeleton` |
| Footprint: `footprint_multiplier × cell_size_m`, grid n×n | ✅ | `planner/footprint.py` |
| `DistrictSlot` + `placement_conditions` | ✅ | `planner/placement.py`, `districts.py` |
| `plan_settlement_entries`: shared registry, through_road W↔E/S↔N, entry_point | ✅ | `planner/streets.py` |
| `block_size` по `settlement_density` (единый с `gridLayout`) | ✅ | `road/blockSize.py` |
| `plan_city_street_grid`: perimeter gates + inter-district corridors (n>1) | ✅ | `planner/streets.py` |
| `DistrictAssembler` → district nodes/edges (grid v1) | ✅ | `districtAssembler/` |
| DEBUG smoke: shared `node_uid` на стыке x=3000 | ✅ | `debug_settlement.py` |

---

## Фаза B — Semantic-first на city graph ✅ (частично)

| Задача | Статус | Зависимости |
|---|---|---|
| `resolve_material` + `skeleton.economic_tier` на city edges | ✅ | `planner/streets.py` |
| `has_sidewalk` по `settlement_density` (не sparse) | ✅ | `_city_has_sidewalk` |
| `resolve_sidewalk_width` — лог tier → width (sidewalk child edges — позже) | ✅ | INFO log |
| `road_tier_bonus` / durability из `economic_tier_registry` | ⬜ | TZ §4.3 |
| Per-edge sidewalk из template `connections[].sidewalk` | ⬜ | |

**Acceptance:** city edges несут width/material/sidewalk согласованные с tier скелета; unit/smoke на одном tier.

---

## Фаза C — Placement районов (доработка §9) ✅

| Задача | Статус | Где |
|---|---|---|
| Приоритет «специализированные > общие» (§9.6) | ✅ | `template_specialization_key`, pool + zone |
| `required_structures` на `DistrictSlot` + лог в `DistrictAssembler` | ✅ | `districtSlot`, `districtAssembler` |
| `economic_tier_range` / `economic_tier_band` на шаблоне района | ✅ | `planner/economic.py` |
| `building_tier_compatible` ±1 для `_assign_template` | ✅ | `districtAssembler` |
| `ground_z` из terrain в footprint | ✅ | `planner/terrain.py` |
| `cell_zone` в `placement_conditions` (civic → center) | ✅ | `defaults.py`, `placement.py` |
| Несколько районов в одной global cell (sub-cells) | ⬜ | открытый вопрос §10 |
| Физическое размещение `required_structures` | ⬜ | фаза E |

---

## Фаза D — Barriers ✅

| Задача | Статус | Где |
|---|---|---|
| `_plan_barriers` → `barrier_template_registry` | ✅ | `planner/barriers.py`, `barrierDefaults.py` |
| Perimeter wall по footprint + tier | ✅ | `plan_settlement_barriers`, gate coords = `footprint_gate_coordinates` |
| `SettlementLayout.barrier_cells` заполнен | ✅ | `settlementAssembler.py` |

**Acceptance:** town/city → `barrier_cells` > 0; gate terrain на координатах settlement_gate; hamlet/village → 0.

---

## Фаза E — Кэш зданий + передача вниз (§7.7) ✅

| Задача | Статус | Где |
|---|---|---|
| `SettlementAssembler` создаёт `dict[template_name, StructureLayout]` | ✅ | `buildingCache.py` |
| Передача cache в `DistrictAssembler.assemble(..., layout_cache=)` | ✅ | `settlementAssembler.py` |
| generate-first bin-packing по `occupied_footprint` | ✅ | `districtAssembler/planner/areaSlots.py` |
| Warning-политика при неразмещении | ✅ | `areaSlots.py`, `buildingCache.py` |
| `StructureAreaAssembler` — layout из cache + `translate_layout` | ✅ | `structureAreaAssembler.py` |
| `OccupiedFootprint` на `StructureLayout` | ✅ | `structureGeneratorService.py` |
| Default templates для smoke (`town_hall`, `inn_small`) | ✅ | `planner/buildingDefaults.py` |

**Acceptance:** один `town_hall` — одна генерация на город; civic получает `area_layouts=1`.

---

## Фаза F — Map occupancy ✅

| Задача | Статус | Где |
|---|---|---|
| Резервирование `map_cells` под footprint (`location_uid` = settlement) | ✅ | `planner/mapOccupancy.py` |
| `footprint_grid_rect` — связь метры ↔ global grid | ✅ | `planner/footprint.py` |
| `SettlementLayout.occupancy_cells` | ✅ | `settlementLayout.py` |
| `collect_map_cells_from_layout` + `rebind_layout_to_building` | ✅ | `layoutCells.py` |
| `SettlementGeneratorService` (generate + needs_geometry) | ✅ | `settlementGeneratorService.py` |
| Lazy hook: `lazy_settlement` engine node | ✅ | `engine/nodes/.../lazySettlementNode.py` |
| Persist NamedLocation зданий в БД | ⬜ | отдельно от map_cells |

**Acceptance:** town 1×1 → 1 occupancy cell; city 2×2 → 4; `needs_geometry` false после generate.

---

## Фаза G — Footprint v2 (organic) ⬜

| Задача | Статус |
|---|---|
| `radial_organic` / `river_linear` / … | ⬜ | §10 TODO |
| Convex hull + terrain deformation | ⬜ | ждёт terrain v2 |

---

## Фаза H — Топология z ⬜

| Задача | Статус |
|---|---|
| Наземный + подземный + воздушный слой одновременно | ⬜ | `tz_assembler_hierarchy.md` §2 |
| Мосты / тоннели между ячейками поселения | ⬜ |

---

## Техдолг / cleanup

| Задача | Статус |
|---|---|
| Удалить legacy `cityAssembler.py`, `cityLayout.py` | ✅ удалены; код = `SettlementAssembler` / `SettlementLayout` |
| INFO-лог: tier = `skeleton.economic_tier` (resolved) | ✅ |
| ТЗ: `CityAssembler` → `SettlementAssembler`, `CityLayout` → `SettlementLayout` | ✅ |
| `CitySkeleton.state_uid` для полного контракта LLM | ⬜ опционально |
| Persist `SettlementLayout` → `connection_nodes` / `connection_edges` в БД | ⬜ | `tz_structure_connections.md` §6 |

---

## Порядок работ (рекомендуемый)

1. **D** — barriers
2. **F** — map_cells + lazy hook
5. **G/H** — v2 footprint и z-topology
6. **B** (остаток) — road_tier_bonus, per-district sidewalk на city edges

---

## Вне scope SettlementAssembler

- Интерьеры, мебель → `StructureInteriorAssembler`
- Highway / sea_route / portal между поселениями → `WorldGenerator`
- Import validator economic_tier refs → отложено (`tz_economic_tier.md` §6)
