---
name: "source-command-impl-wilderness-0"
description: "Имплементирует шаг 0 плана wilderness-regions-mechanic: перенос seeded_u01/seeded_index в app/ids, удаление bake_seed (потребители → seed_root без fallback), таблица каналов UidKind.REGION. Новый чат: /impl-wilderness-0."
---

# source-command-impl-wilderness-0

Use this skill when the user asks to run the migrated source command `impl-wilderness-0`.

## Command Template

# Имплементация: wilderness-0 — det-утилиты в `app/ids`

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/wilderness-regions-mechanic.md`](../../../.cursor/plans/wilderness-regions-mechanic.md) — **единственный SoT этой задачи**: §4 таблица шагов, строка **0** (цель/ТЗ/файлы/проверка); §5 #4 — таблица каналов `UidKind.REGION` и формулы вызовов. Не отклоняться.
2. [`docs/project_data_storage_tz.md`](../../../docs/project_data_storage_tz.md) — § DET-1 / det-функции `app.ids`: контракт `seeded_u01`/`seeded_index`, снятие `bake_seed`, разделение потоков по `channel`.
3. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок»
   - [`.cursor/rules/layer-boundaries.mdc`](../../../.cursor/rules/layer-boundaries.mdc)
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Что уже есть — не переписывать

- `backend/app/ids/deterministicIds.py` — целевой дом для det-утилит (туда переносятся тела `seeded_u01`/`seeded_index`, без изменений алгоритма).
- `backend/app/ids/uidKind.py` — `UidKind` StrEnum; в этом шаге `UidKind.REGION` **не** добавляется (это шаг 3).
- `backend/app/application/worldData/generators/terrain/relief/geom/seededHash.py` — текущие `seeded_u01`/`seeded_index` (переносим тела в `app/ids`, файл удаляем).
- `backend/app/application/worldData/generators/terrain/relief/geom/bakeSeed.py` — `bake_seed(world)` с тихим fallback `"world"` (файл удаляем; fallback **не переносится**).
- Потребители (перевести импорты на `app/ids`, `bake_seed` → `seed_root`):
  - `generators/terrain/relief/__init__.py`
  - `generators/terrain/relief/pick/templatePick.py`
  - `generators/terrain/relief/pick/kindRoll.py`
  - `pack/refine/detailed/detailedGradeDiscover.py`
  - `generators/terrain/mountains/materializer.py`
- Тест: `tests/test_deterministic_ids.py` — существующие проверки det-функций должны остаться зелёными без изменения результата.

## Скоуп шага 0 — строго по плану §4

- Перенос `seeded_u01(world_seed, kind, **keys)` и `seeded_index(world_seed, kind, n, **keys)` в `backend/app/ids/deterministicIds.py` (тела без изменений); экспорт через `ids/__init__.py`.
- Удаление `relief/geom/seededHash.py` и `relief/geom/bakeSeed.py`; все вызовы `bake_seed(world)` → `seed_root(world)`.
- Тихий fallback `"world"` при отсутствии `world_uid` — **запрещён**: объект без `world_uid` = ошибка вызова; чинить вызов, не подставлять дефолт.
- Таблица каналов `UidKind.REGION` (#4 плана) — документировать в коде контракт каналов (`channel="seed"/"claim"/"edge"/"density"`) для будущих потребителей шагов 4–7 (комментарий/docstring в `deterministicIds.py`; кода самих каналов пока нет).
- **Не в шаге 0:** `UidKind.REGION` (шаг 3), `RegionShape`/Specs (шаг 2), rasterizer/resolver/materializer (4–6), region_states (9a–c), StateChangeConsumer (10a). Ничего из них не создавать.

## Жёсткие запреты

- Тела функций и формулы seed'ов не меняются — перенос = copy, иначе рушится детерминизм существующих миров (relief pick, mountains materialize).
- Не добавлять `UidKind.REGION` и не трогать формулу `entity_uid`.
- Не трогать DAG-ноды, schema, не стартовать backend, не коммитить.
- Нет новых fallback/дефолтов: `seed_root` — единственный источник; объект без `world_uid` — ошибка контракта.
- Проверки запускать из `backend/`; не чинить окружение «заодно».

## Приёмка (из плана, строка 0)

- `python -m compileall backend/app` — чисто; импортов `seededHash`/`bakeSeed` в дереве не осталось (grep).
- `python -m unittest tests.test_deterministic_ids` — зелёный, результаты det-функций идентичны до/после.
- Relief pick / kind roll и mountains materialize на тест-мире — результат идентичен до/после (значения seed'ов не сдвинулись).
- Пометка «выполнен» в плане — только после приёмки и «ок» мастера.

## Старт

Прочитай план целиком, сверь строку шага 0 с текущим кодом (потребители могли уехать), покажи карту переноса (файл → новый импорт → вызов `seed_root`) до первой правки.
