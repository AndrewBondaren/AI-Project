---
name: "source-command-impl-hy-6"
description: "Имплементирует HY-6 (coastline water-side): водная сторона по (C−K)·n > 0 на ближайшем сегменте, bounded/unbounded flood, единый n(K) для seeds/shore/flood, warning'и, smoke на world_test_004. По плану hy-6-coastline-water-side.md. Новый чат: /impl-hy-6."
---

# source-command-impl-hy-6

Use this skill when the user asks to run the migrated source command `impl-hy-6`.

## Command Template

# Имплементация: HY-6 — водная сторона declared coastline

Это **явная просьба писать код** (шаги плана). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/hy-6-coastline-water-side.md`](../plans/hy-6-coastline-water-side.md) — **единственный SoT по шагам**: контракт, A1–C тест-матрица, проверки, smoke. Не отклоняться.
2. [`docs/tz_terrain_hydrology.md`](../../docs/tz_terrain_hydrology.md) — § SeaBasinGenerator (U15/U21), § declare/autoresolve, `z_sea`. Шаг 1 — правка этого файла.
3. [`docs/tz_generator_technical_debt.md`](../../docs/tz_generator_technical_debt.md) — строка **HY-6** (evidence, fix-направление); контекст соседей HY-7/HY-8 (не реализовать!).
4. Кодовое состояние (сверить с кодом, не с памятью):
   - `backend/app/application/worldData/generators/hydrology/shore/deepeningBandCarver.py` — `carve_deepening_bands`, `flood_water_side`, `flood_water_side_unbounded`, `_in_water_strip`, `water_step_from_segment`, `land_centroid`
   - `backend/app/application/worldData/generators/hydrology/autoresolve/proceduralSeaAutoresolve.py` — `autoresolve_sea_basins`, `_autoresolve_beyond_declare_bbox`, `_autoresolve_from_map_boundary`, `pad=1`
   - `backend/app/application/worldData/generators/hydrology/load/buildHydrologyMasterInput.py` — `fine_segments_to_grid`, сегменты для carver'а
   - `backend/app/application/worldData/pack/bake/lightGrid/contributors/hydro/declaredBasins.py` + `coarseOpenWater.py` — paint-уровень (не трогать; объясняет `s` без воды)
   - тесты: `backend/tests/test_hydrology_*.py` — существующие hy2/hy5a регрессии на `flat_heightmap(z=5)`
5. Правила (нарушение = стоп):
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/layer-boundaries.mdc`](../rules/layer-boundaries.mdc)
   - [`.cursor/rules/code-gates.mdc`](../rules/code-gates.mdc) — один шаг за заход
   - [`.cursor/rules/project-context.mdc`](../rules/project-context.mdc) — не DAG, не коммитить, **не стартовать backend** (smoke — через мастера или уже поднятый сервер)
   - [`.cursor/rules/class-size-limit.mdc`](../rules/class-size-limit.mdc) — класс ≤300 строк
   - [`.cursor/rules/contract-creation.mdc`](../rules/contract-creation.mdc) — строгая типизация, новый контракт только при отсутствии

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Целевой контракт (кратко — SoT в плане)

```
water(C) ⇔ (C − K)·n(K) > 0
```

- `n(K)` — водная сторона **сегмента, владеющего ближайшей клеткой** K (per-segment nearest: расстояние до отрезка, не до растровой клетки; `n` и проекция `t` — по одному объекту).
- **bounded** = `dot > 0` **и** проекция `t ∈ [0,1]` на owning-сегмент; **unbounded** = только `dot > 0`.
- Открытые концы полилинии не обтекаются на land-сторону.
- Один и тот же per-segment `n(K)` для: water seeds, `land_shore`, bounded flood, unbounded flood.
- Стена — dot-тест, не множество coastline-клеток (Bresenham 8-связен, BFS 4-связен → протечки между диагоналями).
- Tie при равном расстоянии до сегментов — `max dot`, детерминированный порядок `(gy, gx)`.
- Вода — только на клетках `heightmap.surface_z` (за краем bounds воды нет — документировать, не обходить).
- Вогнутые берега — v1-эвристика; сложные формы раскладываются на несколько coastline (документировать).
- **Шов под HY-8:** helper водной стороны возвращает только **footprint**; проходимость BFS — параметр-предикат `passable`, не вшитая проверка. Условный `surface_z = z_sea` в apply **не** трогать.

## Порядок шагов (по плану, один за заход)

1. **ТЗ** — § SeaBasinGenerator: water-side контракт (per-segment nearest, `n(K)`, bounded/unbounded, tie-break, «вода за bounds нет», concave-ограничение) + контракт двух warning'ов.
2. **Flood** — общий water-side helper в `deepeningBandCarver.py` (footprint + `passable`-предикат); обе flood-функции на нём; удалить `_in_water_strip`/`_water_gy_direction`; тесты матрицы A1–C (N-S, диагональ, bounded vs unbounded примеры `(2,1)`/`(0,1)`/`(10,0)`/`(0,3)` на линии `(2,2)-(8,2)`, endpoint-непроточка, tie, вода-за-bounds, угол/per-segment nearest).
3. **Warnings** — `water_dist=0` при ненулевой линии → warning; `water extent < bands.min` → warning. Лог generation (`backend/logs/generation/{uid}/bake-*.log`).
4. **Smoke** — `fixtures/world_test_004.json`: coastline x=−1500 → **−500** (пин `map_x` синхронно; океан-пин западнее; линию по z не двигать — западный столбец остаётся `m`, демонстратор HY-7). Затем: wipe pack → light+full bake → `GET /api/worlds/{uid}/map/render-world-grid` → `python backend/scripts/render_maps.py <uid>` (скрипты: `backend/scripts/light_and_full_bake.py`, `render_maps.py`). **Backend агенту не стартовать** — если сервер не поднят, попросить мастера.
   Ожидание: западный столбец — deepening band (`s`, `deepening_index=1`); `~`/`o` **нет** до HY-BATH-1 rim-профиля; `s` сквозь `m` — демонстратор HY-7, не маскировать.

## Жёсткие запреты

- Не реализовывать HY-7 (shoreline × mountain), HY-8 (вода-уровень), HY-BATH-1, HY-9 (coastline forms — отдельный план `.cursor/plans/coastline-forms.md`).
- Не менять `declaredBasins`/`coarseOpenWater` paint-контрибьюторы — `s` от declare остаётся by design.
- Не DAG-ноды, не schema-изменения, не коммит, не старт backend.
- Не новые bulk-циклы — при необходимости `app.db.bulkSql` (правило bulk-sql).
- Не расширять класс carver'а сверх 300 строк — вынести helper в свой модуль (`shore/`).

## Приёмка

- Тест-матрица A1–C зелёная; существующие hy2/hy5a — без новых падений (pre-existing baseline съюта не путать с регрессиями — сверить с логом).
- `compileall` изменённых модулей, `git diff --check`.
- Smoke: generation log показывает `coastal_sea cells>5` с водой (не только shore) ИЛИ явный warning «водная сторона за пределами bounds»; рендер — `s` + band на западном столбце.
- Долг HY-6 в `tz_generator_technical_debt.md` → статус `resolved` (в финале), план → `hy-6-coastline-water-side-done.md`.

## Старт

Прочитай план целиком + `deepeningBandCarver.py` + `proceduralSeaAutoresolve.py`. Затем шаг 1 (ТЗ).
