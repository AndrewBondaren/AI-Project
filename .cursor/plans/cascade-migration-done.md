# План: миграция старых потребителей на каскадный движок + зачистка старых логик — done

Статус: **done** (M1–M10 закрыты 2026-10-05; отложенные кандидаты —
без шага до решения, см. конец файла). Предшественник:
`cascade-context-resolution-done.md` (S1–S3
done — контракт, граф, `extend()` работают; это план его S4 + вынос
старья). Сверочная матрица параметров (родитель/наследник по уровням):
[`cascade-params-matrix.md`](cascade-params-matrix.md).

## Цель

Все точки потребления `economic_tier` получают значение из
`LocationContext`, построенного `extend()` на границах scope. Старые
логики (`TierResolver`, `building_band`-проводка, внутренний резолв
`resolve_room_materials`) удаляются — не помечаются, а вычищаются.

## ТЗ

`docs/tz_cascade_context.md` §4 (движок), §6 (stamp на NL), §7
(потребители); `docs/tz_economic_tier.md` §4 (каскад), §9 (поля);
правило «обход движка запрещён» — `pojo-world-row-wire.mdc`.

## Текущие точки старой логики (инвентарь)

| Точка | Что делает | Новая форма |
|---|---|---|
| `tierResolver.TierResolver.resolve` ×8 | ручной каскад + band + median | `ctx.economic_tier` |
| `settlementAssembler.py:175`, `settlementGeneratorService.py:73`, `settlementOutdoorPackingJob.py:152` | `resolve(world, city=settlement)` → skeleton | settlement ctx → `ctx.economic_tier` |
| `structureGeneratorService.py:344,363,733,762` | `resolve(world, building, building_band, rng)` по фазам | `ctx.economic_tier` один раз |
| `wallOpening.py:144` | `resolve(room_tier, building_tier)` → glass | `room_ctx.economic_tier` |
| `materialResolver.resolve_room_materials:90` | резолвит tier внутри | принимает `effective_tier`, не резолвит |
| `StructureContext.building_band` + `building_band=` ×8 функций | проводка band-строки до roomFactory | `context: LocationContext` в StructureContext |
| `structureAreaAssembler.py:106` | читает `template.economic_tier_band` | `district_ctx.extend(area link)` |
| `roomFactory.py:165`, `shaftFactory.py:116` | `resolve_room_materials(..., building_band)` | `extend(room_link)` → `ctx.economic_tier` → materials |
| `_district_named_location`, `_place_building`, `_room_to_named_location` | NL без stamp | `system_economic_tier = ctx.economic_tier` |
| `debug.py:166`, `debugStructureRotations.py:79` | `generate_from_template` без каскада | EmptyLink-цепочка → building ctx |

## Шаги

### M1 — settlement scope: ctx строится у skeleton

- **Цель:** `SettlementSkeleton.economic_tier` идёт из settlement ctx,
  не из `TierResolver`.
- **ТЗ:** tz_cascade §4, §6.
- **Файлы:** `settlementAssembler.py`, `settlementGeneratorService.py`,
  `settlementOutdoorPackingJob.py` (+ их callers, где создаётся
  skeleton / city NL).
- **Контракт:** на входе в assemble —
  `ctx = extend(LocationContext.root(world), Link(SETTLEMENT, city_nl_pojo), Link(SETTLEMENT, skeleton_pojo), rng=Random(_make_seed(world_uid, city_uid, "tier")))`;
  `skeleton.economic_tier = ctx.economic_tier`. `TierResolver` в этих
  трёх точках удаляется.
- **Проверка:** unittest трёх assembler-тестов + `test_city_three_axes`,
  `test_settlement_topology` (перевести фикстуры на ctx).
- **Done:** `grep TierResolver` в assembler-пакете пуст; skeleton tier
  совпадает со старым на тех же входах.

### M2 — district + area ctx доходит до структуры

- **Цель:** district ctx (NL district + DTE range) на каждый
  `DistrictSlot`; area ctx на `PlotLayoutTemplate`; оба доходят до
  `StructureContext`.
- **Файлы:** `settlementOutdoorExtract.py` (`_district_named_location` —
  stamp), `structureAreaAssembler.py` (`derive_structure_context` —
  сигнатура `+ district_ctx`, убрать чтение `economic_tier_band`),
  `structureContext.py` (`building_band` → `context: LocationContext`),
  `buildingAssembler.py` (передача ctx).
- **Контракт:**
  `district_ctx = extend(settlement_ctx, Link(DISTRICT, district_nl), Link(DISTRICT, dte), rng=…)`;
  `area_ctx = extend(district_ctx, Link(AREA, plot), rng=…)`;
  `StructureContext.context: LocationContext` вместо `building_band`.
