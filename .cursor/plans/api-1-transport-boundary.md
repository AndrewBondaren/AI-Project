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

## API-1-R3 — проверка отчёта R2 по actual contracts (2026-11-02)

Источником предыдущего отчёта служит раздел R2 этого файла; отдельный report в доступном дереве не найден. Перед работой `git status --short` пуст; последний commit документа — `60ccaae5`. R2 сохранён как история исследования. Нижеследующие исправления имеют приоритет над его рекомендациями. Это документальный proposal, не приёмка исключений.

### Исправления evidence и контрактов

1. **R2 client mismatch опровергнут.** `frontend/src/api/settingsApi.js` вызывает существующие GET/PUT `/chat/settings` из `api/routes/chat.py:79,90`; оба router подключены в `core/app.py` с `/api`. `/settings` — другой контракт: optional поля и ответ `{ok,updated}`, тогда как `/chat/settings` принимает полный ChatSettings и возвращает ChatSettings. Поэтому предложение исправить helper на `/settings` снято. Поиск имён helper в frontend/src не выявил callers за пределами его файла; это не доказательство отсутствия внешних клиентов. Сохранить оба wire contracts до отдельной приёмки. В chat update есть прямой `app_settings.update`, в settings update — `container.settings_service().update`: ревизия должна включать оба пути.
2. **API-F1 подтверждён с уточнением:** `WorldService.update → _write_scope → _update → _save → repo.update + DeclaredRegionEditor.reconcile`, затем route вызывает `map_cell_service.clear`. `DeclaredRegionEditor.transaction` использует `transaction_if_needed`; внутри reconcile создаётся StateChangeConsumer и вызываются remove_declared/add_declared/evaluate. SQL сохранение и region effects имеют общую transaction scope при установленном editor; route clear вне неё. Нельзя утверждать, что все effects вне транзакции, либо что SQL transaction обеспечивает Pack publication.
3. **Preview не равен новому состоянию:** `edit_region(validate_only=True)` выполняет apply_region_operation, merge, normalize и prepare_import, но возвращает **исходный World**; это не PreparedOwnerChange и не preview нового POJO. `validate_only` обходит write scope и `_update`. Перенос этой сигнатуры как общего preview дал бы ложный результат. Pure prepare должен вернуть отдельно вычисленный candidate и diagnostics, не называть исходный World candidate.
4. **Нет optimistic concurrency в actual storage:** `IWorldRepository.update(World)` не принимает expected revision; `SqliteWorldRepository.update → BaseRepository.save` обновляет по primary key без CAS. `next_version_number` считает суффиксы имени, current_tick — runtime clock; schema_version и Pack hash также не универсальная revision всей строки. WorldPublicationRef из R2 — proposed foreign contract, не найденный existing type. Нельзя приписывать существующему read coherent publication или обещать conflict detection.
5. **Общая validation-инфраструктура уже содержит domain policy:** `facade.merge_world_patch` специально нормализует terrain_masks; `normalize_world` вызывает terrainHillRegistry.apply_landcover_policies с terrain_registry/default_landcover. WorldService._validate содержит grid/terrain checks. Поэтому одного переноса COLUMN_INVALIDATES недостаточно. Retain resolver/report/WorldSlice; replace domain branches owner-owned normalization/validation на том же POJO контракте. Никакого второго field registry. Cutover требует parity authored presence, canonical overlays и cross-reference validation, а не только сравнения model_dump.
6. **Pack grid не безопасный write pilot по умолчанию.** fine_cells_per_map_cell вызывает clear, grid влияет на materialization; WorldPackMetadata включает служебные publication сведения и не является автоматически редактируемой settings секцией. Предлагается сначала read/preview WorldGridSettings, только после решения routing и доказательства no writes; accepted apply — отдельный срез. Owner Pack предложен, не утверждён.
7. **Roster WorldSlice не покрывает все настройки World.** `db/models/world.py` также содержит stat/skill/resist schemas, formulas/action_registry, slots/weight/volume, HP/wounds, calendar/sleep, дополнительные registry, caves, custom fields и migration policy. Отсутствие в WORLD_SLICES не даёт права raw passthrough. Их public exposure закрыт до owning typed contract. Calendar остаётся World-owned; current_tick, created_at, идентичность, pack path/hash/version и schema/publication metadata исключаются из пользовательского settings patch.
8. **Transport размещение не доказывает thinness:** map.bake_world_pack читает World/locations/connections, собирает materialization context/writer и вызывает bake_pack, затем loading progress. Это explicit multi-input scenario; не переносить его в settings helper. chat history/pending обращаются к repositories. Для этих families A/B gate остаётся OPEN; R2 inventory не означает проверку всех вложенных callers.

### Решение ownership для непокрытых секций (proposal)

Existing для всех строк — World row + WorldService.get_by_id/update/prepare_import, а не отдельные typed public settings методы. Target — отдельный owner contract только после проверки его consumers; до этого read существующего world export сохраняется, новый settings write запрещён.

| Секция | Предлагаемый owner / граница |
|---|---|
| name, narrative_language, measurement_system | World; идентификаторы и creation metadata не менять через settings |
| calendar | World: CalendarSettings read/prepare; Time только consumer resolved calendar и clock-dependent consequences |
| stat_schema, skill_schema, resist_schema, derived_formulas, action_formulas, action_registry | Character stats / Actions; раздельное подтверждение owners, не один World bag |
| slots, weight_enabled, volume_enabled, overload_penalty_formula | Inventory |
| combat_settings | Combat/Actions |
| hp_enabled, faint_threshold, faint_check_formula, wounds_enabled, wound_death_formula, wound_type_registry | Health/Wounds |
| sleep_penalty_formula | Needs/Time consumer; ownership OPEN, не приписывать календарю |
| colour/texture/tag/intensity/narrative registries | Content owners OPEN; не выводить ownership из SQL таблицы |
| body_schema, muscle/constitution, npc target/needs/goals, character traits, respawn registries | Character/NPC owners; references и live effects проверять отдельно |
| material_category/use_type | Materials; согласовать с typed material_registry |
| cell_state/danger/road_type/location_state, caves | Соответственно cell/locations/roads/terrain owners, OPEN точные contracts |
| faction_relation_type_registry | Factions |
| player_fields, npc_fields | Character schema owner |
| stat_conflict_mode/stat_migrations/registry_migrations/trait_change_log_threshold | Migration/character evolution operations, не обычный replace settings |
| library_pins | Library attachment operation, не свободное редактирование массива |

Эта таблица дополняет все 36 строк R2, но не утверждает новые домены. File/import source для typed строк — конкретные POJO imports в worldSlices.py и accessors worldRow.py; для непокрытых строк единственный установленный storage type — World. Запрещено объявлять dict-поля production typed контрактами.

### Карточки атомарных срезов: методы, типы, файлы, переход

Все новые имена ниже — **proposed**, не existing symbols. `Revision`, `ActorContext`, `PublicationReceipt` требуют точного foreign freeze; строковый hash или request bool не заменяют их. Ошибки: существующие WorldDataNotFoundError/WorldDataValidationError/ImportValidationError сохраняются на legacy path; новые операции различают not-found, invalid с FieldPathError, forbidden, conflict, unsupported lifecycle и infrastructure failure. HTTP mapping принадлежит api/errorMapping.py, не домену.

| Срез | Existing → target public method; Input / Output / Error | Class/factory/file/import map; retain/replace/remove; gate |
|---|---|---|
| App settings | app_settings reads/update и SettingsService.update → SettingsService.read/update; typed app patch с присутствием полей / redacted view либо updated keys / invalid, forbidden, IO | Existing core/settingsService.py и container.settings_service; proposed types рядом с owner. api routes settings/chat → service; retain оба wire shape, replace прямой singleton access, remove bypass после parity. A-app: сравнить side effects обоих writers, включая reload и persistence |
| Каждый typed WorldSlice из R2 | WorldService.get_by_id + worldRow accessor → owner.read_settings(Read(world_uid,base,actor)); конкретный POJO + base / not-found, conflict, forbidden | Existing POJO import worldSlices.py retain; proposed public service в owning application package, factory в container; route imports только public method/types. B-read: coherent source и security contract, C routing |
| Каждый typed WorldSlice prepare | WorldService._update/prepare_import → owner.prepare_settings(Change(world_uid,base,actor,concrete intent)); candidate конкретного POJO + typed consequences + diagnostics / invalid, refs, conflict, forbidden | Proposed owner settings contracts рядом с конкретным POJO, service рядом с owner operation; reuse resolve + WorldSlice + merge. Replace policy branches в facade/worldColumnWrite только при parity. B-prepare: full final-state validation и нулевые effects |
| Grid pilot | WorldService.update(dict) → proposed PackSettingsService.read_grid/prepare_grid; WorldGridSettings candidate / grid lifecycle refusal | Proposed dataModel/worldPack/settings/change.py, application/worldData/pack/settings/settingsService.py; factory pack_settings_service. Retain WorldGridSettings; replace clear requirement ownership; remove legacy bypass только при accepted replacement. Gate отдельно от write |
| Regions | WorldService.edit_region(str,DeclaredRegionEdit,validate_only) → owner prepare declaration; DeclaredRegionEdit + base / candidate WorldTerrainMasks + consequences / structured invalid | Retain terrainMasks/regions/edit.py; DeclaredRegionEditor и StateChangeConsumer effects остаются owning domain. Replace old-world preview result. Acceptance связывает declaration + region state, не вызывает reconcile после publication отдельно |
| Calendar | World.calendar:dict → proposed WorldCalendarSettingsService.read/prepare; World-owned calendar contract + base / resolved candidate + Time consequences / invalid, lifecycle, conflict | Proposed worldData/calendar public service; owning World POJO path требует согласования World/Time. Не импортировать Time algorithms в common layer. Gate только calendar schema + anchor consequences, не весь Time DONE |
| Apply одной/нескольких секций | WorldService.update + route clear → согласованный DAG invocation → owner operations → Snapshot acceptance; prepared typed changes + base + operation identity / PublicationReceipt / conflict, invalid, forbidden, unknown outcome | Retain public owner operations; DAG и Snapshot bindings только отдельной приёмкой. Remove route clear и старые writers в том же cutover. Gate: applicable handlers, atomic acceptance и idempotency доказаны |
| Остальные transport families | R2 handlers → их owner public methods; existing wire Input/Output сохранить, domain errors отдельно от HTTP | Retain app/api routes/core registration; replace repositories/algorithms в handlers. Map bake зависит от согласования конкретного DAG сценария, chat SSE от protocol parity. Exact nested I/O для непроверенных families OPEN; code gate закрыт |

Общая строка «каждый WorldSlice» применяется отдельно к каждой строке R2, не предлагает generic runtime dispatch или общий service. Concrete change shape нельзя принять одним generic template: перед B PASS каждая строка должна иметь frozen I/O и factory, либо явно быть unsupported. Это оставшийся документальный gate, не разрешение реализовать недостающие contracts по усмотрению агента.

### Сквозные semantics и проверка атомарности

- Missing patch field сохраняет значение. Explicit null передаётся resolver и принимается/отвергается owning policy; null не универсальный reset. Reset — отдельный owner intent только для разрешённых полей, через existing canonical policy. Для whole-section replace missing проходит правила полного POJO; нельзя применять patch semantics незаметно.
- Facade рекурсивно сливает json_blob; supplied registries заменяются. На примере terrain_masks + terrain_registry validation и consequences вычисляются на **общем candidate**, иначе валидная совместная правка может быть отвергнута или отдельные previews окажутся несовместимыми. Проверка refs по прежнему состоянию недостаточна.
- `validate_only` не выделяет version, operation receipt, artifacts, jobs, clock events, state changes или repair defaults; разрешены чтения и локальное вычисление. Read не вызывает repair_defaults. Prepared result не authority token: apply повторно проверяет base, права и applicable invariants внутри acceptance boundary.
- Trusted actor/capability проверяется application boundary для read, preview и apply; get_container/CORS не authorization. Нельзя доверять world_uid как доказательству доступа. До freeze permission mechanism безопасность нового API не заявлена.
- Revision должна покрывать все прочитанные settings и зависимости; при независимых domain revisions нужен согласованный consistent vector, не произвольная смесь последних reads. CAS и запись результата операции выполняются в acceptance transaction. Preview A; competing apply B; apply A должен конфликтовать даже при разных HTTP соединениях.
- Multi-section operation возвращает один accepted receipt только после общего commit; failure любого handler до commit оставляет прежнюю публикацию. Staged artifact не visible state; crash после commit разрешается по operation identity без второго apply. SQL transaction region reconciliation сама по себе этого не обеспечивает. До готовности такого контракта batch apply unsupported, не partial success/207.

### DAG decision: варианты и последствия для согласования

Действующее правило `.cursor/rules/dag-generator-interface.mdc:64–81` требует API → engine DAG → принятая node → domain CRUD и удаления bypass после cutover. Оно включает CRUD read; отсутствие writes само по себе не создаёт действующее исключение.

Предпочтительный **proposal**: direct только pinned read и pure prepare/validate одной owner operation; любая persistent mutation, repair, registry membership change, draft creation/save, live calendar reanchor, grid rebuild и batch acceptance — DAG. Pure multi-section preview допустим лишь как согласованная композиция owners на общем candidate, не универсальный settings service. Пока композиция не принята, поддерживать только single-owner preview.

Сценарии: просмотр grid — direct read после exception; проверка календаря — direct World prepare без изменения tick/anchor; смена масштаба сетки — DAG с Pack consequences; удаление material с refs — domain rejection либо согласованный DAG миграции ссылок; изменение climate и material одновременно — DAG общий candidate/acceptance; изменение live календаря — DAG World + Time consequence + Snapshot; app LLM preference — отдельный app settings контракт, не World DAG exemption. Альтернатива: сохранить DAG даже для read/prepare; цена — invocation/nodes должны быть приняты для этих операций, но owning POJO/API дизайн не меняется. Direct persistent single-owner save не рекомендуется: SQL locality не гарантирует отсутствие nested effects или coherent publication.

### Очерёдность и stop verdict

1. **A-corrections (этот документ):** исправить ложный mismatch, раскрыть nested reconcile/facade policy/CAS gap. Проверка — указанные source chains; код не меняется.
2. **B-app и B-grid-read/prepare:** независимые документальные контракты, каждый со своим factory/I/O/error/security/source revision. Prerequisites — согласование owners и routing; не Time/GEN/Snapshot целиком. Grid не считается принятым пилотом.
3. **B-owner cards:** независимая детализация Climate, Materials, Terrain, Locations, World Calendar и остальных строк; shared resolver изменения одним writer. Acceptance: нет непокрытых полей или скрытых writes, all callers замкнуты по конкретной операции.
4. **C-acceptance seam:** общий candidate, CAS, operation receipt, applicable Snapshot handlers и Pack lifecycle только для выбранного среза. Требуется согласованный ограниченный contract, не завершение всего Snapshot. До этого read/prepare может быть спроектирован, apply не разрешён.
5. **D-contract migration proposal:** replacement + client parity + удаление всех legacy bypass в одной атомарной операции перехода; отдельно запрашивается разрешение кода. Не параллелить writers worldSlices/facade/container/errorMapping. Независимые owner исследования и app settings можно вести параллельно после согласования scope.

**Verdict: CHANGES REQUIRED / DOCUMENT PROPOSAL, не PASS и не CODE-READY.** R2 ошибочно предлагал client URL correction; его inventory не закрывает exact contracts и nested closure всех families. Проверенные corrections внесены; оставшиеся exact owner types, security/revision source и transport family call closure явно блокируют соответствующие B gates. Межплановые предложения отдельно: GEN — ограниченное read/prepare исключение; Snapshot — CAS/receipt/atomic batch seam; World/Time — calendar ownership и anchor consequences; Pack — grid consequences. Эти документы, rules и bindings не изменены.

**На согласование:** (а) direct read/prepare exception либо DAG для всего CRUD; (б) owner roster с OPEN секциями, не автоматическая приёмка по пути POJO; (в) grid read/prepare как пилот, без apply; (г) unsupported batch apply до atomic publication contract. **Следующий допустимый шаг:** документальная детализация одной выбранной B карточки и закрытие её callers/security/revision evidence; принятие routing не подменяется review PASS. Код, production POJO/ports, URL, DDL, nodes/bindings, публикация и cutover остаются за stop boundary.

## Принятое уточнение пользователя: domain contracts → авторские DAG-ноды → transport (2026-11-02)

Пользователь определил целевую цепочку настроек: **app/api → engine DAG → ноды, написанные пользователем → публичные typed-контракты owning domains**. Формулировка «API вызывает эти ноды» означает вызов через engine DAG, согласно действующему правилу, а не обход engine через concrete node.execute.

Домены сначала предоставляют собственные публичные settings methods с Input/Output/Error, validation и effects/lifecycle boundaries. DAG использует эти контракты; доменные методы не проектируются под выдуманные агентом ноды. **Ноды пишет пользователь.** Агент не создаёт и не изменяет ноды/bindings и не выводит их поведение из существующего implementation. Time-domain пользователь готовит к контракту отдельно; API-1 не меняет этот план.

Это решение заменяет предложенное в R2/R3 direct read/prepare exception: новый settings transport не вызывает домены напрямую. Read и prepare остаются самостоятельными публичными доменными операциями, но их транспортный вызов также проходит согласованный DAG-путь. Pure/no-write semantics prepare сохраняются независимо от routing. Дополнительное исключение из DAG-правила этим планом больше не запрашивается.

Уточнение gates: проектирование и согласование B owner contracts не зависят от готовности DAG-ноды или всего Time/GEN/Snapshot. Для transport cutover необходимы написанная пользователем и принятая нода, её engine invocation contract и проверка actual effects/publication. API остаётся тонким клиентом invocation; домены владеют своей семантикой; общего WorldSettingsService и второго registry/policy engine нет. Публикация и multi-section atomicity по-прежнему требуют собственного принятого acceptance contract.

Снятый вопрос на согласование: direct read/prepare versus DAG. Оставшиеся вопросы: точные owner contracts, спорные owner assignments, пилотный срез, revision/security и atomic acceptance. Следующий допустимый шаг — документально уточнять public settings contracts доменов для последующего использования пользовательскими нодами. Это не разрешение кода, URL changes, DDL, publication или cutover; stop boundary сохраняется.

## API-1-R4 — перечень «домен / настройка / контракт» (2026-11-02)

Scope: настройки конкретного мира, включая authored registries и generation policies. Instance CRUD персонажей/локаций и параметры одного запуска генерации не превращаются в world settings. В колонке «контракт» разделены **existing data contract** и **public settings operation**. POJO не равен публичному сервисному API. Имена будущих методов не замораживаются этой таблицей; ноды пишет пользователь, внешний API вызывает их через engine DAG.

