---
name: "source-command-impl-5b-b2"
description: "Имплементирует шаг B2 плана domain-template-libraries-5b-implementation.md: применение legacy world migration plan через существующий 4d writer в world import UOW. Входы закрыты: A0–A7 и B1. Новый чат: /impl-5b-b2."
---

# source-command-impl-5b-b2

Use this skill when the user asks to run the migrated source command `impl-5b-b2`.

## Command Template

# Имплементация: 5b-B2 — legacy world migration в world import UOW

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/domain-template-libraries-5b-implementation.md`](../../../.cursor/plans/domain-template-libraries-5b-implementation.md) — **единственный SoT этой задачи**: §1–4 (границы, целевая архитектура, data flow, правила исполнения) и шаг **B2** (§6). Также статусы A6/A7/B1 — они описывают входные контракты. Не отклоняться.
2. [`.cursor/plans/library-packs-model.md`](../../../.cursor/plans/library-packs-model.md) — §5b (исходная формулировка шага) и §4d (writer, который B2 переиспользует).
3. [`.cursor/plans/library-packs-5b-analysis.md`](../../../.cursor/plans/library-packs-5b-analysis.md) — анализ разрывов, основание декомпозиции B1–B7.
4. [`docs/tz_template_library_packs.md`](../../../docs/tz_template_library_packs.md) — §0.3 (write-политика/409/token), §4.1/§4.2 (bundle/archive), §5 (resolve).
5. [`docs/tz_world_bundle.md`](../../../docs/tz_world_bundle.md) — «Порядок секций», «Domain errors», «Два рода handlers».
6. [`docs/tz_json_validation.md`](../../../docs/tz_json_validation.md) — «Import path», «Normalize vs reject», «Scoped column write».
7. [`docs/tz_domain_template_libraries.md`](../../../docs/tz_domain_template_libraries.md) — доменные контракты в редакции A0 (legacy split и refs).
8. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок»
   - [`.cursor/rules/layer-boundaries.mdc`](../../../.cursor/rules/layer-boundaries.mdc)
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить, schema только через `0001_initial.sql`
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Что уже есть — не переписывать

- `libraryPacks/legacyWorldInput.py` — `extract_legacy_world_input(raw_world, body_sections)` → `LegacyWorldInput` (pointers/bodies, raw до normalize).
- `libraryPacks/legacyWorldPlan.py` — `plan_legacy_world_migration(legacy, facts)` → `LegacyWorldMigrationPlan`; pure, без SQL/instantiate/writer.
- `libraryPacks/legacyWorldContracts.py` — `LegacyWorldFacts`, `LegacyPackRoute`, `LegacyPointerDecision`, `LegacyBodyComparison`, `LegacyPackProjection`.
- `libraryPacks/legacyWorldBodies.py`, `legacyWorldProjection.py`, `legacyWorldRefs.py`; `legacyDomainContracts.py`, `legacyDomainSplit.py` (`split_legacy_domains`), `uidMap.py`, `legacyPack.py`, `bodyDiff.py` — split A6 и composed UID maps.
- `bundle/legacyTemplateBodies.py` — общий discriminator legacy bodies.
- `bundle/worldCopyImport.py` — `WorldCopyImport`, `ImportFailed`: uid_map remap + `library_token` continuation + `PolicyRequired`.
- `bundle/worldLibraries.py` — `import_libraries`/`export_libraries`.
- `libraryPacks/writeService.py`/`writeFacade.py`/`writeExecutor.py`/`writeInspector.py`/`writePolicy.py`/`writePlanner.py` — общий inspect→decide→prepare→apply протокол, batch/rollback/PolicyRequired (4d).
- `domainAdapters/{plot,building,structure,refFields}.py` + factory — typed adapters трёх доменов (A3/A4).
- Тесты: `test_library_packs_5b_migration.py` (B1, 36), `test_template_domain_split.py` (A6), `test_template_domain_archive.py`/`test_template_domain_api.py` (A7), `test_library_packs_4d.py`, `test_fixture_bundle_import.py`.

## Скоуп B2 — строго по плану §6

- Новый `legacyWorldMigration.py` — применение `LegacyWorldMigrationPlan` через существующий 4d writer **атомарно в world import UOW**.
- Wiring: `bundle/worldCopyImport.py`, `bundle/worldLibraries.py`, `worldService`/import entry points — raw extraction до normalize → facts → pure plan → общий writer в той же UOW → composed split/world-copy remap → entities → commit.
- Новый тест `tests/test_library_packs_5b_import.py`.
- **Не в B2:** snapshot loader / переключение runtime consumers (B3), selector/readers (B4), снятие registry reads (B5/B6), удаление legacy колонок (B7).

## Жёсткие запреты

- SQL hydrate **не** мигрирует скрыто: только явный import path; обычное чтение мира не пишет паки.
- `prepare_import` остаётся pure — никакого SQL I/O; fixture/world-row path идёт через application pipeline.
- Modern input проходит существующий 4d путь без изменений; второй confirm/второй writer — запрещены.
- Нет скрытых commit внутри library apply: одна caller UOW, token continuation по общему контракту.
- Не трогать DAG-ноды, не менять schema вне `0001_initial.sql`, не стартовать backend (HTTP-тесты через ASGITransport), не коммитить.
- Проверки из `backend/` рабочим interpreter; перед первым запуском убедиться, что `.venv`/python работает (ранее launcher сообщал ошибку пути — среду не чинить «заодно»).

## Приёмка (из плана B2)

- `python -m unittest tests.test_library_packs_5b_import tests.test_library_packs_4d tests.test_fixture_bundle_import` — зелёные.
- Preview/stale/entity error → полный rollback, ноль записей; исходники immutable; повторный импорт без duplicates.
- Imported мир не зависит от legacy registry для восстановления graph.
- Пометка «выполнен» в плане — только после прохождения приёмки и «ок» мастера.

## Старт

Прочитай план целиком, сверь статусы B1/A7 с текущим кодом (могло уехать вперёд), затем вызови `extract_legacy_world_input`/`plan_legacy_world_migration` на реальном bundle fixture и покажи точку врезки в `worldCopyImport` до первой правки.
