---
name: impl-location-transitions
description: >-
  Имплементирует согласованный план location-transitions по одному шагу:
  физические переходы, SQL/pack и application CRUD. Продолжение после S0 — C1.
  Новый чат: /impl-location-transitions.
---

# Имплементация: location-transitions

Вызов этой команды — явная просьба писать код в рамках согласованного
плана. Не запрашивай повторное разрешение на текущий шаг. Выполняй один
шаг за заход: проверка → отчёт → ожидание «ок» мастера → следующий шаг.

## Прочитать до первой правки

1. [Завершённый план location-transitions](../plans/location-transitions-done.md) целиком:
   scope, архитектура, контракты, data flow, зависимости и статусы шагов.
2. [ТЗ переходов](../../docs/tz_location_transitions.md) целиком.
3. Указанные в выбранном шаге разделы связанных ТЗ. Для C1:
   [tz_json_validation.md](../../docs/tz_json_validation.md), POJO-first/N1-W.
4. Правила [code-gates](../rules/code-gates.mdc),
   [project-context](../rules/project-context.mdc),
   [layer-boundaries](../rules/layer-boundaries.mdc),
   [dataModel-no-hardcode](../rules/dataModel-no-hardcode.mdc),
   [pojo-world-row-wire](../rules/pojo-world-row-wire.mdc),
   [json-validation-architecture](../rules/json-validation-architecture.mdc),
   [deterministic-ids](../rules/deterministic-ids.mdc),
   [database-migrations](../rules/database-migrations.mdc),
   [bulk-sql](../rules/bulk-sql.mdc) и другие применимые правила.

Не опирайся на память предыдущего чата. Семантика — в ТЗ, порядок поставки
и зависимости — в плане, defaults/wire policies — в POJO. Противоречие,
которое мешает текущему шагу, вынеси мастеру; не переписывай доменное ТЗ
и не вводи новый контракт молча. Отложенные вопросы вне шага не блокируют его.

## Выбрать шаг

На момент создания команды S0 выполнен 2026-10-06; следующий шаг — C1.
Перечитай актуальные статусы плана и текущий код: статус может измениться.
Возьми первый незавершённый шаг в порядке §5, только если Done всех его
зависимостей подтверждён. Если мастер указал шаг аргументом, проверь его
место в последовательности; не перескакивай незакрытые зависимости.
Не повторяй уже сделанное и не считай зависимость готовой только потому,
что соответствующий файл существует.

Перед изменениями проверь git status/diff и callers. В workspace есть
независимые изменения UID/assembler/extract; не откатывай и не переписывай
их. Используй уже существующий worldData/ids helper, не создавай второй.

## Первый кодовый шаг — C1

Создай engine enum TransitionType и единый N+1 реестр согласно §3.1 ТЗ:
metadata entry/directional/vertical, обязательный behaves_as,
RegistryKey, SCHEMA_ID и canonical_engine по действующим POJO-паттернам.

Файлы по плану, относительно backend/:

- app/dataModel/locations/transitions/transitionType.py
- app/dataModel/locations/transitions/transitionTypeEntry.py
- app/dataModel/locations/transitions/worldTransitionTypeRegistry.py
- tests/test_transition_registry.py

Portal — один builtin-тип; graph/coordinate — реализации портала,
не отдельные TransitionType. Не реализуй destination/arrival algorithms.
Не удаляй PassageType и не переключай generator callers в C1.
Сначала сверяй действующие образцы реестров и metadata; не копируй
таблицы поведения/defaults в несколько слоёв.

Проверка из backend/:

```powershell
& '..\.venv\Scripts\python.exe' -m unittest tests.test_transition_registry
```

Проверить builtin metadata, main/service/hidden, custom behaves_as,
ошибки неизвестного builtin. Done: один typed реестр поведения готов,
действующие generator enums/callers продолжают работать.

Для последующих шагов бери файлы, контракты и проверки из актуального
плана, не из отдельного самостоятельно придуманного чеклиста.

## Принятые границы

- Единый Transition и отдельная transition_sides; parent/child не условие прохода.
- Surface — явное пространство по умолчанию, без фиктивной NL/нулевой клетки
  и обязательных ручных xyz. Поиск выхода — отложенный SURFACE-T-1.
- is_accessible — состояние движка, не направленность. Не придумывай
  правило проверки обеих сторон или персональное discovery.
- SQL — наружные/runtime переходы; pack — interior одного здания по явному
  layout scope. Существующие production callers переключаются в G3,
  после готовности extract/codec и проверки нового write/read пути.
- Operational portal, перенос node/import portal_*, PORTAL-T-1,
  WP-13, traversal, discovery, DAG/actions, новый bundle/converter,
  regenerate/reset policy — вне текущей реализации.
- Legacy passage/entry cleanup — только F1 после готовности callers/readers.

## Запреты и отчёт

Не запускай backend; не меняй DAG-ноды; не коммить и не пушь.
DDL — только 0001_initial.sql + db/models в соответствующем шаге,
без новых миграций и удаления рабочей БД. Массовый SQL — app.db.bulkSql.
Генераторы чистые; persist/CRUD/scene decisions не помещать внутрь них.

После проверок разрешена краткая статусная пометка выполненного шага
в плане: дата, что сделано, результаты проверок, следующий шаг.
Не меняй состав шагов/scope заодно. Не отмечай весь план DONE до A1.

Отчёт: выполненный шаг, изменённые файлы/контракт, проверки и результат,
оставшиеся ограничения и следующий шаг. Остановись после одного шага
и жди «ок» по code-gates; не начинай следующий автоматически.
