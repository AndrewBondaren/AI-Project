# World bundle archive — zip-конверт экспорта/импорта ✅ DONE

> Карта межплановых зависимостей и критический путь:
> [`plan-dependency-graph.md`](plan-dependency-graph.md).

Транспортный формат экспорта мира и library-паков: один zip-архив с
файловой структурой, читаемой мастером/игроком стандартным архиватором
(решение 2026-10-09: прозрачность важнее единого контейнерного стека —
custom pack-формат отклонён, архив не читается в runtime). Архив —
конверт над существующей моделью секций bundle (`WorldBundleService`,
handlers, `dict {key: payload}`), не замена SQL/World Pack-хранилища.

**Первичен к `library-packs-model-done.md`:** интерфейс — схема манифеста пака
(ТЗ §4) и FS-layout (`template-pack-layout.mdc`), оба уже зафиксированы;
SQL-семантика паков архиву не нужна. Шаг 4d library-плана использует
этот конверт.

## Целевые контракты

- **Контейнер:** zip (`zipfile` stdlib, ZIP64). Расширение `.wpack`.
  JSON-секции — DEFLATED; `*.zst` и уже-сжатые блобы — STORED (двойной
  компрессии нет). Детерминированный порядок entries, без переменных
  ZIP metadata — воспроизводимый хеш при одинаковых payloads и manifest.
  `exported_at` задаёт вызывающий слой один раз на операцию; новый экспорт
  с другим временем может иметь другой хеш (§4.2).
- **Строгость входа:** неизвестные файлы в архиве — reject (тот же
  принцип, что lone files в `template-pack-layout`); битый zip,
  отсутствующий/невалидный manifest — reject до разбора секций.
- **Структура:**

```text
{name}.wpack
  bundle.manifest.json        # метаданные упаковки — не доменные данные
  skeleton/
    world.json                # world row + реестры + pin-набор
    states.json
    locations.json
    connection_nodes.json
    connection_edges.json
    {section_key}.json        # transitional: плоские body-секции
                              # (relief/building/race/perk — все 9 ключей
                              # BundleSection.SKELETON уже реализованы)
                              # до переезда world-owned тел в library/
                              # (шаг 5 + library-план 4b); pack-owned
                              # тела плоскими секциями не дублируются
  library/                    # библиотеки мира — self-contained
    {domain_root}/
      {pack_uid}/
        pack.manifest.json    # members {local_uid→template_uid}, deps,
                              # provenance — схема ТЗ §4
        {template_uid}.json  # тела по UID, имена — metadata
  pack/                       # запечённый World Pack, только уровень full:
                              # verbatim зеркало pack_root; layout SoT —
                              # pack/io/worldPackPaths.py, имена здесь не
                              # перечисляются (не второй источник истины);
                              # debug `*.grade_rays.json` не входят
```

- **`bundle.manifest.json`:** `kind` (`"world"` / `"library_pack"`),
  `format_version: 1`, `source`, `sections` — индекс `section key → path`. Доменные
  настройки живут в секционных файлах (`skeleton/world.json`), манифест
  их не дублирует — иначе два источника истины.
- **`source` — владелец-источник для импорта:** `{kind:"world",
  world_uid, world_name, exporter, exported_at, content_hash?}`.
  `source.world_uid` — исходный владелец для проверки и remap default copy
  (ТЗ §4.1, уточнение 2026-10-13). `content_hash` — optional, дедупликация и
  диагностика «тот же мир» vs «чужой мир с совпавшим uid».
  Per-pack provenance (`source_pack_uid`/`source_template_uid`) — в
  `pack.manifest.json`, не в корневом.
  `source.kind` совпадает с `kind`, `source.world_uid` — с world row до
  remap. Для library-пака source содержит `pack_uid` вместо world-полей.
  Optional `source.content_hash` в v1 не формируется writer и не участвует
  в выборе режима импорта. Подробные проверки — ТЗ §4.2 (SoT).
- **Уровни экспорта:** `registry` → manifest + `skeleton/world.json`;
  `skeleton` → + все `skeleton/*` + `library/`; `full` → + `pack/`.
  `full` на мире без запечённого pack — явная ошибка уровня, не пустой
  subtree.
- **Секция ↔ path — явная таблица** в `dataModel/worldBundle/`, не вывод
  из имени файла. Архивные member paths строятся по UID; stem ==
  system_name остаётся правилом только авторского FS-входа.
