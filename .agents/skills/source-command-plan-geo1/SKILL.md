---
name: "source-command-plan-geo1"
description: "Проектирует план GEO-1 designed water: процедурный океан как designed-объект существующего placement resolver + continental/plate-поле в terrain pass. Задача — анализ и файл плана для согласования мастером, НЕ код. Покрывает ответ на HY-RIV-1 (источники процедурных рек как consumer resolver'а). Новый чат: /plan-geo-1."
---

# source-command-plan-geo1

Use this skill when the user asks to run the migrated source command `plan-geo-1`.

## Command Template

# Проектирование: GEO-1 — designed water (процедурный океан)

Это задача **проектирования**, не кода. По `code-gates`: пишешь только файл плана `.cursor/plans/geo-1-designed-water.md` — код, тесты, fixtures и ТЗ **не трогать**. План уходит мастеру на согласование; имплементация — отдельной командой после «ок».

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом план.

## Прочитать до первой строки плана

1. [`docs/tz_generator_technical_debt.md`](../../../docs/tz_generator_technical_debt.md) — строка **GEO-1** (суть: relief генерирует noise без «океанского дна»; вариант «synthesize из lowest-component» отклонён мастером — нестабилен на пересчёте; размещение воды — НЕ задача гидрологии) + строки **HY-RIV-1**, **HY-BATH-1**, **HY-12**.
2. [`.cursor/plans/generator-placement.md`](../../../.cursor/plans/generator-placement.md) — SoT общего resolver'а. P0–P2 выполнены, P3 водный adapter declared basin/coastline готов; production wiring и остальные adapters открыты. Раздел «Инвентарь P0» — полная карта потребителей.
3. [`docs/tz_map_light_bake.md`](../../../docs/tz_map_light_bake.md) — § **Placement priority** + § Placement P1/P2: контракты `PlacementIntent/Dependency/Overlap/Separation/Footprint/Candidate/PreparedPlacement/Batch`, `CoastlinePlacementFact`, specificity → площадь → UID, phase `pre_relief | dependent`.
4. [`.cursor/plans/plan-dependency-graph.md`](../../../.cursor/plans/plan-dependency-graph.md) — § связей: «placement + relief/continental field → GEO-1 (отдельного плана пока нет)»; какие треки ждут GEO-1.
5. [`docs/tz_terrain_hydrology.md`](../../../docs/tz_terrain_hydrology.md) — § autoresolve `z < z_water_level`, уровень на тело, `WaterBody.kind`, priority elevation hierarchy (что уже умеет HY-12 принимать на вход).
6. [`.cursor/plans/hy-12-sea-elevation-contract-done.md`](../../../.cursor/plans/hy-12-sea-elevation-contract-done.md) — как устроен water placement pass; где граница «разместить ↔ заполнить».
7. [`docs/tz_terrain_relief.md`](../../../docs/tz_terrain_relief.md) — SoT terrain pipeline: где проход continental-поля встаёт относительно base heightmap/anchors и pre-1.4 placement прохода.
8. Правила: `.cursor/rules/code-gates.mdc` (один шаг = одно проверяемое изменение; ТЗ-ссылки обязательны), `contract-creation.mdc`, `dataModel-no-hardcode.mdc`, `layer-boundaries.mdc` (размещение воды — не гидрология; водный домен — fill/classify/shore/rivers), `project-context.mdc`.

## Что уже решено — не переоткрывать

- «Synthesize бассейн из lowest-component post-carve» **отклонён** — не предлагать.
- Общий placement resolver существует (P2 реализован) — GEO-1 его потребитель, параллельный resolver запрещён.
- Размещение designed water — terrain-side до hydrology: низкочастотное поле опускает designed-регионы ниже `default_water_level` **до** водного прохода; стабильность — размещение от pre-hydrology снимка.
- Кандидаты алгоритма поля: plate-модель Azgaar-типа, continental noise + `water_fraction` скаляр мира, authored region→basin. На wrapped/sphere нет ocean-края bbox — bounds не опора.
- Coastline = контракт создания воды (приоритет 0 без воды) — уже в P1.

## Что план обязан покрыть

1. **Контракт designed water как placement-объекта:** authored/policy declared regions → `PlacementIntent` (mode, shape, specificity, dependencies); water как зависимый объект coastline; как existing declared basins/lakes участвуют как accepted-опоры.
2. **Continental/plate-поле в terrain pass:** где в pipeline, вход (seed, `water_fraction`, designed regions), выход (relief spec / basinZ до level-fill), детерминизм и стабильность на пересчёте (читает pre-hydrology snapshot).
3. **Граница с HY-12:** designed water materialize через существующий `BasinSpec`/relief writer — hydrology получает готовые впадины, classify-only путь не меняется; уровень на тело сохраняется.
4. **HY-RIV-1 как downstream:** как источники процедурных рек станут consumer'ом resolver'а (intent источника + dependency на принимающее тело) — только обозначить точку входа, полный дизайн рек — отдельный мини-план после GEO-1.
5. **Открытые вопросы мастера:** список Q-* с вариантами, где нужно решение до кода (выбор алгоритма поля, доля воды, что делает мир без authored water, судьба legacy `proceduralRiverAutoresolve`).
6. **Порядок шагов:** атомарные, каждый с целью/ТЗ/файлами/контрактом/проверкой/Done по code-gates.

## Жёсткие запреты

- Не писать код. План — единственный артефакт.
- Не проектировать локальный resolver/обход P2; domain adapters готовят геометрию, resolve — общий.
- Не расширять гидрологию размещением: fill/classify/shore/rivers остаются как в HY-12.
- Не предлагать пересчёт океана от post-carve terrain.
- Новые поля/enum — только после инвентаризации `dataModel/` (contract-creation).
- Не DAG-ноды, не старт backend, не коммит.

## Приёмка

- Файл `.cursor/plans/geo-1-designed-water.md`: целевая архитектура (слои/инварианты), контракты, data flow, порядок шагов, открытые вопросы, связи (HY-RIV-1, HY-BATH-1, HY-9/10, P3 adapters, TOPO-1).
- Все утверждения о существующем поведении — со ссылкой на файл/строку, не по памяти.
- Мастеру в конце: краткая сводка + список Q-* для решений.

## Старт

Прочитай источники выше, покажи мастеру карту будущего плана (разделы + какие вопросы остались открытыми) **до** записи файла и жди «ок».
