---
name: "source-command-impl-5b-b7"
description: "Имплементирует шаг B7 плана domain-template-libraries-5b-implementation.md: schema/legacy API cleanup — колонки building_template_registry/relief_template_registry, registry POJO, accessors, ambiguous parse_body, legacy denorm, member name lookup, судьба flat bundle-секций, итоговая приёмка трека. Входы закрыты: A0–A7, B1–B6. Новый чат: /impl-5b-b7."
---

# source-command-impl-5b-b7

Use this skill when the user asks to run the migrated source command `impl-5b-b7`.

## Command Template

# Имплементация: 5b-B7 — schema/legacy API cleanup и итоговая приёмка

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/domain-template-libraries-5b-implementation.md`](../../../.cursor/plans/domain-template-libraries-5b-implementation.md) — **единственный SoT этой задачи**: §1–4 и шаг **B7** (§6). Статусы B1–B6 описывают входные контракты; B6 уже убрал pointer dual-write и перевёл export на membership — registry-колонки с этого момента только compatibility-данные для legacy input.
2. [`docs/tz_template_library_packs.md`](../../../docs/tz_template_library_packs.md) — §3/4/5 (bundle/library archive, import, usage).
3. [`docs/tz_building_generator.md`](../../../docs/tz_building_generator.md) — §5–6 в редакции A0.
4. [`docs/tz_json_validation.md`](../../../docs/tz_json_validation.md) — «Wire projection», «WorldSlice», «Runtime path».
5. [`.cursor/plans/schema-migrations-policy.md`](../../../.cursor/plans/schema-migrations-policy.md) — schema только через `0001_initial.sql` + sync `db/models/`; recreate БД, не incremental.
6. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок»
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Что уже есть — не переписывать

- Membership — единственный availability source (B1–B6). Export flat секций уже читает `members.list_for_world(owner_world_uid == world)`; `layouts_for_world` удалён.
- `libraryPacks/legacyWorldMigration.py` + compatibility parser — читают legacy registry-входы и конвертируют в pack/member rows; **остаются** отдельным модулем (единственное легальное место чтения registry-имён).
- `libraryPacks/domainAdapters/` — typed adapters; `structure.py` ещё содержит `world_refs` скан embedded layout-строк внутри `building_template_registry` — умрёт вместе с колонкой в этом шаге.
- `members.list_for_world`, `LibraryTemplateSectionHandler`/`LibrarySectionAdapter` — общие швы bundle-секций.

## Скоуп B7 — строго по плану §6

- **Schema + модель**: `db/models/world.py` (`World`) и `db/migrations/0001_initial.sql` — удалить `building_template_registry`, `relief_template_registry` **в одном изменении** с моделью.
- **Accessors**: `application/jsonValidation/worldRow.py`, `worldSlices.py`, re-exports в `jsonValidation/__init__.py` — снять registry accessors/keys.
- **Registry/entry POJO**: `BuildingTemplateRegistryEntry`, `WorldBuildingTemplateRegistry`, `ReliefTemplateRegistryEntry`, `WorldReliefTemplateRegistry` — удалить; импорты поправить во всех потребителях (compatibility parser переводится на сырой dict/свой минимальный reader, если он зависел от этих POJO).
- **Ambiguous `parse_body`**: `buildingTemplateLibraryService` — убрать `_PLOT_ONLY_FIELDS` discriminator и mixed-shape parse; остаются только typed тела.
- **Legacy denorm**: `structure_type` на `BuildingTemplateRow` (помечен legacy outline metadata) — удалить из 0001 + модели + потребителей.
- **Member name lookup**: `iReliefTemplateRepository.get_by_system_name` (transitional/deprecated) и аналоги member-level lookup по имени — удалить. Pack-level `get_by_system_name` **остаётся** (глобально уникальная pack identity).
- **Flat bundle-секции**: `relief_templates`/`building_templates` handlers в `bundle/registry.py` — решить судьбу по плану (чтение уже на membership; вопрос — нужна ли flat-секция как legacy-input совместимость старых архивов или удаляется). Если удаление меняет round-trip старых bundle — остановиться и спросить мастера.
- **Fixtures/tests**: обновить фикстуры и тесты, читающие registry-колонки; старые pointer-assertions из ранних suites, дошедшие до B7, удаляются здесь.
- **Source audit**: `rg` по backend/frontend/fixtures/scripts — registry names, mixed POJO, `by_system_name`, `list_all` с явным compatibility allowlist.
- **ТЗ и dependency graph**: обновить `docs/tz_template_library_packs.md`, `tz_world_bundle.md`, `tz_building_generator.md`, `.cursor/plans/plan-dependency-graph.md` под финальное состояние; план пометить `-done` только после всех обязательных проверок.

## Жёсткие запреты

- SQL только `0001_initial.sql` + sync dataclass-моделей (одно изменение); `0002_*.sql` запрещены.
- Registry names разрешены лишь в legacy input parser/tests/history — modern runtime не читает registries. Не оставлять silent drop: legacy вход без миграции — диагностируемая ошибка, не проглатывание.
- Compatibility parser остаётся отдельным модулем — не встраивать registry-чтение в runtime-сервисы.
- Race/perk `_ensure_registry` и их flat-секции **вне scope** — не pack-домены.
- Не трогать DAG-ноды, не стартовать backend, не коммитить. Проверки из `backend/` рабочим interpreter (перед запуском убедиться, что python/.venv работает).
- Bulk-записи — только через `app.db.bulkSql` (`executemany_rows`/`iter_batches`/`EXECUTEMANY_BATCH_SIZE`), без ad hoc циклов.

## Приёмка (из плана B7)

- `python -m unittest discover -s tests -p "test_library_packs_*.py"`;
  `python -m unittest discover -s tests -p "test_library_write_*.py"`;
  `python -m unittest tests.test_fixture_bundle_import tests.test_world_column_write tests.test_bundle_archive tests.test_bundle_library_archive tests.test_template_location_refs` — зелёные.
- Fresh schema и modern/legacy round-trip прошли; нет silent drops; modern runtime не читает registries.
- Source audit чист вне allowlist; обнаруженные node dependencies закрыты по «Gate: DAG».
- Пометка «выполнен» в плане — только после прохождения приёмки и «ок» мастера.

## Старт

Прочитай план целиком, сверь статусы B6 с текущим кодом, покажи карту удалений до первой правки: где `World`/0001 хранят registry-колонки, кто читает registry accessors и POJO, где `_PLOT_ONLY_FIELDS`, `structure_type`, `get_by_system_name`, и какие тесты/фикстуры держатся на старых полях.