- **Codec на границе:** экспорт — `handler.export_section()` payload →
  файл `skeleton/{key}.json`; импорт — файлы → тот же `dict`
  `{section_key: payload}` → существующий `import_bundle`. Handlers и
  `WorldBundleService` не меняются.
- **Единый конверт:** экспорт engine library-пака — тот же контейнер,
  `kind:"library_pack"`, обязательный `bundle.manifest.json`, пустой
  `sections`; корень = `{domain_root}/{pack_uid}/` (`pack.manifest.json` +
  member-файлы), без `library/`, `skeleton/`, `pack/`.
  Один архив = один логический пак, возможно с несколькими domain roots.
  World archive несёт **только world-owned** manifests —
  импорт мира никогда не пишет глобальный каталог движка (ТЗ §4.1,
  решение 2026-10-09).
- **Legacy:** flat-JSON bundle остаётся входом (transitional read,
  миграция старых refs — карта шага 3 library-плана); запись — только
  архив. Inline JSON-preview по `download=false` остаётся представлением
  sections dict — это не транспортный формат.

### UID-политика при импорте (carry / attach / mint)

Три операции над идентичностью, не смешивать: **carry** — uid тянется из
источника без изменений (повторный импорт того же объекта = тот же uid);
**attach** — uid перевычисляется по центральной формуле при смене
владельца (ТЗ §2: новый владелец ⇒ новая идентичность, `source_*`
фиксирует исходные uid); **mint** — новый uid по uid_map ремапа мира
(режим `copy` §4.1 / текущий auto-remap при коллизии). SoT — ТЗ §4.2
«UID при импорте архива»; здесь только механика по шагам:

- Entity-секции и `world_uid` — существующий `remap_bundle`/uid_map,
  без изменений.
- World-owned паки/члены (шаг 5): при copy — attach: новый `pack_uid`
  по формуле владельца-мира, member `template_uid` перевычисляются от
  нового пака, `source_pack_uid`/`source_template_uid` = исходные.
- `pack/` blobs (шаг 6): uid-поля `manifest.json`/`locations_index.json`
  и имена `locations/l.{uid}.*` переписываются по тому же uid_map слоем
  импорта поверх распаковки — codec байты не переписывает. Тела блобов
  неизменны — хеши тел валидны; manifest пересобирается, `content_hash`
  пересчитывается. `terrain_pack_path` сбрасывается на pack_root
  импортированного мира.
- `kind:"library_pack"` — только carry: pack/member uid из архива
  записываются в engine-каталог как есть (повторный импорт = update);
  attach/mint — это `instantiate_pack`/`copy_pack` (ТЗ §2), не разбор
  архива.

## Порядок имплементации (2026-10-09)

```text
1 → 2 → 3 → 4 → ┬→ 5 ──┐
                └→ 6   ┴→ (pack-план 4d использует шаги 1–5)
```

- **1 → 2 → 3 → 4** — строго последовательно: ТЗ → модель манифеста →
  codec → routes; каждый следующий опирается на артефакт предыдущего.
- **5 ∥ 6** — оба зависят от codec/layout-таблицы (шаги 2–3), не друг от
  друга: `library/` subtree — размещение манифестов/тел паков по
  FS-layout; `pack/` subtree — verbatim World Pack уровня `full`.
- **Шаг 5 не требует SQL-модели паков** — интерфейс: схема манифеста
  (ТЗ §4) и FS-layout, оба зафиксированы; round-trip проверяется на
  синтетических manifest-фикстурах без pack-каталога.
- **Межплановая зависимость:** шаг 4d `library-packs-model-done.md`
  использует шаги 1–5 этого плана (конверт + `library/` subtree);
  шаг 6 вне критического пути pack-модели и может идти позже.
- Default copy мира и общий library negotiation — application-интеграция
  pack-плана 4d по ТЗ §4.1. Обязательный выбор update/copy снят 2026-10-13;
  обновления существующего мира идут через библиотеки/политику патчей.

## Шаги

### Шаг 1 — ТЗ: раздел формата архива ✅ DONE (2026-10-11)

- **Статус:** сверка выполнена, уточнения §4.2 согласованы мастером
  2026-10-11. C-1 закрыт; C-2 разблокирован.
  Код шагов C-2/C-3 этим изменением не добавляется.
- **Цель:** зафиксировать контракт контейнера до кода.
- **ТЗ:** §4.2 «Формат архива» в `docs/tz_template_library_packs.md`
  **уже написан** (2026-10-09), ссылка из `docs/tz_world_bundle.md`
  § «Целевое расширение» стоит — шаг сводится к финальной сверке и
  согласованию; правки ревью (verbatim pack_root, transitional
  body-файлы, UID-политика) уже внесены.
