# API-1 — Ревизия транспортного API и единый доступ к настройкам мира

**Статус:** DOCUMENT DESIGN / ACTIVE REVIEW (2026-11-02); exact contracts и пользовательская приёмка OPEN. Только архитектурный план, не разрешение на реализацию.
**Scope:** весь backend; целевое размещение транспортных endpoints — `backend/app/api/`.
**Связанные планы:** [GEN-DAG](./gen-dag-1-post-geo-ws.md), [Snapshot](./world-domain-patches-snapshots.md), [runtime/worldEdit policy](./runtime-world-edit-policy.md), [Time](./time-domain.md). [DAG-ROUTING-1](./dag-api-mode-routing.md) остаётся owner chat interaction routing, не механизмом настроек.

## Цель
Собрать все HTTP, WebSocket, SSE и debug endpoints и их маршрутную транспортную адаптацию в `backend/app/api/`. Не перемещать туда публичные Python API доменов, CRUD, алгоритмы, планирование или оркестрацию. Не создавать новую архитектуру исполнения.

## Обязательные границы
- Transport endpoints, маршруты, transport DTO, HTTP exception mapping и привязка зависимостей конкретных маршрутов принадлежат `backend/app/api/`. Исключение для инфраструктурного composition root и middleware определено ниже.
- Application, DAG, генераторы и домены не должны зависеть от FastAPI/Starlette, HTTPException или `app.api` схем. Доменные ошибки переводятся в HTTP на транспортной границе.
- Route — тонкий адаптер: разбор запроса, транспортная валидация, вызов публичного контракта, адаптация ответа и ошибок. Никаких доменных алгоритмов, скрытых pipeline, прямых записей в storage или самостоятельного PatchSet/Snapshot orchestration.
- Debug API сохраняется как диагностический интерфейс. Его вызовы должны повторять production-семантику публичных операций, а в DAG-сценариях — путь DAG. Нормативная граница DAG определяется GEN-DAG-1, а не API-1.
- Сохранить публичные URL, HTTP methods/status, query/body/response, WebSocket/SSE protocol, авторизацию и поведение клиентов. Breaking changes — отдельное согласование.
- Не переносить CLI, unit tests или обычные Python-контракты только из-за слова «API». Не создавать дубли маршрутов и бессрочные compatibility shims.

## Этапы
1. **Аудит:** искать все определения FastAPI/APIRouter endpoints, WebSocket/SSE, HTTPException, StreamingResponse, transport DTO, регистрацию роутеров и обратные импорты `app.api` / FastAPI из доменных слоёв. Проверять фактические call chains, а не только имена.
2. **Реестр нарушений:** исходный путь, роль, внешний контракт, доменный владелец, решение (оставить/перенести/разделить/не транспорт), целевой путь, риски. Утвердить реестр до кода.
3. **Карта зависимостей:** `api → application/domain`; выделить транспортные DTO и error mapping, устранить обратные импорты без переписывания доменных контрактов.
4. **Миграция:** небольшими этапами переместить подтверждённые transport responsibilities, сохранив публичные контракты и не затронув DAG/генераторную логику.
5. **Debug API:** подтвердить отсутствие альтернативного production pipeline и соблюдение GEN-DAG-1.
6. **Приёмка:** повторный полный аудит; сравнение endpoint/protocol contracts до/после; проверка отсутствия циклов, дублей и доменных операций в routes; аудит реальных цепочек вызовов. Зелёные тесты не заменяют архитектурное ревью.

## Definition of Done
- Все transport endpoints backend находятся в `backend/app/api/`; инфраструктурные исключения ниже не дают права определять endpoints вне `api/`.
- Нет transport-specific зависимостей из application/domain слоёв и нет оркестрации мира внутри маршрутов.
- Внешние контракты сохранены или изменения явно согласованы.
- Для каждого выявленного нарушения имеется решение и проверенная цепочка вызовов.

## Ограничения
API-1 не блокирует GEO-1 или GEN-DAG-1 целиком. Не менять GEO-1, DAG, доменный CRUD, PatchSet/Snapshot lifecycle или генераторные алгоритмы в рамках переноса. Реализация только после аудита, согласования реестра и отдельного разрешения мастера.


## Предварительная ревизия кода (2026-10-29; не полный аудит)

**Метод:** GitHub code search по `APIRouter`, `FastAPI`, `HTTPException`, `WebSocket`, `StreamingResponse` в `backend/app/` и выборочное чтение подозрительных файлов. Результаты поиска не доказывают полноту: динамическая регистрация, импорты, SSE, middleware и все фактические call chains ещё не проверены.

| Файл / область | Наблюдение | Решение для API-1 |
| --- | --- | --- |
| `backend/app/core/app.py` | Создаёт `FastAPI`, подключает routers, middleware/CORS и инфраструктурный lifespan | **Допустимое исключение (composition root)**, если только собирает приложение и подключает API-маршруты, но не определяет собственные endpoints и не содержит бизнес-операций. Не переносить механически |
| `backend/app/api/routes/*` | Найденные объявления `APIRouter` находятся в целевом каталоге | Оставить; проверить толщину handlers и наличие скрытой оркестрации |
| `backend/app/api/routes/chat.py` | Найден `StreamingResponse` в транспортном слое | Расположение корректно; дополнительно проверить SSE semantics |
| `backend/app/application/worldData/errors.py`, `worldBundle/errors.py`, `templateLibrary/packs/errors.py` | Упоминания FastAPI в комментариях; фактически обычные Python-исключения | **Не нарушение**, не переносить |
| `backend/app/application/templateLibrary/reliefTemplateLibraryService.py`, `structureTemplateLibraryService.py` | Поиск отметил упоминания FastAPI, но выборочно прочитанные фрагменты не выявили transport imports | Не объявлять нарушением без дальнейшей проверки |

**Промежуточный итог (уточнён):** 0 подтверждённых нарушений расположения endpoints по проверенной выборке; `core/app.py` — допустимое инфраструктурное исключение при соблюдении ограничений ниже; 0 найденных `APIRouter` вне `api/`. Это **не** утверждение, что других нарушений нет.

