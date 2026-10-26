# 4d + L-5 — анализ перед реализацией ✅ DONE

Дата: 2026-10-13. Статус: **реализовано и принято 2026-10-13**.
Приёмочные suites зелёные: `test_library_write_*` 97, `test_library_packs_*`
164, bundle/archive/library_archive/routes/remap/manifest/writer-reader
84, `test_fixture_bundle_import` 5. Устаревшие фикстуры мигрированы явно:
pins `local_uid` → `template_uid` (legacy-member uid), локации читаются по
`display_name`, `world_template.json` получил `world_uid`.

Источники: `library-packs-model-done.md` §4d, `library-write-policy-done.md` §L-5,
`library-write-l4-architecture.md`, `library-write-l4-review-debt-done.md`,
`world-bundle-archive-done.md`, `docs/tz_template_library_packs.md` §0.3/4–4.2.

## Готовность и границы

**Уточнение пользователя 2026-10-13, вопрос 2:** импорт именно целого мира
по умолчанию создаёт независимую копию с remap. Обновление существующего
мира следует строить через библиотеки и действующую политику патчей,
чтобы не вводить конфликтующую полную перезапись мира. Это уточнение
заменяет прежнее требование обязательного выбора update/copy при коллизии
world_uid. Full-world update не считать согласованным обязательным путём
4d; его отдельная семантика пока не определена. Общая библиотечная
policy/decisions/token сохраняется. Engine library import мира не требует.

По текущим планам 4c, C-1…5 и L-4 завершены; 4d разблокирован. Исправления
LIBWRITE-TD-1…3 уже присутствуют в коде. L-5 нельзя выполнять как повторную
разработку HTTP negotiation: `api/libraryWrite.py` содержит DTO,
serializer 409 и mapper; relief/structure routes уже передают decisions/token.

4d и L-5 целесообразно выполнять согласованными срезами: сначала общий
application-контракт импорта, затем bundle wiring, затем lifecycle routes и
проверка клиентов. Отдельной library policy внутри bundle не создавать.
5b, удаление реестров, W2, 5c/defaults, DAG и новые домены автоматически сюда
не включать. Fallback из manifest пака отложен в отдельное ТЗ
`docs/tz_library_contextual_fallback.md` и не блокирует 4d/L-5.
Не запускать backend и не коммитить без отдельного запроса.

## Актуальные открытые вопросы после согласований

**Открытых вопросов к пользователю нет.** Ниже зафиксированы принятое
решение об отложенном расширении и техническая задача реализации.

### ОВ-1 закрыт: fallback из manifest — отдельное отложенное расширение

Решение пользователя 2026-10-13: оставить идею для отдельного ТЗ
`docs/tz_library_contextual_fallback.md`. База — дефолты POJO и дефолтные
библиотеки движка. Pack fallback не покрывает автоматически все кейсы;
контекст, пригодность и непокрытые случаи должны определяться отдельно.
SQL-хранение defaults и world/pack override resolver не включаются в 4d/L-5
и не блокируют их. Комментарий добавлен непосредственно к полю
`LibraryArchiveManifest.defaults`; транспортное поле пока сохраняется.
Явная обработка непустого отложенного поля consumer'ом — задача интеграции,
а не основание реализовать расширение. Общий round-trip активного контракта
по-прежнему не должен молча терять поддерживаемые данные.

### Техническая задача: актуальность повторного запроса при copy

Это не открытый вопрос к пользователю. Требуется техническая реализация;
дополнительного пользовательского выбора
copy/update не требуется. Default copy создаёт новый owner/world UID;
если library preview token включает его, повторная генерация UID может
сделать актуальный preview stale. Нужно обеспечить согласованную identity
и fingerprint при продолжении операции после полного rollback.

Приёмка: неизменённые источник и значимое состояние → повторный запрос
с решениями завершается; изменённый источник/цель → свежий preview без
сохранённых изменений. При default copy целевого существующего мира для
перезаписи нет, поэтому требование fingerprint всех entities старого мира
снято. Объём fingerprint определяется фактическими входами решения,
источником импорта и значимым состоянием библиотечного каталога.
Механизм (стабильный контекст операции/token binding) выбрать при реализации
через существующий общий pipeline, без второго library confirm-протокола.

### Что больше не является открытым вопросом

