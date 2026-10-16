---
name: "source-command-impl-5b-b3"
description: "Имплементирует шаг B3 плана domain-template-libraries-5b-implementation-done.md: WorldTemplateSnapshot loader и переключение packing/district planner с name-based на member UID identity. Входы закрыты: A0–A7, B1–B2. Новый чат: /impl-5b-b3."
---

# source-command-impl-5b-b3

Use this skill when the user asks to run the migrated source command `impl-5b-b3`.

## Command Template

# Имплементация: 5b-B3 — world template snapshot и packing identity по UID

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/domain-template-libraries-5b-implementation-done.md`](../../../.cursor/plans/domain-template-libraries-5b-implementation-done.md) — **единственный SoT**: §1–4 (границы, целевая архитектура, data flow, правила) и шаг **B3** (§6). Статусы A1/A5/B1/B2 описывают входные контракты. Не отклоняться.
2. [`.cursor/plans/library-packs-model-done.md`](../../../.cursor/plans/library-packs-model-done.md) — §5b (pointer-миграция/pins) и §5a (effective catalog, который B3 потребляет).
3. [`docs/tz_template_library_packs.md`](../../../docs/tz_template_library_packs.md) — §1/1.1 (availability = membership, pins ≠ фильтр), §3, §5 (resolve).
4. [`docs/tz_domain_template_libraries.md`](../../../docs/tz_domain_template_libraries.md) — §1 (композиция), §5 (runtime refs), §6 (selectors/legacy).
5. [`docs/tz_city_generation.md`](../../../docs/tz_city_generation.md) — §3, §9.2/9.4 (selectors, required plots).
6. [`docs/tz_structure_connections.md`](../../../docs/tz_structure_connections.md) — §5.1.3: «Число токенов», «Приоритет посадки», «Два прохода посадки».
7. [`docs/tz_json_validation.md`](../../../docs/tz_json_validation.md) — «Runtime path».
8. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок»
   - [`.cursor/rules/layer-boundaries.mdc`](../../../.cursor/rules/layer-boundaries.mdc) — генераторы только materialize, sync; async I/O на границе
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить, schema только через `0001_initial.sql`
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Что уже есть — не переписывать

- `effectiveCatalog.py` + `membership.py` (5a): scoped membership (owned ∪ defaults), `member/available/candidates` с детерминированным sort by `template_uid`; `EffectiveCatalogLoader` из публичных `PackCatalogRepos` + adapters.
- `refResolve.py` — `TemplateRef`/`resolve()`, один `FieldPathError` на событие, `resolve_fallback` hook в адаптерах.
- Typed контракты A1: `TemplateEntry`, `WorldTemplateSnapshot`, `ReliefTemplateSnapshot` с read-only UID indexes.
- `domainAdapters/{plot,building,structure}.py` + factory (A3/A4), canonical default-паки (A5), legacy migration в import UOW (B1/B2).
- `container.effective_catalog_loader()` / `container.ref_resolver()`.

## Текущая name-based цепочка (что переключается)

- `buildingDefaults.assemble_structure_catalog` — FS stdlib (`load_structure_stdlib`) ⊕ SQL rows; `assemble_building_catalog` — canonical_defaults ⊕ library_layouts ⊕ **`world_building_layout_overrides(world)`** (чтение удаляемого реестра).
- `buildingCache.BuildingLayoutCache` — ключи `(system_name, facing)`; `collect_building_template_names` → `set[str]`.
- `tokens.py` — `pick_layout_names` → `system_name`; `PackingToken(system_name=name, uid=f"{name}#{i}")`; `resolve_plot_count/priority(name, plot_counts/plot_priority)`; `resolve_required_layouts(req, catalog)` по `req.plot_template`-имени; `seen_names` dedup по имени.

## Скоуп B3 — строго по плану §6

- Новый `templateSnapshotLoader.py`: async `load(world, ctx) → WorldTemplateSnapshot` на границе; sync-генераторы получают immutable snapshot.
- `BuildingCatalog`/target catalogs питаются из snapshot/effective catalog — **не** FS stdlib, **не** world registry; `StructureCatalog` без `list_all`/прямого FS source.
- Identity = member UID: token/cache/placement/recipe keys (`plot_counts`/`plot_priority`/`req.plot_template`) — UID; одноимённые plots не сливаются.
- Pins — не фильтр доступа; чужой owner невидим; ни один consumer не восстанавливает identity по имени (legacy names — только converter A6).
- N/priority порядок итерации сохранён; ожидаемый дифф registry-order → sort by `template_uid` документировать, не считается регрессией.
- Файлы из плана: `templateSnapshotLoader.py`, BuildingCatalog/target catalogs, `settlementOutdoorPackingJob`, `buildingCache`/`buildingDefaults`, district planner `tokens`/`areaSlots`/`requiredStructureResolve` + typed token/slot DTO, `RequiredStructure`/`DistrictTemplateEntry`/`SettlementPayload`/`structurePlacement`.

**Не в B3:** `system_structure_template_uid` и persist-refs (B4); relief reader/pick (B5); удаление pointer dual-write (B6); удаление registry колонок/schema cleanup (B7); DAG-ноды.

## Жёсткие запреты

- Генераторы sync — async I/O только в loader на границе; persist — не в генераторе.
- Нет global `list_all` по всем членам, нет FS-fallback в каталоге, нет name→uid угадывания.
- `resolve_required_layouts`/pick errors остаются доменными; одна library diagnostic на границе resolve (ТЗ §7).
- Не менять `0001_initial.sql` (B3 — без schema), не трогать DAG, не стартовать backend, не коммитить.
- Проверки из `backend/` рабочим interpreter.

## Приёмка (из плана B3)

- `python -m unittest tests.test_library_packs_5b_snapshot` (новый обязательный suite) +
  `tests.test_required_structure_position tests.test_building_assembler tests.test_settlement_topology`.
- Одноимённые plots различимы по UID; pins не режут кандидатов; чужой owner не виден;
  ни один packing consumer не восстанавливает identity по имени (source-grep).
- Пометка «выполнен» в плане — только после прогонов и «ок» мастера.

## Старт

Прочитай план целиком + статусы A1/A5/B2 по коду (могли уехать вперёд). Покажи точку врезки loader'а (кто вызывает assemble_building_catalog сегодня) и mapping `system_name`→`template_uid` по одному consumer до первой правки.
