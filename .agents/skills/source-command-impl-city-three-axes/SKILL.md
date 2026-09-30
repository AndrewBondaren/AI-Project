---
name: "source-command-impl-city-three-axes"
description: "Имплементирует переход generate города на три оси (CITY-T-2a…2d): рецепт subtype поселения, BuildingCatalog, seed клетки footprint. Использовать в новом чате по команде /impl-city-three-axes или когда мастер просит реализовать план city-three-axes-transition."
---

# source-command-impl-city-three-axes

Use this skill when the user asks to run the migrated source command `impl-city-three-axes`.

## Command Template

# Имплементация: три оси generate города

Это **явная просьба писать код** (слои A–F плана). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала прочитай SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/city-three-axes-transition-done.md`](../plans/city-three-axes-transition-done.md) — **архитектура и порядок слоёв** (не отклоняться).
2. [`docs/tz_city_generation.md`](../../docs/tz_city_generation.md) **§1.1 и §9.6** — продукт.
3. CITY-T-2a…2d в [`docs/tz_generator_technical_debt.md`](../../docs/tz_generator_technical_debt.md).
4. Правила: `layer-boundaries.mdc`, `assembler-hierarchy.mdc`, `dataModel-no-hardcode.mdc`, `pojo-world-row-wire.mdc`, `json-validation-architecture.mdc`, `project-context.mdc` (DAG / backend / commit).

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Цель

Тип ≠ чертёж. Город не хранит список `tavern_1`.

| Ось | Тип | Чертёж |
|---|---|---|
| Поселение | subtype `settlement` + рецепт | этот `location_uid` |
| Район | `district_type` | `district_template_registry` |
| Здание | `structure_type` | library `system_name` / uid |

`system_city_size` — только масштаб footprint. Клетка seed — `(cell_x, cell_y)` **footprint города**, не pack макротайл.

## Жёсткие запреты

- Не трогать `application/engine/nodes/` (Gate: DAG). Не чинить CITY-T-1b / CITY-T-3.
- Не стартовать backend (`start.py`, uvicorn, `npm run backend`).
- Не коммитить, пока мастер не скажет.
- Не `0002_*.sql`. Рецепт — JSON `location_type_registry`, не новые колонки, пока план не велит иначе.
- Генераторы **pure sync**, без SQL/`await` repo. Гидратация library — только orchestrator / library service.
- Не дублировать POJO литералами в assembler.
- **Не** подключать `allowed` null = весь каталог (2a) **до** слоя E вместе с фильтром типов и `BuildingCatalog`. Иначе builtins разъедутся по всем кварталам.
- Не ломать C22 packing (pass1 → рамка → pass2). Меняется состав токенов, не пайплайн.
- Не заводить `district_type_registry` SQL и не класть список чертежей на NL города.
- Не считать контур закрытым без path-2 прогона (слой F); агент не поднимает сервер — дать мастеру curl/скрипт.

## Порядок (слои целиком, не слайс «сначала tavern»)

Каждый слой с **fallback**, generate не должен стать пустым.

| Слой | Что сделать | Готово когда |
|---|---|---|
| **A** dataModel | Рецепт на `LocationTypeSubtypeEntry`: `typical_district_types`, `required_structure_types`. Канон на engine subtypes (`city` / `village` / …) — таблица в плане §2.1. `BuildingCatalog`. `settlement_cell_rng(world_uid, location_uid, cell_x, cell_y, role)`. Резолв required (тип / имя чертежа). Функция allowed null/`[]` — **ещё не в cache**. | Unit POJO + стабильный rng; assembler не менять |
| **B** jsonValidation | Рецепт только через `location_types(world)`. Geographic subtype + extra ключи не 422. | Import/runtime читают канон⊕мир |
| **C** library hydrate | `BuildingTemplateLibraryService.layouts_for_world`. Outline-only `data` → warning, не в пул. Orchestrator собирает catalog (builtins ⊕ uid SQL ⊕ layout-строки мира) → `generate_layout(..., catalog=)`. `catalog=None` = builtins + layout-строки (path 3). | Assembler по-прежнему может работать без SQL |
| **D** SettlementAssembler | Рецепт с subtype NL. Клетка: `district_type` = typical ∩ зона; нет типа — skip+warning. Нет рецепта → **legacy** `select_district_template`. `DistrictSlot` хранит `cell_x/y`; union required поселения∪района. Catalog вниз. | |
| **E** DistrictAssembler | 2a + фильтр типов. Токен: rng чертёж **типа** из catalog; N=1 на **выбранный** чертёж, не по одному токену на каждый файл типа. `structure_counts[system_name]` — копии этого чертежа. Cache оболочек затронутых типов до packing. | |
| **F** | Unit path 3. Чеклист path 2 для мастера (мир с library, поселение **без** authored-детей; повтор generate → те же чертежи на клетке). | Не закрывать без прогона мастером |

Слой G (DAG, deprecate wire required) — **не делать**, пока мастер не снимет.

## Контракты (не изобретать другие)

- Рецепт: поля subtype `settlement` в `location_type_registry`, не таблица SQL, не поля на каждом городе.
- Required: оставить `building_template`; optional `structure_type`; резолв как план §2.3.
- Seed: не `city_size`, не `tile_gx/gy`. Суффикс `buildings` / `districts` — константа роли.
- `village` size ≠ `village` subtype.

## Стиль правок

- Минимум файлов, без рефакторинга «заодно» (MR-1 cache split — не этот чат).
- Тесты: узкие unit на рецепт, catalog, rng, резолв required, select района с/без рецепта. Не раздувать `debug_settlement.py`.
- После слоя: кратко что сделано / что осталось / что запустить мастеру.

## Старт

Прочитай план §1–5 и текущие `LocationTypeSubtypeEntry`, `plan_district_slots`, `tokens.py` / `buildingCache.py`, `SettlementOutdoorOrchestrator`, `BuildingTemplateLibraryService`. Затем слой A.