**Обязательная следующая проверка до имплементации:** инвентаризировать все импорты `fastapi`, `starlette`, `app.api` вне `api/`; определения HTTP/WebSocket/SSE endpoints, middleware и registration sites; выяснить, что в `core/app.py` является транспортом, а что инфраструктурным bootstrap. Составить полную карту `current → target`; отдельно проверить, что `core/app.py` не определяет endpoints и не выполняет доменные операции. Само наличие FastAPI в composition root не является нарушением.


## Явные инфраструктурные исключения из правила размещения

1. **Composition root:** `backend/app/core/app.py` вправе создавать экземпляр `FastAPI`, подключать роутеры из `app.api`, middleware, CORS, обработчики ошибок, lifecycle/DI и инфраструктурный bootstrap. Это сборка приложения, а не определение transport endpoints. Исключение действует только пока здесь **нет** декораторов endpoints, доменных алгоритмов, самостоятельных CRUD/pipeline или orchestration policy. Сам факт импорта `FastAPI` и `app.api.routes` из composition root допустим.
2. **Инфраструктурный HTTP middleware:** `backend/app/core/logMiddleware.py` (`RequestLoggingMiddleware`) вправе оставаться в `core/`, хотя использует `starlette.middleware.base.BaseHTTPMiddleware` и `Request`: его назначение — сквозное логирование запросов, статуса, времени, ошибок и корреляционного `request_id`. Middleware не должен объявлять endpoints, реализовывать доменные операции или обходить публичные контракты. Инфраструктурная зависимость от Starlette здесь не является обратной зависимостью домена.
3. **Граница исключений:** они применяются только к composition root и cross-cutting transport infrastructure, **не** к `application/`, `dataModel/`, генераторам, DAG и доменным сервисам. Новые исключения требуют отдельного обоснования; наличие `FastAPI` или `Request` в произвольном модуле само по себе исключением не становится.

**Коррекция ревизии:** прежняя классификация `core/app.py` как подтверждённого нарушения и `core/logMiddleware.py` как обязательного кандидата на перенос отменена. Их следует проверять на соблюдение описанных границ, а не перемещать по одному лишь пути файла.

## Расширение API-1: настройки конкретного мира (2026-11-02)

По поручению пользователя объединено с существующей ревизией API; отдельный World Settings implementation plan не создаётся. Исходный transport audit сохраняется. Объединение scope не означает приёмки нового API, изменения URL, DAG exceptions или разрешения кода.

### Базовая политика runtime/worldEdit

Нормативны [runtime/worldEdit](../../docs/tz_runtime_world_edit_policy.md), [json validation](../../docs/tz_json_validation.md), [layer boundaries](../rules/layer-boundaries.mdc) и [POJO-first](../rules/json-validation-architecture.mdc). Defaults/missing/null/empty/invariants принадлежат owning POJO; общий resolver применяет их без дублирующего settings policy engine. Partial patch missing означает не менять; после merge проверяется полное состояние. `validate_only` проходит тот же разрешённый pipeline без writes/version allocation/изменяющих задач, не write+rollback. Invalid не заменяется default. Отдельный backend worldEdit-mode/validation endpoint не вводится.

### Зафиксированные требования пользователя

1. Внешние HTTP/WS/SSE endpoints расположены в `app/api`; API — тонкий транспортный клиент публичных application contracts. Доменные Python API остаются в owning domains.
2. Домены предоставляют явные публичные методы чтения и изменения принадлежащих им настроек с typed Input/Output/Error. Домен определяется ownership, а не названием UI-вкладки: календарь принадлежит World, Time получает разрешённые settings.
3. Общий механизм не содержит доменных алгоритмов, defaults, validation rules, решений об invalidation/rebake, календарных conversions или выбора чужих операций. `WorldSettingsService` как универсальный orchestrator доменов **не предлагается**. Перенос такой логики из routes в общий helper не устраняет нарушение.
4. Единообразие — transport/error/revision/validation conventions и существующая инфраструктура, а не один огромный CRUD с domain switches. Различия owners остаются в публичных контрактах; методы не создаются ради симметрии.
5. Междоменные изменения и публикация используют принятый orchestration/acceptance path. API и settings infrastructure не становятся вторым writer/executor.

### Повторно проверенное AS-IS evidence

| Existing file / цепочка | Вывод / disposition / gate |
|---|---|---|
| [api/routes/worlds.py](../../backend/app/api/routes/worlds.py): get/create/update → container.world_service | Расположение правильное; raw dict/asdict — existing contract, не целевой typed settings API. Retain URL до принятия replacement, проверить все clients и schema semantics |
| worlds.update_world → WorldService.update → result.map_cells_invalidated → map_cell_service.clear | Подтверждён дополнительный application effect прямо в handler. Убрать из transport при принятии целевой операции/lifecycle; не просто переместить clear в generic settings helper и не удалять действующий effect до replacement |
| worlds.edit_declared_region → WorldService.edit_region | Typed operation и validate_only уже есть; reuse transport conventions после проверки nested validation/write boundary. Не выдавать этот path за готовую общую settings implementation |
| [api/routes/settings.py](../../backend/app/api/routes/settings.py) | Настройки приложения/LLM через app_settings, не world-scoped settings. Не смешивать URL/state с настройками конкретного мира; аудит transport DTO остаётся API-1 |
| [WorldService](../../backend/app/application/worldData/registries/worldService.py): update/_update/_save/edit_region | Existing merge/normalize/storage/reconcile/invalidation responsibilities. Inventory публичных world operations и nested effects обязателен; service не принимать как универсальный settings owner всех доменов |
| [worldSlices.py](../../backend/app/application/jsonValidation/worldSlices.py), worldSliceMerge/facade/worldRow | Existing WorldSlice mapping, owning POJO и общий resolver — reuse candidates. Не создавать второй каталог полей/defaults. Наличие каталога не доказывает public API/freshness/atomic acceptance |
| [core/app.py](../../backend/app/core/app.py), core/container | Retain разрешённый composition root. Explicit binding интерфейсов, без доменных алгоритмов и динамического вызова методов по пользовательской строке |

Это выборочная source-проверка, не полный audit всего API. Непроверенные endpoints, indirect imports, authorization и dynamic registration остаются в исходном этапе 1.