- **Q4 (существующая NL):** если building NL уже есть (из БД /
  перегенерация) — она идёт первым звеном building-уровня, а её
  authored `system_economic_tier` побеждает шаблоны; stamp пишется
  только при отсутствии authored-значения.
- **Проверка:** `test_area_slot_height`, `test_building_assembler`
  (patch-сайты TierResolver → ctx), compileall.
- **Done:** `building_band` не покидает area-слой; `StructureContext`
  несёт ctx.

### M3 — structure: один ctx, ноль резолвов

- **Цель:** `generate_from_template` получает building ctx; фазы читают
  `ctx.economic_tier`; room ctx — в factories.
- **Файлы:** `structureGeneratorService.py` (сигнатура `building_band`
  → `ctx: LocationContext`; 4 сайта `TierResolver` → `ctx.economic_tier`;
  `building_band=` из `_instantiate_rooms`, `_run_passages`,
  `_place_wall_openings` удаляется), `roomFactory.py`,
  `shaftFactory.py` (`+ ctx` / `extend(ROOM, room_def)`),
  `_room_to_named_location` (stamp).
- **Контракт:**
  `generate_from_template(world, building, structure, *, ctx, …)`;
  `room_ctx = extend(building_ctx, Link(ROOM, room_def), rng=Random(_make_seed(world_uid, room_uid, "tier")))`;
  `_RoomInstance.economic_tier = room_ctx.economic_tier`.
- **Проверка:** structure-тесты; baseline snapshot — effective tier
  идентичен во всех фазах, один резолв.
- **Done:** `TierResolver` и `building_band` в `generators/structure/`
  отсутствуют.

### M4 — materialResolver + wallOpening: консьюмеры, не резолверы

- **Цель:** материалы получают effective tier аргументом.
- **Файлы:** `materialResolver.py` (`resolve_room_materials(world,
  effective_tier, rng, room_id)` — убрать `room_tier`/`template_tier`/
  `building_tier`/`building_band`/внутренний `TierResolver`),
  `wallOpening.py` (`glass_tier = room_ctx.economic_tier`, параметр
  `building_tier` → ctx или effective).
- **Проверка:** `test_wall_material*` сьюты, snapshot материалов.
- **Done:** в `materialResolver` нет `TierResolver`; подписи без
  tier-каскада.

### M5 — debug-точки и NL stamps

- **Цель:** debug-роуты собирают ctx через `EmptyLink`; каждая NL
  цепочки получает stamp.
- **Файлы:** `api/routes/debug.py`, `debugStructureRotations.py`,
  `settlementOutdoorExtract.py`, `structureAreaAssembler._place_building`,
  `structureGeneratorService._room_to_named_location`.
- **Контракт:** debug —
  `extend(root(world), EmptyLink(SETTLEMENT), EmptyLink(DISTRICT), …)`;
  stamp `nl.system_economic_tier = ctx.economic_tier` на каждой новой NL.
- **Проверка:** кейс tz_cascade §8.4 — persist + перегенерация:
  stamped NL первым звеном сохраняет authored тир, повторный резолв
  его не перебивает.
- **Done:** debug-пути генерируют через ctx, не raw band; stamped NL
  стабилен при перегенерации.

### M6 — зачистка TierResolver

- **Цель:** старые логики физически удалены.
- **Файлы:** `tierResolver.py` (удалить целиком), остатки `building_band`
  параметров, `median_system_tier`/`materialize_band` вызовы вне движка.
- **Проверка:** `grep -rn "TierResolver\|building_band\|resolve_room_materials.*tier" app` — пусто;
  полный прогон backend-тестов; baseline snapshot сравнение (тиры могут
  легитимно измениться только там, где старый код терял звенья).
- **Acceptance (из S5 старого плана):** persist-решение по
  `system_economic_tier` на NL зафиксировано явно; таблица «Где что
  используется» в `tz_economic_tier.md` §8 обновлена под
  `LocationContext`; sweep-гейт генерации.
- **Done:** `tierResolver.py` удалён, тесты зелёные; контекст —
  единственный путь параметра к консьюмерам.

## Параметры-кандидаты — каждый атомарным шагом

Общая форма шага параметра (паттерн уже доказан `economic_tier`):

1. `Cascade` в `cascadeParams` домена (`field`, `default`, `axis`,
   `input_types` если есть materialize-kind);
2. `CascadeChannel` на полях source-POJO (ребро `above`/`below` — один
   раз, на стороне без цикла импорта);
3. поле на `LocationContext` + привязка materialize/default в
   `contextResolver`;
4. потребители читают `ctx.<param>`; старая or-цепочка удаляется;
5. `verify_cascade_contract` + `test_context_extend` — новый кейс.

