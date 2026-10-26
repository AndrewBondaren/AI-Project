---
name: "source-command-impl-topology-2"
description: "Имплементирует шаг 2 плана surface-topology: WorldTopology dataModel в dataModel/worldPack/wire/worldTopology.py (mode + WorldBounds; neighbor → NeighborResult; canonicalize; seam-pairs/facings; делегаты grid_neighbor/antagonist_tile) + скаляр worlds.world_topology_mode / WorldTerrainScalars (default wrapped). Без потребителей. Вход закрыт: topology-1 (ТЗ). Новый чат: /impl-topology-2."
---

# source-command-impl-topology-2

Use this skill when the user asks to run the migrated source command `impl-topology-2`.

## Command Template

# Имплементация: topology-2 — `WorldTopology` + скаляр мира

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

**Блокер-условие:** `tz_terrain_generation.md` § Форма мира и `tz_world_pack_storage.md` § L0 уже содержат контракт трёх режимов / seam-пар (шаг topology-1 сдан). Нет → стоп, доклад мастеру.

## Прочитать до первой правки

1. [`.cursor/plans/surface-topology.md`](../../../.cursor/plans/surface-topology.md) — **единственный SoT этой задачи**: §0 контракт, «Целевая реализация» (пункты про `WorldTopology` и скаляр), «Решения 2026-10-17» 1–5, «Порядок подготовки» п.2. **Единственный владелец `worldTopology.py` — этот план.** Не отклоняться.
2. [`docs/tz_terrain_generation.md`](../../../docs/tz_terrain_generation.md) — § Форма мира (контракт после topology-1: режимы, `NeighborResult`, canonicalize).
3. [`docs/tz_world_pack_storage.md`](../../../docs/tz_world_pack_storage.md) — § L0 (seam-пары, pull, invalidation).
4. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок»
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc) — режим/default в POJO + `canonical_defaults`, не литералы
   - [`.cursor/rules/layer-boundaries.mdc`](../../../.cursor/rules/layer-boundaries.mdc)
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — schema только через `0001_initial.sql` + sync dataclass; **recreate** БД, не incremental; не стартовать backend, не коммитить
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Что уже есть — не переписывать

- `backend/app/dataModel/worldPack/wire/worldBounds.py` — `WorldBounds`, `grid_neighbor`, `antagonist_tile` (тор-формула), `wrap_owner_and_other`, `facing_to_antagonist` — `WorldTopology` использует их как **делегаты**, формулы не копируются.
- `backend/app/dataModel/terrain/worldTerrainScalars.py` — прецедент `closed_planet_grid` для скаляра `world_topology_mode`.
- `backend/app/application/worldData/generators/coordinates/antipode.py` — `antipode_xy`, local-mod идиома (canonicalize).
- `backend/app/application/worldData/pack/bake/lightGrid/worldSeam.py` — `apply_world_seam`, `_copy_rim` (`opposite(facing)` — для sphere неверно; **не правится в этом шаге**, миграция потребителей — шаг 3+).
- `worlds` таблица — прецедент колонки скаляра; schema = `0001_initial.sql` + sync `db/models` в одном заходе.
- `dataModel/spatial/facing.py` — `Facing` для seam-пар/результата.

## Скоуп шага 2 — строго по плану п.2

- `backend/app/dataModel/worldPack/wire/worldTopology.py` (рядом с `worldBounds.py`, **только подпапки** — корень `worldPack/` после restructure шага 14):
  - `WorldTopology` — `mode` + `WorldBounds`; единственная точка резолва соседства;
  - `neighbor(x, y, facing) -> NeighborResult | None` — `NeighborResult{coord, edge_crossing: bool, invert_dy: bool}`; `planar` за краем → `None`;
  - `canonicalize(x, y)` — local-mod нормализация по режиму;
  - Seam-пары и их facings: `wrapped` → `opposite`, `sphere` y-кромки → NORTH↔NORTH / SOUTH↔SOUTH (+`invert_dy`), `planar` → ∅;
  - `grid_neighbor`/`antagonist_tile` — делегаты существующих формул (caller API не ломать).
- Скаляр: `worlds.world_topology_mode` в `0001_initial.sql` + `WorldTerrainScalars.world_topology_mode` (default `wrapped` — миров без поля = тор) + sync `db/models`; recreate-политика.
- Pure dataModel: без потребителей, без wiring в bake — шаг 3 (`seam → halo → transit → raster → A*`) отдельно; `apply_world_seam` и `gridNeighborHalo` **не трогать**.
- Юнит: соседство на трёх mode; canonicalize на кромках; sphere-пары N↔N / S↔S с `invert_dy`; planar → `None` за краем.

- **Не в шаге 2:** миграция любых потребителей (worldSeam/halo/transit/raster/A* — порядок миграции шаг 3; raster = wilderness-4), worldEdit-warning при смене mode (отдельно), ребейк.

## Жёсткие запреты

- Формулы соседства — делегаты `worldBounds`/antipode; новых тор/сфера-формул в `worldTopology.py` нет.
- `world_topology_mode` — только dataModel+SQL+скаляр; никаких чтений из application-кода этого шага.
- Model и SQL в одном заходе — иначе `validate_schema` упадёт при старте.
- Не трогать DAG-ноды, не стартовать backend, не коммитить.
- Проверки запускать из `backend/`; не чинить окружение «заодно».

## Приёмка

- `python -m compileall backend/app` — чисто; `validate_schema` проходит при старте (после recreate БД — подсказать мастеру, самому не стартовать).
- Юнит: 4 соседа у каждой клетки при `wrapped`/`sphere`; `planar` край → `None`; canonicalize сводит координаты; sphere y-шов — пары N↔N/S↔S с `invert_dy=True`; default-миp без поля = `wrapped`.
- `apply_world_seam`/`grid_neighbor` — без изменений (делегация видна, дубли формул нет).
- Пометка «выполнен» в плане — только после приёмки и «ок» мастера.

## Старт

Прочитай план целиком, проверь блокер (ТЗ разделы на месте), покажи API `WorldTopology` (сигнатуры + `NeighborResult` + seam-pairs таблица) и diff-карту (`worldTopology.py`, `worldTerrainScalars.py`, `0001_initial.sql`, `db/models`) до первой правки.