- Очередность: world → libraries в общей UOW, rollback всего запроса
  при policy/stale/ошибке. Prepared context несуществующего мира не требуется.
- Целый мир по умолчанию импортируется копией. Его full-world update,
  purge и удаление отсутствующих entities не входят в обязательный 4d.
- Обновления существующего мира идут через библиотеки и действующую
  политику патчей; правила missing/null/merge заново не изобретаются.
  Это не отменяет общего library copy/replace и его retention.
- Engine library import не требует мира. Импорт в существующий мир
  использует его world scope.
- Pins — пары kind/template_uid; при copy переписываются по общей uid_map.
  Исправление старых формулировок/фикстур — задача реализации.
- Attach, batch remap, propagation policy outcome, порядок FK и rollback —
  задачи интеграции, а не новые продуктовые вопросы.
- Новый UI библиотек не требуется. Использовать существующий API client;
  отсутствующий library UI отметить в результате L-5.

## Что фактически есть в коде

- `bundle/archive/contents.py`: typed `ArchiveContents.library_packs`.
  Codec читает/пишет UID-layout и сохраняет archive metadata.
- `worldBundleService.py`: export собирает старые плоские секции;
  `write_archive` не передаёт library_packs; `read_archive` отвергает
  непустые библиотеки. При коллизии мира `import_bundle` автоматически
  вызывает remap и создаёт копию, без явного mode. Это описание текущего
  кода: целевой default copy операции должен работать независимо от коллизии.
- `bundleSections.py`, `bundle/registry.py`, `bundle/order.py` не содержат
  library_packs/structure_templates. Текущий порядок — world, entities,
  затем старые body-секции.
- `LibraryWriteService.execute` выполняет inspect/policy/prepare/apply
  под `transaction_if_needed`; executor требует caller main-connection UOW.
  Возврат PolicyRequired сам по себе не откатывает записи внешнего caller:
  bundle должен выйти из UOW через application exception.
- `WriteImportSource` — готовый вход parsed sources, но не lossless DTO
  всего архива. FS-reader использовать для UID-архива нельзя.
- `LibraryWritePlanner` уже строит batch maps, remap dependencies и тел,
  retention и подготовленные world changes. Не повторять эту логику.
- `api/libraryWrite.py` возвращает `policy_required`, preview_token,
  choices, preview, stale; `errorMapping.py` подключает общий обработчик.
- `packService.py` уже имеет negotiated instantiate, publish continuation,
  CRUD и member operations. Отдельного pack lifecycle router поиском нет.
- `frontend/src/api/worldApi.js` содержит importWorld, но не принимает
  decisions/token и теряет structured 409, сохраняя только data.detail.
  Добавлять обязательный mode update/copy не требуется.
  Вызовов importWorld и library/template UI в frontend/src поиском не найдено.

## Существенные разрывы, которые закрыть до apply

### 1. Очередность world → libraries — зафиксировано пользователем 2026-10-13

Первый импорт world archive: импортировать мир, затем поверх него библиотеки
в рамках того же архивного пака и одной общей UOW. Writer видит world row
внутри этой транзакции. При PolicyRequired/stale или ошибке откатить весь
импорт, включая мир; ответ preview/409 формируется после выхода из UOW.
Запрет частичного импорта означает отсутствие сохранённых изменений после
конфликтного запроса, а не запрет временной записи мира внутри откатываемой UOW.

Копия мира использует тот же механизм: подготовить remap, создать новый мир,
затем импортировать библиотеки с новым владельцем в той же UOW. Проверить
стабильность preview/token при повторном запросе с remap нового world_uid.

Обновления через библиотеки используют существующий world scope и действующую
политику патчей. Отдельный импорт библиотеки в существующий мир использует
тот же scope. Для engine library import мир вообще не требуется.

Отдельный prepared context ещё не созданного мира не является требованием:
прежнее предложение снято как необоснованное при этой очередности.

### 2. Attach при copy мира не получается только сменой owner

Для IMPORT ветка CREATE в `packWritePlanner.py` сохраняет source system_name;
scope change сам по себе не выбирает новый ключ пака. Inspector matches
также ищет импортный source key. Следовательно, простая смена owner_world_uid
даст коллизию/неверную идентичность, а не attach.

