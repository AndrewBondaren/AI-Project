# Cache — публичные контракты данных и настроек

Владелец — домен Cache. Домен передаёт в GEN-DAG принятые контракты. Текущий статус OPEN. [Норматив Cache PC-0](../../docs/tz_terrain_generation.md#surface-planningcache--норматив-pc-0-2026-10-23)

**Cache V1 / AS-IS — binding передаёт caller.** Конкретный владелец — `app.application.cache.service.cacheService.CacheService`. Действующие синхронные методы: `get[T](binding: CacheBinding[T], key: CacheKey[T]) -> CacheLookup[T]`, `put[T](binding: CacheBinding[T], entry: CacheEntry[T]) -> CacheAdmission`, `evict[T](binding: CacheBinding[T], key: CacheKey[T]) -> None`. У get два результата: CacheHit с точными key/value и CacheMiss. Put добавляет либо заменяет запись по тому же ключу; STORED и SKIPPED_OVERSIZE штатны. Evict удаляет точный ключ. Для пути чтения/заполнения нужны get/put. CacheFailure имеет причины CONTRACT_MISMATCH, INVALID_PAYLOAD, BACKEND_FAILURE; конвертация ошибки в miss нарушает контракт. Источники: [норматив общего sync API](../../docs/tz_terrain_generation.md), [ключ](../../backend/app/dataModel/cache/identity/cacheKey.py), [entry и admission](../../backend/app/dataModel/cache/contracts/cacheEntry.py), [lookup](../../backend/app/dataModel/cache/contracts/cacheLookup.py), [реализация CacheService](../../backend/app/application/cache/service/cacheService.py).

**Ограничение архитектурной границы.** В целевом контракте composition root регистрирует binding внутри Cache. DAG передаёт ключ или запись. По потоку данных передаются только POJO ключа, записи и результата; registry, codec, worker, storage guard и backend не являются выходами доменных операций. Действующий get/put вызывает codec.validate; put также вызывает retained_bytes. Для Pack предусмотреть чистый codec bytes, для планов проверить каждый зарегистрированный envelope binding. Допускаются локальная проверка immutable schema и расчёт размера. Callback, выполняющий расчёт плана, проверку pin, чтение хранилища, повтор или обращение к другому домену, блокирует перенос такого binding. [Методы CachePayloadCodec](../../backend/app/application/cache/contracts/cacheBackend.py) · [Pack: точные входы и результаты](../../docs/tz_world_pack_storage.md#контракты-чтения-manifest-через-cache--проект-для-приёмки-владельцами)

| Ответственный за поведение | Допустимые зависимости и эффекты | Проверка / основание отклонить перенос |
|---|---|---|
| CacheBinding[T] | Неизменяемая пара из CacheContract[T] и CachePayloadCodec[T], которую предоставляет composition root. Контракт описывает namespace через id и schema_version; полезное значение хранится в CacheEntry[T].value. Binding связывает описание с кодеком, без вычислений и IO. | Проверить конкретную регистрацию: тип значения кодека согласован с T выбранного контракта. Подстановка кодека чужой схемы или появление в binding выбора операции — основание отклонить регистрацию. [Binding](../../backend/app/application/cache/contracts/cacheBackend.py) · [Метаданные](../../backend/app/dataModel/cache/contracts/cacheContract.py) · [Запись](../../backend/app/dataModel/cache/contracts/cacheEntry.py) |
| CachePayloadCodec[T] | Внутренний типизированный Protocol. Конкретный кодек реализует validate(value: object) → T, encode, decode и retained_bytes. На RAM-пути get при hit и put сервис использует validate, при put также retained_bytes. Допустимы локальные операции над значением и его схемой. | Проверить каждую реализацию на корректном и повреждённом значении; при put оценка размера должна быть целым неотрицательным числом. Вызов provider, Pack IO или DAG из кодека отклоняет binding. [Контракт кодека](../../backend/app/application/cache/contracts/cacheBackend.py) |
| CacheService | Проверяет соответствие ключа контракту binding и целостность возвращённой записи, применяет кодек и CachePolicy, обращается к CacheBackend. Get возвращает CacheLookup, put изменяет кэш при STORED либо возвращает SKIPPED_OVERSIZE. | Несовпадение контракта ключа даёт CONTRACT_MISMATCH до вызова backend; отклонённое кодеком значение даёт INVALID_PAYLOAD и при put не записывается. Превращение такого отказа в miss или запуск доменного расчёта нарушают ответственность сервиса. [Реализация](../../backend/app/application/cache/service/cacheService.py) |
| MemoryCache и CachePolicy | Адрес из namespace/version/item key, учёт памяти, LRU, лимит одной записи. | Oversize возвращает SKIPPED_OVERSIZE, вычисленный результат доступен caller. Решения о пересчёте или допуске pin внутри backend запрещены. |

**Обязательная CRUD-приёмка по AGENTS.md.** Для Cache обязательны восемь отдельных проверок. Для каждой предъявить путь к модулю, конкретный публичный Python-класс и полную сигнатуру метода, модули и имена конкретных POJO входа, результата и доменной ошибки в `backend/app/dataModel/`. Для настроек дополнительно показать участие именованной модели настроек в каждой операции. План отклоняется при отсутствии этих сведений. Приёмка домена целиком требует реализации и проверки всех восьми контрактов. [Обязательный критерий](../rules/dag-generator-interface.mdc#конкретность-публичного-crud-контракта)

| Объект | Операция | Текущее свидетельство и пробел для приёмки |
|---|---|---|
| Данные | Запись | CacheService.put принимает CacheEntry и возвращает CacheAdmission; проверить создание новой записи, исход oversize и полный набор POJO. |
| Данные | Чтение | CacheService.get возвращает CacheLookup с hit/miss; требуется конкретный POJO доменной ошибки. |
| Данные | Обновление | Backend заменяет запись при put; отдельный публичный метод обновления с полным контрактом пока не предъявлен. |
| Данные | Удаление | CacheService.evict удаляет по ключу и возвращает None; публичный POJO результата и ошибки не предъявлен. |
| Настройки | Запись | CachePolicy передаётся при сборке; публичный метод записи и его контракт не предъявлены. |
| Настройки | Чтение | Наличие CachePolicy в DI не подтверждает публичный метод чтения и его контракт. |
| Настройки | Обновление | Требуются конкретный публичный метод, типизированный контракт и проверка применения обновлённой политики. |
| Настройки | Удаление | Требуются конкретный публичный метод, типизированный контракт и определённый результат удаления политики. |

**Статус доменной приёмки Cache — OPEN.** Срез get/put и проверка ответственности отдельных классов не закрывают полный CRUD. Источники текущего поведения: [CacheService](../../backend/app/application/cache/service/cacheService.py), [MemoryCache](../../backend/app/application/cache/backends/memoryCache.py), [CachePolicy](../../backend/app/dataModel/cache/policy/cachePolicy.py), [сборка в контейнере](../../backend/app/core/container/worldData.py).

### Обязательная приёмка удаления Cache V1

V1 здесь означает API Cache с явным binding и прежний путь get_or_build → Cache. После переноса всех callers предъявить инвентарь использований в application, DI, workers, debug, scripts и tests, diff удаления и проверки через публичный API. В итоговом коде отсутствуют мёртвые V1-методы, импорты, регистрации, adapters, прежние overload/fallback и дублирующие маршруты чтения/записи. Для каждого сохранённого общего компонента (включая CacheBinding, codec и RAM backend) показать действующий целевой caller. При наличии хотя бы одного остаточного или параллельного пути приёмка отклоняется. Проверить hit, miss, ошибочную версию до backend и единственную запись результата через DAG. Метки `LEGACY REMOVE(CACHE-V1-BINDING)` снять вместе с переходом, после проверки каждого места. [V1 API](../../backend/app/application/cache/service/cacheService.py) · [V1 callers](../../backend/app/application/planning/service/planningService.py) · [Порядок перехода](./gen-dag-1-post-geo-ws.md)

### Открытые замечания Cache

| Статус | Замечание | Условие закрытия |
|---|---|---|
| Решение принято; реализация OPEN | Владелец выбора кодека — Cache. DAG передаёт CacheKey при чтении/удалении и CacheEntry при записи. | Cache разрешает зарегистрированный binding по contract.id и проверяет точное совпадение schema_version. Неизвестный id или версия дают типизированный CONTRACT_MISMATCH до обращения к backend. Реестр метаданных сегодня обеспечивает уникальность id и не хранит кодеки. [Ключ](../../backend/app/dataModel/cache/identity/cacheKey.py) · [Реестр метаданных](../../backend/app/dataModel/cache/contracts/cacheContract.py) |
| OPEN | Доменная ошибка Cache. Вызов _failure(CONTRACT_MISMATCH, ...) воспроизводимо даёт TypeError при создании базового FieldPathError. | Предъявить конкретный тип диагностики Cache и проверить через публичные методы причины CONTRACT_MISMATCH, INVALID_PAYLOAD и BACKEND_FAILURE. [Конструктор ошибки](../../backend/app/application/cache/service/cacheService.py) · [Требование конкретного подкласса](../../backend/app/dataModel/validation/diagnostics/fieldPathError.py) |
| OPEN | Атрибуция SKIPPED_OVERSIZE. Штатный исход возвращает CacheService.put; прямой oversized put в MemoryCache даёт ValueError. CachePolicy описывает лимиты. | Разнести три ответственности в критериях и проверить результат public put и защиту backend раздельно. [Backend](../../backend/app/application/cache/backends/memoryCache.py) |

**CRUD — восемь самостоятельных открытых пунктов.** Для каждой строки действуют требования к классу, модулю, полной сигнатуре и POJO из матрицы выше.

| Статус | Объект и операция | Что предъявить |
|---|---|---|
| OPEN | Данные — запись | Публичный контракт создания записи, результат admission и типизированный отказ. |
| OPEN | Данные — чтение | Полный контракт get, различимые hit, miss и доменный отказ. |
| OPEN | Данные — обновление | Явный публичный метод обновления, семантика отсутствующего ключа и результат замены. |
| OPEN | Данные — удаление | Публичный метод с POJO результата и ошибки; определить результат повторного удаления. |
| OPEN | Настройки — запись | Публичный метод записи CachePolicy, POJO входа, результата и ошибки. |
| OPEN | Настройки — чтение | Публичный метод чтения действующей CachePolicy и его POJO. |
| OPEN | Настройки — обновление | Публичный метод и проверяемый эффект применения новых лимитов. |
| OPEN | Настройки — удаление | Публичный метод, POJO и определённое состояние политики после удаления. |