### Целевая граница общего механизма

| Слой / размещение | Разрешено | Не разрешено |
|---|---|---|
| `app/api/routes`, `api/schemas`, `api/errorMapping` | Transport parsing, framework validation, auth context по существующему механизму, делегирование, typed result→HTTP | Defaults доменов, raw repository writes, самостоятельные clear/rebake/commit, composition domain stages |
| `dataModel/<owner>` | Настройки/patch intent/result contracts, field policies, schema identity и model invariants | FastAPI, repositories, callbacks выполнения и новый универсальный settings bag |
| `application/<owner>` | Публичные settings read/prepare/change operations, domain checks, declared typed consequences | Чужие algorithms, скрытый междоменный pipeline, собственный Snapshot publisher |
| Общая application infrastructure | Existing resolver/report, технические protocol contracts и version checks по явным contracts | `if domain == time/physics/...`, доменные helpers, второй field registry/policy engine |
| Composition root | Явное связывание owners с согласованными интерфейсами | Выбор gameplay сценария или авторитетное принятие результата |
| Existing publication/Snapshot | Принятие изменений по lifecycle и ownership | Settings-specific algorithms или HTTP concerns |

Новый общий application service пока **не требуется**. Если audit выявит повторяющуюся чисто техническую обвязку, выделять только доказанный общий механизм с узким contract; точные папки/классы/файлы согласовать после reuse inventory. Автоматическая генерация endpoints, settings registry/router и dynamic plugin discovery не считаются принятыми решениями.

### Публичные domain operations: обязательная карточка

Для каждой settings-секции зафиксировать: owner и source of truth; current public method/caller; target method и Input/Output/Error; scope world/entity; schema/version; read revision/provenance; patch merge/null/reset semantics; validate_only; allowed lifecycle (draft/pregame/gameplay); domain consequences; commit owner; permissions; idempotency/concurrent update; exact file/import map; retain/replace/remove и migration gate.

Read возвращает typed настройки и revision, не raw SQL model. Preparation возвращает validated proposed change/diagnostics и explicit consequences, не accepted success. Update success требует подтверждения принятого lifecycle; prepared и persisted различаются. Expected revision конфликт не скрывается last-write-wins. Конкретные shapes не изобретаются общей инфраструктурой вместо owners.

Для multi-domain edit исследовать атомарное принятие prepared changes через existing lifecycle. Нельзя реализовать цикл generic service «сохранить секцию A, потом B» с partial success. Если transactional contract отсутствует, batch apply остаётся OPEN/unsupported; UI не должен обещать атомарность. Preview не резервирует версию и не гарантирует последующий apply: apply повторно проверяет актуальность.

### DAG: явный нерешённый routing contract

Действующее [dag-generator-interface.mdc](../rules/dag-generator-interface.mdc) требует `api → engine DAG → согласованная нода → public domain operation` для доменных CRUD. Пользователь поставил под вопрос необходимость DAG для settings; исключение ещё не принято. API-1 не меняет правило молча и не выводит accepted bindings из существующих прямых callers.

**На согласование:** разрешить тонкому settings endpoint напрямую вызывать одну public domain operation для ограниченного settings CRUD, если она не запускает междоменный сценарий/генерацию/публикацию мира. Если операция требует таких действий, использовать согласованный DAG/publication path; не выбирать маршрут скрыто в handler по результату операции. Точный inventory допустимых direct operations и boundary save vs prepare должны быть приняты до реализации. Альтернатива — сохранить DAG для всех domain CRUD; публичные owner contracts и transport thinness одинаковы в обоих вариантах.

Решение принимается по каждой категории операций, не по HTTP GET/POST или слову settings. Reading settings и изменение live календаря с новым anchor могут иметь разные lifecycle requirements. После принятия exception требуется явный sync owning GEN/rule; сейчас эти документы не изменяются. DAG-ROUTING-1 про chat mode flags не решает этот вопрос и не является prerequisite settings audit.

### Объединённые этапы и приёмка

Эти этапы детализируют исходные этапы 1–6, не запускают вторую миграцию.

| Gate | Prerequisites | Результат / stop |
|---|---|---|
| API-1-A audit | Existing repo/rules/clients | Endpoint + settings operation ledger, actual nested calls, placements, auth/errors/protocols. Сейчас только частичный evidence |
| API-1-B owner contracts | A по соответствующей операции | Typed public domain methods, settings POJO/resolver reuse, proposed target files и lifecycle. Foreign owner согласование, не code |
| API-1-C routing decision | B + GEN/publication owner review | Явный direct-settings exception либо сохранение DAG; multi-domain atomicity, validate_only и client compatibility. Пока OPEN |
| API-1-D migration slices | Accepted B/C для slice + отдельная команда | Сначала готовая replacement operation/binding, затем thin handler и удаление старого обхода. Без whole GEN/Time DONE |
| API-1-E verification | D по scope | Contract parity/negative/revision/concurrency/no-write-preview, nested effect audit, no domain imports в common mechanism, no bypass/duplicate routes |

Audit разных endpoint families и owner contracts можно вести параллельно. Shared error mapping/resolver/composition root меняет один writer. World calendar settings contract согласуется с Time/World; Physics numerical/API freeze не prerequisite универсального transport audit. Producer bake и runtime effects не мигрируются под видом settings cleanup.

**Дополнительный DoD:** все settings operations имеют owner/public method; API тонок по actual nested trace; общая инфраструктура не держит код доменов; validation/defaults не продублированы; routes приложения и мира различены; route choice явно согласован; multi-section atomicity не обещана без доказательства; legacy удалён только после принятого перехода.

**Следующий разрешённый шаг:** полный API-1-A inventory с отдельными settings карточками, затем B/C proposal. Код, перенос endpoints, новые POJO/ports, изменения правил и cutover этим объединением не разрешены. Обновлён только существующий API-1; незавершённые Time/graph/review-debt изменения сохранены.

## API-1-R2 — статический inventory и предметный design proposal

2026-11-02. Источники: AST всех backend/app Python файлов, rg registration/streaming/client references; imports и decorators просмотрены без импорта приложения. Сервер/тесты не запускались. Чужие изменения сохранены.