- **Файлы:** `docs/tz_template_library_packs.md`, `docs/tz_world_bundle.md`.
- **Контракт:** тексты «Целевые контракты» выше.
- **Проверка:** сверка с `template-pack-layout.mdc` и §4 — нет
  дублирования доменных данных в манифесте.
- **Результат сверки:** девять текущих `BundleSection.SKELETON` учтены;
  определены первая версия/индекс, source обоих видов архива, условия
  воспроизводимости и reject некорректных путей. В `tz_world_bundle.md`
  убраны устаревшие bindings, перенос следует world-owned модели §4.
  Copy мира использует общую карту переносимых паков/членов, включая
  межпаковые refs; одиночный `copy_pack` сохраняет свой прежний scope.
  Verbatim zst при copy остаётся проверкой C-6, а не гарантией C-1.
- **Done:** раздел согласован мастером 2026-10-11 (явное подтверждение
  внесённых уточнений в чате).

### Шаг 2 — Модель манифеста и layout-таблица ✅ DONE (2026-10-11)

- **Статус:** реализован `BundleManifest` с различимыми source-моделями
  world/library_pack, wire-политиками и проверками версии, UTC timestamp,
  совпадения kind и секционного индекса. `SECTION_PATHS` / `PATH_SECTIONS`
  неизменяемы, покрывают все девять текущих skeleton-секций.
  `BundleArchiveLayout` фиксирует manifest и отдельные subtree prefixes;
  файлы поддеревьев разрешаются только codec шагов C-5/C-6.
- **Уточнение C-2 по запросу мастера:** wire-значения видов архива
  определены единственным `BundleKind` (StrEnum); root kind, source
  discriminators и проверки используют enum. JSON-значения сохранены.
- **Цель:** typed-контракт манифеста и отображения секция ↔ path.
- **ТЗ:** §4.2.
- **Файлы:** `backend/app/dataModel/worldBundle/bundleManifest.py`
  (новый), `bundleSections.py` (таблица путей).
- **Контракт:** `BundleManifest` POJO (`kind`, `format_version`,
  `source`, `sections` index); `SECTION_PATHS` и обратное отображение;
  unknown path → reject.
- **Проверка:** `python -m unittest tests.test_bundle_manifest` —
  round-trip serialize/deserialize, покрытие всех ключей
  `BundleSection.SKELETON`.
- **Результат:** 13 тестов нового контракта; вместе с
  `test_bundle_remap`, `test_bundle_named_location_wire`,
  `test_pack_import_levels`, `test_fixture_bundle_import` — 26 тестов,
  все зелёные. `git diff --check` без ошибок. C-3 разблокирован.
- **Done:** модель покрывает секции + `library/` + `pack/` subtree keys.

### Шаг 3 — Archive codec ✅ DONE (2026-10-11)

- **Статус:** reader/writer изолированы в `bundle/archive/`; общие
  transport-проверки — `validation.py`, результат — `contents.py`.
  Writer сериализует JSON детерминированно, фиксирует ZIP metadata,
  DEFLATED для JSON / STORED для бинарных blobs, публикует файл атомарно.
  Reader проверяет manifest и точный состав файлов до section JSON;
  reject на дубликаты entries/JSON keys, небезопасные пути, symlinks,
  неизвестные файлы/папки, повреждения ZIP/CRC и source/world UID mismatch.
- **Цель:** reader/writer архива на границе, handlers не трогаем.
- **ТЗ:** §4.2.
- **Файлы:** `backend/app/application/worldData/bundle/archive/` —
  `writer.py`, `reader.py`, `errors.py`, `validation.py`, `contents.py`,
  `__init__.py`; `backend/tests/test_bundle_archive.py`.
- **Уточнение C-3:** исходная пара результата reader теряла `pack_blobs`.
  Reader возвращает `ArchiveContents(manifest, sections, blobs)`; codec
  принимает точный trusted allowlist blob-путей от layout-слоя C-5/C-6,
  без него неизвестные subtree-файлы отвергаются. Payloads остаются
  отдельным sections dict для существующего import pipeline.
- **Контракт:** `write_archive(sections: dict, manifest, pack_blobs, *, path) →
  path`; `read_archive(path, *, blob_paths=()) → ArchiveContents`; STORED для
  `*.zst`, DEFLATED для JSON; детерминированный порядок entries.
