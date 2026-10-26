# Library write — самостоятельный план исправления c5d5b2c3 ✅ DONE

Дата: 2026-10-13. Статус: **done**, исправления реализованы и проверены.

Коммит: `c5d5b2c32cc396827fd5f2bf084d166a1bcb5a8c`.
Основание: ревью последнего коммита; 62 теста из
`test_library_write_service`, `test_library_packs_4b`, `test_library_packs_4c`
прошли. Сценарии ниже выявлены анализом кода; отдельные воспроизводящие
тесты ещё не добавлены.

**Решение пользователя:** исправить регрессии отдельной ближайшей работой.
Этот план исполняется самостоятельно, не ждёт L-5 или bundle 4d.
Ни один из трёх пунктов не переносится в очередь этих этапов.

Контекст: [архитектура L-4](library-write-l4-architecture.md),
[library-write-policy-done.md](library-write-policy-done.md). Переиспользовать их общий
write pipeline и формат negotiation. Реализованный здесь transport seam
в дальнейшем используется L-5; повторно писать его на L-5 не требуется.

Объём: уже существующие HTTP-входы relief/structure, world relief import,
их текущие callers и application publish/copy_pack. Bundle consumers
защитить от неверного типа результата с полным rollback. Новые редакторы
библиотек, полный архивный import 4d и остальная миграция L-5 сюда не входят.

## LIBWRITE-TD-1 — P1, создание шаблонов через HTTP без owning pack

Статус: **done** 2026-10-13. Исправление: шаги 1–3 этого плана.

`POST /relief-templates` и `POST /structure-templates` вызывают
`upsert_from_dict(data)` без `pack_uid`/`local_uid`. Новый
`libraryPacks/domainWriteEntry.py` запрещает ownerless writes. Для нового
relief отказ происходит сразу; для новой структуры — при отсутствии member.
Маршруты ловят прежние domain errors, но не `LibraryPackValidationError`,
поэтому отказ превращается в HTTP 500. Аналогичный путь есть у JSON-upload
relief import.

План исправления:

1. В существующие create/import request models добавить owning `pack_uid`
   и `local_uid` для структуры. Сохранить тело шаблона в прежнем формате:
   transport-поля не должны попадать в domain outline. Для relief local key
   берётся из `system_name`; для структуры wire `system_name` должен совпасть
   с member UID по существующему контракту. Scope брать из world route,
   глобальный route работает в engine scope.
2. Передавать эти аргументы через domain library service в общий pipeline.
   Создать outcome-returning entry для HTTP там, где row-returning upsert
   не позволяет продолжить negotiation; сохранить старый application API
   для его callers. Не восстанавливать ownerless upsert и silent replace.
3. Обновить существующие frontend/API callers, если они найдены, чтобы
   передавать выбранный pack; не выбирать произвольный pack автоматически.
   При отсутствии owning pack возвращать 422 до записи.
4. Общий HTTP mapper: validation → 422, ownership/read-only → 403,
   not-found → 404, conflict/in-use → 409. Policy-required exception
   обрабатывать раньше обычного conflict, сохраняя её outcome.

Приёмка: валидное создание в writable pack; отсутствие pack даёт 4xx без
записи; default/чужой pack запрещён; структуры получают согласованную
pack/member identity; JSON-upload не обходит эти правила.

## LIBWRITE-TD-2 — P1, PolicyRequired не поддержан существующим транспортом

Статус: **done** 2026-10-13. Исправление: шаги 1–4 этого плана.

Повторный импорт пользовательского FS-пака возвращает `PolicyRequired`
из `ReliefTemplateLibraryService.import_path` /
`StructureTemplateLibraryService.import_path`, тогда как HTTP-маршруты
вызывают `len(rows)` и итерируют результат. Повторный импорт relief bodies
в мир возвращает тот же outcome из `ReliefWorldImportService`, а HTTP
передаёт его напрямую в `JSONResponse`; dataclass не JSON-сериализуем.
Получается HTTP 500 вместо согласования. Маршруты также не принимают
decisions/token для продолжения операции.

