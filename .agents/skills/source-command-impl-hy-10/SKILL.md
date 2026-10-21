---
name: "source-command-impl-hy-10"
description: "Имплементирует HY-10: L0 light-footprint гидрологии — shore/deepening bands, water roles и z_water_level в L0 wire через HydroContributor/compose с общим merge ролей; coarse planning остаётся диагностикой, не вторым SoT L0 mask. По строке HY-10 в tz_generator_technical_debt.md; до кода — отдельный план и ТЗ. Новый чат: /impl-hy-10."
---

# source-command-impl-hy-10

Use this skill when the user asks to run the migrated source command `impl-hy-10`.

## Command Template

# Имплементация: HY-10 — гидрология в L0 light footprint

Это **явная просьба писать код** — но **только после согласованного плана и ТЗ** (см. «Старт»). Пока плана нет в `.cursor/plans/` — работа ограничивается его составлением.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом план, потом код.

## Гейт входа

- **HY-12 закрыт** (план `hy-12-sea-elevation-contract-done.md`, все шаги 1–6, coarse smoke пройден). Роли/уровни/`water_body_uid`/`deepening_index` теперь производит water-пipeline — HY-10 читает их, а не legacy flood/paint. Если HY-12 не закрыт — стоп, вернуться к `/impl-hy-12`.

## Прочитать до первой правки

1. [`docs/tz_generator_technical_debt.md`](../../docs/tz_generator_technical_debt.md) — строки **HY-10** (SoT этого трека), HY-7 (precedence mountain × shoreline), HY-8/HY-BATH-1 (уровень/впадина), HY-12 (новый контракт воды).
2. [`docs/tz_map_light_bake.md`](../../docs/tz_map_light_bake.md) — § **Source of truth** (`coarse_hydro` = planning/L2, **не** SoT L0 mask), § SoT↔bake таблица, § precedence ролей, контракт light wire (какие поля несёт клетка).
3. [`docs/tz_terrain_hydrology.md`](../../docs/tz_terrain_hydrology.md) — актуальный контракт ролей/уровней/bands после HY-12 (strict fill `z < z_water_level`, derived SHORE, `water_body_uid`, `deepening_index`, waterfall-факты).
4. Кодовое состояние (сверить с кодом):
   - `app/application/worldData/pack/bake/lightGrid/` — `maskDomainRegistry.py`, contributors: `hydro/hydro.py`, `hydro/coarseOpenWater.py`, `hydro/declaredBasins.py`, `hydro/declaredRivers.py`, compose/merge ролей
   - `generators/hydrology/` — новый water-пipeline: `water/` (levelFill, componentLabel, waterBodyResolver, waterClassifier, shoreDerive, waterMaterialize, waterDiagnostics), `waterBodyAssembler.py`, `types.py` (`HydrologyResult`)
   - `dataModel/hydrology/mapCellHydrology.py` — `role`, `water_body_uid`, `z_water_level`, `deepening_index`
   - `generators/terrain/passes/surfaceTerrainContext.py` — `coarse_hydro` (planning-источник, не SoT)
   - debug/render точки приёмки: `GET /map/render-world-grid`, `/render-world-tile-grids`, `pack/bake?mode=light|full`
   - fixture: `fixtures/world_test_004.json`
5. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../rules/code-gates.mdc) — **план до кода**, один шаг за заход
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../rules/dataModel-no-hardcode.mdc) — роли/enum только через `dataModel` типы
   - [`.cursor/rules/contract-creation.mdc`](../rules/contract-creation.mdc)
   - [`.cursor/rules/layer-boundaries.mdc`](../rules/layer-boundaries.mdc) — bake/contributor ≠ второй генератор гидрологии
   - [`.cursor/rules/project-context.mdc`](../rules/project-context.mdc) — не DAG, не коммитить, не стартовать backend
   - [`.cursor/rules/class-size-limit.mdc`](../rules/class-size-limit.mdc)

## Целевой контракт (из строки HY-10 — детали согласуются в плане)

L0-клетка несёт факты воды, которые сейчас живут только в coarse planning:

- **SHORE и deepening bands в L0** — footprint береговой полосы и `deepening_index` доходят до light wire (ocean-пин на band, не только `s` на declare-линии)
- **Роли воды** — open-water роли из water-пipeline (SEA/LAKE/RIVER_BED…) попадают в L0 с `water_body_uid` и `z_water_level`
- **Применение через `HydroContributor`/compose** — единый merge ролей с другими contributors; precedence `mountain` vs hydro-role определён явно (согласовать с HY-7)

## Жёсткие запреты

- **Coarse planning не SoT L0 mask** — не копировать `coarse_hydro` в L0 как второй источник; L0 читает результат water-pipeline (или согласованный в плане механизм переноса).
- **Не делать flood/carve/rim-профиль в paint/contributor** — геометрия уже решена до bake; contributor только читает факты и кладёт в wire. Не подменять HY-BATH-1.
- **Не дублировать merge ролей** — использовать общий compose; не заводить приватный precedence внутри hydro contributor.
- Не реализовывать HY-7 (сам precedence — согласование, не код горы), HY-9, W/L-треки, waterfall-продукт (HY-WF-1), GEO-1.
- Не DAG-ноды, не schema `0002_*.sql`, не коммит, не старт backend. Класс ≤300 строк.

## Порядок (первый заход = план, не код)

1. **План** `.cursor/plans/hy-10-l0-water-wire.md` — до кода: инвентарь того, что теряется между water-pipeline и L0 wire (поля, роли, bands); целевой light-footprint (band metadata, merge ролей, precedence mountain/hydro по HY-7); проверка на `world_test_004`. Согласовать с мастером.
2. **ТЗ** — раздел в `tz_map_light_bake.md` (и/или `tz_terrain_hydrology.md`): wire-поля, precedence, правило SoT.
3. **Реализация** по шагам плана — contributor/compose/wire, без генераторной геометрии.
4. **Приёмка** — smoke render/bake: bands + роли + уровни видимы в L0 на `world_test_004` (включая wrapped-шов); детерминизм rebake; отчёт.

## Приёмка

- Новые тесты (wire-поля, merge precedence, band→L0) зелёные; baseline без новых падений.
- `python -m unittest` по затронутым наборам, `compileall`, `git diff --check`.
- HTTP smoke через мастера: `render-world-grid`/`render-world-tile-grids` показывают воду/берег/bands, а не только declare-линии.
- HY-10 → `resolved` в реестре; план → `-done`.

## Старт

Проверь гейт (HY-12 закрыт). Прочитай строку HY-10 + `tz_map_light_bake.md` § Source of truth + `contributors/hydro/` целиком. Составь инвентарь «что производит water-pipeline vs что доезжает до L0» и предложи мастеру план. Код — только после «ок» на план.