- **Проверка:** unittest round-trip `dict → zip → dict` идентичен;
  reject на неизвестные файлы / битый zip / отсутствующий manifest.
- **Результат:** `python -m unittest tests.test_bundle_archive
  tests.test_bundle_manifest tests.test_bundle_remap
  tests.test_bundle_named_location_wire tests.test_pack_import_levels
  tests.test_fixture_bundle_import` — 52 теста зелёные (26 новых codec-тестов).
  Проверены побайтовая воспроизводимость, raw blob round-trip с явным
  allowlist, Windows path normalization и сохранность предыдущего файла
  при ошибке записи. `git diff --check` без ошибок. C-4 разблокирован;
  доменные layout-политики subtree остаются C-5/C-6.
- **Done:** codec изолирован — не знает про SQL, repos, handlers.

### Шаг 4 — Routes: экспорт/импорт `.wpack` + legacy вход ✅ DONE (2026-10-12)

- **Статус:** HTTP download отдаёт `.wpack` через FileResponse;
  inline JSON-preview сохранён. `bundleSource.py` одинаково определяет
  формат file/path до JsonResolver; upload перематывается после сигнатуры.
  Manifest и codec подключены через тонкие методы WorldBundleService.
  Ошибки входного архива и чужой kind возвращают 422 до import pipeline;
  временные файлы очищаются после download и при ошибках подготовки/чтения.
- **Проверено:** 59 тестов archive routes/codec/manifest/remap/wire/levels/
  fixture import прошли; затем 18 тестов archive routes + validation policy
  прошли с усиленным HTTP round-trip на непустом `world_test` (states,
  locations, race/perk bodies). Всего 70 разных тестов в двух наборах.
  Pyright на трёх изменённых production-модулях: 0 errors/warnings;
  `git diff --check` без ошибок. Backend-сервер не запускался.
- **Цель:** HTTP-граница принимает и отдаёт архив.
- **ТЗ:** §4.2; `tz_world_bundle.md` (facade unchanged).
- **Файлы:** `api/routes/worlds.py`, `worldBundleService.py` (тонкая
  точка входа codec → dict).
- **Контракт:** export → `.wpack` download; import принимает `.wpack` и
  legacy flat JSON — различение по сигнатуре `PK\x03\x04` **до**
  `JsonResolver` (он парсит только JSON и отдаёт 422 на бинарнике), для
  `file` и `path` входов одинаково; дальше — существующий pipeline;
  `ImportValidationReport` без изменений.
- **Проверка:** smoke export → import (skeleton) round-trip;
  legacy-файл импортируется; существующие тесты bundle зелёные.
- **Done:** оба формата входа работают через один pipeline.

#### Утверждённые уточнения C-4 — 2026-10-12

- **Экспорт:** `download=false` сохраняет inline JSON-preview sections dict;
  `download=true` возвращает бинарный `.wpack` с attachment filename и
  соответствующим Content-Type. JSON helper для download архива не используется.
  Временный файл удаляется после отправки ответа; при ошибке подготовки —
  сразу. Upload-временные файлы очищаются и при успешном импорте, и при ошибке.
- **Вход:** одинаковое определение формата по `PK\x03\x04` для `file` и
  `path` до `JsonResolver`. После чтения сигнатуры upload перематывается
  перед дальнейшим чтением, в том числе legacy JSON. Сохраняются ошибки
  выбора источника: оба/ни одного — 400, отсутствующий path — 404,
  path не является файлом — 400.
- **Ошибки:** чтение codec находится внутри обработки
  `BundleValidationError` → HTTP 422. World-import явно отвергает
  `kind=library_pack` до вызова доменного import pipeline.
- **Слои:** API отвечает за HTTP, источник входа и жизненный цикл
  временных файлов; application — за manifest и вызовы codec.
  `source.exported_at` задаётся один раз на операцию экспорта в UTC;
  `source` строится из экспортируемого world payload, индекс — по
  `SECTION_PATHS`. Оба формата сходятся в существующий `import_bundle`;
  handlers, transaction/remap и `ImportValidationReport` сохраняются.
- **Scope:** C-4 поддерживает `registry`/`skeleton` с текущими плоскими
  секциями. `library/` — C-5; `full`/`pack/` — C-6; default copy и общий
  библиотечный negotiation — library-план 4d. Текущий C-4 делает auto-remap
  только при коллизии; 4d подключает default copy операции целого мира
  и перенос библиотек. C-4 не объявляет целевой импорт §4.1 завершённым.
  Allowlist subtree не выводится из недоверенного списка entries архива.
