# План: единый мини-движок canonical defaults для библиотек и реестров ✅ DONE

> Карта межплановых зависимостей и критический путь:
> [`plan-dependency-graph.md`](plan-dependency-graph.md).

## Контекст

Коммит `112da04` ввёл canonical-attach для world-реестров: `CANONICAL_OVERLAY_ID_FIELD`
на POJO + `canonical_registry_wire()` + `_merge_registry_list()` (material/terrain).
Механика работает, но привязана к одному слою (`world` slice → `registry_list`).

Цель — **домен-агностический движок**: библиотека/реестр объявляет спецификацию
(идентичность, источник канона, scope, политика подключения), движок выполняет attach,
ничего не зная о потребителях. Любой новый домен = новая декларация, не новый код слияния.

Этот план покрывает **ядро движка и world scope** — они не требуют pack-модели.
Global scope (fill-missing в SQL глобальных библиотек) опирается на pack-модель —
соседний план [`library-packs-model-done.md`](library-packs-model-done.md): pack-owned UID,
SQL-каталог паков, manifests, instantiate/copy, эффективный каталог и проводка
structures/relief через `ensure_canonical` этого плана. Порядок: шаг 2 → шаг 3;
контракт шага 2 согласуется **до** шага 2 pack-плана — тот фиксирует
cache-контракт полноты по spec-декларации `ensure_canonical`.

## Целевая архитектура

```text
Декларации (по одному месту на домен)          Движок (без знаний о доменах)
┌───────────────────────────────┐             ┌──────────────────────────────────┐
│ POJO: CANONICAL_OVERLAY_ID_   │             │ canonicalLibrary/                │
│ FIELD + canonical_defaults()  │  world-scope│  · CanonicalLibrarySpec           │
├───────────────────────────────┤ ───────────▶│  · canonical_merge(spec, rows)    │
│ Library service: adapter spec │ global-scope│  · attach triggers (absent/empty/ │
│  (id key, canonical source,   │ ───────────▶│    partial, persist vs overlay)   │
│   FS domain root, pack list)  │             │  · ensure_canonical(spec, ctx)    │
└───────────────────────────────┘             └──────────────────────────────────┘
         ▲ registration только через spec — потребители движка не знают
```

### Инварианты

1. **Движок не знает доменов.** Всё специфичное (ключ идентичности, источник канона,
   scope, триггеры, persist-политика) — в `CanonicalLibrarySpec`, объявленной доменом.
2. **World wire-overlay** (= текущий `canonical_registry_wire`): world/explicit
   строки идут первыми (индексы ошибок валидации сохраняются), по совпадению ключа
   явные поля world-строки побеждают, отсутствующие поля наследуют canonical;
   canonical-only ключи добавляются в конец. Явные `false`/`0`/`[]` — это значения,
   не отсутствие; nullable-поля — по контракту POJO.
3. **Global fill-missing.** Автоматический attach добавляет только отсутствующие
   UID; существующее тело и `source_file` сохраняет, включая пользовательские
   изменения canonical UID. Конфликт разрешается атомарно в SQL без замены строки.
   Ручной импорт сохраняет отдельную политику явной замены. Повторный attach
   идемпотентен. Field-merge нормализованных SQL-тел не выполняется: они уже не
   несут информацию об исходной явности полей.
4. **Partial update сохраняет текущую семантику.** При `partial=True` отсутствующий
   в запросе реестр не меняется. Переданный список нормализуется с каноном и
   заменяет сохранённый реестр целиком; прежние overrides, не вошедшие в запрос,
   не сохраняются автоматически. Merge с сохранённым миром вне scope.
5. **Два scope:**
   - `world` — merge в wire до валидации при полном импорте и при runtime-чтении
     (как сейчас material/terrain); результат персистится обычным импортом.
   - `global` — только явно объявленная дефолтная (canonical) библиотека движка
     доступна без ручного импорта и независимо от конкретного мира. Любой публичный
     путь чтения (`list_all`, `find_by_uid`, `get_by_uid`/resolve) обеспечивает
     attach до возврата результата, включая чтение вне генерации. `source_file`
     для новых строк проставляется как при ручном импорте. Attach не добавляет
     per-world pointers и не меняет pick-policy мира. Конкретные домены и
     pack-контракт — `library-packs-model-done.md`.
6. **Opt-out через отсутствие spec.** Instance-каталоги (resource/crops/livestock)
   сохраняют семантику полного списка мира — spec не объявляется, движок не трогает.
7. **Источник канона — декларация**, не литералы в движке: `canonical_defaults()` POJO
   для world-реестров; FS domain root + список canonical-паков для глобальных
   библиотек (состав паков и владение — pack-план). Ключ идентичности
   world-домена читается из `CANONICAL_OVERLAY_ID_FIELD` POJO — spec-адаптер
   не переобъявляет его литералом (dataModel — единственный источник,
   `dataModel-no-hardcode.mdc`).