Найдено **114 endpoint declarations**, parse failures: 0. Это исчерпывающий static decorator inventory просмотренного checkout, не доказательство отсутствия динамических routes. rg add_route/add_api_route/include_router не выявил иных registration sites вне core/app.py; 16 routers подключены с prefix /api. WebSocket declarations не найдены; StreamingResponse — chat.py:162,232 (SSE transport retain).

### Endpoint contract ledger

Все перечисленные routes сохраняют URL/method до отдельной compatibility-приёмки. Для CRUD — owner/public method и routing gate B/C; для bake/patch effects — DAG gate; streaming — protocol parity. Перечень не маркирует все nested тела уже проверенными.

| Source | Method / path без /api | Handler |
|---|---|---|
| [characters.py:17](../../backend/app/api/routes/characters.py:17) | POST `/characters/import` | `import_character` |
| [characters.py:28](../../backend/app/api/routes/characters.py:28) | GET `/characters` | `list_characters` |
| [characters.py:33](../../backend/app/api/routes/characters.py:33) | GET `/characters/{character_uid}` | `get_character` |
| [characters.py:41](../../backend/app/api/routes/characters.py:41) | POST `/characters` | `create_character` |
| [characters.py:49](../../backend/app/api/routes/characters.py:49) | POST `/characters/{character_uid}/copy` | `copy_character` |
| [characters.py:58](../../backend/app/api/routes/characters.py:58) | DELETE `/characters/{character_uid}` | `delete_character` |
| [chat.py:65](../../backend/app/api/routes/chat.py:65) | GET `/health` | `health` |
| [chat.py:70](../../backend/app/api/routes/chat.py:70) | GET `/chat/history` | `get_history` |
| [chat.py:79](../../backend/app/api/routes/chat.py:79) | GET `/chat/settings` | `get_chat_settings` |
| [chat.py:90](../../backend/app/api/routes/chat.py:90) | PUT `/chat/settings` | `update_chat_settings` |
| [chat.py:102](../../backend/app/api/routes/chat.py:102) | GET `/chat/pending` | `get_pending` |
| [chat.py:113](../../backend/app/api/routes/chat.py:113) | DELETE `/chat/stream/{request_id}` | `cancel_stream` |
| [chat.py:119](../../backend/app/api/routes/chat.py:119) | POST `/chat` | `chat` |
| [chat.py:152](../../backend/app/api/routes/chat.py:152) | POST `/chat/stream` | `chat_stream` |
| [connections.py:13](../../backend/app/api/routes/connections.py:13) | GET `/worlds/{world_uid}/connections/nodes` | `list_connection_nodes` |
| [connections.py:22](../../backend/app/api/routes/connections.py:22) | GET `/worlds/{world_uid}/connections/edges` | `list_connection_edges` |
| [connections.py:31](../../backend/app/api/routes/connections.py:31) | GET `/worlds/{world_uid}/connections` | `list_connections` |
| [debug.py:47](../../backend/app/api/routes/debug.py:47) | POST `/worlds/{world_uid}/generate-structure-rotations` | `debug_generate_structure_rotations` |
| [debug.py:111](../../backend/app/api/routes/debug.py:111) | POST `/worlds/{world_uid}/generate-structure` | `debug_generate_structure` |
| [libraryArchives.py:19](../../backend/app/api/routes/libraryArchives.py:19) | POST `/library-packs/import` | `import_library` |
| [libraryArchives.py:33](../../backend/app/api/routes/libraryArchives.py:33) | GET `/library-packs/{pack_uid}/export` | `export_library` |
| [libraryPacks.py:53](../../backend/app/api/routes/libraryPacks.py:53) | GET `/library-packs` | `list_packs` |
| [libraryPacks.py:53](../../backend/app/api/routes/libraryPacks.py:53) | GET `/worlds/{world_uid}/library-packs` | `list_packs` |
| [libraryPacks.py:61](../../backend/app/api/routes/libraryPacks.py:61) | POST `/library-packs` | `create_pack` |
| [libraryPacks.py:61](../../backend/app/api/routes/libraryPacks.py:61) | POST `/worlds/{world_uid}/library-packs` | `create_pack` |
| [libraryPacks.py:67](../../backend/app/api/routes/libraryPacks.py:67) | POST `/worlds/{world_uid}/library-packs/instantiate` | `instantiate` |
| [libraryPacks.py:74](../../backend/app/api/routes/libraryPacks.py:74) | GET `/library-packs/{pack_uid}` | `get_pack` |
| [libraryPacks.py:80](../../backend/app/api/routes/libraryPacks.py:80) | PATCH `/library-packs/{pack_uid}` | `edit_pack` |
| [libraryPacks.py:80](../../backend/app/api/routes/libraryPacks.py:80) | PATCH `/worlds/{world_uid}/library-packs/{pack_uid}` | `edit_pack` |
| [libraryPacks.py:87](../../backend/app/api/routes/libraryPacks.py:87) | DELETE `/library-packs/{pack_uid}` | `delete_pack` |
| [libraryPacks.py:87](../../backend/app/api/routes/libraryPacks.py:87) | DELETE `/worlds/{world_uid}/library-packs/{pack_uid}` | `delete_pack` |
| [libraryPacks.py:92](../../backend/app/api/routes/libraryPacks.py:92) | POST `/worlds/{world_uid}/library-packs/{pack_uid}/publish` | `publish` |
| [libraryPacks.py:104](../../backend/app/api/routes/libraryPacks.py:104) | GET `/library-packs/{pack_uid}/members` | `list_members` |
| [libraryPacks.py:109](../../backend/app/api/routes/libraryPacks.py:109) | GET `/library-members/{template_uid}` | `get_member` |
| [libraryPacks.py:117](../../backend/app/api/routes/libraryPacks.py:117) | POST `/library-packs/{pack_uid}/members` | `create_member` |
| [libraryPacks.py:117](../../backend/app/api/routes/libraryPacks.py:117) | POST `/worlds/{world_uid}/library-packs/{pack_uid}/members` | `create_member` |
| [libraryPacks.py:130](../../backend/app/api/routes/libraryPacks.py:130) | POST `/library-packs/{pack_uid}/members/copy` | `copy_member` |
| [libraryPacks.py:130](../../backend/app/api/routes/libraryPacks.py:130) | POST `/worlds/{world_uid}/library-packs/{pack_uid}/members/copy` | `copy_member` |
| [libraryPacks.py:139](../../backend/app/api/routes/libraryPacks.py:139) | PUT `/library-members/{template_uid}` | `edit_member` |
| [libraryPacks.py:139](../../backend/app/api/routes/libraryPacks.py:139) | PUT `/worlds/{world_uid}/library-members/{template_uid}` | `edit_member` |
| [libraryPacks.py:145](../../backend/app/api/routes/libraryPacks.py:145) | DELETE `/library-members/{template_uid}` | `delete_member` |
| [libraryPacks.py:145](../../backend/app/api/routes/libraryPacks.py:145) | DELETE `/worlds/{world_uid}/library-members/{template_uid}` | `delete_member` |
| [locations.py:31](../../backend/app/api/routes/locations.py:31) | GET `/worlds/{world_uid}/locations` | `list_locations` |
| [locations.py:37](../../backend/app/api/routes/locations.py:37) | GET `/worlds/{world_uid}/locations/{location_uid}` | `get_location` |
| [locations.py:47](../../backend/app/api/routes/locations.py:47) | GET `/worlds/{world_uid}/locations/{location_uid}/render-grid` | `render_location_grid` |
| [locations.py:73](../../backend/app/api/routes/locations.py:73) | GET `/worlds/{world_uid}/locations/{location_uid}/children` | `get_children` |
| [locations.py:83](../../backend/app/api/routes/locations.py:83) | POST `/worlds/{world_uid}/locations` | `create_location` |
| [locations.py:93](../../backend/app/api/routes/locations.py:93) | PUT `/worlds/{world_uid}/locations/{location_uid}` | `update_location` |
| [locations.py:104](../../backend/app/api/routes/locations.py:104) | DELETE `/worlds/{world_uid}/locations/{location_uid}` | `delete_location` |
| [locations.py:113](../../backend/app/api/routes/locations.py:113) | POST `/worlds/{world_uid}/locations/import` | `import_locations` |
| [locations.py:129](../../backend/app/api/routes/locations.py:129) | POST `/worlds/{world_uid}/locations/{location_uid}/generate-settlement` | `generate_settlement` |
| [locations.py:156](../../backend/app/api/routes/locations.py:156) | POST `/worlds/{world_uid}/generate-settlements` | `generate_settlements` |
| [map.py:45](../../backend/app/api/routes/map.py:45) | GET `/worlds/{world_uid}/map/loading-progress` | `get_loading_progress` |
| [map.py:60](../../backend/app/api/routes/map.py:60) | GET `/worlds/{world_uid}/map/bootstrap-tiles` | `list_bootstrap_tiles` |
| [map.py:99](../../backend/app/api/routes/map.py:99) | POST `/worlds/{world_uid}/map/pack/bake` | `bake_world_pack` |
| [map.py:191](../../backend/app/api/routes/map.py:191) | GET `/worlds/{world_uid}/map/pack/fine-terrain-read` | `pack_fine_terrain_read` |
| [map.py:244](../../backend/app/api/routes/map.py:244) | GET `/worlds/{world_uid}/map` | `list_map_cells` |
| [map.py:257](../../backend/app/api/routes/map.py:257) | GET `/worlds/{world_uid}/map/export` | `export_map` |
| [map.py:271](../../backend/app/api/routes/map.py:271) | POST `/worlds/{world_uid}/map/import` | `import_map` |
| [map.py:287](../../backend/app/api/routes/map.py:287) | DELETE `/worlds/{world_uid}/map` | `clear_map` |
| [map.py:295](../../backend/app/api/routes/map.py:295) | GET `/worlds/{world_uid}/map/render-world-grid` | `render_world_grid` |
| [map.py:337](../../backend/app/api/routes/map.py:337) | GET `/worlds/{world_uid}/map/render-world-tile-grids` | `render_world_tile_grids` |
| [map.py:358](../../backend/app/api/routes/map.py:358) | GET `/worlds/{world_uid}/map/render-location-grids` | `render_all_location_grids` |
| [map.py:379](../../backend/app/api/routes/map.py:379) | GET `/worlds/{world_uid}/map/render-wilderness-tile-grid` | `render_wilderness_tile_grid` |
| [map.py:424](../../backend/app/api/routes/map.py:424) | GET `/worlds/{world_uid}/map/has-column` | `has_column_cells_route` |
| [map.py:441](../../backend/app/api/routes/map.py:441) | GET `/worlds/{world_uid}/map/scene-volume` | `scene_volume_route` |
| [map.py:471](../../backend/app/api/routes/map.py:471) | POST `/worlds/{world_uid}/map/refine-from-entry` | `refine_from_entry_route` |
| [map.py:576](../../backend/app/api/routes/map.py:576) | POST `/worlds/{world_uid}/map/refine-chunk` | `refine_chunk_route` |
| [map.py:653](../../backend/app/api/routes/map.py:653) | POST `/worlds/{world_uid}/map/schedule-chunk-refine` | `schedule_chunk_refine_route` |
| [map.py:721](../../backend/app/api/routes/map.py:721) | GET `/worlds/{world_uid}/map/regions/{region_uid}` | `get_wilderness_region` |
| [map.py:734](../../backend/app/api/routes/map.py:734) | GET `/worlds/{world_uid}/map/regions/{region_uid}/outline` | `get_wilderness_region_outline` |
| [perks.py:15](../../backend/app/api/routes/perks.py:15) | GET `/worlds/{world_uid}/perks` | `list_perks` |
| [perks.py:21](../../backend/app/api/routes/perks.py:21) | GET `/worlds/{world_uid}/perks/{perk_uid}` | `get_perk` |
| [perks.py:30](../../backend/app/api/routes/perks.py:30) | POST `/worlds/{world_uid}/perks` | `create_perk` |
| [perks.py:40](../../backend/app/api/routes/perks.py:40) | PUT `/worlds/{world_uid}/perks/{perk_uid}` | `update_perk` |
| [perks.py:51](../../backend/app/api/routes/perks.py:51) | DELETE `/worlds/{world_uid}/perks/{perk_uid}` | `delete_perk` |
| [perks.py:60](../../backend/app/api/routes/perks.py:60) | POST `/worlds/{world_uid}/perks/import` | `import_perks` |
| [races.py:19](../../backend/app/api/routes/races.py:19) | GET `/worlds/{world_uid}/races` | `list_races` |
| [races.py:25](../../backend/app/api/routes/races.py:25) | GET `/worlds/{world_uid}/races/{race_uid}` | `get_race` |
| [races.py:34](../../backend/app/api/routes/races.py:34) | POST `/worlds/{world_uid}/races` | `create_race` |
| [races.py:44](../../backend/app/api/routes/races.py:44) | PUT `/worlds/{world_uid}/races/{race_uid}` | `update_race` |
| [races.py:55](../../backend/app/api/routes/races.py:55) | DELETE `/worlds/{world_uid}/races/{race_uid}` | `delete_race` |
| [races.py:64](../../backend/app/api/routes/races.py:64) | POST `/worlds/{world_uid}/races/import` | `import_races` |
| [reliefTemplates.py:49](../../backend/app/api/routes/reliefTemplates.py:49) | GET `/relief-templates` | `list_relief_templates` |
| [reliefTemplates.py:55](../../backend/app/api/routes/reliefTemplates.py:55) | GET `/relief-templates/{template_uid}` | `get_relief_template` |
| [reliefTemplates.py:64](../../backend/app/api/routes/reliefTemplates.py:64) | POST `/relief-templates` | `upsert_relief_template` |
| [reliefTemplates.py:82](../../backend/app/api/routes/reliefTemplates.py:82) | POST `/relief-templates/import` | `import_relief_templates` |
| [reliefTemplates.py:114](../../backend/app/api/routes/reliefTemplates.py:114) | POST `/worlds/{world_uid}/relief-templates/import` | `import_relief_into_world` |
| [reliefTemplates.py:136](../../backend/app/api/routes/reliefTemplates.py:136) | DELETE `/relief-templates/{template_uid}` | `delete_relief_template` |
| [seed.py:19](../../backend/app/api/routes/seed.py:19) | POST `/seed/import` | `import_seed` |
| [seed.py:37](../../backend/app/api/routes/seed.py:37) | GET `/seed/export` | `export_seed` |
| [seed.py:46](../../backend/app/api/routes/seed.py:46) | GET `/seed/{table}` | `list_seed` |
| [seed.py:54](../../backend/app/api/routes/seed.py:54) | POST `/seed/{table}` | `upsert_seed` |
| [seed.py:67](../../backend/app/api/routes/seed.py:67) | DELETE `/seed/{table}/{pk_val}` | `delete_seed` |
| [sessions.py:23](../../backend/app/api/routes/sessions.py:23) | GET `/sessions` | `list_sessions` |
| [sessions.py:28](../../backend/app/api/routes/sessions.py:28) | POST `/sessions` | `create_session` |
| [sessions.py:37](../../backend/app/api/routes/sessions.py:37) | GET `/sessions/{session_id}` | `get_session` |
| [sessions.py:45](../../backend/app/api/routes/sessions.py:45) | DELETE `/sessions/{session_id}` | `delete_session` |
| [settings.py:32](../../backend/app/api/routes/settings.py:32) | GET `/settings` | `get_settings` |
| [settings.py:49](../../backend/app/api/routes/settings.py:49) | PUT `/settings` | `update_settings` |
| [structureTemplates.py:49](../../backend/app/api/routes/structureTemplates.py:49) | GET `/structure-templates` | `list_structure_templates` |
| [structureTemplates.py:55](../../backend/app/api/routes/structureTemplates.py:55) | GET `/structure-templates/{template_uid}` | `get_structure_template` |
| [structureTemplates.py:66](../../backend/app/api/routes/structureTemplates.py:66) | POST `/structure-templates` | `upsert_structure_template` |
| [structureTemplates.py:85](../../backend/app/api/routes/structureTemplates.py:85) | POST `/structure-templates/import` | `import_structure_templates` |
| [structureTemplates.py:103](../../backend/app/api/routes/structureTemplates.py:103) | DELETE `/structure-templates/{template_uid}` | `delete_structure_template` |
| [worlds.py:22](../../backend/app/api/routes/worlds.py:22) | POST `/worlds/{world_uid}/regions` | `edit_declared_region` |
| [worlds.py:38](../../backend/app/api/routes/worlds.py:38) | GET `/worlds` | `list_worlds` |
| [worlds.py:44](../../backend/app/api/routes/worlds.py:44) | GET `/worlds/{world_uid}/export` | `export_world` |
| [worlds.py:69](../../backend/app/api/routes/worlds.py:69) | GET `/worlds/{world_uid}` | `get_world` |
| [worlds.py:75](../../backend/app/api/routes/worlds.py:75) | POST `/worlds` | `create_world` |
| [worlds.py:81](../../backend/app/api/routes/worlds.py:81) | PUT `/worlds/{world_uid}` | `update_world` |
| [worlds.py:101](../../backend/app/api/routes/worlds.py:101) | DELETE `/worlds/{world_uid}` | `delete_world` |
| [worlds.py:112](../../backend/app/api/routes/worlds.py:112) | POST `/worlds/import` | `import_world` |
| [worlds.py:154](../../backend/app/api/routes/worlds.py:154) | POST `/worlds/{world_uid}/pack/import` | `import_world_pack` |

