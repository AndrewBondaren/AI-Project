# API-1 — Единая граница транспортного API

**Статус:** DRAFT / DEFERRED. Только архитектурный план, не разрешение на реализацию.
**Scope:** весь backend; целевое размещение транспортных endpoints — `backend/app/api/`.
**Связанные планы:** `gen-dag-1-post-geo-ws.md`, `world-domain-patches-snapshots.md`.

## Цель
Собрать все HTTP, WebSocket, SSE и debug endpoints и транспортную адаптацию в `backend/app/api/`. Не перемещать туда публичные Python API доменов, CRUD, алгоритмы, планирование или оркестрацию. Не создавать новую архитектуру исполнения.

## Обязательные границы
- Transport endpoints, маршруты, transport DTO, HTTP exception mapping и привязка transport dependencies принадлежат `backend/app/api/`. Composition root вправе подключать роутеры.
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
- Все transport endpoints backend находятся в `backend/app/api/` (исключения требуют явного утверждения).
- Нет transport-specific зависимостей из application/domain слоёв и нет оркестрации мира внутри маршрутов.
- Внешние контракты сохранены или изменения явно согласованы.
- Для каждого выявленного нарушения имеется решение и проверенная цепочка вызовов.

## Ограничения
API-1 не блокирует GEO-1 или GEN-DAG-1 целиком. Не менять GEO-1, DAG, доменный CRUD, PatchSet/Snapshot lifecycle или генераторные алгоритмы в рамках переноса. Реализация только после аудита, согласования реестра и отдельного разрешения мастера.


## Предварительная ревизия кода (2026-10-29; не полный аудит)

**Метод:** GitHub code search по `APIRouter`, `FastAPI`, `HTTPException`, `WebSocket`, `StreamingResponse` в `backend/app/` и выборочное чтение подозрительных файлов. Результаты поиска не доказывают полноту: динамическая регистрация, импорты, SSE, middleware и все фактические call chains ещё не проверены.

| Файл / область | Наблюдение | Решение для API-1 |
| --- | --- | --- |
| `backend/app/core/app.py` | **Подтверждено:** создаёт `FastAPI`, регистрирует routers, middleware/CORS и обработчики HTTP; одновременно владеет инфраструктурным lifespan, DB и container bootstrap | **Кандидат на разделение.** Перенести transport-specific factory/wiring в `backend/app/api/`, сохранить инфраструктурную инициализацию у надлежащего владельца; проверить импортные зависимости, ASGI entrypoint и совместимость |
| `backend/app/api/routes/*` | Найденные объявления `APIRouter` находятся в целевом каталоге | Оставить; проверить толщину handlers и наличие скрытой оркестрации |
| `backend/app/api/routes/chat.py` | Найден `StreamingResponse` в транспортном слое | Расположение корректно; дополнительно проверить SSE semantics |
| `backend/app/application/worldData/errors.py`, `worldBundle/errors.py`, `templateLibrary/packs/errors.py` | Упоминания FastAPI в комментариях; фактически обычные Python-исключения | **Не нарушение**, не переносить |
| `backend/app/application/templateLibrary/reliefTemplateLibraryService.py`, `structureTemplateLibraryService.py` | Поиск отметил упоминания FastAPI, но выборочно прочитанные фрагменты не выявили transport imports | Не объявлять нарушением без дальнейшей проверки |

**Промежуточный итог:** 1 подтверждённый кандидат на изменение границы — `core/app.py`; 0 найденных `APIRouter` вне `api/`. Это **не** утверждение, что других нарушений нет.

**Обязательная следующая проверка до имплементации:** инвентаризировать все импорты `fastapi`, `starlette`, `app.api` вне `api/`; определения HTTP/WebSocket/SSE endpoints, middleware и registration sites; выяснить, что в `core/app.py` является транспортом, а что инфраструктурным bootstrap. Составить полную карту `current → target` и отдельно согласовать перенос `core/app.py` без переноса доменной инициализации в API.