В общем pipeline явно представить перенос владельца и целевую идентичность
по `packIdentity.py`/центральным UID-функциям; сохранить оригинальные sources
для provenance. Это контекст переноса, а не разрешение silent REPLACE.
Все паки одного мира готовить одним batch. Pack/member maps из готового
плана объединить с entity map для world-side refs; UID вне карты сохранять.
Валидация исходной и итоговой identity должна учитывать authored, pack_copy
и member_copy; copied UID нельзя восстанавливать по local_uid.

### 3. Актуальность и повтор запроса — техническая задача

Текущий library token защищает источники/каталог/scopes библиотек.
При продолжении импорта нужно также связать выбор с исходным импортируемым
содержимым. Default world copy не подтверждает библиотечный REPLACE.

Для целого мира default copy не требует отдельного конфликта выбора
update/copy из-за совпадения source world_uid. Библиотечный negotiation DTO
с decisions/preview_token сериализовать существующим seam. Full-world update
не добавлять как обязательную ветку до определения его отдельного контракта.
Token binding учитывает source contents, level, согласованную identity копии
и значимое состояние library snapshot. Состояние всех entities существующего
исходного мира не является обязательной целью проверки: он не перезаписывается.
Library token не заменять клиентским произвольным значением.

Первый конфликтный запрос и stale не сохраняют никаких изменений: временные
записи общей UOW откатываются до ответа. Повторный запрос
перечитывает источник и значимое состояние в той же UOW, где будет apply.
Способ сохранения согласованной identity copy между запросами выбрать
при реализации; не фиксировать преждевременно порядок генерации UID
относительно проверки token.

### 4. Согласовать library apply и world/entities

Полный library plan должен быть готов до применения библиотечных изменений;
world row к этому моменту уже доступна в общей UOW согласно п. 1.
Применение: world → library manifests/bodies/membership
через executor → entity handlers, затем итоговые проверки/диагностика.
Точный порядок FK и prepared world columns закрепить integration tests.
Ошибка entity после library apply обязана откатывать всё; PolicyRequired
должен покинуть transaction до преобразования в HTTP 409.

Существующие section handlers не должны независимо импортировать те же
pack-owned bodies или выбирать policy по каждому домену. Старые body-секции
принимать только через явную legacy-карту/миграцию, без угадывания owning pack.

### 5. Lossless transport и SQL-представление — разные контракты

`LibraryArchiveManifest` сохраняет defaults и extra metadata, а
`LibraryPackRow`/`WriteImportSource` их полностью не представляют.
Нельзя молча отбросить поля при conversion archive → writer → export.
Defaults относятся к отложенному расширению по решению ОВ-1; не добавлять
их SQL-хранение и fallback resolver как условие завершения 4d/L-5.
При интеграции явно обработать непустое отложенное поле, не обещая его
применения и не выдавая сохранность codec за сохранность SQL round-trip.
Owner выводить из проверенного world archive/source scope, а не доверять
произвольным extra fields. World import не создаёт engine user packs.

## Устаревшие формулировки и регрессии при смене контракта

- ТЗ §1.1/4.2 и `LibraryPinEntry` требуют пары kind/template_uid и remap pins
  по общей member uid_map. Старая строка §4d о неизменных local_uid pins
  исправлена при обновлении вопросов. Одноимённые members не сливать.
- Часть старых fixture pins содержит local_uid вместо template_uid;
  прежнее падение fixture_bundle_import зафиксировано L-4 review-debt.
  Мигрировать через явную карту старых refs, не ослаблять POJO валидатор.
- `test_bundle_archive_routes.py` ожидает auto-copy при повторном импорте.
  Default copy согласован пользователем; дополнить проверки remap библиотек,
  изоляции оригинала и rollback, а не заменять их обязательным world-conflict.
- `validate_only` остаётся read-only валидацией и не равен negotiation
  preview/token. Нельзя использовать его как разрешение последующего apply.
- Обновления существующего мира строить через библиотеки/политику патчей.
  Full-world update и удаление отсутствующих в архиве entities не согласованы;
  не вводить purge мира или force-delete как скрытую часть 4d.

## Последовательность дальнейшей реализации

