---
name: "source-command-impl-worlddata-restructure"
description: "Имплементирует шаги 1–2 плана worlddata-domain-restructure: worldData/ids → app/ids и worldData/context → application/cascade (git mv + rewrite импортов). Шаги 3+ заблокированы треком plan-dependency-graph. Новый чат: /impl-worlddata-restructure."
---

# source-command-impl-worlddata-restructure

Use this skill when the user asks to run the migrated source command `impl-worlddata-restructure`.

## Command Template

# Имплементация: вынос ids и cascade из worldData (шаги 1–2)

Это **явная просьба писать код** (шаги плана). Правило no-code-until-asked
на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT,
потом код.

## Прочитать до первой правки

1. [`.cursor/plans/worlddata-domain-restructure.md`](../plans/worlddata-domain-restructure.md) —
   **контракт, целевое дерево, порядок шагов, проверки**; не отклоняться.
   Выполняются **только шаги 1–2**. Шаги 3+ заблокированы условием входа
   (трек [`plan-dependency-graph.md`](../plans/plan-dependency-graph.md)
   не закрыт) — не трогать и не «захватывать заодно».
2. [`docs/project_data_storage_tz.md`](../../docs/project_data_storage_tz.md) § DET-1 —
   контракт det-uid формулы.
3. [`docs/tz_cascade_context.md`](../../docs/tz_cascade_context.md) §2, §4 —
   что живёт в `context/` (движок `extend`, `Link`/`EmptyLink`, location glue).
4. Существующий код:
   - `backend/app/application/worldData/ids/` (`deterministicIds`, `uidKind`, `__init__` re-exports)
   - `backend/app/application/worldData/context/` (`contextResolver`, `runtimeChain`,
     `cascadeLink`, `cascadeLog`, `locationScope`)
5. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../rules/code-gates.mdc) — атомарность шагов,
     отчёт → ожидание «ок»
   - [`.cursor/rules/project-context.mdc`](../rules/project-context.mdc) — не стартовать
     backend, не коммитить без явной просьбы, DAG-ноды не трогать
   - [`.cursor/rules/layer-boundaries.mdc`](../rules/layer-boundaries.mdc)
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../rules/dataModel-no-hardcode.mdc)

План важнее догадок. Противоречие план↔код — остановиться и спросить мастера.

## Цель

- **Шаг 1:** `backend/app/application/worldData/ids/` → `backend/app/ids/`
  (топ-уровень `app/`). Все `app.application.worldData.ids` → `app.ids`
  (~50 файлов: application, tests, scripts, `core/`).
- **Шаг 2:** `backend/app/application/worldData/context/` →
  `backend/app/application/cascade/`. Все `app.application.worldData.context`
  → `app.application.cascade` (~28 файлов: generators, settlementOutdoor,
  api/routes/debug, core/loggingConfig, core/generationLogging, tests).
  Внутри `locationScope`/`contextResolver` импорты `worldData.ids` → `app.ids`
  (шаг 1 уже сделан); `worldData.locationPayloadAccess`/`settlementSkeletonAccess`
  остаются прежними (их переезд — шаг 9, не этот чат).

## Механика

- `git mv` для каждого файла/папки; `__init__.py` переносится с тем же
  re-export surface (`app/ids/__init__.py` = бывший `worldData/ids/__init__.py`).
- Repo-wide замена по `git grep -l "app.application.worldData.ids"` /
  `"app.application.worldData.context"` (включая `backend/tests/`,
  `backend/scripts/`). Формы импорта: `from app.application.worldData.ids import`,
  `from app.application.worldData.ids.deterministicIds import`, `import …`.
- Поведение и сигнатуры не меняются. Не «улучшать» заодно.
- Docstring/комментарии с текстовыми упоминаниями старого пути — **не** чистить
  в этих шагах (синк документации — шаг 12 плана).

## Жёсткие запреты

- Шаги 3–12 плана — не начинать (условие входа: `plan-dependency-graph`
  трек не закрыт).
- `dataModel` — не менять (прямой импорт `LibraryKind` из `app/ids` —
  follow-up плана, не этот чат).
- Binding-таблицу `_MATERIALIZE`/`_FOLDS` в `contextResolver` не трогать —
  направление `cascade → worldData.generators.utils` принято мастером.
- Не новые поля, wire-ключи, schema-изменения. Не DAG `engine/nodes/`.
  Не стартовать backend. Не коммитить без явной просьбы.

## Порядок — строго по шагам

Шаг 1 (ids) → отчёт → ждать «ок» → шаг 2 (cascade) → отчёт.

**Правило мастера:** каждое сообщение мастера после отчёта = приступать
к следующему шагу, **если** в нём нет фидбека по ревью кода. Фидбек —
сначала обработать, шаг не начинать.

После каждого шага: что сделано / файлы / проверки (чем прогнал) / что
осталось / что сознательно не тронуто. Один шаг за заход — без исключений.

## Проверки

Шаг 1:
- `git grep "app.application.worldData.ids"` = 0
- `python -m compileall backend/app`
- `python -m unittest tests.test_deterministic_ids tests.test_library_packs_b3 tests.test_canonical_library` (из `backend/`)

Шаг 2:
- `git grep "app.application.worldData.context"` = 0
- `python -m compileall backend/app`
- `python -m unittest tests.test_context_extend tests.test_cascade_context_baseline tests.test_cascade_migration_m2 tests.test_e6_consumers` (из `backend/`)
- smoke: `python -c "from app.application.cascade.contextResolver import extend, scope_sequence"`

## Приёмка

- Пакеты `app.ids` и `app.application.cascade` импортируются; старых путей
  нет ни в `app/`, ни в `tests/`, ни в `scripts/`.
- Все перечисленные тесты зелёные; `git diff --check` чист.
- Никаких изменений вне mechanical move + import rewrite.

## Старт

Прочитай план целиком + перечисленные файлы. Затем шаг 1.