- **Файлы проверки:** новый `backend/tests/test_bundle_archive_routes.py`;
  при необходимости тонкий API helper источника/ответа рядом с routes.
- **Приёмка:** HTTP-тесты без запуска backend: оба формата × оба источника,
  registry/skeleton export, бинарный download и JSON-preview,
  skeleton export → import round-trip, `validate_only` без записи,
  malformed archive и чужой kind → 422, ошибки выбора источника/path,
  очистка временных файлов после ответа и при сбоях.
  Команда: `python -m unittest tests.test_bundle_archive_routes
  tests.test_bundle_archive tests.test_bundle_manifest tests.test_bundle_remap
  tests.test_bundle_named_location_wire tests.test_pack_import_levels
  tests.test_fixture_bundle_import`; затем `git diff --check`.
- **База перед исполнением:** 52 существующих bundle-теста прошли
  2026-10-12. Эти проверки подтверждают C-2/C-3 и прежний pipeline;
  HTTP-приёмка C-4 выполняется после реализации.

### Шаг 5 — `library/` subtree ✅ DONE (2026-10-12)

- **Статус:** typed archive manifest/member/pack DTO и mapping по LibraryKind
  добавлены; reader/writer поддерживают UID-layout world и standalone
  library archives. Точный inventory проверяется до section/body JSON;
  multi-domain manifests согласованы, metadata и body refs сохраняются.
  HTTP guard отклоняет libraries до доменного wiring 4d, без silent loss.
- **Проверено:** 91 unittest (20 новых C-5 transport-тестов, 8 HTTP-тестов
  C-4/C-5, codec/manifest/remap/wire/levels/fixture/validation regression)
  прошли; Pyright production DTO/archive/facade — 0 errors/warnings;
  `git diff --check` без ошибок. SQL schema и backend server не менялись.
- **Цель:** world-owned манифесты и тела членов путешествуют в архиве по
  UID-layout с раздельными domain roots.
- **ТЗ:** ТЗ §4 (схема манифеста), `template-pack-layout.mdc`, §4.2.
- **Библиотеки:** семантика manifests/members и доменное наполнение
  секций — [`library-packs-model-done.md`](library-packs-model-done.md) шаги
  4a–4d; здесь только размещение файлов в архиве, контракт не
  дублируется.
- **Файлы:** `dataModel/worldBundle/libraryArchive.py` (archive manifest
  DTO и mapping); `bundle/archive/libraryLayout.py` (проверки manifests,
  UID-path mapping); reader/writer/contents; `tests/test_bundle_library_archive.py`.
  Guard в `WorldBundleService.read_archive` запрещает потерю библиотек
  до подключения доменного импорта в 4d.
- **UID:** member `template_uid`/`pack_uid` при импорте — по
  UID-политике «carry / attach / mint» выше (carry при update, attach
  при copy); codec uid не трогает — разбор происходит слоем импорта.
- **Зависит от:** схемы манифеста (ТЗ §4 — зафиксирована); **не** от
  SQL-модели паков.
- **Проверка:** skeleton-архив содержит `library/`; round-trip
  сохраняет состав паков и refs.
- **Done:** self-contained перенос world-owned библиотек в архиве.

#### Уточнения C-5 — согласовано 2026-10-12

- Архивные пути только по UID:
  `library/{domain_root}/{pack_uid}/{template_uid}.json`; metadata-файл
  `pack.manifest.json` в той же папке. Name-based FS-layout сохраняется
  для авторского входа. Архив не восстанавливает UID по имени и не
  использует diagnostic `source_file` для адресации.
- Новый optional `library_packs` вход writer и поле результата
  `ArchiveContents.library_packs` несут typed manifest + bodies по UID.
  Multi-domain пак повторяет один полный manifest во всех своих roots.
  Для standalone kind тот же mapper без префикса `library/`, source pack
  UID обязан совпасть с единственным логическим паком.
- Reader сначала проверяет inventory и manifests, строит точный состав
  разрешённых файлов из деклараций, затем читает sections и bodies.
  Reject: неверный root/UID-path, несовпадающие manifests одного пака,
  отсутствующее/лишнее тело, повторный UID члена в одном/разных паках,
  body не является object. Имена могут повторяться; UID и refs сохраняются.