### Imports и клиенты

Transport imports вне api найдены только в:

- `backend/app/core/app.py:3` — `fastapi`.
- `backend/app/core/app.py:4` — `fastapi.middleware.cors`.
- `backend/app/core/app.py:102` — `app.api.errorMapping`.
- `backend/app/core/app.py:114` — `app.api.routes.chat`.
- `backend/app/core/app.py:115` — `app.api.routes.settings`.
- `backend/app/core/app.py:116` — `app.api.routes.worlds`.
- `backend/app/core/app.py:117` — `app.api.routes.races`.
- `backend/app/core/app.py:118` — `app.api.routes.perks`.
- `backend/app/core/app.py:119` — `app.api.routes.locations`.
- `backend/app/core/app.py:120` — `app.api.routes.seed`.
- `backend/app/core/app.py:121` — `app.api.routes.characters`.
- `backend/app/core/app.py:122` — `app.api.routes.sessions`.
- `backend/app/core/app.py:123` — `app.api.routes.map`.
- `backend/app/core/app.py:124` — `app.api.routes.connections`.
- `backend/app/core/app.py:125` — `app.api.routes.debug`.
- `backend/app/core/app.py:126` — `app.api.routes.reliefTemplates`.
- `backend/app/core/app.py:127` — `app.api.routes.structureTemplates`.
- `backend/app/core/app.py:128` — `app.api.routes.libraryPacks`.
- `backend/app/core/app.py:129` — `app.api.routes.libraryArchives`.
- `backend/app/core/logMiddleware.py:5` — `starlette.middleware.base`.
- `backend/app/core/logMiddleware.py:6` — `starlette.requests`.