### M7 — `city_size`

- **Цель:** `skeleton.system_city_size or settlement.system_city_size
  or "hamlet"` → `ctx.system_city_size`; литерал-default уходит в
  `DefaultPolicy`/`dataModel` (`dataModel-no-hardcode`).
- **ТЗ:** tz_cascade §5; tz_locations (поле `system_city_size`).
- **Файлы:** `settlementAssembler/planner/barriers.py:41`,
  `planner/footprint.py` (`system_city_size or …`), каналы —
  `SettlementSkeleton.system_city_size` + NL `system_city_size`
  (SETTLEMENT); `cascadeParams`, `locationContext`, `contextResolver`.
- **Контракт:** `CITY_SIZE = Cascade(field="system_city_size",
  default=CANONICAL_DEFAULT, axis=ScopeLevel, levels=(SETTLEMENT,))` —
  параметр живёт только на settlement-уровне; проверит `Cascade.levels`
  (покрытие подмножества). Default — `WorldSettlementSizeRegistry`
  canonical, не литерал `"hamlet"`.
- **Done:** `or "hamlet"` и or-цепочки удалены; barriers/footprint
  читают ctx.

### M8 — `settlement_density`

- **Цель:** `slot.district_template.density or skeleton.settlement_density`
  → `ctx.settlement_density`.
- **ТЗ:** tz_cascade §5; tz_city_generation (density/районы).
- **Файлы:** `districtAssembler/planner/lattice.py:52`,
  `settlementAssembler/planner/barriers.py` (`block_size_for_density`),
  каналы — `DistrictTemplateEntry.density` (DISTRICT) →
  `SettlementSkeleton.settlement_density` (SETTLEMENT).
- **Контракт:** цепочка `district → settlement`; default по политике
  POJO (`DistrictDensity` — registry/enum default). Проверяет
  district-first семантику (шаблон бьёт settlement).
- **Done:** or-цепочка density удалена; ctx-потребление.

### M9 — `wall_material` / `floor_material`

- **Цель:** `NL.parent_wall_material`/`parent_floor_material` и
  or-цепочки структуры → `ctx.wall_material`/`ctx.floor_material`.
- **ТЗ:** tz_cascade §5, §7; классификация/политика материалов —
  [`structure-wall-materials-done`](structure-wall-materials-done.md)
  (закрыт, разблокирован); этот шаг только проводка через каскад.
- **Файлы:** `foundationBuilder.py:65`, `roofBuilder.py:41`,
  `connect_corridors` (`parent_wall_material or DEFAULT`), каналы —
  NL `parent_*_material` (надёжно — parent = верхний scope), room-
  resolved материалы.
- **Контракт:** два `Cascade` (или один grouped — решить по §7);
  `default` — политика материального реестра, не литерал.
- **Done:** `or parent_*` цепочки удалены; материалы стены/пола — ctx.

### M10 — `dominant_material`

- **Цель:** `resolve_dominant_material` (settlement → fallback по
  районам / по tier) → каскад.
- **Особенность:** семантика не pure first-non-null — fallback «из
  районов» и «по tier» это derived/fold-логика → **первая реальная
  проверка `Cascade.fold`**; если fold не нужен — декомпозиция на
  authored-цепочку + domain-default.
- **Файлы:** `planner/dominantMaterial.py`.
- **Done:** решение по fold зафиксировано; or-resolution удалён.

### Отложенные кандидаты (без шага до решения)

`race_mix`/`population_composition`, культура/язык/фракция,
climate anchor (подмножество уровней — `levels`), торговый профиль/
валюта, law/magic/tech level, loyalty/иерархии фракций (своя ось
`FactionScope` — см. `cascade-params-matrix.md`). Каждый — по общей
форме выше; race_mix проверит multi-source на уровне (не DTE),
climate — `levels`.

## Проверки (общие)

- `python -m unittest` по затронутым сьютам после каждого шага;
- `compileall` изменённых модулей; `git diff --check`;
- детерминизм ×2 на seed: effective tier идентичен во всех фазах;
- кейсы tz_cascade §8.1–8.4 на POJO-фикстурах;
- WARNING при пустой цепочке один раз на scope (provisional default не
  повторяется), без WARNING при authored tier.

## Не scope

- Перевод кода потребителей district/settlement-уровня на ctx сверх
  перечисленных шагов параметров — сам потребитель меняется в шаге
  своего параметра (M7+), не в M1–M6.
- `wall_material`/`floor_material` классификация и политика — план
  `structure-wall-materials-done` (закрыт); здесь только
  каскад-проводка (M9).
- `planner/economic.py` — фильтрация шаблонов, не каскад.
- Отложенные кандидаты без шага — до отдельного решения.