Обозначения: **P** — existing POJO и WorldSlice; dedicated public read/prepare settings method ещё требуется. **L** — legacy World field, typed settings boundary не установлена; новый generic dict endpoint запрещён. **D** — документальный target, не production type. **S** — служебное состояние, не редактируемая настройка. Owner, помеченный «proposal», требует подтверждения и не выводится автоматически из места хранения.

Для P existing access — WorldService.get_by_id → worldRow/resolve_world_slice, write — WorldService.update/prepare_import через facade. Это общий legacy путь, а не доменный публичный контракт. Target каждой P строки: owner read возвращает указанный concrete POJO на согласованной base; owner prepare принимает concrete typed intent и возвращает candidate того же POJO, diagnostics и typed consequences. Для registry отдельно требуются entry identity, upsert/remove, references и retained history policy. Ошибки и revision/security/acceptance gates — R3. Нет общего dispatch по строковому имени домена.

### Мир, время, физическая среда и карта

| Домен / owner | Настройка / actual field | Контракт и статус |
|---|---|---|
| World | name, narrative_language, measurement_system | **L:** World scalar fields; нужны World-owned typed read/prepare identity-independent preferences |
| World (Time — consumer) | Настройки времени: initial start, hours_per_day, версии/bindings | **D:** WorldTimeSettings и public settings inventory [Time §28](./time-domain.md); exact I/O/method/files freeze в owning плане, не выдумывать здесь |
| World (Time — consumer) | calendar: registry, definition, epoch, selected calendar | **L:** World.calendar:dict; **D:** WorldCalendarRegistry и World public read current/historical, prepare create/update/select/remove по Time §28. Не объявлять calendar единственной periodic definition |
| World Environment | world_environment.atmosphere: mode, composition(system_material, fraction) | **P:** WorldEnvironmentSettings / WorldAtmosphereSettings / AtmosphereGasComponent; dataModel/worldEnvironment/worldEnvironmentSettings.py |
| Pack / spatial grid (owner proposal) | fine_cells_per_map_cell | **P:** WorldGridSettings; dataModel/worldPack/meta/worldGridSettings.py; apply имеет invalidation consequences |
| Pack / L0 resolution | world_map_cells_per_tile | **P:** WorldMapResolutionSettings; dataModel/worldPack/meta/worldMapResolutionSettings.py; это authored override, не готовая resolved сторона тайла |
| Terrain, spatial topology (ownership split OPEN) | world_topology_mode, closed_planet_grid, z_min, z_max, map_subsurface_depth | **P:** WorldTerrainScalars; dataModel/terrain/worldTerrainScalars.py. Public contract должен определить допустимость live изменения |
| Terrain execution | terrain_chunk_columns, terrain_parallel_workers | **P:** тот же WorldTerrainScalars; existing world persistence не делает эти поля physical law; не смешивать с per-request override |
| Terrain / Physics / Climate (ownership OPEN) | g, elevation_lapse_rate, magma_band_thickness | **P:** фактически WorldTerrainScalars. Не объявлять уже существующий PhysicsSettings по смыслу g; требуется owner decision без дублирования policy |
| World / spatial layout (proposal) | grid_bbox_padding, world_bounds, default_passage_height | **L:** поля World, отдельный public settings contract в проверенном roster отсутствует |
| Pack publication | terrain_pack_path, terrain_pack_hash | **S:** WorldPackMetadata в dataModel/worldPack/meta/worldPackMetadata.py; read metadata, не пользовательский replace |
| World publication / clock | world_uid, created_at, current_tick, schema_version, world_map_version, terrain_pack_version | **S:** identity/runtime/version fields; не settings patch и не универсальный revision token |

### Климат, поверхность, вода и регионы

| Домен / owner | Настройка / actual field | Контракт и статус |
|---|---|---|
| Climate | default_climate_zone; climate_temperature_peak_min/max; climate_pole_mode/preset; climate_local_influence_fraction; precipitation_liquid; climate_parallel_workers; season_temp_offsets | **P:** WorldClimateScalars + SeasonTempOffsets; dataModel/climate/worldClimateScalars.py |
| Climate | climate_zone_registry | **P:** WorldClimateZoneRegistry; dataModel/climate/climateZone/worldClimateZoneRegistry.py |
| Climate / Weather | weather_type_registry | **P:** WorldWeatherTypeRegistry; dataModel/climate/weatherType/worldWeatherTypeRegistry.py |
| Terrain | terrain_registry | **P:** WorldTerrainRegistry; dataModel/terrain/worldTerrainRegistry.py; учитывать связь с default_landcover |
| Terrain | terrain_category_registry | **P:** WorldTerrainCategoryRegistry; dataModel/terrain/worldTerrainCategoryRegistry.py |
| Relief | relief_grade_obstacle_policy | **P:** WorldReliefGradeObstacleScalars; dataModel/terrain/relief/worldReliefGradeObstacle.py |
| Relief | relief_pick_policy: mountain, open_land, shore, road_shoulder, ravine; canal_obstacle_policy | **P:** WorldReliefPickPolicy, ReliefContextPickPolicy; dataModel/terrain/relief/worldReliefPickPolicy.py |
| Relief | canal_template_registry | **P:** WorldCanalTemplateRegistry; dataModel/terrain/relief/worldCanalTemplateRegistry.py |
| Hydrology | hydrology.enabled/default_water_level/default_shore/default_rivers/default_lakes/default_seas/default_landforms/materialize_named_locations | **P:** WorldHydrology; dataModel/hydrology/worldHydrology.py; nested owning policies, не второй flat registry |
| Hydrology | hydrology.declared_lakes/basins/coastlines/rivers | **P:** тот же WorldHydrology с concrete declaration POJO; это authored objects, нужны owner operations, не произвольный patch списка |
| Hydrology / designed water | water_fraction, autoresolve, strategy; body generation_region_uid | Existing WorldWaterGenerationSettings / CategoryWaterGenerationSettings / BodyWaterGenerationSettings в hydrology/generation/waterGenerationSettings.py; **не объявлять текущим WorldSlice root**: WorldHydrologyGenerationFields отмечен future root до G10-A. Runtime binding — generators/hydrology/policy/hydrologyGenerationBinding.py |
| Terrain / Regions | terrain_masks.enabled; default_mountains; declared_mountains; default_landcover; declared_regions; default_ravines; default_roads | **P:** WorldTerrainMasks + category policies; dataModel/terrainMasks/worldTerrainMasks.py. Это несколько semantic owners под одним storage root, не доказательство одного RegionsSettingsService |
| World declarations / Regions effects | add/remove/update declared region | Existing typed DeclaredRegionEdit → WorldService.edit_region; dataModel/terrainMasks/regions/edit.py. Это публичная operation, но без нового revision/preview contract; validate_only возвращает старый World |
| Terrain / Caves (proposal) | caves | **L:** World.caves:dict; typed settings contract не установлен |

### Материалы, ресурсы, экономика и контент

| Домен / owner | Настройка / actual field | Контракт и статус |
|---|---|---|
| Materials | material_registry | **P:** WorldMaterialRegistry; dataModel/materials/worldMaterialRegistry.py |
| Materials | material_category_registry, material_use_type_registry | **L:** World dict fields; не подменять контрактом material_registry |
| Economy | economic_tier_registry | **P:** WorldEconomyTierRegistry; dataModel/economy/economyTier/worldEconomyTierRegistry.py |
| Resources | resource_type_registry | **P:** WorldResourceTypeRegistry; dataModel/resources/worldResourceTypeRegistry.py |
| Flora / Crops | crops_registry | **P:** WorldCropsRegistry; dataModel/flora/worldCropsRegistry.py; прежняя группировка всего под Economy — только UI proposal |
| Livestock | livestock_registry | **P:** WorldLivestockRegistry; dataModel/livestock/worldLivestockRegistry.py |
| Lore | lore_registry | **P:** WorldLoreRegistry; dataModel/lore/loreRegistry/worldLoreRegistry.py; registry_dict, не list |
| Races | race_template_registry | **P:** WorldRaceTemplateRegistry; dataModel/races/worldRaceTemplateRegistry.py; не путать world template settings с race instance CRUD |
| Perks | perk_template_registry | **P:** WorldPerkTemplateRegistry; dataModel/perks/worldPerkTemplateRegistry.py |
| Content owners OPEN | colour_registry, texture_registry, tag_registry, intensity_level_registry, narrative_type_registry | **L:** World dict fields; public owner/contract требуется установить, общий «контент service» не предлагается |
| Library attachment | library_pins | **L:** World list storage; dedicated attach/publish lifecycle, не свободный replace refs через settings |

### Локации, строения и связи

| Домен / owner | Настройка / actual field | Контракт и статус |
|---|---|---|
| Locations | location_type_registry | **P:** WorldLocationTypeRegistry; dataModel/locations/locationType/worldLocationTypeRegistry.py |
| Settlements | city_size_registry | **P:** WorldSettlementSizeRegistry; dataModel/locations/settlement/settlement/worldSettlementSizeRegistry.py |
| Settlements | settlement_specialization_registry | **P:** WorldSettlementSpecializationRegistry; тот же пакет settlement/settlement |
| Settlements | location_mood_registry | **P:** WorldLocationMoodRegistry; тот же пакет; наличие WorldSlice отдельно сверять с SQL/bundle projection, не считать каждую slice SQL колонкой |
| Districts | district_template_registry | **P:** WorldDistrictTemplateRegistry; dataModel/locations/settlement/district/worldDistrictTemplateRegistry.py |
| Districts | district_zone_preference | **P:** WorldDistrictZonePreference; dataModel/locations/settlement/district/worldDistrictZonePreference.py |
| Structures / Barriers | barrier_template_registry | **P:** WorldBarrierTemplateRegistry; dataModel/locations/structure/barrier/worldBarrierTemplateRegistry.py |
| Structures / Rooms | room_type_registry | **P:** WorldRoomTypeRegistry; dataModel/locations/structure/room/worldRoomTypeRegistry.py |
| Structures / purpose libraries | purpose_pack_registry; purpose_packs | **P:** WorldPurposePackRegistry; WorldPurposePacks; dataModel/locations/structure/enums/buildingPurpose; два разных контракта, не один произвольный list |
| Roads | road_settings | **P:** WorldRoadSettings с RoadSettingsEntry; dataModel/roads/worldRoadSettings.py; wire dump_by_alias, это registry-list несмотря на имя Settings |
| Connections | connection_type_registry | **P:** WorldConnectionTypeRegistry; dataModel/connections/connectionType/worldConnectionTypeRegistry.py |
| Transitions | transition_type_registry | **P:** WorldTransitionTypeRegistry; dataModel/locations/transitions/worldTransitionTypeRegistry.py. Коррекция R2: не относить автоматически к Roads |
| Cells / Locations / Roads (owners OPEN) | cell_state_registry, danger_level_registry, location_state_registry, road_type_registry | **L:** World dict fields; нужны отдельные typed boundaries |

### Character / gameplay: legacy storage, не готовые settings API

Для следующих строк actual source — `backend/app/db/models/world.py`. Поиск direct consumers по именам ряда полей в application не установил owning public settings methods. Поэтому названия доменов здесь **proposal по назначению**, не подтверждение готовой реализации. Перед freeze обязательны consumers/ref lifecycle и owning POJO; raw storage type приведён честно.

| Домен / owner proposal | Настройка / actual field | Контракт и статус |
|---|---|---|
| Character stats / skills / resistance | stat_schema, skill_schema, resist_schema | **L:** dict; concrete schema settings contracts OPEN |
| Stats / Actions | derived_formulas, action_formulas, action_registry | **L:** dict/dict/list; formula validation и action references принадлежат owners |
| Inventory | slots, weight_enabled, volume_enabled, overload_penalty_formula | **L:** dict/bool/bool/optional str; Inventory settings contract OPEN |
| Combat | combat_settings | **L:** dict; Combat settings contract OPEN |
| Health / Wounds | hp_enabled, faint_threshold, faint_check_formula, wounds_enabled, wound_death_formula, wound_type_registry | **L:** bool/float/optional str/bool/optional str/dict; Health settings contract OPEN |
| Needs (Time consumer, ownership OPEN) | sleep_penalty_formula | **L:** optional str; не приписывать Time clock settings |
| Character anatomy | body_schema_registry, muscle_tables, constitution_tables | **L:** dict; owner typed registry contracts OPEN |
| NPC | npc_target_type_registry, npc_needs_registry, npc_goal_type_registry | **L:** dict; NPC settings contracts OPEN |
| Character traits / respawn | character_trait_registry, respawn_type_registry | **L:** dict; два owning policies, не единый mutation |
| Factions | faction_relation_type_registry | **L:** dict; faction registry contract OPEN |
| Character extension schemas | player_fields, npc_fields | **L:** dict; custom declaration не разрешает arbitrary settings field |
| Migration / character evolution | stat_conflict_mode, stat_migrations, registry_migrations, trait_change_log_threshold | **L:** str/dict/dict/float; typed migration operations, не обычный replace без effects |

### Отдельно: настройки приложения и параметры вычисления