Это core composition/middleware exceptions исходного плана; application/dataModel обратных transport imports AST-поиском не выявлено. AST не разрешает runtime import aliases или сторонний plugin code.

Frontend `src/api/worldApi.js` использует GET /worlds и POST /worlds/import (query/body сохранять). `src/api/settingsApi.js` вызывает /chat/settings, backend settings router объявляет /settings и core prefix /api: статическое несовпадение. Поиск callers getSettings/updateSettings не выявил потребителей helper; production outage не заявлена. Решение migration: сохранить backend /api/settings, исправить/удалить неиспользуемый client helper по caller closure, не создавать alias route без evidence внешнего потребителя. App settings остаются отдельными от world. SettingsUpdate сейчас отбрасывает None и тем самым не различает explicit null; эту semantics не копировать в world patch.

### Полный declared WorldSlice roster и владельцы

Каждая строка — existing POJO из worldSlices.py, не готовый публичный settings method. Proposed operation для каждой пары: `<Owner>Settings.read` и `<Owner>Settings.prepare_change`; exact имена/paths утверждает owner. Существующий write caller общий WorldService._update/import; transport replacement после B/C. Registry entry CRUD принадлежит owner и не выводится автоматически из root replacement.

| POJO | World wire keys | Proposed owner |
|---|---|---|
| WorldPackMetadata | `tuple(PACK_METADATA_WIRE_KEYS)` | Pack |
| WorldMapResolutionSettings | `tuple(MAP_RESOLUTION_WIRE_KEYS)` | Pack |
| WorldGridSettings | `tuple(GRID_SETTINGS_WIRE_KEYS)` | Pack |
| WorldClimateScalars | `tuple(CLIMATE_SCALAR_WIRE_KEYS)` | Climate |
| WorldTerrainScalars | `tuple(TERRAIN_SCALAR_WIRE_KEYS)` | Terrain/Relief |
| WorldReliefGradeObstacleScalars | `tuple(RELIEF_OBSTACLE_SCALAR_WIRE_KEYS)` | Terrain/Relief |
| WorldEconomyTierRegistry | `'economic_tier_registry'` | Economy/Resources |
| WorldMaterialRegistry | `'material_registry'` | Materials |
| WorldResourceTypeRegistry | `'resource_type_registry'` | Economy/Resources |
| WorldCropsRegistry | `'crops_registry'` | Economy/Resources |
| WorldLivestockRegistry | `'livestock_registry'` | Economy/Resources |
| WorldTerrainRegistry | `'terrain_registry'` | Terrain/Relief |
| WorldClimateZoneRegistry | `'climate_zone_registry'` | Climate |
| WorldEnvironmentSettings | `('world_environment',)` | World Environment |
| WorldHydrology | `('hydrology',)` | Hydrology |
| WorldTerrainMasks | `('terrain_masks',)` | Regions |
| WorldBarrierTemplateRegistry | `'barrier_template_registry'` | Locations/Structures |
| WorldSettlementSizeRegistry | `'city_size_registry'` | Locations/Structures |
| WorldSettlementSpecializationRegistry | `'settlement_specialization_registry'` | Locations/Structures |
| WorldDistrictTemplateRegistry | `'district_template_registry'` | Locations/Structures |
| WorldDistrictZonePreference | `'district_zone_preference'` | Locations/Structures |
| WorldRoadSettings | `'road_settings'` | Connections/Roads |
| WorldConnectionTypeRegistry | `'connection_type_registry'` | Connections/Roads |
| WorldTransitionTypeRegistry | `'transition_type_registry'` | Connections/Roads |
| WorldLocationTypeRegistry | `'location_type_registry'` | Locations/Structures |
| WorldLoreRegistry | `'lore_registry'` | World Lore |
| WorldWeatherTypeRegistry | `'weather_type_registry'` | Climate |
| WorldTerrainCategoryRegistry | `'terrain_category_registry'` | Terrain/Relief |
| WorldRoomTypeRegistry | `'room_type_registry'` | Locations/Structures |
| WorldLocationMoodRegistry | `'location_mood_registry'` | Locations/Structures |
| WorldRaceTemplateRegistry | `'race_template_registry'` | Races/Perks |
| WorldPerkTemplateRegistry | `'perk_template_registry'` | Races/Perks |
| WorldPurposePackRegistry | `'purpose_pack_registry'` | Locations/Structures |
| WorldPurposePacks | `'purpose_packs'` | Locations/Structures |
| WorldCanalTemplateRegistry | `'canal_template_registry'` | Terrain/Relief |
| WorldReliefPickPolicy | `('relief_pick_policy',)` | Terrain/Relief |

