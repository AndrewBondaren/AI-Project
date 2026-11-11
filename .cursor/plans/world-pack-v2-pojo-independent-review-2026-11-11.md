# Независимое ревью POJO World Pack V2

Дата: 2026-11-11. Связанный план: [spatial-distribution-domain.md §15.69](spatial-distribution-domain.md#1569-sp-p2w--сверка-границы-публикации-после-приёмки-read-пути).

## Область и статус проверки

Основа: текущие POJO, [ТЗ World Pack](../../docs/tz_world_pack_storage.md), §15.69 плана и [обязательные критерии приёмки](../rules/dag-generator-interface.mdc#обязательная-приёмка-плана-любого-домена). Проверка статическая; тесты, restart и GC-сценарии не выполнялись. Код и DAG-ноды не изменялись. Отчёт фиксирует выводы ревью, а не утверждает изменения контрактов или порядка реализации.

Предлагаемые preparation/read POJO не следует считать реализованными. Наличие WorldPackManifestV2 и finish_pack_preparation не означает реализации описанных prepare/read_part. Ссылки и номера строк ниже относятся к состоянию на дату проверки.

**Вердикт: контракты не готовы к приёмке для реализации; архитектурный gate остаётся открытым.**

## Находки P1/P2

### P1-1. Сохраняемый header включает режим операции

Источники: docs/tz_world_pack_storage.md:325, :479, :485.

PackVersionContents сохраняет assembly: PackAssemblyInput, содержащий request_mode. Header proof охватывает параметры вне коллекций. Требование V2 — сохранять происхождение неизменных данных независимо от текущей операции.

Контрпример: после full выполняется detailed без изменения сетки и других параметров версии. request_mode меняется, поэтому header нельзя целиком унаследовать со старым proof. История команды становится частью сохраняемого значения.

Минимальное исправление: исключить request_mode из сохраняемой assembly; получать режим операции из preparation scope. Общие effective параметры объявить один раз для входа и сохраняемого состава. last_l0_mode сохранить: у него иная семантика.

Критерий: detailed без изменения параметров сохраняет header value/proof базы; fingerprint операции учитывает scope.

### P1-2. Scope не содержит конкретных доказательств области и полноты

Источники: docs/tz_world_pack_storage.md:355, :360, :376.

Location UID не определяет materialized chunks и допустимые fine-climate tiles. Wilderness tiles не доказывают ожидаемое покрытие chunks. Отсутствие concrete evidence признано документом.

Контрпример: одинаковое число chunks при разных координатах; summary/status complete не выявляет неправильный набор. Требования V2 к coverage и запрету изменений вне scope не проверяемы по представленным полям.

Минимальное исправление: завершить producer-owned immutable coverage/policy evidence и передачу через DAG. Не переносить planner в Pack.

Критерий: неверные координаты, пропущенный chunk, лишний district и изменение вне scope отклоняются; незатронутые данные и proofs сохраняются.

### P1-3. Durable provenance не закрыт конкретным внешним контрактом

Источники: docs/tz_world_pack_storage.md:295, :487, :489.

Capture, входной и durable proof остаются незакрытыми внешними типами. Нельзя проверить сериализацию, dependency closure, удержания и независимость от временного capture. Это блокер проекта, а не доказанная ошибка работающего V2 runtime.

Минимальное исправление: согласовать типы и codec Source, состав удерживаемых refs и проверяющий контракт.

Критерий: после удаления доступа к запросу, освобождения temporary holds и старой версии, затем restart новая версия читает унаследованные данные и proofs.

### P2-1. PackPreparationIdentity повторяет смысловое тело входа

Источники: docs/tz_world_pack_storage.md:295, :493.

Исключение operation_id и fingerprint оправдывает canonical projection, но не независимую декларацию семи одинаковых полей и правил. Контрпример: новое смысловое поле добавляется во вход, но не в identity; разные запросы получают одинаковый fingerprint.

Минимальное исправление: единая декларация смыслового тела либо зарегистрированная canonical projection существующей модели. Identity не должна независимо заполняться как второй источник истины.

Критерий: изменение каждого смыслового поля меняет digest; перестановки множеств его не меняют.

### P2-2. registry_hash и location z_band перенесены без завершённой семантики

Источники: docs/tz_world_pack_storage.md:327, :339; backend/app/dataModel/worldPack/meta/worldPackManifest.py:87, :103; backend/app/application/worldData/pack/read/packFineTerrainReadFacade.py:145.

По поиску в backend/app registry_hash имеет только декларацию manifest. У location z_band есть reader, но смысл строкового значения не обоснован. Числовой ParentLightRefinePolicy.z_band — другой факт.

Минимальное исправление: определить producer, смысл, единицы, условия отсутствия и consumer либо согласовать исключение с миграцией. Не выводить значение из похожего policy-поля.

Критерий: воспроизводимый producer→storage→reader round-trip; отсутствие не заменяется придуманным default.

### P1-4. Binding сохраняемого состава и миграция readers остаются открытыми

Источники: docs/tz_world_pack_storage.md:485, :491; backend/app/application/worldData/pack/encoding/packManifestCodec.py; backend/app/dataModel/worldPack/meta/worldPackManifest.py.

Текущий manifest содержит path/hash и climate/spatial refs. Проект вводит authoritative PackVersionContents, но inline/ref и storage version ещё не выбраны. Текущий codec кодирует manifest, не предложенный contents. Без cutover остаётся риск двух независимо изменяемых представлений одного факта.

Минимальное исправление: зафиксировать binding и карту миграции readers. Старые индексы удалить из целевого пути либо сделать проверяемыми производными contents.

Критерий: противоречивые refs/индексы отвергаются; альтернативное чтение V2 через старый path отсутствует; encode→storage→restart→decode восстанавливает состав и provenance.

## Трассировка типов

| Предложенный POJO | Требование V2 / данные и инварианты | Существующая модель | Различие назначения / минимальное решение | Критерий проверки |
|---|---|---|---|---|
| PackTileAddress | Macro адрес gx/gy | PackTileRef | Прямой дубль, уже исключён проектом | Новый alias-класс отсутствует |
| PackChunkAssembly | cx/cy/refine_role без storage fields | ChunkRef | Metadata-проекция; общая декларация полей | Единые constraints и сохранение chunk proof |
| PackTileAssembly | gx/gy, состояния, индекс chunks | TileManifestEntry | Общие metadata, отдельные refs | Status согласован с составом |
| PackLocationAssembly | UID, inclusive fine-grid volume, climate metadata | LocationTerrainEntry | Общая metadata; z_band требует решения | Единицы и round-trip совпадают |
| PackSettlementAssembly | UID, volume, status, districts | SettlementStructureEntry | Общая metadata; уникальные immutable districts | Неверное district coverage отклоняется |
| PackPinnedReadIdentity | Execution/invocation/pin/publication | ManifestPinRead, внутренний PinIntent | Общая identity; budget у запроса, DB intent внутренний | Подмена pin/publication отвергается |
| PackAssemblyInput | Effective параметры и индексы | Manifest, grid/resolution settings | Authored override не равен resolved value; единые constraints | Captured effective значения, без defaults Pack |
| PackL0PreparationScope | Ожидаемый набор, подтверждённый capture | PackTilePlan | Scope не копирует planner result; нужны cap/evidence | Capped selection не выдаётся за полное покрытие |
| Location/Wilderness scope | Разрешённая область результата | DetailedBakeRequest | Request выбирает работу, scope ограничивает результат | Вне scope значения и proofs неизменны |
| PackPreparationIdentity | Canonical digest смыслового входа | PackPreparationInput | Общая декларация или canonical projection | Векторы изменения каждого поля |
| PackPartInput | Admission address/ref/new-or-inherited proof | ArtifactRef, spatial root descriptor | Новая связывающая оболочка оправданна | Адрес, формат, ref и proof согласованы |
| PackStoredPart | Восстановление без запроса | PackPartInput | Иной lifecycle: durable proof без new/inherited | Restart без temporary capture |
| Coverage records | Expected/actual адреса и источник | PackCompletenessSnapshot | Новые evidence; summary не доказательство | Неверный набор при равном количестве отклоняется |
| PackPartReadContract | Идентичность typed read schema | CacheContract, ArtifactFormatContract | Отдельный read descriptor оправдан | Неверный T не меняет зарегистрированный decoder |
| PackPartReadContractRegistry | Перечень read schemas | Cache registry | Публичный metadata registry пока не обязателен: consumer не предъявлен | Предъявлен конкретный потребитель |
| PackPartReadBinding | Format/version/payload/decoder | Artifact/cache bindings | Внутренняя реализация | Нет executable объектов в публичном POJO |
| PackPartReadBudget | IO-лимиты запроса | PackReadPolicy | Новый: LRU retention не IO budget | Ограничение bytes до декодирования |
| PackVersionContents | Единственный authoritative состав | WorldPackManifestV2 | Предпочтительна эволюция существующего manifest; отдельный объект хранения не обоснован | Все readers используют один состав |
| Assembly provenance/address records | Происхождение metadata | Подтверждённого аналога нет | Новые; chunk proof отдельно от tile | Обновление A сохраняет proof B |
| PackStoredProvenance | Durable source/dependency identity | Внешний Source proof | Pack-оболочка допустима, proof принадлежит Source | Closure удерживается новой версией |
| Preparation errors/issues | Типизированный отказ admission | FieldPathError | Специализация carrier без копии path/message machinery | Стабильные codes/paths и порядок issues |

## Переиспользование, единицы, неизменность и сериализация

Macro gx/gy, локальные chunk cx/cy и inclusive fine-grid XYZ — разные координатные пространства. Одинаковые числовые поля не обосновывают объединение типов. WorldGridSettings требует минимум и кратность 1000; положительного int недостаточно. TerritoryVolume уже предоставляет нормализацию bounds и STRICT_BOUNDS; второй AABB не нужен.

PackTilePlan.tiles, manifest collections и packed_district_uids содержат списки. Frozen верхнего объекта не даёт глубокой неизменности. Следует эволюционировать owning модели и admission с проверкой callers/serialization, а не создавать V2 payload только ради tuple/strict/frozen.

ArtifactRef описывает физическое содержимое, logical address — его использование, payload — данные владельца, provenance — источник и зависимости. Они не дубли только из-за повторяющихся идентификаторов, если соответствие проверяется и один факт не изменяется независимо в двух местах. Metadata не должны повторять path/hash/bytes из refs. Spatial root format validation должна иметь единую декларацию.

PackPartInput и PackStoredPart имеют действительно разный lifecycle: admission зависит от capture/base, durable descriptor обязан пережить их освобождение. Объединять их ценой сохранения относительного new/inherited нельзя.

CacheContract владеет namespace/schema кэша; ArtifactFormatContract — storage format и executable codec/backend binding; PackPartReadContract — typed read schema. Универсальный registry не требуется. Необходимость отдельного публичного списка read metadata ещё не доказана.

## Явные решения

### Уточнение: полный состав внутри WorldPackManifestV2

Повторно проверены worldPackManifest.py, packManifestCodec.py, manifestFormat.py и pinnedManifestReader.py. Ответственность существующего manifest уже охватывает состав версии: world_uid, параметры сетки, индексы terrain/settlement/tiles, spatial roots и climate refs. Поэтому полный состав (адреса частей, ArtifactRef, durable provenance частей и метаданных) семантически можно разместить непосредственно в эволюционирующем WorldPackManifestV2. Новой самостоятельной ответственности хранения для PackVersionContents не установлено. Ранее приведённая возможность отдельного contents не означает необходимости нового POJO или отдельного артефакта.

Предпочтительный вариант для дальнейшего проектирования — один authoritative WorldPackManifestV2 с полным составом. Вложенные records допустимы для отдельных ответственностей, но отдельный агрегат PackVersionContents, отдельный ref, holder и дополнительное чтение не вводить без доказанной необходимости. Конкретная раскладка полей ещё не утверждена. Нельзя просто добавить parts рядом с независимо изменяемыми climate/spatial refs и path/hash индексами: факты должны иметь одну декларацию и одно authoritative представление; оставшиеся проекции вычисляются или проверяются.

Это не готовность текущего класса к такому использованию. Сейчас WorldPackManifestV2 — strict admission поверх общих _ManifestFields. decode_manifest после admission преобразует его в WorldPackManifest; encode_candidate_manifest требует exact WorldPackManifest. Добавленные только в V2 поля рискуют потеряться при таком преобразовании из-за extra="ignore" общего класса. Следовательно, до реализации требуется согласованная эволюция модели и всего encode/decode/read пути, без потери полного состава и provenance. Списки и отсутствие глубокой неизменности также остаются предметом доработки существующей модели.

Manifest format сейчас принимает bounded bytes и проверяет их через decode_manifest; pinned reader уже читает один manifest ArtifactRef. В проверенном пути не найдено требования к отдельному contents artifact. Возможность уложиться в byte budget не доказана: объём durable proofs ещё неизвестен, нужны измерения репрезентативного полного состава. Превышение бюджета потребует отдельного решения, а не автоматического введения второго объекта хранения.

Критерии проверки варианта: полный состав переживает encode→storage→restart→decode без потери полей; ref и provenance незатронутого chunk сохраняются при partial refine; все readers и retention closure используют тот же состав; противоречивые дубли отвергаются; размер проверен против явно заданного бюджета.

**Выбор формата, storage/schema version и политика прежних bytes остаются OPEN.** Эта проверка не выбирает JSON/TLV, не разрешает молчаливую смену зарегистрированного формата и не устанавливает миграцию, перекодирование, удаление или обязательную поддержку прежних bytes. Находка P1-4 остаётся открытой как вопрос binding и consumers, но не является аргументом за второй объект хранения.

- **Удалить из проекта:** отдельный PackTileAddress; независимую копию декларации PackPreparationIdentity; request_mode из сохраняемой assembly. Это рекомендации, не выполненные изменения.
- **Переиспользовать:** ArtifactRef, WorldPublicationRef, PackTileRef, TerritoryVolume, WildernessRegionEntry, существующие enums и owning payload schemas.
- **Доработать:** admission и вложенную неизменность существующих payload/metadata, scope evidence, codecs и consumers contents.
- **Выделить общую часть:** metadata четырёх manifest entries, pin identity, effective grid constraints, смысловое тело preparation.
- **Оставить новыми:** preparation/stored provenance, coverage evidence, resolved scopes, logical part addresses, read input/result/budget и минимальный read descriptor.
- **Не считать обоснованными обязательными полями/сущностями:** публичный read registry, registry_hash и location z_band в предложенной форме.

## Границы, DAG и непроверенные зависимости

В проектных сигнатурах preparation/read codec, backend, lease, fence и CommitScope не вынесены наружу. PackPartReadBinding описан как внутренний. Публичные metadata registry и executable registry — не одно и то же.

Существующий finish_pack_preparation принимает lease/stager/staging и не является готовой публичной границей prepare. Его наличие не доказывает завершённость нового контракта.

Не закрыты или не проверены полностью:

1. Конкретные Source capture/proof, codec и retention closure: внешние типы остаются OPEN.
2. Producer bindings coverage и grade sidecars: concrete контракты остаются OPEN.
3. Полный транзитивный маршрут DAG→prepare/activate/read_part и вложенные междоменные вызовы: полного аудита всех callers нет.
4. Все activation/publication transaction, recovery и GC callers: сквозные сценарии не выполнялись.
5. Serialization и callers каждого переиспользуемого payload: полной проверки всех моделей нет.
6. CRUD данных и настроек, включая update/delete: отдельная матрица не закрыта.
7. Runtime partial refine, restart, replay и release старой версии: тесты не запускались.

Отсутствие скрытой оркестрации и прямых междоменных вызовов не подтверждено. Документ сохраняет L2→settlement materialization, но полное соответствие фактического маршрута этому порядку не установлено. Roster новых классов описан в ТЗ, однако полный набор ответственностей, допустимых зависимостей, эффектов и критериев каждого задействованного существующего класса не проверен.

По обязательным критериям проекта недостающих сведений достаточно для отказа в приёмке. Требования V2 к durable provenance, coverage и partial refine нельзя ослаблять ради reuse V1. Сначала закрыть указанные контрактные зависимости и противоречия, затем повторить приёмку; этот отчёт не разрешает реализацию или изменение утверждённого порядка действий.
