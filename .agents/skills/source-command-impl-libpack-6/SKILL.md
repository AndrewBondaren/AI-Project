---
name: "source-command-impl-libpack-6"
description: "Имплементирует шаг 6 плана library-packs-model.md: global-scope attach structure_templates через CanonicalLibrarySpec (A5 уже сдан), удаление runtime FS-fallback, фикс resolve domain root. Входы закрыты: A0–A7, B1–B7 (5b), A-2. Новый чат: /impl-libpack-6."
---

# source-command-impl-libpack-6

Use this skill when the user asks to run the migrated source command `impl-libpack-6`.

## Command Template

# Имплементация: шаг 6 — global-scope structure templates

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/library-packs-model.md`](../../../.cursor/plans/library-packs-model.md) — **единственный SoT этой задачи**: шаг **6** (§964). Внимание: абзац про POJO-only plots/default selector — исторический контракт 2026-10-09, **заменён уточнением A0** (canonical spec/attach перенесён в A5 плана 5b; специальный builtin/default selector не вводится).
2. [`.cursor/plans/domain-template-libraries-5b-implementation.md`](../../../.cursor/plans/domain-template-libraries-5b-implementation.md) — статусы A0–A7 и B1–B7 описывают входные контракты: membership — единственный availability source, canonical attach-механизм (A5) уже реализован, реестры-указатели сняты.
3. [`docs/tz_template_library_packs.md`](../../../docs/tz_template_library_packs.md) — pack-модель, canonical spec, attach-политика.
4. [`docs/tz_building_generator.md`](../../../docs/tz_building_generator.md) — §5.1 «Глобальная библиотека», §6.1 «Загрузка» в редакции A0.
5. [`docs/tz_json_validation.md`](../../../docs/tz_json_validation.md) — «Wire projection → WorldSlice» (engine, scope global).
6. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок»
   - [`.cursor/rules/template-pack-layout.mdc`](../../../.cursor/rules/template-pack-layout.mdc) — domain root, имя папки = pack_name, stem = system_name, lone files запрещены
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Что уже есть — не переписывать

- **Canonical attach (A5) реализован**: `CanonicalLibrarySpec`-механизм, atomic fill-missing в SQL с сохранением существующего тела и `source_file`, `ensure_canonical` на чтениях. Задача шага — **декларация spec для structures**, не новый движок.
- Membership — единственный availability source; effective catalog (5a) и `WorldTemplateSnapshot`-loader (B3/B5) на месте.
- `system_structure_template_uid` на `named_locations` (B4) — persist реального member UID работает.
- Стандартные plot/building templates — default members по A0; выбор — обычный UID, POJO задаёт defaults параметров.

## Скоуп шага 6 — строго по плану

- **Spec-декларация** для `StructureTemplateLibraryService`: id = `template_uid` (stem-файл = system_name по template-pack-layout), canonical source = FS domain root `structures_templates/` + canonical-пак `base`, attach на всех публичных чтениях, политика = atomic fill-missing (существующее тело и `source_file` не перетирать).
- **Удалить прямой runtime FS-fallback** из runtime-каталога structures.
- **Фикс resolve domain root**: env `STRUCTURES_TEMPLATES_ROOT` → repo-relative fallback, без `Path.cwd()`.
- **Файлы** (ориентир из плана): `structureTemplateLibraryService.py`, `structureTemplateFsImport.py`, декларация spec, repository/interface для atomic fill-missing, `planner/buildingDefaults.py`, callers/tests typed catalog, wiring адаптеров по необходимости.
- **Junction** `backend/structures_templates`, если существует — удалить после проверки типа/target (отсутствие допустимо).

## Жёсткие запреты

- Не вводить специальный builtin/default selector для structure — выбор только UID + POJO-defaults параметров (A0).
- Не автоимпортировать пак вне defaults, объявленных в spec; пользовательские записи не получают canonical-статус.
- Пак мира A недоступен миру B без явного инстанцирования; никакого обхода через общий SQL `list_all`.
- Generation-чтение — через эффективный каталог мира; прямой `find_by_uid`/`list_all` в generation-пути = запрещённый global bypass.
- SQL только `0001_initial.sql` + sync `db/models/` в одном изменении.
- Не трогать DAG-ноды, не стартовать backend (HTTP-smoke поднимает мастер), не коммитить.
- Bulk-записи — только `app.db.bulkSql`.

## Приёмка (из плана шага 6)

- Свежая БД → `generate-settlement?district_uid=…` для `world-test-002` проходит без ручного импорта; повтор идемпотентен (HTTP-smoke запускает мастер — агент готовит код и команду).
- User-override на canonical UID и его `source_file` не перетираются.
- Каталог строится из SQL после attach: defaults + явно инстанцированный пользовательский контент; прямой FS-fallback удалён; чтение не зависит от cwd (cwd=repo/backend + env-root).
- Замыкание building → structure refs; неразрешимый явный UID/неинстанцированная зависимость → default + warning, сохранённая ссылка не меняется.
- Юнит-проверки из `backend/` рабочим interpreter: релевантные `test_library_packs_*`, `test_template_location_refs`, structure/building suites.

Пометка «выполнен» в плане — только после приёмки и «ок» мастера; план получает суффикс `-done`, граф обновляется.

## Старт

Прочитай шаг 6 и уточнение A0, сверь с текущим кодом: где `StructureTemplateLibraryService` читает FS напрямую, как объявлены существующие `CanonicalLibrarySpec` (A5 — образец), кто держит `Path.cwd()` в resolve domain root, какие callers/tests зависят от FS-fallback. Покажи карту изменений до первой правки.