- Archive DTO сохраняет provenance/creation_kind/defaults/дополнительные
  metadata, допускает отсутствие FS-only source_file. Доменные проверки
  тел, формулы UID и ownership — 4d, через общую L-policy. Caller экспортирует
  только world-owned библиотеки; C-5 не читает SQL и не строит каталог по именам.
  Пак без членов отвергается явно: в этом layout domain roots определяются
  объявленным составом, домен пустого пака не угадывается. Raw blobs C-3
  остаются только explicit trusted seam; они не могут перекрыть typed
  library paths и не допускаются в standalone library archive.
- До 4d HTTP world-import явно отвергает непустые libraries вместо
  молчаливого отбрасывания. C-4 export пока даёт прежние sections;
  C-5 проверяется синтетическими fixtures без SQL. Подключение мировых
  библиотек к export/import pipeline — 4d, не скрытая часть C-5.
- Проверка: `python -m unittest tests.test_bundle_library_archive
  tests.test_bundle_archive tests.test_bundle_manifest
  tests.test_bundle_archive_routes`; multi-domain/world/standalone
  round-trip, одноимённые копии и паки, provenance/refs, точный inventory,
  детерминированные bytes и отсутствие потерь на HTTP-границе.

### Шаг 6 — `pack/` subtree (уровень `full`) ✅ DONE

- **Цель:** запечённый World Pack путешествует в том же файле — один
  `.wpack` несёт настройки мира и его компиляцию.
- **ТЗ:** `tz_world_pack_storage.md` (формат pack), §4.2.
- **Файлы:** codec + wiring к pack storage; `ImportLevel` / `for_level`
  / route pattern — plumbing уровня `full`; импорт — распаковка `pack/`
  в pack-каталог мира (семантика `PackImportService`, subtree extract).
- **Контракт:**
  - `ImportLevel` += `"full"`; `for_level("full")` = SKELETON — `pack/`
    не секция dict, а файлы, через `filter_bundle_for_export` не
    проходит; route pattern `^(registry|skeleton|full)$`.
  - Экспорт: verbatim обход `pack_root` (`WorldPackPaths.for_world`) →
    entries под `pack/`; `*.grade_rays.json` не входят; `*.zst` —
    STORED. `full` на мире без bake — явная ошибка уровня, не пустой
    subtree.
  - Импорт: extract `pack/` → `pack_root` импортированного мира;
    `terrain_pack_path` сбрасывается на этот pack_root.
  - **Pack remap:** если импорт выполнил uid_map (режим `copy` §4.1 или
    текущий auto-remap при коллизии) — uid-поля `manifest.json` /
    `locations_index.json` и имена `locations/l.{uid}.*` переписываются
    по тому же uid_map слоем импорта поверх распаковки; codec байты не
    переписывает. Тела блобов неизменны — хеши тел валидны; manifest
    пересобирается, `content_hash` пересчитывается.
  - **Открытая проверка — uid внутри zst-payloads:** контракт «блобы
    verbatim» предполагает, что `location_uid`/`world_uid` живут только
    в именах файлов и manifest/index. При реализации проверить
    wire-формат `settlement.zst`/`world_map.zst`/`terrain.zst`: если uid
    зашит и внутри payload — pack remap при copy становится глубже
    (переупаковка блобов), контракт расширяется явной правкой.
- **Проверка:** full export → import восстанавливает pack-каталог
  побайтно (hash entries); `full` на unbaked мире — ошибка; copy-импорт
  переписывает uid в pack subtree согласованно с секциями.
- **Done:** один файл несёт мир целиком: настройки + библиотеки + bake.

## Вне scope

- Default copy целого мира и library negotiation реализуются в шаге 4d
  `library-packs-model-done.md`; этот план даёт source metadata и codec.
  Full-world update не входит в обязательный 4d/L-5.
- SQL-модель паков, владение, инстанцирование, эффективный каталог —
  `library-packs-model-done.md`.
- Publish world→engine, импорт engine user-паков из bundle — ТЗ §4.1.
- Standalone `POST /worlds/{uid}/pack/import` (pack-only zip) остаётся —
  другая операция (обновить pack без импорта мира); общий
  extract-контракт переиспользуется, замены не требует.
- Старый транспорт «zip `world_{uid}_pack.zip` рядом с `world.json`»
  (`tz_world_pack_storage.md` §B) — superseded этим форматом; пометить
  там при сдаче шага 6.
- Runtime-чтение из архива — архив только транспорт; хранилище остаётся
  SQL + World Pack-каталог.
