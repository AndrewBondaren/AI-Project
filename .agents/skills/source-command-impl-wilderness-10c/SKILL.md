---
name: "source-command-impl-wilderness-10c"
description: "Имплементирует шаг 10c плана wilderness-regions-mechanic: worldEdit регионов — add/remove/update declared_regions[] keyed by name, remove → tombstone в region_states, draft-валидация (name обязателен, коллизия имён) через ResolveContext.validate_only; runtime — WarningError + degraded uid; одинаковое решение в обоих режимах. Входы закрыты: 3 (uid-формула), 9a (store), 10a (consumer). Новый чат: /impl-wilderness-10c."
---

# source-command-impl-wilderness-10c

Use this skill when the user asks to run the migrated source command `impl-wilderness-10c`.

## Command Template

# Имплементация: wilderness-10c — worldEdit регионов

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

**Блокер-условия (все):**
1. Шаг 3 — `region_uid` формула + degraded-режим (`log_issues`).
2. Шаги 9a/10a — `region_states` store + `StateChangeConsumer` (tombstone — его write-канал).
Чего-то нет → стоп, доклад мастеру.

## Прочитать до первой правки

1. [`.cursor/plans/wilderness-regions-mechanic.md`](../../../.cursor/plans/wilderness-regions-mechanic.md) — **единственный SoT этой задачи**: §4 строка **10c** (цель/ТЗ/файлы/проверка); §5 **#7 worldEdit** (операции add/remove/update элемента `declared_regions[]` keyed by `name`; remove → orphan state → tombstone+чистка; draft-валидация: `name` обязателен, uid-коллизия двух declared с одним именем — ошибка), **#1** (degraded uid в runtime), #8 (declared-edit → reset-правила: shape-edit keep type/reset progress, type-edit reset к `entry_type` + history, rename → новая сущность). Не отклоняться.
2. [`docs/tz_runtime_world_edit_policy.md`](../../../docs/tz_runtime_world_edit_policy.md) — общий worldEdit/draft-контракт (операции, валидация, apply).
3. [`docs/tz_map_light_bake.md`](../../../docs/tz_map_light_bake.md) — § Регионы покрытия › **Identity** (author-check vs runtime-разделение через `validate_only`).
4. [`docs/tz_json_validation.md`](../../../docs/tz_json_validation.md) — `ResolveContext`/`FieldPathError`/issue-отчёт идиомы.
5. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок»
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/layer-boundaries.mdc`](../../../.cursor/rules/layer-boundaries.mdc) — route thin, логика в сервисах
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Что уже есть — не переписывать

- `backend/app/application/jsonValidation/resolve.py` — `ResolveContext` (`validate_only`, `child`, `report_issues`, `FieldPathError`) — существующая идиома разделения author-check/runtime (используется для `name`-валидации).
- `backend/app/api/routes/worlds.py` — `import_world` с `validate_only` Query-param (~95–111) — точка draft-проверки.
- `backend/app/application/imports/` — import helpers/result; handlers импорта мира.
- `wd/regions/stateChange/consumer.py` (10a) — `StateChangeConsumer` пишет tombstone/reset через repo; worldEdit вызывает его интерфейс, не repo напрямую.
- `ids/regionIdentity.py` — uid-формула с degraded-веткой (3): `validate_only` → issue; runtime → `log_issues` WarningError + degraded uid.
- `RegionSpecBase.name`/`identity_key` (2) — ключ операций add/remove/update.

## Скоуп шага 10c — строго по плану §4

- Операции worldEdit на `declared_regions[]`:
  - `add` — новый элемент union `LandcoverDeclareEntry` (author-валидация форм из шага 2 + `name` обязателен + уникальность имени в коллекции → uid-коллизия двух declared с одним `name` = ошибка);
  - `update` — по `name` (identity): правка shape/params; declared-edit правила #8 — `entry_type`-смена → reset state к новому `entry_type` + history; shape-edit → keep `current_type`, reset progress; rename → новый uid = новая сущность, старый state → orphan → tombstone;
  - `remove` — удаление элемента → `region_states` tombstone через `StateChangeConsumer` (не прямым repo-write) + чистка orphan при следующем чтении/bake.
- Draft-валидация через `ResolveContext.validate_only` (`import_world?validate_only=true` + будущий worldEdit draft): `name` отсутствует → issue (ошибка); коллизия имён → issue; некорректная форма shape → issue; **одинаковое решение в обоих режимах** — та же функция валидации, различие только sink (issue-report vs `log_issues` WarningError + degraded uid).
- Runtime без `name` → degraded uid (`bbox_min`+`kind`/`anchor_uid`/`seed_xy`) + `log_issues` — регион работает.
- Юнит/API-тесты по приёмке ниже.

- **Не в шаге 10c:** `StateChangeConsumer` internals (10a — есть), tombstone-store (9a — есть), region overlay (9c — есть), UI редактора миров.

## Жёсткие запреты

- Одинаковое решение в обоих режимах — одна валидационная функция; не плодить «импорт-вариант» и «edit-вариант» с разным результатом.
- Tombstone/write state — только через `StateChangeConsumer` (single-writer #8/#11); worldEdit не пишет repo сам.
- `name` — `strip()`+NFC по #1; `|` в имени — ошибка author-check (не silent-правка).
- Никаких силовых overwrite сущностей при rename — rename = новая сущность, старый state orphan→tombstone.
- Не трогать DAG-ноды, schema (9a), не стартовать backend, не коммитить.
- Проверки запускаются из `backend/`; не чинить окружение «заодно».

## Приёмка (из плана, строка 10c)

- `python -m compileall backend/app` — чисто.
- `POST /worlds/import?validate_only=true` с `declared_regions[]` без `name` → issue в отчёте (ошибка), импорт не применяется.
- Обычный импорт без `name` → WarningError в логе + degraded uid (регион работает).
- Коллизия имён двух declared → issue/ошибка в обоих режимах одинаково.
- `remove` → tombstone в store; повторная вставка того же `name` после remove → чистая сущность (нет воскрешения старого state).
- `update` shape → тот же uid, progress reset; `update` entry_type → reset + history-запись; rename → новый uid, старый orphan→tombstone.
- Пометка «выполнен» в плане — только после приёмки и «ок» мастера.

## Старт

Прочитай план целиком, проверь блокеры, найди точку worldEdit/import handlers, где материализуется `declared_regions` (сверь с `imports/` и `worlds.py`), покажи контракт операций и разводку `validate_only`/runtime до первой правки.