Calendar/combat_settings/current_tick не объявлены этим roster полноценными typed settings slices: Calendar — World-owned foreign contract Time-плана; combat — owner combat/actions; current_tick runtime state, **не редактируемая настройка**. UI section не может разрешить запись произвольного World field. Группировка owners выше — proposal по фактическим POJO paths, не новая доменная архитектура.

### Contract template и lifecycle — конкретное решение на согласование

Для каждого concrete SettingsPOJO из roster предлагается отдельная закрытая specialization:
`ReadRequest(world_uid:EntityUid, expected:WorldPublicationRef)` → `SettingsRead(settings:ConcreteSettingsPOJO, publication:WorldPublicationRef, schema_id, schema_version)`.
`PrepareRequest(world_uid, expected, operation_id:EntityUid, change:ConcreteOwnerChange, validate_only:bool)` → `ValidatedPreview | PreparedOwnerChange | SettingsRefused`.
ConcreteOwnerChange — declared typed ReplaceSettings, owner-specific EntryUpsert/EntryRemove либо typed patch с explicit omission semantics. Не dict[Any], universal union всех доменов или path-based setattr. Первый implementation slice рекомендован **whole-section replacement** на expected revision: проще доказать сохранение полного POJO; partial merge добавлять только после exact owner patch schema. DELETE whole world и removal required settings не входят в uniform methods.

