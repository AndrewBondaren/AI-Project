---
name: "source-command-impl-wilderness-3"
description: "Имплементирует шаг 3 плана wilderness-regions-mechanic: TerrainRegistryEntry += merge_rank/eligibility/inertia/hills, canonical defaults реестра, UidKind.REGION + формула region_uid (name strip+NFC; degraded fallback bbox_min+kind / anchor_uid / seed_xy), применение state_fingerprint. Входы закрыты: 0, 2. Новый чат: /impl-wilderness-3."
---

# source-command-impl-wilderness-3

Use this skill when the user asks to run the migrated source command `impl-wilderness-3`.

## Command Template

# Имплементация: wilderness-3 — dataModel реестр + `region_uid`

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/wilderness-regions-mechanic.md`](../../../.cursor/plans/wilderness-regions-mechanic.md) — **единственный SoT этой задачи**: §4 строка **3** (цель/ТЗ/файлы/проверка); §5 **#1** — формула `region_uid` по источникам, нормализация `name`, degraded-режим с `log_issues`; **#11** — `EligibilityRule`-контракт scorer'а (`{fact, op: gte|lte|in_range|flag, lo/hi, weight, required}`) и `inertia`. Не отклоняться.
2. [`docs/tz_map_light_bake.md`](../../../docs/tz_map_light_bake.md) — § Регионы покрытия › **Identity** (что входит/не входит в uid), › **Реестр и CoverageResolver** (`merge_rank`, `eligibility`, `inertia`, `hills` на `TerrainRegistryEntry`; builtin-значения — canonical defaults реестра, не литералы в application).
3. [`docs/project_data_storage_tz.md`](../../../docs/project_data_storage_tz.md) — § DET-1: контракт `entity_uid`/`state_fingerprint` (`UidKind` — закрытый StrEnum, расширение = contract change).
4. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок»
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc) — builtin-значения только в `canonical_defaults()` POJO
   - [`.cursor/rules/layer-boundaries.mdc`](../../../.cursor/rules/layer-boundaries.mdc)
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить, schema только через `0001_initial.sql`
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Что уже есть — не переписывать

- `backend/app/ids/deterministicIds.py` — `entity_uid(world_uid, kind, **keys)`, `seed_rng`, `seeded_u01`, `seeded_index` (после шага 0), `state_fingerprint(value)` (строка 160 — **существует, только применить**), `seed_root(world)`; `UID_PART_SEPARATOR`.
- `backend/app/ids/uidKind.py` — `UidKind` StrEnum; сюда `REGION` (contract change — один член).
- `backend/app/dataModel/terrain/terrainRegistryEntry.py` + `worldTerrainRegistry.py` — точки расширения реестра; `canonical_defaults()` — единственное место builtin-значений.
- `backend/app/dataModel/terrainMasks/hillPolicy.py` — `HillPolicy` (реэкспорт/тип для `TerrainRegistryEntry.hills`, не копия).
- `FieldPathError` / `log_issues` / `ResolveContext.validate_only` — существующая инфраструктура диагностики; runtime-разделение режимов по идиоме проекта.
- Модели шага 2 (`RegionSpecBase`, `RegionShape`, `LandcoverDeclareEntry`) — вход; uid-формула опирается на `shape.bbox()` / `shape.kind` / `anchor_uid`.

## Скоуп шага 3 — строго по плану §4

- `TerrainRegistryEntry` += поля: `merge_rank`, `eligibility: list[EligibilityRule]`, `inertia`, `hills: HillPolicy | None`. `EligibilityRule` — POJO `{fact: str, op: Literal["gte","lte","in_range","flag"], lo, hi, weight: float = 1.0, required: bool = False}`.
- `canonical_defaults()` реестра: builtin `merge_rank` (`road > ravine > mountain > forest > plains`), `inertia`, `hills` forest/plains — данные мира, **не** литералы в application; `WorldTerrainMasks.merge_rank_order()` / `TERRAIN_MERGE_RANK_HIGH_TO_LOW` пока **не удалять** (cutover — шаг 3b).
- `UidKind.REGION` в `uidKind.py`.
- Формула `region_uid` (#1) — один helper в `app/ids` или тонкий модуль рядом, вызывающий `entity_uid(world_uid, UidKind.REGION, **keys)`:
  - declared: `name` — `strip()` + Unicode NFC, **без** casefold; `|` в имени — ошибка author-валидации (через `validate_only`-идиому);
  - runtime без `name` — **degraded fallback**: `bbox`/`ellipse`/`polygon` → `bbox_min=(x,y)` из `shape.bbox()` + `kind`; `anchor_radius` → `anchor_uid`; `FieldPathError` → `log_issues` (`landcover | WarningError | path=… code=…`), работа продолжается;
  - anchor: `anchor_uid`; autoresolve: `seed_xy=(x, y)`.
  - В формулу НЕ входят: геометрия дальше bbox-min, `entry_type`/`current_type`, density — правки не убивают сущность.
- `state_fingerprint(spec_wire)` — применить существующую функцию к wire-представлению Spec (для revision-check шага 9b — здесь только доступность/юнит).
- Юнит-тесты по приёмке ниже.

- **Не в шаге 3:** удаление `merge_rank_order`/`system_terrain_for_domain` и перепайка `may_paint_terrain` (шаг 3b), `CoverageResolver` использует `eligibility` (шаг 5a), `place_hills` по ключу (шаг 7b), `RegionState` (9b). Здесь — только данные и identity.

## Жёсткие запреты

- `entity_uid` и формулу существующих видов не менять — `UidKind.REGION` добавление, не правка.
- Нет своих uid-формул/конкатенаций в consumers — только `entity_uid` центра.
- `name` не нормализуется casefold'ом; `|` запрещён в авторском вводе (author-check), в runtime — не silent-исправление, а issue.
- Не трогать DAG-ноды, schema вне `0001_initial.sql`, не стартовать backend, не коммитить.
- Проверки запускать из `backend/`; не чинить окружение «заодно».

## Приёмка (из плана, строка 3)

- `python -m compileall backend/app` — чисто.
- Юнит: правка `rx`/`ry` **именованного** региона ≠ новый uid; **безымянный** bbox — сдвиг min-угла = новый uid **и** WarningError в логе; `anchor_radius` — uid от `anchor_uid`; autoresolve seed → uid от `seed_xy`.
- `state_fingerprint(spec_wire)` меняется при правке поля Spec и стабилен при повторе.
- Wire-ключи `merge_rank`/`eligibility`/`inertia`/`hills` на `TerrainRegistryEntry` разбираются; canonical defaults содержат builtin-значения.
- Пометка «выполнен» в плане — только после приёмки и «ок» мастера.

## Старт

Прочитай план целиком, сверь строку 3 и статусы 0/2 с кодом (det-функции и модели Spec/Shape должны существовать — иначе стоп и доклад мастеру), покажи diff-карту (`terrainRegistryEntry.py`, `worldTerrainRegistry.py`, `uidKind.py`, модуль uid-формулы) до первой правки.
