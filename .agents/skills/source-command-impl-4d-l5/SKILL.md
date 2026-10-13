---
name: "source-command-impl-4d-l5"
description: "Имплементирует остаток шага 4d (bundle round-trip + тонкие API routes) и L-5 (общий HTTP-контракт записи библиотек) по согласованному анализу library-packs-4d-l5-analysis.md. Входы закрыты: 4c, C-1..5, L-1..L-4. Новый чат: /impl-4d-l5."
---

# source-command-impl-4d-l5

Use this skill when the user asks to run the migrated source command `impl-4d-l5`.

## Command Template

# Имплементация: 4d + L-5 — bundle round-trip и общий HTTP-контракт библиотек

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/library-packs-4d-l5-analysis.md`](../plans/library-packs-4d-l5-analysis.md) — **единственный SoT этой задачи**: фактическое состояние кода, разрывы, «Последовательность дальнейшей реализации» (пункты 1–7), «Обязательная приёмка». Не отклоняться.
2. [`.cursor/plans/library-packs-model.md`](../plans/library-packs-model.md) — §4d (включая актуализацию 2026-10-13: импорт мира по умолчанию = независимая копия с remap; обновление — через библиотеки и политику патчей; full-world update не обязателен).
3. [`.cursor/plans/library-write-policy-done.md`](../plans/library-write-policy-done.md) — §L-5 (двухэтапный обмен 409 + `policy_required` + token; source-grep обходов в приёмке).
4. [`.cursor/plans/world-bundle-archive.md`](../plans/world-bundle-archive.md) — C-1..5 done, формат архива и `library/` subtree.
5. [`docs/tz_template_library_packs.md`](../../docs/tz_template_library_packs.md) — §0.3 (write-политика), §1.1 (владение = доступность), §2 (remap), §4/§4.1/§4.2 (экспорт/архив).
6. [`docs/tz_world_bundle.md`](../../docs/tz_world_bundle.md) — контракт bundle и импорта мира.
7. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../rules/code-gates.mdc) — один шаг за заход
   - [`.cursor/rules/layer-boundaries.mdc`](../rules/layer-boundaries.mdc)
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/project-context.mdc`](../rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить без просьбы, schema только через `0001_initial.sql`
   - [`.cursor/rules/class-size-limit.mdc`](../rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Что уже есть — не переписывать

- `libraryPacks/writeService.py`, `writeFacade.py`, `writeExecutor.py`, `writeInspector.py`, `writePolicy.py`, `writePlanner.py` (+ planners/retention) — общий inspect→decide→prepare→apply протокол; batch, rollback, PolicyRequired.
- `api/libraryWrite.py` — DTO, serializer 409, error mapper; `api/errorMapping.py` подключён.
- `api/routes/libraryPacks.py` — lifecycle routes: packs CRUD (engine/world), instantiate, publish, member CRUD/copy; `decisions`/`preview_token` принимаются; `PolicyRequired` → `policy_response`.
- `api/routes/libraryArchives.py` — архивные роуты.
- `bundle/archive/libraryLayout.py` — UID-layout, typed manifests; `archiveSources.py` (`pack_to_wire`/`packs_from_wire`).
- `bundle/worldLibraries.py` — `import_libraries`/`export_libraries`, legacy flat bodies → `legacy`-пак мира.
- `worldBundleService`: `write_archive(library_packs=…)`, `read_archive` принимает библиотеки; `import_bundle(decisions, preview_token)` → `worldCopyImport`.
- `worldCopyImport.py` — uid_map remap + `library_token` continuation + PolicyRequired.
- `frontend/src/api/worldApi.js` — `importWorld` принимает `decisions`/`previewToken`.
- Тесты: `test_library_write_api.py` (12), `test_bundle_library_archive.py`, `test_bundle_archive_routes.py`, `test_world_pack_writer_reader.py`.

## Известные разрывы (закрыть в рамках последовательности)

- Нет HTTP-route для negotiated **re-instantiate** (`reinstantiateOps` на application-уровне есть; legacy confirm не экспонировать вторым протоколом).
- `resolve_bundle_source` должен сохранять library metadata (не только sections).
- structure_templates секция и исключение дублей плоских bodies при SQL export/import.
- Техзадача токена: стабильность preview/token при copy после полного rollback (UID-map подписанный контекст; источник и level в binding).
- Source-grep обходных write-путей (приёмка L-5).

## Порядок — строго по «Последовательности» анализа

Пункты 1→7; уже сделанное проверить по коду и не дублировать. Шаг = один
атомарный срез: отчёт (сделано/файлы/проверки/остаток) → ждать «ок».

**Правило мастера:** каждое сообщение после отчёта = следующий шаг, если в
нём нет фидбека по ревью. Фидбек — сначала обработать.

## Жёсткие запреты

- Отдельная library policy/confirm/remap механика внутри bundle — запрещена;
  только общий writer в caller UOW мира.
- Импорт мира никогда не пишет engine-каталог; publish — только `copy_pack`.
- Непустое отложенное `defaults` в манифесте архива и неизвестная metadata —
  отказ до записей, не silent round-trip. Fallback из manifest — отдельное ТЗ
  `tz_library_contextual_fallback.md`, **не** входит сюда.
- Нет FS-переимпорта ZIP; `WriteImportSource` не lossless — typed bundle input.
- Не трогать DAG-ноды, не менять schema вне `0001_initial.sql`, не создавать
  library-редактор UI.
- Не стартовать backend (HTTP-тесты через ASGITransport), не коммитить.

## Приёмка (из анализа §Обязательная приёмка)

- World-owned pack со structure/relief/building bodies экспортируется
  self-contained; импорт копией сохраняет содержимое/provenance с remap
  packs/members/entities/pins/refs; исходный мир неизменен.
- Engine user catalog не меняется от world import.
- Без решений / неполный batch / stale → ноль записей.
- Ошибка entity после library apply → полный rollback (общая UOW).
- Одинаковый source/scope → одинаковые policy decisions через library import
  и через world bundle.
- Прогоны: `python -m unittest discover -s tests -p "test_library_write_*.py"`,
  `tests.test_library_packs_{4b,4c,5a}`, `tests.test_bundle_library_archive`,
  `tests.test_bundle_archive_routes`, `tests.test_fixture_bundle_import`.
- Пометки «выполнен» в `library-packs-model.md` §4d и
  `library-write-policy-done.md` §L-5 — **только после** прохождения приёмки
  (пункт 7 последовательности).

## Старт

Прочитай `library-packs-4d-l5-analysis.md` целиком, сверь «Что фактически есть»
с текущим кодом (могло уехать вперёд), затем пункт 1 последовательности.