8. **FS domain root не зависит от cwd сервера** — резолв через env или путь от корня
   репозитория (текущий `Path.cwd()/structures_templates` ломается при cwd=backend/).
   Реализация резолва — в доменных адаптерах pack-плана (шаги 6–7
   `library-packs-model-done.md`); в этом плане инвариант — только требование
   к spec-контракту, шага-владельца здесь нет.

### Контракты движка (2026-10-08)

- Общие `CanonicalLibrarySpec` и механизм attach; политики различны:
  `world_wire_overlay` и `global_fill_missing`. Доменный адаптер отвечает за
  загрузку/валидацию источника, преобразование identity и SQL-row; ядро не
  импортирует доменные модели, FS-importers или конкретные репозитории.
- Global attach сначала загружает и валидирует весь объявленный canonical-источник,
  включая уникальность identity, затем атомарно добавляет отсутствующие записи.
  Существующие строки не заменяются даже при конкурентном ручном импорте.
- Полнота определяется наличием всех canonical UID, а не непустотой таблицы или
  наличием одной строки с `source_file` нужного пака. Удалённый canonical UID
  восстанавливается при следующем обеспечении доступности; новые canonical UID
  подключаются после повторной проверки источника. Кеш не должен скрывать
  удаление/неполноту; область и инвалидирование кеша фиксируются до реализации.
- Параллельные attach согласуются на уровне библиотеки/БД и атомарного SQL-conflict;
  ошибка загрузки/валидации не оставляет записей, ошибка записи откатывает attach.
  Неуспешный attach не отмечается завершённым и допускает повтор. Persistence
  adapter определяет владение транзакцией и не делает скрытый commit чужой работы.
- Дефолтные canonical-наборы перечисляются отдельной явной декларацией, без
  wildcard-сканирования источника; конкретные наборы доменов — pack-план.
- **Единственные точки UID и логов.** UID формируется только существующей
  инфраструктурой `app.application.worldData.ids` по DET-1
  (`docs/project_data_storage_tz.md`): никаких uuid/hash/ручной конкатенации входа
  формулы в canonical engine, адаптерах или потребителях. Логи — через фасад
  `app.core.loggingConfig` и существующие доменные эмиттеры; без новых
  logger/sink/formatter для того же события.

## Шаги

### Шаг 1 — ТЗ: контракт движка — выполнен (2026-10-08)

ТЗ синхронизировано с решениями 2026-10-08: разные политики scope,
global fill-missing вместо replace-upsert, доступность на всех публичных
чтениях, partial replacement, identity адаптеров, атомарность/повтор,
разделение defaults и пользовательских библиотек. Pack-модель (прежние шаги
2a–2e и 4–5) выделена в отдельный план `.cursor/plans/library-packs-model-done.md`.

- **Цель:** раздел «Библиотеки defaults material/terrain» в `docs/tz_json_validation.md`
  расширен до контракта единого движка: `CanonicalLibrarySpec` (ключ идентичности,
  источник канона, scope, триггер, persist-политика), scope `world` + scope
  `global`; world merge-семантика и opt-out без изменений. Pack-контракт
  (владелец, членство, instantiate/copy, provenance, эффективный каталог) —
  `docs/tz_template_library_packs.md`.
- **ТЗ:** `tz_json_validation.md` § «Wire projection → WorldSlice»;
  `tz_template_library_packs.md` целиком; `tz_building_generator.md` §5.1, §6.1.
- **Файлы:** `docs/tz_template_library_packs.md`, `docs/tz_json_validation.md`,
  `docs/tz_building_generator.md`, `docs/tz_terrain_relief.md`,
  `docs/project_data_storage_tz.md`, `docs/tz_world_bundle.md`, `docs/tz_logging.md`,
  `.cursor/rules/template-pack-layout.mdc`.
- **Проверка:** review согласованности ТЗ и ссылок; никаких изменений
  runtime/schema/tests на этом этапе.
- **Done:** ТЗ согласовано; нет кода.

### Шаг 2 — ядро движка — выполнен (2026-10-09)

- **Цель:** новый модуль `backend/app/application/canonicalLibrary/` — домен-
  агностические `canonical_merge()` (world wire-overlay) и
  `ensure_canonical()` (global fill-missing) поверх spec-деклараций доменов.
- **ТЗ:** `tz_json_validation.md` § «Wire projection → WorldSlice»;
  `tz_template_library_packs.md` §2–7.
- **Файлы:** `backend/app/application/canonicalLibrary/*.py`,
  `backend/tests/test_canonical_library.py`.