Контракты реализации (2026-10-13): logical `library_packs` переносит typed
manifest + UID-keyed bodies в JSON-preview, а codec размещает их только в
`library/` subtree. `LibraryWriteItem.target_system_name` задаётся application
при owner attach, общий inspector/planner проверяет итоговую identity.
`LibraryWriteService.prepare` возвращает plan либо negotiation outcome в caller
UOW; `apply_prepared` использует тот же executor. Copy continuation использует
подписанный контекст UID-map и library token; источник и level входят в binding.
Непустой отложенный defaults и неизвестная manifest metadata отклоняются до
записей вместо молчаливого SQL round-trip. Существующие flat bodies поддерживаются
через явный legacy pack/remap; неподдерживаемый archive-домен явно отклоняется.

1. Зафиксировать request/outcome DTO для default world copy + library negotiation,
   typed bundle input, scope/identity projection и импортного token.
   Добавить failing integration scenarios нового/существующего мира.
2. Подключить очередность world → libraries в caller UOW и owner attach
   через общий writer; проверить полный rollback на preview/stale,
   стабильность token при copy и batch межпаковых refs.
3. Подключить SQL export/import world-owned packs к существующему codec;
   добавить structure_templates и исключение дублей плоских bodies.
   resolve_bundle_source должен сохранять library metadata, а не возвращать
   только sections после снятия guard.
4. Подключить default world copy, общий prepare/apply и rollback;
   сохранить JSON/file/path transport C-4. Отдельный library_pack archive
   import/export использует codec и тот же writer, не FS importer.
5. Добавить тонкие pack lifecycle routes поверх service: CRUD и доступные
   member операции, negotiated instantiate/reinstantiate/publish. Выбор
   copy/replace использует decisions/token; legacy confirm не экспонировать
   как второй HTTP-протокол. Явное редактирование по UID не требует лишнего
   выбора политики. Source-grep обязан исключить обходные import/upsert writes.
6. Обновить существующий importWorld API client: default copy, decisions/token,
   сохранение structured conflicts/stale. Не создавать новый редактор
   библиотек. Отсутствие соответствующего UI отметить в результате L-5.
7. Прогнать suites и актуализировать планы 4d/L-5 только после приёмки.

## Обязательная приёмка

- World-owned pack со structure/relief/building bodies, provenance и
  одноимёнными members экспортируется self-contained; импорт копией
  сохраняет содержимое и происхождение с согласованным remap
  packs/members/entities/pins/refs, исходный мир неизменен.
- Engine user catalog не меняется от world import; publish отдельный.
- Library policy без решений, неполный batch и stale
  не создают world/entities/library rows и не меняют исходный мир.
- Обновление через библиотеки соблюдает политику патчей. Copy не меняет
  внешние refs вне карты и корректно remap межпаковых dependencies.
- Ошибка entity после library apply откатывает world/member/body/dependency
  changes; финальная проверка актуальности и apply защищены общей UOW.
- Поддельная identity/owner, default/чужой pack и битые bodies отвергаются
  управляемо. Metadata обрабатывается с учётом отложенного расширения ОВ-1;
  никаких silent losses и FS-переимпорта ZIP.
- Одинаковый source/scope даёт одинаковые library policy decisions через
  отдельный library import и через world bundle.
- Проверки: test_library_write_api/service/inspector/plan/policy,
  test_library_packs_4b/4c/5a, bundle_archive/library_archive/routes/remap,
  fixture_bundle_import после явной миграции. Frontend checks по затронутому
  API client. Backend process не требуется: HTTP tests через ASGITransport.

## Проверки текущего анализа

Код изучен без изменений реализации. Baseline `test_library_write_api`:
12 тестов, OK (8.622 s). Первый sandbox-запуск не смог определить расположение
Python; повторный запуск вне sandbox завершился успешно. Остальные suites
в этом анализе не запускались; готовность всех зависимостей взята из текущих
планов, а наличие ключевых швов подтверждено чтением кода.

Проверка согласованности документов 2026-10-13 после решений пользователя:
4d/L-5, archive-план, граф зависимостей и ТЗ §4.1/4.2 приведены к default
copy и общей world → libraries UOW. Сняты обязательный world-conflict,
активная зависимость от pack fallback и неоднозначное требование «первый
запрос без writes»: без сохранённых изменений завершаются policy/stale
запросы, допустимый импорт без конфликтов может применяться сразу.
Прежний world/pack override в §5.1/5c явно помечен историческим предложением.
`git diff --check` пройден; поведение реализации в этой проверке не менялось,
повторный прогон тестов для правок документации не выполнялся.
