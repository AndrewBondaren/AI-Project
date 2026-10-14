---
name: "source-command-impl-5b-b4"
description: "Имплементирует шаг B4 плана domain-template-libraries-5b-implementation.md: building materialize и persist template refs — system_template_uid реального member + новое system_structure_template_uid (SQL/DTO/remap/usage). Входы закрыты: A0–A7, B1–B3. Новый чат: /impl-5b-b4."
---

# source-command-impl-5b-b4

Use this skill when the user asks to run the migrated source command `impl-5b-b4`.

## Command Template

# Имплементация: 5b-B4 — building materialize и persist template refs

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/domain-template-libraries-5b-implementation.md`](../../../.cursor/plans/domain-template-libraries-5b-implementation.md) — **единственный SoT этой задачи**: §1–4 и шаг **B4** (§6), включая §2.4 (persist refs: `system_template_uid` = UID реально применённого шаблона; `system_structure_template_uid` = UID фактически применённой structure, identity не снимок). Статусы B1–B3 описывают входные контракты.
2. [`docs/tz_building_generator.md`](../../../docs/tz_building_generator.md) — §3.1 (plot wire), §7 (BuildingLayout result/template refs), §11.1/§11.6 (building context).
3. [`docs/tz_city_generation.md`](../../../docs/tz_city_generation.md) — §11.3 (materialize), §11.5 (persist).
4. [`docs/project_data_storage_tz.md`](../../../docs/project_data_storage_tz.md) — «named_locations», «DET-1» (детерминированные uid).
5. [`docs/tz_cascade_context.md`](../../../docs/tz_cascade_context.md) — §2/§4 (source-POJO, inheritance), §8.4.
6. [`docs/tz_json_validation.md`](../../../docs/tz_json_validation.md) — «Bundle row DTO», «Runtime path».
7. [`.cursor/plans/schema-migrations-policy.md`](../../../.cursor/plans/schema-migrations-policy.md) — schema только через `0001_initial.sql` + sync `db/models/`.
8. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок»
   - [`.cursor/rules/layer-boundaries.mdc`](../../../.cursor/rules/layer-boundaries.mdc) — generators materialize, persist — в сервисах
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc) — default-параметры не дублировать в generators
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Что уже есть — не переписывать

- `application/worldData/templateSnapshotLoader.py` — load → `WorldTemplateSnapshot`, UID-indexed candidates (B3).
- Packing/placement на catalog `template_uid`: district planner (tokens/areaSlots/types, layoutPicks/subjects), `settlementAssembler` buildingCache/buildingDefaults, `settlementOutdoorPackingJob` (B3).
- `libraryPacks/legacyWorldMigration.py` + `worldCopyImport`/`worldLibraries` — legacy migration в world import UOW (B2).
- `libraryPacks/domainAdapters/{plot,building,structure,refFields,remapRefs}.py` — typed adapters, декларации refs для usage/remap (A3/A4); общий writer в caller UOW (A4/4d).
- `db/models/namedLocation.py` — уже есть `system_template_uid: str | None`; `dataModel/locations/namedLocation/bundleNamedLocation.py` — bundle DTO; `bundle/reliefSection.py` использует поле; `namedLocationService.py`, `iNamedLocationRepository`/`namedLocationRepository` — persist/remap.
- `structureAreaAssembler.py` уже читает `system_template_uid` — место врезки identity/materialize.

## Скоуп B4 — строго по плану §6

- Провести разрешённый graph (snapshot UID → materialize) до сохранения локаций: `areaAssembler`/`structureAreaAssembler` и context helpers получают **identity отдельно от читаемого имени тела**.
- `system_template_uid` = UID реально выбранного member; проверки PK uniqueness, kind/owner/body, world availability; одинаковые имена не влияют на разрешение.
- **Новое поле `system_structure_template_uid`**: `db/models/namedLocation.py` + `0001_initial.sql` + `bundleNamedLocation` DTO **в одном изменении**; import/export/world copy и ref usage поддерживают обе ссылки. UID фактически применённой при генерации structure; повторная генерация обновляет, обычное чтение не пересчитывает; `None` — для локаций без structure и невосстановимых legacy.
- Context: подготовленные building параметры, `None` сохраняет cascade-наследование; plot без building не создаёт NL; central det-id — принятая identity.
- Новый тест `tests/test_template_location_refs.py`.
- **Не в B4:** relief pick cutover (B5), удаление pointer dual-write (B6), registry columns cleanup (B7).

## Жёсткие запреты

- SQL только `0001_initial.sql` + sync dataclass-модели (одно изменение); `0002_*.sql` запрещены.
- `system_structure_template_uid` **не** пересчитывать из текущей редакции building template при обычном чтении — identity применённого шаблона, не версия тела.
- Legacy ref восстанавливать только по явному однозначному mapping — без угадывания по имени.
- Default-параметры — из POJO, не литералами в generators (`dataModel-no-hardcode`).
- Прочие location types сохраняют семантику своих ссылок — без blanket-правил.
- Не трогать DAG-ноды, не стартовать backend, не коммитить. Проверки из `backend/` рабочим interpreter (перед запуском убедиться, что python/.venv работает).

## Приёмка (из плана B4)

- `python -m unittest tests.test_template_location_refs tests.test_structure_area_assembler tests.test_structure_orientation tests.test_bundle_named_location_wire tests.test_bundle_remap tests.test_cascade_context_baseline` — зелёные.
- Persist и round-trip содержат реальные member UID, не имена; две одноимённые копии различимы; wrong-kind/unknown UID не обходятся.
- Применённый structure UID переживает смену structure ref исходного building template, export/import и remap; usage видит ссылку созданного здания.
- Пометка «выполнен» в плане — только после прохождения приёмки и «ок» мастера.

## Старт

Прочитай план целиком, сверь статусы B3 с текущим кодом, покажи точки врезки: где `structureAreaAssembler` получает building identity и где `namedLocationService`/bundle DTO пишут `system_template_uid` — до первой правки.