- **Контракт:** `CanonicalLibrarySpec` (identity key, canonical source
  provider, scope, attach policy + domain source/persistence adapters) —
  immutable, typed scope/policy. `canonical_merge(spec, raw) -> raw` — pure,
  работает на **wire-dict до валидации** (merge сырых полей, инвариант 2;
  semantic-валидация остаётся у resolver). `ensure_canonical(spec, context)`
  — async, результат added/existing UID. Для global-политики source adapter
  выдаёт полностью проверенный typed snapshot домена, persistence adapter
  атомарно делает insert-missing в контексте БД; engine не валидирует
  семантику доменных тел и не читает raw dict global-источника. World
  partial gating остаётся у caller; engine не читает сохранённый мир.
- **Проверка (cwd=backend):** `python -m unittest tests.test_canonical_library` —
  absent/empty/partial реестр, world-override по ключу, N+1 ключ, явные false/0,
  порядок строк; global fill-missing, конфликт canonical UID с user override,
  конкурентный attach, ошибка/rollback/повтор, частичная библиотека и восстановление
  удалённого UID. Persistence-double — адаптер по протоколу движка поверх
  временной SQLite: SQL-гарантии (insert-missing, conflict без replace,
  rollback) проверяются на реальной БД, не на mock. Реальные таблицы
  pack-каталога и их constraint-ы — шаг 2 pack-плана.
- **Найдено и исправлено (2026-10-09):** `INSERT OR IGNORE` молча пропускает
  не только конфликт по PK/UNIQUE, но и NOT NULL/CHECK-нарушения — битая
  canonical-строка терялась бы silently при статусе added. Persistence
  использует `INSERT … ON CONFLICT (uid_col) DO NOTHING`: игнорируется
  только конфликт идентичности, прочие нарушения целостности — ошибка →
  rollback всего attach. Требование к uid-колонке — UNIQUE/PK-индекс;
  доменные UNIQUE constraints (не identity) при конфликте дают ошибку,
  а не skip. Покрыто `test_insert_error_rolls_back_and_retry_works`.
- **Done:** ядро покрыто тестами; world-slices ещё не переведены.

### Шаг 3 — world-scope через движок — выполнен (2026-10-09)

- **Цель:** перевести material/terrain canonical-attach на движок без смены
  поведения (дифф семантики = 0).
- **ТЗ:** `tz_json_validation.md` § «Wire projection → WorldSlice» (merge-семантика),
  § «Import path (write)», § «Runtime path (read)».
- **Файлы:** `backend/app/application/jsonValidation/worldSliceMerge.py`,
  `worldSlices.py` (тонкая делегация).
- **Контракт:** `worldSlices.canonical_registry_wire` и
  `worldSliceMerge._merge_registry_list` делегируют в `canonical_merge`
  движка; `WorldSlice` по-прежнему несёт только
  `canonical_overlay_id_field` — identity world-домена читается из
  `CANONICAL_OVERLAY_ID_FIELD` POJO, spec не дублирует ключ литералом.
  Одноимённый 3-аргументный `_merge_registry_list` в
  `scripts/build_world_test_all_fixture.py` — отдельный helper сборки
  fixture, не затрагивается.
- **Проверка (cwd=backend):** `python -m unittest tests.test_world_registry_defaults
  tests.test_fixture_bundle_import` — без регрессии семантики. Зафиксировать отдельно
  absent-registry partial и replacement переданного списка.
- **Baseline анализа:** 13 тестов, одна ошибка `FileNotFoundError` для отсутствующего
  `fixtures/world_test_gen.json`. Восстановить согласованный baseline до миграции;
  не маскировать ошибку пропуском теста и не считать её следствием движка.
  **Факт:** baseline уже согласован — fixture переименован в `world_test_002.json`
  (коммиты `6c4f3e1`, `4955deb`), ссылок на старое имя в тестах нет; прогон до
  миграции — 13 OK.
- **Done:** material/terrain работают через движок; дифф поведения = 0.

## Вне scope

- **Pack-модель библиотек** — pack-owned UID, SQL-каталог паков/членства/зависимостей,
  manifests, instantiate/copy/publish, bundle round-trip, эффективный каталог мира,
  resolve template-refs, проводка structures/relief через global scope —
  `.cursor/plans/library-packs-model-done.md`.
- Перевод каталожных N+1-реестров (terrain, material, economic_tier…) на
  pack-модель — deferred-фаза pack-плана.
- `runtime_merge_id_field` (T-29 union merge canonical⊕world на resolved
  POJO — district/barrier) — другая семантика: union resolved entries,
  не wire-overlay исходных dict. В этот план не переводится; при
  необходимости — отдельная политика spec поздним расширением.
- Instance-каталоги resource/crops/livestock — семантика полного списка мира.
- DAG-ноды, изменение семантики REF-W правил, master-mode.