| Owner / scope | Настройка | Контракт / решение |
|---|---|---|
| App LLM / chat | provider base URLs/API keys, llm_streaming, max_tokens, language, repair_iterations/mode, max_passes, system_role_providers | core/appSettings.py + core/settingsService.py; transport SettingsUpdate и ChatSettings — existing DTO, не World POJO. Два existing URL контракта сохранять |
| App logging | log_level | LogLevel + SettingsService; процесс, не мир |
| Planning process resources | planning.cache, planning.execution | PlanningRuntimeSettings(CachePolicy, PlanningExecutionPolicy); dataModel/planning/policy/planningRuntimeSettings.py; container/worldData.planning_resources читает app_settings.planning. Не включать в WorldSettings |
| Generator invocation | free_cores, parallel_workers override, scope/tiles/grade stages | Request/operation inputs; не автоматически persisted settings; отдельно от World scalar worker caps |
| Designed-water internal policy | plate generation, field selection/composition, continental noise policies | dataModel/terrain/designedWater/settings/*.py; наличие Settings в пути не доказывает world-editable contract. Не выставлять наружу без owning operation/schema decision |

### Что этот перечень устанавливает

Проверены WORLD_SLICES (все 36 declarations), World row fields, ключевые scalar/blob POJO, worldRow accessors, legacy WorldService pipeline, process planning source и текущий Time §28. Перечень разделяет существующие типы, legacy storage и будущие contracts; он не объявляет законченной проверку всех gameplay consumers или всех вложенных policy полей. Полные вложенные поля/defaults остаются в linked POJO, не копируются во второй registry.

Для каждой P строки следующий документальный шаг — exact owner public method Input/Output/Error и factory; для L — сначала owning contract/consumer evidence; для D Time — ссылаться на результат owning freeze, не создавать конкурирующий контракт. Общий обязательный внешний путь для всех будущих world settings operations: app/api → engine DAG → пользовательская нода → owner public method. Apply/publication не выводится автоматически из наличия POJO. Изменён только API-1; межплановые правки не выполнялись.

### Приёмка исключения служебных полей (2026-11-02)

Пользователь согласовал исключение из произвольного settings update: `world_uid`, `created_at`, `current_tick`, `terrain_pack_path`, `terrain_pack_hash`, `terrain_pack_version`, `schema_version`, `world_map_version`. Поля могут возвращаться при чтении как metadata. Их запись принадлежит соответствующим операциям создания, продвижения времени, миграции или публикации, а не generic settings mutation. Согласование относится к этой границе; оно не означает приёмки остальных OPEN contracts, разрешения кода или cutover.

### Решения пользователя: первый срез и ownership g (2026-11-02)

- Первым срезом принят **Climate**: публичные settings contracts для WorldClimateScalars, WorldClimateZoneRegistry и WorldWeatherTypeRegistry. Следующий допустимый шаг — документально исследовать и описать exact public methods, Input/Output/Error, factories, consumers, revision/security и effects. Это выбор среза, не приёмка его ещё не подготовленных контрактов и не разрешение реализации.
- Владельцем настройки **g принят Physics**. Actual storage/data contract пока остаётся в WorldTerrainScalars; это выявленный ownership debt, не выполненный перенос. Пользователь самостоятельно отметит упущение в Physics. API-1 не меняет Physics-план или production types. Владение elevation_lapse_rate и magma_band_thickness остаётся отдельным OPEN вопросом.
- Предложение ограничить первую версию только секциями с существующими POJO пока **не принято**: пользователь подтвердил пункты 1 и 2, но не пункт 3. Legacy-секции остаются в inventory с собственными contract gates.

### Дополнительные поля: ownership по actual consumers; legacy scope (2026-11-02)

**Принято пользователем:** legacy `dict`-секции в текущем виде не поддерживаем новым settings API. Строки L в R4 остаются инвентарём предстоящей переработки, а не обязательством сделать compatibility adapters или raw passthrough. Их подключение возможно после новых owning typed contracts. Это не команда удалить действующие legacy routes/storage сейчас: удаление относится к отдельно разрешённой переработке/cutover. Сам формат JSON object не запрещён: existing typed blob POJO (например WorldHydrology) остаются в scope. Секции Time/World проектируются по своему новому контракту, а не через поддержку старого calendar dict.

| Поле | Actual evidence | Рекомендуемый владелец и target contract |
|---|---|---|
| elevation_lapse_rate | WorldTerrainScalars хранит optional float; canonical_defaults/resolved_elevation_lapse_rate дают 0.65. generators/climate/climateGeneratorService.py:162–167 читает через terrain_scalars, считает `round(base - lapse * (z / 100))`, затем clamp и rainfall. docs/tz_climate.md:916 и project_data_storage_tz.md:2600–2606 задают °C на 100 m, допускают отрицательное и нулевое значение | **Climate**, а не Physics/Terrain: это параметр модели изменения температуры с высотой. Предлагается включить в WorldClimateScalars и Climate public settings contract; перенести единственный default/resolution policy вместе с полем. Terrain поставляет высоту, не владеет climate lapse policy. Включить этот ownership debt в первый Climate design slice |
| magma_band_thickness | WorldTerrainScalars: optional int. generators/terrain/passes/columnFillPass.py:31–35 трактует None и <=0 как отсутствие; :77–78 включает только при closed_planet_grid; :159–170 создаёт указанное число z-слоёв ниже solid. docs/tz_terrain_generation.md:627,704 описывают геометрию magma band | **Terrain**: настройка генерации подземных слоёв, не физическая температура/вязкость магмы. Retain WorldTerrainScalars как existing owner POJO; public Terrain prepare описывает consequences для колонок/Pack и проверяет topology applicability. Physics/material properties не перемещаются сюда |

Рекомендации ownership выведены из source, **не отмечены пользовательской приёмкой**. Для g уже принято Physics; эти два поля не следует механически переносить вместе с g.

**Contract gaps для Climate lapse:** сохранить возможность negative/zero, единицы °C/100 m и единственный default; определить finite-value validation. Отличать SQL NULL-as-absence от explicit null в authored payload по resolver policy. Текущий optional type и fallback не являются автоматически утверждённой reset semantics нового API. Read возвращает resolved setting с publication source; prepare пересчитывает candidate/объявляет climate consequences без записи и самостоятельного rebake. Исключить повторную регистрацию одного wire key одновременно в Terrain и Climate; обновление WorldSlice projection, worldRow consumers и import/default parity — один будущий согласованный migration slice. Никаких DDL/URL изменений из этого исследования не следует.

**Contract gaps для magma thickness:** сейчас отрицательное значение молча выключает слой, а POJO не задаёт minimum. Target proposal: None/0 — отсутствие слоя по явно принятой owner policy; положительное целое — число z-слоёв; отрицательное — structured validation error, не silent reset. Это изменение legacy validation semantics требует отдельной приёмки. Связь с closed_planet_grid и новым topology mode должна быть проверена в Terrain contract: пока actual code использует legacy bool, нельзя заявлять их эквивалентность. Apply требует accepted Terrain/Pack lifecycle, не вызова column fill из settings route.

**Межплановые предложения, без правок:** Climate — ownership/default/resolver migration elevation_lapse_rate; Terrain — magma validation и topology applicability. Physics-план пользователь уточняет для g самостоятельно. Следующий документальный Climate срез включает lapse proposal вместе с существующими скалярами/реестрами. Ноды, код, production contracts и publication не менялись.

### Приёмка ownership и единая необходящаяся settings semantics (2026-11-02)

**Принято пользователем:** elevation_lapse_rate принадлежит Climate; перенос поля вместе с единственным default/resolver policy включается в документальный Climate slice. Magma_band_thickness пока остаётся Terrain; будущий владелец — геология, поддомен рельефа. Это не согласование изменения negative-value semantics magma: последнее уточнение пользователя подтверждало сохранение текущего положения до будущего домена.

**Принято общее правило для всех новых публичных settings contracts:** missing в partial update не меняет поле; explicit null допустим только согласно owning POJO policy и не означает универсальный reset; reset — отдельный typed intent, разрешённый лишь там, где owner поддерживает его. Create/whole-section replace используют full-model правила, а не patch missing semantics. Invalid не исправляется default. Поведение едино для transport/DAG/debug/import и внутренних callers при изменении тех же настроек. Пользователь отдельно потребовал отсутствие возможности обхода. Это целевой gate, а не уже обеспеченное свойство текущего legacy кода.

**Предложенный пользователем подход:** наследовать публичные настройки от общего интерфейса с этой семантикой. Интерфейс без реализации недостаточен: Protocol/ABC описывает форму методов, но не обеспечивает вызов validation и не закрывает прямой repository writer. Конкретная конструкция ниже — design proposal для проверки на Climate, не production class freeze.

- Общий typed public interface и общий implementation skeleton для preparation. Public entry фиксирует последовательность: принять intent с сохранённым presence → применить existing resolver/merge → проверить полный candidate → вызвать owning checks/consequences → вернуть typed prepared result. Domain extension points не переопределяют presence/reset semantics. Exact generics/signatures/files должны быть представлены на Climate B gate; не добавлять новый field registry или policy engine.
- Реализация общих semantics переиспользует resolve/WorldSlice/owning annotation policies. Defaults, null applicability и reset eligibility принадлежат конкретным POJO/owner contracts. Общий механизм не перечисляет домены, не вычисляет effects, не читает чужие repositories, не вызывает DAG и не публикует состояние. Это не WorldSettingsService.
- Typed intent сохраняет различие absent/value/null/reset до resolver. Запрещены defaults в transport, `exclude_none` или заполнение missing до owner boundary. Unknown fields и неподдержанный reset отклоняются структурированно. Reset не задаётся arbitrary string field path. Registry replacement и nested blob patch сохраняют явно объявленные owner semantics.
- Наследование/final-аннотация не являются security barrier в Python. Повторно используемый skeleton должен сопровождаться закрытием writer/caller boundary: routes → engine DAG → пользовательские ноды → public owner operations; никаких альтернативных update helpers с raw dict. Согласованный acceptance path заново проверяет actor/base и candidate invariants через тот же механизм; произвольный caller-created prepared object не является разрешением записи.
- Snapshot/domain handlers остаются единственным принятым runtime acceptance path; settings preparation не получает произвольный commit callback. Import/create/restore/migration имеют собственный lifecycle, но не получают права обходить owning invariants или менять missing/null semantics под видом helper. Exact applicability для исторических schema versions фиксируется их owning contract; текущие defaults не должны молча переписывать историю.

**Доказательство отсутствия поддерживаемого обхода — обязательный gate:** inventory всех writers/callers выбранных полей (HTTP, debug, import, CLI, DAG, внутренние services); отсутствие direct writes вне принятого acceptance path после cutover; dependency/architecture checks для запрещённых imports/calls; contract tests по каждому concrete public implementation на missing/null/reset, неизвестные поля, invalid без default, no-write preview, stale/forged prepared result и atomic failure. Проверять вложенные paths, а не только наследование. Все новые реализации обязаны проходить одну conformance suite с owner-specific допустимыми/недопустимыми значениями. Это гарантия поддерживаемых application paths, не обещание защитить БД от произвольного привилегированного SQL.

Legacy dict-секции не адаптируются в новый API. Существующий legacy WorldService не становится допустимым fallback для перенесённой настройки: в атомарном cutover выбранного поля закрываются все его обходные writers, сохраняя неперенесённые области до их отдельных работ. До этой проверки gate остаётся OPEN, даже если новый интерфейс и его tests готовы.

Следующий допустимый шаг: на Climate документально предъявить concrete interface/skeleton/owner implementation и exact I/O/Error, reuse existing resolver, все writer seams и conformance criteria. Ноды пишет пользователь; код, bindings, правила, другие планы и production contracts сейчас не изменяются.

**Приёмка подхода пользователем (2026-11-02):** согласованы общий public interface + общая реализация missing/null/reset через existing resolver, owning POJO defaults/validation, запрет переопределения общей семантики и закрытие альтернативных writers с общей conformance suite. Это приёмка архитектурного подхода, а не exact signatures/files или доказательство уже обеспеченной защиты от обхода. Concrete design проверяется на Climate; прежний документальный stop boundary сохраняется.

## API-1-C1 — конкретный Climate settings contract proposal (2026-11-02)

[1. Целевая архитектура C1](./api-1-climate-c1-d1.md#1-целевая-архитектура) — владельцы World/Time/Climate/Weather, оркестрация DAG, чтение, запись и расширение сезонного payload.

[C1-EXT: архитектура количественных показателей Environment](./api-1-climate-c1-d1.md#c1-ext-архитектура-количественных-показателей-environment) — декларация мира, reader владельца факта, проекция единиц и передача результата потребителям через DAG.

**Уточнение границы Climate / Weather.** Climate поставляет климатические поля и сезонную температуру. Weather владеет weather_type_registry и определяет погоду сцены по выборке Climate. Опубликованный просмотр объединяет оба результата одной R. Для редактирования World.open_climate_draft возвращает последнюю авторскую версию с EditBase. World.read_season_effects поставляет сезонные входы для сцены на точной R. [Публичные операции для DAG, входы, выходы, ошибки и открытые привязки](./api-1-climate-c1-d1.md#публичные-контракты-climate-и-weather-для-dag).

Кандидаты отражены в [реестре публичных методов генератора](./generator_public_method.md#climate-и-weather--публичные-операции-для-dag). До исполнения требуется закрыть [результаты проверки правил и legacy inventory C1](./api-1-climate-c1-d1.md#проверка-плана-и-legacy-inventory).

**Согласованные решения D1 (2026-11-08).** Read включает девять скаляров и оба реестра, guarded update меняет скаляры. Десятое поле появится после отдельного переноса lapse. R — publication_id выбранного мира. Каждый writer сохраняет только колонки своей операции. В runtime Snapshot владеет транзакцией, в которой проверяются ожидаемая публикация и версия входов Materials. До старта игры редактор может сохранить авторскую ревизию до bake и открыть её повторно. Bake запускается отдельно. Сохранение черновика требует собственного контракта World с проверкой авторской ревизии. [Контракты, граница атомарности и первый срез](./api-1-climate-c1-d1.md).

Для сохранения черновика согласована одна авторская ревизия на девять скаляров Climate. World проверяет её вместе с ревизиями прочитанных климатических реестров и использованных данных Materials. Независимые правки других объектов мира допускают параллельное сохранение.

До старта gameplay редактор настроек может многократно сохранять изменения в первую рабочую ревизию мира, в том числе после bake. При повторном открытии видны последние сохранённые значения. Проверка версий объектов защищает от перезаписи из устаревшей формы; bake читает закреплённые входы. В D1 описан общий процесс создания, обновления и импорта мира.

[Аудит редактора мастера, контракты open/preview/save и переходы первой рабочей ревизии](./api-1-climate-c1-d1.md#редактор-мастера-фактические-пути-и-контракт-первой-рабочей-ревизии). Сегодня страница настроек мира — заглушка; обычный пользовательский импорт создаёт копию. Сохранение формы проектируется как обновление выбранного UID.

**Статус:** DOCUMENT PROPOSAL, exact foreign publication/security seams OPEN; реализация и ноды не разрешены. Первый срез — Climate, включая принятый перенос elevation_lapse_rate. Данный раздел уточняет generic templates R2/R3 и не объявляет их placeholders existing types.

### Проверенные actual contracts и существенные findings

- `WorldClimateScalars` содержит девять scalar/nested полей; будущий десятый — elevation_lapse_rate из Terrain. `SeasonTempOffsets` содержит winter/spring/summer/autumn. DefaultWhenMissing и nullable типы уже заданы owning POJO. `canonical_defaults()` даёт peak -40/45 и offsets -12/0/8/-4, тогда как missing при обычном создании модели даёт peak None и offsets 0. **Reset не может произвольно выбирать между этими источниками.**
- `ClimateZoneEntry`: system_climate и пять optional int полей base_temperature, typical_elevation_z, base_rainfall, temperature_variance, rainfall_variance. `WorldClimateZoneRegistry` — RootModel списка, canonical_defaults и canonical_engine различаются. Existing `registry.profile_for` дополняет nullable entry полями enum/fallback profile; неизвестный ключ может привести к temperate fallback. Это отдельная effective-profile semantics, не повод «исправлять» неверную ссылку на write.
- `WeatherTypeEntry`: system_weather, display_weather, temp_min/max, rainfall_min, priority, travel_modifier, need_modifiers, glossary_ref. WorldWeatherTypeRegistry.sorted_by_priority лишь сортирует; наличие entry_for не доказывает unique keys или обязательность clear. Требования unique/reference/fallback должны быть явно закреплены owner validation.
- Scalar/entry модели имеют extra="ignore"; resolve._patch_fields наследует это. Запрет неизвестных полей нового settings API **не обеспечен** текущими POJO. Требуется общий shape guard по существующей model schema (включая nested fields/aliases), без ручного второго каталога полей. Открытые maps вроде need_modifiers нельзя принимать за неизвестные POJO attributes.
- WorldClimateScalars.resolve_peak_bounds меняет местами обратные границы. Новый write proposal должен отклонять invalid peak pair, а не молча переставлять. Это proposed изменение validation, не уже принятое пользователем поведение.
- `SourcePublicationGuard.require_fresh` существует, но сравнивает SurfacePlanningView с повторным capture world/locations/mountain templates. Его нельзя переименовать в готовую settings revision: coverage Climate/weather/material refs и атомарность settings acceptance этим не доказаны.

### Конкретные public methods и typed payloads

Все имена ниже proposed. Existing public dedicated Climate settings API отсутствует; existing get/update — WorldService, existing typed reads — worldRow.climate_scalars/climate_zones/weather_types. Для чтения DAG вызывает Climate.read_settings и Weather.read_weather_rules независимо. Для подготовки DAG напрямую вызывает IClimateSettingsPrepareOpenPipeline.prepare_change; ClimateSettingsPrepareOpenPipeline реализует этот интерфейс. Общий механизм фиксирует preparation semantics, не реализует Climate policy.

| Метод | Input | Output | Domain errors |
|---|---|---|---|
| `Climate.read_settings(request: ReadClimateSettings)` | world_uid и точная публикация R | R, скаляры и зоны Climate; DAG отдельно получает WeatherRulesView от Weather | WorldNotFound, PublicationUnavailable, InvalidStoredSettings |
| `prepare_initial(request: PrepareInitialClimateSettings)` | world_uid; initialization context/actor; полные скаляры и зоны Climate | PreparedClimateSettings со candidate/consequences; без записи | InvalidClimateSettings, InvalidReference, Forbidden, UnsupportedLifecycle |
| `prepare_change(request: PrepareClimateSettingsChange)` | world_uid; expected revision; actor; operation_id; PatchClimateScalars и MaterialRegistryView от DAG | PreparedClimateSettings; DAG возвращает preview из результата либо передаёт его на acceptance | те же + RevisionConflict, DuplicateChange, UnsupportedChange |

`ClimateSettingsState` — форма данных для двух явно различных оснований чтения: `scalars:WorldClimateScalars` и `zones:WorldClimateZoneRegistry` от Climate, `weather:WorldWeatherTypeRegistry` от Weather. Для опубликованного просмотра DAG соединяет результаты по одной R. Для формы редактирования World возвращает состояние и EditBase из одного авторского снимка. Nullable authored fields могут требовать runtime fallback. Effective profiles, если понадобятся клиенту, должны быть отдельным typed результатом существующего climate resolve; не materialize defaults в storage при чтении. Initial input уже полный POJO: absent/default interpretation выполняет тот же public boundary до construction; API не подставляет значения. [Граница CRUD, OpenPipeline и публикации](./api-1-climate-c1-d1.md#поверхность-доменов-и-ответственность-dag).

**Исходная карта изменений C1 по владельцам.** PatchClimateScalars — согласованный первый срез. Операции с записями зон относятся к Climate, операции с типами погоды — к Weather. При детализации будущих команд каждый владелец определяет свой закрытый typed intent.

| Variant | Concrete payload / semantics |
|---|---|
| PatchClimateScalars | typed присутствующие поля девяти текущих scalar settings; отсутствующие остаются неизменными; SeasonTempOffsets patch сохраняет отсутствующие seasons |
| ReplaceClimateZoneRegistry | WorldClimateZoneRegistry; полная замена authored списка |
| UpsertClimateZone | ClimateZoneEntry; полная запись по system_climate, не неявный entry patch |
| RemoveClimateZone | RegistryKey[WorldClimateZoneRegistry]; отсутствие ключа → structured not-found, не silent success |
| ReplaceWeatherTypeRegistry | WorldWeatherTypeRegistry; полная замена authored списка |
| UpsertWeatherType | WeatherTypeEntry; полная запись по system_weather |
| RemoveWeatherType | RegistryKey[WorldWeatherTypeRegistry] |

Reset **не входит в первый Climate union**: общий контракт различает его и отвергает unsupported reset, но owner ещё не выбрал import defaults versus canonical preset. Это сохраняет принятое «reset только где owner поддерживает», не подменяет reset=null. В дальнейшем отдельный concrete ResetClimate… intent потребует explicit owner semantics/приёмки. Whole scalar replacement также не нужен для первого update среза; initial отдельно от patch.

**Presence representation proposal:** общий `FieldChange[T] = Keep | SetValue[T]`, оба variants с закрытым discriminator, без default T=None. Для nullable поля T включает None; omission декодируется в Keep, explicit null — SetValue(None). PatchClimateScalars имеет ровно owning поля и typed FieldChange соответствующего field type; season offsets — отдельный typed nested patch. Patch shape/schema должна выводиться из owning model либо проверяться на точное соответствие ей при contract validation; ограничения не копируются в transport. Это не runtime field policy registry. Exact механизм derivation требует технического design review: не выдавать существующий resolve_patch(dict) за уже существующий typed patch POJO.

Не допускаются две записи одного scalar/registry key в одной команде, replace и entry operations одного registry вместе; DuplicateChange вместо зависимости результата от порядка. Изменение scalar default_climate_zone и upsert соответствующей зоны допускается в одной команде, validation — по итоговому candidate. Climate+Materials batch не входит в этот single-owner union.

**Output shape:** ClimateSettingsPreview(source, candidate: скаляры и зоны Climate, issues:tuple[FieldPathError,...], consequences:ClimateConsequences); PreparedClimateSettings дополнительно carries operation_id и fingerprint исходного intent. Ошибочный candidate не возвращается как валидный prepared result. Эти outcomes не publication receipts и не авторизация commit. Idempotent accepted receipt принадлежит acceptance, не pure prepare. Возвращаемые mutable RootModel lists должны быть изолированы от исходного capture; frozen внешняя оболочка сама по себе не гарантирует deep immutability.

**Error union proposal:** ClimateSettingsFailure с closed ClimateSettingsErrorCode = WORLD_NOT_FOUND, FORBIDDEN, SOURCE_UNAVAILABLE, REVISION_CONFLICT, INVALID_SETTINGS, INVALID_REFERENCE, ENTRY_NOT_FOUND, DUPLICATE_CHANGE, UNSUPPORTED_CHANGE, UNSUPPORTED_LIFECYCLE; issues — existing tuple[FieldPathError,...]. InvalidStoredSettings использует INVALID_SETTINGS с source context, не default repair. Infrastructure IO/cancellation/unknown acceptance outcome не маскируются domain validation. HTTP mapping отдельно; новые HTTP codes/URLs этим не вводятся.

### Общая реализация и Climate ownership

Proposed общий `ISettingsPreparation[Request,Result]` и implementation skeleton `SettingsPreparationPipeline` в `application/settingsContracts/preparation.py`. Общие presence types — `dataModel/settingsContracts/presence.py`. Это техническая инфраструктура, **не** сервис WorldSettings и не registry всех owners. Сам public Climate интерфейс остаётся owner-owned; наследование skeleton распространяется на preparation, не навязывает CRUD read классу фиктивные mutation methods.

Фиксированная последовательность: shape/presence check → verified source/actor → owner intent application на detached candidate через existing resolve_patch/resolve_model → owner final validation/references → owner consequences → common typed outcome. Missing/null не интерпретируются повторно owner hooks. Skeleton не знает Climate поля/defaults и не выбирает чужие операции. Read использует тот же schema resolve, но не preparation и не repair. Инициализация имеет full-model policy; PATCH — partial policy. Validate_only меняет outcome, не ослабляет validation.

Проверки владельцев по переданным DAG данным:

- Разрешить девять полей существующего WorldClimateScalars; elevation_lapse_rate доступен только после отдельной миграции; значения nullable проходят existing annotation policy. Для lapse finite float, включая zero/negative; единица °C/100 m. Default остаётся 0.65 у Climate POJO после accepted migration.
- Проверять peak ordering после merge при двух заданных границах по CL-5; workers сохраняет текущий тип int или null. Не выдавать эти новые constraints за уже принятые изменения.
- Climate проверяет уникальность system_climate; default_climate_zone существует в допустимом resolved registry; precipitation_liquid — существующий liquid material по typed material contract. Проверить ссылки из accepted dependent state до удаления зоны. Registry fallback policy (engine entries, custom entries, clear) должна быть принята по owner schema; нельзя использовать fallback_profile для сокрытия invalid write.
- Weather проверяет уникальность system_weather; ссылки Need/glossary проверяются через согласованный typed captured dependency, не новый lookup по строке в общем helper. Пока точные reference contracts не установлены, weather write freeze OPEN; scalar read/prepare design от этого не обязан ждать весь gameplay domain.

### Effects и минимальный source/acceptance seam

ClimateConsequences proposed: typed признаки `climate_surface_changed` и `execution_policy_changed` плюс точный dependency/read fingerprint; это owner output, не список исполняемых задач. Execution cap alone не означает rebuild physical map. Zones/default/poles/lapse/peak/season/precipitation требуют проверки зависимых climate plans, temperatures/rainfall/landcover; Weather отдельно возвращает `runtime_weather_rules_changed` для потребителей погоды через DAG. Concrete invalidation applicability определяет принятый Climate/Pack lifecycle; общая инфраструктура не превращает признаки в команды.

Foreign requests для freeze (не новые production ports):

1. DAG получает снимки публичными чтениями владельцев и объединяет одну базу: world UID, lifecycle, ClimateState, material/reference inputs, base settings revision и версии всех read dependencies. Не смешивать World SQL latest и unrelated Pack hash. Existing SourcePublicationGuard — reuse candidate, coverage надо доказать.
2. Trusted authorization capability для read/prepare/acceptance; identity из запроса не доказательство прав. Не проектировать actor bool.
3. Acceptance перепроверяет revision/authority/candidate в одной UOW, записывает operation receipt и применяет owner consequences через applicable domain handlers. До gameplay — согласованный World/Pack publication; runtime — Snapshot acceptance. API и preparation не получают repo writer. Нельзя пометить подготовленный результат «accepted» до этой границы.

Ни один из этих foreign types не подменяется `str` или `Any` ради компилируемого интерфейса. Поэтому таблица public methods конкретизирует owner shape, но общий contract freeze остаётся OPEN по точным source/authority types. Ноды пользователя зависят от принятого public freeze, а не наоборот.

### Class / factory / file / import map

| Existing | Target proposal | Disposition |
|---|---|---|
| dataModel/climate/worldClimateScalars.py, climateZone/*, weatherType/* | Сохранить owning POJO; перенести lapse из terrain/worldTerrainScalars.py в Climate | retain + targeted replace; один WorldSlice key owner, без второго default |
| WorldService.get_by_id/update/prepare_import | Порт IClimateSettingsPrepareOpenPipeline в application/worldData/climate/ports/settingsPrepareOpenPipeline.py; реализация ClimateSettingsPrepareOpenPipeline в application/worldData/climate/settings/prepareOpenPipeline.py. DI связывает их в composition root. | Нода вызывает порт; импорт реализации и legacy fallback дают FAIL. [Карта абстракций и критерии](./api-1-climate-c1-d1.md#что-публично-и-где-заканчивается-абстракция) |
| Нет settings command/result POJO | dataModel/climate/settings/{commands,state,results,errors}.py | proposed Climate-only closed types; imports existing POJO/RegistryKey/FieldPathError |
| resolve.py, worldSlices.py, worldSliceMerge.py | retain resolver/schema inventory; application/settingsContracts/preparation.py + dataModel/settingsContracts/presence.py | common skeleton, без Climate imports, domain tables/defaults |
| core/container/worldData.py | отдельные фабрики reader и `make_climate_settings_prepare_pipeline()`, явная сборка capture/security dependencies | composition only; exact injected foreign contracts OPEN |
| app/api routes | transport → согласованный engine invocation; пользовательская нода → публичный reader либо IClimateSettingsPrepareOpenPipeline.prepare_change | retain URLs до приёмки; route не импортирует concrete pipeline/repo |

Domain public interface не импортирует app/api или engine nodes. Общий skeleton не импортирует concrete Climate; dependency injection связывает owner implementation. Snapshot handler imports public owner validation/prepared contract, не вызывает route. Exact filenames — proposed, не уже созданные файлы.

### Реальные writers и обходы: обязательная closure

| Existing path | Риск / действие при Climate cutover |
|---|---|
| worlds.update → WorldService._update/_save; create/import_from_json → repo create/upsert | Generic World write принимает Climate поля. После перехода маршрутизировать выбранную операцию на accepted path; запретить Climate bypass в старом update, initial/import проводить через тот же owner validation |
| WorldBundleService._prepare_bundle → normalize_world + WorldService.prepare_import; далее copy import | Existing pure preparation не заменяет settings acceptance. Проверить final copy/import writer и initialization lifecycle до cutover; не запретить корректный import просто из-за другого входа |
| WorldService.repair_defaults → ensure_world_climate_defaults → repo.update | Скрытый Climate/Materials rewrite; не вызывать из новых read/prepare. После cutover отдельная принятая repair operation либо удалить обход; silent repair не validation |
| raceService._ensure_registry/_unbind_registry; worldPerkService аналогично → _worlds.update(World) | **Whole-row lost update:** даже чужая registry mutation может перезаписать Climate stale values. Запрет только climate-specific routes недостаточен. Нужна атомарная защищённая partial write ownership либо общий guarded row revision для всех таких writers |
| templateLibrary/packs/write/writeExecutor.py → _worlds.update(World) | Тот же whole-row overwrite риск; inclusion в writer closure, не перенос библиотечных алгоритмов в Climate |
| SqliteWorldRepository.update → BaseRepository.save; upsert → INSERT OR REPLACE | Нет expected revision; потенциальная запись всей строки. Repository boundary и acceptance должны исключить незаметное изменение защищённых Climate columns любым caller; интерфейс/final не решает это |

Этот список — подтверждённые пути, не заявление полного SQL audit. До cutover обязательны поиск всех SQL UPDATE/INSERT/REPLACE worlds и aliases repo methods, проверка bundle-copy/finalizers/migrations/scripts. Общий guarded storage seam не содержит domain validation/defaults; ownership protected write-set извлекается из существующего WorldSlice/schema после согласования revision mechanics, не заводится второй field registry. Legacy других областей не переписывается под видом Climate, но возможность затереть Climate ими должна быть закрыта до принятия cutover.

### Атомарные документальные/будущие migration этапы

1. **C1-schema:** согласовать patch representation и ошибки, lapse ownership (уже принято), новые constraints peak/workers/registry policy (ещё proposal), отсутствие reset в первом union. Acceptance: field-by-field presence/null matrix на actual POJO; canonical versus import defaults не смешиваются.
2. **C1-read/prepare:** замкнуть exact source/authority и common skeleton design; initial/update/preview проходят один resolver. Gate: no repair/write/task/version allocation; invalid не превращается в candidate. Не ждать весь Time или весь GEN.
3. **C1-storage:** доказать CAS/read-set/partial write seam на World строке, включая чужие full-row writers; prepared forgery и race сценарии закрыты. Это ограниченный World storage prerequisite, не требование завершить весь Snapshot.
4. **C1-acceptance:** согласованные Climate consequences + применимые Pack/Snapshot handlers + пользовательская DAG-нода. Unsupported lifecycle отказывается явно. Node design/implementation принадлежит пользователю.
5. **C1-cutover:** только отдельной командой; replacement invocation, migration lapse ownership и закрытие bypass атомарны по выбранной операции. Existing URL parity отдельно; нет fallback legacy writer. Weather/references можно выделить в следующий срез, не объявляя весь domain write готовым.

**Conformance scenarios:** omitted scalar не меняется; explicit null сохраняет/отклоняет owning policy; unsupported reset отказ; unknown nested season отказ; malformed registry не canonical fallback; defaults при initial и patch различаются намеренно; duplicate commands отказ; zone add + default switch валидируются вместе; удаление используемой зоны отказ; concurrent material ref change конфликт; preview не repair; stale race/perk row не затирает Climate; forged prepared result не acceptance authority; no-op не создаёт ненужный publication (точная receipt policy foreign); failure до commit сохраняет старую publication, unknown outcome после commit разрешается по operation identity.

**Verdict:** исследованный owner-specific proposal готов к обсуждению, не CODE-READY. Найдены blockers к «необходящемуся» контракту: ignored unknown fields, неоднозначный reset default, missing settings-wide revision/authority, full-row writers чужих доменов и незамкнутый weather/reference lifecycle. Следующий допустимый шаг — принять конкретные C1-schema решения и закрыть exact foreign seams документально. Межплановые предложения: World storage guarded updates; Climate owning validation/default migration; Snapshot applicable acceptance. Другие планы/rules, production POJO/ports, nodes/bindings, URLs и код не изменены.

## API-1-A2 — передача настроек в DAG по полям (2026-11-03)

Сверка по работающим объявлениям моделей: 110 полей dataclass World, 36 WorldSlice, 51 совпадающих колонок. 59 полей строки не входят в WorldSlice. Ключи срезов вне World: `district_template_registry`, `location_mood_registry`, `road_settings`. Для последних требуется подтвердить источник конкретного мира и обратное сохранение до подключения записи. Наличие canonical defaults само по себе не доказывает сохранение авторской настройки.

Для всех редактируемых строк предлагается единое правило передачи. Нода вызывает публичный read владельца для конкретного world_uid и согласованной публикации. Вход следующей операции явно принимает нужную часть типизированного результата и его версию. Если потребителю нужен вычисленный профиль, владелец отдельно определяет преобразование authored → effective. Потребитель не перечитывает latest World. Чтения из разных публикаций отвергаются до выполнения. Это требование к будущей связи Output → Input. Указанный accessor или вызов Python подтверждает лишь существующую зависимость, а не готовый DAG binding. Имена нод и их компоновку определяет пользователь.

### Типизированные источники и потребители

| Область существующей модели | Поля World или bundle | Output владельца для DAG | Существующее чтение и пример места вызова |
|---|---|---|---|
| worldPack | `terrain_pack_hash`, `terrain_pack_path` | `WorldPackMetadata` | WorldSlice, отдельный вызов accessor не установлен |
| worldPack | `world_map_cells_per_tile` | `WorldMapResolutionSettings` | WorldSlice, отдельный вызов accessor не установлен |
| worldPack | `fine_cells_per_map_cell` | `WorldGridSettings` | grid_settings() |
| climate | `climate_local_influence_fraction`, `climate_parallel_workers`, `climate_pole_mode`, `climate_pole_preset`, `climate_temperature_peak_max`, `climate_temperature_peak_min`, `default_climate_zone`, `precipitation_liquid`, `season_temp_offsets` | `WorldClimateScalars` | climate_scalars() → climateRuntimeAssembler:33 |
| terrain | `closed_planet_grid`, `elevation_lapse_rate`, `g`, `magma_band_thickness`, `map_subsurface_depth`, `terrain_chunk_columns`, `terrain_parallel_workers`, `world_topology_mode`, `z_max`, `z_min` | `WorldTerrainScalars` | terrain_scalars() → climateGeneratorService:163 |
| terrain | `relief_grade_obstacle_policy` | `WorldReliefGradeObstacleScalars` | relief_obstacle_scalars() |
| economy | `economic_tier_registry` | `WorldEconomyTierRegistry` | economic_tiers() → locationScope:54 |
| materials | `material_registry` | `WorldMaterialRegistry` | materials() → precipitation:37 |
| resources | `resource_type_registry` | `WorldResourceTypeRegistry` | resource_types() → subjects:177 |
| flora | `crops_registry` | `WorldCropsRegistry` | crops() → subjects:192 |
| livestock | `livestock_registry` | `WorldLivestockRegistry` | livestock() → subjects:75 |
| terrain | `terrain_registry` | `WorldTerrainRegistry` | terrain() → heightmapPass:23 |
| climate | `climate_zone_registry` | `WorldClimateZoneRegistry` | climate_zones() → registry:45 |
| worldEnvironment | `world_environment` | `WorldEnvironmentSettings` | world_environment() |
| hydrology | `hydrology` | `WorldHydrology` | hydrology() → seaLevelPolicy:12 |
| terrainMasks | `terrain_masks` | `WorldTerrainMasks` | terrain_masks() → heightmapPass:22 |
| locations | `barrier_template_registry` | `WorldBarrierTemplateRegistry` | barrier_templates() → reliefWorldRefValidation:24 |
| locations | `city_size_registry` | `WorldSettlementSizeRegistry` | city_sizes() → footprint:68, settlement_sizes() |
| locations | `settlement_specialization_registry` | `WorldSettlementSpecializationRegistry` | settlement_specializations() → districts:369 |
| locations | `district_template_registry` | `WorldDistrictTemplateRegistry` | district_templates() → footprint:206 |
| locations | `district_zone_preference` | `WorldDistrictZonePreference` | district_zone_preference() → placement:179 |
| roads | `road_settings` | `WorldRoadSettings` | road_settings() → connectionPolicy:38 |
| connections | `connection_type_registry` | `WorldConnectionTypeRegistry` | connection_types() → districtAssembler:192 |
| locations | `transition_type_registry` | `WorldTransitionTypeRegistry` | transition_types() → settlementOutdoorPackingJob:261 |
| locations | `location_type_registry` | `WorldLocationTypeRegistry` | location_types() → locationScope:42 |
| lore | `lore_registry` | `WorldLoreRegistry` | lore() |
| climate | `weather_type_registry` | `WorldWeatherTypeRegistry` | weather_types() |
| terrain | `terrain_category_registry` | `WorldTerrainCategoryRegistry` | terrain_categories() |
| locations | `room_type_registry` | `WorldRoomTypeRegistry` | room_types() |
| locations | `location_mood_registry` | `WorldLocationMoodRegistry` | location_moods() |
| races | `race_template_registry` | `WorldRaceTemplateRegistry` | WorldSlice, отдельный вызов accessor не установлен |
| perks | `perk_template_registry` | `WorldPerkTemplateRegistry` | WorldSlice, отдельный вызов accessor не установлен |
| locations | `purpose_pack_registry` | `WorldPurposePackRegistry` | purpose_pack_registry() |
| locations | `purpose_packs` | `WorldPurposePacks` | purpose_packs() |
| terrain | `canal_template_registry` | `WorldCanalTemplateRegistry` | canal_templates() → reliefWorldRefValidation:50 |
| terrain | `relief_pick_policy` | `WorldReliefPickPolicy` | relief_pick_policy() → refFields:118 |

Служебный WorldPackMetadata передаётся только как metadata. У WorldTerrainScalars текущий путь хранения расходится с принятым ownership: g → Physics, elevation_lapse_rate → Climate, magma_band_thickness → Terrain до выделения геологии. Совместная выдача сырой строки World не закрывает эти три доменных контракта. Для World-owned времени закреплена отдельная связь WorldTimeSettings и calendar bindings → Time input в [Time §28](./time-domain.md). Historical и current read должны сохранять привязку к запрошенной версии.

### Остаток строки World — disposition каждого поля

Группы владельцев и назначение приведены в R4. Здесь зафиксировано решение именно о передаче через DAG. Для scalar без owning schema нужен самостоятельный контракт и проверенный consumer. Raw dict-секции исключены до переработки.

| Статус передачи | Поля |
|---|---|
| Legacy dict, исключено | `action_formulas`, `body_schema_registry`, `caves`, `cell_state_registry`, `character_trait_registry`, `colour_registry`, `combat_settings`, `constitution_tables`, `danger_level_registry`, `derived_formulas`, `faction_relation_type_registry`, `intensity_level_registry`, `location_state_registry`, `material_category_registry`, `material_use_type_registry`, `muscle_tables`, `narrative_type_registry`, `npc_fields`, `npc_goal_type_registry`, `npc_needs_registry`, `npc_target_type_registry`, `player_fields`, `registry_migrations`, `resist_schema`, `respawn_type_registry`, `road_type_registry`, `skill_schema`, `slots`, `stat_migrations`, `stat_schema`, `tag_registry`, `texture_registry`, `world_bounds`, `wound_type_registry` |
| Legacy list, требуется owner contract | `action_registry` |
| World → Time по новому контракту §28 | `calendar` |
| Metadata / lifecycle | `created_at`, `current_tick`, `schema_version`, `terrain_pack_version`, `world_map_version`, `world_uid` |
| Scalar, typed public operation OPEN | `default_passage_height`, `faint_check_formula`, `faint_threshold`, `grid_bbox_padding`, `hp_enabled`, `measurement_system`, `name`, `narrative_language`, `overload_penalty_formula`, `sleep_penalty_formula`, `stat_conflict_mode`, `trait_change_log_threshold`, `volume_enabled`, `weight_enabled`, `wound_death_formula`, `wounds_enabled` |
| Library attachment operation | `library_pins` |

### Поля вложенных контрактов

Ниже — снимок validation schema из тех же 36 POJO с wire aliases. Именованные типы раскрыты один раз для всех мест использования. Тип элемента списка и варианты union задают дальнейший путь внутри настройки. Словари со свободными ключами остаются картами. Условия допустимости, defaults и ограничения остаются у POJO. Для всех полей строки действует правило передачи родительского результата выше. Отдельный вход ноды нужен только при наличии операции, использующей это поле.

| Контракт данных | Wire-поля и типы либо элементы корня |
|---|---|
| `AnchorRadiusShape` | `edge_noise: EdgeNoise / null`, `kind: string`, `anchor_uid: string`, `radius: integer` |
| `AtmosphereGasComponent` | `system_material: WorldEnvironmentSettings.StrictOnWire_MaterialKey_`, `fraction: WorldEnvironmentSettings.StrictOnWire_Annotated_float__FieldInfo_annotation_NoneType__required_True__metadata__0__0____PydanticGeneralMetadata_allow_inf_nan_False_____` |
| `BarrierTemplateEntry` | `system_type: WorldBarrierTemplateRegistry.StrictOnWire_RegistryKey_WorldBarrierTemplateRegistry__`, `glossary_ref: WorldBarrierTemplateRegistry.DefaultWhenMissing_Union_str__NoneType__`, `wall_material: WorldBarrierTemplateRegistry.DefaultWhenMissing_Union_MaterialPick__NoneType__`, `height_levels: WorldBarrierTemplateRegistry.DefaultWhenMissing_Union_IntMinMax__NoneType__`, `gates: WorldBarrierTemplateRegistry.DefaultWhenMissing_Union_IntMinMax__NoneType__`, `towers: WorldBarrierTemplateRegistry.DefaultWhenMissing_Union_IntMinMax__NoneType__`, `width_cells: WorldBarrierTemplateRegistry.DefaultWhenMissing_int__Ge_ge_1_` |
| `BboxShape` | `edge_noise: EdgeNoise / null`, `kind: string`, `x_min: integer`, `y_min: integer`, `x_max: integer`, `y_max: integer` |
| `CanalObstaclePolicyRule` | `to_canal_cut_enable: WorldReliefPickPolicy.StrictOnWire_bool_`, `entities: WorldReliefPickPolicy.StrictOnWire_list_CanalObstacleEntity___MinLen_min_length_1_`, `canal_ref: WorldReliefPickPolicy.DefaultWhenMissing_Union_str__NoneType__` |
| `CanalStructureSpec` | `structure_refs: WorldCanalTemplateRegistry.DefaultWhenMissing_list_str__` |
| `CanalTemplateEntry` | `system_type: WorldCanalTemplateRegistry.StrictOnWire_str_`, `earthen_canal: WorldCanalTemplateRegistry.DefaultWhenMissing_Union_bool__NoneType__`, `structure: WorldCanalTemplateRegistry.DefaultWhenMissing_Union_CanalStructureSpec__NoneType__` |
| `ClimateZoneEntry` | `system_climate: WorldClimateZoneRegistry.StrictOnWire_str_`, `base_temperature: WorldClimateZoneRegistry.DefaultWhenMissing_Union_int__NoneType__`, `typical_elevation_z: WorldClimateZoneRegistry.DefaultWhenMissing_Union_int__NoneType__`, `base_rainfall: WorldClimateZoneRegistry.DefaultWhenMissing_Union_int__NoneType__`, `temperature_variance: WorldClimateZoneRegistry.DefaultWhenMissing_Union_int__NoneType__`, `rainfall_variance: WorldClimateZoneRegistry.DefaultWhenMissing_Union_int__NoneType__` |
| `ConnectionTypeEntry` | `system_connection_type: WorldConnectionTypeRegistry.StrictOnWire_RegistryKey_WorldConnectionTypeRegistry__`, `display_name: WorldConnectionTypeRegistry.StrictOnWire_str_` |
| `ConnectionTypeKey` | `string` |
| `CorridorShape` | `edge_noise: EdgeNoise / null`, `kind: string`, `path: list[tuple[integer, integer]]`, `width: integer` |
| `CropsTypeEntry` | `system_crop: WorldCropsRegistry.StrictOnWire_str_`, `crop_kind: WorldCropsRegistry.StrictEnumOnWire_CropKind_`, `display_name: WorldCropsRegistry.DefaultWhenMissing_Union_str__NoneType__`, `glossary_ref: WorldCropsRegistry.DefaultWhenMissing_Union_str__NoneType__` |
| `DeclaredBasin` | `placement_specificity: WorldHydrology.DefaultWhenMissing_Union_Specificity__NoneType__`, `location_uid: WorldHydrology.StrictOnWire_str_`, `footprint: WorldHydrology.StrictOnWire_Annotated_Union_BboxShape__EllipseShape__PolygonShape__AnchorRadiusShape__CorridorShape___FieldInfo_annotation_NoneType__required_True__discriminator__kind____`, `kind: WorldHydrology.StrictOnWire_BasinKind_`, `liquid: WorldHydrology.DefaultWhenMissing_StrictOnWire_MaterialKey__`, `floor_z: WorldHydrology.StrictOnWire_int_`, `z_water_level: WorldHydrology.DefaultWhenMissing_Union_int__NoneType__`, `rim: WorldHydrology.DefaultWhenMissing_Union_HydrologyBands__NoneType__` |
| `DeclaredCoastline` | `placement_specificity: WorldHydrology.DefaultWhenMissing_Union_Specificity__NoneType__`, `location_uid: WorldHydrology.StrictOnWire_str_`, `purpose: WorldHydrology.DefaultEnumWhenMissing_CoastlinePurpose_`, `target_source_uid: WorldHydrology.DefaultWhenMissing_Union_EntityUid__NoneType__`, `kind: WorldHydrology.StrictOnWire_BasinKind_`, `liquid: WorldHydrology.DefaultWhenMissing_StrictOnWire_MaterialKey__`, `closed: WorldHydrology.DefaultWhenMissing_bool_`, `water_side: WorldHydrology.DefaultWhenMissing_Union_WaterSide__NoneType__`, `path: WorldHydrology.DefaultWhenMissing_tuple_HydrologyWaypoint__________` |
| `DeclaredLake` | `placement_specificity: WorldHydrology.DefaultWhenMissing_Union_Specificity__NoneType__`, `location_uid: WorldHydrology.StrictOnWire_str_`, `liquid: WorldHydrology.DefaultWhenMissing_StrictOnWire_MaterialKey__`, `shoreline: WorldHydrology.DefaultWhenMissing_tuple_HydrologyWaypoint__________` |
| `DeclaredRiver` | `location_uid: WorldHydrology.StrictOnWire_str_`, `system_role: WorldHydrology.DefaultWhenMissing_RiverSystemRole_`, `river_system_topology: WorldHydrology.DefaultWhenMissing_Union_RiverSystemTopology__NoneType__`, `parent_location_uid: WorldHydrology.DefaultWhenMissing_Union_str__NoneType__`, `declare_mode: WorldHydrology.DefaultWhenMissing_Union_RiverDeclareMode__NoneType__`, `source: WorldHydrology.DefaultWhenMissing_Union_HydrologyWaypoint__NoneType__`, `mouth: WorldHydrology.DefaultWhenMissing_Union_HydrologyMouth__NoneType__`, `route_location_uids: WorldHydrology.DefaultWhenMissing_tuple_str__________`, `segments: WorldHydrology.DefaultWhenMissing_tuple_DeclaredRiverSegment__________` |
| `DeclaredRiverSegment` | `from: HydrologyWaypoint`, `to: HydrologyWaypoint`, `connection_type: WorldHydrology.StrictOnWire_str_`, `width_cells: WorldHydrology.DefaultWhenMissing_int_` |
| `DistrictConnection` | `connection_type: WorldDistrictTemplateRegistry.StrictOnWire_ConnectionTypeKey_`, `role: WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_str__NoneType__`, `sidewalk: WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_bool__NoneType__`, `lanes_per_side: WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_int__NoneType__` |
| `DistrictTemplateEntry` | `system_name: WorldDistrictTemplateRegistry.StrictOnWire_RegistryKey_WorldDistrictTemplateRegistry__`, `display_name: WorldDistrictTemplateRegistry.StrictOnWire_str_`, `district_type: WorldDistrictTemplateRegistry.StrictOnWire_str_`, `district_subtype: WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_str__NoneType__`, `placement_conditions: WorldDistrictTemplateRegistry.DefaultWhenMissing_list_PlacementCondition__`, `max_per_city: WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_int__NoneType__`, `size_pct: WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_SizePct__NoneType__`, `allowed_structure_types: WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_list_Union_BuildingPurpose__BuildingPurposeFamily____NoneType__`, `allowed_match: WorldDistrictTemplateRegistry.DefaultWhenMissing_BuildingPurposeMatch_`, `economic_tier_range: WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_EconomicTierRange__NoneType__`, `density: WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_DistrictDensity__NoneType__`, `street_layout: WorldDistrictTemplateRegistry.DefaultWhenMissing_StreetLayout_`, `connections: WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_list_DistrictConnection___NoneType__`, `required_structures: WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_list_RequiredStructure___NoneType__`, `frontage_type_order: WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_list_ConnectionTypeKey___NoneType__`, `plot_counts: WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_dict_DrawingKey__int___NoneType__`, `plot_priority: WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_dict_DrawingKey__int___NoneType__`, `perimeter_barrier: WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_PerimeterBarrier__NoneType__`, `deck: WorldDistrictTemplateRegistry.DefaultWhenMissing_int_` |
| `DistrictTemplateKey` | `string` |
| `DistrictZonePreferenceEntry` | `zone: WorldDistrictZonePreference.StrictEnumOnWire_CellZone_`, `district_types: WorldDistrictZonePreference.DefaultWhenMissing_list_str__` |
| `DrawingKey` | `string` |
| `EconomicTierRange` | `min: WorldDistrictTemplateRegistry.StrictOnWire_EconomyTierKey_`, `max: WorldDistrictTemplateRegistry.StrictOnWire_EconomyTierKey_` |
| `EconomyTierEntry` | `system_tier: WorldEconomyTierRegistry.StrictOnWire_RegistryKey_WorldEconomyTierRegistry__`, `display_tier: WorldEconomyTierRegistry.StrictOnWire_str_`, `base_value: WorldEconomyTierRegistry.StrictOnWire_int__Ge_ge_0_`, `road_tier_bonus: IgnoreOnWire_float_0_`, `road_tier_durability: IgnoreOnWire_float_0_` |
| `EconomyTierKey` | `string` |
| `EdgeNoise` | `amplitude: integer`, `scale: integer` |
| `EligibilityRule` | `fact: string`, `op: WorldTerrainRegistry.StrictEnumOnWire_EligibilityOp_`, `lo: number / null`, `hi: number / null`, `weight: number`, `required: boolean` |
| `EllipseShape` | `edge_noise: EdgeNoise / null`, `kind: string`, `cx: integer`, `cy: integer`, `rx: integer`, `ry: integer` |
| `EntityUid` | `string` |
| `FarmlandSpec` | `name: string / null`, `shape: BboxShape / EllipseShape / PolygonShape / AnchorRadiusShape / CorridorShape`, `density: number`, `placement_specificity: integer / null`, `location_uid: string / null`, `entry_type: string` |
| `ForestSpec` | `name: string / null`, `shape: BboxShape / EllipseShape / PolygonShape / AnchorRadiusShape / CorridorShape`, `density: number`, `placement_specificity: integer / null`, `location_uid: string / null`, `entry_type: string` |
| `HillPolicy` | `min_spacing: WorldTerrainRegistry.DefaultWhenMissing_int__Ge_ge_1_`, `radius: WorldTerrainRegistry.DefaultWhenMissing_int__Ge_ge_1_`, `height: WorldTerrainRegistry.DefaultWhenMissing_int__Ge_ge_1_`, `shapes: WorldTerrainRegistry.DefaultWhenMissing_tuple_HillShape__________` |
| `HydrologyBands` | `min: WorldHydrology.StrictOnWire_int__Ge_ge_1__Le_le_99_`, `max: WorldHydrology.StrictOnWire_int__Ge_ge_1__Le_le_99_` |
| `HydrologyMouth` | `location_uid: WorldHydrology.DefaultWhenMissing_Union_str__NoneType__`, `x: WorldHydrology.DefaultWhenMissing_Union_int__NoneType__`, `y: WorldHydrology.DefaultWhenMissing_Union_int__NoneType__`, `z: WorldHydrology.DefaultWhenMissing_Union_int__NoneType__` |
| `HydrologyWaypoint` | `x: WorldHydrology.StrictOnWire_int_`, `y: WorldHydrology.StrictOnWire_int_`, `z: WorldHydrology.StrictOnWire_int_` |
| `IgnoreOnWire_Union_bool__NoneType__` | `boolean / null` |
| `IgnoreOnWire_bool_` | `boolean` |
| `IgnoreOnWire_float_0_` | `number` |
| `IntMinMax` | `min: WorldBarrierTemplateRegistry.StrictOnWire_int_`, `max: WorldBarrierTemplateRegistry.StrictOnWire_int_` |
| `LandcoverTerrainPolicy` | `enabled: WorldTerrainMasks.DefaultWhenMissing_bool_`, `autoresolve: WorldTerrainMasks.DefaultWhenMissing_bool_`, `system_terrain: TerrainKey`, `min_rainfall: integer / null`, `hills: WorldTerrainMasks.HillPolicy / null` |
| `LivestockTypeEntry` | `system_livestock: WorldLivestockRegistry.StrictOnWire_str_`, `livestock_kind: WorldLivestockRegistry.StrictEnumOnWire_LivestockKind_`, `display_name: WorldLivestockRegistry.DefaultWhenMissing_Union_str__NoneType__`, `glossary_ref: WorldLivestockRegistry.DefaultWhenMissing_Union_str__NoneType__` |
| `LocationMoodEntry` | `system_mood: WorldLocationMoodRegistry.StrictOnWire_RegistryKey_WorldLocationMoodRegistry__`, `display_mood: WorldLocationMoodRegistry.DefaultWhenMissing_Union_str__NoneType__` |
| `LocationTypeEntry` | `system_type: WorldLocationTypeRegistry.StrictOnWire_RegistryKey_WorldLocationTypeRegistry__`, `display_type: WorldLocationTypeRegistry.StrictOnWire_str_`, `parent_types: WorldLocationTypeRegistry.DefaultWhenMissing_list_Union_RegistryKey_WorldLocationTypeRegistry___NoneType___`, `is_outdoor: WorldLocationTypeRegistry.DefaultWhenMissing_Union_bool__NoneType__`, `payload_kind: WorldLocationTypeRegistry.DefaultWhenMissing_Union_PayloadKind__NoneType__`, `is_inhabited: IgnoreOnWire_bool_`, `subtypes: WorldLocationTypeRegistry.DefaultWhenMissing_list_LocationTypeSubtypeEntry__` |
| `LocationTypeSubtypeEntry` | `system_subtype: WorldLocationTypeRegistry.StrictOnWire_str_`, `display_subtype: WorldLocationTypeRegistry.DefaultWhenMissing_Union_str__NoneType__`, `border_category: WorldLocationTypeRegistry.DefaultWhenMissing_Union_str__NoneType__`, `l0_map_symbol: WorldLocationTypeRegistry.DefaultWhenMissing_Union_Annotated_str__FieldInfo_annotation_NoneType__required_True__metadata__MinLen_min_length_1___MaxLen_max_length_1______NoneType__`, `typical_district_types: WorldLocationTypeRegistry.DefaultWhenMissing_list_str__`, `required_structure_types: WorldLocationTypeRegistry.DefaultWhenMissing_list_str__`, `footprint_by_size: WorldLocationTypeRegistry.DefaultWhenMissing_dict_str__float__`, `is_inhabited: IgnoreOnWire_Union_bool__NoneType__` |
| `LoreRegistryEntry` | `display_name: WorldLoreRegistry.StrictOnWire_str_`, `description: WorldLoreRegistry.DefaultWhenMissing_Union_str__NoneType__` |
| `MaterialPick` | `pick_from: WorldBarrierTemplateRegistry.StrictOnWire_list_str___MinLen_min_length_1_` |
| `MaterialRegistryEntry` | `system_material: WorldMaterialRegistry.StrictOnWire_RegistryKey_WorldMaterialRegistry__`, `display_name: WorldMaterialRegistry.StrictOnWire_str_`, `glossary_ref: WorldMaterialRegistry.DefaultWhenMissing_Union_str__NoneType__`, `material_category: WorldMaterialRegistry.StrictEnumOnWire_MaterialCategory_`, `substrate_kind: WorldMaterialRegistry.DefaultWhenMissing_Union_StrictEnumOnWire_MaterialSubstrateKind___NoneType__`, `tags: WorldMaterialRegistry.DefaultWhenMissing_list_str__`, `use_type: WorldMaterialRegistry.DefaultWhenMissing_list_str__`, `economic_tier: WorldMaterialRegistry.DefaultWhenMissing_Union_EconomyTierKey__NoneType__`, `hardness: WorldMaterialRegistry.DefaultWhenMissing_Union_Annotated_int__FieldInfo_annotation_NoneType__required_True__metadata__Ge_ge_1___Le_le_5______NoneType__`, `density: WorldMaterialRegistry.DefaultWhenMissing_Union_Annotated_int__FieldInfo_annotation_NoneType__required_True__metadata__Ge_ge_1______NoneType__`, `heat_conductivity: WorldMaterialRegistry.DefaultWhenMissing_float_0_`, `viscosity: WorldMaterialRegistry.DefaultWhenMissing_Union_Annotated_float__FieldInfo_annotation_NoneType__required_True__metadata__0__0______NoneType__`, `heat_into: WorldMaterialRegistry.DefaultWhenMissing_Union_str__NoneType__`, `heat_temp: WorldMaterialRegistry.DefaultWhenMissing_Union_int__NoneType__`, `cool_into: WorldMaterialRegistry.DefaultWhenMissing_Union_str__NoneType__`, `cool_temp: WorldMaterialRegistry.DefaultWhenMissing_Union_int__NoneType__`, `structural_strength: WorldMaterialRegistry.DefaultWhenMissing_Union_Annotated_float__FieldInfo_annotation_NoneType__required_True__metadata__0__0______NoneType__`, `flammable: WorldMaterialRegistry.DefaultWhenMissing_bool_`, `freezable: WorldMaterialRegistry.DefaultWhenMissing_bool_`, `corrodible: WorldMaterialRegistry.DefaultWhenMissing_bool_`, `meltable: WorldMaterialRegistry.DefaultWhenMissing_bool_`, `mineable: WorldMaterialRegistry.DefaultWhenMissing_bool_`, `transparent: WorldMaterialRegistry.DefaultWhenMissing_float_0___PydanticGeneralMetadata_allow_inf_nan_False_`, `breakable: WorldMaterialRegistry.DefaultWhenMissing_bool_`, `temp_damage: WorldMaterialRegistry.DefaultWhenMissing_bool_`, `vision_block: WorldMaterialRegistry.DefaultWhenMissing_bool_`, `components: WorldMaterialRegistry.DefaultWhenMissing_Union_list_str___NoneType__` |
| `MountainFormBySides` | `form_type: string`, `side_count: WorldTerrainMasks.DefaultWhenMissing_int__Ge_ge_3_` |
| `MountainRangeSpec` | `entry_type: string`, `spine: list[tuple[integer, integer]]`, `width_m: WorldTerrainMasks.DefaultWhenMissing_int__Ge_ge_1_`, `kind: WorldTerrainMasks.DefaultEnumWhenMissing_MountainKind_`, `sides: WorldTerrainMasks.DefaultWhenMissing_MountainRangeSides_`, `peaks: WorldTerrainMasks.DefaultWhenMissing_tuple_MountainSpec__________`, `style: WorldTerrainMasks.DefaultEnumWhenMissing_MountainRangeStyle_`, `peak_spacing_m: integer / null`, `peak_spacings_m: WorldTerrainMasks.DefaultWhenMissing_tuple_int__________`, `saddle_rise_fraction: number / null`, `saddles: WorldTerrainMasks.DefaultWhenMissing_tuple_MountainSaddleSpec__________`, `location_uid: string / null` |
| `MountainSaddleSpec` | `peak_a_index: integer`, `peak_b_index: integer`, `t: app__dataModel__annotationPolicy__DefaultWhenMissing_float__Ge_ge_0__0__Le_le_1__0_`, `rise_fraction: number / null` |
| `MountainSpec` | `entry_type: string`, `origin_x_m: integer`, `origin_y_m: integer`, `radius_m: WorldTerrainMasks.DefaultWhenMissing_int__Ge_ge_1_`, `kind: WorldTerrainMasks.DefaultEnumWhenMissing_MountainKind_`, `form: MountainFormBySides / StarForm / PeakForm / PlateauForm`, `sides: WorldTerrainMasks.DefaultWhenMissing_tuple_ReliefSideSpec__________`, `relief_pick_policy: WorldTerrainMasks.DefaultWhenMissing_Union_ObjectReliefPickPolicy__NoneType__`, `location_uid: string / null` |
| `ObjectReliefPickPolicy` | `mountain: WorldTerrainMasks.DefaultWhenMissing_Union_ReliefContextPickPolicy__NoneType__`, `open_land: WorldTerrainMasks.DefaultWhenMissing_Union_ReliefContextPickPolicy__NoneType__`, `shore: WorldTerrainMasks.DefaultWhenMissing_Union_ReliefContextPickPolicy__NoneType__`, `road_shoulder: WorldTerrainMasks.DefaultWhenMissing_Union_ReliefContextPickPolicy__NoneType__`, `ravine: WorldTerrainMasks.DefaultWhenMissing_Union_ReliefContextPickPolicy__NoneType__` |
| `PctRange` | `min: WorldDistrictTemplateRegistry.StrictOnWire_float_0_`, `max: WorldDistrictTemplateRegistry.StrictOnWire_float_0_` |
| `PeakForm` | `form_type: string`, `side_count: WorldTerrainMasks.DefaultWhenMissing_int__Ge_ge_3_` |
| `PerimeterBarrier` | `template: WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_RegistryKey_WorldBarrierTemplateRegistry___NoneType__`, `probability: WorldDistrictTemplateRegistry.DefaultWhenMissing_float_0_`, `sides: WorldDistrictTemplateRegistry.DefaultWhenMissing_CardinalBarrierSides_` |
| `PerkTemplateRegistryEntry` | `system_template_uid: WorldPerkTemplateRegistry.StrictOnWire_str_`, `display_template_name: WorldPerkTemplateRegistry.DefaultWhenMissing_Union_str__NoneType__`, `imported_at: WorldPerkTemplateRegistry.DefaultWhenMissing_Union_str__NoneType__` |
| `PlacementCondition` | `type: WorldDistrictTemplateRegistry.StrictEnumOnWire_PlacementConditionType_`, `terrain_types: WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_list_TerrainKey___NoneType__`, `min_adjacent_cells: WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_int__NoneType__`, `size: WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_SettlementSizeKey__NoneType__`, `tier: WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_EconomyTierKey__NoneType__`, `district_type: WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_str__NoneType__`, `zone: WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_CellZone__NoneType__` |
| `PlainSpec` | `name: string / null`, `shape: BboxShape / EllipseShape / PolygonShape / AnchorRadiusShape / CorridorShape`, `density: number`, `placement_specificity: integer / null`, `location_uid: string / null`, `entry_type: string` |
| `PlateauForm` | `form_type: string`, `side_count: WorldTerrainMasks.DefaultWhenMissing_int__Ge_ge_3_`, `hat_fraction: app__dataModel__annotationPolicy__DefaultWhenMissing_float__Ge_ge_0__05__Le_le_1__0_` |
| `PolygonShape` | `edge_noise: EdgeNoise / null`, `kind: string`, `vertices: list[tuple[integer, integer]]` |
| `PurposePackEntry` | `system_pack: WorldPurposePackRegistry.StrictOnWire_Annotated_RegistryKey_WorldPurposePackRegistry___BeforeValidator__`, `allowed: WorldPurposePackRegistry.DefaultWhenMissing_Annotated_list_Union_BuildingPurpose__BuildingPurposeFamily____BeforeValidator__` |
| `RaceTemplateRegistryEntry` | `system_template_uid: WorldRaceTemplateRegistry.StrictOnWire_str_`, `display_template_name: WorldRaceTemplateRegistry.DefaultWhenMissing_Union_str__NoneType__`, `imported_at: WorldRaceTemplateRegistry.DefaultWhenMissing_Union_str__NoneType__` |
| `ReliefContextPickPolicy` | `mode: WorldTerrainMasks.DefaultEnumWhenMissing_ReliefPickMode_`, `default_template_uid: WorldTerrainMasks.DefaultWhenMissing_Union_str__NoneType__` |
| `ReliefSideSpec` | `kind: WorldTerrainMasks.DefaultEnumWhenMissing_ReliefSideKind_`, `sheer_band_light: WorldTerrainMasks.DefaultWhenMissing_int__Ge_ge_0_` |
| `RequiredStructure` | `plot_template: WorldDistrictTemplateRegistry.StrictOnWire_DrawingKey_`, `structure_type: WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_BuildingPurpose__NoneType__`, `count: WorldDistrictTemplateRegistry.DefaultWhenMissing_int_`, `position: WorldDistrictTemplateRegistry.DefaultWhenMissing_RequiredStructurePosition_` |
| `ResourceTypeEntry` | `system_resource: WorldResourceTypeRegistry.StrictOnWire_str_`, `resource_kind: WorldResourceTypeRegistry.StrictEnumOnWire_ResourceKind_`, `display_name: WorldResourceTypeRegistry.DefaultWhenMissing_Union_str__NoneType__`, `glossary_ref: WorldResourceTypeRegistry.DefaultWhenMissing_Union_str__NoneType__`, `is_renewable: WorldResourceTypeRegistry.DefaultWhenMissing_bool_`, `base_regen_per_tick: WorldResourceTypeRegistry.DefaultWhenMissing_Union_Annotated_int__FieldInfo_annotation_NoneType__required_True__metadata__Ge_ge_0______NoneType__`, `default_yield: WorldResourceTypeRegistry.DefaultWhenMissing_int__Ge_ge_0_`, `yield_item_uid: WorldResourceTypeRegistry.DefaultWhenMissing_Union_str__NoneType__`, `tag_refs: WorldResourceTypeRegistry.DefaultWhenMissing_list_str__` |
| `RoadSettingsEntry` | `connection_type: WorldRoadSettings.StrictOnWire_str_`, `curve_radius_factor: WorldRoadSettings.DefaultWhenMissing_int__Ge_ge_1_`, `max_segment_length_m: WorldRoadSettings.DefaultWhenMissing_int__Ge_ge_1_`, `min_segment_length_m: WorldRoadSettings.DefaultWhenMissing_int__Ge_ge_1_`, `default_lanes_per_side: WorldRoadSettings.DefaultWhenMissing_Union_int__NoneType__`, `auto_sidewalk: WorldRoadSettings.DefaultWhenMissing_bool_`, `base_travel_modifier: app__dataModel__annotationPolicy__DefaultWhenMissing_float__Gt_gt_0__0_`, `condition_degradation: app__dataModel__annotationPolicy__DefaultWhenMissing_float__Ge_ge_0__0_` |
| `RoomTypeEntry` | `system_room: WorldRoomTypeRegistry.StrictOnWire_str_`, `glossary_ref: WorldRoomTypeRegistry.DefaultWhenMissing_Union_str__NoneType__` |
| `SettlementSizeEntry` | `system_size: WorldSettlementSizeRegistry.StrictOnWire_RegistryKey_WorldSettlementSizeRegistry__`, `display_size: WorldSettlementSizeRegistry.DefaultWhenMissing_Union_str__NoneType__` |
| `SettlementSizeKey` | `string` |
| `SettlementSpecializationEntry` | `system_specialization: WorldSettlementSpecializationRegistry.StrictOnWire_RegistryKey_WorldSettlementSpecializationRegistry__`, `display_specialization: WorldSettlementSpecializationRegistry.DefaultWhenMissing_Union_str__NoneType__`, `subject_kind: WorldSettlementSpecializationRegistry.DefaultWhenMissing_Union_str__list_str___NoneType__`, `typical_districts: WorldSettlementSpecializationRegistry.DefaultWhenMissing_list_TypicalDistrictRef__`, `allowed_family: WorldSettlementSpecializationRegistry.StrictEnumOnWire_BuildingPurposeFamily_` |
| `SizePct` | `width: WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_PctRange__NoneType__`, `depth: WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_PctRange__NoneType__` |
| `Specificity` | `integer` |
| `StarForm` | `form_type: string`, `rays: WorldTerrainMasks.DefaultWhenMissing_int__Ge_ge_3_`, `inner_ratio: WorldTerrainMasks.DefaultWhenMissing_float_95_` |
| `TerrainCategoryEntry` | `system_category: WorldTerrainCategoryRegistry.StrictOnWire_str_`, `display_category: WorldTerrainCategoryRegistry.DefaultWhenMissing_Union_str__NoneType__`, `passable: WorldTerrainCategoryRegistry.DefaultWhenMissing_bool_`, `jumpable: WorldTerrainCategoryRegistry.DefaultWhenMissing_bool_`, `climbable: WorldTerrainCategoryRegistry.DefaultWhenMissing_bool_`, `breakable: WorldTerrainCategoryRegistry.DefaultWhenMissing_bool_` |
| `TerrainKey` | `string` |
| `TerrainRegistryEntry` | `system_terrain: WorldTerrainRegistry.StrictOnWire_RegistryKey_WorldTerrainRegistry__`, `glossary_ref: WorldTerrainRegistry.DefaultWhenMissing_Union_str__NoneType__`, `terrain_category: WorldTerrainRegistry.StrictOnWire_str_`, `travel_modifier: WorldTerrainRegistry.DefaultWhenMissing_Union_float__NoneType__`, `danger_level: WorldTerrainRegistry.DefaultWhenMissing_str_`, `has_state: WorldTerrainRegistry.DefaultWhenMissing_bool_`, `default_state: WorldTerrainRegistry.DefaultWhenMissing_Union_str__NoneType__`, `default_material: WorldTerrainRegistry.DefaultWhenMissing_Union_str__NoneType__`, `gap_width: WorldTerrainRegistry.DefaultWhenMissing_Union_Annotated_int__FieldInfo_annotation_NoneType__required_True__metadata__Ge_ge_1______NoneType__`, `merge_rank: WorldTerrainRegistry.DefaultWhenMissing_int_`, `eligibility: WorldTerrainRegistry.DefaultWhenMissing_list_EligibilityRule__`, `inertia: WorldTerrainRegistry.DefaultWhenMissing_float__Gt_gt_0___PydanticGeneralMetadata_allow_inf_nan_False_`, `hills: WorldTerrainRegistry.DefaultWhenMissing_Union_HillPolicy__NoneType__`, `fill_roles: WorldTerrainRegistry.DefaultWhenMissing_tuple_StrictEnumOnWire_TerrainFillRole___________`, `fill_priority: WorldTerrainRegistry.DefaultWhenMissing_int_`, `morph_hydrology_role: WorldTerrainRegistry.DefaultEnumWhenMissing_Union_HydrologyCellRole__NoneType__`, `supports_open_land_grade: WorldTerrainRegistry.DefaultWhenMissing_bool_`, `open_land_profile: WorldTerrainRegistry.DefaultWhenMissing_Union_Literal__plains____forest____NoneType__` |
| `TransitionTypeEntry` | `system_type: WorldTransitionTypeRegistry.StrictOnWire_RegistryKey_WorldTransitionTypeRegistry__`, `display_name: WorldTransitionTypeRegistry.StrictOnWire_str_`, `behaves_as: WorldTransitionTypeRegistry.StrictEnumOnWire_TransitionType_`, `glossary_ref: WorldTransitionTypeRegistry.DefaultWhenMissing_Union_str__NoneType__` |
| `TypicalDistrictRef` | `district_type: WorldSettlementSpecializationRegistry.StrictOnWire_str_`, `district_subtype: WorldSettlementSpecializationRegistry.DefaultWhenMissing_Union_str__NoneType__`, `system_name: WorldSettlementSpecializationRegistry.DefaultWhenMissing_Union_DistrictTemplateKey__NoneType__` |
| `WeatherTypeEntry` | `system_weather: WorldWeatherTypeRegistry.StrictOnWire_str_`, `display_weather: WorldWeatherTypeRegistry.DefaultWhenMissing_Union_str__NoneType__`, `temp_max: WorldWeatherTypeRegistry.DefaultWhenMissing_Union_int__NoneType__`, `temp_min: WorldWeatherTypeRegistry.DefaultWhenMissing_Union_int__NoneType__`, `rainfall_min: WorldWeatherTypeRegistry.DefaultWhenMissing_Union_int__NoneType__`, `priority: WorldWeatherTypeRegistry.DefaultWhenMissing_int__Ge_ge_1_`, `travel_modifier: WorldWeatherTypeRegistry.DefaultWhenMissing_float_0_`, `need_modifiers: WorldWeatherTypeRegistry.DefaultWhenMissing_dict_str__int__`, `glossary_ref: WorldWeatherTypeRegistry.DefaultWhenMissing_Union_str__NoneType__` |
| `WorldAtmosphereSettings` | `mode: WorldEnvironmentSettings.StrictEnumOnWire_AtmosphereMode_`, `composition: WorldEnvironmentSettings.DefaultWhenMissing_list_AtmosphereGasComponent__` |
| `WorldBarrierTemplateRegistry` | `list[BarrierTemplateEntry]` |
| `WorldBarrierTemplateRegistry.DefaultWhenMissing_Union_IntMinMax__NoneType__` | `IntMinMax / null` |
| `WorldBarrierTemplateRegistry.DefaultWhenMissing_Union_MaterialPick__NoneType__` | `MaterialPick / null` |
| `WorldBarrierTemplateRegistry.DefaultWhenMissing_Union_str__NoneType__` | `string / null` |
| `WorldBarrierTemplateRegistry.DefaultWhenMissing_int__Ge_ge_1_` | `integer` |
| `WorldBarrierTemplateRegistry.StrictOnWire_RegistryKey_WorldBarrierTemplateRegistry__` | `string` |
| `WorldBarrierTemplateRegistry.StrictOnWire_int_` | `integer` |
| `WorldBarrierTemplateRegistry.StrictOnWire_list_str___MinLen_min_length_1_` | `list[string]` |
| `WorldCanalTemplateRegistry` | `list[CanalTemplateEntry]` |
| `WorldCanalTemplateRegistry.DefaultWhenMissing_Union_CanalStructureSpec__NoneType__` | `CanalStructureSpec / null` |
| `WorldCanalTemplateRegistry.DefaultWhenMissing_Union_bool__NoneType__` | `boolean / null` |
| `WorldCanalTemplateRegistry.DefaultWhenMissing_list_str__` | `list[string]` |
| `WorldCanalTemplateRegistry.StrictOnWire_str_` | `string` |
| `WorldClimateScalars` | `default_climate_zone: WorldClimateScalars.DefaultWhenMissing_str_`, `climate_temperature_peak_min: WorldClimateScalars.DefaultWhenMissing_Union_int__NoneType__`, `climate_temperature_peak_max: WorldClimateScalars.DefaultWhenMissing_Union_int__NoneType__`, `climate_pole_mode: WorldClimateScalars.DefaultWhenMissing_str_`, `climate_pole_preset: WorldClimateScalars.DefaultWhenMissing_str_`, `climate_local_influence_fraction: WorldClimateScalars.DefaultWhenMissing_float_0_`, `precipitation_liquid: WorldClimateScalars.DefaultWhenMissing_str_`, `climate_parallel_workers: WorldClimateScalars.DefaultWhenMissing_Union_int__NoneType__`, `season_temp_offsets: WorldClimateScalars.DefaultWhenMissing_SeasonTempOffsets_` |
| `WorldClimateScalars.DefaultWhenMissing_SeasonTempOffsets_` | `winter: WorldClimateScalars.DefaultWhenMissing_int_`, `spring: WorldClimateScalars.DefaultWhenMissing_int_`, `summer: WorldClimateScalars.DefaultWhenMissing_int_`, `autumn: WorldClimateScalars.DefaultWhenMissing_int_` |
| `WorldClimateScalars.DefaultWhenMissing_Union_int__NoneType__` | `integer / null` |
| `WorldClimateScalars.DefaultWhenMissing_float_0_` | `number` |
| `WorldClimateScalars.DefaultWhenMissing_int_` | `integer` |
| `WorldClimateScalars.DefaultWhenMissing_str_` | `string` |
| `WorldClimateZoneRegistry` | `list[ClimateZoneEntry]` |
| `WorldClimateZoneRegistry.DefaultWhenMissing_Union_int__NoneType__` | `integer / null` |
| `WorldClimateZoneRegistry.StrictOnWire_str_` | `string` |
| `WorldConnectionTypeRegistry` | `list[ConnectionTypeEntry]` |
| `WorldConnectionTypeRegistry.StrictOnWire_RegistryKey_WorldConnectionTypeRegistry__` | `string` |
| `WorldConnectionTypeRegistry.StrictOnWire_str_` | `string` |
| `WorldCropsRegistry` | `list[CropsTypeEntry]` |
| `WorldCropsRegistry.DefaultWhenMissing_Union_str__NoneType__` | `string / null` |
| `WorldCropsRegistry.StrictOnWire_str_` | `string` |
| `WorldDistrictTemplateRegistry` | `list[DistrictTemplateEntry]` |
| `WorldDistrictTemplateRegistry.DefaultWhenMissing_CardinalBarrierSides_` | `list[Facing] / null` |
| `WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_BuildingPurpose__NoneType__` | `BuildingPurpose / null` |
| `WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_CellZone__NoneType__` | `CellZone / null` |
| `WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_DistrictDensity__NoneType__` | `DistrictDensity / null` |
| `WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_EconomicTierRange__NoneType__` | `EconomicTierRange / null` |
| `WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_EconomyTierKey__NoneType__` | `EconomyTierKey / null` |
| `WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_PctRange__NoneType__` | `PctRange / null` |
| `WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_PerimeterBarrier__NoneType__` | `PerimeterBarrier / null` |
| `WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_RegistryKey_WorldBarrierTemplateRegistry___NoneType__` | `string / null` |
| `WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_SettlementSizeKey__NoneType__` | `SettlementSizeKey / null` |
| `WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_SizePct__NoneType__` | `SizePct / null` |
| `WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_bool__NoneType__` | `boolean / null` |
| `WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_dict_DrawingKey__int___NoneType__` | `map[integer] / null` |
| `WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_int__NoneType__` | `integer / null` |
| `WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_list_ConnectionTypeKey___NoneType__` | `list[ConnectionTypeKey] / null` |
| `WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_list_DistrictConnection___NoneType__` | `list[DistrictConnection] / null` |
| `WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_list_RequiredStructure___NoneType__` | `list[RequiredStructure] / null` |
| `WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_list_TerrainKey___NoneType__` | `list[TerrainKey] / null` |
| `WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_list_Union_BuildingPurpose__BuildingPurposeFamily____NoneType__` | `list[BuildingPurpose / BuildingPurposeFamily] / null` |
| `WorldDistrictTemplateRegistry.DefaultWhenMissing_Union_str__NoneType__` | `string / null` |
| `WorldDistrictTemplateRegistry.DefaultWhenMissing_float_0_` | `number` |
| `WorldDistrictTemplateRegistry.DefaultWhenMissing_int_` | `integer` |
| `WorldDistrictTemplateRegistry.DefaultWhenMissing_list_PlacementCondition__` | `list[PlacementCondition]` |
| `WorldDistrictTemplateRegistry.StrictOnWire_ConnectionTypeKey_` | `string` |
| `WorldDistrictTemplateRegistry.StrictOnWire_DrawingKey_` | `string` |
| `WorldDistrictTemplateRegistry.StrictOnWire_EconomyTierKey_` | `string` |
| `WorldDistrictTemplateRegistry.StrictOnWire_RegistryKey_WorldDistrictTemplateRegistry__` | `string` |
| `WorldDistrictTemplateRegistry.StrictOnWire_float_0_` | `number` |
| `WorldDistrictTemplateRegistry.StrictOnWire_str_` | `string` |
| `WorldDistrictZonePreference` | `list[DistrictZonePreferenceEntry]` |
| `WorldDistrictZonePreference.DefaultWhenMissing_list_str__` | `list[string]` |
| `WorldEconomyTierRegistry` | `list[EconomyTierEntry]` |
| `WorldEconomyTierRegistry.StrictOnWire_RegistryKey_WorldEconomyTierRegistry__` | `string` |
| `WorldEconomyTierRegistry.StrictOnWire_int__Ge_ge_0_` | `integer` |
| `WorldEconomyTierRegistry.StrictOnWire_str_` | `string` |
| `WorldEnvironmentSettings` | `atmosphere: WorldEnvironmentSettings.DefaultWhenMissing_Union_WorldAtmosphereSettings__NoneType__` |
| `WorldEnvironmentSettings.DefaultWhenMissing_Union_WorldAtmosphereSettings__NoneType__` | `WorldAtmosphereSettings / null` |
| `WorldEnvironmentSettings.DefaultWhenMissing_list_AtmosphereGasComponent__` | `list[AtmosphereGasComponent]` |
| `WorldEnvironmentSettings.StrictOnWire_Annotated_float__FieldInfo_annotation_NoneType__required_True__metadata__0__0____PydanticGeneralMetadata_allow_inf_nan_False_____` | `number` |
| `WorldEnvironmentSettings.StrictOnWire_MaterialKey_` | `string` |
| `WorldGridSettings` | `fine_cells_per_map_cell: WorldGridSettings.DefaultWhenMissing_int__Strict_strict_True__Ge_ge_1000__MultipleOf_multiple_of_1000_` |
| `WorldGridSettings.DefaultWhenMissing_int__Strict_strict_True__Ge_ge_1000__MultipleOf_multiple_of_1000_` | `integer` |
| `WorldHydrology` | `enabled: WorldHydrology.DefaultWhenMissing_bool_`, `default_water_level: WorldHydrology.DefaultWhenMissing_int_`, `default_shore: WorldHydrology.DefaultWhenMissing_HydrologyShoreDefaults_`, `default_rivers: WorldHydrology.DefaultWhenMissing_HydrologyRiversPolicy_`, `default_lakes: WorldHydrology.DefaultWhenMissing_HydrologyLakesPolicy_`, `default_seas: WorldHydrology.DefaultWhenMissing_HydrologySeasPolicy_`, `default_landforms: WorldHydrology.DefaultWhenMissing_HydrologyLandformsPolicy_`, `materialize_named_locations: WorldHydrology.DefaultWhenMissing_bool_`, `declared_lakes: WorldHydrology.DefaultWhenMissing_list_DeclaredLake__`, `declared_basins: WorldHydrology.DefaultWhenMissing_list_DeclaredBasin__`, `declared_coastlines: WorldHydrology.DefaultWhenMissing_list_DeclaredCoastline__`, `declared_rivers: WorldHydrology.DefaultWhenMissing_list_DeclaredRiver__` |
| `WorldHydrology.DefaultWhenMissing_HydrologyBands_` | `min: WorldHydrology.StrictOnWire_int__Ge_ge_1__Le_le_99_`, `max: WorldHydrology.StrictOnWire_int__Ge_ge_1__Le_le_99_` |
| `WorldHydrology.DefaultWhenMissing_HydrologyLakesPolicy_` | `placement_specificity: WorldHydrology.DefaultWhenMissing_Union_Specificity__NoneType__`, `enabled: WorldHydrology.DefaultWhenMissing_bool_`, `autoresolve: WorldHydrology.DefaultWhenMissing_bool_`, `bands: WorldHydrology.DefaultWhenMissing_HydrologyBands_`, `basin_depth: WorldHydrology.DefaultWhenMissing_int__Gt_gt_0_`, `min_water_cells: WorldHydrology.DefaultWhenMissing_int__Ge_ge_1_`, `shore: WorldHydrology.DefaultWhenMissing_HydrologyShoreDefaults_` |
| `WorldHydrology.DefaultWhenMissing_HydrologyLandformsPolicy_` | `enabled: WorldHydrology.DefaultWhenMissing_bool_`, `autoresolve: WorldHydrology.DefaultWhenMissing_bool_`, `bands: WorldHydrology.DefaultWhenMissing_Union_HydrologyBands__NoneType__` |
| `WorldHydrology.DefaultWhenMissing_HydrologyRiversPolicy_` | `enabled: WorldHydrology.DefaultWhenMissing_bool_`, `autoresolve: WorldHydrology.DefaultWhenMissing_bool_`, `bands: WorldHydrology.DefaultWhenMissing_HydrologyBands_`, `placement_specificity: WorldHydrology.DefaultWhenMissing_int__Ge_ge_0_`, `channel_depth_cells: WorldHydrology.DefaultWhenMissing_int__Strict_strict_True__Gt_gt_0_`, `mouth_search_radius_fine: WorldHydrology.DefaultWhenMissing_int__Strict_strict_True__Ge_ge_0_`, `max_path_cells: WorldHydrology.DefaultWhenMissing_int__Strict_strict_True__Ge_ge_2_`, `type_classify: WorldHydrology.DefaultWhenMissing_RiverTypeClassify_`, `shore: WorldHydrology.DefaultWhenMissing_HydrologyShoreDefaults_`, `mountain_shore: WorldHydrology.DefaultWhenMissing_HydrologyShoreDefaults_` |
| `WorldHydrology.DefaultWhenMissing_HydrologySeasPolicy_` | `placement_specificity: WorldHydrology.DefaultWhenMissing_Union_Specificity__NoneType__`, `enabled: WorldHydrology.DefaultWhenMissing_bool_`, `autoresolve: WorldHydrology.DefaultWhenMissing_bool_`, `autoresolve_coastal_sea: WorldHydrology.DefaultWhenMissing_bool_`, `autoresolve_open_ocean: WorldHydrology.DefaultWhenMissing_bool_`, `basin_depth: WorldHydrology.DefaultWhenMissing_int__Gt_gt_0_`, `max_area_fraction: WorldHydrology.DefaultWhenMissing_float__Gt_gt_0__Le_le_1_`, `max_extent_x_fraction: WorldHydrology.DefaultWhenMissing_float__Gt_gt_0__Le_le_1_`, `max_extent_y_fraction: WorldHydrology.DefaultWhenMissing_float__Gt_gt_0__Le_le_1_`, `min_water_cells: WorldHydrology.DefaultWhenMissing_int__Ge_ge_1_`, `inland_sea_min_area_fraction: WorldHydrology.DefaultWhenMissing_float__Gt_gt_0__Le_le_1_`, `bands: WorldHydrology.DefaultWhenMissing_HydrologyBands_`, `shore: WorldHydrology.DefaultWhenMissing_HydrologyShoreDefaults_` |
| `WorldHydrology.DefaultWhenMissing_HydrologyShoreDefaults_` | `system_terrain: WorldHydrology.StrictOnWire_str_`, `system_material: WorldHydrology.StrictOnWire_str_` |
| `WorldHydrology.DefaultWhenMissing_RiverTypeClassify_` | `mountain_min_source_z: WorldHydrology.DefaultWhenMissing_int_`, `path_mountain_fraction: app__dataModel__annotationPolicy__DefaultWhenMissing_float__Ge_ge_0__0__Le_le_1__0_`, `rapid_drop_threshold_m: WorldHydrology.DefaultWhenMissing_int__Ge_ge_0_`, `mountain_bed_steepness_factor: app__dataModel__annotationPolicy__DefaultWhenMissing_float__Gt_gt_0__0_`, `foothill_gradient_threshold: app__dataModel__annotationPolicy__DefaultWhenMissing_float__Ge_ge_0__0_` |
| `WorldHydrology.DefaultWhenMissing_StrictOnWire_MaterialKey__` | `string` |
| `WorldHydrology.DefaultWhenMissing_Union_EntityUid__NoneType__` | `EntityUid / null` |
| `WorldHydrology.DefaultWhenMissing_Union_HydrologyBands__NoneType__` | `HydrologyBands / null` |
| `WorldHydrology.DefaultWhenMissing_Union_HydrologyMouth__NoneType__` | `HydrologyMouth / null` |
| `WorldHydrology.DefaultWhenMissing_Union_HydrologyWaypoint__NoneType__` | `HydrologyWaypoint / null` |
| `WorldHydrology.DefaultWhenMissing_Union_RiverDeclareMode__NoneType__` | `RiverDeclareMode / null` |
| `WorldHydrology.DefaultWhenMissing_Union_RiverSystemTopology__NoneType__` | `RiverSystemTopology / null` |
| `WorldHydrology.DefaultWhenMissing_Union_Specificity__NoneType__` | `Specificity / null` |
| `WorldHydrology.DefaultWhenMissing_Union_WaterSide__NoneType__` | `WaterSide / null` |
| `WorldHydrology.DefaultWhenMissing_Union_int__NoneType__` | `integer / null` |
| `WorldHydrology.DefaultWhenMissing_Union_str__NoneType__` | `string / null` |
| `WorldHydrology.DefaultWhenMissing_bool_` | `boolean` |
| `WorldHydrology.DefaultWhenMissing_float__Gt_gt_0__Le_le_1_` | `number` |
| `WorldHydrology.DefaultWhenMissing_int_` | `integer` |
| `WorldHydrology.DefaultWhenMissing_int__Ge_ge_0_` | `integer` |
| `WorldHydrology.DefaultWhenMissing_int__Ge_ge_1_` | `integer` |
| `WorldHydrology.DefaultWhenMissing_int__Gt_gt_0_` | `integer` |
| `WorldHydrology.DefaultWhenMissing_int__Strict_strict_True__Ge_ge_0_` | `integer` |
| `WorldHydrology.DefaultWhenMissing_int__Strict_strict_True__Ge_ge_2_` | `integer` |
| `WorldHydrology.DefaultWhenMissing_int__Strict_strict_True__Gt_gt_0_` | `integer` |
| `WorldHydrology.DefaultWhenMissing_list_DeclaredBasin__` | `list[DeclaredBasin]` |
| `WorldHydrology.DefaultWhenMissing_list_DeclaredCoastline__` | `list[DeclaredCoastline]` |
| `WorldHydrology.DefaultWhenMissing_list_DeclaredLake__` | `list[DeclaredLake]` |
| `WorldHydrology.DefaultWhenMissing_list_DeclaredRiver__` | `list[DeclaredRiver]` |
| `WorldHydrology.DefaultWhenMissing_tuple_DeclaredRiverSegment__________` | `list[DeclaredRiverSegment]` |
| `WorldHydrology.DefaultWhenMissing_tuple_HydrologyWaypoint__________` | `list[HydrologyWaypoint]` |
| `WorldHydrology.DefaultWhenMissing_tuple_str__________` | `list[string]` |
| `WorldHydrology.StrictOnWire_Annotated_Union_BboxShape__EllipseShape__PolygonShape__AnchorRadiusShape__CorridorShape___FieldInfo_annotation_NoneType__required_True__discriminator__kind____` | `BboxShape / EllipseShape / PolygonShape / AnchorRadiusShape / CorridorShape` |
| `WorldHydrology.StrictOnWire_int_` | `integer` |
| `WorldHydrology.StrictOnWire_int__Ge_ge_1__Le_le_99_` | `integer` |
| `WorldHydrology.StrictOnWire_str_` | `string` |
| `WorldLivestockRegistry` | `list[LivestockTypeEntry]` |
| `WorldLivestockRegistry.DefaultWhenMissing_Union_str__NoneType__` | `string / null` |
| `WorldLivestockRegistry.StrictOnWire_str_` | `string` |
| `WorldLocationMoodRegistry` | `list[LocationMoodEntry]` |
| `WorldLocationMoodRegistry.DefaultWhenMissing_Union_str__NoneType__` | `string / null` |
| `WorldLocationMoodRegistry.StrictOnWire_RegistryKey_WorldLocationMoodRegistry__` | `string` |
| `WorldLocationTypeRegistry` | `list[LocationTypeEntry]` |
| `WorldLocationTypeRegistry.DefaultWhenMissing_Union_Annotated_str__FieldInfo_annotation_NoneType__required_True__metadata__MinLen_min_length_1___MaxLen_max_length_1______NoneType__` | `string / null` |
| `WorldLocationTypeRegistry.DefaultWhenMissing_Union_PayloadKind__NoneType__` | `PayloadKind / null` |
| `WorldLocationTypeRegistry.DefaultWhenMissing_Union_bool__NoneType__` | `boolean / null` |
| `WorldLocationTypeRegistry.DefaultWhenMissing_Union_str__NoneType__` | `string / null` |
| `WorldLocationTypeRegistry.DefaultWhenMissing_dict_str__float__` | `map[number]` |
| `WorldLocationTypeRegistry.DefaultWhenMissing_list_LocationTypeSubtypeEntry__` | `list[LocationTypeSubtypeEntry]` |
| `WorldLocationTypeRegistry.DefaultWhenMissing_list_Union_RegistryKey_WorldLocationTypeRegistry___NoneType___` | `list[string / null]` |
| `WorldLocationTypeRegistry.DefaultWhenMissing_list_str__` | `list[string]` |
| `WorldLocationTypeRegistry.StrictOnWire_RegistryKey_WorldLocationTypeRegistry__` | `string` |
| `WorldLocationTypeRegistry.StrictOnWire_str_` | `string` |
| `WorldLoreRegistry` | `map[LoreRegistryEntry]` |
| `WorldLoreRegistry.DefaultWhenMissing_Union_str__NoneType__` | `string / null` |
| `WorldLoreRegistry.StrictOnWire_str_` | `string` |
| `WorldMapResolutionSettings` | `world_map_cells_per_tile: WorldMapResolutionSettings.DefaultWhenMissing_Annotated_Union_int__NoneType___BeforeValidator__` |
| `WorldMapResolutionSettings.DefaultWhenMissing_Annotated_Union_int__NoneType___BeforeValidator__` | `integer / null` |
| `WorldMaterialRegistry` | `list[MaterialRegistryEntry]` |
| `WorldMaterialRegistry.DefaultWhenMissing_Union_Annotated_float__FieldInfo_annotation_NoneType__required_True__metadata__0__0______NoneType__` | `number / null` |
| `WorldMaterialRegistry.DefaultWhenMissing_Union_Annotated_int__FieldInfo_annotation_NoneType__required_True__metadata__Ge_ge_1___Le_le_5______NoneType__` | `integer / null` |
| `WorldMaterialRegistry.DefaultWhenMissing_Union_Annotated_int__FieldInfo_annotation_NoneType__required_True__metadata__Ge_ge_1______NoneType__` | `integer / null` |
| `WorldMaterialRegistry.DefaultWhenMissing_Union_EconomyTierKey__NoneType__` | `EconomyTierKey / null` |
| `WorldMaterialRegistry.DefaultWhenMissing_Union_StrictEnumOnWire_MaterialSubstrateKind___NoneType__` | `WorldMaterialRegistry.StrictEnumOnWire_MaterialSubstrateKind_ / null` |
| `WorldMaterialRegistry.DefaultWhenMissing_Union_int__NoneType__` | `integer / null` |
| `WorldMaterialRegistry.DefaultWhenMissing_Union_list_str___NoneType__` | `list[string] / null` |
| `WorldMaterialRegistry.DefaultWhenMissing_Union_str__NoneType__` | `string / null` |
| `WorldMaterialRegistry.DefaultWhenMissing_bool_` | `boolean` |
| `WorldMaterialRegistry.DefaultWhenMissing_float_0_` | `number` |
| `WorldMaterialRegistry.DefaultWhenMissing_float_0___PydanticGeneralMetadata_allow_inf_nan_False_` | `number` |
| `WorldMaterialRegistry.DefaultWhenMissing_list_str__` | `list[string]` |
| `WorldMaterialRegistry.StrictOnWire_RegistryKey_WorldMaterialRegistry__` | `string` |
| `WorldMaterialRegistry.StrictOnWire_str_` | `string` |
| `WorldPackMetadata` | `terrain_pack_path: WorldPackMetadata.DefaultWhenMissing_Union_str__NoneType__`, `terrain_pack_hash: WorldPackMetadata.DefaultWhenMissing_Union_str__NoneType__` |
| `WorldPackMetadata.DefaultWhenMissing_Union_str__NoneType__` | `string / null` |
| `WorldPerkTemplateRegistry` | `list[PerkTemplateRegistryEntry]` |
| `WorldPerkTemplateRegistry.DefaultWhenMissing_Union_str__NoneType__` | `string / null` |
| `WorldPerkTemplateRegistry.StrictOnWire_str_` | `string` |
| `WorldPurposePackRegistry` | `list[PurposePackEntry]` |
| `WorldPurposePackRegistry.DefaultWhenMissing_Annotated_list_Union_BuildingPurpose__BuildingPurposeFamily____BeforeValidator__` | `list[BuildingPurpose / BuildingPurposeFamily]` |
| `WorldPurposePackRegistry.StrictOnWire_Annotated_RegistryKey_WorldPurposePackRegistry___BeforeValidator__` | `string` |
| `WorldPurposePacks` | `list[string]` |
| `WorldRaceTemplateRegistry` | `list[RaceTemplateRegistryEntry]` |
| `WorldRaceTemplateRegistry.DefaultWhenMissing_Union_str__NoneType__` | `string / null` |
| `WorldRaceTemplateRegistry.StrictOnWire_str_` | `string` |
| `WorldReliefGradeObstacleScalars` | `relief_grade_obstacle_policy: WorldReliefGradeObstacleScalars.DefaultEnumWhenMissing_ReliefGradeObstaclePolicy_` |
| `WorldReliefPickPolicy` | `mountain: WorldReliefPickPolicy.DefaultWhenMissing_ReliefContextPickPolicy_`, `open_land: WorldReliefPickPolicy.DefaultWhenMissing_ReliefContextPickPolicy_`, `shore: WorldReliefPickPolicy.DefaultWhenMissing_ReliefContextPickPolicy_`, `road_shoulder: WorldReliefPickPolicy.DefaultWhenMissing_ReliefContextPickPolicy_`, `ravine: WorldReliefPickPolicy.DefaultWhenMissing_ReliefContextPickPolicy_`, `canal_obstacle_policy: WorldReliefPickPolicy.DefaultWhenMissing_list_CanalObstaclePolicyRule__` |
| `WorldReliefPickPolicy.DefaultWhenMissing_ReliefContextPickPolicy_` | `mode: WorldReliefPickPolicy.DefaultEnumWhenMissing_ReliefPickMode_`, `default_template_uid: WorldReliefPickPolicy.DefaultWhenMissing_Union_str__NoneType__` |
| `WorldReliefPickPolicy.DefaultWhenMissing_Union_str__NoneType__` | `string / null` |
| `WorldReliefPickPolicy.DefaultWhenMissing_list_CanalObstaclePolicyRule__` | `list[CanalObstaclePolicyRule]` |
| `WorldReliefPickPolicy.StrictOnWire_bool_` | `boolean` |
| `WorldReliefPickPolicy.StrictOnWire_list_CanalObstacleEntity___MinLen_min_length_1_` | `list[CanalObstacleEntity]` |
| `WorldResourceTypeRegistry` | `list[ResourceTypeEntry]` |
| `WorldResourceTypeRegistry.DefaultWhenMissing_Union_Annotated_int__FieldInfo_annotation_NoneType__required_True__metadata__Ge_ge_0______NoneType__` | `integer / null` |
| `WorldResourceTypeRegistry.DefaultWhenMissing_Union_str__NoneType__` | `string / null` |
| `WorldResourceTypeRegistry.DefaultWhenMissing_bool_` | `boolean` |
| `WorldResourceTypeRegistry.DefaultWhenMissing_int__Ge_ge_0_` | `integer` |
| `WorldResourceTypeRegistry.DefaultWhenMissing_list_str__` | `list[string]` |
| `WorldResourceTypeRegistry.StrictOnWire_str_` | `string` |
| `WorldRoadSettings` | `list[RoadSettingsEntry]` |
| `WorldRoadSettings.DefaultWhenMissing_Union_int__NoneType__` | `integer / null` |
| `WorldRoadSettings.DefaultWhenMissing_bool_` | `boolean` |
| `WorldRoadSettings.DefaultWhenMissing_int__Ge_ge_1_` | `integer` |
| `WorldRoadSettings.StrictOnWire_str_` | `string` |
| `WorldRoomTypeRegistry` | `list[RoomTypeEntry]` |
| `WorldRoomTypeRegistry.DefaultWhenMissing_Union_str__NoneType__` | `string / null` |
| `WorldRoomTypeRegistry.StrictOnWire_str_` | `string` |
| `WorldSettlementSizeRegistry` | `list[SettlementSizeEntry]` |
| `WorldSettlementSizeRegistry.DefaultWhenMissing_Union_str__NoneType__` | `string / null` |
| `WorldSettlementSizeRegistry.StrictOnWire_RegistryKey_WorldSettlementSizeRegistry__` | `string` |
| `WorldSettlementSpecializationRegistry` | `list[SettlementSpecializationEntry]` |
| `WorldSettlementSpecializationRegistry.DefaultWhenMissing_Union_DistrictTemplateKey__NoneType__` | `DistrictTemplateKey / null` |
| `WorldSettlementSpecializationRegistry.DefaultWhenMissing_Union_str__NoneType__` | `string / null` |
| `WorldSettlementSpecializationRegistry.DefaultWhenMissing_Union_str__list_str___NoneType__` | `string / list[string] / null` |
| `WorldSettlementSpecializationRegistry.DefaultWhenMissing_list_TypicalDistrictRef__` | `list[TypicalDistrictRef]` |
| `WorldSettlementSpecializationRegistry.StrictOnWire_RegistryKey_WorldSettlementSpecializationRegistry__` | `string` |
| `WorldSettlementSpecializationRegistry.StrictOnWire_str_` | `string` |
| `WorldTerrainCategoryRegistry` | `list[TerrainCategoryEntry]` |
| `WorldTerrainCategoryRegistry.DefaultWhenMissing_Union_str__NoneType__` | `string / null` |
| `WorldTerrainCategoryRegistry.DefaultWhenMissing_bool_` | `boolean` |
| `WorldTerrainCategoryRegistry.StrictOnWire_str_` | `string` |
| `WorldTerrainMasks` | `enabled: WorldTerrainMasks.DefaultWhenMissing_bool_`, `default_mountains: WorldTerrainMasks.DefaultWhenMissing_MountainsCategoryPolicy_`, `declared_mountains: WorldTerrainMasks.DefaultWhenMissing_list_Annotated_Union_MountainSpec__MountainRangeSpec___FieldInfo_annotation_NoneType__required_True__discriminator__entry_type_____`, `declared_regions: WorldTerrainMasks.DefaultWhenMissing_list_Annotated_Union_ForestSpec__PlainSpec__FarmlandSpec___FieldInfo_annotation_NoneType__required_True__discriminator__entry_type_____`, `default_landcover: WorldTerrainMasks.DefaultWhenMissing_LandcoverRegionsCategoryPolicy_`, `default_ravines: WorldTerrainMasks.DefaultWhenMissing_RavinesCategoryPolicy_`, `default_roads: WorldTerrainMasks.DefaultWhenMissing_RoadsCategoryPolicy_` |
| `WorldTerrainMasks.DefaultWhenMissing_LandcoverClaimNoise_` | `amplitude: WorldTerrainMasks.DefaultWhenMissing_int__Ge_ge_0_`, `scale: WorldTerrainMasks.DefaultWhenMissing_int__Gt_gt_0_` |
| `WorldTerrainMasks.DefaultWhenMissing_LandcoverRegionsCategoryPolicy_` | `enabled: WorldTerrainMasks.DefaultWhenMissing_bool_`, `autoresolve: WorldTerrainMasks.DefaultWhenMissing_bool_`, `transition_threshold: WorldTerrainMasks.DefaultWhenMissing_float__Gt_gt_0__Le_le_1___PydanticGeneralMetadata_allow_inf_nan_False_`, `seed_spacing: WorldTerrainMasks.StrictOnWire_int__Gt_gt_0_`, `max_radius: WorldTerrainMasks.DefaultWhenMissing_int__Gt_gt_0_`, `claim_noise: WorldTerrainMasks.DefaultWhenMissing_LandcoverClaimNoise_`, `fallback_terrain: WorldTerrainMasks.DefaultWhenMissing_TerrainKey_`, `terrain_policies: map[LandcoverTerrainPolicy]` |
| `WorldTerrainMasks.DefaultWhenMissing_MountainRangeSides_` | `left: ReliefSideSpec`, `right: ReliefSideSpec`, `start: ReliefSideSpec / null`, `end: ReliefSideSpec / null` |
| `WorldTerrainMasks.DefaultWhenMissing_MountainsCategoryPolicy_` | `enabled: WorldTerrainMasks.DefaultWhenMissing_bool_`, `autoresolve: WorldTerrainMasks.DefaultWhenMissing_bool_`, `system_terrain: WorldTerrainMasks.DefaultWhenMissing_str_`, `threshold: app__dataModel__annotationPolicy__DefaultWhenMissing_float__Ge_ge_0__0__Le_le_2__0_`, `elevation_bias_weight: app__dataModel__annotationPolicy__DefaultWhenMissing_float__Ge_ge_0__0_`, `relief_weight: app__dataModel__annotationPolicy__DefaultWhenMissing_float__Ge_ge_0__0_`, `ridge_cell_m: WorldTerrainMasks.DefaultWhenMissing_int__Ge_ge_1_`, `default_kind: WorldTerrainMasks.DefaultEnumWhenMissing_MountainKind_`, `default_form: MountainFormBySides / StarForm / PeakForm / PlateauForm`, `default_radius_m: WorldTerrainMasks.DefaultWhenMissing_int__Ge_ge_1_`, `sides: WorldTerrainMasks.DefaultWhenMissing_tuple_ReliefSideSpec__________`, `default_range_style: WorldTerrainMasks.DefaultEnumWhenMissing_MountainRangeStyle_`, `hybrid_smooth_edge_factor: app__dataModel__annotationPolicy__DefaultWhenMissing_float__Ge_ge_0__0_`, `range_gap_length_fraction: app__dataModel__annotationPolicy__DefaultWhenMissing_float__Ge_ge_0__0_`, `range_gap_height_factor: app__dataModel__annotationPolicy__DefaultWhenMissing_float__Ge_ge_0__0_`, `range_gap_spread: app__dataModel__annotationPolicy__DefaultWhenMissing_float__Ge_ge_1__0_`, `range_gap_other_radius_factor: app__dataModel__annotationPolicy__DefaultWhenMissing_float__Ge_ge_0__0_`, `enable_secondary_ridges: WorldTerrainMasks.DefaultWhenMissing_bool_` |
| `WorldTerrainMasks.DefaultWhenMissing_RavinesCategoryPolicy_` | `enabled: WorldTerrainMasks.DefaultWhenMissing_bool_`, `autoresolve: WorldTerrainMasks.DefaultWhenMissing_bool_`, `system_terrain: WorldTerrainMasks.DefaultWhenMissing_str_`, `min_drop: WorldTerrainMasks.DefaultWhenMissing_int__Ge_ge_1_`, `min_neighbors: WorldTerrainMasks.DefaultWhenMissing_int__Ge_ge_1_`, `drop_z: WorldTerrainMasks.DefaultWhenMissing_int__Ge_ge_1_` |
| `WorldTerrainMasks.DefaultWhenMissing_RoadsCategoryPolicy_` | `enabled: WorldTerrainMasks.DefaultWhenMissing_bool_`, `autoresolve: WorldTerrainMasks.DefaultWhenMissing_bool_`, `system_terrain: WorldTerrainMasks.DefaultWhenMissing_str_`, `connection_types: WorldTerrainMasks.DefaultWhenMissing_tuple_str__________`, `graph_levels: WorldTerrainMasks.DefaultWhenMissing_tuple_str__________`, `dilate_radius_light: WorldTerrainMasks.DefaultWhenMissing_int__Ge_ge_0_` |
| `WorldTerrainMasks.DefaultWhenMissing_TerrainKey_` | `string` |
| `WorldTerrainMasks.DefaultWhenMissing_Union_ObjectReliefPickPolicy__NoneType__` | `ObjectReliefPickPolicy / null` |
| `WorldTerrainMasks.DefaultWhenMissing_Union_ReliefContextPickPolicy__NoneType__` | `ReliefContextPickPolicy / null` |
| `WorldTerrainMasks.DefaultWhenMissing_Union_str__NoneType__` | `string / null` |
| `WorldTerrainMasks.DefaultWhenMissing_bool_` | `boolean` |
| `WorldTerrainMasks.DefaultWhenMissing_float_95_` | `number` |
| `WorldTerrainMasks.DefaultWhenMissing_float__Gt_gt_0__Le_le_1___PydanticGeneralMetadata_allow_inf_nan_False_` | `number` |
| `WorldTerrainMasks.DefaultWhenMissing_int__Ge_ge_0_` | `integer` |
| `WorldTerrainMasks.DefaultWhenMissing_int__Ge_ge_1_` | `integer` |
| `WorldTerrainMasks.DefaultWhenMissing_int__Ge_ge_3_` | `integer` |
| `WorldTerrainMasks.DefaultWhenMissing_int__Gt_gt_0_` | `integer` |
| `WorldTerrainMasks.DefaultWhenMissing_list_Annotated_Union_ForestSpec__PlainSpec__FarmlandSpec___FieldInfo_annotation_NoneType__required_True__discriminator__entry_type_____` | `list[ForestSpec / PlainSpec / FarmlandSpec]` |
| `WorldTerrainMasks.DefaultWhenMissing_list_Annotated_Union_MountainSpec__MountainRangeSpec___FieldInfo_annotation_NoneType__required_True__discriminator__entry_type_____` | `list[MountainSpec / MountainRangeSpec]` |
| `WorldTerrainMasks.DefaultWhenMissing_str_` | `string` |
| `WorldTerrainMasks.DefaultWhenMissing_tuple_HillShape__________` | `list[HillShape]` |
| `WorldTerrainMasks.DefaultWhenMissing_tuple_MountainSaddleSpec__________` | `list[MountainSaddleSpec]` |
| `WorldTerrainMasks.DefaultWhenMissing_tuple_MountainSpec__________` | `list[MountainSpec]` |
| `WorldTerrainMasks.DefaultWhenMissing_tuple_ReliefSideSpec__________` | `list[ReliefSideSpec]` |
| `WorldTerrainMasks.DefaultWhenMissing_tuple_int__________` | `list[integer]` |
| `WorldTerrainMasks.DefaultWhenMissing_tuple_str__________` | `list[string]` |
| `WorldTerrainMasks.HillPolicy` | `min_spacing: WorldTerrainMasks.DefaultWhenMissing_int__Ge_ge_1_`, `radius: WorldTerrainMasks.DefaultWhenMissing_int__Ge_ge_1_`, `height: WorldTerrainMasks.DefaultWhenMissing_int__Ge_ge_1_`, `shapes: WorldTerrainMasks.DefaultWhenMissing_tuple_HillShape__________` |
| `WorldTerrainMasks.StrictOnWire_int__Gt_gt_0_` | `integer` |
| `WorldTerrainRegistry` | `list[TerrainRegistryEntry]` |
| `WorldTerrainRegistry.DefaultEnumWhenMissing_Union_HydrologyCellRole__NoneType__` | `HydrologyCellRole / null` |
| `WorldTerrainRegistry.DefaultWhenMissing_Union_Annotated_int__FieldInfo_annotation_NoneType__required_True__metadata__Ge_ge_1______NoneType__` | `integer / null` |
| `WorldTerrainRegistry.DefaultWhenMissing_Union_HillPolicy__NoneType__` | `HillPolicy / null` |
| `WorldTerrainRegistry.DefaultWhenMissing_Union_Literal__plains____forest____NoneType__` | `string / null` |
| `WorldTerrainRegistry.DefaultWhenMissing_Union_float__NoneType__` | `number / null` |
| `WorldTerrainRegistry.DefaultWhenMissing_Union_str__NoneType__` | `string / null` |
| `WorldTerrainRegistry.DefaultWhenMissing_bool_` | `boolean` |
| `WorldTerrainRegistry.DefaultWhenMissing_float__Gt_gt_0___PydanticGeneralMetadata_allow_inf_nan_False_` | `number` |
| `WorldTerrainRegistry.DefaultWhenMissing_int_` | `integer` |
| `WorldTerrainRegistry.DefaultWhenMissing_int__Ge_ge_1_` | `integer` |
| `WorldTerrainRegistry.DefaultWhenMissing_list_EligibilityRule__` | `list[EligibilityRule]` |
| `WorldTerrainRegistry.DefaultWhenMissing_str_` | `string` |
| `WorldTerrainRegistry.DefaultWhenMissing_tuple_HillShape__________` | `list[HillShape]` |
| `WorldTerrainRegistry.DefaultWhenMissing_tuple_StrictEnumOnWire_TerrainFillRole___________` | `list[WorldTerrainRegistry.StrictEnumOnWire_TerrainFillRole_]` |
| `WorldTerrainRegistry.StrictOnWire_RegistryKey_WorldTerrainRegistry__` | `string` |
| `WorldTerrainRegistry.StrictOnWire_str_` | `string` |
| `WorldTerrainScalars` | `terrain_chunk_columns: WorldTerrainScalars.DefaultWhenMissing_int__Ge_ge_1_`, `terrain_parallel_workers: WorldTerrainScalars.DefaultWhenMissing_Union_int__NoneType__`, `map_subsurface_depth: WorldTerrainScalars.DefaultWhenMissing_int__Ge_ge_0_`, `z_min: WorldTerrainScalars.DefaultWhenMissing_Union_int__NoneType__`, `z_max: WorldTerrainScalars.DefaultWhenMissing_Union_int__NoneType__`, `elevation_lapse_rate: WorldTerrainScalars.DefaultWhenMissing_Union_float__NoneType__`, `g: WorldTerrainScalars.DefaultWhenMissing_float_0_`, `closed_planet_grid: WorldTerrainScalars.DefaultWhenMissing_bool_`, `world_topology_mode: WorldTerrainScalars.DefaultEnumWhenMissing_WorldTopologyMode_`, `magma_band_thickness: WorldTerrainScalars.DefaultWhenMissing_Union_int__NoneType__` |
| `WorldTerrainScalars.DefaultWhenMissing_Union_float__NoneType__` | `number / null` |
| `WorldTerrainScalars.DefaultWhenMissing_Union_int__NoneType__` | `integer / null` |
| `WorldTerrainScalars.DefaultWhenMissing_bool_` | `boolean` |
| `WorldTerrainScalars.DefaultWhenMissing_float_0_` | `number` |
| `WorldTerrainScalars.DefaultWhenMissing_int__Ge_ge_0_` | `integer` |
| `WorldTerrainScalars.DefaultWhenMissing_int__Ge_ge_1_` | `integer` |
| `WorldTransitionTypeRegistry` | `list[TransitionTypeEntry]` |
| `WorldTransitionTypeRegistry.DefaultWhenMissing_Union_str__NoneType__` | `string / null` |
| `WorldTransitionTypeRegistry.StrictOnWire_RegistryKey_WorldTransitionTypeRegistry__` | `string` |
| `WorldTransitionTypeRegistry.StrictOnWire_str_` | `string` |
| `WorldWeatherTypeRegistry` | `list[WeatherTypeEntry]` |
| `WorldWeatherTypeRegistry.DefaultWhenMissing_Union_int__NoneType__` | `integer / null` |
| `WorldWeatherTypeRegistry.DefaultWhenMissing_Union_str__NoneType__` | `string / null` |
| `WorldWeatherTypeRegistry.DefaultWhenMissing_dict_str__int__` | `map[integer]` |
| `WorldWeatherTypeRegistry.DefaultWhenMissing_float_0_` | `number` |
| `WorldWeatherTypeRegistry.DefaultWhenMissing_int__Ge_ge_1_` | `integer` |
| `WorldWeatherTypeRegistry.StrictOnWire_str_` | `string` |
| `app__dataModel__annotationPolicy__DefaultWhenMissing_float__Ge_ge_0__05__Le_le_1__0_` | `number` |
| `app__dataModel__annotationPolicy__DefaultWhenMissing_float__Ge_ge_0__0_` | `number` |
| `app__dataModel__annotationPolicy__DefaultWhenMissing_float__Ge_ge_0__0__Le_le_1__0_` | `number` |
| `app__dataModel__annotationPolicy__DefaultWhenMissing_float__Ge_ge_0__0__Le_le_2__0_` | `number` |
| `app__dataModel__annotationPolicy__DefaultWhenMissing_float__Ge_ge_1__0_` | `number` |
| `app__dataModel__annotationPolicy__DefaultWhenMissing_float__Gt_gt_0__0_` | `number` |

**Вердикт.** Покрытие полей хранилища и объявленных wire-схем проверено. До приёмки каждой DAG-связи нужно сопоставить фактический вход конкретной операции с выходом владельца, указать сохранённые presence/aliases и версию зависимостей. Для ключей вне строки World сначала доказать источник и round-trip. Для Climate поправка к C1: WorldClimateScalars объявляет девять полей, после переноса lapse их будет десять. Критерий приёмки — нода получает именно указанное значение, включая 0, false и разрешённый null, с выбранной публикации и передаёт его потребителю без подстановки другого default. Настройки процесса и параметры одного вызова остаются в отдельной таблице R4.
