# Топология поверхности мира: `world_topology_mode` (DRAFT)

> Карта межплановых зависимостей и критический путь:
> [`plan-dependency-graph.md`](plan-dependency-graph.md) — отдельный трек,
> связь только с `wilderness-regions-mechanic.md`.

**Статус:** выделено из wilderness-regions-mechanic по решению разработчика
2026-10-16 (§5 вопрос 10). Отдельный план реализации; разрешения на код нет.

**Связанный план:** [wilderness-regions-mechanic.md](./wilderness-regions-mechanic.md)
§0 — там зафиксирован контракт (все решения по режимам, транзиту, шву,
экстентам). Этот план — декомпозиция реализации `WorldTopology` и
миграции потребителей; контракт здесь не переобсуждается.

## Зафиксированная постановка (из §0 wilderness, решения 2026-10-07/16)

- Скаляр `world_topology_mode: "planar" | "wrapped" | "sphere"`,
  default `wrapped`. Mode — **координатная карта соседей** сетки, не
  механика транзита.
- Координатная карта: `wrapped` — тор (`x_min↔x_max` тот же y;
  `y_min↔y_max` тот же x); `sphere` — по x как у тора, **каждый** край y
  сшит сам с собой со сдвигом `x' = (x + w/2) mod w` + инверсия
  Δy-intent; `planar` — соседа за краем нет.
- Транзит за край = обычный шаг по neighbor lookup; отдельного
  transit-event нет (`world_edge_crossing` — опционально, ортогонально).
- Чётность по x для `sphere` — инвариант сетки: движок нормализует
  `world_bounds` при resolve, автор сетку не считает, reject-валидации
  в authored-вводе нет.
- «Полюс» — термин climate-домена (`climate_pole`); в топологии полюс —
  шов-кромка краевой строки, не сущность; в `wrapped`/`sphere` у каждой
  клетки 4 соседа.
- Экстенты через шов — идиомы `wrap_owner_and_other` (canonical owner,
  `frozenset`-identity) и `antipode_xy` (local-mod нормализация на
  границе); нового механизма не вводить.
- Частичный bake — pull-строчка: baked tile = `other` → читает owner-rim
  из пака и применяет `WorldSeamCopy` к себе; baked tile = `owner` → не
  строчит (antagonist подтянет при своём bake); pack-write за пределы
  bake-scope не вводится.

## Точки входа для проверки

- `dataModel/worldPack/wire/worldBounds.py` — `grid_neighbor`, `antagonist_tile`
  (тор-формула), `wrap_owner_and_other`, `facing_to_antagonist`.
- `pack/bake/lightGrid/worldSeam.py` — `apply_world_seam`, `_copy_rim`
  (сейчас `opposite(facing)` — для sphere y-кромки неверно: NORTH↔NORTH).
- `pack/refine/gridNeighborHalo.py` — только `grid_neighbor`, без wrap.
- `generators/coordinates/antipode.py` — local-mod идиома.
- `worlds` + `dataModel/terrain/worldTerrainScalars.py` — прецедент
  `closed_planet_grid` для скаляра.
- ТЗ: [tz_terrain_generation.md](../../docs/tz_terrain_generation.md)
  § Форма мира / шов мира; [tz_world_pack_storage.md](../../docs/tz_world_pack_storage.md).

## Целевая реализация (контракт из §0 — перенесено без переобсуждения)

- `worlds.world_topology_mode` — SQL + `WorldTerrainScalars` поле.
- `WorldTopology` (`dataModel/worldPack/worldTopology.py`) — mode +
  `WorldBounds`; `neighbor` (+edge-crossing, intent transform),
  `canonicalize` (local-mod), пары шва и их facings. Единственная точка
  резолва; `grid_neighbor`/`antagonist_tile` — делегаты.
- `apply_world_seam` — пары/facings из `WorldTopology` (sphere y:
  NORTH↔NORTH/SOUTH↔SOUTH, не `opposite`; planar: no-op); pull-семантика.
- Потребители из списка §0-14 мигрируют на `topology.neighbor`:
  `gridNeighborHalo`, pathfinding/дистанции, `RegionShape`-растеризация,
  контуры регионов, hydrology/z-continuity, climate field у полюсов.
- `antipode_xy`/`closed_planet_grid` — ось нижнего слоя, не трогается.

## Решения (2026-10-17)

1. **За краем `planar` — impassable void:** `neighbor()` → `None`,
   движение невозможно. «Обрыв vs стена» — визуал/наррация, не
   топология; lookup-контракту всё равно.
2. **`intent transform` — флаги в typed-результате, не метод:**
   `NeighborResult{coord, edge_crossing: bool, invert_dy: bool}`;
   потребитель сам применяет к своему intent — скрытой магии нет.
3. **Порядок миграции потребителей** — зафиксирован: seam → halo →
   transit → raster → A*.
4. **Миров без `world_topology_mode`:** default `wrapped` = текущее
   тор-поведение — обратная совместимость, данных мигрировать нечего,
   старые паки валидны.
5. **Смена mode у существующего мира — pack invalidation:** меняется
   карта соседей → seam-пары и halo всех испечённых тайлов инвалидны
   → обязательный full re-bake (как смена размеров мира); warning при
   worldEdit.

## Порядок дальнейшей подготовки

1. ТЗ sync: `world_topology_mode` и координатная карта трёх режимов,
   чётность x для `sphere`, `NeighborResult{coord, edge_crossing,
   invert_dy}`, `canonicalize` — в `tz_terrain_generation.md` § Форма мира;
   seam-контракт (пары NORTH↔NORTH / SOUTH↔SOUTH для sphere, pull-строчка
   частичного bake, pack invalidation при смене mode) — в
   `tz_world_pack_storage.md` § L0. После этого ссылка в
   `tz_map_light_bake.md` § Регионы покрытия › RegionShape ведёт на раздел
   ТЗ (сейчас — на этот план).
2. `WorldTopology` dataModel + скаляр мира (без потребителей). Путь —
   `dataModel/worldPack/wire/worldTopology.py` (рядом с `worldBounds.py`;
   корень `worldPack/` после restructure шаг 14 — только подпапки).
   **Единственный владелец файла — этот план**; wilderness его не создаёт.
3. Перевод потребителей по одному: seam → halo → transit → raster → A*.
   Пункт **raster = wilderness-regions-mechanic §4 шаг 4**
   (`RegionRasterizer`: `canonicalize` на границе, `neighbor` для обхода
   seed-решётки) — выполняется там, здесь только порядок.
4. Проверки: детерминизм соседства на всех трёх mode; seam owner→antagonist
   при full и partial bake; sphere flip проход через обе y-кромки.

**Техническая детализация шага 2 (2026-10-17):** `WorldTopologyMode`
находится в `dataModel/worldPack/wire/worldTopologyMode.py`; default режима
принадлежит `WorldTerrainScalars`. Геометрические примитивы local-mod,
half-width и отражения unrolled-строк добавляются в `WorldBounds`;
`worldTopology.py` делегирует им канонизацию и существующим
`grid_neighbor`/`antagonist_tile` — соседство. Старые методы `WorldBounds`
и потребители не меняются. Чётность sphere нормализуется при разрешении
поля `WorldTopology.bounds`, без изменения authored-объекта.

Этот план не меняет механику регионов; wilderness использует
`topology.neighbor`/`canonicalize` как готовый сервис **после шагов 1–2**
(ребро в `plan-dependency-graph.md`: surface-topology [1–2] → wilderness [4]).
Planar-заглушка на стороне wilderness не вводится: текущий шов — `wrapped`,
planar-rasterizer дал бы рассинхрон на кромке.