Bundle consumers сохраняют старые ожидания: `bundle/reliefSection.py`
читает `info["imported"]`, `WorldBundleService` ожидает `ImportResult.failed`.
При поступлении policy outcome они также не могут продолжить обмен.

План исправления:

1. Добавить общий serializer policy outcome: HTTP 409 с `status`,
   `preview_token`, `choices`, `preview`, `stale`. Явно сериализовать
   application DTO в JSON-совместимые значения; не отдавать raw dataclass
   или весь внутренний persistence plan. Успешные ответы сохранить.
2. Добавить `decisions`/`preview_token` к существующим FS/world/body import
   запросам, в том числе multipart relief import. Передавать их до writer;
   повторный запрос перечитывает источник и проверяет token в общей UOW.
   Для body create/edit использовать тот же transport seam из TD-1.
3. В routes разбирать outcome до `len`, итерации и `JSONResponse`.
   Уточнить union-аннотации application methods и проверить всех callers.
4. В текущих bundle handlers до обращения к `info["imported"]` или
   `ImportResult.failed` обнаруживать policy outcome и поднимать application
   exception с этим outcome. Исключение должно выйти из общей transaction,
   откатить world/entity/library writes и только затем превратиться в 409
   общим HTTP mapper. Не возвращать успешный ImportResult и не коммитить
   частичный bundle. Полный новый архивный negotiation 4d здесь не строить.

Приёмка: повторный FS/world import возвращает 409, а не 500; copy/replace
с актуальным token применяются; stale и неполный batch не пишут данные;
bundle negotiation не оставляет world/entity/library writes, а ошибка
любой секции откатывает весь apply. Сохранить тесты canonical additive attach.

## LIBWRITE-TD-3 — P2, публикация под свободным именем требует недоступный token

Статус: **done** 2026-10-13. Исправление: шаги 1–2 этого плана.

Последовательность: `copy_pack(world_pack_uid)` создаёт стандартную
публикацию; затем `copy_pack(world_pack_uid, system_name="another.copy")`
передаёт явное COPY под свободным именем. Inspector всё ещё обнаруживает
стандартную публикацию в matches, и policy требует preview_token.
`LibraryWriteFacade.publish` / `LibraryPackService.copy_pack` не принимают
token, поэтому второй вызов возвращает `PolicyRequired`, а завершить
согласование через этот фасад невозможно.

План исправления:

1. Добавить keyword-only `decisions=()` / `preview_token=None` к
   `LibraryPackService.copy_pack` и `LibraryWriteFacade.publish`.
   Первый запрос без решений сохраняет нынешнюю семантику default publish;
   явный `system_name` формирует COPY selection как сейчас. При повторном
   запросе передавать полученные decisions/token в `pack_request`.
2. Проверять согласованность `system_name` с переданным COPY selection;
   конфликт аргументов отклонять, не выбирать один молча. Разрешать только
   COPY для publish: этот API не должен превращаться в replace engine pack.
3. Явно объявить union `PackRemapResult | PolicyRequired` и обновить callers.
   Если стандартная публикация найдена, возврат preview допустим, но
   последующий вызов с актуальным token обязан завершать COPY под свободным
   именем. Проверку занятости оставить общей policy/executor внутри UOW.

Приёмка: после стандартной публикации можно завершить публикацию под
другим свободным именем через поддерживаемый обмен; занятое новое имя
не перезаписывается; stale не пишет данные; исходный world pack неизменен.

## Исполнимые шаги и затрагиваемые файлы

1. **Воспроизведение.** Добавить `backend/tests/test_library_write_api.py`
   с реальным Container/SQLite и HTTP-вызовами, а также regression case в
   `test_library_packs_4b.py`: стандартная публикация → другое имя → preview
   → повтор с token → применено. Зафиксировать ошибки до изменений.
2. **Application contract.** Исправить `libraryPacks/writeFacade.py`,
   `packService.py`, `domainWriteEntry.py` и domain library services:
   forwarding контекста/decisions/token, outcome-типы, publish continuation.
   Проверить TD-3 и application tests до подключения HTTP.
