---
name: "source-command-impl-wilderness-9a"
description: "Имплементирует шаг 9a плана wilderness-regions-mechanic: region_states SQL-таблица в 0001_initial.sql + db/models/regionState.py + iRegionStateRepository (upsert/tombstone, массовая запись через bulkSql). Entity-store рядом с Patch Store, не WP-20. Single-writer — StateChangeConsumer (10a). Входы закрыты: 3 (region_uid, state_fingerprint). Новый чат: /impl-wilderness-9a."
---

# source-command-impl-wilderness-9a

Use this skill when the user asks to run the migrated source command `impl-wilderness-9a`.

## Command Template

# Имплементация: wilderness-9a — `region_states` store

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

**Блокер-условие:** шаг 3 сдан — `region_uid` формула и `state_fingerprint` существуют (`ids/regionIdentity.py`, `ids/deterministicIds.py`); модели региона на месте. Нет → стоп, доклад мастеру.

## Прочитать до первой правки

1. [`.cursor/plans/wilderness-regions-mechanic.md`](../../../.cursor/plans/wilderness-regions-mechanic.md) — **единственный SoT этой задачи**: §4 строка **9a** (цель/ТЗ/файлы/проверка); §5 #8 — почему entity-store, а не WP-20 (`map_cell_patches` — per-cell дельты `(x,y,z)`, состояние сущности туда не ложится); single-writer — `StateChangeConsumer` (10a), здесь только хранилище; tombstone-политика (`remove` declared → orphan → tombstone + чистка при следующем чтении/bake); single-writer на уровне API — write-методы repo не дёргаются из bake/генераторов. Не отклоняться.
2. [`docs/tz_world_pack_storage.md`](../../../docs/tz_world_pack_storage.md) — § **Region state store** (таблица `region_states`, keyed `(world_uid, region_uid)`, поля: `current_type`, `pending_target`, `progress`, `last_eval_tick`, `overrides` JSON, `history` JSON append-only `{from_type,to_type,cause,at}`, `state_fingerprint`, `tombstone`; схема — `0001_initial.sql` + `db/models/regionState.py` + repo; массовая запись — `app.db.bulkSql`).
3. [`docs/tz_map_light_bake.md`](../../../docs/tz_map_light_bake.md) — § Регионы покрытия › Состояние и переходы (контекст полей).
4. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок»
   - [`.cursor/rules/bulk-sql.mdc`](../../../.cursor/rules/bulk-sql.mdc) — массовая запись **только** `executemany_rows`/`iter_batches`, своих циклов/констант нет
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — schema только `0001_initial.sql` + sync `db/models` **в одном заходе**; recreate БД (drop+restart), не incremental; не DAG, не стартовать backend, не коммитить
   - [`.cursor/rules/layer-boundaries.mdc`](../../../.cursor/rules/layer-boundaries.mdc)
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Что уже есть — не переписывать

- `backend/app/db/migrations/0001_initial.sql` — единственная точка DDL; образец таблиц entity-store рядом (не `map_cell_patches` — другой тип).
- `backend/app/db/models/` — snake_case dataclass-модели (`mapCell.py`, `namedLocation.py`…); `db/mapper.py` — образец маппинга row↔model.
- `backend/app/db/repositories/i*Repository.py` — конвенция имён (`iMapCellRepository.py`, `iNamedLocationRepository.py`…); `BaseRepository.upsert`/`execute` для поштучных записей.
- `backend/app/db/bulkSql.py` — `executemany_rows`/`iter_batches`/`EXECUTEMANY_BATCH_SIZE` — массовые записи (bulk tombstone/чистка).
- `backend/app/db/guardedConnection.py` / `database.py` — конвенции соединений/transactions.
- `RegionState` POJO — шаг 9b (здесь только SQL/dataclass/repo; если POJO уже появился — sync полей обязателен, не дублировать).

## Скоуп шага 9a — строго по плану §4

- `0001_initial.sql` += таблица `region_states` (`world_uid`, `region_uid` PK-пара, `current_type`, `pending_target`, `progress`, `last_eval_tick`, `overrides` JSON, `history` JSON, `state_fingerprint`, `tombstone`, timestamps по конвенции таблиц) — **entity-store**, не patch-таблица.
- `db/models/regionState.py` — dataclass-модель, sync полей со schema (одним заходом, `validate_schema` не должен падать).
- `db/repositories/iRegionStateRepository.py` — repo: get/upsert (одна строка — `BaseRepository`), bulk-write через `executemany_rows`, `mark_tombstone`/`cleanup_orphans` (по чистке — читать §8 плана: удаление записей tombstoned регионов при следующем чтении/bake), keyed `(world_uid, region_uid)`.
- **Single-writer контракт зафиксировать в модуле** (docstring): writer — `StateChangeConsumer` (шаг 10a); bake/генераторы/repo из других мест не пишут. Чтение свободное (collect/overlay).
- Юнит-тесты repo: upsert/read round-trip, tombstone, cleanup, bulk-pачка через `iter_batches`.

- **Не в шаге 9a:** `RegionState` Pydantic-POJO уровня dataModel (9b), revision-check при bake (9b), read-overlay (9c), writer-логика `StateChangeConsumer` (10a), worldEdit remove→tombstone вызовы (10c). Только схема + модель + repo.

## Жёсткие запреты

- Schema только `0001_initial.sql` — **никаких** `0002_*.sql`; model+SQL в одном заходе (иначе `validate_schema` упадёт).
- `executemany`/пачки — только через `bulkSql` (`executemany_rows`, `iter_batches`); литерала размера пачки нет.
- Ключ `(world_uid, region_uid)` — без суррогатных автоинкрементов; `region_uid` строка uid из `app.ids`.
- `history`/`overrides` — JSON-колонки, не отдельные таблицы (append-only контракт — 9b/10a).
- Repo не содержит бизнес-логики переходов (progress/гистерезис — 10a); repo = CRUD + tombstone + cleanup.
- Не трогать DAG-ноды, не стартовать backend (smoke — `validate_schema` только при старте; подсказать мастеру recreate), не коммитить.
- Проверки запускать из `backend/`; не чинить окружение «заодно».

## Приёмка (из плана, строка 9a)

- `python -m compileall backend/app` — чисто; `validate_schema` при старте (после recreate БД мастером) — проходит.
- Юнит repo: upsert → read идентичен; tombstone-флаг ставится/читается; `iter_batches`-пачка пишет все строки; cleanup удаляет tombstoned; пустой список = no-op.
- Колонки совпадают с ТЗ § Region state store (все поля из списка).
- Пометка «выполнен» в плане — только после приёмки и «ок» мастера.

## Старт

Прочитай план целиком, проверь блокер и то, что `region_states` ещё нет в `0001_initial.sql` (возможно уже появилась — тогда сверка, не дубль), покажи DDL + dataclass + API repo (сигнатуры) до первой правки.
