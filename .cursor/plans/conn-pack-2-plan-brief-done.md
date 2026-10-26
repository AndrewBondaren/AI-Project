# Бриф: план CONN-PACK-2 (кластер центра района) ✅ DONE

Скопируй этот файл (или вставь текст ниже) **другому агенту** в новый чат. Задача агента — **только план**, не код.

---

Ты агент в репозитории AI Project (`E:/AI Project`). Режим: **план**, не имплементация.

## Что сделать

Составить **итоговый** архитектурный план закрытия **CONN-PACK-2**: несколько участков с `position: "center"` в одном районе сажаются как **единый центр** (кластер), а не leftover.

План класть в [`.cursor/plans/`](./) (новый файл, например `conn-pack-2-center-cluster.md`). Не в `docs/` (там только продуктовые ТЗ). Код, тесты, правки ТЗ — **не писать**, пока мастер не скажет «делай».

Формат плана — architecture-first ([`.cursor/rules/architecture-first.mdc`](../rules/architecture-first.mdc)):

1. Целевое состояние (слои, инварианты)
2. Контракты (какие POJO/токены/сигнатуры; что **не** менять в wire)
3. Data flow (проход 1 → рамка → аллеи/площадь)
4. Порядок имплементации по слоям, не «сначала один район»
5. Тесты / риски / что остаётся leftover

## Продуктовый lock (уже согласован с мастером)

**Середина одна — у района**, не у города.

- `position: "center"` = домашний модуль **inner bbox слота района** (fine cells, решётка `block_size`). Не centroid footprint поселения. Не `CellZone.center`.
- `CellZone.center` на `civic_center` — куда садится **район** на сетке города. Не reopen.
- Несколько `required_structures` с `center` → **один кластер** вокруг того же домашнего модуля: участки **рядом** (4-соседство модулей), первый в массиве ближе к точному центру.
- Рамка улиц прохода 1 обходит **весь** кластер (как сейчас обходит одну ратушу).
- Связка внутри кластера:
  - **Аллея** — если ≥2 участка в бине и в `connections` района есть нитка аллеи. Не выдумывать новый тип ребра.
  - **Площадь** — только если в кластере **пин** участка с листом `plaza` (`plot_template`, обычно без `main_building`). Packing **не** подставляет чертёж площади сам. Канонного `plaza_*.json` в packing-каталоге сейчас нет.
- Не влезло в inner bbox: что влезло — сажать; остальное leftover + warning. **Не** проход 2. **Не** расти `DistrictSlot`.
- Канон civic по-прежнему один `town_hall` с `center` — кластер проявляется, когда мастер (или тест) даст два+ `center`.

## Сейчас в коде (дырявый исход)

[`backend/app/application/worldData/generators/assemblers/districtAssembler/planner/pass1.py`](../../backend/app/application/worldData/generators/assemblers/districtAssembler/planner/pass1.py): флаг `center_taken` — первый `center` на домашний модуль, остальные leftover + `PackingReason.CENTER`. `run_pass1` leftover дальше не едят (`_ = leftover1` в assembler). Проход 2 не берёт `required` (`_pass2_tokens`).

Pin участка: `RequiredStructure.plot_template` (`DrawingKey`). Leftover JSON `building_template`. Не путать с SQL `building_templates`.

## SoT

- [`docs/tz_structure_connections.md`](../../docs/tz_structure_connections.md) §5.1.3 «Два прохода», §8 CONN-PACK-2 (сейчас: «кто занимает центр; второй leftover / смещение / warning»)
- [`docs/tz_city_generation.md`](../../docs/tz_city_generation.md) §9.4 `position`
- Inner bbox / решётка: `pass1._center_module`, `barrierInset.inner_bbox_for_slot`
- Аллеи: `districtAssembler/planner/frontage.py` `add_alleys`; ТЗ: ≥2 в модуле → `alley` из connections
- `plaza`: тег purpose, не тип ребра; frontage не выбирает парадную

После утверждения плана (не в этом задании) обновить CONN-PACK-2 в connections §8 + city §9.4 + очередь в [`.cursor/plans/city-generation-remaining-holes.md`](./city-generation-remaining-holes.md).

## Якоря проекта (не нарушать)

- Не трогать `engine/nodes/` (Gate DAG)
- Ранг ≠ морфология; generate в fine cells
- Не писать код, пока нет «делай»
- Не reopen: дерево purpose / паки / `plot_template` rename / §9.3 / `connections[].role`
- Не CONN-PACK-1 (`radial`/`organic` рамка), не CONN-PACK-3 (AABB до рамки), не CITY-T-1c стены, не footprint без subtype
- Не invent лист purpose и не invent чертёж `plaza` «чтобы связать центр»
- `dataModel` — SoT полей; не дублировать литералы

## Вопросы, которые план должен закрыть (не оставлять «потом»)

1. Геометрия кластера: один связный супер-бин вокруг home vs жадная посадка соседних спанов по очереди массива.
2. Зазор между участками кластера: 0 модулей / 1 модуль под аллею / только щель packing.
3. Если в кластере пин `plaza` — она **дыра между** зданиями или ещё один соседний участок с тегом plaza.
4. `count: 2` на одном `plot_template` с `center` — две копии в том же кластере.
5. `plot_priority > 0` без `center` — не в кластер (как сейчас: first-fit проход 1).
6. Тесты: два center влезают; второй не влезает → leftover; civic один town_hall без регрессии.

Ответ пользователю: краткое резюме плана + путь к файлу в `.cursor/plans/`. Не имплементировать.