3. **HTTP.** Общие request/response DTO, serializer и error mapper в API
   слое; подключить `api/routes/reliefTemplates.py`, `structureTemplates.py`
   и найденные текущие callers. Закрыть создание и повторный импорт
   полностью, включая первый 409, подтверждение и stale.
4. **Bundle safety.** Изменить `bundle/reliefSection.py`,
   `bundle/library/libraryTemplateSection.py` и границу world bundle import
   для propagation policy exception и rollback. Добавить тест на отсутствие
   world/entity/library изменений после конфликтного исхода.
5. **Приёмка.** Прогнать новый API suite, library write/4b/4c suites и
   применимые bundle tests. Для изменённых frontend callers — проверки
   проекта. Обновить статусы TD-1…3 только после прохождения сценариев ниже.

## Обязательные сценарии приёмки

- Создание relief и structure в явно выбранном writable pack проходит;
  отсутствие pack даёт 422, default/чужой pack — 403 без writes.
- Повторный FS import обеих библиотек и world relief body import дают
  JSON-совместимый 409; COPY/REPLACE с token завершаются через те же routes.
- Изменение source/target между preview и apply возвращает свежий preview
  со `stale=true`; прежнее содержимое сохранено.
- JSON-upload использует тот же контракт; для массива выбор неполного
  набора не приводит к частичной записи: отправлять тела одним batch.
- Стандартная публикация не мешает завершить COPY под другим именем;
  занятое имя и попытка REPLACE через publish отклоняются.
- Bundle policy conflict даёт управляемый 409 после rollback всей UOW;
  ошибка следующей entity-секции также откатывает библиотечный apply.
- Существующие успешные response payloads, UID/provenance и additive
  canonical attach сохраняются.

**Done:** три исходных сценария имеют рабочий публичный путь и regression
tests. Ни один из них не оставлен с пометкой «исправить на L-5/4d».

Не менять SQL schema, UID/provenance или canonical attach для устранения
этих дефектов. Не закрывать пункты только по прохождению существующих
62 тестов: нужны проверки соответствующих публичных входов.

## Результат реализации 2026-10-13

- `libraryPacks/authoringWrite.py` нормализует HTTP bodies в один batch
  общего writer, сохраняя pack ownership и UID скопированных структур.
  Старые row-returning application entry points сохранены.
- Create routes принимают `pack_uid` в query, структура также `local_uid`.
  `decisions` (JSON-массив) и `preview_token` передаются в query для
  create/world import; в form для relief upload/FS import; в JSON body
  для structure FS import. Тела шаблонов остаются прежнего формата.
- `api/libraryWrite.py` задаёт общий serializer 409 с choices/preview/token
  и mapper ошибок через `api/errorMapping.py`. В wire идут изменения и
  идентификаторы, а не внутренние outlines/world snapshots из plan.
- Добавлены продолжение `copy_pack()` через decisions/token и negotiated
  instantiate для HTTP; прежний lifecycle/confirm API оставлен совместимым.
- Bundle consumers поднимают `LibraryPackPolicyRequiredError`, выходят из
  общей UOW с rollback и затем получают HTTP 409 через общий mapper.
- Frontend callers этих template routes поиском не найдены; UI не менялся.
- 126 тестов library API/write/4b/4c/B3/bundle archive routes — **OK**.
  После уточнения identity скопированной структуры повторно все 12 новых
  `test_library_write_api` regression tests — **OK**. `git diff --check` — OK.
- Расширенный прогон с `test_fixture_bundle_import` выявил прежнее падение
  `test_all_eight_bundles_import_and_export_every_section` на
  `world_test_gen_003`: `world.library_pins` содержит `local_uid`, а
  `LibraryPinEntry` требует `template_uid`. Ошибка воспроизведена отдельным
  запуском на неизменённом HEAD во временной копии. Это отдельный открытый
  долг фикстуры, три пункта этого плана его не исправляют.

Код не закоммичен. Документ хранится локально: `.cursor/` исключена из Git.