Refusal codes proposal: WORLD_NOT_FOUND, REVISION_CONFLICT, INVALID_SETTINGS (existing structured issue tuple), LIFECYCLE_FORBIDDEN, REFERENCED_ENTRY, UNSUPPORTED_CHANGE. Unauthorised/Forbidden — transport/security policy, но effective write authority должна проверяться trusted application boundary, не request bool. IO/unknown commit — infrastructure outcome, не validation refusal. Schema/version mismatch не silent migration. Exact actor/capability type пока foreign OPEN: текущий get_container не permission mechanism, новые guarantees не заявлять.

PreparedOwnerChange содержит expected base, canonical change fingerprint, validated new settings, owner-defined consequences, operation_id; не authoritative accepted receipt. ValidatedPreview содержит diagnostics/proposed summary, не commit token. Общий слой не интерпретирует последствия. Runtime accepted result — existing publication result/ref после Snapshot acceptance, а не echo request. Idempotency same ID+same fingerprint returns prior accepted outcome; different fingerprint conflict; unknown outcome resolves existing operation status, не повторная новая mutation.

**Direct exception proposal:** pinned reads и pure prepare/validate могут делегироваться напрямую owner public method. Runtime acceptance и многодоменные effects остаются DAG→Snapshot. Для initial/draft save нужен отдельный принятый World lifecycle contract; до него не разрешать generic direct live save. Это сужает прежнюю неопределённую формулу «settings CRUD без DAG»: safe seam определяется side effects, не названием. Правило DAG пока не изменяется.

Multi-domain edit первой версии: preview разрешён только с coherent base; apply как единый prepared PatchSet через существующую Snapshot композицию после acceptance всех applicable section handlers. Пока этого нет — явный unsupported batch apply, не последовательный save A/B, не write+rollback preview. Mixed source returns revision conflict. Это не новый central orchestrator: сборка/порядок изменений у DAG, validation у owners, transaction у Snapshot.

### Проверенные findings и точные dispositions

- **API-F1:** worlds.update_world выполняет clear после WorldService._save. Если clear падает, settings уже могут быть сохранены; route не владеет единым acceptance. Решение: владелец grid/Pack готовит invalidation/rebuild requirement, DAG выбирает accepted lifecycle; до готовности replacement сохраняется legacy поведение, новый путь не вызывает этот helper. force=true не revision token и не Snapshot approval.
- **API-F2:** worldColumnWrite.COLUMN_INVALIDATES содержит fine_cells_per_map_cell→map_cells; это доменное правило в общей обвязке. Перенести ownership решения в Pack/grid public prepare operation при migration; общий mapper не расширять новыми domain branches.
- **API-F3:** WorldService._IMMUTABLE защищает world_uid/created_at, generic patch принимает прочие hasattr fields. Clock/runtime fields не должны попасть в settings public shape. Allowlist определяется конкретными POJO/contracts, не blacklist нового settings service.
- **API-F4:** settings.py читает app_settings напрямую, response keys/default semantics описаны в transport. Выделить application settings read contract у существующего settings-service owner; transport DTO остаётся wire-only. Это другой scope, не World settings storage.
- **API-F5:** semantic public types отсутствуют для ряда секций: roster не API freeze. Owner готовит specialization; не создавать пустые интерфейсы ради обхода B.

### File/import map и атомарные срезы

Сохранить `api/routes/worlds.py`, `settings.py`, `api/errorMapping.py`, `core/app.py`/container. Domain settings public contracts располагаются рядом с existing owning POJO/application services, не под api и не в новом application/worldSettings. Для пилота Pack: proposed `dataModel/worldPack/settings/change.py`, `application/worldData/pack/settings/settingsService.py`; common enum/transport DTO добавлять лишь при доказанной повторяемости. Existing WorldSlice registration сохраняется; новый catalog fields не создаётся. Точные папочные counts/complete specialization fields — B gate, текущая карта не объявляется code-ready. Domain errors не импортируют HTTP; route импортирует public contract, а не repository/algorithms; core связывает зависимости.

Порядок: (1) принять routing decision и owner roster; (2) пилот read/preview одного Pack grid slice, включая stale revision и lifecycle refusal; (3) отдельно accepted save/invalidations handoff; (4) независимые owners по той же форме, registry membership/refs отдельно; (5) batch integration только по готовым handler contracts; (6) legacy bypass removal после parity. App settings client correction — независимый transport slice. Нельзя параллельно менять WorldService/worldSlices/errorMapping разными writers. Общий Time calendar freeze не блокирует grid pilot; отсутствие invocation runtime блокирует зависимый DAG binding, не public contract design.

Приёмочные сценарии: missing vs explicit null/reset; invalid не default; preview no DB/Pack/tasks/version writes; stale between preview/apply; repeated operation и unknown commit; linked registry deletion; grid change после gameplay; failure до/после commit без partial acceptance; app secret write не возвращает secret read; frontend protocol parity; независимые pure reads без bake. SSE проверяется отдельно по existing chat protocol, не переделывается settings migration.

**Verdict:** static endpoint/import и slice inventories выполнены; полная nested-call/client/authorization ревизия каждой строки ещё не завершена. Proposal готов к предметному согласованию ownership/routing/lifecycle, **не exact freeze всех доменов и не CODE-READY**. Следующий разрешённый шаг — принять routing exception и пилотный owner contract; затем B exact schema/files и independent review, без кода. Межплановые requests: GEN rule exception для read/prepare, Snapshot applicable settings handler/atomic batch, Pack grid consequences, World calendar/creation ownership; в чужие документы изменения не внесены.
