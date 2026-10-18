---
name: "source-command-impl-wilderness-9b"
description: "Имплементирует шаг 9b плана wilderness-regions-mechanic: RegionState POJO (dm/regions/regionState.py — current_type/pending_target TerrainKey, progress, history[] append-only, state_fingerprint, tombstone) + revision-check в landcover collect: state_fingerprint(spec_wire) ≠ store → клетки региона в тайле перекрашиваются. Входы закрыты: 3, 9a. Новый чат: /impl-wilderness-9b."
---

# source-command-impl-wilderness-9b

Use this skill when the user asks to run the migrated source command `impl-wilderness-9b`.

## Command Template

# Имплементация: wilderness-9b — `RegionState` POJO + revision-check

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

**Блокер-условия:**
1. Шаг 9a — `region_states` SQL + `iRegionStateRepository` (read-side уже нужен для revision-check; если 9a не сдан — stub-reader из шага 6 заменяется реальным repo в этом же шаге или ждать 9a).
2. Шаг 3 — `state_fingerprint`, `region_uid`-формула.
Чего-то нет → стоп, доклад мастеру.

## Прочитать до первой правки

1. [`.cursor/plans/wilderness-regions-mechanic.md`](../../../.cursor/plans/wilderness-regions-mechanic.md) — **единственный SoT этой задачи**: §4 строка **9b** (цель/ТЗ/файлы/проверка); §5 #8 (revision-check: mismatch → клетки региона **в этом тайле** перекрашиваются, немедленной перепечки мира нет; declared-edit правила — shape-edit keep type/reset progress, type-edit reset к `entry_type` + history, rename → новая сущность/orphan), #11 (поля POJO, `history[]{from,to,cause,at}` — привязка к событию/времени позже). Не отклоняться.
2. [`docs/tz_world_pack_storage.md`](../../../docs/tz_world_pack_storage.md) — § **Region state store** (поля, append-only history, single-writer) и § Region state overlay (контекст read).
3. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок»
   - [`.cursor/rules/contract-creation.mdc`](../../../.cursor/rules/contract-creation.mdc) — инвентаризация `dataModel`/`app/ids` до новых полей
   - [`.cursor/rules/type-kind-str-fields.mdc`](../../../.cursor/rules/type-kind-str-fields.mdc) — `current_type`/`pending_target`/`from_type`/`to_type` = `TerrainKey` (`RegistryKey`), **не** `str`; `cause` — StrEnum/закрытый набор
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Что уже есть — не переписывать

- `backend/app/db/repositories/iRegionStateRepository.py` + `db/models/regionState.py` (9a) — хранилище; здесь — read-side в collect и POJO-контракт над ним.
- `backend/app/ids/deterministicIds.py` — `state_fingerprint(spec_wire)`.
- `TerrainKey` (`RegistryKey[WorldTerrainRegistry]`) — тип для ключей покрытия (WR-TD-1: `ResolvedRegion`/`StateSnapshotEntry` уже typed — тот же паттерн, инвентаризация обязательна).
- `wd/generators/terrain/landcover/collect.py` — точка revision-check: Spec-контекст уже собирается здесь (resolve anchors, state-lookup заглушка из 6 — заменяется repo-read).
- `db/mapper.py` — конвенция row↔model; repo read → dataclass, POJO — отдельный dataModel-слой.
- `validate_reference_value`/`WorldRegistryIndex`/`reject_unresolved` — REF-W membership на границе (если применимо к state-чтению — по образцу `regionCoverageValidation.py`).

## Скоуп шага 9b — строго по плану §4

- `backend/app/dataModel/regions/` (новый пакет) — `regionState.py`:
  - `RegionState` (frozen Pydantic): `region_uid`, `current_type: TerrainKey`, `pending_target: TerrainKey | None`, `progress: float` (0..1/ge-ограничение), `last_eval_tick: int`, `overrides: RegionStateOverrides | None` (typed, не голый dict — `density` и др. по контракту), `history: list[RegionStateTransition]` (`{from_type: TerrainKey, to_type: TerrainKey, cause: <StrEnum-набор причин>, at: str|int}` — append-only семантика, `cause`-enum по канонам плана: `drift|declared_edit|event|…` — свериться с ТЗ; нет набора — предложить `RegionTransitionCause` enum и записать в ТЗ/план), `state_fingerprint: str`, `tombstone: bool`.
  - Маппинг POJO ↔ `db/models/regionState.py` (JSON полей `overrides`/`history` — typed сериализация, не `json.loads` на произвол).
- `landcover/collect.py` — revision-check:
  - чтение state для региона через repo (замена заглушке шага 6; repo-absent кейс — `None` → spec→fallback без падения);
  - `state_fingerprint(spec_wire)` текущего Spec ≠ `state.state_fingerprint` → клетки региона **в этом тайле/scope** перекрашиваются (re-materialize footprint; глобальный re-bake не инициируется);
  - declared-edit семантика из #8: mismatch по shape → keep `current_type`/reset progress при записи (запись — не здесь, здесь только repaint + сигнал потребителю; запись стейта — single-writer 10a);
  - tombstone-регион → spec не материализуется (регион мёртв) либо policy-fallback — по ТЗ.
- Юнит-тесты по приёмке ниже.

- **Не в шаге 9b:** write-path стейта (10a), read-overlay facade (9c), `overrides.density` применение в растризации (если не покрыто — отдельный вопрос к плану), worldEdit (10c).

## Жёсткие запреты

- `*_type`/`cause` — typed (`TerrainKey`/enum); `str`-поля контракта только через исключение в ТЗ (новые rules).
- Revision-check не пишет в store — чтение + сигнал; single-writer — 10a.
- Re-materialize ограничен текущим scope bake (тайл), не «весь регион» — инвариант #8.
- Исторический manifest — snapshot (WR-TD-1): fingerprint/state из manifest не подменяется live-store при чтении пака.
- Не трогать DAG-ноды, SQL (9a), не стартовать backend, не коммитить.
- Проверки запускать из `backend/`; не чинить окружение «заодно».

## Приёмка (из плана, строка 9b)

- `python -m compileall backend/app` — чисто.
- Юнит: `state_fingerprint` mismatch → клетки региона в тайле перекрашиваются (paint отличается от store-snapshot); match → без изменений.
- `RegionState` round-trip POJO ↔ db-модель (overrides/history typed, не строки-JSON на выходе).
- Tombstone-регион — поведение по ТЗ (не красится / fallback — зафиксировать факт в отчёте).
- Пометка «выполнен» в плане — только после приёмки и «ок» мастера.

## Старт

Прочитай план целиком, проверь блокеры, сделай инвентаризацию `dataModel`/`ids` (`TerrainKey`, `StateSnapshotEntry`, `regionCoverageValidation`) до новых полей, покажи POJO-контракт и точку revision-check в `collect.py` до первой правки.
