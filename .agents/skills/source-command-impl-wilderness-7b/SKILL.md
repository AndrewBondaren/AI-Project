---
name: "source-command-impl-wilderness-7b"
description: "Имплементирует шаг 7b плана wilderness-regions-mechanic: L2 hills/open-land cutover — place_hills по TerrainRegistryEntry.hills ключа клетки (не пара plains_key/forest_key), openLandTerrains → предикат реестра terrain_category. default_*.hills — wire-совместимый источник до миграции данных. Входы закрыты: 3 (hills на записи), 7. Новый чат: /impl-wilderness-7b."
---

# source-command-impl-wilderness-7b

Use this skill when the user asks to run the migrated source command `impl-wilderness-7b`.

## Command Template

# Имплементация: wilderness-7b — hills / open-land по ключу реестра

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

**Блокер-условия:**
1. Шаг 3 — `TerrainRegistryEntry.hills: HillPolicy | None` существует, builtin `hills` для forest/plains в `canonical_defaults()`.
2. Шаг 7 — region paint на fine-сетке подключён.
Чего-то нет → стоп, доклад мастеру.

## Прочитать до первой правки

1. [`.cursor/plans/wilderness-regions-mechanic.md`](../../../.cursor/plans/wilderness-regions-mechanic.md) — **единственный SoT этой задачи**: §4 строка **7b** (цель/ТЗ/файлы/проверка); §5 #5 (порядок hills относительно region paint), #9 (hills-политика transitional в `default_*`, holder переезжает на ключ). Не отклоняться.
2. [`docs/tz_world_pack_storage.md`](../../../docs/tz_world_pack_storage.md) — § **L2 open-land hills** (target: `TerrainRegistryEntry.hills`, `default_*.hills` — wire-совместимый источник для builtin-ключей до миграции данных мира; локационный override не меняется).
3. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок»
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc) — политика холмов из реестра/POJO, не литералы
   - [`.cursor/rules/layer-boundaries.mdc`](../../../.cursor/rules/layer-boundaries.mdc)
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Что уже есть — не переписывать

- `backend/app/application/worldData/generators/terrain/hills/hillPlacement.py` — `place_hills(…, plains_key, forest_key, …)` (строка 20): сейчас решает «ставить ли холмы» по двум ключам покрытия.
- `backend/app/application/worldData/generators/terrain/relief/sample/openLandTerrains.py` — open-land предикат по двум ключам.
- `backend/app/application/worldData/materialize/terrainBatchOrchestrator.py` — вызов `place_hills` с `plains_key=masks.default_plains.system_terrain, forest_key=masks.default_forests.system_terrain` (~181–182).
- `backend/app/dataModel/terrainMasks/hillPolicy.py` — `HillPolicy` POJO (уже встроена в `default_plains`/`default_forests` и на локации — override-цепочка не меняется).
- `TerrainRegistryEntry.hills` (шаг 3) — holder политики на ключе; `terrain_category` — предикат open-land (вход — если категории на ключах существуют; нет — см. протокол ниже).

## Скоуп шага 7b — строго по плану §4

- `place_hills` — политика выбирается по `system_terrain` клетки → `terrain_registry.entry_for(key).hills`; ключ без `hills` → холмов нет. `plains_key`/`forest_key`-параметры **удаляются** из сигнатуры (вместе с вызовом в оркестраторе).
- `default_forests.hills`/`default_plains.hills` — остаются **wire-совместимым источником** для builtin-ключей до миграции данных мира: canonical defaults реестра читают из них (или наоборот — как зафиксировано в ТЗ; **не** дублировать литерал в двух местах — один источник).
- `openLandTerrains` — предикат реестра (`terrain_category` записи) вместо пары ключей; если `terrain_category` на записи ещё нет — ввести как часть этого шага в dataModel (canonical defaults: open-land у plains/steppe/farmland-классов; forest/water — нет) **или** стоп с докладом, если категория — отдельный контракт. Проверить по ТЗ до кода.
- Локационный override hills (на `location`-политике) — без изменений.
- Юнит/smoke по приёмке ниже.

- **Не в шаге 7b:** удаление `default_forests`/`default_plains` целиком (10b), `ForestsCategoryPolicy`/`PlainsCategoryPolicy` (10b), region paint (7 — уже есть), manifest/state (8–10).

## Жёсткие запреты

- Нет перебора «известных ключей» (`if key in (plains, forest)`) — только запись реестра; N+1-ключ с `hills` получает холмы без правок engine.
- Один источник builtin-политики: либо `default_*.hills` → canonical entry, либо наоборот — без двух литералов (dataModel-no-hardcode).
- Поведение для `forest`/`plains` — как до шага (проверка).
- Не трогать DAG-ноды, schema (поле на dataModel-записи — wire; SQL не нужна, реестр — JSON мира), не стартовать backend, не коммитить.
- Проверки запускать из `backend/`; не чинить окружение «заодно».

## Приёмка (из плана, строка 7b)

- `python -m compileall backend/app` — чисто; `grep` `plains_key`/`forest_key` по `place_hills` — ноль.
- Refine чанка со `steppe`-регионом (N+1-ключ с `hills` в записи): холмы ставятся, open-land grade срабатывает — без правок engine.
- `forest`/`plains` — результат идентичен до/после.
- Ключ без `hills` в записи → холмов нет; `terrain_category` не open-land → grade не срабатывает.
- Пометка «выполнен» в плане — только после приёмки и «ок» мастера.

## Старт

Прочитай план целиком, проверь блокеры, выясни — есть ли `terrain_category` на `TerrainRegistryEntry` (шаг 3) или нужен в этом шаге; покажи diff-карту (`hillPlacement.py`, `openLandTerrains.py`, `terrainBatchOrchestrator.py`, при необходимости `terrainRegistryEntry.py`/`canonical_defaults`) до первой правки.
